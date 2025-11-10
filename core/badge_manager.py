"""
Badge manager for handling badge awards and notifications.
Manages badge display and notification sending.
"""
from typing import Optional, List
from aiogram import Bot
from aiogram.types import Message

from db.crud import (
    get_badge_by_key,
    award_badge_to_user,
    get_user_badges,
    get_user_by_id,
)
from db.database import get_db
from db.models import Badge, UserBadge
from config.settings import settings


class BadgeManager:
    """Manages badge awards and notifications."""
    
    @staticmethod
    async def award_badge_and_notify(
        user_id: int,
        badge_key: str,
        bot: Optional[Bot] = None,
        telegram_id: Optional[int] = None
    ) -> Optional[UserBadge]:
        """
        Award a badge to user and send notification.
        
        Args:
            user_id: User database ID
            badge_key: Badge key (e.g., 'chat_100', 'like_given_50')
            bot: Bot instance for sending notification (optional)
            telegram_id: User's Telegram ID (optional, will be fetched if not provided)
            
        Returns:
            UserBadge object if badge was awarded, None otherwise
        """
        async for db_session in get_db():
            # Check if badge exists
            badge = await get_badge_by_key(db_session, badge_key)
            if not badge:
                return None
            
            # Check if user already has this badge
            user_badges = await get_user_badges(db_session, user_id)
            existing_badge = next((ub for ub in user_badges if ub.badge_id == badge.id), None)
            if existing_badge:
                return existing_badge  # Already has badge
            
            # Award badge
            user_badge = await award_badge_to_user(db_session, user_id, badge.id)
            
            if user_badge and bot:
                # Get user's Telegram ID if not provided
                if not telegram_id:
                    user = await get_user_by_id(db_session, user_id)
                    if user:
                        telegram_id = user.telegram_id
                
                if telegram_id:
                    # Send notification
                    await BadgeManager.send_badge_notification(
                        bot,
                        telegram_id,
                        badge
                    )
            
            return user_badge
    
    @staticmethod
    async def send_badge_notification(
        bot: Bot,
        telegram_id: int,
        badge: Badge
    ) -> None:
        """
        Send badge notification to user.
        
        Args:
            bot: Bot instance
            telegram_id: User's Telegram ID
            badge: Badge object
        """
        icon = badge.badge_icon or "🏆"
        message_text = (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎉 تبریک! مدال جدید دریافت کردی!\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{icon} {badge.badge_name}\n\n"
        )
        
        if badge.badge_description:
            message_text += f"{badge.badge_description}\n\n"
        
        message_text += (
            f"💎 این مدال در پروفایلت نمایش داده می‌شه!\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        
        try:
            await bot.send_message(
                telegram_id,
                message_text
            )
        except Exception:
            pass  # Don't fail if notification fails
    
    @staticmethod
    async def get_user_badges_display(
        user_id: int,
        limit: int = 5
    ) -> str:
        """
        Get user badges as display string.
        
        Args:
            user_id: User database ID
            limit: Maximum number of badges to display
            
        Returns:
            String representation of badges (empty if no badges)
        """
        async for db_session in get_db():
            user_badges = await get_user_badges(db_session, user_id)
            
            if not user_badges:
                return ""
            
            # Sort by earned_at (most recent first) and limit
            sorted_badges = sorted(
                user_badges,
                key=lambda ub: ub.earned_at,
                reverse=True
            )[:limit]
            
            # Format badges
            badge_texts = []
            for user_badge in sorted_badges:
                icon = user_badge.badge.badge_icon or "🏆"
                badge_texts.append(f"{icon} {user_badge.badge.badge_name}")
            
            return " • ".join(badge_texts) if badge_texts else ""
    
    @staticmethod
    async def get_user_badges_list(
        user_id: int,
        limit: Optional[int] = None
    ) -> List[UserBadge]:
        """
        Get list of user badges.
        
        Args:
            user_id: User database ID
            limit: Maximum number of badges to return (None for all)
            
        Returns:
            List of UserBadge objects
        """
        async for db_session in get_db():
            user_badges = await get_user_badges(db_session, user_id)
            
            # Sort by earned_at (most recent first)
            sorted_badges = sorted(
                user_badges,
                key=lambda ub: ub.earned_at,
                reverse=True
            )
            
            if limit:
                return sorted_badges[:limit]
            return sorted_badges

