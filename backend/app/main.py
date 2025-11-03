from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, status, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Set, Any
from pydantic import BaseModel, EmailStr, validator
import logging
import sqlite3
import json
import os
import asyncio
import aiohttp
import ssl
import psycopg
import time
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from .services.currency_service import currency_service
from .services.price_service import PriceService
from .services.multi_exchange_price_service import multi_exchange_price_service
from .services.csv_import_service import CSVImportService
from .dependencies.auth import get_current_active_user, get_db_connection
from .utils.auth import verify_password, get_password_hash, create_access_token, create_refresh_token, generate_reset_token
from .core.config import settings
try:
    from utils.logger import get_logger  # root-level utils when available
except Exception:  # pragma: no cover
    from .utils.logger import get_logger  # fallback to app-local logger

# Load environment variables
load_dotenv()

# Centralized logger
logger = get_logger("backend.app.main")

from .utils.db import (
    normalize_placeholders as _normalize_placeholders,
    execute_insert_and_get_id as _execute_insert_and_get_id,
    is_postgres_connection,
    connect_with_retry,
)

# Database file - resolve to absolute path
import os
# Get the project root directory (parent of backend directory)
current_file = os.path.abspath(__file__)  # /path/to/backend/app/main.py
backend_dir = os.path.dirname(os.path.dirname(current_file))  # /path/to/backend
project_root = os.path.dirname(backend_dir)  # /path/to/project
DB_FILE = os.path.join(project_root, settings.database_file)

# Initialize services
price_service = PriceService()

from .api.ws import manager

# Background price fetching
async def fetch_prices_for_symbols(symbols: List[str]):
    """Fetch prices for symbols and broadcast updates"""
    conn = None
    try:
        # Ensure currency rates are initialized before any conversions
        currency_service.ensure_rates_initialized()
        
        prices = await multi_exchange_price_service.get_current_prices(symbols)
        
        if not prices:
            logger.warning("No prices fetched, skipping update")
            return
        
        # Update database with new prices
        conn = get_db_connection()
        cursor = conn.cursor()
        is_pg = is_postgres_connection(conn)
        
        for symbol, price in prices.items():
            # Get the base currency for this symbol from the database
            sql = _normalize_placeholders("SELECT DISTINCT base_currency FROM portfolio_items WHERE symbol = ?", is_pg)
            cursor.execute(sql, (symbol,))
            base_currencies = cursor.fetchall()
            
            for base_currency_row in base_currencies:
                base_currency = base_currency_row[0]
                
                # Convert USD price to the base currency if needed
                if base_currency != "USD":
                    converted_price = currency_service.convert_amount(price, "USD", base_currency)
                else:
                    converted_price = price
                
                # Update current_price for all items with this symbol and base currency
                if is_pg:
                    update_sql = (
                        "UPDATE portfolio_items "
                        "SET current_price = %s, current_value = amount * %s, updated_at = NOW() "
                        "WHERE symbol = %s AND base_currency = %s"
                    )
                else:
                    update_sql = (
                        "UPDATE portfolio_items "
                        "SET current_price = ?, current_value = amount * ?, updated_at = datetime('now') "
                        "WHERE symbol = ? AND base_currency = ?"
                    )
                cursor.execute(update_sql, (converted_price, converted_price, symbol, base_currency))
            
            # Calculate P&L for each item using USD-based calculations
            sql = _normalize_placeholders(
                "SELECT id, amount, price_buy, price_buy_usd, commission, commission_usd, base_currency, exchange_rate_at_purchase "
                "FROM portfolio_items WHERE symbol = ?",
                is_pg
            )
            cursor.execute(sql, (symbol,))
            
            items = cursor.fetchall()
            for item_id, amount, price_buy, price_buy_usd, commission, commission_usd, base_currency, exchange_rate_at_purchase in items:
                # Use USD values if available, otherwise calculate from display currency
                if price_buy_usd is None or commission_usd is None:
                    # Calculate USD values from display currency
                    if base_currency != "USD":
                        exchange_rate = exchange_rate_at_purchase if exchange_rate_at_purchase else currency_service.get_rate(base_currency)
                        price_buy_usd = price_buy / exchange_rate if exchange_rate else price_buy
                        commission_usd = commission / exchange_rate if exchange_rate else commission
                    else:
                        price_buy_usd = price_buy
                        commission_usd = commission
                
                # Use USD price for calculations
                current_value_usd = amount * price
                total_investment_usd = (amount * price_buy_usd) + commission_usd
                pnl_usd = current_value_usd - total_investment_usd
                pnl_percent_usd = (pnl_usd / total_investment_usd * 100) if total_investment_usd > 0 else 0
                
                # Convert to display currency for display
                if base_currency != "USD":
                    current_price_display = currency_service.convert_amount(price, "USD", base_currency)
                    current_value_display = currency_service.convert_amount(current_value_usd, "USD", base_currency)
                    pnl_display = currency_service.convert_amount(pnl_usd, "USD", base_currency)
                else:
                    current_price_display = price
                    current_value_display = current_value_usd
                    pnl_display = pnl_usd
                
                update_sql = _normalize_placeholders(
                    "UPDATE portfolio_items "
                    "SET current_price = ?, current_value = ?, pnl = ?, pnl_percent = ?, "
                    "current_price_usd = ?, current_value_usd = ?, pnl_usd = ?, pnl_percent_usd = ?, "
                    "price_buy_usd = ?, commission_usd = ? WHERE id = ?",
                    is_pg
                )
                cursor.execute(update_sql, (current_price_display, current_value_display, pnl_display, pnl_percent_usd,
                      price, current_value_usd, pnl_usd, pnl_percent_usd, 
                      price_buy_usd, commission_usd, item_id))
        
        conn.commit()
        
        # Update in-memory cache
        current_time = datetime.now(timezone.utc).isoformat()
        for symbol, price in prices.items():
            manager.price_cache[symbol] = {
                "price": price,
                "timestamp": current_time
            }
        
        # Broadcast updates via WebSocket
        for symbol, price in prices.items():
            await manager.broadcast_price_update(symbol, price)
        
        # Check and trigger alerts
        await check_and_trigger_alerts(prices)
            
        logger.info(f"Fetched and updated prices for {len(prices)} symbols")
        
    except Exception as e:
        logger.error(f"Error fetching prices: {e}", exc_info=True)
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

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
        
        # Wait 60 seconds before next fetch
        await asyncio.sleep(60)

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

