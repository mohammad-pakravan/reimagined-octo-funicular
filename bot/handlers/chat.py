"""
Chat handler for the bot.
Handles starting chat, ending chat, and video call requests.
"""
import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter

from db.database import get_db
from db.crud import get_user_by_telegram_id, get_user_by_id, check_user_premium
from core.matchmaking import MatchmakingQueue
from core.chat_manager import ChatManager
from bot.keyboards.common import (
    get_chat_keyboard,
    get_confirm_keyboard,
    get_main_menu_keyboard,
    get_preferred_gender_keyboard
)
from bot.keyboards.reply import get_main_reply_keyboard, get_chat_reply_keyboard
from config.settings import settings

router = Router()


class ChatStates(StatesGroup):
    """FSM states for chat."""
    waiting_preferred_gender = State()


# Export ChatStates for use in other modules
__all__ = ['ChatStates', 'set_matchmaking_queue', 'set_chat_manager']

# Global instances (should be injected properly)
matchmaking_queue = None
chat_manager = None


def set_matchmaking_queue(queue: MatchmakingQueue):
    """Set matchmaking queue instance."""
    global matchmaking_queue
    matchmaking_queue = queue


def set_chat_manager(manager: ChatManager):
    """Set chat manager instance."""
    global chat_manager
    chat_manager = manager


@router.callback_query(F.data.startswith("pref_gender:"))
async def process_chat_gender_preference(callback: CallbackQuery, state: FSMContext):
    """Process preferred gender selection for chat."""
    if not matchmaking_queue or not chat_manager:
        await callback.answer("❌ خطای سیستم. لطفاً دوباره تلاش کنید.", show_alert=True)
        return
    
    preferred_gender = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    # Log for debugging
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"DEBUG: User {user_id} selected preferred_gender: {preferred_gender}")
    
    # Convert "all" to None
    if preferred_gender == "all":
        preferred_gender = None
        logger.info(f"DEBUG: User {user_id} preferred_gender converted to None (all selected)")
    else:
        logger.info(f"DEBUG: User {user_id} preferred_gender kept as: {preferred_gender}")
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        
        if not user or not user.gender or not user.age or not user.city:
            await callback.answer(
                "❌ لطفاً ابتدا پروفایل خودت را کامل کن. /start را بزنید.",
                show_alert=True
            )
            return
        
        # Check if user already has active chat
        if await chat_manager.is_chat_active(user.id, db_session):
            await callback.answer("❌ شما در حال حاضر یک چت فعال دارید!", show_alert=True)
            await state.clear()
            return
        
        # Check if user is already in queue
        if await matchmaking_queue.is_user_in_queue(user_id):
            await callback.answer("⏳ شما در صف هستید. لطفاً صبر کنید...", show_alert=True)
            return
        
        await callback.answer()
        
        # Add user to queue with preferred gender (no filters)
        logger.info(f"DEBUG: User {user_id} adding to queue with preferred_gender: {preferred_gender}")
        await matchmaking_queue.add_user_to_queue(
            user_id=user_id,
            gender=user.gender,
            city=user.city,
            age=user.age,
            preferred_gender=preferred_gender,
            min_age=None,
            max_age=None,
            preferred_city=None,
        )
        logger.info(f"DEBUG: User {user_id} added to queue successfully")
        
        queue_count = await matchmaking_queue.get_total_queue_count()
        gender_counts = await matchmaking_queue.get_queue_count_by_gender()
        
        # Check if user has premium
        from db.crud import check_user_premium
        user_premium = await check_user_premium(db_session, user.id)
        
        from bot.keyboards.common import get_queue_status_keyboard
        
        # Get chat cost from system settings
        from db.crud import get_system_setting_value
        from core.points_manager import PointsManager
        from db.crud import get_user_points
        
        chat_cost_str = await get_system_setting_value(db_session, 'chat_message_cost', '3')
        try:
            chat_cost = int(chat_cost_str)
        except (ValueError, TypeError):
            chat_cost = 3
        
        # Get required message count from system settings
        required_message_count_str = await get_system_setting_value(db_session, 'chat_success_message_count', '2')
        try:
            required_message_count = int(required_message_count_str)
        except (ValueError, TypeError):
            required_message_count = 2
        
        user_points = await get_user_points(db_session, user.id)
        
        # Prepare queue status message with beautiful UI
        queue_status_text = (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🔍 در حال جستجو...\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👥 وضعیت صف:\n"
            f"• 👨 پسر: {gender_counts.get('male', 0)} نفر\n"
            f"• 👩 دختر: {gender_counts.get('female', 0)} نفر\n\n"
        )
        
        # Add cost information
        if user_premium:
            queue_status_text += (
                "💎 وضعیت: پریمیوم\n"
                "💰 هزینه چت: رایگان\n\n"
            )
        elif preferred_gender is None:
            queue_status_text += (
                "🌐 انتخاب: همه\n"
                "💰 هزینه چت: رایگان\n"
                "💡 چون «همه» رو انتخاب کردی، هیچ سکه‌ای کسر نمی‌شه.\n\n"
            )
        else:
            queue_status_text += (
                f"💰 هزینه چت: {chat_cost} سکه\n"
                f"💎 سکه‌های فعلی تو: {user_points}\n\n"
            )
            
            if user_points < chat_cost:
                queue_status_text += (
                    f"⚠️ سکه کافی نداری!\n"
                    f"برای شروع چت به {chat_cost} سکه نیاز داری.\n\n"
                    f"💎 با خرید پریمیوم:\n"
                    f"• هزینه چت: رایگان\n"
                    f"• نفر اول صف\n"
                    f"• امکانات بیشتر\n\n"
                )
            else:
                queue_status_text += (
                    f"💡 نکته: وقتی هم‌چت پیدا بشه، {chat_cost} سکه ازت کسر می‌شه.\n"
                    f"اگر چت موفقیت‌آمیز باشه (هر دو طرف حداقل {required_message_count} پیام بفرستن)، این سکه کسر می‌مونه.\n"
                    f"در غیر این صورت، سکه‌ها بهت برمی‌گرده.\n\n"
                    f"💎 با خرید پریمیوم:\n"
                    f"• هزینه چت: رایگان\n"
                    f"• نفر اول صف\n"
                    f"• امکانات بیشتر\n\n"
            )
        
        queue_status_text += "⏳ لطفاً صبر کنید، در حال پیدا کردن کسی برای شما هستیم..."
        
        await callback.message.edit_text(
            queue_status_text,
            reply_markup=get_queue_status_keyboard(user_premium)
        )
        
        await state.clear()
        
        # Don't call try_find_match here - let the worker handle matching
        # This prevents duplicate messages
        # The worker will handle matching in the background
        break


