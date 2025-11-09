"""
Message handler for the bot.
Handles forwarding messages between chat partners.
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ContentType
from aiogram.fsm.context import FSMContext

from db.database import get_db
from db.crud import get_user_by_telegram_id
from core.chat_manager import ChatManager
from utils.rate_limiter import MessageRateLimiter
from config.settings import settings

router = Router()

# Global instances
chat_manager = None
rate_limiter = None


def set_chat_manager(manager: ChatManager):
    """Set chat manager instance."""
    global chat_manager
    chat_manager = manager


def set_rate_limiter(limiter: MessageRateLimiter):
    """Set rate limiter instance."""
    global rate_limiter
    rate_limiter = limiter


@router.message(F.content_type.in_({ContentType.TEXT, ContentType.VOICE, ContentType.PHOTO, ContentType.VIDEO}))
async def forward_message(message: Message, state: FSMContext):
    """Forward message to chat partner."""
    # Skip if user is in registration state or DM state
    from bot.handlers.registration import RegistrationStates
    current_state = await state.get_state()
    if current_state in [
        RegistrationStates.waiting_age,
        RegistrationStates.waiting_city,
        RegistrationStates.waiting_photo,
        RegistrationStates.waiting_gender
    ] or current_state == "dm:waiting_message":
        return  # Let registration or DM handlers process the message
    
    if not chat_manager:
        return
    
    user_id = message.from_user.id
    
    # Check rate limit
    if rate_limiter:
        is_allowed, remaining = await rate_limiter.check_message_limit(user_id)
        if not is_allowed:
            await message.answer(
                f"⏳ محدودیت ارسال پیام!\n"
                f"لطفاً چند لحظه صبر کنید و دوباره تلاش کنید.\n"
                f"پیام‌های باقی‌مانده: {remaining}"
            )
            return
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        
        if not user:
            return
        
        # Check if user has active chat
        # Skip check for admin users
        is_admin = user_id in settings.ADMIN_IDS
        if not is_admin and not await chat_manager.is_chat_active(user.id, db_session):
            from bot.keyboards.reply import get_main_reply_keyboard
            await message.answer(
                "❌ شما در حال حاضر چت فعالی ندارید.\n\n"
                "💬 برای شروع چت، دکمه «💬 شروع چت» را بزنید.\n\n"
                "برای پیدا کردن یک هم‌چت، باید در صف جستجو قرار بگیرید.",
                reply_markup=get_main_reply_keyboard()
            )
            return
        
        # For admin users without active chat, just return silently
        if is_admin and not await chat_manager.is_chat_active(user.id, db_session):
            return
        
        # Get partner's Telegram ID
        partner_telegram_id = await chat_manager.get_partner_telegram_id(user.id, db_session)
        
        if not partner_telegram_id:
            await message.answer("❌ هم‌چت شما یافت نشد. لطفاً دوباره چت را شروع کنید.")
            return
        
        # Forward message based on type
        try:
            from aiogram import Bot
            bot = Bot(token=settings.BOT_TOKEN)
            
            if message.text:
                # Forward text message
                await bot.send_message(
                    partner_telegram_id,
                    message.text
                )
            elif message.voice:
                # Forward voice message (using file_id)
                await bot.send_voice(
                    partner_telegram_id,
                    voice=message.voice.file_id
                )
            elif message.photo:
                # Forward photo (using file_id)
                await bot.send_photo(
                    partner_telegram_id,
                    photo=message.photo[-1].file_id,
                    caption=message.caption
                )
            elif message.video:
                # Forward video (using file_id)
                await bot.send_video(
                    partner_telegram_id,
                    video=message.video.file_id,
                    caption=message.caption
                )
            
            await bot.session.close()
            
        except Exception as e:
            await message.answer(f"❌ خطا در ارسال پیام: {str(e)}\n\nلطفاً دوباره تلاش کنید.")
        
        break

