"""
Premium handler for the bot.
Handles premium subscription information and purchase flow.
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery, SuccessfulPayment, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
import requests
import logging

from db.database import get_db
from db.crud import get_user_by_telegram_id, check_user_premium, create_premium_subscription, get_premium_plan_by_id, get_user_by_id, get_system_setting_value, create_payment_transaction
from bot.keyboards.common import get_premium_keyboard, get_main_menu_keyboard
from bot.keyboards.engagement import get_premium_rewards_menu_keyboard
from bot.keyboards.premium_plan import get_premium_plan_payment_keyboard
from core.points_manager import PointsManager
from config.settings import settings

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "premium:info")
async def premium_info(callback: CallbackQuery):
    """Show premium information."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        
        if not user:
            await callback.answer("❌ User not found.", show_alert=True)
            return
        
        is_premium = await check_user_premium(db_session, user.id)
        
        if is_premium:
            expires_at = user.premium_expires_at.strftime("%Y-%m-%d %H:%M") if user.premium_expires_at else "هرگز"
            
            # Try to edit message, if fails send new message
            try:
                await callback.message.edit_text(
                    f"💎 وضعیت پریمیوم\n\n"
                    f"✅ شما اشتراک پریمیوم فعال دارید!\n\n"
                    f"تاریخ انقضا: {expires_at}\n\n"
                    f"ویژگی‌های پریمیوم:\n"
                    f"• تماس تصویری در وب اپ ( به زودی )\n"
                    f"• چت نامحدود بدون سکه و رایگان\n"
                    f"• درخواست تماس  نامحدود و رایگان\n"
                    f"• پیام دایرکت  نامحدود و رایگان\n"
                    f"• فیلترهای پیشرفته ( به زودی )\n"
                    f"• اولویت در صف (نفر اول صف)",
                    reply_markup=get_main_menu_keyboard()
                )
            except Exception:
                # If edit fails, send new message
                await callback.message.answer(
                    f"💎 وضعیت پریمیوم\n\n"
                    f"✅ شما اشتراک پریمیوم فعال دارید!\n\n"
                    f"تاریخ انقضا: {expires_at}\n\n"
                    f"ویژگی‌های پریمیوم:\n"
                    f"• تماس تصویری در وب اپ ( به زودی )\n"
                    f"• چت نامحدود بدون سکه و رایگان\n"
                    f"• درخواست تماس رایگان\n"
                    f"• پیام دایرکت رایگان\n"
                    f"• فیلترهای پیشرفته ( به زودی )\n"
                    f"• اولویت در صف (نفر اول صف)",
                    reply_markup=get_main_menu_keyboard()
                )
        else:
            # Get premium plans from database
            from db.crud import get_visible_premium_plans
            from bot.keyboards.premium_plan import get_user_premium_plans_keyboard
            
            plans = await get_visible_premium_plans(db_session)
            
            if plans:
                text = "💎 اشتراک پریمیوم\n\n"
                text += "با خرید پریمیوم از امکانات زیر بهره‌مند شوید:\n\n"
                text += "• تماس تصویری در وب اپ ( به زودی )\n"
                text += "• چت نامحدود بدون سکه و رایگان\n"
                text += "• درخواست تماس  نامحدود و رایگان\n"
                text += "• پیام دایرکت  نامحدود و رایگان\n"
                text += "• فیلترهای پیشرفته ( به زودی )\n"
                text += "• اولویت در صف (نفر اول صف)\n\n"
                text += "🎁 پلن‌های موجود:\n\n"
                
                from datetime import datetime
                now = datetime.utcnow()
                for plan in plans:
                    discount_text = ""
                    if plan.discount_start_date and plan.discount_end_date:
                        if plan.discount_start_date <= now <= plan.discount_end_date:
                            discount_text = f" 🔥 {plan.discount_percent}% تخفیف"
                    
                    text += f"💎 {plan.plan_name}\n"
                    if plan.original_price and plan.price < plan.original_price:
                        text += f"   ~~{int(plan.original_price):,}~~ {int(plan.price):,} تومان{discount_text}\n"
                    else:
                        text += f"   {int(plan.price):,} تومان\n"
                    text += f"   ⏰ {plan.duration_days} روز\n\n"
                
                text += "پلن مورد نظر را انتخاب کنید:"
                
                try:
                    await callback.message.edit_text(
                        text,
                        reply_markup=get_user_premium_plans_keyboard(plans)
                    )
                except Exception:
                    await callback.message.answer(
                        text,
                        reply_markup=get_user_premium_plans_keyboard(plans)
                    )
            else:
                # Fallback to default if no plans
                try:
                    await callback.message.edit_text(
                        f"💎 اشتراک پریمیوم\n\n"
                        f"با خرید پریمیوم از امکانات زیر بهره‌مند شوید:\n\n"
                        f"• تماس تصویری در وب اپ ( به زودی )\n"
                        f"• چت نامحدود بدون سکه و رایگان\n"
                        f"• درخواست تماس  نامحدود و رایگان\n"
                        f"• پیام دایرکت  نامحدود و رایگان\n"
                        f"• فیلترهای پیشرفته ( به زودی )\n"
                        f"• اولویت در صف (نفر اول صف)\n\n"
                        f"قیمت: {settings.PREMIUM_PRICE} تومان\n"
                        f"مدت زمان: {settings.PREMIUM_DURATION_DAYS} روز\n\n"
                        f"آیا می‌خواهید پریمیوم بخرید?",
                        reply_markup=get_premium_keyboard()
                    )
                except Exception:
                    await callback.message.answer(
                        f"💎 اشتراک پریمیوم\n\n"
                        f"با خرید پریمیوم از امکانات زیر بهره‌مند شوید:\n\n"
                        f"• تماس تصویری در وب اپ ( به زودی )\n"
                        f"• چت نامحدود بدون سکه و رایگان\n"
                        f"• درخواست تماس رایگان\n"
                        f"• پیام دایرکت رایگان\n"
                        f"• فیلترهای پیشرفته ( به زودی )\n"
                        f"• اولویت در صف (نفر اول صف)\n\n"
                        f"قیمت: {settings.PREMIUM_PRICE} تومان\n"
                        f"مدت زمان: {settings.PREMIUM_DURATION_DAYS} روز\n\n"
                        f"آیا می‌خواهید پریمیوم بخرید?",
                        reply_markup=get_premium_keyboard()
                    )
        
        await callback.answer()
        break


