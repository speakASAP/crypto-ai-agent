#!/usr/bin/env python3

import sqlite3
import os

# Test database initialization
DB_FILE = "data/crypto_portfolio.db"

def test_init_database():
    """Test database initialization"""
    print(f"Testing database initialization with file: {DB_FILE}")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Database file exists: {os.path.exists(DB_FILE)}")
    
    if os.path.exists(DB_FILE):
        print(f"Database file size: {os.path.getsize(DB_FILE)} bytes")
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            full_name TEXT,
            is_active BOOLEAN DEFAULT 1,
            is_verified BOOLEAN DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    print("✅ Users table created")
    
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    result = cursor.fetchone()
    print(f"Users table exists: {result is not None}")
    
    # List all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"All tables: {[table[0] for table in tables]}")
    
    conn.close()
    print(f"Database file size after: {os.path.getsize(DB_FILE)} bytes")

if __name__ == "__main__":
    test_init_database()
