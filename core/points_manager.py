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
            coins_base = await get_coins_for_activity(db_session, "chat_success")
            if coins_base is None:
                coins_base = settings.POINTS_CHAT_SUCCESS  # Fallback to settings
            break
        
        # Calculate actual coins with multiplier for display
        coins_user1_actual = await EventEngine.apply_points_multiplier(user1_id, coins_base, "chat_success")
        coins_user2_actual = await EventEngine.apply_points_multiplier(user2_id, coins_base, "chat_success")
        
        # Award points to both users (with event multiplier if active)
        await PointsManager.award_points(
            user1_id,
            coins_base,
            "chat_success",
            "Successful chat completion",
            user2_id
        )
        
        await PointsManager.award_points(
            user2_id,
            coins_base,
            "chat_success",
            "Successful chat completion",
            user1_id
        )
        
        # Get event info and send notifications if multiplier was applied
        async for db_session in get_db():
            from db.crud import get_user_by_id, get_active_events
            from aiogram import Bot
            
            # Get event info for user1
            user1_event_info = ""
            if coins_user1_actual > coins_base:
                events = await get_active_events(db_session, event_type="points_multiplier")
                if events:
                    event = events[0]
                    config = await EventEngine.parse_event_config(event)
                    apply_to_sources = config.get("apply_to_sources", [])
                    if not apply_to_sources or "chat_success" in apply_to_sources:
                        multiplier = config.get("multiplier", 1.0)
                        user1_event_info = f"\n\n🎁 به خاطر ایونت «{event.event_name}» ضریب {multiplier}x اعمال شد!\n✨ سکه پایه: {coins_base} → سکه نهایی: {coins_user1_actual}"
            
            # Get event info for user2
            user2_event_info = ""
            if coins_user2_actual > coins_base:
                events = await get_active_events(db_session, event_type="points_multiplier")
                if events:
                    event = events[0]
                    config = await EventEngine.parse_event_config(event)
                    apply_to_sources = config.get("apply_to_sources", [])
                    if not apply_to_sources or "chat_success" in apply_to_sources:
                        multiplier = config.get("multiplier", 1.0)
                        user2_event_info = f"\n\n🎁 به خاطر ایونت «{event.event_name}» ضریب {multiplier}x اعمال شد!\n✨ سکه پایه: {coins_base} → سکه نهایی: {coins_user2_actual}"
            
            # Send notifications
            user1 = await get_user_by_id(db_session, user1_id)
            user2 = await get_user_by_id(db_session, user2_id)
            
            bot = Bot(token=settings.BOT_TOKEN)
            try:
                if user1:
                    try:
                        await bot.send_message(
                            user1.telegram_id,
                            f"🎉 چت موفقیت‌آمیز بود!\n\n"
                            f"💰 {coins_user1_actual} سکه به حساب شما اضافه شد!{user1_event_info}\n\n"
                            f"💡 با چت‌های بیشتر، سکه بیشتری دریافت می‌کنی!"
                        )
                    except Exception:
                        pass
                
                if user2:
                    try:
                        await bot.send_message(
                            user2.telegram_id,
                            f"🎉 چت موفقیت‌آمیز بود!\n\n"
                            f"💰 {coins_user2_actual} سکه به حساب شما اضافه شد!{user2_event_info}\n\n"
                            f"💡 با چت‌های بیشتر، سکه بیشتری دریافت می‌کنی!"
                        )
                    except Exception:
                        pass
            finally:
                await bot.session.close()
            break
        
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
            coins_base = await get_coins_for_activity(db_session, "mutual_like")
            if coins_base is None:
                coins_base = settings.POINTS_MUTUAL_LIKE  # Fallback to settings
            break
        
        # Calculate actual coins with multiplier for display
        coins_user1_actual = await EventEngine.apply_points_multiplier(user1_id, coins_base, "mutual_like")
        coins_user2_actual = await EventEngine.apply_points_multiplier(user2_id, coins_base, "mutual_like")
        
        # Award points to both users
        await PointsManager.award_points(
            user1_id,
            coins_base,
            "mutual_like",
            "Mutual like",
            user2_id
        )
        
        await PointsManager.award_points(
            user2_id,
            coins_base,
            "mutual_like",
            "Mutual like",
            user1_id
        )
        
        # Get event info and send notifications if multiplier was applied
        async for db_session in get_db():
            from db.crud import get_user_by_id, get_active_events
            from aiogram import Bot
            
            # Get event info for user1
            user1_event_info = ""
            if coins_user1_actual > coins_base:
                events = await get_active_events(db_session, event_type="points_multiplier")
                if events:
                    event = events[0]
                    config = await EventEngine.parse_event_config(event)
                    apply_to_sources = config.get("apply_to_sources", [])
                    if not apply_to_sources or "mutual_like" in apply_to_sources:
                        multiplier = config.get("multiplier", 1.0)
                        user1_event_info = f"\n\n🎁 به خاطر ایونت «{event.event_name}» ضریب {multiplier}x اعمال شد!\n✨ سکه پایه: {coins_base} → سکه نهایی: {coins_user1_actual}"
            
            # Get event info for user2
            user2_event_info = ""
            if coins_user2_actual > coins_base:
                events = await get_active_events(db_session, event_type="points_multiplier")
                if events:
                    event = events[0]
                    config = await EventEngine.parse_event_config(event)
                    apply_to_sources = config.get("apply_to_sources", [])
                    if not apply_to_sources or "mutual_like" in apply_to_sources:
                        multiplier = config.get("multiplier", 1.0)
                        user2_event_info = f"\n\n🎁 به خاطر ایونت «{event.event_name}» ضریب {multiplier}x اعمال شد!\n✨ سکه پایه: {coins_base} → سکه نهایی: {coins_user2_actual}"
            
            # Send notifications
            user1 = await get_user_by_id(db_session, user1_id)
            user2 = await get_user_by_id(db_session, user2_id)
            
            bot = Bot(token=settings.BOT_TOKEN)
            try:
                if user1:
                    try:
                        await bot.send_message(
                            user1.telegram_id,
                            f"💕 لایک متقابل!\n\n"
                            f"✅ شما و طرف مقابل همدیگر را لایک کردید!\n\n"
                            f"💰 {coins_user1_actual} سکه به حساب شما اضافه شد!{user1_event_info}\n\n"
                            f"💡 با لایک‌های بیشتر، سکه بیشتری دریافت می‌کنی!"
                        )
                    except Exception:
                        pass
                
                if user2:
                    try:
                        await bot.send_message(
                            user2.telegram_id,
                            f"💕 لایک متقابل!\n\n"
                            f"✅ شما و طرف مقابل همدیگر را لایک کردید!\n\n"
                            f"💰 {coins_user2_actual} سکه به حساب شما اضافه شد!{user2_event_info}\n\n"
                            f"💡 با لایک‌های بیشتر، سکه بیشتری دریافت می‌کنی!"
                        )
                    except Exception:
                        pass
            finally:
                await bot.session.close()
            break
        
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
        # Get coins from database (must be set by admin)
        async for db_session in get_db():
            coins_referrer_base = await get_coins_for_activity(db_session, "referral_signup")
            if coins_referrer_base is None:
                # No fallback - admin must set this in database
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"referral_signup coins not set in database, using 0")
                coins_referrer_base = 0
            
            coins_referred_base = await get_coins_for_activity(db_session, "referral_referred_signup")
            if coins_referred_base is None:
                # No fallback - admin must set this in database
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"referral_referred_signup coins not set in database, using 0")
                coins_referred_base = 0
            break
        
        # Calculate actual coins with multiplier for display
        coins_referrer_actual = await EventEngine.apply_points_multiplier(referrer_id, coins_referrer_base, "referral_signup")
        coins_referred_actual = await EventEngine.apply_points_multiplier(referred_id, coins_referred_base, "referral_signup")
        
        # Check for event referral reward first (premium days)
        event_reward_given = await EventEngine.handle_referral_reward(referrer_id, referred_id)
        
        # Award points to referrer (if event didn't give premium, still give points)
        if not event_reward_given:
            await PointsManager.award_points(
                referrer_id,
                coins_referrer_base,
                "referral_signup",
                "Referral signup reward",
                referred_id
            )
        
        # Award points to referred user
        await PointsManager.award_points(
            referred_id,
            coins_referred_base,
            "referral_signup",
            "Welcome reward for using referral link",
            referrer_id
        )
        
        # Get event info and send notifications
        async for db_session in get_db():
            from db.crud import get_user_by_id, get_active_events
            from aiogram import Bot
            
            # Get event info for referrer if multiplier was applied
            referrer_event_info = ""
            if coins_referrer_actual > coins_referrer_base:
                events = await get_active_events(db_session, event_type="points_multiplier")
                if events:
                    event = events[0]
                    config = await EventEngine.parse_event_config(event)
                    apply_to_sources = config.get("apply_to_sources", [])
                    if not apply_to_sources or "referral_signup" in apply_to_sources:
                        multiplier = config.get("multiplier", 1.0)
                        referrer_event_info = f"\n\n🎁 به خاطر ایونت «{event.event_name}» ضریب {multiplier}x اعمال شد!\n✨ سکه پایه: {coins_referrer_base} → سکه نهایی: {coins_referrer_actual}"
            
            # Get event info for referred user if multiplier was applied
            referred_event_info = ""
            if coins_referred_actual > coins_referred_base:
                events = await get_active_events(db_session, event_type="points_multiplier")
                if events:
                    event = events[0]
                    config = await EventEngine.parse_event_config(event)
                    apply_to_sources = config.get("apply_to_sources", [])
                    if not apply_to_sources or "referral_signup" in apply_to_sources:
                        multiplier = config.get("multiplier", 1.0)
                        referred_event_info = f"\n\n🎁 به خاطر ایونت «{event.event_name}» ضریب {multiplier}x اعمال شد!\n✨ سکه پایه: {coins_referred_base} → سکه نهایی: {coins_referred_actual}"
            
            # Send notifications
            referrer = await get_user_by_id(db_session, referrer_id)
            referred = await get_user_by_id(db_session, referred_id)
            
            bot = Bot(token=settings.BOT_TOKEN)
            try:
                # Notify referrer (only if didn't get premium from event)
                if referrer and not event_reward_given:
                    # Check if referrer wants to receive referral notifications
                    if getattr(referrer, 'receive_referral_notifications', True):
                        try:
                            await bot.send_message(
                                referrer.telegram_id,
                                f"🎉 خبر خوب!\n\n"
                                f"✅ یکی از کاربرانی که از لینک دعوت شما استفاده کرده، عضو ربات شد!\n\n"
                                f"💰 {coins_referrer_actual} سکه به حساب شما اضافه شد!{referrer_event_info}\n\n"
                                f"💡 با دعوت کاربران بیشتر، سکه بیشتری دریافت می‌کنی!"
                            )
                        except Exception:
                            pass
                
                # Notify referred user
                if referred:
                    try:
                        await bot.send_message(
                            referred.telegram_id,
                            f"🎉 خوش آمدی!\n\n"
                            f"✅ با لینک دعوت عضو شدی!\n\n"
                            f"💰 {coins_referred_actual} سکه به حساب شما اضافه شد!{referred_event_info}\n\n"
                            f"💡 با تکمیل پروفایلت، سکه بیشتری دریافت می‌کنی!"
                        )
                    except Exception:
                        pass
            finally:
                await bot.session.close()
            break
        
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
        # Get coins from database (must be set by admin)
        async for db_session in get_db():
            coins_referrer = await get_coins_for_activity(db_session, "referral_profile_complete")
            if coins_referrer is None:
                # Fallback: try old referral_referrer setting
                coins_referrer = await get_coins_for_activity(db_session, "referral_referrer")
                if coins_referrer is None:
                    # No fallback - admin must set this in database
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"referral_profile_complete coins not set in database, using 0")
                    coins_referrer = 0
            
            # Get coins for referred user (use referral_referred_signup or referral_referred)
            coins_referred = await get_coins_for_activity(db_session, "referral_referred_signup")
            if coins_referred is None:
                coins_referred = await get_coins_for_activity(db_session, "referral_referred")
                if coins_referred is None:
                    # No fallback - admin must set this in database
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"referral_referred_signup/referral_referred coins not set in database, using 0")
                    coins_referred = 0
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
        # Get coins from database (must be set by admin)
        async for db_session in get_db():
            coins_referrer = await get_coins_for_activity(db_session, "referral_referrer")
            if coins_referrer is None:
                # No fallback - admin must set this in database
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"referral_referrer coins not set in database, using 0")
                coins_referrer = 0
            
            coins_referred = await get_coins_for_activity(db_session, "referral_referred")
            if coins_referred is None:
                # No fallback - admin must set this in database
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"referral_referred coins not set in database, using 0")
                coins_referred = 0
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




