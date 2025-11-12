"""
Direct message list handlers.
Handles viewing direct messages from specific senders and replying.
"""
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter, BaseFilter
from aiogram.enums import ContentType
from typing import Any

from db.database import get_db
from db.crud import (
    get_user_by_telegram_id,
    get_user_by_id,
    get_direct_messages_received,
    get_direct_message_list,
    mark_direct_message_read,
    create_direct_message,
    is_blocked,
    delete_conversation,
)
from bot.keyboards.my_profile import get_direct_messages_list_keyboard
from bot.keyboards.common import get_dm_reply_keyboard, get_dm_confirm_keyboard, get_dm_receive_keyboard
from config.settings import settings

router = Router()


class IsReplyFilter(BaseFilter):
    """Filter to check if callback is for a reply."""
    
    async def __call__(self, callback: CallbackQuery, state: FSMContext) -> bool:
        """Check if this is a reply callback."""
        if not callback.data or not callback.data.startswith("dm:confirm:"):
            return False
        
        try:
            sender_id = int(callback.data.split(":")[-1])
        except (ValueError, IndexError):
            return False
        
        state_data = await state.get_data()
        reply_to_sender_id = state_data.get("dm_reply_to_sender_id")
        
        return reply_to_sender_id is not None and reply_to_sender_id == sender_id


@router.callback_query(F.data.startswith("dm_list:view:"))
async def view_direct_messages_from_list(callback: CallbackQuery):
    """View direct messages from a specific sender."""
    sender_id = int(callback.data.split(":")[-1])
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Get all messages from this sender
        all_messages = await get_direct_messages_received(db_session, user.id, limit=100)
        
        # Filter messages from this specific sender
        sender_messages = [msg for msg in all_messages if msg.sender_id == sender_id]
        sender_messages = sorted(sender_messages, key=lambda x: x.created_at, reverse=True)  # Newest first
        
        if not sender_messages:
            await callback.answer("📭 هیچ پیامی از این کاربر ندارید.", show_alert=True)
            return
        
        # Get sender info
        sender = await get_user_by_id(db_session, sender_id)
        if not sender:
            await callback.answer("❌ فرستنده یافت نشد.", show_alert=True)
            return
        
        # Generate profile_id if not exists
        if not sender.profile_id:
            import hashlib
            profile_id = hashlib.md5(f"user_{sender.telegram_id}".encode()).hexdigest()[:12]
            sender.profile_id = profile_id
            await db_session.commit()
            await db_session.refresh(sender)
        
        gender_map = {"male": "پسر 🧑", "female": "دختر 👩", "other": "سایر"}
        gender_text = gender_map.get(sender.gender, sender.gender or "تعیین نشده")
        
        # Get sender profile ID
        sender_profile_id = f"/user_{sender.profile_id}"
        
        # Show all messages
        from utils.validators import get_display_name
        messages_text = f"✉️ پیام‌های دایرکت\n\n"
        messages_text += f"👤 از: {get_display_name(sender)}\n"
        messages_text += f"⚧️ جنسیت: {gender_text}\n"
        messages_text += f"🆔 ID: {sender_profile_id}\n"
        messages_text += f"📊 تعداد پیام‌ها: {len(sender_messages)}\n\n"
        messages_text += "📝 پیام‌ها:\n\n"
        
        for idx, msg in enumerate(sender_messages, 1):
            date_str = msg.created_at.strftime('%Y-%m-%d %H:%M')
            read_status = "✅" if msg.is_read else "🔴"
            messages_text += f"{read_status} [{idx}] {date_str}\n{msg.message_text}\n\n"
        
        if len(messages_text) > 4000:
            # Telegram message limit, show only latest messages
            messages_text = f"✉️ پیام‌های دایرکت\n\n"
            messages_text += f"👤 از: {get_display_name(sender)}\n"
            messages_text += f"⚧️ جنسیت: {gender_text}\n"
            messages_text += f"📊 تعداد پیام‌ها: {len(sender_messages)}\n\n"
            messages_text += f"🆔 ID: {sender_profile_id}\n"            
            messages_text += "📝 آخرین پیام‌ها:\n\n"
            
            for msg in sender_messages[:10]:  # Show only latest 10
                date_str = msg.created_at.strftime('%Y-%m-%d %H:%M')
                read_status = "✅" if msg.is_read else "🔴"
                messages_text += f"{read_status} {date_str}\n{msg.message_text}\n\n"
            
            messages_text += f"\n... و {len(sender_messages) - 10} پیام دیگر"
        
        # Mark all messages as read
        for msg in sender_messages:
            if not msg.is_read:
                await mark_direct_message_read(db_session, msg.id)
        
        # Add reply keyboard
        reply_keyboard = get_dm_reply_keyboard(sender_id)
        
        try:
            await callback.message.edit_text(messages_text, reply_markup=reply_keyboard)
        except:
            await callback.message.answer(messages_text, reply_markup=reply_keyboard)
        await callback.answer()
        break


