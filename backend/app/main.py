from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import redis.asyncio as redis
from app.core.config import settings
from app.core.database import init_db
from app.api.routes import api_router
from app.api.optimized_routes import router as optimized_router
from app.services.advanced_cache_service import cache_service
from app.services.performance_monitor import performance_monitor
from app.services.cache_service import CacheService
import logging

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format=settings.log_format,
    handlers=[
        logging.FileHandler(settings.log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Starting Crypto AI Agent API v2.0")
    
    # Initialize database
    await init_db()
    logger.info("✅ Database initialized")
    
    # Initialize Redis
    app.state.redis = redis.from_url(settings.redis_url)
    app.state.cache = CacheService(app.state.redis)
    logger.info("✅ Redis initialized")
    
    # Initialize advanced cache service
    await cache_service.initialize()
    logger.info("✅ Advanced cache service initialized")
    
    # Start performance monitoring
    performance_monitor.start_monitoring()
    logger.info("✅ Performance monitoring started")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Crypto AI Agent API v2.0")
    
    # Stop performance monitoring
    performance_monitor.stop_monitoring()
    logger.info("✅ Performance monitoring stopped")
    
    # Close cache service
    await cache_service.close()
    logger.info("✅ Cache service closed")
    
    # Close Redis connection
    await app.state.redis.close()
    logger.info("✅ Redis connection closed")


app = FastAPI(
    title="Crypto AI Agent API",
    description="High-performance crypto portfolio management API",
    version="2.0.0",
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include API routes
app.include_router(api_router, prefix="/api")
app.include_router(optimized_router, prefix="/api/v2", tags=["optimized"])

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "2.0.0"}

# Dependency to get cache service
def get_cache_service() -> CacheService:
    return app.state.cache

# Make cache service available globally
app.dependency_overrides[get_cache_service] = lambda: app.state.cache

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )
