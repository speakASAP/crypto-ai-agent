import streamlit as st
import pandas as pd, aiosqlite, asyncio
import os
import sys
import aiohttp
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from functools import lru_cache
import time

# Import reusable components
from ui_dashboard.components import PortfolioComponents, SymbolComponents, DataDisplayComponents, AppSetupComponents, AlertComponents

# Import currency converter
from currency_converter import CurrencyConverter

# Add current directory and parent directory to path
sys.path.append(os.path.dirname(__file__))
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Import from utils package
from utils.logger import (
    get_logger, log_function_entry, log_function_exit, log_database_operation,
    log_api_call, log_performance, log_user_action, log_error_with_context,
    log_warning_with_context, log_info_with_context, log_function_calls,
    log_performance_timing
)
from utils.env_validator import get_env_validator

# Load environment variables from .env file
load_dotenv()

# Apply SSL configuration immediately after loading environment variables
import ssl

# Disable SSL verification if configured
if os.getenv('SSL_VERIFY', 'false').lower() in ['false', '0', 'no', 'off']:
    ssl._create_default_https_context = ssl._create_unverified_context
    os.environ['PYTHONHTTPSVERIFY'] = '0'
    print("SSL verification disabled globally")

# Initialize environment validator
env_validator = get_env_validator()
is_valid, errors, warnings = env_validator.validate_all()

# Initialize centralized logger
logger = get_logger("ui_dashboard")

# Log environment validation results
AppSetupComponents.handle_environment_validation(is_valid, errors, warnings, env_validator.get_validation_report(), logger)

# Get validated database path and configuration
DB_PATH = env_validator.get_validated_value("DB_PATH", "data/crypto_history.db")
HTTP_TIMEOUT = env_validator.get_validated_value("HTTP_TIMEOUT", 10)
BINANCE_API_URL = env_validator.get_validated_value("BINANCE_API_URL", "https://api.binance.com/api/v3/ticker/price")

# Initialize currency converter
currency_converter = CurrencyConverter(DB_PATH)

PREDICTION_CACHE_TIME = env_validator.get_validated_value("PREDICTION_CACHE_TIME", 10)

# Log UI startup
log_info_with_context("UI Dashboard starting", "ui_startup", "ui_dashboard", db_path=DB_PATH)

# Setup page configuration and title using components
AppSetupComponents.setup_page_config("Crypto Portfolio Dashboard", "wide")
AppSetupComponents.display_page_title("Crypto AI Portfolio Dashboard")

@log_performance_timing("get_portfolio", "ui_dashboard")
async def get_portfolio():
    """Get portfolio data from database with multi-currency support"""
    log_function_entry("get_portfolio", "ui_dashboard")
    
    try:
        log_database_operation("select", "portfolio", "ui_dashboard")
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT symbol, amount, price_buy, purchase_date, base_currency, purchase_price_eur, purchase_price_czk, source, commission FROM portfolio")
            rows = await cursor.fetchall()
            
            # Handle both old and new schema
            if rows and len(rows[0]) == 3:  # Old schema
                result = pd.DataFrame(rows, columns=["symbol", "amount", "price_buy"])
                result['purchase_date'] = None
                result['base_currency'] = 'USD'
                result['purchase_price_eur'] = None
                result['purchase_price_czk'] = None
                result['source'] = 'Unknown'
                result['commission'] = 0
            elif rows and len(rows[0]) == 7:  # Schema without source
                result = pd.DataFrame(rows, columns=["symbol", "amount", "price_buy", "purchase_date", "base_currency", "purchase_price_eur", "purchase_price_czk"])
                result['source'] = 'Unknown'
                result['commission'] = 0
            elif rows and len(rows[0]) == 8:  # Schema without commission
                result = pd.DataFrame(rows, columns=["symbol", "amount", "price_buy", "purchase_date", "base_currency", "purchase_price_eur", "purchase_price_czk", "source"])
                result['commission'] = 0
            else:  # New schema with commission
                result = pd.DataFrame(rows, columns=["symbol", "amount", "price_buy", "purchase_date", "base_currency", "purchase_price_eur", "purchase_price_czk", "source", "commission"])
            
            log_info_with_context(f"Retrieved {len(result)} portfolio items", "get_portfolio", "ui_dashboard", count=len(result))
            log_function_exit("get_portfolio", "ui_dashboard", result=f"{len(result)} items")
            return result
    except Exception as e:
        log_error_with_context(e, "get_portfolio", "ui_dashboard")
        log_function_exit("get_portfolio", "ui_dashboard", result="error")
        return pd.DataFrame()


async def get_tracked_symbols():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT symbol, is_active, created_at FROM tracked_symbols ORDER BY symbol")
        rows = await cursor.fetchall()
        return pd.DataFrame(rows, columns=["symbol","is_active","created_at"])

