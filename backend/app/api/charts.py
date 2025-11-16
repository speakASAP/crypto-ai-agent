from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List
import asyncio
from ..dependencies.auth import get_current_active_user
from ..schemas.ai_advisor import ChartData, ChartDataPoint
from ..services.historical_price_service import historical_price_service
from ..services.multi_exchange_price_service import multi_exchange_price_service
from ..services.chart_tasks import fetch_chart_data_for_symbols
from ..utils.logger import get_logger

logger = get_logger("backend.app.api.charts")

router = APIRouter(prefix="/api/charts", tags=["charts"])


@router.get("/history/{symbol}", response_model=ChartData)
async def get_price_history(
    symbol: str,
    days: int = 365,
    current_user: dict = Depends(get_current_active_user),
):
    """Get 1-year price history for a symbol"""
    try:
        history = await historical_price_service.get_price_history(
            symbol.upper(), days=days
        )

        # Return 200 with empty data instead of 404 to prevent browser console errors
        # Frontend handles empty data gracefully by showing "No data" or "Failed to load chart"
        if not history:
            logger.debug(f"No price history available for {symbol}")
            return ChartData(symbol=symbol.upper(), data=[])

        data_points = [
            ChartDataPoint(
                timestamp=point["timestamp"],
                price=point["price"],
                date=point["date"],
            )
            for point in history
        ]

        return ChartData(symbol=symbol.upper(), data=data_points)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting price history for {symbol}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get price history: {str(e)}"
        )


@router.get("/mini/{symbol}", response_model=ChartData)
async def get_mini_chart(
    symbol: str,
    days: int = 7,
    current_user: dict = Depends(get_current_active_user),
):
    """Get mini chart data (last N days) for a symbol from CoinGecko API"""
    try:
        # Get mini chart data directly from CoinGecko API (with internal fallbacks)
        mini_data = await historical_price_service.get_mini_chart_data(
            symbol.upper(), days=days
        )

        # If no data and no cache, trigger background fetch (non-blocking)
        if not mini_data:
            # Check if cache exists (even if stale)
            cached = historical_price_service._get_from_cache(symbol.upper())
            if not cached:
                # No cache at all - trigger background fetch
                logger.info(f"📊 No chart cache for {symbol}, triggering background fetch")
                # Trigger background fetch (non-blocking, don't wait)
                asyncio.create_task(
                    fetch_chart_data_for_symbols([symbol.upper()], days=days, skip_cached=False)
                )
            logger.debug(f"No mini chart data available for {symbol} (may be rate limited or no cache)")
            # Return 200 with empty data array instead of 404
            return ChartData(symbol=symbol.upper(), data=[])

        data_points = [
            ChartDataPoint(
                timestamp=point["timestamp"],
                price=point["price"],
                date=point["date"],
            )
            for point in mini_data
        ]

        return ChartData(symbol=symbol.upper(), data=data_points)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting mini chart for {symbol}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get mini chart: {str(e)}"
        )


@router.post("/fetch", response_model=dict)
async def trigger_chart_fetch(
    symbols: List[str] = Body(...),
    current_user: dict = Depends(get_current_active_user),
):
    """Trigger chart data fetching for specific symbols (non-blocking)"""
    try:
        if not symbols:
            raise HTTPException(status_code=400, detail="Symbols list cannot be empty")
        
        # Normalize symbols
        normalized_symbols = [s.upper() for s in symbols]
        
        logger.info(f"📊 Triggering chart data fetch for {len(normalized_symbols)} symbols: {normalized_symbols}")
        
        # Trigger background fetch (non-blocking, don't wait for completion)
        asyncio.create_task(
            fetch_chart_data_for_symbols(normalized_symbols, days=7, skip_cached=False)
        )
        
        return {
            "message": f"Chart data fetch triggered for {len(normalized_symbols)} symbols",
            "symbols": normalized_symbols
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering chart fetch: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to trigger chart fetch: {str(e)}"
        )

