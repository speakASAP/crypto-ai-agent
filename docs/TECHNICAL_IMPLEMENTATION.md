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
SECRET_KEY = settings.jwt_secret
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
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT refresh token with longer expiration"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> dict:
    """Decode and verify JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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
import sqlite3
from backend.app.core.config import DB_FILE
from backend.app.utils.auth import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def get_db_connection():
    """Get database connection with row factory"""
    conn = sqlite3.connect(DB_FILE)
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
    cursor.execute(
        "SELECT id, email, username, full_name, is_active, created_at FROM users WHERE id = ?", 
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
```

### Database Migration

**File**: `backend/app/main.py`

```python
def migrate_database_for_users():
    """Migrate database to add user management - DELETES EXISTING DATA"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        # Check if users table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if cursor.fetchone():
            logger.info("Users table already exists, skipping migration")
            return

        logger.info("Starting database migration for user management...")

        # Drop existing tables (delete all data)
        cursor.execute("DROP TABLE IF EXISTS alert_history")
        cursor.execute("DROP TABLE IF EXISTS alerts")
        cursor.execute("DROP TABLE IF EXISTS tracked_symbols")
        cursor.execute("DROP TABLE IF EXISTS portfolio_items")

        conn.commit()
        logger.info("Migration complete: Old tables dropped, will create new schema")

    except Exception as e:
        logger.error(f"Migration error: {e}")
        conn.rollback()
    finally:
        conn.close()

def init_database():
    """Initialize SQLite database with user management tables"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            full_name TEXT,
            is_active BOOLEAN DEFAULT 1,
            is_verified BOOLEAN DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')

    # Create password reset tokens table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TEXT NOT NULL,
            used BOOLEAN DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Create user sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Create portfolio table with user_id
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfolio_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            amount REAL NOT NULL,
            price_buy REAL NOT NULL,
            purchase_date TEXT,
            base_currency TEXT NOT NULL,
            purchase_price_eur REAL,
            purchase_price_czk REAL,
            source TEXT,
            commission REAL DEFAULT 0.0,
            total_investment_text TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            current_price REAL,
            current_value REAL,
            pnl REAL,
            pnl_percent REAL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Create alerts table with user_id
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            threshold_price REAL NOT NULL,
            alert_type TEXT NOT NULL,
            message TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Create tracked_symbols table with user_id
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tracked_symbols (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            active BOOLEAN DEFAULT 1,
            last_updated TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, symbol)
        )
    ''')

    # Create alert_history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alert_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            triggered_price REAL NOT NULL,
            triggered_at TEXT NOT NULL,
            FOREIGN KEY (alert_id) REFERENCES alerts (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    conn.commit()
    conn.close()
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
      baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
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

```
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
SECRET_KEY = settings.jwt_secret  # From environment
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

def create_access_token(data: dict) -> str:
    """Create access token with short expiration"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
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
SECRET_KEY=your-super-secure-secret-key
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
DATABASE_URL=postgresql://user:password@localhost:5432/crypto_agent
```

### Database Migration

```python
# Production migration script
def migrate_to_production():
    """Migrate from SQLite to PostgreSQL"""
    # 1. Export SQLite data
    # 2. Transform data for PostgreSQL
    # 3. Import to PostgreSQL
    # 4. Verify data integrity
    pass
```

### Security Checklist

- [ ] JWT_SECRET is cryptographically secure
- [ ] HTTPS is enabled in production
- [ ] CORS origins are properly configured
- [ ] Database credentials are secure
- [ ] Password hashing rounds are appropriate
- [ ] Token expiration times are reasonable
- [ ] Input validation is comprehensive
- [ ] Error messages don't leak information

### Performance Optimization

```python
# Database connection pooling
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True
)

# Redis caching for sessions
import redis
redis_client = redis.Redis(host='localhost', port=6379, db=0)
```

---

**Last Updated**: October 23, 2025
**Version**: 2.0.0
**Status**: Production Ready
