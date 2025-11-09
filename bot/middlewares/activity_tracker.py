"""
Middleware to track user activity.
Updates user's last activity timestamp on every message/update.
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update, Message, CallbackQuery

from utils.user_activity import UserActivityTracker


class ActivityTrackerMiddleware(BaseMiddleware):
    """Middleware to track user activity."""
    
    def __init__(self, activity_tracker: UserActivityTracker):
        self.activity_tracker = activity_tracker
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Track user activity before handling update."""
        # Extract user ID from update
        user_id = None
        
        # Try to get from event directly - Update is most common
        if isinstance(event, Update):
            # Check all possible update types
            if event.message and event.message.from_user:
                user_id = event.message.from_user.id
            elif event.callback_query and event.callback_query.from_user:
                user_id = event.callback_query.from_user.id
            elif event.edited_message and event.edited_message.from_user:
                user_id = event.edited_message.from_user.id
            elif event.channel_post and event.channel_post.from_user:
                user_id = event.channel_post.from_user.id
            elif event.edited_channel_post and event.edited_channel_post.from_user:
                user_id = event.edited_channel_post.from_user.id
            elif event.inline_query and event.inline_query.from_user:
                user_id = event.inline_query.from_user.id
            elif event.chosen_inline_result and event.chosen_inline_result.from_user:
                user_id = event.chosen_inline_result.from_user.id
            elif event.shipping_query and event.shipping_query.from_user:
                user_id = event.shipping_query.from_user.id
            elif event.pre_checkout_query and event.pre_checkout_query.from_user:
                user_id = event.pre_checkout_query.from_user.id
            elif event.poll_answer and event.poll_answer.user:
                user_id = event.poll_answer.user.id
            elif event.my_chat_member and event.my_chat_member.from_user:
                user_id = event.my_chat_member.from_user.id
            elif event.chat_member and event.chat_member.from_user:
                user_id = event.chat_member.from_user.id
        elif isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
        
        # Update activity if user ID found
        if user_id:
            try:
                await self.activity_tracker.update_activity(user_id)
            except Exception as e:
                # Log but don't fail
                import logging
                logging.getLogger(__name__).error(f"Error updating activity for user {user_id}: {e}")
        
        # Continue to handler
        return await handler(event, data)

