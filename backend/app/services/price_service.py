import aiohttp
import asyncio
import json
import logging
import ssl
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime, timezone
from app.core.config import settings

logger = logging.getLogger(__name__)


class PriceService:
    def __init__(self):
        # Handle the case where .env might have the wrong URL format
        api_url = settings.binance_api_url
        if api_url.endswith('/ticker/price'):
            api_url = api_url.replace('/ticker/price', '')
        self.api_url = api_url
        self.last_updated_timestamps: Dict[str, datetime] = {}
        self.last_bulk_update = None
    
    async def get_current_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Get current prices for multiple symbols in parallel"""
        if not symbols:
            return {}
        
        # Create symbol list for Binance API
        symbol_list = [f"{symbol.upper()}USDT" for symbol in symbols]
        
        try:
            # Create SSL context that doesn't verify certificates
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                # Create tasks for parallel execution
                tasks = [
                    self._fetch_price(session, symbol)
                    for symbol in symbol_list
                ]
                
                # Execute all tasks in parallel
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                prices = {}
                current_time = datetime.now(timezone.utc)
                self.last_bulk_update = current_time
                
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.warning(f"Failed to fetch price for {symbol_list[i]}: {result}")
                        continue
                    if result:
                        base_symbol = symbol_list[i].replace('USDT', '')
                        prices[base_symbol] = result
                        # Track individual symbol update time
                        self.last_updated_timestamps[base_symbol] = current_time
                
                logger.info(f"Fetched prices for {len(prices)} symbols at {current_time}")
                
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
        
        try:
            # Create SSL context that doesn't verify certificates
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
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
        
        try:
            # Create SSL context that doesn't verify certificates
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
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
                        
                        return stats
                    else:
                        logger.warning(f"API returned status {response.status} for 24h stats")
                        return {}
                        
        except Exception as e:
            logger.error(f"Error fetching 24h stats: {e}")
            return {}
    
    def get_last_update_timestamp(self, symbol: str = None) -> Optional[datetime]:
        """Get last update timestamp for a specific symbol or bulk update"""
        if symbol:
            return self.last_updated_timestamps.get(symbol)
        return self.last_bulk_update
    
    def get_formatted_timestamp(self, symbol: str = None) -> str:
        """Get formatted timestamp for display"""
        timestamp = self.get_last_update_timestamp(symbol)
        if timestamp:
            return timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
        else:
            return "Never updated"
    
    def get_timestamp_iso(self, symbol: str = None) -> str:
        """Get ISO format timestamp for API responses"""
        timestamp = self.get_last_update_timestamp(symbol)
        if timestamp:
            return timestamp.isoformat()
        else:
            return datetime.now(timezone.utc).isoformat()
    
    def get_all_symbol_timestamps(self) -> Dict[str, str]:
        """Get all symbol timestamps in ISO format"""
        return {
            symbol: timestamp.isoformat() 
            for symbol, timestamp in self.last_updated_timestamps.items()
        }
