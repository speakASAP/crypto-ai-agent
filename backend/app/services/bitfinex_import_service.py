import aiohttp
import asyncio
import json
import logging
import ssl
import hmac
import hashlib
import time
import requests
import warnings
import urllib3
from typing import Dict, List, Optional
from datetime import datetime
from ..services.currency_service import currency_service
from ..services.multi_exchange_price_service import MultiExchangePriceService

# Suppress SSL warnings for Bitfinex API
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class BitfinexImportService:
    def __init__(self, api_key: str = None, api_secret: str = None):
        self.api_url = "https://api.bitfinex.com"
        self.api_key = api_key
        self.api_secret = api_secret
        self.price_service = MultiExchangePriceService()
        self._btc_price_cache = None
        self._eth_price_cache = None
        
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

    async def get_all_trades(self) -> List[Dict]:
        """Try to get all trades at once (if endpoint supports it)"""
        try:
            logger.info("Attempting to fetch all trades at once")
            # Try the endpoint without symbol parameter
            result = self._make_authenticated_request("/v2/auth/r/trades/hist")
            
            if isinstance(result, list):
                logger.info(f"✅ Retrieved {len(result)} total trades from all symbols")
                return result
            else:
                logger.warning("Unexpected response format for all trades")
                return []
        except Exception as e:
            # This endpoint might not exist, which is fine
            logger.debug(f"All-trades endpoint not available (expected): {e}")
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

    def _normalize_pair(self, pair: str) -> str:
        """Normalize trading pair format for matching (e.g., 'BTCUSD', 'tBTCUSD' -> 'tBTCUSD')"""
        if not pair:
            return pair
        # Remove 't' prefix if present, then add it back for consistency
        pair_clean = pair[1:] if pair.startswith('t') else pair
        return f"t{pair_clean}"

    def _extract_quote_currency(self, pair: str) -> str:
        """Extract quote currency from trading pair (e.g., 'tBTCUSD' -> 'USD')"""
        # Remove 't' prefix if present
        if pair.startswith('t'):
            pair = pair[1:]
        
        # Common quote currencies (ordered by priority/commonness)
        quote_currencies = ['USD', 'USDT', 'EUR', 'GBP', 'JPY', 'BTC', 'ETH', 'BNB', 'USDC', 'DAI']
        
        for quote in quote_currencies:
            if pair.endswith(quote):
                return quote
        
        # Fallback: try to detect by length (most pairs are BASE+QUOTE, 3+3 chars)
        if len(pair) >= 6:
            # Try common patterns
            for quote in quote_currencies:
                if quote in pair[-len(quote):]:
                    return quote
        
        # Default fallback
        return 'USD'

    async def _get_crypto_price_usd(self, symbol: str) -> float:
        """Get current USD price for a crypto symbol (with caching)"""
        # Use cache if available
        if symbol == 'BTC' and self._btc_price_cache:
            return self._btc_price_cache
        if symbol == 'ETH' and self._eth_price_cache:
            return self._eth_price_cache
        
        try:
            prices = await self.price_service.get_current_prices([symbol])
            if symbol in prices:
                price = prices[symbol]
                # Cache the price
                if symbol == 'BTC':
                    self._btc_price_cache = price
                elif symbol == 'ETH':
                    self._eth_price_cache = price
                return price
        except Exception as e:
            logger.debug(f"Could not fetch {symbol} price: {e}")
        
        # Fallback prices if fetch fails
        fallback_prices = {
            'BTC': 50000.0,
            'ETH': 3000.0
        }
        return fallback_prices.get(symbol, 1.0)

    def _convert_price_to_usd(self, price: float, quote_currency: str, trade_time: int = None) -> float:
        """Convert price from quote currency to USD (synchronous version for use in loops)
        
        Note: For BTC/ETH quotes, this uses cached prices or fallback values.
        For async version with live price fetching, use _convert_price_to_usd_async.
        
        Args:
            price: The execution price from the trade (in quote currency)
            quote_currency: The quote currency of the trading pair (e.g., 'BTC', 'USD', 'EUR')
            trade_time: Optional timestamp of the trade for historical rate lookup
        
        Returns:
            Price converted to USD
        """
        if quote_currency in ['USD', 'USDT', 'USDC']:
            return price
        
        # Ensure currency service is initialized
        currency_service.ensure_rates_initialized()
        
        try:
            # For crypto quote currencies (BTC, ETH), we need to multiply by their USD rates
            # Example: tETHBTC with price 0.05 means 1 ETH = 0.05 BTC
            # To get USD price: 0.05 * (BTC/USD rate) = ETH price in USD
            if quote_currency == 'BTC':
                # Use cached price or fallback
                btc_price_usd = self._btc_price_cache if self._btc_price_cache else 50000.0
                logger.debug(f"Converting BTC-quoted price to USD using BTC price: {btc_price_usd}")
                return price * btc_price_usd
            elif quote_currency == 'ETH':
                # Use cached price or fallback
                eth_price_usd = self._eth_price_cache if self._eth_price_cache else 3000.0
                logger.debug(f"Converting ETH-quoted price to USD using ETH price: {eth_price_usd}")
                return price * eth_price_usd
            else:
                # For fiat currencies (EUR, GBP, JPY, etc.), use currency service conversion
                return currency_service.convert_amount(price, quote_currency, 'USD')
        except Exception as e:
            logger.warning(f"Error converting {price} {quote_currency} to USD: {e}, using price as-is")
            return price

    async def calculate_portfolio_from_wallets(self, wallets: List[Dict]) -> List[Dict]:
        """Calculate portfolio items from Bitfinex wallets"""
        portfolio_items = []
        
        # Pre-fetch BTC and ETH prices for better conversion accuracy
        try:
            logger.info("Fetching BTC and ETH prices for price conversion")
            btc_price = await self._get_crypto_price_usd('BTC')
            eth_price = await self._get_crypto_price_usd('ETH')
            logger.info(f"BTC price: ${btc_price:.2f}, ETH price: ${eth_price:.2f}")
        except Exception as e:
            logger.warning(f"Could not fetch crypto prices, will use fallbacks: {e}")
        
        # First, try to get all trades at once (more efficient)
        all_trades_map = {}
        try:
            all_trades = await self.get_all_trades()
            if all_trades:
                logger.info(f"Processing {len(all_trades)} trades from all-trades endpoint")
                for trade in all_trades:
                    if len(trade) >= 2:
                        # Normalize pair format for consistent matching
                        pair_raw = trade[1] if isinstance(trade[1], str) else str(trade[1])
                        pair = self._normalize_pair(pair_raw)
                        if pair not in all_trades_map:
                            all_trades_map[pair] = []
                        all_trades_map[pair].append(trade)
                logger.info(f"✅ Built trades map with {len(all_trades_map)} unique pairs: {list(all_trades_map.keys())[:10]}")
        except Exception as e:
            logger.debug(f"Could not use all-trades endpoint, will fetch per-symbol: {e}")
        
        # Common quote currencies to try (expanded list)
        common_quote_currencies = ['USD', 'USDT', 'EUR', 'GBP', 'JPY', 'BTC', 'ETH', 'USDC', 'DAI']
        
        for wallet in wallets:
            currency = wallet['currency']
            total_amount = wallet['balance']
            
            # Skip stablecoins as they're not crypto investments
            if currency in ['USD', 'USDT', 'EUR', 'GBP', 'JPY', 'USDC', 'DAI']:
                continue
            
            buy_trades = []
            
            # Build list of trading pairs to check
            trading_pairs = []
            for quote in common_quote_currencies:
                trading_pairs.append(f"t{currency}{quote}")
            
            logger.info(f"🔍 Looking for trades for {currency} in pairs: {trading_pairs}")
            
            # Process trades from all-trades endpoint if available
            for pair in trading_pairs:
                # Try both exact match and normalized match
                normalized_pair = self._normalize_pair(pair)
                trades_to_process = []
                
                if pair in all_trades_map:
                    trades_to_process = all_trades_map[pair]
                    logger.info(f"Found {len(trades_to_process)} trades for {pair} (exact match) from all-trades")
                elif normalized_pair in all_trades_map:
                    trades_to_process = all_trades_map[normalized_pair]
                    logger.info(f"Found {len(trades_to_process)} trades for {pair} (normalized: {normalized_pair}) from all-trades")
                
                for trade in trades_to_process:
                    # Trade format: [id, pair, mts_create, order_id, exec_amount, exec_price, order_type, order_price, maker, fee, fee_currency]
                    # exec_amount: positive = buy (you receive base currency), negative = sell (you give base currency)
                    if len(trade) >= 6:
                        try:
                            exec_amount = float(trade[4]) if trade[4] is not None else 0
                            exec_price = float(trade[5]) if trade[5] is not None else 0
                            mts_create = int(trade[2]) if len(trade) > 2 and trade[2] is not None else 0
                            order_type = trade[6] if len(trade) > 6 else None
                            
                            logger.debug(f"Trade for {currency}/{pair}: exec_amount={exec_amount}, exec_price={exec_price}, mts_create={mts_create}, order_type={order_type}, trade={trade[:7]}")
                            
                            # Positive amount means buy (you receive the base currency)
                            # Check both exec_amount > 0 and valid price
                            if exec_amount > 0 and exec_price > 0 and mts_create > 0:
                                quote_currency = self._extract_quote_currency(normalized_pair)
                                price_usd = self._convert_price_to_usd(exec_price, quote_currency, mts_create)
                                
                                buy_trades.append({
                                    'pair': normalized_pair,
                                    'amount': abs(exec_amount),
                                    'price': exec_price,
                                    'price_usd': price_usd,
                                    'quote_currency': quote_currency,
                                    'time': mts_create
                                })
                                logger.info(f"✅ Added buy trade: {currency} amount={exec_amount}, price={exec_price}, price_usd={price_usd:.2f}, time={mts_create} ({datetime.fromtimestamp(mts_create/1000).isoformat()})")
                            elif exec_amount != 0:
                                logger.debug(f"Skipping trade (not a buy): {currency} exec_amount={exec_amount}, price={exec_price}")
                        except (ValueError, TypeError, IndexError) as e:
                            logger.warning(f"Error parsing trade for {pair}: {e}, trade data: {trade}")
                            continue
            
            # If no trades found from all-trades endpoint, try fetching per symbol
            if not buy_trades:
                logger.info(f"No trades found in all-trades map, trying per-symbol fetch for {currency}")
                for pair in trading_pairs:
                    try:
                        trades = await self.get_trades(pair, 250)
                        logger.info(f"Found {len(trades)} total trades for {pair}")
                        
                        for trade in trades:
                            # Trade format: [id, pair, mts_create, order_id, exec_amount, exec_price, order_type, order_price, maker, fee, fee_currency]
                            # exec_amount: positive = buy (you receive base currency), negative = sell (you give base currency)
                            if len(trade) >= 6:
                                try:
                                    exec_amount = float(trade[4]) if trade[4] is not None else 0
                                    exec_price = float(trade[5]) if trade[5] is not None else 0
                                    mts_create = int(trade[2]) if len(trade) > 2 and trade[2] is not None else 0
                                    order_type = trade[6] if len(trade) > 6 else None
                                    
                                    logger.debug(f"Trade for {currency}/{pair}: exec_amount={exec_amount}, exec_price={exec_price}, mts_create={mts_create}, order_type={order_type}, trade={trade[:7]}")
                                    
                                    # Positive amount means buy (you receive the base currency)
                                    # Check both exec_amount > 0 and valid price and timestamp
                                    if exec_amount > 0 and exec_price > 0 and mts_create > 0:
                                        quote_currency = self._extract_quote_currency(pair)
                                        price_usd = self._convert_price_to_usd(exec_price, quote_currency, mts_create)
                                        
                                        buy_trades.append({
                                            'pair': pair,
                                            'amount': abs(exec_amount),
                                            'price': exec_price,
                                            'price_usd': price_usd,
                                            'quote_currency': quote_currency,
                                            'time': mts_create
                                        })
                                        logger.info(f"✅ Added buy trade: {currency} amount={exec_amount}, price={exec_price}, price_usd={price_usd:.2f}, time={mts_create} ({datetime.fromtimestamp(mts_create/1000).isoformat()})")
                                    elif exec_amount != 0:
                                        logger.debug(f"Skipping trade (not a buy): {currency} exec_amount={exec_amount}, price={exec_price}")
                                except (ValueError, TypeError, IndexError) as e:
                                    logger.warning(f"Error parsing trade for {pair}: {e}, trade data: {trade}")
                                    continue
                    except Exception as e:
                        logger.warning(f"Error processing trades for {pair}: {e}")
                        continue
            
            logger.info(f"Total buy trades found for {currency}: {len(buy_trades)}")
            
            if buy_trades:
                # Sort trades by time to get earliest
                buy_trades.sort(key=lambda x: x['time'] if x['time'] > 0 else float('inf'))
                
                # Calculate weighted average buy price in USD
                total_qty = sum(trade['amount'] for trade in buy_trades)
                total_cost_usd = sum(trade['amount'] * trade['price_usd'] for trade in buy_trades)
                
                if total_qty > 0:
                    avg_buy_price_usd = total_cost_usd / total_qty
                    
                    # Scale to current balance
                    scaled_amount = total_amount
                    
                    # Get the EARLIEST trade date for purchase date
                    earliest_trade = buy_trades[0]
                    if earliest_trade['time'] > 0:
                        # Bitfinex timestamps are in milliseconds
                        trade_date = datetime.fromtimestamp(earliest_trade['time'] / 1000).isoformat() + "Z"
                    else:
                        # Fallback to current date if timestamp is invalid
                        trade_date = datetime.now().isoformat() + "Z"
                        logger.warning(f"Invalid timestamp for {currency}, using current date")
                    
                    logger.info(f"✅ Calculated portfolio item for {currency}: amount={scaled_amount}, price_buy={avg_buy_price_usd:.2f}, purchase_date={trade_date}")
                    
                    portfolio_items.append({
                        'symbol': currency,
                        'amount': scaled_amount,
                        'price_buy': avg_buy_price_usd,
                        'purchase_date': trade_date,
                        'base_currency': 'USD',
                        'source': 'Bitfinex',
                        'commission': 0.0,
                        'total_investment_text': f"${scaled_amount * avg_buy_price_usd:.2f}"
                    })
                else:
                    logger.warning(f"⚠️ Total quantity is 0 for {currency}, cannot calculate average price")
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
            else:
                # If no trading history, create a placeholder entry
                logger.warning(f"⚠️ No buy trades found for {currency}, creating placeholder entry with price_buy=0.0")
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

