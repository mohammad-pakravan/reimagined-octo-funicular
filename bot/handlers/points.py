"""
Points handler for managing user points.
"""
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery

from db.database import get_db
from db.crud import (
    get_user_by_telegram_id,
    get_visible_coin_packages,
    get_visible_premium_plans,
)
from core.points_manager import PointsManager
from bot.keyboards.coin_package import (
    get_user_coin_packages_keyboard,
    get_combined_purchase_keyboard,
)
from bot.keyboards.engagement import (
    get_points_menu_keyboard,
    get_points_convert_keyboard,
    get_engagement_menu_keyboard,
    get_premium_menu_keyboard,
    get_rewards_menu_keyboard,
    get_coins_menu_keyboard,
)
from config.settings import settings

router = Router()


async def build_points_info_text(db_session, user):
    """Build the text shown for the points overview."""
    points = await PointsManager.get_balance(user.id)

    from db.crud import get_coins_for_premium_days, get_coins_for_activity

    coins_for_1_day = await get_coins_for_premium_days(db_session, 1)
    if coins_for_1_day is None:
        coins_for_1_day = settings.POINTS_TO_PREMIUM_DAY

    daily_login_coins = await get_coins_for_activity(db_session, "daily_login")
    if daily_login_coins is None:
        daily_login_coins = settings.POINTS_DAILY_LOGIN

    chat_success_coins = await get_coins_for_activity(db_session, "chat_success")
    if chat_success_coins is None:
        chat_success_coins = settings.POINTS_CHAT_SUCCESS

    mutual_like_coins = await get_coins_for_activity(db_session, "mutual_like")
    if mutual_like_coins is None:
        mutual_like_coins = settings.POINTS_MUTUAL_LIKE

    referral_coins = await get_coins_for_activity(db_session, "referral_referrer")
    if referral_coins is None:
        referral_coins = await get_coins_for_activity(db_session, "referral_signup")
        if referral_coins is None:
            referral_coins = await get_coins_for_activity(db_session, "referral_profile_complete")
            if referral_coins is None:
                referral_coins = 0

    return (
        f"⭐ سکه‌ها\n\n"
        f"💰 سکه فعلی: {points}\n\n"
        f"💡 می‌توانی سکه‌ها را به روزهای پریمیوم تبدیل کنی!\n"
        f"📊 نرخ تبدیل: {coins_for_1_day} سکه = 1 روز پریمیوم\n\n"
        f"چطور سکه کسب کنم؟\n"
        f"• ورود روزانه: {daily_login_coins} سکه\n"
        f"• چت موفق: {chat_success_coins} سکه\n"
        f"• لایک متقابل: {mutual_like_coins} سکه\n"
        f"• دعوت دوستان: {referral_coins} سکه"
    )


async def build_premium_coins_overview(db_session, user):
    """Compose the premium plans + coin packages overview text."""
    points_balance = await PointsManager.get_balance(user.id)
    premium_plans = await get_visible_premium_plans(db_session)
    coin_packages = await get_visible_coin_packages(db_session)

    text_lines = [
        "💎 پریمیوم و سکه‌ها",
        "",
        f"💰 موجودی سکهٔ فعلی: {points_balance}",
    ]

    if premium_plans:
        text_lines.append("")
        text_lines.append("✨ پلن‌های پریمیوم:")
        for plan in premium_plans:
            stars_text = f" / {plan.stars_required} ⭐" if plan.stars_required else ""
            text_lines.append(
                f"• {plan.plan_name} – {plan.duration_days} روز – {int(plan.price):,} تومان{stars_text}"
            )
    else:
        text_lines.append("")
        text_lines.append("✨ فعلاً هیچ پلن پریمیومی فعال نیست.")

    if coin_packages:
        text_lines.append("")
        text_lines.append("💰 پکیج‌های سکه:")
        for package in coin_packages:
            stars_text = f" / {package.stars_required} ⭐" if package.stars_required else ""
            text_lines.append(
                f"• {package.package_name} – {int(package.price):,} تومان{stars_text}"
            )
    else:
        text_lines.append("")
        text_lines.append("💰 فعلاً پکیج سکه‌ای فعال نیست.")

    if premium_plans or coin_packages:
        text_lines.append("")
        text_lines.append("برای خرید، گزینهٔ مورد نظر را از دکمه‌های زیر انتخاب کن.")
    else:
        text_lines.append("")
        text_lines.append("❌ در حال حاضر پلن یا پکیجی برای خرید فعال نیست.")

    return "\n".join(text_lines), premium_plans, coin_packages


