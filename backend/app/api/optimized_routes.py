"""
Optimized API Routes with Performance Enhancements
"""
import time
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.portfolio import PortfolioCreate, PortfolioUpdate, PortfolioResponse, PortfolioSummary
from app.schemas.alerts import PriceAlertCreate, PriceAlertUpdate, PriceAlertResponse, AlertHistoryResponse
from app.schemas.symbols import TrackedSymbolCreate, TrackedSymbolUpdate, TrackedSymbolResponse
from app.services.optimized_db_service import optimized_db_service
from app.services.performance_monitor import performance_monitor, monitor_performance
from app.services.advanced_cache_service import cache_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Performance monitoring middleware
async def performance_middleware(request, call_next):
    """Middleware to monitor API performance"""
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    performance_monitor.record_api_call(
        endpoint=str(request.url.path),
        method=request.method,
        response_time=process_time,
        status_code=response.status_code
    )
    
    # Add performance headers
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-Cache-Status"] = "miss"  # This would be set by cache service
    
    return response

# Portfolio routes with optimization
@router.get("/portfolio/", response_model=List[PortfolioResponse])
@monitor_performance("database", "get_portfolio")
async def get_portfolio_optimized(
    currency: str = Query("USD", description="Base currency for portfolio"),
    db: AsyncSession = Depends(get_db)
):
    """Get portfolio with optimized query and caching"""
    try:
        portfolio_data = await optimized_db_service.get_portfolio_optimized(currency)
        
        # Convert to response format
        portfolio_items = []
        for item in portfolio_data:
            portfolio_items.append(PortfolioResponse(**item))
        
        logger.info(f"📊 Portfolio retrieved: {len(portfolio_items)} items in {currency}")
        return portfolio_items
        
    except Exception as e:
        logger.error(f"❌ Portfolio retrieval error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve portfolio")

@router.get("/portfolio/summary", response_model=PortfolioSummary)
@monitor_performance("database", "get_portfolio_summary")
async def get_portfolio_summary_optimized(
    currency: str = Query("USD", description="Base currency for summary"),
    db: AsyncSession = Depends(get_db)
):
    """Get portfolio summary with optimized aggregation"""
    try:
        summary_data = await optimized_db_service.get_portfolio_summary_optimized(currency)
        
        logger.info(f"📊 Portfolio summary calculated for {currency}")
        return PortfolioSummary(**summary_data)
        
    except Exception as e:
        logger.error(f"❌ Portfolio summary error: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate portfolio summary")