@router.callback_query(F.data == "chat:start_search")
async def start_search(callback: CallbackQuery, state: FSMContext):
    """Start searching for a chat partner (legacy handler)."""
    # This is now handled by reply handler, but keep for compatibility
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        
        if not user or not user.gender or not user.age or not user.city:
            await callback.answer(
                "❌ لطفاً ابتدا پروفایل خودت را کامل کن. /start را بزنید.",
                show_alert=True
            )
            return
        
        # Ask for preferred gender
        await callback.message.edit_text(
            "💬 شروع چت ناشناس\n\n"
            "به دنبال چه جنسیتی هستی؟",
            reply_markup=get_preferred_gender_keyboard()
        )
        
        await state.set_state(ChatStates.waiting_preferred_gender)
        break


async def try_find_match(telegram_id: int, db_session):
    """Try to find a match for user immediately (worker will handle matching)."""
    # Just wait a bit and let the worker handle matching
    # The worker runs continuously and will match users
    # This function is kept for immediate match attempt, but worker is primary
    await asyncio.sleep(1)
    
    user = await get_user_by_telegram_id(db_session, telegram_id)
    if not user:
        return
    
    # Try immediate match (optional - worker will handle if this fails)
    if matchmaking_queue:
        match_telegram_id = await matchmaking_queue.find_match(telegram_id)
        
        if match_telegram_id:
            # Match found immediately!
            matched_user = await get_user_by_telegram_id(db_session, match_telegram_id)
            if matched_user:
                # Check if neither user has active chat
                if not await chat_manager.is_chat_active(user.id, db_session) and \
                   not await chat_manager.is_chat_active(matched_user.id, db_session):
                    # Get preferred genders from queue data
                    user_data = await matchmaking_queue.get_user_data(telegram_id)
                    matched_user_data = await matchmaking_queue.get_user_data(match_telegram_id)
                    
                    # Get raw values
                    user_pref_gender_raw = user_data.get("preferred_gender") if user_data else None
                    matched_user_pref_gender_raw = matched_user_data.get("preferred_gender") if matched_user_data else None
                    
                    # Normalize: convert "all" or None to None, keep "male" and "female" as is
                    # IMPORTANT: If raw value is "male" or "female", keep it as is!
                    if user_pref_gender_raw is None:
                        user_pref_gender = None
                    elif user_pref_gender_raw == "all":
                        user_pref_gender = None
                    elif user_pref_gender_raw in ["male", "female"]:
                        user_pref_gender = user_pref_gender_raw
                    else:
                        # Unknown value, treat as None
                        user_pref_gender = None
                    
                    if matched_user_pref_gender_raw is None:
                        matched_user_pref_gender = None
                    elif matched_user_pref_gender_raw == "all":
                        matched_user_pref_gender = None
                    elif matched_user_pref_gender_raw in ["male", "female"]:
                        matched_user_pref_gender = matched_user_pref_gender_raw
                    else:
                        # Unknown value, treat as None
                        matched_user_pref_gender = None
                    
                    # Create chat room with preferred genders
                    chat_room = await chat_manager.create_chat(
                        user.id, 
                        matched_user.id, 
                        db_session,
                        user1_preferred_gender=user_pref_gender,
                        user2_preferred_gender=matched_user_pref_gender
                    )
                    
                    # Notify both users and deduct coins if needed
                    from aiogram import Bot
                    from db.crud import check_user_premium, spend_points, get_user_points
                    from core.points_manager import PointsManager
                    from db.crud import get_system_setting_value
                    
                    # Check premium status
                    user_premium = await check_user_premium(db_session, user.id)
                    matched_user_premium = await check_user_premium(db_session, matched_user.id)
                    
                    # Get chat cost from system settings
                    chat_cost_str = await get_system_setting_value(db_session, 'chat_message_cost', '3')
                    try:
                        chat_cost = int(chat_cost_str)
                    except (ValueError, TypeError):
                        chat_cost = 3
                    
                    # Get user points
                    user_points = await get_user_points(db_session, user.id)
                    matched_user_points = await get_user_points(db_session, matched_user.id)
                    
                    # Deduct coins for non-premium users
                    # Simple logic: if preferred_gender is "male" or "female", deduct coins
                    # If preferred_gender is None (meaning "all"), don't deduct coins
                    user_coins_deducted = False
                    matched_user_coins_deducted = False
                    
                    # Check if user selected specific gender (not "all")
                    if not user_premium and user_pref_gender is not None and user_pref_gender in ["male", "female"]:
                        # Check if user has enough coins
                        if user_points >= chat_cost:
                            success = await spend_points(
                                db_session,
                                user.id,
                                chat_cost,
                                "spent",
                                "chat_start",
                                f"Cost for starting chat (will be refunded if chat unsuccessful)"
                            )
                            if success:
                                user_coins_deducted = True
                                await chat_manager.set_chat_cost_deducted(chat_room.id, user.id, True)
                                user_points -= chat_cost
                    
                    # Check if matched_user selected specific gender (not "all")
                    if not matched_user_premium and matched_user_pref_gender is not None and matched_user_pref_gender in ["male", "female"]:
                        # Check if user has enough coins
                        if matched_user_points >= chat_cost:
                            success = await spend_points(
                                db_session,
                                matched_user.id,
                                chat_cost,
                                "spent",
                                "chat_start",
                                f"Cost for starting chat (will be refunded if chat unsuccessful)"
                            )
                            if success:
                                matched_user_coins_deducted = True
                                await chat_manager.set_chat_cost_deducted(chat_room.id, matched_user.id, True)
                                matched_user_points -= chat_cost
                    
                    # Prepare messages with beautiful UI
                    user_msg = (
                        "━━━━━━━━━━━━━━━━━━━━\n"
                        "✅ هم‌چت پیدا شد!\n"
                        "━━━━━━━━━━━━━━━━━━━━\n\n"
                        "🎉 شما الان به هم متصل شدید!\n"
                        "💬 می‌تونید شروع به چت کنید.\n\n"
                    )
                    
                    matched_user_msg = (
                        "━━━━━━━━━━━━━━━━━━━━\n"
                        "✅ هم‌چت پیدا شد!\n"
                        "━━━━━━━━━━━━━━━━━━━━\n\n"
                        "🎉 شما الان به هم متصل شدید!\n"
                        "💬 می‌تونید شروع به چت کنید.\n\n"
                    )
                    
                    # Add cost information
                    if user_premium:
                        user_msg += (
                            "💎 وضعیت: پریمیوم\n"
                            "💰 هزینه این چت: رایگان\n\n"
                        )
                    elif user_pref_gender is None:
                        # "all" was selected - no coins deducted
                        user_msg += (
                            "💰 هزینه این چت: رایگان\n"
                            "🌐 چون «همه» رو انتخاب کردی، هیچ سکه‌ای کسر نمی‌شه.\n\n"
                        )
                    elif user_coins_deducted:
                        # Specific gender selected and coins were deducted
                        user_msg += (
                            f"💰 هزینه این چت: {chat_cost} سکه\n"
                            f"💎 سکه‌های باقی‌مانده: {user_points}\n\n"
                            f"💡 نکته: اگر چت موفقیت‌آمیز باشه (هر دو طرف حداقل 2 پیام بفرستن)، این سکه کسر می‌مونه.\n"
                            f"در غیر این صورت، سکه‌ها بهت برمی‌گرده.\n\n"
                            f"💎 با خرید پریمیوم:\n"
                            f"• هزینه چت: رایگان\n"
                            f"• نفر اول صف\n"
                            f"• امکانات بیشتر\n\n"
                        )
                    else:
                        # Specific gender selected but coins weren't deducted (probably didn't have enough coins)
                        user_msg += (
                            f"⚠️ سکه کافی نداشتی!\n"
                            f"💰 برای شروع چت به {chat_cost} سکه نیاز داری.\n"
                            f"💎 سکه فعلی تو: {user_points}\n\n"
                            f"💡 می‌تونی سکه‌هات رو به پریمیوم تبدیل کنی!\n\n"
                            f"💎 با خرید پریمیوم:\n"
                            f"• هزینه چت: رایگان\n"
                            f"• نفر اول صف\n"
                            f"• امکانات بیشتر\n\n"
                        )
                    
                    if matched_user_premium:
                        matched_user_msg += (
                            "💎 وضعیت: پریمیوم\n"
                            "💰 هزینه این چت: رایگان\n\n"
                        )
                    elif matched_user_pref_gender is None:
                        # "all" was selected - no coins deducted
                        matched_user_msg += (
                            "💰 هزینه این چت: رایگان\n"
                            "🌐 چون «همه» رو انتخاب کردی، هیچ سکه‌ای کسر نمی‌شه.\n\n"
                        )
                    elif matched_user_coins_deducted:
                        # Specific gender selected and coins were deducted
                        matched_user_msg += (
                            f"💰 هزینه این چت: {chat_cost} سکه\n"
                            f"💎 سکه‌های باقی‌مانده: {matched_user_points}\n\n"
                            f"💡 نکته: اگر چت موفقیت‌آمیز باشه (هر دو طرف حداقل 2 پیام بفرستن)، این سکه کسر می‌مونه.\n"
                            f"در غیر این صورت، سکه‌ها بهت برمی‌گرده.\n\n"
                        )
                    else:
                        # Specific gender selected but coins weren't deducted (probably didn't have enough coins)
                        matched_user_msg += (
                            f"⚠️ سکه کافی نداشتی!\n"
                            f"💰 برای شروع چت به {chat_cost} سکه نیاز داری.\n"
                            f"💎 سکه فعلی تو: {matched_user_points}\n\n"
                            f"💡 می‌تونی سکه‌هات رو به پریمیوم تبدیل کنی!\n\n"
                        )
                    
                    user_msg += "━━━━━━━━━━━━━━━━━━━━"
                    matched_user_msg += "━━━━━━━━━━━━━━━━━━━━"
                    
                    bot = Bot(token=settings.BOT_TOKEN)
                    
                    await bot.send_message(
                        user.telegram_id,
                        user_msg,
                        reply_markup=get_chat_reply_keyboard()
                    )
                    
                    await bot.send_message(
                        matched_user.telegram_id,
                        matched_user_msg,
                        reply_markup=get_chat_reply_keyboard()
                    )
                    
                    await bot.session.close()
                    
                    # Remove users from queue after sending messages
                    await matchmaking_queue.remove_user_from_queue(telegram_id)
                    await matchmaking_queue.remove_user_from_queue(match_telegram_id)
                    
                    # IMPORTANT: Don't let worker connect these users again
                    # Mark them as processed so worker skips them
                    return  # Match found
    
    # If no immediate match, user stays in queue
    # Worker will handle matching in background


