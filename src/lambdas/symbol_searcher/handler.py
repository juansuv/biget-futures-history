import json
import time
import os
from typing import Dict, Any, List, Set
from pybitget import Client

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Symbol Searcher Lambda: Busca todos los símbolos con trades en una ventana de tiempo específica
    """
    try:
        print("Symbol Searcher lambda invoked")
        
        # Extraer ventana de tiempo del evento
        window_id = event.get('window_id', 'unknown')
        start_time = event.get('start_time')
        end_time = event.get('end_time')
        start_date = event.get('start_date', 'unknown')
        end_date = event.get('end_date', 'unknown')
        
        if not start_time or not end_time:
            raise ValueError("Missing start_time or end_time in event")
        
        print(f"Processing window {window_id}: {start_date} to {end_date}")
        
        # Inicializar cliente Bitget
        api_key = os.environ.get('BITGET_API_KEY')
        secret_key = os.environ.get('BITGET_SECRET_KEY')
        passphrase = os.environ.get('BITGET_PASSPHRASE')
        
        if not all([api_key, secret_key, passphrase]):
            return {
                'statusCode': 500,
                'window_id': window_id,
                'error': 'Missing Bitget credentials in environment variables',
                'symbols': []
            }
        
        client = Client(
            api_key=api_key,
            api_secret_key=secret_key,
            passphrase=passphrase
        )
        
        # Buscar símbolos en esta ventana de tiempo
        symbols = search_symbols_in_window(client, start_time, end_time, window_id)
        
        print(f"Window {window_id}: Found {len(symbols)} unique symbols")
        
        return {
            'statusCode': 200,
            'window_id': window_id,
            'start_time': start_time,
            'end_time': end_time,
            'start_date': start_date,
            'end_date': end_date,
            'symbols': list(symbols),
            'symbols_count': len(symbols),
            'processed_at': int(time.time() * 1000)
        }
        
    except Exception as e:
        print(f"Error in symbol searcher: {e}")
        return {
            'statusCode': 500,
            'window_id': event.get('window_id', 'unknown'),
            'error': str(e),
            'symbols': [],
            'symbols_count': 0
        }

def search_symbols_in_window(client: Client, start_time: int, end_time: int, window_id: str) -> Set[str]:
    """
    Busca símbolos en una ventana de tiempo específica
    """
    symbols = set()
    
    try:
        last_end_id = ""
        page = 1
        max_pages = 30  # Límite optimizado de páginas por ventana
        
        print(f"Searching symbols in window {window_id} from {start_time} to {end_time}")
        
        while page <= max_pages:
            try:
                # Obtener órdenes históricas
                resp = client.mix_get_productType_history_orders(
                    productType="umcbl",  # USDT-M futures
                    startTime=str(start_time),
                    endTime=str(end_time),
                    pageSize="1000",  # Máximo permitido
                    lastEndId=last_end_id,
                    isPre=False,
                )
                
                data = (resp or {}).get("data") or {}
                order_list = data.get("orderList") or []
                next_flag = data.get("nextFlag")
                end_id = data.get("endId")
                
                if not order_list:
                    print(f"Window {window_id}: No more orders found, stopping at page {page}")
                    break
                
                # Extraer símbolos únicos de esta página
                page_symbols = set()
                for order in order_list:
                    sym = order.get("symbol")
                    if sym:
                        symbols.add(sym)
                        page_symbols.add(sym)
                
                print(f"Window {window_id}, page {page}: Found {len(page_symbols)} new symbols, total: {len(symbols)}")
                
                # Early exit si encontramos suficientes símbolos
                if len(symbols) >= 60:
                    print(f"Window {window_id}: Found enough symbols ({len(symbols)}), stopping early")
                    break
                
                if not next_flag:
                    print(f"Window {window_id}: No more pages available")
                    break
                    
                last_end_id = end_id or order_list[-1].get("orderId", "")
                page += 1
                
                # Pausa más larga para respetar rate limits
                #time.sleep(0.2)
                
            except Exception as api_error:
                error_msg = str(api_error).lower()
                if 'rate' in error_msg or '429' in error_msg:
                    print(f"Window {window_id}: Rate limit hit, backing off...")
                    #time.sleep(0.2)  # Backoff más largo
                    continue
                else:
                    print(f"Window {window_id}: API error on page {page}: {api_error}")
                    break
        
        print(f"Window {window_id}: Completed search, found {len(symbols)} symbols in {page-1} pages")
        return symbols
        
    except Exception as e:
        print(f"Error searching symbols in window {window_id}: {e}")
        return symbols  # Retorna lo que haya encontrado hasta ahora