"""
Registration handler for the bot.
Handles multi-step user registration flow.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter
from bot.keyboards.reply import remove_keyboard, get_main_reply_keyboard
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db.database import get_db
from db.crud import get_user_by_telegram_id, create_user, update_user_profile
from db.models import User
from bot.keyboards.common import (
    get_gender_keyboard,
    get_registration_skip_keyboard,
    get_main_menu_keyboard
)
from utils.validators import validate_age, parse_age, validate_gender, validate_city, validate_username
from config.settings import settings

router = Router()


class RegistrationStates(StatesGroup):
    """FSM states for registration."""
    waiting_gender = State()
    waiting_age = State()
    waiting_city = State()
    waiting_display_name = State()
    waiting_photo = State()
    waiting_username = State()


# Store registration data in memory (in production, use Redis)
registration_data = {}


@router.callback_query(F.data.startswith("gender:"))
async def process_gender(callback: CallbackQuery, state: FSMContext):
    """Process gender selection."""
    gender = callback.data.split(":")[1]
    
    # Validate gender
    is_valid, error_msg = validate_gender(gender)
    if not is_valid:
        await callback.answer(error_msg, show_alert=True)
        return
    
    user_id = callback.from_user.id
    
    # Store gender
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        
        if user:
            await update_user_profile(db_session, user_id, gender=gender)
        else:
            # Store in memory for later
            if user_id not in registration_data:
                registration_data[user_id] = {}
            registration_data[user_id]["gender"] = gender
        break
    
    await callback.answer()
    # Send a new message instead of edit_text to be able to use ReplyKeyboardRemove
    await callback.message.answer(
        "عالی! چند سالته؟\n"
        "لطفاً سن خودت را بفرست (13 تا 120):",
        reply_markup=remove_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_age)


# Note: Preferred gender selection is now in chat handler, not registration


@router.message(StateFilter(RegistrationStates.waiting_age))
async def process_age(message: Message, state: FSMContext):
    """Process age input."""
    user_id = message.from_user.id
    
    # Parse and validate age
    is_valid, age, error_msg = parse_age(message.text)
    
    if not is_valid:
        await message.answer(f"❌ {error_msg}\n\nلطفاً دوباره سن خودت را بفرست:")
        return
    
    # Store age
    if user_id not in registration_data:
        registration_data[user_id] = {}
    registration_data[user_id]["age"] = age
    
    await message.answer(
        "عالی! از چه شهری هستی؟\n"
        "لطفاً نام شهر خودت را بفرست:",
        reply_markup=remove_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_city)


@router.message(StateFilter(RegistrationStates.waiting_city))
async def process_city(message: Message, state: FSMContext):
    """Process city input."""
    city = message.text.strip()
    user_id = message.from_user.id
    
    # Validate city
    is_valid, error_msg = validate_city(city)
    if not is_valid:
        await message.answer(f"❌ {error_msg}\n\nلطفاً دوباره نام شهر خودت را بفرست:")
        return
    
    # Store city
    if user_id not in registration_data:
        registration_data[user_id] = {}
    registration_data[user_id]["city"] = city
    
    await message.answer(
        "عالی! حالا یک نام نمایشی برای خودت انتخاب کن:\n"
        "لطفاً نام نمایشی خودت را بفرست (حداکثر 50 کاراکتر):",
        reply_markup=remove_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_display_name)


@router.message(StateFilter(RegistrationStates.waiting_display_name))
async def process_display_name(message: Message, state: FSMContext):
    """Process display name input."""
    display_name = message.text.strip()
    user_id = message.from_user.id
    
    # Validate display name
    if not display_name or len(display_name) < 2:
        await message.answer("❌ نام نمایشی باید حداقل 2 کاراکتر باشد.\n\nلطفاً دوباره نام نمایشی خودت را بفرست:")
        return
    
    if len(display_name) > 50:
        await message.answer("❌ نام نمایشی نمی‌تواند بیشتر از 50 کاراکتر باشد.\n\nلطفاً دوباره نام نمایشی خودت را بفرست:")
        return
    
    # Store display name
    if user_id not in registration_data:
        registration_data[user_id] = {}
    registration_data[user_id]["display_name"] = display_name
    
    await message.answer(
        "خوب! حالا عکس پروفایل خودت را بفرست (یا رد کن):",
        reply_markup=get_registration_skip_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_photo)


@router.message(StateFilter(RegistrationStates.waiting_photo), F.photo)
async def process_photo(message: Message, state: FSMContext):
    """Process profile photo."""
    user_id = message.from_user.id
    
    # Get the largest photo
    photo = message.photo[-1]
    file_id = photo.file_id
    
    # Upload photo to MinIO
    from utils.minio_storage import upload_telegram_photo_to_minio
    from aiogram import Bot
    from config.settings import settings
    import logging
    logger = logging.getLogger(__name__)
    
    bot = Bot(token=settings.BOT_TOKEN)
    try:
        # Use telegram_id for filename generation (user may not exist in DB yet)
        minio_url = await upload_telegram_photo_to_minio(bot, file_id, user_id)
        if not minio_url:
            logger.warning(f"Failed to upload photo to MinIO for user {user_id}, using file_id as fallback")
            # Fallback to file_id if MinIO upload fails
            minio_url = file_id
        
        # Store photo URL (MinIO URL or file_id as fallback)
    if user_id not in registration_data:
        registration_data[user_id] = {}
        registration_data[user_id]["profile_image_url"] = minio_url
    
    # Complete registration
    await complete_registration(message, state, user_id)
    except Exception as e:
        logger.error(f"Error uploading photo to MinIO during registration: {e}", exc_info=True)
        # Fallback to file_id if error occurs
        if user_id not in registration_data:
            registration_data[user_id] = {}
        registration_data[user_id]["profile_image_url"] = file_id
        await complete_registration(message, state, user_id)
    finally:
        await bot.session.close()


@router.callback_query(F.data == "registration:skip_photo")
async def skip_photo(callback: CallbackQuery, state: FSMContext):
    """Skip profile photo."""
    user_id = callback.from_user.id
    
    # Complete registration without photo
    await complete_registration(callback.message, state, user_id)


async def complete_registration(message: Message, state: FSMContext, user_id: int):
    """Complete registration and save user to database."""
    username = message.from_user.username
    user_data = registration_data.get(user_id, {})
    
    # Get or create user (including inactive users)
    async for db_session in get_db():
        # Check for existing user including inactive ones
        user = await get_user_by_telegram_id(db_session, user_id, include_inactive=True)
        is_new_user = user is None
        
        if user:
            # User exists (active or inactive)
            # If inactive, reactivate the account
            if not user.is_active:
                from sqlalchemy import update
                await db_session.execute(
                    update(User)
                    .where(User.id == user.id)
                    .values(is_active=True, is_banned=False)
                )
                await db_session.commit()
                # Refresh user to get updated state
                await db_session.refresh(user)
            
            # Update existing user profile
            await update_user_profile(
                db_session,
                user_id,
                username=username,
                display_name=user_data.get("display_name"),
                gender=user_data.get("gender"),
                age=user_data.get("age"),
                city=user_data.get("city"),
                profile_image_url=user_data.get("profile_image_url"),
            )
        else:
            # Create new user
            user = await create_user(
                db_session,
                telegram_id=user_id,
                username=username,
                display_name=user_data.get("display_name"),
                gender=user_data.get("gender"),
                age=user_data.get("age"),
                city=user_data.get("city"),
                profile_image_url=user_data.get("profile_image_url"),
            )
        
        # Check if user came from admin referral link
        if is_new_user and user_data.get("admin_link_code"):
            from db.crud import get_admin_referral_link_by_code, record_link_signup
            link = await get_admin_referral_link_by_code(db_session, user_data.get("admin_link_code"))
            if link and link.is_active:
                await record_link_signup(db_session, link.id, user.id)
        
        # Refresh user to get latest data
        await db_session.refresh(user)
        
        # Check if user came from user referral link
        referral_code = user_data.get("referral_code")
        referral_code_obj = None
        if referral_code:
            from db.crud import get_referral_code_by_code, create_referral, get_coins_for_activity
            referral_code_obj = await get_referral_code_by_code(db_session, referral_code)
        
        if is_new_user and referral_code_obj:
            # New user with referral code - create referral relationship
            # Points will be awarded when profile is completed
            if referral_code_obj.user_id != user.id:
                # Check if this telegram_id has used this referral code before (prevent abuse)
                from db.crud import check_telegram_id_used_referral_code
                if await check_telegram_id_used_referral_code(db_session, user_id, referral_code):
                    # User has used this code before, don't create referral
                    pass
                else:
                # Create referral
                await create_referral(
                    db_session,
                    referral_code_obj.user_id,
                    user.id,
                        referral_code,
                        check_telegram_id=user_id
                )
                
                await message.answer(
                    f"✅ عضویت شما از طریق لینک دعوت ثبت شد!\n\n"
                    f"💡 با تکمیل پروفایل خود (اسم، سن، شهر، تصویر)، سکه دریافت می‌کنی!"
                )
        
        # Check if profile is complete (username, age, city, profile_image_url)
        profile_complete = (
            user.username and
            user.age and
            user.city and
            user.profile_image_url
        )
        
        # If profile is complete and user has a referral, award profile completion points
        # Only for new users who registered with referral link
        if is_new_user and profile_complete and referral_code_obj and referral_code_obj.user_id != user.id:
            # Check if referral exists
            from db.crud import get_referral_by_users
            existing_referral = await get_referral_by_users(
                db_session,
                referral_code_obj.user_id,
                user.id
            )
            
            if existing_referral:
                # Check if we already awarded profile completion (by checking points history)
                from db.crud import get_points_history
                points_history = await get_points_history(db_session, referral_code_obj.user_id, limit=100)
                
                # Check if profile completion reward was already given
                already_awarded = any(
                    ph.source == "referral_profile_complete" and ph.related_user_id == user.id
                    for ph in points_history
                )
                
                # Also check if this telegram_id has received profile completion reward for this referrer before (prevent abuse)
                if not already_awarded:
                    from db.crud import check_telegram_id_received_profile_completion_reward
                    already_awarded = await check_telegram_id_received_profile_completion_reward(
                        db_session,
                        user_id,
                        referral_code_obj.user_id
                )
                
                if not already_awarded:
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
                    from core.points_manager import PointsManager
                    from core.achievement_system import AchievementSystem
                    
                    await PointsManager.award_referral_profile_complete(
                        referral_code_obj.user_id,
                        user.id
                    )
                    
                    # Calculate actual coins with multiplier for display
                    from core.event_engine import EventEngine
                    coins_profile_complete_actual = await EventEngine.apply_points_multiplier(
                        referral_code_obj.user_id,
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
                    
                    # Check achievements
                    from db.crud import get_referral_count, get_user_by_id
                    referral_count = await get_referral_count(db_session, referral_code_obj.user_id)
                    await AchievementSystem.check_referral_achievement(
                        referral_code_obj.user_id,
                        referral_count
                    )
                    
                    # Notify referrer
                    referrer = await get_user_by_id(db_session, referral_code_obj.user_id)
                    if referrer:
                        from aiogram import Bot
                        bot = Bot(token=settings.BOT_TOKEN)
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
                        finally:
                            await bot.session.close()
                    
                    # Notify referred user
                        await message.answer(
                        f"🎉 تبریک!\n\n"
                        f"✅ پروفایل شما تکمیل شد!\n\n"
                        f"💰 {coins_referred_actual} سکه به حساب شما اضافه شد!{referred_event_info}\n\n"
                        f"💡 با تکمیل پروفایل، سکه دریافت کردی!"
                    )
        
        # Clear registration data
        registration_data.pop(user_id, None)
        
        await message.answer(
            "✅ ثبت نام تکمیل شد!\n\n"
            "پروفایل شما ایجاد شده است. حالا می‌تونی شروع به چت کنی!",
            reply_markup=get_main_reply_keyboard()
        )
        
        await state.clear()
        break

