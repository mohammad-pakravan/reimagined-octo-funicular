"""
Chat handler for the bot.
Handles starting chat, ending chat, and video call requests.
"""
import asyncio
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter

from db.database import get_db
from db.crud import get_user_by_telegram_id, get_user_by_id, check_user_premium, get_system_setting_value, spend_points, get_user_points, add_points, set_system_setting
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
from utils.validators import get_display_name

router = Router()


class ChatStates(StatesGroup):
    """FSM states for chat."""
    waiting_preferred_gender = State()
    waiting_chat_filters = State()


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
    """Process preferred gender selection for chat (direct selection: female/male/random)."""
    if not matchmaking_queue or not chat_manager:
        await callback.answer("❌ خطای سیستم. لطفاً دوباره تلاش کنید.", show_alert=True)
        return
    
    preferred_gender = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    # Convert "all" to None for random search
    if preferred_gender == "all":
        preferred_gender = None
    
    # Directly add to queue with same_age filter from user's default settings
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
            from bot.keyboards.common import get_cancel_search_keyboard
            try:
                await callback.message.edit_text(
                "⏳ در حال جستجو هستی ! 🔍\n\n"
                "💡 اگه می‌خوای جستجوی جدیدی شروع کنی، اول جستجوی قبلی رو لغو کن ⏹️",
                    reply_markup=get_cancel_search_keyboard()
                )
            except:
                await callback.message.answer(
                    "⏳ در حال جستجو هستی ! 🔍\n\n"
                    "💡 اگه می‌خوای جستجوی جدیدی شروع کنی، اول جستجوی قبلی رو لغو کن ⏹️",
                    reply_markup=get_cancel_search_keyboard()
                )
            await callback.answer()
            return
        
        await callback.answer()
        
        # Get user's default same_age filter setting
        filter_same_age = getattr(user, 'default_chat_filter_same_age', True)
        
        # Add to queue directly
        await add_user_to_queue_direct(
            callback=callback,
            state=state,
            user=user,
            db_session=db_session,
            preferred_gender=preferred_gender,
            filter_same_age=filter_same_age,
            filter_same_city=False,
            filter_same_province=False,
        )
        break


@router.callback_query(F.data == "chat:filter_city")
async def filter_by_city(callback: CallbackQuery, state: FSMContext):
    """Show gender selection after choosing city filter."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        
        if not user or not user.gender or not user.age or not user.city:
            await callback.answer(
                "❌ لطفاً ابتدا پروفایل خودت را کامل کن. /start را بزنید.",
                show_alert=True
            )
            return
        
        await callback.answer()
        
        from bot.keyboards.common import get_city_province_gender_keyboard
        try:
            await callback.message.edit_text(
                "🏙️ جستجوی همشهری\n\n"
                "مخاطب شما چه جنسیتی باشه؟",
                reply_markup=get_city_province_gender_keyboard("city")
            )
        except:
            await callback.message.answer(
                "🏙️ جستجوی همشهری\n\n"
                "مخاطب شما چه جنسیتی باشه؟",
                reply_markup=get_city_province_gender_keyboard("city")
            )
        break


@router.callback_query(F.data == "chat:filter_province")
async def filter_by_province(callback: CallbackQuery, state: FSMContext):
    """Show gender selection after choosing province filter."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        
        if not user or not user.gender or not user.age or not user.city:
            await callback.answer(
                "❌ لطفاً ابتدا پروفایل خودت را کامل کن. /start را بزنید.",
                show_alert=True
            )
            return
        
        await callback.answer()
        
        from bot.keyboards.common import get_city_province_gender_keyboard
        try:
            await callback.message.edit_text(
                "🗺️ جستجوی هم‌استانی\n\n"
                "مخاطب شما چه جنسیتی باشه؟",
                reply_markup=get_city_province_gender_keyboard("province")
            )
        except:
            await callback.message.answer(
                "🗺️ جستجوی هم‌استانی\n\n"
                "مخاطب شما چه جنسیتی باشه؟",
                reply_markup=get_city_province_gender_keyboard("province")
            )
        break


