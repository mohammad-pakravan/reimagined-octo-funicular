"""
Message handler for the bot.
Handles forwarding messages between chat partners.
"""
import re
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, MessageReactionUpdated, Update
from aiogram.enums import ContentType
from aiogram.fsm.context import FSMContext

from db.database import get_db
from db.crud import get_user_by_telegram_id, check_user_premium, spend_points, get_user_points
from core.chat_manager import ChatManager
from utils.rate_limiter import MessageRateLimiter
from config.settings import settings

router = Router()
logger = logging.getLogger(__name__)

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


@router.message(F.audio | (F.forward_from_chat & F.audio))
async def handle_music_message(message: Message, state: FSMContext):
    """Handle music messages (audio files) and show add-to-playlist button.
    
    Note: Voice messages (ContentType.VOICE) are handled by forward_message
    to be forwarded in active chats, not treated as music.
    """
    from bot.handlers.registration import RegistrationStates
    from bot.keyboards.playlist import get_add_to_playlist_keyboard
    
    # Skip if user is in registration state or DM state
    current_state = await state.get_state()
    if current_state in [
        RegistrationStates.waiting_age,
        RegistrationStates.waiting_city,
        RegistrationStates.waiting_province,
        RegistrationStates.waiting_display_name,
        RegistrationStates.waiting_photo,
        RegistrationStates.waiting_gender
    ] or current_state == "dm:waiting_message" or current_state == "dm:waiting_reply":
        return
    
    user_id = message.from_user.id
    
    # Check if this is a music message (audio file, not voice message)
    is_music = False
    file_id = None
    
    if message.audio:
        is_music = True
        file_id = message.audio.file_id
    elif message.forward_from_chat and message.audio:
        is_music = True
        file_id = message.audio.file_id
    
    if not is_music or not file_id:
        return
    
    # Only show button if user is not in active chat (to avoid interfering with chat forwarding)
    # Or show it after a short delay to not interfere with message forwarding
    if chat_manager:
        async for db_session in get_db():
            from db.crud import get_user_by_telegram_id
            user = await get_user_by_telegram_id(db_session, user_id)
            if user and await chat_manager.is_chat_active(user.id, db_session):
                # User is in chat, return to let forward_message handler process it
                # This allows voice messages to be forwarded properly
                return
            
            # User is not in chat, show button
            try:
                await message.reply(
                    "💡 می‌خواهی این موزیک را به پلی‌لیست خود اضافه کنی؟",
                    reply_markup=get_add_to_playlist_keyboard(message.message_id, file_id)
                )
            except Exception as e:
                logger.error(f"Error showing add-to-playlist button: {e}")
            return  # Return after showing button to prevent further processing
    else:
        # No chat manager, show button anyway
        try:
            await message.reply(
                "💡 می‌خواهی این موزیک را به پلی‌لیست خود اضافه کنی؟",
                reply_markup=get_add_to_playlist_keyboard(message.message_id, file_id)
            )
        except Exception as e:
            logger.error(f"Error showing add-to-playlist button: {e}")
        return  # Return after showing button


