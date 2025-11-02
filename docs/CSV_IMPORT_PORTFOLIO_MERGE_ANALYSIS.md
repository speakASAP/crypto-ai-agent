# CSV Import Portfolio Merge Analysis

**Date**: 2025-01-28  
**Status**: 🔴 CRITICAL ISSUES IDENTIFIED  
**User Concern**: CSV import should update existing portfolio items, not create duplicates

## Executive Summary

After analyzing the CSV import codebase and the user's CSV file, **two critical issues** have been identified that prevent correct portfolio updates:

1. **Sell-only transactions are ignored** - CSV containing only sells (ZEN, DASH, IP, HBAR) will be completely skipped
2. **No merge logic with existing portfolio** - System only does INSERT operations, doesn't UPDATE or DELETE existing items

## User Scenario

### Initial State (Last Month's CSV Import)

- User imported portfolio via CSV showing initial holdings
- Example: Had 5 BTC, some ZEN, DASH, IP, HBAR

### Current State (Today's CSV)

```text
ZEN,Sell,7.65152085,405.25 CZK,"3,100.80 CZK",75.00 CZK,"Nov 1, 2025, 4:38:14 PM"
DASH,Sell,2.00002968,"1,483.42 CZK","2,966.89 CZK",59.00 CZK,"Nov 1, 2025, 4:38:59 PM"
IP,Sell,12,93.27 CZK,"1,119.21 CZK",59.00 CZK,"Nov 1, 2025, 4:42:26 PM"
HBAR,Sell,528.49325905,4.15 CZK,"2,195.76 CZK",59.00 CZK,"Nov 1, 2025, 4:43:40 PM"
BTC,Buy,0.00430399,"2,353,779.41 CZK","10,130.66 CZK",150.94 CZK,"Nov 1, 2025, 4:54:09 PM"
```

### Expected Behavior

- ZEN, DASH, IP, HBAR should be **removed from portfolio** (or quantity reduced if user had more)
- BTC should be **added to portfolio** (or quantity increased if BTC already exists)

### Actual Behavior (Current Code)

- ❌ ZEN, DASH, IP, HBAR sells are **completely ignored** (filtered out)
- ❌ BTC buy may create **duplicate entry** or be skipped if exact duplicate exists

## Critical Issues Identified

### Issue #1: Sell-Only Transactions Are Filtered Out

**Location**: `backend/app/services/csv_import_service.py:367-377`

```362:377:backend/app/services/csv_import_service.py
    def _calculate_weighted_average(self, symbol: str, transactions: List[Dict]) -> Optional[Dict]:
        """Calculate weighted average for a symbol's transactions"""
        buy_txns = [t for t in transactions if t['type'].lower() in ['buy', 'purchase']]
        sell_txns = [t for t in transactions if t['type'].lower() in ['sell', 'sale']]
        
        if not buy_txns:
            logger.warning(f"No buy transactions found for {symbol}")
            return None
        
        total_buy_qty = sum(t['quantity'] for t in buy_txns)
        total_sell_qty = sum(t['quantity'] for t in sell_txns)
        net_quantity = total_buy_qty - total_sell_qty
        
        if net_quantity <= 0:
            logger.info(f"Fully sold position for {symbol}, skipping")
            return None
```

**Problem**:

- If CSV contains **only sells** (no buys), line 367-369 returns `None` immediately
- This means sell-only symbols like ZEN, DASH, IP, HBAR in user's CSV will be completely ignored
- Even if user had these coins in portfolio, they won't be removed

**Impact**: HIGH - User's sold positions will remain in portfolio incorrectly

---

### Issue #2: No Merge Logic with Existing Portfolio

**Location**: `backend/app/api/csv_import.py:115-164`

```115:164:backend/app/api/csv_import.py
        for item in aggregated_items:
            try:
                check_duplicate_sql = _normalize_placeholders(
                    "SELECT id FROM portfolio_items WHERE user_id = ? AND symbol = ? AND ABS(amount - ?) < 0.001",
                    is_pg
                )
                cursor.execute(check_duplicate_sql, (current_user["id"], item['symbol'], item['quantity']))
                if cursor.fetchone():
                    logger.info(f"Skipping duplicate: {item['symbol']}")
                    continue

                currency = item.get('currency', 'USD')
                currency_service.ensure_rates_initialized()

                if currency != 'USD':
                    exchange_rate = currency_service.rates.get(currency, 1.0)
                    price_usd = item['price'] / exchange_rate
                    fees_usd = item['fees'] / exchange_rate if item['fees'] > 0 else 0.0
                    value_usd = item.get('value', 0) / exchange_rate if item.get('value', 0) > 0 else 0.0
                else:
                    exchange_rate = None
                    price_usd = item['price']
                    fees_usd = item['fees']
                    value_usd = item.get('value', 0)

                if item.get('value', 0) > 0:
                    total_investment = item['value'] + item['fees']
                else:
                    total_investment = item['quantity'] * item['price'] + item['fees']

                currency_symbols = {'USD': '$', 'EUR': '€', 'CZK': 'Kč', 'GBP': '£', 'JPY': '¥'}
                currency_symbol = currency_symbols.get(currency, currency + ' ')
                total_investment_text = f"{currency_symbol}{total_investment:.2f}"

                insert_sql = _normalize_placeholders(
                    "INSERT INTO portfolio_items "
                    "(user_id, symbol, amount, price_buy, purchase_date, base_currency, source, commission, "
                    "total_investment_text, created_at, updated_at, price_buy_usd, commission_usd, exchange_rate_at_purchase) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    is_pg
                )
                cursor.execute(insert_sql, (
                    current_user["id"], item['symbol'], item['quantity'], item['price'],
                    item['date'], currency, exchange.capitalize(), item['fees'],
                    total_investment_text, now, now, price_usd, fees_usd, exchange_rate,
                ))
                imported_count += 1
            except Exception as e:
                logger.warning(f"Failed to import item {item['symbol']}: {e}")
                continue
```

