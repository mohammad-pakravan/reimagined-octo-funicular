"""
Profile view handler for viewing user profiles via /user_XXXXX command.
Allows users to view profiles without needing an active chat.
"""
import hashlib
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from db.database import get_db
from db.crud import (
    get_user_by_telegram_id,
    get_user_by_profile_id,
    is_liked,
    is_following,
    is_blocked,
    is_chat_end_notification_active,
)
from bot.keyboards.profile import get_profile_keyboard
from bot.keyboards.reply import get_main_reply_keyboard
from utils.validators import get_display_name

router = Router()


@router.message(Command("user"))
async def view_user_profile(message: Message):
    """Handle /user_XXXXX command to view user profile."""
    # Parse profile ID from command text (e.g., "/user_15e1576abc70")
    import re
    match = re.search(r'/user_([a-zA-Z0-9]{12})', message.text)
    
    if not match:
        await message.answer("❌ فرمت صحیح: /user_XXXXX")
        return
    
    profile_id = match.group(1)
    
    user_id = message.from_user.id
    
    async for db_session in get_db():
        # Get current user
        current_user = await get_user_by_telegram_id(db_session, user_id)
        if not current_user:
            await message.answer(
                "❌ پروفایل شما یافت نشد. لطفاً /start را بزنید.",
                reply_markup=get_main_reply_keyboard()
            )
            return
        
        # Get profile user by profile_id
        profile_user = await get_user_by_profile_id(db_session, profile_id)
        
        if not profile_user:
            await message.answer("❌ پروفایل یافت نشد.")
            return
        
        # Check if viewing own profile
        if profile_user.id == current_user.id:
            await message.answer("این پروفایل شما است! از دکمه '📊 پروفایل من' استفاده کنید.")
            return
        
        # Get like, follow, block status
        is_liked_status = await is_liked(db_session, current_user.id, profile_user.id)
        is_following_status = await is_following(db_session, current_user.id, profile_user.id)
        is_blocked_status = await is_blocked(db_session, current_user.id, profile_user.id)
        is_notifying_status = await is_chat_end_notification_active(db_session, current_user.id, profile_user.id)
        
        # Display profile
        gender_map = {"male": "پسر 🧑", "female": "دختر 👩", "other": "سایر"}
        gender_text = gender_map.get(profile_user.gender, profile_user.gender or "تعیین نشده")
        
        # Generate user ID (use existing profile_id or generate)
        user_unique_id = f"/user_{profile_user.profile_id or profile_id}"
        
        # Calculate distance (simplified - based on same province/city)
        distance = "نامشخص"
        if current_user.city and profile_user.city and current_user.province and profile_user.province:
            if current_user.city == profile_user.city:
                distance = "همشهری"
            elif current_user.province == profile_user.province:
                distance = "هم‌استان"
            else:
                distance = "شهرهای مختلف"
        
        profile_text = (
            f"• نام: {get_display_name(profile_user)}\n"
            f"• جنسیت: {gender_text}\n"
            f"• استان: {profile_user.province or 'تعیین نشده'}\n"
            f"• شهر: {profile_user.city or 'تعیین نشده'}\n"
            f"• سن: {profile_user.age or 'تعیین نشده'}\n"
            f"ID: {user_unique_id}\n"
            f"فاصله : {distance}"
        )
        
        # Get profile keyboard
        from bot.keyboards.profile import get_profile_keyboard
        profile_keyboard = get_profile_keyboard(
            partner_id=profile_user.id,
            is_liked=is_liked_status,
            is_following=is_following_status,
            is_blocked=is_blocked_status,
            like_count=profile_user.like_count or 0,
            is_notifying=is_notifying_status
        )
        
        # Send profile with photo if available
        profile_image_url = getattr(profile_user, 'profile_image_url', None)
        if profile_image_url:
            from aiogram import Bot
            from config.settings import settings
            from utils.minio_storage import is_url_accessible_from_internet, download_telegram_file
            import logging
            logger = logging.getLogger(__name__)
            
            bot = Bot(token=settings.BOT_TOKEN)
            try:
                # Check if URL is accessible from internet
                if profile_image_url.startswith(('http://', 'https://')):
                    if not is_url_accessible_from_internet(profile_image_url):
                        # URL is not accessible, download and re-upload
                        try:
                            import aiohttp
                            async with aiohttp.ClientSession() as session:
                                async with session.get(profile_image_url) as resp:
                                    if resp.status == 200:
                                        image_data = await resp.read()
                                        # Send as photo from bytes
                                        from aiogram.types import BufferedInputFile
                                        photo_file = BufferedInputFile(image_data, filename="profile.jpg")
                                        await bot.send_photo(
                                            user_id,
                                            photo_file,
                                            caption=profile_text,
                                            reply_markup=profile_keyboard
                                        )
                                    else:
                                        raise Exception(f"Failed to download image: {resp.status}")
                        except Exception as e:
                            logger.warning(f"Failed to download and send MinIO image: {e}")
                            # Fallback to text only
                            await message.answer(profile_text, reply_markup=profile_keyboard)
                    else:
                        # URL is accessible, use directly
                        await bot.send_photo(
                            user_id,
                            profile_image_url,
                            caption=profile_text,
                            reply_markup=profile_keyboard
                        )
                else:
                    # It's a file_id, use directly
                    await bot.send_photo(
                        user_id,
                        profile_image_url,
                        caption=profile_text,
                        reply_markup=profile_keyboard
                    )
                await bot.session.close()
            except Exception as e:
                logger.error(f"Error sending photo: {e}", exc_info=True)
                # If photo fails, send text only
                await message.answer(profile_text, reply_markup=profile_keyboard)
        else:
            await message.answer(profile_text, reply_markup=profile_keyboard)
        
        break


