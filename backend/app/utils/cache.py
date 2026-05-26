"""
Redis Cache Utilities.

This module provides async Redis connection management and caching
utilities for the application.

Example Usage:
    from app.utils.cache import get_cache, set_cache, init_redis_connection
    
    # Store data in cache
    await set_cache("user:123", {"name": "John"}, ttl=3600)
    
    # Retrieve from cache
    user = await get_cache("user:123")
    
    # Delete from cache
    await delete_cache("user:123")
"""

import json
import logging
from typing import Any, Optional, Union

import redis.asyncio as redis
from redis.exceptions import RedisError

from app.config import settings

logger = logging.getLogger(__name__)

# Global Redis client
_redis_client: Optional[redis.Redis] = None


async def init_redis_connection() -> None:
    """
    Initialize the Redis connection.
    
    Creates a Redis connection pool and client. Should be called
    once during application startup.
    
    Raises:
        RedisError: If connection to Redis fails
        
    Example:
        >>> await init_redis_connection()
        >>> # Redis is now ready for use
    """
    global _redis_client
    
    logger.info(
        "Initializing Redis connection",
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
    )
    
    try:
        _redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password or None,
            db=settings.redis_db,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True,
        )
        
        # Test the connection
        await _redis_client.ping()
        
        logger.info("Redis connection initialized successfully")
        
    except RedisError as e:
        logger.error(f"Failed to initialize Redis connection: {e}")
        # Don't raise - Redis is optional for basic functionality
        _redis_client = None


async def close_redis_connection() -> None:
    """
    Close the Redis connection.
    
    Should be called during application shutdown to properly
    release the connection.
    
    Example:
        >>> await close_redis_connection()
        >>> # Redis connection is now closed
    """
    global _redis_client
    
    if _redis_client is not None:
        logger.info("Closing Redis connection")
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis connection closed")


async def check_redis_health() -> bool:
    """
    Check Redis connection health.
    
    Returns:
        bool: True if Redis is healthy, False otherwise
        
    Example:
        >>> is_healthy = await check_redis_health()
        >>> print(f"Redis healthy: {is_healthy}")
    """
    if _redis_client is None:
        return False
    
    try:
        await _redis_client.ping()
        return True
    except RedisError as e:
        logger.warning(f"Redis health check failed: {e}")
        return False


async def get_cache(key: str) -> Optional[Any]:
    """
    Get a value from cache.
    
    Args:
        key: Cache key
        
    Returns:
        Cached value or None if not found
        
    Example:
        >>> await set_cache("my_key", {"data": "value"})
        >>> result = await get_cache("my_key")
        >>> print(result)  # {"data": "value"}
    """
    if _redis_client is None:
        logger.debug("Redis not available, cache miss")
        return None
    
    try:
        value = await _redis_client.get(key)
        if value is None:
            return None
        
        # Try to deserialize JSON
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
            
    except RedisError as e:
        logger.warning(f"Redis get error for key {key}: {e}")
        return None


async def set_cache(
    key: str,
    value: Any,
    ttl: Optional[int] = None,
) -> bool:
    """
    Set a value in cache.
    
    Args:
        key: Cache key
        value: Value to cache (will be JSON serialized if not string)
        ttl: Time-to-live in seconds (default from settings)
        
    Returns:
        bool: True if successful, False otherwise
        
    Example:
        >>> await set_cache("user:123", {"name": "John"}, ttl=3600)
        >>> # Value is cached for 1 hour
    """
    if _redis_client is None:
        logger.debug("Redis not available, cache set skipped")
        return False
    
    if ttl is None:
        ttl = settings.cache_ttl_default
    
    try:
        # Serialize non-string values to JSON
        if not isinstance(value, str):
            value = json.dumps(value)
        
        await _redis_client.setex(key, ttl, value)
        return True
        
    except RedisError as e:
        logger.warning(f"Redis set error for key {key}: {e}")
        return False


async def delete_cache(key: str) -> bool:
    """
    Delete a value from cache.
    
    Args:
        key: Cache key to delete
        
    Returns:
        bool: True if key was deleted, False otherwise
        
    Example:
        >>> await delete_cache("user:123")
        >>> # Key is now deleted
    """
    if _redis_client is None:
        return False
    
    try:
        result = await _redis_client.delete(key)
        return result > 0
        
    except RedisError as e:
        logger.warning(f"Redis delete error for key {key}: {e}")
        return False


