#!/usr/bin/env python3
"""
Test script to validate Phase 1 setup
"""
import os
import sys
from pathlib import Path

def test_project_structure():
    """Test that all required files and directories exist"""
    print("🔍 Testing project structure...")
    
    required_files = [
        "backend/app/main.py",
        "backend/app/core/config.py", 
        "backend/app/core/database.py",
        "backend/app/models/__init__.py",
        "backend/app/models/portfolio.py",
        "backend/app/models/alerts.py",
        "backend/app/models/symbols.py",
        "backend/app/models/candles.py",
        "backend/app/models/currency_rates.py",
        "backend/requirements.txt",
        "backend/Dockerfile",
        "backend/schema.sql",
        "frontend/package.json",
        "frontend/next.config.js",
        "frontend/tailwind.config.js",
        "frontend/tsconfig.json",
        "frontend/Dockerfile",
        "docker-compose.yml",
        "README.md"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        return False
    else:
        print("✅ All required files exist")
        return True

def test_python_imports():
    """Test that Python modules can be imported"""
    print("\n🐍 Testing Python imports...")
    
    try:
        # Add backend to path
        sys.path.insert(0, str(Path("backend")))
        
        # Test core imports (skip database connection for now)
        from app.core.config import settings
        from app.models import Portfolio, PriceAlert, TrackedSymbol
        
        print("✅ Core modules imported successfully")
        print(f"✅ Database URL: {settings.database_url}")
        print(f"✅ Redis URL: {settings.redis_url}")
        print("ℹ️  Database connection test skipped (requires PostgreSQL)")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_docker_compose():
    """Test Docker Compose configuration"""
    print("\n🐳 Testing Docker Compose configuration...")
    
    try:
        import yaml
        with open("docker-compose.yml", "r") as f:
            compose_config = yaml.safe_load(f)
        
        required_services = ["frontend", "backend", "postgres", "redis"]
        services = list(compose_config.get("services", {}).keys())
        
        missing_services = set(required_services) - set(services)
        if missing_services:
            print(f"❌ Missing services: {missing_services}")
            return False
        else:
            print("✅ All required services configured")
            return True
            
    except Exception as e:
        print(f"❌ Docker Compose error: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Testing Phase 1: Project Setup & Infrastructure\n")
    
    tests = [
        test_project_structure,
        test_python_imports,
        test_docker_compose
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 Phase 1 setup is complete and ready for Phase 2!")
        return 0
    else:
        print("❌ Some tests failed. Please fix the issues before proceeding.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
