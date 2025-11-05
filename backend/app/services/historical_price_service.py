import aiohttp
import json
import logging
import asyncio
import time
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
from ..core.config import settings
from ..utils.logger import get_logger
from .multi_exchange_price_service import multi_exchange_price_service
from ..utils.db import get_db_connection, normalize_placeholders

logger = get_logger("backend.app.services.historical_price_service")


class HistoricalPriceService:
    """Service for fetching and caching historical price data from CoinGecko"""

    def __init__(self):
        self.coingecko_url = "https://api.coingecko.com/api/v3"
        self.cache_duration = timedelta(hours=1)  # Cache for 1 hour (charts refresh hourly)
        # Rate limiting: CoinGecko free tier allows ~10-50 calls/minute
        # Use semaphore to limit concurrent requests and delay between requests
        self._request_semaphore = asyncio.Semaphore(2)  # Max 2 concurrent requests
        self._min_request_delay = 1.5  # Minimum 1.5 seconds between requests
        self._last_request_time = 0.0
        self._rate_limit_retry_delay = 60  # Wait 60 seconds on rate limit

    def _symbol_to_coingecko_id(self, symbol: str) -> str:
        """Map common symbols to CoinGecko coin IDs"""
        symbol_map = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "BNB": "binancecoin",
            "SOL": "solana",
            "ADA": "cardano",
            "XRP": "ripple",
            "DOT": "polkadot",
            "DOGE": "dogecoin",
            "AVAX": "avalanche-2",
            "MATIC": "matic-network",
            "LINK": "chainlink",
            "UNI": "uniswap",
            "LTC": "litecoin",
            "ATOM": "cosmos",
            "ETC": "ethereum-classic",
            "BCH": "bitcoin-cash",
            "XLM": "stellar",
            "ALGO": "algorand",
            "VET": "vechain",
            "FIL": "filecoin",
            "TRX": "tron",
            "EOS": "eos",
            "AAVE": "aave",
            "GRT": "the-graph",
            "SAND": "the-sandbox",
            "MANA": "decentraland",
            "AXS": "axie-infinity",
            "CHZ": "chiliz",
            "ENJ": "enjincoin",
            "TON": "toncoin",
            "FLR": "flare",
            "RENDER": "render-token",
            "RNDR": "render-token",  # Legacy symbol support (RENDER rebranded from RNDR)
        }
        return symbol_map.get(symbol.upper(), symbol.lower())

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
        async with self._request_semaphore:
            # Ensure minimum delay between requests
            current_time = time.time()
            time_since_last_request = current_time - self._last_request_time
            if time_since_last_request < self._min_request_delay:
                wait_time = self._min_request_delay - time_since_last_request
                await asyncio.sleep(wait_time)
            
            self._last_request_time = time.time()
            
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"{self.coingecko_url}/coins/{coin_id}/market_chart"
                    params = {
                        "vs_currency": "usd",
                        "days": str(days),
                    }
                    # Only specify interval for days > 90 (daily). For 2-90 days, CoinGecko
                    # automatically provides hourly data without explicit interval parameter
                    if days > 90:
                        params["interval"] = "daily"

                    async with session.get(url, params=params, timeout=30) as response:
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
                                f"CoinGecko coin ID not found for {symbol}, trying alternative"
                            )
                            # Try with symbol directly
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
            async with aiohttp.ClientSession() as session:
                # First, search for the coin
                url = f"{self.coingecko_url}/search"
                params = {"query": symbol}

                async with session.get(url, params=params, timeout=30) as response:
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
                                url, params=params, timeout=30
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
        Get mini chart data (last N days). Prefers cached data if fresh (< 1 hour old).
        Otherwise fetches from CoinGecko API and caches the result.

        Args:
            symbol: Cryptocurrency symbol
            days: Number of days to return (default: 7)

        Returns:
            List of price points for the last N days from cache or CoinGecko API
        """
        # Check cache first - if data is < 1 hour old, use it (background task keeps it fresh)
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
        
        async with self._request_semaphore:
            # Ensure minimum delay between requests
            current_time = time.time()
            time_since_last_request = current_time - self._last_request_time
            if time_since_last_request < self._min_request_delay:
                wait_time = self._min_request_delay - time_since_last_request
                await asyncio.sleep(wait_time)
            
            self._last_request_time = time.time()
            
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"{self.coingecko_url}/coins/{coin_id}/market_chart"
                    params = {
                        "vs_currency": "usd",
                        "days": str(days),
                    }
                    # Only specify interval for days > 90 (daily). For 2-90 days, CoinGecko
                    # automatically provides hourly data without explicit interval parameter
                    if days > 90:
                        params["interval"] = "daily"

                    async with session.get(url, params=params, timeout=30) as response:
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
                                f"CoinGecko coin ID not found for {symbol}, trying alternative"
                            )
                            # Try alternative fetch method
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


# Singleton instance
historical_price_service = HistoricalPriceService()

