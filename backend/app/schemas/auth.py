from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr, validator


class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v

    @validator('username')
    def validate_username(cls, v):
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters')
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: Optional[str]
    preferred_currency: str
    is_active: bool
    created_at: str
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    default_alert_percentage_above: Optional[float] = 60.0
    default_alert_percentage_below: Optional[float] = 20.0


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v


class UserProfileUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    preferred_currency: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    binance_api_key: Optional[str] = None
    binance_api_secret: Optional[str] = None
    default_alert_percentage_above: Optional[float] = None
    default_alert_percentage_below: Optional[float] = None

    @validator('username')
    def validate_username(cls, v):
        if v is not None:
            if len(v) < 3:
                raise ValueError('Username must be at least 3 characters')
        return v

    @validator('default_alert_percentage_above', 'default_alert_percentage_below')
    def validate_percentage(cls, v):
        if v is not None:
            if v < 0 or v > 1000:
                raise ValueError('Percentage must be between 0 and 1000')
        return v

    @validator('preferred_currency')
    def validate_preferred_currency(cls, v):
        if v is not None:
            if v not in ['USD', 'EUR', 'CZK']:
                raise ValueError('Preferred currency must be USD, EUR, or CZK')
        return v

    @validator('telegram_bot_token')
    def validate_telegram_bot_token(cls, v):
        if v is not None and v.strip():
            if not v.startswith(('1', '2', '3', '4', '5', '6', '7', '8', '9')) or ':' not in v:
                raise ValueError('Invalid Telegram bot token format. Should be like: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz')
        return v.strip() if v else ''

    @validator('telegram_chat_id')
    def validate_telegram_chat_id(cls, v):
        if v is not None and v.strip():
            if not v.strip().isdigit():
                raise ValueError('Invalid Telegram chat ID format. Should be a numeric value like: 123456789')
        return v.strip() if v else ''

    @validator('binance_api_key')
    def validate_binance_api_key(cls, v):
        if v is not None and v.strip():
            if len(v.strip()) < 10:
                raise ValueError('Binance API key must be at least 10 characters')
        return v.strip() if v else ''

    @validator('binance_api_secret')
    def validate_binance_api_secret(cls, v):
        if v is not None and v.strip():
            if len(v.strip()) < 10:
                raise ValueError('Binance API secret must be at least 10 characters')
        return v.strip() if v else ''


class PasswordChange(BaseModel):
    current_password: str
    new_password: str

    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v


class AccountDeletionConfirm(BaseModel):
    confirmation_text: str = "DELETE"

    @validator('confirmation_text')
    def validate_confirmation(cls, v):
        if v != "DELETE":
            raise ValueError('Confirmation text must be exactly "DELETE"')
        return v


class BinanceCredentials(BaseModel):
    api_key: str
    api_secret: str

    @validator('api_key')
    def validate_api_key(cls, v):
        if not v or len(v.strip()) < 10:
            raise ValueError('Binance API key is required and must be at least 10 characters')
        return v.strip()

    @validator('api_secret')
    def validate_api_secret(cls, v):
        if not v or len(v.strip()) < 10:
            raise ValueError('Binance API secret is required and must be at least 10 characters')
        return v.strip()


class BitfinexCredentials(BaseModel):
    api_key: str
    api_secret: str

    @validator('api_key')
    def validate_api_key(cls, v):
        if not v or len(v.strip()) < 10:
            raise ValueError('Bitfinex API key is required and must be at least 10 characters')
        return v.strip()

    @validator('api_secret')
    def validate_api_secret(cls, v):
        if not v or len(v.strip()) < 10:
            raise ValueError('Bitfinex API secret is required and must be at least 10 characters')
        return v.strip()


class BitfinexCredentialsResponse(BaseModel):
    has_credentials: bool
    message: str
    account_info: Optional[Dict[str, Any]] = None


class BitfinexTestResponse(BaseModel):
    success: bool
    message: str
    account_info: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    troubleshooting: Optional[str] = None


class BinanceCredentialsResponse(BaseModel):
    has_credentials: bool
    message: str
    account_info: Optional[Dict[str, Any]] = None


class BinanceTestResponse(BaseModel):
    success: bool
    message: str
    account_info: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    troubleshooting: Optional[str] = None
