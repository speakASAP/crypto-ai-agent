#!/usr/bin/env python3
"""
Test script to check different Binance regions and endpoints
"""
import argparse
import hmac
import hashlib
import time
import requests
from urllib.parse import urlencode

# Different Binance endpoints
ENDPOINTS = {
    "Global": "https://api.binance.com/api/v3",
    "US": "https://api.binance.us/api/v3",
    "Testnet": "https://testnet.binance.vision/api/v3"
}

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

def test_endpoint(name: str, base_url: str, api_key: str, api_secret: str):
    """Test a specific Binance endpoint"""
    print(f"\n🔍 Testing {name} endpoint: {base_url}")
    
    headers = {'X-MBX-APIKEY': api_key}
    
    # Test 1: Server time
    try:
        response = requests.get(f"{base_url}/time", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Server time: {data['serverTime']}")
        else:
            print(f"   ❌ Server time failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Server time error: {e}")
        return False
    
    # Test 2: Account info
    try:
        timestamp = get_timestamp()
        params = {'timestamp': timestamp}
        query_string = urlencode(params)
        signature = generate_signature(query_string, api_secret)
        
        url = f"{base_url}/account?{query_string}&signature={signature}"
        response = requests.get(url, headers=headers, timeout=10)
        
        print(f"   Account info: {response.status_code} - {response.text[:100]}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Account info retrieved successfully!")
            print(f"      Account type: {data.get('accountType', 'Unknown')}")
            print(f"      Can trade: {data.get('canTrade', False)}")
            return True
        else:
            return False
            
    except Exception as e:
        print(f"   ❌ Account info error: {e}")
        return False

def test_binance_regions(api_key: str, api_secret: str):
    """Test different Binance regions"""
    print("🔍 Testing different Binance regions...")
    
    success_count = 0
    for name, base_url in ENDPOINTS.items():
        if test_endpoint(name, base_url, api_key, api_secret):
            success_count += 1
    
    print(f"\n📊 Results: {success_count}/{len(ENDPOINTS)} endpoints worked")
    
    if success_count == 0:
        print("\n💡 Possible issues:")
        print("   1. API key doesn't have 'Enable Reading' permission")
        print("   2. API key is restricted by IP address")
        print("   3. API key is for a different region")
        print("   4. API key is expired or invalid")
        print("\n🔧 Solutions:")
        print("   1. Check API key permissions in Binance account")
        print("   2. Remove IP restrictions or add current IP")
        print("   3. Verify you're using the correct region")
        print("   4. Create a new API key if needed")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test different Binance regions')
    parser.add_argument('--api-key', required=True, help='Binance API Key')
    parser.add_argument('--api-secret', required=True, help='Binance API Secret')
    args = parser.parse_args()
    
    test_binance_regions(args.api_key, args.api_secret)
