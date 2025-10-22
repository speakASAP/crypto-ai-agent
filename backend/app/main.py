from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Set
from pydantic import BaseModel
import logging
import sqlite3
import json
import os
import asyncio
from datetime import datetime
from .services.currency_service import currency_service
from .services.price_service import PriceService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Database file
DB_FILE = "crypto_portfolio.db"

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
        message = json.dumps({
            "type": "price_update",
            "data": {
                "symbol": symbol,
                "price": price,
                "timestamp": datetime.now().isoformat()
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

def init_database():
    """Initialize SQLite database with tables"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create portfolio table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfolio_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            pnl_percent REAL
        )
    ''')
    
    # Create alerts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            threshold_price REAL NOT NULL,
            alert_type TEXT NOT NULL,
            message TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT NOT NULL
        )
    ''')
    
    # Create tracked_symbols table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tracked_symbols (
            symbol TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            active BOOLEAN DEFAULT 1,
            last_updated TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("✅ Database initialized")

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
        
        # Convert current_value
        converted_current_value = currency_service.convert_amount(
            item.get("current_value", 0), item["base_currency"], target_currency
        ) if item.get("current_value") else None
        
        # Convert pnl
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
    allow_origins=["http://localhost:3000", "https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Portfolio endpoints
@app.get("/api/portfolio/", response_model=List[PortfolioItem])
async def get_portfolio(currency: str = "USD"):
    """Get all portfolio items converted to target currency"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM portfolio_items ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    
    # Convert to dict format
    items = []
    for row in rows:
        item = {
            "id": row[0],
            "symbol": row[1],
            "amount": row[2],
            "price_buy": row[3],
            "purchase_date": row[4],
            "base_currency": row[5],
            "purchase_price_eur": row[6],
            "purchase_price_czk": row[7],
            "source": row[8],
            "commission": row[9],
            "total_investment_text": row[10],
            "created_at": row[11],
            "updated_at": row[12],
            "current_price": row[13],
            "current_value": row[14],
            "pnl": row[15],
            "pnl_percent": row[16]
        }
        
        # Convert currency if needed
        converted_item = convert_portfolio_item(item, currency)
        items.append(converted_item)
    
    return items

@app.get("/api/portfolio/summary")
async def get_portfolio_summary(currency: str = "USD"):
    """Get portfolio summary converted to target currency"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM portfolio_items")
    rows = cursor.fetchall()
    conn.close()
    
    total_value = 0
    total_pnl = 0
    total_investment = 0
    
    for row in rows:
        item = {
            "base_currency": row[5],
            "current_value": row[14],
            "pnl": row[15],
            "amount": row[2],
            "price_buy": row[3],
            "commission": row[9]
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
async def create_portfolio_item(item: PortfolioCreate):
    """Create a new portfolio item"""
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
        (symbol, amount, price_buy, purchase_date, base_currency, source, commission, 
         total_investment_text, created_at, updated_at, current_price, current_value, pnl, pnl_percent)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        item.symbol, item.amount, item.price_buy, item.purchase_date, item.base_currency,
        item.source, item.commission, formatted_total_investment, now, now,
        round(item.price_buy, 8), round(item.amount * item.price_buy, 8), 0.0, 0.0
    ))
    
    item_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # Return the created item
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
async def update_portfolio_item(item_id: int, item: PortfolioUpdate):
    """Update a portfolio item"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get existing item
    cursor.execute("SELECT * FROM portfolio_items WHERE id = ?", (item_id,))
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
async def delete_portfolio_item(item_id: int):
    """Delete a portfolio item"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM portfolio_items WHERE id = ?", (item_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Portfolio item not found")
    
    return {"message": "Portfolio item deleted successfully"}

# Alerts endpoints
@app.get("/api/alerts/", response_model=List[PriceAlert])
async def get_alerts(active_only: bool = False):
    """Get all alerts"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if active_only:
        cursor.execute("SELECT * FROM alerts WHERE is_active = 1 ORDER BY created_at DESC")
    else:
        cursor.execute("SELECT * FROM alerts ORDER BY created_at DESC")
    
    rows = cursor.fetchall()
    conn.close()
    
    alerts = []
    for row in rows:
        alerts.append(PriceAlert(
            id=row[0], symbol=row[1], threshold_price=row[2],
            alert_type=row[3], message=row[4], is_active=bool(row[5]),
            created_at=row[6]
        ))
    
    return alerts

@app.post("/api/alerts/", response_model=PriceAlert)
async def create_alert(alert: PriceAlertCreate):
    """Create a new alert"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat() + "Z"
    
    cursor.execute('''
        INSERT INTO alerts (symbol, threshold_price, alert_type, message, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (alert.symbol, alert.threshold_price, alert.alert_type, alert.message, True, now))
    
    alert_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return PriceAlert(
        id=alert_id, symbol=alert.symbol, threshold_price=alert.threshold_price,
        alert_type=alert.alert_type, message=alert.message, is_active=True,
        created_at=now
    )

@app.put("/api/alerts/{alert_id}", response_model=PriceAlert)
async def update_alert(alert_id: int, alert: PriceAlertUpdate):
    """Update an alert"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get existing alert
    cursor.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,))
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
        id=row[0], symbol=row[1], threshold_price=row[2],
        alert_type=row[3], message=row[4], is_active=bool(row[5]),
        created_at=row[6]
    )

@app.delete("/api/alerts/{alert_id}")
async def delete_alert(alert_id: int):
    """Delete an alert"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    return {"message": "Alert deleted successfully"}

# Tracked symbols endpoints
@app.get("/api/symbols/tracked", response_model=List[TrackedSymbol])
async def get_tracked_symbols(active_only: bool = False):
    """Get all tracked symbols"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if active_only:
        cursor.execute("SELECT * FROM tracked_symbols WHERE active = 1 ORDER BY symbol")
    else:
        cursor.execute("SELECT * FROM tracked_symbols ORDER BY symbol")
    
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
        "last_updated": currency_service.last_updated
    }

@app.get("/api/currency/rates")
async def get_currency_rates():
    """Get current currency exchange rates"""
    return {
        "base_currency": currency_service.base_currency,
        "rates": currency_service.rates,
        "last_updated": currency_service.last_updated
    }

# WebSocket endpoint
@app.websocket("/")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
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
    uvicorn.run(app, host="0.0.0.0", port=8000)
