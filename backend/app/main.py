from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Set
from pydantic import BaseModel, EmailStr, validator
import logging
import sqlite3
import json
import os
import asyncio
import aiohttp
import ssl
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from .services.currency_service import currency_service
from .services.price_service import PriceService
from .dependencies.auth import get_current_active_user, get_db_connection
from .utils.auth import verify_password, get_password_hash, create_access_token, create_refresh_token, generate_reset_token
from .core.config import settings

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Database file - resolve to absolute path
import os
# Get the project root directory (parent of backend directory)
current_file = os.path.abspath(__file__)  # /path/to/backend/app/main.py
backend_dir = os.path.dirname(os.path.dirname(current_file))  # /path/to/backend
project_root = os.path.dirname(backend_dir)  # /path/to/project
DB_FILE = os.path.join(project_root, settings.database_file)

# Initialize services
price_service = PriceService()

# WebSocket connection management
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.price_subscribers: Dict[str, Set[WebSocket]] = {}
        self.alert_subscribers: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        # Remove from price subscribers
        for symbol, subscribers in self.price_subscribers.items():
            subscribers.discard(websocket)
        
        # Remove from alert subscribers
        self.alert_subscribers.discard(websocket)
        
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections.copy():
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting message: {e}")
                self.disconnect(connection)

    async def send_price_update(self, symbol: str, price: float):
        current_time = datetime.now(timezone.utc)
        message = json.dumps({
            "type": "price_update",
            "data": {
                "symbol": symbol,
                "price": price,
                "timestamp": current_time.isoformat(),
                "timestamp_formatted": current_time.strftime("%Y-%m-%d %H:%M:%S UTC")
            }
        })
        
        # Send to subscribers of this symbol
        if symbol in self.price_subscribers:
            for connection in self.price_subscribers[symbol].copy():
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(f"Error sending price update: {e}")
                    self.disconnect(connection)

    async def broadcast_price_update(self, symbol: str, price: float):
        """Broadcast price update to all subscribers of this symbol"""
        await self.send_price_update(symbol, price)

    async def send_alert_triggered(self, alert_data: dict):
        message = json.dumps({
            "type": "alert_triggered",
            "data": {
                "alert": alert_data,
                "timestamp": datetime.now().isoformat()
            }
        })
        
        # Send to alert subscribers
        for connection in self.alert_subscribers.copy():
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error sending alert: {e}")
                self.disconnect(connection)

    def subscribe_to_prices(self, websocket: WebSocket, symbols: List[str]):
        for symbol in symbols:
            if symbol not in self.price_subscribers:
                self.price_subscribers[symbol] = set()
            self.price_subscribers[symbol].add(websocket)
        logger.info(f"Subscribed to price updates for: {symbols}")

    def subscribe_to_alerts(self, websocket: WebSocket):
        self.alert_subscribers.add(websocket)
        logger.info("Subscribed to alert notifications")

manager = ConnectionManager()

# Background price fetching
async def fetch_prices_for_symbols(symbols: List[str]):
    """Fetch prices for symbols and broadcast updates"""
    try:
        # Ensure currency rates are initialized before any conversions
        currency_service.ensure_rates_initialized()
        
        prices = await price_service.get_current_prices(symbols)
        
        # Update database with new prices
        if prices:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            for symbol, price in prices.items():
                # Get the base currency for this symbol from the database
                cursor.execute("SELECT DISTINCT base_currency FROM portfolio_items WHERE symbol = ?", (symbol,))
                base_currencies = cursor.fetchall()
                
                for base_currency_row in base_currencies:
                    base_currency = base_currency_row[0]
                    
                    # Convert USD price to the base currency if needed
                    if base_currency != "USD":
                        converted_price = currency_service.convert_amount(price, "USD", base_currency)
                    else:
                        converted_price = price
                    
                    # Update current_price for all items with this symbol and base currency
                    cursor.execute("""
                        UPDATE portfolio_items 
                        SET current_price = ?, 
                            current_value = amount * ?,
                            updated_at = datetime('now')
                        WHERE symbol = ? AND base_currency = ?
                    """, (converted_price, converted_price, symbol, base_currency))
                
                # Calculate P&L for each item
                cursor.execute("""
                    SELECT id, amount, price_buy, commission, base_currency FROM portfolio_items 
                    WHERE symbol = ?
                """, (symbol,))
                
                items = cursor.fetchall()
                for item_id, amount, price_buy, commission, base_currency in items:
                    # Convert USD price to the item's base currency if needed
                    if base_currency != "USD":
                        converted_price = currency_service.convert_amount(price, "USD", base_currency)
                    else:
                        converted_price = price
                    
                    current_value = amount * converted_price
                    total_investment = (amount * price_buy) + commission
                    pnl = current_value - total_investment
                    pnl_percent = (pnl / total_investment * 100) if total_investment > 0 else 0
                    
                    cursor.execute("""
                        UPDATE portfolio_items 
                        SET current_value = ?, pnl = ?, pnl_percent = ?
                        WHERE id = ?
                    """, (current_value, pnl, pnl_percent, item_id))
            
            conn.commit()
            conn.close()
            
            # Broadcast updates via WebSocket
            for symbol, price in prices.items():
                await manager.broadcast_price_update(symbol, price)
            
            # Check and trigger alerts
            await check_and_trigger_alerts(prices)
                
        logger.info(f"Fetched and updated prices for {len(prices)} symbols")
    except Exception as e:
        logger.error(f"Error fetching prices: {e}")

async def background_price_fetcher():
    """Background task to periodically fetch prices"""
    while True:
        try:
            # Get all symbols that have subscribers
            all_symbols = list(manager.price_subscribers.keys())
            if all_symbols:
                await fetch_prices_for_symbols(all_symbols)
                logger.info(f"Fetched prices for {len(all_symbols)} symbols")
            else:
                logger.debug("No symbols to fetch prices for")
        except Exception as e:
            logger.error(f"Error in background price fetcher: {e}")
        
        # Wait 30 seconds before next fetch
        await asyncio.sleep(30)

async def background_currency_fetcher():
    """Background task to periodically fetch currency rates"""
    while True:
        try:
            await currency_service.refresh_rates()
            logger.info("Currency rates refreshed")
        except Exception as e:
            logger.error(f"Error refreshing currency rates: {e}")
        
        # Wait 30 minutes before next fetch
        await asyncio.sleep(1800)

