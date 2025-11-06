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

try:
    from backend.app.utils.logger import get_logger
except ImportError:
    try:
        from app.utils.logger import get_logger
    except ImportError:
        from utils.logger import get_logger

logger = get_logger("scripts.test_your_data_connection")

def test_your_data_access():
    """Test accessing your specific account data."""
    logger.info("=" * 70)
    logger.info("🔐 TESTING DATABASE CONNECTION WITH YOUR DATA")
    logger.info("=" * 70)
    
    YOUR_EMAIL = "ssfskype@gmail.com"
    
    try:
        logger.info(f"📡 Connecting to database using application get_db_connection()...")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if not settings.database_url:
            logger.error("❌ ERROR: DATABASE_URL is required for PostgreSQL connection")
            return False
        
        logger.info(f"✅ Connected (using same method as application)")
        logger.info(f"   Database type: PostgreSQL")
        
        # Get your user account
        logger.info(f"🔍 Retrieving your account: {YOUR_EMAIL}")
        sql = normalize_placeholders(
            "SELECT id, email, username, full_name, preferred_currency, is_active, created_at FROM users WHERE email = %s"
        )
        cursor.execute(sql, (YOUR_EMAIL,))
        user = cursor.fetchone()
        
        if not user:
            logger.error(f"❌ ERROR: Your account not found!")
            return False
        
        user_id, email, username, full_name, currency, is_active, created_at = user
        logger.info(f"✅ YOUR ACCOUNT RETRIEVED:")
        logger.info(f"   User ID: {user_id}")
        logger.info(f"   Email: {email}")
        logger.info(f"   Username: {username}")
        logger.info(f"   Full Name: {full_name}")
        logger.info(f"   Currency: {currency}")
        logger.info(f"   Active: {is_active}")
        
        # Get your portfolio items
        logger.info(f"💼 Retrieving your portfolio items...")
        sql = normalize_placeholders(
            "SELECT id, symbol, amount, price_buy, base_currency FROM portfolio_items WHERE user_id = %s"
        )
        cursor.execute(sql, (user_id,))
        portfolio_items = cursor.fetchall()
        
        logger.info(f"✅ Found {len(portfolio_items)} portfolio item(s):")
        for item in portfolio_items:
            item_id, symbol, amount, price_buy, currency = item
            logger.info(f"   - {symbol}: {amount} @ {price_buy} {currency}")
        
        # Get your alerts
        logger.info(f"🚨 Retrieving your alerts...")
        sql = normalize_placeholders(
            "SELECT id, symbol, threshold_price, alert_type FROM alerts WHERE user_id = %s"
        )
        cursor.execute(sql, (user_id,))
        alerts = cursor.fetchall()
        
        logger.info(f"✅ Found {len(alerts)} alert(s)")
        for alert in alerts:
            alert_id, symbol, threshold, alert_type = alert
            logger.info(f"   - {symbol}: {alert_type} @ {threshold}")
        
        # Test a write operation (just select, not modifying)
        logger.info(f"✍️  Testing database write capability (read-only check)...")
        # This is actually a read, but tests the connection works for queries
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        logger.info(f"✅ Database is readable and queryable")
        logger.info(f"   Total users in database: {total_users}")
        
        cursor.close()
        conn.close()
        
        logger.info("=" * 70)
        logger.info("✅ DATABASE CONNECTION TEST WITH YOUR DATA: SUCCESS")
        logger.info("=" * 70)
        logger.info(f"   ✓ Connection: WORKING")
        logger.info(f"   ✓ Your account: ACCESSIBLE")
        logger.info(f"   ✓ Your portfolio: {len(portfolio_items)} items")
        logger.info(f"   ✓ Your alerts: {len(alerts)} alerts")
        logger.info(f"   ✓ Database queries: WORKING")
        logger.info(f"   ✓ Application can access your data: YES")
        logger.info("=" * 70)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ DATABASE CONNECTION TEST FAILED")
        logger.error(f"   Error: {str(e)}")
        logger.error(f"   Type: {type(e).__name__}", exc_info=True)
        return False

if __name__ == "__main__":
    success = test_your_data_access()
    sys.exit(0 if success else 1)