@router.callback_query(F.data == "chat:end")
async def end_chat_request(callback: CallbackQuery):
    """Request to end chat."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Check if user has active chat
        if not await chat_manager.is_chat_active(user.id, db_session):
            await callback.answer("❌ شما در حال حاضر یک چت فعال ندارید!", show_alert=True)
            return
        
        try:
            await callback.message.edit_text(
                "❓ آیا مطمئن هستید که می‌خواهید این چت را تمام کنید؟",
                reply_markup=get_confirm_keyboard("end_chat")
            )
        except:
            # If edit fails, send new message
            await callback.message.answer(
                "❓ آیا مطمئن هستید که می‌خواهید این چت را تمام کنید؟",
                reply_markup=get_confirm_keyboard("end_chat")
            )
        
        await callback.answer()
        break


@router.callback_query(F.data == "end_chat:confirm")
async def end_chat_confirm(callback: CallbackQuery):
    """Confirm ending chat."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Get active chat room
        from db.crud import get_active_chat_room_by_user, get_user_by_id
        chat_room = await get_active_chat_room_by_user(db_session, user.id)
        
        if chat_room:
            # Get partner before ending chat
            partner_id = await chat_manager.get_partner_id(user.id, db_session)
            
            # Get partner object before ending chat (for notifications)
            partner = None
            if partner_id:
                partner = await get_user_by_id(db_session, partner_id)
            
            # Get message IDs before ending chat (for deletion)
            user1_message_ids = await chat_manager.get_message_ids(chat_room.id, chat_room.user1_id)
            user2_message_ids = await chat_manager.get_message_ids(chat_room.id, chat_room.user2_id)
            
            # Get user Telegram IDs for message deletion
            user1_telegram_id = user.telegram_id
            user2_telegram_id = None
            if partner:
                user2_telegram_id = partner.telegram_id
            
            # End chat room and get message counts
            end_result = await chat_manager.end_chat(chat_room.id, db_session)
            if isinstance(end_result, tuple):
                success, message_counts = end_result
            else:
                success = end_result
                message_counts = (0, 0)
            
            # Get message counts for both users
            user1_count, user2_count = message_counts
            
            # Determine which user is which
            if chat_room.user1_id == user.id:
                current_user_count = user1_count
                partner_user_count = user2_count
            else:
                current_user_count = user2_count
                partner_user_count = user1_count
            
            # Check if any messages were sent
            total_messages = current_user_count + partner_user_count
            
            # Note: We will send summary to both users below, so no need to send "chat ended" message here
            
            # Notify all users who requested notification for this user's chat end
            if partner:
                from db.crud import get_chat_end_notifications_for_user
                from aiogram import Bot as NotifyBot
                
                notifications = await get_chat_end_notifications_for_user(db_session, partner.id)
                
                if notifications:
                    notify_bot = NotifyBot(token=settings.BOT_TOKEN)
                    try:
                        for notification in notifications:
                            watcher = await get_user_by_id(db_session, notification.watcher_id)
                            if watcher:
                                try:
                                    gender_map = {"male": "پسر 🧑", "female": "دختر 👩", "other": "سایر"}
                                    gender_text = gender_map.get(partner.gender, partner.gender or "تعیین نشده")
                                    
                                    # Generate profile_id if not exists
                                    if not partner.profile_id:
                                        import hashlib
                                        profile_id = hashlib.md5(f"user_{partner.telegram_id}".encode()).hexdigest()[:12]
                                        partner.profile_id = profile_id
                                        await db_session.commit()
                                        await db_session.refresh(partner)
                                    
                                    partner_profile_id = f"/user_{partner.profile_id}"
                                    
                                    notify_msg = f"🔔 چت {partner.username or 'کاربر'} تمام شد!\n\n"
                                    notify_msg += f"👤 نام: {partner.username or 'نامشخص'}\n"
                                    notify_msg += f"⚧️ جنسیت: {gender_text}\n"
                                    
                                    if partner.age:
                                        notify_msg += f"🎂 سن: {partner.age}\n"
                                    if partner.city:
                                        notify_msg += f"🏙️ شهر: {partner.city}\n"
                                    
                                    notify_msg += f"🆔 ID: {partner_profile_id}\n\n"
                                    notify_msg += "اکنون می‌توانید با این کاربر درخواست چت بفرستید."
                                    
                                    # Send notification with photo if available
                                    if partner.profile_image_url:
                                        try:
                                            await notify_bot.send_photo(
                                                watcher.telegram_id,
                                                photo=partner.profile_image_url,
                                                caption=notify_msg
                                            )
                                        except Exception:
                                            await notify_bot.send_message(
                                                watcher.telegram_id,
                                                notify_msg
                                            )
                                    else:
                                        await notify_bot.send_message(
                                            watcher.telegram_id,
                                            notify_msg
                                        )
                                except Exception:
                                    # Continue with other notifications even if one fails
                                    pass
                        
                        await notify_bot.session.close()
                    except Exception:
                        pass
            
            # Get required message count from system settings
            from db.crud import get_system_setting_value
            required_message_count_str = await get_system_setting_value(db_session, 'chat_success_message_count', '2')
            try:
                required_message_count = int(required_message_count_str)
            except (ValueError, TypeError):
                required_message_count = 2
            
            # Check if chat was successful (both users sent at least required_message_count messages)
            chat_successful = current_user_count >= required_message_count and partner_user_count >= required_message_count
            
            # Check if coins were deducted and need refund for both users
            from db.crud import check_user_premium, get_user_points, add_points, get_system_setting_value
            from core.points_manager import PointsManager
            from aiogram import Bot
            
            user_premium = await check_user_premium(db_session, user.id)
            partner_premium = await check_user_premium(db_session, partner_id) if partner_id else False
            
            # Get preferred genders to check if "all" was selected
            user_pref_gender = await chat_manager.get_user_preferred_gender(chat_room.id, user.id)
            partner_pref_gender = await chat_manager.get_user_preferred_gender(chat_room.id, partner_id) if partner_id else None
            
            # Check if coins were deducted for both users
            user_was_cost_deducted = await chat_manager.was_chat_cost_deducted(chat_room.id, user.id)
            partner_was_cost_deducted = await chat_manager.was_chat_cost_deducted(chat_room.id, partner_id) if partner_id else False
            
            # Get chat cost
            chat_cost_str = await get_system_setting_value(db_session, 'chat_message_cost', '3')
            try:
                chat_cost = int(chat_cost_str)
            except (ValueError, TypeError):
                chat_cost = 3
            
            # Refund coins if chat was not successful and coins were deducted
            user_coins_refunded = False
            partner_coins_refunded = False
            
            if not user_premium and user_was_cost_deducted and not chat_successful:
                # Refund coins for user
                success = await add_points(
                    db_session,
                    user.id,
                    chat_cost,
                    "earned",
                    "chat_refund",
                    f"Refund for unsuccessful chat (less than 2 messages from each user)"
                )
                if success:
                    user_coins_refunded = True
            
            if partner_id and not partner_premium and partner_was_cost_deducted and not chat_successful:
                # Refund coins for partner
                success = await add_points(
                    db_session,
                    partner_id,
                    chat_cost,
                    "earned",
                    "chat_refund",
                    f"Refund for unsuccessful chat (less than 2 messages from each user)"
                )
                if success:
                    partner_coins_refunded = True
            
            # Get current points after refund
            user_current_points = await get_user_points(db_session, user.id)
            partner_current_points = await get_user_points(db_session, partner_id) if partner_id else 0
            
            # Prepare end message for user with beautiful UI
            user_end_message = (
                "━━━━━━━━━━━━━━━━━━━━\n"
                "✅ چت به پایان رسید\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
            )
            
            if total_messages == 0:
                user_end_message += (
                    "💬 هیچ پیامی در این چت ارسال نشد.\n\n"
                )
            else:
                user_end_message += (
                    f"📊 آمار چت:\n"
                    f"• پیام‌های شما: {current_user_count}\n"
                    f"• پیام‌های هم‌چت: {partner_user_count}\n"
                    f"• مجموع پیام‌ها: {total_messages}\n\n"
                )
            
            # Add cost information for user
            # Simple logic: check premium first, then check if coins were deducted, then check preferred_gender
            if user_premium:
                user_end_message += (
                    "💎 وضعیت: پریمیوم\n"
                    "💰 هزینه این چت: رایگان\n\n"
                )
            elif user_was_cost_deducted:
                # Coins were deducted (user selected specific gender and had enough coins)
                if chat_successful:
                    user_end_message += (
                        f"✅ چت موفقیت‌آمیز بود!\n"
                        f"💰 هزینه این چت: {chat_cost} سکه (کسر شده)\n"
                        f"💎 سکه‌های باقی‌مانده: {user_current_points}\n\n"
                        f"💎 با خرید پریمیوم:\n"
                        f"• هزینه چت: رایگان\n"
                        f"• نفر اول صف\n"
                        f"• امکانات بیشتر\n\n"
                    )
                else:
                    if user_coins_refunded:
                        # Get required message count from system settings
                        required_message_count_str = await get_system_setting_value(db_session, 'chat_success_message_count', '2')
                        try:
                            required_message_count = int(required_message_count_str)
                        except (ValueError, TypeError):
                            required_message_count = 2
                        
                        user_end_message += (
                            f"⚠️ چت موفقیت‌آمیز نبود.\n"
                            f"💰 {chat_cost} سکه به حساب شما برگشت داده شد.\n"
                            f"💎 سکه‌های فعلی: {user_current_points}\n\n"
                            f"💡 نکته: برای کسر سکه، هر دو طرف باید حداقل {required_message_count} پیام بفرستن.\n\n"
                        )
                    else:
                        user_end_message += (
                            f"⚠️ چت موفقیت‌آمیز نبود.\n"
                            f"💰 تلاش برای بازگشت سکه انجام شد.\n"
                            f"💎 سکه‌های فعلی: {user_current_points}\n\n"
                        )
            elif user_pref_gender is None:
                # "all" was selected - no coins deducted
                user_end_message += (
                    "💰 هزینه این چت: رایگان\n"
                    "🌐 چون «همه» رو انتخاب کردی، هیچ سکه‌ای کسر نشد.\n\n"
                )
            else:
                # User selected specific gender but coins weren't deducted (probably didn't have enough coins)
                user_end_message += (
                    "💰 هزینه این چت: رایگان\n"
                    "💡 هیچ سکه‌ای کسر نشد.\n\n"
                )
            
            user_end_message += "━━━━━━━━━━━━━━━━━━━━\n"
            user_end_message += "بازگشت به منوی اصلی..."
            
            # Prepare end message for partner
            partner_end_message = (
                "━━━━━━━━━━━━━━━━━━━━\n"
                "✅ چت به پایان رسید\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
            )
            
            if total_messages == 0:
                partner_end_message += (
                    "💬 هیچ پیامی در این چت ارسال نشد.\n\n"
                )
            else:
                partner_end_message += (
                    f"📊 آمار چت:\n"
                    f"• پیام‌های شما: {partner_user_count}\n"
                    f"• پیام‌های هم‌چت: {current_user_count}\n"
                    f"• مجموع پیام‌ها: {total_messages}\n\n"
                )
            
            # Add cost information for partner
            # Simple logic: check premium first, then check if coins were deducted, then check preferred_gender
            if partner_id:
                if partner_premium:
                    partner_end_message += (
                        "💎 وضعیت: پریمیوم\n"
                        "💰 هزینه این چت: رایگان\n\n"
                    )
                elif partner_was_cost_deducted:
                    # Coins were deducted (partner selected specific gender and had enough coins)
                    if chat_successful:
                        partner_end_message += (
                            f"✅ چت موفقیت‌آمیز بود!\n"
                            f"💰 هزینه این چت: {chat_cost} سکه (کسر شده)\n"
                            f"💎 سکه‌های باقی‌مانده: {partner_current_points}\n\n"
                            f"💎 با خرید پریمیوم:\n"
                            f"• هزینه چت: رایگان\n"
                            f"• نفر اول صف\n"
                            f"• امکانات بیشتر\n\n"
                        )
                    else:
                        if partner_coins_refunded:
                            # Get required message count from system settings
                            required_message_count_str = await get_system_setting_value(db_session, 'chat_success_message_count', '2')
                            try:
                                required_message_count = int(required_message_count_str)
                            except (ValueError, TypeError):
                                required_message_count = 2
                            
                            partner_end_message += (
                                f"⚠️ چت موفقیت‌آمیز نبود.\n"
                                f"💰 {chat_cost} سکه به حساب شما برگشت داده شد.\n"
                                f"💎 سکه‌های فعلی: {partner_current_points}\n\n"
                                f"💡 نکته: برای کسر سکه، هر دو طرف باید حداقل {required_message_count} پیام بفرستن.\n\n"
                            )
                        else:
                            partner_end_message += (
                                f"⚠️ چت موفقیت‌آمیز نبود.\n"
                                f"💰 تلاش برای بازگشت سکه انجام شد.\n"
                                f"💎 سکه‌های فعلی: {partner_current_points}\n\n"
                            )
                elif partner_pref_gender is None:
                    # "all" was selected - no coins deducted
                    partner_end_message += (
                        "💰 هزینه این چت: رایگان\n"
                        "🌐 چون «همه» رو انتخاب کردی، هیچ سکه‌ای کسر نشد.\n\n"
                    )
                else:
                    # Partner selected specific gender but coins weren't deducted (probably didn't have enough coins)
                    partner_end_message += (
                        "💰 هزینه این چت: رایگان\n"
                        "💡 هیچ سکه‌ای کسر نشد.\n\n"
                    )
            
            partner_end_message += "━━━━━━━━━━━━━━━━━━━━\n"
            partner_end_message += "بازگشت به منوی اصلی..."
            
            # Send message to user (only once)
            # Always send a new message instead of editing, to ensure keyboard is shown
            await callback.message.answer(
                user_end_message,
                reply_markup=get_main_reply_keyboard()
            )
            
            # Ask if user wants to search again and delete messages
            search_again_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="🔍 بله، جستجو کن", callback_data="chat:search_again"),
                    InlineKeyboardButton(text="❌ خیر", callback_data="chat:no_search"),
                ],
                [
                    InlineKeyboardButton(text="🗑️ حذف پیام‌های من", callback_data="chat:delete_my_messages"),
                ],
            ])
            
            await callback.message.answer(
                "━━━━━━━━━━━━━━━━━━━━\n"
                "💬 چت شما قطع شد\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "🔍 می‌خوای دوباره جستجو کنی؟",
                reply_markup=search_again_keyboard
            )
            
            # Send message to partner if exists
            if partner:
                bot = Bot(token=settings.BOT_TOKEN)
                try:
                    await bot.send_message(
                        partner.telegram_id,
                        partner_end_message,
                        reply_markup=get_main_reply_keyboard()
                    )
                    
                    # Ask partner if they want to search again and delete messages
                    partner_search_again_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text="🔍 بله، جستجو کن", callback_data="chat:search_again"),
                            InlineKeyboardButton(text="❌ خیر", callback_data="chat:no_search"),
                        ],
                        [
                            InlineKeyboardButton(text="🗑️ حذف پیام‌های من", callback_data="chat:delete_my_messages"),
                        ],
                    ])
                    
                    await bot.send_message(
                        partner.telegram_id,
                        "━━━━━━━━━━━━━━━━━━━━\n"
                        "💬 چت شما قطع شد\n"
                        "━━━━━━━━━━━━━━━━━━━━\n\n"
                        "🔍 می‌خوای دوباره جستجو کنی؟",
                        reply_markup=partner_search_again_keyboard
                    )
                    
                    await bot.session.close()
                except Exception:
                    pass
            
            # Don't delete messages automatically - user can request deletion via button
            # Message IDs are stored in Redis and will be available for deletion request
            
            # Check and award badges for chat achievements
            if chat_successful:
                from core.achievement_system import AchievementSystem
                from core.badge_manager import BadgeManager
                from db.crud import get_user_chat_count, get_badge_by_key
                from aiogram import Bot as BadgeBot
                
                # Check chat count achievements for both users
                user_chat_count = await get_user_chat_count(db_session, user.id)
                partner_chat_count = await get_user_chat_count(db_session, partner.id) if partner else 0
                
                # Check achievements for user
                completed_achievements = await AchievementSystem.check_chat_count_achievement(user.id, user_chat_count)
                
                # Award badges for completed achievements
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
                    
                    # Check achievements for partner
                    if partner:
                        partner_completed = await AchievementSystem.check_chat_count_achievement(partner.id, partner_chat_count)
                        for achievement in partner_completed:
                            if achievement.achievement and achievement.achievement.badge_id:
                                badge = await get_badge_by_key(db_session, achievement.achievement.achievement_key)
                                if badge:
                                    await BadgeManager.award_badge_and_notify(
                                        partner.id,
                                        badge.badge_key,
                                        badge_bot,
                                        partner.telegram_id
                                    )
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error awarding badges: {e}")
                finally:
                    await badge_bot.session.close()
            
            await callback.answer()
        else:
            await callback.answer("❌ چت فعالی یافت نشد.", show_alert=True)
        break


