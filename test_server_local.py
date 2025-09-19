#!/usr/bin/env python3
"""
Test server para probar el servicio FastAPI localmente
Simula múltiples llamadas al endpoint de transacciones
"""
import asyncio
import aiohttp
import json
import time
from datetime import datetime
from typing import List, Dict

BASE_URL = "http://localhost:8000"

class BitgetTestClient:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def health_check(self) -> Dict:
        """Check if the server is running"""
        try:
            async with self.session.get(f"{self.base_url}/health") as response:
                return {
                    "status": response.status,
                    "data": await response.json() if response.status == 200 else None,
                    "error": None
                }
        except Exception as e:
            return {"status": 0, "data": None, "error": str(e)}
    
    async def extract_orders(self, test_mode: bool = True) -> Dict:
        """Call the extract orders endpoint"""
        try:
            payload = {"test_mode": test_mode}
            async with self.session.post(
                f"{self.base_url}/extract-orders",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                return {
                    "status": response.status,
                    "data": await response.json() if response.status in [200, 422] else None,
                    "error": await response.text() if response.status >= 400 else None,
                    "timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            return {
                "status": 0,
                "data": None,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def test_coordinator(self) -> Dict:
        """Test the coordinator endpoint"""
        try:
            async with self.session.post(f"{self.base_url}/test/coordinator") as response:
                return {
                    "status": response.status,
                    "data": await response.json() if response.status == 200 else None,
                    "error": await response.text() if response.status >= 400 else None
                }
        except Exception as e:
            return {"status": 0, "data": None, "error": str(e)}
    
    async def test_symbol_processor(self, symbol: str = "BTCUSDT") -> Dict:
        """Test the symbol processor endpoint"""
        try:
            async with self.session.post(
                f"{self.base_url}/test/symbol-processor?symbol={symbol}"
            ) as response:
                return {
                    "status": response.status,
                    "data": await response.json() if response.status == 200 else None,
                    "error": await response.text() if response.status >= 400 else None
                }
        except Exception as e:
            return {"status": 0, "data": None, "error": str(e)}
    
    async def test_result_collector(self) -> Dict:
        """Test the result collector endpoint"""
        try:
            async with self.session.post(f"{self.base_url}/test/result-collector") as response:
                return {
                    "status": response.status,
                    "data": await response.json() if response.status == 200 else None,
                    "error": await response.text() if response.status >= 400 else None
                }
        except Exception as e:
            return {"status": 0, "data": None, "error": str(e)}

async def run_single_test(client: BitgetTestClient, test_name: str, test_num: int) -> Dict:
    """Run a single test"""
    print(f"🧪 Test {test_num}: {test_name}")
    start_time = time.time()
    
    if test_name == "health":
        result = await client.health_check()
    elif test_name == "extract_orders":
        result = await client.extract_orders()
    elif test_name == "coordinator":
        result = await client.test_coordinator()
    elif test_name == "symbol_processor":
        result = await client.test_symbol_processor()
    elif test_name == "result_collector":
        result = await client.test_result_collector()
    else:
        result = {"status": 0, "error": f"Unknown test: {test_name}"}
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Add timing info
    result["duration_seconds"] = round(duration, 3)
    result["test_name"] = test_name
    result["test_number"] = test_num
    
    # Print result summary
    status_emoji = "✅" if result["status"] == 200 else "❌"
    print(f"   {status_emoji} Status: {result['status']} | Duration: {duration:.3f}s")
    
    if result.get("error"):
        print(f"   Error: {result['error']}")
    elif result.get("data") and isinstance(result["data"], dict):
        if "message" in result["data"]:
            print(f"   Message: {result['data']['message']}")
    
    return result

async def run_cycle_tests(cycles: int = 3, delay_seconds: int = 2):
    """Run multiple cycles of tests"""
    print(f"🚀 Starting {cycles} cycles of Bitget API tests")
    print(f"⏱️  Delay between calls: {delay_seconds} seconds")
    print("=" * 60)
    
    all_results = []
    
    async with BitgetTestClient() as client:
        # First check if server is running
        health = await client.health_check()
        if health["status"] != 200:
            print("❌ Server is not running!")
            print(f"   Start with: python main.py")
            return
        
        print("✅ Server is running")
        print()
        
        # Define test sequence
        tests = [
            "health",
            "coordinator", 
            "extract_orders",
            "symbol_processor",
            "result_collector"
        ]
        
        for cycle in range(1, cycles + 1):
            print(f"📋 CYCLE {cycle}/{cycles}")
            print("-" * 40)
            
            cycle_results = []
            
            for i, test in enumerate(tests, 1):
                result = await run_single_test(client, test, i)
                cycle_results.append(result)
                all_results.append(result)
                
                # Add delay between calls (except last one)
                if i < len(tests):
                    print(f"   ⏳ Waiting {delay_seconds}s...")
                    await asyncio.sleep(delay_seconds)
            
            # Summary for this cycle
            successful = sum(1 for r in cycle_results if r["status"] == 200)
            print(f"📊 Cycle {cycle} Summary: {successful}/{len(tests)} successful")
            
            # Delay between cycles
            if cycle < cycles:
                print(f"\n⏸️  Pausing {delay_seconds * 2}s before next cycle...\n")
                await asyncio.sleep(delay_seconds * 2)
    
    # Final summary
    print("\n" + "=" * 60)
    print("📈 FINAL SUMMARY")
    print("=" * 60)
    
    total_tests = len(all_results)
    successful_tests = sum(1 for r in all_results if r["status"] == 200)
    failed_tests = total_tests - successful_tests
    
    print(f"Total tests run: {total_tests}")
    print(f"Successful: {successful_tests} ✅")
    print(f"Failed: {failed_tests} ❌")
    print(f"Success rate: {(successful_tests/total_tests)*100:.1f}%")
    
    # Performance stats
    durations = [r["duration_seconds"] for r in all_results if "duration_seconds" in r]
    if durations:
        avg_duration = sum(durations) / len(durations)
        max_duration = max(durations)
        min_duration = min(durations)
        
        print(f"\nPerformance:")
        print(f"Average response time: {avg_duration:.3f}s")
        print(f"Fastest response: {min_duration:.3f}s")
        print(f"Slowest response: {max_duration:.3f}s")
    
    # Test-specific summary
    test_summary = {}
    for result in all_results:
        test_name = result.get("test_name", "unknown")
        if test_name not in test_summary:
            test_summary[test_name] = {"success": 0, "total": 0}
        test_summary[test_name]["total"] += 1
        if result["status"] == 200:
            test_summary[test_name]["success"] += 1
    
    print(f"\nBy endpoint:")
    for test_name, stats in test_summary.items():
        success_rate = (stats["success"] / stats["total"]) * 100
        print(f"  {test_name}: {stats['success']}/{stats['total']} ({success_rate:.1f}%)")
    
    # Save results to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"test_results_{timestamp}.json"
    
    with open(results_file, 'w') as f:
        json.dump({
            "summary": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "failed_tests": failed_tests,
                "success_rate": (successful_tests/total_tests)*100,
                "avg_duration": avg_duration if durations else 0,
                "test_summary": test_summary
            },
            "all_results": all_results
        }, f, indent=2)
    
    print(f"\n💾 Results saved to: {results_file}")

async def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Bitget FastAPI service locally")
    parser.add_argument("--cycles", "-c", type=int, default=3, help="Number of test cycles (default: 3)")
    parser.add_argument("--delay", "-d", type=int, default=2, help="Delay between calls in seconds (default: 2)")
    
    args = parser.parse_args()
    
    try:
        await run_cycle_tests(cycles=args.cycles, delay_seconds=args.delay)
    except KeyboardInterrupt:
        print("\n\n⏹️  Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())