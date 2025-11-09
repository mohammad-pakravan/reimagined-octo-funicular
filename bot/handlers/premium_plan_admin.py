"""
Premium plan admin handlers.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from db.database import get_db
from db.crud import (
    create_premium_plan,
    get_premium_plan_by_id,
    get_all_premium_plans,
    update_premium_plan,
    delete_premium_plan,
)
from bot.keyboards.premium_plan import (
    get_admin_premium_plans_keyboard,
    get_premium_plan_list_keyboard,
    get_premium_plan_detail_keyboard,
)
from bot.handlers.admin import is_admin, PremiumPlanStates

router = Router()


@router.callback_query(F.data == "admin:premium_plans")
async def admin_premium_plans(callback: CallbackQuery):
    """Show premium plans management menu."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "💎 مدیریت پلن‌های پریمیوم\n\n"
        "از منوی زیر انتخاب کنید:",
        reply_markup=get_admin_premium_plans_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:premium_plan:create")
async def admin_premium_plan_create_start(callback: CallbackQuery, state: FSMContext):
    """Start creating a new premium plan."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "➕ ایجاد پلن پریمیوم جدید\n\n"
        "لطفاً نام پلن را ارسال کنید:\n"
        "مثال: 1 روز، 3 روز، 1 ماه"
    )
    await state.set_state(PremiumPlanStates.waiting_plan_name)
    await callback.answer()


@router.message(PremiumPlanStates.waiting_plan_name)
async def process_plan_name(message: Message, state: FSMContext):
    """Process plan name."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        await state.clear()
        return
    
    await state.update_data(plan_name=message.text)
    await message.answer(
        "✅ نام پلن ثبت شد.\n\n"
        "لطفاً مدت زمان پلن را به روز وارد کنید:\n"
        "مثال: 1، 3، 7، 30"
    )
    await state.set_state(PremiumPlanStates.waiting_duration_days)


@router.message(PremiumPlanStates.waiting_duration_days)
async def process_duration_days(message: Message, state: FSMContext):
    """Process duration days."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        await state.clear()
        return
    
    try:
        duration_days = int(message.text)
        if duration_days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ لطفاً یک عدد صحیح مثبت وارد کنید:")
        return
    
    await state.update_data(duration_days=duration_days)
    await message.answer(
        "✅ مدت زمان ثبت شد.\n\n"
        "لطفاً قیمت پلن را به تومان وارد کنید:\n"
        "مثال: 50000"
    )
    await state.set_state(PremiumPlanStates.waiting_price)


@router.message(PremiumPlanStates.waiting_price)
async def process_price(message: Message, state: FSMContext):
    """Process price."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        await state.clear()
        return
    
    try:
        price = float(message.text)
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ لطفاً یک عدد صحیح مثبت وارد کنید:")
        return
    
    await state.update_data(price=price)
    await message.answer(
        "✅ قیمت ثبت شد.\n\n"
        "آیا می‌خواهید تخفیف اضافه کنید؟\n"
        "اگر بله، قیمت اصلی (قبل از تخفیف) را وارد کنید، در غیر این صورت /skip بزنید:"
    )
    await state.set_state(PremiumPlanStates.waiting_original_price)


