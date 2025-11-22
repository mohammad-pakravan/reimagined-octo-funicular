"""
Playlist handler for managing user playlists.
"""
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

logger = logging.getLogger(__name__)

from db.database import get_db
from db.crud import (
    get_user_by_telegram_id,
    get_user_playlist,
    get_partner_playlist,
    add_item_to_playlist,
    remove_item_from_playlist,
    get_playlist_items,
    get_playlist_item_count,
    check_item_exists_in_playlist,
    get_active_chat_room_by_user,
)
from bot.keyboards.playlist import (
    get_playlist_menu_keyboard,
    get_playlist_view_keyboard,
    get_empty_playlist_keyboard,
)
from bot.keyboards.reply import get_main_reply_keyboard, get_chat_reply_keyboard
from core.chat_manager import ChatManager

router = Router()

chat_manager = None

def set_chat_manager(manager: ChatManager):
    """Set chat manager instance."""
    global chat_manager
    chat_manager = manager


@router.message(F.text == "🎵 پلی‌لیست من")
async def handle_playlist_menu(message: Message, state: FSMContext):
    """Handle playlist menu button."""
    user_id = message.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await message.answer("❌ لطفاً ابتدا پروفایل خودت را کامل کن. /start را بزنید.")
            return
        
        # Get or create playlist
        playlist = await get_user_playlist(db_session, user.id)
        item_count = await get_playlist_item_count(db_session, playlist.id)
        
        text = (
            f"🎵 پلی‌لیست من\n\n"
            f"📊 تعداد موزیک‌ها: {item_count}\n\n"
            f"برای مشاهده و مدیریت پلی‌لیست خود، دکمه زیر را بزنید:"
        )
        
        await message.answer(
            text,
            reply_markup=get_playlist_menu_keyboard()
        )
        break


