from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional, Dict
from datetime import datetime, timezone

from ..dependencies.auth import get_current_active_user
from ..schemas.ai_advisor import (
    PredictionResponse,
    NewsAnalysis,
    ChartData,
    PerformanceStats,
    PredictionRequest,
)
from ..services.ai_advisor_service import ai_advisor_service
from ..services.news_service import news_service
from ..services.historical_price_service import historical_price_service
from ..utils.logger import get_logger

logger = get_logger("backend.app.api.ai_advisor")

router = APIRouter(prefix="/api/ai-advisor", tags=["ai-advisor"])


@router.get("/predictions/{symbol}", response_model=PredictionResponse)
async def get_predictions(
    symbol: str,
    current_user: dict = Depends(get_current_active_user),
):
    """Get current AI predictions for a symbol"""
    try:
        predictions = await ai_advisor_service.generate_predictions(
            user_id=current_user["id"],
            symbol=symbol.upper(),
            force_regenerate=False,
        )

        if not predictions:
            raise HTTPException(
                status_code=404,
                detail=f"No predictions available for {symbol}",
            )

        return PredictionResponse(symbol=symbol.upper(), predictions=predictions)

    except Exception as e:
        logger.error(f"Error getting predictions for {symbol}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get predictions: {str(e)}"
        )


@router.get("/predictions/portfolio", response_model=Dict[str, PredictionResponse])
async def get_portfolio_predictions(
    current_user: dict = Depends(get_current_active_user),
):
    """Get predictions for all symbols in user's portfolio"""
    from ..utils.db import get_db_connection, is_postgres_connection, normalize_placeholders

    try:
        # Get user's portfolio symbols directly from database
        conn = get_db_connection()
        cursor = conn.cursor()
        is_pg = is_postgres_connection(conn)

        sql = normalize_placeholders(
            "SELECT DISTINCT symbol FROM portfolio_items WHERE user_id = ?",
            is_pg,
        )
        cursor.execute(sql, (current_user["id"],))
        rows = cursor.fetchall()
        conn.close()

        symbols = [row[0] for row in rows]

        results = {}
        for symbol in symbols:
            try:
                predictions = await ai_advisor_service.generate_predictions(
                    user_id=current_user["id"],
                    symbol=symbol.upper(),
                    force_regenerate=False,
                )

                if predictions:
                    results[symbol.upper()] = PredictionResponse(
                        symbol=symbol.upper(), predictions=predictions
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to get predictions for {symbol}: {e}", exc_info=True
                )
                continue

        return results

    except Exception as e:
        logger.error(f"Error getting portfolio predictions: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get portfolio predictions: {str(e)}"
        )


@router.post("/generate/{symbol}", response_model=PredictionResponse)
async def generate_predictions(
    symbol: str,
    current_user: dict = Depends(get_current_active_user),
):
    """Manually trigger prediction generation for a symbol"""
    try:
        predictions = await ai_advisor_service.generate_predictions(
            user_id=current_user["id"],
            symbol=symbol.upper(),
            force_regenerate=True,
        )

        if not predictions:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate predictions for {symbol}",
            )

        return PredictionResponse(symbol=symbol.upper(), predictions=predictions)

    except Exception as e:
        logger.error(
            f"Error generating predictions for {symbol}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to generate predictions: {str(e)}"
        )


@router.get("/performance/{symbol}", response_model=PerformanceStats)
async def get_performance(
    symbol: Optional[str] = None,
    model_name: Optional[str] = None,
    current_user: dict = Depends(get_current_active_user),
):
    """Get historical prediction performance statistics"""
    try:
        stats = await ai_advisor_service.get_performance_stats(
            user_id=current_user["id"],
            symbol=symbol.upper() if symbol else None,
            model_name=model_name,
        )

        return PerformanceStats(**stats)

    except Exception as e:
        logger.error(f"Error getting performance stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get performance stats: {str(e)}"
        )


@router.get("/performance/by-model", response_model=PerformanceStats)
async def get_performance_by_model(
    current_user: dict = Depends(get_current_active_user),
):
    """Get performance statistics grouped by model"""
    try:
        stats = await ai_advisor_service.get_performance_stats(
            user_id=current_user["id"], model_name=None
        )

        return PerformanceStats(**stats)

    except Exception as e:
        logger.error(f"Error getting performance by model: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get performance by model: {str(e)}",
        )


@router.get("/news/{symbol}")
async def get_news(
    symbol: str,
    days: int = 7,
    current_user: dict = Depends(get_current_active_user),
):
    """Get recent news analysis for a symbol"""
    try:
        articles = await news_service.fetch_news(symbol.upper(), days=days)

        # Convert to NewsAnalysis format
        news_items = []
        for article in articles:
            news_items.append(
                NewsAnalysis(
                    id=0,  # Not stored in DB yet, so no ID
                    symbol=symbol.upper(),
                    news_date=article.get("published_at", ""),
                    title=article.get("title", ""),
                    summary=article.get("description", ""),
                    sentiment_score=article.get("sentiment_score"),
                    relevance_score=article.get("relevance_score"),
                    source=article.get("source", ""),
                    created_at=datetime.now(timezone.utc).isoformat() + "Z",
                )
            )

        return news_items

    except Exception as e:
        logger.error(f"Error getting news for {symbol}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get news: {str(e)}"
        )

