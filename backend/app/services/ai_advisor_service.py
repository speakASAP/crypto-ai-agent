import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone
from ..core.config import settings
from ..utils.logger import get_logger
from ..utils.db import (
    get_db_connection,
    normalize_placeholders,
    execute_insert_and_get_id,
)
from .openrouter_service import openrouter_service, RateLimitError
from .news_service import news_service
from .multi_exchange_price_service import multi_exchange_price_service

logger = get_logger("backend.app.services.ai_advisor_service")


class AIAdvisorService:
    """Main service for AI advisor predictions and analysis"""

    def __init__(self):
        self.model_name = settings.openrouter_model

    async def generate_predictions(
        self, user_id: int, symbol: str, force_regenerate: bool = False
    ) -> Dict[str, Any]:
        """
        Generate or retrieve AI predictions for a symbol (global for all users)
        
        IMPORTANT: Only BTC predictions are generated daily. Other symbols only return cached predictions.

        Args:
            user_id: User ID (not used for storage, predictions are global)
            symbol: Cryptocurrency symbol
            force_regenerate: If True, regenerate even if recent predictions exist (only for BTC)

        Returns:
            Dictionary with predictions for 24h, week, month, year
        """
        symbol_upper = symbol.upper()
        
        # Check if we have cached predictions first (for all symbols)
        existing = self._get_latest_predictions(symbol_upper)
        if existing:
            # Check if predictions are still fresh (within interval)
            # Handle both datetime objects and string timestamps from database
            created_at_value = existing[0]["created_at"]
            if isinstance(created_at_value, datetime):
                created_at = created_at_value
                # Ensure timezone-aware (replace naive datetime with UTC)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
            elif isinstance(created_at_value, str):
                # Replace Z with +00:00 for ISO format compatibility
                created_at = datetime.fromisoformat(created_at_value.replace("Z", "+00:00"))
                # Ensure timezone-aware
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
            else:
                # Fallback: try to parse as string
                created_at = datetime.fromisoformat(str(created_at_value).replace("Z", "+00:00"))
                # Ensure timezone-aware
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
            age = datetime.now(timezone.utc) - created_at
            if age < timedelta(hours=settings.ai_prediction_interval_hours):
                logger.debug(
                    f"Using existing global predictions for {symbol_upper} (age: {age})"
                )
                return self._format_predictions_response(existing)
        
        # Only generate new predictions for BTC (to avoid rate limits)
        # For other symbols, only return cached predictions (any age, including verified)
        if symbol_upper != "BTC":
            # For non-BTC symbols, check for ANY cached predictions (no age limit, including verified)
            cached = self._get_cached_predictions_fallback(symbol_upper, max_age_days=None, include_verified=True)
            if cached:
                logger.info(f"Returning cached predictions for {symbol_upper} (non-BTC, generation disabled)")
                return cached
            # No cached predictions available for non-BTC symbol
            logger.debug(f"No cached predictions available for {symbol_upper} (non-BTC, generation disabled)")
            return {}
        
        # Only BTC reaches here - proceed with generation if needed
        if not force_regenerate and existing:
            # Already checked above, but double-check for BTC
            return self._format_predictions_response(existing)

        # Generate new predictions (only for BTC)
        try:
            # Get current price
            prices = await multi_exchange_price_service.get_current_prices([symbol_upper])
            if symbol_upper not in prices:
                logger.warning(f"Could not fetch current price for {symbol_upper}")
                return {}

            current_price = prices[symbol_upper]

            # Get price trend (need to calculate from history or use simple approximation)
            price_trend = await self._get_price_trend(symbol_upper)

            # Get news
            articles = await news_service.fetch_news(symbol_upper, days=7)
            news_summary = news_service.get_news_summary(articles)
            news_sentiment = news_service.get_average_sentiment(articles)

            # Generate predictions using OpenRouter (only for BTC)
            try:
                predictions_response = await openrouter_service.generate_prediction(
                    symbol=symbol_upper,
                    current_price=current_price,
                    price_trend=price_trend,
                    news_summary=news_summary,
                    news_sentiment=news_sentiment,
                    news_articles=articles[:5],  # Pass top 5 articles for source references
                )

                # Extract predictions
                predictions_dict = predictions_response.get("predictions", {})
                if not predictions_dict:
                    logger.warning(f"No predictions returned from OpenRouter for {symbol_upper}")
                    # Fallback to cached predictions
                    return self._get_cached_predictions_fallback(symbol_upper)

                # Store predictions in database
                # Use isoformat() which includes timezone offset (e.g., +00:00) - PostgreSQL compatible
                now = datetime.now(timezone.utc).isoformat()
                
                # Clean up old predictions for this symbol to avoid duplicates
                self._cleanup_old_predictions(symbol_upper)
                
                stored_predictions = []

                # Store predictions globally (user_id will be set to global user or first available user)
                global_user_id = self._get_global_user_id()
                for pred_type, pred_data in predictions_dict.items():
                    if pred_type in ["24h", "week", "month", "year"]:
                        # Enhance reasoning with news source links
                        reasoning = pred_data.get("reasoning", "")
                        reasoning_with_sources = self._add_news_source_links(
                            reasoning, articles[:5]
                        )
                        
                        prediction_id = self._store_prediction(
                            user_id=global_user_id,
                            symbol=symbol_upper,
                            prediction_type=pred_type,
                            predicted_price=pred_data.get("predicted_price", current_price),
                            confidence_percent=pred_data.get("confidence_percent", 50),
                            reasoning=reasoning_with_sources,
                            model_name=self.model_name,
                            created_at=now,
                        )
                        stored_predictions.append(
                            {
                                "id": prediction_id,
                                "prediction_type": pred_type,
                                "predicted_price": pred_data.get("predicted_price"),
                                "confidence_percent": pred_data.get("confidence_percent"),
                                "reasoning": pred_data.get("reasoning"),
                                "model_name": self.model_name,
                                "created_at": now,
                                "is_verified": False,
                            }
                        )

                logger.info(
                    f"Generated and stored {len(stored_predictions)} predictions for {symbol_upper}"
                )

                return self._format_predictions_response(stored_predictions)
            
            except RateLimitError as e:
                # Rate limit hit - return cached predictions if available
                logger.warning(f"Rate limit hit for {symbol_upper}, falling back to cached predictions")
                cached = self._get_cached_predictions_fallback(symbol_upper)
                if cached:
                    logger.info(f"Returning cached predictions for {symbol_upper}")
                    return cached
                # If no cache, raise the error so API can return appropriate response
                raise

        except RateLimitError:
            # Re-raise rate limit errors so API can handle them
            raise
        except Exception as e:
            logger.error(
                f"Error generating predictions for {symbol_upper}: {e}", exc_info=True
            )
            # Try to return cached predictions as fallback (any age, including verified)
            # This handles connection errors, timeouts, etc.
            cached = self._get_cached_predictions_fallback(symbol_upper, max_age_days=None, include_verified=True)
            if cached:
                logger.info(f"Returning cached predictions for {symbol_upper} due to error: {e}")
                return cached
            # If no cache available, return empty dict (will return 404 for BTC, empty response for others)
            logger.warning(f"No cached predictions available for {symbol_upper} after error: {e}")
            return {}

    def _add_news_source_links(
        self, reasoning: str, articles: List[Dict[str, Any]]
    ) -> str:
        """Add clickable news source links to the reasoning text"""
        if not articles or not reasoning:
            return reasoning
        
        # Look for references like [1], [2], etc. in the reasoning
        import re
        pattern = r'\[(\d+)\]'
        matches = re.findall(pattern, reasoning)
        
        if not matches:
            # If no references, append source links at the end
            sources_text = "\n\nSources: "
            source_links = []
            for idx, article in enumerate(articles[:3], 1):  # Top 3 sources
                title = article.get("title", "Untitled")
                url = article.get("url", "")
                if url:
                    # Ensure URL is absolute (external)
                    if not url.startswith(('http://', 'https://')):
                        url = f"https://{url}"
                    source_links.append(f"[{idx}]({url})")
            
            if source_links:
                reasoning += sources_text + ", ".join(source_links)
            return reasoning
        
        # Replace [1], [2] references with markdown links
        def replace_ref(match):
            idx = int(match.group(1))
            if 1 <= idx <= len(articles):
                article = articles[idx - 1]
                url = article.get("url", "")
                title = article.get("title", "")[:50]  # Truncate long titles
                if url:
                    # Ensure URL is absolute (external)
                    if not url.startswith(('http://', 'https://')):
                        url = f"https://{url}"
                    return f"[{idx}]({url})"
            return match.group(0)  # Return original if no valid article
        
        reasoning = re.sub(pattern, replace_ref, reasoning)
        return reasoning

    async def _get_price_trend(self, symbol: str) -> Dict[str, float]:
        """Get price trend data for a symbol"""
        # For now, return a simple structure
        # In production, this could fetch historical data and calculate trends
        return {
            "change_7d": 0.0,
            "change_30d": 0.0,
            "volatility": 0.0,
        }

    def _get_latest_predictions(
        self, symbol: str, include_verified: bool = False
    ) -> Optional[List[Dict[str, Any]]]:
        """Get the latest global predictions for a symbol (shared across all users)
        
        Args:
            symbol: Cryptocurrency symbol
            include_verified: If True, also include verified predictions (used as fallback)
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Get global predictions (any user_id, but we'll prioritize by recency)
            # First try unverified predictions, then fall back to verified if include_verified=True
            if include_verified:
                sql = normalize_placeholders(
                    """
                    SELECT id, prediction_type, predicted_price, confidence_percent,
                           prediction_reasoning, model_name, created_at, is_verified,
                           actual_price_at_target, accuracy_percent
                    FROM ai_predictions
                    WHERE symbol = %s
                    ORDER BY is_verified ASC, created_at DESC
                    LIMIT 4
                """
                )
            else:
                sql = normalize_placeholders(
                    """
                    SELECT id, prediction_type, predicted_price, confidence_percent,
                           prediction_reasoning, model_name, created_at, is_verified,
                           actual_price_at_target, accuracy_percent
                    FROM ai_predictions
                    WHERE symbol = %s AND is_verified = FALSE
                    ORDER BY created_at DESC
                    LIMIT 4
                """
                )
            cursor.execute(sql, (symbol.upper(),))
            rows = cursor.fetchall()
            conn.close()

            if rows:
                predictions = []
                for row in rows:
                    predictions.append(
                        {
                            "id": row[0],
                            "prediction_type": row[1],
                            "predicted_price": row[2],
                            "confidence_percent": row[3],
                            "reasoning": row[4],
                            "model_name": row[5],
                            "created_at": row[6],
                            "is_verified": bool(row[7]) if len(row) > 7 else False,
                            "actual_price_at_target": row[8] if len(row) > 8 else None,
                            "accuracy_percent": row[9] if len(row) > 9 else None,
                        }
                    )
                return predictions

        except Exception as e:
            logger.error(
                f"Error fetching latest predictions for {symbol}: {e}", exc_info=True
            )

        return None

    def _get_cached_predictions_fallback(
        self, symbol: str, max_age_days: Optional[int] = 7, include_verified: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Get cached predictions as fallback when API fails (less strict age check)
        
        Args:
            symbol: Cryptocurrency symbol
            max_age_days: Maximum age in days (None = no age limit, return any cached predictions)
            include_verified: If True, also check for verified predictions
        """
        try:
            existing = self._get_latest_predictions(symbol, include_verified=include_verified)
            if existing:
                # Handle both datetime objects and string timestamps from database
                created_at_value = existing[0]["created_at"]
                if isinstance(created_at_value, datetime):
                    created_at = created_at_value
                    # Ensure timezone-aware (replace naive datetime with UTC)
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                elif isinstance(created_at_value, str):
                    # Replace Z with +00:00 for ISO format compatibility
                    created_at = datetime.fromisoformat(created_at_value.replace("Z", "+00:00"))
                    # Ensure timezone-aware
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                else:
                    # Fallback: try to parse as string
                    created_at = datetime.fromisoformat(str(created_at_value).replace("Z", "+00:00"))
                    # Ensure timezone-aware
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                age = datetime.now(timezone.utc) - created_at
                
                # If max_age_days is None, return any cached predictions regardless of age
                if max_age_days is None or age < timedelta(days=max_age_days):
                    logger.debug(
                        f"Using cached predictions for {symbol} (age: {age}, max_age: {max_age_days} days)"
                    )
                    return self._format_predictions_response(existing)
                else:
                    logger.debug(
                        f"Cached predictions for {symbol} are too old (age: {age}, max: {max_age_days} days)"
                    )
        except Exception as e:
            logger.debug(f"Error getting cached predictions fallback for {symbol}: {e}")
        
        return None

    def _get_global_user_id(self) -> int:
        """Get a user ID to use for global predictions (reuses first available user)"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get the first user ID (or use 1 as fallback)
            sql = normalize_placeholders("SELECT id FROM users ORDER BY id LIMIT 1")
            cursor.execute(sql)
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return row[0]
            return 1  # Fallback
        except Exception as e:
            logger.warning(f"Error getting global user ID: {e}, using 1 as fallback")
            return 1

    def _cleanup_old_predictions(self, symbol: str) -> None:
        """Delete old unverified predictions for a symbol before storing new ones"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            sql = normalize_placeholders(
                "DELETE FROM ai_predictions WHERE symbol = %s AND is_verified = FALSE"
            )
            cursor.execute(sql, (symbol.upper(),))
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            if deleted_count > 0:
                logger.debug(f"Cleaned up {deleted_count} old predictions for {symbol}")
        except Exception as e:
            logger.warning(f"Error cleaning up old predictions for {symbol}: {e}")

    def _store_prediction(
        self,
        user_id: int,
        symbol: str,
        prediction_type: str,
        predicted_price: float,
        confidence_percent: float,
        reasoning: str,
        model_name: str,
        created_at: str,
    ) -> int:
        """Store a prediction in the database"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            sql = normalize_placeholders(
                """
                INSERT INTO ai_predictions
                (user_id, symbol, prediction_type, predicted_price, confidence_percent,
                 prediction_reasoning, model_name, created_at, is_verified)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            )

            prediction_id = execute_insert_and_get_id(
                cursor,
                sql,
                (
                    user_id,
                    symbol.upper(),
                    prediction_type,
                    predicted_price,
                    confidence_percent,
                    reasoning,
                    model_name,
                    created_at,
                    False,
                ),
            )

            conn.commit()
            conn.close()

            return prediction_id

        except Exception as e:
            logger.error(f"Error storing prediction: {e}", exc_info=True)
            raise

    def _format_predictions_response(
        self, predictions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Format predictions for API response"""
        result = {}
        for pred in predictions:
            pred_type = pred["prediction_type"]
            result[pred_type] = {
                "predicted_price": pred["predicted_price"],
                "confidence_percent": pred["confidence_percent"],
                "reasoning": pred.get("reasoning", ""),
                "model_name": pred.get("model_name", self.model_name),
                "created_at": pred["created_at"],
                "is_verified": pred.get("is_verified", False),
            }
        return result

    async def verify_predictions(self, symbol: str) -> None:
        """
        Verify past predictions against actual prices
        This should be run periodically by a background task
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Find unverified predictions that should have been realized
            sql = normalize_placeholders(
                """
                SELECT id, prediction_type, predicted_price, created_at
                FROM ai_predictions
                WHERE symbol = %s AND is_verified = FALSE
            """
            )
            cursor.execute(sql, (symbol.upper(),))
            rows = cursor.fetchall()
            conn.close()

            # Get current price
            prices = await multi_exchange_price_service.get_current_prices([symbol])
            if symbol not in prices:
                return

            current_price = prices[symbol]
            now = datetime.now(timezone.utc)

            for row in rows:
                pred_id, pred_type, predicted_price, created_at_str = row
                created_at = datetime.fromisoformat(
                    created_at_str.replace("Z", "+00:00")
                )

                # Check if prediction period has passed
                periods = {
                    "24h": timedelta(hours=24),
                    "week": timedelta(days=7),
                    "month": timedelta(days=30),
                    "year": timedelta(days=365),
                }

                period = periods.get(pred_type)
                if not period:
                    continue

                if now - created_at >= period:
                    # Prediction period has passed, verify it
                    accuracy_percent = self._calculate_accuracy(
                        predicted_price, current_price
                    )

                    conn = get_db_connection()
                    cursor = conn.cursor()

                    update_sql = normalize_placeholders(
                        """
                        UPDATE ai_predictions
                        SET is_verified = TRUE,
                            actual_price_at_target = %s,
                            accuracy_percent = %s
                        WHERE id = %s
                    """
                    )
                    cursor.execute(update_sql, (current_price, accuracy_percent, pred_id))
                    conn.commit()
                    conn.close()

                    logger.info(
                        f"Verified prediction {pred_id} for {symbol} {pred_type}: "
                        f"predicted {predicted_price}, actual {current_price}, accuracy {accuracy_percent:.1f}%"
                    )

        except Exception as e:
            logger.error(
                f"Error verifying predictions for {symbol}: {e}", exc_info=True
            )

    def _calculate_accuracy(
        self, predicted_price: float, actual_price: float
    ) -> float:
        """Calculate prediction accuracy percentage (0-100)"""
        if actual_price == 0:
            return 0.0

        error_percent = abs((predicted_price - actual_price) / actual_price) * 100
        accuracy = max(0.0, 100.0 - error_percent)
        return accuracy

    async def get_performance_stats(
        self, user_id: int, symbol: Optional[str] = None, model_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get performance statistics for predictions"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            conditions = ["user_id = %s", "is_verified = TRUE"]
            params = [user_id]

            if symbol:
                conditions.append("symbol = %s")
                params.append(symbol.upper())

            if model_name:
                conditions.append("model_name = %s")
                params.append(model_name)

            sql = normalize_placeholders(
                f"""
                SELECT 
                    COUNT(*) as total_predictions,
                    AVG(accuracy_percent) as avg_accuracy,
                    model_name,
                    symbol
                FROM ai_predictions
                WHERE {' AND '.join(conditions)}
                GROUP BY model_name, symbol
            """
            )

            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
            conn.close()

            stats = {
                "total_predictions": 0,
                "average_accuracy": 0.0,
                "by_model": {},
                "by_symbol": {},
            }

            total_accuracy = 0.0
            count = 0

            for row in rows:
                total, avg_acc, model, sym = row
                stats["total_predictions"] += total
                total_accuracy += avg_acc * total if avg_acc else 0
                count += total

                if model:
                    if model not in stats["by_model"]:
                        stats["by_model"][model] = {"count": 0, "avg_accuracy": 0.0}
                    stats["by_model"][model]["count"] += total
                    stats["by_model"][model]["avg_accuracy"] = avg_acc or 0.0

                if sym:
                    if sym not in stats["by_symbol"]:
                        stats["by_symbol"][sym] = {"count": 0, "avg_accuracy": 0.0}
                    stats["by_symbol"][sym]["count"] += total
                    stats["by_symbol"][sym]["avg_accuracy"] = avg_acc or 0.0

            if count > 0:
                stats["average_accuracy"] = total_accuracy / count

            return stats

        except Exception as e:
            logger.error(f"Error getting performance stats: {e}", exc_info=True)
            return {
                "total_predictions": 0,
                "average_accuracy": 0.0,
                "by_model": {},
                "by_symbol": {},
            }


# Singleton instance
ai_advisor_service = AIAdvisorService()