@router.callback_query(F.data == "premium:buy")
async def premium_buy(callback: CallbackQuery):
    """Handle premium purchase - redirect to premium plans."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Check if user already has premium
        is_premium = await check_user_premium(db_session, user.id)
        
        if is_premium:
            expires_at = user.premium_expires_at.strftime("%Y-%m-%d %H:%M") if user.premium_expires_at else "هرگز"
            await callback.answer(
                f"✅ شما قبلاً اشتراک پریمیوم دارید!\n\n"
                f"تاریخ انقضا: {expires_at}",
                show_alert=True
            )
            return
        
        # Redirect to premium plans
        from db.crud import get_visible_premium_plans
        from bot.keyboards.premium_plan import get_user_premium_plans_keyboard
        
        plans = await get_visible_premium_plans(db_session)
        
        if not plans:
            await callback.answer(
                "❌ در حال حاضر پلن پریمیومی موجود نیست.\n\n"
                "می‌توانید از طریق تبدیل سکه به پریمیوم استفاده کنید.",
                show_alert=True
            )
            return
        
        try:
            await callback.message.edit_text(
                "💎 پلن‌های پریمیوم\n\n"
                "یکی از پلن‌های زیر را انتخاب کنید:",
                reply_markup=get_user_premium_plans_keyboard(plans)
            )
        except Exception:
            # If edit fails (e.g., message not modified), send new message
            await callback.message.answer(
                "💎 پلن‌های پریمیوم\n\n"
                "یکی از پلن‌های زیر را انتخاب کنید:",
                reply_markup=get_user_premium_plans_keyboard(plans)
            )
        
        await callback.answer()
        break


@router.callback_query(F.data == "premium:purchase")
async def premium_purchase(callback: CallbackQuery):
    """Handle premium purchase from queue status."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Show premium info (same as premium:info)
        is_premium = await check_user_premium(db_session, user.id)
        
        if is_premium:
            expires_at = user.premium_expires_at.strftime("%Y-%m-%d %H:%M") if user.premium_expires_at else "هرگز"
            
            try:
                await callback.message.edit_text(
                    f"💎 وضعیت پریمیوم\n\n"
                    f"✅ شما اشتراک پریمیوم فعال دارید!\n\n"
                    f"تاریخ انقضا: {expires_at}\n\n"
                    f"ویژگی‌های پریمیوم:\n"
                    f"• تماس تصویری در وب اپ ( به زودی )\n"
                    f"• چت نامحدود بدون سکه و رایگان\n"
                    f"• درخواست تماس رایگان\n"
                    f"• پیام دایرکت رایگان\n"
                    f"• فیلترهای پیشرفته ( به زودی )\n"
                    f"• اولویت در صف (نفر اول صف)",
                    reply_markup=get_main_menu_keyboard()
                )
            except Exception:
                # If edit fails (e.g., message not modified), ignore
                pass
        else:
            # Get premium plans from database
            from db.crud import get_visible_premium_plans
            from bot.keyboards.premium_plan import get_user_premium_plans_keyboard
            
            plans = await get_visible_premium_plans(db_session)
            
            if plans:
                text = "💎 اشتراک پریمیوم\n\n"
                text += "با خرید پریمیوم از امکانات زیر بهره‌مند شوید:\n\n"
                text += "• تماس تصویری در وب اپ ( به زودی )\n"
                text += "• چت نامحدود بدون سکه و رایگان\n"
                text += "• درخواست تماس رایگان\n"
                text += "• پیام دایرکت رایگان\n"
                text += "• فیلترهای پیشرفته ( به زودی )\n"
                text += "• اولویت در صف (نفر اول صف)\n\n"
                text += "🎁 پلن‌های موجود:\n\n"
                
                from datetime import datetime
                now = datetime.utcnow()
                for plan in plans:
                    discount_text = ""
                    if plan.discount_start_date and plan.discount_end_date:
                        if plan.discount_start_date <= now <= plan.discount_end_date:
                            discount_text = f" 🔥 {plan.discount_percent}% تخفیف"
                    
                    text += f"💎 {plan.plan_name}\n"
                    if plan.original_price and plan.price < plan.original_price:
                        text += f"   ~~{int(plan.original_price):,}~~ {int(plan.price):,} تومان{discount_text}\n"
                    else:
                        text += f"   {int(plan.price):,} تومان\n"
                    text += f"   ⏰ {plan.duration_days} روز\n\n"
                
                text += "پلن مورد نظر را انتخاب کنید:"
                
                try:
                    await callback.message.edit_text(
                        text,
                        reply_markup=get_user_premium_plans_keyboard(plans)
                    )
                except Exception:
                    # If edit fails (e.g., message not modified), send new message
                    await callback.message.answer(
                        text,
                        reply_markup=get_user_premium_plans_keyboard(plans)
                    )
            else:
                # Fallback to default if no plans
                try:
                    await callback.message.edit_text(
                        f"💎 اشتراک پریمیوم\n\n"
                        f"با خرید پریمیوم از امکانات زیر بهره‌مند شوید:\n\n"
                        f"• تماس تصویری در وب اپ ( به زودی )\n"
                        f"• چت نامحدود بدون سکه و رایگان\n"
                        f"• درخواست تماس رایگان\n"
                        f"• پیام دایرکت رایگان\n"
                        f"• فیلترهای پیشرفته ( به زودی )\n"
                        f"• اولویت در صف (نفر اول صف)\n\n"
                        f"قیمت: {settings.PREMIUM_PRICE} تومان\n"
                        f"مدت زمان: {settings.PREMIUM_DURATION_DAYS} روز\n\n"
                        f"آیا می‌خواهید پریمیوم بخرید?",
                        reply_markup=get_premium_keyboard()
                    )
                except Exception:
                    # If edit fails (e.g., message not modified), send new message
                    await callback.message.answer(
                        f"💎 اشتراک پریمیوم\n\n"
                        f"با خرید پریمیوم از امکانات زیر بهره‌مند شوید:\n\n"
                        f"• تماس تصویری در وب اپ ( به زودی )\n"
                        f"• چت نامحدود بدون سکه و رایگان\n"
                        f"• درخواست تماس رایگان\n"
                        f"• پیام دایرکت رایگان\n"
                        f"• فیلترهای پیشرفته ( به زودی )\n"
                        f"• اولویت در صف (نفر اول صف)\n\n"
                        f"قیمت: {settings.PREMIUM_PRICE} تومان\n"
                        f"مدت زمان: {settings.PREMIUM_DURATION_DAYS} روز\n\n"
                        f"آیا می‌خواهید پریمیوم بخرید?",
                        reply_markup=get_premium_keyboard()
                    )
        
        await callback.answer()
        break


