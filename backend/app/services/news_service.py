import aiohttp
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
from ..core.config import settings
from ..utils.logger import get_logger

logger = get_logger("backend.app.services.news_service")


class NewsService:
    """Service for fetching and analyzing cryptocurrency news from NewsAPI"""

    def __init__(self):
        self.api_key = settings.news_api_key
        self.api_url = settings.news_api_url
        self.cache: Dict[str, Dict] = {}
        self.cache_duration = timedelta(hours=1)

    async def fetch_news(
        self, symbol: str, days: int = 7
    ) -> List[Dict[str, any]]:
        """
        Fetch recent news for a cryptocurrency symbol

        Args:
            symbol: Cryptocurrency symbol (e.g., BTC, Bitcoin, Ethereum)
            days: Number of days to look back

        Returns:
            List of news articles with sentiment and relevance scores
        """
        if not self.api_key:
            logger.warning("NewsAPI key not configured, skipping news fetch")
            return []

        # Check cache first
        cache_key = f"{symbol}_{days}"
        if cache_key in self.cache:
            cached_data, cached_time = self.cache[cache_key]
            if datetime.now(timezone.utc) - cached_time < self.cache_duration:
                logger.debug(f"Returning cached news for {symbol}")
                return cached_data

        try:
            # Try multiple search terms for better coverage
            search_terms = [
                symbol,
                self._symbol_to_name(symbol),
                f"{symbol} cryptocurrency",
                f"{self._symbol_to_name(symbol)} crypto",
            ]

            all_articles = []
            seen_urls = set()

            for search_term in search_terms:
                articles = await self._fetch_from_newsapi(search_term, days)
                for article in articles:
                    url = article.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_articles.append(article)

            # Analyze sentiment and relevance
            analyzed_articles = []
            for article in all_articles[:20]:  # Limit to top 20 articles
                sentiment = self._analyze_sentiment(article)
                relevance = self._calculate_relevance(article, symbol)

                analyzed_articles.append(
                    {
                        "title": article.get("title", ""),
                        "description": article.get("description", ""),
                        "url": article.get("url", ""),
                        "source": article.get("source", {}).get("name", "Unknown"),
                        "published_at": article.get("publishedAt", ""),
                        "sentiment_score": sentiment,
                        "relevance_score": relevance,
                    }
                )

            # Sort by relevance and sentiment
            analyzed_articles.sort(
                key=lambda x: (x["relevance_score"] * 0.7 + abs(x["sentiment_score"]) * 0.3),
                reverse=True,
            )

            # Cache results
            self.cache[cache_key] = (analyzed_articles, datetime.now(timezone.utc))

            logger.info(f"Fetched {len(analyzed_articles)} news articles for {symbol}")
            return analyzed_articles

        except Exception as e:
            logger.error(f"Error fetching news for {symbol}: {e}", exc_info=True)
            return []

    async def _fetch_from_newsapi(
        self, query: str, days: int
    ) -> List[Dict[str, any]]:
        """Fetch articles from NewsAPI"""
        from_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
            "%Y-%m-%d"
        )

        async with aiohttp.ClientSession() as session:
            params = {
                "q": query,
                "apiKey": self.api_key,
                "language": "en",
                "sortBy": "publishedAt",
                "from": from_date,
                "pageSize": 20,
            }

            try:
                async with session.get(
                    f"{self.api_url}/everything", params=params, timeout=30
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("articles", [])
                    elif response.status == 429:
                        logger.warning(
                            "NewsAPI rate limit reached, returning empty results"
                        )
                        return []
                    else:
                        error_text = await response.text()
                        logger.warning(
                            f"NewsAPI returned status {response.status}: {error_text}"
                        )
                        return []
            except Exception as e:
                logger.error(f"Error calling NewsAPI: {e}")
                return []

    def _symbol_to_name(self, symbol: str) -> str:
        """Convert symbol to full name for better news search"""
        symbol_map = {
            "BTC": "Bitcoin",
            "ETH": "Ethereum",
            "BNB": "Binance Coin",
            "SOL": "Solana",
            "ADA": "Cardano",
            "XRP": "Ripple",
            "DOT": "Polkadot",
            "DOGE": "Dogecoin",
            "AVAX": "Avalanche",
            "MATIC": "Polygon",
            "LINK": "Chainlink",
            "UNI": "Uniswap",
            "LTC": "Litecoin",
            "ATOM": "Cosmos",
            "ETC": "Ethereum Classic",
        }
        return symbol_map.get(symbol.upper(), symbol)

    def _analyze_sentiment(self, article: Dict[str, any]) -> float:
        """
        Simple sentiment analysis based on keywords
        Returns: float between -1 (very negative) and 1 (very positive)
        """
        text = (
            article.get("title", "") + " " + article.get("description", "")
        ).lower()

        positive_words = [
            "surge",
            "rally",
            "bullish",
            "growth",
            "adoption",
            "partnership",
            "upgrade",
            "success",
            "milestone",
            "gain",
            "rise",
            "increase",
            "breakthrough",
            "innovation",
        ]

        negative_words = [
            "crash",
            "plunge",
            "bearish",
            "decline",
            "hack",
            "security breach",
            "regulation",
            "ban",
            "risk",
            "loss",
            "drop",
            "fall",
            "scam",
            "fraud",
            "warning",
        ]

        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)

        if positive_count == 0 and negative_count == 0:
            return 0.0

        # Normalize to -1 to 1 range
        total = positive_count + negative_count
        sentiment = (positive_count - negative_count) / max(total, 1)

        # Scale to be less extreme
        return max(-1.0, min(1.0, sentiment * 0.8))

    def _calculate_relevance(self, article: Dict[str, any], symbol: str) -> float:
        """
        Calculate relevance score (0 to 1) based on how well the article matches the symbol
        """
        text = (
            article.get("title", "") + " " + article.get("description", "")
        ).lower()
        symbol_lower = symbol.lower()

        # Check for direct mentions
        if symbol_lower in text:
            base_relevance = 0.8
        elif self._symbol_to_name(symbol).lower() in text:
            base_relevance = 0.7
        else:
            base_relevance = 0.3

        # Boost if in title
        if symbol_lower in article.get("title", "").lower():
            base_relevance += 0.2

        return min(1.0, base_relevance)

    def get_news_summary(self, articles: List[Dict[str, any]]) -> str:
        """Create a summary of news articles for AI prompt"""
        if not articles:
            return "No significant news found in the past 7 days."

        top_articles = articles[:5]  # Top 5 most relevant
        summary_parts = []

        for article in top_articles:
            sentiment_label = (
                "positive"
                if article["sentiment_score"] > 0.3
                else "negative"
                if article["sentiment_score"] < -0.3
                else "neutral"
            )
            summary_parts.append(
                f"- {article['title']} ({sentiment_label} sentiment, {article['source']})"
            )

        return "\n".join(summary_parts)

    def get_average_sentiment(self, articles: List[Dict[str, any]]) -> float:
        """Calculate average sentiment score from articles"""
        if not articles:
            return 0.0

        sentiments = [a["sentiment_score"] for a in articles]
        return sum(sentiments) / len(sentiments)


# Singleton instance
news_service = NewsService()
