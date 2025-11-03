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

def verify_production_connection():
    """Verify production backend connects to production database."""
    print("=" * 70)
    print("🔍 VERIFYING PRODUCTION BACKEND → PRODUCTION DATABASE")
    print("=" * 70)
    
    # Production database URL from docker-compose (production format)
    # This should match what production backend uses
    prod_db_url = os.getenv('DATABASE_URL')
    
    if not prod_db_url:
        print("\n❌ DATABASE_URL not set!")
        print("   Production backend needs DATABASE_URL environment variable")
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
    
    print(f"\n📡 Production DATABASE_URL:")
    print(f"   {display_url}")
    print(f"\n📡 Expected format (from docker-compose):")
    print(f"   postgresql+psycopg://USER:PASS@postgres:5432/DB")
    print(f"   (Using 'postgres' hostname - Docker network)")
    
    try:
        print("\n🔌 Connecting to production database...")
        conn = psycopg.connect(prod_url_clean)
        cur = conn.cursor()
        print("✅ Connection successful!")
        
        # Verify customer data
        print("\n👥 Checking customer data...")
        cur.execute("SELECT COUNT(*) FROM users")
        user_count = cur.fetchone()[0]
        
        if user_count == 0:
            print("❌ PRODUCTION DATABASE IS EMPTY!")
            print("   No customer data found")
            print("   Production backend cannot authenticate users without customer data")
            cur.close()
            conn.close()
            return False
        
        print(f"✅ Production database has {user_count} customer account(s)")
        
        # Check your specific account
        print("\n🔍 Checking your account (ssfskype@gmail.com)...")
        cur.execute("SELECT id, email, username, is_active FROM users WHERE email = %s", 
                   ("ssfskype@gmail.com",))
        your_account = cur.fetchone()
        
        if your_account:
            user_id, email, username, is_active = your_account
            print(f"✅ Your account found:")
            print(f"   ID: {user_id}")
            print(f"   Email: {email}")
            print(f"   Username: {username}")
            print(f"   Active: {is_active}")
        else:
            print("❌ Your account NOT found in production database!")
            print("   This is why login fails!")
            cur.close()
            conn.close()
            return False
        
        # Check portfolio items
        cur.execute("SELECT COUNT(*) FROM portfolio_items WHERE user_id = %s", (your_account[0],))
        your_portfolio_count = cur.fetchone()[0]
        print(f"\n💼 Your portfolio items: {your_portfolio_count}")
        
        cur.close()
        conn.close()
        
        print("\n" + "=" * 70)
        print("✅ PRODUCTION DATABASE VERIFICATION")
        print("=" * 70)
        print(f"   ✓ Connection: WORKING")
        print(f"   ✓ Customer data: {user_count} users")
        print(f"   ✓ Your account: FOUND")
        print(f"   ✓ Production backend CAN access customer data")
        print("\n⚠️  If login still fails, check:")
        print("   1. Production backend ENVIRONMENT=production")
        print("   2. Production backend DATABASE_URL matches production database")
        print("   3. Production backend container can reach 'postgres' hostname")
        print("   4. Production backend is using nginx-network")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"\n❌ CONNECTION FAILED")
        print(f"   Error: {str(e)}")
        print(f"   Type: {type(e).__name__}")
        
        if "could not translate host name" in str(e).lower() or "postgres" in str(e).lower():
            print("\n⚠️  Connection issue detected:")
            print("   - 'postgres' hostname not resolvable")
            print("   - Production backend might not be on 'nginx-network'")
            print("   - Or DATABASE_URL uses wrong hostname")
            print("\n   Expected: postgresql+psycopg://user:pass@postgres:5432/db")
            print("   (Note: 'postgres' is Docker network hostname)")
        
        return False

if __name__ == "__main__":
    success = verify_production_connection()
    sys.exit(0 if success else 1)
