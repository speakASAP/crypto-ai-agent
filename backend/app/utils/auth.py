from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from ..core.config import settings
import secrets

# Password hashing context using pbkdf2_sha256 (no 72-byte limit, no bcrypt init issues), with bcrypt_sha256 and bcrypt for legacy hashes
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256", "bcrypt_sha256", "bcrypt"],
    deprecated="auto",
)

# JWT configuration
JWT_SECRET = settings.jwt_secret
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.jwt_access_token_expire_minutes
REFRESH_TOKEN_EXPIRE_DAYS = settings.jwt_refresh_token_expire_days

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password using passlib context (supports pbkdf2_sha256, bcrypt_sha256, and bcrypt)."""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Password verification failed: {e}, hash preview: {hashed_password[:20] if hashed_password else 'None'}...")
        return False

def get_password_hash(password: str) -> str:
    """Hash a password using pbkdf2_sha256 (no 72-byte limit)."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token with expiration"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT refresh token with longer expiration"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> dict:
    """Decode and verify JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

def generate_reset_token() -> str:
    """Generate secure random token for password reset"""
    return secrets.token_urlsafe(32)
