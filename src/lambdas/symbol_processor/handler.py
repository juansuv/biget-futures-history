import time
import os
import boto3
import orjson
from typing import Dict, Any, List
from pybitget import Client

def lambda_handler(event, _):
    """
    Symbol Processor Lambda: Processes a single symbol to extract all its orders
    """
    try:
        print(f"🔄 Symbol Processor started with event: {event}")
        
        # Extract symbol from event
        symbol = event.get('symbol')
        if not symbol:
            print("❌ No symbol provided in event")
            return {}
        
        print(f"📈 Processing symbol: {symbol}")
        
        # Initialize Bitget client using environment variables
        api_key = os.environ.get('BITGET_API_KEY')
        secret_key = os.environ.get('BITGET_SECRET_KEY')
        passphrase = os.environ.get('BITGET_PASSPHRASE')
        
        if not all([api_key, secret_key, passphrase]):
            print("❌ Missing Bitget API credentials")
            return {}
        
        print("✅ Bitget credentials found, initializing client")
        
        client = Client(
            api_key=api_key,
            api_secret_key=secret_key,
            passphrase=passphrase
        )
        
        # Extract all orders for this symbol
        print(f"🔍 Extracting orders for {symbol}")
        orders = get_all_orders_for_symbol(client, symbol)
        print(f"📊 Found {len(orders)} orders for {symbol}")
        
        # Store results in S3 if there are any orders
        if orders:
            store_orders_in_s3(symbol, orders)
        else:
            print(f"⚠️ No orders found for {symbol}, not storing in S3")
        
        return {}
        
    except Exception as e:
        print(f"❌ Symbol Processor error: {e}")
        # CRITICAL: Raise error to fail Lambda completely for Step Function retry
        raise e

def get_all_orders_for_symbol(client: Client, symbol: str) -> List[Dict[str, Any]]:
    all_orders = []
    page_size = 100
    max_pages = 300  # Increased to prevent data loss (30k orders max per symbol)
    
    try:
        # Calculate time range (FIXED: always same range for consistency)
        end_time = int(time.time() * 1000)  # Current time
        start_time = end_time - (9 * 365 * 24 * 60 * 60 * 1000)  # Always 9 years back
        
        print(f"🔍 {symbol}: Searching from {start_time} to {end_time} (9 years)") 
        
        last_end_id = ''
        page_count = 0
        max_rate_limit_retries = 5 # Max 5 rate limit retries per page
        
        while page_count < max_pages:
            
            
            # Inner retry loop for the same page
            page_success = False
            page_retries = 0
            
            while not page_success and page_retries <= max_rate_limit_retries:
                try:
                    response = client.mix_get_history_orders(
                        symbol=symbol,
                        startTime=str(start_time),
                        endTime=str(end_time),
                        pageSize=str(page_size),
                        lastEndId=last_end_id,
                        isPre=False
                    )

                    # SAFETY: Validate response structure
                    if not response:
                        print(f"⚠️ {symbol}: Empty response from API")
                        break
                        
                    data = response.get('data', {})
                    if not data:
                        print(f"⚠️ {symbol}: No 'data' field in response")
                        break

                    orders = data.get('orderList', [])
                    last_end_id = data.get('endId', '')
                    next_flag = data.get('nextFlag', False)

                    # SAFETY: Ensure orders is a list (API might return None)
                    if orders is None:
                        orders = []
                        
                    all_orders.extend(orders)
                    
                    # DIAGNOSTIC: Log progress for each symbol
                    print(f"📄 {symbol} page {page_count + 1}: +{len(orders)} orders, total: {len(all_orders)}, next_flag: {next_flag}")
                    
                    # Mark page as successfully processed
                    page_success = True

                    if not next_flag:
                        print(f"✅ {symbol}: Naturally complete at page {page_count + 1} - {len(all_orders)} total orders")
                        return all_orders  # Exit completely when done
                
                except Exception as api_error:
                    error_str = str(api_error).lower()
                    print(f"❌ {symbol} API error on page {page_count + 1}: {api_error}")
                    
                    # Handle discontinued symbols (error code 40309)
                    if '40309' in error_str or 'symbol has been removed' in error_str or 'removed' in error_str:
                        print(f"⚠️ {symbol}: Symbol discontinued/removed, skipping with 0 orders")
                        return []  # Return empty list for discontinued symbols
                    
                    # Handle rate limiting: wait and retry same page
                    if '429' in error_str or 'too many requests' in error_str or 'rate limit' in error_str:
                        page_retries += 1
                        if page_retries <= max_rate_limit_retries:
                            backoff_time = 0.5 + (page_retries * 0.3)  # Exponential backoff: 0.8s, 1.1s, 1.4s, etc.
                            print(f"⏳ {symbol}: Rate limit hit (retry {page_retries}/{max_rate_limit_retries}), backing off {backoff_time:.1f}s...")
                            time.sleep(backoff_time)
                            # Continue inner loop to retry same page
                            continue
                        else:
                            print(f"🔴 CRITICAL: {symbol} exhausted rate limit retries on page {page_count + 1}")
                            print(f"🔴 This page's orders will be LOST! Failing Lambda for complete retry.")
                            raise api_error  # Fail Lambda completely to retry entire symbol
                    else:
                        # For other errors, fail the Lambda for retry
                        print(f"💥 {symbol}: Non-rate-limit error, failing Lambda for retry")
                        raise api_error
            
            # Move to next page
            page_count += 1
        
        # CRITICAL: Check if we hit max_pages limit (potential data loss)
        if page_count >= max_pages:
            print(f"🔴 TRUNCATED: {symbol} hit max_pages limit ({max_pages})! POTENTIAL DATA LOSS!")
            print(f"🔴 Last endId: {last_end_id}, Total orders collected: {len(all_orders)}")
            print(f"🔴 This symbol may have more orders that were NOT retrieved")
        else:
            print(f"📊 {symbol}: Completed pagination, {len(all_orders)} orders in {page_count} pages")
        
        # Sort orders by creation time (newest first)
        #all_orders.sort(key=lambda x: int(x.get('cTime', 0)), reverse=True)
        return all_orders
        
    except Exception as general_error:
        print(f"❌ {symbol}: General error - {general_error}")
        # CRITICAL: Raise error to fail Lambda for retry  
        raise general_error

def store_orders_in_s3(symbol: str, orders: List[Dict[str, Any]]):
    """
    Store orders in S3 with ultra-fast binary JSON encoding
    """
    try:
        s3_client = boto3.client('s3')
        bucket_name = os.environ.get('RESULTS_BUCKET')
        s3_key = f"symbol_results/{symbol}_{int(time.time())}.json"
        
        print(f"💾 Storing {len(orders)} orders for symbol {symbol}")
        print(f"📁 S3 key: {s3_key}")
        
        # Use orjson for ultra-fast binary JSON encoding (up to 5x faster)
        json_body = orjson.dumps({'orders': orders})
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json_body,
            ContentType='application/json'
        )
        print(f"✅ Successfully stored {symbol} orders in S3")
    except Exception as e:
        print(f"❌ Error storing {symbol} orders in S3: {e}")