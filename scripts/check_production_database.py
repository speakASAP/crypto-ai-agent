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

def check_production_database():
    """Check production database status."""
    print("=" * 70)
    print("🔍 CHECKING PRODUCTION DATABASE")
    print("=" * 70)
    
    # Get production database URL
    prod_db_url = os.getenv('PRODUCTION_DATABASE_URL') or os.getenv('DATABASE_URL')
    
    if not prod_db_url:
        print("\n❌ ERROR: Production DATABASE_URL not found!")
        print("\nTo check production database, set one of these environment variables:")
        print("   export PRODUCTION_DATABASE_URL='postgresql+psycopg://user:pass@host:5432/db'")
        print("   OR")
        print("   export DATABASE_URL='postgresql+psycopg://user:pass@host:5432/db'")
        print("\nFor production server, the database should be accessible via:")
        print("   postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}")
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
    
    print(f"\n📡 Production Database URL:")
    print(f"   {display_url}")
    
    try:
        print("\n🔌 Connecting to production database...")
        conn = psycopg.connect(prod_url_clean)
        cur = conn.cursor()
        print("✅ Connection successful!")
        
        # Check if users table exists
        print("\n📊 Checking database schema...")
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'users'
            )
        """)
        table_exists = cur.fetchone()[0]
        
        if not table_exists:
            print("❌ Users table does NOT exist")
            print("   Production database is empty - needs schema initialization")
            cur.close()
            conn.close()
            return False
        
        print("✅ Users table exists")
        
        # Check user count
        cur.execute("SELECT COUNT(*) FROM users")
        user_count = cur.fetchone()[0]
        
        print(f"\n👥 Customer Accounts: {user_count}")
        
        if user_count == 0:
            print("\n❌ PRODUCTION DATABASE IS EMPTY!")
            print("   No customer data found")
            print("   You need to migrate customer data from local database")
            print("\n   Run: python3 scripts/migrate_to_production_db.py")
            cur.close()
            conn.close()
            return False
        
        print(f"✅ Production database has {user_count} customer account(s)")
        
        # List users
        print("\n📋 Customer Accounts in Production:")
        cur.execute("""
            SELECT id, email, username, full_name, is_active, created_at
            FROM users
            ORDER BY id
        """)
        users = cur.fetchall()
        
        for user in users:
            user_id, email, username, full_name, is_active, created_at = user
            status = "✅ Active" if is_active else "⚠️  Inactive"
            print(f"   ID {user_id}: {email} ({username}) - {status}")
        
        # Check portfolio items
        cur.execute("SELECT COUNT(*) FROM portfolio_items")
        portfolio_count = cur.fetchone()[0]
        print(f"\n💼 Portfolio Items: {portfolio_count}")
        
        cur.close()
        conn.close()
        
        print("\n" + "=" * 70)
        print("✅ PRODUCTION DATABASE CHECK COMPLETE")
        print("=" * 70)
        print(f"   ✓ Connection: WORKING")
        print(f"   ✓ Customer accounts: {user_count} users")
        print(f"   ✓ Portfolio items: {portfolio_count} items")
        print(f"   ✓ Ready for production use: YES")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"\n❌ PRODUCTION DATABASE CHECK FAILED")
        print(f"   Error: {str(e)}")
        print(f"   Type: {type(e).__name__}")
        
        if "connection" in str(e).lower() or "connect" in str(e).lower():
            print("\n⚠️  Connection failed. Possible issues:")
            print("   1. Database server is not running")
            print("   2. Incorrect DATABASE_URL")
            print("   3. Network connectivity issue")
            print("   4. Database credentials are wrong")
            print("\n   For production, ensure:")
            print("   - PostgreSQL container is running")
            print("   - DATABASE_URL points to correct database")
            print("   - Network 'nginx-network' is accessible")
        
        return False

if __name__ == "__main__":
    success = check_production_database()
    sys.exit(0 if success else 1)