@router.callback_query(F.data == "points:info")
async def points_info(callback: CallbackQuery):
    """Show points information."""
    user_id = callback.from_user.id

    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return

        text = await build_points_info_text(db_session, user)
        await callback.message.edit_text(
            text,
            reply_markup=get_points_menu_keyboard()
        )
        await callback.answer()
        break


@router.callback_query(F.data == "points:history")
async def points_history(callback: CallbackQuery):
    """Show points history."""
    user_id = callback.from_user.id

    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return

        history = await PointsManager.get_history(user.id, limit=20)

        if not history:
            await callback.message.edit_text(
                "📜 تاریخچه سکه‌ها\n\n"
                "هنوز هیچ سکه‌ای دریافت نکرده‌ای!",
                reply_markup=get_points_menu_keyboard()
            )
        else:
            history_text = "📜 تاریخچه سکه‌ها\n\n"
            for record in history[:10]:
                points_text = f"+{record.points}" if record.points > 0 else str(record.points)
                history_text += f"{points_text} سکه - {record.source}\n"

            history_text += f"\n(نمایش آخرین 10 تراکنش)"
            await callback.message.edit_text(
                history_text,
                reply_markup=get_points_menu_keyboard()
            )

        await callback.answer()
        break


@router.callback_query(F.data == "menu:main")
async def menu_main(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎯 منوی اصلی پاداش‌ها و تعامل:\n\n"
        "یک گزینه را انتخاب کن تا وارد زیرمنوی مرتبط بشی.",
        reply_markup=get_engagement_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "menu:free_coins")
async def menu_free_coins(callback: CallbackQuery):
    """Handle free coins menu callback."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        from db.crud import check_user_premium
        
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        points = await PointsManager.get_balance(user.id)
        is_premium = await check_user_premium(db_session, user.id)
        
        text = f"🎁 سکه رایگان\n\n💰 سکه‌های فعلی شما: {points}\n"
        
        if is_premium and user.premium_expires_at:
            from datetime import datetime
            expires_at = user.premium_expires_at.strftime("%Y-%m-%d %H:%M")
            text += f"💎 پریمیوم تا: {expires_at}\n"
        
        text += "\nاز گزینه‌های زیر برای دریافت سکه رایگان استفاده کنید:"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_engagement_menu_keyboard()
        )
        await callback.answer()
        break


@router.callback_query(F.data == "menu:premium")
async def menu_premium(callback: CallbackQuery):
    await callback.message.edit_text(
        "💎 منوی پریمیوم:\n"
        "از اینجا می‌تونی اشتراک بگیری یا سکه‌هات رو به پریمیوم تبدیل کنی.",
        reply_markup=get_premium_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "menu:rewards")
async def menu_rewards(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎁 منوی پاداش و تعامل:\n"
        "دریافت سکه روزانه، سکه هدیه و دعوت دوستان از اینجا انجام می‌شه.",
        reply_markup=get_rewards_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "menu:coins")
async def menu_coins(callback: CallbackQuery):
    await callback.message.edit_text(
        "💰 منوی سکه‌ها:\n"
        "موجودی، خرید، تاریخچه و تبدیل سکه در این بخش قرار دارن.",
        reply_markup=get_coins_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "menu:premium_coins")
async def menu_premium_coins(callback: CallbackQuery):
    """Handle premium and coins combined menu."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        text, premium_plans, coin_packages = await build_premium_coins_overview(db_session, user)
        keyboard = get_combined_purchase_keyboard(coin_packages, premium_plans)

        await callback.message.edit_text(
            text,
            reply_markup=keyboard
        )
        await callback.answer()
        break


