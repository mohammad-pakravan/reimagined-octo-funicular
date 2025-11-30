"""
My profile handler for editing own profile and managing follows/blocks.
"""
from datetime import datetime
from aiogram import Router, F
from aiogram import Bot
from aiogram.types import Message, CallbackQuery, InlineQuery, InlineQueryResult, InlineQueryResultArticle, InputTextMessageContent, InputMessageContent
from config.settings import settings
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db.database import get_db
from db.crud import (
    get_user_by_telegram_id,
    update_user_profile,
    get_following_list,
    get_blocked_list,
    get_liked_list,
    unfollow_user,
    unblock_user,
    unlike_user,
    get_user_by_id,
    delete_user_account,
)
from bot.keyboards.my_profile import (
    get_my_profile_keyboard,
    get_following_list_keyboard,
    get_blocked_list_keyboard,
    get_liked_list_keyboard,
)
from bot.keyboards.notification_settings import get_notification_settings_keyboard
from bot.keyboards.reply import get_main_reply_keyboard
from bot.keyboards.common import get_gender_keyboard, get_delete_account_confirm_keyboard
from utils.validators import validate_age, parse_age, validate_city, get_display_name
from utils.user_activity import get_user_status, format_last_seen
from main import activity_tracker

router = Router()


async def check_and_notify_profile_completion(db_session, user_id: int):
    """Check if profile is complete and notify referrer if needed."""
    from db.crud import get_user_by_telegram_id, get_points_history, get_coins_for_activity
    from core.points_manager import PointsManager
    from config.settings import settings
    
    # Get user
    user = await get_user_by_telegram_id(db_session, user_id)
    if not user:
        return
    
    # Check if profile is complete (username, age, city, profile_image_url)
    profile_complete = (
        user.username and
        user.age and
        user.city and
        user.profile_image_url
    )
    
    if not profile_complete:
        return
    
    # Find referral for this user (get all referrals where this user is referred)
    from sqlalchemy import select
    from db.models import Referral
    result = await db_session.execute(
        select(Referral).where(Referral.referred_id == user.id)
    )
    referrals = result.scalars().all()
    
    if not referrals:
        return
    
    # Use the first referral (should only be one)
    referral = referrals[0]
    
    # Check if we already awarded profile completion
    points_history = await get_points_history(db_session, referral.referrer_id, limit=100)
    already_awarded = any(
        ph.source == "referral_profile_complete" and ph.related_user_id == user.id
        for ph in points_history
    )
    
    # Also check if this telegram_id has received profile completion reward for this referrer before (prevent abuse)
    if not already_awarded:
        from db.crud import check_telegram_id_received_profile_completion_reward
        already_awarded = await check_telegram_id_received_profile_completion_reward(
            db_session,
            user.telegram_id,
            referral.referrer_id
        )
    
    if already_awarded:
        return
    
    # Get base coins from database (must be set by admin)
    coins_profile_complete_base = await get_coins_for_activity(db_session, "referral_profile_complete")
    if coins_profile_complete_base is None:
        # Try fallback to old referral_referrer
        coins_profile_complete_base = await get_coins_for_activity(db_session, "referral_referrer")
        if coins_profile_complete_base is None:
            coins_profile_complete_base = 0
    
    coins_referred_base = await get_coins_for_activity(db_session, "referral_referred_signup")
    if coins_referred_base is None:
        coins_referred_base = await get_coins_for_activity(db_session, "referral_referred")
        if coins_referred_base is None:
            coins_referred_base = 0
    
    # Award profile completion points to both users
    await PointsManager.award_referral_profile_complete(
        referral.referrer_id,
        user.id
    )
    
    # Calculate actual coins with multiplier for display
    from core.event_engine import EventEngine
    coins_profile_complete_actual = await EventEngine.apply_points_multiplier(
        referral.referrer_id,
        coins_profile_complete_base,
        "referral_profile_complete"
    )
    coins_referred_actual = await EventEngine.apply_points_multiplier(
        user.id,
        coins_referred_base,
        "referral_profile_complete"
    )
    
    # Get event info for referrer if multiplier was applied
    referrer_event_info = ""
    if coins_profile_complete_actual > coins_profile_complete_base:
        from db.crud import get_active_events
        events = await get_active_events(db_session, event_type="points_multiplier")
        if events:
            event = events[0]
            config = await EventEngine.parse_event_config(event)
            apply_to_sources = config.get("apply_to_sources", [])
            if not apply_to_sources or "referral_profile_complete" in apply_to_sources:
                multiplier = config.get("multiplier", 1.0)
                referrer_event_info = f"\n\n🎁 به خاطر ایونت «{event.event_name}» ضریب {multiplier}x اعمال شد!\n✨ سکه پایه: {coins_profile_complete_base} → سکه نهایی: {coins_profile_complete_actual}"
    
    # Get event info for referred user if multiplier was applied
    referred_event_info = ""
    if coins_referred_actual > coins_referred_base:
        from db.crud import get_active_events
        events = await get_active_events(db_session, event_type="points_multiplier")
        if events:
            event = events[0]
            config = await EventEngine.parse_event_config(event)
            apply_to_sources = config.get("apply_to_sources", [])
            if not apply_to_sources or "referral_profile_complete" in apply_to_sources:
                multiplier = config.get("multiplier", 1.0)
                referred_event_info = f"\n\n🎁 به خاطر ایونت «{event.event_name}» ضریب {multiplier}x اعمال شد!\n✨ سکه پایه: {coins_referred_base} → سکه نهایی: {coins_referred_actual}"
    
    # Notify referrer and referred user
    from db.crud import get_user_by_id
    referrer = await get_user_by_id(db_session, referral.referrer_id)
    
    from aiogram import Bot
    bot = Bot(token=settings.BOT_TOKEN)
    try:
        # Notify referrer
        if referrer:
            try:
                await bot.send_message(
                    referrer.telegram_id,
                    f"🎉 خبر خوب!\n\n"
                    f"✅ یکی از کاربرانی که از لینک دعوت شما استفاده کرده، پروفایلش را تکمیل کرد!\n\n"
                    f"💰 {coins_profile_complete_actual} سکه به حساب شما اضافه شد!{referrer_event_info}\n\n"
                    f"💡 با دعوت کاربران بیشتر، سکه بیشتری دریافت می‌کنی!"
                )
            except Exception:
                pass
        
        # Notify referred user
        try:
            await bot.send_message(
                user.telegram_id,
                f"🎉 تبریک!\n\n"
                f"✅ پروفایل شما تکمیل شد!\n\n"
                f"💰 {coins_referred_actual} سکه به حساب شما اضافه شد!{referred_event_info}\n\n"
                f"💡 با تکمیل پروفایل، سکه دریافت کردی!"
            )
        except Exception:
            pass
    finally:
        await bot.session.close()