@router.message(PremiumPlanStates.waiting_original_price)
async def process_original_price(message: Message, state: FSMContext):
    """Process original price."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        await state.clear()
        return
    
    if message.text.lower() == "/skip":
        await state.update_data(original_price=None, discount_percent=0)
        await message.answer(
            "✅ بدون تخفیف.\n\n"
            "لطفاً تعداد استارز مورد نیاز برای این پلن را وارد کنید:\n"
            "مثال: 100، 500، 1000\n"
            "یا /skip بزنید اگر پرداخت با استارز نمی‌خواهید:"
        )
        await state.set_state(PremiumPlanStates.waiting_stars)
        return
    
    try:
        original_price = float(message.text)
        if original_price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ لطفاً یک عدد صحیح مثبت وارد کنید یا /skip بزنید:")
        return
    
    data = await state.get_data()
    price = data.get("price")
    discount_percent = int(((original_price - price) / original_price) * 100)
    
    await state.update_data(original_price=original_price, discount_percent=discount_percent)
    await message.answer(
        f"✅ قیمت اصلی ثبت شد.\n"
        f"تخفیف محاسبه شده: {discount_percent}%\n\n"
        f"لطفاً تعداد استارز مورد نیاز برای این پلن را وارد کنید:\n"
        f"مثال: 100، 500، 1000\n"
        f"یا /skip بزنید اگر پرداخت با استارز نمی‌خواهید:"
    )
    await state.set_state(PremiumPlanStates.waiting_stars)


@router.message(PremiumPlanStates.waiting_stars)
async def process_stars(message: Message, state: FSMContext):
    """Process stars required."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        await state.clear()
        return
    
    if message.text.lower() == "/skip":
        await state.update_data(stars_required=None)
        await message.answer(
            "✅ بدون پرداخت با استارز.\n\n"
            "روش‌های پرداخت را انتخاب کنید:\n"
            "1️⃣ فقط شاپرک\n"
            "2️⃣ فقط استارز\n"
            "3️⃣ هر دو (شاپرک و استارز)\n\n"
            "عدد 1، 2 یا 3 را ارسال کنید:"
        )
        await state.set_state(PremiumPlanStates.waiting_payment_methods)
        return
    
    try:
        stars_required = int(message.text)
        if stars_required <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ لطفاً یک عدد صحیح مثبت وارد کنید یا /skip بزنید:")
        return
    
    await state.update_data(stars_required=stars_required)
    await message.answer(
        f"✅ استارز ثبت شد: {stars_required} استارز\n\n"
        "روش‌های پرداخت را انتخاب کنید:\n"
        "1️⃣ فقط شاپرک\n"
        "2️⃣ فقط استارز\n"
        "3️⃣ هر دو (شاپرک و استارز)\n\n"
        "عدد 1، 2 یا 3 را ارسال کنید:"
    )
    await state.set_state(PremiumPlanStates.waiting_payment_methods)


@router.message(PremiumPlanStates.waiting_payment_methods)
async def process_payment_methods(message: Message, state: FSMContext):
    """Process payment methods."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        await state.clear()
        return
    
    import json
    
    payment_choice = message.text.strip()
    if payment_choice == "1":
        payment_methods = ["shaparak"]
    elif payment_choice == "2":
        payment_methods = ["stars"]
    elif payment_choice == "3":
        payment_methods = ["shaparak", "stars"]
    else:
        await message.answer("❌ لطفاً عدد 1، 2 یا 3 را ارسال کنید:")
        return
    
    await state.update_data(payment_methods_json=json.dumps(payment_methods))
    
    data = await state.get_data()
    stars_required = data.get("stars_required")
    
    if payment_methods == ["stars"] and not stars_required:
        await message.answer(
            "❌ برای پرداخت فقط با استارز، باید تعداد استارز را مشخص کنید.\n"
            "لطفاً تعداد استارز را وارد کنید:"
        )
        await state.set_state(PremiumPlanStates.waiting_stars)
        return
    
    await message.answer(
        f"✅ روش‌های پرداخت ثبت شد: {', '.join(payment_methods)}\n\n"
        f"آیا می‌خواهید دوره تخفیف محدود اضافه کنید؟\n"
        f"اگر بله، تاریخ شروع تخفیف را وارد کنید (YYYY-MM-DD HH:MM) یا /skip بزنید:"
    )
    await state.set_state(PremiumPlanStates.waiting_discount_start)


@router.message(PremiumPlanStates.waiting_discount_start)
async def process_discount_start(message: Message, state: FSMContext):
    """Process discount start date."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        await state.clear()
        return
    
    if message.text.lower() == "/skip":
        await state.update_data(discount_start_date=None, discount_end_date=None)
        await message.answer(
            "✅ بدون دوره تخفیف محدود.\n\n"
            "لطفاً ترتیب نمایش را وارد کنید (عدد کوچکتر = نمایش اول):\n"
            "مثال: 0، 1، 2"
        )
        await state.set_state(PremiumPlanStates.waiting_display_order)
        return
    
    try:
        from datetime import datetime
        if message.text.lower() == "now":
            discount_start_date = datetime.utcnow()
        else:
            discount_start_date = datetime.strptime(message.text, "%Y-%m-%d %H:%M")
    except ValueError:
        await message.answer("❌ فرمت تاریخ نامعتبر. لطفاً به صورت YYYY-MM-DD HH:MM وارد کنید یا /skip بزنید:")
        return
    
    await state.update_data(discount_start_date=discount_start_date)
    await message.answer(
        "✅ تاریخ شروع تخفیف ثبت شد.\n\n"
        "لطفاً تاریخ پایان تخفیف را وارد کنید (YYYY-MM-DD HH:MM):"
    )
    await state.set_state(PremiumPlanStates.waiting_discount_end)


