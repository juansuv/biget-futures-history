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
        print("Symbol Unifier lambda invoked")
        
        # Extraer resultados de todas las ventanas
        window_results = event.get('window_results', [])
        if not window_results:
            # Fallback: buscar en toda la estructura del evento
            print(f"No window_results found, full event keys: {list(event.keys())}")
            window_results = event
        
        # Debug: mostrar estructura de window_results
        print(f"window_results type: {type(window_results)}")
        if isinstance(window_results, list) and len(window_results) > 0:
            print(f"First window_result sample: {window_results[0]}")
            # Ya tenemos la lista, continuar con el procesamiento
        elif isinstance(window_results, dict):
            print(f"window_results as dict keys: {list(window_results.keys())}")
            # Si window_results es dict, extraer la lista real
            if 'window_results' in window_results:
                window_results = window_results['window_results']
                print(f"Extracted window_results, new type: {type(window_results)}")
            elif isinstance(window_results, dict) and len(window_results) == 1:
                # Podría ser que toda la estructura esté en una clave
                for key, value in window_results.items():
                    if isinstance(value, list):
                        print(f"Found list in key '{key}', using it as window_results")
                        window_results = value
                        break
        
        # Verificar que window_results sea una lista después de todo el procesamiento
        if not isinstance(window_results, list):
            print(f"ERROR: window_results is not a list after processing: {type(window_results)}")
            return {
                'statusCode': 500,
                'error': f'Invalid window_results format: {type(window_results)}',
                'message': 'Error unifying symbols',
                'symbols': []
            }
        
        print(f"Processing results from {len(window_results)} time windows")
        
        # Combinar todos los símbolos
        all_symbols = set()
        symbol_frequency = Counter()
        window_stats = []
        successful_windows = 0
        failed_windows = 0
        
        for result in window_results:
            try:
                if isinstance(result, dict):
                    # Extraer payload si viene del Step Function Map
                    if 'Payload' in result:
                        payload = result['Payload']
                        print(f"Extracting from Payload: {type(payload)}")
                    else:
                        payload = result
                        print(f"Using result directly: {type(payload)}")
                    
                    window_id = payload.get('window_id', 'unknown')
                    status_code = payload.get('statusCode', 500)
                    symbols = payload.get('symbols', [])
                    symbols_count = payload.get('symbols_count', 0)
                    
                    print(f"Processing window {window_id}: status={status_code}, symbols_count={symbols_count}")
                    
                    window_stat = {
                        'window_id': window_id,
                        'status': 'success' if status_code == 200 else 'failed',
                        'symbols_count': symbols_count,
                        'start_date': payload.get('start_date'),
                        'end_date': payload.get('end_date')
                    }
                    window_stats.append(window_stat)
                    
                    if status_code == 200:
                        successful_windows += 1
                        # Agregar símbolos al conjunto global
                        for symbol in symbols:
                            all_symbols.add(symbol)
                            symbol_frequency[symbol] += 1
                        print(f"Window {window_id}: {symbols_count} symbols")
                    else:
                        failed_windows += 1
                        print(f"Window {window_id}: Failed with error: {payload.get('error', 'Unknown')}")
                        
            except Exception as e:
                failed_windows += 1
                print(f"Error processing window result: {e}")
        
        # Ordenar símbolos por frecuencia (más activos primero) y luego alfabéticamente
        sorted_symbols = sorted(all_symbols, key=lambda x: (-symbol_frequency[x], x))
        
        # Limitar a un número manejable de símbolos
        max_symbols = 350  # Límite para evitar timeouts en el procesamiento posterior
        final_symbols = sorted_symbols[:max_symbols]
        
        # Estadísticas
        total_unique_symbols = len(all_symbols)
        total_processing_symbols = len(final_symbols)
        
        print(f"Symbol unification completed:")
        print(f"- Successful windows: {successful_windows}")
        print(f"- Failed windows: {failed_windows}")
        print(f"- Total unique symbols found: {total_unique_symbols}")
        print(f"- Symbols selected for processing: {total_processing_symbols}")
        
        # Preparar resultado
        result = {
            'statusCode': 200,
            'message': f'Successfully unified symbols from {successful_windows} windows',
            'symbols': final_symbols,
            'total_unique_symbols': total_unique_symbols,
            'processing_symbols_count': total_processing_symbols,
            'successful_windows': successful_windows,
            'failed_windows': failed_windows,
            'window_stats': window_stats,
            'symbol_frequency_top10': dict(symbol_frequency.most_common(10)),
            'processing_timestamp': int(time.time() * 1000),
            'truncated': total_unique_symbols > max_symbols
        }
        
        # Opcional: Guardar estadísticas detalladas en S3
        try:
            save_detailed_stats_to_s3(result, all_symbols, symbol_frequency)
        except Exception as e:
            print(f"Warning: Could not save detailed stats to S3: {e}")
        
        return result
        
    except Exception as e:
        print(f"Error in symbol unifier: {e}")
        return {
            'statusCode': 500,
            'error': str(e),
            'message': 'Error unifying symbols',
            'symbols': []
        }

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