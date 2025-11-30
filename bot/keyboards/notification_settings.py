"""
Notification settings keyboards.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_notification_settings_keyboard(
    receive_chat_requests: bool = True,
    receive_direct_messages: bool = True,
    receive_referral_notifications: bool = True
) -> InlineKeyboardMarkup:
    """Get keyboard for notification settings."""
    keyboard = []
    
    # Chat requests toggle
    chat_requests_text = "✅ درخواست‌های چت" if receive_chat_requests else "❌ درخواست‌های چت"
    keyboard.append([
        InlineKeyboardButton(
            text=chat_requests_text,
            callback_data="notification:toggle:chat_requests"
        ),
    ])
    
    # Direct messages toggle
    direct_messages_text = "✅ پیام‌های دایرکت" if receive_direct_messages else "❌ پیام‌های دایرکت"
    keyboard.append([
        InlineKeyboardButton(
            text=direct_messages_text,
            callback_data="notification:toggle:direct_messages"
        ),
    ])
    
    # Referral notifications toggle
    referral_text = "✅ اعلان‌های معرفی" if receive_referral_notifications else "❌ اعلان‌های معرفی"
    keyboard.append([
        InlineKeyboardButton(
            text=referral_text,
            callback_data="notification:toggle:referral_notifications"
        ),
    ])
    
    # Back button
    keyboard.append([
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="my_profile:view"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

