#!/usr/bin/env python3
"""
Test script using urllib.parse for proper query string encoding
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

def test_binance_with_urllib(api_key: str, api_secret: str):
    """Test Binance API with proper URL encoding"""
    print("🔍 Testing Binance API with urllib.parse...")
    
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
    
    # Test 2: Account info with different encoding methods
    print("\n2. Testing account info with different encoding methods...")
    
    timestamp = get_timestamp()
    headers = {'X-MBX-APIKEY': api_key}
    
    # Method 1: Manual query string
    query_string1 = f"timestamp={timestamp}"
    signature1 = generate_signature(query_string1, api_secret)
    url1 = f"{API_URL}/account?{query_string1}&signature={signature1}"
    print(f"   Method 1 - Manual: {query_string1}")
    print(f"   Signature 1: {signature1}")
    response1 = requests.get(url1, headers=headers, timeout=10)
    print(f"   Result 1: {response1.status_code} - {response1.text[:100]}")
    
    # Method 2: Using urllib.parse
    params2 = {'timestamp': timestamp}
    query_string2 = urlencode(params2)
    signature2 = generate_signature(query_string2, api_secret)
    url2 = f"{API_URL}/account?{query_string2}&signature={signature2}"
    print(f"   Method 2 - urllib: {query_string2}")
    print(f"   Signature 2: {signature2}")
    response2 = requests.get(url2, headers=headers, timeout=10)
    print(f"   Result 2: {response2.status_code} - {response2.text[:100]}")
    
    # Method 3: Using requests params (let requests handle encoding)
    params3 = {'timestamp': timestamp, 'signature': signature2}
    response3 = requests.get(f"{API_URL}/account", params=params3, headers=headers, timeout=10)
    print(f"   Method 3 - requests params: {response3.status_code} - {response3.text[:100]}")
    
    # Method 4: Try with different timestamp format
    timestamp_str = str(timestamp)
    params4 = {'timestamp': timestamp_str}
    query_string4 = urlencode(params4)
    signature4 = generate_signature(query_string4, api_secret)
    url4 = f"{API_URL}/account?{query_string4}&signature={signature4}"
    print(f"   Method 4 - String timestamp: {query_string4}")
    print(f"   Signature 4: {signature4}")
    response4 = requests.get(url4, headers=headers, timeout=10)
    print(f"   Result 4: {response4.status_code} - {response4.text[:100]}")
    
    # Check if any method worked
    if response1.status_code == 200:
        print(f"\n✅ Method 1 worked!")
        data = response1.json()
        print(f"   Account type: {data.get('accountType', 'Unknown')}")
        print(f"   Can trade: {data.get('canTrade', False)}")
    elif response2.status_code == 200:
        print(f"\n✅ Method 2 worked!")
        data = response2.json()
        print(f"   Account type: {data.get('accountType', 'Unknown')}")
        print(f"   Can trade: {data.get('canTrade', False)}")
    elif response3.status_code == 200:
        print(f"\n✅ Method 3 worked!")
        data = response3.json()
        print(f"   Account type: {data.get('accountType', 'Unknown')}")
        print(f"   Can trade: {data.get('canTrade', False)}")
    elif response4.status_code == 200:
        print(f"\n✅ Method 4 worked!")
        data = response4.json()
        print(f"   Account type: {data.get('accountType', 'Unknown')}")
        print(f"   Can trade: {data.get('canTrade', False)}")
    else:
        print(f"\n❌ All methods failed")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test Binance API with urllib.parse')
    parser.add_argument('--api-key', required=True, help='Binance API Key')
    parser.add_argument('--api-secret', required=True, help='Binance API Secret')
    args = parser.parse_args()
    
    test_binance_with_urllib(args.api_key, args.api_secret)