@router.message(PremiumPlanStates.waiting_discount_end)
async def process_discount_end(message: Message, state: FSMContext):
    """Process discount end date."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        await state.clear()
        return
    
    try:
        from datetime import datetime
        discount_end_date = datetime.strptime(message.text, "%Y-%m-%d %H:%M")
    except ValueError:
        await message.answer("❌ فرمت تاریخ نامعتبر. لطفاً به صورت YYYY-MM-DD HH:MM وارد کنید:")
        return
    
    data = await state.get_data()
    discount_start_date = data.get("discount_start_date")
    if discount_start_date and discount_end_date <= discount_start_date:
        await message.answer("❌ تاریخ پایان باید بعد از تاریخ شروع باشد. لطفاً دوباره وارد کنید:")
        return
    
    await state.update_data(discount_end_date=discount_end_date)
    await message.answer(
        "✅ تاریخ پایان تخفیف ثبت شد.\n\n"
        "لطفاً ترتیب نمایش را وارد کنید (عدد کوچکتر = نمایش اول):\n"
        "مثال: 0، 1، 2"
    )
    await state.set_state(PremiumPlanStates.waiting_display_order)


@router.message(PremiumPlanStates.waiting_display_order)
async def process_display_order(message: Message, state: FSMContext):
    """Process display order and create plan."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        await state.clear()
        return
    
    try:
        display_order = int(message.text)
    except ValueError:
        await message.answer("❌ لطفاً یک عدد صحیح وارد کنید:")
        return
    
    data = await state.get_data()
    
    async for db_session in get_db():
        plan = await create_premium_plan(
            db_session,
            plan_name=data.get("plan_name"),
            duration_days=data.get("duration_days"),
            price=data.get("price"),
            original_price=data.get("original_price"),
            discount_percent=data.get("discount_percent", 0),
            stars_required=data.get("stars_required"),
            payment_methods_json=data.get("payment_methods_json", '["shaparak"]'),
            discount_start_date=data.get("discount_start_date"),
            discount_end_date=data.get("discount_end_date"),
            features_json=None,
            is_active=True,
            is_visible=True,
            display_order=display_order
        )
        
        if plan:
            await message.answer(
                f"✅ پلن پریمیوم «{plan.plan_name}» با موفقیت ایجاد شد!\n\n"
                f"📌 مدت زمان: {plan.duration_days} روز\n"
                f"💰 قیمت: {int(plan.price):,} تومان\n"
                f"🎯 ترتیب نمایش: {plan.display_order}"
            )
        else:
            await message.answer("❌ خطا در ایجاد پلن.")
        
        await state.clear()
        break


@router.callback_query(F.data == "admin:premium_plan:list")
async def admin_premium_plan_list(callback: CallbackQuery):
    """Show premium plans list."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    async for db_session in get_db():
        plans = await get_all_premium_plans(db_session, active_only=False, visible_only=False)
        
        if not plans:
            await callback.message.edit_text(
                "📋 لیست پلن‌های پریمیوم\n\n"
                "📭 هنوز پلنی ایجاد نشده است.",
                reply_markup=get_admin_premium_plans_keyboard()
            )
            await callback.answer()
            return
        
        # Pagination
        page = 0
        total_pages = (len(plans) + 4) // 5
        
        await callback.message.edit_text(
            "📋 لیست پلن‌های پریمیوم\n\n"
            "پلن مورد نظر را انتخاب کنید:",
            reply_markup=get_premium_plan_list_keyboard(plans, page, total_pages)
        )
        await callback.answer()
        break


@router.callback_query(F.data.startswith("admin:premium_plan:list:"))
async def admin_premium_plan_list_page(callback: CallbackQuery):
    """Show premium plans list with pagination."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    try:
        page = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer("❌ خطا", show_alert=True)
        return
    
    async for db_session in get_db():
        plans = await get_all_premium_plans(db_session, active_only=False, visible_only=False)
        
        total_pages = (len(plans) + 4) // 5 if plans else 1
        
        await callback.message.edit_text(
            "📋 لیست پلن‌های پریمیوم\n\n"
            "پلن مورد نظر را انتخاب کنید:",
            reply_markup=get_premium_plan_list_keyboard(plans, page, total_pages)
        )
        await callback.answer()
        break


