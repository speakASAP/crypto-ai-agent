#!/usr/bin/env python3
"""
Test script for the Portfolio Management feature.
This script tests the CRUD operations and calculations.
"""

import asyncio
import aiosqlite
import aiohttp
import pandas as pd
import os
import sys
from dotenv import load_dotenv

# Add utils directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))
from env_validator import EnvironmentValidator

# Load environment variables
load_dotenv()

# Initialize environment validator
env_validator = EnvironmentValidator()

DB_PATH = env_validator.get_validated_value("DB_PATH", "data/crypto_history.db")
BINANCE_API_URL = env_validator.get_validated_value("BINANCE_API_URL", "https://api.binance.com/api/v3/ticker/price")

async def test_portfolio_functions():
    """Test all portfolio management functions"""
    
    print("🧪 Testing Portfolio Management Functions")
    print("=" * 50)
    
    # Test 0: Environment Variable Validation
    print("\n0. Testing Environment Variable Validation...")
    try:
        from env_validator import get_env_validator
        
        # Test environment validation
        env_validator = get_env_validator()
        is_valid, errors, warnings = env_validator.validate_all()
        
        if is_valid:
            print("   ✅ Environment validation successful")
            if warnings:
                print(f"   ⚠️  {len(warnings)} warnings found")
        else:
            print(f"   ❌ Environment validation failed with {len(errors)} errors")
            
    except Exception as e:
        print(f"   ❌ Environment validation test failed: {e}")
    
    # Test 1: Database Connection
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Create portfolio table if it doesn't exist
            await db.execute("""
            CREATE TABLE IF NOT EXISTS portfolio (
                symbol TEXT PRIMARY KEY,
                amount REAL,
                price_buy REAL
            )
            """)
            await db.commit()
            print("✅ Database connection successful")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return
    
    # Test 1: Add coins to portfolio
    print("\n1. Testing Add Coin Function...")
    test_coins = [
        ("BTC", 0.5, 45000.0),
        ("ETH", 2.0, 3000.0),
        ("BNB", 10.0, 300.0)
    ]
    
    for symbol, amount, price in test_coins:
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("INSERT OR REPLACE INTO portfolio (symbol, amount, price_buy) VALUES (?, ?, ?)", 
                               (symbol, amount, price))
                await db.commit()
            print(f"   ✅ Added {symbol}: {amount} coins at ${price}")
        except Exception as e:
            print(f"   ❌ Failed to add {symbol}: {e}")
    
    # Test 2: Get portfolio data
    print("\n2. Testing Get Portfolio Function...")
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT * FROM portfolio")
            rows = await cursor.fetchall()
            portfolio_df = pd.DataFrame(rows, columns=["symbol", "amount", "price_buy"])
            print(f"   ✅ Retrieved {len(portfolio_df)} portfolio items")
            print("   Portfolio:")
            for _, row in portfolio_df.iterrows():
                print(f"     - {row['symbol']}: {row['amount']} coins @ ${row['price_buy']}")
    except Exception as e:
        print(f"   ❌ Failed to get portfolio: {e}")
        return
    
    # Test 3: Get current prices
    print("\n3. Testing Current Price Fetching...")
    try:
        symbols = portfolio_df['symbol'].tolist()
        symbol_list = [symbol.lower() for symbol in symbols]
        symbols_str = '","'.join(symbol_list)
        
        async with aiohttp.ClientSession() as session:
            url = f"{BINANCE_API_URL}?symbols=[\"{symbols_str}\"]"
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    current_prices = {}
                    for item in data:
                        current_prices[item['symbol'].upper()] = float(item['price'])
                    
                    print("   ✅ Current prices fetched:")
                    for symbol, price in current_prices.items():
                        print(f"     - {symbol}: ${price:,.2f}")
                else:
                    print(f"   ❌ Failed to fetch prices: HTTP {response.status}")
                    return
    except Exception as e:
        print(f"   ❌ Failed to fetch current prices: {e}")
        return
    
    # Test 4: Calculate portfolio metrics
    print("\n4. Testing Portfolio Calculations...")
    try:
        portfolio_data = portfolio_df.copy()
        
        # Calculate current values and P&L
        portfolio_data['current_price'] = portfolio_data['symbol'].map(current_prices).fillna(0)
        portfolio_data['current_value'] = portfolio_data['amount'] * portfolio_data['current_price']
        portfolio_data['cost_basis'] = portfolio_data['amount'] * portfolio_data['price_buy']
        portfolio_data['pnl'] = portfolio_data['current_value'] - portfolio_data['cost_basis']
        portfolio_data['pnl_percent'] = (portfolio_data['pnl'] / portfolio_data['cost_basis'] * 100).fillna(0)
        
        # Calculate totals
        total_value = portfolio_data['current_value'].sum()
        total_cost = portfolio_data['cost_basis'].sum()
        total_pnl = total_value - total_cost
        total_pnl_percent = (total_pnl / total_cost * 100) if total_cost > 0 else 0
        
        print("   ✅ Portfolio calculations completed:")
        print(f"     - Total Value: ${total_value:,.2f}")
        print(f"     - Total Cost: ${total_cost:,.2f}")
        print(f"     - Total P&L: ${total_pnl:,.2f} ({total_pnl_percent:.2f}%)")
        
        print("\n   Individual holdings:")
        for _, row in portfolio_data.iterrows():
            print(f"     - {row['symbol']}: ${row['current_value']:,.2f} (P&L: ${row['pnl']:,.2f}, {row['pnl_percent']:.2f}%)")
            
    except Exception as e:
        print(f"   ❌ Failed to calculate portfolio metrics: {e}")
    
    # Test 5: Update coin
    print("\n5. Testing Update Coin Function...")
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE portfolio SET amount = ?, price_buy = ? WHERE symbol = ?", 
                           (1.0, 50000.0, "BTC"))
            await db.commit()
        print("   ✅ Updated BTC: 1.0 coins @ $50,000")
    except Exception as e:
        print(f"   ❌ Failed to update coin: {e}")
    
    # Test 6: Delete coin
    print("\n6. Testing Delete Coin Function...")
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM portfolio WHERE symbol = ?", ("BNB",))
            await db.commit()
        print("   ✅ Deleted BNB from portfolio")
    except Exception as e:
        print(f"   ❌ Failed to delete coin: {e}")
    
    # Final portfolio check
    print("\n7. Final Portfolio Check...")
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT * FROM portfolio")
            rows = await cursor.fetchall()
            final_portfolio = pd.DataFrame(rows, columns=["symbol", "amount", "price_buy"])
            
            print(f"   ✅ Final portfolio has {len(final_portfolio)} items:")
            for _, row in final_portfolio.iterrows():
                print(f"     - {row['symbol']}: {row['amount']} coins @ ${row['price_buy']}")
                
    except Exception as e:
        print(f"   ❌ Failed to check final portfolio: {e}")
    
    print("\n🎉 Portfolio Management Test Completed!")

async def main():
    """Main test function"""
    await test_portfolio_functions()

if __name__ == "__main__":
    asyncio.run(main())