@router.callback_query(F.data == "points:buy")
async def points_buy(callback: CallbackQuery):
    """Show coin purchase packages and premium plans."""
    user_id = callback.from_user.id

    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return

        text, premium_plans, coin_packages = await build_premium_coins_overview(db_session, user)

        if not premium_plans and not coin_packages:
            await callback.answer(
                "❌ در حال حاضر پکیج یا پلنی موجود نیست.",
                show_alert=True
            )
            return
        
        keyboard = get_combined_purchase_keyboard(coin_packages, premium_plans)

        await callback.message.edit_text(
            text,
            reply_markup=keyboard
        )
        await callback.answer()
        break


@router.callback_query(F.data == "points:convert")
async def points_convert_menu(callback: CallbackQuery):
    """Show points conversion menu."""
    user_id = callback.from_user.id

    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return

        points = await PointsManager.get_balance(user.id)
        from db.crud import get_coins_for_premium_days

        price_1 = await get_coins_for_premium_days(db_session, 1)
        price_3 = await get_coins_for_premium_days(db_session, 3)
        price_7 = await get_coins_for_premium_days(db_session, 7)
        price_30 = await get_coins_for_premium_days(db_session, 30)

        def fmt(value):
            return value if value is not None else "نامشخص"

        await callback.message.edit_text(
            f"💎 تبدیل سکه به پریمیوم\n\n"
            f"💰 سکه فعلی: {points}\n\n"
            f"🎁 قیمت‌ها:\n"
            f"• 1 روز: {fmt(price_1)} سکه\n"
            f"• 3 روز: {fmt(price_3)} سکه\n"
            f"• 7 روز: {fmt(price_7)} سکه\n"
            f"• 30 روز: {fmt(price_30)} سکه\n\n"
            f"انتخاب کن:",
            reply_markup=get_points_convert_keyboard()
        )
        await callback.answer()
        break


@router.callback_query(F.data.startswith("points:convert:"))
async def points_convert(callback: CallbackQuery):
    """Convert points to premium."""
    user_id = callback.from_user.id
    days = int(callback.data.split(":")[-1])

    async for db_session in get_db():
        from db.crud import (
            get_coins_for_premium_days,
            spend_points,
            create_premium_subscription,
            get_user_premium_days,
            get_badge_by_key,
        )

        required_points = await get_coins_for_premium_days(db_session, days)
        if required_points is None:
            required_points = days * 200

        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return

        current_points = await PointsManager.get_balance(user.id)
        if current_points < required_points:
            await callback.answer(
                f"❌ سکه کافی نیست!\n\n"
                f"سکه فعلی: {current_points}\n"
                f"سکه مورد نیاز: {required_points}",
                show_alert=True
            )
            return

        success = await spend_points(
            db_session,
            user.id,
            required_points,
            "spent",
            "premium_purchase",
            f"Purchased {days} days of premium"
        )

        if success:
            now = datetime.utcnow()
            duration = timedelta(days=days)

            expiration_base = user.premium_expires_at if user.premium_expires_at and user.premium_expires_at > now else now
            expiration = expiration_base + duration

            transaction_id = f"points_{user_id}_{int(now.timestamp())}"
            subscription = await create_premium_subscription(
                db_session,
                user.id,
                provider="points",
                transaction_id=transaction_id,
                amount=0.0,
                start_date=now,
                end_date=expiration
            )

            if subscription:
                from core.achievement_system import AchievementSystem
                from core.badge_manager import BadgeManager
                from aiogram import Bot as BadgeBot

                premium_days = await get_user_premium_days(db_session, user.id)
                completed = await AchievementSystem.check_premium_achievement(user.id, premium_days)

                badge_bot = BadgeBot(token=settings.BOT_TOKEN)
                try:
                    for achievement in completed:
                        if achievement.achievement and achievement.achievement.badge_id:
                            badge = await get_badge_by_key(db_session, achievement.achievement.achievement_key)
                            if badge:
                                await BadgeManager.award_badge_and_notify(
                                    user.id,
                                    badge.badge_key,
                                    badge_bot,
                                    user.telegram_id
                                )
                except Exception:
                    pass
                finally:
                    await badge_bot.session.close()

                await callback.answer(
                    f"✅ {days} روز پریمیوم دریافت کردی!",
                    show_alert=True
                )
                await callback.message.edit_text(
                    f"💎 تبدیل سکه به پریمیوم\n\n"
                    f"✅ موفق! {days} روز پریمیوم دریافت کردی!",
                    reply_markup=get_points_menu_keyboard()
                )
            else:
                await callback.answer("❌ خطا در فعال کردن پریمیوم.", show_alert=True)
        else:
            await callback.answer("❌ خطا در تبدیل سکه.", show_alert=True)

        break
