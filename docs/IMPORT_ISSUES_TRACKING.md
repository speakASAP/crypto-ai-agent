# Import Issues & Warnings Tracking

## Overview

All import methods (Binance, Bitfinex, CSV) now ensure that **EVERY cryptocurrency symbol is imported**, with **ZERO TOLERANCE** for missing or invalid `price_buy_usd` values. The system enforces database-level constraints and uses intelligent fallbacks to ensure data integrity. When data is missing or invalid, the system uses fallbacks and tracks all issues for user review.

## Key Principles

1. **Zero Tolerance for Skipping**: No symbol is ever skipped during import
2. **Zero Tolerance for price_buy_usd**: Database enforces `price_buy_usd > 0` with CHECK constraint
3. **Intelligent Fallbacks**: Missing data is replaced with best-available values
4. **Comprehensive Tracking**: All issues and warnings are tracked and displayed
5. **User Notification**: Users are informed about all issues requiring manual attention
6. **Database Constraints**: NOT NULL and CHECK constraints prevent invalid data at database level

## Import Behavior

### All Items Are Imported

- ✅ **Every symbol is imported**, even if data is incomplete
- ✅ Missing prices use current market price as fallback
- ✅ If market price unavailable, uses fallback value **9999999** (huge amount to alert user) with critical warning
- ✅ Missing purchase dates use current date with warning
- ✅ Invalid exchange rates use 1.0 with warning
- ✅ All items are tracked with their issues/warnings
- ✅ **Database enforces price_buy_usd > 0** with CHECK constraint (zero tolerance)

### Issue Categories

#### Critical Issues (Must Fix)

- Missing buy price that couldn't be fetched from market
- Invalid price calculations that required fallback values
- Import failures that prevented item from being saved

#### Warnings (Recommended to Fix)

- Missing buy price that was replaced with current market price
- Missing purchase date that was replaced with current date
- Invalid exchange rate that was replaced with 1.0
- Price calculations that used fallback values

## Import Methods

### Binance Import

**Files**:

- `backend/app/api/exchange_imports.py` (API layer)
- `backend/app/services/binance_import_service.py` (Service layer)

**Behavior**:

- **Service Layer**: NEVER skips any crypto symbol. If no buy trades are found, uses fallback prices (current market price or 9999999) instead of skipping
- **API Layer**: Fetches current market prices for all symbols before import
- Uses market price as fallback if `price_buy` is missing/invalid
- Uses **9999999** (huge amount) as last resort with critical issue tracking - user will immediately notice
- Validates `price_buy_usd > 0` before INSERT with try-catch for database constraint violations
- Tracks all issues and warnings per item (including items from service layer that used fallbacks)
- Returns `items_with_issues` array with detailed information
- **Zero Skip Policy**: Every symbol in account balances is imported, even if no trading history exists

**Response Structure**:

```json
{
  "success": true,
  "items_imported": 10,
  "total_found": 10,
  "items_with_issues": [
    {
      "symbol": "BTC",
      "amount": 0.5,
      "issues": [],
      "warnings": [
        "Missing purchase date - used current date as fallback. Please update with the actual purchase date."
      ],
      "price_buy": 50000.0,
      "price_buy_usd": 50000.0,
      "purchase_date": "2025-11-06T12:00:00"
    }
  ]
}
```

### Bitfinex Import

**Files**:

- `backend/app/api/exchange_imports.py` (API layer)
- `backend/app/services/bitfinex_import_service.py` (Service layer)

**Behavior**: Similar to Binance import

- **Service Layer**: NEVER skips any crypto symbol. If no buy trades are found, uses fallback prices (current market price or 9999999) instead of skipping
- **API Layer**: Fetches current market prices for all symbols before import
- Uses intelligent fallbacks for missing data
- Tracks all issues and warnings (including items from service layer that used fallbacks)
- **Zero Skip Policy**: Every symbol in wallets is imported, even if no trading history exists

### CSV Import

**File**: `backend/app/api/csv_import.py`

**Behavior**:

- Handles both new items and updates to existing items
- For new items: Uses market price fallback if price is missing
- For updates: Preserves existing price if valid, uses fallback if invalid
- Tracks issues separately for inserts and updates
- Never skips any item

**Response Structure**:

```json
{
  "success": true,
  "items_imported": 5,
  "items_updated": 3,
  "items_deleted": 1,
  "items_with_issues": [
    {
      "symbol": "ETH",
      "amount": 2.5,
      "issues": [
        "CRITICAL: Invalid CSV price - using fallback 9999999. MUST be updated manually."
      ],
      "warnings": [],
      "price_buy": 9999999.0,
      "price_buy_usd": 9999999.0,
      "purchase_date": null
    }
  ]
}
```

## Frontend Display

### Issues Dialog

**File**: `frontend/src/app/dashboard/page.tsx`

The dialog displays:

