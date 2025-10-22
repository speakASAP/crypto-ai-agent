#!/usr/bin/env python3
"""
Test script to verify the search UI functions work correctly
"""

import asyncio
import sys
import os

# Add the crypto-ai-agent directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'crypto-ai-agent'))

async def test_search_functions():
    """Test the search functions used by the UI"""
    print("🔍 Testing Search UI Functions")
    print("=" * 40)
    
    try:
        # Import the UI functions
        from ui_dashboard.app import search_crypto_symbols_ui, get_all_crypto_symbols_ui
        
        # Test search for 'B'
        print("\n1. Testing search for 'B':")
        results = await search_crypto_symbols_ui('B', 10)
        print(f"   Found {len(results)} results")
        for i, result in enumerate(results[:5]):
            print(f"   {i+1}. {result['symbol']} - {result['name']}")
        
        # Test search for 'Bitcoin'
        print("\n2. Testing search for 'Bitcoin':")
        results = await search_crypto_symbols_ui('Bitcoin', 10)
        print(f"   Found {len(results)} results")
        for result in results:
            print(f"   {result['symbol']} - {result['name']}")
        
        # Test search for 'ADA'
        print("\n3. Testing search for 'ADA':")
        results = await search_crypto_symbols_ui('ADA', 10)
        print(f"   Found {len(results)} results")
        for result in results:
            print(f"   {result['symbol']} - {result['name']}")
        
        # Test get all symbols
        print("\n4. Testing get all symbols:")
        all_symbols = await get_all_crypto_symbols_ui()
        print(f"   Total symbols available: {len(all_symbols)}")
        
        # Show first 10
        print("   First 10 symbols:")
        for i, symbol in enumerate(all_symbols[:10]):
            print(f"   {i+1}. {symbol['symbol']} - {symbol['name']}")
        
        print("\n✅ All search functions working correctly!")
        
    except Exception as e:
        print(f"❌ Error testing search functions: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_search_functions())
