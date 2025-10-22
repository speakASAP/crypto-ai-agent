"""
Unit tests for Advanced Cache Service
"""
import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.advanced_cache_service import AdvancedCacheService


class TestAdvancedCacheService:
    """Test cases for AdvancedCacheService"""
    
    @pytest.fixture
    def cache_service(self):
        """Create cache service instance for testing"""
        return AdvancedCacheService()
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis connection"""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock(return_value=1)
        mock_redis.keys = AsyncMock(return_value=[])
        mock_redis.mget = AsyncMock(return_value=[])
        mock_redis.pipeline = MagicMock()
        return mock_redis
    
    @pytest.mark.asyncio
    async def test_initialize_success(self, cache_service, mock_redis):
        """Test successful cache service initialization"""
        with patch('aioredis.from_url', return_value=mock_redis):
            await cache_service.initialize()
            assert cache_service.redis is not None
    
    @pytest.mark.asyncio
    async def test_initialize_failure(self, cache_service):
        """Test cache service initialization failure"""
        with patch('aioredis.from_url', side_effect=Exception("Connection failed")):
            await cache_service.initialize()
            assert cache_service.redis is None
    
    @pytest.mark.asyncio
    async def test_close(self, cache_service, mock_redis):
        """Test cache service close"""
        cache_service.redis = mock_redis
        await cache_service.close()
        mock_redis.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_set_success(self, cache_service, mock_redis):
        """Test successful cache set operation"""
        cache_service.redis = mock_redis
        
        result = await cache_service.set("test_key", {"data": "value"}, "test", 300)
        
        assert result is True
        assert "test:test_key" in cache_service.memory_cache
        mock_redis.setex.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_memory_cache_hit(self, cache_service):
        """Test cache get from memory cache"""
        # Set up memory cache
        test_data = {"value": "test_data", "expires_at": (datetime.now() + timedelta(seconds=300)).isoformat()}
        cache_service.memory_cache["test:test_key"] = test_data
        
        result = await cache_service.get("test_key", "test", 300)
        
        assert result == "test_data"
    
    @pytest.mark.asyncio
    async def test_get_memory_cache_expired(self, cache_service):
        """Test cache get with expired memory cache"""
        # Set up expired memory cache
        expired_time = (datetime.now() - timedelta(seconds=300)).isoformat()
        test_data = {"value": "test_data", "expires_at": expired_time}
        cache_service.memory_cache["test:test_key"] = test_data
        
        result = await cache_service.get("test_key", "test", 300)
        
        assert result is None
        assert "test:test_key" not in cache_service.memory_cache
    
    @pytest.mark.asyncio
    async def test_get_redis_cache_hit(self, cache_service, mock_redis):
        """Test cache get from Redis cache"""
        cache_service.redis = mock_redis
        
        # Mock Redis response
        test_data = {
            "value": "test_data",
            "expires_at": (datetime.now() + timedelta(seconds=300)).isoformat()
        }
        mock_redis.get.return_value = json.dumps(test_data)
        
        result = await cache_service.get("test_key", "test", 300)
        
        assert result == "test_data"
        assert "test:test_key" in cache_service.memory_cache
    
    @pytest.mark.asyncio
    async def test_get_cache_miss(self, cache_service, mock_redis):
        """Test cache miss scenario"""
        cache_service.redis = mock_redis
        mock_redis.get.return_value = None
        
        result = await cache_service.get("test_key", "test", 300)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete_success(self, cache_service, mock_redis):
        """Test successful cache delete operation"""
        cache_service.redis = mock_redis
        cache_service.memory_cache["test:test_key"] = {"value": "test_data"}
        
        result = await cache_service.delete("test_key", "test")
        
        assert result is True
        assert "test:test_key" not in cache_service.memory_cache
        mock_redis.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_invalidate_pattern(self, cache_service, mock_redis):
        """Test cache pattern invalidation"""
        cache_service.redis = mock_redis
        mock_redis.keys.return_value = ["crypto_agent:test:key1", "crypto_agent:test:key2"]
        mock_redis.delete.return_value = 2
        
        # Set up memory cache
        cache_service.memory_cache["test:key1"] = {"value": "data1"}
        cache_service.memory_cache["test:key2"] = {"value": "data2"}
        
        result = await cache_service.invalidate_pattern("key*", "test")
        
        assert result == 2
        assert "test:key1" not in cache_service.memory_cache
        assert "test:key2" not in cache_service.memory_cache
    
    @pytest.mark.asyncio
    async def test_get_or_set_cache_hit(self, cache_service):
        """Test get_or_set with cache hit"""
        # Set up memory cache
        test_data = {"value": "cached_data", "expires_at": (datetime.now() + timedelta(seconds=300)).isoformat()}
        cache_service.memory_cache["test:test_key"] = test_data
        
        async def fetch_func():
            return "fresh_data"
        
        result = await cache_service.get_or_set("test_key", fetch_func, "test", 300)
        
        assert result == "cached_data"
    
    @pytest.mark.asyncio
    async def test_get_or_set_cache_miss(self, cache_service, mock_redis):
        """Test get_or_set with cache miss"""
        cache_service.redis = mock_redis
        mock_redis.get.return_value = None
        
        async def fetch_func():
            return "fresh_data"
        
        result = await cache_service.get_or_set("test_key", fetch_func, "test", 300)
        
        assert result == "fresh_data"
        assert "test:test_key" in cache_service.memory_cache
    
    @pytest.mark.asyncio
    async def test_batch_get(self, cache_service, mock_redis):
        """Test batch get operation"""
        cache_service.redis = mock_redis
        
        # Set up memory cache
        cache_service.memory_cache["test:key1"] = {"value": "data1", "expires_at": (datetime.now() + timedelta(seconds=300)).isoformat()}
        
        # Mock Redis response
        mock_redis.mget.return_value = [json.dumps({"value": "data2", "expires_at": (datetime.now() + timedelta(seconds=300)).isoformat()}), None]
        
        result = await cache_service.batch_get(["key1", "key2", "key3"], "test")
        
        assert result == {"key1": "data1", "key2": "data2"}
    
    @pytest.mark.asyncio
    async def test_batch_set(self, cache_service, mock_redis):
        """Test batch set operation"""
        cache_service.redis = mock_redis
        
        test_data = {"key1": "data1", "key2": "data2"}
        result = await cache_service.batch_set(test_data, "test", 300)
        
        assert result is True
        assert "test:key1" in cache_service.memory_cache
        assert "test:key2" in cache_service.memory_cache
    
    def test_get_stats(self, cache_service):
        """Test cache statistics"""
        # Set up some test data
        cache_service.cache_stats = {
            'hits': 10,
            'misses': 5,
            'memory_hits': 8,
            'redis_hits': 2,
            'redis_misses': 3
        }
        cache_service.memory_cache = {"key1": "data1", "key2": "data2"}
        
        stats = cache_service.get_stats()
        
        assert stats['total_requests'] == 15
        assert stats['hits'] == 10
        assert stats['misses'] == 5
        assert stats['hit_rate'] == 66.67
        assert stats['memory_cache_size'] == 2
    
    @pytest.mark.asyncio
    async def test_clear_all(self, cache_service, mock_redis):
        """Test clear all caches"""
        cache_service.redis = mock_redis
        cache_service.memory_cache = {"key1": "data1", "key2": "data2"}
        cache_service.cache_stats = {'hits': 10, 'misses': 5}
        
        mock_redis.keys.return_value = ["crypto_agent:test:key1"]
        mock_redis.delete.return_value = 1
        
        result = await cache_service.clear_all()
        
        assert result is True
        assert len(cache_service.memory_cache) == 0
        assert cache_service.cache_stats['hits'] == 0
        assert cache_service.cache_stats['misses'] == 0
