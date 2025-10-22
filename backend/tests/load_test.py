"""
Load testing script for Crypto AI Agent API
"""
import asyncio
import aiohttp
import time
import statistics
import json
from typing import List, Dict, Any
import argparse


class LoadTester:
    """Load testing class for API endpoints"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results: List[Dict[str, Any]] = []
    
    async def make_request(self, session: aiohttp.ClientSession, method: str, endpoint: str, 
                          data: Dict = None, headers: Dict = None) -> Dict[str, Any]:
        """Make a single API request and measure performance"""
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        try:
            if method.upper() == "GET":
                async with session.get(url, headers=headers) as response:
                    content = await response.text()
                    status_code = response.status
            elif method.upper() == "POST":
                async with session.post(url, json=data, headers=headers) as response:
                    content = await response.text()
                    status_code = response.status
            elif method.upper() == "PUT":
                async with session.put(url, json=data, headers=headers) as response:
                    content = await response.text()
                    status_code = response.status
            elif method.upper() == "DELETE":
                async with session.delete(url, headers=headers) as response:
                    content = await response.text()
                    status_code = response.status
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            end_time = time.time()
            response_time = end_time - start_time
            
            return {
                "method": method,
                "endpoint": endpoint,
                "status_code": status_code,
                "response_time": response_time,
                "success": 200 <= status_code < 300,
                "timestamp": start_time
            }
            
        except Exception as e:
            end_time = time.time()
            response_time = end_time - start_time
            
            return {
                "method": method,
                "endpoint": endpoint,
                "status_code": 0,
                "response_time": response_time,
                "success": False,
                "error": str(e),
                "timestamp": start_time
            }
    
    async def run_concurrent_requests(self, requests: List[Dict], concurrency: int = 10):
        """Run multiple requests concurrently"""
        connector = aiohttp.TCPConnector(limit=concurrency)
        timeout = aiohttp.ClientTimeout(total=30)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            semaphore = asyncio.Semaphore(concurrency)
            
            async def limited_request(request_data):
                async with semaphore:
                    return await self.make_request(session, **request_data)
            
            tasks = [limited_request(req) for req in requests]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions and add to results
            for result in results:
                if isinstance(result, dict):
                    self.results.append(result)
                else:
                    self.results.append({
                        "method": "UNKNOWN",
                        "endpoint": "UNKNOWN",
                        "status_code": 0,
                        "response_time": 0,
                        "success": False,
                        "error": str(result),
                        "timestamp": time.time()
                    })
    
    def generate_test_requests(self, endpoint_configs: List[Dict], num_requests: int) -> List[Dict]:
        """Generate test requests based on endpoint configurations"""
        requests = []
        
        for _ in range(num_requests):
            for config in endpoint_configs:
                request_data = {
                    "method": config["method"],
                    "endpoint": config["endpoint"],
                    "data": config.get("data"),
                    "headers": config.get("headers", {})
                }
                requests.append(request_data)
        
        return requests
    
    def calculate_statistics(self) -> Dict[str, Any]:
        """Calculate performance statistics from results"""
        if not self.results:
            return {}
        
        response_times = [r["response_time"] for r in self.results]
        successful_requests = [r for r in self.results if r["success"]]
        failed_requests = [r for r in self.results if not r["success"]]
        
        stats = {
            "total_requests": len(self.results),
            "successful_requests": len(successful_requests),
            "failed_requests": len(failed_requests),
            "success_rate": len(successful_requests) / len(self.results) * 100,
            "response_times": {
                "min": min(response_times),
                "max": max(response_times),
                "mean": statistics.mean(response_times),
                "median": statistics.median(response_times),
                "p95": self.percentile(response_times, 95),
                "p99": self.percentile(response_times, 99)
            },
            "requests_per_second": len(self.results) / max(response_times) if response_times else 0
        }
        
        # Group by endpoint
        endpoint_stats = {}
        for result in self.results:
            endpoint = result["endpoint"]
            if endpoint not in endpoint_stats:
                endpoint_stats[endpoint] = {
                    "total": 0,
                    "successful": 0,
                    "failed": 0,
                    "response_times": []
                }
            
            endpoint_stats[endpoint]["total"] += 1
            if result["success"]:
                endpoint_stats[endpoint]["successful"] += 1
            else:
                endpoint_stats[endpoint]["failed"] += 1
            endpoint_stats[endpoint]["response_times"].append(result["response_time"])
        
        # Calculate per-endpoint statistics
        for endpoint, data in endpoint_stats.items():
            if data["response_times"]:
                data["avg_response_time"] = statistics.mean(data["response_times"])
                data["success_rate"] = data["successful"] / data["total"] * 100
            else:
                data["avg_response_time"] = 0
                data["success_rate"] = 0
        
        stats["endpoint_stats"] = endpoint_stats
        
        return stats
    
    def percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of data"""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def print_results(self, stats: Dict[str, Any]):
        """Print load test results"""
        print("\n" + "="*60)
        print("LOAD TEST RESULTS")
        print("="*60)
        
        print(f"Total Requests: {stats['total_requests']}")
        print(f"Successful Requests: {stats['successful_requests']}")
        print(f"Failed Requests: {stats['failed_requests']}")
        print(f"Success Rate: {stats['success_rate']:.2f}%")
        print(f"Requests per Second: {stats['requests_per_second']:.2f}")
        
        print("\nResponse Times:")
        rt = stats['response_times']
        print(f"  Min: {rt['min']:.3f}s")
        print(f"  Max: {rt['max']:.3f}s")
        print(f"  Mean: {rt['mean']:.3f}s")
        print(f"  Median: {rt['median']:.3f}s")
        print(f"  95th Percentile: {rt['p95']:.3f}s")
        print(f"  99th Percentile: {rt['p99']:.3f}s")
        
        print("\nPer-Endpoint Statistics:")
        for endpoint, data in stats['endpoint_stats'].items():
            print(f"  {endpoint}:")
            print(f"    Total: {data['total']}")
            print(f"    Success Rate: {data['success_rate']:.2f}%")
            print(f"    Avg Response Time: {data['avg_response_time']:.3f}s")