async def send_telegram_notification(message: str):
    """Send notification to Telegram bot"""
    try:
        telegram_token = os.getenv('TELEGRAM_TOKEN')
        telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not telegram_token or not telegram_chat_id:
            logger.warning("Telegram credentials not found in environment variables")
            return False
            
        url = f"{settings.telegram_api_url}{telegram_token}/sendMessage"
        data = {
            "chat_id": telegram_chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        
        # Create SSL context that doesn't verify certificates (for development)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    logger.info(f"Telegram notification sent successfully: {message[:50]}...")
                    return True
                else:
                    response_text = await response.text()
                    logger.error(f"Failed to send Telegram notification: {response.status} - {response_text}")
                    return False
                    
    except Exception as e:
        logger.error(f"Error sending Telegram notification: {e}")
        return False

def get_user_telegram_credentials(user_id: int) -> Optional[dict]:
    """Get user's personal Telegram credentials from database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT telegram_bot_token, telegram_chat_id FROM users WHERE id = ?", 
            (user_id,)
        )
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0] and result[1]:
            return {
                'bot_token': result[0],
                'chat_id': result[1]
            }
        return None
    except Exception as e:
        logger.error(f"Error getting user Telegram credentials: {e}")
        return None

async def send_telegram_notification_with_credentials(message: str, bot_token: str, chat_id: str):
    """Send notification to Telegram bot using specific credentials"""
    try:
        url = f"{settings.telegram_api_url}{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        
        # Create SSL context that doesn't verify certificates (for development)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    logger.info(f"Telegram notification sent successfully: {message[:50]}...")
                    return True
                else:
                    response_text = await response.text()
                    logger.error(f"Failed to send Telegram notification: {response.status} - {response_text}")
                    return False
                    
    except Exception as e:
        logger.error(f"Error sending Telegram notification: {e}")
        return False

async def send_user_telegram_notification(user_id: int, message: str):
    """Send Telegram notification using user-specific credentials with .env fallback"""
    try:
        # Try to get user's personal Telegram credentials
        user_credentials = get_user_telegram_credentials(user_id)
        
        if user_credentials and user_credentials['bot_token'] and user_credentials['chat_id']:
            # Use user's personal settings
            logger.info(f"Using user-specific Telegram credentials for user {user_id}")
            return await send_telegram_notification_with_credentials(
                message, 
                user_credentials['bot_token'], 
                user_credentials['chat_id']
            )
        else:
            # Fall back to global .env settings
            logger.info(f"Using global Telegram credentials for user {user_id} (no user settings)")
            return await send_telegram_notification(message)  # Uses .env
            
    except Exception as e:
        logger.error(f"Error sending Telegram notification for user {user_id}: {e}")
        return False

async def check_and_trigger_alerts(current_prices: Dict[str, float]):
    """Check all active alerts against current prices and trigger notifications"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all active alerts
        cursor.execute("SELECT * FROM alerts WHERE is_active = 1")
        alerts = cursor.fetchall()
        
        triggered_alerts = []
        
        for alert in alerts:
            alert_id, user_id, symbol, threshold_price, alert_type, message, is_active, created_at = alert
            
            if symbol not in current_prices:
                continue
                
            current_price = current_prices[symbol]
            should_trigger = False
            
            # Check if alert should trigger
            if alert_type == 'ABOVE' and current_price >= threshold_price:
                should_trigger = True
            elif alert_type == 'BELOW' and current_price <= threshold_price:
                should_trigger = True
                
            if should_trigger:
                # Get portfolio information for this symbol
                # First, get all base currencies for this symbol
                cursor.execute("""
                    SELECT DISTINCT base_currency 
                    FROM portfolio_items 
                    WHERE symbol = ? AND base_currency IS NOT NULL
                """, (symbol,))
                
                base_currencies = [row[0] for row in cursor.fetchall()]
                portfolio_data = []
                
                # Calculate portfolio data for each base currency
                for base_currency in base_currencies:
                    # Convert USD price to base currency
                    if base_currency != "USD":
                        converted_price = currency_service.convert_amount(current_price, "USD", base_currency)
                    else:
                        converted_price = current_price
                    
                    # Get portfolio data for this base currency
                    cursor.execute("""
                        SELECT 
                            SUM(amount) as total_amount,
                            SUM(amount * price_buy + commission) as total_investment,
                            SUM(amount * ?) as current_value,
                            base_currency
                        FROM portfolio_items 
                        WHERE symbol = ? AND base_currency = ?
                        GROUP BY base_currency
                    """, (converted_price, symbol, base_currency))
                    
                    result = cursor.fetchone()
                    if result:
                        portfolio_data.append(result)
                
                # Log alert history
                cursor.execute('''
                    INSERT INTO alert_history 
                    (alert_id, user_id, symbol, triggered_price, triggered_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (alert_id, user_id, symbol, current_price, datetime.now().isoformat() + "Z"))
                
                # Deactivate the alert
                cursor.execute("UPDATE alerts SET is_active = 0 WHERE id = ?", (alert_id,))
                
                # Prepare enhanced notification message
                alert_message = f"🚨 <b>Price Alert Triggered!</b>\n\n"
                alert_message += f"📈 <b>Symbol:</b> {symbol}\n"
                alert_message += f"💰 <b>Current Price:</b> ${current_price:,.2f}\n"
                alert_message += f"🎯 <b>Threshold:</b> ${threshold_price:,.2f} ({alert_type})\n"
                
                # Add portfolio information if available
                if portfolio_data:
                    for total_amount, total_investment, current_value, base_currency in portfolio_data:
                        if total_amount > 0:
                            pnl = current_value - total_investment
                            pnl_percent = (pnl / total_investment * 100) if total_investment > 0 else 0
                            
                            alert_message += f"\n💼 <b>Portfolio Summary ({base_currency}):</b>\n"
                            alert_message += f"📊 <b>Amount:</b> {total_amount:,.6f} {symbol}\n"
                            alert_message += f"💵 <b>Original Investment:</b> {base_currency} {total_investment:,.2f}\n"
                            alert_message += f"💎 <b>Current Value:</b> {base_currency} {current_value:,.2f}\n"
                            alert_message += f"📈 <b>P&L:</b> {base_currency} {pnl:,.2f} ({pnl_percent:+.2f}%)\n"
                
                if message:
                    alert_message += f"\n💬 <b>Alert Message:</b> {message}\n"
                alert_message += f"\n⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                
                triggered_alerts.append({
                    'alert_id': alert_id,
                    'symbol': symbol,
                    'current_price': current_price,
                    'threshold_price': threshold_price,
                    'alert_type': alert_type,
                    'message': message,
                    'notification_message': alert_message
                })
        
        conn.commit()
        conn.close()
        
        # Send Telegram notifications for triggered alerts
        for alert_data in triggered_alerts:
            await send_user_telegram_notification(user_id, alert_data['notification_message'])
            
            # Broadcast alert triggered via WebSocket
            await manager.send_alert_triggered(alert_data)
            
        if triggered_alerts:
            logger.info(f"Triggered {len(triggered_alerts)} alerts")
            
    except Exception as e:
        logger.error(f"Error checking alerts: {e}")

# Pydantic models
class PortfolioItem(BaseModel):
    id: int
    symbol: str
    amount: float
    price_buy: float
    purchase_date: Optional[str] = None
    base_currency: str
    purchase_price_eur: Optional[float] = None
    purchase_price_czk: Optional[float] = None
    source: Optional[str] = None
    commission: float = 0.0
    total_investment_text: Optional[str] = None
    created_at: str
    updated_at: str
    current_price: Optional[float] = None
    current_value: Optional[float] = None
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None

    class Config:
        json_encoders = {
            float: lambda v: round(v, 8) if v is not None else None
        }

class PortfolioCreate(BaseModel):
    symbol: str
    amount: float
    price_buy: float
    purchase_date: Optional[str] = None
    base_currency: str
    source: Optional[str] = None
    commission: float = 0.0
    total_investment_text: Optional[str] = None

    class Config:
        json_encoders = {
            float: lambda v: round(v, 8) if v is not None else None
        }

class PortfolioUpdate(BaseModel):
    symbol: Optional[str] = None
    amount: Optional[float] = None
    price_buy: Optional[float] = None
    purchase_date: Optional[str] = None
    base_currency: Optional[str] = None
    source: Optional[str] = None
    commission: Optional[float] = None
    total_investment_text: Optional[str] = None

    class Config:
        json_encoders = {
            float: lambda v: round(v, 8) if v is not None else None
        }

class PriceAlert(BaseModel):
    id: int
    symbol: str
    threshold_price: float
    alert_type: str
    message: Optional[str] = None
    is_active: bool = True
    created_at: str

class PriceAlertCreate(BaseModel):
    symbol: str
    threshold_price: float
    alert_type: str
    message: Optional[str] = None

class PriceAlertUpdate(BaseModel):
    symbol: Optional[str] = None
    threshold_price: Optional[float] = None
    alert_type: Optional[str] = None
    message: Optional[str] = None
    is_active: Optional[bool] = None

class TrackedSymbol(BaseModel):
    symbol: str
    name: str
    active: bool = True
    last_updated: str

# Authentication Models
class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v

    @validator('username')
    def validate_username(cls, v):
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters')
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: Optional[str]
    preferred_currency: str
    is_active: bool
    created_at: str
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v

class UserProfileUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    preferred_currency: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

    @validator('username')
    def validate_username(cls, v):
        if v is not None:
            if len(v) < 3:
                raise ValueError('Username must be at least 3 characters')
        return v

    @validator('preferred_currency')
    def validate_preferred_currency(cls, v):
        if v is not None:
            if v not in ['USD', 'EUR', 'CZK']:
                raise ValueError('Preferred currency must be USD, EUR, or CZK')
        return v

    @validator('telegram_bot_token')
    def validate_telegram_bot_token(cls, v):
        if v is not None and v.strip():
            # Basic validation for Telegram bot token format
            if not v.startswith(('1', '2', '3', '4', '5', '6', '7', '8', '9')) or ':' not in v:
                raise ValueError('Invalid Telegram bot token format. Should be like: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz')
        return v.strip() if v else ''

    @validator('telegram_chat_id')
    def validate_telegram_chat_id(cls, v):
        if v is not None and v.strip():
            # Basic validation for Telegram chat ID format (should be numeric)
            if not v.strip().isdigit():
                raise ValueError('Invalid Telegram chat ID format. Should be a numeric value like: 123456789')
        return v.strip() if v else ''

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v

class AccountDeletionConfirm(BaseModel):
    confirmation_text: str = "DELETE"
    
    @validator('confirmation_text')
    def validate_confirmation(cls, v):
        if v != "DELETE":
            raise ValueError('Confirmation text must be exactly "DELETE"')
        return v

def init_database():
    """Initialize SQLite database with user management tables"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            full_name TEXT,
            preferred_currency TEXT DEFAULT 'USD',
            is_active BOOLEAN DEFAULT 1,
            is_verified BOOLEAN DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')

    # Create password reset tokens table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TEXT NOT NULL,
            used BOOLEAN DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Create user sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Create portfolio table with user_id
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfolio_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            amount REAL NOT NULL,
            price_buy REAL NOT NULL,
            purchase_date TEXT,
            base_currency TEXT NOT NULL,
            purchase_price_eur REAL,
            purchase_price_czk REAL,
            source TEXT,
            commission REAL DEFAULT 0.0,
            total_investment_text TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            current_price REAL,
            current_value REAL,
            pnl REAL,
            pnl_percent REAL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Create alerts table with user_id
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            threshold_price REAL NOT NULL,
            alert_type TEXT NOT NULL,
            message TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Create tracked_symbols table with user_id
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tracked_symbols (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            active BOOLEAN DEFAULT 1,
            last_updated TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, symbol)
        )
    ''')

    # Create alert_history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alert_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            triggered_price REAL NOT NULL,
            triggered_at TEXT NOT NULL,
            FOREIGN KEY (alert_id) REFERENCES alerts (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Add preferred_currency column to existing users table if it doesn't exist
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN preferred_currency TEXT DEFAULT 'USD'")
        logger.info("✅ Added preferred_currency column to users table")
    except sqlite3.OperationalError:
        # Column already exists, ignore
        pass
    
    # Add telegram_bot_token column to existing users table if it doesn't exist
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN telegram_bot_token TEXT")
        logger.info("✅ Added telegram_bot_token column to users table")
    except sqlite3.OperationalError:
        # Column already exists, ignore
        pass
    
    # Add telegram_chat_id column to existing users table if it doesn't exist
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN telegram_chat_id TEXT")
        logger.info("✅ Added telegram_chat_id column to users table")
    except sqlite3.OperationalError:
        # Column already exists, ignore
        pass
    
    # Add symbol column to existing alert_history table if it doesn't exist
    try:
        cursor.execute("ALTER TABLE alert_history ADD COLUMN symbol TEXT")
        logger.info("✅ Added symbol column to alert_history table")
    except sqlite3.OperationalError:
        # Column already exists, ignore
        pass
    
    conn.commit()
    conn.close()
    logger.info("✅ Database initialized with user management")

def load_migration_data():
    """Load data from migration file if it exists"""
    migration_file = "data_migration.json"
    if os.path.exists(migration_file):
        try:
            with open(migration_file, 'r') as f:
                data = json.load(f)
            
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            
            # Insert portfolio items
            for item in data.get('portfolio_items', []):
                cursor.execute('''
                    INSERT OR REPLACE INTO portfolio_items 
                    (id, symbol, amount, price_buy, purchase_date, base_currency, 
                     purchase_price_eur, purchase_price_czk, source, commission, 
                     total_investment_text, created_at, updated_at, current_price, 
                     current_value, pnl, pnl_percent)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    item['id'], item['symbol'], item['amount'], item['price_buy'],
                    item['purchase_date'], item['base_currency'], item['purchase_price_eur'],
                    item['purchase_price_czk'], item['source'], item['commission'],
                    item['total_investment_text'], item['created_at'], item['updated_at'],
                    item['current_price'], item['current_value'], item['pnl'], item['pnl_percent']
                ))
            
            # Insert alerts
            for alert in data.get('alerts', []):
                cursor.execute('''
                    INSERT OR REPLACE INTO alerts 
                    (id, symbol, threshold_price, alert_type, message, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    alert['id'], alert['symbol'], alert['threshold_price'],
                    alert['alert_type'], alert.get('message'), alert.get('is_active', True),
                    alert['created_at']
                ))
            
            # Insert tracked symbols
            for symbol in data.get('tracked_symbols', []):
                cursor.execute('''
                    INSERT OR REPLACE INTO tracked_symbols 
                    (symbol, name, active, last_updated)
                    VALUES (?, ?, ?, ?)
                ''', (
                    symbol['symbol'], symbol['name'], symbol['active'], symbol['last_updated']
                ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Migrated {len(data.get('portfolio_items', []))} portfolio items")
            logger.info(f"✅ Migrated {len(data.get('alerts', []))} alerts")
            logger.info(f"✅ Migrated {len(data.get('tracked_symbols', []))} tracked symbols")
            
            # Remove migration file after successful migration
            os.remove(migration_file)
            logger.info("✅ Migration file removed")
            
        except Exception as e:
            logger.error(f"Error loading migration data: {e}")

def get_db_connection():
    """Get database connection"""
    return sqlite3.connect(DB_FILE)

def format_total_investment_text(amount: float, currency: str) -> str:
    """Format total investment text with proper currency symbol"""
    if not amount or amount == 0:
        return f"0 {currency}"
    
    # Format number with commas for thousands
    formatted_amount = f"{amount:,.0f}" if amount >= 1 else f"{amount:.8f}".rstrip('0').rstrip('.')
    
    # Add currency symbol
    currency_symbols = {
        "USD": "$",
        "EUR": "€", 
        "CZK": "Kč",
        "GBP": "£",
        "JPY": "¥"
    }
    
    symbol = currency_symbols.get(currency, currency)
    return f"{symbol}{formatted_amount}" if symbol in ["$", "€", "£", "¥"] else f"{formatted_amount} {symbol}"

def convert_portfolio_item(item: dict, target_currency: str) -> dict:
    """Convert a portfolio item to target currency"""
    if item["base_currency"] == target_currency:
        # Ensure total_investment_text is properly formatted even without conversion
        if not item.get("total_investment_text") or not any(symbol in item.get("total_investment_text", "") for symbol in ["$", "€", "Kč", "£", "¥"]):
            total_investment = (item["amount"] * item["price_buy"]) + item.get("commission", 0)
            item["total_investment_text"] = format_total_investment_text(total_investment, target_currency)
        return item

    try:
        # Convert price_buy
        converted_price_buy = currency_service.convert_amount(
            item["price_buy"], item["base_currency"], target_currency
        )
        
        # Convert current_price
        converted_current_price = currency_service.convert_amount(
            item.get("current_price", 0), item["base_currency"], target_currency
        ) if item.get("current_price") else None
        
        # Convert current_value - FIXED: Don't convert if already in target currency
        if item.get("current_value") and item["base_currency"] == target_currency:
            converted_current_value = item.get("current_value")
        else:
            converted_current_value = currency_service.convert_amount(
                item.get("current_value", 0), item["base_currency"], target_currency
            ) if item.get("current_value") else None
        
        # Convert pnl - FIXED: Don't convert if already in target currency
        if item.get("pnl") and item["base_currency"] == target_currency:
            converted_pnl = item.get("pnl")
        else:
            converted_pnl = currency_service.convert_amount(
                item.get("pnl", 0), item["base_currency"], target_currency
            ) if item.get("pnl") else None
        
        # Convert commission
        converted_commission = currency_service.convert_amount(
            item.get("commission", 0), item["base_currency"], target_currency
        ) if item.get("commission") else 0.0

        # Calculate total investment in target currency
        total_investment = (item["amount"] * converted_price_buy) + converted_commission
        
        return {
            **item,
            "base_currency": target_currency,
            "price_buy": round(converted_price_buy, 8),
            "current_price": round(converted_current_price, 8) if converted_current_price else None,
            "current_value": round(converted_current_value, 8) if converted_current_value else None,
            "pnl": round(converted_pnl, 8) if converted_pnl else None,
            "commission": round(converted_commission, 8),
            "total_investment_text": format_total_investment_text(total_investment, target_currency)
        }
    except Exception as e:
        logger.error(f"Currency conversion error: {e}")
        return item


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Starting Crypto AI Agent API v2.0 (SQLite Mode)")
    
    # Initialize database
    init_database()
    logger.info("✅ Database initialized")
    
    # Load migration data if exists
    load_migration_data()
    
    # Initialize currency service
    await currency_service.get_exchange_rates()
    logger.info("✅ Currency service initialized")
    
    # Start background price update task
    price_task = asyncio.create_task(background_price_fetcher())
    logger.info("✅ Price update task started")
    
    # Start background currency update task
    currency_task = asyncio.create_task(background_currency_fetcher())
    logger.info("✅ Currency update task started")
    
    yield
    
    # Shutdown
    price_task.cancel()
    currency_task.cancel()
    logger.info("🛑 Shutting down Crypto AI Agent API v2.0")

# Create FastAPI app
app = FastAPI(
    title="Crypto AI Agent API",
    description="Advanced cryptocurrency portfolio management API",
    version="2.0.0",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Authentication endpoints
@app.post("/api/auth/register", response_model=TokenResponse)
async def register(user_data: UserCreate):
    """Register a new user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if email or username already exists
    cursor.execute("SELECT id FROM users WHERE email = ? OR username = ?", (user_data.email, user_data.username))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Email or username already registered")
    
    # Hash password
    hashed_password = get_password_hash(user_data.password)
    
    # Create user
    now = datetime.now().isoformat() + "Z"
    cursor.execute('''
        INSERT INTO users (email, username, hashed_password, full_name, is_active, is_verified, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_data.email, user_data.username, hashed_password, user_data.full_name, True, False, now, now))
    
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # Generate tokens
    access_token = create_access_token(data={"sub": str(user_id)})
    refresh_token = create_refresh_token(data={"sub": str(user_id)})
    
    # Return user data and tokens
    user_response = UserResponse(
        id=user_id,
        email=user_data.email,
        username=user_data.username,
        full_name=user_data.full_name,
        preferred_currency='USD',  # Default for new users
        is_active=True,
        created_at=now
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user_response
    )

@app.post("/api/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    """Login user with email and password"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get user by email
    cursor.execute("SELECT id, email, username, hashed_password, full_name, preferred_currency, is_active, created_at FROM users WHERE email = ?", (credentials.email,))
    user = cursor.fetchone()
    conn.close()
    
    if not user or not verify_password(credentials.password, user[3]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user[6]:  # is_active
        raise HTTPException(status_code=400, detail="Inactive user")
    
    # Generate tokens
    access_token = create_access_token(data={"sub": str(user[0])})
    refresh_token = create_refresh_token(data={"sub": str(user[0])})
    
    # Return user data and tokens
    user_response = UserResponse(
        id=user[0],
        email=user[1],
        username=user[2],
        full_name=user[4],
        preferred_currency=user[5],
        is_active=user[6],
        created_at=user[7]
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user_response
    )

@app.post("/api/auth/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str = None):
    """Refresh access token using refresh token"""
    if not refresh_token:
        raise HTTPException(status_code=400, detail="Refresh token required")
    
    # Decode refresh token
    from backend.app.utils.auth import decode_token
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    # Get user
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, username, full_name, preferred_currency, is_active, created_at FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user or not user[5]:  # is_active
        raise HTTPException(status_code=401, detail="User not found or inactive")
    
    # Generate new tokens
    access_token = create_access_token(data={"sub": str(user_id)})
    new_refresh_token = create_refresh_token(data={"sub": str(user_id)})
    
    # Return user data and tokens
    user_response = UserResponse(
        id=user[0],
        email=user[1],
        username=user[2],
        full_name=user[3],
        preferred_currency=user[4],
        is_active=user[5],
        created_at=user[6]
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        user=user_response
    )

@app.get("/api/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_active_user)):
    """Get current user information"""
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        username=current_user["username"],
        full_name=current_user["full_name"],
        preferred_currency=current_user["preferred_currency"],
        is_active=current_user["is_active"],
        created_at=current_user["created_at"],
        telegram_bot_token=current_user.get("telegram_bot_token"),
        telegram_chat_id=current_user.get("telegram_chat_id")
    )

@app.put("/api/auth/profile", response_model=UserResponse)
async def update_profile(update_data: UserProfileUpdate, current_user: dict = Depends(get_current_active_user)):
    """Update user profile"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if email or username already exists (excluding current user)
    if update_data.email or update_data.username:
        email_check = update_data.email or current_user["email"]
        username_check = update_data.username or current_user["username"]
        cursor.execute("SELECT id FROM users WHERE (email = ? OR username = ?) AND id != ?", 
                      (email_check, username_check, current_user["id"]))
        if cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=400, detail="Email or username already in use")
    
    # Update fields
    update_fields = []
    update_values = []
    
    if update_data.email is not None:
        update_fields.append("email = ?")
        update_values.append(update_data.email)
    if update_data.username is not None:
        update_fields.append("username = ?")
        update_values.append(update_data.username)
    if update_data.full_name is not None:
        update_fields.append("full_name = ?")
        update_values.append(update_data.full_name)
    if update_data.preferred_currency is not None:
        update_fields.append("preferred_currency = ?")
        update_values.append(update_data.preferred_currency)
    if update_data.telegram_bot_token is not None:
        update_fields.append("telegram_bot_token = ?")
        update_values.append(update_data.telegram_bot_token)
    if update_data.telegram_chat_id is not None:
        update_fields.append("telegram_chat_id = ?")
        update_values.append(update_data.telegram_chat_id)
    
    if update_fields:
        update_fields.append("updated_at = ?")
        update_values.append(datetime.now().isoformat() + "Z")
        update_values.append(current_user["id"])
        
        cursor.execute(f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?", update_values)
        conn.commit()
    
    # Get updated user
    cursor.execute("SELECT id, email, username, full_name, preferred_currency, is_active, created_at, telegram_bot_token, telegram_chat_id FROM users WHERE id = ?", (current_user["id"],))
    user = cursor.fetchone()
    conn.close()
    
    return UserResponse(
        id=user[0],
        email=user[1],
        username=user[2],
        full_name=user[3],
        preferred_currency=user[4],
        is_active=user[5],
        created_at=user[6],
        telegram_bot_token=user[7],
        telegram_chat_id=user[8]
    )

@app.post("/api/auth/change-password")
async def change_password(password_change: PasswordChange, current_user: dict = Depends(get_current_active_user)):
    """Change user password"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get current password hash
    cursor.execute("SELECT hashed_password FROM users WHERE id = ?", (current_user["id"],))
    user = cursor.fetchone()
    
    if not user or not verify_password(password_change.current_password, user[0]):
        conn.close()
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    # Update password
    new_hashed_password = get_password_hash(password_change.new_password)
    cursor.execute("UPDATE users SET hashed_password = ?, updated_at = ? WHERE id = ?", 
                  (new_hashed_password, datetime.now().isoformat() + "Z", current_user["id"]))
    conn.commit()
    conn.close()
    
    return {"message": "Password changed successfully"}

@app.post("/api/auth/test-telegram")
async def test_telegram_connection(current_user: dict = Depends(get_current_active_user)):
    """Test Telegram connection for current user"""
    try:
        test_message = f"🧪 <b>Test Message</b>\n\nHello {current_user['username']}! This is a test message from your Crypto AI Agent.\n\n✅ Your Telegram integration is working correctly!"
        
        success = await send_user_telegram_notification(current_user["id"], test_message)
        
        if success:
            return {"message": "Telegram test message sent successfully!", "success": True}
        else:
            return {"message": "Failed to send Telegram test message. Please check your credentials.", "success": False}
            
    except Exception as e:
        logger.error(f"Error testing Telegram connection for user {current_user['id']}: {e}")
        return {"message": f"Error testing Telegram connection: {str(e)}", "success": False}

@app.post("/api/auth/password-reset-request")
async def request_password_reset(request: PasswordResetRequest):
    """Request password reset (logs token to console)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get user by email
    cursor.execute("SELECT id FROM users WHERE email = ?", (request.email,))
    user = cursor.fetchone()
    
    if user:
        # Generate reset token
        reset_token = generate_reset_token()
        expires_at = (datetime.now() + timedelta(hours=1)).isoformat() + "Z"
        now = datetime.now().isoformat() + "Z"
        
        # Store reset token
        cursor.execute('''
            INSERT INTO password_reset_tokens (user_id, token, expires_at, used, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (user[0], reset_token, expires_at, False, now))
        conn.commit()
        
        # Log token to console (for development)
        logger.info(f"Password reset token for {request.email}: {reset_token}")
        logger.info(f"Token expires at: {expires_at}")
    
    conn.close()
    
    # Always return success to prevent email enumeration
    return {"message": "If the email exists, a password reset token has been generated. Check the server logs for the token."}

@app.post("/api/auth/password-reset-confirm")
async def confirm_password_reset(confirm: PasswordResetConfirm):
    """Confirm password reset with token"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get reset token
    cursor.execute('''
        SELECT user_id, expires_at, used FROM password_reset_tokens 
        WHERE token = ? AND used = 0
    ''', (confirm.token,))
    token_data = cursor.fetchone()
    
    if not token_data:
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    
    user_id, expires_at, used = token_data
    
    # Check if token is expired
    if datetime.now() > datetime.fromisoformat(expires_at.replace('Z', '+00:00')):
        conn.close()
        raise HTTPException(status_code=400, detail="Reset token has expired")
    
    # Update password
    new_hashed_password = get_password_hash(confirm.new_password)
    cursor.execute("UPDATE users SET hashed_password = ?, updated_at = ? WHERE id = ?", 
                  (new_hashed_password, datetime.now().isoformat() + "Z", user_id))
    
    # Mark token as used
    cursor.execute("UPDATE password_reset_tokens SET used = 1 WHERE token = ?", (confirm.token,))
    
    conn.commit()
    conn.close()
    
    return {"message": "Password reset successfully"}

@app.delete("/api/auth/delete-account")
async def delete_account(confirmation: AccountDeletionConfirm, current_user: dict = Depends(get_current_active_user)):
    """Delete user account and all associated data"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    user_id = current_user["id"]
    
    try:
        # Delete all user-related data in the correct order to respect foreign key constraints
        
        # 1. Delete alert history
        cursor.execute("DELETE FROM alert_history WHERE user_id = ?", (user_id,))
        
        # 2. Delete alerts
        cursor.execute("DELETE FROM alerts WHERE user_id = ?", (user_id,))
        
        # 3. Delete tracked symbols
        cursor.execute("DELETE FROM tracked_symbols WHERE user_id = ?", (user_id,))
        
        # 4. Delete portfolio items
        cursor.execute("DELETE FROM portfolio_items WHERE user_id = ?", (user_id,))
        
        # 5. Delete password reset tokens
        cursor.execute("DELETE FROM password_reset_tokens WHERE user_id = ?", (user_id,))
        
        # 6. Delete user sessions
        cursor.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
        
        # 7. Finally, delete the user account
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"User account {user_id} ({current_user['email']}) has been permanently deleted")
        
        return {"message": "Account deleted successfully"}
        
    except Exception as e:
        conn.rollback()
        conn.close()
        logger.error(f"Error deleting account for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete account")

# Portfolio endpoints
@app.get("/api/portfolio/", response_model=List[PortfolioItem])
async def get_portfolio(currency: str = "USD", current_user: dict = Depends(get_current_active_user)):
    """Get all portfolio items converted to target currency"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM portfolio_items WHERE user_id = ? ORDER BY created_at DESC", (current_user["id"],))
    rows = cursor.fetchall()
    conn.close()
    
    # Convert to dict format
    items = []
    for row in rows:
        item = {
            "id": row[0],           # id
            "user_id": row[1],      # user_id
            "symbol": row[2],       # symbol
            "amount": row[3],       # amount
            "price_buy": row[4],    # price_buy
            "purchase_date": row[5], # purchase_date
            "base_currency": row[6], # base_currency
            "purchase_price_eur": row[7], # purchase_price_eur
            "purchase_price_czk": row[8],  # purchase_price_czk
            "source": row[9],              # source
            "commission": row[10],         # commission
            "total_investment_text": row[11], # total_investment_text
            "created_at": row[12],         # created_at
            "updated_at": row[13],         # updated_at
            "current_price": row[14],      # current_price
            "current_value": row[15],      # current_value
            "pnl": row[16],                # pnl
            "pnl_percent": row[17]         # pnl_percent
        }
        
        # Convert currency if needed
        converted_item = convert_portfolio_item(item, currency)
        items.append(converted_item)
    
    return items

@app.get("/api/portfolio/summary")
async def get_portfolio_summary(currency: str = "USD", current_user: dict = Depends(get_current_active_user)):
    """Get portfolio summary converted to target currency"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM portfolio_items WHERE user_id = ?", (current_user["id"],))
    rows = cursor.fetchall()
    conn.close()
    
    total_value = 0
    total_pnl = 0
    total_investment = 0
    
    for row in rows:
        item = {
            "base_currency": row[6],    # base_currency
            "current_value": row[15],   # current_value
            "pnl": row[16],             # pnl
            "amount": row[3],           # amount
            "price_buy": row[4],        # price_buy
            "commission": row[10]       # commission
        }
        
        # Convert to target currency
        converted_item = convert_portfolio_item(item, currency)
        
        total_value += converted_item["current_value"] or 0
        total_pnl += converted_item["pnl"] or 0
        total_investment += (converted_item["amount"] * converted_item["price_buy"] + converted_item["commission"])
    
    total_pnl_percent = (total_pnl / total_investment * 100) if total_investment > 0 else 0
    item_count = len(rows)
    
    return {
        "total_value": round(total_value, 8),
        "total_invested": round(total_investment, 8),
        "total_pnl": round(total_pnl, 8),
        "total_pnl_percent": round(total_pnl_percent, 8),
        "currency": currency,
        "item_count": item_count
    }

@app.post("/api/portfolio/", response_model=PortfolioItem)
async def create_portfolio_item(item: PortfolioCreate, current_user: dict = Depends(get_current_active_user)):
    """Create a new portfolio item"""
    # Validate numeric fields to prevent database corruption
    if not isinstance(item.amount, (int, float)) or item.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be a positive number")
    if not isinstance(item.price_buy, (int, float)) or item.price_buy <= 0:
        raise HTTPException(status_code=400, detail="Price must be a positive number")
    if not isinstance(item.commission, (int, float)) or item.commission < 0:
        raise HTTPException(status_code=400, detail="Commission must be a non-negative number")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat() + "Z"
    
    # Format total investment text if not provided or improperly formatted
    total_investment = (item.amount * item.price_buy) + item.commission
    formatted_total_investment = item.total_investment_text
    if not formatted_total_investment or not any(symbol in formatted_total_investment for symbol in ["$", "€", "Kč", "£", "¥"]):
        formatted_total_investment = format_total_investment_text(total_investment, item.base_currency)
    
    cursor.execute('''
        INSERT INTO portfolio_items 
        (user_id, symbol, amount, price_buy, purchase_date, base_currency, source, commission, 
         total_investment_text, created_at, updated_at, current_price, current_value, pnl, pnl_percent)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        current_user["id"], item.symbol, item.amount, item.price_buy, item.purchase_date, item.base_currency,
        item.source, item.commission, formatted_total_investment, now, now,
        round(item.price_buy, 8), round(item.amount * item.price_buy, 8), 0.0, 0.0
    ))
    
    item_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # Return the created item - frontend will handle price refresh
    return PortfolioItem(
        id=item_id,
        symbol=item.symbol,
        amount=item.amount,
        price_buy=item.price_buy,
        purchase_date=item.purchase_date,
        base_currency=item.base_currency,
        source=item.source,
        commission=item.commission,
        total_investment_text=formatted_total_investment,
        created_at=now,
        updated_at=now,
        current_price=round(item.price_buy, 8),
        current_value=round(item.amount * item.price_buy, 8),
        pnl=0.0,
        pnl_percent=0.0
    )

@app.put("/api/portfolio/{item_id}", response_model=PortfolioItem)
async def update_portfolio_item(item_id: int, item: PortfolioUpdate, current_user: dict = Depends(get_current_active_user)):
    """Update a portfolio item"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get existing item and verify ownership
    cursor.execute("SELECT * FROM portfolio_items WHERE id = ? AND user_id = ?", (item_id, current_user["id"]))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Portfolio item not found")
    
    # Update only provided fields
    update_fields = []
    update_values = []
    
    if item.symbol is not None:
        update_fields.append("symbol = ?")
        update_values.append(item.symbol)
    if item.amount is not None:
        update_fields.append("amount = ?")
        update_values.append(item.amount)
    if item.price_buy is not None:
        update_fields.append("price_buy = ?")
        update_values.append(item.price_buy)
    if item.purchase_date is not None:
        update_fields.append("purchase_date = ?")
        update_values.append(item.purchase_date)
    if item.base_currency is not None:
        update_fields.append("base_currency = ?")
        update_values.append(item.base_currency)
    if item.source is not None:
        update_fields.append("source = ?")
        update_values.append(item.source)
    if item.commission is not None:
        update_fields.append("commission = ?")
        update_values.append(item.commission)
    if item.total_investment_text is not None:
        update_fields.append("total_investment_text = ?")
        update_values.append(item.total_investment_text)
    
    if update_fields:
        # If total_investment_text is being updated, ensure it's properly formatted
        if "total_investment_text" in [field.split(" = ")[0] for field in update_fields]:
            total_investment_text_idx = None
            for i, field in enumerate(update_fields):
                if field.startswith("total_investment_text = ?"):
                    total_investment_text_idx = i
                    break
            
            if total_investment_text_idx is not None:
                total_investment_text = update_values[total_investment_text_idx]
                if not total_investment_text or not any(symbol in total_investment_text for symbol in ["$", "€", "Kč", "£", "¥"]):
                    # Get current item data to calculate proper total investment
                    cursor.execute("SELECT amount, price_buy, commission, base_currency FROM portfolio_items WHERE id = ?", (item_id,))
                    current_data = cursor.fetchone()
                    if current_data:
                        amount, price_buy, commission, base_currency = current_data
                        total_investment = (amount * price_buy) + commission
                        update_values[total_investment_text_idx] = format_total_investment_text(total_investment, base_currency)
        
        update_fields.append("updated_at = ?")
        update_values.append(datetime.now().isoformat() + "Z")
        update_values.append(item_id)
        
        cursor.execute(f'''
            UPDATE portfolio_items 
            SET {', '.join(update_fields)}
            WHERE id = ?
        ''', update_values)
        
        conn.commit()
    
    conn.close()
    
    # Return updated item
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM portfolio_items WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    conn.close()
    
    return PortfolioItem(
        id=row[0], symbol=row[1], amount=row[2], price_buy=row[3],
        purchase_date=row[4], base_currency=row[5], purchase_price_eur=row[6],
        purchase_price_czk=row[7], source=row[8], commission=row[9],
        total_investment_text=row[10], created_at=row[11], updated_at=row[12],
        current_price=row[13], current_value=row[14], pnl=row[15], pnl_percent=row[16]
    )

@app.delete("/api/portfolio/{item_id}")
async def delete_portfolio_item(item_id: int, current_user: dict = Depends(get_current_active_user)):
    """Delete a portfolio item"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM portfolio_items WHERE id = ? AND user_id = ?", (item_id, current_user["id"]))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Portfolio item not found")
    
    return {"message": "Portfolio item deleted successfully"}

# Alerts endpoints
@app.get("/api/alerts/", response_model=List[PriceAlert])
async def get_alerts(active_only: bool = False, current_user: dict = Depends(get_current_active_user)):
    """Get all alerts"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if active_only:
        cursor.execute("SELECT * FROM alerts WHERE user_id = ? AND is_active = 1 ORDER BY created_at DESC", (current_user["id"],))
    else:
        cursor.execute("SELECT * FROM alerts WHERE user_id = ? ORDER BY created_at DESC", (current_user["id"],))
    
    rows = cursor.fetchall()
    conn.close()
    
    alerts = []
    for row in rows:
        alerts.append(PriceAlert(
            id=row[0], symbol=row[2], threshold_price=row[3],
            alert_type=row[4], message=row[5], is_active=bool(row[6]),
            created_at=row[7]
        ))
    
    return alerts

@app.post("/api/alerts/", response_model=PriceAlert)
async def create_alert(alert: PriceAlertCreate, current_user: dict = Depends(get_current_active_user)):
    """Create a new alert"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat() + "Z"
    
    cursor.execute('''
        INSERT INTO alerts (user_id, symbol, threshold_price, alert_type, message, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (current_user["id"], alert.symbol, alert.threshold_price, alert.alert_type, alert.message, True, now))
    
    alert_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return PriceAlert(
        id=alert_id, symbol=alert.symbol, threshold_price=alert.threshold_price,
        alert_type=alert.alert_type, message=alert.message, is_active=True,
        created_at=now
    )

@app.put("/api/alerts/{alert_id}", response_model=PriceAlert)
async def update_alert(alert_id: int, alert: PriceAlertUpdate, current_user: dict = Depends(get_current_active_user)):
    """Update an alert"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get existing alert and verify ownership
    cursor.execute("SELECT * FROM alerts WHERE id = ? AND user_id = ?", (alert_id, current_user["id"]))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Alert not found")
    
    # Update only provided fields
    update_fields = []
    update_values = []
    
    if alert.symbol is not None:
        update_fields.append("symbol = ?")
        update_values.append(alert.symbol)
    if alert.threshold_price is not None:
        update_fields.append("threshold_price = ?")
        update_values.append(alert.threshold_price)
    if alert.alert_type is not None:
        update_fields.append("alert_type = ?")
        update_values.append(alert.alert_type)
    if alert.message is not None:
        update_fields.append("message = ?")
        update_values.append(alert.message)
    if alert.is_active is not None:
        update_fields.append("is_active = ?")
        update_values.append(alert.is_active)
    
    if update_fields:
        update_values.append(alert_id)
        cursor.execute(f'''
            UPDATE alerts 
            SET {', '.join(update_fields)}
            WHERE id = ?
        ''', update_values)
        conn.commit()
    
    conn.close()
    
    # Return updated alert
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,))
    row = cursor.fetchone()
    conn.close()
    
    return PriceAlert(
        id=row[0], symbol=row[2], threshold_price=row[3],
        alert_type=row[4], message=row[5], is_active=bool(row[6]),
        created_at=row[7]
    )

@app.delete("/api/alerts/{alert_id}")
async def delete_alert(alert_id: int, current_user: dict = Depends(get_current_active_user)):
    """Delete an alert"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM alerts WHERE id = ? AND user_id = ?", (alert_id, current_user["id"]))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    return {"message": "Alert deleted successfully"}

@app.get("/api/alerts/history")
async def get_alert_history(limit: int = 100, current_user: dict = Depends(get_current_active_user)):
    """Get alert history"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT 
                ah.id,
                ah.alert_id,
                ah.symbol,
                ah.triggered_price,
                ah.triggered_at
            FROM alert_history ah
            WHERE ah.user_id = ?
            ORDER BY ah.triggered_at DESC
            LIMIT ?
        """, (current_user["id"], limit))
        
        history = []
        for row in cursor.fetchall():
            history.append({
                "id": row[0],
                "alert_id": row[1],
                "symbol": row[2],
                "triggered_price": row[3],
                "triggered_at": row[4]
            })
        
        return history
        
    except Exception as e:
        logger.error(f"Error fetching alert history: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch alert history")
    finally:
        conn.close()

# Tracked symbols endpoints
@app.get("/api/symbols/tracked", response_model=List[TrackedSymbol])
async def get_tracked_symbols(active_only: bool = False, current_user: dict = Depends(get_current_active_user)):
    """Get all tracked symbols"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if active_only:
        cursor.execute("SELECT symbol, name, active, last_updated FROM tracked_symbols WHERE user_id = ? AND active = 1 ORDER BY symbol", (current_user["id"],))
    else:
        cursor.execute("SELECT symbol, name, active, last_updated FROM tracked_symbols WHERE user_id = ? ORDER BY symbol", (current_user["id"],))
    
    rows = cursor.fetchall()
    conn.close()
    
    symbols = []
    for row in rows:
        symbols.append(TrackedSymbol(
            symbol=row[0], name=row[1], active=bool(row[2]), last_updated=row[3]
        ))
    
    return symbols

# Currency endpoints
@app.post("/api/currency/refresh")
async def refresh_currency_rates():
    """Refresh currency exchange rates"""
    await currency_service.refresh_rates()
    return {
        "message": "Currency rates refreshed successfully",
        "rates_count": len(currency_service.rates),
        "last_updated": currency_service.last_updated_timestamp.isoformat() + "Z" if currency_service.last_updated_timestamp else currency_service.last_updated
    }

@app.post("/api/crypto/refresh")
async def refresh_crypto_prices():
    """Refresh crypto prices for all tracked symbols"""
    try:
        # Get all tracked symbols from the database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all unique symbols from portfolio items
        cursor.execute("SELECT DISTINCT symbol FROM portfolio_items")
        portfolio_symbols = [row[0] for row in cursor.fetchall()]
        
        # Get all active tracked symbols
        cursor.execute("SELECT symbol FROM tracked_symbols WHERE active = 1")
        tracked_symbols = [row[0] for row in cursor.fetchall()]
        
        # Combine and deduplicate symbols
        all_symbols = list(set(portfolio_symbols + tracked_symbols))
        conn.close()
        
        if not all_symbols:
            return {
                "message": "No symbols to refresh",
                "symbols_count": 0,
                "last_updated": datetime.now().isoformat() + "Z"
            }
        
        # Fetch prices for all symbols
        await fetch_prices_for_symbols(all_symbols)
        
        return {
            "message": "Crypto prices refreshed successfully",
            "symbols_count": len(all_symbols),
            "symbols": all_symbols,
            "last_updated": datetime.now().isoformat() + "Z"
        }
        
    except Exception as e:
        logger.error(f"Error refreshing crypto prices: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to refresh crypto prices: {str(e)}")

@app.get("/api/currency/rates")
async def get_currency_rates():
    """Get current currency exchange rates"""
    return {
        "base_currency": currency_service.base_currency,
        "rates": currency_service.rates,
        "last_updated": currency_service.last_updated,
        "last_updated_timestamp": currency_service.get_timestamp_iso(),
        "last_updated_formatted": currency_service.get_formatted_timestamp()
    }

@app.get("/api/symbols/last-updated")
async def get_symbol_last_updated():
    """Get last update timestamps for crypto symbols"""
    return {
        "last_bulk_update": price_service.get_timestamp_iso(),
        "last_bulk_update_formatted": price_service.get_formatted_timestamp(),
        "symbol_timestamps": price_service.get_all_symbol_timestamps()
    }

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)
    
    try:
        while True:
            try:
                # Receive message from client with timeout
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                message = json.loads(data)
                
                if message.get("type") == "subscribe":
                    # Subscribe to price updates for specific symbols
                    symbols = message.get("symbols", [])
                    manager.subscribe_to_prices(websocket, symbols)
                    
                    # Send confirmation
                    await manager.send_personal_message(json.dumps({
                        "type": "connection_status",
                        "data": f"Subscribed to {len(symbols)} symbols"
                    }), websocket)
                    
                elif message.get("type") == "subscribe_alerts":
                    # Subscribe to alert notifications
                    manager.subscribe_to_alerts(websocket)
                    
                    # Send confirmation
                    await manager.send_personal_message(json.dumps({
                        "type": "connection_status",
                        "data": "Subscribed to alert notifications"
                    }), websocket)
                    
            except asyncio.TimeoutError:
                # Send a ping to keep connection alive
                try:
                    await manager.send_personal_message(json.dumps({
                        "type": "ping",
                        "data": "Connection alive"
                    }), websocket)
                except:
                    # Connection is dead, break the loop
                    break
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "database": "sqlite", "version": "2.0.0", "websocket_connections": len(manager.active_connections)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
