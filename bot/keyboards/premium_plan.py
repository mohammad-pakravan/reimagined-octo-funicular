"""
Premium plan keyboards for admin and user.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_admin_premium_plans_keyboard() -> InlineKeyboardMarkup:
    """Get admin premium plans management keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ ایجاد پلن جدید", callback_data="admin:premium_plan:create"),
        ],
        [
            InlineKeyboardButton(text="📋 لیست پلن‌ها", callback_data="admin:premium_plan:list"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:main"),
        ],
    ])
    return keyboard


def get_premium_plan_list_keyboard(plans: list, page: int = 0, total_pages: int = 1) -> InlineKeyboardMarkup:
    """Get premium plan list keyboard with pagination."""
    keyboard = []
    
    # Show up to 5 plans per page
    start_idx = page * 5
    end_idx = min(start_idx + 5, len(plans))
    
    for plan in plans[start_idx:end_idx]:
        status = "✅" if plan.is_active else "❌"
        status += " 👁️" if plan.is_visible else " 🙈"
        keyboard.append([
            InlineKeyboardButton(
                text=f"{status} {plan.plan_name} ({plan.duration_days} روز)",
                callback_data=f"admin:premium_plan:view:{plan.id}"
            )
        ])
    
    # Pagination buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"admin:premium_plan:list:{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="▶️ بعدی", callback_data=f"admin:premium_plan:list:{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:premium_plans"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_premium_plan_detail_keyboard(plan_id: int) -> InlineKeyboardMarkup:
    """Get premium plan detail keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ ویرایش", callback_data=f"admin:premium_plan:edit:{plan_id}"),
            InlineKeyboardButton(text="🗑️ حذف", callback_data=f"admin:premium_plan:delete:{plan_id}"),
        ],
        [
            InlineKeyboardButton(text="🔄 فعال/غیرفعال", callback_data=f"admin:premium_plan:toggle:{plan_id}"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:premium_plan:list"),
        ],
    ])
    return keyboard


def get_user_premium_plans_keyboard(plans: list) -> InlineKeyboardMarkup:
    """Get user premium plans keyboard."""
    keyboard = []
    
    for plan in plans:
        # Show discount badge if active
        discount_text = ""
        from datetime import datetime
        now = datetime.utcnow()
        if plan.discount_start_date and plan.discount_end_date:
            if plan.discount_start_date <= now <= plan.discount_end_date:
                discount_text = f" 🔥 {plan.discount_percent}% تخفیف"
        
        # Build price text
        price_text = f"{int(plan.price):,} تومان"
        if plan.stars_required:
            price_text += f" / {plan.stars_required} ⭐"
        
        keyboard.append([
            InlineKeyboardButton(
                text=f"💎 {plan.plan_name} - {price_text}{discount_text}",
                callback_data=f"premium:plan:{plan.id}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="engagement:menu"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_premium_plan_payment_keyboard(plan) -> InlineKeyboardMarkup:
    """Get keyboard for premium plan payment methods."""
    import json
    keyboard = []
    
    # Get payment methods, default to shaparak if not set
    if plan.payment_methods_json:
        try:
            payment_methods = json.loads(plan.payment_methods_json)
        except (json.JSONDecodeError, TypeError):
            payment_methods = ["shaparak"]
    else:
        payment_methods = ["shaparak"]
    
    if "shaparak" in payment_methods:
        discount_text = ""
        from datetime import datetime
        now = datetime.utcnow()
        if plan.discount_start_date and plan.discount_end_date:
            if plan.discount_start_date <= now <= plan.discount_end_date:
                discount_text = f" 🔥 {plan.discount_percent}% تخفیف"
        
        price_text = f"{int(plan.price):,} تومان{discount_text}"
        keyboard.append([
            InlineKeyboardButton(
                text=f"💳 پرداخت با شاپرک - {price_text}",
                callback_data=f"premium:plan:shaparak:{plan.id}"
            )
        ])
    
    if "stars" in payment_methods and plan.stars_required:
        keyboard.append([
            InlineKeyboardButton(
                text=f"⭐ پرداخت با استارز - {plan.stars_required} ⭐",
                callback_data=f"premium:plan:stars:{plan.id}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="premium:info"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