async def process_premium_purchase(
    user_id: int,
    provider: str,
    transaction_id: str,
    amount: float
) -> bool:
    """
    Process premium purchase.
    
    Args:
        user_id: Telegram user ID
        provider: Payment provider (e.g., 'myket')
        transaction_id: Transaction ID
        amount: Payment amount
        
    Returns:
        True if successful
    """
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        
        if not user:
            return False
        
        # Create premium subscription (use default duration from settings)
        from datetime import timedelta
        now = datetime.utcnow()
        duration_to_add = timedelta(days=settings.PREMIUM_DURATION_DAYS)
        
        # Calculate expiration date
        if user.premium_expires_at and user.premium_expires_at > now:
            # Extend existing premium
            expiration_date = user.premium_expires_at + duration_to_add
        else:
            # Start new premium
            expiration_date = now + duration_to_add
        
        subscription = await create_premium_subscription(
            db_session,
            user.id,
            provider,
            transaction_id,
            amount,
            start_date=now,
            end_date=expiration_date
        )
        
        # Check and award badges for premium achievements
        if subscription:
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
        
        return subscription is not None


@router.callback_query(F.data.startswith("premium:plan:") & ~F.data.startswith("premium:plan:stars:") & ~F.data.startswith("premium:plan:shaparak:"))
async def premium_plan_purchase(callback: CallbackQuery):
    """Handle premium plan purchase selection - show payment methods."""
    user_id = callback.from_user.id
    plan_id = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Get plan
        plan = await get_premium_plan_by_id(db_session, plan_id)
        
        if not plan or not plan.is_active or not plan.is_visible:
            await callback.answer("❌ پلن یافت نشد یا غیرفعال است.", show_alert=True)
            return
        
        # Check if user already has premium
        is_premium = await check_user_premium(db_session, user.id)
        
        if is_premium:
            expires_at = user.premium_expires_at.strftime("%Y-%m-%d %H:%M") if user.premium_expires_at else "هرگز"
            await callback.answer(
                f"✅ شما قبلاً اشتراک پریمیوم دارید!\n\n"
                f"تاریخ انقضا: {expires_at}",
                show_alert=True
            )
            return
        
        # Show payment method selection
        import json
        # Get payment methods, default to shaparak if not set
        if plan.payment_methods_json:
            try:
                payment_methods = json.loads(plan.payment_methods_json)
            except (json.JSONDecodeError, TypeError):
                payment_methods = ["shaparak"]
        else:
            payment_methods = ["shaparak"]
        
        discount_text = ""
        from datetime import datetime
        now = datetime.utcnow()
        if plan.discount_start_date and plan.discount_end_date:
            if plan.discount_start_date <= now <= plan.discount_end_date:
                discount_text = f"\n🔥 تخفیف {plan.discount_percent}% فعال است!"
        
        plan_info = (
            f"💎 پلن: {plan.plan_name}\n"
            f"📅 مدت زمان: {plan.duration_days} روز\n"
            f"💰 قیمت: {int(plan.price):,} تومان"
        )
        
        if plan.stars_required:
            plan_info += f"\n⭐ استارز: {plan.stars_required} ⭐"
        
        plan_info += discount_text
        plan_info += "\n\nروش پرداخت را انتخاب کنید:"
        
        try:
            await callback.message.edit_text(
                plan_info,
                reply_markup=get_premium_plan_payment_keyboard(plan)
            )
        except Exception:
            # If edit fails (e.g., message not modified), send new message
            await callback.message.answer(
                plan_info,
                reply_markup=get_premium_plan_payment_keyboard(plan)
            )
        
        await callback.answer()
        break


