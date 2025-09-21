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
        return {}

def get_all_orders_for_symbol(client: Client, symbol: str) -> List[Dict[str, Any]]:
    all_orders = []
    page_size = 100
    max_pages = 130  # Prevent infinite loops
    
    try:
        # Calculate time range (last 90 days for comprehensive history)
        end_time = int(time.time() * 1000)
        start_time = 1514764800000 # 2018-01-01 in milliseconds
        
        last_end_id = ''
        page_count = 0
        
        while page_count < max_pages:
            retry_count = 0
            max_retries = 3
            
            while retry_count < max_retries:
                try:
                    # Get order history for this symbol
                    response = client.mix_get_history_orders(
                        symbol=symbol,
                        startTime=str(start_time),
                        endTime=str(end_time),
                        pageSize=str(page_size),
                        lastEndId=last_end_id,
                        isPre=False
                    )
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    error_str = str(e).lower()
                    if '429' in error_str or 'rate' in error_str or 'limit' in error_str:
                        retry_count += 1
                        if retry_count < max_retries:
                            continue
                        else:
                            return all_orders
                    else:
                        return all_orders
            
            try:
                
                if not response or 'data' not in response:
                    break
                
                orders_data = response['data']
                if not orders_data or 'orderList' not in orders_data:
                    break
                
                orders = orders_data['orderList']
                ()
                if not orders:
                    break
                all_orders.extend(orders)
                
                #print("all_orders", all_orders)                
                # Add orders to our collection
                # for order in orders:
                #     # Ensure we only get futures orders
                #     all_orders.append(order)
                
                # Check if there are more pages
                if 'endId' in orders_data and orders_data['endId']:
                    last_end_id = orders_data['endId']
                    page_count += 1
                else:
                    break
                    
                # Increased delay to respect rate limits
                #time.sleep(0.1)
                
            except Exception as e:
                break
        
        # Sort orders by creation time (newest first)
        #all_orders.sort(key=lambda x: int(x.get('cTime', 0)), reverse=True)
        return all_orders
        
    except Exception as e:
        return []

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