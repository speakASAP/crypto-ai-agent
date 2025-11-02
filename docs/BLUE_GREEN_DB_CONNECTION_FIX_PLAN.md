# Blue/Green Deployment Database Connection Fix Plan

## Problem Summary

During blue/green deployment restarts, users experience multiple failures due to database unavailability:

1. **Login endpoint** (`/api/auth/login`): Returns 401 "Invalid email or password" - actually a database connection failure
2. **Current user endpoint** (`/api/auth/me`): Returns 401 - token validation requires database access
3. **Token refresh endpoint** (`/api/auth/refresh`): Returns 404 "User not found" - database query fails during refresh
4. **Unhandled Promise Rejections**: Frontend receives uncaught database connection errors

All errors stem from the same root cause: database connections fail immediately without retry logic during blue/green deployment transitions.

## Root Causes Identified

1. **Health check doesn't verify database connectivity**: The `/health` endpoint returns a status but doesn't actually test if database connections work. This causes deployment scripts to mark services as "healthy" even when database connections fail.

2. **No retry logic for database connections during startup**: `init_postgres_database()` attempts to connect immediately without retry logic. If the database container isn't fully ready (even though infrastructure is running), initialization fails silently.

3. **No retry logic for runtime database connection failures**: `get_db_connection()` creates new connections but fails immediately if the database is temporarily unavailable. Login requests fail with 401 errors.

4. **Poor error handling**: Database connection failures aren't properly logged or handled gracefully, making debugging difficult.

## Solution Overview

The fix will:

1. Update the health check endpoint to verify actual database connectivity
2. Add retry logic with exponential backoff for database connections during startup
3. Add retry logic for runtime database connection failures
4. Improve error handling and logging for database connection issues
5. Ensure connections are properly tested before considering service "healthy"

## Implementation Details

### 1. Update Health Check Endpoint (`backend/app/api/health.py`)

**Current State:**

- Returns status without testing database connectivity
- Deployment scripts think service is healthy even when database isn't accessible

**Changes:**

- Add actual database connection test
- Return appropriate status based on database connectivity
- Include database connection status in response

**File:** `backend/app/api/health.py`

**Changes:**

```python
# Add database connection test
# Test both read and write connectivity
# Return detailed status including database connection state
```

### 2. Add Retry Logic to Database Initialization (`backend/app/main.py`)

**Current State:**

- `init_postgres_database()` connects immediately without retry
- Fails silently if database isn't ready
- No exponential backoff

**Changes:**

- Add retry logic with exponential backoff (max 5 retries, starting at 2 seconds)
- Add proper error logging
- Ensure initialization doesn't fail the entire startup if retries are exhausted (log warning, continue)

**File:** `backend/app/main.py`

**Function:** `init_postgres_database()`

**Retry Logic:**

- Max retries: 5
- Initial delay: 2 seconds
- Exponential backoff: delay *= 1.5
- Max delay: 30 seconds
- Log each retry attempt

### 3. Add Retry Logic to Database Connection Functions

**Current State:**

- `get_db_connection()` in `backend/app/main.py` and `backend/app/dependencies/auth.py` create connections without retry
- Fail immediately if database is unavailable

**Changes:**

- Create shared database connection retry function
- Add retry logic with exponential backoff for runtime connections
- Max 3 retries for runtime connections (faster failure than startup)
- Proper error handling and logging

**Files:**

- `backend/app/main.py` - `get_db_connection()` function
- `backend/app/dependencies/auth.py` - `get_db_connection()` function

**Retry Logic for Runtime:**

- Max retries: 3
- Initial delay: 0.5 seconds
- Exponential backoff: delay *= 2
- Max delay: 2 seconds
- Raise exception after retries exhausted

### 4. Improve Error Handling and Logging

**Changes:**

- Add detailed logging for database connection attempts
- Log connection failures with context
- Include retry information in logs
- Use centralized logger

### 5. Update Lifespan Function for Better Startup Handling

**Current State:**

- `lifespan()` calls `init_postgres_database()` without error handling
- If initialization fails, service may start but be unable to handle requests

**Changes:**

- Wrap `init_postgres_database()` call in try-except
- Log warnings if initialization fails after retries
- Continue startup even if initialization fails (database might be ready later)

**File:** `backend/app/main.py`

**Function:** `lifespan()`

## Files to Modify

1. `backend/app/api/health.py` - Add database connectivity check
2. `backend/app/main.py` - Add retry logic to `init_postgres_database()` and `get_db_connection()`
3. `backend/app/dependencies/auth.py` - Add retry logic to `get_db_connection()`
4. `backend/app/api/auth.py` - All endpoints using `get_db_connection()` will benefit from retry logic:
   - `/api/auth/login` (line 115)
   - `/api/auth/refresh` (line 194)
   - `/api/auth/me` (line 227)
   - All other endpoints using `get_current_active_user` dependency

## Implementation Checklist

1. Update `backend/app/api/health.py`:
   - [ ] Import database connection utilities
   - [ ] Add function to test database connectivity
   - [ ] Update `health_check()` endpoint to test database connection
   - [ ] Return appropriate status based on database connectivity
   - [ ] Include database status in response

2. Update `backend/app/main.py`:
   - [ ] Add `time` and `sleep` imports for retry logic
   - [ ] Create `connect_with_retry()` helper function with exponential backoff
   - [ ] Update `init_postgres_database()` to use retry logic with max 5 retries
   - [ ] Add proper error handling and logging in `init_postgres_database()`
   - [ ] Update `get_db_connection()` to use retry logic with max 3 retries
   - [ ] Update `lifespan()` to handle `init_postgres_database()` failures gracefully
   - [ ] Add detailed logging for all database connection attempts

3. Update `backend/app/dependencies/auth.py`:
   - [ ] Add `time` and `sleep` imports for retry logic
   - [ ] Import or create shared retry logic function
   - [ ] Update `get_db_connection()` to use retry logic with max 3 retries
   - [ ] Add proper error handling and logging

4. Testing:
   - [ ] Test health endpoint with database available
   - [ ] Test health endpoint with database unavailable
   - [ ] Test startup with database not ready (should retry)
   - [ ] Test login (`/api/auth/login`) during deployment (should retry database connections)
   - [ ] Test `/api/auth/me` endpoint during deployment (should retry database connections)
   - [ ] Test `/api/auth/refresh` endpoint during deployment (should retry database connections)
   - [ ] Verify logs show retry attempts
   - [ ] Verify deployment script receives accurate health status
   - [ ] Verify no unhandled promise rejections in frontend

## Expected Outcomes

1. Health check endpoint will accurately report database connectivity status
2. Application will retry database connections during startup, preventing premature "healthy" status
3. Runtime database connection failures will retry, preventing immediate errors during deployments:
   - Login endpoint will retry before returning 401
   - `/me` endpoint will retry before returning 401
   - `/refresh` endpoint will retry before returning 404
4. Better logging will make debugging connection issues easier
5. Blue/green deployments will maintain availability because:
   - New instances wait for database connectivity before being marked healthy
   - Runtime requests retry database connections, preventing temporary failures
   - Health checks accurately reflect actual service readiness
   - No unhandled promise rejections - all database errors are caught and handled

## Notes

- Retry logic should be configurable via environment variables if needed
- Database connection retries should not block application startup indefinitely
- Health check should fail fast but accurately report database status
- All database connection errors should be logged for troubleshooting
