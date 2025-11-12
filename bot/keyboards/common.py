"""
Common inline keyboards for the bot.
Provides keyboard buttons for registration, chat actions, and general navigation.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_gender_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for gender selection."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👨 آقا", callback_data="gender:male"),
            InlineKeyboardButton(text="👩 خانم", callback_data="gender:female"),
        ],
    ])
    return keyboard


def get_preferred_gender_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for preferred gender selection."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👨 آقا", callback_data="pref_gender:male"),
            InlineKeyboardButton(text="👩 خانم", callback_data="pref_gender:female"),
        ],
        [
            InlineKeyboardButton(text="🌐 همه", callback_data="pref_gender:all"),
        ],
    ])
    return keyboard


def get_chat_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for chat actions."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔍 Start Search", callback_data="chat:start_search"),
        ],
        [
            InlineKeyboardButton(text="❌ End Chat", callback_data="chat:end"),
        ],
        [
            InlineKeyboardButton(text="📊 Profile", callback_data="profile:view"),
            InlineKeyboardButton(text="💎 Premium", callback_data="premium:info"),
        ],
    ])
    return keyboard


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Get main menu keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💬 Start Chat", callback_data="chat:start_search"),
        ],
        [
            InlineKeyboardButton(text="📊 My Profile", callback_data="profile:view"),
            InlineKeyboardButton(text="💎 Premium", callback_data="engagement:menu"),
        ],
        [
            InlineKeyboardButton(text="🎁 پاداش‌ها و تعامل", callback_data="engagement:menu"),
        ],
    ])
    return keyboard


def get_registration_skip_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard with skip option for registration."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⏭️ رد کردن", callback_data="registration:skip_photo"),
        ],
    ])
    return keyboard


def get_confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    """
    Get confirmation keyboard.
    
    Args:
        action: Action to confirm (e.g., "video_call", "end_chat")
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ بله", callback_data=f"{action}:confirm"),
            InlineKeyboardButton(text="❌ خیر", callback_data=f"{action}:cancel"),
        ],
    ])
    return keyboard


def get_delete_account_confirm_keyboard() -> InlineKeyboardMarkup:
    """Get confirmation keyboard for account deletion."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ بله، حذف کن", callback_data="my_profile:delete_account:confirm"),
            InlineKeyboardButton(text="❌ خیر، لغو", callback_data="my_profile:delete_account:cancel"),
        ],
    ])
    return keyboard


def get_premium_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for premium features."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💎 خرید پریمیوم", callback_data="premium:info"),
        ],
        [
            InlineKeyboardButton(text="📋 Premium Features", callback_data="premium:features"),
        ],
        [
            InlineKeyboardButton(text="🔙 Back", callback_data="menu:main"),
        ],
    ])
    return keyboard


def get_call_request_keyboard(call_type: str, caller_id: int) -> InlineKeyboardMarkup:
    """
    Get keyboard for accepting/rejecting call request.
    
    Args:
        call_type: 'video' or 'voice'
        caller_id: User ID who requested the call
    """
    if call_type == "video":
        accept_text = "✅ تایید تماس تصویری"
        reject_text = "❌ رد تماس تصویری"
        accept_callback = f"call:accept:video:{caller_id}"
        reject_callback = f"call:reject:video:{caller_id}"
    else:  # voice
        accept_text = "✅ تایید تماس صوتی"
        reject_text = "❌ رد تماس صوتی"
        accept_callback = f"call:accept:voice:{caller_id}"
        reject_callback = f"call:reject:voice:{caller_id}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=accept_text, callback_data=accept_callback),
            InlineKeyboardButton(text=reject_text, callback_data=reject_callback),
        ],
    ])
    return keyboard


def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for admin panel."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Stats", callback_data="admin:stats"),
            InlineKeyboardButton(text="👥 Users", callback_data="admin:users"),
        ],
        [
            InlineKeyboardButton(text="📢 Broadcast", callback_data="admin:broadcast"),
            InlineKeyboardButton(text="⚠️ Reports", callback_data="admin:reports"),
        ],
    ])
    return keyboard


def get_channel_check_keyboard(channels: list = None) -> InlineKeyboardMarkup:
    """
    Get keyboard for checking channel membership with channel links.
    
    Args:
        channels: List of channel objects with channel_link and channel_name
    """
    keyboard = []
    
    # Add channel link buttons if provided
    if channels:
        for channel in channels:
            channel_link = channel.get('link') or channel.get('channel_link')
            channel_name = channel.get('name') or channel.get('channel_name') or 'چنل'
            
            if channel_link:
                # Create URL button for channel
                keyboard.append([
                    InlineKeyboardButton(
                        text=f"📺 {channel_name}",
                        url=channel_link
                    )
                ])
    
    # Add check membership button
    keyboard.append([
        InlineKeyboardButton(text="✅ بررسی عضویت", callback_data="channel:check_membership"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_dm_confirm_keyboard(receiver_id: int) -> InlineKeyboardMarkup:
    """
    Get confirmation keyboard for direct message.
    
    Args:
        receiver_id: Receiver user ID
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ ارسال", callback_data=f"dm:confirm:{receiver_id}"),
            InlineKeyboardButton(text="❌ لغو", callback_data="dm:cancel"),
        ],
    ])
    return keyboard


