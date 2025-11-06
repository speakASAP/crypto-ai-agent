#!/usr/bin/env python3
"""
Integration tests for service connections
Tests connectivity between nginx, frontend, backend, and database services
"""
import os
import sys
import time
import requests
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import docker
from docker.errors import DockerException

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from backend.app.utils.logger import get_logger
except ImportError:
    try:
        from app.utils.logger import get_logger
    except ImportError:
        from utils.logger import get_logger

logger = get_logger("tests.test_service_connections")

class ServiceConnectionTester:
    """Test service connections and network configuration"""
    
    def __init__(self):
        self.docker_client = None
        self.test_results = {}
        self.services = {
            'nginx': {
                'container_name': 'nginx-microservice',
                'network': 'nginx-network',
                'ports': {'80': 80, '443': 443}
            },
            'backend': {
                'container_name': 'crypto-ai-backend',
                'network': 'nginx-network',
                'ports': {'8100': 8100},
                'internal_url': 'http://crypto-ai-backend:8100'
            },
            'frontend': {
                'container_name': 'crypto-ai-frontend',
                'network': 'nginx-network',
                'ports': {'3100': 3100},
                'internal_url': 'http://crypto-ai-frontend:3100'
            },
            'postgres': {
                'container_name': 'crypto-ai-postgres',
                'network': 'nginx-network',
                'ports': {'5432': 5432}
            }
        }
        
    def init_docker_client(self):
        """Initialize Docker client"""
        try:
            self.docker_client = docker.from_env()
            self.docker_client.ping()
            return True
        except DockerException as e:
            logger.error(f"❌ Failed to connect to Docker: {e}")
            return False
    
    def get_container(self, container_name: str):
        """Get container by name"""
        try:
            containers = self.docker_client.containers.list(all=True, filters={'name': container_name})
            return containers[0] if containers else None
        except Exception as e:
            logger.error(f"❌ Error getting container {container_name}: {e}")
            return None
    
    def check_container_running(self, container_name: str) -> Tuple[bool, Optional[str]]:
        """Check if container is running"""
        container = self.get_container(container_name)
        if not container:
            return False, f"Container {container_name} not found"
        
        if container.status != 'running':
            return False, f"Container {container_name} is {container.status}"
        
        return True, None
    
    def check_network_connectivity(self, container_name: str, network_name: str) -> Tuple[bool, Optional[str]]:
        """Check if container is on the specified network"""
        container = self.get_container(container_name)
        if not container:
            return False, f"Container {container_name} not found"
        
        networks = container.attrs.get('NetworkSettings', {}).get('Networks', {})
        if network_name not in networks:
            return False, f"Container {container_name} not on network {network_name}"
        
        return True, None
    
    def test_docker_network(self) -> bool:
        """Test Docker network configuration"""
        logger.info("🔍 Testing Docker Network Configuration...")
        logger.info("-" * 60)
        
        if not self.init_docker_client():
            self.test_results['docker_network'] = False
            return False
        
        all_passed = True
        
        # Check nginx-network exists
        try:
            networks = self.docker_client.networks.list(names=['nginx-network'])
            if not networks:
                logger.error("❌ Network 'nginx-network' not found")
                all_passed = False
            else:
                logger.info("✅ Network 'nginx-network' exists")
        except Exception as e:
            logger.error(f"❌ Error checking network: {e}")
            all_passed = False
        
        # Check all containers are on the network
        for service_name, config in self.services.items():
            container_name = config['container_name']
            network_name = config.get('network', 'nginx-network')
            
            is_running, error = self.check_container_running(container_name)
            if error:
                logger.warning(f"⚠️  {container_name}: {error}")
                continue
            
            if is_running:
                logger.info(f"✅ {container_name} is running")
            
            on_network, error = self.check_network_connectivity(container_name, network_name)
            if error:
                logger.error(f"❌ {container_name}: {error}")
                all_passed = False
            else:
                logger.info(f"✅ {container_name} is on network {network_name}")
        
        self.test_results['docker_network'] = all_passed
        return all_passed
    
    def test_backend_health(self) -> bool:
        """Test backend health endpoint"""
        logger.info("🔍 Testing Backend Health...")
        logger.info("-" * 60)
        
        test_urls = [
            ('Internal', 'http://crypto-ai-backend:8100/health'),
            ('External', 'http://localhost:8100/health'),
            ('Via Nginx', 'https://crypto-ai-agent.statex.cz/health'),
        ]
        
        all_passed = True
        for label, url in test_urls:
            try:
                response = requests.get(url, timeout=5, verify=False)
                if response.status_code == 200:
                    logger.info(f"✅ {label} ({url}): OK - {response.status_code}")
                    try:
                        data = response.json()
                        logger.debug(f"   Response: {json.dumps(data, indent=2)}")
                    except:
                        logger.debug(f"   Response: {response.text[:100]}")
                else:
                    logger.error(f"❌ {label} ({url}): {response.status_code}")
                    all_passed = False
            except requests.exceptions.ConnectionError:
                logger.error(f"❌ {label} ({url}): Connection refused")
                all_passed = False
            except requests.exceptions.Timeout:
                logger.error(f"❌ {label} ({url}): Timeout")
                all_passed = False
            except Exception as e:
                logger.error(f"❌ {label} ({url}): {e}")
                all_passed = False
        
        self.test_results['backend_health'] = all_passed
        return all_passed
    
    def test_backend_api_endpoints(self) -> bool:
        """Test backend API endpoints"""
        logger.info("🔍 Testing Backend API Endpoints...")
        logger.info("-" * 60)
        
        # Test endpoints that should exist
        endpoints = [
            '/api/portfolio/',
            '/api/portfolio/summary',
            '/api/alerts/',
            '/api/symbols/tracked',
            '/api/symbols/last-updated',
            '/api/currency/rates',
        ]
        
        test_urls = [
            ('Internal Direct', 'http://crypto-ai-backend:8100'),
            ('External Direct', 'http://localhost:8100'),
            ('Via Nginx', 'https://crypto-ai-agent.statex.cz'),
        ]
        
        all_passed = True
        for endpoint in endpoints:
            logger.info(f"📋 Testing endpoint: {endpoint}")
            
            for label, base_url in test_urls:
                url = f"{base_url}{endpoint}"
                try:
                    # Use GET with auth header (will fail auth but should return 401, not 404)
                    response = requests.get(url, timeout=5, verify=False, headers={
                        'Authorization': 'Bearer test-token'
                    })
                    
                    if response.status_code == 401:
                        logger.info(f"   ✅ {label}: {url} - Auth required (401)")
                    elif response.status_code == 404:
                        logger.error(f"   ❌ {label}: {url} - Not Found (404)")
                        logger.debug(f"      Response: {response.text[:200]}")
                        all_passed = False
                    elif response.status_code == 200:
                        logger.info(f"   ✅ {label}: {url} - OK (200)")
                    else:
                        logger.warning(f"   ⚠️  {label}: {url} - {response.status_code}")
                        
                except requests.exceptions.ConnectionError:
                    logger.error(f"   ❌ {label}: {url} - Connection refused")
                    all_passed = False
                except requests.exceptions.Timeout:
                    logger.error(f"   ❌ {label}: {url} - Timeout")
                    all_passed = False
                except Exception as e:
                    logger.error(f"   ❌ {label}: {url} - {e}")
                    all_passed = False
        
        self.test_results['backend_api_endpoints'] = all_passed
        return all_passed
    
    def test_frontend_connectivity(self) -> bool:
        """Test frontend connectivity"""
        logger.info("🔍 Testing Frontend Connectivity...")
        logger.info("-" * 60)
        
        test_urls = [
            ('Internal', 'http://crypto-ai-frontend:3100'),
            ('External', 'http://localhost:3100'),
            ('Via Nginx', 'https://crypto-ai-agent.statex.cz'),
        ]
        
        all_passed = True
        for label, url in test_urls:
            try:
                response = requests.get(url, timeout=5, verify=False)
                if response.status_code == 200:
                    logger.info(f"✅ {label} ({url}): OK - {response.status_code}")
                    if 'crypto' in response.text.lower() or 'portfolio' in response.text.lower():
                        logger.info(f"   ✅ Content appears to be frontend")
                    else:
                        logger.warning(f"   ⚠️  Content doesn't look like frontend")
                else:
                    logger.error(f"❌ {label} ({url}): {response.status_code}")
                    all_passed = False
            except requests.exceptions.ConnectionError:
                logger.error(f"❌ {label} ({url}): Connection refused")
                all_passed = False
            except requests.exceptions.Timeout:
                logger.error(f"❌ {label} ({url}): Timeout")
                all_passed = False
            except Exception as e:
                logger.error(f"❌ {label} ({url}): {e}")
                all_passed = False
        
        self.test_results['frontend_connectivity'] = all_passed
        return all_passed
    
    def test_nginx_proxy_config(self) -> bool:
        """Test nginx proxy configuration"""
        logger.info("🔍 Testing Nginx Proxy Configuration...")
        logger.info("-" * 60)
        
        # Test API proxy through nginx
        api_endpoints = [
            '/api/portfolio/',
            '/api/portfolio/summary',
            '/api/alerts/',
            '/api/symbols/tracked',
            '/api/currency/rates',
        ]
        
        all_passed = True
        nginx_url = 'https://crypto-ai-agent.statex.cz'
        
        logger.info(f"📋 Testing API proxy through nginx: {nginx_url}")
        
        for endpoint in api_endpoints:
            url = f"{nginx_url}{endpoint}"
            try:
                response = requests.get(url, timeout=5, verify=False, headers={
                    'Authorization': 'Bearer test-token'
                }, allow_redirects=False)
                
                # Should get 401 (auth required) or 200, not 404
                if response.status_code == 401:
                    logger.info(f"   ✅ {endpoint} - Auth required (401) - Proxy working")
                elif response.status_code == 404:
                    logger.error(f"   ❌ {endpoint} - Not Found (404) - Proxy misconfigured")
                    logger.debug(f"      Response: {response.text[:200]}")
                    all_passed = False
                elif response.status_code == 200:
                    logger.info(f"   ✅ {endpoint} - OK (200) - Proxy working")
                else:
                    logger.warning(f"   ⚠️  {endpoint} - {response.status_code}")
                    
            except requests.exceptions.SSLError as e:
                logger.warning(f"   ⚠️  {endpoint} - SSL Error (using verify=False): {e}")
                # Try HTTP instead
                http_url = url.replace('https://', 'http://')
                try:
                    response = requests.get(http_url, timeout=5, headers={
                        'Authorization': 'Bearer test-token'
                    }, allow_redirects=False)
                    if response.status_code == 401:
                        logger.info(f"   ✅ {endpoint} (HTTP) - Auth required (401)")
                    elif response.status_code == 404:
                        logger.error(f"   ❌ {endpoint} (HTTP) - Not Found (404)")
                        all_passed = False
                except Exception as e2:
                    logger.error(f"   ❌ {endpoint} (HTTP fallback): {e2}")
                    all_passed = False
            except Exception as e:
                logger.error(f"   ❌ {endpoint}: {e}")
                all_passed = False
        
        # Test frontend proxy
        logger.info(f"📋 Testing frontend proxy through nginx: {nginx_url}")
        try:
            response = requests.get(nginx_url, timeout=5, verify=False, allow_redirects=False)
            if response.status_code == 200:
                logger.info(f"   ✅ Frontend proxy working (200)")
            else:
                logger.warning(f"   ⚠️  Frontend proxy returned {response.status_code}")
        except Exception as e:
            logger.error(f"   ❌ Frontend proxy error: {e}")
            all_passed = False
        
        self.test_results['nginx_proxy_config'] = all_passed
        return all_passed
    
    def test_dns_resolution(self) -> bool:
        """Test DNS resolution between containers"""
        logger.info("🔍 Testing DNS Resolution Between Containers...")
        logger.info("-" * 60)
        
        if not self.init_docker_client():
            self.test_results['dns_resolution'] = False
            return False
        
        # Get backend container
        backend_container = self.get_container('crypto-ai-backend')
        if not backend_container:
            logger.error("❌ Backend container not found")
            self.test_results['dns_resolution'] = False
            return False
        
        # Test DNS resolution from backend to other services
        dns_tests = [
            ('crypto-ai-frontend', '3100'),
            ('crypto-ai-postgres', '5432'),
            ('crypto-ai-backend', '8100'),
        ]
        
        all_passed = True
        for hostname, port in dns_tests:
            try:
                # Execute nslookup or ping from backend container
                exec_result = backend_container.exec_run(
                    f"nslookup {hostname} || getent hosts {hostname} || ping -c 1 {hostname}",
                    user='root'
                )
                
                if exec_result.exit_code == 0:
                    logger.info(f"✅ {hostname}: DNS resolution OK")
                    output = exec_result.output.decode('utf-8') if exec_result.output else ''
                    if output:
                        logger.debug(f"   Output: {output[:100]}")
                else:
                    logger.error(f"❌ {hostname}: DNS resolution failed")
                    output = exec_result.output.decode('utf-8') if exec_result.output else ''
                    if output:
                        logger.debug(f"   Error: {output[:200]}")
                    all_passed = False
            except Exception as e:
                logger.error(f"❌ {hostname}: Error testing DNS - {e}")
                all_passed = False
        
        self.test_results['dns_resolution'] = all_passed
        return all_passed
    
    def test_nginx_config_syntax(self) -> bool:
        """Test nginx configuration syntax"""
        logger.info("🔍 Testing Nginx Configuration Syntax...")
        logger.info("-" * 60)
        
        nginx_container = self.get_container('nginx-microservice')
        if not nginx_container:
            logger.error("❌ Nginx container not found")
            self.test_results['nginx_config_syntax'] = False
            return False
        
        try:
            # Test nginx configuration
            exec_result = nginx_container.exec_run("nginx -t")
            
            if exec_result.exit_code == 0:
                logger.info("✅ Nginx configuration syntax is valid")
                output = exec_result.output.decode('utf-8') if exec_result.output else ''
                if output:
                    logger.debug(f"   Output: {output}")
                self.test_results['nginx_config_syntax'] = True
                return True
            else:
                logger.error("❌ Nginx configuration syntax error")
                output = exec_result.output.decode('utf-8') if exec_result.output else ''
                if output:
                    logger.debug(f"   Error: {output}")
                self.test_results['nginx_config_syntax'] = False
                return False
        except Exception as e:
            logger.error(f"❌ Error testing nginx config: {e}")
            self.test_results['nginx_config_syntax'] = False
            return False
    
    def analyze_nginx_logs(self) -> bool:
        """Analyze nginx logs for errors"""
        logger.info("🔍 Analyzing Nginx Logs...")
        logger.info("-" * 60)
        
        nginx_container = self.get_container('nginx-microservice')
        if not nginx_container:
            logger.error("❌ Nginx container not found")
            self.test_results['nginx_logs'] = False
            return False
        
        try:
            # Get recent logs
            logs = nginx_container.logs(tail=100).decode('utf-8')
            
            # Look for errors
            error_count = 0
            error_lines = []
            
            for line in logs.split('\n'):
                if 'error' in line.lower() or 'failed' in line.lower() or '404' in line:
                    error_count += 1
                    error_lines.append(line)
                    if error_count <= 10:  # Show first 10 errors
                        logger.warning(f"   ⚠️  {line}")
            
            if error_count == 0:
                logger.info("✅ No errors found in nginx logs")
                self.test_results['nginx_logs'] = True
                return True
            else:
                logger.warning(f"⚠️  Found {error_count} potential errors in nginx logs")
                if error_count > 10:
                    logger.info(f"   (Showing first 10, total: {error_count})")
                self.test_results['nginx_logs'] = False
                return False
                
        except Exception as e:
            logger.error(f"❌ Error analyzing nginx logs: {e}")
            self.test_results['nginx_logs'] = False
            return False
    
    def run_all_tests(self) -> bool:
        """Run all service connection tests"""
        logger.info("=" * 60)
        logger.info("🚀 Starting Service Connection Tests")
        logger.info("=" * 60)
        
        tests = [
            ("Docker Network", self.test_docker_network),
            ("Nginx Config Syntax", self.test_nginx_config_syntax),
            ("DNS Resolution", self.test_dns_resolution),
            ("Backend Health", self.test_backend_health),
            ("Backend API Endpoints", self.test_backend_api_endpoints),
            ("Frontend Connectivity", self.test_frontend_connectivity),
            ("Nginx Proxy Config", self.test_nginx_proxy_config),
            ("Nginx Logs Analysis", self.analyze_nginx_logs),
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            try:
                if test_func():
                    passed += 1
            except Exception as e:
                logger.error(f"❌ {test_name} - Exception: {e}", exc_info=True)
        
        # Print summary
        logger.info("=" * 60)
        logger.info("TEST SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Tests: {total}")
        logger.info(f"Passed: {passed}")
        logger.info(f"Failed: {total - passed}")
        logger.info(f"Success Rate: {(passed / total) * 100:.1f}%")
        
        logger.info("Detailed Results:")
        for test_name, result in self.test_results.items():
            status = "✅ PASSED" if result else "❌ FAILED"
            logger.info(f"  {test_name}: {status}")
        
        return passed == total


def main():
    """Main function"""
    import warnings
    warnings.filterwarnings('ignore', message='Unverified HTTPS request')
    
    tester = ServiceConnectionTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