"""
Points handler for managing user points.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery

from db.database import get_db
from db.crud import get_user_by_telegram_id
from core.points_manager import PointsManager
from bot.keyboards.engagement import get_points_menu_keyboard, get_points_convert_keyboard, get_engagement_menu_keyboard
from config.settings import settings

router = Router()


@router.callback_query(F.data == "points:info")
async def points_info(callback: CallbackQuery):
    """Show points information."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        points = await PointsManager.get_balance(user.id)
        
        # Get conversion rate from database (for 1 day)
        from db.crud import get_coins_for_premium_days, get_coins_for_activity
        coins_for_1_day = await get_coins_for_premium_days(db_session, 1)
        if coins_for_1_day is None:
            # Fallback to settings if not in database
            coins_for_1_day = settings.POINTS_TO_PREMIUM_DAY
        
        # Get coin rewards from database
        daily_login_coins = await get_coins_for_activity(db_session, "daily_login")
        if daily_login_coins is None:
            daily_login_coins = settings.POINTS_DAILY_LOGIN
        
        chat_success_coins = await get_coins_for_activity(db_session, "chat_success")
        if chat_success_coins is None:
            chat_success_coins = settings.POINTS_CHAT_SUCCESS
        
        mutual_like_coins = await get_coins_for_activity(db_session, "mutual_like")
        if mutual_like_coins is None:
            mutual_like_coins = settings.POINTS_MUTUAL_LIKE
        
        referral_coins = await get_coins_for_activity(db_session, "referral_referrer")
        if referral_coins is None:
            # Try fallback to referral_signup or referral_profile_complete
            referral_coins = await get_coins_for_activity(db_session, "referral_signup")
            if referral_coins is None:
                referral_coins = await get_coins_for_activity(db_session, "referral_profile_complete")
                if referral_coins is None:
                    referral_coins = 0  # No fallback - admin must set this in database
        
        await callback.message.edit_text(
            f"⭐ سکه‌ها\n\n"
            f"💰 سکه فعلی: {points}\n\n"
            f"💡 می‌توانی سکه‌ها را به روزهای پریمیوم تبدیل کنی!\n"
            f"📊 نرخ تبدیل: {coins_for_1_day} سکه = 1 روز پریمیوم\n\n"
            f"چطور سکه کسب کنم؟\n"
            f"• ورود روزانه: {daily_login_coins} سکه\n"
            f"• چت موفق: {chat_success_coins} سکه\n"
            f"• لایک متقابل: {mutual_like_coins} سکه\n"
            f"• دعوت دوستان: {referral_coins} سکه",
            reply_markup=get_points_menu_keyboard()
        )
        await callback.answer()
        break


