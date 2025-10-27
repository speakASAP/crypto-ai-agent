#!/usr/bin/env python3
"""
Test script to check API key permissions and restrictions
"""
import argparse
import requests
import time

API_URL = "https://api.binance.com/api/v3"

def test_api_key_permissions(api_key: str, api_secret: str):
    """Test API key permissions and restrictions"""
    print("🔍 Testing API key permissions...")
    
    headers = {'X-MBX-APIKEY': api_key}
    
    # Test 1: Server time (no auth required)
    print("\n1. Testing server time...")
    try:
        response = requests.get(f"{API_URL}/time", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Server time: {data['serverTime']}")
            server_time = data['serverTime']
        else:
            print(f"❌ Server time failed: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Server time error: {e}")
        return
    
    # Test 2: Exchange info (no auth required)
    print("\n2. Testing exchange info...")
    try:
        response = requests.get(f"{API_URL}/exchangeInfo", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Exchange info: {len(data.get('symbols', []))} symbols")
        else:
            print(f"❌ Exchange info failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Exchange info error: {e}")
    
    # Test 3: 24hr ticker (no auth required)
    print("\n3. Testing 24hr ticker...")
    try:
        response = requests.get(f"{API_URL}/ticker/24hr?symbol=BTCUSDT", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 24hr ticker: BTCUSDT = ${data.get('lastPrice', 'N/A')}")
        else:
            print(f"❌ 24hr ticker failed: {response.status_code}")
    except Exception as e:
        print(f"❌ 24hr ticker error: {e}")
    
    # Test 4: API key status (requires API key but no signature)
    print("\n4. Testing API key status...")
    try:
        response = requests.get(f"{API_URL}/api/v3/apiTradingStatus", headers=headers, timeout=10)
        print(f"   API key status: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ API key status error: {e}")
    
    # Test 5: Check if API key is restricted
    print("\n5. Testing API key restrictions...")
    try:
        # Try to get account info without signature (should fail with different error)
        response = requests.get(f"{API_URL}/account", headers=headers, timeout=10)
        print(f"   Account without signature: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Account test error: {e}")
    
    # Test 6: Check time synchronization
    print("\n6. Checking time synchronization...")
    try:
        local_time = int(time.time() * 1000)
        time_diff = abs(local_time - server_time)
        print(f"   Local time: {local_time}")
        print(f"   Server time: {server_time}")
        print(f"   Time difference: {time_diff}ms")
        if time_diff > 5000:  # More than 5 seconds
            print(f"   ⚠️  Time difference is large: {time_diff}ms")
        else:
            print(f"   ✅ Time difference is acceptable: {time_diff}ms")
    except Exception as e:
        print(f"❌ Time sync error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test Binance API key permissions')
    parser.add_argument('--api-key', required=True, help='Binance API Key')
    parser.add_argument('--api-secret', required=True, help='Binance API Secret')
    args = parser.parse_args()
    
    test_api_key_permissions(args.api_key, args.api_secret)
