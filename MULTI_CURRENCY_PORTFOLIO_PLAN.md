# MULTI-CURRENCY PORTFOLIO ENHANCEMENT PLAN

> 📚 **Documentation Navigation**: [Main README](README.md) | [Current Plan](CURRENT_PLAN.md) | [Logging Config](LOGGING_CONFIG.md)

## PROJECT STATUS

**Current Issue**: Portfolio system only supports USD currency tracking
**Priority**: HIGH - User requires USD, EUR, and CZK support
**Impact**: Users cannot track investments in multiple currencies as required

## CONFIRMED REQUIREMENTS

- ✅ Manual coin entry with amount, date, and buying price
- ❌ Multi-currency support (USD, EUR, CZK)
- ❌ Investment tracking in EUR and CZK
- ❌ Purchase date tracking
- ❌ Enhanced portfolio visualization with multi-currency charts
- ❌ Historical portfolio performance tracking

## TECHNICAL SPECIFICATION

### OVERVIEW

Enhance the existing portfolio tracking system to support multiple currencies (USD, EUR, CZK) with:

1. Multi-currency portfolio tracking
2. Currency conversion capabilities
3. Enhanced database schema with purchase dates
4. Multi-currency portfolio visualization
5. Investment tracking in all three currencies

### IMPLEMENTATION PHASES

#### PHASE 1: DATABASE SCHEMA ENHANCEMENT ✅

**File**: `crypto-ai-agent/agent_advanced.py`

- Add `purchase_date` field to portfolio table
- Add `base_currency` field to portfolio table
- Add `purchase_price_eur` and `purchase_price_czk` fields
- Create currency conversion rates table
- Update database initialization code

**Database Schema Changes**:

```sql
-- Enhanced portfolio table
CREATE TABLE IF NOT EXISTS portfolio (
    symbol TEXT PRIMARY KEY,
    amount REAL,
    price_buy REAL,
    purchase_date DATETIME,
    base_currency TEXT DEFAULT 'USD',
    purchase_price_eur REAL,
    purchase_price_czk REAL
);

-- Currency conversion rates table
CREATE TABLE IF NOT EXISTS currency_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_currency TEXT,
    to_currency TEXT,
    rate REAL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### PHASE 2: CURRENCY CONVERSION SYSTEM ✅

**File**: `crypto-ai-agent/ui_dashboard/app.py`

- Add currency conversion functions
- Integrate with external currency API (e.g., exchangerate-api.com)
- Add currency rate caching system
- Implement real-time currency conversion

**New Functions**:

- `get_currency_rates()` - Fetch current exchange rates
- `convert_currency()` - Convert between USD/EUR/CZK
- `update_currency_rates()` - Update cached rates
- `calculate_multi_currency_portfolio()` - Calculate portfolio in all currencies

#### PHASE 3: ENHANCED PORTFOLIO COMPONENTS ✅

**File**: `crypto-ai-agent/ui_dashboard/components/portfolio_components.py`

- Add multi-currency portfolio display
- Add currency selector for portfolio view
- Add purchase date tracking
- Add multi-currency P&L calculations
- Add currency-specific performance metrics

**New Methods**:

- `display_multi_currency_portfolio()`
- `display_currency_selector()`
- `display_purchase_date_tracking()`
- `display_multi_currency_metrics()`

#### PHASE 4: UI ENHANCEMENTS ✅

**File**: `crypto-ai-agent/ui_dashboard/app.py`

- Add currency selection controls
- Add purchase date input fields
- Add multi-currency portfolio tabs
- Add currency conversion display
- Add historical portfolio tracking

**New UI Sections**:

- Currency Selection Panel
- Multi-Currency Portfolio View
- Purchase Date Tracking
- Currency Conversion Rates Display
- Historical Portfolio Performance

#### PHASE 5: PORTFOLIO VISUALIZATION ENHANCEMENTS ✅

**File**: `crypto-ai-agent/ui_dashboard/components/chart_components.py`

- Add multi-currency balance charts
- Add currency-specific performance charts
- Add historical portfolio value tracking
- Add currency distribution charts

**New Chart Methods**:

- `display_multi_currency_balance_chart()`
- `display_currency_performance_chart()`
- `display_portfolio_history_chart()`
- `display_currency_distribution_chart()`

#### PHASE 6: TESTING AND VALIDATION ✅

**File**: `test_multi_currency_portfolio.py` (NEW)

- Test currency conversion functions
- Test multi-currency portfolio calculations
- Test database schema changes
- Test UI components
- Test currency rate fetching

## IMPLEMENTATION CHECKLIST

### Database Layer

1. Update portfolio table schema with new fields
2. Create currency_rates table
3. Add database migration functions
4. Update portfolio CRUD operations for new fields
5. Add currency rate storage functions

### Currency Conversion System

1. Implement currency rate fetching from external API
2. Add currency conversion calculation functions
3. Add currency rate caching system
4. Add real-time currency updates
5. Add error handling for currency API failures

### Portfolio Components

1. Update PortfolioComponents class for multi-currency support
2. Add currency selector component
3. Add purchase date input component
4. Add multi-currency portfolio display
5. Add currency-specific metrics calculation

### UI Integration

1. Add currency selection controls to main dashboard
2. Update portfolio management forms with new fields
3. Add multi-currency portfolio tabs
4. Add currency conversion rate display
5. Add historical portfolio tracking section

### Chart Components

1. Add multi-currency balance visualization
2. Add currency performance comparison charts
3. Add portfolio history tracking charts
4. Add currency distribution pie charts
5. Add real-time currency rate charts

### Testing & Validation

1. Create comprehensive test suite
2. Test currency conversion accuracy
3. Test multi-currency calculations
4. Test database operations with new schema
5. Test UI components and user interactions

### Documentation

1. Update README with multi-currency features
2. Add currency configuration documentation
3. Update API documentation
4. Add user guide for multi-currency features

## TECHNICAL REQUIREMENTS

### Dependencies

- `requests` or `aiohttp` for currency API calls
- `pandas` for multi-currency calculations
- `plotly` for enhanced visualizations
- `datetime` for purchase date tracking

### External APIs

- Currency conversion API (exchangerate-api.com or similar)
- Fallback currency rates for offline operation

### Database Changes

- Schema migration for existing portfolio data
- Backward compatibility with existing data
- Data validation for new fields

### Performance Considerations

- Currency rate caching (30-minute intervals)
- Lazy loading for large portfolios
- Efficient multi-currency calculations
- Real-time updates without performance impact

## SUCCESS CRITERIA

- Users can track portfolio in USD, EUR, and CZK
- Real-time currency conversion works accurately
- Purchase dates are properly tracked and displayed
- Multi-currency portfolio visualization is intuitive
- Historical portfolio performance is visible
- Currency conversion rates are updated regularly
- All existing functionality remains intact
- Performance is maintained with new features

## FILE STRUCTURE

### New Files

- `test_multi_currency_portfolio.py`
- `currency_converter.py` (utility module)

### Modified Files

- `crypto-ai-agent/agent_advanced.py`
- `crypto-ai-agent/ui_dashboard/app.py`
- `crypto-ai-agent/ui_dashboard/components/portfolio_components.py`
- `crypto-ai-agent/ui_dashboard/components/chart_components.py`
- `README.md`

## IMPLEMENTATION TIMELINE

- **Phase 1-2**: Database and currency system (2-3 hours)
- **Phase 3-4**: UI components and integration (2-3 hours)
- **Phase 5**: Visualization enhancements (1-2 hours)
- **Phase 6**: Testing and validation (1-2 hours)

**Total Estimated Time**: 6-10 hours

---

**IMPLEMENTATION CHECKLIST**:

1. Update portfolio table schema with purchase_date, base_currency, and multi-currency price fields
2. Create currency_rates table for exchange rate storage
3. Add database migration functions for existing data
4. Implement currency rate fetching from external API
5. Add currency conversion calculation functions
6. Add currency rate caching system with 30-minute intervals
7. Update portfolio CRUD operations for new fields
8. Add currency rate storage and retrieval functions
9. Update PortfolioComponents class for multi-currency support
10. Add currency selector component to UI
11. Add purchase date input component to portfolio forms
12. Add multi-currency portfolio display with currency tabs
13. Add currency-specific metrics calculation and display
14. Add currency conversion rate display panel
15. Add historical portfolio tracking section
16. Add multi-currency balance visualization charts
17. Add currency performance comparison charts
18. Add portfolio history tracking charts
19. Add currency distribution pie charts
20. Add real-time currency rate monitoring
21. Create comprehensive test suite for multi-currency features
22. Test currency conversion accuracy with real data
23. Test multi-currency calculations and edge cases
24. Test database operations with new schema
25. Test UI components and user interactions
26. Update README with multi-currency features documentation
27. Add currency configuration and setup instructions
28. Update API documentation for new endpoints
29. Add user guide for multi-currency portfolio management
30. Validate all existing functionality remains intact

---

*Plan created: 2025-01-21*
*Status: READY FOR IMPLEMENTATION*