@log_performance_timing("search_crypto_symbols_ui", "ui_dashboard")
async def search_crypto_symbols_ui(query, limit=50):
    """Search cryptocurrency symbols for UI"""
    log_function_entry("search_crypto_symbols_ui", "ui_dashboard", query=query, limit=limit)
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
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
            
            log_info_with_context(f"Found {len(results)} symbols for query '{query}'", "search_crypto_symbols_ui", "ui_dashboard", 
                                query=query, results_count=len(results))
            log_function_exit("search_crypto_symbols_ui", "ui_dashboard", result=f"{len(results)} results")
            return results
            
    except Exception as e:
        log_error_with_context(e, "search_crypto_symbols_ui", "ui_dashboard", query=query)
        log_function_exit("search_crypto_symbols_ui", "ui_dashboard", result="error")
        return []

@log_performance_timing("get_all_crypto_symbols_ui", "ui_dashboard")
async def get_all_crypto_symbols_ui():
    """Get all available cryptocurrency symbols for UI"""
    log_function_entry("get_all_crypto_symbols_ui", "ui_dashboard")
    
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
            
            log_info_with_context(f"Retrieved {len(results)} crypto symbols", "get_all_crypto_symbols_ui", "ui_dashboard", 
                                symbols_count=len(results))
            log_function_exit("get_all_crypto_symbols_ui", "ui_dashboard", result=f"{len(results)} symbols")
            return results
            
    except Exception as e:
        log_error_with_context(e, "get_all_crypto_symbols_ui", "ui_dashboard")
        log_function_exit("get_all_crypto_symbols_ui", "ui_dashboard", result="error")
        return []

@log_performance_timing("fetch_crypto_symbols_ui", "ui_dashboard")
async def fetch_crypto_symbols_ui():
    """Fetch cryptocurrency symbols from Binance API for UI"""
    log_function_entry("fetch_crypto_symbols_ui", "ui_dashboard")
    
    try:
        # Binance API endpoint for exchange info
        binance_exchange_url = "https://api.binance.com/api/v3/exchangeInfo"
        
        log_api_call("Binance", "/api/v3/exchangeInfo", "ui_dashboard")
        
        # Configure SSL context for aiohttp
        ssl_context = ssl.create_default_context()
        if os.getenv('SSL_VERIFY', 'false').lower() in ['false', '0', 'no', 'off']:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(binance_exchange_url, timeout=HTTP_TIMEOUT) as response:
                log_api_call("Binance", "/api/v3/exchangeInfo", "ui_dashboard", status_code=response.status)
                
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
                    await store_crypto_symbols_ui(symbols_data)
                    
                    log_info_with_context(f"Fetched and stored {len(symbols_data)} crypto symbols", "fetch_crypto_symbols_ui", "ui_dashboard", 
                                        symbols_count=len(symbols_data))
                    log_function_exit("fetch_crypto_symbols_ui", "ui_dashboard", result=f"{len(symbols_data)} symbols")
                    return symbols_data
                    
                else:
                    log_warning_with_context(f"HTTP {response.status} from Binance exchange info API", "fetch_crypto_symbols_ui", "ui_dashboard", 
                                           status_code=response.status)
                    log_function_exit("fetch_crypto_symbols_ui", "ui_dashboard", result="error")
                    return []
                    
    except Exception as e:
        log_error_with_context(e, "fetch_crypto_symbols_ui", "ui_dashboard")
        log_function_exit("fetch_crypto_symbols_ui", "ui_dashboard", result="error")
        return []

@log_performance_timing("store_crypto_symbols_ui", "ui_dashboard")
async def store_crypto_symbols_ui(symbols_data):
    """Store cryptocurrency symbols in database for UI"""
    log_function_entry("store_crypto_symbols_ui", "ui_dashboard", symbols_count=len(symbols_data))
    
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
            log_database_operation("bulk_insert", "crypto_symbols", "ui_dashboard", count=len(symbols_data))
            log_function_exit("store_crypto_symbols_ui", "ui_dashboard", result=f"{len(symbols_data)} symbols stored")
            
    except Exception as e:
        log_error_with_context(e, "store_crypto_symbols_ui", "ui_dashboard")
        log_function_exit("store_crypto_symbols_ui", "ui_dashboard", result="error")






