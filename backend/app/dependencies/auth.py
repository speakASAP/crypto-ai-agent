from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from ..utils.db import connect_with_retry

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def get_db_connection():
    """Get PostgreSQL database connection with retry logic."""
    # Use retry logic for runtime connections (max 3 retries, faster backoff)
    return connect_with_retry(max_retries=3, initial_delay=0.5, max_delay=2.0, is_startup=False)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Dependency to get current authenticated user from JWT token via auth-microservice"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Use auth-microservice to validate token
        from ..services.auth_service import auth_service
        auth_user = await auth_service.validate_token(token)
        
        if not auth_user:
            raise credentials_exception
        
        user_id = auth_user.get("id")
        if not user_id:
            raise credentials_exception

        # Get additional user profile data from local database
        # (preferred_currency, telegram settings, etc. are specific to crypto-ai-agent)
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
                # User exists in auth-microservice but not in local DB - create minimal record
                user = {
                    "id": user_id,
                    "email": auth_user.get("email"),
                    "username": auth_user.get("email", "").split("@")[0],
                    "full_name": f"{auth_user.get('firstName', '')} {auth_user.get('lastName', '')}".strip() or None,
                    "preferred_currency": "USD",
                    "is_active": auth_user.get("isActive", True),
                    "created_at": auth_user.get("createdAt"),
                    "telegram_bot_token": None,
                    "telegram_chat_id": None,
                    "default_alert_percentage_above": None,
                    "default_alert_percentage_below": None,
                }
        finally:
            conn.close()

        return dict(user)
    except HTTPException:
        raise
    except Exception as e:
        # Log error but don't expose details
        import logging
        logger = logging.getLogger("backend.app.dependencies.auth")
        logger.error(f"Token validation failed: {e}", exc_info=True)
        raise credentials_exception

async def get_current_active_user(current_user: dict = Depends(get_current_user)):
    """Dependency to ensure user is active"""
    if not current_user["is_active"]:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
