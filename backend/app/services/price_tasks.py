"""Background tasks for price fetching and updates"""
from typing import List
import asyncio
from datetime import datetime, timezone
from ..services.currency_service import currency_service
from ..services.price_service import PriceService
from ..services.multi_exchange_price_service import multi_exchange_price_service
from ..dependencies.auth import get_db_connection
from ..core.config import settings
from ..api.ws import manager
from ..utils.db import normalize_placeholders as _normalize_placeholders
try:
    from utils.logger import get_logger
except Exception:  # pragma: no cover
    from ..utils.logger import get_logger

logger = get_logger("backend.app.services.price_tasks")

# Initialize price service
price_service = PriceService()


async def fetch_prices_for_symbols(symbols: List[str]):
    """Fetch prices for symbols and broadcast updates"""
    conn = None
    try:
        # Ensure currency rates are initialized before any conversions
        currency_service.ensure_rates_initialized()

        # Fetch prices from external APIs (may be in USD or USDT)
        prices_from_api = await multi_exchange_price_service.get_current_prices(symbols)

        if not prices_from_api:
            logger.warning("No prices fetched, skipping update")
            return

        # Normalize all prices to USD before storing
        # Note: Binance returns USDT prices, but USDT ≈ USD (1:1), so we treat them as USD
        prices_usd = {}
        for symbol, price in prices_from_api.items():
            # Prices from multi_exchange_price_service are already in USD/USDT
            # USDT is treated as equivalent to USD (1:1 stablecoin)
            # So we can store directly as USD
            prices_usd[symbol] = price

        # Update centralized crypto_prices table with UPSERT logic
        conn = get_db_connection()
        cursor = conn.cursor()

        # Store USD prices in crypto_prices table (centralized storage)
        for symbol, price_usd in prices_usd.items():
            # UPSERT: Insert or update price in crypto_prices table
            upsert_sql = _normalize_placeholders(
                """
                INSERT INTO crypto_prices (symbol, price_usd, updated_at, created_at)
                VALUES (%s, %s, NOW(), COALESCE((SELECT created_at FROM crypto_prices WHERE symbol = %s), NOW()))
                ON CONFLICT (symbol) DO UPDATE SET
                    price_usd = EXCLUDED.price_usd,
                    updated_at = NOW()
                """
            )
            cursor.execute(upsert_sql, (symbol, price_usd, symbol))

        # Now update portfolio_items from centralized USD prices
        for symbol, price_usd in prices_usd.items():
            # Get the base currency for this symbol from the database
            sql = _normalize_placeholders("SELECT DISTINCT base_currency FROM portfolio_items WHERE symbol = ?")
            cursor.execute(sql, (symbol,))
            base_currencies = cursor.fetchall()

            for base_currency_row in base_currencies:
                base_currency = base_currency_row[0]

                # Convert USD price to the base currency if needed
                if base_currency != "USD":
                    converted_price = currency_service.convert_amount(price_usd, "USD", base_currency)
                else:
                    converted_price = price_usd

                # Update current_price for all items with this symbol and base currency
                update_sql = (
                    "UPDATE portfolio_items "
                    "SET current_price = %s, current_value = amount * %s, updated_at = NOW() "
                    "WHERE symbol = %s AND base_currency = %s"
                )
                cursor.execute(update_sql, (converted_price, converted_price, symbol, base_currency))

            # Calculate P&L for each item using USD-based calculations
            sql = _normalize_placeholders(
                "SELECT id, amount, price_buy, price_buy_usd, commission, commission_usd, base_currency, exchange_rate_at_purchase "
                "FROM portfolio_items WHERE symbol = ?"
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
                current_value_usd = amount * price_usd
                total_investment_usd = (amount * price_buy_usd) + commission_usd
                pnl_usd = current_value_usd - total_investment_usd
                pnl_percent_usd = (pnl_usd / total_investment_usd * 100) if total_investment_usd > 0 else 0

                # Convert to display currency for display
                if base_currency != "USD":
                    current_price_display = currency_service.convert_amount(price_usd, "USD", base_currency)
                    current_value_display = currency_service.convert_amount(current_value_usd, "USD", base_currency)
                    pnl_display = currency_service.convert_amount(pnl_usd, "USD", base_currency)
                else:
                    current_price_display = price_usd
                    current_value_display = current_value_usd
                    pnl_display = pnl_usd

                update_sql = _normalize_placeholders(
                    "UPDATE portfolio_items "
                    "SET current_price = ?, current_value = ?, pnl = ?, pnl_percent = ?, "
                    "current_price_usd = ?, current_value_usd = ?, pnl_usd = ?, pnl_percent_usd = ?, "
                    "price_buy_usd = ?, commission_usd = ? WHERE id = ?"
                )
                cursor.execute(update_sql, (current_price_display, current_value_display, pnl_display, pnl_percent_usd,
                      price_usd, current_value_usd, pnl_usd, pnl_percent_usd,
                      price_buy_usd, commission_usd, item_id))

        conn.commit()

        # Update in-memory cache (using USD prices)
        current_time = datetime.now(timezone.utc).isoformat()
        for symbol, price_usd in prices_usd.items():
            manager.price_cache[symbol] = {
                "price": price_usd,
                "timestamp": current_time
            }

        # Broadcast updates via WebSocket (using USD prices)
        for symbol, price_usd in prices_usd.items():
            await manager.broadcast_price_update(symbol, price_usd)

        # Check and trigger alerts (using USD prices)
        from ..services.notification_service import check_and_trigger_alerts
        await check_and_trigger_alerts(prices_usd)

        logger.info(f"Fetched and updated prices for {len(prices_usd)} symbols")

    except Exception as e:
        logger.error(f"Error fetching prices: {e}", exc_info=True)
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


async def background_price_fetcher():
    """Background task to periodically fetch prices for all unique symbols in database"""
    while True:
        try:
            # Query all unique symbols from portfolio_items table
            conn = get_db_connection()
            cursor = conn.cursor()
            sql = _normalize_placeholders(
                "SELECT DISTINCT symbol FROM portfolio_items WHERE symbol IS NOT NULL"
            )
            cursor.execute(sql)
            rows = cursor.fetchall()
            conn.close()

            all_symbols = [row[0] for row in rows if row[0]]

            if all_symbols:
                await fetch_prices_for_symbols(all_symbols)
                logger.info(f"📊 Fetched prices for {len(all_symbols)} unique symbols from database")
            else:
                logger.debug("No symbols found in database to fetch prices for")
        except Exception as e:
            logger.error(f"Error in background price fetcher: {e}", exc_info=True)

        # Wait configured interval (default: 300 seconds = 5 minutes) before next fetch
        await asyncio.sleep(settings.price_update_interval_seconds)