class MyProfileEditStates(StatesGroup):
    """FSM states for editing my profile."""
    waiting_new_photo = State()
    waiting_new_city = State()
    waiting_new_province = State()
    waiting_new_age = State()
    waiting_new_gender = State()
    waiting_new_display_name = State()


@router.callback_query(F.data == "my_profile:view")
async def view_my_profile(callback: CallbackQuery):
    """View my profile."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        gender_map = {"male": "پسر 🧑", "female": "دختر 👩", "other": "سایر"}
        gender_text = gender_map.get(user.gender, user.gender or "تعیین نشده")
        
        # Generate user ID
        user_unique_id = f"/user_{user.profile_id or 'unknown'}"
        
        # Get user badges
        from core.badge_manager import BadgeManager
        user_badges_display = await BadgeManager.get_user_badges_display(user.id, limit=5)
        
        profile_text = (
            f"📊 پروفایل من\n\n"
            f"• نام: {get_display_name(user)}\n"
            f"• جنسیت: {gender_text}\n"
            f"• استان: {user.province or 'تعیین نشده'}\n"
            f"• شهر: {user.city or 'تعیین نشده'}\n"
            f"• سن: {user.age or 'تعیین نشده'}\n"
            f"• پریمیوم: {'✅ فعال' if user.is_premium else '❌ غیرفعال'}\n"
        )
        
        # Add badges if available
        if user_badges_display:
            profile_text += f"• مدال‌ها: {user_badges_display}\n"
        
        profile_text += f"ID: {user_unique_id}"
        
        profile_keyboard = get_my_profile_keyboard()
        
        # Send profile with photo if available
        profile_image_url = getattr(user, 'profile_image_url', None)
        if profile_image_url:
            from aiogram import Bot
            from config.settings import settings
            from utils.minio_storage import is_url_accessible_from_internet
            import logging
            logger = logging.getLogger(__name__)
            
            bot = Bot(token=settings.BOT_TOKEN)
            try:
                # Check if it's a URL or file_id
                if profile_image_url.startswith(('http://', 'https://')):
                    # It's a URL - check if accessible
                    if is_url_accessible_from_internet(profile_image_url):
                        # URL is accessible, use directly
                        await bot.send_photo(
                            user_id,
                            profile_image_url,
                            caption=profile_text,
                            reply_markup=profile_keyboard
                        )
                    else:
                        # URL is not accessible, download and re-upload
                        try:
                            import aiohttp
                            async with aiohttp.ClientSession() as session:
                                async with session.get(profile_image_url) as resp:
                                    if resp.status == 200:
                                        image_data = await resp.read()
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
                            await callback.message.answer(profile_text, reply_markup=profile_keyboard)
                else:
                    # It's a file_id, use directly
                    await bot.send_photo(
                        user_id,
                        profile_image_url,
                        caption=profile_text,
                        reply_markup=profile_keyboard
                    )
                await bot.session.close()
                await callback.answer()
            except Exception as e:
                logger.error(f"Error sending photo: {e}", exc_info=True)
                await callback.message.answer(profile_text, reply_markup=profile_keyboard)
                await callback.answer()
        else:
            try:
                await callback.message.edit_text(profile_text, reply_markup=profile_keyboard)
            except:
                await callback.message.answer(profile_text, reply_markup=profile_keyboard)
            await callback.answer()
        
        break


@router.callback_query(F.data == "my_profile:edit_photo")
async def edit_photo(callback: CallbackQuery, state: FSMContext):
    """Start editing profile photo."""
    await callback.message.answer(
        "📸 لطفاً عکس جدید پروفایل خود را ارسال کنید:",
        reply_markup=None
    )
    await state.set_state(MyProfileEditStates.waiting_new_photo)
    await callback.answer()


@router.message(MyProfileEditStates.waiting_new_photo, F.photo)
async def process_new_photo(message: Message, state: FSMContext):
    """Process new profile photo."""
    user_id = message.from_user.id
    photo = message.photo[-1]
    file_id = photo.file_id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await message.answer("❌ کاربر یافت نشد.")
            await state.clear()
            return
        
        # Upload photo to MinIO
        from utils.minio_storage import upload_telegram_photo_to_minio
        from utils.nsfw_detector import download_and_check_photo
        from aiogram import Bot
        from config.settings import settings
        
        bot = Bot(token=settings.BOT_TOKEN)
        try:
            # Check for NSFW content before uploading
            is_safe, error_message = await download_and_check_photo(bot, file_id)
            if not is_safe:
                await message.answer(error_message)
                await state.clear()
                return
            
            minio_url = await upload_telegram_photo_to_minio(bot, file_id, user.id)
            if not minio_url:
                await message.answer("❌ خطا در آپلود عکس. لطفاً دوباره تلاش کنید.")
                await state.clear()
                return
            
            await update_user_profile(
                db_session,
                user_id,
                profile_image_url=minio_url
            )
            
            # Check if profile is complete and notify referrer
            await check_and_notify_profile_completion(db_session, user_id)
            
            await message.answer(
                "✅ عکس پروفایل به‌روزرسانی شد!",
                reply_markup=get_main_reply_keyboard()
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error uploading photo to MinIO: {e}", exc_info=True)
            await message.answer("❌ خطا در آپلود عکس. لطفاً دوباره تلاش کنید.")
        finally:
            await bot.session.close()
        
        await state.clear()
        break


@router.callback_query(F.data == "my_profile:edit_city")
async def edit_city(callback: CallbackQuery, state: FSMContext):
    """Start editing city."""
    await callback.message.answer(
        "🏙️ لطفاً نام شهر جدید خود را بفرستید:",
        reply_markup=None
    )
    await state.set_state(MyProfileEditStates.waiting_new_city)
    await callback.answer()


@router.message(MyProfileEditStates.waiting_new_city)
async def process_new_city(message: Message, state: FSMContext):
    """Process new city."""
    user_id = message.from_user.id
    new_city = message.text.strip()
    
    is_valid, error_msg = validate_city(new_city)
    if not is_valid:
        await message.answer(f"❌ {error_msg}\n\nلطفاً دوباره نام شهر را بفرستید:")
        return
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await message.answer("❌ کاربر یافت نشد.")
            await state.clear()
            return
        
        await update_user_profile(
            db_session,
            user_id,
            city=new_city
        )
        
        # Check if profile is complete and notify referrer
        await check_and_notify_profile_completion(db_session, user_id)
        
        await message.answer(
            f"✅ شهر به {new_city} تغییر یافت!",
            reply_markup=get_main_reply_keyboard()
        )
        await state.clear()
        break


@router.callback_query(F.data == "my_profile:edit_province")
async def edit_province(callback: CallbackQuery, state: FSMContext):
    """Start editing province."""
    await callback.message.answer(
        "🗺️ لطفاً نام استان جدید خود را بفرستید:",
        reply_markup=None
    )
    await state.set_state(MyProfileEditStates.waiting_new_province)
    await callback.answer()


@router.message(MyProfileEditStates.waiting_new_province)
async def process_new_province(message: Message, state: FSMContext):
    """Process new province."""
    user_id = message.from_user.id
    new_province = message.text.strip()
    
    if len(new_province) < 2:
        await message.answer("❌ نام استان باید حداقل 2 کاراکتر باشد.\n\nلطفاً دوباره نام استان را بفرستید:")
        return
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await message.answer("❌ کاربر یافت نشد.")
            await state.clear()
            return
        
        await update_user_profile(
            db_session,
            user_id,
            province=new_province
        )
        
        await message.answer(
            f"✅ استان به {new_province} تغییر یافت!",
            reply_markup=get_main_reply_keyboard()
        )
        await state.clear()
        break


@router.callback_query(F.data == "my_profile:edit_age")
async def edit_age(callback: CallbackQuery, state: FSMContext):
    """Start editing age."""
    await callback.message.answer(
        "🎂 لطفاً سن جدید خود را بفرستید (13 تا 120):",
        reply_markup=None
    )
    await state.set_state(MyProfileEditStates.waiting_new_age)
    await callback.answer()


@router.message(MyProfileEditStates.waiting_new_age)
async def process_new_age(message: Message, state: FSMContext):
    """Process new age."""
    user_id = message.from_user.id
    
    is_valid, age, error_msg = parse_age(message.text)
    if not is_valid:
        await message.answer(f"❌ {error_msg}\n\nلطفاً دوباره سن را بفرستید:")
        return
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await message.answer("❌ کاربر یافت نشد.")
            await state.clear()
            return
        
        await update_user_profile(
            db_session,
            user_id,
            age=age
        )
        
        # Check if profile is complete and notify referrer
        await check_and_notify_profile_completion(db_session, user_id)
        
        await message.answer(
            f"✅ سن به {age} سال تغییر یافت!",
            reply_markup=get_main_reply_keyboard()
        )
        await state.clear()
        break


@router.callback_query(F.data == "my_profile:edit_gender")
async def edit_gender(callback: CallbackQuery, state: FSMContext):
    """Start editing gender."""
    from bot.keyboards.common import get_gender_keyboard
    await callback.message.answer(
        "👤 لطفاً جنسیت جدید خود را انتخاب کنید:",
        reply_markup=get_gender_keyboard()
    )
    await state.set_state(MyProfileEditStates.waiting_new_gender)
    await callback.answer()


@router.callback_query(MyProfileEditStates.waiting_new_gender, F.data.startswith("gender:"))
async def process_new_gender(callback: CallbackQuery, state: FSMContext):
    """Process new gender."""
    user_id = callback.from_user.id
    gender = callback.data.split(":")[1]
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            await state.clear()
            return
        
        await update_user_profile(
            db_session,
            user_id,
            gender=gender
        )
        
        gender_map = {"male": "پسر 🧑", "female": "دختر 👩", "other": "سایر"}
        gender_text = gender_map.get(gender, gender)
        
        await callback.message.answer(
            f"✅ جنسیت به {gender_text} تغییر یافت!",
            reply_markup=get_main_reply_keyboard()
        )
        await callback.answer()
        await state.clear()
        break


@router.callback_query(F.data == "my_profile:edit_display_name")
async def edit_display_name(callback: CallbackQuery, state: FSMContext):
    """Start editing display name."""
    await callback.message.answer(
        "📝 لطفاً نام نمایشی جدید خود را بفرستید:",
        reply_markup=None
    )
    await state.set_state(MyProfileEditStates.waiting_new_display_name)
    await callback.answer()


@router.message(MyProfileEditStates.waiting_new_display_name)
async def process_new_display_name(message: Message, state: FSMContext):
    """Process new display name."""
    user_id = message.from_user.id
    new_display_name = message.text.strip()
    
    if len(new_display_name) < 2:
        await message.answer("❌ نام نمایشی باید حداقل 2 کاراکتر باشد.\n\nلطفاً دوباره نام نمایشی را بفرستید:")
        return
    
    # Check for inappropriate content
    from utils.content_filter import validate_display_name
    is_valid, error_message = validate_display_name(new_display_name)
    if not is_valid:
        await message.answer(error_message + "\n\nلطفاً دوباره نام نمایشی را بفرستید:")
        return
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await message.answer("❌ کاربر یافت نشد.")
            await state.clear()
            return
        
        await update_user_profile(
            db_session,
            user_id,
            display_name=new_display_name
        )
        
        # Check if profile is complete and notify referrer
        await check_and_notify_profile_completion(db_session, user_id)
        
        await message.answer(
            f"✅ نام نمایشی به {new_display_name} تغییر یافت!",
            reply_markup=get_main_reply_keyboard()
        )
        await state.clear()
        break


@router.inline_query(F.query.startswith("following:"))
async def inline_following_list(inline_query: InlineQuery):
    """Handle inline query for following users list."""
    user_id = inline_query.from_user.id
    query = inline_query.query
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await inline_query.answer(
                results=[],
                cache_time=1
            )
            return
        
        following_list = await get_following_list(db_session, user.id)
        
        if not following_list:
            await inline_query.answer(
                results=[],
                cache_time=1,
                is_personal=True
            )
            return
        
        # Get user details for each followed user
        from db.crud import get_user_by_id
        results = []
        
        for followed_user_id, username, profile_id in following_list[:50]:  # Max 50 results
            followed_user = await get_user_by_id(db_session, followed_user_id)
            if not followed_user:
                continue
            
            # Use display_name instead of username
            display_name_text = get_display_name(followed_user)
            user_unique_id = f"/user_{profile_id or 'unknown'}"
            
            # Get profile image for thumbnail
            profile_image_url = getattr(followed_user, 'profile_image_url', None)
            
            # Get thumbnail URL - only use if accessible from internet
            from utils.minio_storage import get_telegram_thumbnail_url
            thumbnail_url = get_telegram_thumbnail_url(profile_image_url) if profile_image_url else None
            
            # If it's a file_id and thumbnail_url is None, try to get Telegram file URL
            if not thumbnail_url and profile_image_url and not profile_image_url.startswith(('http://', 'https://')):
                try:
                    bot = Bot(token=settings.BOT_TOKEN)
                    file = await bot.get_file(profile_image_url)
                    thumbnail_url = f"https://api.telegram.org/file/bot{settings.BOT_TOKEN}/{file.file_path}"
                    await bot.session.close()
                except Exception:
                    thumbnail_url = None
            
            # Determine online status
            _, last_seen = await get_user_status(followed_user.telegram_id, activity_tracker, db_session)
            status_text = format_last_seen(last_seen if last_seen else followed_user.last_seen)
            description = f"{status_text} • {user_unique_id}"
            
            results.append(
                InlineQueryResultArticle(
                    id=str(followed_user_id),
                    title=f"👥 {display_name_text[:30]}",
                    description=description[:50],
                    thumbnail_url=thumbnail_url,
                    input_message_content=InputTextMessageContent(
                        message_text=user_unique_id
                    )
                )
            )
        
        await inline_query.answer(
            results=results,
            cache_time=1,
            is_personal=True
        )
        break


@router.callback_query(F.data.startswith("my_profile:following_page:"))
async def following_list_page(callback: CallbackQuery):
    """Handle pagination for following list."""
    user_id = callback.from_user.id
    page = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        following_list = await get_following_list(db_session, user.id)
        
        if not following_list:
            await callback.answer("📭 شما هنوز کسی را دنبال نکرده‌اید.", show_alert=True)
            return
        
        following_keyboard = get_following_list_keyboard(following_list, page=page)
        
        list_text = f"👥 دنبال شده‌ها ({len(following_list)} نفر)\n\n"
        list_text += "روی هر کاربر کلیک کنید تا آنفالو شود:"
        
        try:
            await callback.message.edit_text(list_text, reply_markup=following_keyboard)
        except:
            await callback.message.answer(list_text, reply_markup=following_keyboard)
        await callback.answer()
        break


@router.callback_query(F.data.startswith("my_profile:unfollow:"))
async def unfollow_user_from_list(callback: CallbackQuery):
    """Unfollow a user from the following list."""
    user_id = callback.from_user.id
    followed_id = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        followed_user = await get_user_by_id(db_session, followed_id)
        if not followed_user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        success = await unfollow_user(db_session, user.id, followed_id)
        
        if success:
            await callback.answer(f"✅ {get_display_name(followed_user)} آنفالو شد!")
            
            # Refresh list
            following_list = await get_following_list(db_session, user.id)
            
            if not following_list:
                await callback.message.edit_text(
                    "📭 شما دیگر کسی را دنبال نمی‌کنید.",
                    reply_markup=None
                )
            else:
                following_keyboard = get_following_list_keyboard(following_list, page=0)
                list_text = f"👥 دنبال شده‌ها ({len(following_list)} نفر)\n\n"
                list_text += "روی هر کاربر کلیک کنید تا آنفالو شود:"
                
                try:
                    await callback.message.edit_text(list_text, reply_markup=following_keyboard)
                except:
                    await callback.message.answer(list_text, reply_markup=following_keyboard)
        else:
            await callback.answer("❌ خطا در آنفالو کردن.", show_alert=True)
        break


@router.inline_query(F.query.startswith("liked:"))
async def inline_liked_list(inline_query: InlineQuery):
    """Handle inline query for liked users list."""
    user_id = inline_query.from_user.id
    query = inline_query.query
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await inline_query.answer(
                results=[],
                cache_time=1
            )
            return
        
        liked_list = await get_liked_list(db_session, user.id)
        
        if not liked_list:
            await inline_query.answer(
                results=[],
                cache_time=1,
                is_personal=True
            )
            return
        
        # Get user details for each liked user
        from db.crud import get_user_by_id
        results = []
        
        for liked_user_id, username, profile_id in liked_list[:50]:  # Max 50 results
            liked_user = await get_user_by_id(db_session, liked_user_id)
            if not liked_user:
                continue
            
            # Use display_name instead of username
            display_name_text = get_display_name(liked_user)
            user_unique_id = f"/user_{profile_id or 'unknown'}"
            
            # Get profile image for thumbnail
            profile_image_url = getattr(liked_user, 'profile_image_url', None)
            
            # Get thumbnail URL - only use if accessible from internet
            from utils.minio_storage import get_telegram_thumbnail_url
            thumbnail_url = get_telegram_thumbnail_url(profile_image_url) if profile_image_url else None
            
            # If it's a file_id and thumbnail_url is None, try to get Telegram file URL
            if not thumbnail_url and profile_image_url and not profile_image_url.startswith(('http://', 'https://')):
                try:
                    bot = Bot(token=settings.BOT_TOKEN)
                    file = await bot.get_file(profile_image_url)
                    thumbnail_url = f"https://api.telegram.org/file/bot{settings.BOT_TOKEN}/{file.file_path}"
                    await bot.session.close()
                except Exception:
                    thumbnail_url = None
            
            # Determine online status
            _, last_seen = await get_user_status(liked_user.telegram_id, activity_tracker, db_session)
            status_text = format_last_seen(last_seen if last_seen else liked_user.last_seen)
            description = f"{status_text} • {user_unique_id}"
            
            results.append(
                InlineQueryResultArticle(
                    id=str(liked_user_id),
                    title=f"❤️ {display_name_text[:30]}",
                    description=description[:50],
                    thumbnail_url=thumbnail_url,
                    input_message_content=InputTextMessageContent(
                        message_text=user_unique_id
                    )
                )
            )
        
        await inline_query.answer(
            results=results,
            cache_time=1,
            is_personal=True
        )
        break


@router.inline_query(F.query.startswith("blocked:"))
async def inline_blocked_list(inline_query: InlineQuery):
    """Handle inline query for blocked users list."""
    user_id = inline_query.from_user.id
    query = inline_query.query
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await inline_query.answer(
                results=[],
                cache_time=1
            )
            return
        
        blocked_list = await get_blocked_list(db_session, user.id)
        
        if not blocked_list:
            await inline_query.answer(
                results=[],
                cache_time=1,
                is_personal=True
            )
            return
        
        # Get user details for each blocked user
        from db.crud import get_user_by_id
        results = []
        
        for blocked_user_id, username, profile_id in blocked_list[:50]:  # Max 50 results
            blocked_user = await get_user_by_id(db_session, blocked_user_id)
            if not blocked_user:
                continue
            
            # Use display_name instead of username
            display_name_text = get_display_name(blocked_user)
            user_unique_id = f"/user_{profile_id or 'unknown'}"
            
            # Get profile image for thumbnail
            profile_image_url = getattr(blocked_user, 'profile_image_url', None)
            
            # Get thumbnail URL - only use if accessible from internet
            from utils.minio_storage import get_telegram_thumbnail_url
            thumbnail_url = get_telegram_thumbnail_url(profile_image_url) if profile_image_url else None
            
            # If it's a file_id and thumbnail_url is None, try to get Telegram file URL
            if not thumbnail_url and profile_image_url and not profile_image_url.startswith(('http://', 'https://')):
                try:
                    bot = Bot(token=settings.BOT_TOKEN)
                    file = await bot.get_file(profile_image_url)
                    thumbnail_url = f"https://api.telegram.org/file/bot{settings.BOT_TOKEN}/{file.file_path}"
                    await bot.session.close()
                except Exception:
                    thumbnail_url = None
            
            # Determine online status
            _, last_seen = await get_user_status(blocked_user.telegram_id, activity_tracker, db_session)
            status_text = format_last_seen(last_seen if last_seen else blocked_user.last_seen)
            description = f"{status_text} • {user_unique_id}"
            
            results.append(
                InlineQueryResultArticle(
                    id=str(blocked_user_id),
                    title=f"🚫 {display_name_text[:30]}",
                    description=description[:50],
                    thumbnail_url=thumbnail_url,
                    input_message_content=InputTextMessageContent(
                        message_text=user_unique_id
                    )
                )
            )
        
        await inline_query.answer(
            results=results,
            cache_time=1,
            is_personal=True
        )
        break


@router.callback_query(F.data.startswith("my_profile:liked_page:"))
async def liked_list_page(callback: CallbackQuery):
    """Handle pagination for liked list."""
    user_id = callback.from_user.id
    page = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        liked_list = await get_liked_list(db_session, user.id)
        
        if not liked_list:
            await callback.answer("❤️ شما هنوز کسی را لایک نکرده‌اید.", show_alert=True)
            return
        
        liked_keyboard = get_liked_list_keyboard(liked_list, page=page)
        
        list_text = f"❤️ لایک شده‌ها ({len(liked_list)} نفر)\n\n"
        list_text += "روی هر کاربر کلیک کنید تا لایک برداشته شود:"
        
        try:
            await callback.message.edit_text(list_text, reply_markup=liked_keyboard)
        except:
            await callback.message.answer(list_text, reply_markup=liked_keyboard)
        await callback.answer()
        break


@router.callback_query(F.data.startswith("my_profile:unlike:"))
async def unlike_user_from_list(callback: CallbackQuery):
    """Unlike a user from the liked list."""
    user_id = callback.from_user.id
    liked_user_id = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        liked_user = await get_user_by_id(db_session, liked_user_id)
        if not liked_user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        success = await unlike_user(db_session, user.id, liked_user_id)
        
        if success:
            await callback.answer(f"❤️ لایک {get_display_name(liked_user)} برداشته شد!")
            
            # Refresh list
            liked_list = await get_liked_list(db_session, user.id)
            
            if not liked_list:
                await callback.message.edit_text(
                    "❤️ شما دیگر کسی را لایک نکرده‌اید.",
                    reply_markup=None
                )
            else:
                liked_keyboard = get_liked_list_keyboard(liked_list, page=0)
                list_text = f"❤️ لایک شده‌ها ({len(liked_list)} نفر)\n\n"
                list_text += "روی هر کاربر کلیک کنید تا لایک برداشته شود:"
                
                try:
                    await callback.message.edit_text(list_text, reply_markup=liked_keyboard)
                except:
                    await callback.message.answer(list_text, reply_markup=liked_keyboard)
        else:
            await callback.answer("❌ خطا در برداشتن لایک.", show_alert=True)
        break


@router.callback_query(F.data == "my_profile:blocked_list")
async def show_blocked_list(callback: CallbackQuery):
    """Show list of blocked users."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        blocked_list = await get_blocked_list(db_session, user.id)
        
        if not blocked_list:
            await callback.answer("🚫 شما هنوز کسی را بلاک نکرده‌اید.", show_alert=True)
            return
        
        blocked_keyboard = get_blocked_list_keyboard(blocked_list, page=0)
        
        list_text = f"🚫 بلاک شده‌ها ({len(blocked_list)} نفر)\n\n"
        list_text += "روی هر کاربر کلیک کنید تا آنبلاک شود:"
        
        try:
            await callback.message.edit_text(list_text, reply_markup=blocked_keyboard)
        except:
            await callback.message.answer(list_text, reply_markup=blocked_keyboard)
        await callback.answer()
        break


