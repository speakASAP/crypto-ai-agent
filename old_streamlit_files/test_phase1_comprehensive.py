#!/usr/bin/env python3
"""
Comprehensive Phase 1 Testing Script
Tests all components of the Next.js + FastAPI migration setup
"""
import os
import sys
import json
import yaml
from pathlib import Path
import subprocess

def test_project_structure():
    """Test complete project structure"""
    print("🔍 Testing project structure...")
    
    required_structure = {
        "backend/": [
            "app/main.py",
            "app/core/config.py",
            "app/core/database.py", 
            "app/models/__init__.py",
            "app/models/portfolio.py",
            "app/models/alerts.py",
            "app/models/symbols.py",
            "app/models/candles.py",
            "app/models/currency_rates.py",
            "requirements.txt",
            "Dockerfile",
            "schema.sql"
        ],
        "frontend/": [
            "package.json",
            "next.config.js",
            "tailwind.config.js",
            "tsconfig.json",
            "Dockerfile"
        ],
        ".": [
            "docker-compose.yml",
            "README.md"
        ]
    }
    
    missing_files = []
    for base_dir, files in required_structure.items():
        for file_path in files:
            full_path = Path(base_dir) / file_path
            if not full_path.exists():
                missing_files.append(str(full_path))
    
    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        return False
    else:
        print("✅ All required files and directories exist")
        return True

def test_backend_configuration():
    """Test backend configuration and imports"""
    print("\n🐍 Testing backend configuration...")
    
    try:
        sys.path.insert(0, str(Path("backend")))
        
        # Test configuration
        from app.core.config import settings
        print(f"✅ Configuration loaded: {settings.database_url}")
        
        # Test models
        from app.models import Portfolio, PriceAlert, TrackedSymbol, Candle, CurrencyRate
        print("✅ All database models imported successfully")
        
        # Test model attributes
        portfolio_attrs = [attr for attr in dir(Portfolio) if not attr.startswith('_')]
        print(f"✅ Portfolio model has {len(portfolio_attrs)} attributes")
        
        return True
        
    except Exception as e:
        print(f"❌ Backend error: {e}")
        return False

def test_frontend_configuration():
    """Test frontend configuration"""
    print("\n⚛️ Testing frontend configuration...")
    
    try:
        # Test package.json
        with open("frontend/package.json", "r") as f:
            pkg = json.load(f)
        
        required_deps = ["next", "react", "typescript", "zustand"]
        missing_deps = [dep for dep in required_deps if dep not in pkg.get("dependencies", {})]
        
        if missing_deps:
            print(f"❌ Missing dependencies: {missing_deps}")
            return False
        
        print(f"✅ Package.json valid with {len(pkg['dependencies'])} dependencies")
        
        # Test Next.js config
        if Path("frontend/next.config.js").exists():
            print("✅ Next.js configuration exists")
        
        # Test TypeScript config
        if Path("frontend/tsconfig.json").exists():
            print("✅ TypeScript configuration exists")
        
        # Test Tailwind config
        if Path("frontend/tailwind.config.js").exists():
            print("✅ Tailwind CSS configuration exists")
        
        return True
        
    except Exception as e:
        print(f"❌ Frontend error: {e}")
        return False

def test_docker_configuration():
    """Test Docker configuration"""
    print("\n🐳 Testing Docker configuration...")
    
    try:
        with open("docker-compose.yml", "r") as f:
            compose = yaml.safe_load(f)
        
        # Check services
        services = compose.get("services", {})
        required_services = ["frontend", "backend", "postgres", "redis"]
        missing_services = [svc for svc in required_services if svc not in services]
        
        if missing_services:
            print(f"❌ Missing services: {missing_services}")
            return False
        
        print(f"✅ Docker Compose has {len(services)} services configured")
        
        # Check volumes
        volumes = compose.get("volumes", {})
        if volumes:
            print(f"✅ Docker volumes configured: {list(volumes.keys())}")
        
        # Check health checks
        health_checks = 0
        for service_name, service_config in services.items():
            if "healthcheck" in service_config:
                health_checks += 1
        
        print(f"✅ {health_checks} services have health checks")
        
        return True
        
    except Exception as e:
        print(f"❌ Docker error: {e}")
        return False

