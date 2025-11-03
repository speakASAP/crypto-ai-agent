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

def test_connection():
    """Test database connection and verify data."""
    print("🔍 Testing database connection using application credentials...")
    print(f"   Environment: {settings.environment}")
    print(f"   Database URL: {'SET' if settings.database_url else 'NOT SET'}")
    
    if not settings.database_url:
        print("\n❌ DATABASE_URL is required for PostgreSQL connection")
        return False
    
    try:
        # Test connection with retry logic
        print("\n📡 Attempting PostgreSQL connection...")
        conn = connect_with_retry(max_retries=3, initial_delay=0.5, max_delay=2.0, is_startup=False)
        
        cur = conn.cursor()
        
        # Test basic connectivity
        print("✅ Connection established")
        
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
            print(f"✅ Users table exists with {user_count} users")
            
            # Get some sample data (without sensitive info)
            cur.execute("SELECT id, email, username FROM users LIMIT 5")
            users = cur.fetchall()
            if users:
                print("\n📊 Sample users (first 5):")
                for user in users:
                    print(f"   ID: {user[0]}, Email: {user[1]}, Username: {user[2]}")
        else:
            print("⚠️  Users table does not exist")
        
        cur.close()
        conn.close()
        
        print("\n✅ Database connection test PASSED")
        print("   ✓ Connection successful")
        print("   ✓ Database accessible")
        print("   ✓ Ready for blue/green deployment")
        return True
        
    except Exception as e:
        print(f"\n❌ Database connection test FAILED")
        print(f"   Error: {str(e)}")
        print(f"   Type: {type(e).__name__}")
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