async def run_load_test(base_url: str, concurrency: int, num_requests: int):
    """Run the load test"""
    tester = LoadTester(base_url)
    
    # Define test endpoints
    endpoint_configs = [
        {"method": "GET", "endpoint": "/health"},
        {"method": "GET", "endpoint": "/api/portfolio/"},
        {"method": "GET", "endpoint": "/api/alerts/"},
        {"method": "GET", "endpoint": "/api/symbols/tracked"},
        {"method": "GET", "endpoint": "/api/v2/performance/summary"},
        {"method": "GET", "endpoint": "/api/v2/performance/health"},
        {"method": "GET", "endpoint": "/api/v2/performance/cache-stats"},
        {
            "method": "POST", 
            "endpoint": "/api/portfolio/",
            "data": {
                "symbol": "BTC",
                "amount": 1.0,
                "price_buy": 50000.0,
                "base_currency": "USD",
                "commission": 0.0
            }
        }
    ]
    
    print(f"Starting load test with {concurrency} concurrent connections...")
    print(f"Total requests: {num_requests * len(endpoint_configs)}")
    
    # Generate test requests
    requests = tester.generate_test_requests(endpoint_configs, num_requests)
    
    # Run the test
    start_time = time.time()
    await tester.run_concurrent_requests(requests, concurrency)
    end_time = time.time()
    
    # Calculate and print results
    stats = tester.calculate_statistics()
    stats["total_time"] = end_time - start_time
    tester.print_results(stats)
    
    return stats


async def run_stress_test(base_url: str, max_concurrency: int = 100):
    """Run stress test to find breaking point"""
    print(f"\nStarting stress test (max concurrency: {max_concurrency})...")
    
    concurrency_levels = [1, 5, 10, 20, 50, 100]
    results = []
    
    for concurrency in concurrency_levels:
        if concurrency > max_concurrency:
            break
            
        print(f"\nTesting with {concurrency} concurrent connections...")
        tester = LoadTester(base_url)
        
        # Simple health check requests
        endpoint_configs = [{"method": "GET", "endpoint": "/health"}]
        requests = tester.generate_test_requests(endpoint_configs, 10)
        
        await tester.run_concurrent_requests(requests, concurrency)
        stats = tester.calculate_statistics()
        
        results.append({
            "concurrency": concurrency,
            "success_rate": stats["success_rate"],
            "avg_response_time": stats["response_times"]["mean"],
            "requests_per_second": stats["requests_per_second"]
        })
        
        print(f"  Success Rate: {stats['success_rate']:.2f}%")
        print(f"  Avg Response Time: {stats['response_times']['mean']:.3f}s")
        print(f"  Requests/sec: {stats['requests_per_second']:.2f}")
    
    # Find breaking point
    breaking_point = None
    for result in results:
        if result["success_rate"] < 95:  # Less than 95% success rate
            breaking_point = result["concurrency"]
            break
    
    print(f"\nStress Test Results:")
    print(f"Breaking point: {breaking_point} concurrent connections")
    
    return results


def main():
    """Main function to run load tests"""
    parser = argparse.ArgumentParser(description="Load test Crypto AI Agent API")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of the API")
    parser.add_argument("--concurrency", type=int, default=10, help="Number of concurrent connections")
    parser.add_argument("--requests", type=int, default=100, help="Number of requests per endpoint")
    parser.add_argument("--stress-test", action="store_true", help="Run stress test")
    
    args = parser.parse_args()
    
    if args.stress_test:
        asyncio.run(run_stress_test(args.url, args.concurrency))
    else:
        asyncio.run(run_load_test(args.url, args.concurrency, args.requests))


if __name__ == "__main__":
    main()