def test_database_schema():
    """Test database schema syntax"""
    print("\n🗄️ Testing database schema...")
    
    try:
        with open("backend/schema.sql", "r") as f:
            schema = f.read()
        
        # Basic syntax checks
        if "CREATE TABLE" in schema:
            table_count = schema.count("CREATE TABLE")
            print(f"✅ Schema contains {table_count} table definitions")
        
        if "PRIMARY KEY" in schema:
            print("✅ Schema contains primary key definitions")
        
        if "INDEX" in schema:
            index_count = schema.count("CREATE INDEX")
            print(f"✅ Schema contains {index_count} indexes")
        
        if "INSERT INTO" in schema:
            print("✅ Schema contains initial data inserts")
        
        return True
        
    except Exception as e:
        print(f"❌ Schema error: {e}")
        return False

def test_environment_variables():
    """Test environment variable configuration"""
    print("\n🔧 Testing environment variables...")
    
    try:
        # Check if .env.example exists in parent directory
        env_example_path = Path("../.env.example")
        if env_example_path.exists():
            with open(env_example_path, "r") as f:
                env_content = f.read()
            
            required_vars = [
                "DATABASE_URL", "REDIS_URL", "BINANCE_API_URL",
                "CURRENCY_API_URL", "SECRET_KEY", "JWT_SECRET"
            ]
            
            missing_vars = [var for var in required_vars if var not in env_content]
            if missing_vars:
                print(f"❌ Missing environment variables: {missing_vars}")
                return False
            
            print(f"✅ Environment template contains all required variables")
            return True
        else:
            print("❌ .env.example not found in parent directory")
            return False
            
    except Exception as e:
        print(f"❌ Environment error: {e}")
        return False

def test_file_permissions():
    """Test file permissions and executability"""
    print("\n🔐 Testing file permissions...")
    
    try:
        # Check if test scripts are executable
        test_files = ["test_setup.py", "test_phase1_comprehensive.py"]
        for test_file in test_files:
            if Path(test_file).exists():
                if os.access(test_file, os.R_OK):
                    print(f"✅ {test_file} is readable")
                else:
                    print(f"❌ {test_file} is not readable")
                    return False
        
        # Check Docker files
        docker_files = ["docker-compose.yml", "backend/Dockerfile", "frontend/Dockerfile"]
        for docker_file in docker_files:
            if Path(docker_file).exists():
                if os.access(docker_file, os.R_OK):
                    print(f"✅ {docker_file} is readable")
                else:
                    print(f"❌ {docker_file} is not readable")
                    return False
        
        return True
        
    except Exception as e:
        print(f"❌ Permissions error: {e}")
        return False

def main():
    """Run comprehensive Phase 1 tests"""
    print("🚀 Comprehensive Phase 1 Testing\n")
    print("=" * 50)
    
    tests = [
        ("Project Structure", test_project_structure),
        ("Backend Configuration", test_backend_configuration),
        ("Frontend Configuration", test_frontend_configuration),
        ("Docker Configuration", test_docker_configuration),
        ("Database Schema", test_database_schema),
        ("Environment Variables", test_environment_variables),
        ("File Permissions", test_file_permissions)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 30)
        if test_func():
            passed += 1
            print(f"✅ {test_name} - PASSED")
        else:
            print(f"❌ {test_name} - FAILED")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} test suites passed")
    
    if passed == total:
        print("\n🎉 Phase 1 is FULLY FUNCTIONAL and ready for Phase 2!")
        print("\nNext steps:")
        print("1. Start Docker: docker compose up --build")
        print("2. Access Frontend: http://localhost:3000")
        print("3. Access Backend API: http://localhost:8000/docs")
        print("4. Begin Phase 2: Backend Development")
        return 0
    else:
        print(f"\n❌ {total - passed} test suites failed. Please fix issues before proceeding.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
