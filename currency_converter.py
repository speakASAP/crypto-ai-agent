"""
Currency Converter Utility for Multi-Currency Portfolio Support
Handles currency conversion between USD, EUR, and CZK
"""

import asyncio
import aiohttp
import aiosqlite
import os
import time
import ssl
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import sys

# Add utils directory to path for centralized logging
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))
from utils.logger import (
    get_logger, log_function_entry, log_function_exit, log_database_operation,
    log_api_call, log_performance, log_error_with_context,
    log_warning_with_context, log_info_with_context, log_performance_timing
)
from utils.env_validator import EnvironmentValidator

# Initialize environment validator
env_validator = EnvironmentValidator()

class CurrencyConverter:
    """Handles currency conversion and rate management"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.logger = get_logger("currency_converter")
        self.cache_duration = env_validator.get_validated_value("CURRENCY_CACHE_DURATION", 1800)
        self.api_url = env_validator.get_validated_value("CURRENCY_API_URL", "https://api.exchangerate-api.com/v4/latest/USD")
        
    @log_performance_timing("get_currency_rates", "currency_converter")
    async def get_currency_rates(self) -> Dict[str, float]:
        """Fetch current currency rates from external API"""
        log_function_entry("get_currency_rates", "currency_converter")
        
        try:
            # Check cache first
            cached_rates = await self._get_cached_rates()
            if cached_rates:
                log_info_with_context("Using cached currency rates", "get_currency_rates", "currency_converter")
                log_function_exit("get_currency_rates", "currency_converter", result="cached")
                return cached_rates
            
            # Fetch from API
            log_api_call("ExchangeRate-API", "/v4/latest/USD", "currency_converter")
            
            # Create SSL context that doesn't verify certificates (for development)
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            timeout = aiohttp.ClientTimeout(total=env_validator.get_validated_value("HTTP_TIMEOUT", 10))
            
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.get(self.api_url) as response:
                    log_api_call("ExchangeRate-API", "/v4/latest/USD", "currency_converter", status_code=response.status)
                    
                    if response.status == 200:
                        data = await response.json()
                        rates = data.get('rates', {})
                        
                        # Extract relevant currencies
                        fallback_eur = env_validator.get_validated_value("CURRENCY_FALLBACK_EUR", 0.85)
                        fallback_czk = env_validator.get_validated_value("CURRENCY_FALLBACK_CZK", 23.5)
                        currency_rates = {
                            'USD': 1.0,
                            'EUR': rates.get('EUR', fallback_eur),
                            'CZK': rates.get('CZK', fallback_czk)
                        }
                        
                        # Cache the rates
                        await self._cache_rates(currency_rates)
                        
                        log_info_with_context(f"Fetched currency rates: {currency_rates}", "get_currency_rates", "currency_converter")
                        log_function_exit("get_currency_rates", "currency_converter", result="success")
                        return currency_rates
                    else:
                        log_warning_with_context(f"API returned status {response.status}", "get_currency_rates", "currency_converter")
                        return await self._get_fallback_rates()
                        
        except Exception as e:
            log_error_with_context(e, "get_currency_rates", "currency_converter")
            log_function_exit("get_currency_rates", "currency_converter", result="error")
            return await self._get_fallback_rates()
    
    async def _get_cached_rates(self) -> Optional[Dict[str, float]]:
        """Get cached currency rates if they're still valid"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT from_currency, to_currency, rate, timestamp 
                    FROM currency_rates 
                    WHERE timestamp > ? 
                    ORDER BY timestamp DESC
                """, (datetime.now() - timedelta(seconds=self.cache_duration),))
                
                rows = await cursor.fetchall()
                if not rows:
                    return None
                
                rates = {'USD': 1.0}
                for row in rows:
                    from_curr, to_curr, rate, timestamp = row
                    if from_curr == 'USD':
                        rates[to_curr] = rate
                
                # Check if we have all required currencies
                if 'EUR' in rates and 'CZK' in rates:
                    return rates
                return None
                
        except Exception as e:
            log_error_with_context(e, "_get_cached_rates", "currency_converter")
            return None
    
    async def _cache_rates(self, rates: Dict[str, float]):
        """Cache currency rates in database"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Clear old rates
                await db.execute("DELETE FROM currency_rates WHERE timestamp < ?", 
                               (datetime.now() - timedelta(seconds=self.cache_duration * 2),))
                
                # Insert new rates
                for currency, rate in rates.items():
                    if currency != 'USD':
                        await db.execute("""
                            INSERT INTO currency_rates (from_currency, to_currency, rate) 
                            VALUES (?, ?, ?)
                        """, ('USD', currency, rate))
                
                await db.commit()
                log_info_with_context("Cached currency rates", "_cache_rates", "currency_converter")
                
        except Exception as e:
            log_error_with_context(e, "_cache_rates", "currency_converter")
    
    async def _get_fallback_rates(self) -> Dict[str, float]:
        """Get fallback currency rates when API is unavailable"""
        log_warning_with_context("Using fallback currency rates", "get_currency_rates", "currency_converter")
        
        # Fallback rates from environment variables
        fallback_eur = env_validator.get_validated_value("CURRENCY_FALLBACK_EUR", 0.85)
        fallback_czk = env_validator.get_validated_value("CURRENCY_FALLBACK_CZK", 23.5)
        fallback_rates = {
            'USD': 1.0,
            'EUR': fallback_eur,
            'CZK': fallback_czk
        }
        
        return fallback_rates
    
    @log_performance_timing("convert_currency", "currency_converter")
    async def convert_currency(self, amount: float, from_currency: str, to_currency: str) -> float:
        """Convert amount from one currency to another"""
        log_function_entry("convert_currency", "currency_converter", 
                          amount=amount, from_currency=from_currency, to_currency=to_currency)
        
        if from_currency == to_currency:
            log_function_exit("convert_currency", "currency_converter", result=f"{amount} (same currency)")
            return amount
        
        try:
            rates = await self.get_currency_rates()
            
            # Convert to USD first if needed
            if from_currency != 'USD':
                usd_amount = amount / rates.get(from_currency, 1.0)
            else:
                usd_amount = amount
            
            # Convert from USD to target currency
            if to_currency != 'USD':
                converted_amount = usd_amount * rates.get(to_currency, 1.0)
            else:
                converted_amount = usd_amount
            
            log_info_with_context(f"Converted {amount} {from_currency} to {converted_amount:.2f} {to_currency}", 
                                "convert_currency", "currency_converter")
            log_function_exit("convert_currency", "currency_converter", result=f"{converted_amount:.2f}")
            return converted_amount
            
        except Exception as e:
            log_error_with_context(e, "convert_currency", "currency_converter")
            log_function_exit("convert_currency", "currency_converter", result="error")
            return amount  # Return original amount on error
    
    @log_performance_timing("calculate_multi_currency_portfolio", "currency_converter")
    async def calculate_multi_currency_portfolio(self, portfolio_data: dict, target_currency: str = 'USD') -> dict:
        """Calculate portfolio values in multiple currencies"""
        log_function_entry("calculate_multi_currency_portfolio", "currency_converter", 
                          target_currency=target_currency, portfolio_count=len(portfolio_data))
        
        try:
            rates = await self.get_currency_rates()
            multi_currency_data = {}
            
            for symbol, data in portfolio_data.items():
                amount = data.get('amount', 0)
                base_currency = data.get('base_currency', 'USD')
                price_buy = data.get('price_buy', 0)
                current_price = data.get('current_price', 0)
                
                # Convert purchase price to target currency
                price_buy_converted = await self.convert_currency(price_buy, base_currency, target_currency)
                
                # Convert current price to target currency
                current_price_converted = await self.convert_currency(current_price, 'USD', target_currency)
                
                # Calculate values
                cost_basis = amount * price_buy_converted
                current_value = amount * current_price_converted
                pnl = current_value - cost_basis
                pnl_percent = (pnl / cost_basis * 100) if cost_basis > 0 else 0
                
                multi_currency_data[symbol] = {
                    'amount': amount,
                    'price_buy': price_buy_converted,
                    'current_price': current_price_converted,
                    'cost_basis': cost_basis,
                    'current_value': current_value,
                    'pnl': pnl,
                    'pnl_percent': pnl_percent,
                    'base_currency': base_currency,
                    'target_currency': target_currency
                }
            
            log_info_with_context(f"Calculated multi-currency portfolio for {target_currency}", 
                                "calculate_multi_currency_portfolio", "currency_converter")
            log_function_exit("calculate_multi_currency_portfolio", "currency_converter", result="success")
            return multi_currency_data
            
        except Exception as e:
            log_error_with_context(e, "calculate_multi_currency_portfolio", "currency_converter")
            log_function_exit("calculate_multi_currency_portfolio", "currency_converter", result="error")
            return {}
    
    async def get_currency_rate(self, from_currency: str, to_currency: str) -> float:
        """Get specific currency rate between two currencies"""
        if from_currency == to_currency:
            return 1.0
        
        rates = await self.get_currency_rates()
        
        if from_currency == 'USD':
            return rates.get(to_currency, 1.0)
        elif to_currency == 'USD':
            return 1.0 / rates.get(from_currency, 1.0)
        else:
            # Convert through USD
            usd_rate = 1.0 / rates.get(from_currency, 1.0)
            target_rate = rates.get(to_currency, 1.0)
            return usd_rate * target_rate