@router.callback_query(F.data.startswith("premium:plan:stars:") | F.data.startswith("premium:plan:shaparak:"))
async def premium_plan_payment_method(callback: CallbackQuery):
    """Handle premium plan payment method selection."""
    user_id = callback.from_user.id
    parts = callback.data.split(":")
    
    if len(parts) != 4:
        await callback.answer("❌ خطا در پردازش درخواست.", show_alert=True)
        return
    
    payment_method = parts[2]  # "stars" or "shaparak"
    plan_id = int(parts[3])
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Get plan
        plan = await get_premium_plan_by_id(db_session, plan_id)
        
        if not plan or not plan.is_active or not plan.is_visible:
            await callback.answer("❌ پلن یافت نشد یا غیرفعال است.", show_alert=True)
            return
        
        # Check if user already has premium
        is_premium = await check_user_premium(db_session, user.id)
        
        if is_premium:
            expires_at = user.premium_expires_at.strftime("%Y-%m-%d %H:%M") if user.premium_expires_at else "هرگز"
            await callback.answer(
                f"✅ شما قبلاً اشتراک پریمیوم دارید!\n\n"
                f"تاریخ انقضا: {expires_at}",
                show_alert=True
            )
            return
        
        # Process payment based on method
        if payment_method == "stars":
            await process_stars_payment(callback, db_session, user, plan)
        elif payment_method == "shaparak":
            await process_shaparak_payment(callback, db_session, user, plan)
        
        await callback.answer()
        break


