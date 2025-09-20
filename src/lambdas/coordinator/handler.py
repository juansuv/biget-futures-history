import json
import time
import os
import boto3
from typing import List, Dict, Any
from pybitget import Client
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Coordinator Lambda: Detects all symbols with trades and initiates Step Function
    """
    try:
        # Initialize Bitget client using environment variables
        api_key = os.environ.get('BITGET_API_KEY',"bg_680026a00a63d58058c738c952ce67a2")
        secret_key = os.environ.get('BITGET_SECRET_KEY',"7abac4a9404e82830db5f9db5e867a8370c7e59dc74e52615c59552d0afbd7c9")
        passphrase = os.environ.get('BITGET_PASSPHRASE',"22Dominic22")
        print("Coordinator lambda invoked")
        if not all([api_key, secret_key, passphrase]):
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Missing Bitget credentials in environment variables',
                    'message': 'Error in coordinator lambda'
                })
            }
        
        client = Client(
            api_key=api_key,
            api_secret_key=secret_key,
            passphrase=passphrase
        )
        
        # Get test mode from event
        test_mode = event.get('test_mode', False)
        
        if test_mode:
            print("Running in test mode")
            # Return test symbols
            symbols_with_trades = ["BTCUSDT", "ETHUSDT", "ADAUSDT", "DOGEUSDT", "SOLUSDT"]
        else:
            print("Detecting symbols with trades from Bitget account")
            # Get all symbols with futures trades
            symbols_with_trades = get_symbols_with_trades(client)
            print(f"Total symbols with trades found: {len(symbols_with_trades)}")
        print(f"Symbols with trades: {symbols_with_trades}")
        if not symbols_with_trades:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'No symbols with trades found',
                    'symbols': []
                })
            }
        
        # Start Step Function execution
        step_function_arn = event.get('step_function_arn')
        if step_function_arn:
            start_step_function(step_function_arn, symbols_with_trades)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Found {len(symbols_with_trades)} symbols with trades',
                'symbols': symbols_with_trades,
                'test_mode': test_mode
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Error in coordinator lambda'
            })
        }

def process_time_window(window_info):
    """
    Process a single time window to extract symbols (standalone function for threading)
    """
    start_time, end_time, credentials = window_info
    window_symbols = set()
    
    try:
        # Create separate client instance for thread safety
        thread_client = Client(
            api_key=credentials['api_key'],
            api_secret_key=credentials['secret_key'],
            passphrase=credentials['passphrase']
        )
        
        last_end_id = ""
        page = 1
        
        while page <= 10:  # Limit pages per window to prevent infinite loops
            try:
                resp = thread_client.mix_get_productType_history_orders(
                    productType="umcbl",
                    startTime=str(start_time),
                    endTime=str(end_time),
                    pageSize="1000",  # Optimize for speed
                    lastEndId=last_end_id,
                    isPre=False,
                )
                
                data = (resp or {}).get("data") or {}
                order_list = data.get("orderList") or []
                next_flag = data.get("nextFlag")
                end_id = data.get("endId")
                
                if not order_list:
                    break
                
                # Extract symbols from this batch
                for order in order_list:
                    sym = order.get("symbol")
                    if sym:
                        window_symbols.add(sym)
                
                # Early exit if we found enough symbols in this window
                if len(window_symbols) >= 50:
                    print(f"Window {start_time}-{end_time}: Found {len(window_symbols)} symbols, stopping early")
                    break
                
                if not next_flag:
                    break
                    
                last_end_id = end_id or order_list[-1].get("orderId", "")
                page += 1
                
                # Small delay to respect rate limits
                time.sleep(0.05)
                
            except Exception as e:
                print(f"Error in window {start_time}-{end_time}, page {page}: {e}")
                time.sleep(0.5)
                break
        
        print(f"Window {start_time}-{end_time}: Found {len(window_symbols)} symbols")
        return window_symbols
        
    except Exception as e:
        print(f"Error processing window {start_time}-{end_time}: {e}")
        return set()


def get_symbols_with_trades(client: Client) -> List[str]:
    """
    Get all symbols with trades using optimized parallel processing
    """
    try:
        # Check cache first
        cache_key = f"/tmp/symbols_cachea_{int(time.time() // 86400)}.json"
        if os.path.exists(cache_key):
            try:
                with open(cache_key, 'r') as f:
                    cached_symbols = json.load(f)
                print(f"Using cached symbols: {len(cached_symbols)} symbols")
                return cached_symbols[:300]
            except Exception as e:
                print(f"Cache read error: {e}, proceeding with API scan")

        print("Starting parallel symbol discovery...")
        
        # Parallel strategy: Process multiple time windows simultaneously  
        end_time = int(time.time() * 1000)
        months_6_ago = end_time - (6 * 30 * 24 * 60 * 60 * 1000)  # 6 months
        
        # Create time windows for parallel processing
        window_size = 15 * 24 * 60 * 60 * 1000  # 15-day windows
        time_windows = []
        
        # Prepare credentials for threads
        credentials = {
            'api_key': os.environ.get('BITGET_API_KEY', "bg_680026a00a63d58058c738c952ce67a2"),
            'secret_key': os.environ.get('BITGET_SECRET_KEY', "7abac4a9404e82830db5f9db5e867a8370c7e59dc74e52615c59552d0afbd7c9"),
            'passphrase': os.environ.get('BITGET_PASSPHRASE', "22Dominic22")
        }
        
        current_start = months_6_ago
        while current_start <= end_time and len(time_windows) < 12:  # Max 12 windows
            current_end = min(current_start + window_size - 1, end_time)
            time_windows.append((current_start, current_end, credentials))
            current_start = current_end + 1
        
        print(f"Processing {len(time_windows)} time windows in parallel...")
        
        # Execute parallel processing
        all_symbols = set()
        completed_windows = 0
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            # Submit all tasks
            future_to_window = {executor.submit(process_time_window, window): window for window in time_windows}
            
            # Process completed futures as they finish
            for future in as_completed(future_to_window):
                window_info = future_to_window[future]
                try:
                    window_symbols = future.result()
                    all_symbols.update(window_symbols)
                    completed_windows += 1
                    
                    print(f"Completed {completed_windows}/{len(time_windows)} windows. Total symbols: {len(all_symbols)}")
                    
                    # Early exit condition - but let running tasks finish
                    if len(all_symbols) >= 300:
                        print(f"Found enough symbols ({len(all_symbols)}). Waiting for remaining {len(time_windows) - completed_windows} tasks to complete...")
                        # Don't break - let remaining tasks complete naturally
                        
                except Exception as e:
                    print(f"Error getting result from window {window_info[:2]}: {e}")
                    completed_windows += 1
        
        print(f"All {completed_windows} windows completed.")
        
        # Sort and cache results
        result = sorted(list(all_symbols))
        print(f"Found {len(result)} symbols using parallel processing")
        
        # Cache results
        try:
            with open(cache_key, 'w') as f:
                json.dump(result, f)
            print(f"Cached {len(result)} symbols for future use")
        except Exception as e:
            print(f"Cache write error: {e}")
        
        return result
        
    except Exception as e:
        print(f"Error in parallel symbol discovery: {e}")
        # Fallback to common symbols
        return ["BTCUSDT", "ETHUSDT", "ADAUSDT", "DOGEUSDT", "SOLUSDT"]








def start_step_function(step_function_arn: str, symbols: List[str]) -> None:
    """
    Start the Step Function execution with the list of symbols
    """
    try:
        stepfunctions = boto3.client('stepfunctions')
        
        input_data = {
            'symbols': symbols,
        }
        
        stepfunctions.start_execution(
            stateMachineArn=step_function_arn,
            input=json.dumps(input_data)
        )
        
    except Exception as e:
        print(f"Error starting Step Function: {e}")
        raise
    
    
def get_all_orders_secuencial(client: Client, productType="umcbl"):
    start_time = 1514764800000   # 2021-01-01
    end_time = int(time.time() * 1000)  # ahora
    page=1
    page_size = 100
    last_end_id = ""
    first_order = None
    all_orders = []
    print("Fetching orders...")
    while True:
        resp = client.mix_get_productType_history_orders(
            productType=productType,
            startTime=start_time,
            endTime=end_time,
            pageSize=page_size,
            lastEndId=last_end_id,
            isPre=False
        )
        resp = resp.get("data", [])
        order_list = resp.get("orderList", [])
        flag=resp.get("nextFlag")
        endId = resp.get("endId")
        print(f"Response: flag={flag}, endId={endId}")
        if not order_list:
            break
        for order in order_list:
            all_orders.append(order)
            if not first_order or int(order["cTime"]) < int(first_order["cTime"]):
                first_order = order
        
        # Avanza al siguiente bloque
        last_end_id = order_list[-1]["orderId"]
        page += 1
    
    # Uso:
    with open("/tmp/all_orders.json", "w") as f:
        json.dump(all_orders, f, indent=2)
    print(f"Saved {len(all_orders)} orders to /tmp/all_orders_dmcbl.json")
    
    print("page:", page)
    print("First order found:", first_order)
    return first_order