@router.callback_query(F.data.startswith("my_profile:blocked_page:"))
async def blocked_list_page(callback: CallbackQuery):
    """Handle pagination for blocked list."""
    user_id = callback.from_user.id
    page = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        blocked_list = await get_blocked_list(db_session, user.id)
        
        if not blocked_list:
            await callback.answer("🚫 شما هنوز کسی را بلاک نکرده‌اید.", show_alert=True)
            return
        
        blocked_keyboard = get_blocked_list_keyboard(blocked_list, page=page)
        
        list_text = f"🚫 بلاک شده‌ها ({len(blocked_list)} نفر)\n\n"
        list_text += "روی هر کاربر کلیک کنید تا آنبلاک شود:"
        
        try:
            await callback.message.edit_text(list_text, reply_markup=blocked_keyboard)
        except:
            await callback.message.answer(list_text, reply_markup=blocked_keyboard)
        await callback.answer()
        break


@router.callback_query(F.data.startswith("my_profile:unblock:"))
async def unblock_user_from_list(callback: CallbackQuery):
    """Unblock a user from the blocked list."""
    user_id = callback.from_user.id
    blocked_id = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        blocked_user = await get_user_by_id(db_session, blocked_id)
        if not blocked_user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        success = await unblock_user(db_session, user.id, blocked_id)
        
        if success:
            await callback.answer(f"✅ {get_display_name(blocked_user)} آنبلاک شد!")
            
            # Refresh list
            blocked_list = await get_blocked_list(db_session, user.id)
            
            if not blocked_list:
                await callback.message.edit_text(
                    "🚫 شما دیگر کسی را بلاک نکرده‌اید.",
                    reply_markup=None
                )
            else:
                blocked_keyboard = get_blocked_list_keyboard(blocked_list, page=0)
                list_text = f"🚫 بلاک شده‌ها ({len(blocked_list)} نفر)\n\n"
                list_text += "روی هر کاربر کلیک کنید تا آنبلاک شود:"
                
                try:
                    await callback.message.edit_text(list_text, reply_markup=blocked_keyboard)
                except:
                    await callback.message.answer(list_text, reply_markup=blocked_keyboard)
        else:
            await callback.answer("❌ خطا در آنبلاک کردن.", show_alert=True)
        break