@router.message(F.text == "🎵 پلی‌لیست مخاطب")
async def handle_partner_playlist_button(message: Message, state: FSMContext):
    """Handle partner playlist button in chat."""
    user_id = message.from_user.id
    
    if not chat_manager:
        await message.answer("❌ خطا در اتصال به سیستم چت.")
        return
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            return
        
        # Check if user has active chat
        if not await chat_manager.is_chat_active(user.id, db_session):
            await message.answer(
                "❌ شما در حال حاضر چت فعالی ندارید.",
                reply_markup=get_main_reply_keyboard()
            )
            return
        
        # Get partner ID using chat_manager
        partner_id = await chat_manager.get_partner_id(user.id, db_session)
        if not partner_id:
            await message.answer(
                "❌ هم‌چت پیدا نشد.",
                reply_markup=get_chat_reply_keyboard()
            )
            return
        
        # Get partner user by database ID
        from db.crud import get_user_by_id
        partner = await get_user_by_id(db_session, partner_id)
        if not partner:
            await message.answer(
                "❌ اطلاعات مخاطب یافت نشد.",
                reply_markup=get_chat_reply_keyboard()
            )
            return
        
        # Get partner's playlist
        partner_playlist = await get_partner_playlist(db_session, partner.id)
        
        if not partner_playlist:
            await message.answer(
                f"🎵 پلی‌لیست {partner.display_name or 'مخاطب'}\n\n"
                f"📭 این کاربر هنوز پلی‌لیستی ندارد.",
                reply_markup=get_empty_playlist_keyboard(is_own_playlist=False)
            )
            
            # Notify partner that someone tried to view their playlist but they don't have one
            try:
                from aiogram import Bot
                from config.settings import settings
                bot = Bot(token=settings.BOT_TOKEN)
                
                viewer_name = user.display_name or user.username or "کسی"
                notification_text = (
                    f"👀 {viewer_name} از پلی‌لیست شما بازدید کرد!\n\n"
                    f"📭 پلی‌لیست شما در حال حاضر خالی است.\n\n"
                    f"💡 یادت نره پلی‌لیستت رو آپدیت کنی! موزیک‌های خودت رو بفرست و به پلی‌لیست اضافه کن."
                )
                
                await bot.send_message(
                    chat_id=partner.telegram_id,
                    text=notification_text
                )
                await bot.session.close()
            except Exception as e:
                logger.error(f"Error sending playlist view notification: {e}")
            
            return
        
        # Get playlist items
        items = await get_playlist_items(db_session, partner_playlist.id, limit=10, offset=0)
        total_items = await get_playlist_item_count(db_session, partner_playlist.id)
        
        if not items:
            await message.answer(
                f"🎵 پلی‌لیست {partner.display_name or 'مخاطب'}\n\n"
                f"📭 پلی‌لیست خالی است.",
                reply_markup=get_empty_playlist_keyboard(is_own_playlist=False)
            )
            
            # Notify partner that someone viewed their empty playlist
            try:
                from aiogram import Bot
                from config.settings import settings
                bot = Bot(token=settings.BOT_TOKEN)
                
                viewer_name = user.display_name or user.username or "کسی"
                notification_text = (
                    f"👀 {viewer_name} از پلی‌لیست شما بازدید کرد!\n\n"
                    f"📭 پلی‌لیست شما در حال حاضر خالی است.\n\n"
                    f"💡 یادت نره پلی‌لیستت رو آپدیت کنی! موزیک‌های خودت رو بفرست و به پلی‌لیست اضافه کن."
                )
                
                await bot.send_message(
                    chat_id=partner.telegram_id,
                    text=notification_text
                )
                await bot.session.close()
            except Exception as e:
                logger.error(f"Error sending playlist view notification: {e}")
            
            return
        
        # Format playlist text
        text = f"🎵 پلی‌لیست {partner.display_name or 'مخاطب'}\n\n"
        text += f"📊 تعداد موزیک‌ها: {total_items}\n\n"
        text += "برای پخش موزیک، روی آن کلیک کن:"
        
        await message.answer(
            text,
            reply_markup=get_playlist_view_keyboard(
                items=items,
                page=0,
                page_size=10,
                total_items=total_items,
                is_own_playlist=False
            )
        )
        
        # Notify partner that someone viewed their playlist
        try:
            from aiogram import Bot
            from config.settings import settings
            bot = Bot(token=settings.BOT_TOKEN)
            
            viewer_name = user.display_name or user.username or "کسی"
            notification_text = (
                f"👀 {viewer_name} از پلی‌لیست شما بازدید کرد!\n\n"
                f"📊 پلی‌لیست شما {total_items} موزیک دارد."
            )
            
            await bot.send_message(
                chat_id=partner.telegram_id,
                text=notification_text
            )
            await bot.session.close()
        except Exception as e:
            # Silently fail if notification can't be sent
            logger.error(f"Error sending playlist view notification: {e}")
        
        break


