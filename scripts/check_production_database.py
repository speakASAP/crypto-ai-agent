#!/usr/bin/env python3
"""
Check production database connection and verify if it has customer data.
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from dotenv import load_dotenv
load_dotenv()

import psycopg

try:
    from backend.app.utils.logger import get_logger
except ImportError:
    try:
        from app.utils.logger import get_logger
    except ImportError:
        from utils.logger import get_logger

logger = get_logger("scripts.check_production_database")

def check_production_database():
    """Check production database status."""
    logger.info("=" * 70)
    logger.info("🔍 CHECKING PRODUCTION DATABASE")
    logger.info("=" * 70)
    
    # Get production database URL
    prod_db_url = os.getenv('PRODUCTION_DATABASE_URL') or os.getenv('DATABASE_URL')
    
    if not prod_db_url:
        logger.error("❌ ERROR: Production DATABASE_URL not found!")
        logger.info("To check production database, set one of these environment variables:")
        logger.info("   export PRODUCTION_DATABASE_URL='postgresql+psycopg://user:pass@host:5432/db'")
        logger.info("   OR")
        logger.info("   export DATABASE_URL='postgresql+psycopg://user:pass@host:5432/db'")
        logger.info("For production server, the database should be accessible via:")
        logger.info("   postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}")
        return False
    
    # Clean URL (remove +psycopg if present)
    prod_url_clean = prod_db_url.replace("+psycopg", "") if "+psycopg" in prod_db_url else prod_db_url
    
    # Hide password in display
    display_url = prod_db_url
    if '@' in display_url:
        parts = display_url.split('@')
        user_pass = parts[0].split('//')[1]
        if ':' in user_pass:
            user = user_pass.split(':')[0]
            display_url = display_url.replace(user_pass, f"{user}:***")
    
    logger.info(f"📡 Production Database URL:")
    logger.info(f"   {display_url}")
    
    try:
        logger.info("🔌 Connecting to production database...")
        conn = psycopg.connect(prod_url_clean)
        cur = conn.cursor()
        logger.info("✅ Connection successful!")
        
        # Check if users table exists
        logger.info("📊 Checking database schema...")
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'users'
            )
        """)
        table_exists = cur.fetchone()[0]
        
        if not table_exists:
            logger.error("❌ Users table does NOT exist")
            logger.error("   Production database is empty - needs schema initialization")
            cur.close()
            conn.close()
            return False
        
        logger.info("✅ Users table exists")
        
        # Check user count
        cur.execute("SELECT COUNT(*) FROM users")
        user_count = cur.fetchone()[0]
        
        logger.info(f"👥 Customer Accounts: {user_count}")
        
        if user_count == 0:
            logger.error("❌ PRODUCTION DATABASE IS EMPTY!")
            logger.error("   No customer data found")
            logger.error("   You need to migrate customer data from local database")
            logger.info("   Run: python3 scripts/migrate_to_production_db.py")
            cur.close()
            conn.close()
            return False
        
        logger.info(f"✅ Production database has {user_count} customer account(s)")
        
        # List users
        logger.info("📋 Customer Accounts in Production:")
        cur.execute("""
            SELECT id, email, username, full_name, is_active, created_at
            FROM users
            ORDER BY id
        """)
        users = cur.fetchall()
        
        for user in users:
            user_id, email, username, full_name, is_active, created_at = user
            status = "✅ Active" if is_active else "⚠️  Inactive"
            logger.info(f"   ID {user_id}: {email} ({username}) - {status}")
        
        # Check portfolio items
        cur.execute("SELECT COUNT(*) FROM portfolio_items")
        portfolio_count = cur.fetchone()[0]
        logger.info(f"💼 Portfolio Items: {portfolio_count}")
        
        cur.close()
        conn.close()
        
        logger.info("=" * 70)
        logger.info("✅ PRODUCTION DATABASE CHECK COMPLETE")
        logger.info("=" * 70)
        logger.info(f"   ✓ Connection: WORKING")
        logger.info(f"   ✓ Customer accounts: {user_count} users")
        logger.info(f"   ✓ Portfolio items: {portfolio_count} items")
        logger.info(f"   ✓ Ready for production use: YES")
        logger.info("=" * 70)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ PRODUCTION DATABASE CHECK FAILED")
        logger.error(f"   Error: {str(e)}")
        logger.error(f"   Type: {type(e).__name__}", exc_info=True)
        
        if "connection" in str(e).lower() or "connect" in str(e).lower():
            logger.warning("⚠️  Connection failed. Possible issues:")
            logger.warning("   1. Database server is not running")
            logger.warning("   2. Incorrect DATABASE_URL")
            logger.warning("   3. Network connectivity issue")
            logger.warning("   4. Database credentials are wrong")
            logger.info("   For production, ensure:")
            logger.info("   - PostgreSQL container is running")
            logger.info("   - DATABASE_URL points to correct database")
            logger.info("   - Network 'nginx-network' is accessible")
        
        return False

if __name__ == "__main__":
    success = check_production_database()
    sys.exit(0 if success else 1)
