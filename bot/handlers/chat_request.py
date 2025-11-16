"""
Chat request handlers.
Handles sending, accepting, and rejecting chat requests.
"""
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.enums import ContentType

from db.database import get_db
from db.crud import (
    get_user_by_telegram_id,
    get_user_by_id,
    get_active_chat_room_by_user,
)
from bot.keyboards.common import get_chat_request_keyboard, get_chat_request_cancel_keyboard
from bot.keyboards.reply import get_chat_reply_keyboard
from core.chat_manager import ChatManager
from config.settings import settings
from utils.validators import get_display_name

router = Router()

chat_manager = None
redis_client = None


def set_redis_client(client):
    """Set Redis client for tracking pending chat requests."""
    global redis_client
    redis_client = client


def _get_pending_request_key(requester_id: int, receiver_id: int) -> str:
    """Get Redis key for pending chat request."""
    return f"chat_request:pending:{requester_id}:{receiver_id}"


async def has_pending_chat_request(requester_id: int, receiver_id: int) -> bool:
    """Check if user has a pending chat request to receiver."""
    if not redis_client:
        return False
    key = _get_pending_request_key(requester_id, receiver_id)
    exists = await redis_client.exists(key)
    return bool(exists)


async def set_pending_chat_request(requester_id: int, receiver_id: int):
    """Set pending chat request in Redis (expires after 2 minutes)."""
    if not redis_client:
        return
    key = _get_pending_request_key(requester_id, receiver_id)
    await redis_client.setex(key, 120, "1")  # 2 minutes TTL


async def remove_pending_chat_request(requester_id: int, receiver_id: int):
    """Remove pending chat request from Redis."""
    if not redis_client:
        return
    key = _get_pending_request_key(requester_id, receiver_id)
    await redis_client.delete(key)


def set_chat_manager(manager: ChatManager):
    """Set chat manager instance."""
    global chat_manager
    chat_manager = manager


@router.message(StateFilter("chat_request:waiting_message"), F.content_type == ContentType.TEXT)
async def process_chat_request_message(message: Message, state: FSMContext):
    """Process chat request message from user."""
    user_id = message.from_user.id
    request_message = message.text.strip()
    
    if not request_message or len(request_message) < 1:
        await message.answer("❌ پیام نمی‌تواند خالی باشد. لطفاً پیام درخواست چت را بنویسید:")
        return
    
    if len(request_message) > 500:
        await message.answer("❌ پیام خیلی طولانی است. حداکثر 500 کاراکتر مجاز است.")
        return
    
    # Get receiver_id from state
    state_data = await state.get_data()
    receiver_id = state_data.get("chat_request_receiver_id")
    
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
        
        # If not premium, check if user has enough coins
        if not user_premium:
            from config.settings import settings
            chat_request_cost = settings.CHAT_REQUEST_COST
            user_points = await get_user_points(db_session, user.id)
            if user_points < chat_request_cost:
                await message.answer(
                    f"⚠️ سکه کافی نداری!\n\n"
                    f"💰 برای ارسال درخواست چت به {chat_request_cost} سکه نیاز داری.\n"
                    f"💎 سکه فعلی تو: {user_points}\n\n"
                    f"💡 می‌تونی سکه‌هات رو به پریمیوم تبدیل کنی یا پریمیوم بگیری."
                )
                await state.clear()
                return
            
            # Show confirmation with cost
            from bot.keyboards.common import get_confirm_keyboard
            await message.answer(
                f"💬 درخواست چت\n\n"
                f"📝 پیام شما:\n{request_message}\n\n"
                f"📤 برای: {get_display_name(receiver)}\n\n"
                f"💰 هزینه این درخواست: {chat_request_cost} سکه\n"
                f"💎 سکه‌های فعلی تو: {user_points}\n\n"
                f"آیا می‌خواهید این درخواست را ارسال کنید؟",
                reply_markup=get_confirm_keyboard("chat_request:send")
            )
            
            # Store message text and receiver_id in state
            await state.update_data(chat_request_message=request_message)
            await state.update_data(chat_request_receiver_id=receiver_id)
            return
        else:
            # Premium user - show confirmation without cost
            from bot.keyboards.common import get_confirm_keyboard
            await message.answer(
                f"💬 درخواست چت\n\n"
                f"📝 پیام شما:\n{request_message}\n\n"
                f"📤 برای: {get_display_name(receiver)}\n\n"
                f"💎 این درخواست رایگان است (پریمیوم)\n\n"
                f"آیا می‌خواهید این درخواست را ارسال کنید؟",
                reply_markup=get_confirm_keyboard("chat_request:send")
            )
            
            # Store message text and receiver_id in state
            await state.update_data(chat_request_message=request_message)
            await state.update_data(chat_request_receiver_id=receiver_id)
            break


