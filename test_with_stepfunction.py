#!/usr/bin/env python3
"""
Test del servicio con ARN de Step Function
"""
import requests
import json

# ARN de ejemplo (reemplaza con el real después del despliegue)
STEP_FUNCTION_ARN = "arn:aws:states:us-east-1:123456789012:stateMachine:bitget-order-extraction"

def test_extract_orders_with_arn():
    """Test del endpoint principal con ARN de Step Function"""
    
    url = "http://localhost:8000/extract-orders"
    
    payload = {
        "step_function_arn": STEP_FUNCTION_ARN,
        "test_mode": True
    }
    
    print(f"🚀 Testing extract-orders with Step Function ARN...")
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print("-" * 50)
    
    try:
        response = requests.post(url, json=payload)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Body:")
        print(json.dumps(response.json(), indent=2))
        
        if response.status_code == 200:
            print("✅ Request successful!")
        else:
            print("❌ Request failed!")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def test_without_arn():
    """Test sin ARN (solo coordinador local)"""
    
    url = "http://localhost:8000/extract-orders"
    
    payload = {
        "test_mode": True
        # No incluimos step_function_arn
    }
    
    print(f"\n🧪 Testing extract-orders without Step Function ARN...")
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print("-" * 50)
    
    try:
        response = requests.post(url, json=payload)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Body:")
        print(json.dumps(response.json(), indent=2))
        
        if response.status_code == 200:
            print("✅ Request successful!")
        else:
            print("❌ Request failed!")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("🔍 Testing Step Function Integration")
    print("=" * 60)
    
    # Test 1: Con ARN simulado
    test_extract_orders_with_arn()
    
    # Test 2: Sin ARN
    test_without_arn()
    
    print("\n💡 NOTA:")
    print("Para obtener el ARN real después del despliegue:")
    print("aws stepfunctions list-state-machines --query 'stateMachines[?name==`bitget-order-extraction`].stateMachineArn' --output text")