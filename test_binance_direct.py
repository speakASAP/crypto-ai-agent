#!/usr/bin/env python3
"""
Direct test of Binance API credentials
"""
import argparse
import requests
import time
import hmac
import hashlib

API_URL = "https://api.binance.com/api/v3"

def generate_signature(query_string: str, secret: str):
    """Generate HMAC SHA256 signature"""
    return hmac.new(
        secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def get_timestamp():
    """Get current timestamp in milliseconds"""
    return int(time.time() * 1000)

def test_server_time():
    """Test server time endpoint (no auth required)"""
    print("🕐 Testing server time endpoint...")
    try:
        response = requests.get(f"{API_URL}/time", timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Server time: {data['serverTime']}")
            return True
        else:
            print(f"❌ Server time failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Server time error: {e}")
        return False

def test_account_info(api_key: str, api_secret: str):
    """Test account info endpoint (requires auth)"""
    print("\n🔐 Testing account info endpoint...")
    try:
        # Get server time first to ensure timestamp is synchronized
        server_time_response = requests.get(f"{API_URL}/time", timeout=10)
        if server_time_response.status_code != 200:
            print("❌ Cannot get server time")
            return False
        
        server_time = server_time_response.json()['serverTime']
        timestamp = server_time
        
        query_string = f"timestamp={timestamp}"
        signature = generate_signature(query_string, api_secret)
        
        print(f"   Server time: {server_time}")
        print(f"   Local time: {get_timestamp()}")
        print(f"   Time diff: {abs(server_time - get_timestamp())} ms")
        print(f"   Query string: {query_string}")
        print(f"   Signature: {signature[:20]}...")
        
        url = f"{API_URL}/account"
        params = {
            'timestamp': timestamp,
            'signature': signature
        }
        
        headers = {
            'X-MBX-APIKEY': api_key
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Account info retrieved successfully")
            print(f"   Account Type: {data.get('accountType', 'Unknown')}")
            print(f"   Can Trade: {data.get('canTrade', False)}")
            print(f"   Can Withdraw: {data.get('canWithdraw', False)}")
            print(f"   Balances Count: {len(data.get('balances', []))}")
            
            # Show non-zero balances
            non_zero_balances = [b for b in data.get('balances', []) if float(b.get('free', 0)) + float(b.get('locked', 0)) > 0]
            print(f"   Non-zero balances: {len(non_zero_balances)}")
            
            if non_zero_balances:
                print("   Top balances:")
                for balance in non_zero_balances[:5]:
                    free = float(balance.get('free', 0))
                    locked = float(balance.get('locked', 0))
                    total = free + locked
                    print(f"     {balance.get('asset')}: {total}")
            
            return True
        else:
            print(f"❌ Account info failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Account info error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Direct Binance API test')
    parser.add_argument('--api-key', required=True, help='Binance API Key')
    parser.add_argument('--api-secret', required=True, help='Binance API Secret')
    args = parser.parse_args()
    
    print("🚀 Direct Binance API Test")
    print("=" * 40)
    print(f"API URL: {API_URL}")
    print(f"API Key: {args.api_key[:10]}...{args.api_key[-10:]}")
    print(f"API Secret: {args.api_secret[:10]}...{args.api_secret[-10:]}")
    print()
    
    # Test 1: Server time
    if not test_server_time():
        print("❌ Cannot proceed - server time test failed")
        return
    
    # Test 2: Account info
    if test_account_info(args.api_key, args.api_secret):
        print("\n✅ All tests passed! Your Binance API credentials are working.")
    else:
        print("\n❌ Account info test failed. Check your API key permissions.")
        print("Make sure to enable 'Enable Reading' permission in Binance API Management.")

if __name__ == "__main__":
    main()
