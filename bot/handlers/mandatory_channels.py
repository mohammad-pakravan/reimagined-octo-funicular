"""
Mandatory channels management handlers.
Handles admin commands for managing mandatory channels.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db.database import get_db
from db.crud import (
    get_user_by_telegram_id,
    create_mandatory_channel,
    get_all_mandatory_channels,
    get_mandatory_channel_by_id,
    update_mandatory_channel,
    delete_mandatory_channel,
)
from bot.keyboards.admin import (
    get_mandatory_channels_keyboard,
    get_mandatory_channel_list_keyboard,
    get_mandatory_channel_detail_keyboard,
)
from config.settings import settings

router = Router()


def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    return user_id in settings.ADMIN_IDS


class MandatoryChannelStates(StatesGroup):
    """FSM states for mandatory channel management."""
    waiting_channel_id = State()
    waiting_channel_name = State()
    waiting_channel_link = State()
    waiting_order_index = State()


@router.message(F.text == "📺 مدیریت چنل‌های اجباری")
async def cmd_mandatory_channels(message: Message):
    """Show mandatory channels management menu."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Access denied.")
        return
    
    await message.answer(
        "📺 مدیریت چنل‌های اجباری\n\n"
        "از این بخش می‌توانید چنل‌های اجباری را مدیریت کنید.\n"
        "کاربران باید به همه چنل‌های فعال عضو باشند.",
        reply_markup=get_mandatory_channels_keyboard()
    )


@router.callback_query(F.data == "admin:mandatory_channels")
async def callback_mandatory_channels(callback: CallbackQuery):
    """Show mandatory channels management menu."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Access denied.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📺 مدیریت چنل‌های اجباری\n\n"
        "از این بخش می‌توانید چنل‌های اجباری را مدیریت کنید.\n"
        "کاربران باید به همه چنل‌های فعال عضو باشند.",
        reply_markup=get_mandatory_channels_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:mandatory_channel:add")
async def callback_add_mandatory_channel(callback: CallbackQuery, state: FSMContext):
    """Start adding a new mandatory channel."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Access denied.", show_alert=True)
        return
    
    await state.set_state(MandatoryChannelStates.waiting_channel_id)
    await callback.message.edit_text(
        "➕ اضافه کردن چنل اجباری\n\n"
        "لطفاً ID یا username چنل را ارسال کنید:\n"
        "مثال: @channel یا -1001234567890"
    )
    await callback.answer()


@router.message(MandatoryChannelStates.waiting_channel_id)
async def process_channel_id(message: Message, state: FSMContext):
    """Process channel ID and ask for channel name."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Access denied.")
        return
    
    channel_id = message.text.strip()
    await state.update_data(channel_id=channel_id)
    await state.set_state(MandatoryChannelStates.waiting_channel_name)
    
    await message.answer(
        "📝 لطفاً نام نمایشی چنل را ارسال کنید:\n"
        "(اختیاری - می‌توانید /skip بزنید)"
    )


@router.message(MandatoryChannelStates.waiting_channel_name)
async def process_channel_name(message: Message, state: FSMContext):
    """Process channel name and ask for channel link."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Access denied.")
        return
    
    channel_name = message.text.strip() if message.text.strip() != "/skip" else None
    await state.update_data(channel_name=channel_name)
    await state.set_state(MandatoryChannelStates.waiting_channel_link)
    
    await message.answer(
        "🔗 لطفاً لینک کامل چنل را ارسال کنید:\n"
        "مثال: https://t.me/channel\n"
        "(اختیاری - می‌توانید /skip بزنید)"
    )


