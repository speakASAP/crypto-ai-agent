import httpx
import asyncio
from typing import Dict, Optional
import logging
from datetime import datetime, timezone
from app.core.config import settings
from app.utils.time_utils import format_timestamp, get_iso_timestamp, get_current_timestamp

logger = logging.getLogger(__name__)

class CurrencyService:
    def __init__(self):
        self.rates: Dict[str, float] = {}
        self.base_currency = "USD"
        self.last_updated = None
        self.last_updated_timestamp = None
        
    async def get_exchange_rates(self) -> Dict[str, float]:
        """Fetch current exchange rates from a free API"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Using exchangerate-api.com (free tier: 1500 requests/month)
                response = await client.get(settings.currency_api_url)
                response.raise_for_status()
                data = response.json()
                
                self.rates = data.get("rates", {})
                self.last_updated = data.get("date")
                # Store precise timestamp with timezone
                self.last_updated_timestamp = get_current_timestamp()
                
                logger.info(f"Updated exchange rates for {len(self.rates)} currencies at {self.last_updated_timestamp}")
                return self.rates
                
        except Exception as e:
            logger.error(f"Failed to fetch exchange rates: {e}")
            # Fallback to static rates if API fails
            return self.get_fallback_rates()
    
    def get_fallback_rates(self) -> Dict[str, float]:
        """Fallback rates if API is unavailable"""
        # Set timestamp for fallback rates too
        self.last_updated_timestamp = get_current_timestamp()
        return {
            "USD": 1.0,
            "EUR": 0.85,
            "CZK": 20.94,  # Updated to match current market rate
            "GBP": 0.73,
            "JPY": 110.0
        }
    
    def convert_amount(self, amount: float, from_currency: str, to_currency: str) -> float:
        """Convert amount from one currency to another"""
        if from_currency == to_currency:
            return amount
            
        # Ensure we have rates before conversion
        if not self.rates:
            logger.warning("No exchange rates available, initializing with fallback rates")
            self.rates = self.get_fallback_rates()
        
        # Validate that we have the required currency rates
        if from_currency != "USD" and from_currency not in self.rates:
            logger.error(f"Missing exchange rate for {from_currency}, using fallback")
            self.rates[from_currency] = self.get_fallback_rates().get(from_currency, 1.0)
            
        if to_currency != "USD" and to_currency not in self.rates:
            logger.error(f"Missing exchange rate for {to_currency}, using fallback")
            self.rates[to_currency] = self.get_fallback_rates().get(to_currency, 1.0)
        
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
    
    def ensure_rates_initialized(self):
        """Ensure rates are initialized, using fallback if needed"""
        if not self.rates:
            logger.info("Initializing currency rates with fallback values")
            self.rates = self.get_fallback_rates()
        return self.rates
    
    def get_formatted_timestamp(self) -> str:
        """Get formatted timestamp for display"""
        if self.last_updated_timestamp:
            return format_timestamp(self.last_updated_timestamp)
        elif self.last_updated:
            return f"{self.last_updated} (date only)"
        else:
            return "Never updated"
    
    def get_timestamp_iso(self) -> str:
        """Get ISO format timestamp for API responses"""
        return get_iso_timestamp(self.last_updated_timestamp)
    
    def get_rate(self, currency: str) -> float:
        """Get exchange rate for a currency, with fallback"""
        if currency == "USD":
            return 1.0
        
        if not self.rates:
            self.ensure_rates_initialized()
            
        return self.rates.get(currency, self.get_fallback_rates().get(currency, 1.0))

# Global currency service instance
currency_service = CurrencyService()