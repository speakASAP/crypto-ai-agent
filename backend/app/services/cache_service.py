import redis.asyncio as redis
import json
import logging
from typing import Any, Optional, List
from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    async def get(self, key: str) -> Optional[Any]:
        """Get data from cache"""
        try:
            data = await self.redis.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set data in cache with TTL"""
        try:
            await self.redis.setex(key, ttl, json.dumps(value, default=str))
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete data from cache"""
        try:
            await self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate cache by pattern"""
        try:
            keys = await self.redis.keys(pattern)
            if keys:
                return await self.redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache invalidate pattern error for {pattern}: {e}")
            return 0
    
    async def get_or_set(self, key: str, func, ttl: int = 3600) -> Any:
        """Get from cache or set using function"""
        cached = await self.get(key)
        if cached is not None:
            return cached
        
        result = await func()
        await self.set(key, result, ttl)
        return result
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            return await self.redis.exists(key) > 0
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False
    
    async def get_multiple(self, keys: List[str]) -> dict:
        """Get multiple keys from cache"""
        try:
            values = await self.redis.mget(keys)
            return {key: json.loads(value) if value else None for key, value in zip(keys, values)}
        except Exception as e:
            logger.error(f"Cache get multiple error: {e}")
            return {}
    
    async def set_multiple(self, data: dict, ttl: int = 3600) -> bool:
        """Set multiple key-value pairs"""
        try:
            pipe = self.redis.pipeline()
            for key, value in data.items():
                pipe.setex(key, ttl, json.dumps(value, default=str))
            await pipe.execute()
            return True
        except Exception as e:
            logger.error(f"Cache set multiple error: {e}")
            return False
