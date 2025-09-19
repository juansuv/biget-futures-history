#!/usr/bin/env python3
"""
Simple demo of the Bitget solution without AWS dependencies
"""
import json
import time
from pybitget import Client

# Bitget credentials
API_KEY = "bg_680026a00a63d58058c738c952ce67a2"
SECRET_KEY = "7abac4a9404e82830db5f9db5e867a8370c7e59dc74e52615c59552d0afbd7c9"
PASSPHRASE = "22Dominic22"

def test_bitget_connection():
    """Test basic connection to Bitget API"""
    print("🔌 Testing Bitget API connection...")
    
    try:
        client = Client(
            api_key=API_KEY,
            api_secret_key=SECRET_KEY,
            passphrase=PASSPHRASE
        )
        
        # Test with a simple API call
        print("✅ Successfully connected to Bitget API")
        print(f"Client methods: {[m for m in dir(client) if not m.startswith('_')][:10]}...")
        
        return client
        
    except Exception as e:
        print(f"❌ Failed to connect to Bitget: {str(e)}")
        return None

def get_symbols_with_trades(client):
    """Get symbols that have trading activity"""
    print("\n📊 Getting symbols with trading activity...")
    
    try:
        # Get all positions
        positions = client.mix_get_all_positions('umcbl')
        print(f"Positions response: {positions}")
        
        symbols = set()
        
        if positions and 'data' in positions:
            for position in positions['data']:
                if position.get('symbol'):
                    symbols.add(position['symbol'])
        
        print(f"Found {len(symbols)} symbols from positions: {list(symbols)}")
        
        # Also try to get some order history
        try:
            end_time = int(time.time() * 1000)
            start_time = end_time - (7 * 24 * 60 * 60 * 1000)  # 7 days ago
            
            history = client.mix_get_productType_history_orders(
                productType='umcbl',
                startTime=str(start_time),
                endTime=str(end_time),
                pageSize='10'
            )
            
            print(f"Order history response: {history}")
            
            if history and 'data' in history and 'orderList' in history['data']:
                for order in history['data']['orderList']:
                    if order.get('symbol'):
                        symbols.add(order['symbol'])
                        
            print(f"Total symbols after checking order history: {len(symbols)}")
                        
        except Exception as e:
            print(f"Note: Could not fetch order history: {e}")
        
        return list(symbols)
        
    except Exception as e:
        print(f"❌ Error getting symbols: {str(e)}")
        return []

def get_orders_for_symbol(client, symbol):
    """Get orders for a specific symbol"""
    print(f"\n📈 Getting orders for {symbol}...")
    
    try:
        end_time = int(time.time() * 1000)
        start_time = end_time - (30 * 24 * 60 * 60 * 1000)  # 30 days ago
        
        response = client.mix_get_history_orders(
            symbol=symbol,
            startTime=str(start_time),
            endTime=str(end_time),
            pageSize='20'
        )
        
        print(f"Orders response for {symbol}: {response}")
        
        orders = []
        if response and 'data' in response and 'orderList' in response['data']:
            orders = response['data']['orderList']
            
        print(f"Found {len(orders)} orders for {symbol}")
        
        return orders
        
    except Exception as e:
        print(f"❌ Error getting orders for {symbol}: {str(e)}")
        return []

def main():
    """Run the demo"""
    print("🚀 Bitget Trading Orders Demo")
    print("=" * 50)
    
    # Test connection
    client = test_bitget_connection()
    if not client:
        return
    
    # Get symbols
    symbols = get_symbols_with_trades(client)
    
    if not symbols:
        print("\n📊 No symbols found with trading activity")
        print("   This could mean:")
        print("   - No recent trading activity")
        print("   - API credentials may not have trading history")
        print("   - Account might be new or inactive")
        
        # Try to get some market data instead
        print("\n🔍 Trying to get market symbols...")
        try:
            # Get available symbols from market data
            symbols_info = client.mix_get_symbols_info()
            if symbols_info and 'data' in symbols_info:
                sample_symbols = [s['symbol'] for s in symbols_info['data'][:3]]
                print(f"Sample available symbols: {sample_symbols}")
                
                # Test with a popular symbol
                if sample_symbols:
                    test_symbol = sample_symbols[0]
                    print(f"\n🧪 Testing with popular symbol: {test_symbol}")
                    orders = get_orders_for_symbol(client, test_symbol)
                    
        except Exception as e:
            print(f"Could not get market symbols: {e}")
            
    else:
        print(f"\n✅ Found {len(symbols)} symbols with activity:")
        for symbol in symbols[:5]:  # Show first 5
            print(f"   - {symbol}")
        
        # Get orders for first symbol
        if symbols:
            test_symbol = symbols[0]
            orders = get_orders_for_symbol(client, test_symbol)
            
            if orders:
                print(f"\n📋 Sample order from {test_symbol}:")
                sample_order = orders[0]
                for key, value in sample_order.items():
                    print(f"   {key}: {value}")
    
    print("\n✅ Demo completed!")

if __name__ == "__main__":
    main()