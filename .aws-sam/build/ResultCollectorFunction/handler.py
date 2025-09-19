import json
import time
from typing import Dict, Any, List
from datetime import datetime

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Result Collector Lambda: Combines all parallel results and sorts chronologically
    """
    try:
        # Extract parallel results from event
        parallel_results = event.get('parallel_results', [])
        
        if not parallel_results:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'No results to process',
                    'total_orders': 0,
                    'orders': [],
                    'symbols_processed': 0,
                    'processing_summary': {}
                })
            }
        
        # Combine and process all results
        combined_result = combine_and_sort_orders(parallel_results)
        
        return {
            'statusCode': 200,
            'body': json.dumps(combined_result, indent=2)
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Error in result collector lambda'
            })
        }

def combine_and_sort_orders(parallel_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Combine all orders from parallel processing and sort chronologically
    """
    all_orders = []
    processing_summary = {}
    successful_symbols = []
    failed_symbols = []
    
    for result in parallel_results:
        try:
            # Extract the Lambda result from the Step Function response
            if 'Payload' in result:
                payload = result['Payload']
            else:
                payload = result
            
            symbol = payload.get('symbol', 'unknown')
            status_code = payload.get('statusCode', 500)
            orders = payload.get('orders', [])
            orders_count = payload.get('orders_count', 0)
            
            # Update processing summary
            processing_summary[symbol] = {
                'status_code': status_code,
                'orders_count': orders_count,
                'processed_at': payload.get('processed_at'),
                'success': status_code == 200
            }
            
            if status_code == 200:
                successful_symbols.append(symbol)
                # Add symbol info to each order for tracking
                for order in orders:
                    order['processing_symbol'] = symbol
                    all_orders.extend([order] if isinstance(order, dict) else [])
            else:
                failed_symbols.append({
                    'symbol': symbol,
                    'error': payload.get('error', 'Unknown error')
                })
                
        except Exception as e:
            failed_symbols.append({
                'symbol': 'unknown',
                'error': f'Error processing result: {str(e)}'
            })
    
    # Sort all orders chronologically (newest first)
    all_orders.sort(key=lambda x: int(x.get('createTime', 0)), reverse=True)
    
    # Generate statistics
    total_orders = len(all_orders)
    symbols_processed = len(successful_symbols)
    symbols_failed = len(failed_symbols)
    
    # Group orders by symbol for summary
    orders_by_symbol = {}
    for order in all_orders:
        symbol = order.get('symbol', 'unknown')
        if symbol not in orders_by_symbol:
            orders_by_symbol[symbol] = []
        orders_by_symbol[symbol].append(order)
    
    # Calculate date range
    date_range = get_date_range(all_orders)
    
    return {
        'message': 'Orders successfully processed and combined',
        'processing_timestamp': int(time.time() * 1000),
        'total_orders': total_orders,
        'symbols_processed': symbols_processed,
        'symbols_failed': symbols_failed,
        'date_range': date_range,
        'successful_symbols': successful_symbols,
        'failed_symbols': failed_symbols,
        'processing_summary': processing_summary,
        'orders_by_symbol_count': {symbol: len(orders) for symbol, orders in orders_by_symbol.items()},
        'orders': all_orders
    }

def get_date_range(orders: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate the date range of all orders
    """
    if not orders:
        return {'earliest': None, 'latest': None, 'total_days': 0}
    
    timestamps = [int(order.get('createTime', 0)) for order in orders if order.get('createTime')]
    
    if not timestamps:
        return {'earliest': None, 'latest': None, 'total_days': 0}
    
    earliest_ts = min(timestamps)
    latest_ts = max(timestamps)
    
    # Convert to readable dates
    earliest_date = datetime.fromtimestamp(earliest_ts / 1000).isoformat()
    latest_date = datetime.fromtimestamp(latest_ts / 1000).isoformat()
    
    # Calculate days difference
    total_days = (latest_ts - earliest_ts) / (1000 * 60 * 60 * 24)
    
    return {
        'earliest': earliest_date,
        'latest': latest_date,
        'earliest_timestamp': earliest_ts,
        'latest_timestamp': latest_ts,
        'total_days': round(total_days, 2)
    }