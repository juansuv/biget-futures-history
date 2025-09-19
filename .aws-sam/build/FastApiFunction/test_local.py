#!/usr/bin/env python3
"""
Script para probar localmente la solución de Bitget
"""
import json
import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.lambdas.coordinator.handler import lambda_handler as coordinator_handler
from src.lambdas.symbol_processor.handler import lambda_handler as symbol_processor_handler
from src.lambdas.result_collector.handler import lambda_handler as result_collector_handler

def test_coordinator():
    """Test the coordinator Lambda"""
    print("🧪 Testing Coordinator Lambda...")
    
    event = {"test_mode": True}
    result = coordinator_handler(event, None)
    
    print(f"Status Code: {result['statusCode']}")
    body = json.loads(result['body'])
    print(f"Message: {body['message']}")
    
    if 'symbols' in body:
        print(f"Symbols found: {len(body['symbols'])}")
        if body['symbols']:
            print(f"Sample symbols: {body['symbols'][:5]}")
    
    return result

def test_symbol_processor(symbol="BTCUSDT"):
    """Test the symbol processor Lambda"""
    print(f"\n🧪 Testing Symbol Processor Lambda with symbol: {symbol}")
    
    event = {"symbol": symbol}
    result = symbol_processor_handler(event, None)
    
    print(f"Status Code: {result['statusCode']}")
    print(f"Symbol: {result.get('symbol', 'N/A')}")
    print(f"Orders Count: {result.get('orders_count', 0)}")
    
    if result.get('orders'):
        print("Sample order:")
        sample_order = result['orders'][0]
        print(f"  Order ID: {sample_order.get('orderId', 'N/A')}")
        print(f"  Side: {sample_order.get('side', 'N/A')}")
        print(f"  Size: {sample_order.get('size', 'N/A')}")
        print(f"  Price: {sample_order.get('price', 'N/A')}")
    
    return result

def test_result_collector(mock_results=None):
    """Test the result collector Lambda"""
    print("\n🧪 Testing Result Collector Lambda...")
    
    if mock_results is None:
        # Create mock results
        mock_results = [
            {
                "Payload": {
                    "statusCode": 200,
                    "symbol": "BTCUSDT",
                    "orders_count": 3,
                    "orders": [
                        {
                            "orderId": "test123",
                            "symbol": "BTCUSDT",
                            "size": "0.1",
                            "price": "50000",
                            "side": "buy",
                            "createTime": "1640995200000",
                            "orderType": "limit"
                        },
                        {
                            "orderId": "test124",
                            "symbol": "BTCUSDT",
                            "size": "0.2",
                            "price": "51000",
                            "side": "sell",
                            "createTime": "1640995260000",
                            "orderType": "market"
                        }
                    ],
                    "processed_at": 1640995200000
                }
            },
            {
                "Payload": {
                    "statusCode": 200,
                    "symbol": "ETHUSDT",
                    "orders_count": 1,
                    "orders": [
                        {
                            "orderId": "test125",
                            "symbol": "ETHUSDT",
                            "size": "1.0",
                            "price": "4000",
                            "side": "buy",
                            "createTime": "1640995320000",
                            "orderType": "limit"
                        }
                    ],
                    "processed_at": 1640995300000
                }
            }
        ]
    
    event = {"parallel_results": mock_results}
    result = result_collector_handler(event, None)
    
    print(f"Status Code: {result['statusCode']}")
    
    if result['statusCode'] == 200:
        body = json.loads(result['body'])
        print(f"Message: {body['message']}")
        print(f"Total Orders: {body['total_orders']}")
        print(f"Symbols Processed: {body['symbols_processed']}")
        print(f"Date Range: {body['date_range']['total_days']} days")
        
        if body.get('orders'):
            print("\nSample combined orders:")
            for i, order in enumerate(body['orders'][:3]):
                print(f"  {i+1}. {order.get('symbol')} - {order.get('side')} {order.get('size')} @ {order.get('price')}")
    
    return result

def main():
    """Run all tests"""
    print("🚀 Starting Bitget Local Tests...\n")
    
    try:
        # Test 1: Coordinator
        coordinator_result = test_coordinator()
        
        # Test 2: Symbol Processor
        symbol_result = test_symbol_processor()
        
        # Test 3: Result Collector with mock data
        collector_result = test_result_collector()
        
        # Test 4: End-to-end simulation if coordinator found symbols
        if coordinator_result['statusCode'] == 200:
            coordinator_body = json.loads(coordinator_result['body'])
            if coordinator_body.get('symbols'):
                print("\n🔄 Running end-to-end simulation...")
                
                # Process first few symbols
                symbols_to_test = coordinator_body['symbols'][:2]  # Test first 2 symbols
                parallel_results = []
                
                for symbol in symbols_to_test:
                    print(f"Processing {symbol}...")
                    result = test_symbol_processor(symbol)
                    parallel_results.append({"Payload": result})
                
                # Collect results
                final_result = test_result_collector(parallel_results)
                
                if final_result['statusCode'] == 200:
                    final_body = json.loads(final_result['body'])
                    print(f"\n✅ End-to-end test completed!")
                    print(f"   Total orders extracted: {final_body['total_orders']}")
                    print(f"   Symbols processed: {final_body['symbols_processed']}")
        
        print("\n✅ All tests completed!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()