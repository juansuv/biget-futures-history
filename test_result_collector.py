#!/usr/bin/env python3
"""
Test script para ejecutar el Result Collector directamente
"""
import boto3
import json

def test_result_collector():
    """Test directo del Result Collector"""
    
    # Obtener ARN de la función
    lambda_client = boto3.client('lambda')
    
    try:
        # Buscar la función Result Collector
        functions = lambda_client.list_functions()
        result_collector_arn = None
        
        for func in functions['Functions']:
            if 'result-collector' in func['FunctionName'].lower():
                result_collector_arn = func['FunctionArn']
                print(f"✅ Found Result Collector: {func['FunctionName']}")
                break
        
        if not result_collector_arn:
            print("❌ Result Collector function not found")
            return
        
        # Payload de test
        test_payload = {
            "execution_name": f"test-direct-{int(__import__('time').time())}",
            "execution_arn": "test-direct-execution",
            "collect_from_s3": True,
            "test_mode": True
        }
        
        print(f"🚀 Invoking Result Collector directly...")
        print(f"📋 Payload: {json.dumps(test_payload, indent=2)}")
        
        # Invocar la función directamente
        response = lambda_client.invoke(
            FunctionName=result_collector_arn,
            InvocationType='RequestResponse',
            Payload=json.dumps(test_payload)
        )
        
        # Leer la respuesta
        result = json.loads(response['Payload'].read().decode('utf-8'))
        
        print(f"✅ Result Collector Response:")
        print(json.dumps(result, indent=2))
        
        # Si hay URL en la respuesta, mostrarla
        if isinstance(result, dict) and 'body' in result:
            body = json.loads(result['body']) if isinstance(result['body'], str) else result['body']
            if 'public_url' in body:
                print(f"🌐 Public URL: {body['public_url']}")
        
    except Exception as e:
        print(f"❌ Error testing Result Collector: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_result_collector()