@router.message(F.text.regexp(r'/user_[a-zA-Z0-9]{12}'))
async def view_user_profile_regex(message: Message):
    """Handle /user_XXXXX pattern via regex."""
    # Extract profile_id from message text
    import re
    match = re.search(r'/user_([a-zA-Z0-9]+)', message.text)
    
    if not match:
        return
    
    profile_id = match.group(1)
    
    user_id = message.from_user.id
    
    async for db_session in get_db():
        # Get current user
        current_user = await get_user_by_telegram_id(db_session, user_id)
        if not current_user:
            await message.answer(
                "❌ پروفایل شما یافت نشد. لطفاً /start را بزنید.",
                reply_markup=get_main_reply_keyboard()
            )
            return
        
        # Get profile user by profile_id
        profile_user = await get_user_by_profile_id(db_session, profile_id)
        
        if not profile_user:
            await message.answer("❌ پروفایل یافت نشد.")
            return
        
        # Check if viewing own profile
        if profile_user.id == current_user.id:
            await message.answer("این پروفایل شما است! از دکمه '📊 پروفایل من' استفاده کنید.")
            return
        
        # Get like, follow, block status
        is_liked_status = await is_liked(db_session, current_user.id, profile_user.id)
        is_following_status = await is_following(db_session, current_user.id, profile_user.id)
        is_blocked_status = await is_blocked(db_session, current_user.id, profile_user.id)
        is_notifying_status = await is_chat_end_notification_active(db_session, current_user.id, profile_user.id)
        
        # Display profile
        gender_map = {"male": "پسر 🧑", "female": "دختر 👩", "other": "سایر"}
        gender_text = gender_map.get(profile_user.gender, profile_user.gender or "تعیین نشده")
        
        # Generate user ID
        user_unique_id = f"/user_{profile_user.profile_id or profile_id}"
        
        # Calculate distance
        distance = "نامشخص"
        if current_user.city and profile_user.city and current_user.province and profile_user.province:
            if current_user.city == profile_user.city:
                distance = "همشهری"
            elif current_user.province == profile_user.province:
                distance = "هم‌استان"
            else:
                distance = "شهرهای مختلف"
        
        profile_text = (
            f"• نام: {get_display_name(profile_user)}\n"
            f"• جنسیت: {gender_text}\n"
            f"• استان: {profile_user.province or 'تعیین نشده'}\n"
            f"• شهر: {profile_user.city or 'تعیین نشده'}\n"
            f"• سن: {profile_user.age or 'تعیین نشده'}\n"
            f"ID: {user_unique_id}\n"
            f"فاصله : {distance}"
        )
        
        # Get profile keyboard
        from bot.keyboards.profile import get_profile_keyboard
        profile_keyboard = get_profile_keyboard(
            partner_id=profile_user.id,
            is_liked=is_liked_status,
            is_following=is_following_status,
            is_blocked=is_blocked_status,
            like_count=profile_user.like_count or 0,
            is_notifying=is_notifying_status
        )
        
        # Send profile with photo if available
        profile_image_url = getattr(profile_user, 'profile_image_url', None)
        if profile_image_url:
            from aiogram import Bot
            from config.settings import settings
            from utils.minio_storage import is_url_accessible_from_internet
            import logging
            logger = logging.getLogger(__name__)
            
            bot = Bot(token=settings.BOT_TOKEN)
            try:
                # Check if URL is accessible from internet
                if profile_image_url.startswith(('http://', 'https://')):
                    if not is_url_accessible_from_internet(profile_image_url):
                        # URL is not accessible, download and re-upload
                        try:
                            import aiohttp
                            async with aiohttp.ClientSession() as session:
                                async with session.get(profile_image_url) as resp:
                                    if resp.status == 200:
                                        image_data = await resp.read()
                                        # Send as photo from bytes
                                        from aiogram.types import BufferedInputFile
                                        photo_file = BufferedInputFile(image_data, filename="profile.jpg")
                                        await bot.send_photo(
                                            user_id,
                                            photo_file,
                                            caption=profile_text,
                                            reply_markup=profile_keyboard
                                        )
                                    else:
                                        raise Exception(f"Failed to download image: {resp.status}")
                        except Exception as e:
                            logger.warning(f"Failed to download and send MinIO image: {e}")
                            # Fallback to text only
                            await message.answer(profile_text, reply_markup=profile_keyboard)
                    else:
                        # URL is accessible, use directly
                        await bot.send_photo(
                            user_id,
                            profile_image_url,
                            caption=profile_text,
                            reply_markup=profile_keyboard
                        )
                else:
                    # It's a file_id, use directly
                    await bot.send_photo(
                        user_id,
                        profile_image_url,
                        caption=profile_text,
                        reply_markup=profile_keyboard
                    )
                await bot.session.close()
            except Exception as e:
                logger.error(f"Error sending photo: {e}", exc_info=True)
                await message.answer(profile_text, reply_markup=profile_keyboard)
        else:
            await message.answer(profile_text, reply_markup=profile_keyboard)
        
        break

