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
    
    # Row 1: Start Chat
    keyboard.add(KeyboardButton(text="💬 شروع چت"))
    
    # Row 2: Premium, Free Coins, Search Users
    keyboard.add(KeyboardButton(text="💎 پریمیوم"))
    keyboard.add(KeyboardButton(text="💰 سکه ی رایگان"))
    keyboard.add(KeyboardButton(text="🔍 جستجوی کاربران"))
    
    # Row 3: Rewards and Engagement
    keyboard.add(KeyboardButton(text="🎁 پاداش‌ها و تعامل"))
    
    # Row 4: Help, My Profile
    keyboard.add(KeyboardButton(text="📖 راهنما"))
    keyboard.add(KeyboardButton(text="📊 پروفایل من"))
    
    # Row 5: Invite Friends
    keyboard.add(KeyboardButton(text="👥 دعوت دوستان( سکه رایگان )"))
    
    keyboard.adjust(1, 3, 1, 2, 1)
    return keyboard.as_markup(resize_keyboard=True, persistent=True)


def get_chat_reply_keyboard(private_mode: bool = False) -> ReplyKeyboardMarkup:
    """
    Get reply keyboard for active chat.
    
    Args:
        private_mode: Whether private mode is currently enabled
    """
    keyboard = ReplyKeyboardBuilder()
    
    keyboard.add(KeyboardButton(text="👤 پروفایل مخاطب"))
    # Update button text based on private mode status
    if private_mode:
        keyboard.add(KeyboardButton(text="🟢 حالت خصوصی"))
    else:
        keyboard.add(KeyboardButton(text="⚪ حالت خصوصی"))
    keyboard.add(KeyboardButton(text="🎮 بازی"))
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

