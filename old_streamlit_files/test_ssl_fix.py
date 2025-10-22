#!/usr/bin/env python3
"""
Test script to verify SSL configuration works with Binance library
"""

import ssl
import asyncio
import aiohttp
from binance import AsyncClient

# Disable SSL verification globally
ssl._create_default_https_context = ssl._create_unverified_context

# Patch aiohttp to use SSL-disabled connector by default
original_connector = aiohttp.TCPConnector

class SSLDisabledConnector(original_connector):
    def __init__(self, *args, **kwargs):
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        kwargs['ssl'] = ssl_context
        super().__init__(*args, **kwargs)

aiohttp.TCPConnector = SSLDisabledConnector

async def test_binance_connection():
    """Test Binance connection with SSL disabled"""
    try:
        # Test with aiohttp directly
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get('https://api.binance.com/api/v3/ping') as response:
                print(f"Direct aiohttp test: {response.status}")
        
        # Test with Binance library
        client = await AsyncClient.create("test", "test")
        result = await client.ping()
        print(f"Binance library test: {result}")
        
        return True
    except Exception as e:
        print(f"Test failed: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_binance_connection())
    print(f"SSL test result: {result}")
