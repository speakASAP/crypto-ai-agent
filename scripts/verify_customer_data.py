#!/usr/bin/env python3
"""
Verify database contains customer data and check specific user data.
This ensures the database is properly connected with real customer accounts.
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from dotenv import load_dotenv
load_dotenv()

from app.core.config import settings
from app.utils.db import connect_with_retry

try:
    from backend.app.utils.logger import get_logger
except ImportError:
    try:
        from app.utils.logger import get_logger
    except ImportError:
        from utils.logger import get_logger

logger = get_logger("scripts.verify_customer_data")

def verify_customer_data():
    """Verify database has customer data and show user details."""
    logger.info("=" * 70)
    logger.info("🔍 VERIFYING DATABASE CUSTOMER DATA")
    logger.info("=" * 70)
    
    try:
        # Connect to database
        logger.info("📡 Connecting to database...")
        conn = connect_with_retry(max_retries=3, initial_delay=0.5, max_delay=2.0, is_startup=False)
        cur = conn.cursor()
        logger.info("✅ Database connection established")
        
        if not settings.database_url:
            logger.error("❌ ERROR: DATABASE_URL is required for PostgreSQL connection")
            return False
        
        logger.info(f"   Database type: PostgreSQL")
        
        # Check if users table exists
        logger.info("📊 Checking users table...")
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'users'
            )
        """)
        table_exists = cur.fetchone()[0]
        
        if not table_exists:
            logger.error("❌ ERROR: Users table does not exist!")
            logger.error("   This is INCORRECT - database should have customer data")
            return False
        
        logger.info("✅ Users table exists")
        
        # Count total users
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]
        
        logger.info(f"👥 Customer Accounts: {total_users}")
        
        if total_users == 0:
            logger.error("❌ ERROR: Database has NO customer data!")
            logger.error("   This is INCORRECT - database should contain customer accounts")
            logger.error("   Database connection works but contains no customer data")
            return False
        
        logger.info(f"✅ Database contains {total_users} customer account(s)")
        
        # Get all users with details
        logger.info("=" * 70)
        logger.info("📋 ALL CUSTOMER ACCOUNTS:")
        logger.info("=" * 70)
        
        cur.execute("""
            SELECT id, email, username, full_name, preferred_currency, 
                   is_active, created_at
            FROM users
            ORDER BY id
        """)
        
        users = cur.fetchall()
        
        for user in users:
            user_id, email, username, full_name, currency, is_active, created_at = user
            status = "✅ Active" if is_active else "⚠️  Inactive"
            logger.info(f"   User ID: {user_id}")
            logger.info(f"   Email: {email}")
            logger.info(f"   Username: {username}")
            logger.info(f"   Full Name: {full_name or 'N/A'}")
            logger.info(f"   Currency: {currency}")
            logger.info(f"   Status: {status}")
            logger.info(f"   Created: {created_at}")
        
        # Check for your specific account (ssfskype@gmail.com from earlier test)
        logger.info("=" * 70)
        logger.info("🔍 SEARCHING FOR YOUR ACCOUNT (ssfskype@gmail.com):")
        logger.info("=" * 70)
        
        cur.execute("SELECT id, email, username, full_name, is_active FROM users WHERE email = %s", 
                   ("ssfskype@gmail.com",))
        
        your_account = cur.fetchone()
        
        if your_account:
            user_id, email, username, full_name, is_active = your_account
            logger.info(f"✅ YOUR ACCOUNT FOUND:")
            logger.info(f"   User ID: {user_id}")
            logger.info(f"   Email: {email}")
            logger.info(f"   Username: {username}")
            logger.info(f"   Full Name: {full_name or 'N/A'}")
            logger.info(f"   Status: {'✅ Active' if is_active else '⚠️  Inactive'}")
            
            # Check portfolio items for this user
            cur.execute("SELECT COUNT(*) FROM portfolio_items WHERE user_id = %s", (user_id,))
            portfolio_count = cur.fetchone()[0]
            logger.info(f"   Portfolio Items: {portfolio_count}")
            
            # Check alerts for this user
            cur.execute("SELECT COUNT(*) FROM alerts WHERE user_id = %s", (user_id,))
            alerts_count = cur.fetchone()[0]
            logger.info(f"   Alerts: {alerts_count}")
        else:
            logger.warning("⚠️  Account 'ssfskype@gmail.com' not found in database")
            logger.warning("   But database has customer data, so connection is working")
        
        # Check other important tables
        logger.info("=" * 70)
        logger.info("📊 DATABASE TABLES SUMMARY:")
        logger.info("=" * 70)
        
        tables_to_check = [
            ('portfolio_items', 'user_id'),
            ('alerts', 'user_id'),
            ('tracked_symbols', 'user_id'),
            ('alert_history', 'user_id'),
        ]
        
        for table_name, user_col in tables_to_check:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cur.fetchone()[0]
                logger.info(f"   {table_name}: {count} records")
            except Exception as e:
                logger.warning(f"   {table_name}: Table may not exist ({str(e)[:50]})")
        
        cur.close()
        conn.close()
        
        logger.info("=" * 70)
        logger.info("✅ DATABASE VERIFICATION COMPLETE")
        logger.info("=" * 70)
        logger.info(f"   ✓ Database connection: WORKING")
        logger.info(f"   ✓ Customer accounts: {total_users} users")
        logger.info(f"   ✓ Your data: {'FOUND' if your_account else 'Not found (but database has data)'}")
        logger.info(f"   ✓ Database ready: YES")
        logger.info("=" * 70)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ DATABASE VERIFICATION FAILED")
        logger.error(f"   Error: {str(e)}")
        logger.error(f"   Type: {type(e).__name__}", exc_info=True)
        return False

if __name__ == "__main__":
    success = verify_customer_data()
    sys.exit(0 if success else 1)
