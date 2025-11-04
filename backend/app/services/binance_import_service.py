import aiohttp
import asyncio
import json
import logging
import ssl
import hmac
import hashlib
import time
import csv
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from decimal import Decimal
from binance.client import Client as BinanceClient
from ..core.config import settings
from ..utils.time_utils import get_current_timestamp
from ..services.currency_service import currency_service

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
        """Get fiat card purchase history from Binance using direct API call"""
        try:
            # Binance fiat orders endpoint: /sapi/v1/fiat/orders
            base_url = "https://api.binance.com"
            endpoint = "/sapi/v1/fiat/orders"
            
            # Build query parameters
            timestamp = self._get_timestamp()
            params = {
                'transactionType': '0',  # 0 = buy, 1 = sell
                'timestamp': str(timestamp)
            }
            
            # Create query string
            query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
            
            # Generate signature
            signature = self._generate_signature(query_string)
            
            # Add signature to params
            params['signature'] = signature
            
            # Build full URL
            url = f"{base_url}{endpoint}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
            
            # Make request
            headers = {
                'X-MBX-APIKEY': self.api_key
            }
            
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        result = await response.json()
                        orders = result.get('data', [])
                        logger.info(f"✅ Retrieved {len(orders)} fiat orders")
                        return orders
                    else:
                        error_text = await response.text()
                        logger.warning(f"⚠️ Binance fiat orders API returned status {response.status}: {error_text}")
                        return []
                        
        except Exception as e:
            logger.warning(f"⚠️ Error getting fiat purchase history: {e}")
            return []
    
    async def get_deposit_history(self, asset: str = None) -> List[Dict]:
        """Get deposit history from Binance"""
        try:
            client = BinanceClient(self.api_key, self.api_secret)
            
            # Get deposit history
            deposits = client.get_deposit_history(asset=asset) if asset else client.get_deposit_history()
            
            logger.info(f"✅ Retrieved {len(deposits)} deposits" + (f" for {asset}" if asset else ""))
            return deposits
        except Exception as e:
            logger.debug(f"Could not get deposit history: {e}")
            return []
    
    def _save_import_data_to_csv(self, user_id: int, balances: List[Dict], all_trades: Dict[str, List], 
                                 portfolio_items: List[Dict], account_info: Dict = None, fiat_orders: List[Dict] = None) -> str:
        """Save full Binance import data to CSV file for analysis"""
        try:
            # Create logs directory if it doesn't exist
            logs_dir = "/app/logs"
            os.makedirs(logs_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_filename = f"{logs_dir}/binance_import_{user_id}_{timestamp}.csv"
            
            with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow(['=== BINANCE IMPORT DATA ==='])
                writer.writerow(['Timestamp', timestamp])
                writer.writerow(['User ID', user_id])
                writer.writerow([''])
                
                # Write account info
                writer.writerow(['=== ACCOUNT INFO ==='])
                if account_info:
                    for key, value in account_info.items():
                        if isinstance(value, dict):
                            for sub_key, sub_value in value.items():
                                writer.writerow([f"{key}.{sub_key}", sub_value])
                        else:
                            writer.writerow([key, value])
                else:
                    writer.writerow(['No account info'])
                writer.writerow([''])
                
                # Write balances
                writer.writerow(['=== BALANCES ==='])
                writer.writerow(['Asset', 'Free', 'Locked', 'Total'])
                for balance in balances:
                    writer.writerow([
                        balance.get('asset', ''),
                        balance.get('free', 0),
                        balance.get('locked', 0),
                        balance.get('total', 0)
                    ])
                writer.writerow([''])
                
                # Write all trades (raw)
                writer.writerow(['=== ALL TRADES (RAW) ==='])
                if all_trades:
                    writer.writerow(['Symbol', 'Trade Data (JSON)'])
                    for symbol, trades in all_trades.items():
                        for trade in trades:
                            writer.writerow([symbol, json.dumps(trade)])
                else:
                    writer.writerow(['No trades found'])
                writer.writerow([''])
                
                # Write parsed trades details
                writer.writerow(['=== PARSED TRADES DETAILS ==='])
                writer.writerow(['Symbol', 'ID', 'Order ID', 'Price', 'Qty', 'Quote Qty', 'Commission', 
                                'Commission Asset', 'Time', 'Is Buyer', 'Is Maker', 'Trade'])
                for symbol, trades in all_trades.items():
                    for trade in trades:
                        writer.writerow([
                            symbol,
                            trade.get('id', ''),
                            trade.get('orderId', ''),
                            trade.get('price', ''),
                            trade.get('qty', ''),
                            trade.get('quoteQty', ''),
                            trade.get('commission', ''),
                            trade.get('commissionAsset', ''),
                            trade.get('time', ''),
                            trade.get('isBuyer', ''),
                            trade.get('isMaker', ''),
                            trade.get('trade', '')
                        ])
                writer.writerow([''])
                
                # Write fiat orders (if provided)
                writer.writerow(['=== FIAT ORDERS (RAW) ==='])
                if fiat_orders:
                    writer.writerow(['Order Data (JSON)'])
                    for order in fiat_orders:
                        writer.writerow([json.dumps(order)])
                else:
                    writer.writerow(['No fiat orders found'])
                writer.writerow([''])
                
                # Write portfolio items
                writer.writerow(['=== PORTFOLIO ITEMS ==='])
                if portfolio_items:
                    writer.writerow(['Symbol', 'Amount', 'Price Buy', 'Purchase Date', 'Base Currency', 
                                    'Source', 'Commission', 'Total Investment Text'])
                    for item in portfolio_items:
                        writer.writerow([
                            item.get('symbol', ''),
                            item.get('amount', 0),
                            item.get('price_buy', 0),
                            item.get('purchase_date', ''),
                            item.get('base_currency', ''),
                            item.get('source', ''),
                            item.get('commission', 0),
                            item.get('total_investment_text', '')
                        ])
                else:
                    writer.writerow(['No portfolio items'])
                writer.writerow([''])
                
                # Write summary
                writer.writerow(['=== SUMMARY ==='])
                writer.writerow(['Total Balances', len(balances)])
                total_trades = sum(len(trades) for trades in all_trades.values())
                writer.writerow(['Total Trades', total_trades])
                writer.writerow(['Total Portfolio Items', len(portfolio_items)])
                writer.writerow(['Items with Price Buy > 0', sum(1 for item in portfolio_items if item.get('price_buy', 0) > 0)])
                writer.writerow(['Items with Valid Purchase Date', sum(1 for item in portfolio_items if item.get('purchase_date') and item.get('purchase_date') != datetime.utcnow().isoformat())])
            
            logger.info(f"💾 Saved Binance import data to {csv_filename}")
            return csv_filename
            
        except Exception as e:
            logger.error(f"❌ Error saving import data to CSV: {e}")
            return ""

    async def calculate_portfolio_from_balances(self, balances: List[Dict]) -> Tuple[List[Dict], Dict[str, List], List[Dict]]:
        """Calculate portfolio items from account balances
        Returns: (portfolio_items, all_trades_collected, fiat_orders)
        """
        portfolio_items = []
        all_trades_collected = {}
        
        # Get fiat purchase history (card purchases) - these count as buys
        fiat_purchases = {}
        try:
            fiat_orders = await self.get_fiat_purchase_history()
            logger.info(f"📦 Found {len(fiat_orders)} fiat purchase orders")
            for order in fiat_orders:
                # Binance fiat order API returns different field names - try multiple variations
                crypto = (
                    order.get('cryptoType', '') or 
                    order.get('cryptoCurrency', '') or 
                    order.get('crypto', '') or
                    order.get('asset', '')
                ).upper()
                
                if crypto and crypto not in ['USDT', 'USDC', 'BUSD', 'TUSD']:
                    if crypto not in fiat_purchases:
                        fiat_purchases[crypto] = []
                    fiat_purchases[crypto].append(order)
                    logger.info(f"✅ Fiat purchase found: {crypto} - order keys: {list(order.keys())[:10]}")
                    logger.debug(f"Fiat purchase details: {order}")
        except Exception as e:
            logger.warning(f"Could not get fiat purchase history: {e}")
        
        for balance in balances:
            asset = balance['asset']
            total_amount = balance['total']
            
            # Skip USDT and other stablecoins as they're not crypto investments
            if asset in ['USDT', 'USDC', 'BUSD', 'TUSD', 'USDP']:
                continue
            
            # Get trading history to calculate average buy price
            # Try multiple trading pairs - Binance uses various quote currencies
            trading_pairs = [
                f"{asset}USDT", f"{asset}BUSD", f"{asset}USDC",  # Stablecoins
                f"{asset}BTC", f"{asset}ETH", f"{asset}BNB",     # Crypto pairs
                f"{asset}EUR", f"{asset}GBP"                      # Fiat pairs
            ]
            buy_trades = []
            
            logger.info(f"🔍 Looking for trades for {asset} in pairs: {trading_pairs}")
            
            # Check fiat purchases for this asset (from the pre-fetched list)
            if asset in fiat_purchases:
                logger.info(f"Found {len(fiat_purchases[asset])} fiat purchases for {asset}")
                for fiat_order in fiat_purchases[asset]:
                    try:
                        # Binance fiat order fields may vary - try multiple field names
                        crypto_amount = float(fiat_order.get('cryptoAmount', fiat_order.get('obtainAmount', 0)))
                        fiat_amount = float(fiat_order.get('totalPrice', fiat_order.get('fiatAmount', 0)))
                        order_time = fiat_order.get('createTime', fiat_order.get('createTimestamp', 0))
                        
                        if crypto_amount > 0 and fiat_amount > 0:
                            # Calculate price: total fiat paid / crypto amount
                            price_per_unit = fiat_amount / crypto_amount
                            
                            buy_trades.append({
                                'symbol': f"{asset}FIAT",
                                'qty': crypto_amount,
                                'price': price_per_unit,
                                'time': order_time if order_time else int(time.time() * 1000),
                                'commission': 0.0,
                            })
                            logger.info(f"✅ Added fiat purchase: {asset} amount={crypto_amount}, total_price=${fiat_amount:.2f}, price_per_unit=${price_per_unit:.4f}, time={order_time}")
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Error parsing fiat purchase for {asset}: {e}, order: {fiat_order}")
                        continue
            
            for pair in trading_pairs:
                try:
                    trades = await self.get_trading_history(pair, 1000)
                    if trades:
                        all_trades_collected[pair] = trades
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
                            logger.debug(f"Added buy trade: {asset} pair={pair}, qty={trade.get('qty', 0)}, price={trade.get('price', 0)}, time={trade.get('time', 0)}")
                except Exception as e:
                    logger.warning(f"Error processing trades for {pair}: {e}")
                    continue
            
            # Add fiat purchases to buy trades
            buy_trades.extend(fiat_purchases)
            
            logger.info(f"Total buy trades found for {asset}: {len(buy_trades)} (including {len(fiat_purchases)} fiat purchases)")
            
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
                    # Convert to UTC datetime and format for PostgreSQL (ISO format without Z)
                    trade_dt = datetime.utcfromtimestamp(earliest_trade['time'] / 1000)
                    trade_date = trade_dt.isoformat()
                    
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
                purchase_date = datetime.utcnow().isoformat()
                portfolio_items.append({
                    'symbol': asset,
                    'amount': total_amount,
                    'price_buy': 0.0,  # Unknown price
                    'purchase_date': purchase_date,
                    'base_currency': 'USDT',
                    'source': 'Binance',
                    'commission': 0.0,
                    'total_investment_text': "Unknown"
                })
                logger.warning(f"⚠️ No buy trades found for {asset}, using placeholder with current date: {purchase_date}")
        
        logger.info(f"✅ Calculated {len(portfolio_items)} portfolio items from Binance balances")
        logger.info(f"📊 Collected {sum(len(trades) for trades in all_trades_collected.values())} total trades for analysis")
        # Return fiat orders as well for CSV export
        fiat_orders_list = []
        for asset_orders in fiat_purchases.values():
            fiat_orders_list.extend(asset_orders)
        return portfolio_items, all_trades_collected, fiat_orders_list
    
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
            
            # Calculate portfolio items (this will also collect all trades)
            portfolio_items, all_trades_collected, fiat_orders = await self.calculate_portfolio_from_balances(balances)
            
            logger.info(f"✅ Binance import completed: {len(portfolio_items)} items ready for import")
            
            # Save full import data to CSV for analysis
            csv_file = self._save_import_data_to_csv(
                user_id, 
                balances, 
                all_trades_collected, 
                portfolio_items, 
                connection_test.get('account_info', {}),
                fiat_orders
            )
            
            if csv_file:
                logger.info(f"📄 Full import data saved to: {csv_file}")
            
            return {
                'success': True,
                'message': f"Successfully prepared {len(portfolio_items)} portfolio items for import",
                'items_imported': len(portfolio_items),
                'portfolio_items': portfolio_items,
                'account_info': connection_test,
                'debug_csv': csv_file if csv_file else None
            }
            
        except Exception as e:
            logger.error(f"❌ Binance portfolio import failed: {e}")
            # Still try to save what we have
            try:
                csv_file = self._save_import_data_to_csv(
                    user_id,
                    balances if 'balances' in locals() else [],
                    all_trades_collected if 'all_trades_collected' in locals() else {},
                    portfolio_items if 'portfolio_items' in locals() else [],
                    {},
                    fiat_orders if 'fiat_orders' in locals() else []
                )
            except:
                pass
            return {
                'success': False,
                'message': f"Import failed: {str(e)}",
                'items_imported': 0,
                'error': str(e)
            }
