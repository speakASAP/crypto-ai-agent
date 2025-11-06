#!/usr/bin/env python3
"""
Comprehensive Test Runner for Crypto AI Agent v2
"""
import os
import sys
import subprocess
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from backend.app.utils.logger import get_logger
except ImportError:
    try:
        from app.utils.logger import get_logger
    except ImportError:
        from utils.logger import get_logger

logger = get_logger("tests.run_tests")


class TestRunner:
    """Test runner for the entire application"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.backend_dir = self.project_root / "backend"
        self.frontend_dir = self.project_root / "frontend"
        self.results = {}
    
    def run_command(self, command, cwd=None, timeout=300):
        """Run a command and return the result"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd or self.project_root,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds"
            }
        except Exception as e:
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": str(e)
            }
    
    def test_backend_unit_tests(self):
        """Run backend unit tests"""
        logger.info("🧪 Running backend unit tests...")
        
        # Install test dependencies
        install_result = self.run_command(
            "pip3 install pytest pytest-asyncio httpx",
            cwd=self.backend_dir
        )
        
        if not install_result["success"]:
            logger.error(f"❌ Failed to install test dependencies: {install_result['stderr']}")
            return False
        
        # Run tests
        test_result = self.run_command(
            "python -m pytest tests/ -v --tb=short",
            cwd=self.backend_dir
        )
        
        if test_result["success"]:
            logger.info("✅ Backend unit tests passed")
            self.results["backend_unit_tests"] = True
            return True
        else:
            logger.error(f"❌ Backend unit tests failed: {test_result['stderr']}")
            self.results["backend_unit_tests"] = False
            return False
    
    def test_backend_integration_tests(self):
        """Run backend integration tests"""
        logger.info("🔗 Running backend integration tests...")
        
        # Run integration tests
        test_result = self.run_command(
            "python -m pytest tests/test_api_integration.py -v --tb=short",
            cwd=self.backend_dir
        )
        
        if test_result["success"]:
            logger.info("✅ Backend integration tests passed")
            self.results["backend_integration_tests"] = True
            return True
        else:
            logger.error(f"❌ Backend integration tests failed: {test_result['stderr']}")
            self.results["backend_integration_tests"] = False
            return False
    
    def test_frontend_unit_tests(self):
        """Run frontend unit tests"""
        logger.info("🧪 Running frontend unit tests...")
        
        # Install test dependencies
        install_result = self.run_command(
            "npm install --save-dev @testing-library/react @testing-library/jest-dom jest-environment-jsdom",
            cwd=self.frontend_dir
        )
        
        if not install_result["success"]:
            logger.error(f"❌ Failed to install test dependencies: {install_result['stderr']}")
            return False
        
        # Run tests
        test_result = self.run_command(
            "npm test -- --watchAll=false --coverage",
            cwd=self.frontend_dir
        )
        
        if test_result["success"]:
            logger.info("✅ Frontend unit tests passed")
            self.results["frontend_unit_tests"] = True
            return True
        else:
            logger.error(f"❌ Frontend unit tests failed: {test_result['stderr']}")
            self.results["frontend_unit_tests"] = False
            return False
    
    def test_load_testing(self):
        """Run load testing"""
        logger.info("⚡ Running load testing...")
        
        # Install load test dependencies
        install_result = self.run_command(
            "pip3 install aiohttp",
            cwd=self.backend_dir
        )
        
        if not install_result["success"]:
            logger.error(f"❌ Failed to install load test dependencies: {install_result['stderr']}")
            return False
        
        # Run load test
        test_result = self.run_command(
            "python tests/load_test.py --concurrency 5 --requests 10",
            cwd=self.backend_dir
        )
        
        if test_result["success"]:
            logger.info("✅ Load testing completed")
            self.results["load_testing"] = True
            return True
        else:
            logger.error(f"❌ Load testing failed: {test_result['stderr']}")
            self.results["load_testing"] = False
            return False
    
    def test_build_processes(self):
        """Test build processes"""
        logger.info("🔨 Testing build processes...")
        
        # Test backend build
        backend_build = self.run_command(
            "python -c 'import app.main; from app.utils.logger import get_logger; logger = get_logger(\"tests.run_tests\"); logger.info(\"Backend imports successful\")'",
            cwd=self.backend_dir
        )
        
        if not backend_build["success"]:
            logger.error(f"❌ Backend build test failed: {backend_build['stderr']}")
            self.results["backend_build"] = False
            return False
        
        # Test frontend build
        frontend_build = self.run_command(
            "npm run build",
            cwd=self.frontend_dir
        )
        
        if not frontend_build["success"]:
            logger.error(f"❌ Frontend build test failed: {frontend_build['stderr']}")
            self.results["frontend_build"] = False
            return False
        
        logger.info("✅ Build processes successful")
        self.results["backend_build"] = True
        self.results["frontend_build"] = True
        return True
    
    def test_docker_builds(self):
        """Test Docker builds"""
        logger.info("🐳 Testing Docker builds...")
        
        # Test backend Docker build
        backend_docker = self.run_command(
            "docker build -t crypto-ai-agent-backend-test -f Dockerfile .",
            cwd=self.backend_dir,
            timeout=600
        )
        
        if not backend_docker["success"]:
            logger.error(f"❌ Backend Docker build failed: {backend_docker['stderr']}")
            self.results["backend_docker"] = False
            return False
        
        # Test frontend Docker build
        frontend_docker = self.run_command(
            "docker build -t crypto-ai-agent-frontend-test -f Dockerfile .",
            cwd=self.frontend_dir,
            timeout=600
        )
        
        if not frontend_docker["success"]:
            logger.error(f"❌ Frontend Docker build failed: {frontend_docker['stderr']}")
            self.results["frontend_docker"] = False
            return False
        
        logger.info("✅ Docker builds successful")
        self.results["backend_docker"] = True
        self.results["frontend_docker"] = True
        return True
    
    def test_security_scan(self):
        """Run security scan"""
        logger.info("🔒 Running security scan...")
        
        # Install security tools
        install_result = self.run_command(
            "pip3 install bandit safety",
            cwd=self.backend_dir
        )
        
        if not install_result["success"]:
            logger.error(f"❌ Failed to install security tools: {install_result['stderr']}")
            return False
        
        # Run bandit security scan
        bandit_result = self.run_command(
            "bandit -r app/ -f json",
            cwd=self.backend_dir
        )
        
        # Run safety check
        safety_result = self.run_command(
            "safety check --json",
            cwd=self.backend_dir
        )
        
        if bandit_result["success"] and safety_result["success"]:
            logger.info("✅ Security scan completed")
            self.results["security_scan"] = True
            return True
        else:
            logger.error(f"❌ Security scan failed: {bandit_result['stderr']} {safety_result['stderr']}")
            self.results["security_scan"] = False
            return False
    
    def test_code_quality(self):
        """Run code quality checks"""
        logger.info("📊 Running code quality checks...")
        
        # Install quality tools
        install_result = self.run_command(
            "pip3 install black isort flake8 mypy",
            cwd=self.backend_dir
        )
        
        if not install_result["success"]:
            logger.error(f"❌ Failed to install quality tools: {install_result['stderr']}")
            return False
        
        # Run code formatting check
        black_result = self.run_command(
            "black --check app/",
            cwd=self.backend_dir
        )
        
        # Run import sorting check
        isort_result = self.run_command(
            "isort --check-only app/",
            cwd=self.backend_dir
        )
        
        # Run linting
        flake8_result = self.run_command(
            "flake8 app/",
            cwd=self.backend_dir
        )
        
        # Run type checking
        mypy_result = self.run_command(
            "mypy app/",
            cwd=self.backend_dir
        )
        
        if all([black_result["success"], isort_result["success"], 
                flake8_result["success"], mypy_result["success"]]):
            logger.info("✅ Code quality checks passed")
            self.results["code_quality"] = True
            return True
        else:
            logger.error(f"❌ Code quality checks failed")
            self.results["code_quality"] = False
            return False
    
    def run_all_tests(self):
        """Run all tests"""
        logger.info("🚀 Starting comprehensive test suite...")
        logger.info("=" * 60)
        
        start_time = time.time()
        
        # Run all test categories
        test_categories = [
            ("Backend Unit Tests", self.test_backend_unit_tests),
            ("Backend Integration Tests", self.test_backend_integration_tests),
            ("Frontend Unit Tests", self.test_frontend_unit_tests),
            ("Load Testing", self.test_load_testing),
            ("Build Processes", self.test_build_processes),
            ("Docker Builds", self.test_docker_builds),
            ("Security Scan", self.test_security_scan),
            ("Code Quality", self.test_code_quality)
        ]
        
        passed = 0
        total = len(test_categories)
        
        for test_name, test_func in test_categories:
            logger.info(f"📋 {test_name}")
            logger.info("-" * 40)
            
            try:
                if test_func():
                    passed += 1
                    logger.info(f"✅ {test_name} - PASSED")
                else:
                    logger.error(f"❌ {test_name} - FAILED")
            except Exception as e:
                logger.error(f"❌ {test_name} - ERROR: {e}", exc_info=True)
                self.results[test_name.lower().replace(" ", "_")] = False
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Print summary
        logger.info("=" * 60)
        logger.info("TEST SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Tests: {total}")
        logger.info(f"Passed: {passed}")
        logger.info(f"Failed: {total - passed}")
        logger.info(f"Success Rate: {(passed / total) * 100:.1f}%")
        logger.info(f"Total Time: {total_time:.2f} seconds")
        
        # Print detailed results
        logger.info("Detailed Results:")
        for test_name, result in self.results.items():
            status = "✅ PASSED" if result else "❌ FAILED"
            logger.info(f"  {test_name}: {status}")
        
        if passed == total:
            logger.info("🎉 All tests passed! The application is ready for deployment.")
            return True
        else:
            logger.error(f"❌ {total - passed} test categories failed. Please fix issues before deployment.")
            return False


def main():
    """Main function"""
    runner = TestRunner()
    success = runner.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
