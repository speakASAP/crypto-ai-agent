from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
import sqlite3
import os
from urllib.parse import urlparse
import psycopg
from ..core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def get_db_connection():
    """Get database connection using Postgres when DATABASE_URL is set (or in production), otherwise SQLite."""
    use_postgres = settings.environment.lower() == "production" or bool(getattr(settings, "database_url", None))
    if use_postgres:
        # Use psycopg for Postgres; strip +psycopg suffix if present
        pg_url = settings.database_url.replace("+psycopg", "") if settings.database_url and "+psycopg" in settings.database_url else settings.database_url
        conn = psycopg.connect(pg_url)
        return conn
    # Resolve database path relative to project root (SQLite fallback)
    current_file = os.path.abspath(__file__)
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
    project_root = os.path.dirname(backend_dir)
    db_path = os.path.join(project_root, settings.database_file)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

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
        use_postgres = settings.environment.lower() == "production" or bool(getattr(settings, "database_url", None))
        if use_postgres:
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
        else:
            cur.execute(
                "SELECT id, email, username, full_name, preferred_currency, is_active, created_at, telegram_bot_token, telegram_chat_id, default_alert_percentage_above, default_alert_percentage_below FROM users WHERE id = ?",
                (user_id,)
            )
            row = cur.fetchone()
            user = dict(row) if row else None
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
