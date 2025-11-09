"""
Profile keyboards for user profile page.
Provides interactive buttons for user profile actions.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_profile_keyboard(
    partner_id: int,
    is_liked: bool = False,
    is_following: bool = False,
    is_blocked: bool = False,
    like_count: int = 0,
    is_own_profile: bool = False,
    is_notifying: bool = False,
) -> InlineKeyboardMarkup:
    """
    Get keyboard for partner profile page.
    
    Args:
        partner_id: Partner's database ID
        is_liked: Whether current user has liked this partner
        is_following: Whether current user is following this partner
        is_blocked: Whether current user has blocked this partner
        like_count: Total like count for this user
    """
    keyboard = []
    
    # Like button with count
    like_text = f"Like ❤️ {like_count}" if like_count > 0 else "Like ❤️"
    if is_liked:
        like_text = f"❤️ {like_count} (لایک شده)"
 

 
    
    # Follow button
    follow_text = "دنبال کردن 🚶" if not is_following else "✓ دنبال شده 🚶"
    keyboard.append([
                InlineKeyboardButton(text=like_text, callback_data=f"profile:like:{partner_id}"),
        InlineKeyboardButton(text=follow_text, callback_data=f"profile:follow:{partner_id}")
    ])
    
    # Chat request and Direct message
    keyboard.append([
        InlineKeyboardButton(text="درخواست چت 💬", callback_data=f"profile:chat_request:{partner_id}"),
        InlineKeyboardButton(text="پیام دایرکت ✉️", callback_data=f"profile:dm:{partner_id}")
    ])
    
    # Block/Unblock and Report
    if is_blocked:
        keyboard.append([
            InlineKeyboardButton(text="🔓 آنبلاک", callback_data=f"profile:unblock:{partner_id}"),
            InlineKeyboardButton(text="گزارش کردن ⛔", callback_data=f"profile:report:{partner_id}")
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(text="بلاک 🚫", callback_data=f"profile:block:{partner_id}"),
            InlineKeyboardButton(text="گزارش کردن ⛔", callback_data=f"profile:report:{partner_id}")
        ])
    
    # Gift
    keyboard.append([
        InlineKeyboardButton(text="هدیه به کاربر 🎁", callback_data=f"profile:gift:{partner_id}")
    ])
    
    # Notify when chat ends (toggle based on notification status)
    notify_text = "🔔 چت تموم شد خبر بده" if not is_notifying else "🔕 اطلاع‌رسانی غیرفعال کن"
    keyboard.append([
        InlineKeyboardButton(text=notify_text, callback_data=f"profile:notify_end:{partner_id}")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

