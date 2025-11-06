# Binance Portfolio Import Guide

> 📚 **Documentation Navigation**: [Main README](README.md) | [Current Plan](CURRENT_PLAN.md) | [Technical Implementation](TECHNICAL_IMPLEMENTATION.md)

## Overview

The Binance Portfolio Import feature allows users to automatically import their cryptocurrency holdings from their Binance account into the Crypto AI Agent portfolio management system. This eliminates the need for manual entry and ensures accurate, real-time portfolio tracking.

## Features

- ✅ **Automatic Portfolio Import** - Import all cryptocurrency holdings from Binance
- ✅ **Real-time Price Updates** - Live price tracking for imported assets
- ✅ **Multi-currency Support** - USD, EUR, CZK tracking with automatic conversion
- ✅ **Source Tracking** - Mark assets as imported from "Binance"
- ✅ **Import History** - Track all import operations
- ✅ **Duplicate Prevention** - Avoid importing duplicate assets (same symbol, amount, source)
- ✅ **Secure API Integration** - Read-only access for security
- ✅ **Currency Conversion** - All prices automatically converted to USD using current exchange rates

## Prerequisites

### 1. Binance Account

- Active Binance account with cryptocurrency holdings
- API access enabled

### 2. API Key Setup

- **API Key Type**: System Generated (HMAC)
- **Permissions**: Enable Reading (required)
- **Security**: Keep trading permissions disabled for security

## Setup Instructions

### Step 1: Create Binance API Key