@router.callback_query(F.data == "my_profile:back")
async def back_to_my_profile(callback: CallbackQuery):
    """Return to my profile view."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        gender_map = {"male": "پسر 🧑", "female": "دختر 👩", "other": "سایر"}
        gender_text = gender_map.get(user.gender, user.gender or "تعیین نشده")
        
        user_unique_id = f"/user_{user.profile_id or 'unknown'}"
        
        # Get user badges
        from core.badge_manager import BadgeManager
        user_badges_display = await BadgeManager.get_user_badges_display(user.id, limit=5)
        
        profile_text = (
            f"📊 پروفایل من\n\n"
            f"• نام: {get_display_name(user)}\n"
            f"• جنسیت: {gender_text}\n"
            f"• استان: {user.province or 'تعیین نشده'}\n"
            f"• شهر: {user.city or 'تعیین نشده'}\n"
            f"• سن: {user.age or 'تعیین نشده'}\n"
            f"• پریمیوم: {'✅ فعال' if user.is_premium else '❌ غیرفعال'}\n"
        )
        
        # Add badges if available
        if user_badges_display:
            profile_text += f"• مدال‌ها: {user_badges_display}\n"
        
        profile_text += f"ID: {user_unique_id}"
        
        profile_keyboard = get_my_profile_keyboard()
        
        try:
            await callback.message.edit_text(profile_text, reply_markup=profile_keyboard)
        except:
            await callback.message.answer(profile_text, reply_markup=profile_keyboard)
        await callback.answer()
        break


@router.callback_query(F.data == "my_profile:direct_messages")
async def show_direct_messages_list(callback: CallbackQuery):
    """Show list of direct messages with inline buttons."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        from db.crud import get_direct_message_list
        from bot.keyboards.my_profile import get_direct_messages_list_keyboard
        
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        message_list = await get_direct_message_list(db_session, user.id)
        
        if not message_list:
            await callback.answer("📭 شما هیچ پیام دایرکتی ندارید.", show_alert=True)
            return
        
        # Create keyboard with buttons
        keyboard = get_direct_messages_list_keyboard(message_list)
        
        list_text = f"✉️ پیام‌های دایرکت ({len(message_list)} پیام)\n\n"
        list_text += "لیست کاربرانی که برای شما پیام فرستاده‌اند:\n"
        list_text += "روی هر کاربر کلیک کنید تا پیام‌هایش را ببینید:"
        
        try:
            await callback.message.edit_text(list_text, reply_markup=keyboard)
        except:
            await callback.message.answer(list_text, reply_markup=keyboard)
        await callback.answer()
        break


