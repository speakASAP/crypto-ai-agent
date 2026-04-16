# 🚀 Crypto AI Agent v2.0 - Next.js + FastAPI + PostgreSQL

## Project Overview

This is the next-generation version of the Crypto AI Agent, successfully migrated from Streamlit to a modern Next.js + FastAPI + PostgreSQL architecture for optimal performance and scalability.

## Architecture

### Frontend: Next.js 14+ with App Router

- **Framework**: Next.js with TypeScript
- **Styling**: Tailwind CSS + shadcn/ui components
- **State Management**: Zustand + React Query
- **Real-time**: WebSocket integration
- **Deployment**: Vercel or local development

### Backend: FastAPI

- **Framework**: FastAPI with Python 3.12+
- **Database**: PostgreSQL (production-grade, scalable)
- **WebSocket**: FastAPI WebSocket support
- **Real-time**: Live price updates and alerts
- **Deployment**: Local development or production server

### Database: PostgreSQL

- **All Environments** (Development & Production): Uses shared database server
  - Database Server: `db-server-postgres:${DB_SERVER_PORT:-5432}` (via nginx-network, port configured in database-server/.env)
  - Database Name: `crypto_ai_agent`
  - Infrastructure: Managed by centralized `database-server` microservice
  - Connection: Configured via `DATABASE_URL` environment variable
  - Example: `postgresql://dbadmin:password@db-server-postgres:${DB_SERVER_PORT:-5432}/crypto_ai_agent`
  - Shared by Blue/Green: Both environments use the same shared database instance
  - Persistent Storage: Data persists across deployments
  - **Note**: Local Postgres/Redis containers have been removed. All applications now use the shared database infrastructure to eliminate port conflicts and ensure consistency.

## Main Features

### 🔐 Multi-User Authentication

- **Centralized Authentication**: Uses shared `auth-microservice` for all authentication operations
- **User Registration & Login**: Secure JWT-based authentication via auth-microservice
- **Password Security**: bcrypt hashing handled by auth-microservice
- **Data Isolation**: Each user has their own portfolio and alerts
- **Password Reset**: Secure token-based password reset via auth-microservice with email notifications
- **Password Change**: Change password functionality via auth-microservice
- **Profile Management**: Update user information (local profile data stored in application database)

### 📊 Portfolio Management

- **Multi-Currency Support**: USD, EUR, CZK, GBP, JPY
- **Centralized Price Updates**: Prices are updated every 5 minutes for all cryptocurrencies in a single API call
- **Real-time Updates**: Live price tracking via WebSocket broadcasts
- **P&L Tracking**: Automatic profit/loss calculations
- **Portfolio Summary**: Total value and performance metrics
- **Binance Import**: Automatically import your Binance portfolio
- **Source Tracking**: Track where each asset was purchased

### 🚨 Price Alerts

- **Custom Alerts**: Set price thresholds for any cryptocurrency
- **Real-time Notifications**: Instant alerts when prices hit targets
- **Alert History**: Track all triggered alerts with recovery context
- **Telegram Integration**: Optional Telegram notifications with user-specific settings
- **Robust Recovery System**: Historical price checking to catch missed alerts during downtime
- **Database Reliability**: WAL mode and connection pooling for high availability
- **Missed Alert Detection**: Automatic recovery on service startup with detailed notifications

### 🤖 AI Advisor

- **Price Predictions**: AI-powered price predictions for 24 hours, 1 week, 1 month, and 1 year
- **Centralized Predictions**: Predictions are generated once per day per cryptocurrency and shared across all users
- **Confidence Scores**: Each prediction includes a confidence percentage based on data quality
- **News Analysis**: Automatic analysis of cryptocurrency news with sentiment scoring
- **Performance Tracking**: Historical accuracy tracking to compare prediction performance
- **Model Comparison**: Track which AI models perform best for different cryptocurrencies
- **Interactive Charts**: Mini price charts on portfolio items, clickable for detailed 1-year view
- **Detailed Symbol Pages**: Comprehensive analysis pages with full charts, predictions, and news

