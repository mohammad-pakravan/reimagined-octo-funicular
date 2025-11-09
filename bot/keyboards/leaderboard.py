"""
Leaderboard keyboards for displaying rankings.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_leaderboard_main_keyboard() -> InlineKeyboardMarkup:
    """Get main leaderboard keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 بیشترین امتیاز", callback_data="leaderboard:points"),
        ],
        [
            InlineKeyboardButton(text="👥 بیشترین دعوت", callback_data="leaderboard:referrals"),
        ],
        [
            InlineKeyboardButton(text="❤️ بیشترین لایک", callback_data="leaderboard:likes"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="engagement:main"),
        ],
    ])
    return keyboard


def get_leaderboard_period_keyboard(leaderboard_type: str) -> InlineKeyboardMarkup:
    """Get leaderboard period selection keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 هفته", callback_data=f"leaderboard:{leaderboard_type}:week"),
            InlineKeyboardButton(text="📆 ماه", callback_data=f"leaderboard:{leaderboard_type}:month"),
        ],
        [
            InlineKeyboardButton(text="🏆 همه زمان‌ها", callback_data=f"leaderboard:{leaderboard_type}:all"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="leaderboard:main"),
        ],
    ])
    return keyboard


def get_leaderboard_pagination_keyboard(
    leaderboard_type: str,
    period: str,
    page: int,
    has_next: bool
) -> InlineKeyboardMarkup:
    """Get leaderboard pagination keyboard."""
    keyboard = []
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(
            text="◀️ قبلی",
            callback_data=f"leaderboard:{leaderboard_type}:{period}:page:{page-1}"
        ))
    if has_next:
        nav_buttons.append(InlineKeyboardButton(
            text="▶️ بعدی",
            callback_data=f"leaderboard:{leaderboard_type}:{period}:page:{page+1}"
        ))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([
        InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"leaderboard:{leaderboard_type}"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_admin_leaderboard_main_keyboard() -> InlineKeyboardMarkup:
    """Get admin leaderboard keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 بیشترین امتیاز", callback_data="admin:leaderboard:points"),
        ],
        [
            InlineKeyboardButton(text="👥 بیشترین دعوت", callback_data="admin:leaderboard:referrals"),
        ],
        [
            InlineKeyboardButton(text="❤️ بیشترین لایک", callback_data="admin:leaderboard:likes"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:main"),
        ],
    ])
    return keyboard


def get_admin_leaderboard_period_keyboard(leaderboard_type: str) -> InlineKeyboardMarkup:
    """Get admin leaderboard period selection keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 هفته", callback_data=f"admin:leaderboard:{leaderboard_type}:week"),
            InlineKeyboardButton(text="📆 ماه", callback_data=f"admin:leaderboard:{leaderboard_type}:month"),
        ],
        [
            InlineKeyboardButton(text="🏆 همه زمان‌ها", callback_data=f"admin:leaderboard:{leaderboard_type}:all"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:leaderboard:main"),
        ],
    ])
    return keyboard

