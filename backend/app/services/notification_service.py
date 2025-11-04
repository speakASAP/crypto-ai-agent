import os
import ssl
import aiohttp
from typing import Optional, Dict
from datetime import datetime, timezone
from ..core.config import settings
from ..utils.db import normalize_placeholders as _normalize_placeholders
from ..dependencies.auth import get_db_connection
from ..services.currency_service import currency_service
from ..services.price_service import PriceService
from ..api.ws import manager
try:
    from utils.logger import get_logger
except Exception:  # pragma: no cover
    from ..utils.logger import get_logger


logger = get_logger("backend.app.services.notification_service")

# Initialize price service for alert checking
price_service = PriceService()


async def send_telegram_notification(message: str) -> bool:
    try:
        telegram_token = os.getenv('TELEGRAM_TOKEN') or settings.telegram_bot_token
        telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID') or settings.telegram_chat_id

        if not telegram_token or not telegram_chat_id:
            logger.warning("Telegram credentials not found in environment variables or settings")
            return False

        url = f"{settings.telegram_api_url}{telegram_token}/sendMessage"
        data = {"chat_id": telegram_chat_id, "text": message, "parse_mode": "HTML"}

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
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = _normalize_placeholders(
            "SELECT telegram_bot_token, telegram_chat_id FROM users WHERE id = %s"
        )
        cursor.execute(sql, (user_id,))
        result = cursor.fetchone()
        conn.close()

        if result and result[0] and result[1]:
            return {'bot_token': result[0], 'chat_id': result[1]}
        return None
    except Exception as e:
        logger.error(f"Error getting user Telegram credentials: {e}")
        return None


async def send_telegram_notification_with_credentials(message: str, bot_token: str, chat_id: str) -> bool:
    try:
        url = f"{settings.telegram_api_url}{bot_token}/sendMessage"
        data = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}

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


async def send_user_telegram_notification(user_id: int, message: str) -> bool:
    try:
        user_credentials = get_user_telegram_credentials(user_id)
        if user_credentials and user_credentials['bot_token'] and user_credentials['chat_id']:
            logger.info(f"Using user-specific Telegram credentials for user {user_id}")
            return await send_telegram_notification_with_credentials(
                message,
                user_credentials['bot_token'],
                user_credentials['chat_id'],
            )
        else:
            logger.info(f"Using global Telegram credentials for user {user_id} (no user settings)")
            return await send_telegram_notification(message)
    except Exception as e:
        logger.error(f"Error sending Telegram notification for user {user_id}: {e}")
        return False


async def check_missed_alerts_on_startup():
    """Check for alerts that may have been missed during downtime"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get all active alerts
        cursor.execute("SELECT * FROM alerts WHERE is_active = TRUE")
        alerts = cursor.fetchall()

        if not alerts:
            logger.info("No active alerts to check for missed triggers")
            conn.close()
            return

        logger.info(f"Checking {len(alerts)} active alerts for missed triggers")

        for alert in alerts:
            # Handle schema: PostgreSQL has core columns
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
            cursor.execute(
                "SELECT last_check_timestamp, last_check_price FROM price_check_tracking WHERE symbol = %s",
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
    conn: Optional["psycopg.Connection"] = None  # type: ignore[name-defined]
):
    """Trigger an alert and send notifications"""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()

        # Get portfolio information for this symbol
        # First, get all base currencies for this symbol
        cursor.execute("""
            SELECT DISTINCT base_currency
            FROM portfolio_items
            WHERE symbol = %s AND base_currency IS NOT NULL
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

            result = cursor.fetchone()
            if result:
                portfolio_data.append(result)

        # Log alert history with missed flag
        check_type = 'historical' if was_missed else 'realtime'
        # Format timestamp for database
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

        # PostgreSQL schema doesn't have symbol column
        cursor.execute('''
            INSERT INTO alert_history
            (alert_id, user_id, triggered_price, triggered_at, was_missed, check_type)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (alert_id, user_id, trigger_price, trigger_timestamp, was_missed, check_type))

        # Deactivate the alert (one-time alert behavior)
        cursor.execute("UPDATE alerts SET is_active = FALSE WHERE id = %s", (alert_id,))

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

        current_time = datetime.now(timezone.utc)

        # Update price check tracking for all symbols
        # Commit price tracking updates separately to avoid transaction issues
        try:
            for symbol, price in current_prices.items():
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

            # Commit price tracking before processing alerts
            conn.commit()
        except Exception as e:
            logger.error(f"Error updating price tracking: {e}")
            conn.rollback()

        # Get all active alerts
        cursor.execute("SELECT * FROM alerts WHERE is_active = TRUE")
        alerts = cursor.fetchall()

        triggered_count = 0

        for alert in alerts:
            # Handle schema: PostgreSQL has core columns
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
                    # Create savepoint before triggering alert
                    cursor.execute(f"SAVEPOINT {savepoint_name}")

                    await trigger_alert(
                        alert_id, user_id, symbol, threshold_price, alert_type,
                        message, current_price, current_time, was_missed=False,
                        conn=conn
                    )
                    triggered_count += 1

                    # Release savepoint on success
                    cursor.execute(f"RELEASE SAVEPOINT {savepoint_name}")
                    conn.commit()
                except Exception as e:
                    logger.error(f"Error triggering alert {alert_id} in batch: {e}")
                    # Rollback to savepoint to continue with next alert
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

        if triggered_count > 0:
            logger.info(f"Triggered {triggered_count} alerts in real-time check")

    except Exception as e:
        logger.error(f"Error checking alerts: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
