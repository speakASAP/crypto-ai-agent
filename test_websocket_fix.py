#!/usr/bin/env python3.12
"""
Test script to verify WebSocket connection fix
"""

import asyncio
import sys
import os

# Add the crypto-ai-agent directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'crypto-ai-agent'))

from agent_advanced import AsyncClient, BinanceSocketManager, create_ssl_context, get_global_connector
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_websocket_connection():
    """Test WebSocket connection with the fixed code"""
    print("Testing WebSocket connection fix...")
    
    try:
        # Initialize Binance client
        ssl_context = create_ssl_context()
        connector = get_global_connector()
        
        session_params = {'connector': connector}
        client = await AsyncClient.create(
            os.getenv('BINANCE_API_KEY'), 
            os.getenv('BINANCE_API_SECRET'),
            session_params=session_params
        )
        
        bsm = BinanceSocketManager(client)
        print("✅ Binance client initialized successfully")
        
        # Test WebSocket connection for a single symbol
        def test_callback(msg):
            print(f"✅ Received WebSocket message: {msg}")
        
        # Test the fixed WebSocket connection method
        conn_key = bsm.start_symbol_ticker_socket('btc', test_callback)
        
        if conn_key:
            print(f"✅ WebSocket connection established successfully with key: {conn_key}")
            
            # Wait a bit to receive some messages
            print("Waiting for WebSocket messages...")
            await asyncio.sleep(5)
            
            # Stop the connection
            bsm.stop_socket(conn_key)
            print("✅ WebSocket connection stopped successfully")
            
        else:
            print("❌ Failed to establish WebSocket connection")
            
        await client.close_connection()
        print("✅ Test completed successfully - WebSocket fix is working!")
        
    except Exception as e:
        print(f"❌ Error during WebSocket test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_websocket_connection())
