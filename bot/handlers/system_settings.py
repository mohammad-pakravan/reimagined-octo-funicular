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
    waiting_chat_message_cost = State()
    waiting_filtered_chat_cost = State()
    waiting_chat_success_message_count = State()
    waiting_chat_success_message_count_female = State()


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
        chat_cost = await get_system_setting_value(db_session, 'chat_message_cost', '1')
        filtered_chat_cost = await get_system_setting_value(db_session, 'filtered_chat_cost', '1')
        success_message_count = await get_system_setting_value(db_session, 'chat_success_message_count', '2')
        success_message_count_female = await get_system_setting_value(db_session, 'chat_success_message_count_female', '10')
        
        text = (
            "⚙️ تنظیمات سیستم\n\n"
            f"🌐 آدرس درگاه پرداخت: {gateway_domain}\n"
            f"🔑 Merchant ID زرین‌پال: {merchant_id}\n"
            f"🧪 حالت Sandbox: {sandbox_text}\n"
            f"💰 هزینه هر پیام چت (غیر پریمیوم): {chat_cost} سکه\n"
            f"💰 هزینه چت فیلتردار: {filtered_chat_cost} سکه\n"
            f"📊 تعداد پیام برای کسر سکه (پسر): {success_message_count} پیام\n"
            f"📊 تعداد پیام برای پاداش دخترها: {success_message_count_female} پیام\n\n"
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


@router.callback_query(F.data == "admin:setting:chat_message_cost")
async def admin_setting_chat_message_cost(callback: CallbackQuery, state: FSMContext):
    """Set chat message cost."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "💰 تنظیم هزینه هر پیام چت\n\n"
        "لطفاً تعداد سکه‌ای که برای هر پیام چت از کاربران غیر پریمیوم کسر می‌شود را وارد کنید:\n\n"
        "مثال: 1\n\n"
        "یا /cancel برای لغو"
    )
    await state.set_state(SystemSettingStates.waiting_chat_message_cost)
    await callback.answer()


@router.message(StateFilter(SystemSettingStates.waiting_chat_message_cost), F.text & ~F.text.startswith("/"))
async def process_setting_chat_message_cost(message: Message, state: FSMContext):
    """Process chat message cost setting."""
    if not is_admin(message.from_user.id):
        return
    
    try:
        cost = int(message.text.strip())
        if cost < 0:
            await message.answer("❌ هزینه نمی‌تواند منفی باشد.\n\nلطفاً دوباره وارد کنید:")
            return
    except ValueError:
        await message.answer("❌ لطفاً یک عدد معتبر وارد کنید.\n\nلطفاً دوباره وارد کنید:")
        return
    
    async for db_session in get_db():
        await set_system_setting(
            db_session,
            'chat_message_cost',
            str(cost),
            'int',
            'Cost in coins for each chat message (non-premium users)'
        )
        
        await message.answer(f"✅ هزینه هر پیام چت به {cost} سکه تغییر یافت.")
        await state.clear()
        break


@router.callback_query(F.data == "admin:setting:filtered_chat_cost")
async def admin_setting_filtered_chat_cost(callback: CallbackQuery, state: FSMContext):
    """Set filtered chat cost."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "💰 تنظیم هزینه چت فیلتردار\n\n"
        "لطفاً تعداد سکه‌ای که برای شروع چت فیلتردار (مثلاً پسر→دختر، دختر→پسر) از کاربران غیر پریمیوم کسر می‌شود را وارد کنید:\n\n"
        "⚠️ توجه: این سکه برگشت داده نمی‌شود.\n\n"
        "مثال: 1\n\n"
        "یا /cancel برای لغو"
    )
    await state.set_state(SystemSettingStates.waiting_filtered_chat_cost)
    await callback.answer()