@router.callback_query(F.data == "my_profile:delete_account")
async def delete_account_confirm(callback: CallbackQuery):
    """Show confirmation for account deletion."""
    await callback.message.answer(
        "⚠️ هشدار: حذف اکانت\n\n"
        "آیا مطمئن هستید که می‌خواهید اکانت خود را حذف کنید؟\n\n"
        "❌ با حذف اکانت:\n"
        "• تمام اطلاعات پروفایل شما حذف می‌شود\n"
        "• تمام چت‌ها و پیام‌های شما حذف می‌شود\n"
        "• دیگر نمی‌توانید از ربات استفاده کنید\n\n"
        "⚠️ این عمل غیرقابل بازگشت است!",
        reply_markup=get_delete_account_confirm_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "my_profile:delete_account:confirm")
async def delete_account_execute(callback: CallbackQuery):
    """Execute account deletion."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        # Get user including inactive users (for deletion)
        user = await get_user_by_telegram_id(db_session, user_id, include_inactive=True)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Check if user has active chat and end it
        from db.crud import get_active_chat_room_by_user, get_user_by_id, end_chat_room
        from bot.handlers.chat import chat_manager
        from bot.handlers.chat import matchmaking_queue
        
        chat_room = await get_active_chat_room_by_user(db_session, user.id)
        if chat_room and chat_manager:
            # Get partner before ending chat
            partner_id = None
            if chat_room.user1_id == user.id:
                partner_id = chat_room.user2_id
            else:
                partner_id = chat_room.user1_id
            
            partner = None
            if partner_id:
                partner = await get_user_by_id(db_session, partner_id)
            
            # End chat room using chat_manager
            await chat_manager.end_chat(chat_room.id, db_session)
            
            # Notify partner if exists
            if partner:
                from aiogram import Bot
                bot = Bot(token=settings.BOT_TOKEN)
                try:
                    await bot.send_message(
                        partner.telegram_id,
                        "ℹ️ هم‌چت شما اکانت خود را حذف کرد و چت به پایان رسید."
                    )
                    await bot.session.close()
                except Exception:
                    pass
        
        # Remove user from matchmaking queue if exists
        # Note: matchmaking_queue uses telegram_id, not database id
        if matchmaking_queue:
            try:
                if await matchmaking_queue.is_user_in_queue(user_id):
                    await matchmaking_queue.remove_user_from_queue(user_id)
            except Exception:
                pass
        
        # Delete account (soft delete)
        success = await delete_user_account(db_session, user.id)
        
        if success:
            # Verify deletion by querying database again
            deleted_user = await get_user_by_telegram_id(db_session, user_id, include_inactive=True)
            
            if deleted_user and not deleted_user.is_active:
                await callback.message.edit_text(
                    "✅ اکانت شما با موفقیت حذف شد.\n\n"
                    "متأسفیم که شما را از دست دادیم. امیدواریم در آینده دوباره به ما بپیوندید! 👋"
                )
                await callback.answer("✅ اکانت حذف شد")
            else:
                await callback.answer("❌ خطا در حذف اکانت. لطفاً دوباره تلاش کنید.", show_alert=True)
        else:
            await callback.answer("❌ خطا در حذف اکانت. لطفاً دوباره تلاش کنید.", show_alert=True)
        break


@router.callback_query(F.data == "my_profile:delete_account:cancel")
async def delete_account_cancel(callback: CallbackQuery):
    """Cancel account deletion."""
    await callback.message.edit_text(
        "✅ حذف اکانت لغو شد.\n\n"
        "اکانت شما همچنان فعال است."
    )
    await callback.answer("✅ لغو شد")


@router.callback_query(F.data == "my_profile:notification_settings")
async def show_notification_settings(callback: CallbackQuery):
    """Show notification settings menu."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Get current settings (default to True if not set)
        receive_chat_requests = getattr(user, 'receive_chat_requests', True)
        receive_direct_messages = getattr(user, 'receive_direct_messages', True)
        receive_referral_notifications = getattr(user, 'receive_referral_notifications', True)
        
        settings_text = (
            "⚙️ تنظیمات اعلان‌ها\n\n"
            "می‌توانید انتخاب کنید که چه نوع پیام‌هایی را دریافت کنید:\n\n"
            f"💬 درخواست‌های چت: {'✅ فعال' if receive_chat_requests else '❌ غیرفعال'}\n"
            f"✉️ پیام‌های دایرکت: {'✅ فعال' if receive_direct_messages else '❌ غیرفعال'}\n"
            f"🎁 اعلان‌های معرفی: {'✅ فعال' if receive_referral_notifications else '❌ غیرفعال'}\n\n"
            "💡 روی هر گزینه کلیک کنید تا فعال/غیرفعال شود."
        )
        
        # Check if message has photo, if so use edit_caption, otherwise edit_text
        try:
            if callback.message.photo:
                await callback.message.edit_caption(
                    caption=settings_text,
                    reply_markup=get_notification_settings_keyboard(
                        receive_chat_requests=receive_chat_requests,
                        receive_direct_messages=receive_direct_messages,
                        receive_referral_notifications=receive_referral_notifications
                    )
                )
            else:
                await callback.message.edit_text(
                    settings_text,
                    reply_markup=get_notification_settings_keyboard(
                        receive_chat_requests=receive_chat_requests,
                        receive_direct_messages=receive_direct_messages,
                        receive_referral_notifications=receive_referral_notifications
                    )
                )
        except Exception:
            await callback.message.answer(
                settings_text,
                reply_markup=get_notification_settings_keyboard(
                    receive_chat_requests=receive_chat_requests,
                    receive_direct_messages=receive_direct_messages,
                    receive_referral_notifications=receive_referral_notifications
                )
            )
        
        await callback.answer()
        break