@router.callback_query(F.data.startswith("admin:premium_plan:view:"))
async def admin_premium_plan_view(callback: CallbackQuery):
    """View premium plan details."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    try:
        plan_id = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer("❌ خطا", show_alert=True)
        return
    
    async for db_session in get_db():
        plan = await get_premium_plan_by_id(db_session, plan_id)
        if not plan:
            await callback.answer("❌ پلن یافت نشد.", show_alert=True)
            return
        
        status = "✅ فعال" if plan.is_active else "❌ غیرفعال"
        visibility = "👁️ قابل مشاهده" if plan.is_visible else "🙈 مخفی"
        
        text = f"💎 جزئیات پلن پریمیوم\n\n"
        text += f"📌 نام: {plan.plan_name}\n"
        text += f"⏰ مدت زمان: {plan.duration_days} روز\n"
        text += f"💰 قیمت: {int(plan.price):,} تومان\n"
        
        if plan.original_price:
            text += f"💰 قیمت اصلی: {int(plan.original_price):,} تومان\n"
            text += f"🎯 تخفیف: {plan.discount_percent}%\n"
        
        if plan.discount_start_date and plan.discount_end_date:
            from datetime import datetime
            now = datetime.utcnow()
            if plan.discount_start_date <= now <= plan.discount_end_date:
                text += f"🔥 تخفیف فعال تا: {plan.discount_end_date.strftime('%Y-%m-%d %H:%M')}\n"
            else:
                text += f"⏰ دوره تخفیف: {plan.discount_start_date.strftime('%Y-%m-%d %H:%M')} تا {plan.discount_end_date.strftime('%Y-%m-%d %H:%M')}\n"
        
        text += f"📊 وضعیت: {status} | {visibility}\n"
        text += f"🎯 ترتیب نمایش: {plan.display_order}\n"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_premium_plan_detail_keyboard(plan_id)
        )
        await callback.answer()
        break


@router.callback_query(F.data.startswith("admin:premium_plan:delete:"))
async def admin_premium_plan_delete(callback: CallbackQuery):
    """Delete a premium plan."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    try:
        plan_id = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer("❌ خطا", show_alert=True)
        return
    
    async for db_session in get_db():
        plan = await get_premium_plan_by_id(db_session, plan_id)
        if not plan:
            await callback.answer("❌ پلن یافت نشد.", show_alert=True)
            return
        
        success = await delete_premium_plan(db_session, plan_id)
        
        if success:
            await callback.answer(f"✅ پلن «{plan.plan_name}» حذف شد.", show_alert=True)
            await admin_premium_plan_list(callback)
        else:
            await callback.answer("❌ خطا در حذف پلن.", show_alert=True)
        break


@router.callback_query(F.data.startswith("admin:premium_plan:toggle:"))
async def admin_premium_plan_toggle(callback: CallbackQuery):
    """Toggle premium plan active status."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    try:
        plan_id = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer("❌ خطا", show_alert=True)
        return
    
    async for db_session in get_db():
        plan = await get_premium_plan_by_id(db_session, plan_id)
        if not plan:
            await callback.answer("❌ پلن یافت نشد.", show_alert=True)
            return
        
        new_status = not plan.is_active
        await update_premium_plan(db_session, plan_id, is_active=new_status)
        
        status_text = "فعال" if new_status else "غیرفعال"
        await callback.answer(f"✅ پلن «{plan.plan_name}» {status_text} شد.", show_alert=True)
        await admin_premium_plan_view(callback)
        break

