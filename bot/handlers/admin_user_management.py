"""
Admin user management handlers.
Handles ban, unban, and edit profile actions for admins.
"""
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from db.database import get_db
from db.crud import (
    get_user_by_id,
    ban_user,
    unban_user,
    update_user_profile,
)
from bot.keyboards.admin import (
    get_admin_user_management_keyboard,
    get_admin_edit_profile_keyboard,
)
from config.settings import settings
from bot.handlers.admin import is_admin
from bot.handlers.admin import EditUserProfileStates

router = Router()


@router.callback_query(F.data.startswith("admin:user:ban:"))
async def admin_ban_user(callback: CallbackQuery, state: FSMContext):
    """Ban a user with confirmation."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    user_id = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        target_user = await get_user_by_id(db_session, user_id)
        if not target_user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        if target_user.is_banned:
            await callback.answer("⚠️ این کاربر قبلاً بن شده است.", show_alert=True)
            return
        
        # Store user_id and ask for admin message
        await state.update_data(ban_user_id=user_id)
        message_text = (
            f"🚫 بن کردن کاربر\n\n"
            f"👤 کاربر: {target_user.display_name or target_user.username or 'بدون نام'}\n"
            f"🆔 ID: {target_user.id}\n\n"
            f"⚠️ آیا مطمئن هستید که می‌خواهید این کاربر را بن کنید؟\n\n"
            f"لطفاً پیام ادمین را برای ارسال به کاربر وارد کنید (یا /skip برای رد کردن):"
        )
        
        # Check if message has photo, if so use edit_caption, otherwise edit_text
        try:
            if callback.message.photo:
                await callback.message.edit_caption(caption=message_text)
            else:
                await callback.message.edit_text(message_text)
        except Exception:
            await callback.message.answer(message_text)
        await state.set_state(EditUserProfileStates.waiting_admin_message)
        await callback.answer()
        break


@router.callback_query(F.data.startswith("admin:user:unban:"))
async def admin_unban_user(callback: CallbackQuery):
    """Unban a user."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    user_id = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        target_user = await get_user_by_id(db_session, user_id)
        if not target_user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        if not target_user.is_banned:
            await callback.answer("⚠️ این کاربر بن نشده است.", show_alert=True)
            return
        
        # Unban user
        success = await unban_user(db_session, user_id)
        
        if success:
            await callback.message.edit_text(
                f"✅ کاربر آنبن شد\n\n"
                f"👤 کاربر: {target_user.display_name or target_user.username or 'بدون نام'}\n"
                f"🆔 ID: {target_user.id}",
                reply_markup=get_admin_user_management_keyboard(user_id, is_banned=False)
            )
            await callback.answer("✅ کاربر آنبن شد")
        else:
            await callback.answer("❌ خطا در آنبن کردن کاربر.", show_alert=True)
        break