@router.callback_query(F.data.startswith("dm_list:page:"))
async def direct_messages_list_page(callback: CallbackQuery):
    """Handle pagination for direct messages list."""
    page = int(callback.data.split(":")[-1])
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        message_list = await get_direct_message_list(db_session, user.id)
        
        if not message_list:
            await callback.answer("📭 شما هیچ پیام دایرکتی ندارید.", show_alert=True)
            return
        
        # Create keyboard with buttons
        keyboard = get_direct_messages_list_keyboard(message_list, page=page)
        
        list_text = f"✉️ پیام‌های دایرکت ({len(message_list)} پیام)\n\n"
        list_text += "لیست کاربرانی که برای شما پیام فرستاده‌اند:\n"
        list_text += "روی هر کاربر کلیک کنید تا پیام‌هایش را ببینید:"
        
        try:
            await callback.message.edit_text(list_text, reply_markup=keyboard)
        except:
            await callback.message.answer(list_text, reply_markup=keyboard)
        await callback.answer()
        break


@router.callback_query(F.data.startswith("dm:reply:"))
async def reply_to_direct_message(callback: CallbackQuery, state: FSMContext):
    """Start replying to direct message - set FSM state."""
    sender_id = int(callback.data.split(":")[-1])
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        sender = await get_user_by_id(db_session, sender_id)
        if not sender:
            await callback.answer("❌ فرستنده یافت نشد.", show_alert=True)
            return
        
        # Check if sender has blocked the user
        if await is_blocked(db_session, sender.id, user.id):
            await callback.answer("❌ این کاربر شما را بلاک کرده است و نمی‌توانید به او پیام بفرستید.", show_alert=True)
            return
        
        # Set FSM state to wait for reply message
        await state.update_data(dm_reply_to_sender_id=sender_id)
        await state.set_state("dm:waiting_reply")
        
        await callback.message.answer(
            f"✉️ پاسخ به {get_display_name(sender)}\n\n"
            "لطفاً متن پاسخ خود را بنویسید:"
        )
        await callback.answer()
        break


@router.message(StateFilter("dm:waiting_reply"), F.content_type == ContentType.TEXT)
async def process_dm_reply(message: Message, state: FSMContext):
    """Process direct message reply text from user."""
    user_id = message.from_user.id
    reply_text = message.text.strip()
    
    if not reply_text or len(reply_text) < 1:
        await message.answer("❌ پیام نمی‌تواند خالی باشد. لطفاً پاسخ خود را بنویسید:")
        return
    
    if len(reply_text) > 5000:
        await message.answer("❌ پیام خیلی طولانی است. حداکثر 5000 کاراکتر مجاز است.")
        return
    
    # Get sender_id from state
    state_data = await state.get_data()
    sender_id = state_data.get("dm_reply_to_sender_id")
    
    if not sender_id:
        await message.answer("❌ خطا در دریافت اطلاعات گیرنده.")
        await state.clear()
        return
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await message.answer("❌ کاربر یافت نشد.")
            await state.clear()
            return
        
        sender = await get_user_by_id(db_session, sender_id)
        if not sender:
            await message.answer("❌ گیرنده یافت نشد.")
            await state.clear()
            return
        
        # Show confirmation
        await message.answer(
            f"✉️ پاسخ به پیام دایرکت\n\n"
            f"📝 پاسخ شما:\n{reply_text}\n\n"
            f"📤 برای: {get_display_name(sender)}\n\n"
            f"آیا می‌خواهید این پاسخ را ارسال کنید؟",
            reply_markup=get_dm_confirm_keyboard(sender_id)
        )
        
        # Store reply text in state
        await state.update_data(dm_message_text=reply_text)
        break


