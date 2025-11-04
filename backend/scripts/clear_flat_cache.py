#!/usr/bin/env python3
"""
Script to clear flat/synthesized price history cache entries.
Flat data is detected when all prices in a cache entry are identical.
"""

import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_db_connection
from app.utils.db import normalize_placeholders

def clear_flat_cache_entries():
    """Clear cache entries where all prices are identical (synthesized/flat data)"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Get all cache entries
        sql = normalize_placeholders(
            "SELECT symbol, history_data FROM price_history_cache"
        )
        cursor.execute(sql)
        rows = cursor.fetchall()

        cleared_count = 0
        kept_count = 0

        for symbol, history_data_str in rows:
            try:
                history_data = json.loads(history_data_str)
                
                # Check if all prices are identical (flat/synthesized data)
                if len(history_data) > 1:
                    prices = [
                        point.get("price", 0)
                        for point in history_data
                        if isinstance(point, dict)
                    ]
                    
                    if prices and len(set(prices)) == 1:
                        # All prices identical - clear this cache entry
                        delete_sql = normalize_placeholders(
                            "DELETE FROM price_history_cache WHERE symbol = %s"
                        )
                        cursor.execute(delete_sql, (symbol,))
                        cleared_count += 1
                        print(f"Cleared flat cache for {symbol}")
                    else:
                        kept_count += 1
                else:
                    # Single point or empty - might be flat, clear it
                    delete_sql = normalize_placeholders(
                        "DELETE FROM price_history_cache WHERE symbol = %s"
                    )
                    cursor.execute(delete_sql, (symbol,))
                    cleared_count += 1
                    print(f"Cleared single-point cache for {symbol}")

            except json.JSONDecodeError:
                # Invalid JSON - clear it
                delete_sql = normalize_placeholders(
                    "DELETE FROM price_history_cache WHERE symbol = %s"
                )
                cursor.execute(delete_sql, (symbol,))
                cleared_count += 1
                print(f"Cleared invalid cache for {symbol}")

        conn.commit()
        print(f"\n✅ Cleared {cleared_count} flat/invalid cache entries")
        print(f"✅ Kept {kept_count} valid cache entries")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error clearing cache: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    print("Clearing flat/synthesized price history cache entries...")
    clear_flat_cache_entries()
    print("Done!")

