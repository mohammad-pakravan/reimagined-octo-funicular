"""
Daily reward handler for managing daily login rewards.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message

from db.database import get_db
from db.crud import get_user_by_telegram_id
from core.reward_system import RewardSystem
from bot.keyboards.engagement import get_daily_reward_keyboard, get_engagement_menu_keyboard
from bot.keyboards.common import get_main_menu_keyboard

router = Router()


@router.callback_query(F.data == "engagement:menu")
async def engagement_menu(callback: CallbackQuery):
    """Show engagement menu."""
    from db.crud import get_user_by_telegram_id, check_user_premium
    from core.points_manager import PointsManager
    from bot.keyboards.engagement import get_premium_rewards_menu_keyboard
    from config.settings import settings
    
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        is_premium = await check_user_premium(db_session, user.id)
        points = await PointsManager.get_balance(user.id)
        
        if is_premium:
            expires_at = user.premium_expires_at.strftime("%Y-%m-%d %H:%M") if user.premium_expires_at else "هرگز"
            text = (
                f"💎 پریمیوم و پاداش‌ها\n\n"
                f"✅ وضعیت پریمیوم: فعال\n"
                f"📅 تاریخ انقضا: {expires_at}\n\n"
                f"💰 سکه‌های شما: {points}\n\n"
                f"💡 می‌توانی سکه‌ها را ذخیره کنی و بعداً برای تمدید پریمیوم استفاده کنی!\n\n"
                f"از منوی زیر انتخاب کنید:"
            )
        else:
            # Get conversion rates from database
            from db.crud import get_coins_for_premium_days
            coins_1_day = await get_coins_for_premium_days(db_session, 1)
            coins_30_days = await get_coins_for_premium_days(db_session, 30)
            
            # Fallback to settings if not in database
            if coins_1_day is None:
                coins_1_day = 200
            if coins_30_days is None:
                coins_30_days = 3000
            
            text = (
                f"💎 پریمیوم و پاداش‌ها\n\n"
                f"💰 سکه‌های شما: {points}\n\n"
                f"🎯 راه‌های دریافت پریمیوم:\n"
                f"1️⃣ 💎 تبدیل سکه به پریمیوم (اولویت)\n"
                f"   • {coins_1_day} سکه = 1 روز\n"
                f"   • {coins_30_days} سکه = 1 ماه\n\n"
                f"2️⃣ 💳 خرید مستقیم\n"
                f"   • {settings.PREMIUM_PRICE} تومان = {settings.PREMIUM_DURATION_DAYS} روز\n\n"
                f"💡 با تعامل با ربات (پاداش روزانه، چت، دعوت دوستان) سکه کسب کن و پریمیوم بگیر!\n\n"
                f"از منوی زیر انتخاب کنید:"
            )
        
        try:
            await callback.message.edit_text(
                text,
                reply_markup=get_premium_rewards_menu_keyboard(is_premium=is_premium)
            )
        except Exception:
            # If edit fails, send new message
            await callback.message.answer(
                text,
                reply_markup=get_premium_rewards_menu_keyboard(is_premium=is_premium)
            )
        
        await callback.answer()
        break


@router.callback_query(F.data == "daily_reward:claim")
async def claim_daily_reward(callback: CallbackQuery):
    """Claim daily reward."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        reward_info = await RewardSystem.claim_daily_reward(user.id)
        
        if not reward_info:
            await callback.answer("❌ خطا در دریافت پاداش.", show_alert=True)
            return
        
        if reward_info.get('already_claimed'):
            await callback.message.edit_text(
                f"🎁 پاداش روزانه\n\n"
                f"✅ شما امروز پاداش خود را دریافت کرده‌اید!\n\n"
                f"💰 سکه دریافت شده: {reward_info['points']}\n"
                f"🔥 استریک: {reward_info['streak_count']} روز\n\n"
                f"فردا دوباره بیا!",
                reply_markup=get_daily_reward_keyboard(already_claimed=True)
            )
        else:
            streak_text = ""
            if reward_info['streak_count'] > 1:
                streak_text = f"\n🔥 استریک: {reward_info['streak_count']} روز!"
            
            await callback.message.edit_text(
                f"🎁 پاداش روزانه دریافت شد!\n\n"
                f"💰 سکه دریافت شده: {reward_info['points']}{streak_text}\n\n"
                f"فردا دوباره بیا تا استریکت را ادامه بدهی!",
                reply_markup=get_daily_reward_keyboard(already_claimed=False)
            )
        
        await callback.answer()
        break


@router.callback_query(F.data == "daily_reward:streak")
async def show_streak_info(callback: CallbackQuery):
    """Show streak information."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        streak_info = await RewardSystem.get_streak_info(user.id)
        
        streak_text = ""
        if streak_info.get('streak_count', 0) > 0:
            streak_text = f"\n🔥 استریک فعلی: {streak_info['streak_count']} روز"
        else:
            streak_text = "\n⚠️ استریک فعلی: 0 روز (شروع کن!)"
        
        last_reward_text = ""
        if streak_info.get('last_reward_date'):
            last_reward_text = f"\n📅 آخرین پاداش: {streak_info['last_reward_date']}"
        else:
            last_reward_text = "\n📅 آخرین پاداش: هنوز پاداشی دریافت نکرده‌ای"
        
        can_claim_text = ""
        if streak_info.get('can_claim_today'):
            if streak_info.get('next_streak'):
                can_claim_text = f"\n✅ می‌توانی امروز پاداش بگیری! (استریک بعدی: {streak_info['next_streak']} روز)"
            else:
                can_claim_text = "\n✅ می‌توانی امروز پاداش بگیری!"
        else:
            if streak_info.get('points_claimed'):
                can_claim_text = f"\n💰 سکه دریافت شده امروز: {streak_info['points_claimed']}"
        
        try:
            await callback.message.edit_text(
                f"📊 وضعیت استریک\n\n"
                f"{streak_text}{last_reward_text}{can_claim_text}\n\n"
                f"هر روز که پاداش بگیری، استریکت بیشتر می‌شه و پاداش بیشتری دریافت می‌کنی!",
                reply_markup=get_daily_reward_keyboard(already_claimed=not streak_info.get('can_claim_today', False))
            )
        except Exception:
            # Message not modified - ignore error
            pass
        
        await callback.answer()
        break