@router.callback_query(F.data.startswith("playlist:view"))
async def handle_view_playlist(callback: CallbackQuery):
    """Handle view playlist callback."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ خطا در دریافت اطلاعات کاربر.")
            return
        
        # Get playlist
        playlist = await get_user_playlist(db_session, user.id)
        items = await get_playlist_items(db_session, playlist.id, limit=10, offset=0)
        total_items = await get_playlist_item_count(db_session, playlist.id)
        
        if not items:
            text = (
                "🎵 پلی‌لیست من\n\n"
                "📭 پلی‌لیست شما خالی است.\n\n"
                "برای افزودن موزیک، موزیک‌های خود را فوروارد کنید یا بفرستید و روی دکمه «➕ افزودن به پلی‌لیست» کلیک کنید."
            )
            try:
                if callback.message.text:
                    await callback.message.edit_text(
                        text,
                        reply_markup=get_empty_playlist_keyboard(is_own_playlist=True)
                    )
                else:
                    await callback.message.answer(
                        text,
                        reply_markup=get_empty_playlist_keyboard(is_own_playlist=True)
                    )
            except TelegramBadRequest:
                await callback.message.answer(
                    text,
                    reply_markup=get_empty_playlist_keyboard(is_own_playlist=True)
                )
            await callback.answer()
            return
        
        text = f"🎵 پلی‌لیست من\n\n"
        text += f"📊 تعداد موزیک‌ها: {total_items}\n\n"
        text += "برای پخش یا حذف موزیک، روی آن کلیک کن:"
        
        try:
            if callback.message.text:
                await callback.message.edit_text(
                    text,
                    reply_markup=get_playlist_view_keyboard(
                        items=items,
                        page=0,
                        page_size=10,
                        total_items=total_items,
                        is_own_playlist=True
                    )
                )
            else:
                await callback.message.answer(
                    text,
                    reply_markup=get_playlist_view_keyboard(
                        items=items,
                        page=0,
                        page_size=10,
                        total_items=total_items,
                        is_own_playlist=True
                    )
                )
        except TelegramBadRequest:
            await callback.message.answer(
                text,
                reply_markup=get_playlist_view_keyboard(
                    items=items,
                    page=0,
                    page_size=10,
                    total_items=total_items,
                    is_own_playlist=True
                )
            )
        
        await callback.answer()
        break


@router.callback_query(F.data.startswith("playlist:page:"))
async def handle_playlist_pagination(callback: CallbackQuery):
    """Handle playlist pagination."""
    user_id = callback.from_user.id
    page = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ خطا در دریافت اطلاعات کاربر.")
            return
        
        # Get playlist
        playlist = await get_user_playlist(db_session, user.id)
        items = await get_playlist_items(db_session, playlist.id, limit=10, offset=page * 10)
        total_items = await get_playlist_item_count(db_session, playlist.id)
        
        if not items:
            await callback.answer("❌ صفحه‌ای یافت نشد.", show_alert=True)
            return
        
        text = f"🎵 پلی‌لیست من\n\n"
        text += f"📊 تعداد موزیک‌ها: {total_items}\n\n"
        text += "برای پخش یا حذف موزیک، روی آن کلیک کن:"
        
        try:
            if callback.message.text:
                await callback.message.edit_text(
                    text,
                    reply_markup=get_playlist_view_keyboard(
                        items=items,
                        page=page,
                        page_size=10,
                        total_items=total_items,
                        is_own_playlist=True
                    )
                )
            else:
                await callback.message.answer(
                    text,
                    reply_markup=get_playlist_view_keyboard(
                        items=items,
                        page=page,
                        page_size=10,
                        total_items=total_items,
                        is_own_playlist=True
                    )
                )
        except TelegramBadRequest:
            await callback.message.answer(
                text,
                reply_markup=get_playlist_view_keyboard(
                    items=items,
                    page=page,
                    page_size=10,
                    total_items=total_items,
                    is_own_playlist=True
                )
            )
        
        await callback.answer()
        break


@router.callback_query(F.data.startswith("playlist:play:"))
async def handle_play_music(callback: CallbackQuery, bot: Bot):
    """Handle play music callback."""
    user_id = callback.from_user.id
    item_id = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        from db.models import PlaylistItem
        from sqlalchemy import select
        
        # Get playlist item
        query = select(PlaylistItem).where(PlaylistItem.id == item_id)
        result = await db_session.execute(query)
        item = result.scalar_one_or_none()
        
        if not item:
            await callback.answer("❌ موزیک یافت نشد.", show_alert=True)
            return
        
        # Send the music file
        try:
            if item.message_type == "audio":
                await bot.send_audio(
                    chat_id=user_id,
                    audio=item.file_id,
                    title=item.title,
                    performer=item.performer,
                    duration=item.duration
                )
            elif item.message_type == "voice":
                await bot.send_voice(
                    chat_id=user_id,
                    voice=item.file_id,
                    duration=item.duration
                )
            else:
                # For forwarded messages, try to forward if possible
                if item.forwarded_from_chat_id and item.forwarded_from_message_id:
                    try:
                        await bot.forward_message(
                            chat_id=user_id,
                            from_chat_id=item.forwarded_from_chat_id,
                            message_id=item.forwarded_from_message_id
                        )
                    except:
                        # If forward fails, try to send as audio
                        await bot.send_audio(chat_id=user_id, audio=item.file_id)
                else:
                    await bot.send_audio(chat_id=user_id, audio=item.file_id)
            
            await callback.answer("✅ موزیک ارسال شد!")
        except Exception as e:
            await callback.answer(f"❌ خطا در ارسال موزیک: {str(e)}", show_alert=True)
        
        break


@router.callback_query(F.data.startswith("playlist:remove:"))
async def handle_remove_from_playlist(callback: CallbackQuery):
    """Handle remove item from playlist."""
    user_id = callback.from_user.id
    item_id = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        from db.models import PlaylistItem
        from sqlalchemy import select
        
        # Get playlist item and verify ownership
        query = select(PlaylistItem).where(PlaylistItem.id == item_id)
        result = await db_session.execute(query)
        item = result.scalar_one_or_none()
        
        if not item:
            await callback.answer("❌ موزیک یافت نشد.", show_alert=True)
            return
        
        # Check if user owns this playlist
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user or item.playlist.user_id != user.id:
            await callback.answer("❌ شما اجازه حذف این موزیک را ندارید.", show_alert=True)
            return
        
        # Remove item
        success = await remove_item_from_playlist(db_session, item_id)
        
        if success:
            await callback.answer("✅ موزیک از پلی‌لیست حذف شد!")
            
            # Refresh playlist view
            playlist = await get_user_playlist(db_session, user.id)
            items = await get_playlist_items(db_session, playlist.id, limit=10, offset=0)
            total_items = await get_playlist_item_count(db_session, playlist.id)
            
            if not items:
                await callback.message.edit_text(
                    "🎵 پلی‌لیست من\n\n"
                    "📭 پلی‌لیست شما خالی است.\n\n"
                    "برای افزودن موزیک، موزیک‌های خود را فوروارد کنید یا بفرستید و روی دکمه «➕ افزودن به پلی‌لیست» کلیک کنید.",
                    reply_markup=get_empty_playlist_keyboard(is_own_playlist=True)
                )
            else:
                text = f"🎵 پلی‌لیست من\n\n"
                text += f"📊 تعداد موزیک‌ها: {total_items}\n\n"
                text += "برای پخش یا حذف موزیک، روی آن کلیک کن:"
                
                try:
                    await callback.message.edit_text(
                        text,
                        reply_markup=get_playlist_view_keyboard(
                            items=items,
                            page=0,
                            page_size=10,
                            total_items=total_items,
                            is_own_playlist=True
                        )
                    )
                except TelegramBadRequest:
                    pass
        else:
            await callback.answer("❌ خطا در حذف موزیک.", show_alert=True)
        
        break


@router.callback_query(F.data.startswith("playlist:add:"))
async def handle_add_to_playlist(callback: CallbackQuery):
    """Handle add music to playlist callback."""
    user_id = callback.from_user.id
    parts = callback.data.split(":")
    message_id = int(parts[2])
    file_id_hash = parts[3] if len(parts) > 3 else None
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ خطا در دریافت اطلاعات کاربر.")
            return
        
        # Get the original music message from reply
        source_message = callback.message.reply_to_message if callback.message.reply_to_message else None
        
        # If no reply, try to get message by ID (if it's in the same chat)
        if not source_message:
            try:
                source_message = await callback.bot.forward_message(
                    chat_id=user_id,
                    from_chat_id=callback.message.chat.id,
                    message_id=message_id
                )
                # If forward works, we got the message but we need the original
                # Actually, we should get the message directly
                source_message = None
            except:
                pass
        
        # Get playlist
        playlist = await get_user_playlist(db_session, user.id)
        
        # Determine message type and extract metadata
        message_type = "audio"
        file_id = None
        title = None
        performer = None
        duration = None
        forwarded_from_chat_id = None
        forwarded_from_message_id = None
        
        # Get metadata from source message
        if source_message:
            if source_message.audio:
                file_id = source_message.audio.file_id
                title = source_message.audio.title
                performer = source_message.audio.performer
                duration = source_message.audio.duration
                message_type = "audio"
            elif source_message.voice:
                file_id = source_message.voice.file_id
                message_type = "voice"
                duration = source_message.voice.duration
            elif source_message.forward_from_chat:
                if source_message.audio:
                    file_id = source_message.audio.file_id
                    title = source_message.audio.title
                    performer = source_message.audio.performer
                    duration = source_message.audio.duration
                message_type = "forwarded"
                forwarded_from_chat_id = source_message.forward_from_chat.id
                forwarded_from_message_id = source_message.forward_from_message_id
        
        # If we still don't have file_id, try to get it from the message that has the button
        # The button is usually on a reply to the music message
        if not file_id and callback.message.reply_to_message:
            reply_msg = callback.message.reply_to_message
            if reply_msg.audio:
                file_id = reply_msg.audio.file_id
                title = reply_msg.audio.title
                performer = reply_msg.audio.performer
                duration = reply_msg.audio.duration
                message_type = "audio"
            elif reply_msg.voice:
                file_id = reply_msg.voice.file_id
                message_type = "voice"
                duration = reply_msg.voice.duration
            elif reply_msg.forward_from_chat:
                if reply_msg.audio:
                    file_id = reply_msg.audio.file_id
                    title = reply_msg.audio.title
                    performer = reply_msg.audio.performer
                    duration = reply_msg.audio.duration
                message_type = "forwarded"
                forwarded_from_chat_id = reply_msg.forward_from_chat.id
                forwarded_from_message_id = reply_msg.forward_from_message_id
        
        if not file_id:
            await callback.answer("❌ خطا در دریافت فایل موزیک. لطفاً دوباره موزیک را بفرستید.", show_alert=True)
            return
        
        # Check if item already exists
        exists = await check_item_exists_in_playlist(db_session, playlist.id, file_id)
        if exists:
            await callback.answer("⚠️ این موزیک قبلاً در پلی‌لیست شما است.", show_alert=True)
            return
        
        # Add to playlist
        await add_item_to_playlist(
            session=db_session,
            playlist_id=playlist.id,
            message_type=message_type,
            file_id=file_id,
            title=title,
            performer=performer,
            duration=duration,
            forwarded_from_chat_id=forwarded_from_chat_id,
            forwarded_from_message_id=forwarded_from_message_id,
        )
        
        await callback.answer("✅ موزیک به پلی‌لیست شما اضافه شد!")
        
        # Update button to show it's added
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except:
            pass
        
        break


@router.callback_query(F.data == "playlist:back")
async def handle_playlist_back(callback: CallbackQuery):
    """Handle back button from playlist menu."""
    await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data == "playlist:add_music")
async def handle_add_music_instruction(callback: CallbackQuery):
    """Handle add music button - show instructions."""
    text = (
        "➕ افزودن موزیک به پلی‌لیست\n\n"
        "برای افزودن موزیک به پلی‌لیست خود:\n\n"
        "1️⃣ موزیک خود را بفرستید یا فوروارد کنید\n"
        "2️⃣ روی دکمه «➕ افزودن به پلی‌لیست» که زیر پیام نمایش داده می‌شود کلیک کنید\n\n"
        "💡 می‌توانید فایل صوتی، پیام صوتی یا موزیک فوروارد شده را اضافه کنید."
    )
    
    try:
        if callback.message.text:
            await callback.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 بازگشت", callback_data="playlist:view")]
                ])
            )
        else:
            await callback.message.answer(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 بازگشت", callback_data="playlist:view")]
                ])
            )
    except TelegramBadRequest:
        await callback.message.answer(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 بازگشت", callback_data="playlist:view")]
            ])
        )
    
    await callback.answer()

