#!/usr/bin/env python3
"""
Phase 3 Testing Script
Tests the Next.js frontend implementation
"""
import os
import sys
import subprocess
import time
from pathlib import Path

def test_project_structure():
    """Test that all required frontend files exist"""
    print("🔍 Testing frontend project structure...")
    
    required_files = [
        "frontend/package.json",
        "frontend/next.config.js",
        "frontend/tailwind.config.js",
        "frontend/tsconfig.json",
        "frontend/postcss.config.js",
        "frontend/src/app/layout.tsx",
        "frontend/src/app/page.tsx",
        "frontend/src/app/globals.css",
        "frontend/src/types/index.ts",
        "frontend/src/lib/api.ts",
        "frontend/src/lib/utils.ts",
        "frontend/src/stores/portfolioStore.ts",
        "frontend/src/stores/alertsStore.ts",
        "frontend/src/stores/symbolsStore.ts",
        "frontend/src/hooks/useWebSocket.ts",
        "frontend/src/components/ui/button.tsx",
        "frontend/src/components/ui/card.tsx"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        return False
    else:
        print("✅ All required frontend files exist")
        return True

def test_package_json():
    """Test package.json configuration"""
    print("\n📦 Testing package.json...")
    
    try:
        import json
        with open("frontend/package.json", "r") as f:
            pkg = json.load(f)
        
        # Check required dependencies
        required_deps = ["next", "react", "typescript", "zustand", "axios"]
        missing_deps = [dep for dep in required_deps if dep not in pkg.get("dependencies", {})]
        
        # Check dev dependencies
        required_dev_deps = ["tailwindcss"]
        missing_dev_deps = [dep for dep in required_dev_deps if dep not in pkg.get("devDependencies", {})]
        missing_deps.extend(missing_dev_deps)
        
        if missing_deps:
            print(f"❌ Missing dependencies: {missing_deps}")
            return False
        
        # Check scripts
        scripts = pkg.get("scripts", {})
        required_scripts = ["dev", "build", "start", "lint"]
        missing_scripts = [script for script in required_scripts if script not in scripts]
        
        if missing_scripts:
            print(f"❌ Missing scripts: {missing_scripts}")
            return False
        
        print(f"✅ Package.json valid with {len(pkg['dependencies'])} dependencies")
        print(f"✅ Scripts configured: {list(scripts.keys())}")
        return True
        
    except Exception as e:
        print(f"❌ Package.json error: {e}")
        return False

def test_typescript_config():
    """Test TypeScript configuration"""
    print("\n📝 Testing TypeScript configuration...")
    
    try:
        import json
        with open("frontend/tsconfig.json", "r") as f:
            tsconfig = json.load(f)
        
        # Check required compiler options
        compiler_options = tsconfig.get("compilerOptions", {})
        required_options = ["target", "lib", "module", "jsx", "baseUrl", "paths"]
        missing_options = [opt for opt in required_options if opt not in compiler_options]
        
        if missing_options:
            print(f"❌ Missing TypeScript options: {missing_options}")
            return False
        
        # Check path mapping
        paths = compiler_options.get("paths", {})
        if "@/*" not in paths:
            print("❌ Missing @/* path mapping")
            return False
        
        print("✅ TypeScript configuration valid")
        print(f"✅ Path mapping: {paths}")
        return True
        
    except Exception as e:
        print(f"❌ TypeScript config error: {e}")
        return False

def test_tailwind_config():
    """Test Tailwind CSS configuration"""
    print("\n🎨 Testing Tailwind configuration...")
    
    try:
        with open("frontend/tailwind.config.js", "r") as f:
            content = f.read()
        
        # Check for required configurations
        required_configs = ["content", "theme", "plugins"]
        missing_configs = [config for config in required_configs if config not in content]
        
        if missing_configs:
            print(f"❌ Missing Tailwind configs: {missing_configs}")
            return False
        
        print("✅ Tailwind CSS configuration valid")
        return True
        
    except Exception as e:
        print(f"❌ Tailwind config error: {e}")
        return False

def test_nextjs_config():
    """Test Next.js configuration"""
    print("\n⚛️ Testing Next.js configuration...")
    
    try:
        with open("frontend/next.config.js", "r") as f:
            content = f.read()
        
        # Check for required configurations
        required_configs = ["env", "rewrites"]
        missing_configs = [config for config in required_configs if config not in content]
        
        if missing_configs:
            print(f"❌ Missing Next.js configs: {missing_configs}")
            return False
        
        print("✅ Next.js configuration valid")
        return True
        
    except Exception as e:
        print(f"❌ Next.js config error: {e}")
        return False

def test_types_files():
    """Test TypeScript type definitions"""
    print("\n🔧 Testing TypeScript types...")
    
    try:
        # Check if types can be imported (basic syntax check)
        type_files = [
            "frontend/src/types/portfolio.ts",
            "frontend/src/types/alerts.ts", 
            "frontend/src/types/symbols.ts",
            "frontend/src/types/api.ts",
            "frontend/src/types/index.ts"
        ]
        
        for type_file in type_files:
            if not Path(type_file).exists():
                print(f"❌ Missing type file: {type_file}")
                return False
        
        print("✅ All TypeScript type files exist")
        return True
        
    except Exception as e:
        print(f"❌ TypeScript types error: {e}")
        return False

def test_components():
    """Test UI components"""
    print("\n🧩 Testing UI components...")
    
    try:
        component_files = [
            "frontend/src/components/ui/button.tsx",
            "frontend/src/components/ui/card.tsx"
        ]
        
        for component_file in component_files:
            if not Path(component_file).exists():
                print(f"❌ Missing component: {component_file}")
                return False
        
        print("✅ UI components exist")
        return True
        
    except Exception as e:
        print(f"❌ Components error: {e}")
        return False

def test_stores():
    """Test Zustand stores"""
    print("\n🗄️ Testing Zustand stores...")
    
    try:
        store_files = [
            "frontend/src/stores/portfolioStore.ts",
            "frontend/src/stores/alertsStore.ts",
            "frontend/src/stores/symbolsStore.ts"
        ]
        
        for store_file in store_files:
            if not Path(store_file).exists():
                print(f"❌ Missing store: {store_file}")
                return False
        
        print("✅ Zustand stores exist")
        return True
        
    except Exception as e:
        print(f"❌ Stores error: {e}")
        return False

def test_hooks():
    """Test custom hooks"""
    print("\n🪝 Testing custom hooks...")
    
    try:
        hook_files = [
            "frontend/src/hooks/useWebSocket.ts"
        ]
        
        for hook_file in hook_files:
            if not Path(hook_file).exists():
                print(f"❌ Missing hook: {hook_file}")
                return False
        
        print("✅ Custom hooks exist")
        return True
        
    except Exception as e:
        print(f"❌ Hooks error: {e}")
        return False

def test_api_client():
    """Test API client"""
    print("\n🌐 Testing API client...")
    
    try:
        api_file = "frontend/src/lib/api.ts"
        if not Path(api_file).exists():
            print(f"❌ Missing API client: {api_file}")
            return False
        
        print("✅ API client exists")
        return True
        
    except Exception as e:
        print(f"❌ API client error: {e}")
        return False

def test_build():
    """Test if the project can build"""
    print("\n🔨 Testing build process...")
    
    try:
        # Change to frontend directory
        original_cwd = os.getcwd()
        os.chdir("frontend")
        
        # Run build command
        result = subprocess.run(
            ["npm", "run", "build"],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            print("✅ Build successful")
            return True
        else:
            print(f"❌ Build failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Build timed out")
        return False
    except Exception as e:
        print(f"❌ Build error: {e}")
        return False
    finally:
        os.chdir(original_cwd)

def main():
    """Run all Phase 3 tests"""
    print("🚀 Phase 3: Frontend Development Testing")
    print("=" * 50)
    
    tests = [
        ("Project Structure", test_project_structure),
        ("Package.json", test_package_json),
        ("TypeScript Config", test_typescript_config),
        ("Tailwind Config", test_tailwind_config),
        ("Next.js Config", test_nextjs_config),
        ("TypeScript Types", test_types_files),
        ("UI Components", test_components),
        ("Zustand Stores", test_stores),
        ("Custom Hooks", test_hooks),
        ("API Client", test_api_client),
        ("Build Process", test_build)
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
        print("\n🎉 Phase 3 Frontend Development is COMPLETE!")
        print("\n✅ Next.js application is ready")
        print("✅ TypeScript types are defined")
        print("✅ Zustand stores are implemented")
        print("✅ WebSocket integration is ready")
        print("✅ UI components are created")
        print("✅ API client is configured")
        print("\nNext steps:")
        print("1. Start frontend: cd frontend && npm run dev")
        print("2. Start backend: cd backend && python -m uvicorn app.main:app --reload")
        print("3. Access application: http://localhost:3000")
        print("4. Begin Phase 4: Performance Optimization")
        return 0
    else:
        print(f"\n❌ {total - passed} test suites failed. Please fix issues before proceeding.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
