"""
My profile handler for editing own profile and managing follows/blocks.
"""
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
)
from bot.keyboards.my_profile import (
    get_my_profile_keyboard,
    get_following_list_keyboard,
    get_blocked_list_keyboard,
    get_liked_list_keyboard,
)
from bot.keyboards.reply import get_main_reply_keyboard
from bot.keyboards.common import get_gender_keyboard
from utils.validators import validate_age, parse_age, validate_city

router = Router()


class MyProfileEditStates(StatesGroup):
    """FSM states for editing my profile."""
    waiting_new_photo = State()
    waiting_new_city = State()
    waiting_new_province = State()
    waiting_new_age = State()
    waiting_new_gender = State()
    waiting_new_username = State()


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
        
        profile_text = (
            f"📊 پروفایل من\n\n"
            f"• نام: {user.username or 'تعیین نشده'}\n"
            f"• جنسیت: {gender_text}\n"
            f"• استان: {user.province or 'تعیین نشده'}\n"
            f"• شهر: {user.city or 'تعیین نشده'}\n"
            f"• سن: {user.age or 'تعیین نشده'}\n"
            f"• پریمیوم: {'✅ فعال' if user.is_premium else '❌ غیرفعال'}\n"
            f"ID: {user_unique_id}"
        )
        
        profile_keyboard = get_my_profile_keyboard()
        
        # Send profile with photo if available
        profile_image_url = getattr(user, 'profile_image_url', None)
        if profile_image_url:
            try:
                await callback.message.answer_photo(
                    photo=profile_image_url,
                    caption=profile_text,
                    reply_markup=profile_keyboard
                )
                await callback.answer()
            except Exception:
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
        
        await update_user_profile(
            db_session,
            user_id,
            profile_image_url=file_id
        )
        
        await message.answer(
            "✅ عکس پروفایل به‌روزرسانی شد!",
            reply_markup=get_main_reply_keyboard()
        )
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


@router.callback_query(F.data == "my_profile:edit_username")
async def edit_username(callback: CallbackQuery, state: FSMContext):
    """Start editing username."""
    await callback.message.answer(
        "📝 لطفاً نام کاربری جدید خود را بفرستید:",
        reply_markup=None
    )
    await state.set_state(MyProfileEditStates.waiting_new_username)
    await callback.answer()


@router.message(MyProfileEditStates.waiting_new_username)
async def process_new_username(message: Message, state: FSMContext):
    """Process new username."""
    user_id = message.from_user.id
    new_username = message.text.strip()
    
    if len(new_username) < 2:
        await message.answer("❌ نام کاربری باید حداقل 2 کاراکتر باشد.\n\nلطفاً دوباره نام کاربری را بفرستید:")
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
            username=new_username
        )
        
        await message.answer(
            f"✅ نام کاربری به {new_username} تغییر یافت!",
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
            
            username_display = username or f"User {followed_user_id}"
            user_unique_id = f"/user_{profile_id or 'unknown'}"
            
            # Get profile image for thumbnail
            profile_image_url = getattr(followed_user, 'profile_image_url', None)
            
            # Get thumbnail URL - if it's a file_id, convert to URL
            thumbnail_url = None
            if profile_image_url:
                if profile_image_url.startswith(('http://', 'https://')):
                    thumbnail_url = profile_image_url
                else:
                    # It's a Telegram file_id, get file URL
                    try:
                        bot = Bot(token=settings.BOT_TOKEN)
                        file = await bot.get_file(profile_image_url)
                        thumbnail_url = f"https://api.telegram.org/file/bot{settings.BOT_TOKEN}/{file.file_path}"
                        await bot.session.close()
                    except Exception:
                        # If failed, use no thumbnail
                        thumbnail_url = None
            
            results.append(
                InlineQueryResultArticle(
                    id=str(followed_user_id),
                    title=f"👥 {username_display[:30]}",
                    description=f"ID: {user_unique_id}",
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
            await callback.answer(f"✅ {followed_user.username or 'کاربر'} آنفالو شد!")
            
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
            
            username_display = username or f"User {liked_user_id}"
            user_unique_id = f"/user_{profile_id or 'unknown'}"
            
            # Get profile image for thumbnail
            profile_image_url = getattr(liked_user, 'profile_image_url', None)
            
            # Get thumbnail URL - if it's a file_id, convert to URL
            thumbnail_url = None
            if profile_image_url:
                if profile_image_url.startswith(('http://', 'https://')):
                    thumbnail_url = profile_image_url
                else:
                    # It's a Telegram file_id, get file URL
                    try:
                        bot = Bot(token=settings.BOT_TOKEN)
                        file = await bot.get_file(profile_image_url)
                        thumbnail_url = f"https://api.telegram.org/file/bot{settings.BOT_TOKEN}/{file.file_path}"
                        await bot.session.close()
                    except Exception:
                        # If failed, use no thumbnail
                        thumbnail_url = None
            
            results.append(
                InlineQueryResultArticle(
                    id=str(liked_user_id),
                    title=f"❤️ {username_display[:30]}",
                    description=f"ID: {user_unique_id}",
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
            
            username_display = username or f"User {blocked_user_id}"
            user_unique_id = f"/user_{profile_id or 'unknown'}"
            
            # Get profile image for thumbnail
            profile_image_url = getattr(blocked_user, 'profile_image_url', None)
            
            # Get thumbnail URL - if it's a file_id, convert to URL
            thumbnail_url = None
            if profile_image_url:
                if profile_image_url.startswith(('http://', 'https://')):
                    thumbnail_url = profile_image_url
                else:
                    # It's a Telegram file_id, get file URL
                    try:
                        bot = Bot(token=settings.BOT_TOKEN)
                        file = await bot.get_file(profile_image_url)
                        thumbnail_url = f"https://api.telegram.org/file/bot{settings.BOT_TOKEN}/{file.file_path}"
                        await bot.session.close()
                    except Exception:
                        # If failed, use no thumbnail
                        thumbnail_url = None
            
            results.append(
                InlineQueryResultArticle(
                    id=str(blocked_user_id),
                    title=f"🚫 {username_display[:30]}",
                    description=f"ID: {user_unique_id}",
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
            await callback.answer(f"❤️ لایک {liked_user.username or 'کاربر'} برداشته شد!")
            
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
            await callback.answer(f"✅ {blocked_user.username or 'کاربر'} آنبلاک شد!")
            
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
        
        profile_text = (
            f"📊 پروفایل من\n\n"
            f"• نام: {user.username or 'تعیین نشده'}\n"
            f"• جنسیت: {gender_text}\n"
            f"• استان: {user.province or 'تعیین نشده'}\n"
            f"• شهر: {user.city or 'تعیین نشده'}\n"
            f"• سن: {user.age or 'تعیین نشده'}\n"
            f"• پریمیوم: {'✅ فعال' if user.is_premium else '❌ غیرفعال'}\n"
            f"ID: {user_unique_id}"
        )
        
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

