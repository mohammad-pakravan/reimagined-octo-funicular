"""
Channel membership check middleware.
Ensures users have joined the mandatory channel before using chat features.
"""
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from config.settings import settings


class ChannelCheckMiddleware(BaseMiddleware):
    """Middleware to check if user has joined mandatory channel."""
    
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
            Handler result or None if user hasn't joined channel
        """
        # Only check for messages and callback queries that require channel membership
        # Some handlers might need to bypass this check (like /start)
        user_id = None
        
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        
        if user_id and settings.MANDATORY_CHANNEL_ID:
            try:
                bot = data.get("bot")
                if bot:
                    # Check if user is member of channel
                    member = await bot.get_chat_member(
                        settings.MANDATORY_CHANNEL_ID,
                        user_id
                    )
                    
                    # Check membership status
                    if member.status not in ["member", "administrator", "creator"]:
                        # User hasn't joined channel
                        channel_link = f"https://t.me/{settings.MANDATORY_CHANNEL_ID.lstrip('@')}"
                        
                        if isinstance(event, Message):
                            await event.answer(
                                f"⚠️ Please join our channel first to use the chat:\n"
                                f"{channel_link}\n\n"
                                f"After joining, send /start again."
                            )
                        elif isinstance(event, CallbackQuery):
                            await event.answer(
                                f"⚠️ Please join our channel first to use the chat:\n"
                                f"{channel_link}",
                                show_alert=True
                            )
                        
                        return  # Don't process the event
            except TelegramBadRequest:
                # Channel doesn't exist or bot can't access it
                pass
            except Exception:
                # Error checking membership, allow to continue
                pass
        
        # Continue to handler
        return await handler(event, data)

