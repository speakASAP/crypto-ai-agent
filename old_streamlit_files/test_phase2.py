#!/usr/bin/env python3
"""
Phase 2 Testing Script
Tests the FastAPI backend implementation
"""
import sys
import asyncio
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path("backend")))

async def test_imports():
    """Test that all modules can be imported"""
    print("🔍 Testing Phase 2 imports...")
    
    try:
        # Test core modules
        from app.core.config import settings
        from app.core.database import Base, get_db, init_db
        print("✅ Core modules imported")
        
        # Test models
        from app.models import Portfolio, PriceAlert, TrackedSymbol, Candle, CurrencyRate
        print("✅ Database models imported")
        
        # Test schemas
        from app.schemas import (
            PortfolioCreate, PortfolioResponse,
            PriceAlertCreate, PriceAlertResponse,
            TrackedSymbolCreate, TrackedSymbolResponse
        )
        print("✅ Pydantic schemas imported")
        
        # Test services
        from app.services.cache_service import CacheService
        from app.services.price_service import PriceService
        from app.services.currency_service import CurrencyService
        print("✅ Services imported")
        
        # Test API routes
        from app.api.routes import api_router
        from app.api.portfolio import router as portfolio_router
        from app.api.alerts import router as alerts_router
        from app.api.symbols import router as symbols_router
        from app.api.websocket import router as websocket_router
        print("✅ API routes imported")
        
        # Test main app
        from app.main import app
        print("✅ FastAPI app imported")
        
        return True
        
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

def test_schema_validation():
    """Test Pydantic schema validation"""
    print("\n📋 Testing schema validation...")
    
    try:
        from app.schemas.portfolio import PortfolioCreate, PortfolioResponse
        from app.schemas.alerts import PriceAlertCreate, AlertType
        from decimal import Decimal
        from datetime import datetime
        
        # Test portfolio schema
        portfolio_data = {
            "symbol": "BTC",
            "amount": Decimal("1.5"),
            "price_buy": Decimal("50000.0"),
            "base_currency": "USD",
            "source": "Binance"
        }
        
        portfolio = PortfolioCreate(**portfolio_data)
        print("✅ Portfolio schema validation passed")
        
        # Test alert schema
        alert_data = {
            "symbol": "BTC",
            "alert_type": AlertType.ABOVE,
            "threshold_price": Decimal("60000.0"),
            "message": "BTC above $60k!"
        }
        
        alert = PriceAlertCreate(**alert_data)
        print("✅ Alert schema validation passed")
        
        return True
        
    except Exception as e:
        print(f"❌ Schema validation error: {e}")
        return False

def test_fastapi_app():
    """Test FastAPI application structure"""
    print("\n🚀 Testing FastAPI application...")
    
    try:
        from app.main import app
        
        # Check if app has required attributes
        assert hasattr(app, 'routes'), "App should have routes"
        assert hasattr(app, 'middleware'), "App should have middleware"
        
        # Check routes
        route_paths = [route.path for route in app.routes]
        expected_paths = ["/health", "/api/portfolio", "/api/alerts", "/api/symbols", "/api/ws"]
        
        for expected_path in expected_paths:
            if any(expected_path in path for path in route_paths):
                print(f"✅ Route {expected_path} found")
            else:
                print(f"❌ Route {expected_path} not found")
                return False
        
        print("✅ FastAPI application structure valid")
        return True
        
    except Exception as e:
        print(f"❌ FastAPI app error: {e}")
        return False

def test_database_models():
    """Test database model definitions"""
    print("\n🗄️ Testing database models...")
    
    try:
        from app.models.portfolio import Portfolio
        from app.models.alerts import PriceAlert, AlertHistory
        from app.models.symbols import TrackedSymbol, CryptoSymbol
        from app.models.candles import Candle
        from app.models.currency_rates import CurrencyRate
        
        # Check model attributes
        portfolio_attrs = [attr for attr in dir(Portfolio) if not attr.startswith('_')]
        assert 'symbol' in portfolio_attrs, "Portfolio should have symbol attribute"
        assert 'amount' in portfolio_attrs, "Portfolio should have amount attribute"
        
        alert_attrs = [attr for attr in dir(PriceAlert) if not attr.startswith('_')]
        assert 'symbol' in alert_attrs, "PriceAlert should have symbol attribute"
        assert 'threshold_price' in alert_attrs, "PriceAlert should have threshold_price attribute"
        
        print("✅ Database models structure valid")
        return True
        
    except Exception as e:
        print(f"❌ Database models error: {e}")
        return False

def test_services():
    """Test service classes"""
    print("\n⚙️ Testing services...")
    
    try:
        from app.services.cache_service import CacheService
        from app.services.price_service import PriceService
        from app.services.currency_service import CurrencyService
        
        # Check service methods
        cache_methods = [method for method in dir(CacheService) if not method.startswith('_')]
        assert 'get' in cache_methods, "CacheService should have get method"
        assert 'set' in cache_methods, "CacheService should have set method"
        
        price_methods = [method for method in dir(PriceService) if not method.startswith('_')]
        assert 'get_current_prices' in price_methods, "PriceService should have get_current_prices method"
        
        currency_methods = [method for method in dir(CurrencyService) if not method.startswith('_')]
        assert 'get_exchange_rates' in currency_methods, "CurrencyService should have get_exchange_rates method"
        assert 'convert_currency' in currency_methods, "CurrencyService should have convert_currency method"
        
        print("✅ Services structure valid")
        return True
        
    except Exception as e:
        print(f"❌ Services error: {e}")
        return False

async def main():
    """Run all Phase 2 tests"""
    print("🚀 Phase 2: Backend Development Testing\n")
    print("=" * 50)
    
    tests = [
        ("Module Imports", test_imports()),
        ("Schema Validation", test_schema_validation()),
        ("FastAPI Application", test_fastapi_app()),
        ("Database Models", test_database_models()),
        ("Services", test_services())
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_coro in tests:
        print(f"\n📋 {test_name}")
        print("-" * 30)
        if asyncio.iscoroutine(test_coro):
            result = await test_coro
        else:
            result = test_coro
            
        if result:
            passed += 1
            print(f"✅ {test_name} - PASSED")
        else:
            print(f"❌ {test_name} - FAILED")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} test suites passed")
    
    if passed == total:
        print("\n🎉 Phase 2 Backend Development is COMPLETE!")
        print("\nNext steps:")
        print("1. Start the backend: cd backend && python -m uvicorn app.main:app --reload")
        print("2. Test API endpoints: http://localhost:8000/docs")
        print("3. Begin Phase 3: Frontend Development")
        return 0
    else:
        print(f"\n❌ {total - passed} test suites failed. Please fix issues before proceeding.")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
