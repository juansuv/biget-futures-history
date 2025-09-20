import json
import time
import boto3
import os
import orjson
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List

def lambda_handler(event: Dict[str, Any], _) -> Dict[str, Any]:
    """
    Result Collector Lambda: Collects and sorts orders from S3
    """
    try:
        # Collect all orders from S3 symbol_results folder
        combined_result = collect_results_from_s3()
        
        # Store sorted orders in S3 
        s3_result = store_result_in_s3(combined_result.get('orders', []), execution_arn=event.get('execution_arn'))
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Orders processed successfully',
                'total_orders': len(combined_result.get('orders', [])),
                's3_key': s3_result if s3_result else None
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Error in result collector lambda'
            })
        }


def store_result_in_s3(all_orders: List[Dict[str, Any]], execution_arn: str = None) -> str:
    """
    Store sorted orders in S3 and return the S3 key with presigned URL
    """
    try:
        s3_client = boto3.client('s3')
        bucket_name = os.environ.get('RESULTS_BUCKET')
        
        # Generate unique key
        timestamp = int(time.time())
        execution_id = execution_arn.split(':')[-1] if execution_arn else 'unknown'
        s3_key = f"results/{timestamp}_{execution_id}.json"
        
        # Prepare CLEAN JSON with only sorted orders (ultra-fast binary encoding)
        clean_result = {
            'orders': all_orders
        }
        
        # Use orjson for ultra-fast JSON encoding
        json_body = orjson.dumps(clean_result, option=orjson.OPT_INDENT_2)
        
        # Upload to S3 with public read permissions
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json_body,
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


def collect_results_from_s3() -> Dict[str, Any]:
    """
    Collect all orders from S3 symbol_results folder with parallel processing
    """
    try:
        s3_client = boto3.client('s3')
        bucket_name = os.environ.get('RESULTS_BUCKET')
        
        if not bucket_name:
            raise Exception("RESULTS_BUCKET environment variable not set")
        
        print(f"Collecting results from s3://{bucket_name}/symbol_results/")
        
        # List all symbol result files
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix='symbol_results/'
        )
        
        all_orders = []
        
        if 'Contents' in response:
            json_files = [obj['Key'] for obj in response['Contents'] if obj['Key'].endswith('.json')]
            print(f"Found {len(json_files)} JSON files in symbol_results folder")
            
            if json_files:
                # Process files in parallel with optimized thread count
                max_workers = min(32, len(json_files))  # AWS Lambda max concurrent connections
                print(f"Processing files with {max_workers} parallel workers")
                
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # Submit all download tasks
                    future_to_key = {
                        executor.submit(download_and_parse_file, bucket_name, s3_key): s3_key 
                        for s3_key in json_files
                    }
                    
                    # Collect results as they complete
                    for future in as_completed(future_to_key):
                        s3_key = future_to_key[future]
                        try:
                            orders = future.result()
                            if orders:
                                all_orders.extend(orders)
                                print(f"✅ Loaded {len(orders)} orders from {s3_key}")
                        except Exception as e:
                            print(f"❌ Error processing {s3_key}: {e}")
        else:
            print("No files found in symbol_results folder")
        
        # Remove duplicates globally 
        print(f"Before deduplication: {len(all_orders)} orders")
        all_orders = remove_global_duplicates(all_orders)
        print(f"After deduplication: {len(all_orders)} orders")
        
        # Sort all orders globally by cTime (newest first)
        print("Sorting orders globally by cTime...")
        all_orders.sort(key=safe_ctime_parse, reverse=True)
        print(f"✅ Orders sorted globally by cTime")
        
        return {
            'message': 'Orders successfully collected from S3 with parallel processing',
            'orders': all_orders
        }
        
    except Exception as e:
        print(f"Error collecting results from S3: {e}")
        raise


def download_and_parse_file(bucket_name: str, s3_key: str) -> List[Dict[str, Any]]:
    """
    Download and parse a single S3 file (thread-safe)
    """
    try:
        s3_client = boto3.client('s3')
        file_response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
        content = file_response['Body'].read()
        
        # Use orjson for ultra-fast parsing
        try:
            data = orjson.loads(content)
        except:
            # Fallback to standard json
            data = json.loads(content.decode('utf-8'))
        
        return data.get('orders', [])
    except Exception as e:
        print(f"Error downloading {s3_key}: {e}")
        return []


def safe_ctime_parse(order: Dict[str, Any]) -> int:
    """
    Safely parse cTime for sorting (optimized)
    """
    try:
        ctime = order.get('cTime', '0')
        return int(str(ctime))
    except (ValueError, TypeError):
        return 0


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