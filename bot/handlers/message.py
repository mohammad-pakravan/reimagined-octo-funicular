"""
Message handler for the bot.
Handles forwarding messages between chat partners.
"""
import re
from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ContentType
from aiogram.fsm.context import FSMContext

from db.database import get_db
from db.crud import get_user_by_telegram_id, check_user_premium, spend_points, get_user_points
from core.chat_manager import ChatManager
from utils.rate_limiter import MessageRateLimiter
from config.settings import settings

router = Router()

# Global instances
chat_manager = None
rate_limiter = None

# Default cost per message for non-premium users (in coins)
DEFAULT_CHAT_MESSAGE_COST = 1


def set_chat_manager(manager: ChatManager):
    """Set chat manager instance."""
    global chat_manager
    chat_manager = manager


def set_rate_limiter(limiter: MessageRateLimiter):
    """Set rate limiter instance."""
    global rate_limiter
    rate_limiter = limiter


def contains_link(text: str) -> bool:
    """Check if text contains a URL/link."""
    if not text:
        return False
    # Pattern to match URLs (http, https, www, or common domains)
    url_pattern = r'(https?://|www\.|t\.me/|telegram\.me/|bit\.ly/|tinyurl\.com/)'
    return bool(re.search(url_pattern, text, re.IGNORECASE))


def contains_mention(text: str) -> bool:
    """Check if text contains @ mention."""
    if not text:
        return False
    # Pattern to match @ mentions
    return '@' in text


@router.message(F.content_type.in_({ContentType.TEXT, ContentType.VOICE, ContentType.PHOTO, ContentType.VIDEO, ContentType.STICKER, ContentType.ANIMATION}))
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
        
        # Check for links and @ mentions in text messages and captions
        text_to_check = message.text or message.caption
        if text_to_check:
            if contains_link(text_to_check):
                await message.answer("❌ ارسال لینک در چت مجاز نیست.")
                return
            
            if contains_mention(text_to_check):
                await message.answer("❌ ارسال @ و ID در چت مجاز نیست.")
                return
        
        # Get chat room to track message counts
        from db.crud import get_active_chat_room_by_user
        chat_room = await get_active_chat_room_by_user(db_session, user.id)
        if not chat_room:
            await message.answer("❌ چت فعالی یافت نشد.")
            return
        
        # Get partner ID
        partner_id = await chat_manager.get_partner_id(user.id, db_session)
        if not partner_id:
            await message.answer("❌ هم‌چت شما یافت نشد.")
            return
        
        # Get private mode status for this user
        private_mode = await chat_manager.get_private_mode(chat_room.id, user.id)
        
        # Increment message count for this user
        user_message_count = await chat_manager.increment_message_count(chat_room.id, user.id)
        
        # Get message counts for both users
        user1_count, user2_count = await chat_manager.get_chat_message_counts(
            chat_room.id,
            chat_room.user1_id,
            chat_room.user2_id
        )
        
        # Determine which user is which
        if chat_room.user1_id == user.id:
            current_user_count = user1_count
            partner_user_count = user2_count
        else:
            current_user_count = user2_count
            partner_user_count = user1_count
        
        # No coin deduction in message handler - coins are deducted at chat start
        # We only track message counts for success determination
        
        # Get partner's Telegram ID
        partner_telegram_id = await chat_manager.get_partner_telegram_id(user.id, db_session)
        
        if not partner_telegram_id:
            # Decrement message count since we can't send
            await chat_manager.redis.decr(chat_manager._get_message_count_key(chat_room.id, user.id))
            
            await message.answer("❌ هم‌چت شما یافت نشد. لطفاً دوباره چت را شروع کنید.")
            return
        
        # Forward message based on type
        try:
            from aiogram import Bot
            bot = Bot(token=settings.BOT_TOKEN)
            
            sent_message = None
            
            if message.text:
                # Forward text message with protect_content based on user's private mode
                sent_message = await bot.send_message(
                    partner_telegram_id,
                    message.text,
                    protect_content=private_mode
                )
            elif message.voice:
                # Forward voice message (using file_id) with protect_content based on user's private mode
                sent_message = await bot.send_voice(
                    partner_telegram_id,
                    voice=message.voice.file_id,
                    protect_content=private_mode
                )
            elif message.photo:
                # Forward photo (using file_id) with protect_content based on user's private mode
                sent_message = await bot.send_photo(
                    partner_telegram_id,
                    photo=message.photo[-1].file_id,
                    caption=message.caption,
                    protect_content=private_mode
                )
            elif message.video:
                # Forward video (using file_id) with protect_content based on user's private mode
                sent_message = await bot.send_video(
                    partner_telegram_id,
                    video=message.video.file_id,
                    caption=message.caption,
                    protect_content=private_mode
                )
            elif message.sticker:
                # Forward sticker (using file_id) with protect_content based on user's private mode
                sent_message = await bot.send_sticker(
                    partner_telegram_id,
                    sticker=message.sticker.file_id,
                    protect_content=private_mode
                )
            elif message.animation:
                # Forward GIF/animation (using file_id) with protect_content based on user's private mode
                sent_message = await bot.send_animation(
                    partner_telegram_id,
                    animation=message.animation.file_id,
                    caption=message.caption,
                    protect_content=private_mode
                )
            
            # Store message ID for deletion after chat ends
            # Store for both users: the sent message for partner, and the original message for user
            if sent_message and sent_message.message_id:
                # Get partner's database ID (get_user_by_telegram_id is already imported at the top)
                partner_db_user = await get_user_by_telegram_id(db_session, partner_telegram_id)
                if partner_db_user:
                    # Store sent message ID for partner (the message they received)
                    await chat_manager.add_message_id(chat_room.id, partner_db_user.id, sent_message.message_id)
                    
                    # Store message pair mapping (user_msg_id -> partner_msg_id) for deletion
                    if message.message_id:
                        await chat_manager.redis.setex(
                            chat_manager._get_message_pair_key(chat_room.id, message.message_id),
                            604800,  # 7 days TTL
                            str(sent_message.message_id)
                        )
            
            # Also store the original message ID for the sender (user)
            if message.message_id:
                await chat_manager.add_message_id(chat_room.id, user.id, message.message_id)
            
            await bot.session.close()
            
        except Exception as e:
            # If message sending fails, decrement message count
            await chat_manager.redis.decr(chat_manager._get_message_count_key(chat_room.id, user.id))
            
            await message.answer(f"❌ خطا در ارسال پیام: {str(e)}\n\nلطفاً دوباره تلاش کنید.")
        
        break

