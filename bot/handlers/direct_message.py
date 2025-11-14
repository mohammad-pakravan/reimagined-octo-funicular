"""
Direct message handlers for the bot.
Handles sending, receiving, viewing, and managing direct messages.
"""
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.enums import ContentType

from db.database import get_db
from db.crud import (
    get_user_by_telegram_id,
    get_user_by_id,
    is_blocked,
    create_direct_message,
    get_direct_message_by_id,
    mark_direct_message_read,
    reject_direct_message,
    get_direct_message_list,
    block_user,
)
from bot.keyboards.common import get_dm_confirm_keyboard, get_dm_receive_keyboard, get_dm_view_keyboard
from bot.keyboards.reply import get_main_reply_keyboard
from config.settings import settings
from utils.validators import get_display_name

router = Router()


@router.message(StateFilter("dm:waiting_message"), F.content_type == ContentType.TEXT)
async def process_dm_message(message: Message, state: FSMContext):
    """Process direct message text from user."""
    user_id = message.from_user.id
    message_text = message.text.strip()
    
    if not message_text or len(message_text) < 1:
        await message.answer("❌ پیام نمی‌تواند خالی باشد. لطفاً پیام خود را بنویسید:")
        return
    
    if len(message_text) > 5000:
        await message.answer("❌ پیام خیلی طولانی است. حداکثر 5000 کاراکتر مجاز است.")
        return
    
    # Get receiver_id from state
    state_data = await state.get_data()
    receiver_id = state_data.get("dm_receiver_id")
    
    if not receiver_id:
        await message.answer("❌ خطا در دریافت اطلاعات گیرنده.")
        await state.clear()
        return
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await message.answer("❌ کاربر یافت نشد.")
            await state.clear()
            return
        
        receiver = await get_user_by_id(db_session, receiver_id)
        if not receiver:
            await message.answer("❌ گیرنده یافت نشد.")
            await state.clear()
            return
        
        # Check if user has premium
        from db.crud import check_user_premium, get_user_points
        user_premium = await check_user_premium(db_session, user.id)
        
        # Show confirmation with cost info
        if user_premium:
            cost_text = "💎 این پیام رایگان است (پریمیوم)"
        else:
            user_points = await get_user_points(db_session, user.id)
            if user_points < 1:
                await message.answer(
                    f"⚠️ سکه کافی نداری!\n\n"
                    f"💰 برای ارسال پیام دایرکت به 1 سکه نیاز داری.\n"
                    f"💎 سکه فعلی تو: {user_points}\n\n"
                    f"💡 می‌تونی سکه‌هات رو به پریمیوم تبدیل کنی یا پریمیوم بگیری."
                )
                await state.clear()
                return
            cost_text = f"💰 هزینه این پیام: 1 سکه\n💎 سکه‌های فعلی تو: {user_points}"
        
        await message.answer(
            f"✉️ پیام دایرکت\n\n"
            f"📝 پیام شما:\n{message_text}\n\n"
            f"📤 برای: {get_display_name(receiver)}\n\n"
            f"{cost_text}\n\n"
            f"آیا می‌خواهید این پیام را ارسال کنید؟",
            reply_markup=get_dm_confirm_keyboard(receiver_id)
        )
        
        # Store message text in state
        await state.update_data(dm_message_text=message_text)
        break


