from fastapi import APIRouter, Depends, HTTPException
from ..dependencies.auth import get_current_active_user
from ..schemas.ai_advisor import ChartData, ChartDataPoint
from ..services.historical_price_service import historical_price_service
from ..services.multi_exchange_price_service import multi_exchange_price_service
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

        if not history:
            raise HTTPException(
                status_code=404,
                detail=f"No price history available for {symbol}",
            )

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

        # If still no data, try final fallback: synthesize from current price
        if not mini_data:
            try:
                prices = await multi_exchange_price_service.get_current_prices([symbol.upper()])
                current = prices.get(symbol.upper())
                if current is not None:
                    from datetime import datetime, timezone, timedelta
                    now = datetime.now(timezone.utc)
                    synthesized = []
                    for i in range(max(7, days), 0, -1):
                        dt = now - timedelta(days=i)
                        synthesized.append({
                            "timestamp": int(dt.timestamp()),
                            "price": float(current),
                            "date": dt.isoformat(),
                        })
                    mini_data = synthesized
                    logger.debug(f"Using synthesized mini chart data for {symbol}")
            except Exception as e:
                logger.warning(f"Error synthesizing mini chart data for {symbol}: {e}")

        if not mini_data:
            raise HTTPException(status_code=404, detail=f"No mini chart data available for {symbol}")

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

