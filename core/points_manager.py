"""
Points manager for handling user points, rewards, and conversions.
Provides high-level functions for awarding and spending points.
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from db.crud import (
    add_points,
    spend_points,
    get_user_points,
    get_points_history,
    get_or_create_user_points,
    get_coins_for_activity,
)
from db.database import get_db
from config.settings import settings
from core.event_engine import EventEngine


class PointsManager:
    """Manages user points and rewards."""
    
    @staticmethod
    async def award_points(
        user_id: int,
        points: int,
        source: str,
        description: Optional[str] = None,
        related_user_id: Optional[int] = None
    ) -> bool:
        """
        Award points to a user.
        Applies event multipliers if active.
        
        Args:
            user_id: User ID
            points: Points to award
            source: Source of points (e.g., 'daily_login', 'chat_success', 'mutual_like')
            description: Optional description
            related_user_id: Optional related user ID (for referrals, mutual likes, etc.)
            
        Returns:
            True if successful
        """
        # Apply event multiplier if active
        final_points = await EventEngine.apply_points_multiplier(user_id, points, source)
        
        async for db_session in get_db():
            return await add_points(
                db_session,
                user_id,
                final_points,
                "earned",
                source,
                description,
                related_user_id
            )
    
    @staticmethod
    async def spend_points_for_premium(
        user_id: int,
        days: int
    ) -> bool:
        """
        Spend points to get premium days.
        
        Args:
            user_id: User ID
            days: Number of premium days
            
        Returns:
            True if successful, False if insufficient points
        """
        required_points = days * settings.POINTS_TO_PREMIUM_DAY
        
        async for db_session in get_db():
            current_points = await get_user_points(db_session, user_id)
            
            if current_points < required_points:
                return False
            
            return await spend_points(
                db_session,
                user_id,
                required_points,
                "spent",
                "premium_purchase",
                f"Purchased {days} days of premium"
            )
    
    @staticmethod
    async def get_balance(user_id: int) -> int:
        """
        Get user's current points balance.
        
        Args:
            user_id: User ID
            
        Returns:
            Current points balance
        """
        async for db_session in get_db():
            return await get_user_points(db_session, user_id)
    
    @staticmethod
    async def award_chat_success(user1_id: int, user2_id: int) -> bool:
        """
        Award points for successful chat completion.
        Also tracks challenge progress.
        
        Args:
            user1_id: First user ID
            user2_id: Second user ID
            
        Returns:
            True if successful
        """
        # Get coins from database
        async for db_session in get_db():
            coins = await get_coins_for_activity(db_session, "chat_success")
            if coins is None:
                coins = settings.POINTS_CHAT_SUCCESS  # Fallback to settings
            break
        
        # Award points to both users (with event multiplier if active)
        await PointsManager.award_points(
            user1_id,
            coins,
            "chat_success",
            "Successful chat completion",
            user2_id
        )
        
        await PointsManager.award_points(
            user2_id,
            coins,
            "chat_success",
            "Successful chat completion",
            user1_id
        )
        
        # Track challenge progress for both users
        await EventEngine.track_challenge_progress(user1_id, "chat_count", 1)
        await EventEngine.track_challenge_progress(user2_id, "chat_count", 1)
        
        return True
    
    @staticmethod
    async def award_mutual_like(user1_id: int, user2_id: int) -> bool:
        """
        Award points for mutual like.
        
        Args:
            user1_id: First user ID
            user2_id: Second user ID
            
        Returns:
            True if successful
        """
        # Get coins from database
        async for db_session in get_db():
            coins = await get_coins_for_activity(db_session, "mutual_like")
            if coins is None:
                coins = settings.POINTS_MUTUAL_LIKE  # Fallback to settings
            break
        
        # Award points to both users
        await PointsManager.award_points(
            user1_id,
            coins,
            "mutual_like",
            "Mutual like",
            user2_id
        )
        
        await PointsManager.award_points(
            user2_id,
            coins,
            "mutual_like",
            "Mutual like",
            user1_id
        )
        
        return True
    
    @staticmethod
    async def award_referral_signup(
        referrer_id: int,
        referred_id: int
    ) -> bool:
        """
        Award points for referral signup (when user starts the bot via referral link).
        
        Args:
            referrer_id: User who referred
            referred_id: User who was referred
            
        Returns:
            True if successful
        """
        # Get coins from database
        async for db_session in get_db():
            coins_referrer = await get_coins_for_activity(db_session, "referral_signup")
            if coins_referrer is None:
                coins_referrer = settings.POINTS_REFERRAL_REFERRER  # Fallback to settings
            
            coins_referred = await get_coins_for_activity(db_session, "referral_referred_signup")
            if coins_referred is None:
                coins_referred = settings.POINTS_REFERRAL_REFERRED  # Fallback to settings
            break
        
        # Check for event referral reward first (premium days)
        event_reward_given = await EventEngine.handle_referral_reward(referrer_id, referred_id)
        
        # Award points to referrer (if event didn't give premium, still give points)
        if not event_reward_given:
            await PointsManager.award_points(
                referrer_id,
                coins_referrer,
                "referral_signup",
                "Referral signup reward",
                referred_id
            )
        
        # Award points to referred user
        await PointsManager.award_points(
            referred_id,
            coins_referred,
            "referral_signup",
            "Welcome reward for using referral link",
            referrer_id
        )
        
        # Track challenge progress
        await EventEngine.track_challenge_progress(referrer_id, "referral_count", 1)
        
        return True
    
    @staticmethod
    async def award_referral_profile_complete(
        referrer_id: int,
        referred_id: int
    ) -> bool:
        """
        Award points to both referrer and referred user when referred user completes their profile.
        Profile is considered complete when username, age, city, and profile_image_url are set.
        
        Args:
            referrer_id: User who referred
            referred_id: User who completed their profile
            
        Returns:
            True if successful
        """
        # Get coins from database
        async for db_session in get_db():
            coins_referrer = await get_coins_for_activity(db_session, "referral_profile_complete")
            if coins_referrer is None:
                # Fallback: use old referral_referrer setting or default
                coins_referrer = await get_coins_for_activity(db_session, "referral_referrer")
                if coins_referrer is None:
                    coins_referrer = settings.POINTS_REFERRAL_REFERRER
            
            # Get coins for referred user (use referral_referred_signup or referral_referred)
            coins_referred = await get_coins_for_activity(db_session, "referral_referred_signup")
            if coins_referred is None:
                coins_referred = await get_coins_for_activity(db_session, "referral_referred")
                if coins_referred is None:
                    coins_referred = settings.POINTS_REFERRAL_REFERRED
            break
        
        # Check for event referral reward first (premium days)
        event_reward_given = await EventEngine.handle_referral_reward(referrer_id, referred_id)
        
        # Award points to referrer (if event didn't give premium, still give points)
        if not event_reward_given:
            await PointsManager.award_points(
                referrer_id,
                coins_referrer,
                "referral_profile_complete",
                "Referral profile completion reward",
                referred_id
            )
        
        # Award points to referred user
        await PointsManager.award_points(
            referred_id,
            coins_referred,
            "referral_profile_complete",
            "Profile completion reward for using referral link",
            referrer_id
        )
        
        # Track challenge progress
        await EventEngine.track_challenge_progress(referrer_id, "referral_count", 1)
        
        return True
    
    @staticmethod
    async def award_referral(
        referrer_id: int,
        referred_id: int
    ) -> bool:
        """
        Award points for referral (legacy method, kept for backward compatibility).
        This method is deprecated. Use award_referral_signup instead.
        
        Also checks for event referral rewards (premium days).
        
        Args:
            referrer_id: User who referred
            referred_id: User who was referred
            
        Returns:
            True if successful
        """
        # Get coins from database
        async for db_session in get_db():
            coins_referrer = await get_coins_for_activity(db_session, "referral_referrer")
            if coins_referrer is None:
                coins_referrer = settings.POINTS_REFERRAL_REFERRER  # Fallback to settings
            
            coins_referred = await get_coins_for_activity(db_session, "referral_referred")
            if coins_referred is None:
                coins_referred = settings.POINTS_REFERRAL_REFERRED  # Fallback to settings
            break
        
        # Check for event referral reward first (premium days)
        event_reward_given = await EventEngine.handle_referral_reward(referrer_id, referred_id)
        
        # Award points to referrer (if event didn't give premium, still give points)
        if not event_reward_given:
            await PointsManager.award_points(
                referrer_id,
                coins_referrer,
                "referral",
                "Referral reward",
                referred_id
            )
        
        # Award points to referred user
        await PointsManager.award_points(
            referred_id,
            coins_referred,
            "referral",
            "Welcome reward for using referral code",
            referrer_id
        )
        
        # Track challenge progress
        await EventEngine.track_challenge_progress(referrer_id, "referral_count", 1)
        
        return True
    
    @staticmethod
    async def award_daily_login(
        user_id: int,
        points: int,
        streak_count: int
    ) -> bool:
        """
        Award points for daily login.
        
        Args:
            user_id: User ID
            points: Points to award
            streak_count: Current streak count
            
        Returns:
            True if successful
        """
        return await PointsManager.award_points(
            user_id,
            points,
            "daily_login",
            f"Daily login reward (streak: {streak_count} days)"
        )
    
    @staticmethod
    async def get_history(user_id: int, limit: int = 50):
        """
        Get user's points history.
        
        Args:
            user_id: User ID
            limit: Maximum number of records to return
            
        Returns:
            List of points history records
        """
        async for db_session in get_db():
            return await get_points_history(db_session, user_id, limit)