@router.callback_query(F.data.startswith("dm:confirm:"))
async def confirm_dm_send(callback: CallbackQuery, state: FSMContext):
    """Confirm and send direct message."""
    receiver_id = int(callback.data.split(":")[-1])
    user_id = callback.from_user.id
    
    # Get state data
    state_data = await state.get_data()
    
    # If this is a reply, dm_list handler should have processed it (it has IsReplyFilter)
    # So if we reach here, it's a new message, not a reply
    # But we should clear any leftover reply state
    reply_to_sender_id = state_data.get("dm_reply_to_sender_id")
    if reply_to_sender_id:
        # Clear reply state if it exists (user was in reply mode but now sending new message)
        await state.update_data(dm_reply_to_sender_id=None)
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            await state.clear()
            return
        
        receiver = await get_user_by_id(db_session, receiver_id)
        if not receiver:
            await callback.answer("❌ گیرنده یافت نشد.", show_alert=True)
            await state.clear()
            return
        
        # Get message text from state
        message_text = state_data.get("dm_message_text")
        
        if not message_text:
            await callback.answer("❌ پیام یافت نشد.", show_alert=True)
            await state.clear()
            return
        
        # Check if user has premium
        from db.crud import check_user_premium, get_user_points, spend_points
        user_premium = await check_user_premium(db_session, user.id)
        
        # Deduct coin if not premium
        if not user_premium:
            user_points = await get_user_points(db_session, user.id)
            if user_points < 1:
                await callback.answer("❌ سکه کافی نداری!", show_alert=True)
                await state.clear()
                return
            
            # Deduct 1 coin
            success = await spend_points(
                db_session,
                user.id,
                1,
                "spent",
                "direct_message",
                f"Cost for sending direct message to user {receiver.id}"
            )
            if not success:
                await callback.answer("❌ خطا در کسر سکه.", show_alert=True)
            await state.clear()
            return
        
        # Create direct message
        dm = await create_direct_message(
            db_session,
            sender_id=user.id,
            receiver_id=receiver.id,
            message_text=message_text
        )
        
        # Notify receiver immediately
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
            
            await bot.send_message(
                receiver.telegram_id,
                f"✉️ یک پیام دایرکت از {get_display_name(user)} داری!\n\n"
                f"👤 نام: {get_display_name(user)}\n"
                f"⚧️ جنسیت: {gender_text}\n"
                f"🆔 ID: {user_profile_id}\n\n"
                f"برای مشاهده پیام از دکمه زیر استفاده کن:",
                reply_markup=get_dm_receive_keyboard(dm.id)
            )
            await bot.session.close()
        except Exception as e:
            # If bot can't send message (user blocked bot, etc.), still save the message
            pass
        
        # Check and award badges for DM achievements
        from core.achievement_system import AchievementSystem
        from core.badge_manager import BadgeManager
        from db.crud import get_user_dm_sent_count, get_badge_by_key
        from aiogram import Bot as BadgeBot
        
        # Get DM sent count
        dm_sent_count = await get_user_dm_sent_count(db_session, user.id)
        
        # Check DM achievements
        completed_achievements = await AchievementSystem.check_dm_count_achievement(
            user.id,
            dm_sent_count
        )
        
        # Award badges
        badge_bot = BadgeBot(token=settings.BOT_TOKEN)
        try:
            for achievement in completed_achievements:
                if achievement.achievement and achievement.achievement.badge_id:
                    badge = await get_badge_by_key(db_session, achievement.achievement.achievement_key)
                    if badge:
                        await BadgeManager.award_badge_and_notify(
                            user.id,
                            badge.badge_key,
                            badge_bot,
                            user.telegram_id
                        )
        except Exception:
            pass
        finally:
            await badge_bot.session.close()
        
        cost_text = "💎 این پیام رایگان بود (پریمیوم)" if user_premium else "💰 1 سکه از حساب شما کسر شد"
        
        await callback.message.edit_text(
            f"✅ پیام دایرکت با موفقیت ارسال شد!\n\n"
            f"{cost_text}\n\n"
            f"پیام شما برای {get_display_name(receiver)} ارسال شد.",
            reply_markup=None
        )
        await callback.answer("✅ پیام ارسال شد!")
        await state.clear()
        break


@router.callback_query(F.data == "dm:cancel")
async def cancel_dm_send(callback: CallbackQuery, state: FSMContext):
    """Cancel direct message sending."""
    await callback.message.edit_text(
        "❌ ارسال پیام دایرکت لغو شد.",
        reply_markup=None
    )
    await callback.answer("❌ ارسال لغو شد")
    await state.clear()


