#!/usr/bin/env python3
"""
Test script to verify CSV import deletion functionality
1. Register a test account
2. Import 1.csv (creates portfolio items)
3. Import 2.csv (should delete ZEN, DASH, IP, HBAR)
4. Verify deletions
"""
import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8100"
TEST_EMAIL = f"test_csv_{int(time.time())}@example.com"
TEST_USERNAME = f"test_csv_{int(time.time())}"
TEST_PASSWORD = "testpassword123"

def register_user():
    """Register a new test user"""
    print("🔵 Registering test user...")
    response = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={
            "email": TEST_EMAIL,
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD,
            "full_name": "CSV Import Test User"
        }
    )
    if response.status_code != 200:
        print(f"❌ Registration failed: {response.status_code} - {response.text}")
        return None
    data = response.json()
    print(f"✅ Registered user: {TEST_USERNAME} ({TEST_EMAIL})")
    return data["access_token"]

def login_user():
    """Login as test user"""
    print("🔵 Logging in...")
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        }
    )
    if response.status_code != 200:
        print(f"❌ Login failed: {response.status_code} - {response.text}")
        return None
    data = response.json()
    print(f"✅ Logged in as: {data['user']['username']}")
    return data["access_token"]

def get_portfolio(token):
    """Get current portfolio"""
    response = requests.get(
        f"{BASE_URL}/api/portfolio",
        headers={"Authorization": f"Bearer {token}"}
    )
    if response.status_code != 200:
        print(f"❌ Failed to get portfolio: {response.status_code} - {response.text}")
        return []
    return response.json()

def import_csv(token, csv_file, exchange="revolut"):
    """Import a CSV file"""
    print(f"🔵 Importing {csv_file}...")
    with open(csv_file, 'rb') as f:
        files = {'file': (csv_file.split('/')[-1], f, 'text/csv')}
        data = {'exchange': exchange}
        response = requests.post(
            f"{BASE_URL}/api/import/csv/execute",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data=data
        )
    if response.status_code != 200:
        print(f"❌ Import failed: {response.status_code} - {response.text}")
        return None
    result = response.json()
    print(f"✅ Import result: {result.get('message', 'Success')}")
    print(f"   - Inserted: {result.get('items_imported', 0)}")
    print(f"   - Updated: {result.get('items_updated', 0)}")
    print(f"   - Deleted: {result.get('items_deleted', 0)}")
    return result

def main():
    print("=" * 60)
    print("CSV Import Deletion Test")
    print("=" * 60)
    
    # Step 1: Register user
    token = register_user()
    if not token:
        print("❌ Cannot continue without authentication")
        return
    
    time.sleep(1)  # Brief pause
    
    # Step 2: Import 1.csv (should create portfolio items)
    print("\n" + "=" * 60)
    print("STEP 1: Importing 1.csv (initial portfolio)")
    print("=" * 60)
    
    result1 = import_csv(token, "/Users/sergiystashok/Downloads/1.csv")
    if not result1:
        print("❌ Failed to import 1.csv")
        return
    
    time.sleep(2)  # Wait for processing
    
    # Check portfolio after first import
    portfolio_after_1 = get_portfolio(token)
    symbols_after_1 = {item['symbol']: item['amount'] for item in portfolio_after_1}
    print(f"\n📊 Portfolio after 1.csv import ({len(portfolio_after_1)} items):")
    for symbol, amount in sorted(symbols_after_1.items()):
        print(f"   - {symbol}: {amount}")
    
    # Check that ZEN, DASH, IP, HBAR exist
    required_symbols = ['ZEN', 'DASH', 'IP', 'HBAR']
    missing = [s for s in required_symbols if s not in symbols_after_1]
    if missing:
        print(f"⚠️ Warning: Some expected symbols missing: {missing}")
    else:
        print(f"✅ All required symbols found: {required_symbols}")
    
    # Step 3: Import 2.csv (should delete ZEN, DASH, IP, HBAR)
    print("\n" + "=" * 60)
    print("STEP 2: Importing 2.csv (should delete ZEN, DASH, IP, HBAR)")
    print("=" * 60)
    
    result2 = import_csv(token, "/Users/sergiystashok/Documents/GitHub/crypto-ai-agent/2.csv")
    if not result2:
        print("❌ Failed to import 2.csv")
        return
    
    time.sleep(2)  # Wait for processing
    
    # Step 4: Verify deletions
    print("\n" + "=" * 60)
    print("STEP 3: Verifying deletions")
    print("=" * 60)
    
    portfolio_after_2 = get_portfolio(token)
    symbols_after_2 = {item['symbol']: item['amount'] for item in portfolio_after_2}
    print(f"\n📊 Portfolio after 2.csv import ({len(portfolio_after_2)} items):")
    for symbol, amount in sorted(symbols_after_2.items()):
        print(f"   - {symbol}: {amount}")
    
    # Check if sold items were deleted
    sold_symbols = ['ZEN', 'DASH', 'IP', 'HBAR']
    deleted_count = 0
    still_exists = []
    
    for symbol in sold_symbols:
        if symbol in symbols_after_2:
            still_exists.append(symbol)
            print(f"❌ {symbol} still exists in portfolio (amount: {symbols_after_2[symbol]})")
        else:
            deleted_count += 1
            print(f"✅ {symbol} correctly deleted from portfolio")
    
    print("\n" + "=" * 60)
    print("TEST RESULTS")
    print("=" * 60)
    print(f"Items deleted: {deleted_count}/{len(sold_symbols)}")
    if deleted_count == len(sold_symbols):
        print("✅ SUCCESS: All 4 sold items were correctly deleted!")
    else:
        print(f"❌ FAILURE: {len(still_exists)} items were not deleted: {still_exists}")
        print(f"   Expected deletion of: {sold_symbols}")
        print(f"   Still exists: {still_exists}")
    
    print(f"\n📈 Import statistics:")
    print(f"   1.csv: {result1.get('items_imported', 0)} inserted")
    print(f"   2.csv: {result2.get('items_deleted', 0)} deleted, {result2.get('items_imported', 0)} inserted")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

