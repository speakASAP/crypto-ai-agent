# Automatic Symbol Resolution System

## Overview

This document describes the automatic symbol-to-CoinGecko-ID resolution system that prevents 502 errors and ensures all cryptocurrency symbols work correctly with chart data fetching.

## Problem Solved

Previously, when a cryptocurrency symbol (like XMR) wasn't in the hardcoded mapping, the system would:

1. Try to use the symbol directly as a CoinGecko coin ID
2. Get a 404 error from CoinGecko
3. Potentially cause 502 Bad Gateway errors

## Solution

The system now automatically resolves unknown symbols using CoinGecko's search API and caches the results in the database for future use.

## Architecture

### Database Table

A new table `coingecko_symbol_mappings` stores resolved symbol mappings:

```sql
CREATE TABLE coingecko_symbol_mappings (
    symbol TEXT PRIMARY KEY,
    coin_id TEXT NOT NULL,
    coin_name TEXT,
    resolved_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolution_method TEXT DEFAULT 'api_search',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### Resolution Priority

The `_symbol_to_coingecko_id()` method now follows this priority:

1. **Database Cache** (fastest) - Check if symbol was previously resolved and cached
2. **Hardcoded Map** - Check the static mapping for common symbols (BTC, ETH, etc.)
3. **Auto-Resolution** - Use CoinGecko search API to find the coin ID automatically

### Automatic Resolution Flow

When a symbol is not found:

1. **404 Error Detection**: When CoinGecko returns 404, the system detects it
2. **Auto-Resolution**: Calls `_auto_resolve_coingecko_id()` which:
   - Uses CoinGecko `/search` API to find the coin
   - Extracts the best match (first result)
   - Saves the mapping to database
   - Returns the resolved coin_id
3. **Retry**: Automatically retries the original request with the resolved coin_id
4. **AI Predictions** (optional): Triggers AI prediction generation for newly resolved symbols

## Features

### 1. Database Caching

All resolved mappings are saved to the database, so future requests are instant:

```python
# First request: Auto-resolves via API
coin_id = await _auto_resolve_coingecko_id("XMR")  # Returns "monero"

# Subsequent requests: Instant from database
coin_id = _symbol_to_coingecko_id("XMR")  # Returns "monero" from cache
```

### 2. Automatic 404 Handling

When a 404 error occurs:

```python
# Original request fails with 404
response.status == 404

# System automatically resolves
resolved_coin_id = await _auto_resolve_coingecko_id(symbol)

# Retries with resolved coin_id
# Success!
```

### 3. AI Prediction Triggering

After successful resolution, the system optionally triggers AI predictions:

- Checks if predictions already exist (avoids duplicate API calls)
- Generates predictions in background (non-blocking)
- Handles rate limits gracefully

### 4. Logging and Monitoring

All resolution events are logged:

- `🔍 Auto-resolving CoinGecko ID for {symbol}`
- `✅ Auto-resolved {symbol} -> {coin_id} ({coin_name})`
- `🤖 Triggering AI predictions for newly resolved symbol: {symbol}`

## Usage

### For Developers

The system works automatically - no code changes needed. When you request chart data for any symbol:

```python
# This will automatically resolve unknown symbols
history = await historical_price_service.get_price_history("XMR", days=365)
```

### Manual Resolution

If you want to pre-populate mappings, you can query the database:

```sql
SELECT symbol, coin_id, coin_name, resolution_method, resolved_at
FROM coingecko_symbol_mappings
ORDER BY resolved_at DESC;
```

## Benefits

1. **No More 502 Errors**: Unknown symbols are automatically resolved
2. **Self-Healing**: System learns and caches new symbols automatically
3. **Performance**: Database cache makes subsequent requests instant
4. **Comprehensive Coverage**: Works for any cryptocurrency CoinGecko supports
5. **AI Integration**: Automatically triggers predictions for new symbols

## Database Migration

The table is automatically created on startup via `ensure_ai_advisor_tables()`. For existing databases, the migration runs automatically.

## Rate Limiting

The system respects CoinGecko rate limits:

- Uses semaphore to limit concurrent requests (max 2)
- Minimum 1.5 seconds delay between requests
- Handles 429 rate limit errors gracefully

## Future Enhancements

Potential improvements:

1. Batch resolution for multiple symbols at once
2. Periodic refresh of mappings (in case CoinGecko IDs change)
3. Confidence scoring for search results
4. Manual override for incorrect mappings

## Troubleshooting

### Symbol Not Resolving

If a symbol fails to resolve:

1. Check logs for error messages
2. Verify CoinGecko search API is accessible
3. Check if symbol exists on CoinGecko (may be a new/rare token)
4. Review database for existing mappings

### Database Issues

If the table doesn't exist:

1. Restart the application (table is created on startup)
2. Manually run the migration SQL from `database.py`
3. Check database connection

## Example Logs

```
🔍 Auto-resolving CoinGecko ID for XMR using search API
✅ Auto-resolved XMR -> monero (Monero)
🤖 Triggering AI predictions for newly resolved symbol: XMR
✅ AI predictions generated for newly resolved symbol: XMR
```

## Related Files

- `backend/app/services/historical_price_service.py` - Main service implementation
- `backend/app/core/database.py` - Database table creation
- `backend/app/api/charts.py` - Chart API endpoints
