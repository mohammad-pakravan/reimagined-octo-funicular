"""
Channel membership check middleware.
Ensures users have joined all mandatory channels before using chat features.
"""
from typing import Any, Awaitable, Callable, Dict, List
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from config.settings import settings
from db.database import get_db
from db.crud import get_active_mandatory_channels
from bot.keyboards.common import get_channel_check_keyboard


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
        # Some handlers might need to bypass this check (like /start, channel:check_membership)
        user_id = None
        
        # Skip check for channel membership check callback
        if isinstance(event, CallbackQuery):
            if event.data == "channel:check_membership":
                # Allow the handler to process this callback
                return await handler(event, data)
            user_id = event.from_user.id
        elif isinstance(event, Message):
            user_id = event.from_user.id
        
        if user_id:
            try:
                bot = data.get("bot")
                if bot:
                    # Get active mandatory channels from database
                    async for db_session in get_db():
                        mandatory_channels = await get_active_mandatory_channels(db_session)
                        break
                    else:
                        # Fallback to old MANDATORY_CHANNEL_ID if no channels in database
                        if settings.MANDATORY_CHANNEL_ID:
                            mandatory_channels = [type('obj', (object,), {
                                'channel_id': settings.MANDATORY_CHANNEL_ID,
                                'channel_link': f"https://t.me/{settings.MANDATORY_CHANNEL_ID.lstrip('@')}",
                                'channel_name': None
                            })()]
                        else:
                            mandatory_channels = []
                    
                    if not mandatory_channels:
                        # No mandatory channels, allow to continue
                        return await handler(event, data)
                    
                    # Check if user is member of all mandatory channels
                    missing_channels: List[str] = []
                    
                    for channel in mandatory_channels:
                        try:
                            member = await bot.get_chat_member(
                                channel.channel_id,
                                user_id
                            )
                            
                            # Check membership status
                            if member.status not in ["member", "administrator", "creator"]:
                                # User hasn't joined this channel
                                channel_link = channel.channel_link or f"https://t.me/{channel.channel_id.lstrip('@')}"
                                channel_name = channel.channel_name or channel.channel_id
                                missing_channels.append({
                                    'name': channel_name,
                                    'link': channel_link,
                                    'formatted': f"• {channel_name}\n  {channel_link}"
                                })
                        except TelegramBadRequest:
                            # Channel doesn't exist or bot can't access it, skip it
                            pass
                        except Exception:
                            # Error checking membership, skip this channel
                            pass
                    
                    # If user hasn't joined all channels, show message
                    if missing_channels:
                        # Build channel data for keyboard
                        channel_buttons = []
                        channels_list = []
                        
                        for idx, channel_data in enumerate(missing_channels, start=1):
                            if isinstance(channel_data, dict):
                                channel_name = channel_data.get('name', 'چنل')
                                channel_link = channel_data.get('link', '')
                            else:
                                # Fallback for old format
                                parts = channel_data.split('\n')
                                channel_name = parts[0].replace('• ', '').strip()
                                channel_link = parts[1].strip() if len(parts) > 1 else ""
                            
                            channels_list.append(f"{idx}. {channel_name}")
                            channel_buttons.append({
                                'name': channel_name,
                                'link': channel_link
                            })
                        
                        channels_text = "\n".join(channels_list)
                        
                        # Create beautiful message
                        message_text = (
                            "⚠️ عضویت اجباری در چنل‌ها\n\n"
                            "📺 برای استفاده از ربات، باید به چنل‌های زیر عضو شوید:\n\n"
                            f"{channels_text}\n\n"
                            "💡 روی دکمه‌های بالا کلیک کنید تا به چنل‌ها بروید.\n"
                            "بعد از عضویت، روی دکمه «✅ بررسی عضویت» کلیک کنید."
                        )
                        
                        if isinstance(event, Message):
                            await event.answer(
                                message_text,
                                reply_markup=get_channel_check_keyboard(channel_buttons),
                                parse_mode="HTML"
                            )
                        elif isinstance(event, CallbackQuery):
                            # For callback queries, edit the message if possible
                            try:
                                await event.message.edit_text(
                                    message_text,
                                    reply_markup=get_channel_check_keyboard(channel_buttons),
                                    parse_mode="HTML"
                                )
                            except:
                                # If edit fails, answer with alert
                                await event.answer(
                                    f"⚠️ لطفاً ابتدا به چنل‌های زیر عضو شوید:\n\n{channels_text}",
                                    show_alert=True
                                )
                        
                        return  # Don't process the event
            except Exception:
                # Error checking membership, allow to continue
                pass
        
        # Continue to handler
        return await handler(event, data)

