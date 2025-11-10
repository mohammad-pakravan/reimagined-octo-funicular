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
        
        from db.crud import check_user_premium
        is_premium = await check_user_premium(db_session, user.id)
        
        referral_code_obj = await get_or_create_user_referral_code(db_session, user.id)
        referral_count = await get_referral_count(db_session, user.id)
        
        # Get coin rewards from database
        from db.crud import get_coins_for_activity
        coins_profile_complete = await get_coins_for_activity(db_session, "referral_profile_complete")
        if coins_profile_complete is None:
            coins_profile_complete = settings.POINTS_REFERRAL_REFERRER  # Fallback to settings
        
        # Get bot username
        try:
            bot_info = await callback.bot.get_me()
            bot_username = bot_info.username or "bot"
        except Exception:
            bot_username = "bot"
        
        referral_link = f"https://t.me/{bot_username}?start=ref_{referral_code_obj.referral_code}"
        
        # Calculate total points (approximate, as we don't know how many completed profile)
        # Only count profile completion rewards
        total_points = referral_count * coins_profile_complete
        
        text = (
            f"👥 دعوت دوستان\n\n"
            f"🔗 لینک عضویت شما:\n{referral_link}\n\n"
            f"📊 آمار:\n"
            f"• تعداد دعوت‌ها: {referral_count}\n"
            f"• کل سکه کسب شده: {total_points}\n\n"
            f"💡 نحوه کسب سکه:\n"
            f"• با تکمیل پروفایل توسط کاربران دعوت شده (اسم، سن، شهر، تصویر): {coins_profile_complete} سکه\n\n"
        )
        
        if not is_premium:
            text += (
                f"💎 با خرید پریمیوم:\n"
                f"• پاداش بیشتر برای دعوت‌ها\n"
                f"• اولویت در صف\n"
                f"• امکانات بیشتر\n\n"
            )
        
        text += "💡 این لینک را با دوستان خود به اشتراک بگذار!"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_referral_menu_keyboard()
        )
        await callback.answer()
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
        
        from db.crud import check_user_premium
        is_premium = await check_user_premium(db_session, user.id)
        
        referral_code_obj = await get_or_create_user_referral_code(db_session, user.id)
        referral_count = await get_referral_count(db_session, user.id)
        
        # Get coin rewards from database
        from db.crud import get_coins_for_activity
        coins_profile_complete = await get_coins_for_activity(db_session, "referral_profile_complete")
        if coins_profile_complete is None:
            coins_profile_complete = settings.POINTS_REFERRAL_REFERRER  # Fallback to settings
        
        # Calculate total points (approximate, as we don't know how many completed profile)
        # Only count profile completion rewards
        total_points = referral_count * coins_profile_complete
        
        text = (
            f"📊 آمار دعوت‌ها\n\n"
            f"👥 تعداد دعوت‌ها: {referral_count}\n"
            f"💰 کل سکه کسب شده: {total_points}\n\n"
            f"💡 نحوه کسب سکه:\n"
            f"• با تکمیل پروفایل توسط کاربران دعوت شده (اسم، سن، شهر، تصویر): {coins_profile_complete} سکه\n\n"
        )
        
        if not is_premium:
            text += (
                f"💎 با خرید پریمیوم:\n"
                f"• پاداش بیشتر برای دعوت‌ها\n"
                f"• اولویت در صف\n"
                f"• امکانات بیشتر\n\n"
            )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_referral_menu_keyboard()
        )
        await callback.answer()
        break

