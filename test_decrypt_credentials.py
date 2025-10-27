#!/usr/bin/env python3
"""
Test script to decrypt and verify Binance credentials from database
"""
import os
import sys
from app.utils.encryption import CredentialEncryption

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Get JWT_SECRET from environment
SECRET_KEY = os.getenv('JWT_SECRET')
if not SECRET_KEY:
    print("❌ JWT_SECRET not found in environment")
    sys.exit(1)

# Encrypted credentials from database
encrypted_creds_user3 = "Z0FBQUFBQm9fTFVsWWMyQUxET296aVZvU1ZzZHBaLWkzd0NzNWZpTExSa1RHUERmNEpabkhSd0J5Y1JiR2otMWJSc29nNnA1U0xDbjBtTUtDeGRSdTVCeENBVkpGV1R0NnluM05YNVo0ZTNYMTExR3Y4S1dyMWVzQ1J6U0c3X0JkNXFheTdIMnFHWm1jWUJzcm8tbVNEa1RJMi02WmZJVTluSUEtbS0yTkZ1T0tQeWdXeHBaN09tS2l0RXBnTHdtb2ltNndWZ08xWmN1dHJVMmlkaWpBV0V2RXlRYWlWTkRIam5OVU03S1lNaHpSa0tKS21OY3k0eEtWTFczbHU3ZW5CNHI1STJWUUdHLVpmYkl5RzFkOFNSZHdtTEVKVXBXUDZVdWtDdDhwY0tZWWNPMGxHUms3cE1hanF6Y1VSX0JrVGZpQ2lJNko2U0pxUHhDdWpXTGtGWEo1SXFsM2xBVXQyR05aTUM4OXFubnFhRDY1dWJvY01nPQ=="

print("🔍 Testing credential decryption...")

# Create encryption service
encryption = CredentialEncryption(SECRET_KEY)

# Decrypt the credentials
try:
    decrypted = encryption.decrypt_binance_credentials(encrypted_creds_user3)
    print(f"✅ Successfully decrypted credentials!")
    print(f"   API Key: {decrypted['api_key'][:20]}...")
    print(f"   API Secret: {decrypted['api_secret'][:20]}...")
    
    # Test with Binance
    print("\n🔍 Testing with Binance API...")
    from binance.client import Client as BinanceClient
    
    client = BinanceClient(decrypted['api_key'], decrypted['api_secret'])
    
    # Test server time
    server_time = client.get_server_time()
    print(f"✅ Server time: {server_time['serverTime']}")
    
    # Test account info
    account_info = client.get_account()
    print(f"✅ Account info retrieved successfully!")
    print(f"   Account type: {account_info.get('accountType', 'Unknown')}")
    print(f"   Can trade: {account_info.get('canTrade', False)}")
    print(f"   Balances count: {len(account_info.get('balances', []))}")
    
except Exception as e:
    print(f"❌ Error: {e}")

