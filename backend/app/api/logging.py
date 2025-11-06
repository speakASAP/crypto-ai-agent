from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

from ..utils.logger import get_logger

logger = get_logger("backend.app.api.logging")

router = APIRouter(prefix="/api/logging", tags=["logging"])


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
        from ..dependencies.auth import get_current_user
        token = authorization.replace("Bearer ", "")
        # We need to manually decode since get_current_user expects Depends
        from ..utils.auth import decode_token
        from ..utils.db import connect_with_retry
        
        payload = decode_token(token)
        if payload is None:
            return None
        
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            return None
        
        user_id: int = int(user_id_str)
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


@router.post("/log")
async def receive_frontend_log(
    log_entry: LogEntry,
    current_user: Optional[dict] = Depends(get_optional_user),
):
    """
    Receive and process frontend logs.
    All frontend console messages should be sent here instead of console.
    Authentication is optional - logs from unauthenticated users are still accepted.
    """
    try:
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
        
        python_level = level_mapping.get(log_entry.level.lower(), 'info')
        
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
        
        return {"success": True, "message": "Log received"}
        
    except Exception as e:
        # Don't fail the request if logging fails - just log the error
        logger.error(f"Error processing frontend log: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

