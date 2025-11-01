from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
import asyncio

from ..dependencies.auth import get_current_active_user, get_db_connection
from ..utils.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    generate_reset_token,
)
from ..core.config import settings
from ..schemas.auth import (
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
    BinanceCredentialsResponse,
    BinanceTestResponse,
    BitfinexCredentials,
    BitfinexCredentialsResponse,
    BitfinexTestResponse,
)
from ..services.notification_service import send_user_telegram_notification
from ..services.binance_credential_service import binance_credential_service
from ..services.bitfinex_credential_service import bitfinex_credential_service
try:
    from utils.logger import get_logger
except Exception:  # pragma: no cover
    from ..utils.logger import get_logger


router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = get_logger("backend.app.api.auth")
from ..utils.db import (
    normalize_placeholders as _normalize_placeholders,
    execute_insert_and_get_id as _execute_insert_and_get_id,
)


@router.post("/register", response_model=TokenResponse)
async def register(user_data: UserCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    is_pg = (getattr(settings, "environment", "development").lower() == "production") or bool(getattr(settings, "database_url", None))

    sql_check = _normalize_placeholders("SELECT id FROM users WHERE email = ? OR username = ?", is_pg)
    cursor.execute(sql_check, (user_data.email, user_data.username))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Email or username already registered")

    # Hash password with clear error handling
    try:
        hashed_password = get_password_hash(user_data.password)
    except Exception as e:
        logger.error(f"Error hashing password for {user_data.email}: {e}", exc_info=True)
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid password")
    now = datetime.now().isoformat() + "Z"
    insert_sql = '''
        INSERT INTO users (email, username, hashed_password, full_name, is_active, is_verified, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    '''
    sql_insert = _normalize_placeholders(insert_sql, is_pg)
    user_id = _execute_insert_and_get_id(
        cursor,
        sql_insert,
        (user_data.email, user_data.username, hashed_password, user_data.full_name, True, False, now, now),
        is_pg,
    )
    conn.commit()
    conn.close()

    access_token = create_access_token(data={"sub": str(user_id)})
    refresh_token = create_refresh_token(data={"sub": str(user_id)})

    user_response = UserResponse(
        id=user_id,
        email=user_data.email,
        username=user_data.username,
        full_name=user_data.full_name,
        preferred_currency='USD',
        is_active=True,
        created_at=now,
    )

    # Trigger crypto symbols refresh in the background after successful registration
    # This ensures new users can immediately add cryptocurrencies to their portfolio
    try:
        from ..api.prices import _refresh_crypto_symbols_helper
        asyncio.create_task(_refresh_crypto_symbols_helper())
        logger.info(f"Started background crypto symbols refresh for new user {user_id} ({user_data.email})")
    except Exception as e:
        # Log error but don't fail registration if refresh fails
        logger.error(f"Failed to start background crypto symbols refresh for user {user_id}: {e}", exc_info=True)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user_response,
    )


