"""
Referral handler for managing referral system.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from db.database import get_db
from db.crud import (
    get_user_by_telegram_id,
    get_or_create_user_referral_code,
    get_referral_code_by_code,
    create_referral,
    get_referral_count,
)
from core.points_manager import PointsManager
from core.achievement_system import AchievementSystem
from bot.keyboards.engagement import get_referral_menu_keyboard, get_engagement_menu_keyboard
from config.settings import settings

router = Router()


@router.callback_query(F.data == "referral:info")
async def referral_info(callback: CallbackQuery):
    """Show referral information."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        referral_code_obj = await get_or_create_user_referral_code(db_session, user.id)
        referral_count = await get_referral_count(db_session, user.id)
        
        await callback.message.edit_text(
            f"👥 دعوت دوستان\n\n"
            f"📋 کد دعوت شما: {referral_code_obj.referral_code}\n\n"
            f"📊 تعداد دعوت‌ها: {referral_count}\n\n"
            f"💡 دوستان خود را دعوت کن و پاداش بگیر!\n\n"
            f"🎁 پاداش برای دعوت‌کننده: {settings.POINTS_REFERRAL_REFERRER} سکه\n"
            f"🎁 پاداش برای دعوت‌شده: {settings.POINTS_REFERRAL_REFERRED} سکه",
            reply_markup=get_referral_menu_keyboard()
        )
        await callback.answer()
        break


@router.callback_query(F.data == "referral:code")
async def show_referral_code(callback: CallbackQuery):
    """Show user's referral code."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        referral_code_obj = await get_or_create_user_referral_code(db_session, user.id)
        
        # Get bot username
        try:
            bot_info = await callback.bot.get_me()
            bot_username = bot_info.username or "bot"
        except Exception:
            bot_username = "bot"
        
        referral_link = f"https://t.me/{bot_username}?start=ref_{referral_code_obj.referral_code}"
        
        await callback.message.edit_text(
            f"📋 کد دعوت شما\n\n"
            f"🔑 کد: {referral_code_obj.referral_code}\n\n"
            f"🔗 لینک دعوت:\n{referral_link}\n\n"
            f"📊 تعداد استفاده: {referral_code_obj.usage_count}\n\n"
            f"💡 این لینک را با دوستان خود به اشتراک بگذار!",
            reply_markup=get_referral_menu_keyboard()
        )
        await callback.answer()
        break


@router.callback_query(F.data == "referral:use")
async def use_referral_code(callback: CallbackQuery):
    """Prompt user to enter referral code."""
    await callback.message.edit_text(
        "➕ استفاده از کد دعوت\n\n"
        "لطفاً کد دعوت را وارد کن:",
        reply_markup=get_referral_menu_keyboard()
    )
    await callback.answer("لطفاً کد دعوت را به صورت پیام ارسال کن.")


@router.message(F.text.regexp(r"^[A-Z0-9]{8,}$"))
async def handle_referral_code(message: Message, state: FSMContext):
    """Handle referral code entered as text message."""
    code = message.text.strip().upper()
    
    # Skip if user is in event creation state
    current_state = await state.get_state()
    if current_state and "event" in str(current_state).lower():
        return  # Let event_admin handler process this
    
    # Skip if text is a single digit (likely not a referral code)
    if len(code) <= 2 and code.isdigit():
        return  # Likely not a referral code
    
    user_id = message.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await message.answer("❌ ابتدا باید ثبت‌نام کنی!")
            return
        
        referral_code_obj = await get_referral_code_by_code(db_session, code)
        if not referral_code_obj:
            # Only show error if code looks like a referral code (starts with REF or is long enough)
            if code.startswith("REF") or len(code) >= 8:
                await message.answer(f"❌ کد دعوت '{code}' نامعتبر است!")
            return
        
        # Check if user is trying to use their own code
        if referral_code_obj.user_id == user.id:
            await message.answer("❌ نمی‌توانی از کد دعوت خودت استفاده کنی!")
            return
        
        # Check if already referred by this user
        existing = await create_referral(
            db_session,
            referral_code_obj.user_id,
            user.id,
            code
        )
        
        if existing is None:
            await message.answer("✅ قبلاً از این کد استفاده کرده‌ای!")
            return
        
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
            f"✅ کد دعوت '{code}' با موفقیت استفاده شد!\n\n"
            f"🎁 {settings.POINTS_REFERRAL_REFERRED} سکه به شما اهدا شد!"
        )
        break


@router.callback_query(F.data == "referral:stats")
async def referral_stats(callback: CallbackQuery):
    """Show referral statistics."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        referral_code_obj = await get_or_create_user_referral_code(db_session, user.id)
        referral_count = await get_referral_count(db_session, user.id)
        
        total_points = referral_count * settings.POINTS_REFERRAL_REFERRER
        
        await callback.message.edit_text(
            f"📊 آمار دعوت‌ها\n\n"
            f"👥 تعداد دعوت‌ها: {referral_count}\n"
            f"💰 کل سکه کسب شده: {total_points}\n"
            f"📋 تعداد استفاده از کد: {referral_code_obj.usage_count}\n\n"
            f"💡 هر دعوت = {settings.POINTS_REFERRAL_REFERRER} سکه!",
            reply_markup=get_referral_menu_keyboard()
        )
        await callback.answer()
        break

