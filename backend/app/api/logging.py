from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import os
import httpx
import asyncio

from ..utils.logger import get_logger

logger = get_logger("backend.app.api.logging")

router = APIRouter(prefix="/api/logging", tags=["logging"])

# Production mode check - filter non-critical logs in production
IS_PRODUCTION = os.getenv("NODE_ENV") == "production" or os.getenv("ENVIRONMENT") == "production"

# Service name for external logging
SERVICE_NAME = "crypto-ai-agent"


class LogEntry(BaseModel):
    level: str  # 'log', 'error', 'warn', 'info', 'debug'
    message: str
    context: Optional[str] = None  # Component/module name
    metadata: Optional[Dict[str, Any]] = None  # Additional data
    timestamp: Optional[str] = None  # Client-side timestamp
    user_agent: Optional[str] = None
    url: Optional[str] = None


async def get_optional_user(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    """Optional authentication - returns user if token is valid, None otherwise"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    
    try:
        token = authorization.replace("Bearer ", "")
        # Validate token via auth-microservice
        from ..services.auth_service import auth_service
        from ..utils.db import connect_with_retry
        
        # Use auth-microservice to validate token
        auth_user = await auth_service.validate_token(token)
        if not auth_user:
            return None
        
        user_id = auth_user.get("id")
        if not user_id:
            return None
        
        # Get additional user profile data from local database
        conn = connect_with_retry(max_retries=1, initial_delay=0.1, max_delay=0.5, is_startup=False)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, email, username, full_name, preferred_currency, is_active FROM users WHERE id = %s AND is_active = true",
                (user_id,)
            )
            row = cur.fetchone()
            if row:
                columns = [desc[0] for desc in cur.description]
                user = {columns[i]: row[i] for i in range(len(columns))}
                return dict(user)
        finally:
            conn.close()
    except Exception:
        # Silently fail - return None for invalid tokens
        return None
    
    return None


async def _send_to_external_service(
    level: str,
    message: str,
    context: Optional[str] = None,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    url: Optional[str] = None,
    user_agent: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Send log to external logging service.
    Fire-and-forget approach - doesn't block and silently fails if service is unavailable.

    Args:
        level: Log level (debug, info, warn, error)
        message: Log message
        context: Context/module name
        user_id: User ID if available
        username: Username if available
        url: URL if available
        user_agent: User agent if available
        metadata: Additional metadata
    """
    logging_service_url = os.getenv("LOGGING_SERVICE_URL")
    if not logging_service_url:
        return

    try:
        # Map frontend log levels to microservice levels
        level_mapping = {
            'log': 'info',
            'error': 'error',
            'warn': 'warn',
            'warning': 'warn',
            'info': 'info',
            'debug': 'debug',
        }
        microservice_level = level_mapping.get(level.lower(), 'info')

        # Build metadata dictionary
        log_metadata: Dict[str, Any] = {}
        if context:
            log_metadata["context"] = context
        if user_id:
            log_metadata["user_id"] = user_id
        if username:
            log_metadata["username"] = username
        if url:
            log_metadata["url"] = url
        if user_agent:
            log_metadata["user_agent"] = user_agent
        if metadata:
            log_metadata.update(metadata)

        headers = {"Content-Type": "application/json"}
        logging_service_token = os.getenv("LOGGING_SERVICE_TOKEN", "").strip()
        if logging_service_token:
            headers["Authorization"] = f"Bearer {logging_service_token}"

        # Create JSON payload
        payload = {
            "level": microservice_level,
            "message": message,
            "service": SERVICE_NAME,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "metadata": log_metadata,
        }

        # Send HTTP POST request (fire-and-forget, don't await)
        async with httpx.AsyncClient(timeout=2.0) as client:
            try:
                await client.post(
                    f"{logging_service_url}/api/logs",
                    json=payload,
                    headers=headers,
                )
            except Exception:
                # Silently fail - already in outer try-except
                pass
    except Exception:
        # Silently fail - don't log errors about logging service (avoid infinite loops)
        pass


@router.post("/log")
async def receive_frontend_log(
    log_entry: LogEntry,
    current_user: Optional[dict] = Depends(get_optional_user),
):
    """
    Receive and process frontend logs.
    All frontend console messages should be sent here instead of console.
    Authentication is optional - logs from unauthenticated users are still accepted.
    
    Production optimization:
    - In production, non-critical logs (log/info/debug) are filtered out
    - Only errors and warnings are processed in production
    - This reduces unnecessary log processing and file I/O
    """
    try:
        # In production, skip non-critical logs (log/info/debug) unless DEBUG is enabled
        log_level_lower = log_entry.level.lower()
        is_critical = log_level_lower in ('error', 'warn', 'warning')
        is_debug_enabled = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
        
        # Skip non-critical logs in production
        if IS_PRODUCTION and not is_critical and not is_debug_enabled:
            # Return success but don't process the log
            return {"success": True, "message": "Log filtered (production mode)"}
        
        user_id = current_user.get("id") if current_user else None
        username = current_user.get("username") if current_user else "anonymous"
        
        # Map frontend log levels to Python logging levels
        level_mapping = {
            'log': 'info',
            'error': 'error',
            'warn': 'warning',
            'info': 'info',
            'debug': 'debug'
        }
        
        python_level = level_mapping.get(log_level_lower, 'info')
        
        # Build log message with context
        log_message = f"[Frontend] {log_entry.message}"
        if log_entry.context:
            log_message = f"[Frontend:{log_entry.context}] {log_entry.message}"
        
        # Add metadata if available
        if log_entry.metadata:
            metadata_str = ", ".join([f"{k}={v}" for k, v in log_entry.metadata.items()])
            log_message += f" | {metadata_str}"
        
        # Add user info
        if user_id:
            log_message += f" | user_id={user_id}, username={username}"
        
        # Add URL if available
        if log_entry.url:
            log_message += f" | url={log_entry.url}"
        
        # Log to central system using appropriate level
        log_func = getattr(logger, python_level)
        log_func(log_message)
        
        # Send to external service (fire-and-forget, non-blocking)
        try:
            # Create task for fire-and-forget (don't await)
            asyncio.create_task(
                _send_to_external_service(
                    level=log_entry.level,
                    message=log_entry.message,
                    context=log_entry.context,
                    user_id=user_id,
                    username=username,
                    url=log_entry.url,
                    user_agent=log_entry.user_agent,
                    metadata=log_entry.metadata,
                )
            )
        except Exception:
            # Silently fail - don't log errors about logging service
            pass
        
        return {"success": True, "message": "Log received"}
        
    except Exception as e:
        # Don't fail the request if logging fails - just log the error
        logger.error(f"Error processing frontend log: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
