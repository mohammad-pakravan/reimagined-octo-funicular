"""
Leaderboard handlers for users.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from db.database import get_db
from db.crud import (
    get_user_by_telegram_id,
    get_top_users_by_points,
    get_top_users_by_referrals,
    get_top_users_by_likes,
    get_user_rank_by_points,
    get_user_rank_by_referrals,
    get_user_rank_by_likes,
    get_user_points,
    get_referral_count
)
from bot.keyboards.leaderboard import (
    get_leaderboard_main_keyboard,
    get_leaderboard_period_keyboard
)
from sqlalchemy import select, func
from db.models import Like

router = Router()


def get_gender_emoji(gender: str) -> str:
    """Get emoji for gender."""
    if gender == "male":
        return "👨"
    elif gender == "female":
        return "👩"
    else:
        return "⚪"


def format_profile_id(profile_id: str) -> str:
    """Format profile ID for display."""
    if profile_id:
        # profile_id is stored as "15e1576abc70" (without /user_)
        return f"/user_{profile_id}"
    return ""


@router.callback_query(F.data == "leaderboard:main")
async def leaderboard_main(callback: CallbackQuery):
    """Show leaderboard main menu."""
    await callback.message.edit_text(
        "🏆 رتبه‌بندی کاربران\n\n"
        "انتخاب کنید:",
        reply_markup=get_leaderboard_main_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "leaderboard:view")
async def leaderboard_view(callback: CallbackQuery):
    """Show leaderboard view (same as main)."""
    await leaderboard_main(callback)


@router.callback_query(F.data.startswith("leaderboard:points"))
async def leaderboard_points(callback: CallbackQuery):
    """Show points leaderboard."""
    data = callback.data.split(":")
    
    # Parse callback data: leaderboard:points:period or leaderboard:points:period:page:page_num
    if len(data) == 2:
        # No period selected
        await callback.message.edit_text(
            "💰 رتبه‌بندی بر اساس امتیاز\n\n"
            "انتخاب کنید:",
            reply_markup=get_leaderboard_period_keyboard("points")
        )
        await callback.answer()
        return
    
    period = data[2]
    page = int(data[4]) if len(data) > 4 and data[3] == "page" else 0
    
    period_filter = None if period == "all" else period
    limit = 10
    skip = page * limit
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, callback.from_user.id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Get users for current page
        top_users = await get_top_users_by_points(db_session, limit=limit + 1, skip=skip, period=period_filter)
        has_next = len(top_users) > limit
        if has_next:
            top_users = top_users[:limit]
        
        # Get all users to find user's rank (first 10 for checking if user is in top)
        all_top_users = await get_top_users_by_points(db_session, limit=10, skip=0, period=period_filter)
        user_rank = await get_user_rank_by_points(db_session, user.id, period=period_filter)
        user_points = await get_user_points(db_session, user.id) or 0
        
        # Check if user is in top 10
        user_in_top = False
        user_in_current_page = False
        for idx, (uid, _, _, _, _, _) in enumerate(all_top_users[:10], 1):
            if uid == user.id:
                user_in_top = True
                break
        for idx, (uid, _, _, _, _, _) in enumerate(top_users, 1):
            if uid == user.id:
                user_in_current_page = True
                break
        
        period_text = {
            "week": "هفته",
            "month": "ماه",
            "all": "همه زمان‌ها"
        }.get(period, "همه زمان‌ها")
        
        text = f"💰 رتبه‌بندی بر اساس امتیاز ({period_text})\n"
        if page > 0:
            text += f"📄 صفحه {page + 1}\n"
        text += "\n"
        
        if top_users:
            text += "🏆 برترین کاربران:\n\n"
            medals = ["🥇", "🥈", "🥉", "🥉", "🥉", "🥉", "🥉", "🥉", "🥉", "🥉"]
            for idx, (user_id, points, rank, display_name, profile_id, gender) in enumerate(top_users, 1):
                actual_rank = skip + idx
                if actual_rank <= 3:
                    medal = medals[actual_rank - 1]
                elif actual_rank <= 10:
                    medal = "🥉"
                else:
                    medal = f"{actual_rank}."
                
                gender_emoji = get_gender_emoji(gender)
                profile_id_str = format_profile_id(profile_id)
                
                # Format: medal gender name on first line, ID on second line
                text += f"{medal} {gender_emoji} {display_name}\n"
                if profile_id_str:
                    text += f"   {profile_id_str}\n"
                text += f"   {points:,} امتیاز\n\n"
        else:
            text += "📭 هنوز کاربری وجود ندارد.\n"
        
        # User stats section
        text += "─" * 20 + "\n"
        text += "📊 وضعیت شما:\n\n"
        
        if user_in_top:
            text += "🎉 تبریک! شما جزو برترین‌ها هستید!\n"
            text += "💪 ادامه بده و رتبه خودت رو بالاتر ببر!\n\n"
        elif user_in_current_page:
            text += "🌟 شما در این صفحه هستید!\n\n"
        
        text += f"📊 رتبه: {user_rank or 'نامشخص'}\n"
        text += f"💰 امتیاز: {user_points:,}\n\n"
        
        # Motivational message
        if user_rank and user_rank > 10:
            text += "💡 شما هم می‌تونی هفته یا ماه بعد جزو برترین‌ها بشی!\n"
            text += "🔥 بیشتر چت کن، دعوت بده و فعال باش تا رتبه‌ت بالا بره!\n"
        elif user_rank and user_rank > 3:
            text += "💪 خیلی نزدیک به مدال طلا هستی!\n"
            text += "🚀 ادامه بده و به رتبه‌های برتر برس!\n"
        elif user_rank and user_rank <= 3:
            text += "🏆 عالی! تو در رتبه‌های برتر هستی!\n"
            text += "💎 سعی کن رتبه‌ت رو حفظ کنی و بالاتر بری!\n"
        else:
            text += "💡 شروع کن و اولین امتیازت رو بگیر!\n"
            text += "🎯 با چت کردن و دعوت دوستان، امتیاز جمع کن!\n"
        
        from bot.keyboards.leaderboard import get_leaderboard_pagination_keyboard
        await callback.message.edit_text(
            text,
            reply_markup=get_leaderboard_pagination_keyboard("points", period, page, has_next)
        )
        await callback.answer()
        break


@router.callback_query(F.data.startswith("leaderboard:referrals"))
async def leaderboard_referrals(callback: CallbackQuery):
    """Show referrals leaderboard."""
    data = callback.data.split(":")
    
    if len(data) == 2:
        await callback.message.edit_text(
            "👥 رتبه‌بندی بر اساس دعوت\n\n"
            "انتخاب کنید:",
            reply_markup=get_leaderboard_period_keyboard("referrals")
        )
        await callback.answer()
        return
    
    period = data[2]
    page = int(data[4]) if len(data) > 4 and data[3] == "page" else 0
    
    period_filter = None if period == "all" else period
    limit = 10
    skip = page * limit
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, callback.from_user.id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        top_users = await get_top_users_by_referrals(db_session, limit=limit + 1, skip=skip, period=period_filter)
        has_next = len(top_users) > limit
        if has_next:
            top_users = top_users[:limit]
        
        all_top_users = await get_top_users_by_referrals(db_session, limit=10, skip=0, period=period_filter)
        user_rank = await get_user_rank_by_referrals(db_session, user.id, period=period_filter)
        user_referrals = await get_referral_count(db_session, user.id) or 0
        
        user_in_top = any(uid == user.id for uid, _, _, _, _, _ in all_top_users[:10])
        user_in_current_page = any(uid == user.id for uid, _, _, _, _, _ in top_users)
        
        period_text = {
            "week": "هفته",
            "month": "ماه",
            "all": "همه زمان‌ها"
        }.get(period, "همه زمان‌ها")
        
        text = f"👥 رتبه‌بندی بر اساس دعوت ({period_text})\n"
        if page > 0:
            text += f"📄 صفحه {page + 1}\n"
        text += "\n"
        
        if top_users:
            text += "🏆 برترین کاربران:\n\n"
            medals = ["🥇", "🥈", "🥉", "🥉", "🥉", "🥉", "🥉", "🥉", "🥉", "🥉"]
            for idx, (user_id, count, rank, display_name, profile_id, gender) in enumerate(top_users, 1):
                actual_rank = skip + idx
                if actual_rank <= 3:
                    medal = medals[actual_rank - 1]
                elif actual_rank <= 10:
                    medal = "🥉"
                else:
                    medal = f"{actual_rank}."
                
                gender_emoji = get_gender_emoji(gender)
                profile_id_str = format_profile_id(profile_id)
                
                text += f"{medal} {gender_emoji} {display_name}\n"
                if profile_id_str:
                    text += f"   {profile_id_str}\n"
                text += f"   {count} دعوت\n\n"
        else:
            text += "📭 هنوز کاربری وجود ندارد.\n"
        
        text += "─" * 20 + "\n"
        text += "📊 وضعیت شما:\n\n"
        
        if user_in_top:
            text += "🎉 تبریک! شما جزو برترین‌ها هستید!\n"
            text += "💪 ادامه بده و رتبه خودت رو بالاتر ببر!\n\n"
        elif user_in_current_page:
            text += "🌟 شما در این صفحه هستید!\n\n"
        
        text += f"📊 رتبه: {user_rank or 'نامشخص'}\n"
        text += f"👥 دعوت‌ها: {user_referrals}\n\n"
        
        if user_rank and user_rank > 10:
            text += "💡 شما هم می‌تونی هفته یا ماه بعد جزو برترین‌ها بشی!\n"
            text += "🔥 بیشتر دعوت بده و فعال باش تا رتبه‌ت بالا بره!\n"
        elif user_rank and user_rank > 3:
            text += "💪 خیلی نزدیک به مدال طلا هستی!\n"
            text += "🚀 ادامه بده و به رتبه‌های برتر برس!\n"
        elif user_rank and user_rank <= 3:
            text += "🏆 عالی! تو در رتبه‌های برتر هستی!\n"
            text += "💎 سعی کن رتبه‌ت رو حفظ کنی و بالاتر بری!\n"
        else:
            text += "💡 شروع کن و اولین دعوتت رو بده!\n"
            text += "🎯 با دعوت دوستان، امتیاز و رتبه جمع کن!\n"
        
        from bot.keyboards.leaderboard import get_leaderboard_pagination_keyboard
        await callback.message.edit_text(
            text,
            reply_markup=get_leaderboard_pagination_keyboard("referrals", period, page, has_next)
        )
        await callback.answer()
        break


@router.callback_query(F.data.startswith("leaderboard:likes"))
async def leaderboard_likes(callback: CallbackQuery):
    """Show likes leaderboard."""
    data = callback.data.split(":")
    
    if len(data) == 2:
        await callback.message.edit_text(
            "❤️ رتبه‌بندی بر اساس لایک\n\n"
            "انتخاب کنید:",
            reply_markup=get_leaderboard_period_keyboard("likes")
        )
        await callback.answer()
        return
    
    period = data[2]
    page = int(data[4]) if len(data) > 4 and data[3] == "page" else 0
    
    period_filter = None if period == "all" else period
    limit = 10
    skip = page * limit
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, callback.from_user.id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        top_users = await get_top_users_by_likes(db_session, limit=limit + 1, skip=skip, period=period_filter)
        has_next = len(top_users) > limit
        if has_next:
            top_users = top_users[:limit]
        
        all_top_users = await get_top_users_by_likes(db_session, limit=10, skip=0, period=period_filter)
        user_rank = await get_user_rank_by_likes(db_session, user.id, period=period_filter)
        
        user_in_top = any(uid == user.id for uid, _, _, _, _, _ in all_top_users[:10])
        user_in_current_page = any(uid == user.id for uid, _, _, _, _, _ in top_users)
        
        # Get user's like count
        from datetime import datetime, timedelta
        like_count_query = select(func.count(Like.id)).where(Like.liked_user_id == user.id)
        if period_filter:
            period_start = datetime.utcnow() - timedelta(days=7 if period_filter == 'week' else 30)
            like_count_query = like_count_query.where(Like.created_at >= period_start)
        
        result = await db_session.execute(like_count_query)
        user_likes = result.scalar() or 0
        
        period_text = {
            "week": "هفته",
            "month": "ماه",
            "all": "همه زمان‌ها"
        }.get(period, "همه زمان‌ها")
        
        text = f"❤️ رتبه‌بندی بر اساس لایک ({period_text})\n"
        if page > 0:
            text += f"📄 صفحه {page + 1}\n"
        text += "\n"
        
        if top_users:
            text += "🏆 برترین کاربران:\n\n"
            medals = ["🥇", "🥈", "🥉", "🥉", "🥉", "🥉", "🥉", "🥉", "🥉", "🥉"]
            for idx, (user_id, count, rank, display_name, profile_id, gender) in enumerate(top_users, 1):
                actual_rank = skip + idx
                if actual_rank <= 3:
                    medal = medals[actual_rank - 1]
                elif actual_rank <= 10:
                    medal = "🥉"
                else:
                    medal = f"{actual_rank}."
                
                gender_emoji = get_gender_emoji(gender)
                profile_id_str = format_profile_id(profile_id)
                
                text += f"{medal} {gender_emoji} {display_name}\n"
                if profile_id_str:
                    text += f"   {profile_id_str}\n"
                text += f"   {count} لایک\n\n"
        else:
            text += "📭 هنوز کاربری وجود ندارد.\n"
        
        text += "─" * 20 + "\n"
        text += "📊 وضعیت شما:\n\n"
        
        if user_in_top:
            text += "🎉 تبریک! شما جزو برترین‌ها هستید!\n"
            text += "💪 ادامه بده و رتبه خودت رو بالاتر ببر!\n\n"
        elif user_in_current_page:
            text += "🌟 شما در این صفحه هستید!\n\n"
        
        text += f"📊 رتبه: {user_rank or 'نامشخص'}\n"
        text += f"❤️ لایک‌ها: {user_likes}\n\n"
        
        if user_rank and user_rank > 10:
            text += "💡 شما هم می‌تونی هفته یا ماه بعد جزو برترین‌ها بشی!\n"
            text += "🔥 بیشتر فعال باش و پروفایلت رو کامل کن تا لایک بیشتری بگیری!\n"
        elif user_rank and user_rank > 3:
            text += "💪 خیلی نزدیک به مدال طلا هستی!\n"
            text += "🚀 ادامه بده و به رتبه‌های برتر برس!\n"
        elif user_rank and user_rank <= 3:
            text += "🏆 عالی! تو در رتبه‌های برتر هستی!\n"
            text += "💎 سعی کن رتبه‌ت رو حفظ کنی و بالاتر بری!\n"
        else:
            text += "💡 شروع کن و پروفایلت رو کامل کن!\n"
            text += "🎯 با داشتن پروفایل کامل، لایک بیشتری می‌گیری!\n"
        
        from bot.keyboards.leaderboard import get_leaderboard_pagination_keyboard
        await callback.message.edit_text(
            text,
            reply_markup=get_leaderboard_pagination_keyboard("likes", period, page, has_next)
        )
        await callback.answer()
        break
