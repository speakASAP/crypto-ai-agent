"""Background tasks for fetching and caching chart data"""
import asyncio
from typing import List
from datetime import datetime, timezone
from ..services.historical_price_service import historical_price_service
from ..dependencies.auth import get_db_connection
from ..utils.db import normalize_placeholders as _normalize_placeholders
try:
    from utils.logger import get_logger
except Exception:  # pragma: no cover
    from ..utils.logger import get_logger

logger = get_logger("backend.app.services.chart_tasks")


async def fetch_chart_data_for_symbols(symbols: List[str], days: int = 7, skip_cached: bool = True):
    """
    Fetch and cache chart data for multiple symbols sequentially with rate limiting.
    Only fetches symbols that don't have fresh cache (reduces API calls significantly).
    Processes one symbol at a time with 1 second delay between requests to avoid API rate limits.
    Data is saved to database cache for future use.
    
    Args:
        symbols: List of cryptocurrency symbols to fetch chart data for
        days: Number of days of history to fetch (default: 7 for mini charts)
        skip_cached: If True, skip symbols that already have fresh cache (default: True)
    """
    if not symbols:
        logger.debug("No symbols provided for chart data fetch")
        return
    
    # Filter out symbols that already have fresh cache to reduce API calls
    symbols_to_fetch = []
    if skip_cached:
        for symbol in symbols:
            # Check if symbol has fresh cache (cache is valid for 1 hour, refreshed every 30 min)
            cached = historical_price_service._get_from_cache(symbol)
            if not cached:
                symbols_to_fetch.append(symbol)
            else:
                logger.debug(f"⏭️ Skipping {symbol} - already has fresh cache ({len(cached)} data points)")
    else:
        symbols_to_fetch = symbols
    
    if not symbols_to_fetch:
        logger.info(f"✅ All {len(symbols)} symbols already have fresh cache - no API calls needed!")
        return
    
    logger.info(f"📊 Starting sequential chart data fetch for {len(symbols_to_fetch)}/{len(symbols)} symbols (skipped {len(symbols) - len(symbols_to_fetch)} with cache)")
    logger.info(f"⏱️ Estimated time: ~{len(symbols_to_fetch)} seconds (1 request per second)")
    
    success_count = 0
    error_count = 0
    skipped_count = len(symbols) - len(symbols_to_fetch)
    
    # Process symbols sequentially (one at a time) with 1 second delay between requests
    for i, symbol in enumerate(symbols_to_fetch):
        try:
            logger.debug(f"🔄 Fetching chart data for {symbol} ({i+1}/{len(symbols_to_fetch)})")
            
            # Fetch mini chart data (7 days) - this will be cached in database
            # Note: get_mini_chart_data checks cache first, but we already filtered cached ones above
            # This ensures we only make API calls for symbols that need updating
            chart_data = await historical_price_service.get_mini_chart_data(symbol, days=days)
            
            if chart_data and len(chart_data) > 0:
                # Check if data has price variations (not flat)
                prices = [point.get("price", 0) for point in chart_data if isinstance(point, dict)]
                if prices and len(set(prices)) > 1:
                    success_count += 1
                    logger.debug(f"✅ Cached chart data for {symbol} ({len(chart_data)} points)")
                else:
                    logger.warning(f"⚠️ Skipped flat chart data for {symbol}")
                    error_count += 1
            else:
                logger.debug(f"⚠️ No chart data received for {symbol}")
                error_count += 1
                
        except Exception as e:
            logger.error(f"❌ Error fetching chart data for {symbol}: {e}")
            error_count += 1
        
        # Add 1 second delay between requests to avoid rate limiting
        # This ensures we don't hit CoinGecko API rate limits (1 request per second)
        if i < len(symbols_to_fetch) - 1:  # Don't delay after last symbol
            await asyncio.sleep(1.0)  # 1 second delay between symbols
    
    logger.info(
        f"📊 Chart data fetch complete: {success_count} successful, {error_count} failed/empty, {skipped_count} skipped (had cache)"
    )


async def background_chart_data_fetcher():
    """
    Background task to periodically fetch and cache chart data for all portfolio symbols.
    Runs immediately on startup, then every hour to keep charts up-to-date.
    Fetches data sequentially (1 request per second) to avoid API rate limits.
    All data is saved to database cache and served from there.
    """
    # Small delay on startup to let the app initialize
    await asyncio.sleep(30)  # 30 seconds delay before first fetch
    
    while True:
        try:
            logger.info("🔄 Starting hourly chart data update cycle")
            
            # Query all unique symbols from portfolio_items table
            conn = get_db_connection()
            cursor = conn.cursor()
            sql = _normalize_placeholders(
                "SELECT DISTINCT symbol FROM portfolio_items WHERE symbol IS NOT NULL"
            )
            cursor.execute(sql)
            rows = cursor.fetchall()
            conn.close()
            
            all_symbols = [row[0] for row in rows if row[0]]
            
            if not all_symbols:
                logger.debug("No symbols found in portfolio, skipping chart data fetch")
                # Still wait 1 hour before next check
                await asyncio.sleep(3600)
                continue
            
            logger.info(f"📊 Found {len(all_symbols)} unique symbols in portfolio")
            
            # Fetch chart data for symbols that need updating (skips cached ones to reduce API calls)
            # Data is automatically saved to database cache
            await fetch_chart_data_for_symbols(all_symbols, days=7, skip_cached=True)
            
            logger.info("✅ Hourly chart data update cycle complete")
            
        except Exception as e:
            logger.error(f"Error in background chart data fetcher: {e}", exc_info=True)
        
        # Wait 1 hour before next fetch cycle
        await asyncio.sleep(3600)  # 1 hour = 3600 seconds