@router.callback_query(F.data.startswith("dm:confirm:"), IsReplyFilter())
async def confirm_dm_reply_send(callback: CallbackQuery, state: FSMContext):
    """Confirm and send direct message reply."""
    sender_id = int(callback.data.split(":")[-1])
    user_id = callback.from_user.id
    
    # Get state data
    state_data = await state.get_data()
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            await state.clear()
            return
        
        sender = await get_user_by_id(db_session, sender_id)
        if not sender:
            await callback.answer("❌ گیرنده یافت نشد.", show_alert=True)
            await state.clear()
            return
        
        # Get reply text from state
        reply_text = state_data.get("dm_message_text")
        
        if not reply_text:
            await callback.answer("❌ پاسخ یافت نشد.", show_alert=True)
            await state.clear()
            return
        
        # Create direct message (reply)
        dm = await create_direct_message(
            db_session,
            sender_id=user.id,
            receiver_id=sender.id,
            message_text=reply_text
        )
        
        # Notify original sender immediately
        bot = Bot(token=settings.BOT_TOKEN)
        try:
            # Generate profile_id if not exists
            if not user.profile_id:
                import hashlib
                profile_id = hashlib.md5(f"user_{user.telegram_id}".encode()).hexdigest()[:12]
                user.profile_id = profile_id
                await db_session.commit()
                await db_session.refresh(user)
            
            gender_map = {"male": "پسر", "female": "دختر", "other": "سایر"}
            gender_text = gender_map.get(user.gender, user.gender or "نامشخص")
            
            # Get user profile ID
            user_profile_id = f"/user_{user.profile_id}"
            
            # Send notification like a regular direct message
            await bot.send_message(
                sender.telegram_id,
                f"✉️ یک پیام دایرکت از {get_display_name(user)} داری!\n\n"
                f"👤 نام: {get_display_name(user)}\n"
                f"⚧️ جنسیت: {gender_text}\n"
                f"🆔 ID: {user_profile_id}\n\n"
                f"برای مشاهده پیام از دکمه زیر استفاده کن:",
                reply_markup=get_dm_receive_keyboard(dm.id)
            )
            await bot.session.close()
        except Exception as e:
            # If bot can't send message, still save the message
            pass
        
        await callback.message.edit_text(
            "✅ پاسخ شما با موفقیت ارسال شد!\n\n"
            f"پاسخ شما برای {get_display_name(sender)} ارسال شد.",
            reply_markup=None
        )
        await callback.answer("✅ پاسخ ارسال شد!")
        await state.clear()
        break


@router.callback_query(F.data.startswith("dm_list:delete_conversation:"))
async def delete_conversation_handler(callback: CallbackQuery):
    """Delete entire conversation between current user and another user."""
    other_user_id = int(callback.data.split(":")[-1])
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        other_user = await get_user_by_id(db_session, other_user_id)
        if not other_user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Delete all messages between the two users
        deleted_count = await delete_conversation(db_session, user.id, other_user_id)
        
        if deleted_count > 0:
            await callback.answer(f"✅ {deleted_count} پیام حذف شد", show_alert=True)
            
            # Refresh the direct messages list
            message_list = await get_direct_message_list(db_session, user.id)
            
            if not message_list:
                await callback.message.edit_text(
                    "📭 شما هیچ پیام دایرکتی ندارید.",
                    reply_markup=None
                )
            else:
                # Create keyboard with buttons
                keyboard = get_direct_messages_list_keyboard(message_list, page=0)
                
                list_text = f"✉️ پیام‌های دایرکت ({len(message_list)} پیام)\n\n"
                list_text += "لیست کاربرانی که برای شما پیام فرستاده‌اند:\n"
                list_text += "روی هر کاربر کلیک کنید تا پیام‌هایش را ببینید:"
                
                try:
                    await callback.message.edit_text(list_text, reply_markup=keyboard)
                except:
                    await callback.message.answer(list_text, reply_markup=keyboard)
        else:
            await callback.answer("❌ پیامی برای حذف یافت نشد.", show_alert=True)
        break

