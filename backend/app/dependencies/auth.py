from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
import sqlite3
import os
from ..core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def get_db_connection():
    """Get database connection with row factory"""
    # Resolve database path relative to project root
    current_file = os.path.abspath(__file__)  # /path/to/backend/app/dependencies/auth.py
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))  # /path/to/backend
    project_root = os.path.dirname(backend_dir)  # /path/to/project
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
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, email, username, full_name, preferred_currency, is_active, created_at, telegram_bot_token, telegram_chat_id FROM users WHERE id = ?", 
        (user_id,)
    )
    user = cursor.fetchone()
    conn.close()

    if user is None:
        raise credentials_exception
    return dict(user)

async def get_current_active_user(current_user: dict = Depends(get_current_user)):
    """Dependency to ensure user is active"""
    if not current_user["is_active"]:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
