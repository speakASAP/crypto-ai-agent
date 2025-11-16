#!/usr/bin/env python3
"""
Verify production backend can connect to production database with customer data.
This ensures production uses ONLY production database (not local).
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from dotenv import load_dotenv
load_dotenv()

import psycopg
from app.core.config import settings

try:
    from backend.app.utils.logger import get_logger
except ImportError:
    try:
        from app.utils.logger import get_logger
    except ImportError:
        from utils.logger import get_logger

logger = get_logger("scripts.verify_production_connection")

def verify_production_connection():
    """Verify production backend connects to production database."""
    logger.info("=" * 70)
    logger.info("🔍 VERIFYING PRODUCTION BACKEND → PRODUCTION DATABASE")
    logger.info("=" * 70)
    
    # Production database URL from docker-compose (production format)
    # This should match what production backend uses
    prod_db_url = os.getenv('DATABASE_URL')
    
    if not prod_db_url:
        logger.error("❌ DATABASE_URL not set!")
        logger.error("   Production backend needs DATABASE_URL environment variable")
        return False
    
    # Clean URL
    prod_url_clean = prod_db_url.replace("+psycopg", "") if "+psycopg" in prod_db_url else prod_db_url
    
    # Display (hide password)
    display_url = prod_db_url
    if '@' in display_url:
        parts = display_url.split('@')
        user_pass = parts[0].split('//')[1]
        if ':' in user_pass:
            user = user_pass.split(':')[0]
            display_url = display_url.replace(user_pass, f"{user}:***")
    
    logger.info(f"📡 Production DATABASE_URL:")
    logger.info(f"   {display_url}")
    logger.info(f"📡 Expected format (from docker-compose):")
    logger.info(f"   postgresql+psycopg://USER:PASS@postgres:5432/DB")
    logger.info(f"   (Using 'postgres' hostname - Docker network)")
    
    try:
        logger.info("🔌 Connecting to production database...")
        conn = psycopg.connect(prod_url_clean)
        cur = conn.cursor()
        logger.info("✅ Connection successful!")
        
        # Verify customer data
        logger.info("👥 Checking customer data...")
        cur.execute("SELECT COUNT(*) FROM users")
        user_count = cur.fetchone()[0]
        
        if user_count == 0:
            logger.error("❌ PRODUCTION DATABASE IS EMPTY!")
            logger.error("   No customer data found")
            logger.error("   Production backend cannot authenticate users without customer data")
            cur.close()
            conn.close()
            return False
        
        logger.info(f"✅ Production database has {user_count} customer account(s)")
        
        # Check your specific account
        logger.info("🔍 Checking your account (ssfskype@gmail.com)...")
        cur.execute("SELECT id, email, username, is_active FROM users WHERE email = %s", 
                   ("ssfskype@gmail.com",))
        your_account = cur.fetchone()
        
        if your_account:
            user_id, email, username, is_active = your_account
            logger.info(f"✅ Your account found:")
            logger.info(f"   ID: {user_id}")
            logger.info(f"   Email: {email}")
            logger.info(f"   Username: {username}")
            logger.info(f"   Active: {is_active}")
        else:
            logger.error("❌ Your account NOT found in production database!")
            logger.error("   This is why login fails!")
            cur.close()
            conn.close()
            return False
        
        # Check portfolio items
        cur.execute("SELECT COUNT(*) FROM portfolio_items WHERE user_id = %s", (your_account[0],))
        your_portfolio_count = cur.fetchone()[0]
        logger.info(f"💼 Your portfolio items: {your_portfolio_count}")
        
        cur.close()
        conn.close()
        
        logger.info("=" * 70)
        logger.info("✅ PRODUCTION DATABASE VERIFICATION")
        logger.info("=" * 70)
        logger.info(f"   ✓ Connection: WORKING")
        logger.info(f"   ✓ Customer data: {user_count} users")
        logger.info(f"   ✓ Your account: FOUND")
        logger.info(f"   ✓ Production backend CAN access customer data")
        logger.warning("⚠️  If login still fails, check:")
        logger.warning("   1. Production backend ENVIRONMENT=production")
        logger.warning("   2. Production backend DATABASE_URL matches production database")
        logger.warning("   3. Production backend container can reach 'postgres' hostname")
        logger.warning("   4. Production backend is using nginx-network")
        logger.info("=" * 70)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ CONNECTION FAILED")
        logger.error(f"   Error: {str(e)}")
        logger.error(f"   Type: {type(e).__name__}", exc_info=True)
        
        if "could not translate host name" in str(e).lower() or "postgres" in str(e).lower():
            logger.warning("⚠️  Connection issue detected:")
            logger.warning("   - 'postgres' hostname not resolvable")
            logger.warning("   - Production backend might not be on 'nginx-network'")
            logger.warning("   - Or DATABASE_URL uses wrong hostname")
            logger.warning("   Expected: postgresql+psycopg://user:pass@postgres:5432/db")
            logger.warning("   (Note: 'postgres' is Docker network hostname)")
        
        return False

if __name__ == "__main__":
    success = verify_production_connection()
    sys.exit(0 if success else 1)