@router.callback_query(F.data == "chat:delete_my_messages")
async def delete_my_messages(callback: CallbackQuery):
    """Delete user's messages from the ended chat."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Get the most recent ended chat room for this user
        from db.models import ChatRoom
        from sqlalchemy import select, desc
        
        result = await db_session.execute(
            select(ChatRoom)
            .where(
                ((ChatRoom.user1_id == user.id) | (ChatRoom.user2_id == user.id))
                & (ChatRoom.is_active == False)
            )
            .order_by(desc(ChatRoom.ended_at))
            .limit(1)
        )
        ended_chat_room = result.scalar_one_or_none()
        
        if not ended_chat_room:
            await callback.answer("❌ چت پایان یافته‌ای یافت نشد.", show_alert=True)
            return
        
        # Get message IDs for this user from Redis
        user_message_ids = await chat_manager.get_message_ids(ended_chat_room.id, user.id)
        
        if not user_message_ids:
            await callback.answer("⚠️ پیامی برای حذف یافت نشد.", show_alert=True)
            return
        
        # Get partner ID to delete messages from their chat too
        partner_id = None
        if ended_chat_room.user1_id == user.id:
            partner_id = ended_chat_room.user2_id
        else:
            partner_id = ended_chat_room.user1_id
        
        # Get partner user to get their telegram_id
        from db.crud import get_user_by_id
        partner = None
        if partner_id:
            partner = await get_user_by_id(db_session, partner_id)
        
        # Delete messages from user's chat
        from aiogram import Bot as DeleteBot
        delete_bot = DeleteBot(token=settings.BOT_TOKEN)
        try:
            deleted_count = 0
            partner_deleted_count = 0
            
            # Delete messages from user's own chat
            for msg_id in user_message_ids:
                try:
                    await delete_bot.delete_message(user.telegram_id, msg_id)
                    deleted_count += 1
                except Exception:
                    pass  # Message might already be deleted or not found
            
            # Also delete messages from partner's chat
            # The messages sent to partner have the same message_id (they were forwarded)
            # But we need to find which messages in partner's chat correspond to user's messages
            # Actually, when we send a message to partner, we store the sent message_id for partner
            # So we need to get message IDs that were sent TO partner (stored under partner's ID)
            # But wait, we stored message_id for partner when we sent the message
            # So we need to get the message IDs that were sent to partner
            
            # Actually, the message IDs stored for user are:
            # 1. Original messages sent by user (stored with user.id)
            # 2. Messages sent to partner (stored with partner.id) - these are the forwarded messages
            
            # So we need to delete:
            # 1. User's original messages (already done above)
            # 2. Messages sent to partner (need to get from partner's message IDs)
            
            if partner:
                # For each user message ID, find the corresponding partner message ID using the mapping
                partner_msg_ids_to_delete = []
                for user_msg_id in user_message_ids:
                    # Get the corresponding partner message ID from the mapping
                    pair_key = chat_manager._get_message_pair_key(ended_chat_room.id, user_msg_id)
                    partner_msg_id_str = await chat_manager.redis.get(pair_key)
                    if partner_msg_id_str:
                        try:
                            partner_msg_id = int(partner_msg_id_str)
                            partner_msg_ids_to_delete.append(partner_msg_id)
                        except (ValueError, TypeError):
                            pass
                
                # Delete the corresponding messages from partner's chat
                for partner_msg_id in partner_msg_ids_to_delete:
                    try:
                        await delete_bot.delete_message(partner.telegram_id, partner_msg_id)
                        partner_deleted_count += 1
                    except Exception:
                        pass  # Message might already be deleted or not found
                
                # Clean up message pair mappings
                for user_msg_id in user_message_ids:
                    pair_key = chat_manager._get_message_pair_key(ended_chat_room.id, user_msg_id)
                    await chat_manager.redis.delete(pair_key)
            
            await delete_bot.session.close()
            
            # Clear message IDs from Redis after deletion
            await chat_manager.clear_message_ids(ended_chat_room.id, user.id)
            
            total_deleted = deleted_count + partner_deleted_count
            if total_deleted > 0:
                await callback.message.answer(
                    f"✅ {deleted_count} پیام از شما و {partner_deleted_count} پیام از چت مخاطبت حذف شد.",
                    reply_markup=get_main_reply_keyboard()
                )
                await callback.answer("✅ پیام‌های شما حذف شدند.", show_alert=True)
            else:
                await callback.answer("⚠️ پیامی برای حذف یافت نشد.", show_alert=True)
        except Exception as e:
            await callback.answer("❌ خطا در حذف پیام‌ها.", show_alert=True)
        break


@router.callback_query(F.data == "chat:search_again")
async def search_again_after_chat_end(callback: CallbackQuery, state: FSMContext):
    """User wants to search again after chat ended."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Check if user already has active chat
        if await chat_manager.is_chat_active(user.id, db_session):
            await callback.answer("❌ شما در حال حاضر یک چت فعال دارید!", show_alert=True)
            await state.clear()
            return
        
        # Check if user is already in queue
        if await matchmaking_queue.is_user_in_queue(user_id):
            await callback.answer("⏳ شما در صف هستید. لطفاً صبر کنید...", show_alert=True)
            return
        
        # Show gender selection keyboard
        from bot.keyboards.common import get_preferred_gender_keyboard
        try:
            await callback.message.edit_text(
                "👥 با چه جنسیتی می‌خوای چت کنی؟",
                reply_markup=get_preferred_gender_keyboard()
            )
        except:
            await callback.message.answer(
                "👥 با چه جنسیتی می‌خوای چت کنی؟",
                reply_markup=get_preferred_gender_keyboard()
            )
        
        await callback.answer()
        break