@router.message(F.reply_to_message & F.content_type.in_({ContentType.TEXT, ContentType.VOICE, ContentType.PHOTO, ContentType.VIDEO, ContentType.VIDEO_NOTE, ContentType.STICKER, ContentType.ANIMATION}))
async def handle_reply_message(message: Message, state: FSMContext):
    """Handle reply messages - forward reply to chat partner with reply context."""
    logger.info(f"Received reply message: message_id={message.message_id}, user_id={message.from_user.id}, reply_to={message.reply_to_message.message_id if message.reply_to_message else None}")
    
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
        
        # Check for links and @ mentions
        text_to_check = message.text or message.caption
        if text_to_check:
            if contains_link(text_to_check):
                await message.answer("❌ ارسال لینک در چت مجاز نیست.")
                return
            
            if contains_mention(text_to_check):
                await message.answer("❌ ارسال @ و ID در چت مجاز نیست.")
                return
        
        # Get chat room
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
        
        # Check if partner is a virtual profile - don't send messages to virtual profiles
        from db.crud import get_user_by_id
        partner = await get_user_by_id(db_session, partner_id)
        if partner and partner.is_virtual:
            # Silently ignore messages to virtual profiles - simulate that they're not responding
            return
        
        # Get partner's Telegram ID
        partner_telegram_id = await chat_manager.get_partner_telegram_id(user.id, db_session)
        if not partner_telegram_id:
            await message.answer("❌ هم‌چت شما یافت نشد. لطفاً دوباره چت را شروع کنید.")
            return
        
        # Get the message being replied to
        if not message.reply_to_message or not message.reply_to_message.message_id:
            # If no reply, treat as normal message
            logger.warning("No reply_to_message found")
            return
        
        replied_to_msg_id = message.reply_to_message.message_id
        logger.info(f"Looking for partner message for replied message: {replied_to_msg_id}")
        
        # Get partner's message ID for the replied message
        # When user replies, replied_to_msg_id is the message_id in user's chat
        # We need to find the corresponding message_id in partner's chat
        
        # First, check if this is user's own message (direct mapping)
        message_pair_key = chat_manager._get_message_pair_key(chat_room.id, replied_to_msg_id)
        partner_replied_msg_id_raw = await chat_manager.redis.get(message_pair_key)
        
        if partner_replied_msg_id_raw:
            # Found: this is user's message, get partner's message
            partner_replied_msg_id = int(partner_replied_msg_id_raw.decode() if isinstance(partner_replied_msg_id_raw, bytes) else partner_replied_msg_id_raw)
            logger.info(f"Found partner message via direct mapping: {partner_replied_msg_id} for user message {replied_to_msg_id}")
        else:
            # Check reverse mapping: maybe this is partner's message in user's chat
            # If replied_to_msg_id is partner's message in user's chat, we need to find:
            # 1. User's original message (via reverse mapping)
            # 2. Then partner's message from user's original message
            reverse_key = chat_manager._get_message_pair_key(chat_room.id, replied_to_msg_id)
            user_original_msg_id_raw = await chat_manager.redis.get(reverse_key)
            
            if user_original_msg_id_raw:
                # This is partner's message in user's chat
                # When partner sends message P2, we forward it to user as U2
                # We store: P2 -> U2 (partner's original -> user's received)
                # We store: U2 -> P2 (reverse: user's received -> partner's original)
                # So if user replies to U2, reverse mapping U2 -> P2 gives us partner's original message_id
                # We should use P2 as reply_to_message_id
                partner_replied_msg_id = int(user_original_msg_id_raw.decode() if isinstance(user_original_msg_id_raw, bytes) else user_original_msg_id_raw)
                logger.info(f"Found partner message via reverse mapping: {partner_replied_msg_id} (this is partner's original message_id for replied_to_msg_id={replied_to_msg_id})")
            else:
                logger.warning(f"Partner message not found for reply: chat_room_id={chat_room.id}, replied_to_msg_id={replied_to_msg_id}, key={message_pair_key}")
                partner_replied_msg_id = None
        
        # Get private mode status
        private_mode = await chat_manager.get_private_mode(chat_room.id, user.id)
        
        # Increment message count
        await chat_manager.increment_message_count(chat_room.id, user.id)
        
        # Forward message with reply
        try:
            bot = Bot(token=settings.BOT_TOKEN)
            
            sent_message = None
            reply_to_id = None
            if partner_replied_msg_id:
                if isinstance(partner_replied_msg_id, bytes):
                    reply_to_id = int(partner_replied_msg_id.decode())
                elif isinstance(partner_replied_msg_id, (int, str)):
                    reply_to_id = int(partner_replied_msg_id)
            logger.info(f"Sending reply message: reply_to_id={reply_to_id}, partner_replied_msg_id={partner_replied_msg_id}, replied_to_msg_id={replied_to_msg_id}")
            
            if message.text:
                sent_message = await bot.send_message(
                    partner_telegram_id,
                    message.text,
                    reply_to_message_id=reply_to_id,
                    protect_content=private_mode
                )
            elif message.voice:
                sent_message = await bot.send_voice(
                    partner_telegram_id,
                    voice=message.voice.file_id,
                    reply_to_message_id=reply_to_id,
                    protect_content=private_mode
                )
            elif message.photo:
                # Forward photo with support for self-destructing media (has_media_spoiler)
                sent_message = await bot.send_photo(
                    partner_telegram_id,
                    photo=message.photo[-1].file_id,
                    caption=message.caption,
                    reply_to_message_id=reply_to_id,
                    protect_content=private_mode,
                    has_spoiler=getattr(message, 'has_media_spoiler', False) or False
                )
            elif message.video:
                # Forward video with support for self-destructing media (has_media_spoiler)
                sent_message = await bot.send_video(
                    partner_telegram_id,
                    video=message.video.file_id,
                    caption=message.caption,
                    reply_to_message_id=reply_to_id,
                    protect_content=private_mode,
                    has_spoiler=getattr(message, 'has_media_spoiler', False) or False
                )
            elif message.sticker:
                sent_message = await bot.send_sticker(
                    partner_telegram_id,
                    sticker=message.sticker.file_id,
                    reply_to_message_id=reply_to_id,
                    protect_content=private_mode
                )
            elif message.animation:
                sent_message = await bot.send_animation(
                    partner_telegram_id,
                    animation=message.animation.file_id,
                    caption=message.caption,
                    reply_to_message_id=reply_to_id,
                    protect_content=private_mode
                )
            elif message.video_note:
                # Forward video note (round video message)
                sent_message = await bot.send_video_note(
                    partner_telegram_id,
                    video_note=message.video_note.file_id,
                    reply_to_message_id=reply_to_id,
                    protect_content=private_mode
                )
            
            # Store message mapping (bidirectional)
            if sent_message and sent_message.message_id:
                partner_db_user = await get_user_by_telegram_id(db_session, partner_telegram_id)
                if partner_db_user:
                    await chat_manager.add_message_id(chat_room.id, partner_db_user.id, sent_message.message_id)
                    
                    if message.message_id:
                        # Store mapping: user_msg_id -> partner_msg_id
                        await chat_manager.redis.setex(
                            chat_manager._get_message_pair_key(chat_room.id, message.message_id),
                            604800,
                            str(sent_message.message_id)
                        )
                        # Store reverse mapping: partner_msg_id -> user_msg_id
                        await chat_manager.redis.setex(
                            chat_manager._get_message_pair_key(chat_room.id, sent_message.message_id),
                            604800,
                            str(message.message_id)
                        )
            
            if message.message_id:
                await chat_manager.add_message_id(chat_room.id, user.id, message.message_id)
            
            await bot.session.close()
        except Exception as e:
            await chat_manager.redis.decr(chat_manager._get_message_count_key(chat_room.id, user.id))
            await message.answer(f"❌ خطا در ارسال پیام: {str(e)}\n\nلطفاً دوباره تلاش کنید.")
        
        break


