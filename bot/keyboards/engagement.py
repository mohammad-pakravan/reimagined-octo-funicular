"""
Engagement feature keyboards.
Provides keyboards for points, rewards, achievements, referrals, and leaderboard.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_engagement_menu_keyboard() -> InlineKeyboardMarkup:
    """Get main engagement menu keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎁 پاداش روزانه", callback_data="daily_reward:claim"),
        ],
        [
            InlineKeyboardButton(text="⭐ سکه‌ها", callback_data="points:info"),
            InlineKeyboardButton(text="🏅 مدال‌ها", callback_data="achievements:list"),
        ],
        [
            InlineKeyboardButton(text="👥 دعوت دوستان", callback_data="referral:info"),
            InlineKeyboardButton(text="📊 رتبه‌بندی", callback_data="leaderboard:view"),
        ],
        [
            InlineKeyboardButton(text="🎯 ایونت‌ها", callback_data="events:list"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="menu:main"),
        ],
    ])
    return keyboard


def get_premium_rewards_menu_keyboard(is_premium: bool = False) -> InlineKeyboardMarkup:
    """Get unified premium and rewards menu keyboard."""
    keyboard = []
    
    if not is_premium:
        # Show ways to get premium (coins first, then direct purchase)
        keyboard.append([
            InlineKeyboardButton(text="💎 تبدیل سکه به پریمیوم", callback_data="points:convert"),
        ])
        keyboard.append([
            InlineKeyboardButton(text="💎 خرید پریمیوم", callback_data="premium:info"),
        ])
    else:
        # User has premium, show premium status
        keyboard.append([
            InlineKeyboardButton(text="💎 وضعیت پریمیوم", callback_data="premium:info"),
        ])
    
    keyboard.append([
        InlineKeyboardButton(text="🎁 پاداش روزانه", callback_data="daily_reward:claim"),
    ])
    keyboard.append([
        InlineKeyboardButton(text="⭐ سکه‌ها", callback_data="points:info"),
        InlineKeyboardButton(text="🏆 دستاوردها", callback_data="achievements:list"),
    ])
    keyboard.append([
        InlineKeyboardButton(text="👥 دعوت دوستان", callback_data="referral:info"),
        InlineKeyboardButton(text="📊 رتبه‌بندی", callback_data="leaderboard:view"),
    ])
    keyboard.append([
        InlineKeyboardButton(text="🎯 ایونت‌ها", callback_data="events:list"),
    ])
    keyboard.append([
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="menu:main"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_points_menu_keyboard() -> InlineKeyboardMarkup:
    """Get points menu keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📜 تاریخچه", callback_data="points:history"),
        ],
        [
            InlineKeyboardButton(text="💎 تبدیل به پریمیوم", callback_data="points:convert"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="engagement:menu"),
        ],
    ])
    return keyboard


def get_points_convert_keyboard() -> InlineKeyboardMarkup:
    """Get points to premium conversion keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 روز", callback_data="points:convert:1"),
            InlineKeyboardButton(text="3 روز", callback_data="points:convert:3"),
            InlineKeyboardButton(text="7 روز", callback_data="points:convert:7"),
        ],
        [
            InlineKeyboardButton(text="30 روز", callback_data="points:convert:30"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="points:info"),
        ],
    ])
    return keyboard


def get_achievements_menu_keyboard() -> InlineKeyboardMarkup:
    """Get achievements menu keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏅 مدال‌های من", callback_data="achievements:completed"),
        ],
        [
            InlineKeyboardButton(text="🏅 همه مدال‌ها", callback_data="achievements:badges"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="engagement:menu"),
        ],
    ])
    return keyboard


def get_achievements_pagination_keyboard(page: int, total_pages: int, callback_prefix: str = "achievements") -> InlineKeyboardMarkup:
    """Get achievements pagination keyboard."""
    keyboard = []
    
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"{callback_prefix}:page:{page-1}"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="▶️ بعدی", callback_data=f"{callback_prefix}:page:{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="achievements:list"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_referral_menu_keyboard() -> InlineKeyboardMarkup:
    """Get referral menu keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 آمار دعوت‌ها", callback_data="referral:stats"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="engagement:menu"),
        ],
    ])
    return keyboard


def get_leaderboard_menu_keyboard() -> InlineKeyboardMarkup:
    """Get leaderboard menu keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏆 سکه‌ها", callback_data="leaderboard:points"),
            InlineKeyboardButton(text="💬 چت‌ها", callback_data="leaderboard:chats"),
        ],
        [
            InlineKeyboardButton(text="❤️ لایک‌ها", callback_data="leaderboard:likes"),
            InlineKeyboardButton(text="👥 دعوت‌ها", callback_data="leaderboard:referrals"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="engagement:menu"),
        ],
    ])
    return keyboard


def get_leaderboard_pagination_keyboard(page: int, total_pages: int, leaderboard_type: str) -> InlineKeyboardMarkup:
    """Get leaderboard pagination keyboard."""
    keyboard = []
    
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"leaderboard:{leaderboard_type}:page:{page-1}"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="▶️ بعدی", callback_data=f"leaderboard:{leaderboard_type}:page:{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="leaderboard:view"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_leaderboard_user_keyboard(user_ids: list, leaderboard_type: str) -> InlineKeyboardMarkup:
    """Get leaderboard keyboard with clickable user ranks."""
    keyboard = []
    
    # Create buttons for top 10 users (2 per row)
    for i in range(0, min(len(user_ids), 10), 2):
        row = []
        if i < len(user_ids):
            row.append(InlineKeyboardButton(
                text=f"#{i+1}",
                callback_data=f"leaderboard:user:{leaderboard_type}:{user_ids[i]}"
            ))
        if i+1 < len(user_ids):
            row.append(InlineKeyboardButton(
                text=f"#{i+2}",
                callback_data=f"leaderboard:user:{leaderboard_type}:{user_ids[i+1]}"
            ))
        if row:
            keyboard.append(row)
    
    keyboard.append([
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="leaderboard:view"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_daily_reward_keyboard(already_claimed: bool = False) -> InlineKeyboardMarkup:
    """Get daily reward keyboard."""
    keyboard = []
    
    if not already_claimed:
        keyboard.append([
            InlineKeyboardButton(text="🎁 دریافت پاداش", callback_data="daily_reward:claim"),
        ])
    
    keyboard.append([
        InlineKeyboardButton(text="📊 وضعیت سکه ی روزانه", callback_data="daily_reward:streak"),
    ])
    
    keyboard.append([
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="engagement:menu"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