@log_performance_timing("get_price_alerts", "ui_dashboard")
async def get_price_alerts():
    """Get all price alerts from database"""
    log_function_entry("get_price_alerts", "ui_dashboard")
    
    try:
        log_database_operation("select", "price_alerts", "ui_dashboard")
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("""
                SELECT id, symbol, alert_type, threshold_price, message, is_active, created_at, updated_at 
                FROM price_alerts 
                ORDER BY created_at DESC
            """)
            rows = await cursor.fetchall()
            result = pd.DataFrame(rows, columns=[
                "id", "symbol", "alert_type", "threshold_price", "message", "is_active", "created_at", "updated_at"
            ])
            
            log_info_with_context(f"Retrieved {len(result)} price alerts", "get_price_alerts", "ui_dashboard", count=len(result))
            log_function_exit("get_price_alerts", "ui_dashboard", result=f"{len(result)} alerts")
            return result
    except Exception as e:
        log_error_with_context(e, "get_price_alerts", "ui_dashboard")
        log_function_exit("get_price_alerts", "ui_dashboard", result="error")
        return pd.DataFrame()

@log_performance_timing("get_alert_history", "ui_dashboard")
async def get_alert_history(limit=100):
    """Get alert history from database"""
    log_function_entry("get_alert_history", "ui_dashboard", limit=limit)
    
    try:
        log_database_operation("select", "alert_history", "ui_dashboard", limit=limit)
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("""
                SELECT id, alert_id, symbol, triggered_price, threshold_price, alert_type, message, triggered_at 
                FROM alert_history 
                ORDER BY triggered_at DESC 
                LIMIT ?
            """, (limit,))
            rows = await cursor.fetchall()
            result = pd.DataFrame(rows, columns=[
                "id", "alert_id", "symbol", "triggered_price", "threshold_price", "alert_type", "message", "triggered_at"
            ])
            
            log_info_with_context(f"Retrieved {len(result)} alert history records", "get_alert_history", "ui_dashboard", count=len(result))
            log_function_exit("get_alert_history", "ui_dashboard", result=f"{len(result)} records")
            return result
    except Exception as e:
        log_error_with_context(e, "get_alert_history", "ui_dashboard")
        log_function_exit("get_alert_history", "ui_dashboard", result="error")
        return pd.DataFrame()