- **Symbol** and **Amount** for each item
- **Current Price** and **Purchase Date** (if available)
- **Critical Issues** (red) - Must be fixed
- **Warnings** (yellow) - Recommended to fix

### User Actions

Users can:

1. View all issues in the popup dialog after import
2. Click on portfolio items to edit them
3. Update prices, dates, and other information manually
4. Fix critical issues immediately for accurate tracking

## Fallback Strategy

### Price Fallbacks (in order of preference)

1. **Original price** from import data (if valid)
2. **Current market price** from multi-exchange price service
3. **Fallback value 9999999** (huge amount to alert user - with critical issue tracking)

**Note**: The fallback value 9999999 is intentionally large so users will immediately notice and fix the issue. This ensures zero tolerance for invalid prices.

### Date Fallbacks

1. **Original purchase date** from import data
2. **Current date** (with warning)

### Exchange Rate Fallbacks

1. **Stored exchange rate** from existing item (for updates)
2. **Current exchange rate** from currency service
3. **1.0** (with warning)

## Issue Tracking Structure

Each item in `items_with_issues` contains:

```typescript
{
  symbol: string;           // Cryptocurrency symbol
  amount: number;           // Amount imported
  issues: string[];         // Critical issues (must fix)
  warnings: string[];       // Warnings (recommended to fix)
  price_buy?: number;       // Price used (for reference)
  price_buy_usd?: number;   // USD price used (for reference)
  purchase_date?: string;  // Purchase date used (for reference)
}
```

## Examples

### Example 1: Missing Price (Market Price Available)

```json
{
  "symbol": "BTC",
  "amount": 0.1,
  "issues": [],
  "warnings": [
    "Missing buy price - used current market price ($50,000.00) as fallback. Please verify and update manually."
  ],
  "price_buy": 50000.0,
  "price_buy_usd": 50000.0,
  "purchase_date": "2025-11-06T12:00:00"
}
```

### Example 2: Missing Price (No Market Price Available)

```json
{
  "symbol": "OBSCURE",
  "amount": 1000.0,
  "issues": [
    "CRITICAL: Missing buy price - could not fetch current market price. Using fallback 9999999. MUST be updated manually."
  ],
  "warnings": [],
  "price_buy": 9999999.0,
  "price_buy_usd": 9999999.0,
  "purchase_date": "2025-11-06T12:00:00"
}
```

### Example 3: Multiple Issues

```json
{
  "symbol": "ETH",
  "amount": 5.0,
  "issues": [
    "CRITICAL: Could not determine price - using fallback 9999999. MUST be updated manually."
  ],
  "warnings": [
    "Missing purchase date - used current date as fallback. Please update with the actual purchase date.",
    "Invalid exchange rate for EUR - used 1.0. Price conversion may be inaccurate."
  ],
  "price_buy": 9999999.0,
  "price_buy_usd": 9999999.0,
  "purchase_date": "2025-11-06T12:00:00"
}
```

## Database Constraints

The system enforces zero tolerance for invalid `price_buy_usd` values at the database level:

- **NOT NULL constraint**: `price_buy_usd` cannot be NULL
- **CHECK constraint**: `price_buy_usd > 0` (must be positive)
- **CHECK constraint**: `commission_usd >= 0` (must be non-negative)

These constraints are automatically applied on startup via `ensure_price_buy_usd_mandatory()` function in `backend/app/core/database.py`.

Any attempt to insert or update with invalid `price_buy_usd` will be caught and handled gracefully with user-friendly error messages.

## Benefits

✅ **Complete Import**: Every symbol is imported, nothing is lost
✅ **Data Integrity**: Database constraints prevent invalid data
✅ **Zero Tolerance**: Invalid prices are caught at multiple levels (validation, database)
✅ **User Awareness**: Huge fallback value (9999999) ensures users notice issues immediately
✅ **Actionable Information**: Users know exactly what needs to be fixed
✅ **Prioritized Issues**: Critical issues vs warnings help users prioritize

## Migration Notes

- Old `items_with_missing_data` field is replaced with `items_with_issues`
- Frontend dialog updated to show issues and warnings separately
- All imports now use the same issue tracking structure
- Backward compatibility: Frontend handles both old and new formats

## Testing

After deployment, verify:

1. **Import with missing prices**: Should import all items with fallback prices (9999999 if market price unavailable)
2. **Import with missing dates**: Should import all items with current date
3. **Import with invalid data**: Should import all items with fallback values (9999999)
4. **Dialog display**: Should show all issues and warnings clearly
5. **No skipped items**: Every symbol should appear in portfolio
6. **Database constraints**: Verify CHECK constraints are active (try inserting price_buy_usd = 0 or NULL - should fail)
7. **Validation**: All imports validate price_buy_usd > 0 before database operations
8. **Error handling**: Database constraint violations are caught and reported to users
