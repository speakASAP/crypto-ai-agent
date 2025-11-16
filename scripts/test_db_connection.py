#!/usr/bin/env python3
"""
Test database connection using application credentials.
This script uses the same connection logic as the application.
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

logger = get_logger("scripts.test_db_connection")

def test_connection():
    """Test database connection and verify data."""
    logger.info("🔍 Testing database connection using application credentials...")
    logger.info(f"   Environment: {settings.environment}")
    logger.info(f"   Database URL: {'SET' if settings.database_url else 'NOT SET'}")
    
    if not settings.database_url:
        logger.error("❌ DATABASE_URL is required for PostgreSQL connection")
        return False
    
    try:
        # Test connection with retry logic
        logger.info("📡 Attempting PostgreSQL connection...")
        conn = connect_with_retry(max_retries=3, initial_delay=0.5, max_delay=2.0, is_startup=False)
        
        cur = conn.cursor()
        
        # Test basic connectivity
        logger.info("✅ Connection established")
        
        # Check if users table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'users'
            )
        """)
        table_exists = cur.fetchone()[0]
        
        if table_exists:
            # Count users
            cur.execute("SELECT COUNT(*) FROM users")
            user_count = cur.fetchone()[0]
            logger.info(f"✅ Users table exists with {user_count} users")
            
            # Get some sample data (without sensitive info)
            cur.execute("SELECT id, email, username FROM users LIMIT 5")
            users = cur.fetchall()
            if users:
                logger.info("📊 Sample users (first 5):")
                for user in users:
                    logger.info(f"   ID: {user[0]}, Email: {user[1]}, Username: {user[2]}")
        else:
            logger.warning("⚠️  Users table does not exist")
        
        cur.close()
        conn.close()
        
        logger.info("✅ Database connection test PASSED")
        logger.info("   ✓ Connection successful")
        logger.info("   ✓ Database accessible")
        logger.info("   ✓ Ready for blue/green deployment")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database connection test FAILED")
        logger.error(f"   Error: {str(e)}")
        logger.error(f"   Type: {type(e).__name__}", exc_info=True)
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
