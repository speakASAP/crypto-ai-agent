from fastapi import APIRouter, HTTPException
import asyncio
from ..core.config import settings
from .ws import manager
from ..dependencies.auth import get_db_connection

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check():
    # Test PostgreSQL database connectivity and verify it has data
    # Use timeout to prevent hanging on slow database connections
    db_connected = False
    db_has_data = False
    db_error = None
    user_count = 0
    
    def check_database():
        """Synchronous database check function"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Test connection with simple query
            cursor.execute("SELECT 1")
            cursor.fetchone()
            
            # Verify database has data (users table exists and has records)
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'users'
                )
            """)
            users_table_exists = cursor.fetchone()[0]
            
            user_count = 0
            if users_table_exists:
                cursor.execute("SELECT COUNT(*) FROM users")
                user_count = cursor.fetchone()[0]
            
            cursor.close()
            conn.close()
            
            return True, user_count > 0, user_count, None
        except Exception as e:
            return False, False, 0, str(e)
    
    try:
        # Run database check with 5 second timeout to prevent hanging
        # Use asyncio.to_thread to run the synchronous function in a thread pool
        db_connected, db_has_data, user_count, db_error = await asyncio.wait_for(
            asyncio.to_thread(check_database),
            timeout=5.0
        )
    except asyncio.TimeoutError:
        db_error = "Database connection timeout (exceeded 5 seconds)"
        db_connected = False
    except Exception as e:
        db_error = str(e)
        db_connected = False
    
    # Service is only healthy if database is connected AND has data
    # For production: database must have data (customer accounts)
    status = "healthy" if (db_connected and db_has_data) else "unhealthy"
    
    response = {
        "status": status,
        "database": "postgres",
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