@router.message(StateFilter(SystemSettingStates.waiting_filtered_chat_cost), F.text & ~F.text.startswith("/"))
async def process_setting_filtered_chat_cost(message: Message, state: FSMContext):
    """Process filtered chat cost setting."""
    if not is_admin(message.from_user.id):
        return
    
    try:
        cost = int(message.text.strip())
        if cost < 0:
            await message.answer("❌ هزینه نمی‌تواند منفی باشد.\n\nلطفاً دوباره وارد کنید:")
            return
    except ValueError:
        await message.answer("❌ لطفاً یک عدد معتبر وارد کنید.\n\nلطفاً دوباره وارد کنید:")
        return
    
    async for db_session in get_db():
        await set_system_setting(
            db_session,
            'filtered_chat_cost',
            str(cost),
            'int',
            'Cost in coins for filtered chat (e.g., boy->girl, girl->boy). Non-refundable. Random chat is free.'
        )
        
        await message.answer(f"✅ هزینه چت فیلتردار به {cost} سکه تغییر یافت.")
        await state.clear()
        break


@router.callback_query(F.data == "admin:setting:chat_success_message_count")
async def admin_setting_chat_success_message_count(callback: CallbackQuery, state: FSMContext):
    """Set chat success message count."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📊 تنظیم تعداد پیام برای کسر سکه\n\n"
        "لطفاً تعداد پیامی که هر کاربر باید ارسال کند تا چت موفقیت‌آمیز محسوب شود را وارد کنید:\n\n"
        "مثال: 2\n\n"
        "یا /cancel برای لغو"
    )
    await state.set_state(SystemSettingStates.waiting_chat_success_message_count)
    await callback.answer()


@router.callback_query(F.data == "admin:setting:chat_success_message_count_female")
async def admin_setting_chat_success_message_count_female(callback: CallbackQuery, state: FSMContext):
    """Set chat success message count for female reward."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return

    await callback.message.edit_text(
        "📊 تنظیم تعداد پیام برای پاداش دخترها\n\n"
        "لطفاً تعداد پیامی که دختر باید ارسال کند تا چت موفقیت‌آمیز محسوب شود را وارد کنید:\n\n"
        "مثال: 10\n\n"
        "یا /cancel برای لغو"
    )
    await state.set_state(SystemSettingStates.waiting_chat_success_message_count_female)
    await callback.answer()


@router.message(StateFilter(SystemSettingStates.waiting_chat_success_message_count), F.text & ~F.text.startswith("/"))
async def process_setting_chat_success_message_count(message: Message, state: FSMContext):
    """Process chat success message count setting."""
    if not is_admin(message.from_user.id):
        return
    
    try:
        count = int(message.text.strip())
        if count < 1:
            await message.answer("❌ تعداد پیام نمی‌تواند کمتر از 1 باشد.\n\nلطفاً دوباره وارد کنید:")
            return
    except ValueError:
        await message.answer("❌ لطفاً یک عدد معتبر وارد کنید.\n\nلطفاً دوباره وارد کنید:")
        return
    
    async for db_session in get_db():
        await set_system_setting(
            db_session,
            'chat_success_message_count',
            str(count),
            'int',
            'Number of messages each user must send for chat to be considered successful'
        )
        
        await message.answer(f"✅ تعداد پیام برای کسر سکه به {count} پیام تغییر یافت.")
        await state.clear()
        break


@router.message(StateFilter(SystemSettingStates.waiting_chat_success_message_count_female), F.text & ~F.text.startswith("/"))
async def process_setting_chat_success_message_count_female(message: Message, state: FSMContext):
    """Process chat success message count setting for female reward."""
    if not is_admin(message.from_user.id):
        return

    try:
        count = int(message.text.strip())
        if count < 1:
            await message.answer("❌ تعداد پیام نمی‌تواند کمتر از 1 باشد.\n\nلطفاً دوباره وارد کنید:")
            return
    except ValueError:
        await message.answer("❌ لطفاً یک عدد معتبر وارد کنید.\n\nلطفاً دوباره وارد کنید:")
        return

    async for db_session in get_db():
        await set_system_setting(
            db_session,
            'chat_success_message_count_female',
            str(count),
            'int',
            'Number of messages girls must send to earn chat bonus'
        )

        await message.answer(f"✅ تعداد پیام برای پاداش دخترها به {count} پیام تغییر یافت.")
        await state.clear()
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