**Problem**:

1. **Duplicate check is flawed**: Line 117-124 checks if portfolio item exists with **exact same quantity**. This won't work for incremental updates:
   - If user had 5 BTC, and CSV shows 3 BTC net (after sells), it won't be detected as duplicate
   - Creates duplicate entries instead of updating

2. **Only INSERT operations**: Line 149-160 always does INSERT, never UPDATE
   - If BTC already exists in portfolio, CSV import will create a second BTC entry
   - Should merge quantities: `new_quantity = old_quantity + csv_net_quantity`

3. **No DELETE logic**: If a symbol is fully sold (net quantity becomes 0 or negative), it should be removed from portfolio, not ignored

**Impact**: HIGH - Will create duplicate portfolio entries and won't remove sold positions

---

## Detailed Flow Analysis

### Current Flow (Broken)

```text
1. CSV Import → Parse transactions
2. Aggregate transactions by symbol
   - For ZEN (sell-only): No buys found → Returns None ❌
   - For BTC (buy): net_quantity = 0.00430399 → Returns aggregated item ✅
3. For each aggregated item:
   - Check duplicate by exact quantity match (won't match existing 5 BTC)
   - INSERT new portfolio item (creates duplicate BTC) ❌
```

### Expected Flow (Correct)

```text
1. CSV Import → Parse transactions
2. Process ALL transactions (both buys and sells):
   - ZEN: Sell 7.65152085 → Net change: -7.65152085
   - DASH: Sell 2.00002968 → Net change: -2.00002968
   - IP: Sell 12 → Net change: -12
   - HBAR: Sell 528.49325905 → Net change: -528.49325905
   - BTC: Buy 0.00430399 → Net change: +0.00430399
3. For each symbol with net change:
   - Check if exists in portfolio
   - If exists:
     - UPDATE: new_amount = old_amount + net_change
     - If new_amount <= 0: DELETE portfolio item
   - If doesn't exist:
     - If net_change > 0: INSERT new item
     - If net_change < 0: Log warning (selling non-existent position)
```

## Code References

### Key Files

1. **CSV Import Service**: `backend/app/services/csv_import_service.py`
   - `aggregate_transactions()` - Line 332
   - `_calculate_weighted_average()` - Line 362

2. **CSV Import API**: `backend/app/api/csv_import.py`
   - `execute_csv_import()` - Line 75

3. **Portfolio API**: `backend/app/api/portfolio.py`
   - `update_portfolio_item()` - Line 211
   - `delete_portfolio_item()` - Line 350

## Recommendations

### Immediate Fix Required

1. **Fix sell-only transaction handling**:
   - Modify `_calculate_weighted_average()` to return sell transactions even without buys
   - Track net change (positive for buys, negative for sells)
   - Return special flag indicating if this is a sell-only transaction

2. **Implement merge logic in execute_csv_import()**:
   - Query existing portfolio items by symbol (not quantity)
   - For each CSV item:
     - If exists: UPDATE amount, recalculate weighted average price
     - If new_amount <= 0: DELETE item
     - If doesn't exist and net_change > 0: INSERT new item

3. **Handle edge cases**:
   - Selling more than owned (log warning, set to 0)
   - Multiple portfolio items for same symbol (merge or flag)
   - Price calculation for merged positions (weighted average)

### Testing Scenarios

1. ✅ Import CSV with only buys → Should add to portfolio
2. ✅ Import CSV with only sells → Should reduce/remove from portfolio
3. ✅ Import CSV with mixed buys/sells → Should update net quantities correctly
4. ✅ Import CSV for existing symbols → Should merge, not duplicate
5. ✅ Import CSV selling all holdings → Should delete portfolio items

## User Action Required

**DO NOT UPLOAD CSV YET** - The current implementation will not correctly update your portfolio. The system will:

- Ignore your sell transactions (ZEN, DASH, IP, HBAR)
- Possibly create duplicate BTC entries
- Not remove sold positions from portfolio

Wait for the fix to be implemented and tested.

---

**Next Steps**: Fix implementation required before CSV can be safely imported.
