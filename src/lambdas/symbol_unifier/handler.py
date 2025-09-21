import json
import time
import os
import boto3
from typing import Dict, Any, List
from collections import Counter

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Symbol Unifier Lambda: Combina todos los símbolos encontrados por las ventanas de tiempo,
    deduplica, ordena y prepara para el procesamiento de órdenes
    """
    try:
        # Extraer resultados de todas las ventanas
        window_results = event.get('window_results', [])
        if not window_results:
            window_results = event
        
        if isinstance(window_results, dict):
            if 'window_results' in window_results:
                window_results = window_results['window_results']
            else:
                for value in window_results.values():
                    if isinstance(value, list):
                        window_results = value
                        break
        
        if not isinstance(window_results, list):
            return {'statusCode': 500, 'symbols': []}
        
        # Combinar todos los símbolos
        all_symbols = set()
        symbol_frequency = Counter()
        
        for result in window_results:
            try:
                if isinstance(result, dict):
                    # Extraer payload si viene del Step Function Map
                    payload = result['Payload'] if 'Payload' in result else result
                    
                    status_code = payload.get('statusCode', 500)
                    symbols = payload.get('symbols', [])
                    
                    
                    if status_code == 200:
                        for symbol in symbols:
                            all_symbols.add(symbol)
                            symbol_frequency[symbol] += 1
                        
            except Exception:
                pass
        
        # Ordenar símbolos por frecuencia (más activos primero) y luego alfabéticamente
        #final_symbols = sorted(all_symbols, key=lambda x: (-symbol_frequency[x], x))
        
        print(f"Discovered {len(all_symbols)} unique symbols across {len(window_results)} windows")
        
        
        # Preparar resultado - solo símbolos para optimizar velocidad (convertir set a list)
        result = {
            'statusCode': 200,
            'symbols': list(all_symbols)
        }
        
        
        return result
        
    except Exception:
        return {'statusCode': 500, 'symbols': []}

def save_detailed_stats_to_s3(result: dict, all_symbols: set, symbol_frequency: Counter):
    """
    Guarda estadísticas detalladas en S3 para análisis posterior
    """
    try:
        s3_client = boto3.client('s3')
        bucket_name = os.environ.get('RESULTS_BUCKET')
        
        if not bucket_name:
            print("No RESULTS_BUCKET configured, skipping detailed stats")
            return
        
        timestamp = int(time.time())
        s3_key = f"symbol_discovery_stats/{timestamp}_symbol_stats.json"
        
        detailed_stats = {
            'timestamp': timestamp,
            'summary': result,
            'all_symbols': sorted(list(all_symbols)),
            'symbol_frequency': dict(symbol_frequency),
            'discovery_metadata': {
                'total_symbols_discovered': len(all_symbols),
                'most_frequent_symbol': symbol_frequency.most_common(1)[0] if symbol_frequency else None,
                'symbols_appearing_once': sum(1 for count in symbol_frequency.values() if count == 1),
                'symbols_appearing_multiple_times': sum(1 for count in symbol_frequency.values() if count > 1)
            }
        }
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json.dumps(detailed_stats, indent=2, ensure_ascii=False),
            ContentType='application/json',
            ServerSideEncryption='AES256'
        )
        
        print(f"Detailed stats saved to s3://{bucket_name}/{s3_key}")
        
    except Exception as e:
        print(f"Error saving detailed stats to S3: {e}")
        # No re-lanzar la excepción para no fallar el proceso principal