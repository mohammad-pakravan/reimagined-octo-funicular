"""
System settings handler for admin panel.
Handles system configuration like payment gateway domain, Zarinpal settings, etc.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.fsm.state import State, StatesGroup

from db.database import get_db
from db.crud import get_system_setting_value, set_system_setting
from bot.keyboards.admin import get_admin_system_settings_keyboard, get_admin_main_keyboard
from bot.handlers.admin import is_admin

router = Router()


class SystemSettingStates(StatesGroup):
    """FSM states for system settings."""
    waiting_payment_gateway_domain = State()
    waiting_zarinpal_merchant_id = State()


@router.callback_query(F.data == "admin:system_settings")
async def admin_system_settings(callback: CallbackQuery):
    """Show system settings menu."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    async for db_session in get_db():
        gateway_domain = await get_system_setting_value(db_session, 'payment_gateway_domain', 'تنظیم نشده')
        merchant_id = await get_system_setting_value(db_session, 'zarinpal_merchant_id', 'تنظیم نشده')
        sandbox = await get_system_setting_value(db_session, 'zarinpal_sandbox', 'true')
        sandbox_text = "فعال" if sandbox.lower() == 'true' else "غیرفعال"
        
        text = (
            "⚙️ تنظیمات سیستم\n\n"
            f"🌐 آدرس درگاه پرداخت: {gateway_domain}\n"
            f"🔑 Merchant ID زرین‌پال: {merchant_id}\n"
            f"🧪 حالت Sandbox: {sandbox_text}\n\n"
            "یکی از تنظیمات را برای ویرایش انتخاب کنید:"
        )
        
        await callback.message.edit_text(text, reply_markup=get_admin_system_settings_keyboard())
        await callback.answer()
        break


@router.callback_query(F.data == "admin:setting:payment_gateway_domain")
async def admin_setting_payment_gateway_domain(callback: CallbackQuery, state: FSMContext):
    """Set payment gateway domain."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🌐 تنظیم آدرس درگاه پرداخت\n\n"
        "لطفاً آدرس کامل دامنه سرور Flask را وارد کنید:\n\n"
        "مثال: https://payment.example.com\n\n"
        "یا /cancel برای لغو"
    )
    await state.set_state(SystemSettingStates.waiting_payment_gateway_domain)
    await callback.answer()


@router.callback_query(F.data == "admin:setting:zarinpal_merchant_id")
async def admin_setting_zarinpal_merchant_id(callback: CallbackQuery, state: FSMContext):
    """Set Zarinpal merchant ID."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔑 تنظیم Merchant ID زرین‌پال\n\n"
        "لطفاً Merchant ID خود را از پنل زرین‌پال وارد کنید:\n\n"
        "یا /cancel برای لغو"
    )
    await state.set_state(SystemSettingStates.waiting_zarinpal_merchant_id)
    await callback.answer()


@router.callback_query(F.data == "admin:setting:zarinpal_sandbox")
async def admin_setting_zarinpal_sandbox(callback: CallbackQuery):
    """Toggle Zarinpal sandbox mode."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    async for db_session in get_db():
        current_sandbox = await get_system_setting_value(db_session, 'zarinpal_sandbox', 'true')
        new_sandbox = 'false' if current_sandbox.lower() == 'true' else 'true'
        
        await set_system_setting(
            db_session,
            'zarinpal_sandbox',
            new_sandbox,
            'bool',
            'Enable Zarinpal sandbox mode for testing'
        )
        
        sandbox_text = "فعال" if new_sandbox == 'true' else "غیرفعال"
        await callback.answer(f"✅ حالت Sandbox: {sandbox_text}", show_alert=True)
        
        # Refresh settings menu
        await admin_system_settings(callback)
        break


@router.message(F.text & F.text.startswith("/cancel"))
async def cancel_setting(message: Message, state: FSMContext):
    """Cancel setting update."""
    if not is_admin(message.from_user.id):
        return
    
    await state.clear()
    await message.answer("❌ عملیات لغو شد.")


@router.message(StateFilter(SystemSettingStates.waiting_payment_gateway_domain), F.text & ~F.text.startswith("/"))
async def process_setting_payment_gateway_domain(message: Message, state: FSMContext):
    """Process payment gateway domain setting."""
    if not is_admin(message.from_user.id):
        return
    
    domain = message.text.strip()
    
    # Basic validation
    if not domain.startswith("http://") and not domain.startswith("https://"):
        await message.answer("❌ آدرس باید با http:// یا https:// شروع شود.\n\nلطفاً دوباره وارد کنید:")
        return
    
    async for db_session in get_db():
        await set_system_setting(
            db_session,
            'payment_gateway_domain',
            domain,
            'string',
            'Payment gateway Flask server domain URL'
        )
        
        await message.answer(f"✅ آدرس درگاه پرداخت به {domain} تغییر یافت.")
        await state.clear()
        break


@router.message(StateFilter(SystemSettingStates.waiting_zarinpal_merchant_id), F.text & ~F.text.startswith("/"))
async def process_setting_zarinpal_merchant_id(message: Message, state: FSMContext):
    """Process Zarinpal merchant ID setting."""
    if not is_admin(message.from_user.id):
        return
    
    merchant_id = message.text.strip()
    
    if not merchant_id:
        await message.answer("❌ Merchant ID نمی‌تواند خالی باشد.\n\nلطفاً دوباره وارد کنید:")
        return
    
    async for db_session in get_db():
        await set_system_setting(
            db_session,
            'zarinpal_merchant_id',
            merchant_id,
            'string',
            'Zarinpal merchant ID for payment gateway'
        )
        
        await message.answer(f"✅ Merchant ID زرین‌پال ثبت شد: {merchant_id}")
        await state.clear()
        break

