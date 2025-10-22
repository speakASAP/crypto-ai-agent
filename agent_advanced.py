# Asynchronous multi-asset AI agent with Telegram notifications

import os
import sys
import asyncio
import aiosqlite
import aiohttp
import pandas as pd
import numpy as np
import traceback
import ssl
from binance import AsyncClient
from datetime import datetime
from telegram import Bot
from dotenv import load_dotenv

# Add utils directory to path for centralized logging
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))
from utils.logger import (
    get_logger, log_function_entry, log_function_exit, log_database_operation,
    log_api_call, log_performance, log_system_event, log_error_with_context,
    log_warning_with_context, log_info_with_context, log_function_calls,
    log_performance_timing
)
from utils.env_validator import get_env_validator

# Load environment variables from .env file
load_dotenv()

# Apply SSL configuration immediately after loading environment variables
import ssl
import os

# Disable SSL verification if configured
if os.getenv('SSL_VERIFY', 'false').lower() in ['false', '0', 'no', 'off']:
    ssl._create_default_https_context = ssl._create_unverified_context
    os.environ['PYTHONHTTPSVERIFY'] = '0'
    print("SSL verification disabled globally")

# Initialize environment validator
env_validator = get_env_validator()
is_valid, errors, warnings = env_validator.validate_all()

# Initialize centralized logger
logger = get_logger("agent")

# Log environment validation results
if errors:
    for error in errors:
        logger.critical(f"Environment validation error: {error}")
if warnings:
    for warning in warnings:
        logger.warning(f"Environment validation warning: {warning}")

if not is_valid:
    logger.critical("Environment validation failed. Please fix the errors above.")
    logger.critical(env_validator.get_validation_report())
    sys.exit(1)

logger.info("Environment variables validated successfully")
logger.info(env_validator.get_validation_report())

# SSL Configuration (using validated values) - moved here to be available for SSL functions
SSL_VERIFY = env_validator.get_validated_value("SSL_VERIFY", False)
SSL_DEBUG = env_validator.get_validated_value("SSL_DEBUG", False)

# SSL Context Configuration
def create_ssl_context():
    """Create SSL context based on configuration"""
    if not SSL_VERIFY:
        # Create a completely unverified SSL context
        ssl_context = ssl._create_unverified_context()
        logger.warning("SSL certificate verification disabled - using insecure connection")
        
        # Set environment variables for aiohttp to disable SSL verification
        os.environ['PYTHONHTTPSVERIFY'] = '0'
        os.environ['CURL_CA_BUNDLE'] = ''
        os.environ['REQUESTS_CA_BUNDLE'] = ''
        
        # Monkey patch ssl to disable verification
        ssl._create_default_https_context = ssl._create_unverified_context
        logger.warning("SSL verification disabled globally for all HTTPS connections")
    else:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        logger.info("SSL certificate verification enabled")
    
    if SSL_DEBUG:
        ssl_context.set_debug(1)
        logger.info("SSL debugging enabled")
    
    return ssl_context

# Global aiohttp connector with SSL configuration
def get_global_connector():
    """Get global aiohttp connector with SSL configuration"""
    ssl_context = create_ssl_context()
    return aiohttp.TCPConnector(ssl=ssl_context)

# Initialize SSL configuration early
create_ssl_context()

# Monkey patch Binance library to use SSL-disabled connector
if not SSL_VERIFY:
    # Patch aiohttp at the module level to disable SSL verification
    import aiohttp
    import ssl
    
    # Create SSL context that doesn't verify certificates
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    # Store original connector class
    original_connector = aiohttp.TCPConnector
    
    class SSLDisabledConnector(original_connector):
        def __init__(self, *args, **kwargs):
            kwargs['ssl'] = ssl_context
            super().__init__(*args, **kwargs)
    
    # Replace TCPConnector with our SSL-disabled version
    aiohttp.TCPConnector = SSLDisabledConnector
    logger.warning("aiohttp.TCPConnector patched to disable SSL verification globally")