async def check_chat_request_timeout(requester_id: int, requester_telegram_id: int, receiver_id: int, receiver_telegram_id: int):
    """Check if chat request was responded to after 2 minutes and notify if not."""
    await asyncio.sleep(120)  # Wait 2 minutes
    
    # First check if pending request still exists in Redis
    # If it doesn't exist, it means it was already accepted/rejected
    if not await has_pending_chat_request(requester_id, receiver_id):
        # Request was already handled (accepted/rejected), no need to notify
        return
    
    # Check if requester or receiver have active chat together
    async for db_session in get_db():
        if chat_manager:
            # Check if they have active chat
            requester_chat = await get_active_chat_room_by_user(db_session, requester_id)
            if requester_chat:
                # Check if the chat is with the receiver
                if requester_chat.user1_id == receiver_id or requester_chat.user2_id == receiver_id:
                    # Chat was accepted, remove pending request and no need to notify
                    await remove_pending_chat_request(requester_id, receiver_id)
                    break
            
            # No active chat and pending request still exists, request was not responded to
            # Remove pending request from Redis
            await remove_pending_chat_request(requester_id, receiver_id)
            
            # Notify requester
            bot = Bot(token=settings.BOT_TOKEN)
            try:
                from db.crud import get_user_by_id
                receiver = await get_user_by_id(db_session, receiver_id)
                receiver_name = get_display_name(receiver) if receiver else "کاربر"
                
                await bot.send_message(
                    requester_telegram_id,
                    f"⏰ متأسفانه {receiver_name} به درخواست چت شما پاسخ نداد.\n\n"
                    "💡 مثل اینکه کاربر آفلاین است یا درخواست را ندیده است.\n"
                    "می‌تونی دوباره امتحان کنی یا با کاربران دیگر چت کنی."
                )
                await bot.session.close()
            except Exception:
                pass
        break


