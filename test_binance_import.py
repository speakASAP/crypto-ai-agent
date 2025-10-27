#!/usr/bin/env python3
"""
Test script for Binance portfolio import functionality
"""
import requests
import json
import sys

# Configuration
BASE_URL = "http://localhost:8000"
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "password123"  # Assuming this is the password

def login():
    """Login and get access token"""
    print("🔐 Logging in...")
    
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Login successful for {data['user']['email']}")
        return data['access_token']
    else:
        print(f"❌ Login failed: {response.status_code} - {response.text}")
        return None

def test_binance_connection(token):
    """Test Binance API connection"""
    print("\n🔌 Testing Binance API connection...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(f"{BASE_URL}/api/import/binance/test-connection", headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Connection test result: {data}")
        return data['success']
    else:
        print(f"❌ Connection test failed: {response.status_code} - {response.text}")
        return False

def preview_binance_import(token):
    """Preview Binance portfolio import"""
    print("\n👀 Previewing Binance portfolio import...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(f"{BASE_URL}/api/import/binance/preview", headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Preview result: {data['message']}")
        print(f"📊 Found {data['items_imported']} portfolio items")
        
        if data.get('portfolio_items'):
            print("\n📋 Portfolio items preview:")
            for i, item in enumerate(data['portfolio_items'][:5]):  # Show first 5 items
                print(f"  {i+1}. {item['symbol']}: {item['amount']} @ ${item['price_buy']:.2f}")
            
            if len(data['portfolio_items']) > 5:
                print(f"  ... and {len(data['portfolio_items']) - 5} more items")
        
        return data
    else:
        print(f"❌ Preview failed: {response.status_code} - {response.text}")
        return None

def execute_binance_import(token):
    """Execute Binance portfolio import"""
    print("\n🚀 Executing Binance portfolio import...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(f"{BASE_URL}/api/import/binance/execute", headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Import result: {data['message']}")
        print(f"📊 Imported {data['items_imported']} items out of {data['total_found']} found")
        return data
    else:
        print(f"❌ Import failed: {response.status_code} - {response.text}")
        return None

def get_import_history(token):
    """Get import history"""
    print("\n📜 Getting import history...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/api/import/history", headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Import history retrieved: {len(data['import_history'])} records")
        
        for record in data['import_history'][:3]:  # Show last 3 imports
            print(f"  - {record['source']}: {record['items_imported']} items ({record['status']}) on {record['import_date']}")
        
        return data
    else:
        print(f"❌ Failed to get import history: {response.status_code} - {response.text}")
        return None

def main():
    """Main test function"""
    print("🚀 Testing Binance Portfolio Import Functionality")
    print("=" * 50)
    
    # Step 1: Login
    token = login()
    if not token:
        print("❌ Cannot proceed without authentication")
        sys.exit(1)
    
    # Step 2: Test connection
    if not test_binance_connection(token):
        print("❌ Binance API connection failed. Check your API credentials in .env file")
        sys.exit(1)
    
    # Step 3: Preview import
    preview_data = preview_binance_import(token)
    if not preview_data:
        print("❌ Preview failed")
        sys.exit(1)
    
    # Step 4: Ask user if they want to proceed
    if preview_data['items_imported'] > 0:
        print(f"\n⚠️  Found {preview_data['items_imported']} portfolio items to import.")
        print("This will add these items to your portfolio. Continue? (y/N)")
        
        # For automated testing, we'll proceed
        proceed = 'y'  # Auto-proceed for testing
        if proceed in ['y', 'yes']:
            # Step 5: Execute import
            execute_data = execute_binance_import(token)
            if execute_data:
                print("✅ Import completed successfully!")
                
                # Step 6: Show import history
                get_import_history(token)
            else:
                print("❌ Import execution failed")
        else:
            print("⏹️  Import cancelled by user")
    else:
        print("ℹ️  No portfolio items found to import")
    
    print("\n🎉 Test completed!")

if __name__ == "__main__":
    main()