## Quick Start

### Prerequisites

- Node.js 18+
- Python 3.12+

### Development Setup

1. **Clone and navigate to the project:**

   ```bash
   cd crypto-ai-agent
   ```

2. **Install backend dependencies:**

   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Install frontend dependencies:**

   ```bash
   cd frontend
   npm install
   ```

4. **Start the backend:**

   ```bash
   cd backend
   # Port configured in crypto-ai-agent/.env: API_PORT (default: 3102)
   python -m uvicorn app.main:app --reload --host 0.0.0.0 --port ${API_PORT:-3102}
   ```

5. **Start the frontend (in a new terminal):**

   ```bash
   cd frontend
   npm run dev
   ```

6. **Access the application** (ports configured in `crypto-ai-agent/.env`):
   - Frontend: <http://localhost:${FRONTEND_PORT:-3100}>
   - Backend API: <http://localhost:${API_PORT:-3102}>
   - API Docs: <http://localhost:${API_PORT:-3102}/docs>

7. **First Time Setup:**
   - Navigate to <http://localhost:${FRONTEND_PORT:-3100}/register>
   - Create your account
   - Login and start managing your portfolio
   - Configure AI Advisor (see [AI Advisor Documentation](docs/AI_ADVISOR.md))

## 🚀 Binance Portfolio Import

Import your cryptocurrency holdings directly from Binance with just a few clicks!

### Quick Import Setup