async def process_stars_payment(
    callback: CallbackQuery,
    db_session,
    user,
    plan
):
    """Process Stars payment for premium plan."""
    if not plan.stars_required:
        await callback.answer("❌ این پلن پرداخت با استارز ندارد.", show_alert=True)
        return
    
    # Create invoice for Stars payment
    from datetime import timedelta
    now = datetime.utcnow()
    duration_to_add = timedelta(days=plan.duration_days)
    
    # Calculate expiration date
    if user.premium_expires_at and user.premium_expires_at > now:
        expiration_date = user.premium_expires_at + duration_to_add
    else:
        expiration_date = now + duration_to_add
    
    # Create invoice
    bot = Bot(token=settings.BOT_TOKEN)
    invoice_title = f"💎 پریمیوم {plan.plan_name}"
    invoice_description = (
        f"اشتراک پریمیوم {plan.duration_days} روزه\n"
        f"مدت زمان: {plan.duration_days} روز"
    )
    
    # Stars payment uses LabeledPrice with amount in stars (1 star = 1)
    prices = [LabeledPrice(label="پریمیوم", amount=plan.stars_required)]
    
    # Create payload to identify this purchase
    payload = f"premium_plan_{plan.id}_{user.id}_{int(now.timestamp())}"
    
    try:
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=invoice_title,
            description=invoice_description,
            payload=payload,
            provider_token=None,  # Stars don't need provider token
            currency="XTR",  # Telegram Stars currency
            prices=prices,
            start_parameter=payload,
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False,
        )
        await bot.session.close()
    except Exception as e:
        await callback.answer(f"❌ خطا در ایجاد فاکتور: {str(e)}", show_alert=True)
        await bot.session.close()


