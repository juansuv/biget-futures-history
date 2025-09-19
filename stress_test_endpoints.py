#!/usr/bin/env python3
"""
Stress test para los endpoints de Bitget
Realiza múltiples llamadas concurrentes para probar rendimiento y estabilidad
"""
import asyncio
import aiohttp
import json
import time
import statistics
from datetime import datetime
from typing import List, Dict, Optional
import argparse

BASE_URL = "http://localhost:8000"

class StressTestResults:
    def __init__(self):
        self.results = []
        self.start_time = None
        self.end_time = None
    
    def add_result(self, result: Dict):
        self.results.append(result)
    
    def get_summary(self) -> Dict:
        if not self.results:
            return {"error": "No results to analyze"}
        
        # Status analysis
        successful = [r for r in self.results if r.get("status") == 200]
        failed = [r for r in self.results if r.get("status") != 200]
        
        # Timing analysis
        durations = [r.get("duration", 0) for r in self.results if r.get("duration")]
        
        # Error analysis
        errors = {}
        for r in failed:
            error_key = f"Status {r.get('status', 'Unknown')}"
            errors[error_key] = errors.get(error_key, 0) + 1
        
        total_duration = self.end_time - self.start_time if self.start_time and self.end_time else 0
        
        return {
            "total_requests": len(self.results),
            "successful_requests": len(successful),
            "failed_requests": len(failed),
            "success_rate": (len(successful) / len(self.results)) * 100,
            "total_test_duration": total_duration,
            "requests_per_second": len(self.results) / total_duration if total_duration > 0 else 0,
            "response_times": {
                "avg": statistics.mean(durations) if durations else 0,
                "median": statistics.median(durations) if durations else 0,
                "min": min(durations) if durations else 0,
                "max": max(durations) if durations else 0,
                "p95": self._percentile(durations, 95) if durations else 0,
                "p99": self._percentile(durations, 99) if durations else 0
            },
            "errors": errors,
            "start_time": self.start_time,
            "end_time": self.end_time
        }
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]

class BitgetStressTest:
    def __init__(self, base_url: str = BASE_URL, max_concurrent: int = 10):
        self.base_url = base_url
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.session = None
    
    async def __aenter__(self):
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=50)
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def make_request(self, endpoint: str, method: str = "GET", payload: Optional[Dict] = None, request_id: int = 0) -> Dict:
        """Make a single HTTP request with timing and error handling"""
        async with self.semaphore:
            start_time = time.time()
            
            try:
                url = f"{self.base_url}{endpoint}"
                
                if method.upper() == "POST":
                    async with self.session.post(url, json=payload) as response:
                        result = await self._process_response(response, start_time, request_id, endpoint)
                else:
                    async with self.session.get(url) as response:
                        result = await self._process_response(response, start_time, request_id, endpoint)
                
                return result
                
            except asyncio.TimeoutError:
                return {
                    "request_id": request_id,
                    "endpoint": endpoint,
                    "status": 0,
                    "error": "Request timeout",
                    "duration": time.time() - start_time,
                    "timestamp": datetime.now().isoformat()
                }
            except Exception as e:
                return {
                    "request_id": request_id,
                    "endpoint": endpoint,
                    "status": 0,
                    "error": str(e),
                    "duration": time.time() - start_time,
                    "timestamp": datetime.now().isoformat()
                }
    
    async def _process_response(self, response, start_time: float, request_id: int, endpoint: str) -> Dict:
        """Process HTTP response and extract relevant data"""
        duration = time.time() - start_time
        
        try:
            if response.status == 200:
                data = await response.json()
                return {
                    "request_id": request_id,
                    "endpoint": endpoint,
                    "status": response.status,
                    "duration": duration,
                    "data_size": len(json.dumps(data)) if data else 0,
                    "success": True,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                error_text = await response.text()
                return {
                    "request_id": request_id,
                    "endpoint": endpoint,
                    "status": response.status,
                    "duration": duration,
                    "error": error_text[:200],  # Limit error message length
                    "success": False,
                    "timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            return {
                "request_id": request_id,
                "endpoint": endpoint,
                "status": response.status,
                "duration": duration,
                "error": f"Response processing error: {str(e)}",
                "success": False,
                "timestamp": datetime.now().isoformat()
            }

    async def stress_test_endpoint(self, endpoint: str, num_requests: int, method: str = "GET", payload: Optional[Dict] = None) -> StressTestResults:
        """Stress test a single endpoint"""
        print(f"🚀 Starting stress test: {endpoint}")
        print(f"   Requests: {num_requests}")
        print(f"   Method: {method}")
        print(f"   Max concurrent: {self.max_concurrent}")
        
        results = StressTestResults()
        results.start_time = time.time()
        
        # Create tasks for concurrent requests
        tasks = []
        for i in range(num_requests):
            task = self.make_request(endpoint, method, payload, i)
            tasks.append(task)
        
        # Execute all requests concurrently with progress updates
        completed = 0
        batch_size = min(50, num_requests)  # Process in batches for progress updates
        
        for i in range(0, num_requests, batch_size):
            batch = tasks[i:i + batch_size]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, Exception):
                    results.add_result({
                        "request_id": completed,
                        "endpoint": endpoint,
                        "status": 0,
                        "error": str(result),
                        "duration": 0,
                        "success": False,
                        "timestamp": datetime.now().isoformat()
                    })
                else:
                    results.add_result(result)
                completed += 1
            
            # Progress update
            progress = (completed / num_requests) * 100
            print(f"   Progress: {completed}/{num_requests} ({progress:.1f}%)")
        
        results.end_time = time.time()
        
        print(f"✅ Completed stress test: {endpoint}")
        return results

