import aiohttp
import json
import asyncio
import time
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
from ..core.config import settings
from ..utils.logger import get_logger
from .multi_exchange_price_service import multi_exchange_price_service
from ..utils.db import get_db_connection, normalize_placeholders

# Create a shared timeout configuration
CLIENT_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=10)

logger = get_logger("backend.app.services.historical_price_service")


class HistoricalPriceService:
    """Service for fetching and caching historical price data from CoinGecko"""

    def __init__(self):
        self.coingecko_url = "https://api.coingecko.com/api/v3"
        self.cache_duration = timedelta(hours=1)  # Cache valid for 1 hour (background task refresh hourly)
        # Rate limiting: CoinGecko free tier allows ~10-50 calls/minute
        # Background task fetches sequentially (1 request per second) to avoid rate limits
        # Use semaphore to limit concurrent requests and delay between requests
        self._request_semaphore = asyncio.Semaphore(2)  # Max 2 concurrent requests
        self._min_request_delay = 1.5  # Minimum 1.5 seconds between requests
        self._last_request_time = 0.0
        self._rate_limit_retry_delay = 60  # Wait 60 seconds on rate limit

    def _symbol_to_coingecko_id(self, symbol: str) -> Optional[str]:
        """
        Map symbols to CoinGecko coin IDs with automatic resolution.
        Priority: 1) Database cache, 2) Return None to trigger auto-resolution via API
        
        Note: all symbols are resolved via database cache or API.
        Common symbols are automatically cached in database on first use.
        """
        symbol_upper = symbol.upper()
        
        # Check database cache (fastest, most up-to-date)
        cached_mapping = self._get_cached_coingecko_id(symbol_upper)
        if cached_mapping:
            # Update last_used timestamp
            self._update_mapping_last_used(symbol_upper)
            return cached_mapping
        
        # Return None to trigger automatic resolution via API
        # The API will resolve and cache the result for future use
        return None

    async def get_price_history(
        self, symbol: str, days: int = 365
    ) -> List[Dict[str, any]]:
        """
        Get historical price data for a symbol (cached)

        Args:
            symbol: Cryptocurrency symbol (e.g., BTC, ETH)
            days: Number of days of history to fetch (default: 365 for 1 year)

        Returns:
            List of price data points with timestamp and price
        """
        # Check cache first
        cached_data = self._get_from_cache(symbol)
        if cached_data:
            logger.debug(f"Returning cached price history for {symbol}")
            return cached_data

        # Fetch from CoinGecko with rate limiting
        coin_id = self._symbol_to_coingecko_id(symbol)
        
        # If coin_id is None, try to auto-resolve it
        if coin_id is None:
            coin_id = await self._auto_resolve_coingecko_id(symbol)
            if coin_id is None:
                logger.warning(f"Could not resolve CoinGecko ID for {symbol}, returning empty history")
                return []
        
        async with self._request_semaphore:
            # Ensure minimum delay between requests
            current_time = time.time()
            time_since_last_request = current_time - self._last_request_time
            if time_since_last_request < self._min_request_delay:
                wait_time = self._min_request_delay - time_since_last_request
                await asyncio.sleep(wait_time)
            
            self._last_request_time = time.time()
            
            try:
                async with aiohttp.ClientSession(timeout=CLIENT_TIMEOUT) as session:
                    url = f"{self.coingecko_url}/coins/{coin_id}/market_chart"
                    params = {
                        "vs_currency": "usd",
                        "days": str(days),
                    }
                    # Only specify interval for days > 90 (daily). For 2-90 days, CoinGecko
                    # automatically provides hourly data without explicit interval parameter
                    if days > 90:
                        params["interval"] = "daily"

                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            prices = data.get("prices", [])

                            # Format data
                            history = [
                                {
                                    "timestamp": int(price[0] / 1000),  # Convert to seconds
                                    "price": float(price[1]),
                                    "date": datetime.fromtimestamp(
                                        price[0] / 1000, tz=timezone.utc
                                    ).isoformat(),
                                }
                                for price in prices
                            ]

                            # Cache the results
                            self._save_to_cache(symbol, history)

                            logger.info(
                                f"Fetched {len(history)} price points for {symbol}"
                            )
                            return history
                        elif response.status == 404:
                            logger.warning(
                                f"CoinGecko coin ID '{coin_id}' not found for {symbol}, attempting auto-resolution"
                            )
                            # Try to auto-resolve the symbol
                            resolved_coin_id = await self._auto_resolve_coingecko_id(symbol)
                            if resolved_coin_id and resolved_coin_id != coin_id:
                                # Retry with resolved coin_id
                                logger.info(f"🔄 Retrying with auto-resolved coin_id: {resolved_coin_id}")
                                # Recursive call with resolved coin_id (but limit depth to prevent infinite loop)
                                # Instead, we'll try the alternative fetch method
                                return await self._fetch_alternative(symbol, days)
                            else:
                                # Fallback to alternative fetch method
                                return await self._fetch_alternative(symbol, days)
                        elif response.status == 429:
                            # Rate limit - try to use cached data if available
                            error_text = await response.text()
                            logger.warning(
                                f"CoinGecko rate limit hit for {symbol}, trying cache fallback"
                            )
                            # Try cache fallback (won't return synthesized data)
                            cached = self._get_from_cache(symbol)
                            if cached:
                                return cached
                            return []
                        else:
                            error_text = await response.text()
                            logger.error(
                                f"CoinGecko API error {response.status} for {symbol}: {error_text}"
                            )
                            # Try cache fallback (won't return synthesized data)
                            cached = self._get_from_cache(symbol)
                            if cached:
                                return cached
                            return []
            except Exception as e:
                logger.error(
                    f"Error fetching price history for {symbol}: {e}", exc_info=True
                )
                # Try cache fallback (won't return synthesized data)
                cached = self._get_from_cache(symbol)
                if cached:
                    return cached
                return []

    async def _fetch_alternative(self, symbol: str, days: int) -> List[Dict[str, any]]:
        """Alternative fetch method using coin list search"""
        try:
            async with aiohttp.ClientSession(timeout=CLIENT_TIMEOUT) as session:
                # First, search for the coin
                url = f"{self.coingecko_url}/search"
                params = {"query": symbol}

                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        coins = data.get("coins", [])
                        if coins:
                            coin_id = coins[0].get("id")
                            # Now fetch market chart
                            url = f"{self.coingecko_url}/coins/{coin_id}/market_chart"
                            params = {
                                "vs_currency": "usd",
                                "days": str(days),
                            }
                            # Only specify interval for days > 90 (daily). For 2-90 days, CoinGecko
                            # automatically provides hourly data without explicit interval parameter
                            if days > 90:
                                params["interval"] = "daily"

                            async with session.get(
                                url, params=params
                            ) as response:
                                if response.status == 200:
                                    data = await response.json()
                                    prices = data.get("prices", [])

                                    history = [
                                        {
                                            "timestamp": int(price[0] / 1000),
                                            "price": float(price[1]),
                                            "date": datetime.fromtimestamp(
                                                price[0] / 1000, tz=timezone.utc
                                            ).isoformat(),
                                        }
                                        for price in prices
                                    ]

                                    self._save_to_cache(symbol, history)
                                    return history
        except Exception as e:
            logger.error(f"Error in alternative fetch for {symbol}: {e}")

        return []

    async def _fallback_from_current_price(self, symbol: str, days: int) -> List[Dict[str, any]]:
        """Synthesize a minimal price history using the current price when external APIs are unavailable.

        Returns a flat series for the requested window so UI can render mini charts instead of 404.
        """
        try:
            prices = await multi_exchange_price_service.get_current_prices([symbol])
            current = prices.get(symbol.upper())
            if current is None:
                return []

            now = datetime.now(timezone.utc)
            # Build daily points for the requested period (at least 7 points)
            num_days = max(7, days)
            history = []
            for i in range(num_days, 0, -1):
                dt = now - timedelta(days=i)
                history.append({
                    "timestamp": int(dt.timestamp()),
                    "price": float(current),
                    "date": dt.isoformat(),
                })
            # Include a point for now
            history.append({
                "timestamp": int(now.timestamp()),
                "price": float(current),
                "date": now.isoformat(),
            })

            # Cache synthesized data to unblock mini charts
            self._save_to_cache(symbol, history)
            logger.warning(f"Using synthesized price history for {symbol} due to upstream limits")
            return history
        except Exception:
            return []

    def _get_from_cache(self, symbol: str) -> Optional[List[Dict[str, any]]]:
        """Get cached price history from database"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            sql = normalize_placeholders(
                "SELECT history_data, last_updated FROM price_history_cache WHERE symbol = %s"
            )
            cursor.execute(sql, (symbol.upper(),))
            row = cursor.fetchone()
            conn.close()

            if row:
                history_data_str, last_updated_value = row
                
                # Handle both string and datetime objects from database
                if isinstance(last_updated_value, datetime):
                    last_updated = last_updated_value
                    # Ensure timezone-aware
                    if last_updated.tzinfo is None:
                        last_updated = last_updated.replace(tzinfo=timezone.utc)
                elif isinstance(last_updated_value, str):
                    # Parse string timestamp
                    last_updated_str = last_updated_value.replace("Z", "+00:00")
                    last_updated = datetime.fromisoformat(last_updated_str)
                else:
                    # Try to parse as ISO format
                    last_updated_str = str(last_updated_value).replace("Z", "+00:00")
                    last_updated = datetime.fromisoformat(last_updated_str)

                # Check if cache is still valid
                if datetime.now(timezone.utc) - last_updated < self.cache_duration:
                    try:
                        history_data = json.loads(history_data_str)
                        # Detect if cached data is synthesized/flat (all prices identical)
                        # This can happen when fallback was used previously
                        if len(history_data) > 1:
                            prices = [point.get("price", 0) for point in history_data if isinstance(point, dict)]
                            if prices and len(set(prices)) == 1:
                                # All prices are identical - likely synthesized data
                                logger.warning(
                                    f"Detected synthesized/flat cached data for {symbol}, invalidating cache"
                                )
                                self._clear_cache(symbol)
                                return None
                        return history_data
                    except json.JSONDecodeError:
                        logger.warning(
                            f"Invalid JSON in cache for {symbol}, clearing cache"
                        )
                        self._clear_cache(symbol)

        except Exception as e:
            logger.debug(f"Error reading cache for {symbol}: {e}")

        return None

    def _save_to_cache(self, symbol: str, history: List[Dict[str, any]]) -> None:
        """Save price history to database cache"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            history_json = json.dumps(history)
            now = datetime.now(timezone.utc).isoformat()

            sql = """
                INSERT INTO price_history_cache (symbol, history_data, last_updated)
                VALUES (%s, %s, %s)
                ON CONFLICT (symbol) DO UPDATE SET
                    history_data = EXCLUDED.history_data,
                    last_updated = EXCLUDED.last_updated
            """

            cursor.execute(sql, (symbol.upper(), history_json, now))
            conn.commit()
            conn.close()

            logger.debug(f"Cached price history for {symbol}")

        except Exception as e:
            logger.error(f"Error saving cache for {symbol}: {e}", exc_info=True)

    def _clear_cache(self, symbol: str) -> None:
        """Clear cache for a symbol"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            sql = normalize_placeholders(
                "DELETE FROM price_history_cache WHERE symbol = %s"
            )
            cursor.execute(sql, (symbol.upper(),))
            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error clearing cache for {symbol}: {e}")

    async def get_mini_chart_data(
        self, symbol: str, days: int = 7
    ) -> List[Dict[str, any]]:
        """
        Get mini chart data (last N days). Serves from database cache (refresh hourly by background task).
        Only fetches from CoinGecko API if cache is missing or stale (fallback for new symbols).

        Args:
            symbol: Cryptocurrency symbol
            days: Number of days to return (default: 7)

        Returns:
            List of price points for the last N days from database cache or CoinGecko API (if cache miss)
        """
        # Check database cache first - background task refresh hourly
        cached_data = self._get_from_cache(symbol)
        if cached_data:
            # Filter to last N days if needed
            if days < 365:  # Only filter if we need less than full year
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
                cutoff_timestamp = int(cutoff_date.timestamp())
                filtered = [
                    point
                    for point in cached_data
                    if point.get("timestamp", 0) >= cutoff_timestamp
                ]
                if filtered:
                    logger.debug(f"Returning cached mini chart data for {symbol} ({len(filtered)} points)")
                    return filtered
            else:
                logger.debug(f"Returning cached chart data for {symbol} ({len(cached_data)} points)")
                return cached_data
        
        # Cache miss or stale - fetch from CoinGecko API
        coin_id = self._symbol_to_coingecko_id(symbol)
        
        # If coin_id is None, try to auto-resolve it
        if coin_id is None:
            coin_id = await self._auto_resolve_coingecko_id(symbol)
            if coin_id is None:
                logger.warning(f"Could not resolve CoinGecko ID for {symbol}, returning empty chart data")
                return []
        
        async with self._request_semaphore:
            # Ensure minimum delay between requests
            current_time = time.time()
            time_since_last_request = current_time - self._last_request_time
            if time_since_last_request < self._min_request_delay:
                wait_time = self._min_request_delay - time_since_last_request
                await asyncio.sleep(wait_time)
            
            self._last_request_time = time.time()
            
            try:
                async with aiohttp.ClientSession(timeout=CLIENT_TIMEOUT) as session:
                    url = f"{self.coingecko_url}/coins/{coin_id}/market_chart"
                    params = {
                        "vs_currency": "usd",
                        "days": str(days),
                    }
                    # Only specify interval for days > 90 (daily). For 2-90 days, CoinGecko
                    # automatically provides hourly data without explicit interval parameter
                    if days > 90:
                        params["interval"] = "daily"

                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            prices = data.get("prices", [])

                            # Format data points
                            history = [
                                {
                                    "timestamp": int(price[0] / 1000),  # Convert milliseconds to seconds
                                    "price": float(price[1]),
                                    "date": datetime.fromtimestamp(
                                        price[0] / 1000, tz=timezone.utc
                                    ).isoformat(),
                                }
                                for price in prices
                            ]

                            # Cache the fetched data
                            self._save_to_cache(symbol, history)
                            
                            logger.debug(
                                f"Fetched {len(history)} real-time price points from CoinGecko for {symbol} ({days} days)"
                            )
                            return history
                        elif response.status == 404:
                            logger.warning(
                                f"CoinGecko coin ID '{coin_id}' not found for {symbol}, attempting auto-resolution"
                            )
                            # Try to auto-resolve the symbol
                            resolved_coin_id = await self._auto_resolve_coingecko_id(symbol)
                            if resolved_coin_id and resolved_coin_id != coin_id:
                                # Retry with resolved coin_id (use alternative fetch to avoid recursion)
                                logger.info(f"🔄 Retrying with auto-resolved coin_id: {resolved_coin_id}")
                                return await self._fetch_alternative(symbol, days)
                            else:
                                # Fallback to alternative fetch method
                                return await self._fetch_alternative(symbol, days)
                        elif response.status == 429:
                            # Rate limit - don't create synthesized data
                            error_text = await response.text()
                            logger.warning(
                                f"CoinGecko rate limit hit for {symbol} mini chart, using cache fallback"
                            )
                            # Fallback to cached data if available
                            return await self._get_mini_chart_fallback(symbol, days)
                        else:
                            error_text = await response.text()
                            logger.error(
                                f"CoinGecko API error {response.status} for {symbol}: {error_text}"
                            )
                            # Fallback to cached data if available
                            return await self._get_mini_chart_fallback(symbol, days)
            except Exception as e:
                logger.error(
                    f"Error fetching mini chart data from CoinGecko for {symbol}: {e}", exc_info=True
                )
                # Fallback to cached data if available
                return await self._get_mini_chart_fallback(symbol, days)

    async def _get_mini_chart_fallback(
        self, symbol: str, days: int
    ) -> List[Dict[str, any]]:
        """
        Fallback method: get mini chart data from cache if CoinGecko API fails

        Args:
            symbol: Cryptocurrency symbol
            days: Number of days to return

        Returns:
            List of price points from cache, or empty list if no cache available
        """
        # Try to get from cache as fallback
        full_history = self._get_from_cache(symbol)
        if not full_history:
            logger.warning(
                f"No cached data available for {symbol}, returning empty chart data"
            )
            return []

        # Filter to last N days
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_timestamp = int(cutoff_date.timestamp())

        filtered = [
            point
            for point in full_history
            if point.get("timestamp", 0) >= cutoff_timestamp
        ]

        # Sort by timestamp
        filtered.sort(key=lambda x: x.get("timestamp", 0))

        logger.debug(
            f"Using cached fallback data for {symbol}: {len(filtered)} points"
        )
        return filtered

    def _get_cached_coingecko_id(self, symbol: str) -> Optional[str]:
        """Get cached CoinGecko coin ID from database"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            sql = normalize_placeholders(
                "SELECT coin_id FROM coingecko_symbol_mappings WHERE symbol = %s"
            )
            cursor.execute(sql, (symbol.upper(),))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return row[0]
        except Exception as e:
            logger.debug(f"Error reading cached CoinGecko mapping for {symbol}: {e}")
        
        return None

    def _save_coingecko_mapping(
        self, symbol: str, coin_id: str, resolution_method: str = "api_search", coin_name: Optional[str] = None
    ) -> None:
        """Save CoinGecko symbol mapping to database"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            
            sql = normalize_placeholders(
                """
                INSERT INTO coingecko_symbol_mappings (symbol, coin_id, coin_name, resolved_at, last_used, resolution_method, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol) DO UPDATE SET
                    coin_id = EXCLUDED.coin_id,
                    coin_name = COALESCE(EXCLUDED.coin_name, coingecko_symbol_mappings.coin_name),
                    last_used = EXCLUDED.last_used,
                    resolution_method = EXCLUDED.resolution_method
                """
            )
            cursor.execute(sql, (symbol.upper(), coin_id, coin_name, now, now, resolution_method, now))
            conn.commit()
            conn.close()
            
            logger.debug(f"Saved CoinGecko mapping: {symbol} -> {coin_id} (method: {resolution_method})")
        except Exception as e:
            logger.error(f"Error saving CoinGecko mapping for {symbol}: {e}", exc_info=True)

    def _update_mapping_last_used(self, symbol: str) -> None:
        """Update last_used timestamp for a mapping"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            
            sql = normalize_placeholders(
                "UPDATE coingecko_symbol_mappings SET last_used = %s WHERE symbol = %s"
            )
            cursor.execute(sql, (now, symbol.upper()))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.debug(f"Error updating mapping last_used for {symbol}: {e}")

    async def pre_populate_common_symbols(self) -> None:
        """
        Pre-populate database with common cryptocurrency symbols for faster first-time access.
        This runs on startup to ensure common symbols (BTC, ETH, etc.) are cached immediately.
        """
        common_symbols = [
            "BTC", "ETH", "BNB", "SOL", "ADA", "XRP", "DOT", "DOGE", "AVAX", "MATIC",
            "LINK", "UNI", "LTC", "ATOM", "ETC", "BCH", "XLM", "ALGO", "VET", "FIL",
            "TRX", "EOS", "AAVE", "GRT", "SAND", "MANA", "AXS", "CHZ", "ENJ", "TON",
            "FLR", "RENDER", "RNDR", "XMR"
        ]
        
        logger.info(f"🔄 Pre-populating {len(common_symbols)} common symbol mappings...")
        
        for symbol in common_symbols:
            # Check if already cached
            if self._get_cached_coingecko_id(symbol):
                continue
            
            # Resolve and cache
            try:
                coin_id = await self._auto_resolve_coingecko_id(symbol)
                if coin_id:
                    logger.debug(f"✅ Pre-populated {symbol} -> {coin_id}")
                # Small delay to respect rate limits
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.debug(f"Could not pre-populate {symbol}: {e}")
                continue
        
        logger.info("✅ Common symbol pre-population complete")

    async def _auto_resolve_coingecko_id(self, symbol: str) -> Optional[str]:
        """
        Automatically resolve symbol to CoinGecko coin ID using search API.
        Saves result to database for future use.
        """
        try:
            symbol_upper = symbol.upper()
            logger.info(f"🔍 Auto-resolving CoinGecko ID for {symbol_upper} using search API")
            
            async with self._request_semaphore:
                # Ensure minimum delay between requests
                current_time = time.time()
                time_since_last_request = current_time - self._last_request_time
                if time_since_last_request < self._min_request_delay:
                    wait_time = self._min_request_delay - time_since_last_request
                    await asyncio.sleep(wait_time)
                
                self._last_request_time = time.time()
                
                async with aiohttp.ClientSession(timeout=CLIENT_TIMEOUT) as session:
                    # Use CoinGecko search API
                    url = f"{self.coingecko_url}/search"
                    params = {"query": symbol_upper}
                    
                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            coins = data.get("coins", [])
                            
                            if coins:
                                # Get the best match (first result, usually most relevant)
                                best_match = coins[0]
                                coin_id = best_match.get("id")
                                coin_name = best_match.get("name")
                                
                                if coin_id:
                                    # Save to database for future use
                                    self._save_coingecko_mapping(
                                        symbol_upper, coin_id, "api_search", coin_name
                                    )
                                    logger.info(
                                        f"✅ Auto-resolved {symbol_upper} -> {coin_id} ({coin_name})"
                                    )
                                    
                                    # Optionally trigger AI predictions for newly resolved symbol (non-blocking)
                                    self._trigger_ai_predictions_async(symbol_upper)
                                    
                                    return coin_id
                                else:
                                    logger.warning(f"⚠️ CoinGecko search returned match for {symbol_upper} but no coin_id")
                            else:
                                logger.warning(f"⚠️ CoinGecko search returned no matches for {symbol_upper}")
                        elif response.status == 429:
                            logger.warning(f"⚠️ CoinGecko rate limit hit during auto-resolution for {symbol_upper}")
                        else:
                            error_text = await response.text()
                            logger.error(
                                f"❌ CoinGecko search API error {response.status} for {symbol_upper}: {error_text[:200]}"
                            )
        except Exception as e:
            logger.error(f"❌ Error auto-resolving CoinGecko ID for {symbol}: {e}", exc_info=True)
        
        return None

    def _trigger_ai_predictions_async(self, symbol: str) -> None:
        """
        Trigger AI predictions for a newly resolved symbol (non-blocking).
        This runs in the background and doesn't block chart data fetching.
        """
        try:
            # Check if predictions already exist to avoid unnecessary API calls
            conn = get_db_connection()
            cursor = conn.cursor()
            sql = normalize_placeholders(
                "SELECT COUNT(*) FROM ai_predictions WHERE symbol = %s AND user_id IS NULL"
            )
            cursor.execute(sql, (symbol.upper(),))
            existing_count = cursor.fetchone()[0]
            conn.close()
            
            if existing_count == 0:
                # Trigger prediction generation in background (non-blocking)
                logger.info(f"🤖 Triggering AI predictions for newly resolved symbol: {symbol.upper()}")
                asyncio.create_task(self._generate_ai_predictions_background(symbol.upper()))
            else:
                logger.debug(f"📊 Predictions already exist for {symbol.upper()}, skipping generation")
        except Exception as e:
            logger.debug(f"Could not check/trigger AI predictions for {symbol}: {e}")

    async def _generate_ai_predictions_background(self, symbol: str) -> None:
        """Generate AI predictions in background (non-blocking)"""
        try:
            from ..services.ai_advisor_service import ai_advisor_service
            
            # Generate global predictions (user_id=None) for the newly resolved symbol
            predictions = await ai_advisor_service.generate_predictions(
                user_id=None,  # None = global predictions (stored with user_id = NULL)
                symbol=symbol,
                force_regenerate=True,  # Force generation for newly resolved symbol
            )
            if predictions:
                logger.info(f"✅ AI predictions generated for newly resolved symbol: {symbol}")
            else:
                logger.debug(f"⚠️ No predictions generated for {symbol} (may be rate-limited)")
        except Exception as e:
            logger.debug(f"⚠️ Failed to generate predictions for {symbol}: {e}")
            # Don't log as error - this is optional and rate limits are expected


# Singleton instance
historical_price_service = HistoricalPriceService()

