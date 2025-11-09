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
    
    # Store photo file_id
    if user_id not in registration_data:
        registration_data[user_id] = {}
    registration_data[user_id]["profile_image_url"] = file_id
    
    # Complete registration
    await complete_registration(message, state, user_id)


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
    
    # Get or create user
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        is_new_user = user is None
        
        if user:
            # Update existing user
            await update_user_profile(
                db_session,
                user_id,
                username=username,
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
        
        # Check if user came from user referral link
        if is_new_user and user_data.get("referral_code"):
            referral_code = user_data.get("referral_code")
            from db.crud import get_referral_code_by_code, create_referral
            from core.points_manager import PointsManager
            from core.achievement_system import AchievementSystem
            
            referral_code_obj = await get_referral_code_by_code(db_session, referral_code)
            if referral_code_obj:
                # Check if user is trying to use their own code (shouldn't happen, but check anyway)
                if referral_code_obj.user_id != user.id:
                    # Create referral
                    existing = await create_referral(
                        db_session,
                        referral_code_obj.user_id,
                        user.id,
                        referral_code
                    )
                    
                    if existing is not None:
                        # Award points
                        await PointsManager.award_referral(
                            referral_code_obj.user_id,
                            user.id
                        )
                        
                        # Check achievements
                        from db.crud import get_referral_count
                        referral_count = await get_referral_count(db_session, referral_code_obj.user_id)
                        await AchievementSystem.check_referral_achievement(
                            referral_code_obj.user_id,
                            referral_count
                        )
                        
                        await message.answer(
                            f"✅ کد دعوت '{referral_code}' با موفقیت ثبت شد!\n\n"
                            f"🎁 {settings.POINTS_REFERRAL_REFERRED} سکه به شما اهدا شد!"
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

