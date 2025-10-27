#!/usr/bin/env python3
"""
Fixed Binance API test with proper signature generation
"""
import argparse
import requests
import time
import hmac
import hashlib
import urllib.parse

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

def test_with_requests_lib(api_key: str, api_secret: str):
    """Test using requests library with proper URL encoding"""
    print("🔧 Testing with requests library...")
    
    try:
        # Get server time first
        server_time_response = requests.get(f"{API_URL}/time", timeout=10)
        if server_time_response.status_code != 200:
            print("❌ Cannot get server time")
            return False
        
        server_time = server_time_response.json()['serverTime']
        timestamp = server_time
        
        # Create query string
        query_string = f"timestamp={timestamp}"
        signature = generate_signature(query_string, api_secret)
        
        print(f"   Server time: {server_time}")
        print(f"   Query string: {query_string}")
        print(f"   Signature: {signature}")
        
        # Make request with proper headers
        headers = {
            'X-MBX-APIKEY': api_key
        }
        
        params = {
            'timestamp': timestamp,
            'signature': signature
        }
        
        response = requests.get(f"{API_URL}/account", params=params, headers=headers, timeout=10)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:200]}...")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success! Account type: {data.get('accountType')}")
            print(f"   Balances: {len(data.get('balances', []))}")
            
            # Show non-zero balances
            non_zero = [b for b in data.get('balances', []) if float(b.get('free', 0)) + float(b.get('locked', 0)) > 0]
            print(f"   Non-zero balances: {len(non_zero)}")
            
            for balance in non_zero[:5]:
                free = float(balance.get('free', 0))
                locked = float(balance.get('locked', 0))
                total = free + locked
                print(f"     {balance.get('asset')}: {total}")
            
            return True
        else:
            print(f"❌ Failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_with_manual_url(api_key: str, api_secret: str):
    """Test with manually constructed URL"""
    print("\n🔧 Testing with manual URL construction...")
    
    try:
        # Get server time
        server_time_response = requests.get(f"{API_URL}/time", timeout=10)
        server_time = server_time_response.json()['serverTime']
        
        # Manual URL construction
        timestamp = server_time
        query_string = f"timestamp={timestamp}"
        signature = generate_signature(query_string, api_secret)
        
        url = f"{API_URL}/account?timestamp={timestamp}&signature={signature}"
        
        headers = {
            'X-MBX-APIKEY': api_key
        }
        
        print(f"   URL: {url}")
        print(f"   Headers: {headers}")
        
        response = requests.get(url, headers=headers, timeout=10)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:200]}...")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success! Account type: {data.get('accountType')}")
            return True
        else:
            print(f"❌ Failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_api_key_validity(api_key: str, api_secret: str):
    """Test if API key is valid by checking different endpoints"""
    print("\n🔍 Testing API key validity...")
    
    # Test 1: Server info (no auth)
    try:
        response = requests.get(f"{API_URL}/exchangeInfo", timeout=10)
        print(f"   Exchange info: {response.status_code}")
    except Exception as e:
        print(f"   Exchange info error: {e}")
    
    # Test 2: 24hr ticker (no auth)
    try:
        response = requests.get(f"{API_URL}/ticker/24hr?symbol=BTCUSDT", timeout=10)
        print(f"   24hr ticker: {response.status_code}")
    except Exception as e:
        print(f"   24hr ticker error: {e}")
    
    # Test 3: Account status (requires auth)
    try:
        timestamp = get_timestamp()
        query_string = f"timestamp={timestamp}"
        signature = generate_signature(query_string, api_secret)
        
        headers = {'X-MBX-APIKEY': api_key}
        params = {'timestamp': timestamp, 'signature': signature}
        
        response = requests.get(f"{API_URL}/api/v3/account/status", params=params, headers=headers, timeout=10)
        print(f"   Account status: {response.status_code} - {response.text[:100]}")
    except Exception as e:
        print(f"   Account status error: {e}")

def main():
    parser = argparse.ArgumentParser(description='Fixed Binance API test')
    parser.add_argument('--api-key', required=True, help='Binance API Key')
    parser.add_argument('--api-secret', required=True, help='Binance API Secret')
    args = parser.parse_args()
    
    print("🚀 Fixed Binance API Test")
    print("=" * 50)
    print(f"API Key: {args.api_key[:10]}...{args.api_key[-10:]}")
    print(f"API Secret: {args.api_secret[:10]}...{args.api_secret[-10:]}")
    print()
    
    # Test API key validity
    test_api_key_validity(args.api_key, args.api_secret)
    
    # Test with requests library
    if test_with_requests_lib(args.api_key, args.api_secret):
        print("\n✅ Portfolio import should work!")
    else:
        # Try manual URL construction
        if test_with_manual_url(args.api_key, args.api_secret):
            print("\n✅ Portfolio import should work!")
        else:
            print("\n❌ Still having issues. Let's check the API key configuration.")

if __name__ == "__main__":
    main()