@router.callback_query(F.data.startswith("dm:view:"))
async def view_direct_message(callback: CallbackQuery):
    """View a direct message."""
    dm_id = int(callback.data.split(":")[-1])
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        dm = await get_direct_message_by_id(db_session, dm_id)
        if not dm:
            await callback.answer("❌ پیام یافت نشد.", show_alert=True)
            return
        
        # Check if user is receiver
        if dm.receiver_id != user.id:
            await callback.answer("❌ این پیام برای شما نیست.", show_alert=True)
            return
        
        # Mark as read
        await mark_direct_message_read(db_session, dm_id)
        
        # Get sender info
        sender = await get_user_by_id(db_session, dm.sender_id)
        if not sender:
            await callback.answer("❌ فرستنده یافت نشد.", show_alert=True)
            return
        
        # Generate profile_id if not exists
        from db.crud import update_user_profile
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
        
        # Get keyboard with delete and block options
        view_keyboard = get_dm_view_keyboard(dm_id, dm.sender_id)
        
        await callback.message.edit_text(
            f"✉️ پیام دایرکت\n\n"
            f"👤 از: {get_display_name(sender)}\n"
            f"⚧️ جنسیت: {gender_text}\n"
            f"🆔 ID: {sender_profile_id}\n"
            f"📅 تاریخ: {dm.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"📝 پیام:\n{dm.message_text}",
            reply_markup=view_keyboard
        )
        await callback.answer("✅ پیام مشاهده شد")
        break


@router.callback_query(F.data.startswith("dm:reject:"))
async def reject_direct_message_handler(callback: CallbackQuery):
    """Reject a direct message."""
    dm_id = int(callback.data.split(":")[-1])
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        dm = await get_direct_message_by_id(db_session, dm_id)
        if not dm:
            await callback.answer("❌ پیام یافت نشد.", show_alert=True)
            return
        
        # Check if user is receiver
        if dm.receiver_id != user.id:
            await callback.answer("❌ این پیام برای شما نیست.", show_alert=True)
            return
        
        # Reject message
        await reject_direct_message(db_session, dm_id)
        
        await callback.message.edit_text(
            "❌ پیام رد شد.",
            reply_markup=None
        )
        await callback.answer("❌ پیام رد شد")
        break


@router.callback_query(F.data.startswith("dm:delete:"))
async def delete_direct_message_handler(callback: CallbackQuery):
    """Delete a direct message."""
    dm_id = int(callback.data.split(":")[-1])
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        dm = await get_direct_message_by_id(db_session, dm_id)
        if not dm:
            await callback.answer("❌ پیام یافت نشد.", show_alert=True)
            return
        
        # Check if user is receiver
        if dm.receiver_id != user.id:
            await callback.answer("❌ این پیام برای شما نیست.", show_alert=True)
            return
        
        # Reject message (mark as rejected, which hides it from list)
        await reject_direct_message(db_session, dm_id)
        
        await callback.message.edit_text(
            "🗑️ پیام حذف شد.",
            reply_markup=None
        )
        await callback.answer("🗑️ پیام حذف شد")
        break


@router.callback_query(F.data.startswith("dm:block:"))
async def block_sender_from_dm_handler(callback: CallbackQuery):
    """Block the sender of a direct message."""
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
        
        # Block the sender
        success = await block_user(db_session, user.id, sender_id)
        
        if success:
            await callback.message.edit_text(
                f"🚫 {get_display_name(sender)} بلاک شد.\n\n"
                "این کاربر دیگر نمی‌تواند برای شما پیام دایرکت بفرستد.",
                reply_markup=None
            )
            await callback.answer(f"🚫 {get_display_name(sender)} بلاک شد")
        else:
            await callback.answer("❌ خطا در بلاک کردن.", show_alert=True)
        break


@router.callback_query(F.data.startswith("dm:reply_from_view:"))
async def reply_to_direct_message_from_view(callback: CallbackQuery, state: FSMContext):
    """Start replying to direct message from view page - set FSM state."""
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