@router.callback_query(F.data == "chat:toggle_same_age")
async def toggle_same_age_filter(callback: CallbackQuery):
    """Toggle same age filter setting."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Toggle the setting
        current_value = getattr(user, 'default_chat_filter_same_age', True)
        user.default_chat_filter_same_age = not current_value
        await db_session.commit()
        
        new_value = user.default_chat_filter_same_age
        status_text = "✅ فعال شد" if new_value else "❌ غیرفعال شد"
        
        await callback.answer(f"🎂 فیلتر همسن {status_text}", show_alert=False)
        
        # Update the keyboard to show new status
        from bot.keyboards.common import get_preferred_gender_keyboard
        try:
            await callback.message.edit_reply_markup(reply_markup=get_preferred_gender_keyboard(same_age_enabled=new_value))
        except:
            pass
        break


@router.callback_query(F.data.startswith("chat_filter:"))
async def process_city_province_filters(callback: CallbackQuery, state: FSMContext):
    """Process city/province filter with gender selection."""
    if not matchmaking_queue or not chat_manager:
        await callback.answer("❌ خطای سیستم. لطفاً دوباره تلاش کنید.", show_alert=True)
        return
    
    # Parse callback data: chat_filter:city:gender or chat_filter:province:gender
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("❌ خطا در پردازش درخواست.", show_alert=True)
        return
    
    filter_type = parts[1]  # 'city' or 'province'
    preferred_gender_str = parts[2]  # 'female', 'male', or 'all'
    
    user_id = callback.from_user.id
    
    # Convert gender string
    if preferred_gender_str == "all":
        preferred_gender = None
    else:
        preferred_gender = preferred_gender_str
    
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
            from bot.keyboards.common import get_cancel_search_keyboard
            try:
                await callback.message.edit_text(
                    "⏳ در حال جستجو هستی ! 🔍\n\n"
                    "💡 اگه می‌خوای جستجوی جدیدی شروع کنی، اول جستجوی قبلی رو لغو کن ⏹️",
                    reply_markup=get_cancel_search_keyboard()
                )
            except:
                await callback.message.answer(
                    "⏳ در حال جستجو هستی ! 🔍\n\n"
                    "💡 اگه می‌خوای جستجوی جدیدی شروع کنی، اول جستجوی قبلی رو لغو کن ⏹️",
                    reply_markup=get_cancel_search_keyboard()
                )
            await callback.answer()
            return
        
        await callback.answer()
        
        # Set filters based on type
        filter_same_city = (filter_type == "city")
        filter_same_province = (filter_type == "province")
        # Use user's default same_age filter setting
        filter_same_age = getattr(user, 'default_chat_filter_same_age', True)
        
        # Add to queue
        await add_user_to_queue_direct(
            callback=callback,
            state=state,
            user=user,
            db_session=db_session,
            preferred_gender=preferred_gender,
            filter_same_age=filter_same_age,
            filter_same_city=filter_same_city,
            filter_same_province=filter_same_province,
        )
        break


async def add_user_to_queue_direct(
    callback: CallbackQuery,
    state: FSMContext,
    user,
    db_session,
    preferred_gender: Optional[str],
    filter_same_age: bool,
    filter_same_city: bool,
    filter_same_province: bool,
):
    """Helper function to add user to queue with filters and show status."""
    user_id = user.telegram_id
    
    # Check if user has premium
    from db.crud import check_user_premium, get_system_setting_value, get_user_points
    user_premium = await check_user_premium(db_session, user.id)
    
    # Get filtered chat cost from database (non-refundable)
    filtered_chat_cost_str = await get_system_setting_value(db_session, 'filtered_chat_cost', '1')
    try:
        filtered_chat_cost = int(filtered_chat_cost_str)
    except (ValueError, TypeError):
        filtered_chat_cost = 1  # Default fallback
    
    user_points = await get_user_points(db_session, user.id)
    
    success_message_count_male_str = await get_system_setting_value(db_session, 'chat_success_message_count', str(settings.CHAT_SUCCESS_MESSAGE_COUNT_MALE))
    try:
        required_message_count_male = int(success_message_count_male_str)
    except (ValueError, TypeError):
        required_message_count_male = settings.CHAT_SUCCESS_MESSAGE_COUNT_MALE

    # Check if user has enough coins for filtered chat
    if not user_premium and preferred_gender is not None and user_points < filtered_chat_cost:
        from db.crud import get_visible_coin_packages, get_visible_premium_plans
        from bot.keyboards.coin_package import get_insufficient_coins_keyboard
        
        packages = await get_visible_coin_packages(db_session)
        premium_plans = await get_visible_premium_plans(db_session)
        
        text = (
            f"💡 هزینه‌ی این چت {filtered_chat_cost} سکه است؛ در صورت موفقیت چت (حداقل {required_message_count_male} پیام از پسر) ازت کسر می‌شود.\n\n"
            f"💰 سکه فعلی تو: {user_points}\n\n"
            f"💡 می‌تونی:\n"
            f"🔹 سکه‌هات رو به پریمیوم تبدیل کنی\n"
            f"🔹 یا پریمیوم بگیری (چت رایگان)\n"
            f"🔹 یا «جستجوی شانسی» رو انتخاب کنی (رایگان)\n"
            f"🔹 یا از پایین منو سکهٔ رایگان روزانه بگیری 👇\n"
            f"🔹 راستی با دعوت دوستات و تکمیل پروفایل‌شون 15 تا سکه بگیری"
        )


        try:
            await callback.message.edit_text(
                text,
           
                reply_markup=get_insufficient_coins_keyboard(packages, premium_plans)
            )
        except:
            await callback.message.answer(
                text,
       
                reply_markup=get_insufficient_coins_keyboard(packages, premium_plans)
            )
        await state.clear()
        return
        
    # Add user to queue
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"DEBUG: User {user_id} adding to queue with preferred_gender: {preferred_gender}, filters: age={filter_same_age}, city={filter_same_city}, province={filter_same_province}, is_premium: {user_premium}")
    
    await matchmaking_queue.add_user_to_queue(
        user_id=user_id,
        gender=user.gender,
        city=user.city,
        age=user.age,
        preferred_gender=preferred_gender,
        min_age=None,
        max_age=None,
        preferred_city=None,
        filter_same_age=filter_same_age,
        filter_same_city=filter_same_city,
        filter_same_province=filter_same_province,
        province=user.province,
        is_premium=user_premium,
    )
    logger.info(f"DEBUG: User {user_id} added to queue successfully")
    
    from bot.keyboards.common import get_queue_status_keyboard
    
    # Helper function to generate cost summary
    def get_search_cost_summary():
        if user_premium:
            return "💰 هزینه: رایگان (پریمیوم)"
        elif preferred_gender is None:
            return "💰 هزینه: رایگان (شانسی)"
        elif user_points < filtered_chat_cost:
            return f"💡 هزینه این چت {filtered_chat_cost} سکه است؛ در صورت موفقیت چت، ازت کسر می‌شود"
        else:
            return f"💰 هزینه: {filtered_chat_cost} سکه"
    
    cost_summary = get_search_cost_summary()
    
    # Build filter description
    filter_desc = []
    if filter_same_age:
        filter_desc.append("🎂 همسن")
    if filter_same_city:
        filter_desc.append("🏙️ همشهری")
    if filter_same_province:
        filter_desc.append("🗺️ هم‌استانی")
    filter_text = " | ".join(filter_desc) if filter_desc else "بدون فیلتر"
    
    # Build queue status message
    if not user_premium:
        queue_status_text = (
            f"🔍 در حال جستجو...\n\n"
            f"{cost_summary}\n"
            f"🔎 فیلتر: {filter_text}\n\n"
            f"⏳  لطفاً صبر کنید در حال جستجوی مخاطب شما هستم...\n\n"
            f"💎✨ با پریمیوم تجربه بهتری داشته باش! ✨💎\n\n"
            f"🎁 ویژگی‌های پریمیوم:\n"
            f"✅ چت نامحدود بدون سکه و رایگان\n"
            f"✅ درخواست تماس  نامحدود و رایگان\n"
            f"✅ پیام دایرکت  نامحدود و رایگان\n"
            f"✅ اولویت در صف (نفر اول صف)\n\n"
            f"🚀💎 همین الان پریمیوم بخر و اول صف باش! 💎🚀"
        )
    else:
        queue_status_text = (
            f"🔍 در حال جستجو...\n\n"
            f"{cost_summary}\n"
            f"🔎 فیلتر: {filter_text}\n\n"
            f"⏳  لطفاً صبر کنید در حال جستجوی مخاطب شما هستم..."
        )
        
    try:
        await callback.message.edit_text(
            queue_status_text,
            reply_markup=get_queue_status_keyboard(user_premium)
        )
    except:
        await callback.message.answer(
            queue_status_text,
            reply_markup=get_queue_status_keyboard(user_premium)
        )
        
        await state.clear()
        
    return


async def check_matchmaking_timeout_with_virtual(
    user_id: int, 
    telegram_id: int, 
    db_user_id: int,
    user_age: Optional[int],
    user_city: Optional[str],
    user_province: Optional[str],
    preferred_gender: Optional[str],
    timeout_seconds: int = 45,
    virtual_gender: str = "female",  # "female" or "male"
    filter_same_age: bool = False,
    filter_same_city: bool = False,
    filter_same_province: bool = False
):
    """
    Check if user is still in queue after timeout and create virtual profile if needed.
    Used for boys searching for girls - creates virtual female profile after 40-50 seconds.
    """
    import logging
    logger = logging.getLogger(__name__)
    import time as time_module
    from core.matchmaking_worker import matchmaking_queue
    
    start_time = time_module.time()
    logger.info(f"Virtual profile timeout task started for user {user_id}, will check after {timeout_seconds} seconds")
    
    try:
        # Wait for timeout (40-50 seconds)
        await asyncio.sleep(timeout_seconds)
        
        elapsed_time = time_module.time() - start_time
        logger.info(f"Virtual profile timeout check triggered for user {user_id} after {elapsed_time:.1f} seconds")
    except asyncio.CancelledError:
        logger.info(f"Virtual profile timeout task cancelled for user {user_id}")
        raise
    
    # Check if user is still in queue
    if matchmaking_queue and await matchmaking_queue.is_user_in_queue(user_id):
        logger.info(f"User {user_id} is still in queue after {timeout_seconds} seconds, checking for active chat")
        # Before creating virtual profile, check if user has active chat
        async for db_session in get_db():
            user = await get_user_by_telegram_id(db_session, telegram_id)
            if not user:
                logger.warning(f"User {user_id} not found in DB during virtual profile timeout check")
                break
            
            # Check if user has active chat
            if chat_manager and await chat_manager.is_chat_active(user.id, db_session):
                # User has active chat, they were matched successfully
                logger.info(f"User {user_id} has active chat, removing from queue silently (matched successfully)")
                await matchmaking_queue.remove_user_from_queue(user_id)
                break
            
            # User is still in queue and has no active chat - create virtual profile
            logger.info(f"User {user_id} still in queue with no active chat after {timeout_seconds} seconds, checking for real users before creating virtual profile")
            
            # IMPORTANT: Before creating virtual profile, check MULTIPLE TIMES if there's a real user available
            # This ensures we ALWAYS prioritize real users over virtual profiles
            # Try 10 times with 1 second delay between attempts
            real_match_found = False
            if matchmaking_queue:
                for attempt in range(5):
                    logger.info(f"User {user_id}: Attempt {attempt + 1}/10 to find real match before creating virtual profile")
                    match_id = await matchmaking_queue.find_match(user_id)
                    if match_id:
                        logger.info(f"User {user_id} found real match {match_id} on attempt {attempt + 1}, connecting users now...")
                        # Connect the matched users immediately
                        from core.matchmaking_worker import connect_users
                        await connect_users(user_id, match_id)
                        real_match_found = True
                        break  # Match found, no need for virtual profile
                    
                    # Check if user was removed from queue (matched by another worker)
                    if not await matchmaking_queue.is_user_in_queue(user_id):
                        logger.info(f"User {user_id} was removed from queue (possibly matched), aborting virtual profile creation")
                        real_match_found = True
                        break
                    
                    # Check if user now has active chat
                    if chat_manager and await chat_manager.is_chat_active(user.id, db_session):
                        logger.info(f"User {user_id} now has active chat, aborting virtual profile creation")
                        real_match_found = True
                        break
                    
                    # Wait 1 second before next attempt (unless this is the last attempt)
                    if attempt < 9:
                        await asyncio.sleep(1.0)
            
            if real_match_found:
                return  # Real match found or user matched by worker, no need for virtual profile
            
            # No real match found after 10 attempts, proceed with virtual profile
            logger.info(f"No real users available for user {user_id} after 10 attempts, creating virtual profile")
            
            # Remove from queue first
            await matchmaking_queue.remove_user_from_queue(user_id)
            
            # Get or create virtual female profile from new virtual_profiles table
            from db.virtual_profile_crud import get_or_create_virtual_profile
            try:
                # Get activity_tracker for setting online status
                from main import activity_tracker, redis_client
                import json
                
                # Get recently used virtual profiles for this user from Redis
                exclude_profile_ids = []
                if redis_client:
                    try:
                        redis_key = f"user:virtual_profiles:{user_id}"
                        recently_used_str = await redis_client.get(redis_key)
                        
                        if recently_used_str:
                            try:
                                if isinstance(recently_used_str, bytes):
                                    recently_used_str = recently_used_str.decode('utf-8')
                                exclude_profile_ids = json.loads(recently_used_str)
                                # Keep only last 10 profiles to avoid excluding too many
                                exclude_profile_ids = exclude_profile_ids[-10:]
                                logger.info(f"User {user_id} has {len(exclude_profile_ids)} recently used virtual profiles to exclude: {exclude_profile_ids}")
                            except (json.JSONDecodeError, ValueError):
                                exclude_profile_ids = []
                        else:
                            logger.info(f"User {user_id} has no recently used virtual profiles")
                    except Exception as e:
                        logger.warning(f"Failed to get recently used profiles from Redis: {e}")
                        exclude_profile_ids = []
                
                # Try to get a virtual profile that is not in an active chat
                # Use multiple attempts to find a different profile each time
                virtual_profile = None
                max_attempts = 15  # More attempts to find a different profile
                used_profile_ids = set(exclude_profile_ids)  # Track used profiles
                
                # Get a virtual profile (this handles everything - selection, creation, uniqueness)
                # Pass user's filters (age, city, province) to match appropriate virtual profiles
                # Also pass the gender of virtual profile to create
                
                # Get or create virtual profile with specified gender
                virtual_profile = await get_or_create_virtual_profile(
                    db_session,
                    user_age=user_age if filter_same_age else None,  # Only filter by age if user enabled it
                    user_city=user_city if filter_same_city else None,  # Only filter by city if user selected it
                    user_province=user_province if filter_same_province else None,  # Only filter by province if user selected it
                    exclude_profile_ids=list(used_profile_ids),
                    activity_tracker=activity_tracker,
                    gender=virtual_gender  # Pass the desired gender
                )
                
                # Eager load the user relationship to avoid lazy loading issues
                from sqlalchemy.orm import selectinload
                from sqlalchemy import select as sql_select
                from db.models import VirtualProfile as VP
                virtual_profile_query = sql_select(VP).options(
                    selectinload(VP.user)
                ).where(VP.id == virtual_profile.id)
                result = await db_session.execute(virtual_profile_query)
                virtual_profile = result.scalars().first()
                
                # Store this profile ID in Redis for future exclusions (keep last 10)
                if virtual_profile and redis_client:
                    try:
                        exclude_profile_ids.append(virtual_profile.id)
                        exclude_profile_ids = exclude_profile_ids[-10:]  # Keep only last 10
                        redis_key = f"user:virtual_profiles:{user_id}"
                        await redis_client.setex(
                            redis_key,
                            86400,  # 24 hours TTL
                            json.dumps(exclude_profile_ids)
                        )
                        logger.info(f"Stored virtual profile {virtual_profile.id} in Redis exclusion list for user {user_id}, total excluded: {len(exclude_profile_ids)}")
                    except Exception as e:
                        logger.warning(f"Failed to store recently used profile in Redis: {e}")
                
                logger.info(f"Selected virtual profile {virtual_profile.id} (user_id: {virtual_profile.user_id}, name: {virtual_profile.display_name}) for user {user_id}")
                
                # Create chat between user and virtual profile's user
                if chat_manager:
                    # Set preferred_gender to None for virtual profile to make it free (like "all" option)
                    chat_room = await chat_manager.create_chat(
                        user1_id=user.id,
                        user2_id=virtual_profile.user_id,  # Use virtual_profile.user_id instead of virtual_profile.id
                        db_session=db_session,
                        user1_preferred_gender=preferred_gender if preferred_gender else None,  # Use actual preferred_gender or None
                        user2_preferred_gender=None,  # Virtual profile always uses "all" (free)
                    )
                    logger.info(f"Created chat room {chat_room.id} between user {user.id} and virtual profile {virtual_profile.id} (user_id={virtual_profile.user_id})")
                    
                    # Get user premium status and cost info (like real matchmaking)
                    from db.crud import check_user_premium, get_user_points, get_system_setting_value
                    user_premium = await check_user_premium(db_session, user.id)
                    
                    # Get filtered chat cost from database (same as real matchmaking)
                    filtered_chat_cost_str = await get_system_setting_value(db_session, 'filtered_chat_cost', '1')
                    try:
                        filtered_chat_cost = int(filtered_chat_cost_str)
                    except (ValueError, TypeError):
                        filtered_chat_cost = 1  # Default fallback
                    
                    user_points = await get_user_points(db_session, user.id)
                    
                    # Deduct coins for virtual profile chats (same as real matches)
                    # If user selected filtered chat (preferred_gender is not None), deduct coins
                    user_coins_deducted = False
                    if not user_premium and preferred_gender is not None:
                        # Check if user has enough coins
                        if user_points >= filtered_chat_cost:
                            from db.crud import spend_points
                            success = await spend_points(
                                db_session,
                                user.id,
                                filtered_chat_cost,
                                "spent",
                                "filtered_chat",
                                f"Cost for filtered chat with virtual profile (non-refundable)"
                            )
                            if success:
                                user_coins_deducted = True
                                user_points -= filtered_chat_cost
                                logger.info(f"User {user.id}: Deducted {filtered_chat_cost} coins for virtual profile filtered chat, remaining: {user_points}")
                    
                    # Helper function to generate cost summary (same as matchmaking_worker)
                    def get_match_cost_summary(is_premium, pref_gender, coins_deducted, cost, points):
                        # Show cost based on user's premium status and preference
                        if is_premium:
                            return "💰 هزینه: رایگان (پریمیوم)"
                        elif pref_gender is None:
                            return "💰 هزینه: رایگان (شانسی)"
                        else:
                            # User selected specific gender, show cost
                            if coins_deducted:
                                return f"💰 {cost} سکه کسر شد (باقی‌مانده: {points})"
                            else:
                                return f"💡 هزینه این چت {cost} سکه است؛ در صورت موفقیت چت ازت کسر می‌شود"
                    
                    # Send notification to user that they are connected (exactly like real match)
                    bot = Bot(token=settings.BOT_TOKEN)
                    try:
                        user_cost_summary = get_match_cost_summary(
                            user_premium, preferred_gender, user_coins_deducted, filtered_chat_cost, user_points
                        )
                        
                        connection_msg = (
                            "✅ هم‌چت پیدا شد!\n\n"
                            f"{user_cost_summary}\n\n"
                            "💬 می‌تونید شروع به چت کنید."
                        )
                        
                        await bot.send_message(
                            telegram_id,
                            connection_msg,
                            reply_markup=get_chat_reply_keyboard()
                        )
                        await bot.session.close()
                    except Exception as e:
                        logger.error(f"Failed to send connection message to user {user_id}: {e}")
                    
                    # Wait random time (2-5 seconds) before sending "پروفایلت مشاهده شد"
                    import random
                    wait_time = random.uniform(2.0, 5.0)
                    await asyncio.sleep(wait_time)
                    
                    # Send "پروفایلت مشاهده شد" message (as if from virtual profile)
                    try:
                        bot = Bot(token=settings.BOT_TOKEN)
                        await bot.send_message(
                            telegram_id,
                            "👁️ مخاطبت پروفایلت رو مشاهده کرد!"
                        )
                        await bot.session.close()
                    except Exception as e:
                        logger.error(f"Failed to send profile viewed message: {e}")
                    
                    # Wait random time (3-8 seconds) before automatically ending the chat
                    wait_time = random.uniform(3.0, 8.0)
                    await asyncio.sleep(wait_time)
                    
                    # End the chat
                    try:
                        await chat_manager.end_chat(chat_room.id, db_session)
                        logger.info(f"Ended chat {chat_room.id} with virtual profile")
                        
                        # Get cost summary for end chat (same as real end_chat_confirm)
                        from db.crud import check_user_premium, get_user_points, get_system_setting_value
                        user_premium = await check_user_premium(db_session, user.id)
                        user_current_points = await get_user_points(db_session, user.id)
                        
                        # Get filtered chat cost from database
                        filtered_chat_cost_str = await get_system_setting_value(db_session, 'filtered_chat_cost', '1')
                        try:
                            filtered_chat_cost = int(filtered_chat_cost_str)
                        except (ValueError, TypeError):
                            filtered_chat_cost = 1  # Default fallback
                        
                        # Helper function to generate cost summary (same as end_chat_confirm)
                        def get_cost_summary(is_premium, pref_gender, cost):
                            # Show actual deduction status
                            if is_premium:
                                return "💰 این چت رایگان بود (پریمیوم)"
                            elif pref_gender is None:
                                return "💰 این چت رایگان بود (شانسی)"
                            else:
                                # User selected specific gender, coins were deducted (non-refundable)
                                return f"💰 {cost} سکه کسر شد"
                        
                        user_cost_summary = get_cost_summary(
                            user_premium,
                            preferred_gender,
                            filtered_chat_cost
                        )
                        
                        # Get virtual profile profile_id
                        virtual_profile_id_text = f"/user_{virtual_profile.profile_id}" if virtual_profile.profile_id else "کاربر"
                        
                        # Create keyboard with only "جستجوی دوباره" and "حذف پیام‌ها" (same as real end_chat)
                        search_again_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                            [
                                InlineKeyboardButton(text="🔍 جستجوی دوباره", callback_data="chat:search_again"),
                            ],
                            [
                                InlineKeyboardButton(text="🗑️ حذف پیام‌های من", callback_data="chat:delete_my_messages"),
                            ],
                        ])
                        
                        # Send end chat message (exactly like real end_chat)
                        bot = Bot(token=settings.BOT_TOKEN)
                        await bot.send_message(
                            telegram_id,
                            f"💬 چت شما با {virtual_profile_id_text} به پایان رسید\n\n"
                            f"{user_cost_summary}",
                            reply_markup=search_again_keyboard
                        )
                        # Update reply keyboard
                        await bot.send_message(
                            telegram_id,
                            "📱 منوی اصلی",
                            reply_markup=get_main_reply_keyboard()
                        )
                        await bot.session.close()
                    except Exception as e:
                        logger.error(f"Failed to end chat with virtual profile: {e}")
                
            except Exception as e:
                logger.error(f"Failed to create virtual profile for user {user_id}: {e}")
                # Fallback to normal timeout message
                bot = Bot(token=settings.BOT_TOKEN)
                try:
                    await bot.send_message(
                        telegram_id,
                        "❌ متأسفانه کسی رو برات پیدا نکردیم.\n\n"
                        "💡 می‌تونی دوباره امتحان کنی یا از طریق پروفایل‌ها با کاربران خاص چت کنی."
                    )
                    await bot.session.close()
                except Exception:
                    pass
            break
    else:
        # User is no longer in queue (removed by matchmaking worker or manually)
        # IMPORTANT: Still check if they have active chat to avoid race conditions
        logger.info(f"User {user_id} is no longer in queue (may have been matched or removed), checking if they have active chat")
        
        async for db_session in get_db():
            user = await get_user_by_telegram_id(db_session, telegram_id)
            if not user:
                logger.warning(f"User {user_id} not found in DB during virtual profile timeout check (no longer in queue)")
                break
            
            # Check if user has active chat (they were matched successfully)
            if chat_manager and await chat_manager.is_chat_active(user.id, db_session):
                # User was matched successfully, don't create virtual profile
                logger.info(f"User {user_id} has active chat (matched successfully), aborting virtual profile creation")
                break
            else:
                logger.info(f"User {user_id} has no active chat and not in queue, safe to proceed (user cancelled search)")
            break


async def check_matchmaking_timeout(user_id: int, telegram_id: int):
    """Check if user is still in queue after 2 minutes and notify if no match found."""
    import logging
    logger = logging.getLogger(__name__)
    import time as time_module
    
    start_time = time_module.time()
    logger.info(f"Timeout task started for user {user_id}, will check after 120 seconds")
    
    try:
        # Wait exactly 2 minutes (120 seconds)
        await asyncio.sleep(120)
        
        elapsed_time = time_module.time() - start_time
        logger.info(f"Timeout check triggered for user {user_id} after {elapsed_time:.1f} seconds (expected: 120 seconds)")
    except asyncio.CancelledError:
        logger.info(f"Timeout task cancelled for user {user_id}")
        raise
    
    # Check if user is still in queue
    if matchmaking_queue and await matchmaking_queue.is_user_in_queue(user_id):
        logger.info(f"User {user_id} is still in queue after 120 seconds, checking for active chat")
        # Before sending timeout message, check if user has active chat
        # If user has active chat, they were matched successfully, don't send timeout
        async for db_session in get_db():
            user = await get_user_by_telegram_id(db_session, telegram_id)
            if not user:
                logger.warning(f"User {user_id} not found in DB during timeout check")
                break
            
            # Check if user has active chat
            if chat_manager and await chat_manager.is_chat_active(user.id, db_session):
                # User has active chat, they were matched successfully
                logger.info(f"User {user_id} has active chat, removing from queue silently (matched successfully)")
                # Just remove from queue silently (they might have been matched but not removed from queue)
                await matchmaking_queue.remove_user_from_queue(user_id)
                break
            
            # User is still in queue and has no active chat, no match found
            logger.info(f"User {user_id} still in queue with no active chat after 120 seconds, sending timeout message")
            # Remove from queue
            await matchmaking_queue.remove_user_from_queue(user_id)
            
            # Notify user
            bot = Bot(token=settings.BOT_TOKEN)
            try:
                await bot.send_message(
                    telegram_id,
                    "❌ متأسفانه کسی رو برات پیدا نکردیم.\n\n"
                    "💡 می‌تونی دوباره امتحان کنی یا از طریق پروفایل‌ها با کاربران خاص چت کنی."
                )
                await bot.session.close()
                logger.info(f"Timeout message sent to user {user_id}")
            except Exception as e:
                logger.error(f"Failed to send timeout message to user {user_id}: {e}")
            break
    else:
        logger.info(f"User {user_id} is no longer in queue (may have been matched or removed)")


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
        # Get user's default same_age filter setting
        default_same_age = getattr(user, 'default_chat_filter_same_age', True)
        await callback.message.edit_text(
            "💬 شروع چت ناشناس\n\n"
            "انتخاب کن با کی میخوای چت کنی ؟ 🚀\n\n"
             "انتخاب فیلترها ممکنه روی سرعت چتت اثر بگذاره 💡",
            reply_markup=get_preferred_gender_keyboard(same_age_enabled=default_same_age)
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
                    # Get preferred genders from queue data
                    user_data = await matchmaking_queue.get_user_data(telegram_id)
                    matched_user_data = await matchmaking_queue.get_user_data(match_telegram_id)
                    
                    # Get raw values
                    user_pref_gender_raw = user_data.get("preferred_gender") if user_data else None
                    matched_user_pref_gender_raw = matched_user_data.get("preferred_gender") if matched_user_data else None
                    
                    # Normalize: convert "all" or None to None, keep "male" and "female" as is
                    # IMPORTANT: If raw value is "male" or "female", keep it as is!
                    if user_pref_gender_raw is None:
                        user_pref_gender = None
                    elif user_pref_gender_raw == "all":
                        user_pref_gender = None
                    elif user_pref_gender_raw in ["male", "female"]:
                        user_pref_gender = user_pref_gender_raw
                    else:
                        # Unknown value, treat as None
                        user_pref_gender = None
                    
                    if matched_user_pref_gender_raw is None:
                        matched_user_pref_gender = None
                    elif matched_user_pref_gender_raw == "all":
                        matched_user_pref_gender = None
                    elif matched_user_pref_gender_raw in ["male", "female"]:
                        matched_user_pref_gender = matched_user_pref_gender_raw
                    else:
                        # Unknown value, treat as None
                        matched_user_pref_gender = None
                    
                    # Create chat room with preferred genders
                    chat_room = await chat_manager.create_chat(
                        user.id, 
                        matched_user.id, 
                        db_session,
                        user1_preferred_gender=user_pref_gender,
                        user2_preferred_gender=matched_user_pref_gender
                    )
                    
                    # Notify both users and deduct coins if needed
                    from aiogram import Bot
                    from db.crud import check_user_premium, spend_points, get_user_points
                    from core.points_manager import PointsManager
                    from db.crud import get_system_setting_value
                    
                    # Check premium status
                    user_premium = await check_user_premium(db_session, user.id)
                    matched_user_premium = await check_user_premium(db_session, matched_user.id)
                    
                    # Get chat cost from system settings
                    chat_cost_str = await get_system_setting_value(db_session, 'chat_message_cost', '3')
                    try:
                        chat_cost = int(chat_cost_str)
                    except (ValueError, TypeError):
                        chat_cost = 3
                    
                    # Get user points
                    user_points = await get_user_points(db_session, user.id)
                    matched_user_points = await get_user_points(db_session, matched_user.id)
                    
                    # Deduct coins for non-premium users
                    # Simple logic: if preferred_gender is "male" or "female", deduct coins
                    # If preferred_gender is None (meaning "all"), don't deduct coins
                    user_coins_deducted = False
                    matched_user_coins_deducted = False
                    
                    # Helper function to generate cost summary for match found
                    def get_match_cost_summary(is_premium, pref_gender, coins_deducted, chat_cost, points):
                        if is_premium:
                            return "💰 هزینه: رایگان (پریمیوم)"
                        elif pref_gender is None:
                            return "💰 هزینه: رایگان (شانسی)"
                        elif coins_deducted:
                            return f"💰 {chat_cost} سکه کسر شد (باقی‌مانده: {points})"
                        else:
                            return f"💡 هزینه این چت {chat_cost} سکه است؛ در صورت موفقیت چت ازت کسر می‌شود"
                    
                    # Prepare messages with beautiful UI
                    user_cost_summary = get_match_cost_summary(
                        user_premium, user_pref_gender, user_coins_deducted, chat_cost, user_points
                    )
                    matched_user_cost_summary = get_match_cost_summary(
                        matched_user_premium, matched_user_pref_gender, matched_user_coins_deducted, chat_cost, matched_user_points
                    )
                    
                    user_msg = (
                        "✅ هم‌چت پیدا شد!\n\n"
                        f"{user_cost_summary}\n\n"
                        "💬 می‌تونید شروع به چت کنید."
                    )
                    
                    matched_user_msg = (
                        "✅ هم‌چت پیدا شد!\n\n"
                        f"{matched_user_cost_summary}\n\n"
                        "💬 می‌تونید شروع به چت کنید."
                        )
                    
                    
                    bot = Bot(token=settings.BOT_TOKEN)
                    
                    await bot.send_message(
                        user.telegram_id,
                        user_msg,
                        reply_markup=get_chat_reply_keyboard()
                    )
                    
                    await bot.send_message(
                        matched_user.telegram_id,
                        matched_user_msg,
                        reply_markup=get_chat_reply_keyboard()
                    )
                    
                    await bot.session.close()
                    
                    # Remove users from queue after sending messages
                    await matchmaking_queue.remove_user_from_queue(telegram_id)
                    await matchmaking_queue.remove_user_from_queue(match_telegram_id)
                    
                    # IMPORTANT: Don't let worker connect these users again
                    # Mark them as processed so worker skips them
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
        from db.crud import get_active_chat_room_by_user, get_user_by_id
        chat_room = await get_active_chat_room_by_user(db_session, user.id)
        
        if chat_room:
            # Get partner before ending chat
            partner_id = await chat_manager.get_partner_id(user.id, db_session)
            
            # Get partner object before ending chat (for notifications)
            partner = None
            if partner_id:
                partner = await get_user_by_id(db_session, partner_id)
            
            # Get message IDs before ending chat (for deletion)
            user1_message_ids = await chat_manager.get_message_ids(chat_room.id, chat_room.user1_id)
            user2_message_ids = await chat_manager.get_message_ids(chat_room.id, chat_room.user2_id)
            
            # Get user Telegram IDs for message deletion
            user1_telegram_id = user.telegram_id
            user2_telegram_id = None
            if partner:
                user2_telegram_id = partner.telegram_id
            
            # Add both users to each other's blocked list to prevent re-matching
            if partner and matchmaking_queue:
                await matchmaking_queue.add_blocked_user(user1_telegram_id, user2_telegram_id)
            
            # End chat room and get message counts
            end_result = await chat_manager.end_chat(chat_room.id, db_session)
            if isinstance(end_result, tuple):
                success, message_counts = end_result
            else:
                success = end_result
                message_counts = (0, 0)
            
            # Get message counts for both users
            user1_count, user2_count = message_counts

            # Determine which user is which
            if chat_room.user1_id == user.id:
                current_user_count = user1_count
                partner_user_count = user2_count
            else:
                current_user_count = user2_count
                partner_user_count = user1_count

            # Determine male vs female message counts
            if user.gender == "male":
                male_messages = current_user_count
                female_messages = partner_user_count
                male_id = user.id
                female_id = partner_id
            else:
                male_messages = partner_user_count
                female_messages = current_user_count
                male_id = partner_id
                female_id = user.id

            # Check if any messages were sent
            total_messages = current_user_count + partner_user_count

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
                                    
                                    notify_msg = f"🔔 چت {get_display_name(partner) or 'کاربر'} تمام شد!\n\n"
                                    notify_msg += f"👤 نام: {get_display_name(partner) or 'نامشخص'}\n"
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
            
            # Get required message counts from system settings
            from db.crud import get_system_setting_value
            required_message_count_male_str = await get_system_setting_value(
                db_session,
                'chat_success_message_count',
                str(settings.CHAT_SUCCESS_MESSAGE_COUNT_MALE)
            )
            try:
                required_message_count_male = int(required_message_count_male_str)
            except (ValueError, TypeError):
                required_message_count_male = settings.CHAT_SUCCESS_MESSAGE_COUNT_MALE

            required_message_count_female_str = await get_system_setting_value(
                db_session,
                'chat_success_message_count_female',
                str(settings.CHAT_SUCCESS_MESSAGE_COUNT_FEMALE)
            )
            try:
                required_message_count_female = int(required_message_count_female_str)
            except (ValueError, TypeError):
                required_message_count_female = settings.CHAT_SUCCESS_MESSAGE_COUNT_FEMALE

            # Check if chat was successful for male and female separately
            chat_successful_male = (
                male_messages >= required_message_count_male
                and female_messages >= required_message_count_male
            )
            chat_successful_female = (
                female_id is not None
                and female_messages >= required_message_count_female
                and male_messages >= required_message_count_female
            )

            # Get filtered chat cost to deduct only if chat is successful
            from db.crud import check_user_premium, get_user_points, add_points, get_system_setting_value, spend_points
            from core.points_manager import PointsManager
            from aiogram import Bot
            
            user_premium = await check_user_premium(db_session, user.id)
            partner_premium = await check_user_premium(db_session, partner_id) if partner_id else False
            
            # Get preferred genders to check if "all" was selected
            user_pref_gender = await chat_manager.get_user_preferred_gender(chat_room.id, user.id)
            partner_pref_gender = await chat_manager.get_user_preferred_gender(chat_room.id, partner_id) if partner_id else None
            
            # Get chat cost
            filtered_chat_cost_str = await get_system_setting_value(db_session, 'filtered_chat_cost', '1')
            try:
                chat_cost = int(filtered_chat_cost_str)
            except (ValueError, TypeError):
                chat_cost = 1

            # Deduct coins now that chat success is confirmed
            if chat_successful_male:
                user_can_be_charged = (
                    not user_premium and user_pref_gender is not None and user.gender == "male"
                )
                partner_can_be_charged = (
                    partner_id
                    and partner
                    and not partner_premium
                    and partner_pref_gender is not None
                    and partner.gender == "male"
                )

                if user_can_be_charged:
                    user_balance = await get_user_points(db_session, user.id)
                    if user_balance >= chat_cost:
                        success = await spend_points(
                            db_session,
                            user.id,
                            chat_cost,
                            "spent",
                            "filtered_chat",
                            "Filtered chat cost after success"
                        )
                        if success:
                            await chat_manager.set_chat_cost_deducted(chat_room.id, user.id, True)
                if partner_can_be_charged:
                    partner_balance = await get_user_points(db_session, partner_id)
                    if partner_balance >= chat_cost:
                        success = await spend_points(
                            db_session,
                            partner_id,
                            chat_cost,
                            "spent",
                            "filtered_chat",
                            "Filtered chat cost after success"
                        )
                        if success:
                            await chat_manager.set_chat_cost_deducted(chat_room.id, partner_id, True)

            # Check if coins were deducted for both users
            user_was_cost_deducted = await chat_manager.was_chat_cost_deducted(chat_room.id, user.id)
            partner_was_cost_deducted = await chat_manager.was_chat_cost_deducted(chat_room.id, partner_id) if partner_id else False
            
            # Refund coins if chat was not successful and coins were deducted
            user_coins_refunded = False
            partner_coins_refunded = False
            
            if not user_premium and user_was_cost_deducted and not chat_successful_male:
                # Refund coins for user
                success = await add_points(
                    db_session,
                    user.id,
                    chat_cost,
                    "earned",
                    "chat_refund",
                    f"Refund for unsuccessful chat (less than 2 messages from each user)"
                )
                if success:
                    user_coins_refunded = True
            
            if partner_id and not partner_premium and partner_was_cost_deducted and not chat_successful_male:
                # Refund coins for partner
                success = await add_points(
                    db_session,
                    partner_id,
                    chat_cost,
                    "earned",
                    "chat_refund",
                    f"Refund for unsuccessful chat (less than 2 messages from each user)"
                )
                if success:
                    partner_coins_refunded = True
            
            # Get current points after refund
            user_current_points = await get_user_points(db_session, user.id)
            partner_current_points = await get_user_points(db_session, partner_id) if partner_id else 0
            
            # Helper function to generate cost summary
            def get_cost_summary(is_premium, was_cost_deducted, pref_gender, coins_refunded, chat_cost, current_points):
                """Generate a short cost summary for the chat."""
                if is_premium:
                    return "💰 این چت رایگان بود (پریمیوم)"
                elif was_cost_deducted:
                    if coins_refunded:
                        return f"💰 {chat_cost} سکه برگشت داده شد"
                    else:
                        return f"💰 {chat_cost} سکه کسر شد"
                elif pref_gender is None:
                    return "💰 این چت رایگان بود (همه)"
                else:
                    return "💰 این چت رایگان بود"
            
            # Generate cost summary for user
            user_cost_summary = get_cost_summary(
                user_premium,
                user_was_cost_deducted,
                user_pref_gender,
                user_coins_refunded,
                chat_cost,
                user_current_points
            )
            
            # Get partner profile_id for message
            partner_profile_id_text = ""
            if partner:
                # Generate profile_id if not exists
                if not partner.profile_id:
                    import hashlib
                    profile_id = hashlib.md5(f"user_{partner.telegram_id}".encode()).hexdigest()[:12]
                    partner.profile_id = profile_id
                    await db_session.commit()
                    await db_session.refresh(partner)
                partner_profile_id_text = f"/user_{partner.profile_id}"
            
            # Create keyboard with only "جستجوی دوباره" and "حذف پیام‌ها"
            search_again_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="🔍 جستجوی دوباره", callback_data="chat:search_again"),
                ],
                [
                    InlineKeyboardButton(text="🗑️ حذف پیام‌های من", callback_data="chat:delete_my_messages"),
                ],
            ])
            
            from bot.keyboards.reply import get_main_reply_keyboard
            # Edit the confirmation message to show final message (single message)
            try:
                await callback.message.edit_text(
                    f"💬 چت شما با {partner_profile_id_text} به پایان رسید\n\n"
                    f"{user_cost_summary}",
                reply_markup=search_again_keyboard
            )
                # Update reply keyboard by sending a message with reply keyboard
                await callback.message.answer(
                    "📱 منوی اصلی",
                    reply_markup=get_main_reply_keyboard()
                )
            except:
                # If edit fails, send new message
                await callback.message.answer(
                    f"💬 چت شما با {partner_profile_id_text} به پایان رسید\n\n"
                    f"{user_cost_summary}",
                    reply_markup=search_again_keyboard
                )
                await callback.message.answer(
                    "📱 منوی اصلی",
                    reply_markup=get_main_reply_keyboard()
                )
            
            # Send message to partner if exists
            if partner:
                # Generate cost summary for partner
                partner_cost_summary = get_cost_summary(
                    partner_premium,
                    partner_was_cost_deducted,
                    partner_pref_gender,
                    partner_coins_refunded,
                    chat_cost,
                    partner_current_points
                )
                
                # Get user profile_id for partner's message
                user_profile_id_text = ""
                if not user.profile_id:
                    import hashlib
                    profile_id = hashlib.md5(f"user_{user.telegram_id}".encode()).hexdigest()[:12]
                    user.profile_id = profile_id
                    await db_session.commit()
                    await db_session.refresh(user)
                user_profile_id_text = f"/user_{user.profile_id}"
                
                bot = Bot(token=settings.BOT_TOKEN)
                try:
                    # Create keyboard with only "جستجوی دوباره" and "حذف پیام‌ها"
                    partner_search_again_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text="🔍 جستجوی دوباره", callback_data="chat:search_again"),
                        ],
                        [
                            InlineKeyboardButton(text="🗑️ حذف پیام‌های من", callback_data="chat:delete_my_messages"),
                        ],
                    ])
                    
                    await bot.send_message(
                        partner.telegram_id,
                        f"💬 چت شما با {user_profile_id_text} به پایان رسید\n\n"
                        f"{partner_cost_summary}",
                        reply_markup=partner_search_again_keyboard
                    )
                    # Update keyboard to main keyboard for partner
                    from bot.keyboards.reply import get_main_reply_keyboard as get_main_kb
                    try:
                        await bot.send_message(
                            partner.telegram_id,
                            "📱 منوی اصلی",
                            reply_markup=get_main_kb()
                        )
                    except:
                        pass
                    
                    await bot.session.close()
                except Exception:
                    pass
            
            # Don't delete messages automatically - user can request deletion via button
            # Message IDs are stored in Redis and will be available for deletion request
            
            # Award coins for successful chat
            if chat_successful_female:
                from db.crud import get_coins_for_activity
                from core.event_engine import EventEngine
                from aiogram import Bot as RewardBot
                from core.points_manager import PointsManager as RewardPointsManager

                coins_base = await get_coins_for_activity(db_session, "chat_success")
                if coins_base is None:
                    coins_base = settings.POINTS_CHAT_SUCCESS

                if coins_base and coins_base > 0:
                    reward_users = []
                    if user.gender == "female":
                        reward_users.append(user)
                    if partner and partner.gender == "female":
                        reward_users.append(partner)

                    if reward_users:
                        reward_bot = RewardBot(token=settings.BOT_TOKEN)
                        try:
                            for target in reward_users:
                                actual_coins = await EventEngine.apply_points_multiplier(
                                    target.id,
                                    coins_base,
                                    "chat_success"
                                )
                                await RewardPointsManager.award_points(
                                    target.id,
                                    coins_base,
                                    "chat_success",
                                    "پاداش چت موفق برای دختران"
                                )
                                try:
                                    await reward_bot.send_message(
                                        target.telegram_id,
                                        f"🎉 چت موفقیت‌آمیز بود!\n\n"
                                        f"💰 {int(actual_coins)} سکه به حسابت اضافه شد!\n"
                                        f"💡 میتونی سکه هات رو به پریمیوم تبدیل کنی ، با دوستات بازی کنی یا برای چت اختصاصی با دخترا و پسرای باحال استفاده کنی"
                                    )
                                except Exception:
                                    pass
                        finally:
                            await reward_bot.session.close()
            
            # Check and award badges for chat achievements
            if chat_successful_male:
                from core.achievement_system import AchievementSystem
                from core.badge_manager import BadgeManager
                from db.crud import get_user_chat_count, get_badge_by_key
                from aiogram import Bot as BadgeBot
                
                # Check chat count achievements for both users
                user_chat_count = await get_user_chat_count(db_session, user.id)
                partner_chat_count = await get_user_chat_count(db_session, partner.id) if partner else 0
                
                # Check achievements for user
                completed_achievements = await AchievementSystem.check_chat_count_achievement(user.id, user_chat_count)
                
                # Award badges for completed achievements
                badge_bot = BadgeBot(token=settings.BOT_TOKEN)
                try:
                    for achievement in completed_achievements:
                        if achievement.achievement and achievement.achievement.badge_id:
                            badge = await get_badge_by_key(db_session, achievement.achievement.achievement_key)
                            if badge:
                                await BadgeManager.award_badge_and_notify(
                                    user.id,
                                    badge.badge_key,
                                    badge_bot,
                                    user.telegram_id
                                )
                    
                    # Check achievements for partner
                    if partner:
                        partner_completed = await AchievementSystem.check_chat_count_achievement(partner.id, partner_chat_count)
                        for achievement in partner_completed:
                            if achievement.achievement and achievement.achievement.badge_id:
                                badge = await get_badge_by_key(db_session, achievement.achievement.achievement_key)
                                if badge:
                                    await BadgeManager.award_badge_and_notify(
                                        partner.id,
                                        badge.badge_key,
                                        badge_bot,
                                        partner.telegram_id
                                    )
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error awarding badges: {e}")
                finally:
                    await badge_bot.session.close()
            
            await callback.answer()
        else:
            await callback.answer("❌ چت فعالی یافت نشد.", show_alert=True)
        break


@router.callback_query(F.data == "chat:delete_my_messages")
async def delete_my_messages(callback: CallbackQuery):
    """Delete user's messages from the ended chat."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Get the most recent ended chat room for this user
        from db.models import ChatRoom
        from sqlalchemy import select, desc
        
        result = await db_session.execute(
            select(ChatRoom)
            .where(
                ((ChatRoom.user1_id == user.id) | (ChatRoom.user2_id == user.id))
                & (ChatRoom.is_active == False)
            )
            .order_by(desc(ChatRoom.ended_at))
            .limit(1)
        )
        ended_chat_room = result.scalar_one_or_none()
        
        if not ended_chat_room:
            await callback.answer("❌ چت پایان یافته‌ای یافت نشد.", show_alert=True)
            return
        
        # Get message IDs for this user from Redis
        user_message_ids = await chat_manager.get_message_ids(ended_chat_room.id, user.id)
        
        if not user_message_ids:
            await callback.answer("⚠️ پیامی برای حذف یافت نشد.", show_alert=True)
            return
        
        # Get partner ID to delete messages from their chat too
        partner_id = None
        if ended_chat_room.user1_id == user.id:
            partner_id = ended_chat_room.user2_id
        else:
            partner_id = ended_chat_room.user1_id
        
        # Get partner user to get their telegram_id
        from db.crud import get_user_by_id
        partner = None
        if partner_id:
            partner = await get_user_by_id(db_session, partner_id)
        
        # Delete messages from user's chat
        from aiogram import Bot as DeleteBot
        delete_bot = DeleteBot(token=settings.BOT_TOKEN)
        try:
            deleted_count = 0
            partner_deleted_count = 0
            
            # Delete messages from user's own chat
            for msg_id in user_message_ids:
                try:
                    await delete_bot.delete_message(user.telegram_id, msg_id)
                    deleted_count += 1
                except Exception:
                    pass  # Message might already be deleted or not found
            
            # Also delete messages from partner's chat
            # The messages sent to partner have the same message_id (they were forwarded)
            # But we need to find which messages in partner's chat correspond to user's messages
            # Actually, when we send a message to partner, we store the sent message_id for partner
            # So we need to get message IDs that were sent TO partner (stored under partner's ID)
            # But wait, we stored message_id for partner when we sent the message
            # So we need to get the message IDs that were sent to partner
            
            # Actually, the message IDs stored for user are:
            # 1. Original messages sent by user (stored with user.id)
            # 2. Messages sent to partner (stored with partner.id) - these are the forwarded messages
            
            # So we need to delete:
            # 1. User's original messages (already done above)
            # 2. Messages sent to partner (need to get from partner's message IDs)
            
            if partner:
                # For each user message ID, find the corresponding partner message ID using the mapping
                partner_msg_ids_to_delete = []
                for user_msg_id in user_message_ids:
                    # Get the corresponding partner message ID from the mapping
                    pair_key = chat_manager._get_message_pair_key(ended_chat_room.id, user_msg_id)
                    partner_msg_id_str = await chat_manager.redis.get(pair_key)
                    if partner_msg_id_str:
                        try:
                            partner_msg_id = int(partner_msg_id_str)
                            partner_msg_ids_to_delete.append(partner_msg_id)
                        except (ValueError, TypeError):
                            pass
                
                # Delete the corresponding messages from partner's chat
                for partner_msg_id in partner_msg_ids_to_delete:
                    try:
                        await delete_bot.delete_message(partner.telegram_id, partner_msg_id)
                        partner_deleted_count += 1
                    except Exception:
                        pass  # Message might already be deleted or not found
                
                # Clean up message pair mappings
                for user_msg_id in user_message_ids:
                    pair_key = chat_manager._get_message_pair_key(ended_chat_room.id, user_msg_id)
                    await chat_manager.redis.delete(pair_key)
            
            await delete_bot.session.close()
            
            # Clear message IDs from Redis after deletion
            await chat_manager.clear_message_ids(ended_chat_room.id, user.id)
            
            total_deleted = deleted_count + partner_deleted_count
            if total_deleted > 0:
                await callback.message.answer(
                    f"✅ {deleted_count} پیام از شما و {partner_deleted_count} پیام از چت مخاطبت حذف شد.",
                    reply_markup=get_main_reply_keyboard()
                )
                await callback.answer("✅ پیام‌های شما حذف شدند.", show_alert=True)
            else:
                await callback.answer("⚠️ پیامی برای حذف یافت نشد.", show_alert=True)
        except Exception as e:
            await callback.answer("❌ خطا در حذف پیام‌ها.", show_alert=True)
        break


