from fastapi import APIRouter, HTTPException
from ..core.config import settings
from .ws import manager
from ..dependencies.auth import get_db_connection

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    db_type = "postgres" if bool(getattr(settings, "database_url", None)) or settings.environment.lower() == "production" else "sqlite"
    
    # Test database connectivity and verify it has data
    db_connected = False
    db_has_data = False
    db_error = None
    user_count = 0
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Test connection with simple query
        if db_type == "postgres":
            cursor.execute("SELECT 1")
        else:
            cursor.execute("SELECT 1")
        cursor.fetchone()
        db_connected = True
        
        # Verify database has data (users table exists and has records)
        if db_type == "postgres":
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'users'
                )
            """)
            users_table_exists = cursor.fetchone()[0]
            
            if users_table_exists:
                cursor.execute("SELECT COUNT(*) FROM users")
                user_count = cursor.fetchone()[0]
                db_has_data = user_count > 0
        else:
            # SQLite - check if users table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            table_exists = cursor.fetchone() is not None
            if table_exists:
                cursor.execute("SELECT COUNT(*) FROM users")
                user_count = cursor.fetchone()[0]
                db_has_data = user_count > 0
        
        cursor.close()
        conn.close()
    except Exception as e:
        db_error = str(e)
        db_connected = False
    
    # Service is only healthy if database is connected AND has data
    # For production: database must have data (customer accounts)
    status = "healthy" if (db_connected and db_has_data) else "unhealthy"
    
    response = {
        "status": status,
        "database": db_type,
        "database_connected": db_connected,
        "database_has_data": db_has_data,
        "user_count": user_count,
        "version": "2.0.0",
        "websocket_connections": len(manager.active_connections),
    }
    
    if db_error:
        response["database_error"] = db_error
    
    # Return 503 if database is not connected or has no data (service unavailable)
    if not db_connected or not db_has_data:
        raise HTTPException(status_code=503, detail=response)
    
    return response
