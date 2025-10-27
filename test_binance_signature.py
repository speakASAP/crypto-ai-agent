#!/usr/bin/env python3
"""
Test script to verify Binance API signature generation
"""
import argparse
import hmac
import hashlib
import time
import requests

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

def test_binance_connection(api_key: str, api_secret: str):
    """Test Binance API connection with your credentials"""
    print("🔍 Testing Binance API connection...")
    
    # Test 1: Server time (no auth required)
    print("\n1. Testing server time endpoint...")
    try:
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
    
    # Test 2: Account info (requires API key and signature)
    print("\n2. Testing account info endpoint...")
    try:
        timestamp = get_timestamp()
        query_string = f"timestamp={timestamp}"
        signature = generate_signature(query_string, api_secret)
        
        print(f"   Timestamp: {timestamp}")
        print(f"   Query string: {query_string}")
        print(f"   Signature: {signature}")
        
        # Try different approaches
        print("\n   Testing different signature methods...")
        
        # Method 1: Direct URL with params
        url1 = f"{API_URL}/account?timestamp={timestamp}&signature={signature}"
        headers = {'X-MBX-APIKEY': api_key}
        response1 = requests.get(url1, headers=headers, timeout=10)
        print(f"   Method 1 (direct URL): {response1.status_code} - {response1.text[:100]}")
        
        # Method 2: Using requests params
        url2 = f"{API_URL}/account"
        params2 = {'timestamp': timestamp, 'signature': signature}
        response2 = requests.get(url2, params=params2, headers=headers, timeout=10)
        print(f"   Method 2 (params): {response2.status_code} - {response2.text[:100]}")
        
        # Method 3: Try with different timestamp format
        timestamp_str = str(timestamp)
        query_string3 = f"timestamp={timestamp_str}"
        signature3 = generate_signature(query_string3, api_secret)
        url3 = f"{API_URL}/account?timestamp={timestamp_str}&signature={signature3}"
        response3 = requests.get(url3, headers=headers, timeout=10)
        print(f"   Method 3 (string timestamp): {response3.status_code} - {response3.text[:100]}")
        
        if response1.status_code == 200:
            data = response1.json()
            print(f"✅ Account info retrieved successfully!")
            print(f"   Account type: {data.get('accountType', 'Unknown')}")
            print(f"   Can trade: {data.get('canTrade', False)}")
            print(f"   Balances count: {len(data.get('balances', []))}")
        elif response2.status_code == 200:
            data = response2.json()
            print(f"✅ Account info retrieved successfully!")
            print(f"   Account type: {data.get('accountType', 'Unknown')}")
            print(f"   Can trade: {data.get('canTrade', False)}")
            print(f"   Balances count: {len(data.get('balances', []))}")
        elif response3.status_code == 200:
            data = response3.json()
            print(f"✅ Account info retrieved successfully!")
            print(f"   Account type: {data.get('accountType', 'Unknown')}")
            print(f"   Can trade: {data.get('canTrade', False)}")
            print(f"   Balances count: {len(data.get('balances', []))}")
        else:
            print(f"❌ All methods failed")
            
    except Exception as e:
        print(f"❌ Account info error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test Binance API signature')
    parser.add_argument('--api-key', required=True, help='Binance API Key')
    parser.add_argument('--api-secret', required=True, help='Binance API Secret')
    args = parser.parse_args()
    
    test_binance_connection(args.api_key, args.api_secret)
