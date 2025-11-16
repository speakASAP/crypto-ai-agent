from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from ..core.config import settings
from ..utils.db import connect_with_retry

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def get_db_connection():
    """Get PostgreSQL database connection with retry logic."""
    # Use retry logic for runtime connections (max 3 retries, faster backoff)
    return connect_with_retry(max_retries=3, initial_delay=0.5, max_delay=2.0, is_startup=False)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Dependency to get current authenticated user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        from ..utils.auth import decode_token
        payload = decode_token(token)
        if payload is None:
            raise credentials_exception
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id: int = int(user_id_str)
    except JWTError:
        raise credentials_exception

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, email, username, full_name, preferred_currency, is_active, created_at, telegram_bot_token, telegram_chat_id, default_alert_percentage_above, default_alert_percentage_below FROM users WHERE id = %s",
            (user_id,)
        )
        row = cur.fetchone()
        if row:
            columns = [desc[0] for desc in cur.description]
            user = {columns[i]: row[i] for i in range(len(columns))}
        else:
            user = None
    finally:
        conn.close()

    if user is None:
        raise credentials_exception
    return dict(user)

async def get_current_active_user(current_user: dict = Depends(get_current_user)):
    """Dependency to ensure user is active"""
    if not current_user["is_active"]:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