async def delete_pattern(pattern: str) -> int:
    """
    Delete all keys matching a pattern.
    
    Args:
        pattern: Key pattern (e.g., "user:*")
        
    Returns:
        int: Number of keys deleted
        
    Example:
        >>> await delete_pattern("session:*")
        >>> # All session keys are deleted
    """
    if _redis_client is None:
        return 0
    
    try:
        keys = []
        async for key in _redis_client.scan_iter(pattern):
            keys.append(key)
        
        if keys:
            return await _redis_client.delete(*keys)
        return 0
        
    except RedisError as e:
        logger.warning(f"Redis delete pattern error for {pattern}: {e}")
        return 0


async def increment(key: str, amount: int = 1) -> Optional[int]:
    """
    Increment a counter in cache.
    
    Args:
        key: Cache key
        amount: Amount to increment by
        
    Returns:
        New value after increment, or None on error
        
    Example:
        >>> await increment("page_views:home")
        >>> count = await increment("page_views:home")
        >>> print(count)  # 2
    """
    if _redis_client is None:
        return None
    
    try:
        return await _redis_client.incrby(key, amount)
    except RedisError as e:
        logger.warning(f"Redis increment error for key {key}: {e}")
        return None


async def get_or_set(
    key: str,
    factory: callable,
    ttl: Optional[int] = None,
) -> Any:
    """
    Get value from cache, or compute and cache it.
    
    Args:
        key: Cache key
        factory: Async function to compute value if not cached
        ttl: Time-to-live in seconds
        
    Returns:
        Cached or computed value
        
    Example:
        >>> async def fetch_user(user_id: int):
        ...     return await db.get_user(user_id)
        >>> 
        >>> user = await get_or_set(
        ...     f"user:{user_id}",
        ...     lambda: fetch_user(user_id),
        ...     ttl=3600
        ... )
    """
    # Try to get from cache
    cached = await get_cache(key)
    if cached is not None:
        return cached
    
    # Compute value
    if callable(factory):
        value = await factory() if hasattr(factory, '__await__') else factory()
    else:
        value = factory
    
    # Cache the value
    await set_cache(key, value, ttl)
    
    return value


class RateLimiter:
    """
    Simple rate limiter using Redis.
    
    Implements sliding window rate limiting.
    
    Attributes:
        key_prefix: Prefix for rate limit keys
        max_requests: Maximum requests per window
        window_seconds: Window size in seconds
        
    Example:
        >>> limiter = RateLimiter("api", max_requests=100, window_seconds=60)
        >>> 
        >>> if await limiter.is_allowed("user:123"):
        ...     # Process request
        ... else:
        ...     raise RateLimitError()
    """
    
    def __init__(
        self,
        key_prefix: str,
        max_requests: int = 100,
        window_seconds: int = 60,
    ) -> None:
        """
        Initialize rate limiter.
        
        Args:
            key_prefix: Prefix for rate limit keys
            max_requests: Maximum requests per window
            window_seconds: Window size in seconds
        """
        self.key_prefix = key_prefix
        self.max_requests = max_requests
        self.window_seconds = window_seconds
    
    async def is_allowed(self, identifier: str) -> bool:
        """
        Check if request is allowed under rate limit.
        
        Args:
            identifier: Unique identifier (e.g., user ID, IP)
            
        Returns:
            bool: True if request is allowed
        """
        if _redis_client is None:
            # Allow all requests if Redis is unavailable
            return True
        
        key = f"ratelimit:{self.key_prefix}:{identifier}"
        
        try:
            current = await _redis_client.incr(key)
            
            if current == 1:
                # Set expiration on first request
                await _redis_client.expire(key, self.window_seconds)
            
            return current <= self.max_requests
            
        except RedisError as e:
            logger.warning(f"Rate limit check error: {e}")
            return True  # Allow on error
    
    async def get_remaining(self, identifier: str) -> int:
        """
        Get remaining requests for identifier.
        
        Args:
            identifier: Unique identifier
            
        Returns:
            int: Remaining requests in current window
        """
        if _redis_client is None:
            return self.max_requests
        
        key = f"ratelimit:{self.key_prefix}:{identifier}"
        
        try:
            current = await _redis_client.get(key)
            if current is None:
                return self.max_requests
            return max(0, self.max_requests - int(current))
            
        except RedisError:
            return self.max_requests
    
    async def reset(self, identifier: str) -> bool:
        """
        Reset rate limit for identifier.
        
        Args:
            identifier: Unique identifier
            
        Returns:
            bool: True if reset successful
        """
        key = f"ratelimit:{self.key_prefix}:{identifier}"
        return await delete_cache(key)


def get_redis_client() -> Optional[redis.Redis]:
    """
    Get the current Redis client.
    
    Returns:
        Optional[redis.Redis]: The Redis client or None if not initialized
    """
    return _redis_client