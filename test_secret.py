#!/usr/bin/env python3
"""
Test if the API secret is correct by trying a simple endpoint
"""
import argparse
import requests
import time
import hmac
import hashlib

API_URL = "https://api.binance.com/api/v3"

def test_simple_endpoint(api_key: str, api_secret: str):
    """Test with a simpler endpoint that requires auth"""
    print("🧪 Testing with a simpler endpoint...")
    
    try:
        # Get server time
        server_time_response = requests.get(f"{API_URL}/time", timeout=10)
        server_time = server_time_response.json()['serverTime']
        
        # Test with account status endpoint (simpler than account info)
        timestamp = server_time
        query_string = f"timestamp={timestamp}"
        
        signature = hmac.new(
            api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        print(f"   Timestamp: {timestamp}")
        print(f"   Query: {query_string}")
        print(f"   Signature: {signature[:20]}...")
        
        headers = {'X-MBX-APIKEY': api_key}
        params = {'timestamp': timestamp, 'signature': signature}
        
        # Try account status first (simpler endpoint)
        response = requests.get(f"{API_URL}/account/status", params=params, headers=headers, timeout=10)
        print(f"   Account status: {response.status_code} - {response.text}")
        
        if response.status_code == 200:
            print("✅ API secret is working!")
            return True
        else:
            print("❌ API secret issue confirmed")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test Binance API secret')
    parser.add_argument('--api-key', required=True, help='Binance API Key')
    parser.add_argument('--api-secret', required=True, help='Binance API Secret')
    args = parser.parse_args()
    
    test_simple_endpoint(args.api_key, args.api_secret)
