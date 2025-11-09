"""
Call request handlers.
Handles accepting and rejecting video/voice call requests.
"""
import os
import aiohttp
from aiogram import Router, F
from aiogram.types import CallbackQuery

from db.database import get_db
from db.crud import get_user_by_telegram_id, get_user_by_id
from bot.keyboards.reply import get_chat_reply_keyboard
from core.chat_manager import ChatManager
from config.settings import settings

router = Router()

chat_manager = None


def set_chat_manager(manager: ChatManager):
    """Set chat manager instance."""
    global chat_manager
    chat_manager = manager


@router.callback_query(F.data.startswith("call:accept:"))
async def accept_call_request(callback: CallbackQuery):
    """Accept call request (video or voice)."""
    # Parse callback data: call:accept:video:{caller_id} or call:accept:voice:{caller_id}
    parts = callback.data.split(":")
    call_type = parts[2]  # 'video' or 'voice'
    caller_id = int(parts[3])
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        caller = await get_user_by_id(db_session, caller_id)
        if not caller:
            await callback.answer("❌ درخواست‌دهنده یافت نشد.", show_alert=True)
            return
        
        # Check if user has active chat with caller
        if not chat_manager or not await chat_manager.is_chat_active(user.id, db_session):
            await callback.answer("❌ شما در حال حاضر یک چت فعال ندارید!", show_alert=True)
            return
        
        partner_id = await chat_manager.get_partner_id(user.id, db_session)
        if partner_id != caller_id:
            await callback.answer("❌ این درخواست برای شما نیست.", show_alert=True)
            return
        
        # Create call room and generate tokens
        from aiogram import Bot
        import aiohttp
        import json
        
        bot = Bot(token=settings.BOT_TOKEN)
        call_type_text = "تصویری" if call_type == "video" else "صوتی"
        call_icon = "📹" if call_type == "video" else "📞"
        
        try:
            # Get chat room ID
            from db.crud import get_active_chat_room_by_user
            chat_room = await get_active_chat_room_by_user(db_session, user.id)
            if not chat_room:
                await callback.answer("❌ چت فعالی یافت نشد.", show_alert=True)
                return
            
            # Create video call room via API
            # Use container name in Docker, localhost in development
            api_host = os.getenv("VIDEO_CALL_API_URL", "http://localhost:8000").replace("http://", "").replace("https://", "").split(":")[0]
            if not api_host or api_host == "localhost" or api_host.startswith("127.0.0.1"):
                api_host = "localhost"
                api_base = f"http://{api_host}:{settings.API_PORT}"
            else:
                # In Docker, use container name
                api_base = f"http://bot:{settings.API_PORT}"
            
            api_url = f"{api_base}/api/video-call/create"
            headers = {
                "X-API-Key": settings.API_SECRET_KEY,
                "Content-Type": "application/json"
            }
            payload = {
                "user1_id": caller.id,
                "user2_id": user.id,
                "chat_room_id": chat_room.id,
                "call_type": call_type
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, headers=headers, json=payload) as response:
                    if response.status != 200:
                        raise Exception("Failed to create call room")
                    room_data = await response.json()
                    room_id = room_data["room_id"]
                
                # Generate tokens for both users
                tokens_url = f"{api_base}/api/video-call/{room_id}/tokens"
                async with session.post(tokens_url, headers=headers) as tokens_response:
                    if tokens_response.status != 200:
                        raise Exception("Failed to generate tokens")
                    tokens_data = await tokens_response.json()
            
            # Build call links
            base_url = settings.VIDEO_CALL_DOMAIN.rstrip('/')
            caller_link = f"{base_url}/call/{room_id}?token={tokens_data['user1_token']}"
            receiver_link = f"{base_url}/call/{room_id}?token={tokens_data['user2_token']}"
            
            # Create inline keyboard with call link button
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            caller_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"🎥 ورود به تماس {call_type_text}",
                        url=caller_link
                    )
                ]
            ])
            
            receiver_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"🎥 ورود به تماس {call_type_text}",
                        url=receiver_link
                    )
                ]
            ])
            
            # Privacy notice message
            privacy_notice = (
                "\n\n"
                "🔒 حریم خصوصی و امنیت:\n"
                "• ما هیچ اطلاعاتی از تماس شما ذخیره نمی‌کنیم\n"
                "• اتصالات مستقیم (P2P) و رمزگذاری شده هستند\n"
                "• سرور ما فقط برای ارتباط اولیه استفاده می‌شود\n"
                "• به حفظ حریم شخصی خود پایبند باشید\n"
                "• از ضبط یا انتشار محتوای تماس بدون رضایت طرف مقابل خودداری کنید"
            )
            
            # Notify caller
            await bot.send_message(
                caller.telegram_id,
                f"{call_icon} تماس {call_type_text} شما پذیرفته شد!{privacy_notice}",
                reply_markup=caller_keyboard
            )
            
            # Notify receiver
            try:
                await callback.message.edit_text(
                    f"{call_icon} تماس {call_type_text} پذیرفته شد!{privacy_notice}",
                    reply_markup=receiver_keyboard
                )
            except Exception:
                await callback.message.answer(
                    f"{call_icon} تماس {call_type_text} پذیرفته شد!{privacy_notice}",
                    reply_markup=receiver_keyboard
                )
            
            await bot.session.close()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error creating call: {e}")
            try:
                await callback.message.answer(
                    f"{call_icon} تماس {call_type_text} پذیرفته شد!\n\n"
                    "خطا در ایجاد لینک تماس. لطفاً دوباره تلاش کنید.",
                    reply_markup=get_chat_reply_keyboard()
                )
            except:
                pass
        
        await callback.answer(f"✅ تماس {call_type_text} پذیرفته شد!")
        break


@router.callback_query(F.data.startswith("call:reject:"))
async def reject_call_request(callback: CallbackQuery):
    """Reject call request (video or voice)."""
    # Parse callback data: call:reject:video:{caller_id} or call:reject:voice:{caller_id}
    parts = callback.data.split(":")
    call_type = parts[2]  # 'video' or 'voice'
    caller_id = int(parts[3])
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        caller = await get_user_by_id(db_session, caller_id)
        if not caller:
            await callback.answer("❌ درخواست‌دهنده یافت نشد.", show_alert=True)
            return
        
        # Notify caller that call was rejected
        from aiogram import Bot
        bot = Bot(token=settings.BOT_TOKEN)
        
        call_type_text = "تصویری" if call_type == "video" else "صوتی"
        call_icon = "📹" if call_type == "video" else "📞"
        
        try:
            # Notify caller
            await bot.send_message(
                caller.telegram_id,
                f"{call_icon} تماس {call_type_text} شما رد شد.",
                reply_markup=get_chat_reply_keyboard()
            )
            
            # Update receiver's message
            try:
                await callback.message.edit_text(
                    f"❌ تماس {call_type_text} رد شد.",
                    reply_markup=None
                )
            except Exception:
                await callback.message.answer(
                    f"❌ تماس {call_type_text} رد شد.",
                    reply_markup=get_chat_reply_keyboard()
                )
            
            await bot.session.close()
        except Exception:
            try:
                await callback.message.answer(
                    f"❌ تماس {call_type_text} رد شد.",
                    reply_markup=get_chat_reply_keyboard()
                )
            except:
                pass
        
        await callback.answer(f"❌ تماس {call_type_text} رد شد")
        break