@router.message(MandatoryChannelStates.waiting_channel_link)
async def process_channel_link(message: Message, state: FSMContext):
    """Process channel link and create channel."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Access denied.")
        return
    
    channel_link = message.text.strip() if message.text.strip() != "/skip" else None
    data = await state.get_data()
    
    async for db_session in get_db():
        # Get admin user ID
        admin_user = await get_user_by_telegram_id(db_session, message.from_user.id)
        admin_user_id = admin_user.id if admin_user else None
        
        # Get max order_index
        all_channels = await get_all_mandatory_channels(db_session)
        max_order = max([ch.order_index for ch in all_channels], default=-1)
        
        # Create channel
        channel = await create_mandatory_channel(
            db_session,
            channel_id=data['channel_id'],
            channel_name=data.get('channel_name'),
            channel_link=channel_link,
            is_active=True,
            order_index=max_order + 1,
            created_by_admin_id=admin_user_id
        )
        
        await message.answer(
            f"✅ چنل اجباری با موفقیت اضافه شد!\n\n"
            f"📺 ID: {channel.channel_id}\n"
            f"📝 نام: {channel.channel_name or 'بدون نام'}\n"
            f"🔗 لینک: {channel.channel_link or 'بدون لینک'}\n"
            f"✅ وضعیت: فعال",
            reply_markup=get_mandatory_channels_keyboard()
        )
        break
    
    await state.clear()


@router.callback_query(F.data.startswith("admin:mandatory_channel:list:"))
async def callback_mandatory_channel_list(callback: CallbackQuery):
    """Show list of mandatory channels."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Access denied.", show_alert=True)
        return
    
    page = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        channels = await get_all_mandatory_channels(db_session)
        break
    
    if not channels:
        await callback.message.edit_text(
            "📋 لیست چنل‌های اجباری\n\n"
            "❌ هیچ چنل اجباری ثبت نشده است.",
            reply_markup=get_mandatory_channels_keyboard()
        )
        await callback.answer()
        return
    
    channels_text = "📋 لیست چنل‌های اجباری:\n\n"
    start_idx = page * 10
    end_idx = start_idx + 10
    channels_page = channels[start_idx:end_idx]
    
    for idx, channel in enumerate(channels_page, start=start_idx + 1):
        status = "✅" if channel.is_active else "❌"
        channel_name = channel.channel_name or channel.channel_id
        channels_text += f"{idx}. {status} {channel_name}\n"
    
    await callback.message.edit_text(
        channels_text,
        reply_markup=get_mandatory_channel_list_keyboard(channels, page)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:mandatory_channel:detail:"))
async def callback_mandatory_channel_detail(callback: CallbackQuery):
    """Show mandatory channel detail."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Access denied.", show_alert=True)
        return
    
    channel_id = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        channel = await get_mandatory_channel_by_id(db_session, channel_id)
        break
    
    if not channel:
        await callback.answer("❌ چنل یافت نشد.", show_alert=True)
        return
    
    status = "✅ فعال" if channel.is_active else "❌ غیرفعال"
    await callback.message.edit_text(
        f"📺 جزئیات چنل اجباری\n\n"
        f"🆔 ID: {channel.channel_id}\n"
        f"📝 نام: {channel.channel_name or 'بدون نام'}\n"
        f"🔗 لینک: {channel.channel_link or 'بدون لینک'}\n"
        f"📊 ترتیب: {channel.order_index}\n"
        f"✅ وضعیت: {status}\n"
        f"📅 ایجاد شده: {channel.created_at.strftime('%Y-%m-%d %H:%M')}",
        reply_markup=get_mandatory_channel_detail_keyboard(channel_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:mandatory_channel:toggle:"))
async def callback_toggle_mandatory_channel(callback: CallbackQuery):
    """Toggle mandatory channel active status."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Access denied.", show_alert=True)
        return
    
    channel_id = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        channel = await get_mandatory_channel_by_id(db_session, channel_id)
        if not channel:
            await callback.answer("❌ چنل یافت نشد.", show_alert=True)
            return
        
        new_status = not channel.is_active
        await update_mandatory_channel(db_session, channel_id, is_active=new_status)
        
        status_text = "فعال" if new_status else "غیرفعال"
        await callback.answer(f"✅ چنل {status_text} شد.", show_alert=True)
        
        # Refresh detail view
        channel = await get_mandatory_channel_by_id(db_session, channel_id)
        status = "✅ فعال" if channel.is_active else "❌ غیرفعال"
        await callback.message.edit_text(
            f"📺 جزئیات چنل اجباری\n\n"
            f"🆔 ID: {channel.channel_id}\n"
            f"📝 نام: {channel.channel_name or 'بدون نام'}\n"
            f"🔗 لینک: {channel.channel_link or 'بدون لینک'}\n"
            f"📊 ترتیب: {channel.order_index}\n"
            f"✅ وضعیت: {status}\n"
            f"📅 ایجاد شده: {channel.created_at.strftime('%Y-%m-%d %H:%M')}",
            reply_markup=get_mandatory_channel_detail_keyboard(channel_id)
        )
        break


@router.callback_query(F.data.startswith("admin:mandatory_channel:delete:"))
async def callback_delete_mandatory_channel(callback: CallbackQuery):
    """Delete mandatory channel."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Access denied.", show_alert=True)
        return
    
    channel_id = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        channel = await get_mandatory_channel_by_id(db_session, channel_id)
        if not channel:
            await callback.answer("❌ چنل یافت نشد.", show_alert=True)
            return
        
        channel_name = channel.channel_name or channel.channel_id
        success = await delete_mandatory_channel(db_session, channel_id)
        
        if success:
            await callback.answer(f"✅ چنل {channel_name} حذف شد.", show_alert=True)
            # Show list
            channels = await get_all_mandatory_channels(db_session)
            if not channels:
                await callback.message.edit_text(
                    "📋 لیست چنل‌های اجباری\n\n"
                    "❌ هیچ چنل اجباری ثبت نشده است.",
                    reply_markup=get_mandatory_channels_keyboard()
                )
            else:
                channels_text = "📋 لیست چنل‌های اجباری:\n\n"
                for idx, ch in enumerate(channels[:10], start=1):
                    status = "✅" if ch.is_active else "❌"
                    ch_name = ch.channel_name or ch.channel_id
                    channels_text += f"{idx}. {status} {ch_name}\n"
                
                await callback.message.edit_text(
                    channels_text,
                    reply_markup=get_mandatory_channel_list_keyboard(channels, 0)
                )
        else:
            await callback.answer("❌ خطا در حذف چنل.", show_alert=True)
        break