@router.callback_query(F.data == "points:history")
async def points_history(callback: CallbackQuery):
    """Show points history."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        history = await PointsManager.get_history(user.id, limit=20)
        
        if not history:
            await callback.message.edit_text(
                "📜 تاریخچه سکه‌ها\n\n"
                "هنوز هیچ سکه‌ای دریافت نکرده‌ای!",
                reply_markup=get_points_menu_keyboard()
            )
        else:
            history_text = "📜 تاریخچه سکه‌ها\n\n"
            for record in history[:10]:  # Show last 10
                points_text = f"+{record.points}" if record.points > 0 else str(record.points)
                history_text += f"{points_text} سکه - {record.source}\n"
            
            history_text += f"\n(نمایش آخرین 10 تراکنش)"
            
            await callback.message.edit_text(
                history_text,
                reply_markup=get_points_menu_keyboard()
            )
        
        await callback.answer()
        break


@router.callback_query(F.data == "points:convert")
async def points_convert_menu(callback: CallbackQuery):
    """Show points conversion menu."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        points = await PointsManager.get_balance(user.id)
        
        # Get prices from database
        from db.crud import get_coins_for_premium_days
        price_1 = await get_coins_for_premium_days(db_session, 1)
        price_3 = await get_coins_for_premium_days(db_session, 3)
        price_7 = await get_coins_for_premium_days(db_session, 7)
        price_30 = await get_coins_for_premium_days(db_session, 30)
        
        # If not in database, show "نامشخص"
        price_1 = price_1 if price_1 is not None else "نامشخص"
        price_3 = price_3 if price_3 is not None else "نامشخص"
        price_7 = price_7 if price_7 is not None else "نامشخص"
        price_30 = price_30 if price_30 is not None else "نامشخص"
        
        await callback.message.edit_text(
            f"💎 تبدیل سکه به پریمیوم\n\n"
            f"💰 سکه فعلی: {points}\n\n"
            f"🎁 قیمت‌ها:\n"
            f"• 1 روز: {price_1} سکه\n"
            f"• 3 روز: {price_3} سکه\n"
            f"• 7 روز: {price_7} سکه\n"
            f"• 30 روز: {price_30} سکه\n\n"
            f"انتخاب کن:",
            reply_markup=get_points_convert_keyboard()
        )
        await callback.answer()
        break


@router.callback_query(F.data.startswith("points:convert:"))
async def points_convert(callback: CallbackQuery):
    """Convert points to premium."""
    user_id = callback.from_user.id
    days = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        # Get required coins from database
        from db.crud import get_coins_for_premium_days
        required_points = await get_coins_for_premium_days(db_session, days)
        
        if required_points is None:
            # Fallback to default calculation
            required_points = days * 200
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        current_points = await PointsManager.get_balance(user.id)
        
        if current_points < required_points:
            await callback.answer(
                f"❌ سکه کافی نیست!\n\n"
                f"سکه فعلی: {current_points}\n"
                f"سکه مورد نیاز: {required_points}",
                show_alert=True
            )
            return
        
        # Spend points manually with custom amount
        from db.crud import spend_points
        success = await spend_points(
            db_session,
            user.id,
            required_points,
            "spent",
            "premium_purchase",
            f"Purchased {days} days of premium"
        )
        
        if success:
            # Grant premium days
            from db.crud import create_premium_subscription
            from datetime import datetime, timedelta
            
            now = datetime.utcnow()
            # Calculate the duration to add
            duration_to_add = timedelta(days=days)
            
            # Calculate expiration date
            if user.premium_expires_at and user.premium_expires_at > now:
                # Extend existing premium
                expiration_date = user.premium_expires_at + duration_to_add
            else:
                # Start new premium
                expiration_date = now + duration_to_add
            
            transaction_id = f"points_{user_id}_{int(now.timestamp())}"
            subscription = await create_premium_subscription(
                db_session,
                user.id,
                provider="points",
                transaction_id=transaction_id,
                amount=0.0,  # Free - paid with points
                start_date=now,
                end_date=expiration_date
            )
            
            if subscription:
                # Check and award badges for premium achievements
                from core.achievement_system import AchievementSystem
                from core.badge_manager import BadgeManager
                from db.crud import get_user_premium_days, get_badge_by_key
                from aiogram import Bot as BadgeBot
                
                # Get premium days
                premium_days = await get_user_premium_days(db_session, user.id)
                
                # Check premium achievements
                completed_achievements = await AchievementSystem.check_premium_achievement(
                    user.id,
                    premium_days
                )
                
                # Award badges
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
                except Exception:
                    pass
                finally:
                    await badge_bot.session.close()
                
                await callback.answer(
                    f"✅ {days} روز پریمیوم دریافت کردی!",
                    show_alert=True
                )
                await callback.message.edit_text(
                    f"💎 تبدیل سکه به پریمیوم\n\n"
                    f"✅ موفق! {days} روز پریمیوم دریافت کردی!",
                    reply_markup=get_points_menu_keyboard()
                )
            else:
                await callback.answer("❌ خطا در فعال کردن پریمیوم.", show_alert=True)
        else:
            await callback.answer("❌ خطا در تبدیل سکه.", show_alert=True)
        
        break

