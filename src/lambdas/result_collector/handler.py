import json
import time
import boto3
import os
from typing import Dict, Any, List
from datetime import datetime

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Result Collector Lambda: Collects results from S3 symbol_results folder
    """
    try:
        # Check if we should collect from S3
        collect_from_s3 = event.get('collect_from_s3', False)
        
        if collect_from_s3:
            print("Collecting results directly from S3 symbol_results folder")
            combined_result = collect_results_from_s3()
        else:
            # Legacy mode: Extract parallel results from event
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
        
        # Store large result in S3 and return minimal summary
        s3_result = store_result_in_s3(combined_result, execution_arn=event.get('execution_arn'))
        
        # Check if S3 storage was successful
        if s3_result:
            # S3 storage successful - return minimal summary
            if isinstance(s3_result, dict):
                s3_key = s3_result['s3_key']
                presigned_url = s3_result.get('presigned_url')
            else:
                s3_key = s3_result
                presigned_url = None
                
            summary = {
                'message': 'Orders processed and stored in S3',
                'total_orders': combined_result['total_orders'],
                'symbols_processed': combined_result['symbols_processed'],
                'symbols_failed': combined_result['symbols_failed'],
                's3_key': s3_key,
                's3_bucket': os.environ.get('RESULTS_BUCKET'),
                'direct_download_url': presigned_url if presigned_url else f"https://{os.environ.get('RESULTS_BUCKET')}.s3.amazonaws.com/{s3_key}"
            }
        else:
            # S3 storage failed - return truncated result directly
            print("S3 storage failed, returning truncated result")
            # Limit orders to prevent Step Function data limit
            truncated_orders = combined_result['orders'][:50] if len(combined_result['orders']) > 50 else combined_result['orders']
            summary = {
                'message': 'Orders processed (S3 storage failed, result truncated)',
                'processing_timestamp': combined_result['processing_timestamp'],
                'total_orders': combined_result['total_orders'],
                'symbols_processed': combined_result['symbols_processed'],
                'symbols_failed': combined_result['symbols_failed'],
                'orders': truncated_orders,
                'orders_truncated': len(combined_result['orders']) > 50,
                's3_fallback_failed': True
            }
        
        return {
            'statusCode': 200,
            'body': json.dumps(summary, indent=2)
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
            orders_count = payload.get('orders_count', 0)
            
            # Update processing summary
            processing_summary[symbol] = {
                'status_code': status_code,
                'orders_count': orders_count,
                'processed_at': payload.get('processed_at'),
                'success': status_code == 200,
                'stored_in_s3': payload.get('stored_in_s3', False)
            }
            
            if status_code == 200:
                successful_symbols.append(symbol)
                
                # Check if orders are stored in S3
                if payload.get('stored_in_s3', False):
                    # Load orders from S3
                    s3_key = payload.get('s3_key')
                    s3_bucket = payload.get('s3_bucket')
                    if s3_key and s3_bucket:
                        orders = load_orders_from_s3(s3_bucket, s3_key)
                        print(f"Loaded {len(orders)} orders for {symbol} from S3")
                    else:
                        orders = []
                        print(f"Missing S3 reference for {symbol}")
                elif payload.get('s3_fallback_failed', False):
                    # S3 failed but we have limited orders
                    orders = payload.get('orders', [])
                    print(f"Using fallback orders for {symbol}: {len(orders)} (S3 failed)")
                else:
                    # Use orders directly from payload (no orders case)
                    orders = payload.get('orders', [])
                
                # Add symbol info to each order for tracking
                if orders and isinstance(orders, list):
                    for order in orders:
                        if isinstance(order, dict):
                            order['processing_symbol'] = symbol
                            all_orders.append(order)
                # Symbol processed successfully but no orders found (this is OK)
                elif orders_count == 0:
                    print(f"Symbol {symbol} processed successfully but no orders found")
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
    
    # Remove duplicates across all symbols before sorting
    print(f"Before global deduplication: {len(all_orders)} orders")
    all_orders = remove_global_duplicates(all_orders)
    print(f"After global deduplication: {len(all_orders)} orders")
    
    # Sort all orders chronologically (newest first)
    all_orders.sort(key=lambda x: int(x.get('createTime', 0)), reverse=True)
    
    # Generate statistics
    total_orders = len(all_orders)
    symbols_processed = len(successful_symbols)
    symbols_failed = len(failed_symbols)
    
    # # Group orders by symbol for summary
    # orders_by_symbol = {}
    # for order in all_orders:
    #     symbol = order.get('symbol', 'unknown')
    #     if symbol not in orders_by_symbol:
    #         orders_by_symbol[symbol] = []
    #     orders_by_symbol[symbol].append(order)
    
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
        #'orders_by_symbol_count': {symbol: len(orders) for symbol, orders in orders_by_symbol.items()},
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

def store_result_in_s3(result: Dict[str, Any], execution_arn: str = None) -> str:
    """
    Store large result in S3 and return the S3 key with presigned URL
    """
    try:
        s3_client = boto3.client('s3')
        bucket_name = os.environ.get('RESULTS_BUCKET')
        
        # Generate unique key
        timestamp = int(time.time())
        execution_id = execution_arn.split(':')[-1] if execution_arn else 'unknown'
        s3_key = f"results/{timestamp}_{execution_id}.json"
        
        # Prepare CLEAN JSON with only orders
        clean_result = {
            'orders': result.get('orders', [])
        }
        
        # Upload to S3 with public read permissions
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json.dumps(clean_result, indent=2, ensure_ascii=False),
            ContentType='application/json',
            ServerSideEncryption='AES256',
            ACL='bucket-owner-full-control'
        )
        
        print(f"Stored clean result in S3: s3://{bucket_name}/{s3_key}")
        
        # Generate presigned URL for direct download
        try:
            presigned_url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': s3_key},
                ExpiresIn=3600 * 24 * 7  # 7 days
            )
            print(f"Generated presigned URL: {presigned_url}")
            return {'s3_key': s3_key, 'presigned_url': presigned_url}
        except Exception as e:
            print(f"Error generating presigned URL: {e}")
            return s3_key
        
    except Exception as e:
        print(f"Error storing result in S3: {e}")
        # Fallback: return None and include orders in response (truncated)
        return None

def load_orders_from_s3(bucket_name: str, s3_key: str) -> List[Dict[str, Any]]:
    """
    Load orders from S3
    """
    try:
        s3_client = boto3.client('s3')
        
        # Get object from S3
        response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
        content = response['Body'].read().decode('utf-8')
        
        # Parse JSON
        data = json.loads(content)
        
        # Extract orders
        orders = data.get('orders', [])
        print(f"Loaded {len(orders)} orders from s3://{bucket_name}/{s3_key}")
        
        return orders
        
    except Exception as e:
        print(f"Error loading orders from S3 s3://{bucket_name}/{s3_key}: {e}")
        return []

def collect_results_from_s3() -> Dict[str, Any]:
    """
    Collect all results directly from S3 symbol_results folder
    """
    try:
        s3_client = boto3.client('s3')
        bucket_name = os.environ.get('RESULTS_BUCKET')
        
        if not bucket_name:
            raise Exception("RESULTS_BUCKET environment variable not set")
        
        print(f"Collecting results from s3://{bucket_name}/symbol_results/")
        
        # List all files in symbol_results folder
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix='symbol_results/'
        )
        
        all_orders = []
        successful_symbols = []
        failed_symbols = []
        total_files = 0
        
        if 'Contents' in response:
            total_files = len(response['Contents'])
            print(f"Found {total_files} files in symbol_results folder")
            
            for obj in response['Contents']:
                s3_key = obj['Key']
                if not s3_key.endswith('.json'):
                    continue
                    
                try:
                    # Download and parse JSON file
                    file_response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
                    content = file_response['Body'].read().decode('utf-8')
                    data = json.loads(content)
                    
                    symbol = data.get('symbol', 'unknown')
                    orders = data.get('orders', [])
                    orders_count = len(orders)
                    
                    print(f"Processing {symbol}: {orders_count} orders from {s3_key}")
                    
                    if orders_count > 0:
                        successful_symbols.append(symbol)
                        # Add symbol info to each order
                        for order in orders:
                            if isinstance(order, dict):
                                order['processing_symbol'] = symbol
                                all_orders.append(order)
                    else:
                        successful_symbols.append(symbol)
                        
                except Exception as e:
                    print(f"Error processing {s3_key}: {e}")
                    failed_symbols.append({
                        'symbol': s3_key.split('/')[-1].replace('.json', ''),
                        'error': str(e)
                    })
        else:
            print("No files found in symbol_results folder")
        
        # Remove duplicates across all symbols before sorting
        print(f"Before global deduplication: {len(all_orders)} orders")
        all_orders = remove_global_duplicates(all_orders)
        print(f"After global deduplication: {len(all_orders)} orders")
        
        # Sort all orders chronologically (newest first)
        all_orders.sort(key=lambda x: int(x.get('createTime', 0)), reverse=True)
        
        # Calculate date range
        date_range = get_date_range(all_orders)
        
        print(f"Collection complete: {len(all_orders)} total orders from {len(successful_symbols)} symbols")
        
        return {
            'message': 'Orders successfully collected from S3',
            'processing_timestamp': int(time.time() * 1000),
            'total_orders': len(all_orders),
            'symbols_processed': len(successful_symbols),
            'symbols_failed': len(failed_symbols),
            'date_range': date_range,
            'successful_symbols': successful_symbols,
            'failed_symbols': failed_symbols,
            'files_processed': total_files,
            'orders': all_orders
        }
        
    except Exception as e:
        print(f"Error collecting results from S3: {e}")
        raise

def remove_global_duplicates(all_orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicate orders across all symbols based on orderId
    """
    if not all_orders:
        return []
    
    seen_order_ids = set()
    unique_orders = []
    duplicates_count = 0
    
    for order in all_orders:
        order_id = order.get('orderId')
        if not order_id:
            # Si no tiene orderId, lo incluimos (caso raro)
            unique_orders.append(order)
            continue
            
        if order_id not in seen_order_ids:
            seen_order_ids.add(order_id)
            unique_orders.append(order)
        else:
            duplicates_count += 1
    
    if duplicates_count > 0:
        print(f"Removed {duplicates_count} duplicate orders across all symbols")
    
    return unique_orders