def get_dm_receive_keyboard(dm_id: int) -> InlineKeyboardMarkup:
    """
    Get keyboard for received direct message.
    
    Args:
        dm_id: Direct message ID
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👁️ مشاهده", callback_data=f"dm:view:{dm_id}"),
        ],
    ])
    return keyboard


def get_dm_view_keyboard(dm_id: int, sender_id: int) -> InlineKeyboardMarkup:
    """
    Get keyboard for viewing direct message with delete, block, reply and back options.
    
    Args:
        dm_id: Direct message ID
        sender_id: Sender user ID
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 پاسخ", callback_data=f"dm:reply_from_view:{sender_id}"),
        ],
        [
            InlineKeyboardButton(text="🗑️ حذف پیام", callback_data=f"dm:delete:{dm_id}"),
            InlineKeyboardButton(text="🚫 بلاک کاربر", callback_data=f"dm:block:{sender_id}"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت به لیست", callback_data="my_profile:direct_messages"),
        ],
    ])
    return keyboard


def get_queue_status_keyboard(is_premium: bool = False) -> InlineKeyboardMarkup:
    """
    Get keyboard for queue status with premium purchase and cancel search buttons.
    
    Args:
        is_premium: Whether user has premium subscription
    """
    keyboard = []
    
    if not is_premium:
        keyboard.append([
            InlineKeyboardButton(text="💎 خرید اشتراک پریمیوم", callback_data="premium:purchase")
        ])
    
    keyboard.append([
        InlineKeyboardButton(text="❌ لغو جستجو", callback_data="chat:cancel_search")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_dm_reply_keyboard(sender_id: int) -> InlineKeyboardMarkup:
    """
    Get keyboard for replying to direct message.
    
    Args:
        sender_id: Sender user ID (user to reply to)
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 پاسخ", callback_data=f"dm:reply:{sender_id}"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت به لیست", callback_data="my_profile:direct_messages"),
        ],
    ])
    return keyboard


def get_chat_request_keyboard(request_id: int, requester_id: int) -> InlineKeyboardMarkup:
    """
    Get keyboard for chat request (accept/reject/block).
    
    Args:
        request_id: Chat request ID (optional, can be same as requester_id for now)
        requester_id: User ID who requested chat
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ شروع چت", callback_data=f"chat_request:accept:{requester_id}"),
            InlineKeyboardButton(text="❌ رد", callback_data=f"chat_request:reject:{requester_id}"),
        ],
        [
            InlineKeyboardButton(text="🚫 بلاک کاربر", callback_data=f"chat_request:block:{requester_id}"),
        ],
    ])
    return keyboard


def get_chat_request_cancel_keyboard(requester_id: int, receiver_id: int) -> InlineKeyboardMarkup:
    """
    Get keyboard for canceling chat request (for requester).
    
    Args:
        requester_id: User ID who requested chat
        receiver_id: User ID who received the request
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ لغو درخواست چت", callback_data=f"chat_request:cancel:{receiver_id}"),
        ],
    ])
    return keyboard

