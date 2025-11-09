"""
Anonymous call keyboards for video and voice chat.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_gender_preference_keyboard(call_type: str) -> InlineKeyboardMarkup:
    """Get keyboard for gender preference selection."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👨 پسر", callback_data=f"anonymous_call:gender:{call_type}:male"),
            InlineKeyboardButton(text="👩 دختر", callback_data=f"anonymous_call:gender:{call_type}:female"),
        ],
        [
            InlineKeyboardButton(text="🌐 فرقی نمیکنه", callback_data=f"anonymous_call:gender:{call_type}:all"),
        ],
        [
            InlineKeyboardButton(text="❌ لغو", callback_data="menu:main"),
        ],
    ])
    return keyboard


def get_match_found_keyboard(call_type: str, partner_id: int, room_id: str, call_link: str) -> InlineKeyboardMarkup:
    """Get keyboard when match is found."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📞 وارد چت شو", url=call_link),
        ],
        [
            InlineKeyboardButton(text="👤 پروفایل کاربر", callback_data=f"anonymous_call:profile:{partner_id}"),
            InlineKeyboardButton(text="➡️ بعدی", callback_data=f"anonymous_call:next:{call_type}"),
        ],
        [
            InlineKeyboardButton(text="❌ لغو", callback_data="anonymous_call:cancel"),
        ],
    ])
    return keyboard


def get_searching_keyboard(call_type: str) -> InlineKeyboardMarkup:
    """Get keyboard while searching for match."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ لغو جستجو", callback_data="anonymous_call:cancel"),
        ],
    ])
    return keyboard




