import json
import time
import os
import random
import boto3
from typing import Dict, Any, List
from pybitget import Client

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Symbol Processor Lambda: Processes a single symbol to extract all its orders
    """
    print("Symbol processor lambda invoked")
    
    # Pausa más larga para respetar rate limits
    #time.sleep(0.2)
    
    try:
        print(f"Processing event: {event}")
        # Extract symbol from event
        symbol = event.get('symbol')
        if not symbol:
            raise ValueError("Symbol not provided in event")
        
        # Initialize Bitget client using environment variables
        api_key = os.environ.get('BITGET_API_KEY')
        secret_key = os.environ.get('BITGET_SECRET_KEY')
        passphrase = os.environ.get('BITGET_PASSPHRASE')
        
        if not all([api_key, secret_key, passphrase]):
            return {
                'statusCode': 500,
                'symbol': symbol,
                'error': 'Missing Bitget credentials in environment variables',
                'orders': [],
                'orders_count': 0,
                'processed_at': int(time.time() * 1000)
            }
        
        client = Client(
            api_key=api_key,
            api_secret_key=secret_key,
            passphrase=passphrase
        )
        
        # Extract all orders for this symbol
        orders = get_all_orders_for_symbol(client, symbol)
        print(f"Extracted {len(orders)} orders for symbol {symbol}")
        
        # Store results in S3 if there are any orders
        if len(orders) > 0:
            s3_key = store_orders_in_s3(symbol, orders)
            if s3_key:
                return {'statusCode': 200, 'symbol': symbol}
            else:
                return {'statusCode': 200, 'symbol': symbol, 'orders': orders[:1]}
        else:
            return {'statusCode': 200, 'symbol': symbol}
        
    except Exception:
        return {'statusCode': 500, 'symbol': event.get('symbol', 'unknown')}

def get_all_orders_for_symbol(client: Client, symbol: str) -> List[Dict[str, Any]]:
    """
    Get all historical futures orders for a specific symbol
    """
    all_orders = []
    page_size = 100
    max_pages = 60  # Prevent infinite loops
    
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
                        print(f"Rate limit hit for {symbol}, retry {retry_count}/{max_retries}")
                        if retry_count < max_retries:
                            #time.sleep(2 ** retry_count)  # Exponential backoff
                            continue
                        else:
                            print(f"Max retries reached for {symbol}")
                            return all_orders
                    else:
                        # Non-rate limit error, break immediately
                        print(f"Non-rate limit error for {symbol}: {e}")
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
                print(f"Error fetching page {page_count} for symbol {symbol}: {e}")
                break
        
        # Sort orders by creation time (newest first)
        #all_orders.sort(key=lambda x: int(x.get('cTime', 0)), reverse=True)
        print("all_orders", all_orders)
        return all_orders
        
    except Exception as e:
        print(f"Error getting orders for symbol {symbol}: {e}")
        return []

def store_orders_in_s3(symbol: str, orders: List[Dict[str, Any]]) -> str:
    """
    Store symbol orders in S3 and return the S3 key
    """
    try:
        s3_client = boto3.client('s3')
        bucket_name = os.environ.get('RESULTS_BUCKET')
        
        # Generate unique key for this symbol
        s3_key = f"symbol_results/{symbol}_{int(time.time())}.json"
        
        # Upload minimal result to S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json.dumps({'symbol': symbol, 'orders': orders}, separators=(',', ':')),
            ContentType='application/json'
        )
        
        return s3_key
        
    except Exception:
        return None