@router.post("/portfolio/", response_model=PortfolioResponse)
@monitor_performance("database", "create_portfolio_item")
async def create_portfolio_item_optimized(
    item: PortfolioCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create portfolio item with optimization"""
    try:
        # Use optimized batch create for single item
        created_items = await optimized_db_service.batch_create_portfolio_items([item.dict()])
        
        if not created_items:
            raise HTTPException(status_code=400, detail="Failed to create portfolio item")
        
        logger.info(f"📊 Portfolio item created: {item.symbol}")
        return PortfolioResponse(**created_items[0])
        
    except Exception as e:
        logger.error(f"❌ Portfolio item creation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create portfolio item")

# Alerts routes with optimization
@router.get("/alerts/", response_model=List[PriceAlertResponse])
@monitor_performance("database", "get_alerts")
async def get_alerts_optimized(
    active_only: bool = Query(True, description="Get only active alerts"),
    db: AsyncSession = Depends(get_db)
):
    """Get price alerts with optimized query"""
    try:
        alerts_data = await optimized_db_service.get_alerts_optimized(active_only)
        
        # Convert to response format
        alerts = []
        for alert_data in alerts_data:
            alerts.append(PriceAlertResponse(**alert_data))
        
        logger.info(f"🔔 Alerts retrieved: {len(alerts)} alerts")
        return alerts
        
    except Exception as e:
        logger.error(f"❌ Alerts retrieval error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve alerts")

@router.get("/alerts/history", response_model=List[AlertHistoryResponse])
@monitor_performance("database", "get_alert_history")
async def get_alert_history_optimized(
    limit: int = Query(100, description="Number of history entries to retrieve"),
    db: AsyncSession = Depends(get_db)
):
    """Get alert history with optimized query and pagination"""
    try:
        history_data = await optimized_db_service.get_alert_history_optimized(limit)
        
        # Convert to response format
        history = []
        for entry_data in history_data:
            history.append(AlertHistoryResponse(**entry_data))
        
        logger.info(f"📜 Alert history retrieved: {len(history)} entries")
        return history
        
    except Exception as e:
        logger.error(f"❌ Alert history retrieval error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve alert history")

# Symbols routes with optimization
@router.get("/symbols/tracked", response_model=List[TrackedSymbolResponse])
@monitor_performance("database", "get_tracked_symbols")
async def get_tracked_symbols_optimized(
    active_only: bool = Query(True, description="Get only active symbols"),
    db: AsyncSession = Depends(get_db)
):
    """Get tracked symbols with optimized query"""
    try:
        symbols_data = await optimized_db_service.get_tracked_symbols_optimized(active_only)
        
        # Convert to response format
        symbols = []
        for symbol_data in symbols_data:
            symbols.append(TrackedSymbolResponse(**symbol_data))
        
        logger.info(f"📈 Tracked symbols retrieved: {len(symbols)} symbols")
        return symbols
        
    except Exception as e:
        logger.error(f"❌ Tracked symbols retrieval error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve tracked symbols")

# Performance monitoring routes
@router.get("/performance/summary")
async def get_performance_summary():
    """Get system performance summary"""
    try:
        summary = performance_monitor.get_performance_summary()
        return JSONResponse(content=summary)
        
    except Exception as e:
        logger.error(f"❌ Performance summary error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get performance summary")

@router.get("/performance/health")
async def get_health_status():
    """Get system health status"""
    try:
        health = performance_monitor.get_health_status()
        return JSONResponse(content=health)
        
    except Exception as e:
        logger.error(f"❌ Health status error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get health status")

@router.get("/performance/cache-stats")
async def get_cache_stats():
    """Get cache statistics"""
    try:
        stats = cache_service.get_stats()
        return JSONResponse(content=stats)
        
    except Exception as e:
        logger.error(f"❌ Cache stats error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cache statistics")

@router.post("/performance/reset")
async def reset_performance_metrics():
    """Reset performance metrics"""
    try:
        performance_monitor.reset_metrics()
        await cache_service.clear_all()
        
        logger.info("📊 Performance metrics and cache reset")
        return JSONResponse(content={"message": "Performance metrics and cache reset successfully"})
        
    except Exception as e:
        logger.error(f"❌ Reset metrics error: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset metrics")

# Batch operations for better performance
@router.post("/portfolio/batch", response_model=List[PortfolioResponse])
@monitor_performance("database", "batch_create_portfolio")
async def batch_create_portfolio_items(
    items: List[PortfolioCreate],
    db: AsyncSession = Depends(get_db)
):
    """Batch create portfolio items for better performance"""
    try:
        if len(items) > 100:
            raise HTTPException(status_code=400, detail="Batch size too large. Maximum 100 items.")
        
        # Convert to dict format
        items_data = [item.dict() for item in items]
        
        # Use optimized batch create
        created_items = await optimized_db_service.batch_create_portfolio_items(items_data)
        
        # Convert to response format
        portfolio_items = []
        for item_data in created_items:
            portfolio_items.append(PortfolioResponse(**item_data))
        
        logger.info(f"📊 Batch created {len(portfolio_items)} portfolio items")
        return portfolio_items
        
    except Exception as e:
        logger.error(f"❌ Batch create portfolio error: {e}")
        raise HTTPException(status_code=500, detail="Failed to batch create portfolio items")

# Currency conversion optimization
@router.get("/currency/rate")
async def get_currency_rate_optimized(
    from_currency: str = Query(..., description="Source currency"),
    to_currency: str = Query(..., description="Target currency")
):
    """Get currency rate with optimization"""
    try:
        rate = await optimized_db_service.get_currency_rates_optimized(from_currency, to_currency)
        
        if rate is None:
            raise HTTPException(status_code=404, detail=f"Currency rate not found for {from_currency}/{to_currency}")
        
        return JSONResponse(content={
            "from_currency": from_currency,
            "to_currency": to_currency,
            "rate": rate,
            "timestamp": time.time()
        })
        
    except Exception as e:
        logger.error(f"❌ Currency rate error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get currency rate")

# Latest prices optimization
@router.get("/symbols/prices")
async def get_latest_prices_optimized(
    symbols: str = Query(..., description="Comma-separated list of symbols")
):
    """Get latest prices for multiple symbols with optimization"""
    try:
        symbol_list = [s.strip().upper() for s in symbols.split(",")]
        
        if len(symbol_list) > 50:
            raise HTTPException(status_code=400, detail="Too many symbols. Maximum 50 symbols.")
        
        prices = await optimized_db_service.get_latest_prices_optimized(symbol_list)
        
        return JSONResponse(content={
            "prices": prices,
            "timestamp": time.time(),
            "symbol_count": len(prices)
        })
        
    except Exception as e:
        logger.error(f"❌ Latest prices error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get latest prices")