async def process_shaparak_payment(
    callback: CallbackQuery,
    db_session,
    user,
    plan
):
    """Process Shaparak payment for premium plan via Zarinpal."""
    from db.crud import create_payment_transaction, get_system_setting_value
    import requests
    
    # Get payment gateway domain (external URL configured by admin)
    gateway_domain = await get_system_setting_value(
        db_session,
        'payment_gateway_domain',
        None
    )
    
    # Gateway domain must be configured by admin
    if not gateway_domain or gateway_domain == 'https://payment.example.com' or gateway_domain.strip() == '':
        await callback.answer(
            "❌ درگاه پرداخت تنظیم نشده است.\n\n"
            "لطفاً با ادمین تماس بگیرید.",
            show_alert=True
        )
        return
    
    # Ensure gateway_domain doesn't have trailing slash
    gateway_domain = gateway_domain.rstrip('/')
    
    # Create payment transaction
    # callback_url for Zarinpal callback
    callback_url = f"{gateway_domain}/payment/callback"
    
    transaction = await create_payment_transaction(
        db_session,
        user.id,
        plan.id,
        plan.price,
        gateway="zarinpal",
        currency="IRT",
        callback_url=callback_url,
        return_url=None  # Not needed in new flow
    )
    
    if not transaction:
        await callback.answer("❌ خطا در ایجاد تراکنش.", show_alert=True)
        return
    
    # Create unique payment link
    payment_link = f"{gateway_domain}/transition/{transaction.transaction_id}"
    
    # Get bot username for return link
    try:
        bot_info = await callback.bot.get_me()
        bot_username = bot_info.username or "bot"
    except Exception:
        bot_username = "asdasdczaxcqeqwbot"  # Fallback to provided username
    
    # Create inline button for payment link (transparent/inline button)
    payment_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 پرداخت آنلاین", url=payment_link)]
    ])
    
    try:
        await callback.message.edit_text(
            f"💳 پرداخت با زرین‌پال\n\n"
            f"💎 پلن: {plan.plan_name}\n"
            f"💰 مبلغ: {int(plan.price):,} تومان\n\n"
            f"⚠️🔒 قبل از اقدام برای پرداخت، فیلترشکن خودتون رو خاموش کنید! 🔒⚠️\n\n"
            f"💡 پس از پرداخت، می‌توانید از طریق لینک بازگشت به ربات برگردید.",
            reply_markup=payment_keyboard
        )
    except Exception:
        # If edit fails (e.g., message not modified), send new message
        await callback.message.answer(
            f"💳 پرداخت با زرین‌پال\n\n"
            f"💎 پلن: {plan.plan_name}\n"
            f"💰 مبلغ: {int(plan.price):,} تومان\n\n"
            f"⚠️🔒 قبل از اقدام برای پرداخت، فیلترشکن خودتون رو خاموش کنید! 🔒⚠️\n\n"
            f"💡 پس از پرداخت، می‌توانید از طریق لینک بازگشت به ربات برگردید.",
            reply_markup=payment_keyboard
        )
    
    await callback.answer("✅ لینک پرداخت برای شما نمایش داده شد.", show_alert=True)


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    """Handle pre-checkout query for Stars payment."""
    # Verify the payment
    await pre_checkout_query.answer(ok=True)