# Error handling utilities
class ErrorHandler:
    """Centralized error handling and notification system"""
    
    def __init__(self, bot=None, chat_id=None):
        self.bot = bot
        self.chat_id = chat_id
        self.error_counts = {}
        self.max_errors_per_hour = MAX_ERRORS_PER_HOUR  # Rate limiting for notifications
    
    async def handle_error(self, error, context="", critical=False, notify_user=True):
        """Handle errors with logging, recovery, and user notification"""
        error_msg = str(error)
        error_type = type(error).__name__
        
        # Use centralized logging
        if critical:
            log_error_with_context(error, context, "agent", error_type=error_type, critical=True)
        else:
            log_error_with_context(error, context, "agent", error_type=error_type, critical=False)
        
        # Rate limiting for user notifications
        if notify_user and self.bot and self.chat_id:
            current_hour = datetime.now().strftime("%Y-%m-%d-%H")
            error_key = f"{context}_{error_type}_{current_hour}"
            
            if error_key not in self.error_counts:
                self.error_counts[error_key] = 0
            
            if self.error_counts[error_key] < self.max_errors_per_hour:
                try:
                    # Escape underscores in error message to prevent Markdown parsing issues
                    escaped_error_msg = str(error_msg).replace('_', '\\_')
                    
                    notification = f"⚠️ *Crypto Agent Error*\n\n"
                    notification += f"*Context:* {context}\n"
                    notification += f"*Error:* {error_type}\n"
                    notification += f"*Message:* `{escaped_error_msg}`\n"  # Use code formatting for error details
                    notification += f"*Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    
                    if critical:
                        notification += "\n\n🚨 *CRITICAL ERROR - IMMEDIATE ATTENTION REQUIRED*"
                    
                    # Log the message before sending
                    logger.info(f"TELEGRAM BOT - Sending ERROR notification to chat {self.chat_id}")
                    logger.info(f"TELEGRAM BOT - Message content: {notification}")
                    
                    await self.bot.send_message(chat_id=self.chat_id, text=notification, parse_mode='Markdown')
                    
                    # Log successful send
                    logger.info(f"TELEGRAM BOT - ERROR notification sent successfully to chat {self.chat_id}")
                    self.error_counts[error_key] += 1
                    log_system_event("error_notification_sent", "agent", context=context, error_type=error_type)
                except Exception as notify_error:
                    logger.error(f"TELEGRAM BOT - ERROR sending notification to chat {self.chat_id}: {notify_error}")
                    log_error_with_context(notify_error, "sending error notification", "agent")
    
    async def handle_warning(self, message, context=""):
        """Handle warnings with logging and optional user notification"""
        log_warning_with_context(message, context, "agent")
        
        # Send warning to user if it's important
        if self.bot and self.chat_id and "connection" in message.lower():
            try:
                # Escape underscores in warning message to prevent Markdown parsing issues
                escaped_message = str(message).replace('_', '\\_')
                notification = f"⚠️ *Crypto Agent Warning*\n\n*Context:* {context}\n*Message:* `{escaped_message}`"
                
                # Log the message before sending
                logger.info(f"TELEGRAM BOT - Sending WARNING notification to chat {self.chat_id}")
                logger.info(f"TELEGRAM BOT - Message content: {notification}")
                
                await self.bot.send_message(chat_id=self.chat_id, text=notification, parse_mode='Markdown')
                
                # Log successful send
                logger.info(f"TELEGRAM BOT - WARNING notification sent successfully to chat {self.chat_id}")
                log_system_event("warning_notification_sent", "agent", context=context)
            except Exception as notify_error:
                logger.error(f"TELEGRAM BOT - ERROR sending warning notification to chat {self.chat_id}: {notify_error}")
                log_error_with_context(notify_error, "sending warning notification", "agent")
    
    async def handle_info(self, message, context=""):
        """Handle informational messages"""
        log_info_with_context(message, context, "agent")

# Initialize error handler
error_handler = None

# Environment variables (using validated values)
BINANCE_API_KEY = env_validator.get_validated_value("BINANCE_API_KEY")
BINANCE_API_SECRET = env_validator.get_validated_value("BINANCE_API_SECRET")
TELEGRAM_TOKEN = env_validator.get_validated_value("TELEGRAM_TOKEN")
CHAT_ID = env_validator.get_validated_value("TELEGRAM_CHAT_ID")