@router.post("/login", response_model=TokenResponse)
async def login(user_data: UserLogin):
    conn = get_db_connection()
    cursor = conn.cursor()
    is_pg = (getattr(settings, "environment", "development").lower() == "production") or bool(getattr(settings, "database_url", None))
    sql = _normalize_placeholders(
        "SELECT id, email, username, hashed_password, full_name, preferred_currency, is_active, created_at FROM users WHERE email = ?",
        is_pg,
    )
    cursor.execute(sql, (user_data.email,))
    user = cursor.fetchone()
    
    # Enhanced logging for debugging
    if not user:
        logger.error(f"LOGIN FAILED - User not found for email: {user_data.email}")
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Log hash format for debugging (first 20 chars only for security)
    hash_preview = user[3][:20] + "..." if len(user[3]) > 20 else user[3]
    logger.info(f"LOGIN ATTEMPT - User {user[0]} ({user_data.email}), hash preview: {hash_preview}")
    
    password_valid = verify_password(user_data.password, user[3])
    logger.info(f"LOGIN PASSWORD CHECK - User {user[0]}, verification result: {password_valid}")
    
    if not password_valid:
        logger.error(f"LOGIN FAILED - Password verification failed for user {user[0]} ({user_data.email})")
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    logger.info(f"Successful login for user {user[0]} ({user_data.email})")

    access_token = create_access_token(data={"sub": str(user[0])})
    refresh_token = create_refresh_token(data={"sub": str(user[0])})

    # Convert datetime to ISO format string if needed
    created_at = user[7]
    if isinstance(created_at, datetime):
        created_at = created_at.isoformat() + "Z"
    elif created_at is not None:
        created_at = str(created_at)

    user_response = UserResponse(
        id=user[0],
        email=user[1],
        username=user[2],
        full_name=user[4],
        preferred_currency=user[5],
        is_active=bool(user[6]),
        created_at=created_at,
    )
    conn.close()

    return TokenResponse(access_token=access_token, refresh_token=refresh_token, user=user_response)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: Optional[str] = None, current_user: dict = None):
    # Accept refresh_token from query or body; do NOT require current access token
    from fastapi import Request
    from fastapi import Depends
    from ..utils.auth import decode_token
    token = refresh_token
    if not token:
        # Try to read from request body if sent as JSON { refresh_token }
        try:
            from fastapi import Body
            token = Body(None)
        except Exception:
            token = None
    if not token:
        # Try to read from query param handled by FastAPI already; if still missing
        raise HTTPException(status_code=401, detail="Missing refresh_token")
    payload = decode_token(token) if isinstance(token, str) else None
    if not payload or payload.get("type") != "refresh" or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = int(payload["sub"]) if str(payload.get("sub")).isdigit() else None
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid refresh token subject")

    conn = get_db_connection()
    cursor = conn.cursor()
    is_pg = (getattr(settings, "environment", "development").lower() == "production") or bool(getattr(settings, "database_url", None))
    sql = _normalize_placeholders(
        "SELECT id, email, username, full_name, preferred_currency, is_active, created_at FROM users WHERE id = ?",
        is_pg,
    )
    cursor.execute(sql, (user_id,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    new_access_token = create_access_token(data={"sub": str(user[0])})
    new_refresh_token = create_refresh_token(data={"sub": str(user[0])})

    # Convert datetime to ISO format string if needed
    created_at = user[6]
    if isinstance(created_at, datetime):
        created_at = created_at.isoformat() + "Z"
    elif created_at is not None:
        created_at = str(created_at)

    user_response = UserResponse(
        id=user[0], email=user[1], username=user[2], full_name=user[3],
        preferred_currency=user[4], is_active=bool(user[5]), created_at=created_at,
    )
    return TokenResponse(access_token=new_access_token, refresh_token=new_refresh_token, user=user_response)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_active_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    is_pg = (getattr(settings, "environment", "development").lower() == "production") or bool(getattr(settings, "database_url", None))
    sql = _normalize_placeholders(
        "SELECT id, email, username, full_name, preferred_currency, is_active, created_at, telegram_bot_token, telegram_chat_id, default_alert_percentage_above, default_alert_percentage_below FROM users WHERE id = ?",
        is_pg,
    )
    cursor.execute(sql, (current_user["id"],))
    user = cursor.fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Convert datetime to ISO format string if needed
    created_at = user[6]
    if isinstance(created_at, datetime):
        created_at = created_at.isoformat() + "Z"
    elif created_at is not None:
        created_at = str(created_at)
    return UserResponse(
        id=user[0], email=user[1], username=user[2], full_name=user[3], preferred_currency=user[4],
        is_active=bool(user[5]), created_at=created_at, telegram_bot_token=user[7], telegram_chat_id=user[8],
        default_alert_percentage_above=user[9] if user[9] is not None else 60.0,
        default_alert_percentage_below=user[10] if user[10] is not None else 20.0,
    )


@router.put("/profile", response_model=UserResponse)
async def update_profile(update_data: UserProfileUpdate, current_user: dict = Depends(get_current_active_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    is_pg = (getattr(settings, "environment", "development").lower() == "production") or bool(getattr(settings, "database_url", None))

    try:
        update_fields = []
        params = []
        if update_data.email is not None:
            update_fields.append("email = ?")
            params.append(update_data.email)
        if update_data.username is not None:
            update_fields.append("username = ?")
            params.append(update_data.username)
        if update_data.full_name is not None:
            update_fields.append("full_name = ?")
            params.append(update_data.full_name)
        if update_data.preferred_currency is not None:
            update_fields.append("preferred_currency = ?")
            params.append(update_data.preferred_currency)
        if update_data.telegram_bot_token is not None:
            update_fields.append("telegram_bot_token = ?")
            params.append(update_data.telegram_bot_token)
        if update_data.telegram_chat_id is not None:
            update_fields.append("telegram_chat_id = ?")
            params.append(update_data.telegram_chat_id)
        if update_data.default_alert_percentage_above is not None:
            update_fields.append("default_alert_percentage_above = ?")
            params.append(update_data.default_alert_percentage_above)
        if update_data.default_alert_percentage_below is not None:
            update_fields.append("default_alert_percentage_below = ?")
            params.append(update_data.default_alert_percentage_below)

        if update_fields:
            update_fields.append("updated_at = ?")
            updated_ts = datetime.now() if is_pg else (datetime.now().isoformat() + "Z")
            params.append(updated_ts)
            params.append(current_user["id"])
            sql = _normalize_placeholders(f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?", is_pg)
            cursor.execute(sql, params)
            conn.commit()

        if update_data.binance_api_key is not None and update_data.binance_api_secret is not None:
            binance_credential_service.save_user_credentials(
                current_user["id"], update_data.binance_api_key, update_data.binance_api_secret
            )

        sql = _normalize_placeholders(
            "SELECT id, email, username, full_name, preferred_currency, is_active, created_at, telegram_bot_token, telegram_chat_id, default_alert_percentage_above, default_alert_percentage_below FROM users WHERE id = ?",
            is_pg,
        )
        cursor.execute(sql, (current_user["id"],))
        user = cursor.fetchone()
        # Convert datetime to ISO format string if needed
        created_at = user[6]
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat() + "Z"
        elif created_at is not None:
            created_at = str(created_at)
        return UserResponse(
            id=user[0], email=user[1], username=user[2], full_name=user[3], preferred_currency=user[4],
            is_active=bool(user[5]), created_at=created_at, telegram_bot_token=user[7], telegram_chat_id=user[8],
            default_alert_percentage_above=user[9] if user[9] is not None else 60.0,
            default_alert_percentage_below=user[10] if user[10] is not None else 20.0,
        )
    except Exception as e:
        logger.error(f"Error updating profile for user {current_user['id']}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update profile")
    finally:
        conn.close()


@router.post("/change-password")
async def change_password(password_change: PasswordChange, current_user: dict = Depends(get_current_active_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    is_pg = (getattr(settings, "environment", "development").lower() == "production") or bool(getattr(settings, "database_url", None))
    sql = _normalize_placeholders("SELECT hashed_password FROM users WHERE id = ?", is_pg)
    cursor.execute(sql, (current_user["id"],))
    user = cursor.fetchone()
    if not user or not verify_password(password_change.current_password, user[0]):
        conn.close()
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    new_hashed_password = get_password_hash(password_change.new_password)
    sql = _normalize_placeholders("UPDATE users SET hashed_password = ?, updated_at = ? WHERE id = ?", is_pg)
    cursor.execute(sql, (new_hashed_password, datetime.now().isoformat() + "Z", current_user["id"]))
    conn.commit()
    conn.close()
    return {"message": "Password changed successfully"}


@router.post("/test-telegram")
async def test_telegram_connection(current_user: dict = Depends(get_current_active_user)):
    try:
        test_message = (
            f"🧪 <b>Test Message</b>\n\nHello {current_user['username']}! This is a test message from your Crypto AI Agent.\n\n✅ Your Telegram integration is working correctly!"
        )
        success = await send_user_telegram_notification(current_user["id"], test_message)
        if success:
            return {"message": "Telegram test message sent successfully!", "success": True}
        else:
            return {"message": "Failed to send Telegram test message. Please check your credentials.", "success": False}
    except Exception as e:
        logger.error(f"Error testing Telegram connection for user {current_user['id']}: {e}")
        return {"message": f"Error testing Telegram connection: {str(e)}", "success": False}


@router.post("/password-reset-request")
async def request_password_reset(request: PasswordResetRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    is_pg = (getattr(settings, "environment", "development").lower() == "production") or bool(getattr(settings, "database_url", None))
    sql = _normalize_placeholders("SELECT id FROM users WHERE email = ?", is_pg)
    cursor.execute(sql, (request.email,))
    user = cursor.fetchone()
    if user:
        reset_token = generate_reset_token()
        expires_at = (datetime.now() + timedelta(hours=1)).isoformat() + "Z"
        now = datetime.now().isoformat() + "Z"
        insert_sql = '''
            INSERT INTO password_reset_tokens (user_id, token, expires_at, used, created_at)
            VALUES (?, ?, ?, ?, ?)
        '''
        sql = _normalize_placeholders(insert_sql, is_pg)
        cursor.execute(sql, (user[0], reset_token, expires_at, False, now))
        conn.commit()
        logger.info(f"Password reset token for {request.email}: {reset_token}")
        logger.info(f"Token expires at: {expires_at}")
    conn.close()
    return {"message": "If the email exists, a password reset token has been generated. Check the server logs for the token."}


@router.post("/password-reset-confirm")
async def confirm_password_reset(confirm: PasswordResetConfirm):
    conn = get_db_connection()
    cursor = conn.cursor()
    is_pg = (getattr(settings, "environment", "development").lower() == "production") or bool(getattr(settings, "database_url", None))
    select_sql = '''
        SELECT user_id, expires_at, used FROM password_reset_tokens 
        WHERE token = ? AND used = 0
    '''
    sql = _normalize_placeholders(select_sql, is_pg)
    cursor.execute(sql, (confirm.token,))
    token_data = cursor.fetchone()
    if not token_data:
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    user_id, expires_at, used = token_data
    if datetime.now() > datetime.fromisoformat(expires_at.replace('Z', '+00:00')):
        conn.close()
        raise HTTPException(status_code=400, detail="Reset token has expired")

    new_hashed_password = get_password_hash(confirm.new_password)
    sql1 = _normalize_placeholders("UPDATE users SET hashed_password = ?, updated_at = ? WHERE id = ?", is_pg)
    cursor.execute(sql1, (new_hashed_password, datetime.now().isoformat() + "Z", user_id))
    sql2 = _normalize_placeholders("UPDATE password_reset_tokens SET used = 1 WHERE token = ?", is_pg)
    cursor.execute(sql2, (confirm.token,))
    conn.commit()
    conn.close()
    return {"message": "Password reset successfully"}


@router.delete("/delete-account")
async def delete_account(confirmation: AccountDeletionConfirm, current_user: dict = Depends(get_current_active_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    user_id = current_user["id"]
    try:
        is_pg = (getattr(settings, "environment", "development").lower() == "production") or bool(getattr(settings, "database_url", None))
        for stmt in [
            "DELETE FROM alert_history WHERE user_id = ?",
            "DELETE FROM alerts WHERE user_id = ?",
            "DELETE FROM tracked_symbols WHERE user_id = ?",
            "DELETE FROM portfolio_items WHERE user_id = ?",
            "DELETE FROM password_reset_tokens WHERE user_id = ?",
            "DELETE FROM user_sessions WHERE user_id = ?",
            "DELETE FROM users WHERE id = ?",
        ]:
            cursor.execute(_normalize_placeholders(stmt, is_pg), (user_id,))
        conn.commit()
        conn.close()
        logger.info(f"User account {user_id} ({current_user['email']}) has been permanently deleted")
        return {"message": "Account deleted successfully"}
    except Exception as e:
        conn.rollback()
        conn.close()
        logger.error(f"Error deleting account for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete account")


@router.post("/binance-credentials", response_model=BinanceCredentialsResponse)
async def save_binance_credentials(credentials: BinanceCredentials, current_user: dict = Depends(get_current_active_user)):
    user_id = current_user["id"]
    success = binance_credential_service.save_user_credentials(user_id, credentials.api_key, credentials.api_secret)
    if success:
        test_result = await binance_credential_service.test_user_credentials(user_id)
        return BinanceCredentialsResponse(
            has_credentials=True,
            message="Binance credentials saved successfully",
            account_info=test_result.get('account_info') if test_result.get('success') else None,
        )
    else:
        raise HTTPException(status_code=500, detail="Failed to save Binance credentials")


@router.get("/binance-credentials", response_model=BinanceCredentialsResponse)
async def get_binance_credentials_status(current_user: dict = Depends(get_current_active_user)):
    user_id = current_user["id"]
    has_credentials = binance_credential_service.has_user_credentials(user_id)
    if has_credentials:
        test_result = await binance_credential_service.test_user_credentials(user_id)
        return BinanceCredentialsResponse(
            has_credentials=True,
            message="Binance credentials are configured",
            account_info=test_result.get('account_info') if test_result.get('success') else None,
        )
    else:
        return BinanceCredentialsResponse(has_credentials=False, message="No Binance credentials configured")


@router.post("/test-binance-connection", response_model=BinanceTestResponse)
async def test_binance_connection(current_user: dict = Depends(get_current_active_user)):
    user_id = current_user["id"]
    result = await binance_credential_service.test_user_credentials(user_id)
    return BinanceTestResponse(
        success=result.get('success', False),
        message=result.get('message', 'Unknown error'),
        account_info=result.get('account_info'),
        error_code=str(result.get('error_code')) if result.get('error_code') is not None else None,
        troubleshooting=result.get('troubleshooting'),
    )


@router.delete("/binance-credentials")
async def delete_binance_credentials(current_user: dict = Depends(get_current_active_user)):
    user_id = current_user["id"]
    success = binance_credential_service.delete_user_credentials(user_id)
    if success:
        return {"message": "Binance credentials deleted successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete Binance credentials")


@router.post("/bitfinex-credentials", response_model=BitfinexCredentialsResponse)
async def save_bitfinex_credentials(credentials: BitfinexCredentials, current_user: dict = Depends(get_current_active_user)):
    user_id = current_user["id"]
    success = bitfinex_credential_service.save_user_credentials(user_id, credentials.api_key, credentials.api_secret)
    if success:
        test_result = await bitfinex_credential_service.test_user_credentials(user_id)
        return BitfinexCredentialsResponse(
            has_credentials=True,
            message="Bitfinex credentials saved successfully",
            account_info=test_result.get('account_info') if test_result.get('success') else None,
        )
    else:
        raise HTTPException(status_code=500, detail="Failed to save Bitfinex credentials")


@router.get("/bitfinex-credentials", response_model=BitfinexCredentialsResponse)
async def get_bitfinex_credentials_status(current_user: dict = Depends(get_current_active_user)):
    user_id = current_user["id"]
    has_credentials = bitfinex_credential_service.has_user_credentials(user_id)
    if has_credentials:
        test_result = await bitfinex_credential_service.test_user_credentials(user_id)
        return BitfinexCredentialsResponse(
            has_credentials=True,
            message="Bitfinex credentials are configured",
            account_info=test_result.get('account_info') if test_result.get('success') else None,
        )
    else:
        return BitfinexCredentialsResponse(has_credentials=False, message="No Bitfinex credentials configured")


@router.post("/test-bitfinex-connection", response_model=BitfinexTestResponse)
async def test_bitfinex_connection(current_user: dict = Depends(get_current_active_user)):
    user_id = current_user["id"]
    result = await bitfinex_credential_service.test_user_credentials(user_id)
    return BitfinexTestResponse(
        success=result.get('success', False),
        message=result.get('message', 'Unknown error'),
        account_info=result.get('account_info'),
        error_code=str(result.get('error_code')) if result.get('error_code') is not None else None,
        troubleshooting=result.get('troubleshooting'),
    )


@router.delete("/bitfinex-credentials")
async def delete_bitfinex_credentials(current_user: dict = Depends(get_current_active_user)):
    user_id = current_user["id"]
    success = bitfinex_credential_service.delete_user_credentials(user_id)
    if success:
        return {"message": "Bitfinex credentials deleted successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete Bitfinex credentials")


