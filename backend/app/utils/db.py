import time
import sqlite3
import psycopg
from ..core.config import settings
import os
try:
    from utils.logger import get_logger
except Exception:
    from ..utils.logger import get_logger

logger = get_logger("backend.app.utils.db")

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


def get_db_file_path():
    """Get the database file path (for SQLite)."""
    current_file = os.path.abspath(__file__)
    backend_dir = os.path.dirname(os.path.dirname(current_file))
    project_root = os.path.dirname(backend_dir)
    return os.path.join(project_root, settings.database_file)


def connect_with_retry(max_retries=3, initial_delay=0.5, max_delay=2.0, is_startup=False):
    """
    Helper function to connect to database with retry logic and exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3 for runtime, 5 for startup)
        initial_delay: Initial delay in seconds (default: 0.5 for runtime, 2.0 for startup)
        max_delay: Maximum delay between retries in seconds (default: 2.0 for runtime, 30.0 for startup)
        is_startup: If True, uses startup retry parameters (5 retries, 2s initial, 30s max)
    
    Returns:
        Database connection object
    """
    if is_startup:
        max_retries = 5
        initial_delay = 2.0
        max_delay = 30.0
    
    use_postgres = settings.environment.lower() == "production" or bool(getattr(settings, "database_url", None))
    delay = initial_delay
    last_error = None
    
    for attempt in range(1, max_retries + 1):
        try:
            if use_postgres:
                pg_url = settings.database_url.replace("+psycopg", "") if settings.database_url and "+psycopg" in settings.database_url else settings.database_url
                conn = psycopg.connect(pg_url)
                logger.debug(f"✅ Database connection successful (PostgreSQL) - attempt {attempt}")
                return conn
            else:
                db_file = get_db_file_path()
                conn = sqlite3.connect(db_file, timeout=30.0, check_same_thread=False)
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA cache_size=10000")
                logger.debug(f"✅ Database connection successful (SQLite) - attempt {attempt}")
                return conn
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                logger.warning(f"⚠️ Database connection failed (attempt {attempt}/{max_retries}): {str(e)}. Retrying in {delay:.2f}s...")
                time.sleep(delay)
                delay = min(delay * (1.5 if is_startup else 2), max_delay)
            else:
                logger.error(f"❌ Database connection failed after {max_retries} attempts: {str(e)}")
    
    # All retries exhausted, raise the last error
    raise ConnectionError(f"Failed to connect to database after {max_retries} attempts: {str(last_error)}")


def get_db_connection():
    """Get database connection with retry logic: use Postgres when DATABASE_URL is set (or in production), otherwise SQLite."""
    return connect_with_retry(max_retries=3, initial_delay=0.5, max_delay=2.0, is_startup=False)