# Agent configuration from environment (using validated values)
# No default symbols - only user-selected symbols from database
MAX_PRICE_HISTORY = env_validator.get_validated_value("MAX_PRICE_HISTORY", 200)

# Database configuration (using validated values)
DB_PATH = env_validator.get_validated_value("DB_PATH", "data/crypto_history.db")

# Sentiment analysis configuration (using validated values)

# Additional configuration (using validated values)
MAX_ERRORS_PER_HOUR = env_validator.get_validated_value("MAX_ERRORS_PER_HOUR", 10)
MAX_CONNECTION_RETRIES = env_validator.get_validated_value("MAX_CONNECTION_RETRIES", 5)
HTTP_TIMEOUT = env_validator.get_validated_value("HTTP_TIMEOUT", 10)

# SSL Configuration moved to earlier in the file (after environment validation)

# API URLs configuration (using validated values)
BINANCE_API_URL = env_validator.get_validated_value("BINANCE_API_URL", "https://api.binance.com/api/v3/ticker/price")


bot = Bot(token=TELEGRAM_TOKEN)
error_handler = ErrorHandler(bot=bot, chat_id=CHAT_ID)

# Test Telegram bot connection at startup
async def test_telegram_bot():
    """Test Telegram bot connection and send a test message"""
    try:
        logger.info(f"TELEGRAM BOT - Testing connection to chat {CHAT_ID}")
        test_msg = f"🤖 *Crypto AI Agent Test*\n\n*Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n*Status:* Bot connection test successful"
        
        logger.info(f"TELEGRAM BOT - Sending TEST message to chat {CHAT_ID}")
        logger.info(f"TELEGRAM BOT - Test message content: {test_msg}")
        
        await bot.send_message(chat_id=CHAT_ID, text=test_msg, parse_mode='Markdown')
        
        logger.info(f"TELEGRAM BOT - TEST message sent successfully to chat {CHAT_ID}")
        return True
    except Exception as e:
        logger.error(f"TELEGRAM BOT - ERROR testing bot connection: {e}")
        return False

price_history = {}
tracked_symbols = set()


# Log startup
logger.info("Crypto AI Agent starting up...")
logger.info("Tracking symbols: User-selected symbols from database")
logger.info(f"Database path: {DB_PATH}")