async def run_comprehensive_stress_test(num_requests_per_endpoint: int = 50, max_concurrent: int = 10):
    """Run stress tests on all endpoints"""
    print("🔥 BITGET API STRESS TEST")
    print("=" * 60)
    print(f"Requests per endpoint: {num_requests_per_endpoint}")
    print(f"Max concurrent requests: {max_concurrent}")
    print(f"Started at: {datetime.now().isoformat()}")
    print()
    
    # Define endpoints to test
    endpoints = [
        {"path": "/health", "method": "GET", "name": "Health Check"},
        {"path": "/test/coordinator", "method": "POST", "name": "Coordinator Test"},
        {"path": "/test/symbol-processor?symbol=BTCUSDT", "method": "POST", "name": "Symbol Processor Test"},
        {"path": "/test/result-collector", "method": "POST", "name": "Result Collector Test"},
        {"path": "/extract-orders", "method": "POST", "payload": {"test_mode": True}, "name": "Extract Orders (Test Mode)"}
    ]
    
    all_results = {}
    overall_stats = {
        "total_requests": 0,
        "total_successful": 0,
        "total_failed": 0,
        "start_time": time.time()
    }
    
    async with BitgetStressTest(max_concurrent=max_concurrent) as stress_tester:
        # First check if server is running
        health_check = await stress_tester.make_request("/health")
        if health_check.get("status") != 200:
            print("❌ Server is not running!")
            print("   Start the server with: python main.py")
            return
        
        print("✅ Server is running, starting stress tests...\n")
        
        for i, endpoint_config in enumerate(endpoints, 1):
            print(f"📊 Test {i}/{len(endpoints)}: {endpoint_config['name']}")
            print("-" * 40)
            
            results = await stress_tester.stress_test_endpoint(
                endpoint=endpoint_config["path"],
                num_requests=num_requests_per_endpoint,
                method=endpoint_config["method"],
                payload=endpoint_config.get("payload")
            )
            
            summary = results.get_summary()
            all_results[endpoint_config["name"]] = summary
            
            # Update overall stats
            overall_stats["total_requests"] += summary["total_requests"]
            overall_stats["total_successful"] += summary["successful_requests"]
            overall_stats["total_failed"] += summary["failed_requests"]
            
            # Print summary for this endpoint
            print(f"   Results: {summary['successful_requests']}/{summary['total_requests']} successful ({summary['success_rate']:.1f}%)")
            print(f"   Avg response time: {summary['response_times']['avg']:.3f}s")
            print(f"   Max response time: {summary['response_times']['max']:.3f}s")
            print(f"   Requests/second: {summary['requests_per_second']:.2f}")
            
            if summary["errors"]:
                print(f"   Errors: {summary['errors']}")
            
            print()
            
            # Small delay between endpoint tests
            if i < len(endpoints):
                await asyncio.sleep(1)
    
    overall_stats["end_time"] = time.time()
    overall_stats["total_duration"] = overall_stats["end_time"] - overall_stats["start_time"]
    overall_stats["overall_success_rate"] = (overall_stats["total_successful"] / overall_stats["total_requests"]) * 100
    overall_stats["overall_rps"] = overall_stats["total_requests"] / overall_stats["total_duration"]
    
    # Print final summary
    print("=" * 60)
    print("📈 FINAL STRESS TEST SUMMARY")
    print("=" * 60)
    print(f"Total requests: {overall_stats['total_requests']}")
    print(f"Successful: {overall_stats['total_successful']} ✅")
    print(f"Failed: {overall_stats['total_failed']} ❌")
    print(f"Overall success rate: {overall_stats['overall_success_rate']:.1f}%")
    print(f"Total duration: {overall_stats['total_duration']:.2f}s")
    print(f"Overall requests/second: {overall_stats['overall_rps']:.2f}")
    print()
    
    # Endpoint-by-endpoint summary
    print("📊 By Endpoint:")
    print("-" * 40)
    for name, summary in all_results.items():
        print(f"{name}:")
        print(f"  Success rate: {summary['success_rate']:.1f}%")
        print(f"  Avg response: {summary['response_times']['avg']:.3f}s")
        print(f"  P95 response: {summary['response_times']['p95']:.3f}s")
        print(f"  RPS: {summary['requests_per_second']:.2f}")
        if summary["errors"]:
            print(f"  Errors: {list(summary['errors'].keys())}")
        print()
    
    # Save detailed results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"stress_test_results_{timestamp}.json"
    
    final_report = {
        "test_config": {
            "requests_per_endpoint": num_requests_per_endpoint,
            "max_concurrent": max_concurrent,
            "endpoints_tested": len(endpoints)
        },
        "overall_stats": overall_stats,
        "endpoint_results": all_results,
        "timestamp": datetime.now().isoformat()
    }
    
    with open(results_file, 'w') as f:
        json.dump(final_report, f, indent=2)
    
    print(f"💾 Detailed results saved to: {results_file}")
    
    # Performance recommendations
    print("\n💡 RECOMMENDATIONS:")
    if overall_stats['overall_success_rate'] < 95:
        print("   ⚠️  Consider investigating failed requests")
    if overall_stats['overall_rps'] < 10:
        print("   ⚠️  Server performance might need optimization")
    
    fastest_endpoint = min(all_results.items(), key=lambda x: x[1]['response_times']['avg'])
    slowest_endpoint = max(all_results.items(), key=lambda x: x[1]['response_times']['avg'])
    
    print(f"   🚀 Fastest endpoint: {fastest_endpoint[0]} ({fastest_endpoint[1]['response_times']['avg']:.3f}s avg)")
    print(f"   🐌 Slowest endpoint: {slowest_endpoint[0]} ({slowest_endpoint[1]['response_times']['avg']:.3f}s avg)")

async def main():
    """Main function with command line arguments"""
    parser = argparse.ArgumentParser(description="Stress test Bitget FastAPI endpoints")
    parser.add_argument("--requests", "-r", type=int, default=50, help="Number of requests per endpoint (default: 50)")
    parser.add_argument("--concurrent", "-c", type=int, default=10, help="Max concurrent requests (default: 10)")
    
    args = parser.parse_args()
    
    try:
        await run_comprehensive_stress_test(
            num_requests_per_endpoint=args.requests,
            max_concurrent=args.concurrent
        )
    except KeyboardInterrupt:
        print("\n\n⏹️  Stress test interrupted by user")
    except Exception as e:
        print(f"\n❌ Stress test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())