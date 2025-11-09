"""
Redis-based rate limiting utility.
Prevents abuse by limiting the number of actions per user per time window.
"""
import time
from typing import Optional
import redis.asyncio as redis

from config.settings import settings


class RateLimiter:
    """Redis-based rate limiter for limiting user actions."""
    
    def __init__(self, redis_client: redis.Redis):
        """
        Initialize rate limiter with Redis client.
        
        Args:
            redis_client: Redis async client instance
        """
        self.redis = redis_client
    
    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int = 60
    ) -> tuple[bool, int]:
        """
        Check if an action is allowed based on rate limit.
        
        Args:
            key: Unique identifier for rate limiting (e.g., f"rate_limit:{user_id}")
            limit: Maximum number of actions allowed
            window_seconds: Time window in seconds
            
        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        current_time = int(time.time())
        window_key = f"{key}:{current_time // window_seconds}"
        
        # Get current count
        count = await self.redis.get(window_key)
        current_count = int(count) if count else 0
        
        if current_count >= limit:
            return False, 0
        
        # Increment counter
        pipe = self.redis.pipeline()
        pipe.incr(window_key)
        pipe.expire(window_key, window_seconds + 1)  # Add 1 second buffer
        await pipe.execute()
        
        return True, limit - current_count - 1
    
    async def reset_rate_limit(self, key: str) -> None:
        """
        Reset rate limit for a key.
        
        Args:
            key: Key to reset
        """
        pattern = f"{key}:*"
        async for key_name in self.redis.scan_iter(match=pattern):
            await self.redis.delete(key_name)


class MessageRateLimiter(RateLimiter):
    """Rate limiter specifically for message sending."""
    
    async def check_message_limit(self, user_id: int) -> tuple[bool, int]:
        """
        Check if user can send a message based on rate limit.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Tuple of (is_allowed, remaining_messages)
        """
        key = f"msg_rate_limit:{user_id}"
        return await self.check_rate_limit(
            key,
            settings.RATE_LIMIT_MESSAGES_PER_MINUTE,
            window_seconds=60
        )

