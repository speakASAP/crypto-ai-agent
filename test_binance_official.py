#!/usr/bin/env python3
"""
Test script using official python-binance library
"""
import argparse
from binance.client import Client

def test_binance_connection(api_key: str, api_secret: str):
    """Test Binance API connection using official library"""
    print("🔍 Testing Binance API connection with official library...")
    
    try:
        # Create client
        client = Client(api_key, api_secret)
        
        # Test 1: Server time
        print("\n1. Testing server time...")
        server_time = client.get_server_time()
        print(f"✅ Server time: {server_time['serverTime']}")
        
        # Test 2: Account info
        print("\n2. Testing account info...")
        account_info = client.get_account()
        print(f"✅ Account info retrieved successfully!")
        print(f"   Account type: {account_info.get('accountType', 'Unknown')}")
        print(f"   Can trade: {account_info.get('canTrade', False)}")
        print(f"   Can withdraw: {account_info.get('canWithdraw', False)}")
        print(f"   Can deposit: {account_info.get('canDeposit', False)}")
        print(f"   Balances count: {len(account_info.get('balances', []))}")
        
        # Show some balances
        balances = account_info.get('balances', [])
        non_zero_balances = [b for b in balances if float(b['free']) > 0 or float(b['locked']) > 0]
        if non_zero_balances:
            print(f"\n   Non-zero balances:")
            for balance in non_zero_balances[:5]:  # Show first 5
                free = float(balance['free'])
                locked = float(balance['locked'])
                total = free + locked
                if total > 0:
                    print(f"     {balance['asset']}: {total} (free: {free}, locked: {locked})")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test Binance API with official library')
    parser.add_argument('--api-key', required=True, help='Binance API Key')
    parser.add_argument('--api-secret', required=True, help='Binance API Secret')
    args = parser.parse_args()
    
    success = test_binance_connection(args.api_key, args.api_secret)
    if success:
        print("\n🎉 Binance API connection successful!")
    else:
        print("\n💥 Binance API connection failed!")