@log_performance_timing("database_initialization", "agent")
async def init_db():
    """Initialize database with proper error handling and recovery"""
    log_function_entry("init_db", "agent", db_path=DB_PATH)
    
    max_retries = 3
    retry_count = 0
    
    log_system_event("database_init_start", "agent", max_retries=max_retries, db_path=DB_PATH)
    
    while retry_count < max_retries:
        try:
            log_database_operation("connect", "database", "agent", attempt=retry_count + 1)
            
            async with aiosqlite.connect(DB_PATH) as db:
                # Create tables
                log_database_operation("create_table", "candles", "agent")
                await db.execute("""
                CREATE TABLE IF NOT EXISTS candles (
                    symbol TEXT,
                    price REAL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """)
                
                
                log_database_operation("create_table", "portfolio", "agent")
                await db.execute("""
                CREATE TABLE IF NOT EXISTS portfolio (
                    symbol TEXT PRIMARY KEY,
                    amount DECIMAL(20,8),
                    price_buy DECIMAL(20,8),
                    purchase_date DATETIME,
                    base_currency TEXT DEFAULT 'USD',
                    purchase_price_eur DECIMAL(20,8),
                    purchase_price_czk DECIMAL(20,8),
                    source TEXT DEFAULT 'Unknown',
                    commission DECIMAL(20,8) DEFAULT 0
                )
                """)
                
                # Check if source column exists, if not add it (migration)
                cursor = await db.execute("PRAGMA table_info(portfolio)")
                columns = await cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                if 'source' not in column_names:
                    log_info_with_context("Adding source column to portfolio table", "init_db", "agent")
                    await db.execute("ALTER TABLE portfolio ADD COLUMN source TEXT DEFAULT 'Unknown'")
                    log_info_with_context("Source column added successfully", "init_db", "agent")
                
                # Check if commission column exists, if not add it (migration)
                if 'commission' not in column_names:
                    log_info_with_context("Adding commission column to portfolio table", "init_db", "agent")
                    await db.execute("ALTER TABLE portfolio ADD COLUMN commission DECIMAL(20,8) DEFAULT 0")
                    log_info_with_context("Commission column added successfully", "init_db", "agent")
                
                log_database_operation("create_table", "currency_rates", "agent")
                await db.execute("""
                CREATE TABLE IF NOT EXISTS currency_rates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_currency TEXT,
                    to_currency TEXT,
                    rate REAL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """)
                
                log_database_operation("create_table", "tracked_symbols", "agent")
                await db.execute("""
                CREATE TABLE IF NOT EXISTS tracked_symbols (
                    symbol TEXT PRIMARY KEY,
                    is_active INTEGER DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """)
                
                log_database_operation("create_table", "crypto_symbols", "agent")
                await db.execute("""
                CREATE TABLE IF NOT EXISTS crypto_symbols (
                    symbol TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    is_tradable INTEGER DEFAULT 1,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """)
                
                
                log_database_operation("create_table", "price_alerts", "agent")
                await db.execute("""
                CREATE TABLE IF NOT EXISTS price_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    threshold_price REAL NOT NULL,
                    message TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """)
                
                log_database_operation("create_table", "alert_history", "agent")
                await db.execute("""
                CREATE TABLE IF NOT EXISTS alert_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    triggered_price REAL NOT NULL,
                    threshold_price REAL NOT NULL,
                    alert_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    triggered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (alert_id) REFERENCES price_alerts (id)
                )
                """)
                
                log_database_operation("commit", "database", "agent")
                await db.commit()
                
                # Initialize default symbols if table is empty
                log_database_operation("count", "tracked_symbols", "agent")
                cursor = await db.execute("SELECT COUNT(*) FROM tracked_symbols")
                count = await cursor.fetchone()
                
                if count[0] == 0:
                    log_system_event("no_tracked_symbols", "agent", message="No symbols in database - users must add symbols via UI")
                else:
                    log_system_event("tracked_symbols_already_exist", "agent", count=count[0])
                
                log_system_event("database_init_success", "agent", retry_count=retry_count)
                log_function_exit("init_db", "agent", result=True)
                return True
                
        except Exception as e:
            retry_count += 1
            log_error_with_context(e, "database_initialization", "agent", attempt=retry_count, max_retries=max_retries)
            await error_handler.handle_error(e, "Database initialization", critical=True)
            
            if retry_count < max_retries:
                log_warning_with_context(f"Database initialization failed, retrying ({retry_count}/{max_retries})", "database_initialization", "agent")
                await asyncio.sleep(2 ** retry_count)  # Exponential backoff
            else:
                log_error_with_context(Exception("Database initialization failed after all retries"), "database_initialization", "agent", final_attempt=True)
                log_function_exit("init_db", "agent", result=False)
                return False

async def load_tracked_symbols():
    """Load active symbols from database with error handling and recovery"""
    global tracked_symbols, price_history
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT symbol FROM tracked_symbols WHERE is_active = 1")
            rows = await cursor.fetchall()
            new_symbols = {row[0] for row in rows}
            
            # Add new symbols
            for symbol in new_symbols - tracked_symbols:
                try:
                    tracked_symbols.add(symbol)
                    price_history[symbol] = []
                    logger.info(f"Added new symbol to tracking: {symbol}")
                except Exception as e:
                    await error_handler.handle_error(e, f"Adding symbol {symbol}", critical=False)
                    # Remove symbol from tracking if model creation fails
                    tracked_symbols.discard(symbol)
            
            # Remove inactive symbols
            for symbol in tracked_symbols - new_symbols:
                try:
                    tracked_symbols.remove(symbol)
                    if symbol in price_history:
                        del price_history[symbol]
                    logger.info(f"Removed symbol from tracking: {symbol}")
                except Exception as e:
                    await error_handler.handle_error(e, f"Removing symbol {symbol}", critical=False)
                    
    except Exception as e:
        await error_handler.handle_error(e, "Loading tracked symbols", critical=True)
        # No fallback symbols - users must add symbols via UI
        logger.warning("No symbols loaded from database - users must add symbols via UI")

