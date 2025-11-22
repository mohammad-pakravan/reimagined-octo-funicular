"""
Coin package admin handlers.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from db.database import get_db
from db.crud import (
    create_coin_package,
    get_coin_package_by_id,
    get_all_coin_packages,
    update_coin_package,
    delete_coin_package,
)
from bot.keyboards.coin_package import (
    get_admin_coin_packages_keyboard,
    get_coin_package_list_keyboard,
    get_coin_package_detail_keyboard,
)
from bot.handlers.admin import is_admin, CoinPackageStates

router = Router()


@router.callback_query(F.data == "admin:coin_packages")
async def admin_coin_packages(callback: CallbackQuery):
    """Show coin packages management menu."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "💰 مدیریت پکیج‌های سکه\n\n"
        "از منوی زیر انتخاب کنید:",
        reply_markup=get_admin_coin_packages_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:coin_package:create")
async def admin_coin_package_create_start(callback: CallbackQuery, state: FSMContext):
    """Start creating a new coin package."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    await state.set_state(CoinPackageStates.waiting_package_name)
    await callback.message.edit_text(
        "💰 ایجاد پکیج سکه جدید\n\n"
        "نام پکیج را وارد کنید (مثال: 100 سکه):",
        reply_markup=None
    )
    await callback.answer()


@router.message(CoinPackageStates.waiting_package_name)
async def admin_coin_package_create_name(message: Message, state: FSMContext):
    """Receive package name."""
    if not is_admin(message.from_user.id):
        return
    
    package_name = message.text.strip()
    
    if not package_name:
        await message.answer("❌ نام پکیج نمی‌تواند خالی باشد. دوباره وارد کنید:")
        return
    
    await state.update_data(package_name=package_name)
    await state.set_state(CoinPackageStates.waiting_coin_amount)
    await message.answer(
        f"✅ نام پکیج: {package_name}\n\n"
        "تعداد سکه‌ها را وارد کنید (عدد):"
    )


@router.message(CoinPackageStates.waiting_coin_amount)
async def admin_coin_package_create_coin_amount(message: Message, state: FSMContext):
    """Receive coin amount."""
    if not is_admin(message.from_user.id):
        return
    
    try:
        coin_amount = int(message.text.strip())
        if coin_amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ تعداد سکه باید یک عدد مثبت باشد. دوباره وارد کنید:")
        return
    
    await state.update_data(coin_amount=coin_amount)
    await state.set_state(CoinPackageStates.waiting_price)
    await message.answer(
        f"✅ تعداد سکه: {coin_amount}\n\n"
        "قیمت را به تومان وارد کنید (عدد):"
    )


@router.message(CoinPackageStates.waiting_price)
async def admin_coin_package_create_price(message: Message, state: FSMContext):
    """Receive price."""
    if not is_admin(message.from_user.id):
        return
    
    try:
        price = float(message.text.strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ قیمت باید یک عدد مثبت باشد. دوباره وارد کنید:")
        return
    
    await state.update_data(price=price)
    await state.set_state(CoinPackageStates.waiting_stars)
    await message.answer(
        f"✅ قیمت: {int(price):,} تومان\n\n"
        "تعداد استارز مورد نیاز را وارد کنید (عدد یا 0 برای غیرفعال):"
    )


@router.message(CoinPackageStates.waiting_stars)
async def admin_coin_package_create_stars(message: Message, state: FSMContext):
    """Receive stars amount."""
    if not is_admin(message.from_user.id):
        return
    
    try:
        stars = int(message.text.strip())
        if stars < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ تعداد استارز باید یک عدد صفر یا مثبت باشد. دوباره وارد کنید:")
        return
    
    stars_required = stars if stars > 0 else None
    
    # Create package
    data = await state.get_data()
    
    async for db_session in get_db():
        # Determine payment methods based on stars
        import json
        payment_methods = []
        if stars_required:
            payment_methods.append("stars")
        payment_methods.append("shaparak")
        payment_methods_json = json.dumps(payment_methods)
        
        package = await create_coin_package(
            db_session,
            package_name=data['package_name'],
            coin_amount=data['coin_amount'],
            price=data['price'],
            stars_required=stars_required,
            payment_methods_json=payment_methods_json,
            is_active=True,
            is_visible=True
        )
        
        await state.clear()
        
        stars_text = f"{stars_required} ⭐" if stars_required else "ندارد"
        await message.answer(
            f"✅ پکیج سکه جدید ایجاد شد!\n\n"
            f"💰 نام: {package.package_name}\n"
            f"🪙 تعداد سکه: {package.coin_amount}\n"
            f"💵 قیمت: {int(package.price):,} تومان\n"
            f"⭐ استارز: {stars_text}\n\n"
            f"ID: {package.id}"
        )
        break


@router.callback_query(F.data == "admin:coin_package:list")
async def admin_coin_package_list(callback: CallbackQuery):
    """Show list of coin packages."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    async for db_session in get_db():
        packages = await get_all_coin_packages(db_session)
        
        if not packages:
            await callback.message.edit_text(
                "📦 هیچ پکیج سکه‌ای وجود ندارد.\n\n"
                "برای ایجاد پکیج جدید از منوی قبل استفاده کنید.",
                reply_markup=get_admin_coin_packages_keyboard()
            )
        else:
            text = "💰 لیست پکیج‌های سکه:\n\n"
            for pkg in packages:
                status = "✅" if pkg.is_active else "❌"
                visible = "👁" if pkg.is_visible else "🚫"
                stars_text = f" | ⭐{pkg.stars_required}" if pkg.stars_required else ""
                text += f"{status}{visible} {pkg.package_name} - {pkg.coin_amount} سکه - {int(pkg.price):,} تومان{stars_text}\n"
            
            text += "\n\nبرای مشاهده جزئیات یک پکیج، روی آن کلیک کنید:"
            
            await callback.message.edit_text(
                text,
                reply_markup=get_coin_package_list_keyboard(packages)
            )
        
        await callback.answer()
        break


