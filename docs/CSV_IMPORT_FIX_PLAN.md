# CSV Import Portfolio Merge Fix Plan

**Date**: 2025-01-28  
**Status**: ✅ Implementation Complete - Ready for Testing  
**Priority**: HIGH - Critical bug fix  
**Date Completed**: 2025-01-28

## Overview

Fix CSV import to correctly merge with existing portfolio items, handle sell-only transactions, and properly update/delete portfolio items.

## Issues to Fix

1. **Sell-only transactions ignored** - CSV with only sells are filtered out
2. **No merge logic** - System creates duplicates instead of updating existing items
3. **No DELETE logic** - Fully sold positions remain in portfolio

## Implementation Plan

### Step 1: Modify `csv_import_service.py` - Handle Sell-Only Transactions

**File**: `backend/app/services/csv_import_service.py`

**Change 1.1**: Modify `_calculate_weighted_average()` method (lines 362-418)

- Remove early return when no buy_txns found
- Calculate net_quantity even for sell-only transactions
- Return net_quantity (can be negative), net_change flag, and transaction summary
- Return None only if there are no transactions at all

**Change 1.2**: Modify `aggregate_transactions()` method (lines 332-360)

- Include ALL symbols even if net_quantity <= 0
- Add `net_change` field to returned items (positive for buys, negative for sells)
- Add `is_sell_only` flag for symbols with only sells

### Step 2: Modify `csv_import.py` - Implement Portfolio Merge Logic

**File**: `backend/app/api/csv_import.py`

**Change 2.1**: Rewrite portfolio merge logic in `execute_csv_import()` (lines 115-164)

- Replace duplicate check with existence check by symbol only
- For each aggregated item:
  - Query existing portfolio item by symbol (not quantity)
  - If exists:
    - Calculate new amount = old_amount + net_change
    - If new_amount <= 0: DELETE portfolio item
    - If new_amount > 0: UPDATE with weighted average price and new amount
  - If doesn't exist:
    - If net_quantity > 0: INSERT new portfolio item
    - If net_quantity <= 0: Log warning (selling non-existent position)

**Change 2.2**: Update import statistics

- Track items_updated, items_deleted, items_inserted separately
- Update import_history with accurate counts

### Step 3: Handle Edge Cases

**Edge Case 3.1**: Multiple portfolio items for same symbol

- For now: Update the first matching item
- Future: Consider merging all matching items

**Edge Case 3.2**: Price calculation for merged positions

- Calculate weighted average: (old_amount *old_price + new_amount* new_price) / (old_amount + new_amount)

**Edge Case 3.3**: Commission and fees

- Add new commission to existing commission
- Recalculate total_investment_text

**Edge Case 3.4**: Currency handling

- Handle currency conversions correctly when merging items with different currencies

## Implementation Checklist

### Phase 1: Service Layer Changes

- [ ] Modify `_calculate_weighted_average()` to return net_change information for all transaction types
- [ ] Update `aggregate_transactions()` to include sell-only symbols
- [ ] Add helper method to calculate weighted average for merged positions
- [ ] Test aggregation logic with various transaction combinations

### Phase 2: API Layer Changes

- [ ] Replace duplicate check with existence check by symbol
- [ ] Implement UPDATE logic for existing portfolio items
- [ ] Implement DELETE logic for fully sold positions
- [ ] Implement INSERT logic for new positions
- [ ] Update import statistics tracking
- [ ] Add comprehensive logging for merge operations

### Phase 3: Testing & Validation

- [ ] Test with sell-only CSV (user's current scenario)
- [ ] Test with buy-only CSV
- [ ] Test with mixed buys/sells CSV
- [ ] Test merging with existing portfolio items
- [ ] Test price calculation accuracy after merge
- [ ] Test with user credentials (use your own)
- [ ] Verify portfolio dashboard reflects correct holdings

## Detailed Code Changes

### Change 1: `csv_import_service.py` - `_calculate_weighted_average()`

**Current behavior**: Returns None if no buys or net_quantity <= 0

**New behavior**:

- Always calculate net_quantity = total_buy_qty - total_sell_qty
- Return result even if net_quantity <= 0 (so we can DELETE portfolio items)
- Add `net_change` field indicating positive/negative change
- Add `transaction_summary` with buy/sell breakdown

### Change 2: `csv_import_service.py` - `aggregate_transactions()`

**Current behavior**: Filters out items where `_calculate_weighted_average()` returns None

**New behavior**:

- Include ALL aggregated items, even with negative quantities
- Add `net_change` field to each aggregated item
- Don't filter by net_quantity in aggregation

### Change 3: `csv_import.py` - `execute_csv_import()`

**Current behavior**:

- Checks duplicate by symbol + exact quantity
- Only does INSERT operations

**New behavior**:

```python
for item in aggregated_items:
    # Check if portfolio item exists by symbol only
    existing_item = query_portfolio_item_by_symbol(symbol)
    
    if existing_item:
        # Calculate new amount
        new_amount = existing_item.amount + item.net_change
        
        if new_amount <= 0:
            # DELETE portfolio item
            delete_portfolio_item(existing_item.id)
        else:
            # UPDATE with merged data
            merged_price = calculate_weighted_avg_price(
                existing_item, item
            )
            update_portfolio_item(
                existing_item.id,
                amount=new_amount,
                price_buy=merged_price,
                ...
            )
    else:
        # Item doesn't exist in portfolio
        if item.net_quantity > 0:
            # INSERT new item
            insert_portfolio_item(item)
        else:
            # Selling non-existent position - log warning
            logger.warning(f"Selling {symbol} that doesn't exist in portfolio")
```text

## Testing Scenarios

### Test Case 1: Sell-Only Transactions (User's Current Scenario)
**Input CSV**:
- ZEN: Sell 7.65
- DASH: Sell 2.00
- IP: Sell 12
- HBAR: Sell 528.49
- BTC: Buy 0.0043

**Expected Result**:
- ZEN, DASH, IP, HBAR removed from portfolio (if they existed)
- BTC added to portfolio (or updated if exists)

### Test Case 2: Merge with Existing Portfolio
**Portfolio State**: BTC 5.0 @ $50,000
**CSV Input**: BTC Sell 2.0
**Expected Result**: BTC updated to 3.0 @ $50,000

### Test Case 3: Multiple Transactions Same Symbol
**CSV Input**: 
- BTC Buy 1.0 @ $45,000
- BTC Sell 0.5 @ $50,000
- BTC Buy 2.0 @ $55,000
**Expected Result**: BTC net = 2.5 @ weighted average price

### Test Case 4: Fully Sold Position
**Portfolio State**: ETH 2.0
**CSV Input**: ETH Sell 2.0
**Expected Result**: ETH deleted from portfolio

## Rollback Plan

If issues arise:
1. Restore previous version of `csv_import_service.py`
2. Restore previous version of `csv_import.py`
3. Re-import affected portfolios manually

## Success Criteria

✅ Sell-only transactions are processed correctly  
✅ Existing portfolio items are updated (not duplicated)  
✅ Fully sold positions are removed from portfolio  
✅ Weighted average prices calculated correctly after merge  
✅ Import statistics accurately reflect insert/update/delete counts  
✅ User's CSV can be imported without data loss or duplication

