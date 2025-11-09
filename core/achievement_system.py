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
        
        return completed
    
    @staticmethod
    async def check_like_count_achievement(user_id: int, like_count: int) -> List[UserAchievement]:
        """
        Check like count achievements.
        
        Args:
            user_id: User ID
            like_count: Current like count
            
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