@router.callback_query(F.data == "chat_request:send:confirm")
async def confirm_chat_request_send(callback: CallbackQuery, state: FSMContext):
    """Confirm and send chat request with coin deduction."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            await state.clear()
            return
        
        # Get state data
        state_data = await state.get_data()
        request_message = state_data.get("chat_request_message")
        receiver_id = state_data.get("chat_request_receiver_id")
        
        if not request_message or not receiver_id:
            await callback.answer("❌ اطلاعات یافت نشد.", show_alert=True)
            await state.clear()
            return
        
        receiver = await get_user_by_id(db_session, receiver_id)
        if not receiver:
            await callback.answer("❌ گیرنده یافت نشد.", show_alert=True)
            await state.clear()
            return
        
        # Check if user has premium
        from db.crud import check_user_premium, get_user_points, spend_points
        user_premium = await check_user_premium(db_session, user.id)
        
        # Deduct coin if not premium
        if not user_premium:
            from config.settings import settings
            chat_request_cost = settings.CHAT_REQUEST_COST
            user_points = await get_user_points(db_session, user.id)
            if user_points < chat_request_cost:
                await callback.answer("❌ سکه کافی نداری!", show_alert=True)
                await state.clear()
                return
            
            # Deduct coins
            success = await spend_points(
                db_session,
                user.id,
                chat_request_cost,
                "spent",
                "chat_request",
                f"Cost for sending chat request to user {receiver.id}"
            )
            if not success:
                await callback.answer("❌ خطا در کسر سکه.", show_alert=True)
                await state.clear()
                return
        
        # Generate profile_id if not exists
        if not user.profile_id:
            import hashlib
            profile_id = hashlib.md5(f"user_{user.telegram_id}".encode()).hexdigest()[:12]
            user.profile_id = profile_id
            await db_session.commit()
            await db_session.refresh(user)
        
        # Send chat request notification to receiver
        bot = Bot(token=settings.BOT_TOKEN)
        try:
            gender_map = {"male": "پسر 🧑", "female": "دختر 👩", "other": "سایر"}
            gender_text = gender_map.get(user.gender, user.gender or "تعیین نشده")
            
            user_profile_id = f"/user_{user.profile_id}"
            
            # Build profile info text
            profile_info = f"💬 درخواست چت جدید!\n\n"
            profile_info += f"👤 از: {get_display_name(user)}\n"
            profile_info += f"⚧️ جنسیت: {gender_text}\n"
            
            if user.age:
                profile_info += f"🎂 سن: {user.age}\n"
            if user.city:
                profile_info += f"🏙️ شهر: {user.city}\n"
            if user.province:
                profile_info += f"🗺️ استان: {user.province}\n"
            
            profile_info += f"🆔 ID: {user_profile_id}\n\n"
            profile_info += f"💬 پیام درخواست:\n{request_message}\n\n"
            profile_info += "آیا می‌خواهید چت را شروع کنید؟"
            
            # Create keyboard
            from bot.keyboards.common import get_chat_request_keyboard
            chat_request_keyboard = get_chat_request_keyboard(user.id, user.id)
            
            # Send message with photo if available
            if user.profile_image_url:
                try:
                    await bot.send_photo(
                        receiver.telegram_id,
                        photo=user.profile_image_url,
                        caption=profile_info,
                        reply_markup=chat_request_keyboard
                    )
                except Exception:
                    # If photo fails, send text only
                    await bot.send_message(
                        receiver.telegram_id,
                        profile_info,
                        reply_markup=chat_request_keyboard
                    )
            else:
                await bot.send_message(
                    receiver.telegram_id,
                    profile_info,
                    reply_markup=chat_request_keyboard
                )
            
            await bot.session.close()
        except Exception as e:
            # If bot can't send message, inform user
            await callback.answer("❌ امکان ارسال درخواست چت وجود ندارد.", show_alert=True)
            await state.clear()
            break
        
        # Send confirmation message to requester with cancel button
        from bot.keyboards.common import get_chat_request_cancel_keyboard
        cancel_keyboard = get_chat_request_cancel_keyboard(user.id, receiver.id)
        
        cost_text = "💎 این درخواست رایگان بود (پریمیوم)" if user_premium else "💰 1 سکه از حساب شما کسر شد"
        
        await callback.message.edit_text(
            f"✅ درخواست چت شما برای {get_display_name(receiver)} ارسال شد.\n\n"
            f"{cost_text}\n\n"
            f"⏳ منتظر پاسخ باشید...\n\n"
            f"💡 می‌تونی درخواست رو لغو کنی:",
            reply_markup=cancel_keyboard
        )
        await callback.answer("✅ درخواست ارسال شد!")
        await state.clear()
        
        # Set pending request in Redis
        await set_pending_chat_request(user.id, receiver.id)
        
        # Create timeout task - if no response after 2 minutes, notify requester
        asyncio.create_task(check_chat_request_timeout(user.id, user.telegram_id, receiver.id, receiver.telegram_id))
        
        break


@router.callback_query(F.data == "chat_request:send:cancel")
async def cancel_chat_request_send(callback: CallbackQuery, state: FSMContext):
    """Cancel chat request sending."""
    await callback.message.edit_text(
        "❌ ارسال درخواست چت لغو شد.",
        reply_markup=None
    )
    await callback.answer("❌ ارسال لغو شد")
    await state.clear()


@router.callback_query(F.data.startswith("chat_request:accept:"))
async def accept_chat_request(callback: CallbackQuery):
    """Accept chat request and start chat."""
    requester_id = int(callback.data.split(":")[-1])
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        requester = await get_user_by_id(db_session, requester_id)
        if not requester:
            await callback.answer("❌ درخواست‌دهنده یافت نشد.", show_alert=True)
            return
        
        # Check if user already has an active chat
        if chat_manager:
            active_chat = await get_active_chat_room_by_user(db_session, user.id)
            if active_chat:
                await callback.answer("❌ شما در حال حاضر در یک چت فعال هستید.", show_alert=True)
                return
            
            # Check if requester already has an active chat
            requester_active_chat = await get_active_chat_room_by_user(db_session, requester.id)
            if requester_active_chat:
                await callback.answer("❌ این کاربر در حال حاضر در یک چت فعال است.", show_alert=True)
                return
            
            # Create chat room (chat request doesn't have preferred gender, so pass None)
            try:
                chat_room = await chat_manager.create_chat(user.id, requester.id, db_session, None, None)
                
                # Chat created successfully, now notify users
                # If notification fails, it's not critical - chat is already created
                bot = Bot(token=settings.BOT_TOKEN)
                notification_errors = []
                
                # Check premium status and prepare messages
                from db.crud import check_user_premium, get_user_points, spend_points
                from core.points_manager import PointsManager
                from db.crud import get_system_setting_value
                
                user_premium = await check_user_premium(db_session, user.id)
                requester_premium = await check_user_premium(db_session, requester.id)
                
                # Get chat cost from system settings
                chat_cost_str = await get_system_setting_value(db_session, 'chat_message_cost', '3')
                try:
                    chat_cost = int(chat_cost_str)
                except (ValueError, TypeError):
                    chat_cost = 3
                
                # Get user points
                user_points = await get_user_points(db_session, user.id)
                requester_points = await get_user_points(db_session, requester.id)
                
                # Chat requests don't deduct coins (preferred_gender is None, meaning "all")
                # So no coin deduction needed
                
                # Prepare messages with beautiful UI
                user_msg = (
                    "✅ چت شروع شد!\n\n"
                    "🎉 اکنون می‌توانید با هم چت کنید.\n\n"
                )
                
                requester_msg = (
                    "✅ چت شروع شد!\n\n"
                    "🎉 اکنون می‌توانید با هم چت کنید.\n\n"
                )
                
                # Add cost information
                if user_premium:
                    user_msg += (
                        "💎 وضعیت: پریمیوم\n"
                        "💰 هزینه این چت: رایگان\n\n"
                    )
                else:
                    user_msg += (
                        "💰 هزینه این چت: رایگان\n"
                        "🌐 چون از طریق درخواست چت شروع شد، هیچ سکه‌ای کسر نمی‌شه.\n\n"
                    )
                
                if requester_premium:
                    requester_msg += (
                        "💎 وضعیت: پریمیوم\n"
                        "💰 هزینه این چت: رایگان\n\n"
                    )
                else:
                    requester_msg += (
                        "💰 هزینه این چت: رایگان\n"
                        "🌐 چون از طریق درخواست چت شروع شد، هیچ سکه‌ای کسر نمی‌شه.\n\n"
                    )
                
                
                try:
                    await bot.send_message(user.telegram_id, user_msg, reply_markup=get_chat_reply_keyboard())
                except Exception as e:
                    notification_errors.append(f"Failed to notify user: {e}")
                
                try:
                    await bot.send_message(requester.telegram_id, requester_msg, reply_markup=get_chat_reply_keyboard())
                except Exception as e:
                    notification_errors.append(f"Failed to notify requester: {e}")
                
                await bot.session.close()
                
                # Log notification errors but don't fail
                if notification_errors:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Chat created but notification failed: {notification_errors}")
                
                # Remove pending request from Redis
                await remove_pending_chat_request(requester.id, user.id)
                
                # Remove keyboard from message (if possible)
                try:
                    await callback.message.edit_reply_markup(reply_markup=None)
                except Exception:
                    pass
                
                # Show popup notification
                await callback.answer("✅ چت شروع شد!", show_alert=True)
                
            except Exception as e:
                # Only log actual chat creation errors
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error creating chat room: {e}", exc_info=True)
                await callback.answer(f"❌ خطا در ایجاد چت: {str(e)}", show_alert=True)
        else:
            await callback.answer("❌ سیستم چت در دسترس نیست.", show_alert=True)
        break


@router.callback_query(F.data.startswith("chat_request:reject:"))
async def reject_chat_request(callback: CallbackQuery):
    """Reject chat request."""
    requester_id = int(callback.data.split(":")[-1])
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        requester = await get_user_by_id(db_session, requester_id)
        if not requester:
            await callback.answer("❌ درخواست‌دهنده یافت نشد.", show_alert=True)
            return
        
        # Notify requester (optional)
        bot = Bot(token=settings.BOT_TOKEN)
        try:
            await bot.send_message(
                requester.telegram_id,
                f"❌ درخواست چت شما توسط {get_display_name(user)} رد شد."
            )
            await bot.session.close()
        except Exception:
            pass
        
        # Remove pending request from Redis
        await remove_pending_chat_request(requester.id, user.id)
        
        # Add requester to user's blocked list to prevent re-matching
        from bot.handlers.chat import matchmaking_queue
        if matchmaking_queue:
            await matchmaking_queue.add_blocked_user(user.telegram_id, requester.telegram_id)
        
        # Remove keyboard from message (if possible)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        
        # Show popup notification
        await callback.answer("❌ درخواست چت رد شد", show_alert=True)
        break


@router.callback_query(F.data.startswith("chat_request:cancel:"))
async def cancel_chat_request(callback: CallbackQuery):
    """Cancel chat request by requester."""
    receiver_id = int(callback.data.split(":")[-1])
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        receiver = await get_user_by_id(db_session, receiver_id)
        if not receiver:
            await callback.answer("❌ گیرنده یافت نشد.", show_alert=True)
            return
        
        # Check if pending request exists
        if not await has_pending_chat_request(user.id, receiver_id):
            await callback.answer("❌ درخواست چت یافت نشد یا قبلاً لغو شده است.", show_alert=True)
            return
        
        # Remove pending request from Redis
        await remove_pending_chat_request(user.id, receiver_id)
        
        # Notify receiver (optional - can be removed if not needed)
        bot = Bot(token=settings.BOT_TOKEN)
        try:
            await bot.send_message(
                receiver.telegram_id,
                f"ℹ️ {get_display_name(user)} درخواست چت خود را لغو کرد."
            )
            await bot.session.close()
        except Exception:
            pass
        
        # Update requester's message
        try:
            await callback.message.edit_text(
                "❌ درخواست چت لغو شد.\n\n"
                f"درخواست چت شما برای {get_display_name(receiver)} لغو شد.",
                reply_markup=None
            )
        except Exception:
            await callback.message.answer(
                "❌ درخواست چت لغو شد.\n\n"
                f"درخواست چت شما برای {get_display_name(receiver)} لغو شد."
            )
        
        await callback.answer("✅ درخواست چت لغو شد")
        break


@router.callback_query(F.data.startswith("chat_request:block:"))
async def block_from_chat_request(callback: CallbackQuery):
    """Block user from chat request."""
    requester_id = int(callback.data.split(":")[-1])
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        from db.crud import block_user
        
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        requester = await get_user_by_id(db_session, requester_id)
        if not requester:
            await callback.answer("❌ درخواست‌دهنده یافت نشد.", show_alert=True)
            return
        
        # Block the requester
        success = await block_user(db_session, user.id, requester_id)
        
        if success:
            # Notify requester (optional)
            bot = Bot(token=settings.BOT_TOKEN)
            try:
                await bot.send_message(
                    requester.telegram_id,
                    f"🚫 شما توسط {get_display_name(user)} بلاک شدید."
                )
                await bot.session.close()
            except Exception:
                pass
            
            # Remove keyboard from message (if possible)
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            
            # Show popup notification
            await callback.answer(f"🚫 {get_display_name(requester)} بلاک شد", show_alert=True)
        else:
            await callback.answer("❌ خطا در بلاک کردن.", show_alert=True)
        break