async def add_symbol(symbol):
    """Add a new symbol to tracking"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO tracked_symbols (symbol) VALUES (?)", (symbol,))
        await db.commit()
    await load_tracked_symbols()

async def remove_symbol(symbol):
    """Remove a symbol from tracking"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE tracked_symbols SET is_active = 0 WHERE symbol = ?", (symbol,))
        await db.commit()
    await load_tracked_symbols()

@log_performance_timing("fetch_crypto_symbols", "agent")
async def fetch_crypto_symbols():
    """Fetch cryptocurrency symbols and names from Binance API"""
    log_function_entry("fetch_crypto_symbols", "agent")
    
    try:
        # Binance API endpoint for exchange info
        binance_exchange_url = "https://api.binance.com/api/v3/exchangeInfo"
        
        log_api_call("Binance", "/api/v3/exchangeInfo", "agent")
        
        connector = get_global_connector()
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(binance_exchange_url, timeout=HTTP_TIMEOUT) as response:
                log_api_call("Binance", "/api/v3/exchangeInfo", "agent", status_code=response.status)
                
                if response.status == 200:
                    data = await response.json()
                    symbols_data = []
                    
                    # Process symbols from Binance
                    for symbol_info in data.get('symbols', []):
                        if symbol_info.get('status') == 'TRADING':
                            symbol = symbol_info.get('baseAsset', '')
                            quote_asset = symbol_info.get('quoteAsset', '')
                            
                            # Only include USDT pairs for now (can be expanded)
                            if quote_asset == 'USDT':
                                # Create a basic description
                                description = f"{symbol} - {symbol_info.get('baseAssetName', symbol)}"
                                
                                symbols_data.append({
                                    'symbol': symbol,
                                    'name': symbol_info.get('baseAssetName', symbol),
                                    'description': description,
                                    'is_tradable': 1
                                })
                    
                    # Store in database
                    await store_crypto_symbols(symbols_data)
                    
                    log_info_with_context(f"Fetched and stored {len(symbols_data)} crypto symbols", "fetch_crypto_symbols", "agent", 
                                        symbols_count=len(symbols_data))
                    log_function_exit("fetch_crypto_symbols", "agent", result=f"{len(symbols_data)} symbols")
                    return symbols_data
                    
                else:
                    log_warning_with_context(f"HTTP {response.status} from Binance exchange info API", "fetch_crypto_symbols", "agent", 
                                           status_code=response.status)
                    log_function_exit("fetch_crypto_symbols", "agent", result="error")
                    return []
                    
    except Exception as e:
        log_error_with_context(e, "fetch_crypto_symbols", "agent")
        await error_handler.handle_error(e, "Fetching crypto symbols", critical=False)
        log_function_exit("fetch_crypto_symbols", "agent", result="error")
        return []

