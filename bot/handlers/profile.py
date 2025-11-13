"""
Profile handlers for user profile interactions.
Handles like, follow, block, report, gift, and other profile actions.
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
    like_user,
    unlike_user,
    is_liked,
    follow_user,
    unfollow_user,
    is_following,
    block_user,
    unblock_user,
    is_blocked,
    create_report,
    is_chat_end_notification_active,
)
from bot.keyboards.profile import get_profile_keyboard
from bot.keyboards.reply import get_chat_reply_keyboard, get_main_reply_keyboard
from core.chat_manager import ChatManager
from config.settings import settings

router = Router()

chat_manager = None


def set_chat_manager(manager: ChatManager):
    """Set chat manager instance."""
    global chat_manager
    chat_manager = manager


@router.callback_query(F.data.startswith("profile:like:"))
async def handle_like(callback: CallbackQuery):
    """Handle like/unlike action."""
    import logging
    logger = logging.getLogger(__name__)
    
    partner_id = int(callback.data.split(":")[-1])
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        try:
            user = await get_user_by_telegram_id(db_session, user_id)
            if not user:
                await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
                return
            
            partner = await get_user_by_id(db_session, partner_id)
            if not partner:
                await callback.answer("❌ پروفایل یافت نشد.", show_alert=True)
                return
            
            # Check if already liked
            is_liked_status = await is_liked(db_session, user.id, partner.id)
            
            if is_liked_status:
                # Unlike
                success = await unlike_user(db_session, user.id, partner.id)
                if success:
                    logger.info(f"User {user.id} unliked user {partner.id}")
                    await callback.answer("❤️ لایک برداشته شد")
                else:
                    logger.warning(f"Failed to unlike: User {user.id} -> {partner.id}")
                    await callback.answer("❌ خطا در برداشتن لایک.", show_alert=True)
                    return
            else:
                # Like
                like_result = await like_user(db_session, user.id, partner.id)
                if like_result:
                    logger.info(f"User {user.id} liked user {partner.id}, like_id: {like_result.id}")
                    await callback.answer("❤️ لایک شد!")
                else:
                    logger.warning(f"Failed to like: User {user.id} -> {partner.id} (may already be liked)")
                    await callback.answer("❌ خطا در لایک کردن.", show_alert=True)
                    return
        
            # Check and award badges for like achievements
            from core.achievement_system import AchievementSystem
            from core.badge_manager import BadgeManager
            from db.crud import (
                get_user_follow_given_count,
                get_user_follow_received_count,
                get_badge_by_key
            )
            from aiogram import Bot as BadgeBot
            
            # Get like counts
            from sqlalchemy import func, select
            from db.models import Like, Follow
            
            # Count likes given by user
            like_given_result = await db_session.execute(
                select(func.count(Like.id)).where(Like.user_id == user.id)
            )
            like_given_count = like_given_result.scalar() or 0
            
            # Check like given achievements
            completed_achievements = await AchievementSystem.check_like_given_count_achievement(
                user.id,
                like_given_count
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
            
            # Check like received achievements for partner
            partner_like_count = partner.like_count or 0
            partner_completed = await AchievementSystem.check_like_count_achievement(
                partner.id,
                partner_like_count
            )
            
            badge_bot2 = BadgeBot(token=settings.BOT_TOKEN)
            try:
                for achievement in partner_completed:
                    if achievement.achievement and achievement.achievement.badge_id:
                        badge = await get_badge_by_key(db_session, achievement.achievement.achievement_key)
                        if badge:
                            await BadgeManager.award_badge_and_notify(
                                partner.id,
                                badge.badge_key,
                                badge_bot2,
                                partner.telegram_id
                            )
            except Exception:
                pass
            finally:
                await badge_bot2.session.close()
            
            # Refresh partner data
            await db_session.refresh(partner)
            
            # Update keyboard
            is_liked_status = await is_liked(db_session, user.id, partner.id)
            is_following_status = await is_following(db_session, user.id, partner.id)
            is_blocked_status = await is_blocked(db_session, user.id, partner.id)
            
            is_notifying_status = await is_chat_end_notification_active(db_session, user.id, partner.id)
            profile_keyboard = get_profile_keyboard(
                partner_id=partner.id,
                is_liked=is_liked_status,
                is_following=is_following_status,
                is_blocked=is_blocked_status,
                like_count=partner.like_count or 0,
                is_notifying=is_notifying_status
            )
            
            try:
                await callback.message.edit_reply_markup(reply_markup=profile_keyboard)
            except Exception as e:
                logger.error(f"Failed to update keyboard: {e}")
                pass
        except Exception as e:
            logger.error(f"Error in handle_like: {e}", exc_info=True)
            await callback.answer("❌ خطا در انجام عملیات لایک.", show_alert=True)
        
        break


@router.callback_query(F.data.startswith("profile:follow:"))
async def handle_follow(callback: CallbackQuery):
    """Handle follow/unfollow action."""
    import logging
    logger = logging.getLogger(__name__)
    
    partner_id = int(callback.data.split(":")[-1])
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        try:
            user = await get_user_by_telegram_id(db_session, user_id)
            if not user:
                await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
                return
            
            partner = await get_user_by_id(db_session, partner_id)
            if not partner:
                await callback.answer("❌ پروفایل یافت نشد.", show_alert=True)
                return
            
            # Check if already following
            is_following_status = await is_following(db_session, user.id, partner.id)
            
            if is_following_status:
                # Unfollow
                success = await unfollow_user(db_session, user.id, partner.id)
                if success:
                    logger.info(f"User {user.id} unfollowed user {partner.id}")
                    await callback.answer("🚶 دنبال کردن لغو شد")
                else:
                    logger.warning(f"Failed to unfollow: User {user.id} -> {partner.id}")
                    await callback.answer("❌ خطا در لغو دنبال کردن.", show_alert=True)
                    return
            else:
                # Follow
                follow_result = await follow_user(db_session, user.id, partner.id)
                if follow_result:
                    logger.info(f"User {user.id} followed user {partner.id}, follow_id: {follow_result.id}")
                    await callback.answer("✅ دنبال شد!")
                else:
                    logger.warning(f"Failed to follow: User {user.id} -> {partner.id} (may already be following)")
                    await callback.answer("❌ خطا در دنبال کردن.", show_alert=True)
                    return
            
            # Check and award badges for follow achievements
            from core.achievement_system import AchievementSystem
            from core.badge_manager import BadgeManager
            from db.crud import (
                get_user_follow_given_count,
                get_user_follow_received_count,
                get_badge_by_key
            )
            from aiogram import Bot as BadgeBot
            
            # Get follow counts
            follow_given_count = await get_user_follow_given_count(db_session, user.id)
            follow_received_count = await get_user_follow_received_count(db_session, partner.id)
            
            # Check follow achievements for user
            completed_achievements = await AchievementSystem.check_follow_count_achievement(
                user.id,
                follow_given_count,
                0  # User's received follows (not relevant here)
            )
            
            # Award badges for user
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
            
            # Check follow received achievements for partner
            partner_follow_given_count = await get_user_follow_given_count(db_session, partner.id)
            partner_completed = await AchievementSystem.check_follow_count_achievement(
                partner.id,
                partner_follow_given_count,
                follow_received_count
            )
            
            badge_bot2 = BadgeBot(token=settings.BOT_TOKEN)
            try:
                for achievement in partner_completed:
                    if achievement.achievement and achievement.achievement.badge_id:
                        badge = await get_badge_by_key(db_session, achievement.achievement.achievement_key)
                        if badge:
                            await BadgeManager.award_badge_and_notify(
                                partner.id,
                                badge.badge_key,
                                badge_bot2,
                                partner.telegram_id
                            )
            except Exception:
                pass
            finally:
                await badge_bot2.session.close()
            
            # Refresh keyboard
            is_liked_status = await is_liked(db_session, user.id, partner.id)
            is_following_status = await is_following(db_session, user.id, partner.id)
            is_blocked_status = await is_blocked(db_session, user.id, partner.id)
            
            is_notifying_status = await is_chat_end_notification_active(db_session, user.id, partner.id)
            profile_keyboard = get_profile_keyboard(
                partner_id=partner.id,
                is_liked=is_liked_status,
                is_following=is_following_status,
                is_blocked=is_blocked_status,
                like_count=partner.like_count or 0,
                is_notifying=is_notifying_status
            )
            
            try:
                await callback.message.edit_reply_markup(reply_markup=profile_keyboard)
            except Exception as e:
                logger.error(f"Failed to update keyboard: {e}")
                pass
        except Exception as e:
            logger.error(f"Error in handle_follow: {e}", exc_info=True)
            await callback.answer("❌ خطا در انجام عملیات فالو.", show_alert=True)
        
        break


@router.callback_query(F.data.startswith("profile:block:"))
async def handle_block(callback: CallbackQuery):
    """Handle block action."""
    partner_id = int(callback.data.split(":")[-1])
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        partner = await get_user_by_id(db_session, partner_id)
        if not partner:
            await callback.answer("❌ پروفایل یافت نشد.", show_alert=True)
            return
        
        if user.id == partner.id:
            await callback.answer("❌ نمی‌توانید خودتان را بلاک کنید.", show_alert=True)
            return
        
        # Block user
        await block_user(db_session, user.id, partner.id)
        
        # End active chat if exists
        if chat_manager:
            if await chat_manager.is_chat_active(user.id, db_session):
                from db.crud import get_active_chat_room_by_user
                chat_room = await get_active_chat_room_by_user(db_session, user.id)
                if chat_room:
                    await chat_manager.end_chat(chat_room.id, db_session)
        
        # Re-render profile keyboard with unblock option
        is_liked_status = await is_liked(db_session, user.id, partner.id)
        is_following_status = await is_following(db_session, user.id, partner.id)
        is_blocked_status = await is_blocked(db_session, user.id, partner.id)
        is_notifying_status = await is_chat_end_notification_active(db_session, user.id, partner.id)
        
        new_keyboard = get_profile_keyboard(
            partner_id=partner.id,
            is_liked=is_liked_status,
            is_following=is_following_status,
            is_blocked=is_blocked_status,
            like_count=partner.like_count or 0,
            is_notifying=is_notifying_status
        )
        
        try:
            await callback.message.edit_reply_markup(reply_markup=new_keyboard)
        except:
            pass
        
        await callback.answer("🚫 کاربر بلاک شد")
        break


@router.callback_query(F.data.startswith("profile:unblock:"))
async def handle_unblock(callback: CallbackQuery):
    """Handle unblock action."""
    partner_id = int(callback.data.split(":")[-1])
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        partner = await get_user_by_id(db_session, partner_id)
        if not partner:
            await callback.answer("❌ پروفایل یافت نشد.", show_alert=True)
            return
        
        if user.id == partner.id:
            await callback.answer("❌ نمی‌توانید خودتان را آنبلاک کنید.", show_alert=True)
            return
        
        success = await unblock_user(db_session, user.id, partner.id)
        
        if success:
            # Re-render profile keyboard
            is_liked_status = await is_liked(db_session, user.id, partner.id)
            is_following_status = await is_following(db_session, user.id, partner.id)
            is_blocked_status = await is_blocked(db_session, user.id, partner.id)
            is_notifying_status = await is_chat_end_notification_active(db_session, user.id, partner.id)
            
            new_keyboard = get_profile_keyboard(
                partner_id=partner.id,
                is_liked=is_liked_status,
                is_following=is_following_status,
                is_blocked=is_blocked_status,
                like_count=partner.like_count or 0,
                is_notifying=is_notifying_status
            )
            
            try:
                await callback.message.edit_reply_markup(reply_markup=new_keyboard)
            except:
                pass
            
            await callback.answer("✅ آنبلاک شد.")
        else:
            await callback.answer("❌ خطا در آنبلاک کردن.", show_alert=True)
        break


@router.callback_query(F.data.startswith("profile:report:"))
async def handle_report(callback: CallbackQuery, state: FSMContext):
    """Handle report action."""
    partner_id = int(callback.data.split(":")[-1])
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        partner = await get_user_by_id(db_session, partner_id)
        if not partner:
            await callback.answer("❌ پروفایل یافت نشد.", show_alert=True)
            return
        
        # For now, just create a simple report
        # TODO: Add report types selection
        await create_report(
            db_session,
            reporter_id=user.id,
            reported_id=partner.id,
            reason="گزارش از طریق پروفایل",
            report_type="other"
        )
        
        await callback.answer("⛔ گزارش ثبت شد. از توجه شما سپاسگزاریم.", show_alert=True)
        
        break


@router.callback_query(F.data.startswith("profile:gift:"))
async def handle_gift(callback: CallbackQuery):
    """Handle gift action."""
    partner_id = int(callback.data.split(":")[-1])
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        partner = await get_user_by_id(db_session, partner_id)
        if not partner:
            await callback.answer("❌ پروفایل یافت نشد.", show_alert=True)
            return
        
        # TODO: Implement gift system
        await callback.answer("🎁 این قابلیت به زودی پیاده‌سازی خواهد شد.", show_alert=True)
        
        break


@router.callback_query(F.data.startswith("profile:dm:"))
async def handle_dm(callback: CallbackQuery, state: FSMContext):
    """Handle direct message action - start FSM for message."""
    partner_id = int(callback.data.split(":")[-1])
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        from db.crud import is_blocked
        
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        partner = await get_user_by_id(db_session, partner_id)
        if not partner:
            await callback.answer("❌ پروفایل یافت نشد.", show_alert=True)
            return
        
        # Check if partner has blocked user
        partner_blocked_user = await is_blocked(db_session, partner.id, user.id)
        if partner_blocked_user:
            await callback.answer("❌ این کاربر شما را بلاک کرده است. امکان ارسال پیام دایرکت ندارید.", show_alert=True)
            return
        
        # Set FSM state to wait for message
        await state.update_data(dm_receiver_id=partner.id)
        await state.set_state("dm:waiting_message")
        
        await callback.message.answer(
            "✉️ پیام دایرکت\n\n"
            "لطفاً متن پیامی که می‌خواهید ارسال کنید را بنویسید:"
        )
        await callback.answer()
        break


@router.callback_query(F.data.startswith("profile:chat_request:"))
async def handle_chat_request(callback: CallbackQuery, state: FSMContext):
    """Handle chat request action - start FSM for request message."""
    partner_id = int(callback.data.split(":")[-1])
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        from db.crud import is_blocked
        
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        partner = await get_user_by_id(db_session, partner_id)
        if not partner:
            await callback.answer("❌ پروفایل یافت نشد.", show_alert=True)
            return
        
        # Check if partner has blocked user
        partner_blocked_user = await is_blocked(db_session, partner.id, user.id)
        if partner_blocked_user:
            await callback.answer("❌ این کاربر شما را بلاک کرده است. امکان ارسال درخواست چت ندارید.", show_alert=True)
            return
        
        # Check if user already has an active chat
        if chat_manager:
            from db.crud import get_active_chat_room_by_user
            active_chat = await get_active_chat_room_by_user(db_session, user.id)
            if active_chat:
                await callback.answer("❌ شما در حال حاضر در یک چت فعال هستید. لطفاً ابتدا چت فعلی را پایان دهید.", show_alert=True)
                return
        
        # Check if user has a pending chat request to this partner
        from bot.handlers.chat_request import has_pending_chat_request
        if await has_pending_chat_request(user.id, partner.id):
            await callback.answer("⏳  شما یک درخواست چت برای این کاربر ارسال کرده‌اید. لطفاً منتظر پاسخ بمانید...", show_alert=True)
            return
        
        # Set FSM state to wait for request message
        await state.update_data(chat_request_receiver_id=partner.id)
        await state.set_state("chat_request:waiting_message")
        
        await callback.message.answer(
            "💬 درخواست چت\n\n"
            "لطفاً پیامی که می‌خواهید همراه درخواست چت ارسال کنید را بنویسید:"
        )
        await callback.answer()
        break


@router.callback_query(F.data.startswith("profile:notify_end:"))
async def handle_notify_end(callback: CallbackQuery):
    """Handle notify when chat ends action - toggle notification."""
    partner_id = int(callback.data.split(":")[-1])
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        from db.crud import (
            create_chat_end_notification,
            delete_chat_end_notification,
            is_chat_end_notification_active,
        )
        
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        partner = await get_user_by_id(db_session, partner_id)
        if not partner:
            await callback.answer("❌ پروفایل یافت نشد.", show_alert=True)
            return
        
        if user.id == partner.id:
            await callback.answer("❌ نمی‌توانید برای خودتان تنظیم کنید.", show_alert=True)
            return
        
        # Check if notification is already active
        is_active = await is_chat_end_notification_active(db_session, user.id, partner.id)
        
        if is_active:
            # Deactivate notification
            success = await delete_chat_end_notification(db_session, user.id, partner.id)
            if success:
                await callback.answer("🔕 اطلاع‌رسانی غیرفعال شد.", show_alert=True)
            else:
                await callback.answer("❌ خطا در غیرفعال کردن اطلاع‌رسانی.", show_alert=True)
        else:
            # Activate notification
            notification = await create_chat_end_notification(db_session, user.id, partner.id)
            if notification:
                await callback.answer("🔔 وقتی چت این کاربر تمام شد به شما اطلاع داده می‌شود.", show_alert=True)
            else:
                await callback.answer("❌ خطا در فعال کردن اطلاع‌رسانی.", show_alert=True)
        
        # Update keyboard to reflect notification status
        is_liked_status = await is_liked(db_session, user.id, partner.id)
        is_following_status = await is_following(db_session, user.id, partner.id)
        is_blocked_status = await is_blocked(db_session, user.id, partner.id)
        is_notifying_status = await is_chat_end_notification_active(db_session, user.id, partner.id)
        
        profile_keyboard = get_profile_keyboard(
            partner_id=partner.id,
            is_liked=is_liked_status,
            is_following=is_following_status,
            is_blocked=is_blocked_status,
            like_count=partner.like_count or 0,
            is_notifying=is_notifying_status
        )
        
        try:
            await callback.message.edit_reply_markup(reply_markup=profile_keyboard)
        except:
            pass
        
        break

