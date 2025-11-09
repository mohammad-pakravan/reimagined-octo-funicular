"""
My profile keyboards for editing own profile and managing follows/blocks.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_my_profile_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for my profile page with edit options."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ ویرایش تصویر", callback_data="my_profile:edit_photo"),
        ],
        [
            InlineKeyboardButton(text="✏️ ویرایش شهر", callback_data="my_profile:edit_city"),
            InlineKeyboardButton(text="✏️ ویرایش استان", callback_data="my_profile:edit_province"),
        ],
        [
            InlineKeyboardButton(text="✏️ ویرایش سن", callback_data="my_profile:edit_age"),
            InlineKeyboardButton(text="✏️ ویرایش جنسیت", callback_data="my_profile:edit_gender"),
        ],
        [
            InlineKeyboardButton(text="✏️ ویرایش نام کاربری", callback_data="my_profile:edit_username"),
        ],
        [
            InlineKeyboardButton(text="❤️ لایک شده‌ها", switch_inline_query_current_chat="liked:"),
        ],
        [
            InlineKeyboardButton(text="👥 دنبال شده‌ها", switch_inline_query_current_chat="following:"),
            InlineKeyboardButton(text="🚫 بلاک شده‌ها", switch_inline_query_current_chat="blocked:"),
        ],
        [
            InlineKeyboardButton(text="✉️ پیام‌های دایرکت", callback_data="my_profile:direct_messages"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="my_profile:back"),
        ],
    ])
    return keyboard


def get_following_list_keyboard(following_users: list, page: int = 0, page_size: int = 10) -> InlineKeyboardMarkup:
    """
    Get keyboard for following list.
    
    Args:
        following_users: List of (user_id, username, profile_id) tuples
        page: Current page number
        page_size: Number of users per page
    """
    keyboard = []
    
    # Pagination
    start_idx = page * page_size
    end_idx = start_idx + page_size
    page_users = following_users[start_idx:end_idx]
    
    # Add user buttons
    for user_id, username, profile_id in page_users:
        username_display = username or f"User {user_id}"
        keyboard.append([
            InlineKeyboardButton(
                text=f"👤 {username_display[:20]}",
                callback_data=f"my_profile:unfollow:{user_id}"
            )
        ])
    
    # Pagination buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ قبلی", callback_data=f"my_profile:following_page:{page-1}"))
    if end_idx < len(following_users):
        nav_buttons.append(InlineKeyboardButton(text="➡️ بعدی", callback_data=f"my_profile:following_page:{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([
        InlineKeyboardButton(text="🔙 بازگشت به پروفایل", callback_data="my_profile:back")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_blocked_list_keyboard(blocked_users: list, page: int = 0, page_size: int = 10) -> InlineKeyboardMarkup:
    """
    Get keyboard for blocked list.
    
    Args:
        blocked_users: List of (user_id, username, profile_id) tuples
        page: Current page number
        page_size: Number of users per page
    """
    keyboard = []
    
    # Pagination
    start_idx = page * page_size
    end_idx = start_idx + page_size
    page_users = blocked_users[start_idx:end_idx]
    
    # Add user buttons
    for user_id, username, profile_id in page_users:
        username_display = username or f"User {user_id}"
        keyboard.append([
            InlineKeyboardButton(
                text=f"🚫 {username_display[:20]}",
                callback_data=f"my_profile:unblock:{user_id}"
            )
        ])
    
    # Pagination buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ قبلی", callback_data=f"my_profile:blocked_page:{page-1}"))
    if end_idx < len(blocked_users):
        nav_buttons.append(InlineKeyboardButton(text="➡️ بعدی", callback_data=f"my_profile:blocked_page:{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([
        InlineKeyboardButton(text="🔙 بازگشت به پروفایل", callback_data="my_profile:back")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_liked_list_keyboard(liked_users: list, page: int = 0, page_size: int = 10) -> InlineKeyboardMarkup:
    """
    Get keyboard for liked list.
    
    Args:
        liked_users: List of (user_id, username, profile_id) tuples
        page: Current page number
        page_size: Number of users per page
    """
    keyboard = []
    
    # Pagination
    start_idx = page * page_size
    end_idx = start_idx + page_size
    page_users = liked_users[start_idx:end_idx]
    
    # Add user buttons
    for user_id, username, profile_id in page_users:
        username_display = username or f"User {user_id}"
        keyboard.append([
            InlineKeyboardButton(
                text=f"❤️ {username_display[:20]}",
                callback_data=f"my_profile:unlike:{user_id}"
            )
        ])
    
    # Pagination buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ قبلی", callback_data=f"my_profile:liked_page:{page-1}"))
    if end_idx < len(liked_users):
        nav_buttons.append(InlineKeyboardButton(text="➡️ بعدی", callback_data=f"my_profile:liked_page:{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([
        InlineKeyboardButton(text="🔙 بازگشت به پروفایل", callback_data="my_profile:back")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_direct_messages_list_keyboard(message_list: list, page: int = 0, page_size: int = 10) -> InlineKeyboardMarkup:
    """
    Get keyboard for direct messages list with inline buttons.
    
    Args:
        message_list: List of (sender_id, sender_username, sender_gender, latest_date) tuples
        page: Current page number
        page_size: Number of users per page
    """
    keyboard = []
    
    # Pagination
    start_idx = page * page_size
    end_idx = start_idx + page_size
    page_users = message_list[start_idx:end_idx]
    
    # Add user buttons
    for sender_id, sender_username, sender_gender, latest_date in page_users:
        gender_map = {"male": "👨", "female": "👩", "other": "⚪"}
        gender_icon = gender_map.get(sender_gender, "👤")
        
        username_display = sender_username or f"User {sender_id}"
        
        # Format date for display
        from datetime import datetime
        if isinstance(latest_date, datetime):
            date_str = latest_date.strftime('%m/%d %H:%M')
        else:
            date_str = str(latest_date)[:10]
        
        button_text = f"{gender_icon} {username_display[:15]} - {date_str}"
        keyboard.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"dm_list:view:{sender_id}"
            )
        ])
    
    # Pagination buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ قبلی", callback_data=f"dm_list:page:{page-1}"))
    if end_idx < len(message_list):
        nav_buttons.append(InlineKeyboardButton(text="➡️ بعدی", callback_data=f"dm_list:page:{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([
        InlineKeyboardButton(text="🔙 بازگشت به پروفایل", callback_data="my_profile:back")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

