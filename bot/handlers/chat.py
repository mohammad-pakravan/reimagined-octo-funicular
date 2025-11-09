"""
Chat handler for the bot.
Handles starting chat, ending chat, and video call requests.
"""
import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

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
    
    # Convert "all" to None
    if preferred_gender == "all":
        preferred_gender = None
    
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
        
        # Add user to queue with preferred gender
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
        
        queue_count = await matchmaking_queue.get_total_queue_count()
        gender_counts = await matchmaking_queue.get_queue_count_by_gender()
        
        # Check if user has premium
        from db.crud import check_user_premium
        user_premium = await check_user_premium(db_session, user.id)
        
        from bot.keyboards.common import get_queue_status_keyboard
        
        queue_status_text = (
            f"🔍 در حال جستجوی هم‌چت...\n\n"
            f"👥 وضعیت صف:\n"
            f"• 👨 پسر: {gender_counts.get('male', 0)} نفر\n"
            f"• 👩 دختر: {gender_counts.get('female', 0)} نفر\n"
            f"• 👤 سایر: {gender_counts.get('other', 0)} نفر\n\n"
        )
        
        if not user_premium:
            queue_status_text += (
                f"💎 با خرید اشتراک پریمیوم، نفر اول صف شوید!\n\n"
            )
        
        queue_status_text += "لطفاً صبر کنید، در حال پیدا کردن کسی برای شما هستیم..."
        
        await callback.message.edit_text(
            queue_status_text,
            reply_markup=get_queue_status_keyboard(user_premium)
        )
        
        await state.clear()
        
        # Try to find a match immediately and periodically
        await try_find_match(user_id, db_session)
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
                    # Create chat room
                    chat_room = await chat_manager.create_chat(user.id, matched_user.id, db_session)
                    
                    # Notify both users
                    from aiogram import Bot
                    bot = Bot(token=settings.BOT_TOKEN)
                    
                    await bot.send_message(
                        user.telegram_id,
                        "✅ هم‌چت پیدا شد! شما الان به هم متصل شدید.\n\n"
                        "شروع به چت کنید:",
                        reply_markup=get_chat_reply_keyboard()
                    )
                    
                    await bot.send_message(
                        matched_user.telegram_id,
                        "✅ هم‌چت پیدا شد! شما الان به هم متصل شدید.\n\n"
                        "شروع به چت کنید:",
                        reply_markup=get_chat_reply_keyboard()
                    )
                    
                    await bot.session.close()
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
        from db.crud import get_active_chat_room_by_user
        chat_room = await get_active_chat_room_by_user(db_session, user.id)
        
        if chat_room:
            # Get partner before ending chat
            partner_id = await chat_manager.get_partner_id(user.id, db_session)
            
            # Get partner object before ending chat (for notifications)
            partner = None
            if partner_id:
                partner = await get_user_by_id(db_session, partner_id)
            
            # End chat room
            await chat_manager.end_chat(chat_room.id, db_session)
            
            # Notify partner
            if partner:
                from aiogram import Bot
                bot = Bot(token=settings.BOT_TOKEN)
                
                try:
                    await bot.send_message(
                        partner.telegram_id,
                        "❌ مخاطب شما چت را قطع کرد.\n\n"
                        "بازگشت به منوی اصلی...",
                        reply_markup=get_main_reply_keyboard()
                    )
                    await bot.session.close()
                except Exception:
                    pass
            
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
            
            try:
                await callback.message.edit_text(
                    "✅ چت به پایان رسید.\n\n"
                    "بازگشت به منوی اصلی...",
                    reply_markup=None
                )
            except:
                pass
            
            # Send confirmation message
            await callback.message.answer(
                "✅ چت به پایان رسید.\n\n"
                "بازگشت به منوی اصلی...",
                reply_markup=get_main_reply_keyboard()
            )
            
            await callback.answer()
        else:
            await callback.answer("❌ چت فعالی یافت نشد.", show_alert=True)
        break


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
        
        try:
            await callback.message.edit_text(
                "✅ جستجو لغو شد.\n\n"
                "شما از صف خارج شدید.",
                reply_markup=None
            )
        except:
            pass
        
        await callback.message.answer(
            "✅ جستجو لغو شد.\n\n"
            "شما از صف خارج شدید.",
            reply_markup=get_main_reply_keyboard()
        )
        
        await callback.answer("✅ جستجو لغو شد")
        await state.clear()
        break

