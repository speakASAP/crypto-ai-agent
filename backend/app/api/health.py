from fastapi import APIRouter, HTTPException
import asyncio
from .ws import manager
from ..dependencies.auth import get_db_connection

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check():
    return await deep_health_check()


@router.get("/ready")
async def readiness_check():
    """Cheap Kubernetes readiness check.

    Keep this endpoint independent from database and external services so probes do
    not create connection churn or background thread pressure under load.
    """
    return {
        "status": "healthy",
        "version": "2.0.0",
        "websocket_connections": len(manager.active_connections),
    }


@router.get("/health/deep")
async def deep_health_check():
    """Deep diagnostic health check with PostgreSQL schema verification."""
    db_connected = False
    schema_ready = False
    db_has_data = False
    db_error = None
    user_count = 0

    def check_database():
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT 1")
            cursor.fetchone()

            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN ('users', 'portfolio_items', 'currency_rates')
            """)
            existing_tables = {row[0] for row in cursor.fetchall()}
            required_tables = {'users', 'portfolio_items', 'currency_rates'}
            schema_ready = required_tables.issubset(existing_tables)

            user_count = 0
            if 'users' in existing_tables:
                cursor.execute("SELECT COUNT(*) FROM users")
                user_count = cursor.fetchone()[0]

            cursor.close()
            conn.close()

            return True, schema_ready, user_count > 0, user_count, None
        except Exception as e:
            return False, False, False, 0, str(e)

    try:
        db_connected, schema_ready, db_has_data, user_count, db_error = await asyncio.wait_for(
            asyncio.to_thread(check_database),
            timeout=5.0,
        )
    except asyncio.TimeoutError:
        db_error = "Database connection timeout (exceeded 5 seconds)"
        db_connected = False
    except Exception as e:
        db_error = str(e)
        db_connected = False

    status = "healthy" if db_connected and schema_ready else "unhealthy"

    response = {
        "status": status,
        "database": "postgres",
        "database_connected": db_connected,
        "database_schema_ready": schema_ready,
        "database_has_data": db_has_data,
        "user_count": user_count,
        "version": "2.0.0",
        "websocket_connections": len(manager.active_connections),
    }

    if db_error:
        response["database_error"] = db_error

    if not db_connected or not schema_ready:
        raise HTTPException(status_code=503, detail=response)

    return response
