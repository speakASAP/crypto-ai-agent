from fastapi import APIRouter
from ..core.config import settings
from .ws import manager


router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    db_type = "postgres" if bool(getattr(settings, "database_url", None)) or settings.environment.lower() == "production" else "sqlite"
    return {
        "status": "healthy",
        "database": db_type,
        "version": "2.0.0",
        "websocket_connections": len(manager.active_connections),
    }
