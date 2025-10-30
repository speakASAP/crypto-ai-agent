import os
import sqlite3
import psycopg

SQLITE_DB = os.environ.get("SQLITE_DB", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data/crypto_portfolio.db"))
POSTGRES_URL = os.environ.get("DATABASE_URL")

def copy_table(sqlite_conn, pg_conn, table, columns, boolean_cols=None, required_cols=None):
    boolean_cols = boolean_cols or []
    required_cols = required_cols or []
    s_cur = sqlite_conn.cursor()
    p_cur = pg_conn.cursor()
    s_cur.execute(f"SELECT {', '.join(columns)} FROM {table}")
    rows = s_cur.fetchall()
    if not rows:
        return 0
    values_placeholder = f"({', '.join(['%s']*len(columns))})"
    insert_sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES {values_placeholder} ON CONFLICT DO NOTHING"
    copied = 0
    for row in rows:
        # Convert boolean columns from int to bool, and handle empty strings
        converted_row = []
        should_skip = False
        for i, val in enumerate(row):
            col_name = columns[i]
            if col_name in required_cols and (val is None or val == ""):
                should_skip = True
                break
            if col_name in boolean_cols and isinstance(val, int):
                converted_row.append(bool(val))
            elif val == "":
                # Empty string should be None for nullable columns
                converted_row.append(None)
            else:
                converted_row.append(val)
        if should_skip:
            continue
        try:
            p_cur.execute(insert_sql, tuple(converted_row))
            copied += 1
        except Exception as e:
            print(f"Error inserting row into {table}: {e}")
            continue
    pg_conn.commit()
    return copied

def main():
    if not POSTGRES_URL:
        raise RuntimeError("DATABASE_URL must be set for migration")
    sqlite_conn = sqlite3.connect(SQLITE_DB)
    # Parse URL: postgresql+psycopg://user:pass@host:port/db
    pg_url = POSTGRES_URL.replace("+psycopg", "") if "+psycopg" in POSTGRES_URL else POSTGRES_URL
    pg_conn = psycopg.connect(pg_url)

    # Minimal set of tables; extend as needed
    copied = 0
    copied += copy_table(sqlite_conn, pg_conn, "users", [
        "id","email","username","hashed_password","full_name","is_active","is_verified","created_at","updated_at"
    ], boolean_cols=["is_active", "is_verified"], required_cols=["email", "username", "hashed_password"])
    copied += copy_table(sqlite_conn, pg_conn, "portfolio_items", [
        "id","user_id","symbol","amount","price_buy","purchase_date","base_currency","purchase_price_eur","purchase_price_czk","source","commission","total_investment_text","created_at","updated_at","current_price","current_value","pnl","pnl_percent","price_buy_usd","commission_usd","current_price_usd","current_value_usd","pnl_usd","pnl_percent_usd"
    ], required_cols=["user_id", "symbol", "amount", "price_buy", "base_currency"])
    copied += copy_table(sqlite_conn, pg_conn, "alerts", [
        "id","user_id","symbol","threshold_price","alert_type","message","is_active","created_at"
    ], boolean_cols=["is_active"], required_cols=["user_id", "symbol", "threshold_price", "alert_type"])
    copied += copy_table(sqlite_conn, pg_conn, "tracked_symbols", [
        "id","user_id","symbol","name","active","last_updated"
    ], boolean_cols=["active"], required_cols=["user_id", "symbol", "name"])
    copied += copy_table(sqlite_conn, pg_conn, "alert_history", [
        "id","alert_id","user_id","triggered_price","triggered_at","was_missed","check_type"
    ], boolean_cols=["was_missed"], required_cols=["user_id", "triggered_price"])
    copied += copy_table(sqlite_conn, pg_conn, "currency_rates", [
        "from_currency","to_currency","rate","timestamp"
    ], required_cols=["from_currency", "to_currency", "rate"])

    print(f"Copied rows: {copied}")

if __name__ == "__main__":
    main()


