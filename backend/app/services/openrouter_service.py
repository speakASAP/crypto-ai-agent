import aiohttp
import json
import logging
import asyncio
import time
from typing import Dict, Optional, Any, List
from ..core.config import settings
from ..utils.logger import get_logger

logger = get_logger("backend.app.services.openrouter_service")


class RateLimitError(Exception):
    """Custom exception for rate limit errors"""
    pass


class OpenRouterService:
    """Service for interacting with OpenRouter API for AI predictions"""

    def __init__(self):
        self.api_key = settings.openrouter_api_key
        self.model = settings.openrouter_model
        self.api_url = settings.openrouter_api_url
        # Semaphore to limit concurrent requests (max 2 concurrent requests to avoid rate limits)
        self._request_semaphore = asyncio.Semaphore(2)
        # Minimum delay between requests (in seconds)
        self._min_request_delay = 2.0
        self._last_request_time = 0.0

    async def generate_prediction(
        self,
        symbol: str,
        current_price: float,
        price_trend: Dict[str, Any],
        news_summary: str,
        news_sentiment: float,
        news_articles: List[Dict[str, Any]] = None,
        max_retries: int = 1,  # Reduced to 1 retry to fail faster
    ) -> Dict[str, Any]:
        """
        Generate price predictions using OpenRouter API

        Args:
            symbol: Cryptocurrency symbol (e.g., BTC, ETH)
            current_price: Current price in USD
            price_trend: Dictionary with price trend data (7d, 30d changes)
            news_summary: Summary of recent news
            news_sentiment: Sentiment score (-1 to 1)
            max_retries: Maximum number of retries for rate limit errors (default: 3)

        Returns:
            Dictionary with predictions for 24h, week, month, year
            Each prediction includes: predicted_price, confidence_percent, reasoning
        """
        if not self.api_key:
            logger.error("OpenRouter API key not configured")
            raise ValueError("OpenRouter API key not configured")

        prompt = self._build_prompt(
            symbol, current_price, price_trend, news_summary, news_sentiment, news_articles
        )

        # Use semaphore to limit concurrent requests
        async with self._request_semaphore:
            # Ensure minimum delay between requests
            current_time = time.time()
            time_since_last_request = current_time - self._last_request_time
            if time_since_last_request < self._min_request_delay:
                wait_time = self._min_request_delay - time_since_last_request
                logger.debug(f"Waiting {wait_time:.2f}s before next OpenRouter request to avoid rate limits")
                await asyncio.sleep(wait_time)

            for attempt in range(max_retries + 1):
                try:
                    self._last_request_time = time.time()
                    async with aiohttp.ClientSession() as session:
                        headers = {
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://crypto-ai-agent.com",
                            "X-Title": "Crypto AI Agent",
                        }

                        payload = {
                            "model": self.model,
                            "messages": [
                                {
                                    "role": "system",
                                    "content": "You are a cryptocurrency market analyst. Provide price predictions in JSON format with specific timeframes.",
                                },
                                {"role": "user", "content": prompt},
                            ],
                            "temperature": 0.7,
                            "response_format": {"type": "json_object"},
                        }

                        async with session.post(
                            f"{self.api_url}/chat/completions",
                            headers=headers,
                            json=payload,
                            timeout=aiohttp.ClientTimeout(total=30),  # Reduced timeout to 30s to fail faster
                        ) as response:
                            if response.status == 429:
                                # Rate limit error - fail fast to avoid timeout
                                try:
                                    error_text = await response.text()
                                except:
                                    error_text = "Rate limit error"
                                retry_after = response.headers.get("Retry-After")
                                
                                logger.warning(
                                    f"OpenRouter API rate limit (429) for {symbol}, attempt {attempt + 1}/{max_retries + 1}"
                                )
                                
                                # Only retry once if Retry-After is very short (< 5 seconds)
                                if attempt < max_retries and retry_after:
                                    try:
                                        wait_time = float(retry_after)
                                        if wait_time < 5:  # Only retry if wait time is short
                                            logger.info(
                                                f"Retrying after {wait_time} seconds (short wait)"
                                            )
                                            await asyncio.sleep(wait_time)
                                            continue
                                    except ValueError:
                                        pass
                                
                                # Fail fast for rate limits
                                raise RateLimitError(
                                    f"OpenRouter API rate limit exceeded. "
                                    "Please try again later or add your own API key to accumulate rate limits."
                                )
                            elif response.status != 200:
                                try:
                                    error_text = await response.text()
                                except:
                                    error_text = f"HTTP {response.status}"
                                logger.error(
                                    f"OpenRouter API error {response.status}: {error_text}"
                                )
                                raise Exception(f"OpenRouter API error: {response.status}")

                            # Read response data INSIDE the context manager
                            try:
                                data = await response.json()
                            except aiohttp.ClientConnectionError as e:
                                logger.error(f"Connection closed while reading response for {symbol}: {e}")
                                raise Exception(f"Connection closed: {e}")
                            except Exception as e:
                                logger.error(f"Error reading response JSON for {symbol}: {e}")
                                raise Exception(f"Failed to read response: {e}")
                            
                            content = data.get("choices", [{}])[0].get("message", {}).get(
                                "content", "{}"
                            )

                        # Parse JSON response
                        try:
                            predictions = json.loads(content)
                            logger.info(
                                f"Successfully generated predictions for {symbol} using model {self.model}"
                            )
                            return predictions
                        except json.JSONDecodeError as e:
                            logger.error(
                                f"Failed to parse OpenRouter response as JSON: {e}, content: {content}"
                            )
                            # Fallback: try to extract predictions from text
                            return self._parse_fallback_predictions(content, current_price)

                except RateLimitError:
                    # Re-raise rate limit errors immediately (no retries)
                    raise
                except Exception as e:
                    # For other errors, retry once if we have attempts left
                    if attempt < max_retries:
                        logger.warning(f"Error on attempt {attempt + 1}, retrying: {e}")
                        await asyncio.sleep(2)  # Short delay before retry
                        continue
                    else:
                        logger.error(f"Error calling OpenRouter API: {e}", exc_info=True)
                        raise

            # This should never be reached, but just in case
            raise Exception(f"Failed to generate predictions after {max_retries + 1} attempts")

    def _build_prompt(
        self,
        symbol: str,
        current_price: float,
        price_trend: Dict[str, Any],
        news_summary: str,
        news_sentiment: float,
        news_articles: List[Dict[str, Any]] = None,
    ) -> str:
        """Build the prediction prompt for the AI model"""
        sentiment_label = (
            "very positive"
            if news_sentiment > 0.5
            else "positive"
            if news_sentiment > 0
            else "neutral"
            if news_sentiment == 0
            else "negative"
            if news_sentiment > -0.5
            else "very negative"
        )

        # Build news sources section with URLs
        news_sources_text = ""
        if news_articles and len(news_articles) > 0:
            news_sources_text = "\n\nNews Sources (for reference):\n"
            for idx, article in enumerate(news_articles[:5], 1):  # Top 5 most relevant
                title = article.get("title", "Untitled")
                url = article.get("url", "")
                source = article.get("source", "Unknown")
                if url:
                    news_sources_text += f"[{idx}] {title} - {source}\n   URL: {url}\n"

        prompt = f"""Analyze the cryptocurrency {symbol} and provide price predictions.

Current Data:
- Current Price: ${current_price:,.2f}
- 7-day change: {price_trend.get('change_7d', 0):.2f}%
- 30-day change: {price_trend.get('change_30d', 0):.2f}%
- News Sentiment: {sentiment_label} ({news_sentiment:.2f})

Recent News Summary:
{news_summary if news_summary else "No significant news found."}
{news_sources_text}

Provide predictions in JSON format with the following structure:
{{
  "predictions": {{
    "24h": {{
      "predicted_price": <number>,
      "confidence_percent": <number 0-100>,
      "reasoning": "<brief explanation>"
    }},
    "week": {{
      "predicted_price": <number>,
      "confidence_percent": <number 0-100>,
      "reasoning": "<brief explanation>"
    }},
    "month": {{
      "predicted_price": <number>,
      "confidence_percent": <number 0-100>,
      "reasoning": "<brief explanation>"
    }},
    "year": {{
      "predicted_price": <number>,
      "confidence_percent": <number 0-100>,
      "reasoning": "<brief explanation>"
    }}
  }}
}}

Important:
- Predicted prices should be realistic based on current market conditions
- Confidence should reflect data quality and market volatility
- Shorter-term predictions (24h, week) should have higher confidence
- Consider news sentiment and price trends in your analysis
- Provide concise reasoning for each prediction
- If referencing news, you can mention sources by number [1], [2], etc. from the News Sources list above"""

        return prompt

    def _parse_fallback_predictions(
        self, content: str, current_price: float
    ) -> Dict[str, Any]:
        """Fallback parser if JSON parsing fails - provides conservative predictions"""
        logger.warning("Using fallback predictions due to JSON parse failure")
        # Provide conservative predictions as fallback
        return {
            "predictions": {
                "24h": {
                    "predicted_price": current_price * 1.01,
                    "confidence_percent": 50,
                    "reasoning": "Conservative prediction due to parsing error",
                },
                "week": {
                    "predicted_price": current_price * 1.02,
                    "confidence_percent": 45,
                    "reasoning": "Conservative prediction due to parsing error",
                },
                "month": {
                    "predicted_price": current_price * 1.05,
                    "confidence_percent": 40,
                    "reasoning": "Conservative prediction due to parsing error",
                },
                "year": {
                    "predicted_price": current_price * 1.15,
                    "confidence_percent": 35,
                    "reasoning": "Conservative prediction due to parsing error",
                },
            }
        }


# Singleton instance
openrouter_service = OpenRouterService()

