#!/usr/bin/env python3
"""
Test database connection and access YOUR specific data.
This verifies the application can connect and retrieve your customer data.
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from dotenv import load_dotenv
load_dotenv()

from app.core.config import settings
from app.dependencies.auth import get_db_connection
from app.utils.db import normalize_placeholders

def test_your_data_access():
    """Test accessing your specific account data."""
    print("=" * 70)
    print("🔐 TESTING DATABASE CONNECTION WITH YOUR DATA")
    print("=" * 70)
    
    YOUR_EMAIL = "ssfskype@gmail.com"
    
    try:
        print(f"\n📡 Connecting to database using application get_db_connection()...")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        use_postgres = settings.environment.lower() == "production" or bool(settings.database_url)
        print(f"✅ Connected (using same method as application)")
        print(f"   Database type: {'PostgreSQL' if use_postgres else 'SQLite'}")
        
        # Get your user account
        print(f"\n🔍 Retrieving your account: {YOUR_EMAIL}")
        sql = normalize_placeholders(
            "SELECT id, email, username, full_name, preferred_currency, is_active, created_at FROM users WHERE email = ?",
            use_postgres
        )
        cursor.execute(sql, (YOUR_EMAIL,))
        user = cursor.fetchone()
        
        if not user:
            print(f"❌ ERROR: Your account not found!")
            return False
        
        user_id, email, username, full_name, currency, is_active, created_at = user
        print(f"✅ YOUR ACCOUNT RETRIEVED:")
        print(f"   User ID: {user_id}")
        print(f"   Email: {email}")
        print(f"   Username: {username}")
        print(f"   Full Name: {full_name}")
        print(f"   Currency: {currency}")
        print(f"   Active: {is_active}")
        
        # Get your portfolio items
        print(f"\n💼 Retrieving your portfolio items...")
        sql = normalize_placeholders(
            "SELECT id, symbol, amount, price_buy, base_currency FROM portfolio_items WHERE user_id = ?",
            use_postgres
        )
        cursor.execute(sql, (user_id,))
        portfolio_items = cursor.fetchall()
        
        print(f"✅ Found {len(portfolio_items)} portfolio item(s):")
        for item in portfolio_items:
            item_id, symbol, amount, price_buy, currency = item
            print(f"   - {symbol}: {amount} @ {price_buy} {currency}")
        
        # Get your alerts
        print(f"\n🚨 Retrieving your alerts...")
        sql = normalize_placeholders(
            "SELECT id, symbol, threshold_price, alert_type FROM alerts WHERE user_id = ?",
            use_postgres
        )
        cursor.execute(sql, (user_id,))
        alerts = cursor.fetchall()
        
        print(f"✅ Found {len(alerts)} alert(s)")
        for alert in alerts:
            alert_id, symbol, threshold, alert_type = alert
            print(f"   - {symbol}: {alert_type} @ {threshold}")
        
        # Test a write operation (just select, not modifying)
        print(f"\n✍️  Testing database write capability (read-only check)...")
        sql = normalize_placeholders(
            "SELECT COUNT(*) FROM users WHERE user_id = ?",
            use_postgres
        )
        # This is actually a read, but tests the connection works for queries
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        print(f"✅ Database is readable and queryable")
        print(f"   Total users in database: {total_users}")
        
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 70)
        print("✅ DATABASE CONNECTION TEST WITH YOUR DATA: SUCCESS")
        print("=" * 70)
        print(f"   ✓ Connection: WORKING")
        print(f"   ✓ Your account: ACCESSIBLE")
        print(f"   ✓ Your portfolio: {len(portfolio_items)} items")
        print(f"   ✓ Your alerts: {len(alerts)} alerts")
        print(f"   ✓ Database queries: WORKING")
        print(f"   ✓ Application can access your data: YES")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"\n❌ DATABASE CONNECTION TEST FAILED")
        print(f"   Error: {str(e)}")
        print(f"   Type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_your_data_access()
    sys.exit(0 if success else 1)

