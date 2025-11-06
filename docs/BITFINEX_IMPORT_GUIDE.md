# Bitfinex Portfolio Import Guide

> 📚 **Documentation Navigation**: [Main README](README.md) | [Current Plan](CURRENT_PLAN.md) | [Technical Implementation](TECHNICAL_IMPLEMENTATION.md)

## Overview

The Bitfinex Portfolio Import feature allows users to automatically import their cryptocurrency holdings from their Bitfinex account into the Crypto AI Agent portfolio management system. This eliminates the need for manual entry and ensures accurate, real-time portfolio tracking.

## Features

- ✅ **Automatic Portfolio Import** - Import all cryptocurrency holdings from Bitfinex
- ✅ **Real-time Price Updates** - Live price tracking for imported assets
- ✅ **Multi-currency Support** - USD, EUR, CZK tracking with automatic conversion
- ✅ **Source Tracking** - Mark assets as imported from "Bitfinex"
- ✅ **Import History** - Track all import operations
- ✅ **Duplicate Prevention** - Avoid importing duplicate assets (same symbol, amount, source)
- ✅ **Secure API Integration** - Read-only access for security
- ✅ **Currency Conversion** - All prices automatically converted to USD using current exchange rates

## Prerequisites

### 1. Bitfinex Account

- Active Bitfinex account with cryptocurrency holdings
- API access enabled

### 2. API Key Setup

- **API Key Type**: User-generated
- **Permissions**: Enable Account Info, Account History, and Wallets
- **Security**: Keep trading and withdrawal permissions disabled for security

## Setup Instructions

### Step 1: Create Bitfinex API Key

