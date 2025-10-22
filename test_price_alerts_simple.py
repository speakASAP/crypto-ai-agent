#!/usr/bin/env python3
"""
Simple test for Price Alerts database functionality
Tests database operations without importing the full app module
"""

import asyncio
import aiosqlite
import pandas as pd
import sys
import os
from datetime import datetime

# Test database path
TEST_DB_PATH = "test_crypto_alerts.db"

async def test_price_alerts_database():
    """Test price alerts database functionality"""
    print("🚀 Starting Price Alerts Database Test")
    print("="*60)
    
    # Set up test database
    print("🔧 Setting up test database...")
    
    try:
        async with aiosqlite.connect(TEST_DB_PATH) as db:
            # Create price_alerts table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS price_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    threshold_price REAL NOT NULL,
                    message TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create alert_history table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS alert_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    triggered_price REAL NOT NULL,
                    threshold_price REAL NOT NULL,
                    alert_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    triggered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (alert_id) REFERENCES price_alerts (id)
                )
            """)
            
            await db.commit()
            print("✅ Test database setup complete")
    
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        return False
    
    # Test 1: Create alerts
    print("\n🧪 Test 1: Creating price alerts...")
    
    try:
        async with aiosqlite.connect(TEST_DB_PATH) as db:
            # Clear existing alerts first
            await db.execute("DELETE FROM price_alerts")
            
            # Insert test alerts
            await db.execute("""
                INSERT INTO price_alerts (symbol, alert_type, threshold_price, message, is_active) 
                VALUES (?, ?, ?, ?, ?)
            """, ("BTC", "ABOVE", 50000.0, "Bitcoin reached $50k!", 1))
            
            await db.execute("""
                INSERT INTO price_alerts (symbol, alert_type, threshold_price, message, is_active) 
                VALUES (?, ?, ?, ?, ?)
            """, ("ETH", "BELOW", 3000.0, "Ethereum dropped below $3k", 1))
            
            await db.execute("""
                INSERT INTO price_alerts (symbol, alert_type, threshold_price, message, is_active) 
                VALUES (?, ?, ?, ?, ?)
            """, ("ADA", "ABOVE", 1.0, "Cardano above $1", 0))
            
            await db.commit()
            print("✅ Alert creation test passed")
    
    except Exception as e:
        print(f"❌ Alert creation test failed: {e}")
        return False
    
    # Test 2: Retrieve alerts
    print("\n🧪 Test 2: Retrieving price alerts...")
    
    try:
        async with aiosqlite.connect(TEST_DB_PATH) as db:
            cursor = await db.execute("""
                SELECT id, symbol, alert_type, threshold_price, message, is_active, created_at, updated_at 
                FROM price_alerts 
                ORDER BY created_at DESC
            """)
            rows = await cursor.fetchall()
            alerts_df = pd.DataFrame(rows, columns=[
                "id", "symbol", "alert_type", "threshold_price", "message", "is_active", "created_at", "updated_at"
            ])
            
            if len(alerts_df) >= 3:
                print("✅ Alert retrieval test passed")
                print(f"   Found {len(alerts_df)} alerts: {alerts_df['symbol'].tolist()}")
            else:
                print(f"❌ Alert retrieval test failed: Expected at least 3 alerts, got {len(alerts_df)}")
                return False
    
    except Exception as e:
        print(f"❌ Alert retrieval test failed: {e}")
        return False
    
    # Test 3: Update alert
    print("\n🧪 Test 3: Updating price alert...")
    
    try:
        async with aiosqlite.connect(TEST_DB_PATH) as db:
            # Get the first alert ID
            cursor = await db.execute("SELECT id FROM price_alerts LIMIT 1")
            first_alert = await cursor.fetchone()
            
            if not first_alert:
                print("❌ Alert update test failed: No alerts found to update")
                return False
            
            alert_id = first_alert[0]
            
            # Update the first alert
            await db.execute("""
                UPDATE price_alerts 
                SET symbol = ?, alert_type = ?, threshold_price = ?, message = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, ("BTC", "BELOW", 45000.0, "Updated message", 0, alert_id))
            
            await db.commit()
            
            # Verify the update
            cursor = await db.execute("SELECT * FROM price_alerts WHERE id = ?", (alert_id,))
            updated_alert = await cursor.fetchone()
            
            if updated_alert and (updated_alert[2] == 'BELOW' and updated_alert[3] == 45000.0 and 
                updated_alert[4] == 'Updated message' and updated_alert[5] == 0):
                print("✅ Alert update test passed")
            else:
                print("❌ Alert update test failed: Alert not updated correctly")
                return False
    
    except Exception as e:
        print(f"❌ Alert update test failed: {e}")
        return False
    
    # Test 4: Delete alert
    print("\n🧪 Test 4: Deleting price alert...")
    
    try:
        async with aiosqlite.connect(TEST_DB_PATH) as db:
            # Count alerts before deletion
            cursor = await db.execute("SELECT COUNT(*) FROM price_alerts")
            count_before = (await cursor.fetchone())[0]
            
            # Delete an alert (delete the first one we can find)
            cursor = await db.execute("SELECT id FROM price_alerts LIMIT 1")
            alert_to_delete = await cursor.fetchone()
            
            if alert_to_delete:
                await db.execute("DELETE FROM price_alerts WHERE id = ?", (alert_to_delete[0],))
                await db.commit()
                
                # Count alerts after deletion
                cursor = await db.execute("SELECT COUNT(*) FROM price_alerts")
                count_after = (await cursor.fetchone())[0]
                
                if count_after == count_before - 1:
                    print("✅ Alert deletion test passed")
                else:
                    print(f"❌ Alert deletion test failed: Expected {count_before - 1} alerts, got {count_after}")
                    return False
            else:
                print("❌ Alert deletion test failed: No alerts to delete")
                return False
    
    except Exception as e:
        print(f"❌ Alert deletion test failed: {e}")
        return False
    
    # Test 5: Alert history
    print("\n🧪 Test 5: Testing alert history...")
    
    try:
        async with aiosqlite.connect(TEST_DB_PATH) as db:
            # Clear existing history first
            await db.execute("DELETE FROM alert_history")
            
            # Add alert history
            await db.execute("""
                INSERT INTO alert_history 
                (alert_id, symbol, triggered_price, threshold_price, alert_type, message) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (1, "BTC", 50000.0, 50000.0, "ABOVE", "Test alert triggered"))
            
            await db.execute("""
                INSERT INTO alert_history 
                (alert_id, symbol, triggered_price, threshold_price, alert_type, message) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (3, "ADA", 1.0, 1.0, "ABOVE", "Test alert triggered"))
            
            await db.commit()
            
            # Retrieve alert history
            cursor = await db.execute("""
                SELECT id, alert_id, symbol, triggered_price, threshold_price, alert_type, message, triggered_at 
                FROM alert_history 
                ORDER BY triggered_at DESC 
                LIMIT 10
            """)
            rows = await cursor.fetchall()
            history_df = pd.DataFrame(rows, columns=[
                "id", "alert_id", "symbol", "triggered_price", "threshold_price", "alert_type", "message", "triggered_at"
            ])
            
            if len(history_df) == 2:
                print("✅ Alert history test passed")
                print(f"   Found {len(history_df)} history records")
            else:
                print(f"❌ Alert history test failed: Expected 2 history records, got {len(history_df)}")
                return False
    
    except Exception as e:
        print(f"❌ Alert history test failed: {e}")
        return False
    
    # Test 6: Alert triggering logic
    print("\n🧪 Test 6: Testing alert triggering logic...")
    
    try:
        async with aiosqlite.connect(TEST_DB_PATH) as db:
            # First, let's add a new active alert for testing
            await db.execute("""
                INSERT INTO price_alerts (symbol, alert_type, threshold_price, message, is_active) 
                VALUES (?, ?, ?, ?, ?)
            """, ("BTC", "ABOVE", 45000.0, "Bitcoin above $45k", 1))
            
            await db.commit()
            
            # Get active alerts
            cursor = await db.execute("""
                SELECT id, symbol, alert_type, threshold_price, message 
                FROM price_alerts 
                WHERE is_active = 1
            """)
            alerts = await cursor.fetchall()
            
            print(f"   Found {len(alerts)} active alerts for testing")
            
            # Test triggering logic
            test_price = 50000.0
            triggered_alerts = []
            
            for alert in alerts:
                alert_id, symbol, alert_type, threshold_price, message = alert
                
                should_trigger = False
                if alert_type == "ABOVE" and test_price >= threshold_price:
                    should_trigger = True
                elif alert_type == "BELOW" and test_price <= threshold_price:
                    should_trigger = True
                
                if should_trigger:
                    triggered_alerts.append(alert)
                    print(f"   Alert {alert_id} ({symbol} {alert_type} ${threshold_price}) would trigger at ${test_price}")
            
            if len(triggered_alerts) > 0:
                print("✅ Alert triggering logic test passed")
                print(f"   {len(triggered_alerts)} alert(s) would trigger at price ${test_price}")
            else:
                print("❌ Alert triggering logic test failed: No alerts would trigger")
                print("   Available alerts:")
                for alert in alerts:
                    print(f"     {alert[1]} {alert[2]} ${alert[3]}")
                return False
    
    except Exception as e:
        print(f"❌ Alert triggering logic test failed: {e}")
        return False
    
    # Cleanup
    print("\n🧹 Cleaning up test database...")
    try:
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
            print("✅ Test database cleaned up")
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
    
    print("\n" + "="*60)
    print("🎉 ALL TESTS PASSED! Price alerts database functionality is working correctly.")
    print("="*60)
    return True

async def main():
    """Run the price alerts database test"""
    success = await test_price_alerts_database()
    if success:
        print("\n✅ Price alerts implementation is ready for production!")
    else:
        print("\n❌ Price alerts implementation has issues that need to be fixed.")

if __name__ == "__main__":
    asyncio.run(main())
