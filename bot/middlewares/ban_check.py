"""
Ban check middleware.
Prevents banned users from using the bot.
"""
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from db.database import get_db
from db.crud import get_user_by_telegram_id


class BanCheckMiddleware(BaseMiddleware):
    """Middleware to check if user is banned."""
    
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
            Handler result or None if user is banned
        """
        user_id = None
        
        # Get user ID from event
        if isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        elif isinstance(event, Message):
            user_id = event.from_user.id
        
        # If no user ID, allow handler to process (shouldn't happen)
        if not user_id:
            return await handler(event, data)
        
        # Check if user is banned
        async for db_session in get_db():
            user = await get_user_by_telegram_id(db_session, user_id, include_inactive=True)
            
            # If user doesn't exist, allow handler to process (for registration)
            if not user:
                return await handler(event, data)
            
            # If user is banned, block access
            if user.is_banned:
                # Allow /start command so user can see ban message
                if isinstance(event, Message) and event.text and event.text.startswith("/start"):
                    # Still allow /start but show ban message
                    await event.answer(
                        "🚫 شما از استفاده از این ربات مسدود شده‌اید.\n\n"
                        "در صورت نیاز به اطلاعات بیشتر، با پشتیبانی تماس بگیرید."
                    )
                    return None
                
                # Send ban message to user
                if isinstance(event, Message):
                    # Only send message if it's not already a ban message to avoid spam
                    ban_keywords = ["مسدود", "بن", "ban", "blocked"]
                    is_ban_message = event.text and any(keyword in event.text.lower() for keyword in ban_keywords)
                    
                    if not is_ban_message:
                        await event.answer(
                            "🚫 شما از استفاده از این ربات مسدود شده‌اید.\n\n"
                            "در صورت نیاز به اطلاعات بیشتر، با پشتیبانی تماس بگیرید."
                        )
                elif isinstance(event, CallbackQuery):
                    await event.answer(
                        "🚫 شما از استفاده از این ربات مسدود شده‌اید.",
                        show_alert=True
                    )
                
                # Don't process the handler
                return None
            
            # User is not banned, allow handler to process
            return await handler(event, data)

