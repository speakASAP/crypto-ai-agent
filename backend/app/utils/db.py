def is_postgres_connection(conn) -> bool:
    """Best-effort detection of psycopg connection used in production."""
    return conn.__class__.__module__.startswith("psycopg")


def normalize_placeholders(sql: str, is_postgres: bool) -> str:
    """Convert SQLite-style '?' placeholders to PostgreSQL '%s' placeholders when needed."""
    if not is_postgres:
        return sql
    return sql.replace("?", "%s")


def execute_insert_and_get_id(cursor, sql: str, params: tuple, is_postgres: bool) -> int:
    """Execute an INSERT and return the inserted row id for both engines."""
    if is_postgres:
        if "RETURNING id" not in sql.upper():
            sql = sql + " RETURNING id"
        cursor.execute(sql, params)
        row = cursor.fetchone()
        return int(row[0]) if row else None
    else:
        cursor.execute(sql, params)
        return int(cursor.lastrowid)
