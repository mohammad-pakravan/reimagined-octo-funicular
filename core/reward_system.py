"""
Reward system for handling daily rewards and streaks.
Manages daily login rewards, streak tracking, and bonus calculations.
"""
from datetime import date, timedelta
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from db.crud import (
    get_daily_reward,
    get_last_daily_reward,
    create_daily_reward,
    get_coins_for_activity,
)
from db.database import get_db
from core.points_manager import PointsManager
from core.event_engine import EventEngine
from config.settings import settings


class RewardSystem:
    """Manages daily rewards and streaks."""
    
    @staticmethod
    async def calculate_streak(user_id: int) -> Tuple[int, bool]:
        """
        Calculate user's current streak.
        
        Args:
            user_id: User ID
            
        Returns:
            Tuple of (streak_count, is_new_streak)
            - streak_count: Current streak count
            - is_new_streak: True if this is a continuation of streak, False if broken
        """
        async for db_session in get_db():
            last_reward = await get_last_daily_reward(db_session, user_id)
            
            if not last_reward:
                return (1, True)  # First reward
            
            today = date.today()
            last_date = last_reward.reward_date
            
            # Check if last reward was yesterday (continuing streak)
            if last_date == today - timedelta(days=1):
                # Continue streak
                new_streak = last_reward.streak_count + 1
                return (new_streak, True)
            elif last_date == today:
                # Already claimed today
                return (last_reward.streak_count, False)
            else:
                # Streak broken, start new streak
                return (1, True)
    
    @staticmethod
    async def calculate_reward_points(streak_count: int) -> int:
        """
        Calculate reward points (only base coins from admin, no streak bonus).
        Streak bonus is removed - only base coins are given.
        Event multipliers are applied separately in EventEngine.
        
        Args:
            streak_count: Current streak count (kept for tracking, but not used for bonus)
            
        Returns:
            Points to award (base coins only)
        """
        # Get base points from database (set by admin)
        async for db_session in get_db():
            base_coins = await get_coins_for_activity(db_session, "daily_login")
            if base_coins is None:
                base_coins = settings.DAILY_REWARD_BASE_POINTS  # Fallback to settings
            break
        
        # Return only base coins (no streak bonus)
        return base_coins
    
    @staticmethod
    async def claim_daily_reward(user_id: int, telegram_id: Optional[int] = None) -> Optional[dict]:
        """
        Claim daily reward for user.
        
        Args:
            user_id: User ID
            telegram_id: Optional Telegram ID to check if this telegram_id has claimed today (prevents abuse)
            
        Returns:
            Dictionary with reward info or None if already claimed today
            {
                'points': int,
                'streak_count': int,
                'already_claimed': bool
            }
        """
        async for db_session in get_db():
            today = date.today()
            
            # Import here to avoid circular dependency
            from db.crud import check_telegram_id_claimed_daily_reward, get_daily_reward
            from sqlalchemy import select
            from db.models import DailyReward, User
            
            # Check if telegram_id has claimed today (prevent abuse after account deletion)
            if telegram_id:
                if await check_telegram_id_claimed_daily_reward(db_session, telegram_id, today):
                    # Find any daily reward for this telegram_id today
                    result = await db_session.execute(
                        select(DailyReward)
                        .join(User, DailyReward.user_id == User.id)
                        .where(User.telegram_id == telegram_id)
                        .where(DailyReward.reward_date == today)
                    )
                    existing_reward = result.scalar_one_or_none()
                    if existing_reward:
                        return {
                            'points': existing_reward.points_rewarded,
                            'streak_count': existing_reward.streak_count,
                            'already_claimed': True
                        }
            
            # Check if already claimed today
            today_reward = await get_daily_reward(db_session, user_id, today)
            if today_reward:
                return {
                    'points': today_reward.points_rewarded,
                    'streak_count': today_reward.streak_count,
                    'already_claimed': True
                }
            
            # Calculate streak
            streak_count, is_new_streak = await RewardSystem.calculate_streak(user_id)
            
            # Calculate reward points
            reward_points = await RewardSystem.calculate_reward_points(streak_count)
            
            # Create reward record
            reward = await create_daily_reward(
                db_session,
                user_id,
                today,
                reward_points,
                streak_count
            )
            
            # Award points
            await PointsManager.award_daily_login(
                user_id,
                reward_points,
                streak_count
            )
            
            return {
                'points': reward_points,
                'streak_count': streak_count,
                'already_claimed': False
            }
    
    @staticmethod
    async def get_streak_info(user_id: int) -> dict:
        """
        Get user's current streak information.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with streak info:
            {
                'streak_count': int,
                'last_reward_date': Optional[date],
                'can_claim_today': bool
            }
        """
        async for db_session in get_db():
            today = date.today()
            
            # Check today's reward
            today_reward = await get_daily_reward(db_session, user_id, today)
            
            # Get last reward
            last_reward = await get_last_daily_reward(db_session, user_id)
            
            if today_reward:
                return {
                    'streak_count': today_reward.streak_count,
                    'last_reward_date': today_reward.reward_date,
                    'can_claim_today': False,
                    'points_claimed': today_reward.points_rewarded
                }
            
            if not last_reward:
                return {
                    'streak_count': 0,
                    'last_reward_date': None,
                    'can_claim_today': True
                }
            
            # Calculate if streak is still active
            last_date = last_reward.reward_date
            days_since_last = (today - last_date).days
            
            if days_since_last == 0:
                # Already claimed today
                return {
                    'streak_count': last_reward.streak_count,
                    'last_reward_date': last_date,
                    'can_claim_today': False,
                    'points_claimed': last_reward.points_rewarded
                }
            elif days_since_last == 1:
                # Can continue streak
                return {
                    'streak_count': last_reward.streak_count,
                    'last_reward_date': last_date,
                    'can_claim_today': True,
                    'next_streak': last_reward.streak_count + 1
                }
            else:
                # Streak broken
                return {
                    'streak_count': 0,
                    'last_reward_date': last_date,
                    'can_claim_today': True,
                    'streak_broken': True
                }




