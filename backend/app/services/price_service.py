import aiohttp
import asyncio
import logging
from typing import Dict, List, Optional
from decimal import Decimal
from app.core.config import settings
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class PriceService:
    def __init__(self, cache: CacheService):
        self.cache = cache
        self.api_url = settings.binance_api_url
        self.cache_duration = settings.price_cache_duration
    
    async def get_current_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Get current prices for multiple symbols in parallel"""
        if not symbols:
            return {}
        
        # Check cache first
        cache_key = f"prices:{':'.join(sorted(symbols))}"
        cached_prices = await self.cache.get(cache_key)
        if cached_prices:
            logger.debug(f"Retrieved prices from cache for {len(symbols)} symbols")
            return cached_prices
        
        # Create symbol list for Binance API
        symbol_list = [f"{symbol.upper()}USDT" for symbol in symbols]
        
        try:
            async with aiohttp.ClientSession() as session:
                # Create tasks for parallel execution
                tasks = [
                    self._fetch_price(session, symbol)
                    for symbol in symbol_list
                ]
                
                # Execute all tasks in parallel
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                prices = {}
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.warning(f"Failed to fetch price for {symbol_list[i]}: {result}")
                        continue
                    if result:
                        base_symbol = symbol_list[i].replace('USDT', '')
                        prices[base_symbol] = result
                
                # Cache the results
                await self.cache.set(cache_key, prices, self.cache_duration)
                logger.info(f"Fetched and cached prices for {len(prices)} symbols")
                
                return prices
                
        except Exception as e:
            logger.error(f"Error fetching prices: {e}")
            return {}
    
    async def _fetch_price(self, session: aiohttp.ClientSession, symbol: str) -> Optional[float]:
        """Fetch price for a single symbol"""
        try:
            url = f"{self.api_url}/ticker/price?symbol={symbol}"
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return float(data['price'])
                else:
                    logger.warning(f"API returned status {response.status} for {symbol}")
                    return None
        except asyncio.TimeoutError:
            logger.warning(f"Timeout fetching price for {symbol}")
            return None
        except Exception as e:
            logger.warning(f"Error fetching price for {symbol}: {e}")
            return None
    
    async def get_price_history(self, symbol: str, limit: int = 100) -> List[Dict]:
        """Get price history for a symbol"""
        cache_key = f"price_history:{symbol}:{limit}"
        cached_history = await self.cache.get(cache_key)
        if cached_history:
            return cached_history
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_url}/klines"
                params = {
                    'symbol': f"{symbol.upper()}USDT",
                    'interval': '1h',
                    'limit': limit
                }
                
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        history = [
                            {
                                'timestamp': int(candle[0]),
                                'open': float(candle[1]),
                                'high': float(candle[2]),
                                'low': float(candle[3]),
                                'close': float(candle[4]),
                                'volume': float(candle[5])
                            }
                            for candle in data
                        ]
                        
                        # Cache for 5 minutes
                        await self.cache.set(cache_key, history, 300)
                        return history
                    else:
                        logger.warning(f"API returned status {response.status} for {symbol} history")
                        return []
                        
        except Exception as e:
            logger.error(f"Error fetching price history for {symbol}: {e}")
            return []
    
    async def get_24h_stats(self, symbols: List[str]) -> Dict[str, Dict]:
        """Get 24-hour statistics for symbols"""
        if not symbols:
            return {}
        
        cache_key = f"24h_stats:{':'.join(sorted(symbols))}"
        cached_stats = await self.cache.get(cache_key)
        if cached_stats:
            return cached_stats
        
        try:
            async with aiohttp.ClientSession() as session:
                # Create symbol list for Binance API
                symbol_list = [f"{symbol.upper()}USDT" for symbol in symbols]
                
                # Fetch all 24h stats in one request
                url = f"{self.api_url}/ticker/24hr"
                params = {'symbols': json.dumps(symbol_list)}
                
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        stats = {}
                        for item in data:
                            base_symbol = item['symbol'].replace('USDT', '')
                            stats[base_symbol] = {
                                'price_change': float(item['priceChange']),
                                'price_change_percent': float(item['priceChangePercent']),
                                'volume': float(item['volume']),
                                'count': int(item['count'])
                            }
                        
                        # Cache for 1 minute
                        await self.cache.set(cache_key, stats, 60)
                        return stats
                    else:
                        logger.warning(f"API returned status {response.status} for 24h stats")
                        return {}
                        
        except Exception as e:
            logger.error(f"Error fetching 24h stats: {e}")
            return {}