@log_performance_timing("create_price_alert", "ui_dashboard")
async def create_price_alert(symbol, alert_type, threshold_price, message, is_active=True):
    """Create a new price alert"""
    log_function_entry("create_price_alert", "ui_dashboard", symbol=symbol, alert_type=alert_type, threshold_price=threshold_price)
    
    try:
        log_database_operation("insert", "price_alerts", "ui_dashboard", symbol=symbol, alert_type=alert_type)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO price_alerts (symbol, alert_type, threshold_price, message, is_active) 
                VALUES (?, ?, ?, ?, ?)
            """, (symbol.upper(), alert_type, threshold_price, message, 1 if is_active else 0))
            await db.commit()
        
        log_user_action("create_alert", {"symbol": symbol, "alert_type": alert_type, "threshold_price": threshold_price}, "ui_dashboard")
        log_info_with_context(f"Created price alert for {symbol}", "create_price_alert", "ui_dashboard", symbol=symbol)
        log_function_exit("create_price_alert", "ui_dashboard", result="success")
    except Exception as e:
        log_error_with_context(e, "create_price_alert", "ui_dashboard", symbol=symbol)
        log_function_exit("create_price_alert", "ui_dashboard", result="error")
        raise

@log_performance_timing("update_price_alert", "ui_dashboard")
async def update_price_alert(alert_id, symbol, alert_type, threshold_price, message, is_active):
    """Update an existing price alert"""
    log_function_entry("update_price_alert", "ui_dashboard", alert_id=alert_id, symbol=symbol)
    
    try:
        log_database_operation("update", "price_alerts", "ui_dashboard", alert_id=alert_id, symbol=symbol)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                UPDATE price_alerts 
                SET symbol = ?, alert_type = ?, threshold_price = ?, message = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, (symbol.upper(), alert_type, threshold_price, message, 1 if is_active else 0, alert_id))
            await db.commit()
        
        log_user_action("update_alert", {"alert_id": alert_id, "symbol": symbol, "alert_type": alert_type}, "ui_dashboard")
        log_info_with_context(f"Updated price alert {alert_id} for {symbol}", "update_price_alert", "ui_dashboard", alert_id=alert_id, symbol=symbol)
        log_function_exit("update_price_alert", "ui_dashboard", result="success")
    except Exception as e:
        log_error_with_context(e, "update_price_alert", "ui_dashboard", alert_id=alert_id, symbol=symbol)
        log_function_exit("update_price_alert", "ui_dashboard", result="error")
        raise

@log_performance_timing("delete_price_alert", "ui_dashboard")
async def delete_price_alert(alert_id):
    """Delete a price alert"""
    log_function_entry("delete_price_alert", "ui_dashboard", alert_id=alert_id)
    
    try:
        log_database_operation("delete", "price_alerts", "ui_dashboard", alert_id=alert_id)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM price_alerts WHERE id = ?", (alert_id,))
            await db.commit()
        
        log_user_action("delete_alert", {"alert_id": alert_id}, "ui_dashboard")
        log_info_with_context(f"Deleted price alert {alert_id}", "delete_price_alert", "ui_dashboard", alert_id=alert_id)
        log_function_exit("delete_price_alert", "ui_dashboard", result="success")
    except Exception as e:
        log_error_with_context(e, "delete_price_alert", "ui_dashboard", alert_id=alert_id)
        log_function_exit("delete_price_alert", "ui_dashboard", result="error")
        raise

async def add_symbol(symbol):
    """Add a new symbol to tracking"""
    log_function_entry("add_symbol", "ui_dashboard", symbol=symbol)
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO tracked_symbols (symbol) VALUES (?)", (symbol,))
            await db.commit()
        log_user_action("add_symbol", {"symbol": symbol}, "ui_dashboard")
        log_info_with_context(f"Added {symbol} to tracking", "add_symbol", "ui_dashboard", symbol=symbol)
        log_function_exit("add_symbol", "ui_dashboard", result="success")
    except Exception as e:
        log_error_with_context(e, "add_symbol", "ui_dashboard", symbol=symbol)
        log_function_exit("add_symbol", "ui_dashboard", result="error")
        raise

async def remove_symbol(symbol):
    """Remove a symbol from tracking by setting is_active = 0"""
    log_function_entry("remove_symbol", "ui_dashboard", symbol=symbol)
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE tracked_symbols SET is_active = 0 WHERE symbol = ?", (symbol,))
            await db.commit()
        log_user_action("remove_symbol", {"symbol": symbol}, "ui_dashboard")
        log_info_with_context(f"Removed {symbol} from tracking", "remove_symbol", "ui_dashboard", symbol=symbol)
        log_function_exit("remove_symbol", "ui_dashboard", result="success")
    except Exception as e:
        log_error_with_context(e, "remove_symbol", "ui_dashboard", symbol=symbol)
        log_function_exit("remove_symbol", "ui_dashboard", result="error")
        raise

async def restore_symbol(symbol):
    """Restore a symbol to tracking by setting is_active = 1"""
    log_function_entry("restore_symbol", "ui_dashboard", symbol=symbol)
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE tracked_symbols SET is_active = 1 WHERE symbol = ?", (symbol,))
            await db.commit()
        log_user_action("restore_symbol", {"symbol": symbol}, "ui_dashboard")
        log_info_with_context(f"Restored {symbol} to tracking", "restore_symbol", "ui_dashboard", symbol=symbol)
        log_function_exit("restore_symbol", "ui_dashboard", result="success")
    except Exception as e:
        log_error_with_context(e, "restore_symbol", "ui_dashboard", symbol=symbol)
        log_function_exit("restore_symbol", "ui_dashboard", result="error")
        raise

# Portfolio Management Functions
@log_performance_timing("add_coin_to_portfolio", "ui_dashboard")
async def add_coin_to_portfolio(symbol, amount, price_buy, purchase_date=None, base_currency='USD', source='Unknown', commission=0):
    """Add a new coin to the portfolio with multi-currency support"""
    log_function_entry("add_coin_to_portfolio", "ui_dashboard", symbol=symbol, amount=amount, price_buy=price_buy, base_currency=base_currency, source=source, commission=commission)
    
    try:
        # Convert purchase price to other currencies
        price_eur = await currency_converter.convert_currency(price_buy, base_currency, 'EUR')
        price_czk = await currency_converter.convert_currency(price_buy, base_currency, 'CZK')
        
        log_database_operation("insert", "portfolio", "ui_dashboard", symbol=symbol, amount=amount, price_buy=price_buy, source=source, commission=commission)
        async with aiosqlite.connect(DB_PATH) as db:
            # Add to portfolio
            await db.execute("""
                INSERT OR REPLACE INTO portfolio 
                (symbol, amount, price_buy, purchase_date, base_currency, purchase_price_eur, purchase_price_czk, source, commission) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (symbol.upper(), amount, price_buy, purchase_date, base_currency, price_eur, price_czk, source, commission))
            
            # Also add to tracked_symbols for price monitoring
            await db.execute("INSERT OR IGNORE INTO tracked_symbols (symbol, is_active) VALUES (?, ?)", (symbol.upper(), 1))
            
            await db.commit()
        
        log_user_action("add_coin", {"symbol": symbol, "amount": amount, "price_buy": price_buy, "base_currency": base_currency, "source": source}, "ui_dashboard")
        log_info_with_context(f"Added {symbol} to portfolio and tracking in {base_currency} from {source}", "add_coin_to_portfolio", "ui_dashboard", symbol=symbol)
        log_function_exit("add_coin_to_portfolio", "ui_dashboard", result="success")
    except Exception as e:
        log_error_with_context(e, "add_coin_to_portfolio", "ui_dashboard", symbol=symbol)
        log_function_exit("add_coin_to_portfolio", "ui_dashboard", result="error")
        raise

