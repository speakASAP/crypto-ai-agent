import aiohttp
import json
import logging
from typing import Dict, Optional, Any
from ..core.config import settings
from ..utils.logger import get_logger

logger = get_logger("backend.app.services.openrouter_service")


class OpenRouterService:
    """Service for interacting with OpenRouter API for AI predictions"""

    def __init__(self):
        self.api_key = settings.openrouter_api_key
        self.model = settings.openrouter_model
        self.api_url = settings.openrouter_api_url

    async def generate_prediction(
        self,
        symbol: str,
        current_price: float,
        price_trend: Dict[str, Any],
        news_summary: str,
        news_sentiment: float,
    ) -> Dict[str, Any]:
        """
        Generate price predictions using OpenRouter API

        Args:
            symbol: Cryptocurrency symbol (e.g., BTC, ETH)
            current_price: Current price in USD
            price_trend: Dictionary with price trend data (7d, 30d changes)
            news_summary: Summary of recent news
            news_sentiment: Sentiment score (-1 to 1)

        Returns:
            Dictionary with predictions for 24h, week, month, year
            Each prediction includes: predicted_price, confidence_percent, reasoning
        """
        if not self.api_key:
            logger.error("OpenRouter API key not configured")
            raise ValueError("OpenRouter API key not configured")

        prompt = self._build_prompt(
            symbol, current_price, price_trend, news_summary, news_sentiment
        )

        try:
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
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(
                            f"OpenRouter API error {response.status}: {error_text}"
                        )
                        raise Exception(f"OpenRouter API error: {response.status}")

                    data = await response.json()
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

        except Exception as e:
            logger.error(f"Error calling OpenRouter API: {e}", exc_info=True)
            raise

    def _build_prompt(
        self,
        symbol: str,
        current_price: float,
        price_trend: Dict[str, Any],
        news_summary: str,
        news_sentiment: float,
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

        prompt = f"""Analyze the cryptocurrency {symbol} and provide price predictions.

Current Data:
- Current Price: ${current_price:,.2f}
- 7-day change: {price_trend.get('change_7d', 0):.2f}%
- 30-day change: {price_trend.get('change_30d', 0):.2f}%
- News Sentiment: {sentiment_label} ({news_sentiment:.2f})

Recent News Summary:
{news_summary if news_summary else "No significant news found."}

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
- Provide concise reasoning for each prediction"""

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