@router.message(F.content_type.in_({ContentType.TEXT, ContentType.VOICE, ContentType.PHOTO, ContentType.VIDEO, ContentType.VIDEO_NOTE, ContentType.STICKER, ContentType.ANIMATION}))
async def forward_message(message: Message, state: FSMContext):
    """Forward message to chat partner."""
    # Skip dice messages - let game handler process them
    if message.dice:
        return
    
    # Skip if user is in registration state or DM state
    from bot.handlers.registration import RegistrationStates
    current_state = await state.get_state()
    if current_state in [
        RegistrationStates.waiting_age,
        RegistrationStates.waiting_city,
        RegistrationStates.waiting_province,
        RegistrationStates.waiting_display_name,
        RegistrationStates.waiting_photo,
        RegistrationStates.waiting_gender
    ] or current_state == "dm:waiting_message" or current_state == "dm:waiting_reply":
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
        
        # Skip check for "🔍 جستجوی کاربران" button - it doesn't require active chat
        if message.text == "🔍 جستجوی کاربران":
            return  # Let reply handler process it
        
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
        
        # Check if partner is a virtual profile - don't send messages to virtual profiles
        from db.crud import get_user_by_id
        partner = await get_user_by_id(db_session, partner_id)
        if partner and partner.is_virtual:
            # Silently ignore messages to virtual profiles - simulate that they're not responding
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
                # Support for self-destructing media (has_media_spoiler)
                sent_message = await bot.send_photo(
                    partner_telegram_id,
                    photo=message.photo[-1].file_id,
                    caption=message.caption,
                    protect_content=private_mode,
                    has_spoiler=getattr(message, 'has_media_spoiler', False) or False
                )
            elif message.video:
                # Forward video (using file_id) with protect_content based on user's private mode
                # Support for self-destructing media (has_media_spoiler)
                # Note: Timed media effects are preserved automatically by Telegram when using file_id
                sent_message = await bot.send_video(
                    partner_telegram_id,
                    video=message.video.file_id,
                    caption=message.caption,
                    protect_content=private_mode,
                    has_spoiler=getattr(message, 'has_media_spoiler', False) or False
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
            elif message.video_note:
                # Forward video note (round video message)
                sent_message = await bot.send_video_note(
                    partner_telegram_id,
                    video_note=message.video_note.file_id,
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
                    
                    # Store message pair mapping (bidirectional) for deletion, edit, reaction, reply
                    if message.message_id:
                        # Store mapping: user_msg_id -> partner_msg_id
                        await chat_manager.redis.setex(
                            chat_manager._get_message_pair_key(chat_room.id, message.message_id),
                            604800,  # 7 days TTL
                            str(sent_message.message_id)
                        )
                        # Store reverse mapping: partner_msg_id -> user_msg_id
                        await chat_manager.redis.setex(
                            chat_manager._get_message_pair_key(chat_room.id, sent_message.message_id),
                            604800,  # 7 days TTL
                            str(message.message_id)
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


@router.edited_message()
async def handle_edited_message(message: Message):
    """Handle edited messages - forward edit to chat partner."""
    logger.info(f"Received edited message: message_id={message.message_id}, user_id={message.from_user.id}")
    
    if not chat_manager:
        logger.warning("chat_manager is None")
        return
    
    user_id = message.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            logger.warning(f"User not found: {user_id}")
            return
        
        # Check if user has active chat
        is_admin = user_id in settings.ADMIN_IDS
        if not is_admin and not await chat_manager.is_chat_active(user.id, db_session):
            logger.info(f"User {user_id} has no active chat")
            return
        
        # For admin users without active chat, just return silently
        if is_admin and not await chat_manager.is_chat_active(user.id, db_session):
            return
        
        # Get chat room
        from db.crud import get_active_chat_room_by_user
        chat_room = await get_active_chat_room_by_user(db_session, user.id)
        if not chat_room:
            logger.warning(f"Chat room not found for user {user_id}")
            return
        
        # Get partner's Telegram ID
        partner_telegram_id = await chat_manager.get_partner_telegram_id(user.id, db_session)
        if not partner_telegram_id:
            logger.warning(f"Partner telegram ID not found for user {user_id}")
            return
        
        # Get partner's message ID from mapping
        # When user edits a message, we need to find the corresponding message on partner's side
        message_pair_key = chat_manager._get_message_pair_key(chat_room.id, message.message_id)
        partner_msg_id_raw = await chat_manager.redis.get(message_pair_key)
        
        if partner_msg_id_raw:
            # Found direct mapping: this is user's message, get partner's message
            partner_msg_id = int(partner_msg_id_raw.decode() if isinstance(partner_msg_id_raw, bytes) else partner_msg_id_raw)
            logger.info(f"Found partner message via direct mapping: {partner_msg_id} for user message {message.message_id}")
        else:
            # Check if this is partner's message (reverse mapping)
            reverse_key = chat_manager._get_message_pair_key(chat_room.id, message.message_id)
            user_original_msg_id_raw = await chat_manager.redis.get(reverse_key)
            if user_original_msg_id_raw:
                # This is partner's message ID, find the user's original message
                user_original_msg_id = int(user_original_msg_id_raw.decode() if isinstance(user_original_msg_id_raw, bytes) else user_original_msg_id_raw)
                # Now get partner's message from user's original message
                original_key = chat_manager._get_message_pair_key(chat_room.id, user_original_msg_id)
                partner_msg_id_raw = await chat_manager.redis.get(original_key)
                if partner_msg_id_raw:
                    partner_msg_id = int(partner_msg_id_raw.decode() if isinstance(partner_msg_id_raw, bytes) else partner_msg_id_raw)
                    logger.info(f"Found partner message via reverse mapping: {partner_msg_id} for user message {message.message_id}")
                else:
                    logger.warning(f"Could not find partner message via reverse mapping: chat_room_id={chat_room.id}, message_id={message.message_id}")
                    return
            else:
                logger.warning(f"Message pair not found: chat_room_id={chat_room.id}, message_id={message.message_id}, key={message_pair_key}")
                return
        
        partner_msg_id = int(partner_msg_id) if not isinstance(partner_msg_id, int) else partner_msg_id
        logger.info(f"Using partner message ID: {partner_msg_id} for edit on user message {message.message_id}")
        
        # Edit the partner's message
        try:
            bot = Bot(token=settings.BOT_TOKEN)
            
            if message.text:
                logger.info(f"Editing text message: partner_msg_id={partner_msg_id}, text={message.text[:50]}")
                await bot.edit_message_text(
                    chat_id=partner_telegram_id,
                    message_id=partner_msg_id,
                    text=message.text
                )
            elif message.caption is not None:
                # For media messages, edit caption
                logger.info(f"Editing caption: partner_msg_id={partner_msg_id}, caption={message.caption[:50]}")
                if message.photo:
                    await bot.edit_message_caption(
                        chat_id=partner_telegram_id,
                        message_id=partner_msg_id,
                        caption=message.caption
                    )
                elif message.video:
                    await bot.edit_message_caption(
                        chat_id=partner_telegram_id,
                        message_id=partner_msg_id,
                        caption=message.caption
                    )
                elif message.animation:
                    await bot.edit_message_caption(
                        chat_id=partner_telegram_id,
                        message_id=partner_msg_id,
                        caption=message.caption
                    )
            
            await bot.session.close()
            logger.info(f"Successfully edited message: partner_msg_id={partner_msg_id}")
        except Exception as e:
            logger.error(f"Failed to edit message: {e}", exc_info=True)
        
        break


@router.message_reaction()
async def handle_message_reaction(update: MessageReactionUpdated):
    """Handle message reactions - forward reaction to chat partner."""
    logger.info(f"Received message reaction: message_id={update.message_id}, user_id={update.user.id}, new_reaction={update.new_reaction}, old_reaction={update.old_reaction}")
    
    if not chat_manager:
        logger.warning("chat_manager is None")
        return
    
    user_id = update.user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            logger.warning(f"User not found: {user_id}")
            return
        
        # Check if user has active chat
        is_admin = user_id in settings.ADMIN_IDS
        if not is_admin and not await chat_manager.is_chat_active(user.id, db_session):
            logger.info(f"User {user_id} has no active chat")
            return
        
        # For admin users without active chat, just return silently
        if is_admin and not await chat_manager.is_chat_active(user.id, db_session):
            return
        
        # Get chat room
        from db.crud import get_active_chat_room_by_user
        chat_room = await get_active_chat_room_by_user(db_session, user.id)
        if not chat_room:
            logger.warning(f"Chat room not found for user {user_id}")
            return
        
        # Get partner's Telegram ID
        partner_telegram_id = await chat_manager.get_partner_telegram_id(user.id, db_session)
        if not partner_telegram_id:
            logger.warning(f"Partner telegram ID not found for user {user_id}")
            return
        
        # Get partner's message ID from mapping
        # When user reacts to a message, we need to find the corresponding message on partner's side
        # If user reacts to their own message, we need partner's message
        # If user reacts to partner's message, we need user's original message (to apply reaction on partner's message)
        message_pair_key = chat_manager._get_message_pair_key(chat_room.id, update.message_id)
        partner_msg_id_raw = await chat_manager.redis.get(message_pair_key)
        
        if partner_msg_id_raw:
            # Found direct mapping: this is user's message, get partner's message
            partner_msg_id = int(partner_msg_id_raw.decode() if isinstance(partner_msg_id_raw, bytes) else partner_msg_id_raw)
            logger.info(f"Found partner message via direct mapping: {partner_msg_id} for user message {update.message_id}")
        else:
            # Check if this is partner's message (reverse mapping)
            # If user reacts to partner's message, we need to find user's original message first
            # Then get partner's message from that
            reverse_key = chat_manager._get_message_pair_key(chat_room.id, update.message_id)
            user_original_msg_id_raw = await chat_manager.redis.get(reverse_key)
            if user_original_msg_id_raw:
                # This is partner's message ID, find the user's original message
                user_original_msg_id = int(user_original_msg_id_raw.decode() if isinstance(user_original_msg_id_raw, bytes) else user_original_msg_id_raw)
                # Now get partner's message from user's original message
                original_key = chat_manager._get_message_pair_key(chat_room.id, user_original_msg_id)
                partner_msg_id_raw = await chat_manager.redis.get(original_key)
                if partner_msg_id_raw:
                    partner_msg_id = int(partner_msg_id_raw.decode() if isinstance(partner_msg_id_raw, bytes) else partner_msg_id_raw)
                    logger.info(f"Found partner message via reverse mapping: {partner_msg_id} for user message {update.message_id}")
                else:
                    logger.warning(f"Could not find partner message via reverse mapping: chat_room_id={chat_room.id}, message_id={update.message_id}")
                    return
            else:
                logger.warning(f"Message pair not found: chat_room_id={chat_room.id}, message_id={update.message_id}, key={message_pair_key}")
                return
        
        partner_msg_id = int(partner_msg_id) if not isinstance(partner_msg_id, int) else partner_msg_id
        logger.info(f"Using partner message ID: {partner_msg_id} for reaction on user message {update.message_id}")
        
        # Forward reaction to partner's message
        try:
            bot = Bot(token=settings.BOT_TOKEN)
            
            # Set reactions on partner's message
            from aiogram.types import ReactionTypeEmoji
            
            if update.new_reaction:
                # Add reaction - convert to list of ReactionTypeEmoji
                reactions = []
                for r in update.new_reaction:
                    if hasattr(r, 'emoji') and r.emoji:
                        reactions.append(ReactionTypeEmoji(emoji=r.emoji))
                    elif isinstance(r, str):
                        reactions.append(ReactionTypeEmoji(emoji=r))
                    elif hasattr(r, 'type') and r.type == 'emoji' and hasattr(r, 'emoji'):
                        reactions.append(ReactionTypeEmoji(emoji=r.emoji))
                
                if reactions:
                    logger.info(f"Setting reactions: partner_msg_id={partner_msg_id}, reactions={[r.emoji for r in reactions]}")
                    await bot.set_message_reaction(
                        chat_id=partner_telegram_id,
                        message_id=partner_msg_id,
                        reaction=reactions
                    )
            elif update.old_reaction:
                # Remove reaction
                logger.info(f"Removing reaction: partner_msg_id={partner_msg_id}")
                await bot.set_message_reaction(
                    chat_id=partner_telegram_id,
                    message_id=partner_msg_id,
                    reaction=None
                )
            
            await bot.session.close()
            logger.info(f"Successfully set reaction: partner_msg_id={partner_msg_id}")
        except Exception as e:
            logger.error(f"Failed to set reaction: {e}", exc_info=True)
        
        break


@router.message(
    F.content_type.in_({ContentType.DELETE_CHAT_PHOTO, ContentType.NEW_CHAT_PHOTO})
)
async def handle_deleted_messages(message: Message):
    """Handle deleted messages - delete corresponding message from partner."""
    # Note: Telegram doesn't send delete events for private chats
    # This handler won't be triggered for message deletions
    # We need to use a different approach - maybe via callback query or polling
    pass


# Handler for message deletion via callback or manual trigger
# Since Telegram doesn't send delete events, we'll need to add a delete button to messages
# or use a different mechanism


