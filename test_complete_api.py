#!/usr/bin/env python3
"""
Test script for the complete Bitget API with FastAPI + Lambda + API Gateway
"""
import requests
import json
import time
import sys

def test_api_endpoint(base_url: str):
    """Test all API endpoints"""
    
    print(f"🚀 Testing Complete Bitget API")
    print(f"Base URL: {base_url}")
    print("=" * 60)
    
    # Test 1: Health Check
    print("🧪 Test 1: Health Check")
    print("-" * 30)
    try:
        response = requests.get(f"{base_url}/health")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Service: {data.get('service')}")
            print(f"✅ Version: {data.get('version')}")
            print(f"✅ Step Function configured: {data.get('step_function_configured')}")
        else:
            print(f"❌ Health check failed: {response.text}")
    except Exception as e:
        print(f"❌ Health check error: {e}")
    
    print()
    
    # Test 2: Get Symbols
    print("🧪 Test 2: Get Available Symbols")
    print("-" * 30)
    try:
        response = requests.get(f"{base_url}/get-symbols")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            symbols = data.get('symbols', [])
            print(f"✅ Found {len(symbols)} symbols")
            if symbols:
                print(f"Sample symbols: {symbols[:5]}")
        else:
            print(f"❌ Get symbols failed: {response.text}")
    except Exception as e:
        print(f"❌ Get symbols error: {e}")
    
    print()
    
    # Test 3: Extract Single Symbol
    print("🧪 Test 3: Extract Single Symbol (BTCUSDT)")
    print("-" * 30)
    try:
        payload = {"symbol": "BTCUSDT"}
        response = requests.post(
            f"{base_url}/extract-single-symbol",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Status: {data.get('status')}")
            print(f"✅ Message: {data.get('message')}")
            if 'data' in data and 'orders_count' in data['data']:
                print(f"✅ Orders found: {data['data']['orders_count']}")
        else:
            print(f"❌ Single symbol extraction failed: {response.text}")
    except Exception as e:
        print(f"❌ Single symbol error: {e}")
    
    print()
    
    # Test 4: Extract Multiple Symbols (Step Function)
    print("🧪 Test 4: Extract Multiple Symbols (Step Function)")
    print("-" * 30)
    try:
        payload = {
            "symbols": ["BTCUSDT", "ETHUSDT", "ADAUSDT"],
            "test_mode": False
        }
        response = requests.post(
            f"{base_url}/extract-orders",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Status: {data.get('status')}")
            print(f"✅ Message: {data.get('message')}")
            execution_arn = data.get('execution_arn')
            if execution_arn:
                print(f"✅ Execution ARN: {execution_arn}")
                
                # Wait a bit and check execution status
                print("⏳ Waiting 10 seconds to check execution status...")
                time.sleep(10)
                
                # Convert ARN for URL (replace : with _)
                execution_arn_path = execution_arn.replace(":", "_")
                status_response = requests.get(f"{base_url}/execution-status/{execution_arn_path}")
                
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    print(f"📊 Execution Status: {status_data.get('status')}")
                    if 'summary' in status_data:
                        summary = status_data['summary']
                        print(f"📊 Total Orders: {summary.get('total_orders', 0)}")
                        print(f"📊 Symbols Processed: {summary.get('symbols_processed', 0)}")
        else:
            print(f"❌ Multiple symbols extraction failed: {response.text}")
    except Exception as e:
        print(f"❌ Multiple symbols error: {e}")
    
    print()
    
    # Test 5: List Recent Executions
    print("🧪 Test 5: List Recent Executions")
    print("-" * 30)
    try:
        response = requests.get(f"{base_url}/list-executions")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            executions = data.get('executions', [])
            print(f"✅ Found {len(executions)} recent executions")
            for i, execution in enumerate(executions[:3]):
                print(f"  {i+1}. {execution.get('name')} - {execution.get('status')}")
        else:
            print(f"❌ List executions failed: {response.text}")
    except Exception as e:
        print(f"❌ List executions error: {e}")
    
    print()
    print("🎉 API Testing Completed!")
    print()
    print("🔗 Useful URLs:")
    print(f"• Landing Page: {base_url}")
    print(f"• API Documentation: {base_url}/docs")
    print(f"• Health Check: {base_url}/health")
    print(f"• Get Symbols: {base_url}/get-symbols")

def main():
    """Main function"""
    if len(sys.argv) > 1:
        base_url = sys.argv[1].rstrip('/')
    else:
        print("Usage: python test_complete_api.py <API_GATEWAY_URL>")
        print("Example: python test_complete_api.py https://abc123.execute-api.us-east-1.amazonaws.com/Prod")
        return
    
    test_api_endpoint(base_url)

if __name__ == "__main__":
    main()