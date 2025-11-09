"""
Rate limiting middleware for aiogram.
Prevents users from sending too many messages too quickly.
"""
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message

from utils.rate_limiter import MessageRateLimiter


class RateLimitMiddleware(BaseMiddleware):
    """Middleware for rate limiting message sending."""
    
    def __init__(self, rate_limiter: MessageRateLimiter):
        """
        Initialize rate limit middleware.
        
        Args:
            rate_limiter: MessageRateLimiter instance
        """
        self.rate_limiter = rate_limiter
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        Process middleware call.
        
        Args:
            handler: Handler function
            event: Telegram event
            data: Handler data
            
        Returns:
            Handler result or None if rate limited
        """
        # Only apply to messages
        if isinstance(event, Message):
            user_id = event.from_user.id
            
            # Check rate limit
            is_allowed, remaining = await self.rate_limiter.check_message_limit(user_id)
            
            if not is_allowed:
                # Rate limit exceeded
                await event.answer(
                    f"⏳ Rate limit exceeded. Please wait a moment before sending more messages.\n"
                    f"You can send more messages in a few seconds."
                )
                return  # Don't process the message
        
        # Continue to handler
        return await handler(event, data)

