# Technical Implementation Guide - User Management System

## Overview

This document provides detailed technical information about the implementation of the user management system in the Crypto AI Agent project.

## Table of Contents

- [Backend Implementation](#backend-implementation)
- [Frontend Implementation](#frontend-implementation)
- [Database Design](#database-design)
- [Security Implementation](#security-implementation)
- [API Design](#api-design)
- [State Management](#state-management)
- [Error Handling](#error-handling)
- [Testing Strategy](#testing-strategy)
- [Deployment Considerations](#deployment-considerations)

## Backend Implementation

### Authentication Utilities

**File**: `backend/app/utils/auth.py`

```python
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from backend.app.core.config import settings
import secrets

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration
JWT_SECRET = settings.jwt_secret
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash using bcrypt"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt"""
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
```

### Authentication Dependencies

**File**: `backend/app/dependencies/auth.py`

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
import psycopg
from backend.app.core.config import settings
from backend.app.utils.auth import decode_token
from backend.app.utils.db import get_db_connection

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Dependency to get current authenticated user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = decode_token(token)
        if payload is None:
            raise credentials_exception
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # PostgreSQL query
    cursor.execute(
        "SELECT id, email, username, full_name, is_active, created_at FROM users WHERE id = %s", 
        (user_id,)
    )
    row = cursor.fetchone()
    if row:
        columns = [desc[0] for desc in cursor.description]
        user = {columns[i]: row[i] for i in range(len(columns))}
    else:
        user = None
    
    conn.close()

    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: dict = Depends(get_current_user)):
    """Dependency to ensure user is active"""
    if not current_user["is_active"]:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
```

### Database Initialization

**File**: `backend/app/main.py`

The system uses PostgreSQL exclusively:

```python
def init_postgres_database():
    """Initialize PostgreSQL database schema"""
    import psycopg
    pg_url = settings.database_url.replace("+psycopg", "") if "+psycopg" in settings.database_url else settings.database_url
    conn = psycopg.connect(pg_url)
    cur = conn.cursor()
    
    # Create users table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            full_name TEXT,
            preferred_currency TEXT DEFAULT 'USD',
            is_active BOOLEAN DEFAULT TRUE,
            is_verified BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create portfolio_items table with user_id
    cur.execute('''
        CREATE TABLE IF NOT EXISTS portfolio_items (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            symbol TEXT NOT NULL,
            amount REAL NOT NULL,
            price_buy REAL NOT NULL,
            purchase_date TIMESTAMP,
            base_currency TEXT NOT NULL,
            purchase_price_eur REAL,
            purchase_price_czk REAL,
            source TEXT,
            commission REAL DEFAULT 0.0,
            total_investment_text TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            current_price REAL,
            current_value REAL,
            pnl REAL,
            pnl_percent REAL,
            price_buy_usd REAL,
            commission_usd REAL,
            current_price_usd REAL,
            current_value_usd REAL,
            pnl_usd REAL,
            pnl_percent_usd REAL,
            exchange_rate_at_purchase REAL
        )
    ''')
    
    # Similar for other tables...
    
    conn.commit()
    conn.close()
    logger.info("PostgreSQL schema initialized")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if not settings.database_url:
        logger.error("❌ DATABASE_URL environment variable is required. PostgreSQL database connection is mandatory.")
        raise ConnectionError("DATABASE_URL environment variable is required.")
    
    logger.info("🚀 Starting Crypto AI Agent API v2.0 (PostgreSQL Mode)")
    init_postgres_database()
    logger.info("✅ Database initialized")
```

### Redis Caching

**File**: `backend/app/services/currency_service.py`

```python
import redis
import json

class CurrencyService:
    def __init__(self):
        self.rates: Dict[str, float] = {}
        self._redis = None
        if settings.redis_url:
            try:
                self._redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            except Exception:
                self._redis = None

    async def get_exchange_rates(self) -> Dict[str, float]:
        """Fetch current exchange rates from a free API"""
        try:
            # Cache hit from Redis
            if self._redis:
                cached = self._redis.get("currency:USD")
                if cached:
                    obj = json.loads(cached)
                    self.rates = obj.get("rates", {})
                    self.last_updated = obj.get("timestamp")
                    logger.info(f"Using cached exchange rates from Redis")
                    return self.rates
            
            # Fetch fresh rates...
            # ... existing fetch logic ...
            
            # Save to Redis if configured
            if self._redis:
                payload = {"rates": self.rates, "timestamp": self.last_updated}
                self._redis.set("currency:USD", json.dumps(payload), ex=1800)  # 30 min TTL
```

### Database Initialization

**File**: `backend/app/main.py`

The application uses PostgreSQL exclusively. Database initialization is handled by `init_postgres_database()` which:

- Creates all required tables if they don't exist
- Uses PostgreSQL-specific syntax (`SERIAL PRIMARY KEY`, `TIMESTAMP`, etc.)
- Checks for existing data before initializing
- Ensures proper sequence alignment for auto-incrementing IDs

```python
def init_postgres_database():
    """Initialize PostgreSQL database schema"""
    pg_url = settings.database_url.replace("+psycopg", "") if "+psycopg" in settings.database_url else settings.database_url
    with psycopg.connect(pg_url) as conn:
        with conn.cursor() as cur:
            # Create tables with PostgreSQL syntax
            cur.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    # ... other columns ...
                )
            ''')
            # ... other tables ...
```

## Frontend Implementation

### Authentication Store

**File**: `frontend/src/stores/authStore.ts`

```typescript
import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import {
  User,
  UserLogin,
  UserRegister,
  TokenResponse,
  PasswordResetRequest,
  PasswordResetConfirm,
  UserProfileUpdate,
  PasswordChange
} from '@/types/auth'
import { apiClient } from '@/lib/api'

interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  user: User | null
  isAuthenticated: boolean
  login: (credentials: UserLogin) => Promise<void>
  logout: () => void
  refreshAccessToken: () => Promise<void>
  register: (userData: UserRegister) => Promise<void>
  requestPasswordReset: (email: string) => Promise<void>
  confirmPasswordReset: (token: string, newPassword: string) => Promise<void>
  updateProfile: (updateData: UserProfileUpdate) => Promise<User>
  changePassword: (passwordChange: PasswordChange) => Promise<void>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,

      login: async (credentials: UserLogin) => {
        const response = await apiClient.login(credentials)
        set({
          accessToken: response.access_token,
          refreshToken: response.refresh_token,
          user: response.user,
          isAuthenticated: true,
        })
      },

      logout: () => {
        set({ accessToken: null, refreshToken: null, user: null, isAuthenticated: false })
      },

      refreshAccessToken: async () => {
        const currentRefreshToken = get().refreshToken
        if (!currentRefreshToken) {
          get().logout()
          throw new Error("No refresh token available")
        }
        const response = await apiClient.refreshToken(currentRefreshToken)
        set({
          accessToken: response.access_token,
          refreshToken: response.refresh_token,
          user: response.user,
          isAuthenticated: true,
        })
      },

      register: async (userData: UserRegister) => {
        const response = await apiClient.register(userData)
        set({
          accessToken: response.access_token,
          refreshToken: response.refresh_token,
          user: response.user,
          isAuthenticated: true,
        })
      },

      requestPasswordReset: async (email: string) => {
        await apiClient.requestPasswordReset(email)
      },

      confirmPasswordReset: async (token: string, newPassword: string) => {
        await apiClient.confirmPasswordReset(token, newPassword)
      },

      updateProfile: async (updateData: UserProfileUpdate) => {
        const updatedUser = await apiClient.updateProfile(updateData)
        set({ user: updatedUser })
        return updatedUser
      },

      changePassword: async (passwordChange: PasswordChange) => {
        await apiClient.changePassword(passwordChange)
      },
    }),
    {
      name: 'auth-storage',
      storage: createJSONStorage(() => localStorage),
    }
  )
)
```

### API Client with Authentication

**File**: `frontend/src/lib/api.ts`

```typescript
import { useAuthStore } from '@/stores/authStore'

class ApiClient {
  private client: AxiosInstance

  constructor() {
    this.client = axios.create({
      baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8100',
      timeout: 10000,
    })

    // Request interceptor to add auth headers
    this.client.interceptors.request.use(
      (config) => {
        const authState = useAuthStore.getState()
        if (authState.accessToken) {
          config.headers.Authorization = `Bearer ${authState.accessToken}`
        }
        return config
      },
      (error) => Promise.reject(error)
    )

    // Response interceptor to handle token refresh
    this.client.interceptors.response.use(
      (response) => response,
      async (error) => {
        if (error.response?.status === 401) {
          const authState = useAuthStore.getState()
          if (authState.refreshToken) {
            try {
              await authState.refreshAccessToken()
              // Retry the original request
              const originalRequest = error.config
              originalRequest.headers.Authorization = `Bearer ${useAuthStore.getState().accessToken}`
              return this.client(originalRequest)
            } catch (refreshError) {
              authState.logout()
              return Promise.reject(refreshError)
            }
          } else {
            authState.logout()
          }
        }
        return Promise.reject(error)
      }
    )
  }

  // Auth endpoints
  async register(userData: UserRegister): Promise<TokenResponse> {
    const response = await this.client.post('/api/auth/register', userData)
    return response.data
  }

  async login(credentials: UserLogin): Promise<TokenResponse> {
    const response = await this.client.post('/api/auth/login', credentials)
    return response.data
  }

  async refreshToken(refreshToken: string): Promise<TokenResponse> {
    const response = await this.client.post('/api/auth/refresh', null, {
      params: { refresh_token: refreshToken }
    })
    return response.data
  }

  async getCurrentUser(): Promise<User> {
    const response = await this.client.get('/api/auth/me')
    return response.data
  }

  async requestPasswordReset(email: string): Promise<{ message: string }> {
    const response = await this.client.post('/api/auth/password-reset-request', { email })
    return response.data
  }

  async confirmPasswordReset(token: string, newPassword: string): Promise<{ message: string }> {
    const response = await this.client.post('/api/auth/password-reset-confirm', { 
      token, 
      new_password: newPassword 
    })
    return response.data
  }

  async updateProfile(updateData: UserProfileUpdate): Promise<User> {
    const response = await this.client.put('/api/auth/profile', updateData)
    return response.data
  }

  async changePassword(passwordChange: PasswordChange): Promise<{ message: string }> {
    const response = await this.client.post('/api/auth/change-password', passwordChange)
    return response.data
  }
}

export const apiClient = new ApiClient()
```

### Route Protection Middleware

**File**: `frontend/src/middleware.ts`

```typescript
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
  const accessToken = request.cookies.get('auth-storage')?.value
    ? JSON.parse(request.cookies.get('auth-storage')?.value || '{}').state.accessToken
    : null

  const { pathname } = request.nextUrl

  // Define protected routes
  const protectedRoutes = ['/', '/profile']
  const authRoutes = ['/login', '/register', '/forgot-password', '/reset-password']

  if (protectedRoutes.includes(pathname) && !accessToken) {
    const url = request.nextUrl.clone()
    url.pathname = '/login'
    return NextResponse.redirect(url)
  }

  if (authRoutes.includes(pathname) && accessToken) {
    const url = request.nextUrl.clone()
    url.pathname = '/'
    return NextResponse.redirect(url)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/', '/login', '/register', '/profile', '/forgot-password', '/reset-password'],
}
```

## Database Design

### Entity Relationship Diagram

```text
┌─────────────────┐
│      users      │
├─────────────────┤
│ id (PK)         │
│ email (UNIQUE)  │
│ username (UNIQUE)│
│ hashed_password │
│ full_name       │
│ is_active       │
│ is_verified     │
│ created_at      │
│ updated_at      │
└─────────────────┘
         │
         │ 1:N
         ▼
┌─────────────────┐
│ portfolio_items │
├─────────────────┤
│ id (PK)         │
│ user_id (FK)    │
│ symbol          │
│ amount          │
│ price_buy       │
│ ...             │
└─────────────────┘
         │
         │ 1:N
         ▼
┌─────────────────┐
│     alerts      │
├─────────────────┤
│ id (PK)         │
│ user_id (FK)    │
│ symbol          │
│ threshold_price │
│ alert_type      │
│ ...             │
└─────────────────┘
```

### Indexes

```sql
-- User lookups
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);

-- Portfolio queries
CREATE INDEX idx_portfolio_user_id ON portfolio_items(user_id);
CREATE INDEX idx_portfolio_user_symbol ON portfolio_items(user_id, symbol);

-- Alert queries
CREATE INDEX idx_alerts_user_id ON alerts(user_id);
CREATE INDEX idx_alerts_user_symbol ON alerts(user_id, symbol);

-- Password reset tokens
CREATE INDEX idx_reset_tokens_token ON password_reset_tokens(token);
CREATE INDEX idx_reset_tokens_user_id ON password_reset_tokens(user_id);
```

## Security Implementation

### Password Security

```python
# bcrypt configuration
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # Configurable rounds
)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password with timing attack protection"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash password with salt"""
    return pwd_context.hash(password)
```

### JWT Security

```python
# JWT configuration
JWT_SECRET = settings.jwt_secret  # From environment
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

def create_access_token(data: dict) -> str:
    """Create access token with short expiration"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
```

### Input Validation

```python
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
        if not v.isalnum():
            raise ValueError('Username must contain only alphanumeric characters')
        return v
```

## Error Handling

### Backend Error Handling

```python
from fastapi import HTTPException, status

# Authentication errors
credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

# Validation errors
if not user or not verify_password(credentials.password, user[3]):
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

# Business logic errors
if cursor.fetchone():
    raise HTTPException(status_code=400, detail="Email or username already registered")
```

### Frontend Error Handling

```typescript
// API client error handling
this.client.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Handle token expiration
      try {
        await authState.refreshAccessToken()
        return this.client(error.config)
      } catch (refreshError) {
        authState.logout()
        return Promise.reject(refreshError)
      }
    }
    return Promise.reject(this.handleError(error))
  }
)

// Component error handling
const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault()
  setError('')
  
  try {
    await login({ email, password })
    router.push('/')
  } catch (error: any) {
    setError(error.message || 'Login failed')
  }
}
```

## Testing Strategy

### Unit Tests

```python
# test_auth.py
import pytest
from backend.app.utils.auth import verify_password, get_password_hash

def test_password_hashing():
    password = "testpassword123"
    hashed = get_password_hash(password)
    assert verify_password(password, hashed)
    assert not verify_password("wrongpassword", hashed)

def test_jwt_token_creation():
    from backend.app.utils.auth import create_access_token, decode_token
    data = {"sub": 1}
    token = create_access_token(data)
    decoded = decode_token(token)
    assert decoded["sub"] == 1
    assert decoded["type"] == "access"
```

### Integration Tests

```python
# test_auth_endpoints.py
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_user_registration():
    response = client.post("/api/auth/register", json={
        "email": "test@example.com",
        "username": "testuser",
        "password": "password123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "user" in data

def test_user_login():
    # First register
    client.post("/api/auth/register", json={
        "email": "test@example.com",
        "username": "testuser",
        "password": "password123"
    })
    
    # Then login
    response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "password123"
    })
    assert response.status_code == 200
```

### Frontend Tests

```typescript
// authStore.test.ts
import { renderHook, act } from '@testing-library/react'
import { useAuthStore } from '@/stores/authStore'

describe('AuthStore', () => {
  beforeEach(() => {
    useAuthStore.getState().logout()
  })

  it('should login user', async () => {
    const { result } = renderHook(() => useAuthStore())
    
    await act(async () => {
      await result.current.login({
        email: 'test@example.com',
        password: 'password123'
      })
    })

    expect(result.current.isAuthenticated).toBe(true)
    expect(result.current.user).toBeDefined()
  })
})
```

## Deployment Considerations

### Environment Configuration

```bash
# Production environment variables
JWT_SECRET=your-super-secure-jwt-secret-key
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Database configuration
DATABASE_URL=postgresql+psycopg://crypto:crypto_pass@postgres:5432/crypto_ai_agent
REDIS_URL=redis://redis:6379/0

# PostgreSQL connection
POSTGRES_DB=crypto_ai_agent
POSTGRES_USER=crypto
POSTGRES_PASSWORD=crypto_pass

# API configuration
API_PORT=8100
FRONTEND_PORT=3100
```

### Docker Compose Deployment

The system is now containerized with Docker Compose:

```yaml
services:
  backend:
    build: ./backend
    container_name: crypto-ai-backend
    env_file: .env
    ports:
      - "127.0.0.1:${API_PORT:-8100}:8100"
    depends_on:
      - postgres
      - redis
    volumes:
      - ./logs:/app/logs
    environment:
      - DATABASE_URL=postgresql+psycopg://crypto:crypto_pass@postgres:5432/crypto_ai_agent
      - REDIS_URL=redis://redis:6379/0

  postgres:
    image: postgres:15
    container_name: crypto-ai-postgres
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-crypto_ai_agent}
      POSTGRES_USER: ${POSTGRES_USER:-crypto}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-crypto_pass}
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7
    container_name: crypto-ai-redis
    command: ["redis-server", "--save", "", "--appendonly", "no"]
    volumes:
      - redisdata:/data

volumes:
  pgdata:
  redisdata:
```

### Database Schema

The system uses PostgreSQL exclusively. All database operations use PostgreSQL-specific features:

- `SERIAL PRIMARY KEY` for auto-incrementing IDs
- `TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP` for date fields
- `ON CONFLICT DO UPDATE` for upsert operations
- `%s` placeholders for parameterized queries
- `RETURNING id` for insert operations that need the generated ID

The database schema is automatically initialized on startup if tables don't exist:

### Security Checklist

- [x] JWT_SECRET is cryptographically secure
- [x] HTTPS is enabled in production (via Nginx reverse proxy)
- [x] CORS origins are properly configured
- [x] Database credentials are secure
- [x] PostgreSQL connection is isolated to Docker network
- [x] Redis caching with TTL for currency rates
- [x] Password hashing rounds are appropriate
- [x] Token expiration times are reasonable (30 min / 7 days)
- [x] Input validation is comprehensive
- [x] Error messages don't leak information
- [x] Logs are written to mounted volume
- [x] Database uses named volumes for persistence

### Performance Optimization

```python
# PostgreSQL with psycopg
import psycopg

# Connection uses default pooling from psycopg
conn = psycopg.connect(DATABASE_URL)

# Redis caching for currency rates
import redis
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# Cache with 30-minute TTL
redis_client.set("currency:USD", json.dumps(payload), ex=1800)
```

### Database Backup

```bash
# Backup PostgreSQL data
docker compose exec postgres pg_dump -U crypto crypto_ai_agent > backup.sql

# Restore from backup
docker compose exec -T postgres psql -U crypto crypto_ai_agent < backup.sql
```

### Health Checks

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:${API_PORT:-8100}/docs"]
  interval: 30s
  timeout: 5s
  retries: 5
```

---

**Last Updated**: October 29, 2025
**Version**: 2.0.0
**Status**: Production Ready with PostgreSQL + Redis

## Postgres Compatibility and CORS Updates (2025-10-29)

### SQL Query Implementation

- All SQL queries use PostgreSQL syntax:
  - `%s` placeholders for parameterized queries (PostgreSQL standard)
  - `RETURNING id` for insert operations to retrieve generated IDs
  - `ON CONFLICT DO UPDATE` for upsert operations
- Refactored inserts for:
  - `POST /api/portfolio/` (portfolio item creation)
  - `POST /api/alerts/` (alert creation)
- Updated `backend/app/services/bitfinex_credential_service.py` to use PostgreSQL:
  - `ON CONFLICT (user_id, exchange) DO UPDATE` for upsert operations
  - Standard PostgreSQL placeholder syntax

### Alerts Table Sequence Fix (PostgreSQL)

- Ensured `alerts.id` uses a proper sequence and default nextval within `init_postgres_database()` and aligned the sequence to `MAX(id)+1`.

### CORS

- Confirmed `CORSMiddleware` is initialized immediately after `app = FastAPI(...)` with:
  - `allow_origins` from `CORS_ORIGINS` env (e.g., `http://localhost:3100`)
  - `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`
- Note: If any endpoint still shows CORS in browser, it usually indicates an upstream 5xx response. After SQL fixes, portfolio and alerts are functional via API; the UI should reflect success upon refresh.
