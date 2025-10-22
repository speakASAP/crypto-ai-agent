"""
Advanced Caching Service with Multi-level Caching Strategy
"""
import json
import asyncio
from typing import Any, Optional, Dict, List, Union
from datetime import datetime, timedelta
import redis.asyncio as redis
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class AdvancedCacheService:
    """
    Advanced caching service with multiple cache levels and strategies
    """
    
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'memory_hits': 0,
            'redis_hits': 0,
            'redis_misses': 0
        }
    
    async def initialize(self):
        """Initialize Redis connection"""
        try:
            self.redis = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=20,
                retry_on_timeout=True
            )
            logger.info("✅ Advanced cache service initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize cache service: {e}")
            self.redis = None
    
    async def close(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()
            logger.info("🔌 Cache service connection closed")
    
    def _get_memory_key(self, key: str, namespace: str = "default") -> str:
        """Generate namespaced memory cache key"""
        return f"{namespace}:{key}"
    
    def _get_redis_key(self, key: str, namespace: str = "default") -> str:
        """Generate namespaced Redis cache key"""
        return f"crypto_agent:{namespace}:{key}"
    
    def _is_expired(self, cached_data: Dict[str, Any]) -> bool:
        """Check if cached data is expired"""
        if 'expires_at' not in cached_data:
            return True
        return datetime.now() > datetime.fromisoformat(cached_data['expires_at'])
    
    async def get(self, key: str, namespace: str = "default", ttl: int = 300) -> Optional[Any]:
        """
        Get value from cache with multi-level strategy
        
        Strategy:
        1. Check memory cache first (fastest)
        2. Check Redis cache (fast)
        3. Return None if not found
        """
        try:
            # Level 1: Memory cache
            memory_key = self._get_memory_key(key, namespace)
            if memory_key in self.memory_cache:
                cached_data = self.memory_cache[memory_key]
                if not self._is_expired(cached_data):
                    self.cache_stats['hits'] += 1
                    self.cache_stats['memory_hits'] += 1
                    logger.debug(f"💾 Memory cache hit: {key}")
                    return cached_data['value']
                else:
                    # Remove expired entry
                    del self.memory_cache[memory_key]
            
            # Level 2: Redis cache
            if self.redis:
                redis_key = self._get_redis_key(key, namespace)
                cached_value = await self.redis.get(redis_key)
                
                if cached_value:
                    try:
                        cached_data = json.loads(cached_value)
                        if not self._is_expired(cached_data):
                            # Store in memory cache for faster access
                            self.memory_cache[memory_key] = cached_data
                            self.cache_stats['hits'] += 1
                            self.cache_stats['redis_hits'] += 1
                            logger.debug(f"🔴 Redis cache hit: {key}")
                            return cached_data['value']
                        else:
                            # Remove expired entry from Redis
                            await self.redis.delete(redis_key)
                    except json.JSONDecodeError:
                        logger.warning(f"⚠️ Invalid JSON in cache: {key}")
                        await self.redis.delete(redis_key)
            
            self.cache_stats['misses'] += 1
            if self.redis:
                self.cache_stats['redis_misses'] += 1
            logger.debug(f"❌ Cache miss: {key}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Cache get error for {key}: {e}")
            return None
    
    async def set(self, key: str, value: Any, namespace: str = "default", ttl: int = 300) -> bool:
        """
        Set value in cache with multi-level strategy
        
        Strategy:
        1. Store in memory cache (fastest access)
        2. Store in Redis cache (persistent)
        """
        try:
            expires_at = datetime.now() + timedelta(seconds=ttl)
            cached_data = {
                'value': value,
                'expires_at': expires_at.isoformat(),
                'created_at': datetime.now().isoformat()
            }
            
            # Level 1: Memory cache
            memory_key = self._get_memory_key(key, namespace)
            self.memory_cache[memory_key] = cached_data
            
            # Level 2: Redis cache
            if self.redis:
                redis_key = self._get_redis_key(key, namespace)
                await self.redis.setex(
                    redis_key,
                    ttl,
                    json.dumps(cached_data, default=str)
                )
            
            logger.debug(f"💾 Cached: {key} (TTL: {ttl}s)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Cache set error for {key}: {e}")
            return False
    
    async def delete(self, key: str, namespace: str = "default") -> bool:
        """Delete value from all cache levels"""
        try:
            # Level 1: Memory cache
            memory_key = self._get_memory_key(key, namespace)
            if memory_key in self.memory_cache:
                del self.memory_cache[memory_key]
            
            # Level 2: Redis cache
            if self.redis:
                redis_key = self._get_redis_key(key, namespace)
                await self.redis.delete(redis_key)
            
            logger.debug(f"🗑️ Deleted from cache: {key}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Cache delete error for {key}: {e}")
            return False
    
    async def invalidate_pattern(self, pattern: str, namespace: str = "default") -> int:
        """Invalidate all keys matching pattern"""
        try:
            deleted_count = 0
            
            # Level 1: Memory cache
            memory_pattern = self._get_memory_key(pattern, namespace)
            keys_to_delete = [k for k in self.memory_cache.keys() if memory_pattern in k]
            for key in keys_to_delete:
                del self.memory_cache[key]
                deleted_count += 1
            
            # Level 2: Redis cache
            if self.redis:
                redis_pattern = self._get_redis_key(pattern, namespace)
                keys = await self.redis.keys(redis_pattern)
                if keys:
                    deleted_count += await self.redis.delete(*keys)
            
            logger.info(f"🗑️ Invalidated {deleted_count} keys matching pattern: {pattern}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"❌ Cache invalidation error for pattern {pattern}: {e}")
            return 0
    
    async def get_or_set(self, key: str, fetch_func, namespace: str = "default", ttl: int = 300) -> Any:
        """
        Get from cache or fetch and cache the result
        
        This is the most commonly used method for caching expensive operations
        """
        # Try to get from cache first
        cached_value = await self.get(key, namespace, ttl)
        if cached_value is not None:
            return cached_value
        
        # Cache miss - fetch the data
        try:
            if asyncio.iscoroutinefunction(fetch_func):
                value = await fetch_func()
            else:
                value = fetch_func()
            
            # Cache the result
            await self.set(key, value, namespace, ttl)
            return value
            
        except Exception as e:
            logger.error(f"❌ Error in get_or_set for {key}: {e}")
            raise
    
    async def batch_get(self, keys: List[str], namespace: str = "default") -> Dict[str, Any]:
        """Get multiple keys efficiently"""
        results = {}
        
        # Check memory cache first
        memory_keys = [self._get_memory_key(key, namespace) for key in keys]
        for i, memory_key in enumerate(memory_keys):
            if memory_key in self.memory_cache:
                cached_data = self.memory_cache[memory_key]
                if not self._is_expired(cached_data):
                    results[keys[i]] = cached_data['value']
                    self.cache_stats['memory_hits'] += 1
        
        # Check Redis for remaining keys
        remaining_keys = [key for key in keys if key not in results]
        if remaining_keys and self.redis:
            redis_keys = [self._get_redis_key(key, namespace) for key in remaining_keys]
            redis_values = await self.redis.mget(redis_keys)
            
            for i, redis_value in enumerate(redis_values):
                if redis_value:
                    try:
                        cached_data = json.loads(redis_value)
                        if not self._is_expired(cached_data):
                            key = remaining_keys[i]
                            results[key] = cached_data['value']
                            # Store in memory cache
                            memory_key = self._get_memory_key(key, namespace)
                            self.memory_cache[memory_key] = cached_data
                            self.cache_stats['redis_hits'] += 1
                    except json.JSONDecodeError:
                        continue
        
        self.cache_stats['hits'] += len(results)
        self.cache_stats['misses'] += len(keys) - len(results)
        
        return results
    
    async def batch_set(self, data: Dict[str, Any], namespace: str = "default", ttl: int = 300) -> bool:
        """Set multiple keys efficiently"""
        try:
            # Memory cache
            for key, value in data.items():
                memory_key = self._get_memory_key(key, namespace)
                expires_at = datetime.now() + timedelta(seconds=ttl)
                self.memory_cache[memory_key] = {
                    'value': value,
                    'expires_at': expires_at.isoformat(),
                    'created_at': datetime.now().isoformat()
                }
            
            # Redis cache
            if self.redis:
                pipe = self.redis.pipeline()
                for key, value in data.items():
                    redis_key = self._get_redis_key(key, namespace)
                    expires_at = datetime.now() + timedelta(seconds=ttl)
                    cached_data = {
                        'value': value,
                        'expires_at': expires_at.isoformat(),
                        'created_at': datetime.now().isoformat()
                    }
                    pipe.setex(redis_key, ttl, json.dumps(cached_data, default=str))
                await pipe.execute()
            
            logger.debug(f"💾 Batch cached {len(data)} keys")
            return True
            
        except Exception as e:
            logger.error(f"❌ Batch cache set error: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
        hit_rate = (self.cache_stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'total_requests': total_requests,
            'hits': self.cache_stats['hits'],
            'misses': self.cache_stats['misses'],
            'hit_rate': round(hit_rate, 2),
            'memory_hits': self.cache_stats['memory_hits'],
            'redis_hits': self.cache_stats['redis_hits'],
            'redis_misses': self.cache_stats['redis_misses'],
            'memory_cache_size': len(self.memory_cache)
        }
    
    async def clear_all(self) -> bool:
        """Clear all caches"""
        try:
            # Clear memory cache
            self.memory_cache.clear()
            
            # Clear Redis cache
            if self.redis:
                keys = await self.redis.keys("crypto_agent:*")
                if keys:
                    await self.redis.delete(*keys)
            
            # Reset stats
            self.cache_stats = {
                'hits': 0,
                'misses': 0,
                'memory_hits': 0,
                'redis_hits': 0,
                'redis_misses': 0
            }
            
            logger.info("🗑️ All caches cleared")
            return True
            
        except Exception as e:
            logger.error(f"❌ Clear all caches error: {e}")
            return False

# Global cache service instance
cache_service = AdvancedCacheService()