async def update_coin_in_portfolio(symbol, amount, price_buy, base_currency='USD', source='Unknown', commission=0):
    """Update an existing coin in the portfolio with multi-currency support"""
    try:
        log_info_with_context(f"Updating coin: {symbol}, amount: {amount}, price: {price_buy}, currency: {base_currency}, source: {source}, commission: {commission}", "update_coin_in_portfolio", "ui_dashboard")
        
        # Convert prices to EUR and CZK for storage
        price_eur = await currency_converter.convert_currency(price_buy, base_currency, 'EUR')
        price_czk = await currency_converter.convert_currency(price_buy, base_currency, 'CZK')
        
        async with aiosqlite.connect(DB_PATH) as db:
            # First, check if the coin exists
            cursor = await db.execute("SELECT symbol FROM portfolio WHERE symbol = ?", (symbol.upper(),))
            existing = await cursor.fetchone()
            
            if not existing:
                log_warning_with_context(f"Coin {symbol} not found in portfolio", "update_coin_in_portfolio", "ui_dashboard")
                raise ValueError(f"Coin {symbol} not found in portfolio")
            
            # Update the coin
            await db.execute("""
                UPDATE portfolio 
                SET amount = ?, price_buy = ?, base_currency = ?, purchase_price_eur = ?, purchase_price_czk = ?, source = ?, commission = ?
                WHERE symbol = ?
            """, (amount, price_buy, base_currency, price_eur, price_czk, source, commission, symbol.upper()))
            await db.commit()
            
            # Verify the update
            cursor = await db.execute("SELECT symbol, amount, price_buy, base_currency FROM portfolio WHERE symbol = ?", (symbol.upper(),))
            updated_row = await cursor.fetchone()
            log_info_with_context(f"Updated coin verified: {updated_row}", "update_coin_in_portfolio", "ui_dashboard")
            
        log_user_action("update_coin", {"symbol": symbol, "amount": amount, "price_buy": price_buy, "base_currency": base_currency, "source": source}, "ui_dashboard")
        
    except Exception as e:
        log_error_with_context(e, "update_coin_in_portfolio", "ui_dashboard", symbol=symbol)
        raise

