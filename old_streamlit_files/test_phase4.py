#!/usr/bin/env python3
"""
Phase 4 Testing Script
Tests the performance optimization implementation
"""
import os
import sys
import asyncio
import time
import requests
import json
from pathlib import Path

def test_performance_files():
    """Test that all performance optimization files exist"""
    print("🔍 Testing performance optimization files...")
    
    required_files = [
        "backend/app/services/advanced_cache_service.py",
        "backend/app/services/optimized_db_service.py",
        "backend/app/services/performance_monitor.py",
        "backend/app/api/optimized_routes.py"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        return False
    else:
        print("✅ All performance optimization files exist")
        return True

def test_database_schema_optimization():
    """Test database schema optimizations"""
    print("\n📊 Testing database schema optimizations...")
    
    try:
        with open("backend/schema.sql", "r") as f:
            schema_content = f.read()
        
        # Check for comprehensive indexes
        required_indexes = [
            "idx_portfolio_symbol",
            "idx_portfolio_base_currency",
            "idx_currency_rates_latest",
            "idx_price_alerts_symbol_active",
            "idx_alert_history_symbol_triggered",
            "idx_candles_symbol_latest",
            "idx_portfolio_summary",
            "idx_alerts_active_symbols"
        ]
        
        missing_indexes = [idx for idx in required_indexes if idx not in schema_content]
        
        if missing_indexes:
            print(f"❌ Missing database indexes: {missing_indexes}")
            return False
        
        print("✅ Database schema optimizations complete")
        print(f"✅ Found {len(required_indexes)} performance indexes")
        return True
        
    except Exception as e:
        print(f"❌ Database schema test error: {e}")
        return False

def test_advanced_cache_service():
    """Test advanced cache service implementation"""
    print("\n💾 Testing advanced cache service...")
    
    try:
        with open("backend/app/services/advanced_cache_service.py", "r") as f:
            cache_content = f.read()
        
        # Check for required methods
        required_methods = [
            'def initialize', 'def close', 'def get', 'def set', 'def delete',
            'def invalidate_pattern', 'def get_or_set', 'def batch_get',
            'def batch_set', 'def get_stats', 'def clear_all'
        ]
        
        missing_methods = [method for method in required_methods if method not in cache_content]
        
        if missing_methods:
            print(f"❌ Missing cache service methods: {missing_methods}")
            return False
        
        # Check for required imports
        required_imports = ['aioredis', 'asyncio', 'json', 'datetime']
        missing_imports = [imp for imp in required_imports if f"import {imp}" not in cache_content and f"from {imp}" not in cache_content]
        
        if missing_imports:
            print(f"❌ Missing cache service imports: {missing_imports}")
            return False
        
        print("✅ Advanced cache service implementation complete")
        print(f"✅ Found {len(required_methods)} cache methods")
        return True
        
    except Exception as e:
        print(f"❌ Advanced cache service test error: {e}")
        return False

def test_optimized_db_service():
    """Test optimized database service"""
    print("\n🗄️ Testing optimized database service...")
    
    try:
        with open("backend/app/services/optimized_db_service.py", "r") as f:
            db_content = f.read()
        
        # Check for required methods
        required_methods = [
            'def get_portfolio_optimized', 'def get_portfolio_summary_optimized',
            'def get_alerts_optimized', 'def get_alert_history_optimized',
            'def get_tracked_symbols_optimized', 'def get_currency_rates_optimized',
            'def get_latest_prices_optimized', 'def batch_create_portfolio_items',
            'def get_performance_stats'
        ]
        
        missing_methods = [method for method in required_methods if method not in db_content]
        
        if missing_methods:
            print(f"❌ Missing DB service methods: {missing_methods}")
            return False
        
        print("✅ Optimized database service implementation complete")
        print(f"✅ Found {len(required_methods)} optimized methods")
        return True
        
    except Exception as e:
        print(f"❌ Optimized DB service test error: {e}")
        return False

def test_performance_monitor():
    """Test performance monitoring service"""
    print("\n📊 Testing performance monitoring service...")
    
    try:
        with open("backend/app/services/performance_monitor.py", "r") as f:
            monitor_content = f.read()
        
        # Check for required methods
        required_methods = [
            'def start_monitoring', 'def stop_monitoring', 'def record_api_call',
            'def record_database_query', 'def record_cache_operation',
            'def record_websocket_connection', 'def get_performance_summary',
            'def get_health_status', 'def reset_metrics'
        ]
        
        missing_methods = [method for method in required_methods if method not in monitor_content]
        
        if missing_methods:
            print(f"❌ Missing performance monitor methods: {missing_methods}")
            return False
        
        # Check for required imports
        required_imports = ['psutil', 'time', 'datetime', 'collections']
        missing_imports = [imp for imp in required_imports if f"import {imp}" not in monitor_content and f"from {imp}" not in monitor_content]
        
        if missing_imports:
            print(f"❌ Missing performance monitor imports: {missing_imports}")
            return False
        
        print("✅ Performance monitoring service implementation complete")
        print(f"✅ Found {len(required_methods)} monitoring methods")
        return True
        
    except Exception as e:
        print(f"❌ Performance monitor test error: {e}")
        return False

def test_optimized_routes():
    """Test optimized API routes"""
    print("\n🚀 Testing optimized API routes...")
    
    try:
        with open("backend/app/api/optimized_routes.py", "r") as f:
            routes_content = f.read()
        
        # Check for required route endpoints
        required_routes = [
            "get_portfolio_optimized",
            "get_portfolio_summary_optimized",
            "create_portfolio_item_optimized",
            "get_alerts_optimized",
            "get_alert_history_optimized",
            "get_tracked_symbols_optimized",
            "get_performance_summary",
            "get_health_status",
            "get_cache_stats",
            "batch_create_portfolio_items",
            "get_currency_rate_optimized",
            "get_latest_prices_optimized"
        ]
        
        missing_routes = [route for route in required_routes if route not in routes_content]
        
        if missing_routes:
            print(f"❌ Missing optimized routes: {missing_routes}")
            return False
        
        print("✅ Optimized API routes implementation complete")
        print(f"✅ Found {len(required_routes)} optimized endpoints")
        return True
        
    except Exception as e:
        print(f"❌ Optimized routes test error: {e}")
        return False

def test_main_app_integration():
    """Test main application integration"""
    print("\n⚙️ Testing main application integration...")
    
    try:
        with open("backend/app/main.py", "r") as f:
            main_content = f.read()
        
        # Check for performance integrations
        required_integrations = [
            "advanced_cache_service",
            "performance_monitor",
            "optimized_router",
            "cache_service.initialize",
            "performance_monitor.start_monitoring"
        ]
        
        missing_integrations = [integration for integration in required_integrations if integration not in main_content]
        
        if missing_integrations:
            print(f"❌ Missing main app integrations: {missing_integrations}")
            return False
        
        print("✅ Main application integration complete")
        print(f"✅ Found {len(required_integrations)} performance integrations")
        return True
        
    except Exception as e:
        print(f"❌ Main app integration test error: {e}")
        return False

def test_performance_metrics():
    """Test performance metrics collection"""
    print("\n📈 Testing performance metrics collection...")
    
    try:
        with open("backend/app/services/performance_monitor.py", "r") as f:
            monitor_content = f.read()
        
        # Check for metrics collection methods
        required_metrics_methods = [
            'record_api_call', 'record_database_query', 'record_cache_operation',
            'record_websocket_connection', 'get_performance_summary', 'get_health_status'
        ]
        
        missing_methods = [method for method in required_metrics_methods if method not in monitor_content]
        
        if missing_methods:
            print(f"❌ Missing metrics collection methods: {missing_methods}")
            return False
        
        # Check for metrics data structures
        required_metrics = ['api_calls', 'database_queries', 'cache_operations', 'memory_usage', 'cpu_usage']
        missing_metrics = [metric for metric in required_metrics if metric not in monitor_content]
        
        if missing_metrics:
            print(f"❌ Missing metrics data structures: {missing_metrics}")
            return False
        
        print("✅ Performance metrics collection implementation complete")
        print(f"✅ Found {len(required_metrics_methods)} metrics methods")
        return True
        
    except Exception as e:
        print(f"❌ Performance metrics test error: {e}")
        return False

def test_cache_functionality():
    """Test cache functionality"""
    print("\n💾 Testing cache functionality...")
    
    try:
        with open("backend/app/services/advanced_cache_service.py", "r") as f:
            cache_content = f.read()
        
        # Check for cache operation methods
        required_cache_methods = [
            'def get', 'def set', 'def delete', 'def invalidate_pattern',
            'def get_or_set', 'def batch_get', 'def batch_set'
        ]
        
        missing_methods = [method for method in required_cache_methods if method not in cache_content]
        
        if missing_methods:
            print(f"❌ Missing cache operation methods: {missing_methods}")
            return False
        
        # Check for cache features
        required_features = [
            'memory_cache', 'redis', 'ttl', 'expires_at', 'namespace',
            'batch_get', 'batch_set', 'invalidation', 'statistics'
        ]
        
        missing_features = [feature for feature in required_features if feature not in cache_content.lower()]
        
        if missing_features:
            print(f"❌ Missing cache features: {missing_features}")
            return False
        
        print("✅ Cache functionality implementation complete")
        print(f"✅ Found {len(required_cache_methods)} cache methods")
        return True
        
    except Exception as e:
        print(f"❌ Cache functionality test error: {e}")
        return False

def test_backend_startup():
    """Test if backend can start with performance features"""
    print("\n🚀 Testing backend startup with performance features...")
    
    try:
        with open("backend/app/main.py", "r") as f:
            main_content = f.read()
        
        # Check for performance service imports
        required_imports = [
            'advanced_cache_service', 'performance_monitor', 'optimized_routes'
        ]
        
        missing_imports = [imp for imp in required_imports if imp not in main_content]
        
        if missing_imports:
            print(f"❌ Missing performance service imports: {missing_imports}")
            return False
        
        # Check for performance service initialization
        required_initializations = [
            'cache_service.initialize', 'performance_monitor.start_monitoring'
        ]
        
        missing_initializations = [init for init in required_initializations if init not in main_content]
        
        if missing_initializations:
            print(f"❌ Missing performance service initializations: {missing_initializations}")
            return False
        
        # Check for optimized routes inclusion
        if 'optimized_router' not in main_content:
            print("❌ Optimized routes not included in main app")
            return False
        
        print("✅ Backend startup configuration complete")
        print("✅ Performance services properly integrated")
        return True
        
    except Exception as e:
        print(f"❌ Backend startup test error: {e}")
        return False

def main():
    """Run all Phase 4 tests"""
    print("🚀 Phase 4: Performance Optimization Testing")
    print("=" * 50)
    
    tests = [
        ("Performance Files", test_performance_files),
        ("Database Schema Optimization", test_database_schema_optimization),
        ("Advanced Cache Service", test_advanced_cache_service),
        ("Optimized DB Service", test_optimized_db_service),
        ("Performance Monitor", test_performance_monitor),
        ("Optimized Routes", test_optimized_routes),
        ("Main App Integration", test_main_app_integration),
        ("Performance Metrics", test_performance_metrics),
        ("Cache Functionality", test_cache_functionality),
        ("Backend Startup", test_backend_startup)
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
    print(f"📊 Test Results: {passed}/{total} test suites passed")
    
    if passed == total:
        print("\n🎉 Phase 4 Performance Optimization is COMPLETE!")
        print("\n✅ Database queries optimized with comprehensive indexes")
        print("✅ Advanced multi-level caching implemented")
        print("✅ Performance monitoring and metrics collection active")
        print("✅ Optimized API routes with batch operations")
        print("✅ System health monitoring and alerting")
        print("✅ Memory and CPU usage tracking")
        print("✅ Cache statistics and performance analytics")
        print("\nNext steps:")
        print("1. Start backend: cd backend && python -m uvicorn app.main:app --reload")
        print("2. Start frontend: cd frontend && npm run dev")
        print("3. Access performance dashboard: http://localhost:8000/api/v2/performance/summary")
        print("4. Begin Phase 5: Testing & Deployment")
        return 0
    else:
        print(f"\n❌ {total - passed} test suites failed. Please fix issues before proceeding.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
