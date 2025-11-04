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
from ..services.openrouter_service import RateLimitError
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
    symbol_upper = symbol.upper()
    
    try:
        predictions = await ai_advisor_service.generate_predictions(
            user_id=current_user["id"],
            symbol=symbol_upper,
            force_regenerate=False,
        )

        # For non-BTC symbols, return empty predictions structure instead of 404
        # This prevents frontend errors when no cached predictions exist
        if not predictions:
            if symbol_upper != "BTC":
                logger.debug(f"No cached predictions for {symbol_upper} (non-BTC), returning empty structure")
                return PredictionResponse(symbol=symbol_upper, predictions={})
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"No predictions available for {symbol_upper}",
                )

        return PredictionResponse(symbol=symbol_upper, predictions=predictions)

    except RateLimitError as e:
        # Rate limit error - return 503 (Service Unavailable) with helpful message
        logger.warning(f"Rate limit error for {symbol}: {e}")
        raise HTTPException(
            status_code=503,
            detail="AI prediction service is temporarily rate-limited. Please try again later or add your own API key."
        )
    except HTTPException:
        # Re-raise HTTPException as-is
        raise
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
    from ..utils.db import get_db_connection, normalize_placeholders

    try:
        # Get user's portfolio symbols directly from database
        conn = get_db_connection()
        cursor = conn.cursor()

        sql = normalize_placeholders(
            "SELECT DISTINCT symbol FROM portfolio_items WHERE user_id = %s"
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
    """Manually trigger prediction generation for a symbol (BTC only to avoid rate limits)"""
    symbol_upper = symbol.upper()
    
    # Only allow manual generation for BTC
    if symbol_upper != "BTC":
        raise HTTPException(
            status_code=400,
            detail=f"Prediction generation is only available for BTC to avoid rate limits. Use cached predictions for other symbols."
        )
    
    try:
        predictions = await ai_advisor_service.generate_predictions(
            user_id=current_user["id"],
            symbol=symbol_upper,
            force_regenerate=True,
        )

        if not predictions:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate predictions for {symbol_upper}",
            )

        return PredictionResponse(symbol=symbol_upper, predictions=predictions)

    except RateLimitError as e:
        logger.warning(f"Rate limit error for {symbol_upper}: {e}")
        raise HTTPException(
            status_code=503,
            detail="AI prediction service is temporarily rate-limited. Please try again later or add your own API key."
        )
    except Exception as e:
        logger.error(
            f"Error generating predictions for {symbol_upper}: {e}", exc_info=True
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

