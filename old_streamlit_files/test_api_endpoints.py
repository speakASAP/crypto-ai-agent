#!/usr/bin/env python3
"""
Test Phase 2 API endpoints
"""
import requests
import json
import time
import subprocess
import sys
from pathlib import Path

def start_backend():
    """Start the FastAPI backend"""
    print("🚀 Starting FastAPI backend...")
    try:
        # Start backend in background
        process = subprocess.Popen([
            sys.executable, "-m", "uvicorn", 
            "app.main:app", 
            "--host", "0.0.0.0", 
            "--port", "8000"
        ], cwd="backend")
        
        # Wait for server to start
        time.sleep(5)
        return process
    except Exception as e:
        print(f"❌ Failed to start backend: {e}")
        return None

def test_health_endpoint():
    """Test health check endpoint"""
    print("\n🔍 Testing health endpoint...")
    try:
        response = requests.get("http://localhost:8000/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed: {data}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_api_docs():
    """Test API documentation endpoint"""
    print("\n📚 Testing API docs...")
    try:
        response = requests.get("http://localhost:8000/docs", timeout=10)
        if response.status_code == 200:
            print("✅ API documentation accessible")
            return True
        else:
            print(f"❌ API docs failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API docs error: {e}")
        return False

def test_portfolio_endpoints():
    """Test portfolio API endpoints"""
    print("\n💼 Testing portfolio endpoints...")
    try:
        # Test GET portfolio
        response = requests.get("http://localhost:8000/api/portfolio/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ GET /api/portfolio/ - {len(data)} items")
        else:
            print(f"❌ GET /api/portfolio/ failed: {response.status_code}")
            return False
        
        # Test GET portfolio summary
        response = requests.get("http://localhost:8000/api/portfolio/summary", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ GET /api/portfolio/summary - {data}")
        else:
            print(f"❌ GET /api/portfolio/summary failed: {response.status_code}")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Portfolio endpoints error: {e}")
        return False

def test_alerts_endpoints():
    """Test alerts API endpoints"""
    print("\n🔔 Testing alerts endpoints...")
    try:
        # Test GET alerts
        response = requests.get("http://localhost:8000/api/alerts/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ GET /api/alerts/ - {len(data)} alerts")
        else:
            print(f"❌ GET /api/alerts/ failed: {response.status_code}")
            return False
        
        # Test GET alert history
        response = requests.get("http://localhost:8000/api/alerts/history", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ GET /api/alerts/history - {len(data)} records")
        else:
            print(f"❌ GET /api/alerts/history failed: {response.status_code}")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Alerts endpoints error: {e}")
        return False

def test_symbols_endpoints():
    """Test symbols API endpoints"""
    print("\n📊 Testing symbols endpoints...")
    try:
        # Test GET tracked symbols
        response = requests.get("http://localhost:8000/api/symbols/tracked", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ GET /api/symbols/tracked - {len(data)} symbols")
        else:
            print(f"❌ GET /api/symbols/tracked failed: {response.status_code}")
            return False
        
        # Test GET crypto symbols
        response = requests.get("http://localhost:8000/api/symbols/crypto", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ GET /api/symbols/crypto - {len(data)} symbols")
        else:
            print(f"❌ GET /api/symbols/crypto failed: {response.status_code}")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Symbols endpoints error: {e}")
        return False

def test_create_portfolio_item():
    """Test creating a portfolio item"""
    print("\n➕ Testing portfolio item creation...")
    try:
        portfolio_data = {
            "symbol": "BTC",
            "amount": 1.5,
            "price_buy": 50000.0,
            "base_currency": "USD",
            "source": "Binance"
        }
        
        response = requests.post(
            "http://localhost:8000/api/portfolio/",
            json=portfolio_data,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Created portfolio item: {data['symbol']} - ID: {data['id']}")
            return data['id']
        else:
            print(f"❌ Create portfolio item failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Create portfolio item error: {e}")
        return None

def test_create_alert():
    """Test creating a price alert"""
    print("\n🔔 Testing alert creation...")
    try:
        alert_data = {
            "symbol": "BTC",
            "alert_type": "ABOVE",
            "threshold_price": 60000.0,
            "message": "BTC above $60k!",
            "is_active": True
        }
        
        response = requests.post(
            "http://localhost:8000/api/alerts/",
            json=alert_data,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Created alert: {data['symbol']} - ID: {data['id']}")
            return data['id']
        else:
            print(f"❌ Create alert failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Create alert error: {e}")
        return None

def main():
    """Run all API tests"""
    print("🧪 Phase 2 API Endpoint Testing")
    print("=" * 50)
    
    # Start backend
    backend_process = start_backend()
    if not backend_process:
        print("❌ Failed to start backend. Exiting.")
        return 1
    
    try:
        tests = [
            ("Health Check", test_health_endpoint),
            ("API Documentation", test_api_docs),
            ("Portfolio Endpoints", test_portfolio_endpoints),
            ("Alerts Endpoints", test_alerts_endpoints),
            ("Symbols Endpoints", test_symbols_endpoints),
            ("Create Portfolio Item", test_create_portfolio_item),
            ("Create Alert", test_create_alert)
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            print(f"\n📋 {test_name}")
            print("-" * 30)
            result = test_func()
            if result:
                passed += 1
                print(f"✅ {test_name} - PASSED")
            else:
                print(f"❌ {test_name} - FAILED")
        
        print("\n" + "=" * 50)
        print(f"📊 Test Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("\n🎉 Phase 2 API Testing COMPLETE!")
            print("\n✅ All endpoints are working correctly")
            print("✅ Backend is fully functional")
            print("✅ Ready for Phase 3: Frontend Development")
            return 0
        else:
            print(f"\n❌ {total - passed} tests failed. Check the errors above.")
            return 1
            
    finally:
        # Clean up
        if backend_process:
            print("\n🛑 Stopping backend...")
            backend_process.terminate()
            backend_process.wait()

if __name__ == "__main__":
    sys.exit(main())
