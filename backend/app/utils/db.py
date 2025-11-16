import time
import psycopg
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from ..core.config import settings
try:
    from utils.logger import get_logger
except Exception:
    from ..utils.logger import get_logger

logger = get_logger("backend.app.utils.db")


def is_postgres_connection(conn) -> bool:
    """Always returns True since we only use PostgreSQL."""
    return True


def normalize_placeholders(sql: str) -> str:
    """Convert SQL '?' placeholders to PostgreSQL '%s' placeholders."""
    return sql.replace("?", "%s")


def execute_insert_and_get_id(cursor, sql: str, params: tuple) -> int:
    """Execute an INSERT and return the inserted row id using PostgreSQL RETURNING clause."""
    if "RETURNING id" not in sql.upper():
        sql = sql + " RETURNING id"
    cursor.execute(sql, params)
    row = cursor.fetchone()
    return int(row[0]) if row else None


def connect_with_retry(max_retries=3, initial_delay=0.5, max_delay=2.0, is_startup=False):
    """
    Helper function to connect to PostgreSQL database with retry logic and exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3 for runtime, 5 for startup)
        initial_delay: Initial delay in seconds (default: 0.5 for runtime, 2.0 for startup)
        max_delay: Maximum delay between retries in seconds (default: 2.0 for runtime, 30.0 for startup)
        is_startup: If True, uses startup retry parameters (5 retries, 2s initial, 30s max)
    
    Returns:
        PostgreSQL database connection object
    
    Raises:
        ConnectionError: If DATABASE_URL is not set or connection fails after all retries
    """
    if not settings.database_url:
        raise ConnectionError("DATABASE_URL environment variable is required. PostgreSQL database connection is mandatory.")
    
    if is_startup:
        max_retries = 5
        initial_delay = 2.0
        max_delay = 30.0
    
    delay = initial_delay
    last_error = None
    
    for attempt in range(1, max_retries + 1):
        try:
            pg_url = settings.database_url.replace("+psycopg", "") if "+psycopg" in settings.database_url else settings.database_url
            # Add connection timeout to prevent hanging (5 seconds)
            # Properly parse URL and add connect_timeout parameter
            parsed = urlparse(pg_url)
            query_params = parse_qs(parsed.query)
            # Add connect_timeout if not already present
            if 'connect_timeout' not in query_params:
                query_params['connect_timeout'] = ['5']
            # Reconstruct URL with timeout parameter
            new_query = urlencode(query_params, doseq=True)
            pg_url = urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                new_query,
                parsed.fragment
            ))
            
            conn = psycopg.connect(pg_url)
            logger.debug(f"✅ Database connection successful (PostgreSQL) - attempt {attempt}")
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
    raise ConnectionError(f"Failed to connect to PostgreSQL database after {max_retries} attempts: {str(last_error)}")


def get_db_connection():
    """Get PostgreSQL database connection with retry logic."""
    return connect_with_retry(max_retries=3, initial_delay=0.5, max_delay=2.0, is_startup=False)
