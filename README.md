# 🤖 Crypto AI Agent with Portfolio Dashboard

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue.svg)](https://docker.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-UI-red.svg)](https://streamlit.io)
[![Binance](https://img.shields.io/badge/Binance-API-yellow.svg)](https://binance.com)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-blue.svg)](https://telegram.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 📋 Project Description

**Crypto AI Agent** — a powerful asynchronous agent for cryptocurrency monitoring and Telegram notifications. The project includes a **Streamlit UI dashboard** where you can manage your multi-currency portfolio (USD, EUR, CZK).

### 🚀 Key Features

- 🔄 **Asynchronous price monitoring** multi-asset via Binance WebSocket
- 📰 **Free sentiment analysis** using TextBlob (no paid APIs)
- 📱 **Telegram notifications** when upper or lower levels are reached
- 🔔 **Price alerts** with customizable thresholds and custom messages
- 💱 **Multi-currency portfolio tracking** with USD, EUR, and CZK support
- 🔄 **Real-time currency conversion** with live exchange rates and caching
- 📅 **Purchase date tracking** for complete transaction history
- 🏪 **Source tracking** - track where each asset was bought (Binance, Coinbase, Revolut, etc.)
- 🗄️ **SQLite database** for storing portfolio and alerts
- 🎛️ **UI dashboard** for portfolio management and alerts
- 🐳 **Docker Compose** for easy deployment in development and production
- 💰 **Completely FREE** - no paid AI models or APIs required

## 🏗️ Project Architecture

### Components

1. Async WebSocket Manager

- Receives prices for all coins in the portfolio.
- Asynchronous processing with minimal delay.



1. SQLite Database

- Tables: candles, portfolio, price_alerts.
- Storage of price data and portfolio composition.

1. Async Telegram Alert Manager

- Sending notifications for each coin in the portfolio.

1. UI Dashboard (Streamlit / FastAPI + React)

- Portfolio input: adding/removing coins, quantity, purchase price.
- Viewing current prices and portfolio analytics.

1. Docker Compose

- Agent + UI in separate services.
- SQLite accessible via volume for saving history and portfolio.

## 📁 Project Structure

```text
crypto-ai-agent/
├── 📄 docker-compose.yml
├── 🐳 Dockerfile.agent
├── 🐳 Dockerfile.ui
├── 📦 requirements-agent.txt
├── 📦 requirements-ui.txt
├── 🤖 agent_advanced.py
├── 📖 README.md
├── 🔐 .env.example
├── 📁 ui_dashboard/
│   ├── 🎛️ app.py
│   ├── 📁 components/
│   └── 📁 static/
└── 📁 data/
```

> 📝 **Note**: The `data` folder is created empty and will contain the SQLite database `crypto_history.db` after the first run.

agent_advanced.py — main AI agent with environment variable support and dynamic symbol management.
ui_dashboard/app.py — Streamlit UI for portfolio, signals and symbol management.
requirements-agent.txt / requirements-ui.txt — dependencies including python-dotenv.
docker-compose.yml — configuration for running agent + UI with environment variables.
Dockerfile.agent → agent with WebSocket monitoring.
Dockerfile.ui → UI dashboard on Streamlit with configurable port.
.env.example → template for environment variables configuration.
data/crypto_history.db → SQLite database with history, portfolio, signals and tracked symbols (created automatically on first run).

## 🗃️ SQLite Tables

### 1. 📊 `portfolio`

Storing user portfolio with multi-currency support.

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | TEXT | Cryptocurrency symbol (e.g., BTC) |
| `amount` | REAL | Number of coins |
| `price_buy` | REAL | Purchase price in original currency |
| `purchase_date` | DATETIME | Date when coins were purchased |
| `base_currency` | TEXT | Currency used for purchase (USD/EUR/CZK) |
| `purchase_price_eur` | REAL | Purchase price converted to EUR |
| `purchase_price_czk` | REAL | Purchase price converted to CZK |
| `source` | TEXT | Where the asset was bought (Binance, Coinbase, etc.) |

### 2. 🕯️ `candles`

Storing price history (candles).

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | TEXT | Cryptocurrency symbol |
| `price` | REAL | Price at the time of recording |
| `timestamp` | DATETIME | Recording time (default CURRENT_TIMESTAMP) |


### 3. 🎯 `tracked_symbols`

Storing tracked cryptocurrency symbols.

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | TEXT | Cryptocurrency symbol (PRIMARY KEY) |
| `is_active` | INTEGER | Whether symbol is actively tracked (1=active, 0=inactive) |
| `created_at` | DATETIME | When symbol was added to tracking |

### 4. 🔔 `price_alerts`

Storing user-defined price alerts with custom thresholds and messages.

| Field | Type | Description |
|-------|------|-------------|
| `id` | INTEGER | Primary key (auto-increment) |
| `symbol` | TEXT | Cryptocurrency symbol |
| `alert_type` | TEXT | Alert type (ABOVE or BELOW) |
| `threshold_price` | REAL | Price threshold for alert |
| `message` | TEXT | Custom message for when alert triggers |
| `is_active` | INTEGER | Whether alert is active (1=active, 0=inactive) |
| `created_at` | DATETIME | When alert was created |
| `updated_at` | DATETIME | When alert was last updated |

### 5. 📊 `alert_history`

Storing history of triggered alerts.

| Field | Type | Description |
|-------|------|-------------|
| `id` | INTEGER | Primary key (auto-increment) |
| `alert_id` | INTEGER | Reference to price_alerts table |
| `symbol` | TEXT | Cryptocurrency symbol |
| `triggered_price` | REAL | Price when alert was triggered |
| `threshold_price` | REAL | Original threshold price |
| `alert_type` | TEXT | Alert type (ABOVE or BELOW) |
| `message` | TEXT | Alert message that was sent |
| `triggered_at` | DATETIME | When alert was triggered |

### 6. 💱 `currency_rates`

Storing currency exchange rates for multi-currency support.

| Field | Type | Description |
|-------|------|-------------|
| `id` | INTEGER | Primary key (auto-increment) |
| `from_currency` | TEXT | Source currency (e.g., USD) |
| `to_currency` | TEXT | Target currency (e.g., EUR, CZK) |
| `rate` | REAL | Exchange rate from source to target |
| `timestamp` | DATETIME | When rate was fetched (default CURRENT_TIMESTAMP) |

## ⚙️ Environment Variables Setup

The project uses environment variables for configuration. Copy the example file and configure your settings:

```bash
```

**Important**: Use the following commands to view the current environment variables:

```bash
# View current environment variables (contains actual values)
cat .env

# View environment variables template (safe to share)
cat .env.example
```

Then edit the `.env` file with your actual API keys and configuration:

```bash
# View the complete environment variables template
cat .env.example

# View your current environment variables (contains actual values)
cat .env
```

**Note**: All configuration values are now managed through environment variables. The `.env.example` file contains the complete template with all available configuration options. Copy it to `.env` and fill in your actual values.

### 🔧 Environment Variable Management

The project uses a comprehensive environment variable system for all configuration. Here are the key commands:

```bash
# View all available environment variables (safe to share)
cat .env.example

# View your current configuration (contains actual values)
cat .env

# Edit your environment variables
nano .env  # or use your preferred editor
```

**Important Security Notes:**

- Never commit the `.env` file to version control
- The `.env.example` file is safe to share and contains only template values
- All sensitive data (API keys, secrets) should only be in your local `.env` file

### 🔑 Getting API Keys

1. **Binance API**: [binance.com](https://binance.com) → Account → API Management
2. **Telegram Bot**: [@BotFather](https://t.me/botfather) → `/newbot`

## 🚀 Installation and Launch

### 1️⃣ Clone the project

```bash
git clone https://github.com/yourusername/crypto-ai-agent.git
cd crypto-ai-agent
```

### 2️⃣ Configure environment variables

```bash
# Edit .env file with your actual API keys

# View current environment variables
cat .env

# View environment variables template
cat .env.example
```

### 3️⃣ Create database directory

```bash
mkdir data
```

### 4️⃣ Run via Docker Compose

```bash
docker-compose up --build
```

### 5️⃣ Check operation

- 🤖 **AI agent** monitors prices, predicts and sends Telegram notifications
- 🎛️ **UI dashboard** available at: [http://localhost:8501](http://localhost:8501)

## 🎛️ Using the UI Dashboard

### 💼 Portfolio Management

- ➕ **Adding/editing coins**: symbol, quantity, purchase price, purchase date, currency, source
- 👀 **Viewing current coins** in portfolio with multi-currency support
- 💱 **Multi-currency tracking**: USD, EUR, and CZK support
- 📅 **Purchase date tracking**: Complete transaction history
- 🏪 **Source tracking**: Track where each asset was purchased
- 🔄 **Real-time currency conversion**: Live exchange rates with caching
- 📊 **Multi-currency analytics**: Performance metrics in all supported currencies


### 🎯 Symbol Management (NEW!)

- ➕ **Add new symbols** for tracking via sidebar
- ❌ **Remove symbols** from active tracking
- 🔄 **Restore inactive symbols** back to tracking
- 📊 **Manage symbol tracking** with add/remove/restore functionality
- ⚡ **Real-time updates** - changes apply within 30 seconds



### 🔔 Price Alerts (NEW!)

- 🎯 **Custom price thresholds** for any tracked cryptocurrency
- 📱 **Telegram notifications** when price targets are reached
- 💬 **Custom messages** for each alert with actionable instructions
- 📊 **Alert management** with create, edit, delete, and toggle functionality
- 📈 **Alert history** tracking all triggered alerts
- 🎛️ **Portfolio alerts** tab for managing alerts on your holdings
- ⚡ **Real-time monitoring** with instant notifications
- 📊 **Alert statistics** showing performance and trigger rates


### ➕ Adding a coin to portfolio

1. Enter symbol (e.g., `BTC`)
2. Specify quantity and purchase price
3. Select purchase currency (USD, EUR, or CZK)
4. Choose purchase date
5. Select source (Binance, Coinbase, Revolut, etc.)
6. Click **Add / Update Coin**
7. Coin will be saved to database and tracked by agent

### 💱 Multi-Currency Portfolio Features

#### Currency Support

- **USD (US Dollar)**: Default base currency
- **EUR (Euro)**: European currency support
- **CZK (Czech Koruna)**: Czech currency support

#### Real-Time Currency Conversion

- **Live Exchange Rates**: Automatic fetching from external API
- **30-Minute Caching**: Optimized performance with rate caching
- **Fallback Rates**: Offline operation with predefined rates
- **Multi-Currency Display**: View portfolio in any supported currency

#### Enhanced Portfolio Tracking

- **Purchase Date**: Complete transaction history
- **Original Currency**: Track which currency was used for purchase
- **Multi-Currency P&L**: Calculate profits/losses in any currency
- **Currency-Specific Analytics**: Performance metrics by currency

#### Portfolio Management Interface

- **Currency Selector**: Choose display currency (USD/EUR/CZK)
- **Multi-Currency Tabs**: Organized portfolio management
- **Purchase History**: Complete transaction timeline
- **Real-Time Rates Display**: Current exchange rates

### 💱 Using Multi-Currency Features

#### Adding Coins with Currency Support

1. Navigate to **Portfolio Management** → **➕ Add Coin** tab
2. Enter cryptocurrency symbol (e.g., `BTC`)
3. Specify amount of coins
4. Select **Purchase Currency** (USD, EUR, or CZK)
5. Enter purchase price in selected currency
6. Choose purchase date
7. Select **Source** (Binance, Coinbase, Revolut, etc.)
8. Click **Add to Portfolio**

#### Viewing Portfolio in Different Currencies

1. Use **Currency Selector** to choose display currency
2. Portfolio values automatically convert to selected currency
3. P&L calculations update in real-time
4. View **Real-Time Rates** to see current exchange rates

#### Multi-Currency Analytics

- **Performance by Currency**: See how each currency performs
- **Currency-Specific P&L**: Calculate profits/losses in any currency
- **Purchase History**: Complete timeline of all transactions
- **Real-Time Conversion**: Live currency conversion rates

### 🎯 Managing tracked symbols

1. Use the sidebar **Symbol Management** section
2. **Add**: Enter symbol and click "Add Symbol"
3. **Remove**: Click "Remove" next to active symbols
4. **Restore**: Click "Restore" next to inactive symbols
5. Changes are automatically applied to the agent



### 🔔 Using Price Alerts

#### Main Dashboard Price Alerts

1. Navigate to the **Price Alerts** section
2. **Create New Alert**: Click "Create Alert" and fill in:
   - **Symbol**: Choose from tracked cryptocurrencies
   - **Alert Type**: Above or Below threshold
   - **Threshold Price**: Set your target price
   - **Message**: Custom message for when alert triggers
   - **Active**: Enable/disable the alert
3. **Manage Alerts**: Edit, delete, or toggle existing alerts
4. **View History**: See all triggered alerts with details

#### Portfolio Price Alerts

1. Go to **Portfolio Management** → **🔔 Price Alerts** tab
2. **Portfolio Alerts**: Manage alerts specifically for your holdings
3. **Quick Actions**: Create alerts based on current portfolio prices
4. **Alert Statistics**: View performance metrics for your alerts

#### Alert Features

- **Custom Messages**: Add actionable instructions for each alert
- **Real-time Monitoring**: Alerts checked with every price update
- **Telegram Notifications**: Instant notifications when alerts trigger
- **Alert History**: Complete log of all triggered alerts
- **Statistics**: Track alert performance and trigger rates
- **One-time Alerts**: Alerts automatically deactivate after triggering

## ⚙️ Agent Configuration

### Adding new coins for tracking

#### Method 1: Via UI Dashboard (Recommended)

- Use the sidebar **Symbol Management** section in the UI
- Add/remove symbols in real-time without restarting the agent

#### Method 2: Via Environment Variables

To set default symbols, edit the `SYMBOLS` variable in your `.env` file:

```bash
SYMBOLS=BTC,SOL,DOT
```

#### Method 3: Direct Database Access

You can also manage symbols directly in the database:

```sql
-- Add a new symbol
INSERT INTO tracked_symbols (symbol) VALUES ('SOL');

-- Remove a symbol (set inactive)
UPDATE tracked_symbols SET is_active = 0 WHERE symbol = 'ADA';

-- Restore a symbol
UPDATE tracked_symbols SET is_active = 1 WHERE symbol = 'ADA';
```

### Configurable parameters

All agent parameters can be configured in the `.env` file. Use the following commands to view all available configuration options:

```bash
# View all available environment variables with descriptions
cat .env.example

# View your current configuration
cat .env
```

**Key Configuration Variables:**

- `PREDICTION_CACHE_TIME` - Prediction cache time in seconds (default: 10)
- `MAX_PRICE_HISTORY` - Maximum price history to keep (default: 200)
- `BINANCE_API_URL` - Binance API endpoint (default: <https://api.binance.com/api/v3/ticker/price>)
- `CURRENCY_API_URL` - Currency exchange rate API (default: <https://api.exchangerate-api.com/v4/latest/USD>)

## 💡 Recommendations

- 🏭 **For production** use a separate server and `restart: unless-stopped` in Docker Compose
- 🔧 **Environment variables** make configuration easy and secure - use `cat .env` and `cat .env.example` to manage settings
- ⚡ **Dynamic symbol management** - add/remove coins without restarting the agent
- 🎯 **Use UI dashboard** for real-time symbol management instead of editing config files
- 📋 **Configuration management** - all settings are externalized to environment variables for flexibility

## 📊 Centralized Logging System

The project includes a comprehensive logging system that documents every step of the application:

### 🔍 **Logging Features**

- **Centralized logging** across all modules (agent, UI, tests)
- **Multiple log levels** (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **Structured logging** with context and parameters
- **Performance monitoring** with execution time tracking
- **User action tracking** for audit trails
- **API call logging** with status codes and response times
- **Database operation logging** with query details
- **Error tracking** with full stack traces

### 📁 **Log Files**

- **Main log**: `logs/crypto_agent.log`
- **Automatic rotation** for production environments
- **Configurable log levels** via environment variables
- **Real-time monitoring** of critical events

### 🎯 **What Gets Logged**

- ✅ **System startup/shutdown** events
- ✅ **Database operations** (queries, connections, errors)
- ✅ **API calls** (Binance, Telegram)
- ✅ **User actions** (portfolio changes, symbol management)
- ✅ **Performance metrics** (execution times, response times)
- ✅ **Error handling** (exceptions, recovery attempts)
- ✅ **Function entry/exit** with parameters (DEBUG mode)

### ⚙️ **Logging Configuration**

```bash
# Logging Configuration
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE=logs/crypto_agent.log    # Path to log file
LOG_FORMAT="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

For detailed logging configuration, see [LOGGING_CONFIG.md](LOGGING_CONFIG.md).

## 📈 Scaling

- ➕ **Adding new coins** doesn't require UI restart
- 🔌 **WebSocket agent** handles dozens of coins simultaneously
- 💾 **Candle history and portfolio** stored in SQLite
- ⚡ **Dynamic symbol management** - add/remove symbols without agent restart
- 🎯 **Database-driven configuration** - all tracking managed via database
- 🔄 **Auto-reload** - agent checks for symbol changes every 30 seconds
- 📊 **Comprehensive logging** - every step documented for monitoring and debugging

## 🚀 Future Improvements

- ✅ **Price alerts** with customizable thresholds and custom messages - **IMPLEMENTED!**
- 📄 **Portfolio and signals export** to CSV
- ⚡ **UI on FastAPI + React** for interactive interface
- 📊 **Advanced technical indicators** (RSI, MACD, Bollinger Bands)
- 📱 **Mobile app** for on-the-go monitoring

## 📚 Documentation

### 📋 Project Documentation

- **[CURRENT_PLAN.md](CURRENT_PLAN.md)** - Current implementation status and completed features
- **[LOGGING_CONFIG.md](LOGGING_CONFIG.md)** - Comprehensive logging system configuration and usage
- **[PRICE_ALERTS_PLAN.md](PRICE_ALERTS_PLAN.md)** - Price alerts system implementation plan
- **[crypto-ai-agent/README.md](crypto-ai-agent/README.md)** - Subproject documentation and setup

### 🎯 Quick Navigation

- **Getting Started**: See [Installation and Launch](#-installation-and-launch) section
- **Configuration**: See [Environment Variables Setup](#️-environment-variables-setup) section
- **UI Dashboard**: See [Using the UI Dashboard](#️-using-the-ui-dashboard) section
- **Logging**: See [Centralized Logging System](#-centralized-logging-system) section
- **Implementation Status**: See [CURRENT_PLAN.md](CURRENT_PLAN.md) for completed features
- **Technical Details**: See [LOGGING_CONFIG.md](LOGGING_CONFIG.md) for logging configuration

## 📄 License

This project is distributed under the MIT license. See the [LICENSE](LICENSE) file for details.

## 👥 Contacts

- 📧 **Email**: <ssfskype@gmail.com>
- 🐙 **GitHub**: [@yourusername](https://github.com/SpeakASAP)
- 💬 **Telegram**: [@yourusername](https://t.me/sergej_partizan)

---
