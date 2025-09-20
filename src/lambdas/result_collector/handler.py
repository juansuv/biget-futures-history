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
        print(f"📥 Result Collector started with event: {json.dumps(event, default=str)}")
        # Collect all orders from S3 symbol_results folder
        combined_result = collect_results_from_s3()
        
        # Store sorted orders in S3 
        execution_name = event.get('execution_name') or event.get('execution_arn', 'unknown')
        print(f"🔑 Execution name: {execution_name}")
        print(f"📊 Total orders to store: {len(combined_result.get('orders', []))}")
        
        s3_result = store_result_in_s3(combined_result.get('orders', []), execution_name=execution_name)
        print(f"💾 S3 result: {s3_result}")
        
        # Prepare response with URLs
        response_data = {
            'message': 'Orders processed successfully',
            'total_orders': len(combined_result.get('orders', []))
        }
        
        # Add S3 result info if available
        if s3_result:
            if isinstance(s3_result, dict):
                response_data.update(s3_result)
            else:
                response_data['s3_key'] = s3_result
        
        return {
            'statusCode': 200,
            'body': json.dumps(response_data)
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Error in result collector lambda'
            })
        }


def store_result_in_s3(all_orders: List[Dict[str, Any]], execution_name: str = None) -> str:
    """
    Store sorted orders in S3 and return the S3 key with presigned URL
    """
    try:
        s3_client = boto3.client('s3')
        bucket_name = os.environ.get('RESULTS_BUCKET')
        
        if not bucket_name:
            print("❌ RESULTS_BUCKET environment variable not set in store_result_in_s3")
            return None
        
        # Generate unique key first
        timestamp = int(time.time())
        execution_id = execution_name if execution_name else 'unknown'
        s3_key = f"results/{timestamp}_{execution_id}.json"
        
        print(f"🪣 Using bucket: {bucket_name}")
        print(f"📋 Storing {len(all_orders)} orders")
        print(f"🔑 S3 key will be: {s3_key}")
        
        # Test bucket access first
        try:
            s3_client.head_bucket(Bucket=bucket_name)
            print(f"✅ Bucket {bucket_name} is accessible")
        except Exception as e:
            print(f"❌ Cannot access bucket {bucket_name}: {e}")
            return None
        
        # Always create a result file (even if empty) for debugging
        if len(all_orders) == 0:
            print("⚠️ No orders found, creating test file for debugging")
            test_orders = [{
                "test": True,
                "message": "No orders found in symbol_results folder",
                "timestamp": timestamp,
                "execution_name": execution_name,
                "debug_info": "Result Collector executed successfully but found no orders"
            }]
            print("🔧 Using test orders for S3 upload")
        else:
            test_orders = all_orders
            print(f"✅ Using {len(all_orders)} real orders for S3 upload")
        
        # Prepare CLEAN JSON with only sorted orders (ultra-fast binary encoding)
        clean_result = {
            'orders': test_orders
        }
        
        # Use orjson for ultra-fast JSON encoding
        json_body = orjson.dumps(clean_result, option=orjson.OPT_INDENT_2)
        
        # Upload to S3 with public read permissions
        print(f"📤 Starting S3 upload to: s3://{bucket_name}/{s3_key}")
        print(f"📦 JSON body size: {len(json_body)} bytes")
        
        try:
            put_response = s3_client.put_object(
                Bucket=bucket_name,
                Key=s3_key,
                Body=json_body,
                ContentType='application/json',
                ServerSideEncryption='AES256'
            )
            status_code = put_response.get('ResponseMetadata', {}).get('HTTPStatusCode')
            print(f"✅ S3 PUT successful! HTTP Status: {status_code}")
            print(f"✅ S3 ETag: {put_response.get('ETag', 'N/A')}")
        except Exception as upload_error:
            print(f"❌ S3 PUT FAILED: {upload_error}")
            print(f"❌ Error type: {type(upload_error)}")
            import traceback
            print(f"❌ Upload traceback: {traceback.format_exc()}")
            return None
        
        # Generate public URL (direct access)
        public_url = f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"
        
        print(f"✅ Stored clean result in S3: s3://{bucket_name}/{s3_key}")
        print(f"🌐 Public URL: {public_url}")
        print(f"📦 File size: {len(json_body)} bytes")
        
        # Verify the file was actually stored
        try:
            head_response = s3_client.head_object(Bucket=bucket_name, Key=s3_key)
            print(f"✅ File verification successful. Size: {head_response.get('ContentLength')} bytes")
        except Exception as e:
            print(f"❌ File verification failed: {e}")
        
        # Also generate presigned URL as backup
        try:
            presigned_url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': s3_key},
                ExpiresIn=3600 * 24 * 7  # 7 days
            )
            print(f"Generated presigned URL: {presigned_url}")
            return {
                's3_key': s3_key, 
                'public_url': public_url,
                'presigned_url': presigned_url
            }
        except Exception as e:
            print(f"Error generating presigned URL: {e}")
            return {
                's3_key': s3_key, 
                'public_url': public_url
            }
        
    except Exception as e:
        print(f"❌ Error storing result in S3: {e}")
        print(f"❌ Error type: {type(e)}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
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
            all_files = [obj['Key'] for obj in response['Contents']]
            json_files = [obj['Key'] for obj in response['Contents'] if obj['Key'].endswith('.json')]
            print(f"📁 Found {len(response['Contents'])} total files in symbol_results folder")
            print(f"📄 Found {len(json_files)} JSON files in symbol_results folder")
            print(f"📋 All files: {all_files[:10]}...")  # Show first 10 files
            print(f"📋 JSON files: {json_files[:5]}...")  # Show first 5 JSON files
            
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
        
        # Clean up symbol_results folder after processing
        if json_files:
            print(f"🧹 Starting cleanup of {len(json_files)} files AFTER processing")
            cleanup_symbol_results(bucket_name, json_files)
        else:
            print("🧹 No files to cleanup")
        
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


def cleanup_symbol_results(bucket_name: str, json_files: List[str]) -> None:
    """
    Clean up symbol_results folder by deleting all processed files
    ONLY deletes files from symbol_results/ folder, NOT results/ folder
    """
    try:
        s3_client = boto3.client('s3')
        
        print(f"🧹 Starting cleanup of symbol_results/ folder only")
        print(f"🧹 Files to delete: {json_files[:5]}...")  # Show first 5 files
        print(f"🧹 Will delete {len(json_files)} files from symbol_results/ (NOT results/)")
        
        # Delete files in batches (S3 delete_objects supports up to 1000 objects)
        batch_size = 1000
        deleted_count = 0
        
        for i in range(0, len(json_files), batch_size):
            batch = json_files[i:i + batch_size]
            
            # Safety check: only delete files from symbol_results/ folder
            safe_batch = []
            for key in batch:
                if key.startswith('symbol_results/'):
                    safe_batch.append(key)
                else:
                    print(f"⚠️ SKIPPING file not in symbol_results/: {key}")
            
            if not safe_batch:
                print(f"⚠️ No safe files to delete in this batch")
                continue
            
            # Prepare delete request with safety-checked files
            delete_objects = {
                'Objects': [{'Key': key} for key in safe_batch]
            }
            
            print(f"🗑️ Deleting batch of {len(safe_batch)} files from symbol_results/")
            
            # Delete batch
            try:
                response = s3_client.delete_objects(
                    Bucket=bucket_name,
                    Delete=delete_objects
                )
                deleted_in_batch = len(response.get('Deleted', []))
                deleted_count += deleted_in_batch
                print(f"🗑️ Deleted {deleted_in_batch} files from symbol_results")
                
            except Exception as e:
                print(f"❌ Error deleting batch: {e}")
        
        print(f"✅ Cleanup completed: {deleted_count}/{len(json_files)} files deleted from symbol_results/ folder")
        print(f"📁 results/ folder remains untouched with final results")
        
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        # Don't raise - cleanup failure shouldn't stop the main process


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