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
            # Try fallback to old referral_referrer
            coins_profile_complete = await get_coins_for_activity(db_session, "referral_referrer")
            if coins_profile_complete is None:
                # No fallback - admin must set this in database
                coins_profile_complete = 0
        
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
        
        # First message: Statistics and instructions
        stats_text = (
            f"👥 دعوت دوستان\n\n"
            f"📊 آمار:\n"
            f"• تعداد دعوت‌ها: {referral_count}\n"
            f"• کل سکه کسب شده: {total_points}\n\n"
            f"💡 نحوه کسب سکه:\n"
            f"• با تکمیل پروفایل توسط کاربران دعوت شده (اسم، سن، شهر، تصویر): {coins_profile_complete} سکه\n\n"
        )
        
        if not is_premium:
            stats_text += (
                f"💎 با خرید پریمیوم:\n"
                f"• پاداش بیشتر برای دعوت‌ها\n"
                f"• اولویت در صف\n"
                f"• امکانات بیشتر\n\n"
            )
        
        stats_text += "💡 لینک دعوت را از پیام بعدی کپی کنید و با دوستان خود به اشتراک بگذارید!"
        
        try:
            await callback.message.edit_text(
                stats_text,
                reply_markup=get_referral_menu_keyboard()
            )
        except Exception:
            # If edit fails, send new message
            await callback.message.answer(
                stats_text,
                reply_markup=get_referral_menu_keyboard()
            )
        
        # Second message: Forwardable referral link message
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        forward_text = (
            f"🎉 به ربات چت ناشناس خوش آمدید!\n\n"
            f"💬 با این ربات می‌توانید:\n"
            f"• با کاربران دیگر چت کنید\n"
            f"• دوستان جدید پیدا کنید\n"
            f"• سکه رایگان دریافت کنید\n\n"
            f"🔗 برای عضویت روی لینک زیر کلیک کنید:\n"
            f"{referral_link}\n\n"
            f"🎁 با عضویت از طریق این لینک، هر دو نفر سکه رایگان دریافت می‌کنید!"
        )
        
        # Create keyboard with share button
        share_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 عضویت در ربات",
                    url=referral_link
                )
            ]
          
        ])
        
        await callback.message.answer(
            forward_text,
            reply_markup=share_keyboard
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
            # Try fallback to old referral_referrer
            coins_profile_complete = await get_coins_for_activity(db_session, "referral_referrer")
            if coins_profile_complete is None:
                # No fallback - admin must set this in database
                coins_profile_complete = 0
        
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