async def delete_coin_from_portfolio(symbol):
    """Delete a coin from the portfolio"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM portfolio WHERE symbol = ?", (symbol.upper(),))
        await db.commit()

@log_performance_timing("clear_all_portfolio", "ui_dashboard")
async def clear_all_portfolio():
    """Clear all portfolio data"""
    log_function_entry("clear_all_portfolio", "ui_dashboard")
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Get count before deletion for logging
            cursor = await db.execute("SELECT COUNT(*) FROM portfolio")
            count_result = await cursor.fetchone()
            portfolio_count = count_result[0] if count_result else 0
            
            # Clear all portfolio data
            await db.execute("DELETE FROM portfolio")
            await db.commit()
            
            log_database_operation("delete_all", "portfolio", "ui_dashboard", count=portfolio_count)
            log_user_action("clear_all_portfolio", {"cleared_count": portfolio_count}, "ui_dashboard")
            log_info_with_context(f"Cleared all portfolio data - {portfolio_count} items removed", "clear_all_portfolio", "ui_dashboard", cleared_count=portfolio_count)
            log_function_exit("clear_all_portfolio", "ui_dashboard", result=f"cleared {portfolio_count} items")
            
    except Exception as e:
        log_error_with_context(e, "clear_all_portfolio", "ui_dashboard")
        log_function_exit("clear_all_portfolio", "ui_dashboard", result="error")
        raise

@log_performance_timing("get_current_prices", "ui_dashboard")
async def get_current_prices(symbols):
    """Fetch current prices from Binance API"""
    log_function_entry("get_current_prices", "ui_dashboard", symbols=symbols, count=len(symbols))
    
    prices = {}
    if not symbols:
        log_warning_with_context("No symbols provided for price fetching", "get_current_prices", "ui_dashboard")
        log_function_exit("get_current_prices", "ui_dashboard", result="no_symbols")
        return prices
    
    try:
        # Create symbol list for Binance API with USDT suffix
        symbol_list = [f"{symbol.upper()}USDT" for symbol in symbols]
        
        log_api_call("Binance", f"/api/v3/ticker/price", "ui_dashboard")
        
        # Configure SSL context for aiohttp
        ssl_context = ssl.create_default_context()
        if os.getenv('SSL_VERIFY', 'false').lower() in ['false', '0', 'no', 'off']:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            # Use individual symbol requests since batch request format is complex
            for symbol in symbol_list:
                url = f"{BINANCE_API_URL}?symbol={symbol}"
                async with session.get(url, timeout=HTTP_TIMEOUT) as response:
                    log_api_call("Binance", f"/api/v3/ticker/price", "ui_dashboard", status_code=response.status)
                    
                    if response.status == 200:
                        data = await response.json()
                        # Extract base symbol (remove USDT suffix)
                        base_symbol = symbol.replace('USDT', '')
                        prices[base_symbol] = float(data['price'])
                    else:
                        log_warning_with_context(f"HTTP {response.status} from Binance API for {symbol}", "get_current_prices", "ui_dashboard", 
                                               status_code=response.status)
            
            log_info_with_context(f"Fetched prices for {len(prices)} symbols", "get_current_prices", "ui_dashboard", 
                                symbols_fetched=len(prices), symbols_requested=len(symbols))
                    
    except Exception as e:
        log_error_with_context(e, "get_current_prices", "ui_dashboard", symbols=symbols)
        AppSetupComponents.handle_api_error(e, "fetching current prices")
    
    log_function_exit("get_current_prices", "ui_dashboard", result=f"{len(prices)} prices")
    return prices

async def calculate_portfolio_metrics(portfolio_df, current_prices, target_currency='USD'):
    """Calculate portfolio metrics including P&L with multi-currency support"""
    if portfolio_df.empty:
        return {
            'total_value': 0,
            'total_cost': 0,
            'total_pnl': 0,
            'total_pnl_percent': 0,
            'portfolio_data': pd.DataFrame(),
            'target_currency': target_currency
        }
    
    portfolio_data = portfolio_df.copy()
    
    # Get current prices in USD from Binance
    usd_current_prices = portfolio_data['symbol'].map(current_prices).fillna(0)
    
    # Convert current prices to each coin's original currency for display
    portfolio_data['current_price'] = 0.0
    portfolio_data['current_value'] = 0.0
    
    for idx, row in portfolio_data.iterrows():
        base_currency = row.get('base_currency', 'USD')
        usd_price = usd_current_prices.iloc[idx]
        
        if base_currency == 'USD':
            # Price is already in USD
            portfolio_data.at[idx, 'current_price'] = usd_price
        else:
            # Convert USD price to original currency
            converted_price = await currency_converter.convert_currency(usd_price, 'USD', base_currency)
            portfolio_data.at[idx, 'current_price'] = converted_price
        
        # Calculate current value in original currency
        portfolio_data.at[idx, 'current_value'] = row['amount'] * portfolio_data.at[idx, 'current_price']
    
    # Use original prices for cost basis including commission (no conversion needed for display)
    portfolio_data['cost_basis'] = portfolio_data['amount'] * portfolio_data['price_buy'] + portfolio_data.get('commission', 0)
    portfolio_data['pnl'] = portfolio_data['current_value'] - portfolio_data['cost_basis']
    portfolio_data['pnl_percent'] = (portfolio_data['pnl'] / portfolio_data['cost_basis'] * 100).fillna(0)
    
    # For totals, convert everything to target currency for summary
    total_value_usd = 0
    total_cost_usd = 0
    
    for idx, row in portfolio_data.iterrows():
        base_currency = row.get('base_currency', 'USD')
        
        # Convert current value to target currency
        if base_currency == target_currency:
            current_value_converted = row['current_value']
            cost_basis_converted = row['cost_basis']
        else:
            current_value_converted = await currency_converter.convert_currency(row['current_value'], base_currency, target_currency)
            cost_basis_converted = await currency_converter.convert_currency(row['cost_basis'], base_currency, target_currency)
        
        total_value_usd += current_value_converted
        total_cost_usd += cost_basis_converted
    
    total_pnl = total_value_usd - total_cost_usd
    total_pnl_percent = (total_pnl / total_cost_usd * 100) if total_cost_usd > 0 else 0
    
    return {
        'total_value': total_value_usd,
        'total_cost': total_cost_usd,
        'total_pnl': total_pnl,
        'total_pnl_percent': total_pnl_percent,
        'portfolio_data': portfolio_data,
        'target_currency': target_currency
    }

@log_performance_timing("get_currency_rates", "ui_dashboard")
async def get_currency_rates():
    """Get current currency exchange rates"""
    return await currency_converter.get_currency_rates()


# Sidebar for symbol management using components
tracked_symbols_df = asyncio.run(get_tracked_symbols())

# Create wrapper functions for async callbacks
def remove_symbol_callback(symbol):
    asyncio.run(remove_symbol(symbol))
    # Force refresh after removing symbol
    st.rerun()

def add_symbol_callback(symbol):
    asyncio.run(add_symbol(symbol))
    # Force refresh after adding symbol
    st.rerun()


# Check if crypto symbols database exists and has data
crypto_symbols_count = 0
try:
    async def get_crypto_symbols_count():
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM crypto_symbols")
            count = await cursor.fetchone()
            return count[0] if count else 0
    
    crypto_symbols_count = asyncio.run(get_crypto_symbols_count())
except:
    crypto_symbols_count = 0

# Portfolio Management Section using components
AppSetupComponents.display_section_header("Portfolio Management", "💼")

# Get portfolio data and current prices
portfolio = asyncio.run(get_portfolio())
current_prices = {}
if not portfolio.empty:
    current_prices = asyncio.run(get_current_prices(portfolio['symbol'].tolist()))

# Store portfolio data in session state for source suggestions
st.session_state['portfolio_data'] = portfolio

# Currency selection
selected_currency, show_rates = PortfolioComponents.display_currency_selector()

# Get currency rates
currency_rates = asyncio.run(get_currency_rates())

# Display currency rates if requested
if show_rates and currency_rates:
    st.info(f"Current Exchange Rates: 1 USD = {currency_rates.get('EUR', 0):.4f} EUR, {currency_rates.get('CZK', 0):.2f} CZK")

# Calculate portfolio metrics in selected currency
metrics = asyncio.run(calculate_portfolio_metrics(portfolio, current_prices, selected_currency))

# Multi-currency portfolio display
PortfolioComponents.display_multi_currency_portfolio(metrics['portfolio_data'], currency_rates, selected_currency)

# Portfolio Management Tabs using components
async def add_coin_callback(symbol, amount, price_buy, purchase_date=None, base_currency='USD', source='Unknown', commission=0):
    await add_coin_to_portfolio(symbol, amount, price_buy, purchase_date, base_currency, source, commission)
    # Set active tab to Overview after adding coin
    st.session_state['active_portfolio_tab'] = 0  # 0 = Overview tab
    # Force refresh of portfolio data after adding coin
    st.rerun()

async def update_coin_callback(symbol, amount, price_buy, base_currency='USD', source='Unknown', commission=0):
    try:
        await update_coin_in_portfolio(symbol, amount, price_buy, base_currency, source, commission)
        # Set active tab to Overview after updating coin
        st.session_state['active_portfolio_tab'] = 0
        # Clear any cached data
        if 'portfolio_data' in st.session_state:
            del st.session_state['portfolio_data']
        # Force refresh of portfolio data after updating coin
        st.rerun()
    except Exception as e:
        st.error(f"Error updating coin: {str(e)}")
        log_error_with_context(e, "update_coin_callback", "ui_dashboard", symbol=symbol)

async def delete_coin_callback(symbol):
    await delete_coin_from_portfolio(symbol)
    # Set active tab to Overview after deleting coin
    st.session_state['active_portfolio_tab'] = 0
    # Force refresh of portfolio data after deleting coin
    st.rerun()

async def clear_all_portfolio_callback():
    await clear_all_portfolio()
    # Force refresh of portfolio data after clearing all
    st.rerun()

# Synchronous wrapper functions for Streamlit form callbacks
def sync_update_coin_callback(symbol, amount, price_buy, base_currency='USD', source='Unknown', commission=0):
    """Synchronous wrapper for update_coin_callback to work with Streamlit forms"""
    try:
        asyncio.run(update_coin_in_portfolio(symbol, amount, price_buy, base_currency, source, commission))
        # Set active tab to Overview after updating coin
        st.session_state['active_portfolio_tab'] = 0
        # Clear any cached data
        if 'portfolio_data' in st.session_state:
            del st.session_state['portfolio_data']
        # Note: st.rerun() is handled by the calling form to avoid race conditions
    except Exception as e:
        st.error(f"Error updating coin: {str(e)}")
        log_error_with_context(e, "sync_update_coin_callback", "ui_dashboard", symbol=symbol)

def sync_delete_coin_callback(symbol):
    """Synchronous wrapper for delete_coin_callback to work with Streamlit forms"""
    try:
        asyncio.run(delete_coin_from_portfolio(symbol))
        # Set active tab to Overview after deleting coin
        st.session_state['active_portfolio_tab'] = 0
        # Note: st.rerun() is handled by the calling form to avoid race conditions
    except Exception as e:
        st.error(f"Error deleting coin: {str(e)}")
        log_error_with_context(e, "sync_delete_coin_callback", "ui_dashboard", symbol=symbol)

# Display multi-currency portfolio tabs
# Create custom tab system for better control
# Initialize active tab if not set
if 'active_portfolio_tab' not in st.session_state:
    st.session_state['active_portfolio_tab'] = 0

# Tab selection
tab_options = ["📊 Overview", "➕ Add Coin", "📈 Performance", "📅 History"]
selected_tab = st.radio(
    "Portfolio Management",
    options=tab_options,
    index=st.session_state['active_portfolio_tab'],
    horizontal=True,
    key="portfolio_tab_selector"
)

# Update session state when tab changes
if st.session_state['active_portfolio_tab'] != tab_options.index(selected_tab):
    st.session_state['active_portfolio_tab'] = tab_options.index(selected_tab)
    st.rerun()

# Display content based on selected tab
if selected_tab == "📊 Overview":
    # Display portfolio table with Edit and Remove buttons
    if not metrics['portfolio_data'].empty:
        # Add clear all portfolio button and refresh button
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.write("")  # Empty column for spacing
        with col2:
            if st.button("🔄 Refresh", key="refresh_portfolio", type="secondary", help="Refresh portfolio data"):
                st.rerun()
        with col3:
            if st.button("🗑️ Clear All", key="clear_all_portfolio", type="secondary", help="Clear all portfolio items"):
                asyncio.run(clear_all_portfolio_callback())
        
        # Display table headers
        col1, col2, col3, col4, col5, col6, col7, col8, col9, col10, col11 = st.columns([2, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.2, 1, 1])
        with col1:
            st.write("**Symbol**")
        with col2:
            st.write("**Amount**")
        with col3:
            st.write("**Buy Price**")
        with col4:
            st.write("**Current Price**")
        with col5:
            st.write("**Total Invested**")
        with col6:
            st.write("**Current Value**")
        with col7:
            st.write("**P&L**")
        with col8:
            st.write("**P&L %**")
        with col9:
            st.write("**Source**")
        with col10:
            st.write("**Edit**")
        with col11:
            st.write("**Remove**")
        
        st.divider()
        
        # Display portfolio with action buttons
        PortfolioComponents.display_portfolio_table_with_actions(metrics['portfolio_data'], sync_update_coin_callback, sync_delete_coin_callback)
    else:
        st.info("No portfolio holdings to display")

elif selected_tab == "➕ Add Coin":
    # Add coin form with multi-currency support and cryptocurrency search
    if crypto_symbols_count > 0:
        # Use enhanced form with search functionality
        PortfolioComponents.display_add_coin_form_with_search(
            add_coin_callback, 
            lambda query: asyncio.run(search_crypto_symbols_ui(query, 10)),
            selected_currency
        )
    else:
        # Fallback to basic form if no crypto database
        st.info("💡 **Tip**: Use the symbol input field to add cryptocurrency symbols to your portfolio.")
        PortfolioComponents.display_add_coin_form_multi_currency(add_coin_callback, selected_currency)

elif selected_tab == "📈 Performance":
    # Performance metrics
    PortfolioComponents.display_multi_currency_metrics(metrics['portfolio_data'], selected_currency)

elif selected_tab == "📅 History":
    # Purchase history
    PortfolioComponents.display_purchase_date_tracking(portfolio)



# Price Alerts Section
AppSetupComponents.display_section_header("Price Alerts", "🔔")

# Get available symbols for alerts
available_symbols = []
if not portfolio.empty:
    available_symbols = portfolio['symbol'].tolist()
if not tracked_symbols_df.empty:
    active_symbols = tracked_symbols_df[tracked_symbols_df['is_active'] == 1]['symbol'].tolist()
    available_symbols = list(set(available_symbols + active_symbols))

# Get alert data
alerts = asyncio.run(get_price_alerts())
alert_history = asyncio.run(get_alert_history(50))

# Alert management callbacks
async def create_alert_callback(symbol, alert_type, threshold_price, message, is_active):
    await create_price_alert(symbol, alert_type, threshold_price, message, is_active)

async def update_alert_callback(alert_id, symbol, alert_type, threshold_price, message, is_active):
    await update_price_alert(alert_id, symbol, alert_type, threshold_price, message, is_active)

async def delete_alert_callback(alert_id):
    await delete_price_alert(alert_id)

# Display alert management interface
AlertComponents.display_alert_management(
    alerts, 
    alert_history, 
    available_symbols, 
    create_alert_callback, 
    update_alert_callback, 
    delete_alert_callback
)




# Tracked symbols overview using components - DISABLED FOR REFACTORING
# SymbolComponents.display_symbols_overview(tracked_symbols_df)

# Statistics Dashboard using components - DISABLED FOR REFACTORING
# DataDisplayComponents.display_dashboard_statistics(portfolio, tracked_symbols_df, metrics)