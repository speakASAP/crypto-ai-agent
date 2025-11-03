import aiohttp
import json
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
from ..core.config import settings
from ..utils.logger import get_logger
from ..utils.db import get_db_connection, is_postgres_connection, normalize_placeholders

logger = get_logger("backend.app.services.historical_price_service")


class HistoricalPriceService:
    """Service for fetching and caching historical price data from CoinGecko"""

    def __init__(self):
        self.coingecko_url = "https://api.coingecko.com/api/v3"
        self.cache_duration = timedelta(days=1)

    def _symbol_to_coingecko_id(self, symbol: str) -> Dict[str, str]:
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

        # Fetch from CoinGecko
        coin_id = self._symbol_to_coingecko_id(symbol)
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.coingecko_url}/coins/{coin_id}/market_chart"
                params = {
                    "vs_currency": "usd",
                    "days": str(days),
                    "interval": "daily" if days > 90 else "hourly",
                }

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
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"CoinGecko API error {response.status} for {symbol}: {error_text}"
                        )
                        return []
        except Exception as e:
            logger.error(
                f"Error fetching price history for {symbol}: {e}", exc_info=True
            )
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
                                "interval": "daily" if days > 90 else "hourly",
                            }

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

    def _get_from_cache(self, symbol: str) -> Optional[List[Dict[str, any]]]:
        """Get cached price history from database"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            is_pg = is_postgres_connection(conn)

            sql = normalize_placeholders(
                "SELECT history_data, last_updated FROM price_history_cache WHERE symbol = ?",
                is_pg,
            )
            cursor.execute(sql, (symbol.upper(),))
            row = cursor.fetchone()
            conn.close()

            if row:
                history_data_str, last_updated_str = row
                last_updated = datetime.fromisoformat(
                    last_updated_str.replace("Z", "+00:00")
                )

                # Check if cache is still valid
                if datetime.now(timezone.utc) - last_updated < self.cache_duration:
                    try:
                        history_data = json.loads(history_data_str)
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
            is_pg = is_postgres_connection(conn)

            history_json = json.dumps(history)
            now = datetime.now(timezone.utc).isoformat()

            if is_pg:
                sql = """
                    INSERT INTO price_history_cache (symbol, history_data, last_updated)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (symbol) DO UPDATE SET
                        history_data = EXCLUDED.history_data,
                        last_updated = EXCLUDED.last_updated
                """
            else:
                sql = """
                    INSERT OR REPLACE INTO price_history_cache (symbol, history_data, last_updated)
                    VALUES (?, ?, ?)
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
            is_pg = is_postgres_connection(conn)

            sql = normalize_placeholders(
                "DELETE FROM price_history_cache WHERE symbol = ?", is_pg
            )
            cursor.execute(sql, (symbol.upper(),))
            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error clearing cache for {symbol}: {e}")

    def get_mini_chart_data(
        self, symbol: str, days: int = 7
    ) -> List[Dict[str, any]]:
        """
        Get mini chart data (last N days) from cached full history

        Args:
            symbol: Cryptocurrency symbol
            days: Number of days to return (default: 7)

        Returns:
            List of price points for the last N days
        """
        full_history = self._get_from_cache(symbol)
        if not full_history:
            return []

        # Filter to last N days
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_timestamp = int(cutoff_date.timestamp())

        filtered = [
            point
            for point in full_history
            if point.get("timestamp", 0) >= cutoff_timestamp
        ]

        return filtered


# Singleton instance
historical_price_service = HistoricalPriceService()

