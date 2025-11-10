"""
Achievements handler for managing achievements and badges.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery

from db.database import get_db
from db.crud import get_user_by_telegram_id, get_user_badges
from core.achievement_system import AchievementSystem
from sqlalchemy.orm import joinedload
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
        "🏆 مدال‌ها\n\n"
        "از منوی زیر انتخاب کنید:",
        reply_markup=get_achievements_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "achievements:completed")
async def achievements_completed(callback: CallbackQuery):
    """Show user's medals (completed achievements with badges)."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Get user badges (medals)
        from core.badge_manager import BadgeManager
        user_badges = await BadgeManager.get_user_badges_list(user.id)
        
        if not user_badges:
            await callback.message.edit_text(
                "🏅 مدال‌های من\n\n"
                "هنوز هیچ مدالی دریافت نکرده‌ای!\n\n"
                "💡 با تکمیل دستاوردها، مدال‌های مختلف دریافت می‌کنی.",
                reply_markup=get_achievements_menu_keyboard()
            )
        else:
            text = "🏅 مدال‌های من\n\n"
            for ub in user_badges[:15]:  # Show up to 15 medals
                icon = ub.badge.badge_icon or "🏆"
                earned_date = ub.earned_at.strftime("%Y/%m/%d") if ub.earned_at else ""
                text += f"{icon} {ub.badge.badge_name}"
                if ub.badge.badge_description:
                    text += f"\n   📝 {ub.badge.badge_description}"
                if earned_date:
                    text += f"\n   📅 دریافت شده: {earned_date}"
                text += "\n\n"
            
            if len(user_badges) > 15:
                text += f"\n... و {len(user_badges) - 15} مدال دیگر"
            
            await callback.message.edit_text(
                text,
                reply_markup=get_achievements_menu_keyboard()
            )
        
        await callback.answer()
        break


