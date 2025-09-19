import json
import time
import boto3
from typing import List, Dict, Any
from pybitget import Client
from src.config import BitgetConfig

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Coordinator Lambda: Detects all symbols with trades and initiates Step Function
    """
    try:
        # Initialize Bitget client
        config = BitgetConfig.from_env()
        client = Client(
            api_key=config.api_key,
            api_secret_key=config.secret_key,
            passphrase=config.passphrase
        )
        
        # Get all symbols with futures trades
        symbols_with_trades = get_symbols_with_trades(client)
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
                'symbols': symbols_with_trades
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

def get_symbols_with_trades(client: Client) -> List[str]:
    """
    Get all symbols that have futures trades for the user
    """
    try:
        # Get all futures positions (both open and closed)
        # Using mix_get_all_positions to get symbols with any activity
        positions = client.mix_get_all_positions('umcbl')  # USDT-M futures
        
        symbols = set()
        print(f"Positions data: {positions}")
        # Extract symbols from positions
        if positions and 'data' in positions:
            for position in positions['data']:
                if position.get('symbol'):
                    symbols.add(position['symbol'])
        
        # Also check order history for additional symbols
        # Get recent order history to find more symbols
        try:
            # Get orders from last 30 days
            import time
            
            first_order = get_first_order(client, productType="umcbl")
            
            end_time = int(time.time() * 1000)
            start_time = end_time - (30 * 24 * 60 * 60 * 1000)  # 30 days ago
            
            history = client.mix_get_productType_history_orders(
                productType='umcbl',
                startTime=str(start_time),
                endTime=str(end_time),
                pageSize='100'
            )
            if history and 'data' in history and 'orderList' in history['data']:
                for order in history['data']['orderList']:
                    if order.get('symbol'):
                        symbols.add(order['symbol'])
                        
        except Exception as e:
            print(f"Warning: Could not fetch order history: {e}")
        
        return list(symbols)
        
    except Exception as e:
        print(f"Error getting symbols with trades: {e}")
        return []




def get_first_order(client, productType="umcbl"):
    start_time = 1609459200000   # 2021-01-01
    end_time = int(time.time() * 1000)  # ahora
    
    page_size = 100
    last_end_id = ""
    first_order = None
    
    while True:
        resp = client.mix_get_productType_history_orders(
            productType=productType,
            startTime=start_time,
            endTime=end_time,
            pageSize=page_size,
            lastEndId=last_end_id,
            isPre=False
        )
        
        order_list = resp.get("data", [])
        if not order_list:
            break
        
        for order in order_list:
            if not first_order or int(order["createTime"]) < int(first_order["createTime"]):
                first_order = order
        
        # Avanza al siguiente bloque
        last_end_id = order_list[-1]["id"]
    
    
    # Uso:

    print("First order:", first_order)
    return first_order




def start_step_function(step_function_arn: str, symbols: List[str]) -> None:
    """
    Start the Step Function execution with the list of symbols
    """
    try:
        stepfunctions = boto3.client('stepfunctions')
        
        input_data = {
            'symbols': symbols,
            'timestamp': int(time.time() * 1000)
        }
        
        stepfunctions.start_execution(
            stateMachineArn=step_function_arn,
            input=json.dumps(input_data)
        )
        
    except Exception as e:
        print(f"Error starting Step Function: {e}")
        raise