@router.callback_query(F.data == "chat:search_again")
async def search_again_after_chat_end(callback: CallbackQuery, state: FSMContext):
    """User wants to search again after chat ended."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Check if user already has active chat
        if await chat_manager.is_chat_active(user.id, db_session):
            await callback.answer("❌ شما در حال حاضر یک چت فعال دارید!", show_alert=True)
            await state.clear()
            return
        
        # Check if user is already in queue
        if await matchmaking_queue.is_user_in_queue(user_id):
            await callback.answer(
                "⏳ در حال جستجو هستی عزیزم! 🔍\n\n"
                "💡 اگه می‌خوای جستجوی جدیدی شروع کنی، اول جستجوی قبلی رو لغو کن ⏹️",
                show_alert=True
            )
            return
        
        # Show gender selection keyboard
        from bot.keyboards.common import get_preferred_gender_keyboard
        from bot.keyboards.reply import get_main_reply_keyboard
        try:
            await callback.message.edit_text(
                "👥 با چه جنسیتی می‌خوای چت کنی؟",
                reply_markup=get_preferred_gender_keyboard()
            )
        except:
            await callback.message.answer(
                "👥 با چه جنسیتی می‌خوای چت کنی؟",
                reply_markup=get_preferred_gender_keyboard()
            )
            # Update keyboard
            try:
                await callback.message.answer(
                    "📱",
                    reply_markup=get_main_reply_keyboard()
                )
                await asyncio.sleep(0.1)
            except:
                pass
        
        await callback.answer()
        break


@router.callback_query(F.data == "chat:no_search")
async def no_search_after_chat_end(callback: CallbackQuery):
    """User doesn't want to search again after chat ended."""
    try:
        await callback.message.edit_text(
            "✅ باشه، هر وقت خواستی دوباره جستجو کنی، دکمه «💬 شروع چت» رو بزن.",
            reply_markup=None
        )
    except:
        await callback.message.answer(
            "✅ باشه، هر وقت خواستی دوباره جستجو کنی، دکمه «💬 شروع چت» رو بزن."
        )
    
    await callback.answer()


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
                    f"🔹 تماس تصویری\n"
                    f"🔹 تماس صوتی\n"
                    f"🔹 زمان چت بیشتر ({settings.PREMIUM_CHAT_DURATION_MINUTES} دقیقه در مقابل {settings.MAX_CHAT_DURATION_MINUTES} دقیقه)\n"
                    f"🔹 فیلترهای پیشرفته\n"
                    f"🔹 اولویت در صف (نفر اول صف)\n\n"
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
                    f"🔹 تماس تصویری\n"
                    f"🔹 تماس صوتی\n"
                    f"🔹 زمان چت بیشتر ({settings.PREMIUM_CHAT_DURATION_MINUTES} دقیقه در مقابل {settings.MAX_CHAT_DURATION_MINUTES} دقیقه)\n"
                    f"🔹 فیلترهای پیشرفته\n"
                    f"🔹 اولویت در صف (نفر اول صف)\n\n"
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
        
        # Only send one message (either edit or answer, not both)
        try:
            await callback.message.edit_text(
                "✅ جستجو لغو شد.\n\n"
                "شما از صف خارج شدید.",
                reply_markup=None
            )
        except:
            # If edit fails, send new message
            await callback.message.answer(
                "✅ جستجو لغو شد.\n\n"
                "شما از صف خارج شدید.",
                reply_markup=get_main_reply_keyboard()
            )
        
        await callback.answer("✅ جستجو لغو شد")
        await state.clear()
        break


