"""
Middleware to check if user is admin and show admin keyboard.
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from config.settings import settings


def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    return user_id in settings.ADMIN_IDS


class AdminCheckMiddleware(BaseMiddleware):
    """Middleware to check admin status and update reply keyboard."""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Check if user is admin and add admin status to data."""
        user_id = None
        
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
        
        if user_id:
            data['is_admin'] = is_admin(user_id)
        
        return await handler(event, data)




