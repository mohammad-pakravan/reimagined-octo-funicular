"""
Coin package keyboards for admin and user interfaces.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_admin_coin_packages_keyboard() -> InlineKeyboardMarkup:
    """Get admin coin packages management keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ ایجاد پکیج جدید", callback_data="admin:coin_package:create"),
        ],
        [
            InlineKeyboardButton(text="📋 لیست پکیج‌ها", callback_data="admin:coin_package:list"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:panel"),
        ],
    ])
    return keyboard


def get_coin_package_list_keyboard(packages: list, page: int = 0, total_pages: int = 1) -> InlineKeyboardMarkup:
    """Get coin package list keyboard."""
    keyboard = []
    
    # Show packages (max 10 per page)
    start_idx = page * 10
    end_idx = min(start_idx + 10, len(packages))
    
    for package in packages[start_idx:end_idx]:
        status = "✅" if package.is_active else "❌"
        visible = "👁" if package.is_visible else "🚫"
        keyboard.append([
            InlineKeyboardButton(
                text=f"{status}{visible} {package.package_name} - {package.coin_amount} سکه",
                callback_data=f"admin:coin_package:view:{package.id}"
            )
        ])
    
    # Pagination
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"admin:coin_package:list:{page-1}"))
    if end_idx < len(packages):
        nav_buttons.append(InlineKeyboardButton(text="▶️ بعدی", callback_data=f"admin:coin_package:list:{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:coin_packages"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_coin_package_detail_keyboard(package) -> InlineKeyboardMarkup:
    """Get coin package detail keyboard for admin."""
    keyboard = []
    
    # Toggle active status
    toggle_text = "❌ غیرفعال کردن" if package.is_active else "✅ فعال کردن"
    keyboard.append([
        InlineKeyboardButton(text=toggle_text, callback_data=f"admin:coin_package:toggle:{package.id}")
    ])
    
    # Toggle visibility
    visibility_text = "🚫 مخفی کردن" if package.is_visible else "👁 نمایش دادن"
    keyboard.append([
        InlineKeyboardButton(text=visibility_text, callback_data=f"admin:coin_package:toggle_visibility:{package.id}")
    ])
    
    # Delete
    keyboard.append([
        InlineKeyboardButton(text="🗑 حذف پکیج", callback_data=f"admin:coin_package:delete:{package.id}")
    ])
    
    # Back
    keyboard.append([
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:coin_package:list"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_user_coin_packages_keyboard(packages: list) -> InlineKeyboardMarkup:
    """Get coin packages keyboard for users."""
    keyboard = []
    
    for package in packages:
        # Show package with price
        stars_text = f" | ⭐{package.stars_required}" if package.stars_required else ""
        keyboard.append([
            InlineKeyboardButton(
                text=f"🪙 {package.package_name} - {int(package.price):,} تومان{stars_text}",
                callback_data=f"coin:package:{package.id}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="menu:main"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_insufficient_coins_keyboard(coin_packages: list, premium_plans: list) -> InlineKeyboardMarkup:
    """Get combined premium plans and coin packages keyboard for insufficient funds."""
    keyboard = []
    
    # Add premium plans first
    if premium_plans:
        for plan in premium_plans:
            stars_text = f" | ⭐{plan.stars_required}" if plan.stars_required else ""
            keyboard.append([
                InlineKeyboardButton(
                    text=f"💎 {plan.plan_name} - {int(plan.price):,} تومان{stars_text}",
                    callback_data=f"premium:plan:{plan.id}"
                )
            ])
    
    # Add coin packages
    if coin_packages:
        for package in coin_packages:
            stars_text = f" | ⭐{package.stars_required}" if package.stars_required else ""
            keyboard.append([
                InlineKeyboardButton(
                    text=f"💰 {package.package_name} - {int(package.price):,} تومان{stars_text}",
                    callback_data=f"coin:package:{package.id}"
                )
            ])

    # Add Free Coin button
    keyboard.append([
        InlineKeyboardButton(text="🎁 سکه ی رایگان روزانه", callback_data="points:daily_reward"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_coin_package_payment_keyboard(package) -> InlineKeyboardMarkup:
    """Get payment method selection keyboard for coin package."""
    keyboard = []
    
    # Parse payment methods
    import json
    try:
        payment_methods = json.loads(package.payment_methods_json) if package.payment_methods_json else []
    except (json.JSONDecodeError, TypeError):
        payment_methods = ["shaparak"]
    
    # Add payment method buttons
    if "stars" in payment_methods and package.stars_required:
        keyboard.append([
            InlineKeyboardButton(
                text=f"⭐ پرداخت با استارز ({package.stars_required} ⭐)",
                callback_data=f"coin:package:stars:{package.id}"
            )
        ])
    
    if "shaparak" in payment_methods:
        keyboard.append([
            InlineKeyboardButton(
                text=f"💳 پرداخت آنلاین ({int(package.price):,} تومان)",
                callback_data=f"coin:package:shaparak:{package.id}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="chat:insufficient_coins"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_combined_purchase_keyboard(coin_packages: list, premium_plans: list) -> InlineKeyboardMarkup:
    """Get combined keyboard for coin packages and premium plans."""
    keyboard = []
    
    # Normalize inputs
    premium_plans = premium_plans or []
    coin_packages = coin_packages or []
    
    # Add premium plans first
    for plan in premium_plans:
        stars_text = f" / {plan.stars_required} ⭐" if getattr(plan, "stars_required", None) else ""
        keyboard.append([
            InlineKeyboardButton(
                text=f"💎 {getattr(plan, 'plan_name', getattr(plan, 'name', 'پلان'))} - {int(plan.price):,} تومان{stars_text}",
                callback_data=f"premium:plan:{plan.id}"
            )
        ])
    
    # Add coin packages
    for package in coin_packages:
        stars_text = f" / {package.stars_required} ⭐" if getattr(package, "stars_required", None) else ""
        keyboard.append([
            InlineKeyboardButton(
                text=f"💰 {package.package_name} - {int(package.price):,} تومان{stars_text}",
                callback_data=f"coin:package:{package.id}"
            )
        ])
    
    # Back button
    keyboard.append([
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="menu:premium_coins"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