@router.callback_query(F.data == "chat:insufficient_coins")
async def insufficient_coins_back(callback: CallbackQuery):
    """Handle back navigation to insufficient coins menu."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        from db.crud import get_user_by_telegram_id, get_visible_coin_packages, get_visible_premium_plans
        from bot.keyboards.coin_package import get_insufficient_coins_keyboard
        from core.points_manager import PointsManager
        from config.settings import settings
        
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        user_points = await PointsManager.get_balance(user.id)
        
        # Get filtered chat cost
        filtered_chat_cost_str = await get_system_setting_value(db_session, "filtered_chat_cost")
        try:
            filtered_chat_cost = int(filtered_chat_cost_str) if filtered_chat_cost_str else settings.FILTERED_CHAT_COST
        except (ValueError, TypeError):
            filtered_chat_cost = settings.FILTERED_CHAT_COST
        
        # Get required message count for males
        required_message_count_male_str = await get_system_setting_value(db_session, "chat_success_message_count_male")
        try:
            required_message_count_male = int(required_message_count_male_str) if required_message_count_male_str else settings.CHAT_SUCCESS_MESSAGE_COUNT_MALE
        except (ValueError, TypeError):
            required_message_count_male = settings.CHAT_SUCCESS_MESSAGE_COUNT_MALE
        
        packages = await get_visible_coin_packages(db_session)
        premium_plans = await get_visible_premium_plans(db_session)
        
        text = (
            f"💡 هزینه‌ی این چت {filtered_chat_cost} سکه است؛ در صورت موفقیت چت (حداقل {required_message_count_male} پیام از پسر) ازت کسر می‌شود.\n\n"
            f"💰 سکه فعلی تو: {user_points}\n\n"
            f"💡 می‌تونی:\n"
            f"🔹 سکه‌هات رو به پریمیوم تبدیل کنی\n"
            f"🔹 یا پریمیوم بگیری (چت رایگان)\n"
            f"🔹 یا «جستجوی شانسی» رو انتخاب کنی (رایگان)\n"
            f"🔹 یا از پایین منو سکهٔ رایگان روزانه بگیری 👇\n"
            f"🔹 راستی با دعوت دوستات و تکمیل پروفایل‌شون 15 تا سکه بگیری"
        )
        
        try:
            await callback.message.edit_text(
                text,
                reply_markup=get_insufficient_coins_keyboard(packages, premium_plans)
            )
        except:
            await callback.message.answer(
                text,
                reply_markup=get_insufficient_coins_keyboard(packages, premium_plans)
            )
        
        await callback.answer()
        break

