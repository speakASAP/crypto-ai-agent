import aiohttp
import asyncio
import json
import logging
import ssl
import hmac
import hashlib
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from decimal import Decimal
from binance.client import Client as BinanceClient
from app.core.config import settings
from app.utils.time_utils import get_current_timestamp
from app.services.currency_service import currency_service

logger = logging.getLogger(__name__)


class BinanceImportService:
    def __init__(self, api_key: str = None, api_secret: str = None):
        self.api_url = settings.binance_api_url
        # Use provided credentials (global settings are no longer used for security)
        self.api_key = api_key
        self.api_secret = api_secret
        
        # Validate credentials
        if not self.api_key or not self.api_secret:
            raise ValueError("Binance API key and secret are required. Please configure your credentials in Profile Settings.")
        
    def _generate_signature(self, query_string: str) -> str:
        """Generate HMAC SHA256 signature for Binance API"""
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _get_timestamp(self) -> int:
        """Get current timestamp in milliseconds"""
        return int(time.time() * 1000)
    
    async def test_api_connection(self) -> Dict:
        """Test Binance API connection using official library"""
        try:
            # Use official Binance library for proper signature handling
            client = BinanceClient(self.api_key, self.api_secret)
            
            # Test server time
            try:
                server_time = client.get_server_time()
                logger.info(f"✅ Binance API server time: {server_time['serverTime']}")
            except Exception as e:
                logger.error(f"❌ Cannot reach Binance API: {e}")
                return {
                    'success': False,
                    'message': f'Cannot reach Binance API: {str(e)}',
                    'error': str(e)
                }
            
            # Test account info
            try:
                account_info = client.get_account()
                logger.info("✅ Binance API connection successful")
                return {
                    'success': True,
                    'message': 'API connection successful',
                    'account_type': account_info.get('accountType', 'Unknown'),
                    'can_trade': account_info.get('canTrade', False),
                    'can_withdraw': account_info.get('canWithdraw', False),
                    'can_deposit': account_info.get('canDeposit', False),
                    'balances_count': len(account_info.get('balances', [])),
                    'account_info': {
                        'account_type': account_info.get('accountType', 'Unknown'),
                        'can_trade': account_info.get('canTrade', False),
                        'can_withdraw': account_info.get('canWithdraw', False),
                        'can_deposit': account_info.get('canDeposit', False),
                        'balances_count': len(account_info.get('balances', []))
                    }
                }
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ Binance API connection failed: {error_msg}")
                
                if "Signature for this request is not valid" in error_msg:
                    return {
                        'success': False,
                        'message': 'Signature validation failed. Please check your API key and secret.',
                        'error_code': '400',
                        'troubleshooting': 'Verify that your API key and secret are correct.'
                    }
                elif "Invalid API-key" in error_msg:
                    return {
                        'success': False,
                        'message': 'Invalid API key or permissions.',
                        'error_code': '401',
                        'troubleshooting': 'Make sure your API key has "Enable Reading" permission enabled.'
                    }
                else:
                    return {
                        'success': False,
                        'message': f'API connection failed: {error_msg}',
                        'error_code': '400',
                        'troubleshooting': 'Check your API credentials and network connection.'
                    }
                        
        except Exception as e:
            logger.error(f"❌ Binance API connection error: {e}")
            return {
                'success': False,
                'message': f'Connection error: {str(e)}',
                'error': str(e),
                'troubleshooting': 'Check your internet connection and API credentials'
            }
    
    async def get_account_balances(self) -> List[Dict]:
        """Get all account balances from Binance"""
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                timestamp = self._get_timestamp()
                query_string = f"timestamp={timestamp}"
                signature = self._generate_signature(query_string)
                
                url = f"{self.api_url}/account"
                params = {
                    'timestamp': timestamp,
                    'signature': signature
                }
                
                headers = {
                    'X-MBX-APIKEY': self.api_key
                }
                
                async with session.get(url, params=params, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        balances = []
                        
                        for balance in data.get('balances', []):
                            free = float(balance.get('free', 0))
                            locked = float(balance.get('locked', 0))
                            total = free + locked
                            
                            # Only include non-zero balances
                            if total > 0:
                                balances.append({
                                    'asset': balance.get('asset', ''),
                                    'free': free,
                                    'locked': locked,
                                    'total': total
                                })
                        
                        logger.info(f"✅ Retrieved {len(balances)} non-zero balances from Binance")
                        return balances
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Failed to get account balances: {response.status} - {error_text}")
                        return []
                        
        except Exception as e:
            logger.error(f"❌ Error getting account balances: {e}")
            return []
    
    async def get_trading_history(self, symbol: str, limit: int = 1000) -> List[Dict]:
        """Get trading history for a specific symbol using official library"""
        try:
            # Use official Binance library for proper signature handling
            client = BinanceClient(self.api_key, self.api_secret)
            
            # Get trades
            trades = client.get_my_trades(symbol=symbol, limit=limit)
            logger.info(f"✅ Retrieved {len(trades)} trades for {symbol}")
            return trades
                        
        except Exception as e:
            logger.warning(f"⚠️ Error getting trading history for {symbol}: {e}")
            return []
    
    async def get_fiat_purchase_history(self) -> List[Dict]:
        """Get fiat card purchase history from Binance"""
        try:
            # Use official Binance library for proper signature handling
            client = BinanceClient(self.api_key, self.api_secret)
            
            # Get fiat orders (card purchases)
            # This includes the orders you see at https://www.binance.com/en/my/wallet/exchange/buysell-history
            fiat_orders = client.get_fiat_orders(
                transactionType=0,  # 0 = buy, 1 = sell
                beginTime=None,  # Get all history
                endTime=None
            )
            
            logger.info(f"✅ Retrieved {len(fiat_orders.get('data', []))} fiat orders")
            return fiat_orders.get('data', [])
                        
        except Exception as e:
            logger.warning(f"⚠️ Error getting fiat purchase history: {e}")
            return []
    
    async def calculate_portfolio_from_balances(self, balances: List[Dict]) -> List[Dict]:
        """Calculate portfolio items from account balances"""
        portfolio_items = []
        
        for balance in balances:
            asset = balance['asset']
            total_amount = balance['total']
            
            # Skip USDT and other stablecoins as they're not crypto investments
            if asset in ['USDT', 'USDC', 'BUSD', 'TUSD', 'USDP']:
                continue
            
            # Get trading history to calculate average buy price
            trading_pairs = [f"{asset}USDT", f"{asset}BTC", f"{asset}ETH"]
            buy_trades = []
            
            logger.info(f"🔍 Looking for trades for {asset} in pairs: {trading_pairs}")
            
            for pair in trading_pairs:
                try:
                    trades = await self.get_trading_history(pair, 1000)
                    logger.info(f"Found {len(trades)} total trades for {pair}")
                    for trade in trades:
                        is_buyer = trade.get('isBuyer', False)
                        if is_buyer:  # Only buy trades
                            buy_trades.append({
                                'symbol': pair,
                                'qty': float(trade.get('qty', 0)),
                                'price': float(trade.get('price', 0)),
                                'time': trade.get('time', 0),
                                'commission': float(trade.get('commission', 0)),
                            })
                except Exception as e:
                    logger.warning(f"Error processing trades for {pair}: {e}")
                    continue
            
            logger.info(f"Total buy trades found for {asset}: {len(buy_trades)}")
            
            if buy_trades:
                # Sort trades by time to get earliest
                buy_trades.sort(key=lambda x: x['time'])
                
                # Calculate weighted average buy price
                # USDT ≈ USD, so most prices are already in USD
                total_qty = sum(trade['qty'] for trade in buy_trades)
                total_cost = sum(trade['qty'] * trade['price'] for trade in buy_trades)
                total_commission = sum(trade['commission'] for trade in buy_trades)
                
                if total_qty > 0:
                    avg_buy_price = total_cost / total_qty
                    # Scale to current balance
                    scaled_amount = total_amount
                    scaled_cost = (total_cost / total_qty) * total_amount
                    scaled_commission = (total_commission / total_qty) * total_amount
                    
                    # Get the EARLIEST trade date for purchase date
                    earliest_trade = buy_trades[0]
                    trade_date = datetime.fromtimestamp(earliest_trade['time'] / 1000).isoformat() + "Z"
                    
                    # Convert to USD (USDT ≈ USD)
                    # Ensure currency service rates are loaded
                    if not currency_service.rates:
                        currency_service.ensure_rates_initialized()
                    price_buy_usd = avg_buy_price  # USDT is approximately USD
                    
                    portfolio_items.append({
                        'symbol': asset,
                        'amount': scaled_amount,
                        'price_buy': price_buy_usd,
                        'purchase_date': trade_date,
                        'base_currency': 'USD',  # Store in USD
                        'source': 'Binance',
                        'commission': scaled_commission,
                        'total_investment_text': f"${scaled_cost + scaled_commission:.2f}"
                    })
            else:
                # If no trading history, create a placeholder entry
                # This might be from airdrops, staking rewards, or other sources
                portfolio_items.append({
                    'symbol': asset,
                    'amount': total_amount,
                    'price_buy': 0.0,  # Unknown price
                    'purchase_date': datetime.now().isoformat() + "Z",
                    'base_currency': 'USDT',
                    'source': 'Binance',
                    'commission': 0.0,
                    'total_investment_text': "Unknown"
                })
        
        logger.info(f"✅ Calculated {len(portfolio_items)} portfolio items from Binance balances")
        return portfolio_items
    
    async def import_portfolio(self, user_id: int) -> Dict:
        """Import complete portfolio from Binance"""
        try:
            logger.info(f"🚀 Starting Binance portfolio import for user {user_id}")
            
            # Test API connection first
            connection_test = await self.test_api_connection()
            if not connection_test['success']:
                return {
                    'success': False,
                    'message': f"API connection failed: {connection_test['message']}",
                    'items_imported': 0
                }
            
            # Get account balances
            balances = await self.get_account_balances()
            if not balances:
                return {
                    'success': False,
                    'message': "No balances found or API access denied",
                    'items_imported': 0
                }
            
            # Calculate portfolio items
            portfolio_items = await self.calculate_portfolio_from_balances(balances)
            
            logger.info(f"✅ Binance import completed: {len(portfolio_items)} items ready for import")
            
            return {
                'success': True,
                'message': f"Successfully prepared {len(portfolio_items)} portfolio items for import",
                'items_imported': len(portfolio_items),
                'portfolio_items': portfolio_items,
                'account_info': connection_test
            }
            
        except Exception as e:
            logger.error(f"❌ Binance portfolio import failed: {e}")
            return {
                'success': False,
                'message': f"Import failed: {str(e)}",
                'items_imported': 0,
                'error': str(e)
            }
