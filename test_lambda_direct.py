#!/usr/bin/env python3
"""
Test directo de las funciones Lambda sin AWS
"""
import sys
import os

# Add lambda directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src/lambdas/coordinator'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'src/lambdas/symbol_processor'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'src/lambdas/result_collector'))

# Import handlers
from src.lambdas.coordinator.handler import lambda_handler as coordinator_handler
from src.lambdas.symbol_processor.handler import lambda_handler as symbol_processor_handler
from src.lambdas.result_collector.handler import lambda_handler as result_collector_handler

def test_coordinator():
    """Test coordinator function"""
    print("🧪 Testing Coordinator Lambda...")
    
    event = {"test_mode": True}
    try:
        result = coordinator_handler(event, None)
        print(f"✅ Coordinator Status: {result.get('statusCode')}")
        if result.get('statusCode') == 200:
            import json
            body = json.loads(result['body'])
            print(f"   Message: {body.get('message')}")
            print(f"   Symbols found: {len(body.get('symbols', []))}")
        return result
    except Exception as e:
        print(f"❌ Coordinator Error: {e}")
        return None

def test_symbol_processor():
    """Test symbol processor function"""
    print("\n🧪 Testing Symbol Processor Lambda...")
    
    event = {"symbol": "BTCUSDT"}
    try:
        result = symbol_processor_handler(event, None)
        print(f"✅ Symbol Processor Status: {result.get('statusCode')}")
        print(f"   Symbol: {result.get('symbol')}")
        print(f"   Orders found: {result.get('orders_count', 0)}")
        return result
    except Exception as e:
        print(f"❌ Symbol Processor Error: {e}")
        return None

def test_result_collector():
    """Test result collector function"""
    print("\n🧪 Testing Result Collector Lambda...")
    
    # Mock parallel results
    mock_results = [
        {
            "Payload": {
                "statusCode": 200,
                "symbol": "BTCUSDT",
                "orders_count": 5,
                "orders": [
                    {
                        "orderId": "test123",
                        "symbol": "BTCUSDT",
                        "size": "0.1",
                        "price": "50000",
                        "side": "buy",
                        "createTime": "1640995200000"
                    }
                ],
                "processed_at": 1640995200000
            }
        }
    ]
    
    event = {"parallel_results": mock_results}
    try:
        result = result_collector_handler(event, None)
        print(f"✅ Result Collector Status: {result.get('statusCode')}")
        if result.get('statusCode') == 200:
            import json
            body = json.loads(result['body'])
            print(f"   Total orders: {body.get('total_orders', 0)}")
            print(f"   Symbols processed: {body.get('symbols_processed', 0)}")
        return result
    except Exception as e:
        print(f"❌ Result Collector Error: {e}")
        return None

def simulate_step_function_flow():
    """Simulate the complete Step Function flow"""
    print("\n🔄 Simulating Complete Step Function Flow...")
    print("=" * 50)
    
    # Step 1: Coordinator gets symbols
    coordinator_result = test_coordinator()
    if not coordinator_result or coordinator_result.get('statusCode') != 200:
        print("❌ Coordinator failed, cannot continue flow")
        return
    
    import json
    coordinator_body = json.loads(coordinator_result['body'])
    symbols = coordinator_body.get('symbols', ['BTCUSDT', 'ETHUSDT'])  # Fallback symbols
    
    if not symbols:
        symbols = ['BTCUSDT', 'ETHUSDT']  # Use default symbols for testing
        print(f"⚠️  No symbols from coordinator, using default: {symbols}")
    
    print(f"\n📋 Processing {len(symbols)} symbols: {symbols}")
    
    # Step 2: Process each symbol (simulate Map state)
    parallel_results = []
    for symbol in symbols[:2]:  # Limit to 2 for testing
        print(f"\n   Processing {symbol}...")
        event = {"symbol": symbol}
        result = symbol_processor_handler(event, None)
        
        if result and result.get('statusCode') == 200:
            parallel_results.append({"Payload": result})
            print(f"   ✅ {symbol}: {result.get('orders_count', 0)} orders")
        else:
            print(f"   ❌ {symbol}: Failed")
    
    # Step 3: Collect results
    if parallel_results:
        print(f"\n📊 Collecting {len(parallel_results)} results...")
        event = {"parallel_results": parallel_results}
        final_result = result_collector_handler(event, None)
        
        if final_result and final_result.get('statusCode') == 200:
            body = json.loads(final_result['body'])
            print(f"✅ Flow Complete!")
            print(f"   Total orders: {body.get('total_orders', 0)}")
            print(f"   Symbols processed: {body.get('symbols_processed', 0)}")
            print(f"   Success rate: {(body.get('symbols_processed', 0) / len(symbols)) * 100:.1f}%")
        else:
            print("❌ Result collection failed")
    else:
        print("❌ No results to collect")

def main():
    """Main test function"""
    print("🚀 Direct Lambda Function Tests")
    print("=" * 50)
    
    # Individual tests
    test_coordinator()
    test_symbol_processor() 
    test_result_collector()
    
    # Complete flow simulation
    simulate_step_function_flow()
    
    print("\n✅ All tests completed!")
    print("\n💡 Next steps:")
    print("   1. Deploy with: ./deploy_minimal.sh")
    print("   2. Test on AWS with the ARNs provided")

if __name__ == "__main__":
    main()