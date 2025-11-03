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

def verify_customer_data():
    """Verify database has customer data and show user details."""
    print("=" * 70)
    print("🔍 VERIFYING DATABASE CUSTOMER DATA")
    print("=" * 70)
    
    try:
        # Connect to database
        print("\n📡 Connecting to database...")
        conn = connect_with_retry(max_retries=3, initial_delay=0.5, max_delay=2.0, is_startup=False)
        cur = conn.cursor()
        print("✅ Database connection established")
        
        # Check if using PostgreSQL
        use_postgres = settings.environment.lower() == "production" or bool(settings.database_url)
        db_type = "PostgreSQL" if use_postgres else "SQLite"
        print(f"   Database type: {db_type}")
        
        # Check if users table exists
        print("\n📊 Checking users table...")
        if use_postgres:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'users'
                )
            """)
            table_exists = cur.fetchone()[0]
        else:
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            table_exists = cur.fetchone() is not None
        
        if not table_exists:
            print("❌ ERROR: Users table does not exist!")
            print("   This is INCORRECT - database should have customer data")
            return False
        
        print("✅ Users table exists")
        
        # Count total users
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]
        
        print(f"\n👥 Customer Accounts: {total_users}")
        
        if total_users == 0:
            print("\n❌ ERROR: Database has NO customer data!")
            print("   This is INCORRECT - database should contain customer accounts")
            print("   Database connection works but contains no customer data")
            return False
        
        print(f"✅ Database contains {total_users} customer account(s)")
        
        # Get all users with details
        print("\n" + "=" * 70)
        print("📋 ALL CUSTOMER ACCOUNTS:")
        print("=" * 70)
        
        if use_postgres:
            cur.execute("""
                SELECT id, email, username, full_name, preferred_currency, 
                       is_active, created_at
                FROM users
                ORDER BY id
            """)
        else:
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
            print(f"\n   User ID: {user_id}")
            print(f"   Email: {email}")
            print(f"   Username: {username}")
            print(f"   Full Name: {full_name or 'N/A'}")
            print(f"   Currency: {currency}")
            print(f"   Status: {status}")
            print(f"   Created: {created_at}")
        
        # Check for your specific account (ssfskype@gmail.com from earlier test)
        print("\n" + "=" * 70)
        print("🔍 SEARCHING FOR YOUR ACCOUNT (ssfskype@gmail.com):")
        print("=" * 70)
        
        if use_postgres:
            cur.execute("SELECT id, email, username, full_name, is_active FROM users WHERE email = %s", 
                       ("ssfskype@gmail.com",))
        else:
            cur.execute("SELECT id, email, username, full_name, is_active FROM users WHERE email = ?", 
                       ("ssfskype@gmail.com",))
        
        your_account = cur.fetchone()
        
        if your_account:
            user_id, email, username, full_name, is_active = your_account
            print(f"\n✅ YOUR ACCOUNT FOUND:")
            print(f"   User ID: {user_id}")
            print(f"   Email: {email}")
            print(f"   Username: {username}")
            print(f"   Full Name: {full_name or 'N/A'}")
            print(f"   Status: {'✅ Active' if is_active else '⚠️  Inactive'}")
            
            # Check portfolio items for this user
            if use_postgres:
                cur.execute("SELECT COUNT(*) FROM portfolio_items WHERE user_id = %s", (user_id,))
            else:
                cur.execute("SELECT COUNT(*) FROM portfolio_items WHERE user_id = ?", (user_id,))
            portfolio_count = cur.fetchone()[0]
            print(f"   Portfolio Items: {portfolio_count}")
            
            # Check alerts for this user
            if use_postgres:
                cur.execute("SELECT COUNT(*) FROM alerts WHERE user_id = %s", (user_id,))
            else:
                cur.execute("SELECT COUNT(*) FROM alerts WHERE user_id = ?", (user_id,))
            alerts_count = cur.fetchone()[0]
            print(f"   Alerts: {alerts_count}")
        else:
            print("\n⚠️  Account 'ssfskype@gmail.com' not found in database")
            print("   But database has customer data, so connection is working")
        
        # Check other important tables
        print("\n" + "=" * 70)
        print("📊 DATABASE TABLES SUMMARY:")
        print("=" * 70)
        
        tables_to_check = [
            ('portfolio_items', 'user_id'),
            ('alerts', 'user_id'),
            ('tracked_symbols', 'user_id'),
            ('alert_history', 'user_id'),
        ]
        
        for table_name, user_col in tables_to_check:
            try:
                if use_postgres:
                    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                else:
                    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cur.fetchone()[0]
                print(f"   {table_name}: {count} records")
            except Exception as e:
                print(f"   {table_name}: Table may not exist ({str(e)[:50]})")
        
        cur.close()
        conn.close()
        
        print("\n" + "=" * 70)
        print("✅ DATABASE VERIFICATION COMPLETE")
        print("=" * 70)
        print(f"   ✓ Database connection: WORKING")
        print(f"   ✓ Customer accounts: {total_users} users")
        print(f"   ✓ Your data: {'FOUND' if your_account else 'Not found (but database has data)'}")
        print(f"   ✓ Database ready: YES")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"\n❌ DATABASE VERIFICATION FAILED")
        print(f"   Error: {str(e)}")
        print(f"   Type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = verify_customer_data()
    sys.exit(0 if success else 1)
