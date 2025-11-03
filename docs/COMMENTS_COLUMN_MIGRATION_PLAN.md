# Comments Column Migration Plan

## Problem

The `comments` column is missing from the `portfolio_items` table in existing databases, causing errors when trying to create new portfolio items (e.g., "BTC was not created due to the column Comment is not in the database").

## Root Cause

The `init_postgres_database()` function returns early when the database schema exists with data (line 1413-1416), which prevents the ALTER TABLE command from adding the `comments` column to existing databases.

## Solution

Create a dedicated migration function that:

1. Checks if the `comments` column exists in the `portfolio_items` table
2. Adds it if it doesn't exist
3. Works with PostgreSQL
4. Is called during startup regardless of whether tables are created

## Implementation Checklist

1. ✅ Create `ensure_comments_column()` function in `backend/app/main.py`:
   - ✅ Check if `portfolio_items` table exists
   - ✅ Check if `comments` column exists (using PostgreSQL queries)
   - ✅ Add column if it doesn't exist
   - ✅ Handle PostgreSQL database
   - ✅ Add proper error handling and logging

2. ✅ For PostgreSQL column check:
   - ✅ Query: `SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'portfolio_items' AND column_name = 'comments')`
   - ✅ If not exists, execute: `ALTER TABLE portfolio_items ADD COLUMN comments TEXT`

3. ✅ Update `lifespan()` function in `backend/app/main.py`:
   - ✅ Call `ensure_comments_column()` after database initialization
   - ✅ Call it for PostgreSQL database
   - ✅ Place it after `ensure_ai_advisor_tables()` call (around line 1932)

4. ⏳ Test the migration:
   - ⏳ Verify column is added to existing databases
   - ⏳ Verify new portfolio items can be created with comments
   - ⏳ Verify existing functionality still works

## Files to Modify

- `backend/app/main.py`: Add `ensure_comments_column()` function and call it in `lifespan()`
