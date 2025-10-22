import httpx
import asyncio
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class CurrencyService:
    def __init__(self):
        self.rates: Dict[str, float] = {}
        self.base_currency = "USD"
        self.last_updated = None
        
    async def get_exchange_rates(self) -> Dict[str, float]:
        """Fetch current exchange rates from a free API"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Using exchangerate-api.com (free tier: 1500 requests/month)
                response = await client.get("https://api.exchangerate-api.com/v4/latest/USD")
                response.raise_for_status()
                data = response.json()
                
                self.rates = data.get("rates", {})
                self.last_updated = data.get("date")
                
                logger.info(f"Updated exchange rates for {len(self.rates)} currencies")
                return self.rates
                
        except Exception as e:
            logger.error(f"Failed to fetch exchange rates: {e}")
            # Fallback to static rates if API fails
            return self.get_fallback_rates()
    
    def get_fallback_rates(self) -> Dict[str, float]:
        """Fallback rates if API is unavailable"""
        return {
            "USD": 1.0,
            "EUR": 0.85,
            "CZK": 23.5,
            "GBP": 0.73,
            "JPY": 110.0
        }
    
    def convert_amount(self, amount: float, from_currency: str, to_currency: str) -> float:
        """Convert amount from one currency to another"""
        if from_currency == to_currency:
            return amount
            
        if not self.rates:
            logger.warning("No exchange rates available, using fallback")
            self.rates = self.get_fallback_rates()
        
        # Convert to USD first, then to target currency
        if from_currency != "USD":
            usd_amount = amount / self.rates.get(from_currency, 1.0)
        else:
            usd_amount = amount
            
        if to_currency != "USD":
            converted_amount = usd_amount * self.rates.get(to_currency, 1.0)
        else:
            converted_amount = usd_amount
            
        return round(converted_amount, 8)
    
    async def refresh_rates(self):
        """Refresh exchange rates"""
        await self.get_exchange_rates()

# Global currency service instance
currency_service = CurrencyService()