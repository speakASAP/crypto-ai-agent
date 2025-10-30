import os
import ssl
import aiohttp
from typing import Optional
from ..core.config import settings
from ..utils.db import normalize_placeholders as _normalize_placeholders
from ..dependencies.auth import get_db_connection
try:
    from utils.logger import get_logger
except Exception:  # pragma: no cover
    from ..utils.logger import get_logger


logger = get_logger("backend.app.services.notification_service")


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
        is_pg = (getattr(settings, "environment", "development").lower() == "production") or bool(getattr(settings, "database_url", None))
        sql = _normalize_placeholders(
            "SELECT telegram_bot_token, telegram_chat_id FROM users WHERE id = ?",
            is_pg,
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


