#!/usr/bin/env python3
"""
Test the Binance import service directly
"""
import asyncio
import sys
import os

# Add the backend directory to the path
sys.path.append('/Users/sergiystashok/Documents/GitHub/crypto-ai-agent/backend')

from app.services.binance_import_service import BinanceImportService

async def test_service():
    print("🧪 Testing Binance Import Service Directly")
    print("=" * 50)
    
    try:
        service = BinanceImportService()
        
        print(f"API Key: {service.api_key[:10]}...{service.api_key[-10:]}")
        print(f"API Secret: {service.api_secret[:10]}...{service.api_secret[-10:]}")
        print(f"API URL: {service.api_url}")
        print()
        
        # Test connection
        print("🔌 Testing API connection...")
        result = await service.test_api_connection()
        print(f"Result: {result}")
        
        if result['success']:
            print("\n✅ Connection successful! Testing portfolio import...")
            
            # Test portfolio import
            import_result = await service.import_portfolio(1)  # Test with user ID 1
            print(f"Import result: {import_result}")
            
            if import_result['success']:
                print(f"\n🎉 Portfolio import successful!")
                print(f"Found {import_result['items_imported']} portfolio items")
                
                if import_result.get('portfolio_items'):
                    print("\n📋 Portfolio items:")
                    for i, item in enumerate(import_result['portfolio_items'][:5]):
                        print(f"  {i+1}. {item['symbol']}: {item['amount']} @ ${item['price_buy']:.2f}")
            else:
                print(f"❌ Portfolio import failed: {import_result['message']}")
        else:
            print(f"❌ Connection failed: {result['message']}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_service())