@router.callback_query(F.data.startswith("admin:coin_package:view:"))
async def admin_coin_package_view(callback: CallbackQuery):
    """View coin package details."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    try:
        package_id = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer("❌ خطا", show_alert=True)
        return
    
    async for db_session in get_db():
        package = await get_coin_package_by_id(db_session, package_id)
        
        if not package:
            await callback.answer("❌ پکیج یافت نشد.", show_alert=True)
            return
        
        # Parse payment methods
        import json
        try:
            payment_methods = json.loads(package.payment_methods_json) if package.payment_methods_json else []
        except (json.JSONDecodeError, TypeError):
            payment_methods = []
        
        payment_text = ", ".join([
            "استارز" if m == "stars" else "شاپرک" if m == "shaparak" else m
            for m in payment_methods
        ]) if payment_methods else "تعریف نشده"
        
        status_text = "فعال ✅" if package.is_active else "غیرفعال ❌"
        visible_text = "نمایش داده می‌شود 👁" if package.is_visible else "مخفی 🚫"
        stars_text = f"{package.stars_required} ⭐" if package.stars_required else "ندارد"
        
        discount_text = ""
        if package.discount_percent > 0:
            discount_text = f"\n🔥 تخفیف: {package.discount_percent}%"
            if package.original_price:
                discount_text += f"\n💵 قیمت اصلی: {int(package.original_price):,} تومان"
        
        text = (
            f"💰 جزئیات پکیج سکه\n\n"
            f"🆔 ID: {package.id}\n"
            f"📦 نام: {package.package_name}\n"
            f"🪙 تعداد سکه: {package.coin_amount}\n"
            f"💵 قیمت: {int(package.price):,} تومان{discount_text}\n"
            f"⭐ استارز: {stars_text}\n"
            f"💳 روش‌های پرداخت: {payment_text}\n"
            f"📊 وضعیت: {status_text}\n"
            f"👁 نمایش: {visible_text}\n"
            f"🔢 ترتیب نمایش: {package.display_order}\n"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_coin_package_detail_keyboard(package)
        )
        await callback.answer()
        break


@router.callback_query(F.data.startswith("admin:coin_package:delete:"))
async def admin_coin_package_delete(callback: CallbackQuery):
    """Delete a coin package."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    try:
        package_id = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer("❌ خطا", show_alert=True)
        return
    
    async for db_session in get_db():
        package = await get_coin_package_by_id(db_session, package_id)
        if not package:
            await callback.answer("❌ پکیج یافت نشد.", show_alert=True)
            return
        
        package_name = package.package_name
        success = await delete_coin_package(db_session, package_id)
        
        if success:
            await callback.answer(f"✅ پکیج «{package_name}» حذف شد.", show_alert=True)
            # Redirect to list
            await admin_coin_package_list(callback)
        else:
            await callback.answer("❌ خطا در حذف پکیج.", show_alert=True)
        break


@router.callback_query(F.data.startswith("admin:coin_package:toggle:"))
async def admin_coin_package_toggle(callback: CallbackQuery):
    """Toggle coin package active status."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    try:
        package_id = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer("❌ خطا", show_alert=True)
        return
    
    async for db_session in get_db():
        package = await get_coin_package_by_id(db_session, package_id)
        if not package:
            await callback.answer("❌ پکیج یافت نشد.", show_alert=True)
            return
        
        new_status = not package.is_active
        await update_coin_package(db_session, package_id, is_active=new_status)
        
        status_text = "فعال" if new_status else "غیرفعال"
        await callback.answer(f"✅ پکیج «{package.package_name}» {status_text} شد.", show_alert=True)
        await admin_coin_package_view(callback)
        break


@router.callback_query(F.data.startswith("admin:coin_package:toggle_visibility:"))
async def admin_coin_package_toggle_visibility(callback: CallbackQuery):
    """Toggle coin package visibility."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    try:
        package_id = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer("❌ خطا", show_alert=True)
        return
    
    async for db_session in get_db():
        package = await get_coin_package_by_id(db_session, package_id)
        if not package:
            await callback.answer("❌ پکیج یافت نشد.", show_alert=True)
            return
        
        new_visibility = not package.is_visible
        await update_coin_package(db_session, package_id, is_visible=new_visibility)
        
        visibility_text = "نمایش داده می‌شود" if new_visibility else "مخفی شد"
        await callback.answer(f"✅ پکیج «{package.package_name}» {visibility_text}.", show_alert=True)
        await admin_coin_package_view(callback)
        break

