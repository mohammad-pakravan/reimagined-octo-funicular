"""
Reply keyboards (normal keyboards) for the bot.
These appear at the bottom of the screen.
"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from config.settings import settings


def get_main_reply_keyboard() -> ReplyKeyboardMarkup:
    """Get main reply keyboard."""
    keyboard = ReplyKeyboardBuilder()
    
    keyboard.add(KeyboardButton(text="💬 شروع چت"))
    keyboard.add(KeyboardButton(text="📹 چت تصویری ناشناس"))
    keyboard.add(KeyboardButton(text="📞 چت صوتی ناشناس"))
    keyboard.add(KeyboardButton(text="📊 پروفایل من"))
    keyboard.add(KeyboardButton(text="💎 پریمیوم"))
    keyboard.add(KeyboardButton(text="🎁 پاداش‌ها و تعامل"))
    
    keyboard.adjust(1, 2, 2, 1)
    return keyboard.as_markup(resize_keyboard=True, persistent=True)


def get_chat_reply_keyboard() -> ReplyKeyboardMarkup:
    """Get reply keyboard for active chat."""
    keyboard = ReplyKeyboardBuilder()
    
    keyboard.add(KeyboardButton(text="👤 پروفایل مخاطب"))
    keyboard.add(KeyboardButton(text="📹 شروع تماس تصویری"))
    keyboard.add(KeyboardButton(text="📞 شروع تماس صوتی"))
    keyboard.add(KeyboardButton(text="❌ قطع مکالمه"))
    
    keyboard.adjust(2, 2)
    return keyboard.as_markup(resize_keyboard=True, persistent=True)


def get_queue_reply_keyboard() -> ReplyKeyboardMarkup:
    """Get reply keyboard shown when user is in queue."""
    keyboard = ReplyKeyboardBuilder()
    
    keyboard.add(KeyboardButton(text="❌ خروج از صف"))
    
    keyboard.adjust(1)
    return keyboard.as_markup(resize_keyboard=True, persistent=True)


def remove_keyboard() -> ReplyKeyboardMarkup:
    """Remove reply keyboard."""
    from aiogram.types import ReplyKeyboardRemove
    return ReplyKeyboardRemove(remove_keyboard=True)

