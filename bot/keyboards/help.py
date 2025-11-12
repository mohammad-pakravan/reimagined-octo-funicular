"""
Help menu keyboards for user guidance.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config.settings import settings


def get_help_menu_keyboard() -> InlineKeyboardMarkup:
    """Get main help menu keyboard."""
    keyboard = []
    
    keyboard.append([
        InlineKeyboardButton(text="💬 شروع چت", callback_data="help:start_chat"),
        InlineKeyboardButton(text="📊 پروفایل", callback_data="help:profile"),
    ])
    keyboard.append([
        InlineKeyboardButton(text="💰 سکه گرفتن", callback_data="help:earn_coins"),
        InlineKeyboardButton(text="💎 پریمیوم", callback_data="help:premium"),
    ])
    keyboard.append([
        InlineKeyboardButton(text="👥 زیر مجموعه گیری", callback_data="help:referral"),
        InlineKeyboardButton(text="💳 روش‌های پرداخت", callback_data="help:payment"),
    ])
    keyboard.append([
        InlineKeyboardButton(text="✉️ پیام‌های مستقیم", callback_data="help:direct_messages"),
        InlineKeyboardButton(text="🎁 پاداش‌ها", callback_data="help:rewards"),
    ])
    keyboard.append([
        InlineKeyboardButton(text="🏆 رتبه‌بندی", callback_data="help:leaderboard"),
        InlineKeyboardButton(text="📞 تماس ناشناس", callback_data="help:anonymous_call"),
    ])
    
    # Add support button if SUPPORT_ADMIN is configured
    if settings.SUPPORT_ADMIN:
        keyboard.append([
            InlineKeyboardButton(text="💬 پشتیبانی", url=settings.SUPPORT_ADMIN),
        ])
    
    keyboard.append([
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="help:back"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

