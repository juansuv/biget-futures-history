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
            window_results = event  # Fallback si viene directo del map
        
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
                    window_id = result.get('window_id', 'unknown')
                    status_code = result.get('statusCode', 500)
                    symbols = result.get('symbols', [])
                    symbols_count = result.get('symbols_count', 0)
                    
                    window_stat = {
                        'window_id': window_id,
                        'status': 'success' if status_code == 200 else 'failed',
                        'symbols_count': symbols_count,
                        'start_date': result.get('start_date'),
                        'end_date': result.get('end_date')
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
                        print(f"Window {window_id}: Failed with error: {result.get('error', 'Unknown')}")
                        
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