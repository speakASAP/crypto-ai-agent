import httpx
import asyncio
from typing import Dict, Optional
import logging
import psycopg
import json
import redis
from datetime import datetime, timezone
from ..core.config import settings
from ..utils.time_utils import format_timestamp, get_iso_timestamp, get_current_timestamp

logger = logging.getLogger(__name__)

class CurrencyService:
    def __init__(self):
        self.rates: Dict[str, float] = {}
        self.base_currency = "USD"
        self.last_updated = None
        self.last_updated_timestamp = None
        self._redis = None
        if settings.redis_url:
            try:
                self._redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            except Exception:
                self._redis = None
    
    def _save_rates_to_db(self, rates: Dict[str, float], timestamp: str):
        """Save exchange rates to PostgreSQL database"""
        try:
            # Save to Redis if configured
            if self._redis:
                payload = {"rates": rates, "timestamp": timestamp}
                self._redis.set("currency:USD", json.dumps(payload), ex=settings.currency_cache_duration)
            
            pg_url = settings.database_url.replace("+psycopg", "") if "+psycopg" in settings.database_url else settings.database_url
            with psycopg.connect(pg_url) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM currency_rates")
                    for currency, rate in rates.items():
                        cursor.execute(
                            "INSERT INTO currency_rates (from_currency, to_currency, rate, timestamp) VALUES (%s, %s, %s, %s)",
                            ("USD", currency, rate, timestamp)
                        )
                    conn.commit()
            logger.info(f"Saved {len(rates)} currency rates to database")
            
        except Exception as e:
            logger.error(f"Failed to save rates to database: {e}")
    
    def _load_rates_from_db(self) -> Dict[str, float]:
        """Load exchange rates from PostgreSQL database"""
        try:
            # Try Redis first
            if self._redis:
                cached = self._redis.get("currency:USD")
                if cached:
                    obj = json.loads(cached)
                    self.last_updated = obj.get("timestamp")
                    self.last_updated_timestamp = get_current_timestamp()
                    return obj.get("rates", {})
            
            pg_url = settings.database_url.replace("+psycopg", "") if "+psycopg" in settings.database_url else settings.database_url
            with psycopg.connect(pg_url) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT to_currency, rate, timestamp FROM currency_rates WHERE from_currency = 'USD' ORDER BY timestamp DESC"
                    )
                    rows = cursor.fetchall()

            rates = {}
            for currency, rate, timestamp in rows:
                rates[currency] = rate
                if not self.last_updated:
                    self.last_updated = timestamp
            
            if rates:
                logger.info(f"Loaded {len(rates)} currency rates from database")
                self.last_updated_timestamp = get_current_timestamp()
            
            return rates
            
        except Exception as e:
            logger.error(f"Failed to load rates from database: {e}")
            return {}
        
    async def get_exchange_rates(self) -> Dict[str, float]:
        """Fetch current exchange rates from a free API"""
        try:
            # Cache hit from Redis
            if self._redis:
                cached = self._redis.get("currency:USD")
                if cached:
                    obj = json.loads(cached)
                    self.rates = obj.get("rates", {})
                    self.last_updated = obj.get("timestamp")
                    self.last_updated_timestamp = get_current_timestamp()
                    logger.info(f"Using cached exchange rates ({len(self.rates)}) from Redis")
                    return self.rates
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Using exchangerate-api.com (free tier: 1500 requests/month)
                response = await client.get(settings.currency_api_url)
                response.raise_for_status()
                data = response.json()
                
                self.rates = data.get("rates", {})
                self.last_updated = data.get("date")
                # Store precise timestamp with timezone
                self.last_updated_timestamp = get_current_timestamp()
                
                # Save rates to database
                self._save_rates_to_db(self.rates, self.last_updated)
                
                logger.info(f"Updated exchange rates for {len(self.rates)} currencies at {self.last_updated_timestamp}")
                return self.rates
                
        except Exception as e:
            logger.error(f"Failed to fetch exchange rates: {e}")
            # Try to load from database first, then fallback to static rates
            db_rates = self._load_rates_from_db()
            if db_rates:
                self.rates = db_rates
                return db_rates
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
        
        # Handle USDT as a stablecoin (always 1.0 to USD)
        if from_currency == "USDT" and to_currency == "USD":
            return amount
        if from_currency == "USD" and to_currency == "USDT":
            return amount
            
        # Ensure we have rates before conversion
        if not self.rates:
            logger.warning("No exchange rates available, loading from database")
            db_rates = self._load_rates_from_db()
            if db_rates:
                self.rates = db_rates
            else:
                logger.warning("No rates in database, using fallback rates")
                self.rates = self.get_fallback_rates()
        
        # Validate that we have the required currency rates (skip USDT as it's a stablecoin)
        if from_currency != "USD" and from_currency != "USDT" and from_currency not in self.rates:
            logger.error(f"Missing exchange rate for {from_currency}, using fallback")
            self.rates[from_currency] = self.get_fallback_rates().get(from_currency, 1.0)
            
        if to_currency != "USD" and to_currency != "USDT" and to_currency not in self.rates:
            logger.error(f"Missing exchange rate for {to_currency}, using fallback")
            self.rates[to_currency] = self.get_fallback_rates().get(to_currency, 1.0)
        
        # Handle USDT as intermediate currency
        if from_currency == "USDT":
            usd_amount = amount  # USDT is 1:1 with USD
        elif from_currency != "USD":
            usd_amount = amount / self.rates.get(from_currency, 1.0)
        else:
            usd_amount = amount
            
        if to_currency == "USDT":
            converted_amount = usd_amount  # USDT is 1:1 with USD
        elif to_currency != "USD":
            converted_amount = usd_amount * self.rates.get(to_currency, 1.0)
        else:
            converted_amount = usd_amount
            
        return round(converted_amount, 8)
    
    async def refresh_rates(self):
        """Refresh exchange rates"""
        await self.get_exchange_rates()
    
    def ensure_rates_initialized(self):
        """Ensure rates are initialized, loading from database first, then fallback if needed"""
        if not self.rates:
            logger.info("Initializing currency rates from database")
            db_rates = self._load_rates_from_db()
            if db_rates:
                self.rates = db_rates
                logger.info("Loaded currency rates from database")
            else:
                logger.info("No rates in database, using fallback values")
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
        if currency == "USD" or currency == "USDT":
            return 1.0
        
        if not self.rates:
            self.ensure_rates_initialized()
            
        return self.rates.get(currency, self.get_fallback_rates().get(currency, 1.0))

# Global currency service instance
currency_service = CurrencyService()


async def background_currency_fetcher():
    """Background task to periodically fetch currency rates"""
    import asyncio
    try:
        from ..utils.logger import get_logger
    except Exception:  # pragma: no cover
        from utils.logger import get_logger

    logger = get_logger("backend.app.services.currency_service")

    while True:
        try:
            await currency_service.refresh_rates()
            logger.info("Currency rates refreshed")
        except Exception as e:
            logger.error(f"Error refreshing currency rates: {e}")

        # Wait 30 minutes before next fetch
        await asyncio.sleep(1800)