@router.callback_query(F.data.startswith("admin:user:edit:"))
async def admin_edit_user_profile(callback: CallbackQuery):
    """Show edit profile menu for user."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    user_id = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        target_user = await get_user_by_id(db_session, user_id)
        if not target_user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        from utils.validators import get_display_name
        
        gender_map = {"male": "پسر 🧑", "female": "دختر 👩", "other": "سایر"}
        gender_text = gender_map.get(target_user.gender, target_user.gender or "تعیین نشده")
        
        has_photo = bool(target_user.profile_image_url)
        photo_status = "✅ دارد" if has_photo else "❌ ندارد"
        
        profile_text = (
            f"✏️ ویرایش پروفایل کاربر\n\n"
            f"👤 نام: {get_display_name(target_user)}\n"
            f"⚧️ جنسیت: {gender_text}\n"
            f"🎂 سن: {target_user.age or 'تعیین نشده'}\n"
            f"📍 استان: {target_user.province or 'تعیین نشده'}\n"
            f"🏙️ شهر: {target_user.city or 'تعیین نشده'}\n"
            f"📷 عکس پروفایل: {photo_status}\n\n"
            f"لطفاً فیلد مورد نظر را انتخاب کنید:"
        )
        
        # Check if message has photo, if so use edit_caption, otherwise edit_text
        try:
            if callback.message.photo:
                await callback.message.edit_caption(
                    caption=profile_text,
                    reply_markup=get_admin_edit_profile_keyboard(user_id, has_photo=has_photo)
                )
            else:
                await callback.message.edit_text(
                    profile_text,
                    reply_markup=get_admin_edit_profile_keyboard(user_id, has_photo=has_photo)
                )
        except Exception:
            # If edit fails, send new message
            await callback.message.answer(
                profile_text,
                reply_markup=get_admin_edit_profile_keyboard(user_id, has_photo=has_photo)
            )
        await callback.answer()
        break


@router.callback_query(F.data.startswith("admin:user:edit_field:"))
async def admin_edit_user_field(callback: CallbackQuery, state: FSMContext):
    """Start editing a specific user field."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    # Parse: admin:user:edit_field:user_id:field_name
    parts = callback.data.split(":")
    user_id = int(parts[3])
    field_name = parts[4]
    
    field_names = {
        "display_name": "نام",
        "gender": "جنسیت",
        "age": "سن",
        "province": "استان",
        "city": "شهر"
    }
    
    field_display = field_names.get(field_name, field_name)
    
    async for db_session in get_db():
        target_user = await get_user_by_id(db_session, user_id)
        if not target_user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Get current value
        current_value = getattr(target_user, field_name, None) or "تعیین نشده"
        
        # Store in state
        await state.update_data(
            edit_user_id=user_id,
            edit_field=field_name
        )
        
        # Prepare message text based on field
        if field_name == "gender":
            message_text = (
                f"✏️ ویرایش {field_display}\n\n"
                f"مقدار فعلی: {current_value}\n\n"
                f"لطفاً جنسیت را انتخاب کنید:\n"
                f"• male (پسر)\n"
                f"• female (دختر)\n"
                f"• other (سایر)"
            )
        elif field_name == "age":
            message_text = (
                f"✏️ ویرایش {field_display}\n\n"
                f"مقدار فعلی: {current_value}\n\n"
                f"لطفاً سن را وارد کنید (عدد):"
            )
        else:
            message_text = (
                f"✏️ ویرایش {field_display}\n\n"
                f"مقدار فعلی: {current_value}\n\n"
                f"لطفاً مقدار جدید را وارد کنید:"
            )
        
        # Check if message has photo, if so use edit_caption, otherwise edit_text
        try:
            if callback.message.photo:
                await callback.message.edit_caption(
                    caption=message_text
                )
            else:
                await callback.message.edit_text(message_text)
        except Exception:
            # If edit fails, send new message
            await callback.message.answer(message_text)
        
        await state.set_state(EditUserProfileStates.waiting_field_value)
        await callback.answer()
        break


@router.message(EditUserProfileStates.waiting_field_value)
async def process_edit_user_field(message: Message, state: FSMContext):
    """Process edited user field value."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        await state.clear()
        return
    
    data = await state.get_data()
    user_id = data.get("edit_user_id")
    field_name = data.get("edit_field")
    
    if not user_id or not field_name:
        await message.answer("❌ خطا در دریافت اطلاعات.")
        await state.clear()
        return
    
    value = message.text.strip()
    
    async for db_session in get_db():
        target_user = await get_user_by_id(db_session, user_id)
        if not target_user:
            await message.answer("❌ کاربر یافت نشد.")
            await state.clear()
            return
        
        # Validate and update field
        update_data = {}
        
        if field_name == "display_name":
            update_data["display_name"] = value
        elif field_name == "gender":
            if value.lower() not in ["male", "female", "other"]:
                await message.answer("❌ جنسیت باید یکی از این موارد باشد: male, female, other")
                return
            update_data["gender"] = value.lower()
        elif field_name == "age":
            try:
                age = int(value)
                if age < 1 or age > 150:
                    await message.answer("❌ سن باید بین 1 تا 150 باشد.")
                    return
                update_data["age"] = age
            except ValueError:
                await message.answer("❌ لطفاً یک عدد معتبر وارد کنید.")
                return
        elif field_name == "province":
            update_data["province"] = value
        elif field_name == "city":
            update_data["city"] = value
        
        # Update user profile
        updated_user = await update_user_profile(
            db_session,
            target_user.telegram_id,
            **update_data
        )
        
        if updated_user:
            # Ask for admin message
            await state.update_data(edited_user_id=user_id)
            await message.answer(
                f"✅ پروفایل کاربر به‌روزرسانی شد!\n\n"
                f"لطفاً پیام ادمین را برای ارسال به کاربر وارد کنید (یا /skip برای رد کردن):"
            )
            await state.set_state(EditUserProfileStates.waiting_admin_message)
        else:
            await message.answer("❌ خطا در به‌روزرسانی پروفایل.")
            await state.clear()
        break


@router.message(EditUserProfileStates.waiting_admin_message)
async def process_admin_message_after_action(message: Message, state: FSMContext):
    """Process admin message after ban or edit."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        await state.clear()
        return
    
    data = await state.get_data()
    user_id = data.get("ban_user_id") or data.get("edited_user_id")
    action = "ban" if data.get("ban_user_id") else "edit"
    
    if not user_id:
        await message.answer("❌ خطا در دریافت اطلاعات.")
        await state.clear()
        return
    
    message_text = message.text.strip()
    skip_message = message_text.lower() == "/skip" or message_text.lower() == "skip"
    
    async for db_session in get_db():
        target_user = await get_user_by_id(db_session, user_id)
        if not target_user:
            await message.answer("❌ کاربر یافت نشد.")
            await state.clear()
            return
        
        # Perform action
        if action == "ban":
            success = await ban_user(db_session, user_id)
            if not success:
                await message.answer("❌ خطا در بن کردن کاربر.")
                await state.clear()
                return
        else:
            # Edit was already done, just send message
            success = True
        
        # Send admin message to user if provided
        if not skip_message and message_text:
            bot = Bot(token=settings.BOT_TOKEN)
            try:
                await bot.send_message(
                    target_user.telegram_id,
                    f"📢 پیام از ادمین:\n\n{message_text}"
                )
                await bot.session.close()
            except Exception as e:
                # User might have blocked bot, continue anyway
                pass
        
        # Send confirmation
        action_text = "بن شد" if action == "ban" else "ویرایش شد"
        message_status = "و پیام ادمین ارسال شد" if not skip_message and message_text else ""
        
        await message.answer(
            f"✅ کاربر {action_text}{message_status}!\n\n"
            f"👤 کاربر: {target_user.display_name or target_user.username or 'بدون نام'}\n"
            f"🆔 ID: {target_user.id}",
            reply_markup=get_admin_user_management_keyboard(
                user_id, 
                is_banned=(action == "ban" or target_user.is_banned)
            )
        )
        
        await state.clear()
        break