@router.callback_query(F.data.startswith("notification:toggle:"))
async def toggle_notification_setting(callback: CallbackQuery):
    """Toggle a notification setting."""
    user_id = callback.from_user.id
    setting_type = callback.data.split(":")[-1]
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Toggle the setting
        if setting_type == "chat_requests":
            user.receive_chat_requests = not getattr(user, 'receive_chat_requests', True)
            new_value = user.receive_chat_requests
        elif setting_type == "direct_messages":
            user.receive_direct_messages = not getattr(user, 'receive_direct_messages', True)
            new_value = user.receive_direct_messages
        elif setting_type == "referral_notifications":
            user.receive_referral_notifications = not getattr(user, 'receive_referral_notifications', True)
            new_value = user.receive_referral_notifications
        else:
            await callback.answer("❌ تنظیمات نامعتبر.", show_alert=True)
            return
        
        user.updated_at = datetime.utcnow()
        await db_session.commit()
        await db_session.refresh(user)
        
        # Get all settings for display
        receive_chat_requests = getattr(user, 'receive_chat_requests', True)
        receive_direct_messages = getattr(user, 'receive_direct_messages', True)
        receive_referral_notifications = getattr(user, 'receive_referral_notifications', True)
        
        setting_names = {
            "chat_requests": "درخواست‌های چت",
            "direct_messages": "پیام‌های دایرکت",
            "referral_notifications": "اعلان‌های معرفی"
        }
        
        setting_name = setting_names.get(setting_type, setting_type)
        status_text = "فعال شد" if new_value else "غیرفعال شد"
        
        settings_text = (
            "⚙️ تنظیمات اعلان‌ها\n\n"
            "می‌توانید انتخاب کنید که چه نوع پیام‌هایی را دریافت کنید:\n\n"
            f"💬 درخواست‌های چت: {'✅ فعال' if receive_chat_requests else '❌ غیرفعال'}\n"
            f"✉️ پیام‌های دایرکت: {'✅ فعال' if receive_direct_messages else '❌ غیرفعال'}\n"
            f"🎁 اعلان‌های معرفی: {'✅ فعال' if receive_referral_notifications else '❌ غیرفعال'}\n\n"
            "💡 روی هر گزینه کلیک کنید تا فعال/غیرفعال شود."
        )
        
        # Check if message has photo, if so use edit_caption, otherwise edit_text
        try:
            if callback.message.photo:
                await callback.message.edit_caption(
                    caption=settings_text,
                    reply_markup=get_notification_settings_keyboard(
                        receive_chat_requests=receive_chat_requests,
                        receive_direct_messages=receive_direct_messages,
                        receive_referral_notifications=receive_referral_notifications
                    )
                )
            else:
                await callback.message.edit_text(
                    settings_text,
                    reply_markup=get_notification_settings_keyboard(
                        receive_chat_requests=receive_chat_requests,
                        receive_direct_messages=receive_direct_messages,
                        receive_referral_notifications=receive_referral_notifications
                    )
                )
        except Exception:
            await callback.message.answer(
                settings_text,
                reply_markup=get_notification_settings_keyboard(
                    receive_chat_requests=receive_chat_requests,
                    receive_direct_messages=receive_direct_messages,
                    receive_referral_notifications=receive_referral_notifications
                )
            )
        
        await callback.answer(f"✅ {setting_name} {status_text}")
        break