1. **Login to Bitfinex**
   - Go to [Bitfinex Account](https://www.bitfinex.com/)
   - Click on your profile icon in the upper-right corner
   - Select "API Keys" from the dropdown menu

2. **Create New API Key**
   - Click on the "Create New Key" tab
   - Assign a label (e.g., "Crypto AI Agent")
   - Complete 2FA verification
   - Check your email for a confirmation link
   - Click the confirmation link in your email

3. **Configure Permissions**
   - ✅ **Enable Account Info** (required for account verification)
   - ✅ **Enable Account History** (required for trade history)
   - ✅ **Enable Wallets** (required for portfolio import)
   - ❌ **Disable Orders** (for security)
   - ❌ **Disable Withdrawals** (for security)

4. **IP Restrictions** (Optional but Recommended)
   - Choose "Restrict access to trusted IPs only"
   - Add your server's IP address

5. **Save Credentials**
   - Copy the API Key and Secret Key
   - Store them securely

### Step 2: Configure in Profile Settings

1. **Go to Profile Settings**
   - Click on your profile menu → Settings
   - Navigate to "Bitfinex Settings" tab

2. **Enter Credentials**
   - Paste your Bitfinex API Key
   - Paste your Bitfinex API Secret
   - Click "Save Bitfinex Credentials"

3. **Test Connection**
   - Click "Test Connection" to verify credentials
   - You should see account info if successful

### Step 3: Restart Services

```bash
# Stop services
./stop.sh

# Start services
./start.sh
```

## Usage

### Method 1: API Endpoints

#### Test Connection

```bash
curl -X POST "http://localhost:8100/api/import/bitfinex/test-connection" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

#### Preview Import

```bash
curl -X POST "http://localhost:8100/api/import/bitfinex/preview" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

#### Execute Import

```bash
curl -X POST "http://localhost:8100/api/import/bitfinex/execute" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

#### View Import History

```bash
curl -X GET "http://localhost:8100/api/import/history" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Method 2: Web Interface

1. **Go to Dashboard**
   - Navigate to the main dashboard

2. **Click Import Button**
   - Click "📥 Import from Bitfinex" button
   - Confirm the import action

3. **Wait for Import**
   - The system will fetch your Bitfinex wallets
   - Import progress will be displayed
   - You'll see a success message when complete

## API Response Examples

### Successful Connection Test

```json
{
  "success": true,
  "message": "API connection successful",
  "account_info": {
    "id": 12345,
    "email": "user@example.com"
  }
}
```

### Portfolio Import Preview

```json
{
  "success": true,
  "message": "Successfully prepared 8 portfolio items for import",
  "items_imported": 8,
  "portfolio_items": [
    {
      "symbol": "BTC",
      "amount": 0.5,
      "price_buy": 45000.0,
      "purchase_date": "2025-01-15T10:30:00Z",
      "base_currency": "USD",
      "source": "Bitfinex",
      "commission": 0.0,
      "total_investment_text": "$22500.00"
    }
  ]
}
```

### Import Execution Result

```json
{
  "success": true,
  "message": "Successfully imported 8 portfolio items from Bitfinex",
  "items_imported": 8,
  "total_found": 8
}
```

## Technical Implementation

### Database Schema

#### Import History Table

```sql
CREATE TABLE import_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    source TEXT NOT NULL,
    import_date TEXT NOT NULL,
    items_imported INTEGER NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id)
);
```

#### Portfolio Items Table

```sql
CREATE TABLE portfolio_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    amount REAL NOT NULL,
    price_buy REAL NOT NULL,
    purchase_date TEXT,
    base_currency TEXT NOT NULL,
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
);
```

### Service Architecture

#### BitfinexImportService

- **File**: `backend/app/services/bitfinex_import_service.py`
- **Purpose**: Handle Bitfinex API communication and portfolio calculation
- **Key Methods**:
  - `test_api_connection()` - Verify API credentials
  - `get_wallets()` - Fetch account wallets
  - `get_trades(symbol)` - Get trading history for price calculation
  - `calculate_portfolio_from_wallets()` - Convert wallets to portfolio items
  - `import_portfolio()` - Complete import process

#### API Endpoints

- **File**: `backend/app/main.py`
- **Endpoints**:
  - `POST /api/import/bitfinex/test-connection` - Test API connection
  - `POST /api/import/bitfinex/preview` - Preview import without saving
  - `POST /api/import/bitfinex/execute` - Execute import and save to database
  - `GET /api/import/history` - Get import history

### Security Features

1. **Read-Only Access** - Only reading permissions enabled
2. **No Trading Access** - Cannot execute trades or withdrawals
3. **User Isolation** - Each user's data is completely separate
4. **API Key Encryption** - Credentials stored securely
5. **Duplicate Prevention** - Avoid importing duplicate assets

## Zero Tolerance Policy for price_buy_usd

The system enforces **zero tolerance** for missing or invalid `price_buy_usd` values:

- **Database Constraints**: The database enforces `price_buy_usd > 0` with CHECK constraint
- **Validation**: All imports validate `price_buy_usd > 0` before database operations
- **Fallback Strategy**: If price cannot be determined:
  1. First tries current market price
  2. If unavailable, uses **9999999** (huge amount) to alert user
- **User Notification**: All issues are shown in popup dialog after import
- **No Skipping**: Every symbol is imported, even if price data is missing

**Important**: If you see a price of 9999999, this indicates missing price data. You must update it manually with the correct purchase price.

For more details, see [Import Issues Tracking](IMPORT_ISSUES_TRACKING.md).

## Currency Conversion

The Bitfinex import automatically converts all prices to USD for consistent tracking across your portfolio.

### How It Works

**Exchange Rate Format:**

- The system uses rates in the format: **1 USD = exchange_rate CZK**
- Example: If CZK rate is 20.94, it means 1 USD = 20.94 CZK

**Conversion Formula:**

- **From non-USD to USD**: `price_buy_usd = price_buy / exchange_rate`
- **From USD to non-USD (for display)**: `price_buy = price_buy_usd * exchange_rate`

**Example:**

- If you bought 1 ETH for 1,700 EUR and exchange rate is 0.85:
  - `price_buy_usd = 1,700 / 0.85 = 2,000 USD`
  - The system stores: `price_buy = 1,700 EUR` and `price_buy_usd = 2,000 USD`

**Important Notes:**

- All prices are stored in USD in the `price_buy_usd` field (required for accurate portfolio calculations)
- The original currency price is preserved in the `price_buy` field for display
- Exchange rates are fetched from the currency service and cached for 30 minutes
- Invalid exchange rates are replaced with 1.0 with a warning

## Troubleshooting

### Common Issues

#### 1. "Invalid API-key"

- **Cause**: Incorrect API key or missing permissions
- **Solution**:
  - Verify API key is correct
  - Check that required permissions are enabled (Account Info, Account History, Wallets)

#### 2. "Signature validation failed"

- **Cause**: Incorrect API secret or timestamp issues
- **Solution**:
  - Verify API secret is correct
  - Check system time synchronization
  - Regenerate API key if needed

#### 3. "Bitfinex API error: 404"

- **Cause**: Incorrect API endpoint
- **Solution**: Verify you're using the correct Bitfinex API endpoint

#### 4. "No wallets found"

- **Cause**: Account has no cryptocurrency holdings or wallets not accessible
- **Solution**:
  - Ensure your Bitfinex account has cryptocurrency balances
  - Verify "Wallets" permission is enabled

### Debug Commands

#### Test API Credentials

```bash
curl -X POST "http://localhost:8100/api/auth/test-bitfinex-connection" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

#### Check Configuration

```bash
# Access backend console
cd backend && python
>>> from app.services.bitfinex_import_service import BitfinexImportService
>>> # Test service
```

## Performance Considerations

### API Rate Limits

- **Bitfinex API**: 30 requests per minute
- **Account Info**: 1 request per import
- **Wallets**: 1 request per import
- **Trading History**: 1 request per symbol (up to 8 requests)
- **Total**: ~10 requests per import (well within limits)

### Caching

- **Exchange Rates**: 30-minute cache
- **Price Data**: Real-time updates
- **Portfolio Data**: Cached in database

### Database Performance

- **Indexes**: Optimized for user_id and symbol lookups
- **Duplicate Detection**: Efficient similarity matching
- **Batch Operations**: Single transaction for all imports

## Monitoring and Logging

### Log Files

- **Backend Logs**: `logs/backend.log`
- **Import Operations**: Logged with detailed information
- **Error Tracking**: Comprehensive error logging

### Key Metrics to Monitor

- Import success rate
- API response times
- Database operation performance
- Error frequency and types

## Future Enhancements

### Planned Features

1. **Trading History Integration** - Calculate accurate buy prices
2. **Automatic Re-import** - Scheduled portfolio updates
3. **Multi-Exchange Support** - Import from other exchanges
4. **CSV Export** - Export portfolio data
5. **Price Alert Integration** - Set alerts during import

### API Improvements

1. **Pagination Support** - Handle large portfolios
2. **Incremental Updates** - Only import changes
3. **Error Recovery** - Retry failed imports
4. **Progress Tracking** - Real-time import progress

## Support

### Getting Help

1. Check the troubleshooting section
2. Review backend logs for errors
3. Test API credentials independently
4. Verify Bitfinex account permissions

### Common Solutions

- **API Issues**: Regenerate API key with correct permissions
- **Import Failures**: Check network connection and API limits
- **Data Issues**: Verify Bitfinex account has holdings
- **Performance**: Monitor API rate limits and database performance

---

**Last Updated**: 2025-01-25  
**Version**: 1.0.0  
**Status**: Production Ready

## Related Documentation

- [Main README](README.md) - Complete project overview
- [Current Plan](CURRENT_PLAN.md) - Implementation status
- [Technical Implementation](TECHNICAL_IMPLEMENTATION.md) - Technical details
- [User Management](USER_MANAGEMENT.md) - User authentication system
- [Binance Import Guide](BINANCE_IMPORT_GUIDE.md) - Binance import documentation