1. **Login to Binance**
   - Go to [Binance API Management](https://www.binance.com/en/my/settings/api-management)

2. **Create New API Key**
   - Click "Create API"
   - Choose "System generated" (HMAC symmetric encryption)
   - Give it a name (e.g., "crypto-ai-agent")

3. **Configure Permissions**
   - ✅ **Enable Reading** (required for portfolio import)
   - ❌ **Enable Spot & Margin Trading** (disabled for security)
   - ❌ **Enable Futures** (disabled for security)
   - ❌ **Enable Withdrawals** (disabled for security)

4. **IP Restrictions** (Optional but Recommended)
   - Choose "Restrict access to trusted IPs only"
   - Add your server's IP address

5. **Save Credentials**
   - Copy the API Key and Secret Key
   - Store them securely

### Step 2: Configure Environment Variables

Update your `.env` file with the new Binance credentials:

```bash
# Binance API Configuration
BINANCE_API_KEY=your_new_api_key_here
BINANCE_API_SECRET=your_new_secret_key_here
BINANCE_API_URL=https://api.binance.com/api/v3
```

### Step 3: Restart Services

```bash
# Stop services
./stop.sh

# Start services with new credentials
./start.sh
```

## Usage

### Method 1: API Endpoints

#### Test Connection

```bash
curl -X POST "http://localhost:8100/api/import/binance/test-connection" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

#### Preview Import

```bash
curl -X POST "http://localhost:8100/api/import/binance/preview" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

#### Execute Import

```bash
curl -X POST "http://localhost:8100/api/import/binance/execute" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

#### View Import History

```bash
curl -X GET "http://localhost:8100/api/import/history" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Method 2: Test Script

Use the provided test script for easy testing:

```bash
python test_binance_import.py
```

## API Response Examples

### Successful Connection Test

```json
{
  "success": true,
  "message": "API connection successful",
  "account_type": "SPOT",
  "can_trade": true,
  "can_withdraw": true,
  "can_deposit": true,
  "balances_count": 724
}
```

### Portfolio Import Preview

```json
{
  "success": true,
  "message": "Successfully prepared 12 portfolio items for import",
  "items_imported": 12,
  "portfolio_items": [
    {
      "symbol": "BTC",
      "amount": 0.02425376,
      "price_buy": 0.0,
      "purchase_date": "2025-10-25T09:52:44.018969Z",
      "base_currency": "USDT",
      "source": "Binance",
      "commission": 0.0,
      "total_investment_text": "Unknown"
    }
  ]
}
```

### Import Execution Result

```json
{
  "success": true,
  "message": "Successfully imported 12 portfolio items from Binance",
  "items_imported": 12,
  "total_found": 12
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

#### BinanceImportService

- **File**: `backend/app/services/binance_import_service.py`
- **Purpose**: Handle Binance API communication and portfolio calculation
- **Key Methods**:
  - `test_api_connection()` - Verify API credentials
  - `get_account_balances()` - Fetch account balances
  - `get_trading_history()` - Get trading history for price calculation
  - `calculate_portfolio_from_balances()` - Convert balances to portfolio items
  - `import_portfolio()` - Complete import process

#### API Endpoints

- **File**: `backend/app/main.py`
- **Endpoints**:
  - `POST /api/import/binance/test-connection` - Test API connection
  - `POST /api/import/binance/preview` - Preview import without saving
  - `POST /api/import/binance/execute` - Execute import and save to database
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

The Binance import automatically converts all prices to USD for consistent tracking across your portfolio.

### How It Works

**Exchange Rate Format:**

- The system uses rates in the format: **1 USD = exchange_rate CZK**
- Example: If CZK rate is 20.94, it means 1 USD = 20.94 CZK

**Conversion Formula:**

- **From non-USD to USD**: `price_buy_usd = price_buy / exchange_rate`
- **From USD to non-USD (for display)**: `price_buy = price_buy_usd * exchange_rate`

**Example:**

- If you bought 1 BTC for 20,940 CZK and exchange rate is 20.94:
  - `price_buy_usd = 20,940 / 20.94 = 1,000 USD`
  - The system stores: `price_buy = 20,940 CZK` and `price_buy_usd = 1,000 USD`

**Important Notes:**

- All prices are stored in USD in the `price_buy_usd` field (required for accurate portfolio calculations)
- The original currency price is preserved in the `price_buy` field for display
- Exchange rates are fetched from the currency service and cached for 30 minutes
- Invalid exchange rates are replaced with 1.0 with a warning

## Troubleshooting

### Common Issues

#### 1. "Signature for this request is not valid"

- **Cause**: Incorrect API secret or timestamp issues
- **Solution**:
  - Verify API secret is correct
  - Check system time synchronization
  - Regenerate API key if needed

#### 2. "Invalid API-key, IP, or permissions"

- **Cause**: API key doesn't have reading permissions
- **Solution**: Enable "Enable Reading" permission in Binance API Management

#### 3. "Binance API is not accessible: 404"

- **Cause**: Incorrect API URL configuration
- **Solution**: Verify `BINANCE_API_URL` is set to `https://api.binance.com/api/v3`

#### 4. "No balances found"

- **Cause**: Account has no cryptocurrency holdings
- **Solution**: Ensure your Binance account has cryptocurrency balances

### Debug Commands

#### Test API Credentials

```bash
python test_binance_direct.py
```

#### Test Import Service

```bash
python test_binance_service.py
```

#### Check Configuration

```bash
cd backend && python -c "
from app.core.config import settings
print(f'API Key: {settings.binance_api_key[:10]}...')
print(f'API Secret: {settings.binance_api_secret[:10]}...')
"
```

## Performance Considerations

### API Rate Limits

- **Binance API**: 1200 requests per minute
- **Account Info**: 1 request per import
- **Trading History**: 1 request per symbol (up to 12 requests)
- **Total**: ~13 requests per import (well within limits)

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
4. Verify Binance account permissions

### Common Solutions

- **API Issues**: Regenerate API key with correct permissions
- **Import Failures**: Check network connection and API limits
- **Data Issues**: Verify Binance account has holdings
- **Performance**: Monitor API rate limits and database performance

---

**Last Updated**: 2025-10-25  
**Version**: 1.0.0  
**Status**: Production Ready

## Related Documentation

- [Main README](README.md) - Complete project overview
- [Current Plan](CURRENT_PLAN.md) - Implementation status
- [Technical Implementation](TECHNICAL_IMPLEMENTATION.md) - Technical details
- [User Management](USER_MANAGEMENT.md) - User authentication system