1. **Get Binance API Credentials:**
   - Go to [Binance API Management](https://www.binance.com/en/my/settings/api-management)
   - Create new API key with "Enable Reading" permission
   - Copy API Key and Secret Key

2. **Configure Environment:**

   ```bash
   # Add to your .env file
   BINANCE_API_KEY=your_api_key_here
   BINANCE_API_SECRET=your_secret_key_here
   ```

3. **Import Your Portfolio:**

   ```bash
   # Test the import
   python test_binance_import.py
   ```

### What Gets Imported

- ✅ **All cryptocurrency holdings** from your Binance account
- ✅ **Real-time price tracking** for imported assets
- ✅ **Multi-currency support** (USD, EUR, CZK)
- ✅ **Source tracking** (marked as "Binance")
- ✅ **Import history** for tracking

### Security Features

- 🔒 **Read-only access** - Cannot trade or withdraw
- 🔒 **User isolation** - Only you can see your data
- 🔒 **Secure API integration** - Industry-standard encryption
- 🔒 **Duplicate prevention** - Won't import duplicate assets

For detailed setup instructions, see [Binance Import Guide](docs/BINANCE_IMPORT_GUIDE.md).

## User Management System

The Crypto AI Agent now features a complete multi-user authentication system that allows multiple users to manage their personal portfolios independently.

### 🔐 Authentication Features

- **Centralized Auth Service**: All authentication operations use the shared `auth-microservice` (`https://auth.alfares.cz`)
- **JWT-based Authentication**: Secure login/logout with JSON Web Tokens generated by auth-microservice
- **User Registration**: Open registration with email and username validation via auth-microservice
- **Password Security**: bcrypt hashing handled by auth-microservice (no local password storage)
- **Password Reset**: Email-based password reset via auth-microservice (uses notifications-microservice for emails)
- **Password Change**: Change password functionality via auth-microservice
- **User Profile Management**: Update profile information (application-specific data like preferred_currency, telegram settings)
- **Data Isolation**: Complete separation of user data - each user sees only their own portfolio
- **Token Validation**: All JWT tokens validated via auth-microservice
- **User IDs**: Uses UUID (TEXT) format matching auth-microservice (no local integer IDs)
- **No Local Auth Tables**: Removed `password_reset_tokens` and `user_sessions` tables (handled by auth-microservice)

### 🚀 Getting Started with User Management

1. **Start the application:**

   ```bash
   ./start.sh
   ```

2. **Register a new account** (ports configured in `crypto-ai-agent/.env`):
   - Navigate to <http://localhost:${FRONTEND_PORT:-3100}/register>
   - Fill in your email, username, and password
   - Click "Register" to create your account

3. **Login to your account:**
   - Navigate to <http://localhost:${FRONTEND_PORT:-3100}/login>
   - Enter your credentials
   - You'll be redirected to your personal dashboard

4. **Configure Binance API (Optional):**
   - Go to Profile Settings → Binance Settings
   - Add your Binance API credentials for portfolio import
   - Your credentials are encrypted and stored securely
   - Only you can access your API keys

5. **Manage your portfolio:**
   - Add, edit, and delete portfolio items
   - Import portfolio from Binance (if configured)
   - Set up price alerts
   - Track your investments
   - All data is private to your account

### 🔒 Security Features

- **Centralized Authentication**: All authentication handled by auth-microservice for consistent security
- **Password Hashing**: All passwords are hashed using bcrypt (handled by auth-microservice)
- **JWT Tokens** (generated by auth-microservice):
  - Access tokens (default: 7 days, configurable)
  - Refresh tokens (default: 30 days, configurable)
- **Route Protection**: Automatic redirection for unauthenticated users
- **Data Isolation**: Users can only access their own data
- **Session Management**: Automatic token refresh and logout
- **Token Validation**: All tokens validated via auth-microservice
- **Encrypted API Credentials**: User API keys are encrypted using industry-standard encryption
- **Credential Isolation**: Each user's API credentials are completely isolated
- **No Global API Keys**: System no longer uses global API keys for enhanced security

### 📱 User Interface

- **Login Page**: `/login` - User authentication
- **Register Page**: `/register` - New user registration
- **Profile Page**: `/profile` - Manage account settings
- **Forgot Password**: `/forgot-password` - Request password reset
- **Reset Password**: `/reset-password` - Set new password
- **Dashboard**: `/` - Main portfolio interface (protected)

### 🛠️ API Endpoints

All API endpoints now require authentication. Authentication operations are handled by the centralized `auth-microservice`:

**Authentication Endpoints** (delegated to auth-microservice):

- `POST /api/auth/register` - User registration (via auth-microservice)
- `POST /api/auth/login` - User login (via auth-microservice)
- `POST /api/auth/refresh` - Refresh access token (via auth-microservice)
- `POST /api/auth/change-password` - Change password (via auth-microservice, requires authentication)
- `POST /api/auth/password-reset-request` - Request password reset (via auth-microservice)
- `POST /api/auth/password-reset-confirm` - Confirm password reset (via auth-microservice)

**User Profile Endpoints** (application-specific data):

- `GET /api/auth/me` - Get current user info (combines auth-microservice user + local profile data)
- `PUT /api/auth/profile` - Update user profile (local data: preferred_currency, telegram settings, etc.)

**Binance Credential Management:**

- `POST /api/auth/binance-credentials` - Save Binance API credentials
- `GET /api/auth/binance-credentials` - Get Binance credentials status
- `POST /api/auth/test-binance-connection` - Test Binance API connection
- `DELETE /api/auth/binance-credentials` - Delete Binance credentials

All portfolio, alerts, and symbols endpoints are now user-specific and require authentication.

### 🔧 Configuration

The system uses the following environment variables:

```bash
# Auth Microservice (REQUIRED)
# Production: https://auth.alfares.cz
# Docker/Development: http://auth-microservice:3370
AUTH_SERVICE_URL=https://auth.alfares.cz

# Optional: Telegram Notifications
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

**Important**:

- `AUTH_SERVICE_URL` is required - points to the centralized auth-microservice
- For Docker/development, use: `AUTH_SERVICE_URL=http://auth-microservice:${PORT:-3370}` (port configured in auth-microservice/.env)
- For production, use: `AUTH_SERVICE_URL=https://auth.alfares.cz`
- JWT tokens are generated and validated by auth-microservice (no local JWT_SECRET needed)
- Binance API credentials are configured per-user in Profile Settings
- Global Binance API keys are no longer used for enhanced security

### 📊 Database Schema

**Note**: User authentication data (passwords, email verification, password reset tokens, sessions) is stored in the centralized `auth-microservice` database. This application only stores application-specific user profile data.

The system includes the following local tables:

- `users` - Application-specific user profile data (preferred_currency, telegram settings, etc.)
  - `id` - User ID (TEXT/UUID, matches auth-microservice user ID)
  - `email` - Email (synced from auth-microservice)
  - `username` - Username (application-specific)
  - `preferred_currency` - User's preferred currency
  - `telegram_bot_token` - User's Telegram bot token
  - `telegram_chat_id` - User's Telegram chat ID
  - Other application-specific fields
  - **Note**: No `hashed_password` column - passwords handled by auth-microservice
- `user_api_credentials` - Encrypted storage of user API credentials (Binance, etc.)
- All existing tables include `user_id` foreign keys (TEXT/UUID, references auth-microservice user ID)
- **Removed tables**: `password_reset_tokens`, `user_sessions` (handled by auth-microservice)

**Centralized Data Tables:**

- `crypto_prices` - Centralized cryptocurrency price storage (updated every 5 minutes)
  - Stores USD prices for all cryptocurrencies in user portfolios
  - Single source of truth for price data
  - Updated via background task, read by all users
  
- `ai_predictions` - Global AI predictions (updated once per day per symbol)
  - `user_id` is nullable for global predictions (shared across all users)
  - Predictions generated once per day and reused by all users
  - Reduces AI API calls and rate limit issues

### 🧪 Testing User Management

1. **Test Registration:**
   - Visit `/register`
   - Create multiple test accounts
   - Verify each user has isolated data

2. **Test Login/Logout:**
   - Login with different accounts
   - Verify data isolation
   - Test logout functionality

3. **Test Password Reset:**
   - Use `/forgot-password` to request reset
   - Check logs for reset token
   - Use token to reset password

4. **Test Profile Management:**
   - Update profile information
   - Change passwords
   - Verify changes persist

### 🚨 Troubleshooting

**Common Issues:**

1. **"JWT_SECRET not configured" warning:**
   - Add `JWT_SECRET=your-secret-key` to `.env` file

2. **Authentication errors:**
   - Check if backend is running on port 8100
   - Verify JWT_SECRET is set correctly

3. **Data not loading:**
   - Ensure you're logged in
   - Check browser console for errors
   - Verify API endpoints are accessible

4. **Password reset not working:**
   - Check backend logs for reset tokens
   - Verify email configuration (currently logs tokens)

### 📈 Performance

- **User Isolation**: O(1) data filtering by user_id
- **Token Validation**: Fast JWT verification
- **Password Hashing**: Secure bcrypt with configurable rounds
- **Session Management**: Efficient token refresh mechanism

### 🔄 Migration Notes

- **Existing Data**: All existing portfolio data was cleared during migration
- **Fresh Start**: Users need to re-register and recreate their portfolios
- **Backup**: Original data was backed up before migration

## 🔌 Port Configuration

**Port Range**: 31xx (crypto-ai-agent application)

All services use the same host and container ports for consistency:

| Service | Host Port (Blue) | Host Port (Green) | Container Port | Description |
| ------- | ---------------- | ----------------- | -------------- | ----------- |
| **Frontend** | 3100 | 3101 | 3100 | Next.js frontend application |
| **Backend API** | 3102 | 3103 | 3102 | FastAPI backend service |
| **UI Port** | 3104 | 3104 | 3104 | Additional UI interface (Streamlit) |

**Note**:

- Green deployment uses different host ports but same container ports as blue deployment
- All ports are exposed on `127.0.0.1` only (localhost) for security
- External access is provided via nginx-microservice reverse proxy
- Uses shared database-server (db-server-postgres:${DB_SERVER_PORT:-5432}, db-server-redis:${REDIS_SERVER_PORT:-6379}) via nginx-network (ports configured in database-server/.env)

### Local Development

#### Backend Development

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 3102
```

#### Frontend Development

```bash
cd frontend
npm install
npm run dev
```

## Project Structure

```text
crypto-ai-agent/
├── frontend/                 # Next.js application
│   ├── src/
│   │   ├── app/             # App Router pages
│   │   ├── components/      # Reusable components
│   │   ├── lib/            # Utilities and configurations
│   │   ├── hooks/          # Custom React hooks
│   │   ├── stores/         # Zustand stores
│   │   └── types/          # TypeScript types
│   ├── public/             # Static assets
│   └── package.json
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── api/            # API routes
│   │   ├── core/           # Core configurations
│   │   ├── models/         # Database models
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business logic
│   │   └── utils/          # Utilities
│   └── requirements.txt
├── docker-compose.yml      # Docker compose stack (production-compatible)
└── README.md
```

## Features

### User Management

- **Multi-user support**: Each user has their own personal portfolio
- **Centralized Authentication**: All authentication via auth-microservice
- **JWT Authentication**: Secure login/logout with JWT tokens (generated by auth-microservice)
- **User Registration**: Open registration with email and username (via auth-microservice)
- **Password Security**: bcrypt hashing handled by auth-microservice
- **Password Reset**: Email-based password reset via auth-microservice
- **Password Change**: Change password functionality via auth-microservice
- **Profile Management**: Users can update their profile information (application-specific data)
- **Data Isolation**: Complete separation of user data

### Portfolio Management

- Multi-currency support (USD, EUR, CZK)
- Real-time price tracking
- Purchase history and source tracking
- Performance analytics
- **Personal portfolios**: Each user sees only their own data

### Price Monitoring

- WebSocket-based real-time updates
- Customizable price alerts
- Telegram notifications

### Data Visualization

- Interactive charts and graphs
- Portfolio performance metrics
- Real-time market data

## Performance Improvements

### From Streamlit to Next.js + FastAPI

- **Page Load Time**: < 2 seconds (vs 5+ seconds)
- **API Response Time**: < 500ms (vs 2+ seconds)
- **Real-time Updates**: < 100ms latency (vs 1+ seconds)
- **Database Queries**: < 50ms average (vs 200+ ms)
- **Cache Hit Rate**: > 90% (vs 0%)

### Centralized Price and Prediction System

- **Price Updates**: Single API call every 5 minutes for all cryptocurrencies (vs per-user calls)
- **AI Predictions**: Single generation per day per symbol shared across all users (vs per-user generation)
- **API Efficiency**: Reduced external API calls by 90%+ for multi-user scenarios
- **Rate Limit Protection**: No API rate limits even with hundreds of users
- **Database-First**: All user requests read from centralized database tables (no external API calls)

### Scalability

- **Concurrent Users**: 100+ users (vs 10)
- **Portfolio Items**: 1000+ items (vs 100)
- **API Requests**: 1000+ requests/minute (vs 100)
- **Database Connections**: 50+ concurrent (vs 1)

## Deployment

### Production (Docker)

See `docs/DEPLOYMENT_DOCKER.md` for docker-compose deployment with external Nginx.

```bash
# Build and start
docker compose up -d --build

# Access (ports configured in crypto-ai-agent/.env)
# Frontend: http://localhost:${FRONTEND_PORT:-3100}
# Backend API: http://localhost:${API_PORT:-3102}
# API Docs: http://localhost:${API_PORT:-3102}/docs
```

### Blue/Green Deployment (Production Restart)

The production environment uses blue/green deployment for zero-downtime restarts and updates.

#### Deployment Prerequisites

- Nginx microservice must be running
- Service must be registered in `/nginx-microservice/service-registry/crypto-ai-agent.json`
- Shared database server must be running (see [Database Management](#database-management))

#### Restarting the Service

**From the nginx-microservice directory:**

```bash
ssh statex
cd nginx-microservice
./scripts/blue-green/deploy.sh crypto-ai-agent
```

This will:

1. **Check Infrastructure**: Verify database and Redis are running
2. **Prepare New Environment**: Build and start the inactive color (blue or green)
3. **Health Checks**: Verify the new environment is healthy
4. **Switch Traffic**: Instantly switch traffic to the new environment (< 2 seconds downtime)
5. **Monitor**: Monitor health for 5 minutes with automatic rollback on failure
6. **Cleanup**: Remove old environment if deployment is successful

#### Deployment Phases

- **Phase 0**: Infrastructure verification (database/Redis availability)
- **Phase 1**: Build and start new containers, verify health
- **Phase 2**: Switch nginx traffic to new environment
- **Phase 3**: Monitor for 5 minutes (health checks every 30 seconds)
- **Phase 4**: Cleanup old environment if successful

#### Manual Rollback

If you need to rollback to the previous deployment:

```bash
cd nginx-microservice
./scripts/blue-green/rollback.sh crypto-ai-agent
```

#### Check Deployment Status

```bash
cat nginx-microservice/state/crypto-ai-agent.json | jq .
```

**Status Fields:**

- `active_color`: Currently active environment (blue or green)
- `blue.status`: Status of blue containers
- `green.status`: Status of green containers
- `last_deployment`: Last deployment timestamp and success status

#### Database Configuration

**IMPORTANT**: Both blue and green environments connect to the **same shared production database** (`db-server-postgres`) to ensure:

- ✅ Zero data loss during deployments
- ✅ Consistent data across environments
- ✅ Customer data always available

Configuration in `docker-compose.blue.yml` and `docker-compose.green.yml`:

```yaml
environment:
  # Ports configured in database-server/.env: DB_SERVER_PORT (default: 5432), REDIS_SERVER_PORT (default: 6379)
  - DATABASE_URL=postgresql+psycopg://${POSTGRES_USER:-crypto}:${POSTGRES_PASSWORD:-crypto_pass}@db-server-postgres:${DB_SERVER_PORT:-5432}/${POSTGRES_DB:-crypto_ai_agent}
  - REDIS_URL=redis://db-server-redis:${REDIS_SERVER_PORT:-6379}/0
  - LOGGING_SERVICE_URL=http://logging-microservice:3367
```

Shared database server must be running:

```bash
cd database-server
./scripts/start.sh
```

#### Verification After Deployment

1. **Test Login**:

   ```bash
   curl -X POST https://crypto-ai-agent.alfares.cz/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"your-email@example.com","password":"your-password"}'
   ```

2. **Check Health**:

   ```bash
   curl https://crypto-ai-agent.alfares.cz/api/health
   ```

3. **Verify Portfolio**: Login and confirm portfolio items are accessible

#### Deployment Troubleshooting

##### Issue: "Infrastructure not found"

- Ensure database-server is running: `cd database-server && ./scripts/status.sh`
- Start database-server if needed: `cd database-server && ./scripts/start.sh`
- Verify containers are healthy: Check `db-server-postgres` and `db-server-redis` are running

##### Issue: "Health check failed"

- Deployment automatically rolls back on health check failure
- Check logs: `docker logs crypto-ai-backend-green`
- Check deployment logs: `tail -f nginx-microservice/logs/blue-green/deploy.log`

##### Issue: "Login fails after deployment"

- Verify database-server is running: `cd database-server && ./scripts/status.sh`
- Verify database connection: Check `DATABASE_URL` in container
- Verify database has customer data: Check user count in database
- Ensure backend connects to `db-server-postgres` (shared database with customer data)
- Start database-server if needed: `cd database-server && ./scripts/start.sh`

For detailed troubleshooting, see [Blue/Green Deployment Guide](docs/BLUE_GREEN_DEPLOYMENT_GUIDE.md).

### Database Management

The production environment uses a **shared database server** (`database-server`) that provides centralized PostgreSQL and Redis infrastructure. This ensures data persistence, zero-downtime deployments, and centralized management across all services.

#### Database Architecture

**Production Setup:**

- **PostgreSQL**: `db-server-postgres:${DB_SERVER_PORT:-5432}` (shared database server, port configured in database-server/.env)
- **Redis**: `db-server-redis:${REDIS_SERVER_PORT:-6379}` (shared cache, port configured in database-server/.env)
- **Database Name**: `crypto_ai_agent`
- **Infrastructure**: Managed by the centralized `database-server` microservice
- **Connection**: Both blue and green environments use the same shared database instance

#### Database Connection

Both `docker-compose.blue.yml` and `docker-compose.green.yml` are configured to connect to the shared database server:

```yaml
environment:
  # Ports configured in database-server/.env: DB_SERVER_PORT (default: 5432), REDIS_SERVER_PORT (default: 6379)
  - DATABASE_URL=postgresql+psycopg://${POSTGRES_USER:-crypto}:${POSTGRES_PASSWORD:-crypto_pass}@db-server-postgres:${DB_SERVER_PORT:-5432}/${POSTGRES_DB:-crypto_ai_agent}
  - REDIS_URL=redis://db-server-redis:${REDIS_SERVER_PORT:-6379}/0
```

**Important Points:**

- ✅ Both environments use the **same shared database** (zero data loss during deployments)
- ✅ Database hostname is `db-server-postgres` (Docker network hostname)
- ✅ Infrastructure is managed centrally by `database-server` microservice
- ✅ Database is **never stopped** during blue/green deployments
- ✅ Customer data is **always available** in both blue and green environments

#### Infrastructure Management

The shared database server is managed separately from crypto-ai-agent. To manage it:

**Check Database Server Status:**

```bash
cd database-server
./scripts/status.sh
```

**Start Database Server** (if not running):

```bash
cd database-server
./scripts/start.sh
```

**Stop Database Server** (⚠️ Use with caution - affects all services using it):

```bash
cd database-server
./scripts/stop.sh
```

**View Database Server Logs:**

```bash
cd database-server
docker compose logs -f
```

#### Database Backups

**Manual Backup** (using database-server scripts):

```bash
cd database-server
./scripts/backup-database.sh crypto-ai-agent
```

**Backup All Databases:**

```bash
cd database-server
./scripts/backup-all-databases.sh
```

**Automated Backups:**

```bash
cd database-server
./scripts/setup-backup-cron.sh
```

This sets up daily backups at 2:00 AM.

**Manual Backup** (using docker exec directly):

```bash
docker exec db-server-postgres pg_dump -U crypto crypto_ai_agent > backup_$(date +%Y%m%d_%H%M%S).sql
```

**Restore from Backup:**

```bash
cat backup_file.sql | docker exec -i db-server-postgres psql -U crypto crypto_ai_agent
```

#### Verify Database Connection

**From Backend Container:**

```bash
docker exec crypto-ai-backend-green env | grep DATABASE_URL
```

**Test Database Connection:**

```bash
docker exec crypto-ai-backend-green python -c "
import os, psycopg
url = os.getenv('DATABASE_URL', '').replace('+psycopg', '')
conn = psycopg.connect(url)
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM users')
print('Users:', cur.fetchone()[0])
cur.execute('SELECT COUNT(*) FROM portfolio_items')
print('Portfolio Items:', cur.fetchone()[0])
"
```

**List All Databases:**

```bash
cd database-server
./scripts/list-databases.sh
```

Or directly:

```bash
docker exec db-server-postgres psql -U crypto -c "\l"
```

#### Database Safety Features

**Never Create Tables if Database Has Data:**

- The application verifies database connection before creating tables
- If database already has customer data, table creation is **skipped**
- This protects thousands of customer accounts from accidental deletion

**Automatic Retry Logic:**

- Database connections use exponential backoff retry logic
- Startup: 5 retries with 2s initial delay (max 30s)
- Runtime: 3 retries with 0.5s initial delay (max 2s)
- Health checks verify database connectivity before deployment

**Connection Resilience:**

- All database operations use retry logic
- Transient connection failures are automatically retried
- Health endpoints verify database connectivity and data presence

#### Database Schema

The database includes the following tables:

- `users` - User accounts and profiles
- `portfolio_items` - Cryptocurrency portfolio holdings
- `price_alerts` - Price alert configurations
- `alert_history` - Alert trigger history
- `symbols` - Supported cryptocurrency symbols
- `user_api_credentials` - Encrypted user API credentials
- `password_reset_tokens` - Password reset tokens
- And other supporting tables

#### Database Migration Notes

- Database uses shared infrastructure (`db-server-postgres`) from `database-server` microservice
- Infrastructure is managed centrally by the `database-server` service
- All customer data is stored in the shared production database
- **Never migrate from local to production** - production is source of truth
- Blue/green deployments share the same database instance
- Data persistence is guaranteed across deployments
- Database server must be running before blue/green deployments

For more details, see [Database Migration Guide](docs/DATABASE_MIGRATION_COMPLETE.md) and [Production Database Setup](docs/PRODUCTION_DATABASE_SETUP.md).

## Environment Variables

Use `.env` (not committed) and refer to `.env.example` for keys. Important:

- `DOMAIN`: Service domain used by nginx-microservice for auto-registry (required for correct domain detection, default: crypto-ai-agent.alfares.cz)
- `SERVICE_NAME`: Service name identifier (default: crypto-ai-agent)
- `DATABASE_URL`: PostgreSQL connection string
  - Production: `postgresql+psycopg://user:pass@db-server-postgres:5432/crypto_ai_agent`
  - Development: `postgresql+psycopg://crypto:crypto_pass@db-server-postgres:5432/crypto_ai_agent`
- `REDIS_URL`: Redis connection string
  - Production: `redis://db-server-redis:6379/0`
  - Development: `redis://db-server-redis:6379/0`
- `LOGGING_SERVICE_URL`: External logging microservice URL (optional)
  - Production/Docker: `http://logging-microservice:3367`
  - External Access: `https://logging.alfares.cz`
  - If not set, only local file logging is used
- `AUTH_SERVICE_URL`: Auth microservice URL (REQUIRED)
  - Production: `https://auth.alfares.cz`
  - Docker/Development: `http://auth-microservice:3370`
- `BINANCE_API_URL`: Binance API endpoint
- `CORS_ORIGINS`: Allowed CORS origins
- `PRICE_UPDATE_INTERVAL_SECONDS`: Price update interval in seconds (default: 300 = 5 minutes)
- `AI_PREDICTION_INTERVAL_HOURS`: AI prediction generation interval in hours (default: 24 = once per day)
- `AI_PREDICTION_BATCH_SIZE`: Number of symbols to process in batch for AI predictions (default: 1)

**Note**: JWT tokens are managed by auth-microservice. No local `JWT_SECRET` is needed.

## Telegram Notifications Setup

The Crypto AI Agent supports Telegram notifications for price alerts. Here's how to set it up:

### 1. Create a Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` command
3. Follow the instructions to create your bot
4. Save the bot token (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Get Your Chat ID

1. Start a conversation with your bot
2. Send any message to the bot
3. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Find your chat ID in the response (look for `"chat":{"id":123456789`)

### 3. Configure Environment Variables

Add these variables to your `.env` file:

```bash
# Telegram Bot Configuration
TELEGRAM_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### 4. Enhanced Alert Templates

When alerts are triggered, you'll receive rich notifications including:

- **Symbol**: The cryptocurrency symbol (e.g., BTC, ETH)
- **Current Price**: Real-time price when alert triggered
- **Threshold**: The price threshold you set
- **Portfolio Summary**: Your investment details (if you have holdings)
  - Amount of cryptocurrency owned
  - Original investment amount
  - Current value
  - Profit/Loss percentage
- **Custom Message**: Your personal alert message
- **Timestamp**: When the alert was triggered

### 5. Testing Notifications

To test your Telegram setup:

1. Create a price alert in the dashboard
2. Set a threshold that will trigger (e.g., set BTC alert for $1,000,000 if current price is $50,000)
3. The notification will be sent immediately when the condition is met

### Troubleshooting

- **No notifications received**: Check that `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID` are correctly set
- **SSL errors**: The system automatically handles SSL certificate issues in development
- **Bot not responding**: Make sure you've started a conversation with your bot first

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.

## Support

For support and questions:

- Create an issue in the repository
- Check the documentation
