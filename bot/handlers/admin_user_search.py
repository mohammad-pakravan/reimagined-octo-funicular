"""
Admin user search handlers.
Handles searching users by name.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from db.database import get_db
from db.crud import search_users_by_name
from db.models import User
from bot.keyboards.admin import (
    get_admin_users_keyboard,
    get_admin_user_search_results_keyboard,
)
from bot.handlers.admin import is_admin, AdminUserSearchStates
from utils.validators import get_display_name

router = Router()


@router.message(AdminUserSearchStates.waiting_name)
async def process_admin_user_search(message: Message, state: FSMContext):
    """Process user search by name."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        await state.clear()
        return
    
    search_query = message.text.strip()
    
    if len(search_query) < 2:
        await message.answer("❌ لطفاً حداقل 2 کاراکتر وارد کنید.")
        return
    
    async for db_session in get_db():
        # Search users by name
        users = await search_users_by_name(
            db_session,
            name_query=search_query,
            limit=100,  # Get more results for pagination
            offset=0
        )
        
        if not users:
            await message.answer(
                f"❌ هیچ کاربری با نام '{search_query}' یافت نشد.\n\n"
                f"لطفاً دوباره جستجو کنید:",
                reply_markup=get_admin_users_keyboard()
            )
            await state.clear()
            return
        
        # Store search results in state for pagination
        await state.update_data(
            search_results=[user.id for user in users],
            search_query=search_query
        )
        
        # Display first page
        page = 0
        per_page = 10
        start_idx = page * per_page
        end_idx = start_idx + per_page
        users_page = users[start_idx:end_idx]
        
        text = f"🔍 نتایج جستجو برای '{search_query}'\n\n"
        text += f"📊 تعداد کل: {len(users)} کاربر\n\n"
        
        for user in users_page:
            display_name = get_display_name(user)
            status = "🚫 بن شده" if user.is_banned else "✅ فعال"
            gender_map = {"male": "👨", "female": "👩", "other": "⚪"}
            gender_emoji = gender_map.get(user.gender, "❓")
            text += f"{gender_emoji} {display_name} - {status}\n"
            text += f"   ID: {user.id} | /user_{user.profile_id or 'N/A'}\n\n"
        
        await message.answer(
            text,
            reply_markup=get_admin_user_search_results_keyboard(users, page=page)
        )
        await state.clear()
        break


@router.callback_query(F.data.startswith("admin:user:search_results:"))
async def admin_user_search_results_page(callback: CallbackQuery, state: FSMContext):
    """Handle pagination for user search results."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    page = int(callback.data.split(":")[-1])
    
    # Get search results from state or re-search
    data = await state.get_data()
    user_ids = data.get("search_results")
    search_query = data.get("search_query")
    
    if not user_ids or not search_query:
        await callback.answer("❌ نتایج جستجو یافت نشد. لطفاً دوباره جستجو کنید.", show_alert=True)
        return
    
    async for db_session in get_db():
        # Get users by IDs
        result = await db_session.execute(
            select(User).where(User.id.in_(user_ids))
        )
        users = list(result.scalars().all())
        
        # Sort by ID to maintain order
        users_dict = {user.id: user for user in users}
        users = [users_dict[uid] for uid in user_ids if uid in users_dict]
        
        per_page = 10
        start_idx = page * per_page
        end_idx = start_idx + per_page
        users_page = users[start_idx:end_idx]
        
        text = f"🔍 نتایج جستجو برای '{search_query}'\n\n"
        text += f"📊 تعداد کل: {len(users)} کاربر\n\n"
        
        for user in users_page:
            display_name = get_display_name(user)
            status = "🚫 بن شده" if user.is_banned else "✅ فعال"
            gender_map = {"male": "👨", "female": "👩", "other": "⚪"}
            gender_emoji = gender_map.get(user.gender, "❓")
            text += f"{gender_emoji} {display_name} - {status}\n"
            text += f"   ID: {user.id} | /user_{user.profile_id or 'N/A'}\n\n"
        
        # Check if message has photo, if so use edit_caption, otherwise edit_text
        try:
            if callback.message.photo:
                await callback.message.edit_caption(
                    caption=text,
                    reply_markup=get_admin_user_search_results_keyboard(users, page=page)
                )
            else:
                await callback.message.edit_text(
                    text,
                    reply_markup=get_admin_user_search_results_keyboard(users, page=page)
                )
        except Exception:
            await callback.message.answer(
                text,
                reply_markup=get_admin_user_search_results_keyboard(users, page=page)
            )
        
        await callback.answer()
        break

