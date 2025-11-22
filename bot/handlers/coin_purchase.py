"""
Coin purchase handler for the bot.
Handles coin package purchase flow.
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery, SuccessfulPayment, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
import logging

from db.database import get_db
from db.crud import (
    get_user_by_telegram_id,
    get_coin_package_by_id,
    get_user_by_id,
    get_system_setting_value,
    create_payment_transaction,
    add_points,
)
from bot.keyboards.coin_package import get_user_coin_packages_keyboard, get_coin_package_payment_keyboard
from config.settings import settings

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data.startswith("coin:package:") & ~F.data.startswith("coin:package:stars:") & ~F.data.startswith("coin:package:shaparak:"))
async def coin_package_purchase(callback: CallbackQuery):
    """Handle coin package purchase selection - show payment methods."""
    user_id = callback.from_user.id
    package_id = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Get package
        package = await get_coin_package_by_id(db_session, package_id)
        
        if not package or not package.is_active or not package.is_visible:
            await callback.answer("❌ پکیج یافت نشد یا غیرفعال است.", show_alert=True)
            return
        
        # Show payment method selection
        import json
        # Get payment methods, default to shaparak if not set
        if package.payment_methods_json:
            try:
                payment_methods = json.loads(package.payment_methods_json)
            except (json.JSONDecodeError, TypeError):
                payment_methods = ["shaparak"]
        else:
            payment_methods = ["shaparak"]
        
        discount_text = ""
        now = datetime.utcnow()
        if package.discount_start_date and package.discount_end_date:
            if package.discount_start_date <= now <= package.discount_end_date:
                discount_text = f"\n🔥 تخفیف {package.discount_percent}% فعال است!"
        
        package_info = (
            f"🪙 پکیج: {package.package_name}\n"
            f"💰 قیمت: {int(package.price):,} تومان"
        )
        
        if package.stars_required:
            package_info += f"\n⭐ استارز: {package.stars_required} ⭐"
        
        package_info += discount_text
        package_info += "\n\nروش پرداخت را انتخاب کنید:"
        
        try:
            await callback.message.edit_text(
                package_info,
                reply_markup=get_coin_package_payment_keyboard(package)
            )
        except Exception:
            # If edit fails (e.g., message not modified), send new message
            await callback.message.answer(
                package_info,
                reply_markup=get_coin_package_payment_keyboard(package)
            )
        
        await callback.answer()
        break


@router.callback_query(F.data.startswith("coin:package:stars:") | F.data.startswith("coin:package:shaparak:"))
async def coin_package_payment_method(callback: CallbackQuery):
    """Handle coin package payment method selection."""
    user_id = callback.from_user.id
    parts = callback.data.split(":")
    
    if len(parts) != 4:
        await callback.answer("❌ خطا در پردازش درخواست.", show_alert=True)
        return
    
    payment_method = parts[2]  # "stars" or "shaparak"
    package_id = int(parts[3])
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Get package
        package = await get_coin_package_by_id(db_session, package_id)
        
        if not package or not package.is_active or not package.is_visible:
            await callback.answer("❌ پکیج یافت نشد یا غیرفعال است.", show_alert=True)
            return
        
        # Process payment based on method
        if payment_method == "stars":
            await process_stars_payment(callback, db_session, user, package)
        elif payment_method == "shaparak":
            await process_shaparak_payment(callback, db_session, user, package)
        
        await callback.answer()
        break


async def process_stars_payment(
    callback: CallbackQuery,
    db_session,
    user,
    package
):
    """Process Stars payment for coin package."""
    if not package.stars_required:
        await callback.answer("❌ این پکیج پرداخت با استارز ندارد.", show_alert=True)
        return
    
    # Create invoice for Stars payment
    now = datetime.utcnow()
    
    # Create invoice
    bot = Bot(token=settings.BOT_TOKEN)
    invoice_title = f"🪙 {package.package_name}"
    invoice_description = (
        f"خرید {package.coin_amount} سکه"
    )
    
    # Stars payment uses LabeledPrice with amount in stars (1 star = 1)
    prices = [LabeledPrice(label="سکه", amount=package.stars_required)]
    
    # Create payload to identify this purchase
    payload = f"coin_package_{package.id}_{user.id}_{int(now.timestamp())}"
    
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
    package
):
    """Process Shaparak payment for coin package via Zarinpal."""
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
        None,  # No plan_id for coin purchases
        package.price,
        gateway="zarinpal",
        currency="IRT",
        callback_url=callback_url,
        return_url=None,  # Not needed in new flow
        coin_package_id=package.id  # Add coin package ID
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
            f"🪙 پکیج: {package.package_name}\n"
            f"💰 مبلغ: {int(package.price):,} تومان\n\n"
            f"⚠️🔒 قبل از اقدام برای پرداخت، فیلترشکن خودتون رو خاموش کنید! 🔒⚠️\n\n"
            f"💡 پس از پرداخت، می‌توانید از طریق لینک بازگشت به ربات برگردید.",
            reply_markup=payment_keyboard
        )
    except Exception:
        # If edit fails (e.g., message not modified), send new message
        await callback.message.answer(
            f"💳 پرداخت با زرین‌پال\n\n"
            f"🪙 پکیج: {package.package_name}\n"
            f"💰 مبلغ: {int(package.price):,} تومان\n\n"
            f"⚠️🔒 قبل از اقدام برای پرداخت، فیلترشکن خودتون رو خاموش کنید! 🔒⚠️\n\n"
            f"💡 پس از پرداخت، می‌توانید از طریق لینک بازگشت به ربات برگردید.",
            reply_markup=payment_keyboard
        )
    
    await callback.answer("✅ لینک پرداخت برای شما نمایش داده شد.", show_alert=True)


@router.pre_checkout_query()
async def pre_checkout_handler_coin(pre_checkout_query: PreCheckoutQuery):
    """Handle pre-checkout query for Stars payment (coins)."""
    # Verify the payment
    await pre_checkout_query.answer(ok=True)


@router.message(F.content_type == "successful_payment")
async def successful_payment_handler_coin(message: Message):
    """Handle successful payment (Stars) for coin packages."""
    payment: SuccessfulPayment = message.successful_payment
    
    # Parse payload to get package_id and user_id
    payload = payment.invoice_payload
    if not payload.startswith("coin_package_"):
        # Not a coin package payment, skip
        return
    
    parts = payload.split("_")
    if len(parts) < 4:
        await message.answer("❌ خطا در پردازش پرداخت.")
        return
    
    package_id = int(parts[2])
    user_id = int(parts[3])
    
    async for db_session in get_db():
        package = await get_coin_package_by_id(db_session, package_id)
        user = await get_user_by_id(db_session, user_id)
        
        if not package or not user:
            await message.answer("❌ خطا در پردازش پرداخت.")
            return
        
        # Add coins to user
        success = await add_points(
            db_session,
            user.id,
            package.coin_amount,
            "earned",
            "coin_purchase",
            f"Purchased {package.package_name} with Stars"
        )
        
        if success:
            await message.answer(
                f"✅ پرداخت موفق!\n\n"
                f"🪙 {package.coin_amount} سکه به حساب شما اضافه شد!\n\n"
                f"از خرید شما متشکریم."
            )
        else:
            await message.answer("❌ خطا در افزودن سکه.")
        
        break

