"""
Event Engine for executing event rules automatically.
Handles points multipliers, referral rewards, and challenge lotteries.
"""
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from db.crud import (
    get_active_events,
    get_or_create_event_participant,
    update_event_participant_progress,
    get_event_participant,
    create_event_reward,
    get_event_by_key,
    get_user_by_id,
    get_user_by_telegram_id,
    get_referral_count,
)
from db.database import get_db
from db.models import Event, EventParticipant


class EventEngine:
    """Manages event execution and rule application."""
    
    @staticmethod
    async def get_active_events_by_type(event_type: str) -> List[Event]:
        """Get active events of a specific type."""
        async for db_session in get_db():
            return await get_active_events(db_session, event_type=event_type)
    
    @staticmethod
    async def parse_event_config(event: Event) -> Dict[str, Any]:
        """Parse event config JSON."""
        if not event.config_json:
            return {}
        
        try:
            return json.loads(event.config_json)
        except json.JSONDecodeError:
            return {}
    
    @staticmethod
    async def apply_points_multiplier(
        user_id: int,
        base_points: int,
        source: str
    ) -> int:
        """
        Apply points multiplier from active events.
        
        Args:
            user_id: User ID
            base_points: Base points to award
            source: Points source (e.g., 'chat_success', 'daily_login')
            
        Returns:
            Final points after multiplier
        """
        async for db_session in get_db():
            events = await get_active_events(db_session, event_type="points_multiplier")
            
            if not events:
                return base_points
            
            # Get multiplier from first active event (can be enhanced to stack multipliers)
            event = events[0]
            config = await EventEngine.parse_event_config(event)
            
            multiplier = config.get("multiplier", 1.0)
            apply_to_sources = config.get("apply_to_sources", [])  # e.g., ['chat_success', 'daily_login']
            
            # Check if this source should be multiplied
            if apply_to_sources and source not in apply_to_sources:
                return base_points
            
            # Apply multiplier
            final_points = int(base_points * multiplier)
            
            # Track participation
            await get_or_create_event_participant(db_session, event.id, user_id)
            
            return final_points
    
    @staticmethod
    async def handle_referral_reward(
        referrer_id: int,
        referred_id: int
    ) -> bool:
        """
        Handle referral reward from active events.
        
        Args:
            referrer_id: User who referred
            referred_id: User who was referred
            
        Returns:
            True if reward was given
        """
        async for db_session in get_db():
            events = await get_active_events(db_session, event_type="referral_reward")
            
            if not events:
                return False
            
            # Get reward from first active event
            event = events[0]
            config = await EventEngine.parse_event_config(event)
            
            premium_days = config.get("premium_days", 0)
            
            if premium_days <= 0:
                return False
            
            # Check if referrer already received reward for this referral
            participant = await get_event_participant(db_session, event.id, referrer_id)
            
            # Get referral count to check if this is a new referral
            referral_count = await get_referral_count(db_session, referrer_id)
            
            # If participant exists, check if they've already received reward
            if participant and participant.has_received_reward:
                # Check if this is a new referral (referral count increased)
                # This is a simplified check - in production, you might want to track per-referral
                pass
            
            # Award premium days
            from db.crud import check_user_premium, create_premium_subscription
            from datetime import timedelta
            
            # Check current premium status
            user = await get_user_by_id(db_session, referrer_id)
            if not user:
                return False
            
            # Calculate new premium expiration
            now = datetime.utcnow()
            if user.premium_expires_at and user.premium_expires_at > now:
                # Extend existing premium
                new_expires_at = user.premium_expires_at + timedelta(days=premium_days)
            else:
                # Start new premium
                new_expires_at = now + timedelta(days=premium_days)
            
            # Update user premium
            user.is_premium = True
            user.premium_expires_at = new_expires_at
            await db_session.commit()
            await db_session.refresh(user)
            
            # Create premium subscription record
            await create_premium_subscription(
                db_session,
                referrer_id,
                "event_reward",
                f"event_{event.id}_referral_{referred_id}",
                0.0,  # Free from event
                start_date=now,
                end_date=new_expires_at
            )
            
            # Create event reward record
            await create_event_reward(
                db_session,
                event.id,
                referrer_id,
                "premium_days",
                premium_days,
                f"Referral reward from event: {event.event_name}"
            )
            
            # Track participation
            participant = await get_or_create_event_participant(db_session, event.id, referrer_id)
            participant.has_received_reward = True
            await db_session.commit()
            
            return True
    
    @staticmethod
    async def track_challenge_progress(
        user_id: int,
        metric: str,
        increment: int = 1
    ) -> List[EventParticipant]:
        """
        Track progress for challenge/lottery events.
        
        Args:
            user_id: User ID
            metric: Metric to track (e.g., 'chat_count', 'like_count')
            increment: Amount to increment
            
        Returns:
            List of updated participants
        """
        async for db_session in get_db():
            events = await get_active_events(db_session, event_type="challenge_lottery")
            
            updated_participants = []
            
            for event in events:
                config = await EventEngine.parse_event_config(event)
                target_metric = config.get("target_metric", "")
                
                # Check if this event tracks this metric
                if target_metric != metric:
                    continue
                
                # Update participant progress
                participant = await update_event_participant_progress(
                    db_session,
                    event.id,
                    user_id,
                    increment
                )
                
                if participant:
                    updated_participants.append(participant)
            
            return updated_participants
    
    @staticmethod
    async def execute_lottery(
        event_id: int,
        winner_count: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Execute lottery for challenge event.
        
        Args:
            event_id: Event ID
            winner_count: Number of winners
            
        Returns:
            List of winners with their rewards
        """
        async for db_session in get_db():
            from db.crud import get_event_by_id, get_event_participants
            
            event = await get_event_by_id(db_session, event_id)
            if not event or event.event_type != "challenge_lottery":
                return []
            
            config = await EventEngine.parse_event_config(event)
            target_value = config.get("target_value", 0)  # Minimum progress to be eligible
            
            # Get eligible participants (those who reached target)
            participants = await get_event_participants(
                db_session,
                event_id,
                skip=0,
                limit=1000,  # Get all participants
                order_by_progress=True
            )
            
            # Filter eligible participants
            eligible = [p for p in participants if p.progress_value >= target_value and p.is_eligible]
            
            if not eligible:
                return []
            
            # Select winners (top N by progress, or random if needed)
            # For simplicity, we'll select top N by progress
            winners = eligible[:winner_count]
            
            # Get reward config
            reward_type = config.get("reward_type", "premium_days")
            reward_value = config.get("reward_value", 30)  # e.g., 30 days premium
            
            winners_list = []
            
            for rank, participant in enumerate(winners, 1):
                # Award reward
                if reward_type == "premium_days":
                    # Award premium
                    user = await get_user_by_id(db_session, participant.user_id)
                    if user:
                        from datetime import timedelta
                        now = datetime.utcnow()
                        if user.premium_expires_at and user.premium_expires_at > now:
                            new_expires_at = user.premium_expires_at + timedelta(days=reward_value)
                        else:
                            new_expires_at = now + timedelta(days=reward_value)
                        
                        user.is_premium = True
                        user.premium_expires_at = new_expires_at
                        await db_session.commit()
                        
                        # Create subscription record
                        from db.crud import create_premium_subscription
                        await create_premium_subscription(
                            db_session,
                            participant.user_id,
                            "event_lottery",
                            f"event_{event_id}_lottery_rank_{rank}",
                            0.0,
                            now,
                            new_expires_at
                        )
                
                elif reward_type == "points":
                    # Award points (lazy import to avoid circular dependency)
                    from core.points_manager import PointsManager
                    await PointsManager.award_points(
                        participant.user_id,
                        reward_value,
                        "event_lottery",
                        f"Lottery winner (rank {rank}) from event: {event.event_name}",
                        None
                    )
                
                # Create reward record
                await create_event_reward(
                    db_session,
                    event_id,
                    participant.user_id,
                    reward_type,
                    reward_value,
                    f"Lottery winner (rank {rank}) from event: {event.event_name}",
                    is_lottery_winner=True,
                    lottery_rank=rank
                )
                
                winners_list.append({
                    "user_id": participant.user_id,
                    "rank": rank,
                    "progress": participant.progress_value,
                    "reward_type": reward_type,
                    "reward_value": reward_value
                })
            
            return winners_list
    
    @staticmethod
    async def get_user_event_progress(
        user_id: int,
        event_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get user's progress in events.
        
        Args:
            user_id: User ID
            event_id: Optional specific event ID
            
        Returns:
            List of event progress info
        """
        async for db_session in get_db():
            from db.crud import get_event_participant, get_all_events, get_active_events
            
            if event_id:
                events = [await get_event_by_id(db_session, event_id)]
                events = [e for e in events if e]
            else:
                events = await get_active_events(db_session)
            
            progress_list = []
            
            for event in events:
                participant = await get_event_participant(db_session, event.id, user_id)
                
                config = await EventEngine.parse_event_config(event)
                
                progress_info = {
                    "event_id": event.id,
                    "event_name": event.event_name,
                    "event_type": event.event_type,
                    "progress": participant.progress_value if participant else 0,
                    "has_received_reward": participant.has_received_reward if participant else False,
                    "is_eligible": participant.is_eligible if participant else True,
                }
                
                # Add target info for challenge events
                if event.event_type == "challenge_lottery":
                    progress_info["target_value"] = config.get("target_value", 0)
                    progress_info["target_metric"] = config.get("target_metric", "")
                
                progress_list.append(progress_info)
            
            return progress_list

