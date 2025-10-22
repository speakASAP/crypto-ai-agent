from fastapi import APIRouter
from .portfolio import router as portfolio_router
from .alerts import router as alerts_router
from .symbols import router as symbols_router
from .websocket import router as websocket_router

# Create main router
api_router = APIRouter()

# Include all route modules
api_router.include_router(portfolio_router, prefix="/portfolio", tags=["portfolio"])
api_router.include_router(alerts_router, prefix="/alerts", tags=["alerts"])
api_router.include_router(symbols_router, prefix="/symbols", tags=["symbols"])
api_router.include_router(websocket_router, prefix="/ws", tags=["websocket"])
