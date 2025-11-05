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
    
    async def get_trading_history(self, symbol: str, limit: int = 1000, start_time: int = None, end_time: int = None) -> List[Dict]:
        """Get trading history for a specific symbol using official library
        Can fetch historical data with time ranges (up to 2 years)
        """
        try:
            # Use official Binance library for proper signature handling
            client = BinanceClient(self.api_key, self.api_secret)
            
            # Get trades - with time range if provided
            if start_time and end_time:
                # Binance get_my_trades API doesn't support time range directly
                # We need to get all trades and filter by time
                # Note: Binance typically only returns last 3 months of detailed trades
                # For older trades, we rely on orders history
                all_trades = []
                try:
                    # Try to get all available trades (last 1000 trades, which is Binance limit)
                    all_historical_trades = client.get_my_trades(symbol=symbol, limit=1000)
                    
                    # Filter by time range
                    all_trades = [
                        t for t in all_historical_trades 
                        if start_time <= t.get('time', 0) <= end_time
                    ]
                    
                    logger.info(f"✅ Retrieved {len(all_trades)} historical trades for {symbol} (filtered from {len(all_historical_trades)} total trades, time range: {datetime.fromtimestamp(start_time/1000).strftime('%Y-%m-%d')} to {datetime.fromtimestamp(end_time/1000).strftime('%Y-%m-%d')})")
                except Exception as e:
                    logger.warning(f"⚠️ Error getting historical trades for {symbol}: {e}")
                    all_trades = []
                
                return all_trades
            else:
                # Get recent trades (no time range)
                trades = client.get_my_trades(symbol=symbol, limit=limit)
                logger.info(f"✅ Retrieved {len(trades)} trades for {symbol}")
                return trades
                        
        except Exception as e:
            logger.warning(f"⚠️ Error getting trading history for {symbol}: {e}")
            return []
    
    async def get_fiat_payments(self, start_time: int = None, end_time: int = None) -> List[Dict]:
        """Get fiat payment history (buy/sell) from Binance using /sapi/v1/fiat/payments endpoint
        This endpoint provides buy/sell history with prices and dates
        Reference: https://www.binance.com/en/my/wallet/exchange/buysell-history
        Supports pagination to get ALL available data
        """
        try:
            base_url = "https://api.binance.com"
            endpoint = "/sapi/v1/fiat/payments"
            
            all_payments = []
            
            # Default time range: last 2 years (extend if possible)
            if not end_time:
                end_time = int(time.time() * 1000)  # Current time in milliseconds
            if not start_time:
                start_time = end_time - (2 * 365 * 24 * 60 * 60 * 1000)  # 2 years ago
            
            logger.info(f"📅 Fetching fiat payments from {datetime.fromtimestamp(start_time/1000).strftime('%Y-%m-%d')} to {datetime.fromtimestamp(end_time/1000).strftime('%Y-%m-%d')}")
            
            # Get both buy (transactionType=0) and sell (transactionType=1) payments
            for transaction_type in ['0', '1']:
                page = 1
                rows_per_page = 500  # Maximum rows per page
                has_more = True
                
                while has_more:
                    try:
                        timestamp = self._get_timestamp()
                        params = {
                            'transactionType': transaction_type,
                            'beginTime': str(start_time),
                            'endTime': str(end_time),
                            'timestamp': str(timestamp),
                            'rows': str(rows_per_page),
                            'page': str(page)
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
                                    payments = result.get('data', [])
                                    total = result.get('total', len(payments))
                                    
                                    if payments:
                                        all_payments.extend(payments)
                                        logger.info(f"✅ Retrieved page {page}: {len(payments)} fiat payments (type={transaction_type}, buy={'Buy' if transaction_type == '0' else 'Sell'}, total={total})")
                                        
                                        # Check if there are more pages
                                        if len(payments) < rows_per_page or len(all_payments) >= total:
                                            has_more = False
                                        else:
                                            page += 1
                                            await asyncio.sleep(0.1)  # Small delay to avoid rate limits
                                    else:
                                        has_more = False
                                else:
                                    error_text = await response.text()
                                    logger.warning(f"⚠️ Fiat payments API (type={transaction_type}, page={page}) returned status {response.status}: {error_text}")
                                    has_more = False
                    except Exception as e:
                        logger.warning(f"Error getting fiat payments type {transaction_type}, page {page}: {e}")
                        has_more = False
                        continue
            
            logger.info(f"✅ Retrieved {len(all_payments)} total fiat payments (buy/sell history) with pagination")
            return all_payments
                        
        except Exception as e:
            logger.warning(f"⚠️ Error getting fiat payment history: {e}")
            return []
    
    async def get_fiat_orders(self, start_time: int = None, end_time: int = None) -> List[Dict]:
        """Get fiat orders from Binance using /sapi/v1/fiat/orders endpoint
        This is different from fiat payments - orders may contain additional transaction data
        Supports pagination to get ALL available data
        """
        try:
            base_url = "https://api.binance.com"
            endpoint = "/sapi/v1/fiat/orders"
            
            all_orders = []
            
            # Default time range: last 2 years
            if not end_time:
                end_time = int(time.time() * 1000)
            if not start_time:
                start_time = end_time - (2 * 365 * 24 * 60 * 60 * 1000)  # 2 years ago
            
            logger.info(f"📅 Fetching fiat orders from {datetime.fromtimestamp(start_time/1000).strftime('%Y-%m-%d')} to {datetime.fromtimestamp(end_time/1000).strftime('%Y-%m-%d')}")
            
            # Get both buy (transactionType=0) and sell (transactionType=1) orders
            for transaction_type in ['0', '1']:
                page = 1
                rows_per_page = 500  # Maximum rows per page
                has_more = True
                
                while has_more:
                    try:
                        timestamp = self._get_timestamp()
                        params = {
                            'transactionType': transaction_type,
                            'beginTime': str(start_time),
                            'endTime': str(end_time),
                            'timestamp': str(timestamp),
                            'rows': str(rows_per_page),
                            'page': str(page)
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
                                    total = result.get('total', len(orders))
                                    
                                    if orders:
                                        all_orders.extend(orders)
                                        logger.info(f"✅ Retrieved page {page}: {len(orders)} fiat orders (type={transaction_type}, buy={'Buy' if transaction_type == '0' else 'Sell'}, total={total})")
                                        
                                        # Check if there are more pages
                                        if len(orders) < rows_per_page or len(all_orders) >= total:
                                            has_more = False
                                        else:
                                            page += 1
                                            await asyncio.sleep(0.1)  # Small delay to avoid rate limits
                                    else:
                                        has_more = False
                                else:
                                    error_text = await response.text()
                                    logger.warning(f"⚠️ Fiat orders API (type={transaction_type}, page={page}) returned status {response.status}: {error_text}")
                                    has_more = False
                    except Exception as e:
                        logger.warning(f"Error getting fiat orders type {transaction_type}, page {page}: {e}")
                        has_more = False
                        continue
            
            logger.info(f"✅ Retrieved {len(all_orders)} total fiat orders with pagination")
            return all_orders
                        
        except Exception as e:
            logger.warning(f"⚠️ Error getting fiat orders: {e}")
            return []
    
    async def get_fiat_purchase_history(self) -> List[Dict]:
        """Get both fiat payments and fiat orders - all available data"""
        payments = await self.get_fiat_payments()
        orders = await self.get_fiat_orders()
        logger.info(f"📦 Combined: {len(payments)} fiat payments + {len(orders)} fiat orders = {len(payments) + len(orders)} total records")
        return payments + orders
    
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
    
    async def get_deposit_history_full(self) -> List[Dict]:
        """Get complete deposit history with all assets"""
        try:
            client = BinanceClient(self.api_key, self.api_secret)
            
            # Get all deposits (no asset filter)
            deposits = client.get_deposit_history()
            logger.info(f"✅ Retrieved {len(deposits)} total deposits")
            return deposits
        except Exception as e:
            logger.warning(f"⚠️ Error getting deposit history: {e}")
            return []
    
    async def get_withdrawal_history_full(self) -> List[Dict]:
        """Get complete withdrawal history with all assets"""
        try:
            client = BinanceClient(self.api_key, self.api_secret)
            
            # Get all withdrawals
            withdrawals = client.get_withdrawal_history()
            logger.info(f"✅ Retrieved {len(withdrawals)} total withdrawals")
            return withdrawals
        except Exception as e:
            logger.warning(f"⚠️ Error getting withdrawal history: {e}")
            return []
    
    async def get_all_orders(self, symbol: str = None, limit: int = 1000, start_time: int = None, end_time: int = None) -> List[Dict]:
        """Get all orders (open and historical) - this can help find buy prices
        Can fetch historical data for up to 2 years
        """
        try:
            client = BinanceClient(self.api_key, self.api_secret)
            
            # Get all orders (filled, cancelled, etc.)
            if symbol:
                if start_time and end_time:
                    # Get historical orders with time range
                    orders = client.get_all_orders(
                        symbol=symbol, 
                        limit=limit,
                        startTime=start_time,
                        endTime=end_time
                    )
                    logger.info(f"✅ Retrieved {len(orders)} historical orders for {symbol} (from {datetime.fromtimestamp(start_time/1000).strftime('%Y-%m-%d')} to {datetime.fromtimestamp(end_time/1000).strftime('%Y-%m-%d')})")
                else:
                    # Get recent orders
                    orders = client.get_all_orders(symbol=symbol, limit=limit)
                    logger.info(f"✅ Retrieved {len(orders)} orders for {symbol}")
            else:
                # Cannot get all orders without symbol
                orders = []
                logger.debug("Cannot get all orders without symbol - need symbol parameter")
            
            return orders
        except Exception as e:
            logger.debug(f"Could not get all orders: {e}")
            return []
    
    def _save_import_data_to_csv(self, user_id: int, balances: List[Dict], all_trades: Dict[str, List], 
                                 portfolio_items: List[Dict], account_info: Dict = None, fiat_payments: List[Dict] = None,
                                 fiat_orders: List[Dict] = None, deposits: List[Dict] = None, withdrawals: List[Dict] = None) -> str:
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
                
                # Write fiat payments (buy/sell history) (if provided)
                writer.writerow(['=== FIAT PAYMENTS (BUY/SELL HISTORY) ==='])
                if fiat_payments:
                    writer.writerow(['Payment Data (JSON)'])
                    for payment in fiat_payments:
                        writer.writerow([json.dumps(payment)])
                else:
                    writer.writerow(['No fiat payments found'])
                writer.writerow([''])
                
                # Write fiat orders (if provided)
                writer.writerow(['=== FIAT ORDERS ==='])
                if fiat_orders:
                    writer.writerow(['Order Data (JSON)'])
                    for order in fiat_orders:
                        writer.writerow([json.dumps(order)])
                else:
                    writer.writerow(['No fiat orders found'])
                writer.writerow([''])
                
                # Write deposit history
                writer.writerow(['=== DEPOSIT HISTORY ==='])
                if deposits:
                    writer.writerow(['Asset', 'Amount', 'Insert Time', 'Status', 'TxId', 'Address', 'Address Tag', 'Deposit Data (JSON)'])
                    for deposit in deposits:
                        writer.writerow([
                            deposit.get('asset', ''),
                            deposit.get('amount', ''),
                            deposit.get('insertTime', ''),
                            deposit.get('status', ''),
                            deposit.get('txId', ''),
                            deposit.get('address', ''),
                            deposit.get('addressTag', ''),
                            json.dumps(deposit)
                        ])
                else:
                    writer.writerow(['No deposits found'])
                writer.writerow([''])
                
                # Write withdrawal history
                writer.writerow(['=== WITHDRAWAL HISTORY ==='])
                if withdrawals:
                    writer.writerow(['Asset', 'Amount', 'Apply Time', 'Status', 'TxId', 'Address', 'Address Tag', 'Withdrawal Data (JSON)'])
                    for withdrawal in withdrawals:
                        writer.writerow([
                            withdrawal.get('asset', ''),
                            withdrawal.get('amount', ''),
                            withdrawal.get('applyTime', ''),
                            withdrawal.get('status', ''),
                            withdrawal.get('txId', ''),
                            withdrawal.get('address', ''),
                            withdrawal.get('addressTag', ''),
                            json.dumps(withdrawal)
                        ])
                else:
                    writer.writerow(['No withdrawals found'])
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

    async def calculate_portfolio_from_balances(self, balances: List[Dict]) -> Tuple[List[Dict], Dict[str, List], List[Dict], List[Dict]]:
        """Calculate portfolio items from account balances
        Returns: (portfolio_items, all_trades_collected, fiat_payments_list, fiat_orders_list)
        """
        portfolio_items = []
        all_trades_collected = {}
        
        # Calculate time range: last 5 years (Binance API limit is typically 3 months for detailed trades, but we try anyway)
        # For historical orders, we can go back further
        end_time = int(time.time() * 1000)  # Current time in milliseconds
        start_time = end_time - (5 * 365 * 24 * 60 * 60 * 1000)  # 5 years ago
        logger.info(f"📅 Fetching historical data from {datetime.fromtimestamp(start_time/1000).strftime('%Y-%m-%d')} to {datetime.fromtimestamp(end_time/1000).strftime('%Y-%m-%d')} (5 years)")
        
        # Get fiat payment history (buy/sell) - this includes crypto purchases with prices and dates
        # Get BOTH fiat payments and fiat orders separately
        fiat_purchases = {}
        fiat_payments_list = []
        fiat_orders_list = []
        try:
            # Get fiat payments (buy/sell history with crypto info)
            fiat_payments_list = await self.get_fiat_payments(start_time=start_time, end_time=end_time)
            logger.info(f"📦 Found {len(fiat_payments_list)} fiat payments (buy/sell history)")
            
            # Get fiat orders (may contain additional transaction data)
            fiat_orders_list = await self.get_fiat_orders(start_time=start_time, end_time=end_time)
            logger.info(f"📦 Found {len(fiat_orders_list)} fiat orders")
            
            # Process fiat payments for portfolio calculation
            for payment in fiat_payments_list:
                # Log the payment structure first to see what fields exist
                logger.info(f"🔍 Fiat payment structure - keys: {list(payment.keys())[:15]}")
                logger.debug(f"🔍 Fiat payment full data: {json.dumps(payment, indent=2)}")
                
                # Extract crypto information from payment
                # The /sapi/v1/fiat/payments endpoint should include crypto info
                crypto = (
                    payment.get('cryptoCurrency', '') or 
                    payment.get('cryptoType', '') or 
                    payment.get('asset', '') or
                    payment.get('crypto', '') or
                    payment.get('coin', '')
                ).upper()
                
                # Check if this is a buy transaction (transactionType=0)
                # NOTE: The transactionType is passed in the API call, not in the response
                # We need to check the payment data structure differently
                # For fiat payments, buy transactions typically have specific status or structure
                # Since we fetched type=0 (buy) and type=1 (sell) separately, we need to track which is which
                # For now, we'll check all payments and filter by status='Completed' or similar
                transaction_type = payment.get('transactionType', payment.get('type', ''))
                status = payment.get('status', '').upper()
                is_buy = (
                    str(transaction_type) == '0' or 
                    payment.get('side', '').upper() == 'BUY' or
                    status in ['COMPLETED', 'SUCCESS', 'SUCCESSFUL', '1', '2']
                )
                
                logger.info(f"🔍 Processing fiat payment: crypto='{crypto}', transaction_type='{transaction_type}', status='{status}', is_buy={is_buy}")
                
                if crypto and crypto not in ['USDT', 'USDC', 'BUSD', 'TUSD', ''] and is_buy:
                    if crypto not in fiat_purchases:
                        fiat_purchases[crypto] = []
                    fiat_purchases[crypto].append(payment)
                    logger.info(f"✅ Fiat buy payment found: {crypto} - amount={payment.get('obtainAmount', 'N/A')}, price={payment.get('price', 'N/A')}, date={payment.get('createTime', 'N/A')}")
                else:
                    logger.info(f"⚠️ Fiat payment skipped - crypto: '{crypto}', is_buy: {is_buy}, transaction_type: {transaction_type}, status: {status}")
        except Exception as e:
            logger.warning(f"Could not get fiat payment history: {e}")
        
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
            
            logger.info(f"🔍 Looking for trades for {asset} in pairs: {trading_pairs} (last 2 years)")
            
            # ALSO try to get ALL orders (filled orders show buy prices) - historical data
            try:
                all_orders = await self.get_all_orders(f"{asset}USDT", limit=1000, start_time=start_time, end_time=end_time)
                for order in all_orders:
                    # Check if it's a filled BUY order
                    if order.get('status') == 'FILLED' and order.get('side') == 'BUY':
                        executed_qty = float(order.get('executedQty', 0))
                        price = float(order.get('price', 0))
                        if executed_qty > 0 and price > 0:
                            buy_trades.append({
                                'symbol': f"{asset}USDT",
                                'qty': executed_qty,
                                'price': price,
                                'time': order.get('updateTime', order.get('time', 0)),
                                'commission': 0.0,  # Will be calculated from trades
                            })
                            logger.info(f"✅ Added filled BUY order: {asset} qty={executed_qty}, price={price}")
            except Exception as e:
                logger.debug(f"Could not get all orders for {asset}: {e}")
            
            # Get deposit history for this asset to find earliest arrival date (for buy date when no trades)
            deposit_history_for_asset = []
            earliest_deposit_time = None
            try:
                deposits = await self.get_deposit_history(asset)
                for deposit in deposits:
                    if deposit.get('status') == 1:  # 1 = Success
                        deposit_time = deposit.get('insertTime', 0)
                        deposit_history_for_asset.append({
                            'amount': float(deposit.get('amount', 0)),
                            'time': deposit_time,
                        })
                        # Track earliest deposit
                        if deposit_time > 0:
                            if earliest_deposit_time is None or deposit_time < earliest_deposit_time:
                                earliest_deposit_time = deposit_time
                if deposit_history_for_asset:
                    logger.info(f"✅ Found {len(deposit_history_for_asset)} deposits for {asset}, earliest: {datetime.fromtimestamp(earliest_deposit_time/1000).isoformat() if earliest_deposit_time else 'N/A'}")
            except Exception as e:
                logger.debug(f"Could not get deposit history for {asset}: {e}")
            
            # Check fiat payments (buy/sell) for this asset (from the pre-fetched list)
            if asset in fiat_purchases:
                logger.info(f"Found {len(fiat_purchases[asset])} fiat buy payments for {asset}")
                for fiat_payment in fiat_purchases[asset]:
                    try:
                        # Binance fiat payments endpoint fields - try multiple field name variations
                        crypto_amount = float(
                            fiat_payment.get('obtainAmount', 
                            fiat_payment.get('cryptoAmount',
                            fiat_payment.get('amount', 0)))
                        )
                        fiat_amount = float(
                            fiat_payment.get('totalPrice',
                            fiat_payment.get('fiatAmount',
                            fiat_payment.get('sourceAmount', 0)))
                        )
                        payment_time = (
                            fiat_payment.get('createTime',
                            fiat_payment.get('timestamp',
                            fiat_payment.get('updateTime',
                            fiat_payment.get('createTimestamp', 0))))
                        )
                        
                        if crypto_amount > 0 and fiat_amount > 0:
                            # Calculate price: total fiat paid / crypto amount
                            price_per_unit = fiat_amount / crypto_amount
                            
                            buy_trades.append({
                                'symbol': f"{asset}FIAT",
                                'qty': crypto_amount,
                                'price': price_per_unit,
                                'time': payment_time if payment_time else int(time.time() * 1000),
                                'commission': 0.0,
                            })
                            payment_date = datetime.fromtimestamp(payment_time/1000).isoformat() if payment_time else "N/A"
                            logger.info(f"✅ Added fiat buy payment: {asset} amount={crypto_amount}, total_price=${fiat_amount:.2f}, price_per_unit=${price_per_unit:.4f}, date={payment_date}")
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Error parsing fiat payment for {asset}: {e}, payment: {fiat_payment}")
                        continue
            
            for pair in trading_pairs:
                try:
                    # Get historical trades for last 2 years
                    trades = await self.get_trading_history(pair, limit=1000, start_time=start_time, end_time=end_time)
                    if trades:
                        all_trades_collected[pair] = trades
                    logger.info(f"Found {len(trades)} total trades for {pair} (historical)")
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
            
            # NOTE: Fiat purchases are already added to buy_trades in the loop above (lines 783-820)
            # We don't need to extend again here - fiat_purchases is a dict, not a list
            
            # Count fiat purchases for this asset
            fiat_count = len(fiat_purchases.get(asset, []))
            logger.info(f"Total buy trades found for {asset}: {len(buy_trades)} (including {fiat_count} fiat purchases)")
            
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
                    
                    # Get the EARLIEST trade date for purchase date (Buy Date)
                    earliest_trade = buy_trades[0]
                    # Convert to UTC datetime and format for PostgreSQL (ISO format without Z)
                    trade_dt = datetime.utcfromtimestamp(earliest_trade['time'] / 1000)
                    trade_date = trade_dt.isoformat()
                    logger.info(f"📅 Buy date for {asset}: {trade_date} (from earliest buy trade)")
                    
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
                # If no trading history, try to use deposit history date as buy date
                # This might be from airdrops, staking rewards, transfers, or other sources
                if earliest_deposit_time and earliest_deposit_time > 0:
                    # Use earliest deposit date as buy date
                    deposit_dt = datetime.utcfromtimestamp(earliest_deposit_time / 1000)
                    purchase_date = deposit_dt.isoformat()
                    logger.info(f"📅 Buy date for {asset}: {purchase_date} (from earliest deposit - no trades found)")
                else:
                    # Fallback to current date if no deposits either
                    purchase_date = datetime.utcnow().isoformat()
                    logger.warning(f"⚠️ No buy trades or deposits found for {asset}, using current date: {purchase_date}")
                
                portfolio_items.append({
                    'symbol': asset,
                    'amount': total_amount,
                    'price_buy': 0.0,  # Unknown price
                    'purchase_date': purchase_date,  # Buy date from deposit or current date
                    'base_currency': 'USDT',
                    'source': 'Binance',
                    'commission': 0.0,
                    'total_investment_text': "Unknown"
                })
        
        logger.info(f"✅ Calculated {len(portfolio_items)} portfolio items from Binance balances")
        logger.info(f"📊 Collected {sum(len(trades) for trades in all_trades_collected.values())} total trades for analysis")
        # Return fiat payments and orders for CSV export
        # Note: fiat_payments_list is already defined in the try block above
        # fiat_orders_list is also already defined
        # We need to return both separately
        return portfolio_items, all_trades_collected, fiat_payments_list, fiat_orders_list
    
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
            
            # Get additional data: deposits, withdrawals
            logger.info("📥 Fetching deposit history...")
            all_deposits = await self.get_deposit_history_full()
            
            logger.info("📤 Fetching withdrawal history...")
            all_withdrawals = await self.get_withdrawal_history_full()
            
            # Calculate portfolio items (this will also collect all trades)
            portfolio_items, all_trades_collected, fiat_payments_list, fiat_orders_list = await self.calculate_portfolio_from_balances(balances)
            
            logger.info(f"✅ Binance import completed: {len(portfolio_items)} items ready for import")
            
            # Save full import data to CSV for analysis
            csv_file = self._save_import_data_to_csv(
                user_id, 
                balances, 
                all_trades_collected, 
                portfolio_items, 
                connection_test.get('account_info', {}),
                fiat_payments_list,
                fiat_orders_list,
                all_deposits,
                all_withdrawals
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
                    fiat_payments_list if 'fiat_payments_list' in locals() else [],
                    fiat_orders_list if 'fiat_orders_list' in locals() else [],
                    all_deposits if 'all_deposits' in locals() else [],
                    all_withdrawals if 'all_withdrawals' in locals() else []
                )
            except:
                pass
            return {
                'success': False,
                'message': f"Import failed: {str(e)}",
                'items_imported': 0,
                'error': str(e)
            }
