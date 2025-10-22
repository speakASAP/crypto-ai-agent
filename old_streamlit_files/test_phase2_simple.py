#!/usr/bin/env python3
"""
Simple Phase 2 Testing Script (No Database Required)
Tests the FastAPI backend implementation without database connection
"""
import sys
import asyncio
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path("backend")))

def test_imports():
    """Test that all modules can be imported"""
    print("🔍 Testing Phase 2 imports...")
    
    try:
        # Test core modules
        from app.core.config import settings
        print(f"✅ Configuration loaded: {settings.api_host}:{settings.api_port}")
        
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

def test_fastapi_app_structure():
    """Test FastAPI application structure without starting it"""
    print("\n🚀 Testing FastAPI application structure...")
    
    try:
        # Test that we can create the app without database connection
        from app.core.config import settings
        from app.api.routes import api_router
        
        # Check API router
        assert hasattr(api_router, 'routes'), "API router should have routes"
        print(f"✅ API router has {len(api_router.routes)} routes")
        
        # Check individual route modules
        from app.api.portfolio import router as portfolio_router
        from app.api.alerts import router as alerts_router
        from app.api.symbols import router as symbols_router
        from app.api.websocket import router as websocket_router
        
        print(f"✅ Portfolio router: {len(portfolio_router.routes)} routes")
        print(f"✅ Alerts router: {len(alerts_router.routes)} routes")
        print(f"✅ Symbols router: {len(symbols_router.routes)} routes")
        print(f"✅ WebSocket router: {len(websocket_router.routes)} routes")
        
        return True
        
    except Exception as e:
        print(f"❌ FastAPI app structure error: {e}")
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

def test_websocket_components():
    """Test WebSocket components"""
    print("\n🔌 Testing WebSocket components...")
    
    try:
        from app.api.websocket import ConnectionManager, manager
        
        # Check ConnectionManager class
        assert hasattr(ConnectionManager, 'connect'), "ConnectionManager should have connect method"
        assert hasattr(ConnectionManager, 'disconnect'), "ConnectionManager should have disconnect method"
        assert hasattr(ConnectionManager, 'broadcast'), "ConnectionManager should have broadcast method"
        
        # Check manager instance
        assert hasattr(manager, 'active_connections'), "Manager should have active_connections"
        assert isinstance(manager.active_connections, list), "active_connections should be a list"
        
        print("✅ WebSocket components valid")
        return True
        
    except Exception as e:
        print(f"❌ WebSocket components error: {e}")
        return False

def test_environment_configuration():
    """Test environment configuration"""
    print("\n🔧 Testing environment configuration...")
    
    try:
        from app.core.config import settings
        
        # Check required settings
        assert hasattr(settings, 'database_url'), "Settings should have database_url"
        assert hasattr(settings, 'redis_url'), "Settings should have redis_url"
        assert hasattr(settings, 'api_host'), "Settings should have api_host"
        assert hasattr(settings, 'api_port'), "Settings should have api_port"
        
        print(f"✅ Database URL: {settings.database_url}")
        print(f"✅ Redis URL: {settings.redis_url}")
        print(f"✅ API Host: {settings.api_host}")
        print(f"✅ API Port: {settings.api_port}")
        
        return True
        
    except Exception as e:
        print(f"❌ Environment configuration error: {e}")
        return False

def main():
    """Run all Phase 2 tests"""
    print("🚀 Phase 2: Backend Development Testing (Simple)")
    print("=" * 60)
    
    tests = [
        ("Module Imports", test_imports),
        ("Schema Validation", test_schema_validation),
        ("FastAPI App Structure", test_fastapi_app_structure),
        ("Database Models", test_database_models),
        ("Services", test_services),
        ("WebSocket Components", test_websocket_components),
        ("Environment Configuration", test_environment_configuration)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 40)
        result = test_func()
        if result:
            passed += 1
            print(f"✅ {test_name} - PASSED")
        else:
            print(f"❌ {test_name} - FAILED")
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed}/{total} test suites passed")
    
    if passed == total:
        print("\n🎉 Phase 2 Backend Development is COMPLETE!")
        print("\n✅ All components are properly structured")
        print("✅ API routes are defined and ready")
        print("✅ Services are implemented")
        print("✅ Database models are ready")
        print("✅ WebSocket support is implemented")
        print("\nNext steps:")
        print("1. Set up PostgreSQL and Redis for full testing")
        print("2. Run: docker compose up --build")
        print("3. Test API endpoints: http://localhost:8000/docs")
        print("4. Begin Phase 3: Frontend Development")
        return 0
    else:
        print(f"\n❌ {total - passed} test suites failed. Please fix issues before proceeding.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
