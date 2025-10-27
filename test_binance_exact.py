#!/usr/bin/env python3
"""
Test script using exact same method as python-binance library
"""
import argparse
import hmac
import hashlib
import time
import requests
from urllib.parse import urlencode

API_URL = "https://api.binance.com/api/v3"

def generate_signature(query_string: str, secret: str) -> str:
    """Generate HMAC SHA256 signature for Binance API"""
    return hmac.new(
        secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def get_timestamp() -> int:
    """Get current timestamp in milliseconds"""
    return int(time.time() * 1000)

def test_exact_binance_method(api_key: str, api_secret: str):
    """Test using exact same method as python-binance"""
    print("🔍 Testing with exact python-binance method...")
    
    try:
        # Test 1: Server time
        print("\n1. Testing server time...")
        response = requests.get(f"{API_URL}/time", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Server time: {data['serverTime']}")
        else:
            print(f"❌ Server time failed: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Server time error: {e}")
        return
    
    # Test 2: Account info with exact python-binance method
    print("\n2. Testing account info with exact method...")
    
    timestamp = get_timestamp()
    headers = {'X-MBX-APIKEY': api_key}
    
    # Method 1: Exact same as python-binance
    params = {'timestamp': timestamp}
    query_string = urlencode(params)
    signature = generate_signature(query_string, api_secret)
    
    # Add signature to params
    params['signature'] = signature
    
    print(f"   Timestamp: {timestamp}")
    print(f"   Query string: {query_string}")
    print(f"   Signature: {signature}")
    print(f"   Full params: {params}")
    
    # Try different ways to send the request
    print("\n   Trying different request methods...")
    
    # Method 1: Direct URL
    url1 = f"{API_URL}/account?{query_string}&signature={signature}"
    response1 = requests.get(url1, headers=headers, timeout=10)
    print(f"   Method 1 (direct URL): {response1.status_code} - {response1.text[:100]}")
    
    # Method 2: Using requests params
    response2 = requests.get(f"{API_URL}/account", params=params, headers=headers, timeout=10)
    print(f"   Method 2 (requests params): {response2.status_code} - {response2.text[:100]}")
    
    # Method 3: Manual headers
    headers3 = {
        'X-MBX-APIKEY': api_key,
        'Content-Type': 'application/json'
    }
    response3 = requests.get(f"{API_URL}/account", params=params, headers=headers3, timeout=10)
    print(f"   Method 3 (with content-type): {response3.status_code} - {response3.text[:100]}")
    
    # Method 4: Try with different parameter order
    params4 = {'signature': signature, 'timestamp': timestamp}
    response4 = requests.get(f"{API_URL}/account", params=params4, headers=headers, timeout=10)
    print(f"   Method 4 (different order): {response4.status_code} - {response4.text[:100]}")
    
    # Check if any method worked
    for i, response in enumerate([response1, response2, response3, response4], 1):
        if response.status_code == 200:
            print(f"\n✅ Method {i} worked!")
            data = response.json()
            print(f"   Account type: {data.get('accountType', 'Unknown')}")
            print(f"   Can trade: {data.get('canTrade', False)}")
            print(f"   Balances count: {len(data.get('balances', []))}")
            return True
    
    print(f"\n❌ All methods failed")
    return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test Binance API with exact python-binance method')
    parser.add_argument('--api-key', required=True, help='Binance API Key')
    parser.add_argument('--api-secret', required=True, help='Binance API Secret')
    args = parser.parse_args()
    
    success = test_exact_binance_method(args.api_key, args.api_secret)
    if not success:
        print("\n💡 The issue is likely that the API key doesn't have 'Enable Reading' permission enabled.")
        print("   Please check your Binance account settings and enable 'Enable Reading' permission for this API key.")
