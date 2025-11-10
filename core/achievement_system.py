"""
Achievement system for tracking and awarding achievements.
Manages achievement progress, completion checks, and badge awards.
"""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from db.crud import (
    get_achievement_by_key,
    update_user_achievement_progress,
    get_user_achievements,
    get_all_achievements,
    get_achievement_by_key as get_achievement,
)
from db.database import get_db
from db.models import Achievement, UserAchievement
from config.settings import settings


class AchievementSystem:
    """Manages achievements and progress tracking."""
    
    @staticmethod
    async def check_and_update_achievement(
        user_id: int,
        achievement_key: str,
        progress_increment: int = 1
    ) -> Optional[UserAchievement]:
        """
        Check and update achievement progress.
        
        Args:
            user_id: User ID
            achievement_key: Achievement key (e.g., 'chat_10', 'like_100')
            progress_increment: Amount to increment progress
            
        Returns:
            Updated UserAchievement or None if achievement doesn't exist
        """
        if not settings.ACHIEVEMENT_CHECK_ENABLED:
            return None
        
        async for db_session in get_db():
            achievement = await get_achievement_by_key(db_session, achievement_key)
            
            if not achievement:
                return None
            
            return await update_user_achievement_progress(
                db_session,
                user_id,
                achievement.id,
                progress_increment
            )
    
    @staticmethod
    async def check_chat_count_achievement(user_id: int, chat_count: int) -> List[UserAchievement]:
        """
        Check chat count achievements.
        
        Args:
            user_id: User ID
            chat_count: Current chat count
            
        Returns:
            List of completed achievements
        """
        completed = []
        
        # Check first chat achievement
        if chat_count >= 1:
            achievement = await AchievementSystem.check_and_update_achievement(
                user_id,
                "first_chat",
                1
            )
            if achievement and achievement.is_completed:
                completed.append(achievement)
        
        # Check chat_10 achievement
        if chat_count >= 10:
            achievement = await AchievementSystem.check_and_update_achievement(
                user_id,
                "chat_10",
                1
            )
            if achievement and achievement.is_completed:
                completed.append(achievement)
        
        # Check chat_50 achievement
        if chat_count >= 50:
            achievement = await AchievementSystem.check_and_update_achievement(
                user_id,
                "chat_50",
                1
            )
            if achievement and achievement.is_completed:
                completed.append(achievement)
        
        # Check chat_100 achievement
        if chat_count >= 100:
            achievement = await AchievementSystem.check_and_update_achievement(
                user_id,
                "chat_100",
                1
            )
            if achievement and achievement.is_completed:
                completed.append(achievement)
        
        # Check chat_500 achievement
        if chat_count >= 500:
            achievement = await AchievementSystem.check_and_update_achievement(
                user_id,
                "chat_500",
                1
            )
            if achievement and achievement.is_completed:
                completed.append(achievement)
        
        return completed
    
    @staticmethod
    async def check_like_count_achievement(user_id: int, like_count: int) -> List[UserAchievement]:
        """
        Check like count achievements (received likes).
        
        Args:
            user_id: User ID
            like_count: Current like count (received)
            
        Returns:
            List of completed achievements
        """
        completed = []
        
        # Check like_10 achievement
        if like_count >= 10:
            achievement = await AchievementSystem.check_and_update_achievement(
                user_id,
                "like_10",
                1
            )
            if achievement and achievement.is_completed:
                completed.append(achievement)
        
        # Check like_100 achievement
        if like_count >= 100:
            achievement = await AchievementSystem.check_and_update_achievement(
                user_id,
                "like_100",
                1
            )
            if achievement and achievement.is_completed:
                completed.append(achievement)
        
        # Check like_500 achievement
        if like_count >= 500:
            achievement = await AchievementSystem.check_and_update_achievement(
                user_id,
                "like_500",
                1
            )
            if achievement and achievement.is_completed:
                completed.append(achievement)
        
        # Check like_received_1000 achievement
        if like_count >= 1000:
            achievement = await AchievementSystem.check_and_update_achievement(
                user_id,
                "like_received_1000",
                1
            )
            if achievement and achievement.is_completed:
                completed.append(achievement)
        
        return completed
    
    @staticmethod
    async def check_like_given_count_achievement(user_id: int, like_given_count: int) -> List[UserAchievement]:
        """
        Check like given count achievements.
        
        Args:
            user_id: User ID
            like_given_count: Current like given count
            
        Returns:
            List of completed achievements
        """
        completed = []
        
        # Check like_given_50 achievement
        if like_given_count >= 50:
            achievement = await AchievementSystem.check_and_update_achievement(
                user_id,
                "like_given_50",
                1
            )
            if achievement and achievement.is_completed:
                completed.append(achievement)
        
        # Check like_given_200 achievement
        if like_given_count >= 200:
            achievement = await AchievementSystem.check_and_update_achievement(
                user_id,
                "like_given_200",
                1
            )
            if achievement and achievement.is_completed:
                completed.append(achievement)
        
        return completed
    
    @staticmethod
    async def check_streak_achievement(user_id: int, streak_count: int) -> List[UserAchievement]:
        """
        Check streak achievements.
        
        Args:
            user_id: User ID
            streak_count: Current streak count
            
        Returns:
            List of completed achievements
        """
        completed = []
        
        # Check streak_7 achievement
        if streak_count >= 7:
            achievement = await AchievementSystem.check_and_update_achievement(
                user_id,
                "streak_7",
                1
            )
            if achievement and achievement.is_completed:
                completed.append(achievement)
        
        # Check streak_30 achievement
        if streak_count >= 30:
            achievement = await AchievementSystem.check_and_update_achievement(
                user_id,
                "streak_30",
                1
            )
            if achievement and achievement.is_completed:
                completed.append(achievement)
        
        # Check streak_100 achievement
        if streak_count >= 100:
            achievement = await AchievementSystem.check_and_update_achievement(
                user_id,
                "streak_100",
                1
            )
            if achievement and achievement.is_completed:
                completed.append(achievement)
        
        # Check streak_365 achievement
        if streak_count >= 365:
            achievement = await AchievementSystem.check_and_update_achievement(
                user_id,
                "streak_365",
                1
            )
            if achievement and achievement.is_completed:
                completed.append(achievement)
        
        return completed
    
    @staticmethod
    async def check_referral_achievement(user_id: int, referral_count: int) -> List[UserAchievement]:
        """
        Check referral achievements.
        
        Args:
            user_id: User ID
            referral_count: Current referral count
            
        Returns:
            List of completed achievements
        """
        completed = []
        
        # Check referral_1 achievement
        if referral_count >= 1:
            achievement = await AchievementSystem.check_and_update_achievement(
                user_id,
                "referral_1",
                1
            )
            if achievement and achievement.is_completed:
                completed.append(achievement)
        
        # Check referral_10 achievement
        if referral_count >= 10:
            achievement = await AchievementSystem.check_and_update_achievement(
                user_id,
                "referral_10",
                1
            )
            if achievement and achievement.is_completed:
                completed.append(achievement)
        
        # Check referral_50 achievement
        if referral_count >= 50:
            achievement = await AchievementSystem.check_and_update_achievement(
                user_id,
                "referral_50",
                1
            )
            if achievement and achievement.is_completed:
                completed.append(achievement)
        
        # Check referral_100 achievement
        if referral_count >= 100:
            achievement = await AchievementSystem.check_and_update_achievement(
                user_id,
                "referral_100",
                1
            )
            if achievement and achievement.is_completed:
                completed.append(achievement)
        
        return completed
    
    @staticmethod
    async def check_follow_count_achievement(user_id: int, follow_given_count: int, follow_received_count: int) -> List[UserAchievement]:
        """
        Check follow count achievements.
        
        Args:
            user_id: User ID
            follow_given_count: Number of follows given
            follow_received_count: Number of follows received
            
        Returns:
            List of completed achievements
        """
        completed = []
        
        # Check follow_given_20 achievement
        if follow_given_count >= 20:
            achievement = await AchievementSystem.check_and_update_achievement(
                user_id,
                "follow_given_20",
                1
            )
            if achievement and achievement.is_completed:
                completed.append(achievement)
        
        # Check follow_received_50 achievement
        if follow_received_count >= 50:
            achievement = await AchievementSystem.check_and_update_achievement(
                user_id,
                "follow_received_50",
                1
            )
            if achievement and achievement.is_completed:
                completed.append(achievement)
        
        # Check follow_received_200 achievement
        if follow_received_count >= 200:
            achievement = await AchievementSystem.check_and_update_achievement(
                user_id,
                "follow_received_200",
                1
            )
            if achievement and achievement.is_completed:
                completed.append(achievement)
        
        return completed
    
    @staticmethod
    async def check_dm_count_achievement(user_id: int, dm_sent_count: int) -> List[UserAchievement]:
        """
        Check direct message count achievements.
        
        Args:
            user_id: User ID
            dm_sent_count: Number of direct messages sent
            
        Returns:
            List of completed achievements
        """
        completed = []
        
        # Check dm_sent_50 achievement
        if dm_sent_count >= 50:
            achievement = await AchievementSystem.check_and_update_achievement(
                user_id,
                "dm_sent_50",
                1
            )
            if achievement and achievement.is_completed:
                completed.append(achievement)
        
        # Check dm_sent_200 achievement
        if dm_sent_count >= 200:
            achievement = await AchievementSystem.check_and_update_achievement(
                user_id,
                "dm_sent_200",
                1
            )
            if achievement and achievement.is_completed:
                completed.append(achievement)
        
        return completed
    
    @staticmethod
    async def check_message_count_achievement(user_id: int, message_count: int) -> List[UserAchievement]:
        """
        Check message count achievements (messages sent in chats).
        
        Args:
            user_id: User ID
            message_count: Number of messages sent in chats
            
        Returns:
            List of completed achievements
        """
        completed = []
        
        # Check message_1000 achievement
        if message_count >= 1000:
            achievement = await AchievementSystem.check_and_update_achievement(
                user_id,
                "message_1000",
                1
            )
            if achievement and achievement.is_completed:
                completed.append(achievement)
        
        # Check message_10000 achievement
        if message_count >= 10000:
            achievement = await AchievementSystem.check_and_update_achievement(
                user_id,
                "message_10000",
                1
            )
            if achievement and achievement.is_completed:
                completed.append(achievement)
        
        return completed
    
    @staticmethod
    async def check_premium_achievement(user_id: int, premium_days: int) -> List[UserAchievement]:
        """
        Check premium achievements.
        
        Args:
            user_id: User ID
            premium_days: Total premium days user has had
            
        Returns:
            List of completed achievements
        """
        completed = []
        
        # Check premium_1_year achievement (365 days)
        if premium_days >= 365:
            achievement = await AchievementSystem.check_and_update_achievement(
                user_id,
                "premium_1_year",
                1
            )
            if achievement and achievement.is_completed:
                completed.append(achievement)
        
        # Note: premium_lifetime would need special handling
        # For now, we'll check if user has premium_expires_at far in the future
        # This can be improved later
        
        return completed
    
    @staticmethod
    async def get_user_achievements_list(
        user_id: int,
        completed_only: bool = False
    ) -> List[UserAchievement]:
        """
        Get user's achievements.
        
        Args:
            user_id: User ID
            completed_only: If True, only return completed achievements
            
        Returns:
            List of UserAchievement objects
        """
        async for db_session in get_db():
            return await get_user_achievements(db_session, user_id, completed_only)
    
    @staticmethod
    async def get_all_available_achievements() -> List[Achievement]:
        """
        Get all available achievements.
        
        Returns:
            List of Achievement objects
        """
        async for db_session in get_db():
            return await get_all_achievements(db_session)