from .services.notification_service import (
    send_telegram_notification,
    get_user_telegram_credentials,
    send_telegram_notification_with_credentials,
    send_user_telegram_notification,
)

async def check_missed_alerts_on_startup():
    """Check for alerts that may have been missed during downtime"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all active alerts
        if settings.database_url:
            cursor.execute("SELECT * FROM alerts WHERE is_active = TRUE")
        else:
            cursor.execute("SELECT * FROM alerts WHERE is_active = 1")
        alerts = cursor.fetchall()
        
        if not alerts:
            logger.info("No active alerts to check for missed triggers")
            conn.close()
            return
        
        logger.info(f"Checking {len(alerts)} active alerts for missed triggers")
        
        for alert in alerts:
            # Handle both schemas: SQLite may include extended columns, Postgres has core columns only
            alert_id = alert[0]
            user_id = alert[1]
            symbol = alert[2]
            threshold_price = alert[3]
            alert_type = alert[4]
            message = alert[5]
            # Optional fields that may not exist in Postgres schema
            base_currency = None
            threshold_price_usd = None
            exchange_rate_at_creation = None
            if len(alert) > 10:
                threshold_price_usd = alert[8]
                base_currency = alert[9]
                exchange_rate_at_creation = alert[10]
            
            # Get last price check for this symbol
            if settings.database_url:
                cursor.execute(
                    "SELECT last_check_timestamp, last_check_price FROM price_check_tracking WHERE symbol = %s",
                    (symbol,)
                )
            else:
                cursor.execute(
                    "SELECT last_check_timestamp, last_check_price FROM price_check_tracking WHERE symbol = ?",
                    (symbol,)
                )
            tracking = cursor.fetchone()
            
            if not tracking:
                # First time checking, skip historical check
                logger.debug(f"No price tracking data for {symbol}, skipping historical check")
                continue
            
            last_check_timestamp, last_check_price = tracking
            
            # Fetch historical prices from last check to now
            # Handle both 'Z' and '+00:00' timezone formats
            if last_check_timestamp.endswith('Z'):
                start_time = datetime.fromisoformat(last_check_timestamp.replace('Z', '+00:00'))
            else:
                start_time = datetime.fromisoformat(last_check_timestamp)
            start_ms = int(start_time.timestamp() * 1000)
            end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            
            # Skip if the time difference is too small (less than 1 minute)
            if end_ms - start_ms < 60000:
                logger.debug(f"Time difference too small for {symbol}, skipping historical check")
                continue
            
            logger.info(f"Checking historical prices for {symbol} from {start_time} to now")
            
            # Get historical data from Binance
            historical_prices = await price_service.get_historical_prices_for_range(
                symbol, start_ms, end_ms
            )
            
            if not historical_prices:
                logger.warning(f"No historical price data available for {symbol}")
                continue
            
            # Convert threshold price to USD if needed
            threshold_price_usd = threshold_price
            if base_currency and base_currency != "USD":
                try:
                    threshold_price_usd = currency_service.convert_amount(threshold_price, base_currency, "USD")
                    logger.debug(f"Converted {symbol} threshold from {base_currency} {threshold_price} to USD {threshold_price_usd}")
                except Exception as e:
                    logger.warning(f"Could not convert threshold price for {symbol}: {e}")
                    continue
            elif not base_currency and threshold_price > 100000:
                # Legacy alert without base_currency - assume CZK if price is very high
                try:
                    threshold_price_usd = currency_service.convert_amount(threshold_price, "CZK", "USD")
                    logger.debug(f"Converted legacy {symbol} threshold from CZK {threshold_price} to USD {threshold_price_usd}")
                except Exception as e:
                    logger.warning(f"Could not convert legacy threshold price for {symbol}: {e}")
                    continue
            
            # Check if threshold was crossed during downtime
            threshold_crossed = False
            trigger_price = None
            trigger_time = None
            
            for price_data in historical_prices:
                high = price_data['high']
                low = price_data['low']
                timestamp = price_data['timestamp']
                
                if alert_type == 'ABOVE' and high >= threshold_price_usd:
                    threshold_crossed = True
                    trigger_price = high
                    trigger_time = datetime.fromtimestamp(timestamp / 1000, timezone.utc)
                    break
                elif alert_type == 'BELOW' and low <= threshold_price_usd:
                    threshold_crossed = True
                    trigger_price = low
                    trigger_time = datetime.fromtimestamp(timestamp / 1000, timezone.utc)
                    break
            
            if threshold_crossed:
                logger.info(f"Found missed alert for {symbol} at {trigger_time} (price: ${trigger_price:,.2f})")
                # Trigger missed alert
                await trigger_alert(
                    alert_id, user_id, symbol, threshold_price, alert_type, 
                    message, trigger_price, trigger_time, was_missed=True
                )
            else:
                logger.debug(f"No threshold crossing found for {symbol} in historical data")
        
        conn.close()
        logger.info("Startup alert check completed")
        
    except Exception as e:
        logger.error(f"Error checking missed alerts: {e}")

async def trigger_alert(
    alert_id: int,
    user_id: int, 
    symbol: str,
    threshold_price: float,
    alert_type: str,
    message: str,
    trigger_price: float,
    trigger_time: datetime,
    was_missed: bool = False,
    conn: Optional[sqlite3.Connection] = None
):
    """Trigger an alert and send notifications"""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True
    
    try:
        cursor = conn.cursor()
        is_pg = is_postgres_connection(conn)
        
        # Get portfolio information for this symbol
        # First, get all base currencies for this symbol
        if is_pg:
            cursor.execute("""
                SELECT DISTINCT base_currency 
                FROM portfolio_items 
                WHERE symbol = %s AND base_currency IS NOT NULL
            """, (symbol,))
        else:
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
                converted_price = currency_service.convert_amount(trigger_price, "USD", base_currency)
            else:
                converted_price = trigger_price
            
            # Get portfolio data for this base currency
            if is_pg:
                cursor.execute("""
                    SELECT 
                        SUM(amount) as total_amount,
                        SUM(amount * price_buy + commission) as total_investment,
                        SUM(amount * %s) as current_value,
                        base_currency
                    FROM portfolio_items 
                    WHERE symbol = %s AND base_currency = %s
                    GROUP BY base_currency
                """, (converted_price, symbol, base_currency))
            else:
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
        
        # Log alert history with missed flag
        check_type = 'historical' if was_missed else 'realtime'
        # Format timestamp for database
        if is_pg:
            # PostgreSQL: format as ISO timestamp without timezone
            # Convert to UTC first, then format without timezone info
            if trigger_time.tzinfo:
                # Convert to UTC if timezone-aware
                trigger_time_utc = trigger_time.astimezone(timezone.utc)
            else:
                # Assume UTC if timezone-naive
                trigger_time_utc = trigger_time.replace(tzinfo=timezone.utc)
            # Format as ISO string: YYYY-MM-DDTHH:MM:SS[.microseconds]
            # Use strftime to avoid timezone suffix issues
            trigger_timestamp = trigger_time_utc.strftime('%Y-%m-%dT%H:%M:%S')
            # Add microseconds if present
            if trigger_time_utc.microsecond:
                trigger_timestamp += f".{trigger_time_utc.microsecond:06d}"
        else:
            # SQLite: use ISO format with Z
            trigger_timestamp = trigger_time.isoformat() + "Z"
        
        if is_pg:
            # PostgreSQL schema doesn't have symbol column
            cursor.execute('''
                INSERT INTO alert_history 
                (alert_id, user_id, triggered_price, triggered_at, was_missed, check_type)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (alert_id, user_id, trigger_price, trigger_timestamp, was_missed, check_type))
        else:
            # SQLite schema has symbol column
            cursor.execute('''
                INSERT INTO alert_history 
                (alert_id, user_id, symbol, triggered_price, triggered_at, was_missed, check_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (alert_id, user_id, symbol, trigger_price, trigger_timestamp, was_missed, check_type))
        
        # Deactivate the alert (one-time alert behavior)
        if is_pg:
            cursor.execute("UPDATE alerts SET is_active = FALSE WHERE id = %s", (alert_id,))
        else:
            cursor.execute("UPDATE alerts SET is_active = 0 WHERE id = ?", (alert_id,))
        
        # Prepare notification message
        alert_message = f"🚨 <b>Price Alert Triggered!</b>\n\n"
        if was_missed:
            alert_message += "⚠️ <b>Missed Alert Recovered</b>\n"
            alert_message += f"Alert was triggered at: {trigger_time.strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
        
        alert_message += f"📈 <b>Symbol:</b> {symbol}\n"
        alert_message += f"💰 <b>Trigger Price:</b> ${trigger_price:,.2f}\n"
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
        alert_message += f"\n⏰ <b>Time:</b> {trigger_time.strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Don't commit here when conn is passed in - let caller manage transaction
        # Only commit if we created the connection ourselves
        if should_close:
            conn.commit()
        
        # Send notifications
        await send_user_telegram_notification(user_id, alert_message)
        await manager.send_alert_triggered({
            'alert_id': alert_id,
            'symbol': symbol,
            'current_price': trigger_price,
            'threshold_price': threshold_price,
            'alert_type': alert_type,
            'message': message,
            'was_missed': was_missed,
            'trigger_time': trigger_time.isoformat()
        })
        
        logger.info(f"Triggered alert {alert_id} ({'missed' if was_missed else 'realtime'})")
        
    except Exception as e:
        logger.error(f"Error triggering alert {alert_id}: {e}")
        # Only rollback if we created the connection ourselves
        # If conn was passed in, caller will handle savepoint/rollback
        if should_close and conn:
            try:
                conn.rollback()
            except Exception as rollback_error:
                logger.error(f"Error during rollback in trigger_alert: {rollback_error}")
            conn.close()
    finally:
        # Only close if we created the connection (should_close = True)
        if should_close and conn:
            conn.close()

async def check_and_trigger_alerts(current_prices: Dict[str, float]):
    """Check all active alerts against current prices and trigger notifications"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        is_pg = is_postgres_connection(conn)
        
        current_time = datetime.now(timezone.utc)
        
        # Update price check tracking for all symbols
        # Commit price tracking updates separately to avoid transaction issues
        try:
            for symbol, price in current_prices.items():
                if is_pg:
                    # PostgreSQL: use ON CONFLICT
                    cursor.execute('''
                        INSERT INTO price_check_tracking 
                        (symbol, last_check_timestamp, last_check_price, updated_at)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (symbol) DO UPDATE SET
                            last_check_timestamp = EXCLUDED.last_check_timestamp,
                            last_check_price = EXCLUDED.last_check_price,
                            updated_at = EXCLUDED.updated_at
                    ''', (symbol, current_time.isoformat(), price, current_time.isoformat()))
                else:
                    # SQLite: use INSERT OR REPLACE
                    cursor.execute('''
                        INSERT OR REPLACE INTO price_check_tracking 
                        (symbol, last_check_timestamp, last_check_price, updated_at)
                        VALUES (?, ?, ?, ?)
                    ''', (symbol, current_time.isoformat(), price, current_time.isoformat()))
            
            # Commit price tracking before processing alerts
            conn.commit()
        except Exception as e:
            logger.error(f"Error updating price tracking: {e}")
            conn.rollback()
        
        # Get all active alerts
        if settings.database_url:
            cursor.execute("SELECT * FROM alerts WHERE is_active = TRUE")
        else:
            cursor.execute("SELECT * FROM alerts WHERE is_active = 1")
        alerts = cursor.fetchall()
        
        triggered_count = 0
        
        for alert in alerts:
            # Handle both schemas: SQLite may include extended columns, Postgres has core columns only
            alert_id = alert[0]
            user_id = alert[1]
            symbol = alert[2]
            threshold_price = alert[3]
            alert_type = alert[4]
            message = alert[5]
            is_active = alert[6]
            created_at = alert[7]
            # Optional fields that may not exist in Postgres schema
            threshold_price_usd = None
            base_currency = None
            exchange_rate_at_creation = None
            if len(alert) > 8:
                threshold_price_usd = alert[8]
            if len(alert) > 9:
                base_currency = alert[9]
            if len(alert) > 10:
                exchange_rate_at_creation = alert[10]
            
            if symbol not in current_prices:
                continue
            
            current_price = current_prices[symbol]
            should_trigger = False
            
            # Convert threshold price to USD for comparison (current_price is in USD)
            effective_threshold_usd = threshold_price_usd
            
            # If threshold_price_usd is NULL or 0, convert from base currency
            if not effective_threshold_usd or effective_threshold_usd == 0:
                if base_currency and base_currency != "USD":
                    try:
                        effective_threshold_usd = currency_service.convert_amount(threshold_price, base_currency, "USD")
                        logger.debug(f"Converted {symbol} threshold from {base_currency} {threshold_price} to USD {effective_threshold_usd}")
                    except Exception as e:
                        logger.warning(f"Could not convert threshold price for {symbol}: {e}")
                        continue
                elif not base_currency:
                    # Legacy alert without base_currency - try to infer from threshold price
                    # If threshold is very high, assume CZK; otherwise assume it's already in USD
                    if threshold_price > 100:
                        try:
                            effective_threshold_usd = currency_service.convert_amount(threshold_price, "CZK", "USD")
                            logger.debug(f"Converted legacy {symbol} threshold from CZK {threshold_price} to USD {effective_threshold_usd}")
                        except Exception as e:
                            logger.warning(f"Could not convert legacy threshold price for {symbol}: {e}")
                            # Try USD as-is
                            effective_threshold_usd = threshold_price
                    else:
                        # Assume already in USD (or EUR - try both)
                        effective_threshold_usd = threshold_price
                else:
                    effective_threshold_usd = threshold_price
            
            # Check if alert should trigger (comparing USD to USD)
            if alert_type == 'ABOVE' and current_price >= effective_threshold_usd:
                should_trigger = True
            elif alert_type == 'BELOW' and current_price <= effective_threshold_usd:
                should_trigger = True
            
            if should_trigger:
                # Use savepoint for each alert to prevent transaction abort cascading
                savepoint_name = f"alert_{alert_id}_{int(current_time.timestamp() * 1000)}"
                try:
                    if is_pg:
                        # Create savepoint before triggering alert
                        cursor.execute(f"SAVEPOINT {savepoint_name}")
                    
                    await trigger_alert(
                        alert_id, user_id, symbol, threshold_price, alert_type,
                        message, current_price, current_time, was_missed=False,
                        conn=conn
                    )
                    triggered_count += 1
                    
                    if is_pg:
                        # Release savepoint on success
                        cursor.execute(f"RELEASE SAVEPOINT {savepoint_name}")
                        conn.commit()
                except Exception as e:
                    logger.error(f"Error triggering alert {alert_id} in batch: {e}")
                    # Rollback to savepoint for PostgreSQL to continue with next alert
                    if is_pg:
                        try:
                            cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
                            cursor.execute(f"RELEASE SAVEPOINT {savepoint_name}")
                        except Exception as savepoint_error:
                            # If savepoint operations fail, do full rollback
                            logger.error(f"Error with savepoint for alert {alert_id}: {savepoint_error}")
                            try:
                                conn.rollback()
                            except Exception as rollback_error:
                                logger.error(f"Error during rollback for alert {alert_id}: {rollback_error}")
        
        # No final commit needed - PostgreSQL commits per alert, SQLite commits at end
        if not is_pg:
            conn.commit()
        
        if triggered_count > 0:
            logger.info(f"Triggered {triggered_count} alerts in real-time check")
        
    except Exception as e:
        logger.error(f"Error checking alerts: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

from .schemas.portfolio import PortfolioItem, PortfolioCreate, PortfolioUpdate
from .schemas.alerts import PriceAlert, PriceAlertCreate, PriceAlertUpdate
from .schemas.common import TrackedSymbol, CryptoSymbol, CryptoSymbolSearch
from .schemas.auth import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
    PasswordResetRequest,
    PasswordResetConfirm,
    UserProfileUpdate,
    PasswordChange,
    AccountDeletionConfirm,
    BinanceCredentials,
    BitfinexCredentials,
    BitfinexCredentialsResponse,
    BitfinexTestResponse,
    BinanceCredentialsResponse,
    BinanceTestResponse,
)
from .schemas.csv_import import CSVUploadResponse, CSVExecuteRequest

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
            -- New USD-based columns for calculations
            price_buy_usd REAL,
            commission_usd REAL,
            current_price_usd REAL,
            current_value_usd REAL,
            pnl_usd REAL,
            pnl_percent_usd REAL,
            -- Exchange rate at time of purchase
            exchange_rate_at_purchase REAL,
            comments TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    # Add comments column if it doesn't exist (for existing databases)
    try:
        cursor.execute('ALTER TABLE portfolio_items ADD COLUMN comments TEXT')
    except Exception:
        pass  # Column already exists

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
            -- New USD-based columns for calculations
            threshold_price_usd REAL,
            base_currency TEXT,
            exchange_rate_at_creation REAL,
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

    # Create crypto_symbols table for storing available cryptocurrencies
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crypto_symbols (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            market_cap_rank INTEGER,
            last_updated TEXT NOT NULL,
            created_at TEXT NOT NULL
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
            was_missed BOOLEAN DEFAULT 0,
            check_type TEXT DEFAULT 'realtime',
            FOREIGN KEY (alert_id) REFERENCES alerts (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Create price_check_tracking table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_check_tracking (
            symbol TEXT PRIMARY KEY,
            last_check_timestamp TEXT NOT NULL,
            last_check_price REAL NOT NULL,
            updated_at TEXT NOT NULL
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
    
    # Add default_alert_percentage_above column to existing users table if it doesn't exist
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN default_alert_percentage_above REAL DEFAULT 60.0")
        logger.info("✅ Added default_alert_percentage_above column to users table")
    except sqlite3.OperationalError:
        # Column already exists, ignore
        pass
    
    # Add default_alert_percentage_below column to existing users table if it doesn't exist
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN default_alert_percentage_below REAL DEFAULT 20.0")
        logger.info("✅ Added default_alert_percentage_below column to users table")
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
    
    # Add new USD-based columns to portfolio_items table if they don't exist
    try:
        cursor.execute("ALTER TABLE portfolio_items ADD COLUMN price_buy_usd REAL")
        logger.info("✅ Added price_buy_usd column to portfolio_items table")
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("ALTER TABLE portfolio_items ADD COLUMN commission_usd REAL")
        logger.info("✅ Added commission_usd column to portfolio_items table")
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("ALTER TABLE portfolio_items ADD COLUMN current_price_usd REAL")
        logger.info("✅ Added current_price_usd column to portfolio_items table")
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("ALTER TABLE portfolio_items ADD COLUMN current_value_usd REAL")
        logger.info("✅ Added current_value_usd column to portfolio_items table")
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("ALTER TABLE portfolio_items ADD COLUMN pnl_usd REAL")
        logger.info("✅ Added pnl_usd column to portfolio_items table")
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("ALTER TABLE portfolio_items ADD COLUMN pnl_percent_usd REAL")
        logger.info("✅ Added pnl_percent_usd column to portfolio_items table")
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("ALTER TABLE portfolio_items ADD COLUMN exchange_rate_at_purchase REAL")
        logger.info("✅ Added exchange_rate_at_purchase column to portfolio_items table")
    except sqlite3.OperationalError:
        pass
    
    # Add new USD-based columns to alerts table if they don't exist
    try:
        cursor.execute("ALTER TABLE alerts ADD COLUMN threshold_price_usd REAL")
        logger.info("✅ Added threshold_price_usd column to alerts table")
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("ALTER TABLE alerts ADD COLUMN base_currency TEXT")
        logger.info("✅ Added base_currency column to alerts table")
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("ALTER TABLE alerts ADD COLUMN exchange_rate_at_creation REAL")
        logger.info("✅ Added exchange_rate_at_creation column to alerts table")
    except sqlite3.OperationalError:
        pass
    
    # Add new columns to alert_history table if they don't exist
    try:
        cursor.execute("ALTER TABLE alert_history ADD COLUMN was_missed BOOLEAN DEFAULT 0")
        logger.info("✅ Added was_missed column to alert_history table")
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("ALTER TABLE alert_history ADD COLUMN check_type TEXT DEFAULT 'realtime'")
        logger.info("✅ Added check_type column to alert_history table")
    except sqlite3.OperationalError:
        pass
    
    # Create import history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS import_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            import_date TEXT NOT NULL,
            items_imported INTEGER NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create user API credentials table (encrypted storage)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_api_credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            exchange TEXT NOT NULL,
            encrypted_credentials TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, exchange)
        )
    ''')
    
    # Create CSV import mappings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS csv_import_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            exchange TEXT NOT NULL,
            column_mapping TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_used TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, exchange)
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("✅ Database initialized with user management and import functionality")

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
    """Get database connection with retry logic: use Postgres when DATABASE_URL is set (or in production), otherwise SQLite."""
    # Use retry logic for runtime connections (max 3 retries, faster backoff)
    return connect_with_retry(max_retries=3, initial_delay=0.5, max_delay=2.0, is_startup=False)

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
    """Convert a portfolio item to target currency using USD-based calculations"""
    if item["base_currency"] == target_currency:
        # Ensure total_investment_text is properly formatted even without conversion
        if not item.get("total_investment_text") or not any(symbol in item.get("total_investment_text", "") for symbol in ["$", "€", "Kč", "£", "¥"]):
            total_investment = (item["amount"] * item["price_buy"]) + item.get("commission", 0)
            item["total_investment_text"] = format_total_investment_text(total_investment, target_currency)
        return item

    try:
        # Use USD values for calculations if available, otherwise convert from display currency
        if item.get("price_buy_usd") is not None:
            # Use stored USD values for accurate calculations
            price_buy_usd = item["price_buy_usd"]
            commission_usd = item.get("commission_usd", 0)
            current_value_usd = item.get("current_value_usd", 0)
            pnl_usd = item.get("pnl_usd", 0)
        else:
            # Fallback: convert from display currency to USD
            price_buy_usd = currency_service.convert_amount(item["price_buy"], item["base_currency"], "USD")
            commission_usd = currency_service.convert_amount(item.get("commission", 0), item["base_currency"], "USD")
            current_value_usd = currency_service.convert_amount(item.get("current_value", 0), item["base_currency"], "USD") if item.get("current_value") else 0
            pnl_usd = currency_service.convert_amount(item.get("pnl", 0), item["base_currency"], "USD") if item.get("pnl") else 0
        
        # Convert USD values to target currency for display
        converted_price_buy = currency_service.convert_amount(price_buy_usd, "USD", target_currency)
        converted_commission = currency_service.convert_amount(commission_usd, "USD", target_currency)
        converted_current_value = currency_service.convert_amount(current_value_usd, "USD", target_currency) if current_value_usd else None
        converted_pnl = currency_service.convert_amount(pnl_usd, "USD", target_currency) if pnl_usd else None
        
        # Convert current price for display
        converted_current_price = None
        if item.get("current_price_usd") is not None:
            converted_current_price = currency_service.convert_amount(item["current_price_usd"], "USD", target_currency)
        elif item.get("current_price"):
            converted_current_price = currency_service.convert_amount(item["current_price"], item["base_currency"], target_currency)

        # Calculate total investment in target currency
        total_investment = (item["amount"] * converted_price_buy) + converted_commission
        
        # Calculate P&L percentage using USD values for accuracy
        pnl_percent = item.get("pnl_percent_usd") if item.get("pnl_percent_usd") is not None else item.get("pnl_percent", 0)
        
        return {
            **item,
            "base_currency": target_currency,
            "price_buy": round(converted_price_buy, 8),
            "current_price": round(converted_current_price, 8) if converted_current_price else None,
            "current_value": round(converted_current_value, 8) if converted_current_value else None,
            "pnl": round(converted_pnl, 8) if converted_pnl else None,
            "pnl_percent": round(pnl_percent, 8),
            "commission": round(converted_commission, 8),
            "total_investment_text": format_total_investment_text(total_investment, target_currency)
        }
    except Exception as e:
        logger.error(f"Currency conversion error: {e}")
        return item


def verify_database_connection_and_schema():
    """
    Verify database connection and check if schema already exists.
    Returns (is_connected, schema_exists, has_data)
    """
    try:
        conn = connect_with_retry(max_retries=3, initial_delay=1.0, max_delay=5.0, is_startup=False)
        cur = conn.cursor()
        
        # Check if users table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'users'
            );
        """)
        schema_exists = cur.fetchone()[0]
        
        # If schema exists, check if there's data
        has_data = False
        if schema_exists:
            cur.execute("SELECT COUNT(*) FROM users")
            user_count = cur.fetchone()[0]
            has_data = user_count > 0
            logger.info(f"✅ Database schema exists with {user_count} users")
        
        cur.close()
        conn.close()
        return True, schema_exists, has_data
    except Exception as e:
        logger.error(f"❌ Database verification failed: {str(e)}")
        return False, False, False

def init_postgres_database():
    """Initialize PostgreSQL database schema with retry logic.
    NEVER creates tables if database is not available or if schema already exists with data.
    """
    logger.info("🔄 Verifying database connection and schema...")
    
    # First, verify database is available
    is_connected, schema_exists, has_data = verify_database_connection_and_schema()
    
    if not is_connected:
        error_msg = "❌ Database is not available. Cannot initialize schema. Aborting table creation."
        logger.error(error_msg)
        raise ConnectionError(error_msg)
    
    if schema_exists and has_data:
        logger.info("✅ Database schema already exists with customer data. Skipping table creation.")
        logger.info("⚠️ NEVER create tables when database has existing customer data.")
        return  # Schema exists with data - do NOT create tables
    
    if schema_exists and not has_data:
        logger.info("⚠️ Database schema exists but is empty. Skipping table creation (tables may be created by migration).")
        return  # Schema exists but empty - might be a fresh database, but safer to skip
    
    # Only create tables if schema doesn't exist at all (new database)
    logger.info("📋 Database schema does not exist. Creating tables...")
    try:
        # Use retry logic for startup (max 5 retries, exponential backoff)
        conn = connect_with_retry(max_retries=5, initial_delay=2.0, max_delay=30.0, is_startup=True)
        cur = conn.cursor()
        
        # Create users table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            full_name TEXT,
            preferred_currency TEXT DEFAULT 'USD',
            is_active BOOLEAN DEFAULT TRUE,
            is_verified BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            telegram_bot_token TEXT,
            telegram_chat_id TEXT,
            default_alert_percentage_above REAL DEFAULT 0.10,
            default_alert_percentage_below REAL DEFAULT 0.10
        )
    ''')
        
        # Create password reset tokens table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')
        
        # Create user sessions table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS user_sessions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')
        
        # Create portfolio_items table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS portfolio_items (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            symbol TEXT NOT NULL,
            amount REAL NOT NULL,
            price_buy REAL NOT NULL,
            purchase_date TIMESTAMP,
            base_currency TEXT NOT NULL,
            purchase_price_eur REAL,
            purchase_price_czk REAL,
            source TEXT,
            commission REAL DEFAULT 0.0,
            total_investment_text TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            current_price REAL,
            current_value REAL,
            pnl REAL,
            pnl_percent REAL,
            price_buy_usd REAL,
            commission_usd REAL,
            current_price_usd REAL,
            current_value_usd REAL,
            pnl_usd REAL,
            pnl_percent_usd REAL,
            exchange_rate_at_purchase REAL,
            comments TEXT
        )
    ''')
        # Add comments column if it doesn't exist (for existing databases)
        try:
            cur.execute('ALTER TABLE portfolio_items ADD COLUMN comments TEXT')
        except Exception:
            pass  # Column already exists
        
        # Create alerts table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            symbol TEXT NOT NULL,
            threshold_price REAL NOT NULL,
            alert_type TEXT NOT NULL,
            message TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')
        
        # Ensure alerts.id has a working sequence and default nextval (simple, robust approach)
        cur.execute("""
            CREATE SEQUENCE IF NOT EXISTS alerts_id_seq;
        """)
        cur.execute("""
            ALTER TABLE alerts ALTER COLUMN id SET DEFAULT nextval('alerts_id_seq');
        """)
        cur.execute("""
            SELECT setval('alerts_id_seq', COALESCE((SELECT MAX(id) FROM alerts), 0) + 1, false);
        """)
        
        # Create tracked_symbols table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS tracked_symbols (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            active BOOLEAN DEFAULT TRUE,
            last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, symbol)
        )
    ''')
        
        # Create alert_history table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS alert_history (
            id SERIAL PRIMARY KEY,
            alert_id INTEGER REFERENCES alerts(id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            triggered_price REAL NOT NULL,
            triggered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            was_missed BOOLEAN DEFAULT FALSE,
            check_type TEXT DEFAULT 'realtime'
        )
    ''')
        
        # Create price_check_tracking table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS price_check_tracking (
            symbol TEXT PRIMARY KEY,
            last_check_timestamp TEXT NOT NULL,
            last_check_price REAL NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
        
        # Create import_history table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS import_history (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            source TEXT NOT NULL,
            import_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            items_imported INTEGER NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')
        
        # Create currency_rates table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS currency_rates (
            id SERIAL PRIMARY KEY,
            from_currency TEXT NOT NULL,
            to_currency TEXT NOT NULL,
            rate REAL NOT NULL,
            timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')
        
        # Create price_check_tracking table (used for missed-alert logic)
        cur.execute('''
        CREATE TABLE IF NOT EXISTS price_check_tracking (
            symbol TEXT PRIMARY KEY,
            last_check_timestamp TIMESTAMP,
            last_check_price REAL
        )
    ''')
        
        # Create crypto_symbols table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS crypto_symbols (
            id SERIAL PRIMARY KEY,
            symbol TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            market_cap_rank INTEGER,
            last_updated TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')
        
        # Create user_api_credentials table (encrypted storage)
        cur.execute('''
        CREATE TABLE IF NOT EXISTS user_api_credentials (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            exchange TEXT NOT NULL,
            encrypted_credentials TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, exchange)
        )
    ''')
        
        # Create csv_import_mappings table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS csv_import_mappings (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            exchange TEXT NOT NULL,
            column_mapping TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_used TIMESTAMP,
            UNIQUE(user_id, exchange)
        )
    ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ PostgreSQL schema initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize PostgreSQL database after retries: {str(e)}")
        logger.warning("⚠️ Database initialization failed, but continuing startup. Database might be ready later.")
        # Don't raise - allow service to start even if initialization fails
        # The retry logic in get_db_connection() will handle runtime connections
        # Re-raise only if we want to fail fast during startup
        # For now, we'll let it fail and handle in lifespan()
        raise

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # Ensure file handler is attached (uvicorn may have reconfigured logging)
    import logging
    root_logger = logging.getLogger()
    from .utils.logger import _setup_file_handler
    file_handler = _setup_file_handler()
    if file_handler not in root_logger.handlers:
        root_logger.addHandler(file_handler)
        logger.info("✅ File handler re-attached to root logger")
    
    if settings.database_url:
        logger.info("🚀 Starting Crypto AI Agent API v2.0 (PostgreSQL Mode)")
        try:
            # Verify database is available before attempting initialization
            is_connected, schema_exists, has_data = verify_database_connection_and_schema()
            if not is_connected:
                logger.error("❌ Database is not available. Service will start but will fail health checks.")
                logger.error("❌ Deployment should verify database availability before switching traffic.")
            elif has_data:
                logger.info("✅ Database is available with customer data. No table creation needed.")
            else:
                # Only initialize if database is available but empty
                init_postgres_database()
            logger.info("✅ Database verification/initialization complete")
        except Exception as e:
            logger.error(f"❌ Database initialization failed during startup: {str(e)}")
            logger.error("❌ Service will start but will fail health checks until database is available.")
            logger.error("❌ Deployment scripts should verify database before switching traffic.")
            # Continue startup - but health checks will fail until database is available
    else:
        logger.info("🚀 Starting Crypto AI Agent API v2.0 (SQLite Mode)")
    
    # Initialize database (only for SQLite)
    if not settings.database_url:
        init_database()
        logger.info("✅ Database initialized")
    
    # Load migration data if exists (SQLite only)
    if not settings.database_url:
        load_migration_data()
    
    # Initialize currency service
    await currency_service.get_exchange_rates()
    logger.info("✅ Currency service initialized")
    
    # Check for missed alerts on startup
    await check_missed_alerts_on_startup()
    logger.info("✅ Missed alert check completed")
    
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

from .utils.db import (
    is_postgres_connection as _is_postgres_connection,
    normalize_placeholders as _normalize_placeholders,
    execute_insert_and_get_id as _execute_insert_and_get_id,
)

from .api.auth import router as auth_router
app.include_router(auth_router)

# Portfolio endpoints
from .api.portfolio import router as portfolio_router
app.include_router(portfolio_router)

from .api.alerts import router as alerts_router
app.include_router(alerts_router)

from .api.prices import router as prices_router
app.include_router(prices_router)

from .api.csv_import import router as csv_import_router
app.include_router(csv_import_router)

from .api.exchange_imports import router as exchange_imports_router
app.include_router(exchange_imports_router)

from .api.ws import router as ws_router
app.include_router(ws_router)

# All endpoints have been moved to modular routers in app/api/
# Import endpoints: app/api/exchange_imports.py
# CSV import endpoints: app/api/csv_import.py

from .api.health import router as health_router
app.include_router(health_router)

if __name__ == "__main__":
    pass
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
