"""
Admin keyboards for admin panel.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def get_admin_reply_keyboard() -> ReplyKeyboardMarkup:
    """Get admin reply keyboard."""
    keyboard = ReplyKeyboardBuilder()
    
    keyboard.add(KeyboardButton(text="👥 مدیریت کاربران"))
    keyboard.add(KeyboardButton(text="📊 آمار و گزارشات"))
    keyboard.add(KeyboardButton(text="⚙️ تنظیمات"))
    keyboard.add(KeyboardButton(text="🔗 لینک‌های عضویت"))
    keyboard.add(KeyboardButton(text="💰 تنظیمات سکه"))
    keyboard.add(KeyboardButton(text="📢 ارسال پیام همگانی"))
    keyboard.add(KeyboardButton(text="🎯 مدیریت ایونت‌ها"))
    
    keyboard.adjust(2, 2, 2, 1)
    return keyboard.as_markup(resize_keyboard=True, persistent=True)


def get_admin_main_keyboard() -> InlineKeyboardMarkup:
    """Get main admin panel keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 مدیریت کاربران", callback_data="admin:users"),
            InlineKeyboardButton(text="📊 آمار", callback_data="admin:stats"),
        ],
        [
            InlineKeyboardButton(text="🔗 لینک‌های عضویت", callback_data="admin:referral_links"),
            InlineKeyboardButton(text="💰 تنظیمات سکه", callback_data="admin:coin_settings"),
        ],
        [
            InlineKeyboardButton(text="📢 ارسال پیام", callback_data="admin:broadcast"),
            InlineKeyboardButton(text="📋 لیست پیام‌ها", callback_data="admin:broadcast:list"),
        ],
        [
            InlineKeyboardButton(text="🎯 مدیریت ایونت‌ها", callback_data="admin:events"),
            InlineKeyboardButton(text="🏆 رتبه‌بندی", callback_data="admin:leaderboard:main"),
        ],
        [
            InlineKeyboardButton(text="💎 مدیریت پلن‌های پریمیوم", callback_data="admin:premium_plans"),
        ],
        [
            InlineKeyboardButton(text="⚙️ تنظیمات سیستم", callback_data="admin:system_settings"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="menu:main"),
        ],
    ])
    return keyboard


def get_admin_users_keyboard() -> InlineKeyboardMarkup:
    """Get admin users management keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔍 جستجوی کاربر", callback_data="admin:user:search"),
        ],
        [
            InlineKeyboardButton(text="🚫 کاربران مسدود شده", callback_data="admin:users:banned"),
            InlineKeyboardButton(text="💎 کاربران پریمیوم", callback_data="admin:users:premium"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:main"),
        ],
    ])
    return keyboard


def get_admin_referral_links_keyboard() -> InlineKeyboardMarkup:
    """Get admin referral links keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ ایجاد لینک جدید", callback_data="admin:referral_link:create"),
        ],
        [
            InlineKeyboardButton(text="📋 لیست لینک‌ها", callback_data="admin:referral_link:list"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:main"),
        ],
    ])
    return keyboard


def get_admin_coin_settings_keyboard() -> InlineKeyboardMarkup:
    """Get admin coin settings keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 روز", callback_data="admin:coin:edit:1"),
            InlineKeyboardButton(text="3 روز", callback_data="admin:coin:edit:3"),
        ],
        [
            InlineKeyboardButton(text="7 روز", callback_data="admin:coin:edit:7"),
            InlineKeyboardButton(text="30 روز", callback_data="admin:coin:edit:30"),
        ],
        [
            InlineKeyboardButton(text="📋 مشاهده تنظیمات", callback_data="admin:coin:view"),
        ],
        [
            InlineKeyboardButton(text="🎁 تنظیمات پاداش سکه", callback_data="admin:coin_rewards"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:main"),
        ],
    ])
    return keyboard


def get_admin_coin_rewards_keyboard() -> InlineKeyboardMarkup:
    """Get admin coin rewards management keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 لیست تنظیمات", callback_data="admin:coin_reward:list"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:coin_settings"),
        ],
    ])
    return keyboard


def get_coin_reward_list_keyboard(settings: list) -> InlineKeyboardMarkup:
    """Get coin reward settings list keyboard."""
    keyboard = []
    
    # Activity type names in Persian
    activity_names = {
        "daily_login": "ورود روزانه",
        "chat_success": "چت موفق",
        "mutual_like": "لایک متقابل",
        "referral_referrer": "دعوت‌کننده",
        "referral_referred": "دعوت‌شده",
    }
    
    for setting in settings:
        activity_name = activity_names.get(setting.activity_type, setting.activity_type)
        status = "✅" if setting.is_active else "❌"
        keyboard.append([
            InlineKeyboardButton(
                text=f"{status} {activity_name}: {setting.coins_amount} سکه",
                callback_data=f"admin:coin_reward:edit:{setting.activity_type}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:coin_rewards"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_referral_link_list_keyboard(links: list, page: int = 0, total_pages: int = 1) -> InlineKeyboardMarkup:
    """Get referral link list keyboard with pagination."""
    keyboard = []
    
    # Show up to 5 links per page
    start_idx = page * 5
    end_idx = min(start_idx + 5, len(links))
    
    for link in links[start_idx:end_idx]:
        status = "✅" if link.is_active else "❌"
        keyboard.append([
            InlineKeyboardButton(
                text=f"{status} {link.link_code} ({link.click_count} کلیک, {link.signup_count} عضو)",
                callback_data=f"admin:referral_link:view:{link.id}"
            )
        ])
    
    # Pagination buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"admin:referral_link:list:{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="▶️ بعدی", callback_data=f"admin:referral_link:list:{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:referral_links"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_referral_link_detail_keyboard(link_id: int) -> InlineKeyboardMarkup:
    """Get referral link detail keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 آمار کامل", callback_data=f"admin:referral_link:stats:{link_id}"),
        ],
        [
            InlineKeyboardButton(text="✏️ ویرایش", callback_data=f"admin:referral_link:edit:{link_id}"),
            InlineKeyboardButton(text="🗑️ حذف", callback_data=f"admin:referral_link:delete:{link_id}"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:referral_link:list"),
        ],
    ])
    return keyboard


def get_admin_system_settings_keyboard() -> InlineKeyboardMarkup:
    """Get admin system settings keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌐 آدرس درگاه پرداخت", callback_data="admin:setting:payment_gateway_domain"),
        ],
        [
            InlineKeyboardButton(text="🔑 Merchant ID زرین‌پال", callback_data="admin:setting:zarinpal_merchant_id"),
        ],
        [
            InlineKeyboardButton(text="🧪 حالت Sandbox", callback_data="admin:setting:zarinpal_sandbox"),
        ],
        [
            InlineKeyboardButton(text="💰 هزینه پیام چت", callback_data="admin:setting:chat_message_cost"),
        ],
        [
            InlineKeyboardButton(text="📊 تعداد پیام برای کسر سکه", callback_data="admin:setting:chat_success_message_count"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:main"),
        ],
    ])
    return keyboard