@router.message(F.content_type == "successful_payment")
async def successful_payment_handler(message: Message):
    """Handle successful payment (Stars)."""
    payment: SuccessfulPayment = message.successful_payment
    
    # Parse payload to get plan_id and user_id
    payload = payment.invoice_payload
    if not payload.startswith("premium_plan_"):
        await message.answer("❌ خطا در پردازش پرداخت.")
        return
    
    parts = payload.split("_")
    if len(parts) < 4:
        await message.answer("❌ خطا در پردازش پرداخت.")
        return
    
    plan_id = int(parts[2])
    user_id = int(parts[3])
    
    async for db_session in get_db():
        plan = await get_premium_plan_by_id(db_session, plan_id)
        user = await get_user_by_id(db_session, user_id)
        
        if not plan or not user:
            await message.answer("❌ خطا در پردازش پرداخت.")
            return
        
        # Check if user already has premium
        is_premium = await check_user_premium(db_session, user.id)
        
        if is_premium:
            expires_at = user.premium_expires_at.strftime("%Y-%m-%d %H:%M") if user.premium_expires_at else "هرگز"
            await message.answer(
                f"✅ شما قبلاً اشتراک پریمیوم دارید!\n\n"
                f"تاریخ انقضا: {expires_at}"
            )
            return
        
        # Calculate expiration date
        from datetime import timedelta
        now = datetime.utcnow()
        duration_to_add = timedelta(days=plan.duration_days)
        
        # Calculate expiration date
        if user.premium_expires_at and user.premium_expires_at > now:
            expiration_date = user.premium_expires_at + duration_to_add
        else:
            expiration_date = now + duration_to_add
        
        # Create premium subscription
        transaction_id = f"plan_stars_{user.id}_{plan.id}_{int(now.timestamp())}"
        subscription = await create_premium_subscription(
            db_session,
            user.id,
            provider="premium_plan_stars",
            transaction_id=transaction_id,
            amount=0.0,  # Stars payment - amount is in stars
            start_date=now,
            end_date=expiration_date
        )
        
        if subscription:
            expires_at = expiration_date.strftime("%Y-%m-%d %H:%M")
            await message.answer(
                f"✅ پرداخت موفق!\n\n"
                f"💎 اشتراک پریمیوم «{plan.plan_name}» فعال شد!\n\n"
                f"📅 تاریخ انقضا: {expires_at}\n\n"
                f"از این به بعد می‌توانید از تمام امکانات پریمیوم استفاده کنید."
            )
        else:
            await message.answer("❌ خطا در فعال کردن پریمیوم.")


@router.callback_query(F.data == "premium:features")
async def premium_features(callback: CallbackQuery):
    """Show premium features list."""
    from bot.keyboards.common import get_premium_keyboard
    
    features_text = (
        f"💎 Premium Features\n\n"
        f"1. Video Calls\n"
        f"   • Start video calls with your chat partner\n"
        f"   • Only one user needs to be premium\n\n"
        f"2. Longer Chat Time\n"
        f"   • Free users: {settings.MAX_CHAT_DURATION_MINUTES} minutes\n"
        f"   • Premium users: {settings.PREMIUM_CHAT_DURATION_MINUTES} minutes\n\n"
        f"3. Advanced Filters\n"
        f"   • Filter by specific age range\n"
        f"   • Filter by city\n"
        f"   • Filter by gender preferences\n\n"
        f"4. Priority Matching\n"
        f"   • Get matched faster\n"
        f"   • Higher priority in queue\n\n"
        f"Price: {settings.PREMIUM_PRICE} Toman\n"
        f"Duration: {settings.PREMIUM_DURATION_DAYS} days"
    )
    
    try:
        await callback.message.edit_text(
            features_text,
            reply_markup=get_premium_keyboard()
        )
    except Exception:
        # If edit fails (e.g., message not modified), send new message
        await callback.message.answer(
            features_text,
            reply_markup=get_premium_keyboard()
        )
    await callback.answer()