@router.callback_query(F.data.startswith("admin:user:view:"))
async def admin_view_user(callback: CallbackQuery):
    """View user profile from admin menu."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    user_id = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        target_user = await get_user_by_id(db_session, user_id)
        if not target_user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        from utils.validators import get_display_name
        
        gender_map = {"male": "پسر 🧑", "female": "دختر 👩", "other": "سایر"}
        gender_text = gender_map.get(target_user.gender, target_user.gender or "تعیین نشده")
        
        profile_text = (
            f"👤 پروفایل کاربر\n\n"
            f"• نام: {get_display_name(target_user)}\n"
            f"• جنسیت: {gender_text}\n"
            f"• استان: {target_user.province or 'تعیین نشده'}\n"
            f"• شهر: {target_user.city or 'تعیین نشده'}\n"
            f"• سن: {target_user.age or 'تعیین نشده'}\n"
            f"• وضعیت: {'🚫 بن شده' if target_user.is_banned else '✅ فعال'}\n"
            f"🆔 ID: /user_{target_user.profile_id or 'N/A'}"
        )
        
        await callback.message.edit_text(
            profile_text,
            reply_markup=get_admin_user_management_keyboard(
                user_id, 
                is_banned=target_user.is_banned or False
            )
        )
        await callback.answer()
        break


@router.callback_query(F.data.startswith("admin:user:delete_photo:"))
async def admin_delete_user_photo(callback: CallbackQuery, state: FSMContext):
    """Delete user profile photo."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    user_id = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        target_user = await get_user_by_id(db_session, user_id)
        if not target_user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        if not target_user.profile_image_url:
            await callback.answer("⚠️ این کاربر عکس پروفایلی ندارد.", show_alert=True)
            return
        
        # Delete photo by setting profile_image_url to None directly
        target_user.profile_image_url = None
        target_user.updated_at = datetime.utcnow()
        await db_session.commit()
        await db_session.refresh(target_user)
        
        if target_user:
            # Ask for admin message
            await state.update_data(edited_user_id=user_id)
            message_text = (
                f"✅ عکس پروفایل کاربر حذف شد!\n\n"
                f"لطفاً پیام ادمین را برای ارسال به کاربر وارد کنید (یا /skip برای رد کردن):"
            )
            
            # Check if message has photo, if so use edit_caption, otherwise edit_text
            try:
                if callback.message.photo:
                    await callback.message.edit_caption(caption=message_text)
                else:
                    await callback.message.edit_text(message_text)
            except Exception:
                await callback.message.answer(message_text)
            
            await state.set_state(EditUserProfileStates.waiting_admin_message)
            await callback.answer("✅ عکس حذف شد")
        else:
            await callback.answer("❌ خطا در حذف عکس.", show_alert=True)
        break

