import json
import time
import boto3
from typing import List, Dict, Any
from pybitget import Client
from config import BitgetConfig

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
        positions = client.mix_get_symbols_info('umcbl')  # USDT-M futures
        
        symbols = set()
        print(f"Positions data: {positions}")
        # Extract symbols from positions
        if positions and 'data' in positions:
            for position in positions['data']:
                if position.get('symbol'):
                    symbols.add(position['symbol'])
        

        return list(symbols)
        
    except Exception as e:
        print(f"Error getting symbols with trades: {e}")
        return []








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