@router.callback_query(F.data == "achievements:badges")
async def achievements_badges(callback: CallbackQuery):
    """Show all available medals with user progress."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Get all badges from database
        from db.crud import get_all_badges
        from sqlalchemy import select
        from db.models import Achievement
        
        all_badges = await get_all_badges(db_session)
        user_achievements = await AchievementSystem.get_user_achievements_list(user.id)
        user_badges = await get_user_badges(db_session, user.id)
        
        # Create dicts for quick lookup
        user_achievements_dict = {ua.achievement_id: ua for ua in user_achievements}
        user_badges_dict = {ub.badge_id: ub for ub in user_badges}
        
        # Badge icon mapping (to handle encoding issues)
        badge_icon_map = {
            'first_chat': '💬',
            'chat_master': '🎯',
            'social_butterfly': '🦋',
            'popular': '⭐',
            'streak_7': '🔥',
            'streak_30': '💪',
            'referrer': '👥',
            'super_referrer': '🎉',
            'early_bird': '🐦',
            'premium': '💎',
            'chat_100': '🎖️',
            'chat_500': '👑',
            'message_1000': '💬',
            'message_10000': '📨',
            'like_given_50': '👍',
            'like_given_200': '❤️',
            'like_received_1000': '⭐',
            'follow_given_20': '👥',
            'follow_received_50': '🌟',
            'follow_received_200': '🎭',
            'dm_sent_50': '📧',
            'dm_sent_200': '💌',
            'streak_100': '💯',
            'streak_365': '🏆',
            'referral_50': '🎁',
            'referral_100': '🏅',
            'premium_1_year': '💎',
            'premium_lifetime': '👑',
            'early_adopter': '🚀',
            'active_user': '⚡',
        }
        
        # Badge name mapping (Persian names)
        badge_name_map = {
            'first_chat': 'اولین چت',
            'chat_master': 'استاد چت',
            'social_butterfly': 'پروانه اجتماعی',
            'popular': 'محبوب',
            'streak_7': 'جنگجوی هفته',
            'streak_30': 'جنگجوی ماه',
            'referrer': 'معرف',
            'super_referrer': 'معرف برتر',
            'early_bird': 'پرنده اولیه',
            'premium': 'عضو پریمیوم',
            'chat_100': 'کهنه‌کار چت',
            'chat_500': 'افسانه چت',
            'message_1000': 'استاد پیام',
            'message_10000': 'افسانه پیام',
            'like_given_50': 'لایک‌دهنده',
            'like_given_200': 'لایک‌دهنده برتر',
            'like_received_1000': 'ستاره',
            'follow_given_20': 'دنبال‌کننده',
            'follow_received_50': 'تأثیرگذار',
            'follow_received_200': 'سلبریتی',
            'dm_sent_50': 'پیام‌رسان',
            'dm_sent_200': 'ارتباط‌گر',
            'streak_100': 'صدتایی',
            'streak_365': 'جنگجوی سال',
            'referral_50': 'سفیر',
            'referral_100': 'قهرمان',
            'premium_1_year': 'کهنه‌کار پریمیوم',
            'premium_lifetime': 'استاد پریمیوم',
            'early_adopter': 'پیشگام',
            'active_user': 'کاربر فعال',
        }
        
        # Achievement name mapping (Persian names)
        # This mapping ensures Persian names are always used, avoiding encoding issues
        achievement_name_map = {
            'first_chat': 'اولین چت',
            'chat_10': 'چت‌کننده',
            'chat_50': 'استاد چت',
            'like_10': 'لایک شده',
            'like_100': 'پروانه اجتماعی',
            'like_500': 'محبوب',
            'streak_7': 'جنگجوی هفته',
            'streak_30': 'جنگجوی ماه',
            'referral_1': 'معرف',
            'referral_10': 'معرف برتر',
            'chat_100': 'کهنه‌کار چت',
            'chat_500': 'افسانه چت',
            'message_1000': 'استاد پیام',
            'message_10000': 'افسانه پیام',
            'like_given_50': 'لایک‌دهنده',
            'like_given_200': 'لایک‌دهنده برتر',
            'like_received_1000': 'ستاره',
            'follow_given_20': 'دنبال‌کننده',
            'follow_received_50': 'تأثیرگذار',
            'follow_received_200': 'سلبریتی',
            'dm_sent_50': 'پیام‌رسان',
            'dm_sent_200': 'ارتباط‌گر',
            'streak_100': 'صدتایی',
            'streak_365': 'جنگجوی سال',
            'referral_50': 'سفیر',
            'referral_100': 'قهرمان',
        }
        
        # Ensure all achievement keys from database are in the mapping
        # If not found, use a default Persian name based on the key pattern
        
        # Get achievements that have badges (badge_id is not None)
        achievements_result = await db_session.execute(
            select(Achievement)
            .where(Achievement.badge_id.isnot(None))
            .options(joinedload(Achievement.badge))
        )
        achievements_with_badges = list(achievements_result.unique().scalars().all())
        
        # Create a dict mapping badge_id to achievement
        badge_to_achievement = {a.badge_id: a for a in achievements_with_badges if a.badge_id}
        
        # Debug: Print achievement keys to verify they're being read correctly
        # This will help us see if achievement_key is being read properly
        
        if not all_badges:
            await callback.message.edit_text(
                "🏅 مدال‌ها\n\n"
                "هنوز مدالی تعریف نشده است!\n\n"
                "💡 مدال‌ها با تکمیل دستاوردها دریافت می‌شوند.",
                reply_markup=get_achievements_menu_keyboard()
            )
        else:
            text = "🏅 مدال‌ها\n\n"
            text += "💡 با تکمیل دستاوردها، مدال‌های مختلف دریافت می‌کنی.\n\n"
            
            # Show badges that have achievements first
            shown_count = 0
            for badge in all_badges[:20]:  # Show up to 20 badges
                if shown_count >= 15:
                    break
                    
                achievement = badge_to_achievement.get(badge.id)
                has_badge = badge.id in user_badges_dict
                
                # Get badge icon and name - use mapping to handle encoding issues
                icon = badge_icon_map.get(badge.badge_key, "🏆")
                badge_name = badge_name_map.get(badge.badge_key, badge.badge_name or "مدال")
                
                if has_badge:
                    # User has this medal
                    text += f"✅ {icon} {badge_name}\n"
                    if badge.badge_description:
                        text += f"   📝 {badge.badge_description}\n"
                    text += "   🎉 دریافت شده!\n\n"
                    shown_count += 1
                elif achievement:
                    # Has achievement - show progress
                    ua = user_achievements_dict.get(achievement.id)
                    current_progress = ua.current_progress if ua else 0
                    target_value = achievement.target_value
                    progress_percent = int((current_progress / target_value) * 100) if target_value > 0 else 0
                    
                    # Get achievement name from mapping (always use mapping to avoid encoding issues)
                    # achievement_key should be a string like 'first_chat', 'chat_50', etc.
                    achievement_key = str(achievement.achievement_key).strip() if achievement.achievement_key else ""
                    achievement_name = achievement_name_map.get(achievement_key, f"دستاورد ({achievement_key})" if achievement_key else "دستاورد")
                    
                    if ua and ua.is_completed:
                        # Completed but badge not awarded yet (shouldn't happen, but handle it)
                        text += f"✅ {icon} {badge_name}\n"
                        text += f"   📊 پیشرفت: {current_progress}/{target_value} (100%)\n"
                        text += "   🎉 دریافت شده!\n\n"
                    elif current_progress > 0:
                        # In progress
                        text += f"⏳ {achievement_name}\n"
                        text += f"   📊 پیشرفت: {current_progress}/{target_value} ({progress_percent}%)\n"
                        text += f"   🏅 مدال: {icon} {badge_name}\n\n"
                    else:
                        # Not started
                        text += f"🔒 {achievement_name}\n"
                        text += f"   📊 پیشرفت: 0/{target_value} (0%)\n"
                        text += f"   🏅 مدال: {icon} {badge_name}\n\n"
                    shown_count += 1
                else:
                    # Badge exists but no achievement linked (show badge anyway)
                    text += f"🔒 {badge_name}\n"
                    if badge.badge_description:
                        text += f"   📝 {badge.badge_description}\n"
                    text += "   💡 این مدال با تکمیل دستاوردهای مرتبط دریافت می‌شود.\n\n"
                    shown_count += 1
            
            if len(all_badges) > 15:
                remaining = len(all_badges) - shown_count
                if remaining > 0:
                    text += f"\n... و {remaining} مدال دیگر"
            
            await callback.message.edit_text(
                text,
                reply_markup=get_achievements_menu_keyboard()
            )
        
        await callback.answer()
        break






