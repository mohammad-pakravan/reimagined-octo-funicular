"""
Event admin keyboards for managing events.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime


def get_admin_events_keyboard() -> InlineKeyboardMarkup:
    """Get admin events management keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ ایجاد ایونت جدید", callback_data="admin:event:create"),
        ],
        [
            InlineKeyboardButton(text="📋 لیست ایونت‌ها", callback_data="admin:event:list"),
        ],
        [
            InlineKeyboardButton(text="🎲 اجرای قرعه‌کشی", callback_data="admin:event:lottery"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:main"),
        ],
    ])
    return keyboard


def get_event_list_keyboard(events: list, page: int = 0, total_pages: int = 1) -> InlineKeyboardMarkup:
    """Get event list keyboard with pagination."""
    keyboard = []
    
    # Show up to 5 events per page
    start_idx = page * 5
    end_idx = min(start_idx + 5, len(events))
    
    for event in events[start_idx:end_idx]:
        status = "✅" if event.is_active else "❌"
        now = datetime.utcnow()
        if event.start_date <= now <= event.end_date:
            status += " (در حال اجرا)"
        elif event.end_date < now:
            status += " (پایان)"
        elif event.start_date > now:
            status += " (آینده)"
        
        keyboard.append([
            InlineKeyboardButton(
                text=f"{status} {event.event_name}",
                callback_data=f"admin:event:view:{event.id}"
            )
        ])
    
    # Pagination buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"admin:event:list:{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="▶️ بعدی", callback_data=f"admin:event:list:{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:events"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_event_detail_keyboard(event_id: int) -> InlineKeyboardMarkup:
    """Get event detail keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 آمار و شرکت‌کنندگان", callback_data=f"admin:event:stats:{event_id}"),
        ],
        [
            InlineKeyboardButton(text="✏️ ویرایش", callback_data=f"admin:event:edit:{event_id}"),
            InlineKeyboardButton(text="🗑️ حذف", callback_data=f"admin:event:delete:{event_id}"),
        ],
        [
            InlineKeyboardButton(text="🔄 فعال/غیرفعال", callback_data=f"admin:event:toggle:{event_id}"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:event:list"),
        ],
    ])
    return keyboard

