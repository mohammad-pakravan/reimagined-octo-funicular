"""
Playlist keyboards for managing user playlists.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_playlist_menu_keyboard() -> InlineKeyboardMarkup:
    """Get main playlist menu keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎵 مشاهده پلی‌لیست من", callback_data="playlist:view"),
        ],
        [
            InlineKeyboardButton(text="➕ افزودن موزیک", callback_data="playlist:add_music"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="playlist:back"),
        ],
    ])
    return keyboard


def get_playlist_view_keyboard(
    items: list,
    page: int = 0,
    page_size: int = 10,
    total_items: int = 0,
    is_own_playlist: bool = True,
) -> InlineKeyboardMarkup:
    """
    Get keyboard for viewing playlist items with pagination.
    
    Args:
        items: List of PlaylistItem objects
        page: Current page number
        page_size: Number of items per page
        total_items: Total number of items in playlist
        is_own_playlist: Whether this is the user's own playlist (for delete buttons)
    """
    keyboard = []
    
    # Add item buttons
    for item in items:
        # Format item display text
        item_text = "🎵"
        if item.title:
            item_text = f"🎵 {item.title}"
            if item.performer:
                item_text = f"🎵 {item.performer} - {item.title}"
        elif item.message_type == "voice":
            item_text = "🎤 پیام صوتی"
        elif item.message_type == "forwarded":
            item_text = "📤 موزیک فوروارد شده"
        else:
            item_text = "🎵 موزیک"
        
        # Truncate if too long
        if len(item_text) > 40:
            item_text = item_text[:37] + "..."
        
        if is_own_playlist:
            # Own playlist: show delete button
            keyboard.append([
                InlineKeyboardButton(
                    text=item_text,
                    callback_data=f"playlist:play:{item.id}"
                ),
                InlineKeyboardButton(
                    text="🗑️",
                    callback_data=f"playlist:remove:{item.id}"
                )
            ])
        else:
            # Partner's playlist: only play button
            keyboard.append([
                InlineKeyboardButton(
                    text=item_text,
                    callback_data=f"playlist:play:{item.id}"
                )
            ])
    
    # Pagination buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(
            text="⬅️ قبلی",
            callback_data=f"playlist:page:{page-1}"
        ))
    if (page + 1) * page_size < total_items:
        nav_buttons.append(InlineKeyboardButton(
            text="➡️ بعدی",
            callback_data=f"playlist:page:{page+1}"
        ))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Add music button for own playlist
    if is_own_playlist:
        keyboard.append([
            InlineKeyboardButton(text="➕ افزودن موزیک", callback_data="playlist:add_music")
        ])
    
    # Back button (only for own playlist)
    if is_own_playlist:
        keyboard.append([
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="playlist:back")
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_add_to_playlist_keyboard(message_id: int, file_id: str) -> InlineKeyboardMarkup:
    """
    Get inline keyboard for adding music to playlist.
    
    Args:
        message_id: Telegram message ID
        file_id: Telegram file_id of the music (will be hashed to fit in callback_data)
    """
    import hashlib
    # Hash file_id to fit in callback_data (max 64 bytes)
    # Use first 32 chars of hash + message_id
    file_id_hash = hashlib.md5(file_id.encode()).hexdigest()[:16]
    callback_data = f"playlist:add:{message_id}:{file_id_hash}"
    
    # Ensure callback_data is not too long (Telegram limit is 64 bytes)
    if len(callback_data) > 64:
        callback_data = callback_data[:64]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="➕ افزودن به پلی‌لیست",
                callback_data=callback_data
            )
        ]
    ])
    return keyboard


def get_playlist_item_keyboard(item_id: int, is_own_playlist: bool = True) -> InlineKeyboardMarkup:
    """
    Get keyboard for a single playlist item.
    
    Args:
        item_id: PlaylistItem ID
        is_own_playlist: Whether this is the user's own playlist
    """
    keyboard = []
    
    if is_own_playlist:
        keyboard.append([
            InlineKeyboardButton(
                text="🗑️ حذف از پلی‌لیست",
                callback_data=f"playlist:remove:{item_id}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="playlist:view")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_empty_playlist_keyboard(is_own_playlist: bool = True) -> InlineKeyboardMarkup:
    """Get keyboard for empty playlist."""
    keyboard = []
    
    if is_own_playlist:
        keyboard.append([
            InlineKeyboardButton(text="➕ افزودن موزیک", callback_data="playlist:add_music")
        ])
        keyboard.append([
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="playlist:back")
        ])
    # No buttons for partner's empty playlist
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

