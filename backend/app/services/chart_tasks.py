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


async def fetch_chart_data_for_symbols(symbols: List[str], days: int = 7):
    """
    Fetch and cache chart data for multiple symbols with rate limiting.
    
    Args:
        symbols: List of cryptocurrency symbols to fetch chart data for
        days: Number of days of history to fetch (default: 7 for mini charts)
    """
    if not symbols:
        logger.debug("No symbols provided for chart data fetch")
        return
    
    logger.info(f"📊 Starting chart data fetch for {len(symbols)} symbols")
    
    success_count = 0
    error_count = 0
    
    # Process symbols sequentially with delays to respect rate limits
    for i, symbol in enumerate(symbols):
        try:
            # Fetch mini chart data (7 days) - this will be cached
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
        
        # Add delay between requests to avoid rate limiting
        # Small delay between each symbol (the service already has its own rate limiting)
        if i < len(symbols) - 1:  # Don't delay after last symbol
            await asyncio.sleep(0.5)  # 500ms between symbols
    
    logger.info(
        f"📊 Chart data fetch complete: {success_count} successful, {error_count} failed/empty"
    )


async def background_chart_data_fetcher():
    """
    Background task to periodically fetch and cache chart data for all portfolio symbols.
    Runs immediately on startup, then every hour to keep charts up-to-date.
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
            
            logger.info(f"📊 Found {len(all_symbols)} unique symbols to fetch chart data for")
            
            # Fetch chart data for all symbols (with rate limiting built into the service)
            await fetch_chart_data_for_symbols(all_symbols, days=7)
            
            logger.info("✅ Hourly chart data update cycle complete")
            
        except Exception as e:
            logger.error(f"Error in background chart data fetcher: {e}", exc_info=True)
        
        # Wait 1 hour before next fetch cycle
        await asyncio.sleep(3600)  # 1 hour = 3600 seconds