@router.callback_query(F.data == "chat:no_search")
async def no_search_after_chat_end(callback: CallbackQuery):
    """User doesn't want to search again after chat ended."""
    try:
        await callback.message.edit_text(
            "✅ باشه، هر وقت خواستی دوباره جستجو کنی، دکمه «💬 شروع چت» رو بزن.",
            reply_markup=None
        )
    except:
        await callback.message.answer(
            "✅ باشه، هر وقت خواستی دوباره جستجو کنی، دکمه «💬 شروع چت» رو بزن."
        )
    
    await callback.answer()


@router.callback_query(F.data == "chat:video_call")
async def request_video_call(callback: CallbackQuery):
    """Request video call."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Check if user has active chat
        if not await chat_manager.is_chat_active(user.id, db_session):
            await callback.answer("❌ شما در حال حاضر یک چت فعال ندارید!", show_alert=True)
            return
        
        # Check premium status
        user_premium = await check_user_premium(db_session, user.id)
        
        # Only premium users can start video call
        if not user_premium:
            from bot.keyboards.common import get_premium_keyboard
            try:
                await callback.message.edit_text(
                    f"❌ شما عضویت ویژه ندارید.\n\n"
                    f"💎 اشتراک پریمیوم\n\n"
                    f"با خرید پریمیوم از امکانات زیر بهره‌مند شوید:\n"
                    f"• تماس تصویری\n"
                    f"• تماس صوتی\n"
                    f"• زمان چت بیشتر ({settings.PREMIUM_CHAT_DURATION_MINUTES} دقیقه در مقابل {settings.MAX_CHAT_DURATION_MINUTES} دقیقه)\n"
                    f"• فیلترهای پیشرفته\n"
                    f"• اولویت در صف (نفر اول صف)\n\n"
                    f"قیمت: {settings.PREMIUM_PRICE} تومان\n"
                    f"مدت زمان: {settings.PREMIUM_DURATION_DAYS} روز\n\n"
                    f"آیا می‌خواهید پریمیوم بخرید?",
                    reply_markup=get_premium_keyboard()
                )
            except Exception:
                await callback.message.answer(
                    f"❌ شما عضویت ویژه ندارید.\n\n"
                    f"💎 اشتراک پریمیوم\n\n"
                    f"با خرید پریمیوم از امکانات زیر بهره‌مند شوید:\n"
                    f"• تماس تصویری\n"
                    f"• تماس صوتی\n"
                    f"• زمان چت بیشتر ({settings.PREMIUM_CHAT_DURATION_MINUTES} دقیقه در مقابل {settings.MAX_CHAT_DURATION_MINUTES} دقیقه)\n"
                    f"• فیلترهای پیشرفته\n"
                    f"• اولویت در صف (نفر اول صف)\n\n"
                    f"قیمت: {settings.PREMIUM_PRICE} تومان\n"
                    f"مدت زمان: {settings.PREMIUM_DURATION_DAYS} روز\n\n"
                    f"آیا می‌خواهید پریمیوم بخرید?",
                    reply_markup=get_premium_keyboard()
                )
            await callback.answer("❌ فقط کاربران پریمیوم می‌توانند تماس تصویری شروع کنند.", show_alert=True)
            return
        
        # Get partner
        partner_id = await chat_manager.get_partner_id(user.id, db_session)
        if not partner_id:
            await callback.answer("❌ هم‌چت پیدا نشد.", show_alert=True)
            return
        
        # Request video call
        from db.crud import get_user_by_id
        from aiogram import Bot
        from bot.keyboards.common import get_call_request_keyboard
        
        partner = await get_user_by_id(db_session, partner_id)
        if not partner:
            await callback.answer("❌ مخاطب یافت نشد.", show_alert=True)
            return
        
        # Notify user that request was sent
        try:
            await callback.message.edit_text(
                "📹 درخواست تماس تصویری ارسال شد!\n\n"
                "در انتظار تایید مخاطب...",
                reply_markup=None
            )
        except:
            await callback.message.answer(
                "📹 درخواست تماس تصویری ارسال شد!\n\n"
                "در انتظار تایید مخاطب...",
                reply_markup=get_chat_reply_keyboard()
            )
        
        # Notify partner with accept/reject buttons
        bot = Bot(token=settings.BOT_TOKEN)
        try:
            call_keyboard = get_call_request_keyboard("video", user.id)
            await bot.send_message(
                partner.telegram_id,
                "📹 درخواست تماس تصویری از مخاطب شما\n\n"
                "آیا می‌خواهید تماس تصویری را بپذیرید?",
                reply_markup=call_keyboard
            )
            await bot.session.close()
        except Exception:
            pass
        
        await callback.answer()
        break


@router.callback_query(F.data == "chat:cancel_search")
async def cancel_search(callback: CallbackQuery, state: FSMContext):
    """Cancel search and remove user from queue."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Check if user is in queue
        if not await matchmaking_queue.is_user_in_queue(user_id):
            await callback.answer("❌ شما در صف نیستید.", show_alert=True)
            return
        
        # Remove from queue
        await matchmaking_queue.remove_user_from_queue(user_id)
        
        from bot.keyboards.reply import get_main_reply_keyboard
        
        # Only send one message (either edit or answer, not both)
        try:
            await callback.message.edit_text(
                "✅ جستجو لغو شد.\n\n"
                "شما از صف خارج شدید.",
                reply_markup=None
            )
        except:
            # If edit fails, send new message
        await callback.message.answer(
            "✅ جستجو لغو شد.\n\n"
            "شما از صف خارج شدید.",
            reply_markup=get_main_reply_keyboard()
        )
        
        await callback.answer("✅ جستجو لغو شد")
        await state.clear()
        break

