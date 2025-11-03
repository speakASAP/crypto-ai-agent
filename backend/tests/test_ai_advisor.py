"""
Tests for AI Advisor functionality
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta, timezone

# Mock imports
import sys
sys.path.insert(0, 'backend')

from app.services.openrouter_service import OpenRouterService
from app.services.news_service import NewsService
from app.services.historical_price_service import HistoricalPriceService
from app.services.ai_advisor_service import AIAdvisorService


class TestOpenRouterService:
    """Tests for OpenRouter service"""

    @pytest.mark.asyncio
    async def test_generate_prediction_success(self):
        """Test successful prediction generation"""
        service = OpenRouterService()
        
        # Mock the API response
        mock_response = {
            "choices": [{
                "message": {
                    "content": '{"predictions": {"24h": {"predicted_price": 65000, "confidence_percent": 75, "reasoning": "Test"}, "week": {"predicted_price": 66000, "confidence_percent": 70, "reasoning": "Test"}, "month": {"predicted_price": 68000, "confidence_percent": 65, "reasoning": "Test"}, "year": {"predicted_price": 75000, "confidence_percent": 60, "reasoning": "Test"}}}'
                }
            }]
        }

        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response_obj = AsyncMock()
            mock_response_obj.status = 200
            mock_response_obj.json = AsyncMock(return_value=mock_response)
            mock_post.return_value.__aenter__.return_value = mock_response_obj

            result = await service.generate_prediction(
                symbol="BTC",
                current_price=64000,
                price_trend={"change_7d": 2.5, "change_30d": 5.0},
                news_summary="Positive news",
                news_sentiment=0.6
            )

            assert "predictions" in result
            assert "24h" in result["predictions"]
            assert result["predictions"]["24h"]["predicted_price"] == 65000

    @pytest.mark.asyncio
    async def test_generate_prediction_api_error(self):
        """Test handling of API errors"""
        service = OpenRouterService()
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response_obj = AsyncMock()
            mock_response_obj.status = 500
            mock_response_obj.text = AsyncMock(return_value="Internal Server Error")
            mock_post.return_value.__aenter__.return_value = mock_response_obj

            with pytest.raises(Exception):
                await service.generate_prediction(
                    symbol="BTC",
                    current_price=64000,
                    price_trend={},
                    news_summary="",
                    news_sentiment=0.0
                )


class TestNewsService:
    """Tests for News service"""

    def test_analyze_sentiment_positive(self):
        """Test sentiment analysis for positive news"""
        service = NewsService()
        
        article = {
            "title": "Bitcoin surges to new all-time high",
            "description": "Major adoption milestone achieved"
        }
        
        sentiment = service._analyze_sentiment(article)
        assert sentiment > 0

    def test_analyze_sentiment_negative(self):
        """Test sentiment analysis for negative news"""
        service = NewsService()
        
        article = {
            "title": "Bitcoin crashes following security breach",
            "description": "Major security concerns arise"
        }
        
        sentiment = service._analyze_sentiment(article)
        assert sentiment < 0

    def test_analyze_sentiment_neutral(self):
        """Test sentiment analysis for neutral news"""
        service = NewsService()
        
        article = {
            "title": "Cryptocurrency market update",
            "description": "Regular market analysis report"
        }
        
        sentiment = service._analyze_sentiment(article)
        assert -0.3 <= sentiment <= 0.3

    def test_calculate_relevance(self):
        """Test relevance calculation"""
        service = NewsService()
        
        article = {
            "title": "Bitcoin price analysis",
            "description": "BTC shows strong performance"
        }
        
        relevance = service._calculate_relevance(article, "BTC")
        assert 0 <= relevance <= 1
        assert relevance > 0.5  # Should be relevant if symbol is mentioned

    def test_symbol_to_name(self):
        """Test symbol to name conversion"""
        service = NewsService()
        
        assert service._symbol_to_name("BTC") == "Bitcoin"
        assert service._symbol_to_name("ETH") == "Ethereum"
        assert service._symbol_to_name("UNKNOWN") == "UNKNOWN"

    def test_get_average_sentiment(self):
        """Test average sentiment calculation"""
        service = NewsService()
        
        articles = [
            {"sentiment_score": 0.5},
            {"sentiment_score": -0.3},
            {"sentiment_score": 0.7}
        ]
        
        avg = service.get_average_sentiment(articles)
        assert avg == pytest.approx(0.3, abs=0.1)

    def test_get_news_summary(self):
        """Test news summary generation"""
        service = NewsService()
        
        articles = [
            {
                "title": "Test Article 1",
                "sentiment_score": 0.5,
                "source": "TestSource"
            }
        ]
        
        summary = service.get_news_summary(articles)
        assert "Test Article 1" in summary
        assert "positive" in summary.lower() or "TestSource" in summary


class TestHistoricalPriceService:
    """Tests for Historical Price service"""

    def test_symbol_to_coingecko_id(self):
        """Test symbol to CoinGecko ID mapping"""
        service = HistoricalPriceService()
        
        # The method returns a string (CoinGecko ID)
        result = service._symbol_to_coingecko_id("BTC")
        assert result == "bitcoin"
        
        result_eth = service._symbol_to_coingecko_id("ETH")
        assert result_eth == "ethereum"
        
        # Unknown symbol should return lowercase symbol
        result_unknown = service._symbol_to_coingecko_id("UNKNOWN")
        assert result_unknown == "unknown"

    @pytest.mark.asyncio
    async def test_get_price_history_success(self):
        """Test successful price history fetching"""
        service = HistoricalPriceService()
        
        mock_data = {
            "prices": [
                [1609459200000, 29000.0],  # Timestamp in ms, price
                [1609545600000, 31000.0]
            ]
        }

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response_obj = AsyncMock()
            mock_response_obj.status = 200
            mock_response_obj.json = AsyncMock(return_value=mock_data)
            mock_get.return_value.__aenter__.return_value = mock_response_obj

            # Mock cache methods
            with patch.object(service, '_get_from_cache', return_value=None):
                with patch.object(service, '_save_to_cache'):
                    history = await service.get_price_history("BTC", days=30)

                    assert len(history) == 2
                    assert history[0]["price"] == 29000.0
                    assert "timestamp" in history[0]
                    assert "date" in history[0]

    def test_get_mini_chart_data(self):
        """Test mini chart data extraction"""
        service = HistoricalPriceService()
        
        # Create mock cached data
        now = datetime.now(timezone.utc)
        mock_history = [
            {
                "timestamp": int((now - timedelta(days=10)).timestamp()),
                "price": 60000,
                "date": (now - timedelta(days=10)).isoformat()
            },
            {
                "timestamp": int((now - timedelta(days=5)).timestamp()),
                "price": 62000,
                "date": (now - timedelta(days=5)).isoformat()
            },
            {
                "timestamp": int((now - timedelta(days=1)).timestamp()),
                "price": 64000,
                "date": (now - timedelta(days=1)).isoformat()
            }
        ]

        with patch.object(service, '_get_from_cache', return_value=mock_history):
            mini_data = service.get_mini_chart_data("BTC", days=7)
            
            # Should only return last 7 days
            assert len(mini_data) <= 7
            assert all(point["timestamp"] >= int((now - timedelta(days=7)).timestamp()) 
                      for point in mini_data)


class TestAIAdvisorService:
    """Tests for AI Advisor service"""

    def test_calculate_accuracy(self):
        """Test accuracy calculation"""
        service = AIAdvisorService()
        
        # Perfect prediction
        accuracy = service._calculate_accuracy(100.0, 100.0)
        assert accuracy == 100.0
        
        # 10% error
        accuracy = service._calculate_accuracy(110.0, 100.0)
        assert accuracy == pytest.approx(90.0, abs=0.1)
        
        # 20% error
        accuracy = service._calculate_accuracy(120.0, 100.0)
        assert accuracy == pytest.approx(80.0, abs=0.1)

    @pytest.mark.asyncio
    async def test_get_latest_predictions(self):
        """Test fetching latest predictions from database"""
        service = AIAdvisorService()
        
        # This would require mocking the database connection
        # For now, just test the method exists and has correct structure
        assert hasattr(service, '_get_latest_predictions')

    @pytest.mark.asyncio
    async def test_format_predictions_response(self):
        """Test prediction response formatting"""
        service = AIAdvisorService()
        
        predictions = [
            {
                "id": 1,
                "prediction_type": "24h",
                "predicted_price": 65000,
                "confidence_percent": 75,
                "reasoning": "Test",
                "model_name": "gpt-4",
                "created_at": datetime.now(timezone.utc).isoformat() + "Z",
                "is_verified": False
            }
        ]
        
        result = service._format_predictions_response(predictions)
        
        assert "24h" in result
        assert result["24h"]["predicted_price"] == 65000
        assert result["24h"]["confidence_percent"] == 75


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

