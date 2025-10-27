import aiohttp
import asyncio
import json
import logging
import ssl
import hmac
import hashlib
import time
import requests
from typing import Dict, List, Optional
from datetime import datetime
from app.services.currency_service import currency_service

logger = logging.getLogger(__name__)


class BitfinexImportService:
    def __init__(self, api_key: str = None, api_secret: str = None):
        self.api_url = "https://api.bitfinex.com"
        self.api_key = api_key
        self.api_secret = api_secret
        
        # Validate credentials
        if not self.api_key or not self.api_secret:
            raise ValueError("Bitfinex API key and secret are required. Please configure your credentials in Profile Settings.")
        
        # Debug: Log credentials (without exposing secrets)
        logger.info(f"🔐 Initialized BitfinexImportService with API key: {self.api_key[:20]}...")


    def _get_nonce(self) -> int:
        """Get current timestamp in milliseconds for Bitfinex nonce (must be strictly increasing)"""
        # Bitfinex API v2 requires nonce in milliseconds as integer
        # Time-based nonces are sufficient unless making multiple requests per millisecond
        return int(time.time() * 1000)

    def _make_authenticated_request(self, path: str, body: Dict = None) -> Dict:
        """Make authenticated request to Bitfinex API"""
        try:
            nonce = str(self._get_nonce())
            
            if body is None:
                body = {}
            
            # For Bitfinex API v2, the signature is created from:
            # /api/v2/path{nonce}{body_json}
            # path already includes /v2/, so we use /api{path}
            # CRITICAL: Always include "{}" for empty bodies - Bitfinex requires exact signature format
            raw_body = json.dumps(body)  # This becomes "{}" even for empty dict, not ""
            signature_payload = f"/api{path}{nonce}{raw_body}"
            
            # Generate signature from the concatenated payload
            signature = hmac.new(
                self.api_secret.encode('utf-8'),
                signature_payload.encode('utf-8'),
                hashlib.sha384
            ).hexdigest()
            
            headers = {
                'bfx-apikey': self.api_key,
                'bfx-signature': signature,
                'bfx-nonce': nonce,
                'Content-Type': 'application/json'
            }
            
            # Debug logging
            print(f"[DEBUG] Bitfinex request - Nonce: {nonce}, Path: {path}")
            print(f"[DEBUG] Signature Payload: {signature_payload}")
            print(f"[DEBUG] Raw Body: {raw_body}")
            print(f"[DEBUG] API Key: {self.api_key}")
            print(f"[DEBUG] Signature: {signature[:50]}...")
            logger.info(f"Bitfinex request - Nonce: {nonce}, Path: {path}")
            logger.info(f"Signature Payload: {signature_payload}")
            logger.info(f"Raw Body: {raw_body}")
            logger.info(f"Signature: {signature[:20]}...")
            
            url = f"{self.api_url}{path}"
            
            # Use requests library which works reliably with Bitfinex API
            response = requests.post(url, json=body, headers=headers, verify=False, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Bitfinex API error: {response.status_code} - {response.text}")
                raise Exception(f"Bitfinex API error: {response.status_code} - {response.text}")
                        
        except Exception as e:
            logger.error(f"Error making authenticated request to Bitfinex: {e}")
            raise

    async def test_api_connection(self) -> Dict:
        """Test Bitfinex API connection"""
        try:
            logger.info("Testing Bitfinex API connection")
            
            # Test with user info endpoint
            result = self._make_authenticated_request("/v2/auth/r/info/user")
            
            if isinstance(result, list) and len(result) > 0:
                logger.info("✅ Bitfinex API connection successful")
                # Bitfinex returns data as a list: [id, email, username, ...]
                # Don't use .get() on list elements, just access by index
                return {
                    'success': True,
                    'message': 'API connection successful',
                    'account_info': {
                        'id': result[0] if len(result) > 0 else None,
                        'email': result[1] if len(result) > 1 else None,
                        'username': result[2] if len(result) > 2 else None
                    }
                }
            else:
                logger.error("❌ Invalid response from Bitfinex API")
                return {
                    'success': False,
                    'message': 'Invalid response from Bitfinex API',
                    'error': 'Invalid response format'
                }
                        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Bitfinex API connection failed: {error_msg}")
            
            if "Invalid API-key" in error_msg or "Unauthorized" in error_msg:
                return {
                    'success': False,
                    'message': 'Invalid API key or permissions.',
                    'error_code': '401',
                    'troubleshooting': 'Make sure your API key has "Account Info", "Account History", and "Wallets" permissions enabled.'
                }
            elif "signature" in error_msg.lower():
                return {
                    'success': False,
                    'message': 'Signature validation failed. Please check your API key and secret.',
                    'error_code': '400',
                    'troubleshooting': 'Verify that your API key and secret are correct.'
                }
            else:
                return {
                    'success': False,
                    'message': f'Connection error: {error_msg}',
                    'error': error_msg,
                    'troubleshooting': 'Check your internet connection and API credentials'
                }

    async def get_wallets(self) -> List[Dict]:
        """Get all wallets from Bitfinex"""
        try:
            logger.info("Fetching Bitfinex wallets")
            
            result = self._make_authenticated_request("/v2/auth/r/wallets")
            
            wallets = []
            for wallet in result:
                # Wallet format: ["exchange", "BTC", 0.5, 0, null]
                # [wallet_type, currency, balance, unsettled_interest, balance_available]
                wallet_type = wallet[0]
                currency = wallet[1]
                balance = wallet[2]
                unsettled_interest = wallet[3] if len(wallet) > 3 else 0
                balance_available = wallet[4] if len(wallet) > 4 else balance
                
                if balance > 0:
                    wallets.append({
                        'type': wallet_type,
                        'currency': currency,
                        'balance': balance,
                        'unsettled_interest': unsettled_interest,
                        'balance_available': balance_available
                    })
            
            logger.info(f"✅ Retrieved {len(wallets)} non-zero wallets from Bitfinex")
            return wallets
            
        except Exception as e:
            logger.error(f"❌ Error getting Bitfinex wallets: {e}")
            return []

    async def get_trades(self, symbol: str, limit: int = 250) -> List[Dict]:
        """Get trading history for a specific symbol"""
        try:
            logger.info(f"Fetching trade history for {symbol}")
            
            result = self._make_authenticated_request("/v2/auth/r/trades/{}/hist".format(symbol))
            
            logger.info(f"✅ Retrieved {len(result)} trades for {symbol}")
            return result
                        
        except Exception as e:
            logger.warning(f"⚠️ Error getting trade history for {symbol}: {e}")
            return []

    async def calculate_portfolio_from_wallets(self, wallets: List[Dict]) -> List[Dict]:
        """Calculate portfolio items from Bitfinex wallets"""
        portfolio_items = []
        
        for wallet in wallets:
            currency = wallet['currency']
            total_amount = wallet['balance']
            
            # Skip stablecoins as they're not crypto investments
            if currency in ['USD', 'USDT', 'EUR', 'GBP', 'JPY']:
                continue
            
            # Get trading history to calculate average buy price
            trading_pairs = [f"t{currency}USD", f"t{currency}USDT", f"t{currency}BTC", f"t{currency}ETH"]
            buy_trades = []
            
            logger.info(f"🔍 Looking for trades for {currency} in pairs: {trading_pairs}")
            
            for pair in trading_pairs:
                try:
                    trades = await self.get_trades(pair, 250)
                    logger.info(f"Found {len(trades)} total trades for {pair}")
                    
                    for trade in trades:
                        # Trade format: [id, pair, mts_create, order_id, exec_amount, exec_price, order_type, order_price, maker]
                        # We need to determine if this was a buy
                        if len(trade) >= 6:
                            exec_amount = trade[4]
                            exec_price = trade[5]
                            
                            # Positive amount typically means buy
                            if exec_amount > 0:
                                buy_trades.append({
                                    'pair': pair,
                                    'amount': abs(exec_amount),
                                    'price': exec_price,
                                    'time': trade[2]
                                })
                except Exception as e:
                    logger.warning(f"Error processing trades for {pair}: {e}")
                    continue
            
            logger.info(f"Total buy trades found for {currency}: {len(buy_trades)}")
            
            if buy_trades:
                # Sort trades by time to get earliest
                buy_trades.sort(key=lambda x: x['time'])
                
                # Calculate weighted average buy price
                total_qty = sum(trade['amount'] for trade in buy_trades)
                total_cost = sum(trade['amount'] * trade['price'] for trade in buy_trades)
                
                if total_qty > 0:
                    avg_buy_price = total_cost / total_qty
                    
                    # Scale to current balance
                    scaled_amount = total_amount
                    
                    # Get the EARLIEST trade date for purchase date
                    earliest_trade = buy_trades[0]
                    trade_date = datetime.fromtimestamp(earliest_trade['time'] / 1000).isoformat() + "Z"
                    
                    # Convert to USD (assuming price is already in USD)
                    price_buy_usd = avg_buy_price
                    
                    portfolio_items.append({
                        'symbol': currency,
                        'amount': scaled_amount,
                        'price_buy': price_buy_usd,
                        'purchase_date': trade_date,
                        'base_currency': 'USD',
                        'source': 'Bitfinex',
                        'commission': 0.0,
                        'total_investment_text': f"${scaled_amount * price_buy_usd:.2f}"
                    })
            else:
                # If no trading history, create a placeholder entry
                portfolio_items.append({
                    'symbol': currency,
                    'amount': total_amount,
                    'price_buy': 0.0,
                    'purchase_date': datetime.now().isoformat() + "Z",
                    'base_currency': 'USD',
                    'source': 'Bitfinex',
                    'commission': 0.0,
                    'total_investment_text': "Unknown"
                })
        
        logger.info(f"✅ Calculated {len(portfolio_items)} portfolio items from Bitfinex wallets")
        return portfolio_items

    async def import_portfolio(self, user_id: int) -> Dict:
        """Import complete portfolio from Bitfinex"""
        try:
            logger.info(f"🚀 Starting Bitfinex portfolio import for user {user_id}")
            
            # Test API connection first
            connection_test = await self.test_api_connection()
            if not connection_test['success']:
                return {
                    'success': False,
                    'message': f"API connection failed: {connection_test['message']}",
                    'items_imported': 0
                }
            
            # Get wallets
            wallets = await self.get_wallets()
            if not wallets:
                return {
                    'success': False,
                    'message': "No wallets found or API access denied",
                    'items_imported': 0
                }
            
            # Calculate portfolio items
            portfolio_items = await self.calculate_portfolio_from_wallets(wallets)
            
            logger.info(f"✅ Bitfinex import completed: {len(portfolio_items)} items ready for import")
            
            return {
                'success': True,
                'message': f"Successfully prepared {len(portfolio_items)} portfolio items for import",
                'items_imported': len(portfolio_items),
                'portfolio_items': portfolio_items,
                'account_info': connection_test.get('account_info', {})
            }
            
        except Exception as e:
            logger.error(f"❌ Bitfinex portfolio import failed: {e}")
            return {
                'success': False,
                'message': f"Import failed: {str(e)}",
                'items_imported': 0,
                'error': str(e)
            }

