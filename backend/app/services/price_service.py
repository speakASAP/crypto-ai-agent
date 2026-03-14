import aiohttp
import asyncio
import json
import ssl
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime, timezone
from ..core.config import settings
from ..utils.time_utils import format_timestamp, get_iso_timestamp, get_current_timestamp
from ..utils.logger import get_logger

logger = get_logger("backend.app.services.price_service")


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
        
        # Filter out invalid symbols and create symbol list for Binance API
        valid_symbols = []
        symbol_list = []
        
        # Known fiat currencies that should never be fetched as crypto prices
        fiat_currencies = {'USDT', 'USD', 'EUR', 'GBP', 'JPY', 'CZK', 'CAD', 'AUD', 'CHF', 'SEK', 'NOK', 'DKK', 'PLN', 'HUF', 'RUB', 'CNY', 'KRW', 'SGD', 'HKD', 'NZD', 'TRY', 'BRL', 'MXN', 'INR', 'ZAR', 'THB', 'MYR', 'PHP', 'IDR', 'VND'}
        
        # Known invalid/problematic symbols that don't exist on Binance
        invalid_symbols = {'USDC', 'BUSD', 'TUSD', 'DAI', 'FRAX', 'LUSD', 'SUSD', 'GUSD', 'USDP', 'USDD', 'UST', 'USTC', 'LUNA', 'LUNA2', 'LUNC'}
        
        for symbol in symbols:
            symbol_upper = symbol.upper()
            
            # Skip fiat currencies
            if symbol_upper in fiat_currencies:
                logger.debug(f"Skipping fiat currency {symbol_upper}")
                continue
                
            # Skip known invalid symbols
            if symbol_upper in invalid_symbols:
                logger.debug(f"Skipping invalid/problematic symbol {symbol_upper}")
                continue
                
            # Skip symbols that end with USDT (invalid pairs)
            if symbol_upper.endswith('USDT') and symbol_upper != 'USDT':
                logger.debug(f"Skipping invalid pair {symbol_upper}")
                continue
            
            # Skip very short or very long symbols (likely invalid)
            if len(symbol_upper) < 2 or len(symbol_upper) > 10:
                logger.debug(f"Skipping symbol with invalid length {symbol_upper}")
                continue
            
            valid_symbols.append(symbol_upper)
            symbol_list.append(f"{symbol_upper}USDT")
        
        if not valid_symbols:
            logger.debug(f"No valid symbols found in input: {symbols}")
            return {}
        
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
                current_time = get_current_timestamp()
                self.last_bulk_update = current_time
                
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.warning(f"Failed to fetch price for {symbol_list[i]}: {result}")
                        continue
                    if result:
                        base_symbol = valid_symbols[i]
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
            logger.error(f"Timeout fetching price for {symbol} (connectivity or slow execution)")
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
    
    async def get_historical_prices_for_range(
        self, 
        symbol: str, 
        start_timestamp: int, 
        end_timestamp: int
    ) -> List[Dict]:
        """Get historical prices between two timestamps using Binance klines API"""
        try:
            # Create SSL context that doesn't verify certificates
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                # Determine interval based on time range
                time_diff = end_timestamp - start_timestamp
                if time_diff <= 24 * 60 * 60 * 1000:  # Less than 24 hours
                    interval = '1m'  # 1-minute candles for precision
                else:
                    interval = '1h'  # 1-hour candles for longer periods
                
                url = f"{self.api_url}/klines"
                params = {
                    'symbol': f"{symbol.upper()}USDT",
                    'interval': interval,
                    'startTime': start_timestamp,
                    'endTime': end_timestamp,
                    'limit': 1000  # Maximum allowed by Binance
                }
                
                async with session.get(url, params=params, timeout=30) as response:
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
                        
                        logger.info(f"Fetched {len(history)} historical price points for {symbol} from {start_timestamp} to {end_timestamp}")
                        return history
                    else:
                        logger.warning(f"API returned status {response.status} for {symbol} historical data")
                        return []
                        
        except Exception as e:
            logger.error(f"Error fetching historical prices for {symbol}: {e}")
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
        return format_timestamp(timestamp)
    
    def get_timestamp_iso(self, symbol: str = None) -> str:
        """Get ISO format timestamp for API responses"""
        timestamp = self.get_last_update_timestamp(symbol)
        return get_iso_timestamp(timestamp)
    
    def get_all_symbol_timestamps(self) -> Dict[str, str]:
        """Get all symbol timestamps in ISO format"""
        return {
            symbol: get_iso_timestamp(timestamp) 
            for symbol, timestamp in self.last_updated_timestamps.items()
        }
    
    def get_price_from_db(self, symbol: str) -> Optional[float]:
        """Get price for a symbol from crypto_prices table"""
        try:
            from ..utils.db import get_db_connection, normalize_placeholders
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            sql = normalize_placeholders(
                "SELECT price_usd FROM crypto_prices WHERE symbol = %s"
            )
            cursor.execute(sql, (symbol.upper(),))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return float(row[0])
            return None
        except Exception as e:
            logger.error(f"Error getting price from database for {symbol}: {e}")
            return None
    
    def get_prices_from_db(self, symbols: List[str]) -> Dict[str, float]:
        """Get prices for multiple symbols from crypto_prices table"""
        if not symbols:
            return {}
        
        try:
            from ..utils.db import get_db_connection, normalize_placeholders
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Create placeholders for IN clause
            placeholders = ','.join(['%s'] * len(symbols))
            sql = normalize_placeholders(
                f"SELECT symbol, price_usd FROM crypto_prices WHERE symbol IN ({placeholders})"
            )
            cursor.execute(sql, [s.upper() for s in symbols])
            rows = cursor.fetchall()
            conn.close()
            
            prices = {}
            for row in rows:
                prices[row[0]] = float(row[1])
            
            return prices
        except Exception as e:
            logger.error(f"Error getting prices from database: {e}")
            return {}