@log_performance_timing("store_crypto_symbols", "agent")
async def store_crypto_symbols(symbols_data):
    """Store cryptocurrency symbols in database"""
    log_function_entry("store_crypto_symbols", "agent", symbols_count=len(symbols_data))
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Clear existing data and insert new data
            await db.execute("DELETE FROM crypto_symbols")
            
            for symbol_data in symbols_data:
                await db.execute("""
                    INSERT INTO crypto_symbols (symbol, name, description, is_tradable, last_updated)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    symbol_data['symbol'],
                    symbol_data['name'],
                    symbol_data['description'],
                    symbol_data['is_tradable']
                ))
            
            await db.commit()
            log_database_operation("bulk_insert", "crypto_symbols", "agent", count=len(symbols_data))
            log_function_exit("store_crypto_symbols", "agent", result=f"{len(symbols_data)} symbols stored")
            
    except Exception as e:
        log_error_with_context(e, "store_crypto_symbols", "agent")
        await error_handler.handle_error(e, "Storing crypto symbols", critical=False)
        log_function_exit("store_crypto_symbols", "agent", result="error")

@log_performance_timing("search_crypto_symbols", "agent")
async def search_crypto_symbols(query, limit=50):
    """Search cryptocurrency symbols by symbol or name"""
    log_function_entry("search_crypto_symbols", "agent", query=query, limit=limit)
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Search in both symbol and name fields
            cursor = await db.execute("""
                SELECT symbol, name, description 
                FROM crypto_symbols 
                WHERE (symbol LIKE ? OR name LIKE ? OR description LIKE ?)
                AND is_tradable = 1
                ORDER BY 
                    CASE 
                        WHEN symbol = ? THEN 1
                        WHEN symbol LIKE ? THEN 2
                        WHEN name LIKE ? THEN 3
                        ELSE 4
                    END,
                    symbol
                LIMIT ?
            """, (
                f"%{query.upper()}%",
                f"%{query}%",
                f"%{query}%",
                query.upper(),
                f"{query.upper()}%",
                f"{query}%",
                limit
            ))
            
            rows = await cursor.fetchall()
            results = [{'symbol': row[0], 'name': row[1], 'description': row[2]} for row in rows]
            
            log_info_with_context(f"Found {len(results)} symbols for query '{query}'", "search_crypto_symbols", "agent", 
                                query=query, results_count=len(results))
            log_function_exit("search_crypto_symbols", "agent", result=f"{len(results)} results")
            return results
            
    except Exception as e:
        log_error_with_context(e, "search_crypto_symbols", "agent", query=query)
        await error_handler.handle_error(e, f"Searching crypto symbols for '{query}'", critical=False)
        log_function_exit("search_crypto_symbols", "agent", result="error")
        return []

@log_performance_timing("get_all_crypto_symbols", "agent")
async def get_all_crypto_symbols():
    """Get all available cryptocurrency symbols"""
    log_function_entry("get_all_crypto_symbols", "agent")
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("""
                SELECT symbol, name, description 
                FROM crypto_symbols 
                WHERE is_tradable = 1
                ORDER BY symbol
            """)
            
            rows = await cursor.fetchall()
            results = [{'symbol': row[0], 'name': row[1], 'description': row[2]} for row in rows]
            
            log_info_with_context(f"Retrieved {len(results)} crypto symbols", "get_all_crypto_symbols", "agent", 
                                symbols_count=len(results))
            log_function_exit("get_all_crypto_symbols", "agent", result=f"{len(results)} symbols")
            return results
            
    except Exception as e:
        log_error_with_context(e, "get_all_crypto_symbols", "agent")
        await error_handler.handle_error(e, "Getting all crypto symbols", critical=False)
        log_function_exit("get_all_crypto_symbols", "agent", result="error")
        return []



async def handle_price(symbol, price):
    """Handle price updates with comprehensive error handling and recovery"""
    try:
        if symbol not in tracked_symbols:
            return
        
        # Validate price data
        if not isinstance(price, (int, float)) or price <= 0:
            await error_handler.handle_warning(f"Invalid price data for {symbol}: {price}", "Price validation")
            return
        
        # Update price history
        price_history[symbol].append(price)
        if len(price_history[symbol]) > MAX_PRICE_HISTORY:
            price_history[symbol].pop(0)

        # Save to database with retry logic
        max_db_retries = 3
        for attempt in range(max_db_retries):
            try:
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute("INSERT INTO candles(symbol, price) VALUES (?,?)", (symbol, price))
                    await db.commit()
                break
            except Exception as e:
                if attempt == max_db_retries - 1:
                    await error_handler.handle_error(e, f"Saving price data for {symbol}", critical=False)
                else:
                    logger.warning(f"Database save attempt {attempt + 1} failed for {symbol}, retrying...")
                    await asyncio.sleep(0.1)

        # Calculate standard volatility
        # Calculate volatility using last 20 prices or all available if less than 20
        window_size = min(20, len(price_history[symbol]))
        volatility = np.std(price_history[symbol][-window_size:]) if window_size > 0 else 0.0

        # Check price alerts
        try:
            await check_price_alerts(symbol, price)
        except Exception as e:
            await error_handler.handle_error(e, f"Checking price alerts for {symbol}", critical=False)

        logger.info(f"{symbol} | Price: ${price:.2f} | Volatility: {volatility:.2f}")
                
    except Exception as e:
        await error_handler.handle_error(e, f"Handling price for {symbol}", critical=True)

async def check_price_alerts(symbol, current_price):
    """Check if current price triggers any active alerts for the symbol"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Get active alerts for this symbol
            cursor = await db.execute("""
                SELECT id, symbol, alert_type, threshold_price, message 
                FROM price_alerts 
                WHERE symbol = ? AND is_active = 1
            """, (symbol,))
            alerts = await cursor.fetchall()
            
            for alert in alerts:
                alert_id, alert_symbol, alert_type, threshold_price, message = alert
                
                # Check if alert should trigger
                should_trigger = False
                if alert_type == "ABOVE" and current_price >= threshold_price:
                    should_trigger = True
                elif alert_type == "BELOW" and current_price <= threshold_price:
                    should_trigger = True
                
                if should_trigger:
                    # Send alert notification
                    try:
                        alert_message = f"🔔 *Price Alert Triggered*\n\n"
                        alert_message += f"*Symbol:* {alert_symbol}\n"
                        alert_message += f"*Current Price:* ${current_price:.2f}\n"
                        alert_message += f"*Threshold:* ${threshold_price:.2f}\n"
                        alert_message += f"*Alert Type:* {alert_type}\n"
                        alert_message += f"*Message:* {message}\n"
                        alert_message += f"*Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        
                        # Log the alert message before sending
                        logger.info(f"TELEGRAM BOT - Sending PRICE ALERT notification to chat {CHAT_ID}")
                        logger.info(f"TELEGRAM BOT - Alert message content: {alert_message}")
                        
                        await bot.send_message(chat_id=CHAT_ID, text=alert_message, parse_mode='Markdown')
                        
                        # Log successful send
                        logger.info(f"TELEGRAM BOT - PRICE ALERT notification sent successfully to chat {CHAT_ID}")
                        
                        # Log alert to history
                        await db.execute("""
                            INSERT INTO alert_history 
                            (alert_id, symbol, triggered_price, threshold_price, alert_type, message) 
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (alert_id, alert_symbol, current_price, threshold_price, alert_type, message))
                        
                        # Deactivate alert to prevent spam (user can reactivate if needed)
                        await db.execute("UPDATE price_alerts SET is_active = 0 WHERE id = ?", (alert_id,))
                        
                        await db.commit()
                        
                        logger.info(f"Price alert triggered for {alert_symbol}: {alert_type} ${threshold_price:.2f} at ${current_price:.2f}")
                        
                    except Exception as e:
                        await error_handler.handle_error(e, f"Sending alert notification for {alert_symbol}", critical=False)
                        
    except Exception as e:
        await error_handler.handle_error(e, f"Checking price alerts for {symbol}", critical=False)

# WebSocket message handler removed - using HTTP API instead

async def fetch_latest_prices():
    """Fetch latest prices for all tracked symbols using HTTP API"""
    if not tracked_symbols:
        logger.info("No symbols to track, skipping price fetch")
        return
    
    try:
        # Create symbol list for Binance API with USDT suffix
        symbol_list = [f"{symbol.upper()}USDT" for symbol in tracked_symbols]
        
        log_api_call("Binance", f"/api/v3/ticker/price", "agent")
        
        connector = get_global_connector()
        async with aiohttp.ClientSession(connector=connector) as session:
            # Use individual symbol requests since batch request format is complex
            for symbol in symbol_list:
                url = f"{BINANCE_API_URL}?symbol={symbol}"
                async with session.get(url, timeout=HTTP_TIMEOUT) as response:
                    log_api_call("Binance", f"/api/v3/ticker/price", "agent", status_code=response.status)
                    
                    if response.status == 200:
                        data = await response.json()
                        # Extract base symbol (remove USDT suffix)
                        base_symbol = symbol.replace('USDT', '')
                        price = float(data['price'])
                        # Process the price data
                        await handle_price(base_symbol, price)
                    else:
                        log_warning_with_context(f"HTTP {response.status} from Binance API for {symbol}", "fetch_latest_prices", "agent", 
                                               status_code=response.status)
            
            log_info_with_context(f"Fetched prices for tracked symbols", "fetch_latest_prices", "agent", 
                                symbols_requested=len(tracked_symbols))
                    
    except Exception as e:
        log_error_with_context(e, "fetch_latest_prices", "agent", symbols=list(tracked_symbols))
        await error_handler.handle_error(e, "Fetching latest prices", critical=False)

async def start_price_monitoring():
    """Start HTTP-based price monitoring with periodic updates"""
    logger.info("Starting HTTP-based price monitoring...")
    
    while True:
        try:
            # Reload tracked symbols every 30 seconds
            await load_tracked_symbols()
            
            if tracked_symbols:
                logger.info(f"Monitoring {len(tracked_symbols)} symbols: {', '.join(sorted(tracked_symbols))}")
                # Fetch latest prices
                await fetch_latest_prices()
            else:
                logger.info("No symbols to monitor - users can add symbols via UI")
            
            # Wait 60 seconds before next price fetch
            await asyncio.sleep(60)
            
        except Exception as e:
            await error_handler.handle_error(e, "Price monitoring loop", critical=True)
            logger.warning("Price monitoring error, retrying in 30 seconds...")
            await asyncio.sleep(30)

async def main():
    """Main function with comprehensive error handling and startup validation"""
    try:
        logger.info("=" * 60)
        logger.info("CRYPTO AI AGENT STARTUP")
        logger.info("=" * 60)
        
        # Environment variables are already validated at startup
        logger.info("Starting agent with validated environment variables")
        
        # Initialize database
        db_success = await init_db()
        if not db_success:
            logger.critical("Failed to initialize database, exiting")
            return
        
        # Load tracked symbols
        await load_tracked_symbols()
        
        # Test Telegram bot connection first
        bot_test_success = await test_telegram_bot()
        if not bot_test_success:
            logger.warning("TELEGRAM BOT - Bot connection test failed, but continuing with startup")
        
        # Send startup notification
        try:
            startup_msg = f"🚀 *Crypto AI Agent Started*\n\n"
            startup_msg += f"*Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            startup_msg += f"*Tracking:* {len(tracked_symbols)} symbols\n"
            startup_msg += f"*Symbols:* {', '.join(sorted(tracked_symbols))}\n"
            startup_msg += f"*Database:* `{DB_PATH}`\n"  # Use code formatting to escape underscores
            
            # Log the startup message before sending
            logger.info(f"TELEGRAM BOT - Sending STARTUP notification to chat {CHAT_ID}")
            logger.info(f"TELEGRAM BOT - Startup message content: {startup_msg}")
            
            await bot.send_message(chat_id=CHAT_ID, text=startup_msg, parse_mode='Markdown')
            
            # Log successful send
            logger.info(f"TELEGRAM BOT - STARTUP notification sent successfully to chat {CHAT_ID}")
            logger.info("Startup notification sent successfully")
        except Exception as e:
            await error_handler.handle_error(e, "Sending startup notification", critical=False)
        
        # Start HTTP-based price monitoring
        await start_price_monitoring()
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down gracefully...")
        try:
            shutdown_msg = f"🛑 *Crypto AI Agent Shutdown*\n\n*Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            # Log the shutdown message before sending
            logger.info(f"TELEGRAM BOT - Sending SHUTDOWN notification to chat {CHAT_ID}")
            logger.info(f"TELEGRAM BOT - Shutdown message content: {shutdown_msg}")
            
            await bot.send_message(chat_id=CHAT_ID, text=shutdown_msg, parse_mode='Markdown')
            
            # Log successful send
            logger.info(f"TELEGRAM BOT - SHUTDOWN notification sent successfully to chat {CHAT_ID}")
        except:
            pass
        logger.info("Agent shutdown complete")
        
    except Exception as e:
        await error_handler.handle_error(e, "Main function", critical=True)
        logger.critical("Fatal error in main function, agent shutting down")

if __name__ == "__main__":
    asyncio.run(main())