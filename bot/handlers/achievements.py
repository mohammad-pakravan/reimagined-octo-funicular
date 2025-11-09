"""
Achievements handler for managing achievements and badges.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery

from db.database import get_db
from db.crud import get_user_by_telegram_id, get_user_badges
from core.achievement_system import AchievementSystem
from bot.keyboards.engagement import (
    get_achievements_menu_keyboard,
    get_achievements_pagination_keyboard,
    get_engagement_menu_keyboard
)

router = Router()


@router.callback_query(F.data == "achievements:list")
async def achievements_list(callback: CallbackQuery):
    """Show achievements menu."""
    await callback.message.edit_text(
        "🏆 دستاوردها\n\n"
        "از منوی زیر انتخاب کنید:",
        reply_markup=get_achievements_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "achievements:completed")
async def achievements_completed(callback: CallbackQuery):
    """Show completed achievements."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        achievements = await AchievementSystem.get_user_achievements_list(
            user.id,
            completed_only=True
        )
        
        if not achievements:
            await callback.message.edit_text(
                "✅ دستاوردهای کامل شده\n\n"
                "هنوز هیچ دستاوردی کامل نکرده‌ای!",
                reply_markup=get_achievements_menu_keyboard()
            )
        else:
            text = "✅ دستاوردهای کامل شده\n\n"
            for ua in achievements[:10]:
                text += f"✅ {ua.achievement.achievement_name}\n"
            
            await callback.message.edit_text(
                text,
                reply_markup=get_achievements_menu_keyboard()
            )
        
        await callback.answer()
        break


@router.callback_query(F.data == "achievements:badges")
async def achievements_badges(callback: CallbackQuery):
    """Show user badges."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        badges = await get_user_badges(db_session, user.id)
        
        if not badges:
            await callback.message.edit_text(
                "🎖️ بج‌ها\n\n"
                "هنوز هیچ بجی دریافت نکرده‌ای!",
                reply_markup=get_achievements_menu_keyboard()
            )
        else:
            text = "🎖️ بج‌های شما\n\n"
            for ub in badges[:10]:
                icon = ub.badge.badge_icon or "🏆"
                text += f"{icon} {ub.badge.badge_name}\n"
            
            await callback.message.edit_text(
                text,
                reply_markup=get_achievements_menu_keyboard()
            )
        
        await callback.answer()
        break


@router.callback_query(F.data == "achievements:all")
async def achievements_all(callback: CallbackQuery):
    """Show all available achievements."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        all_achievements = await AchievementSystem.get_all_available_achievements()
        user_achievements = await AchievementSystem.get_user_achievements_list(user.id)
        
        # Create a dict of user achievements by achievement_id
        user_achievements_dict = {ua.achievement_id: ua for ua in user_achievements}
        
        text = "📋 همه دستاوردها\n\n"
        for achievement in all_achievements[:10]:
            ua = user_achievements_dict.get(achievement.id)
            status = "✅" if ua and ua.is_completed else "⏳"
            progress = ""
            if ua and not ua.is_completed:
                progress = f" ({ua.current_progress}/{achievement.target_value})"
            text += f"{status} {achievement.achievement_name}{progress}\n"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_achievements_menu_keyboard()
        )
        await callback.answer()
        break




