from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
import asyncio

from ..dependencies.auth import get_current_active_user, get_db_connection
from ..core.config import settings
from ..services.auth_service import auth_service
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
    # Use auth-microservice for registration
    try:
        auth_result = await auth_service.register(
            email=user_data.email,
            password=user_data.password,
            username=user_data.username,
            full_name=user_data.full_name,
        )
        
        # Store additional user profile data in local database
        # (preferred_currency, telegram settings, etc. are specific to crypto-ai-agent)
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.now().isoformat() + "Z"
        
        # Check if user already exists in local DB (shouldn't happen, but handle gracefully)
        sql_check = _normalize_placeholders("SELECT id FROM users WHERE id = %s")
        cursor.execute(sql_check, (auth_result["user"]["id"],))
        if not cursor.fetchone():
            # Insert user profile data into local database
            insert_sql = _normalize_placeholders('''
                INSERT INTO users (id, email, username, full_name, preferred_currency, is_active, is_verified, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''')
            cursor.execute(
                insert_sql,
                (
                    auth_result["user"]["id"],
                    auth_result["user"]["email"],
                    auth_result["user"].get("username", user_data.username),
                    auth_result["user"].get("full_name", user_data.full_name),
                    'USD',  # Default currency
                    auth_result["user"].get("is_active", True),
                    auth_result["user"].get("is_verified", False),
                    now,
                    now,
                ),
            )
            conn.commit()
        
        conn.close()

        user_response = UserResponse(
            id=auth_result["user"]["id"],
            email=auth_result["user"]["email"],
            username=auth_result["user"].get("username", user_data.username),
            full_name=auth_result["user"].get("full_name", user_data.full_name),
            preferred_currency='USD',
            is_active=auth_result["user"].get("is_active", True),
            created_at=auth_result["user"].get("created_at", now),
        )

        # Trigger crypto symbols refresh in the background after successful registration
        try:
            from ..api.prices import _refresh_crypto_symbols_helper
            asyncio.create_task(_refresh_crypto_symbols_helper())
            logger.info(f"Started background crypto symbols refresh for new user {user_response.id} ({user_data.email})")
        except Exception as e:
            logger.error(f"Failed to start background crypto symbols refresh for user {user_response.id}: {e}", exc_info=True)

        return TokenResponse(
            access_token=auth_result["access_token"],
            refresh_token=auth_result["refresh_token"],
            user=user_response,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Registration failed")


@router.post("/login", response_model=TokenResponse)
async def login(user_data: UserLogin):
    # Use auth-microservice for login
    try:
        auth_result = await auth_service.login(
            email=user_data.email,
            password=user_data.password,
        )
        
        # Get additional user profile data from local database
        # (preferred_currency, telegram settings, etc. are specific to crypto-ai-agent)
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = _normalize_placeholders(
            "SELECT id, preferred_currency, telegram_bot_token, telegram_chat_id, default_alert_percentage_above, default_alert_percentage_below FROM users WHERE id = %s"
        )
        cursor.execute(sql, (auth_result["user"]["id"],))
        local_user = cursor.fetchone()
        conn.close()
        
        # Use local DB data if available, otherwise use defaults
        preferred_currency = local_user[1] if local_user and local_user[1] else 'USD'
        
        user_response = UserResponse(
            id=auth_result["user"]["id"],
            email=auth_result["user"]["email"],
            username=auth_result["user"].get("username", user_data.email.split("@")[0]),
            full_name=auth_result["user"].get("full_name"),
            preferred_currency=preferred_currency,
            is_active=auth_result["user"].get("is_active", True),
            created_at=auth_result["user"].get("created_at"),
        )
        
        logger.info(f"Successful login for user {user_response.id} ({user_data.email})")

        # Trigger chart data fetching for user's portfolio symbols (non-blocking)
        try:
            # Get user's portfolio symbols
            portfolio_conn = get_db_connection()
            portfolio_cursor = portfolio_conn.cursor()
            portfolio_sql = _normalize_placeholders(
                "SELECT DISTINCT symbol FROM portfolio_items WHERE user_id = %s AND symbol IS NOT NULL"
            )
            portfolio_cursor.execute(portfolio_sql, (user_response.id,))
            portfolio_rows = portfolio_cursor.fetchall()
            portfolio_conn.close()
            
            if portfolio_rows:
                symbols = [row[0] for row in portfolio_rows if row[0]]
                if symbols:
                    from ..services.chart_tasks import fetch_chart_data_for_symbols
                    logger.info(f"📊 Triggering chart data fetch on login for {len(symbols)} symbols: {symbols}")
                    # Trigger background fetch (non-blocking, don't wait for completion)
                    asyncio.create_task(
                        fetch_chart_data_for_symbols(symbols, days=7, skip_cached=False)
                    )
        except Exception as e:
            logger.error(f"⚠️ Failed to trigger chart fetch on login: {e}", exc_info=True)
            # Don't fail login if chart fetch trigger fails

        return TokenResponse(
            access_token=auth_result["access_token"],
            refresh_token=auth_result["refresh_token"],
            user=user_response,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Login failed")


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: Optional[str] = None, current_user: dict = None):
    # Accept refresh_token from query or body; do NOT require current access token
    from fastapi import Request, Body
    token = refresh_token
    if not token:
        # Try to read from request body if sent as JSON { refresh_token }
        try:
            token = Body(None)
        except Exception:
            token = None
    if not token:
        # Try to read from query param handled by FastAPI already; if still missing
        raise HTTPException(status_code=401, detail="Missing refresh_token")
    
    # Use auth-microservice for token refresh
    try:
        auth_result = await auth_service.refresh_token(token)
        
        # Get additional user profile data from local database
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = _normalize_placeholders(
            "SELECT id, preferred_currency FROM users WHERE id = %s"
        )
        cursor.execute(sql, (auth_result["user"]["id"],))
        local_user = cursor.fetchone()
        conn.close()
        
        preferred_currency = local_user[1] if local_user and local_user[1] else 'USD'
        
        user_response = UserResponse(
            id=auth_result["user"]["id"],
            email=auth_result["user"]["email"],
            username=auth_result["user"].get("username", auth_result["user"]["email"].split("@")[0]),
            full_name=auth_result["user"].get("full_name"),
            preferred_currency=preferred_currency,
            is_active=auth_result["user"].get("is_active", True),
            created_at=auth_result["user"].get("created_at"),
        )

        return TokenResponse(
            access_token=auth_result["access_token"],
            refresh_token=auth_result["refresh_token"],
            user=user_response,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh failed: {e}", exc_info=True)
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_active_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = _normalize_placeholders(
        "SELECT id, email, username, full_name, preferred_currency, is_active, created_at, telegram_bot_token, telegram_chat_id, default_alert_percentage_above, default_alert_percentage_below FROM users WHERE id = %s"
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

    try:
        update_fields = []
        params = []
        if update_data.email is not None:
            update_fields.append("email = %s")
            params.append(update_data.email)
        if update_data.username is not None:
            update_fields.append("username = %s")
            params.append(update_data.username)
        if update_data.full_name is not None:
            update_fields.append("full_name = %s")
            params.append(update_data.full_name)
        if update_data.preferred_currency is not None:
            update_fields.append("preferred_currency = %s")
            params.append(update_data.preferred_currency)
        if update_data.telegram_bot_token is not None:
            update_fields.append("telegram_bot_token = %s")
            params.append(update_data.telegram_bot_token)
        if update_data.telegram_chat_id is not None:
            update_fields.append("telegram_chat_id = %s")
            params.append(update_data.telegram_chat_id)
        if update_data.default_alert_percentage_above is not None:
            update_fields.append("default_alert_percentage_above = %s")
            params.append(update_data.default_alert_percentage_above)
        if update_data.default_alert_percentage_below is not None:
            update_fields.append("default_alert_percentage_below = %s")
            params.append(update_data.default_alert_percentage_below)

        if update_fields:
            update_fields.append("updated_at = %s")
            updated_ts = datetime.now()
            params.append(updated_ts)
            params.append(current_user["id"])
            sql = _normalize_placeholders(f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s")
            cursor.execute(sql, params)
            conn.commit()

        if update_data.binance_api_key is not None and update_data.binance_api_secret is not None:
            binance_credential_service.save_user_credentials(
                current_user["id"], update_data.binance_api_key, update_data.binance_api_secret
            )

        sql = _normalize_placeholders(
            "SELECT id, email, username, full_name, preferred_currency, is_active, created_at, telegram_bot_token, telegram_chat_id, default_alert_percentage_above, default_alert_percentage_below FROM users WHERE id = %s"
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
async def change_password(
    password_change: PasswordChange,
    current_user: dict = Depends(get_current_active_user),
    token: str = Depends(oauth2_scheme),
):
    """Change password using auth-microservice"""
    try:
        result = await auth_service.change_password(
            current_password=password_change.current_password,
            new_password=password_change.new_password,
            access_token=token,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password change failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Password change failed")


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
    """Request password reset using auth-microservice"""
    try:
        result = await auth_service.request_password_reset(request.email)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password reset request failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Password reset request failed")


@router.post("/password-reset-confirm")
async def confirm_password_reset(confirm: PasswordResetConfirm):
    """Confirm password reset using auth-microservice"""
    try:
        result = await auth_service.confirm_password_reset(confirm.token, confirm.new_password)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password reset confirmation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Password reset confirmation failed")


@router.delete("/delete-account")
async def delete_account(confirmation: AccountDeletionConfirm, current_user: dict = Depends(get_current_active_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    user_id = current_user["id"]
    try:
        for stmt in [
            "DELETE FROM alert_history WHERE user_id = %s",
            "DELETE FROM alerts WHERE user_id = %s",
            "DELETE FROM tracked_symbols WHERE user_id = %s",
            "DELETE FROM portfolio_items WHERE user_id = %s",
            "DELETE FROM password_reset_tokens WHERE user_id = %s",
            "DELETE FROM user_sessions WHERE user_id = %s",
            "DELETE FROM users WHERE id = %s",
        ]:
            cursor.execute(_normalize_placeholders(stmt), (user_id,))
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


