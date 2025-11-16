import aiohttp
import asyncio
import json
import ssl
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from ..core.config import settings
from ..utils.time_utils import get_current_timestamp
from ..utils.logger import get_logger

logger = get_logger("backend.app.services.multi_exchange_price_service")


class MultiExchangePriceService:
    """Multi-exchange price service with fallback chain: CoinGecko -> Coinbase -> Binance -> Bitfinex"""
    
    def __init__(self):
        self.coingecko_url = "https://api.coingecko.com/api/v3"
        self.coinbase_url = "https://api.coinbase.com"
        self.binance_url = "https://api.binance.com"
        self.bitfinex_url = "https://api-pub.bitfinex.com"
        self.last_updated_timestamps: Dict[str, datetime] = {}
        self.last_bulk_update = None
        
        # Known fiat currencies that should never be fetched as crypto prices
        self.fiat_currencies = {
            'USDT', 'USD', 'EUR', 'GBP', 'JPY', 'CZK', 'CAD', 'AUD', 'CHF', 
            'SEK', 'NOK', 'DKK', 'PLN', 'HUF', 'RUB', 'CNY', 'KRW', 'SGD', 
            'HKD', 'NZD', 'TRY', 'BRL', 'MXN', 'INR', 'ZAR', 'THB', 'MYR', 
            'PHP', 'IDR', 'VND', 'USDC', 'BUSD', 'TUSD', 'DAI', 'FRAX', 
            'LUSD', 'SUSD', 'GUSD', 'USDP', 'USDD'
        }
    
    async def get_current_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Get current prices for multiple symbols using multi-exchange fallback"""
        if not symbols:
            return {}
        
        # Filter out fiat currencies
        crypto_symbols = [s.upper() for s in symbols if s.upper() not in self.fiat_currencies]
        
        if not crypto_symbols:
            logger.debug(f"No crypto symbols found in input: {symbols}")
            return {}
        
        logger.debug(f"Fetching prices for {len(crypto_symbols)} symbols using multi-exchange fallback")
        
        # Try each exchange in order: CoinGecko -> Coinbase -> Binance -> Bitfinex
        prices = {}
        remaining_symbols = crypto_symbols.copy()
        
        # 1. Try CoinGecko first
        coingecko_prices, coingecko_failed = await self._fetch_from_coingecko(remaining_symbols)
        prices.update(coingecko_prices)
        remaining_symbols = [s for s in remaining_symbols if s not in coingecko_prices]
        
        if remaining_symbols:
            logger.debug(f"CoinGecko failed for {len(remaining_symbols)} symbols, trying Coinbase: {remaining_symbols}")
            
            # 2. Try Coinbase for remaining symbols
            coinbase_prices, coinbase_failed = await self._fetch_from_coinbase(remaining_symbols)
            prices.update(coinbase_prices)
            remaining_symbols = [s for s in remaining_symbols if s not in coinbase_prices]
            
            if remaining_symbols:
                logger.debug(f"Coinbase failed for {len(remaining_symbols)} symbols, trying Binance: {remaining_symbols}")
                
                # 3. Try Binance for remaining symbols
                binance_prices, binance_failed = await self._fetch_from_binance(remaining_symbols)
                prices.update(binance_prices)
                remaining_symbols = [s for s in remaining_symbols if s not in binance_prices]
                
                if remaining_symbols:
                    logger.debug(f"Binance failed for {len(remaining_symbols)} symbols, trying Bitfinex: {remaining_symbols}")
                    
                    # 4. Try Bitfinex for remaining symbols
                    bitfinex_prices, bitfinex_failed = await self._fetch_from_bitfinex(remaining_symbols)
                    prices.update(bitfinex_prices)
                    remaining_symbols = [s for s in remaining_symbols if s not in bitfinex_prices]
                    
                    if remaining_symbols:
                        logger.warning(f"All exchanges failed for {len(remaining_symbols)} symbols: {remaining_symbols}")
        
        # Update timestamps
        current_time = get_current_timestamp()
        self.last_bulk_update = current_time
        for symbol in prices:
            self.last_updated_timestamps[symbol] = current_time
        
        logger.debug(f"Successfully fetched prices for {len(prices)} symbols")
        return prices
    
    async def _fetch_from_coingecko(self, symbols: List[str]) -> Tuple[Dict[str, float], List[str]]:
        """Fetch prices from CoinGecko API using /coins/markets endpoint"""
        prices = {}
        failed_symbols = []
        
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                # CoinGecko /coins/markets endpoint supports filtering by symbol
                # We'll fetch up to 250 coins per request (CoinGecko limit)
                # Filter by symbols we need
                symbols_lower = [s.lower() for s in symbols]
                
                # Fetch prices using markets endpoint with vs_currency=usd
                # Note: This endpoint doesn't directly filter by symbol, so we fetch and filter
                url = f"{self.coingecko_url}/coins/markets"
                params = {
                    'vs_currency': 'usd',
                    'per_page': 250,
                    'page': 1
                }
                
                async with session.get(url, params=params, timeout=15) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Create a mapping of symbol (lowercase) to price
                        symbol_to_price = {}
                        for coin in data:
                            if 'symbol' in coin and 'current_price' in coin:
                                coin_symbol = coin['symbol'].upper()
                                if coin_symbol in symbols:
                                    symbol_to_price[coin_symbol] = float(coin['current_price'])
                        
                        # Map prices back to requested symbols
                        for symbol in symbols:
                            if symbol in symbol_to_price:
                                prices[symbol] = symbol_to_price[symbol]
                            else:
                                failed_symbols.append(symbol)
                        
                        # If we have missing symbols, try fetching more pages
                        if failed_symbols and len(data) == 250:
                            # Try page 2 for missing symbols
                            params['page'] = 2
                            async with session.get(url, params=params, timeout=15) as response2:
                                if response2.status == 200:
                                    data2 = await response2.json()
                                    for coin in data2:
                                        if 'symbol' in coin and 'current_price' in coin:
                                            coin_symbol = coin['symbol'].upper()
                                            if coin_symbol in failed_symbols:
                                                prices[coin_symbol] = float(coin['current_price'])
                                                failed_symbols.remove(coin_symbol)
                    elif response.status == 429:
                        # Rate limit - log and mark all as failed
                        logger.warning("CoinGecko rate limit hit, will try other exchanges")
                        failed_symbols = symbols.copy()
                    else:
                        error_text = await response.text()
                        logger.debug(f"CoinGecko API returned status {response.status}: {error_text[:200]}")
                        failed_symbols = symbols.copy()
        
        except Exception as e:
            logger.error(f"Error fetching from CoinGecko: {e}", exc_info=True)
            failed_symbols = symbols.copy()
        
        logger.info(f"CoinGecko: {len(prices)} successful, {len(failed_symbols)} failed")
        return prices, failed_symbols
    
    async def _fetch_from_binance(self, symbols: List[str]) -> Tuple[Dict[str, float], List[str]]:
        """Fetch prices from Binance API"""
        prices = {}
        failed_symbols = []
        
        try:
            # Create symbol pairs for Binance (e.g., BTCUSDT)
            symbol_pairs = [f"{symbol}USDT" for symbol in symbols]
            
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                tasks = [
                    self._fetch_binance_price(session, symbol, symbol_pair)
                    for symbol, symbol_pair in zip(symbols, symbol_pairs)
                ]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.debug(f"Binance failed for {symbols[i]}: {result}")
                        failed_symbols.append(symbols[i])
                    elif result is not None:
                        prices[symbols[i]] = result
                    else:
                        failed_symbols.append(symbols[i])
        
        except Exception as e:
            logger.error(f"Error fetching from Binance: {e}")
            failed_symbols = symbols.copy()
        
        logger.info(f"Binance: {len(prices)} successful, {len(failed_symbols)} failed")
        return prices, failed_symbols
    
    async def _fetch_from_bitfinex(self, symbols: List[str]) -> Tuple[Dict[str, float], List[str]]:
        """Fetch prices from Bitfinex API"""
        prices = {}
        failed_symbols = []
        
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                tasks = [
                    self._fetch_bitfinex_price(session, symbol)
                    for symbol in symbols
                ]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.debug(f"Bitfinex failed for {symbols[i]}: {result}")
                        failed_symbols.append(symbols[i])
                    elif result is not None:
                        prices[symbols[i]] = result
                    else:
                        failed_symbols.append(symbols[i])
        
        except Exception as e:
            logger.error(f"Error fetching from Bitfinex: {e}")
            failed_symbols = symbols.copy()
        
        logger.info(f"Bitfinex: {len(prices)} successful, {len(failed_symbols)} failed")
        return prices, failed_symbols
    
    async def _fetch_from_coinbase(self, symbols: List[str]) -> Tuple[Dict[str, float], List[str]]:
        """Fetch prices from Coinbase API"""
        prices = {}
        failed_symbols = []
        
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                tasks = [
                    self._fetch_coinbase_price(session, symbol)
                    for symbol in symbols
                ]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.debug(f"Coinbase failed for {symbols[i]}: {result}")
                        failed_symbols.append(symbols[i])
                    elif result is not None:
                        prices[symbols[i]] = result
                    else:
                        failed_symbols.append(symbols[i])
        
        except Exception as e:
            logger.error(f"Error fetching from Coinbase: {e}")
            failed_symbols = symbols.copy()
        
        logger.info(f"Coinbase: {len(prices)} successful, {len(failed_symbols)} failed")
        return prices, failed_symbols
    
    async def _fetch_binance_price(self, session: aiohttp.ClientSession, symbol: str, symbol_pair: str) -> Optional[float]:
        """Fetch price from Binance for a specific symbol"""
        try:
            url = f"{self.binance_url}/api/v3/ticker/price?symbol={symbol_pair}"
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return float(data['price'])
                else:
                    logger.debug(f"Binance API returned status {response.status} for {symbol_pair}")
                    return None
        except Exception as e:
            logger.debug(f"Binance error for {symbol}: {e}")
            return None
    
    async def _fetch_bitfinex_price(self, session: aiohttp.ClientSession, symbol: str) -> Optional[float]:
        """Fetch price from Bitfinex for a specific symbol"""
        try:
            # Bitfinex uses different symbol format (e.g., tBTCUSD)
            bitfinex_symbol = f"t{symbol}USD"
            url = f"{self.bitfinex_url}/v2/ticker/{bitfinex_symbol}"
            
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    # Bitfinex returns an array, price is at index 6 (last price)
                    if isinstance(data, list) and len(data) > 6:
                        return float(data[6])
                    return None
                else:
                    logger.debug(f"Bitfinex API returned status {response.status} for {bitfinex_symbol}")
                    return None
        except Exception as e:
            logger.debug(f"Bitfinex error for {symbol}: {e}")
            return None
    
    async def _fetch_coinbase_price(self, session: aiohttp.ClientSession, symbol: str) -> Optional[float]:
        """Fetch price from Coinbase for a specific symbol"""
        try:
            # Coinbase uses different symbol format (e.g., BTC-USD)
            coinbase_symbol = f"{symbol}-USD"
            url = f"{self.coinbase_url}/v2/prices/{coinbase_symbol}/spot"
            
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'data' in data and 'amount' in data['data']:
                        return float(data['data']['amount'])
                    return None
                else:
                    logger.debug(f"Coinbase API returned status {response.status} for {coinbase_symbol}")
                    return None
        except Exception as e:
            logger.debug(f"Coinbase error for {symbol}: {e}")
            return None


# Create global instance
multi_exchange_price_service = MultiExchangePriceService()
