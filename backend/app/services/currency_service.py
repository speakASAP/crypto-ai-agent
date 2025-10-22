import aiohttp
import logging
from typing import Dict, Optional
from decimal import Decimal
from app.core.config import settings
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class CurrencyService:
    def __init__(self, cache: CacheService):
        self.cache = cache
        self.api_url = settings.currency_api_url
        self.cache_duration = settings.currency_cache_duration
        
        # Fallback rates
        self.fallback_rates = {
            'EUR': Decimal('0.85'),
            'CZK': Decimal('23.5')
        }
    
    async def get_exchange_rates(self, base_currency: str = 'USD') -> Dict[str, Decimal]:
        """Get current exchange rates"""
        cache_key = f"exchange_rates:{base_currency}"
        cached_rates = await self.cache.get(cache_key)
        if cached_rates:
            logger.debug(f"Retrieved exchange rates from cache for {base_currency}")
            return {k: Decimal(str(v)) for k, v in cached_rates.items()}
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_url}/{base_currency}"
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        rates = {
                            currency: Decimal(str(rate))
                            for currency, rate in data.get('rates', {}).items()
                            if currency in ['EUR', 'CZK', 'USD']
                        }
                        
                        # Add base currency
                        rates[base_currency] = Decimal('1.0')
                        
                        # Cache the rates
                        await self.cache.set(cache_key, {k: str(v) for k, v in rates.items()}, self.cache_duration)
                        logger.info(f"Fetched and cached exchange rates for {base_currency}")
                        
                        return rates
                    else:
                        logger.warning(f"Currency API returned status {response.status}")
                        return self._get_fallback_rates()
                        
        except Exception as e:
            logger.error(f"Error fetching exchange rates: {e}")
            return self._get_fallback_rates()
    
    def _get_fallback_rates(self) -> Dict[str, Decimal]:
        """Get fallback exchange rates"""
        logger.warning("Using fallback exchange rates")
        return {
            'USD': Decimal('1.0'),
            'EUR': self.fallback_rates['EUR'],
            'CZK': self.fallback_rates['CZK']
        }
    
    async def convert_currency(self, amount: Decimal, from_currency: str, to_currency: str) -> Decimal:
        """Convert amount from one currency to another"""
        if from_currency == to_currency:
            return amount
        
        rates = await self.get_exchange_rates()
        
        # Convert to USD first if needed
        if from_currency != 'USD':
            if from_currency not in rates:
                logger.error(f"Unknown currency: {from_currency}")
                return amount
            usd_amount = amount / rates[from_currency]
        else:
            usd_amount = amount
        
        # Convert from USD to target currency
        if to_currency != 'USD':
            if to_currency not in rates:
                logger.error(f"Unknown currency: {to_currency}")
                return usd_amount
            return usd_amount * rates[to_currency]
        
        return usd_amount
    
    async def get_portfolio_value(self, portfolio_items: list, target_currency: str = 'USD') -> Dict[str, Decimal]:
        """Calculate portfolio value in target currency"""
        if not portfolio_items:
            return {'total_value': Decimal('0'), 'total_pnl': Decimal('0'), 'total_pnl_percent': Decimal('0')}
        
        # Get current prices for all symbols
        symbols = list(set(item['symbol'] for item in portfolio_items))
        from app.services.price_service import PriceService
        price_service = PriceService(self.cache)
        current_prices = await price_service.get_current_prices(symbols)
        
        total_value = Decimal('0')
        total_cost = Decimal('0')
        
        for item in portfolio_items:
            symbol = item['symbol']
            amount = Decimal(str(item['amount']))
            price_buy = Decimal(str(item['price_buy']))
            base_currency = item['base_currency']
            
            # Convert purchase price to target currency
            cost_in_target = await self.convert_currency(amount * price_buy, base_currency, target_currency)
            total_cost += cost_in_target
            
            # Get current value
            if symbol in current_prices:
                current_price = Decimal(str(current_prices[symbol]))
                current_value = await self.convert_currency(amount * current_price, 'USD', target_currency)
                total_value += current_value
            else:
                # If no current price, use purchase price
                total_value += cost_in_target
        
        total_pnl = total_value - total_cost
        total_pnl_percent = (total_pnl / total_cost * 100) if total_cost > 0 else Decimal('0')
        
        return {
            'total_value': total_value,
            'total_cost': total_cost,
            'total_pnl': total_pnl,
            'total_pnl_percent': total_pnl_percent
        }
