"""
Redis-based matchmaking system for anonymous chat.
Handles user queues, matching, and queue count tracking.

Also provides an in-memory implementation for low-traffic setups where
we want extremely fast matching without depending on Redis for the queue.
"""
import json
import random
import time
from dataclasses import dataclass
from typing import Optional, Dict, List

import redis.asyncio as redis

from config.settings import settings


class MatchmakingQueue:
    """Redis-based matchmaking queue system."""
    
    def __init__(self, redis_client: redis.Redis):
        """
        Initialize matchmaking queue with Redis client.
        
        Args:
            redis_client: Redis async client instance
        """
        self.redis = redis_client
        self.queue_prefix = "matchmaking:queue"
        self.user_data_prefix = "matchmaking:user"
        self.active_chats_prefix = "active:chats"
        self.blocked_users_prefix = "matchmaking:blocked"
    
    def _get_queue_key(self, gender: Optional[str] = None, city: Optional[str] = None) -> str:
        """
        Generate queue key based on filters.
        
        Args:
            gender: Gender filter
            city: City filter
            
        Returns:
            Redis key for the queue
        """
        filters = []
        if gender:
            filters.append(f"gender:{gender}")
        if city:
            filters.append(f"city:{city}")
        
        filter_str = ":".join(filters) if filters else "all"
        return f"{self.queue_prefix}:{filter_str}"
    
    def _get_user_data_key(self, user_id: int) -> str:
        """Get Redis key for user matchmaking data."""
        return f"{self.user_data_prefix}:{user_id}"
    
    async def add_user_to_queue(
        self,
        user_id: int,
        gender: Optional[str] = None,
        city: Optional[str] = None,
        age: Optional[int] = None,
        preferred_gender: Optional[str] = None,
        min_age: Optional[int] = None,
        max_age: Optional[int] = None,
        preferred_city: Optional[str] = None,
        is_premium: bool = False,
    ) -> bool:
        """
        Add user to matchmaking queue.
        
        Args:
            user_id: Telegram user ID
            gender: User's gender
            city: User's city
            age: User's age
            preferred_gender: Preferred partner gender
            min_age: Minimum preferred age
            max_age: Maximum preferred age
            preferred_city: Preferred partner city
            is_premium: Whether user has premium subscription
            
        Returns:
            True if added successfully
        """
        # Store user data
        user_data = {
            "user_id": user_id,
            "gender": gender,
            "city": city,
            "age": age,
            "preferred_gender": preferred_gender,
            "min_age": min_age,
            "max_age": max_age,
            "preferred_city": preferred_city,
            "joined_at": time.time(),
            "is_premium": is_premium,
        }
        
        user_data_key = self._get_user_data_key(user_id)
        
        # Log for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"DEBUG: add_user_to_queue for user {user_id}: preferred_gender = {preferred_gender}, type = {type(preferred_gender)}")
        logger.info(f"DEBUG: user_data before json.dumps: preferred_gender = {user_data.get('preferred_gender')}, type = {type(user_data.get('preferred_gender'))}")
        
        json_str = json.dumps(user_data)
        logger.info(f"DEBUG: json.dumps result: {json_str}")
        
        await self.redis.setex(
            user_data_key,
            settings.MATCHMAKING_TIMEOUT_SECONDS,
            json_str
        )
        
        # Verify what was stored
        stored_data = await self.redis.get(user_data_key)
        if stored_data:
            if isinstance(stored_data, bytes):
                stored_data = stored_data.decode('utf-8')
            stored_user_data = json.loads(stored_data)
            logger.info(f"DEBUG: Verified stored data for user {user_id}: preferred_gender = {stored_user_data.get('preferred_gender')}, type = {type(stored_user_data.get('preferred_gender'))}")
        
        # Add to appropriate queues based on what the user is looking for
        queues_to_join = []
        
        # If user has gender preference, add to that gender's queue
        if preferred_gender:
            queue_key = self._get_queue_key(gender=preferred_gender, city=preferred_city)
            queues_to_join.append(queue_key)
        
        # Also add to general queue
        general_queue = self._get_queue_key()
        queues_to_join.append(general_queue)
        
        # Add user to all relevant queues
        for queue_key in queues_to_join:
            await self.redis.sadd(queue_key, user_id)
            await self.redis.expire(queue_key, settings.MATCHMAKING_TIMEOUT_SECONDS)
        
        return True
    
    async def remove_user_from_queue(self, user_id: int) -> bool:
        """
        Remove user from all matchmaking queues.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if removed successfully
        """
        # Get all queue keys
        pattern = f"{self.queue_prefix}:*"
        async for queue_key in self.redis.scan_iter(match=pattern):
            await self.redis.srem(queue_key, user_id)
        
        # Remove user data
        user_data_key = self._get_user_data_key(user_id)
        await self.redis.delete(user_data_key)
        
        return True
    
    async def get_user_data(self, user_id: int) -> Optional[Dict]:
        """
        Get user matchmaking data.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            User data dictionary or None
        """
        user_data_key = self._get_user_data_key(user_id)
        data = await self.redis.get(user_data_key)
        
        if not data:
            return None
        
        # Decode bytes to string if needed
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        
        user_data = json.loads(data)
        
        # Log for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"DEBUG: get_user_data for user {user_id}: preferred_gender = {user_data.get('preferred_gender')}, type = {type(user_data.get('preferred_gender'))}")
        
        return user_data
    
    async def find_match(self, user_id: int) -> Optional[int]:
        """
        Find a match for a user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Matched user ID or None
        """
        user_data = await self.get_user_data(user_id)
        if not user_data:
            return None
        
        preferred_gender = user_data.get("preferred_gender")
        preferred_city = user_data.get("preferred_city")
        min_age = user_data.get("min_age")
        max_age = user_data.get("max_age")
        user_gender = user_data.get("gender")
        
        # Get all unique users in all queues
        pattern = f"{self.user_data_prefix}:*"
        all_candidates = set()
        
        async for key in self.redis.scan_iter(match=pattern):
            # Handle both bytes and string keys
            if isinstance(key, bytes):
                key_str = key.decode()
            else:
                key_str = str(key)
            
            candidate_id_str = key_str.split(":")[-1]
            try:
                candidate_id = int(candidate_id_str)
                if candidate_id != user_id:
                    all_candidates.add(candidate_id)
            except ValueError:
                continue
        
        if not all_candidates:
            return None
        
        # Try to find a matching candidate
        for candidate_id in all_candidates:
            candidate_data = await self.get_user_data(candidate_id)
            if not candidate_data:
                continue
            
            # Check if candidate is blocked (rejected/ended chat before)
            if await self.is_user_blocked(user_id, candidate_id):
                continue
            
            # Check bidirectional matching:
            # 1. User wants candidate's gender (or all)
            # 2. Candidate wants user's gender (or all)
            
            candidate_gender = candidate_data.get("gender")
            candidate_preferred_gender = candidate_data.get("preferred_gender")
            
            # Check if user wants candidate's gender
            user_wants_candidate = True
            if preferred_gender:
                # User has a gender preference
                if preferred_gender == "all":
                    user_wants_candidate = True  # User accepts all
                else:
                    user_wants_candidate = (candidate_gender == preferred_gender)
            else:
                # No preference, accept all
                user_wants_candidate = True
            
            # Check if candidate wants user's gender
            candidate_wants_user = True
            if candidate_preferred_gender:
                # Candidate has a gender preference
                if candidate_preferred_gender == "all":
                    candidate_wants_user = True  # Candidate accepts all
                else:
                    candidate_wants_user = (user_gender == candidate_preferred_gender)
            else:
                # No preference, accept all
                candidate_wants_user = True
            
            # Both must want each other (or accept all)
            if not (user_wants_candidate and candidate_wants_user):
                continue
            
            # City filter (optional)
            if preferred_city and candidate_data.get("city") != preferred_city:
                continue
            
            # Age filter (optional)
            candidate_age = candidate_data.get("age")
            if candidate_age:
                if min_age and candidate_age < min_age:
                    continue
                if max_age and candidate_age > max_age:
                    continue
            
            # Match found!
            # IMPORTANT: Don't remove user data yet - we need it in connect_users
            # Just remove from queues, but keep user data for now
            # We'll remove user data after connect_users is done
            
            # Remove from queues (but keep user data)
            pattern = f"{self.queue_prefix}:*"
            async for queue_key in self.redis.scan_iter(match=pattern):
                await self.redis.srem(queue_key, user_id)
                await self.redis.srem(queue_key, candidate_id)
            
            # Note: We don't delete user_data_key here - it will be deleted after connect_users
            # This way, connect_users can still access the user data
            
            return candidate_id
        
        return None
    
    async def get_queue_count(
        self,
        gender: Optional[str] = None,
        city: Optional[str] = None
    ) -> int:
        """
        Get count of users in queue.
        
        Args:
            gender: Gender filter
            city: City filter
            
        Returns:
            Number of users in queue
        """
        queue_key = self._get_queue_key(gender=gender, city=city)
        count = await self.redis.scard(queue_key)
        return count
    
    async def get_total_queue_count(self) -> int:
        """
        Get total count of all users in all queues (with deduplication).
        
        Returns:
            Total unique users in queues
        """
        pattern = f"{self.user_data_prefix}:*"
        count = 0
        async for _ in self.redis.scan_iter(match=pattern):
            count += 1
        return count

    async def get_all_user_ids(self) -> List[int]:
        """
        Get all user IDs currently present in the matchmaking queue.
        This is a helper for the matchmaking worker so it doesn't have to
        know about Redis internals.
        """
        pattern = f"{self.user_data_prefix}:*"
        user_ids: List[int] = []
        async for key in self.redis.scan_iter(match=pattern):
            if isinstance(key, bytes):
                key_str = key.decode()
            else:
                key_str = str(key)
            candidate_id_str = key_str.split(":")[-1]
            try:
                candidate_id = int(candidate_id_str)
            except ValueError:
                continue
            user_ids.append(candidate_id)
        return user_ids
    
    async def is_user_in_queue(self, user_id: int) -> bool:
        """
        Check if user is in any queue.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if user is in queue
        """
        user_data_key = self._get_user_data_key(user_id)
        exists = await self.redis.exists(user_data_key)
        return bool(exists)
    
    async def get_queue_count_by_gender(self) -> Dict[str, int]:
        """
        Get count of users in queue by gender.
        
        Returns:
            Dictionary with gender counts: {'male': 5, 'female': 3}
        """
        counts = {'male': 0, 'female': 0, 'other': 0}
        
        # Get all users in queue
        pattern = f"{self.user_data_prefix}:*"
        async for key in self.redis.scan_iter(match=pattern):
            user_data = await self.get_user_data(int(key.decode().split(":")[-1]) if isinstance(key, bytes) else int(str(key).split(":")[-1]))
            if user_data:
                gender = user_data.get("gender")
                if gender in counts:
                    counts[gender] += 1
        
        return counts
    
    def _get_blocked_users_key(self, user_id: int) -> str:
        """Get Redis key for user's blocked users list."""
        return f"{self.blocked_users_prefix}:{user_id}"
    
    async def add_blocked_user(self, user_id: int, blocked_user_id: int, ttl: int = 3600 * 7) -> bool:
        """
        Add a user to another user's blocked list (to prevent re-matching).
        
        Args:
            user_id: User who blocked/rejected/ended chat
            blocked_user_id: User who was blocked/rejected/ended chat with
            ttl: Time to live in seconds (default: 7 hours)
            
        Returns:
            True if added successfully
        """
        blocked_key = self._get_blocked_users_key(user_id)
        await self.redis.sadd(blocked_key, blocked_user_id)
        await self.redis.expire(blocked_key, ttl)
        
        # Also add reverse blocking (bidirectional)
        # If user A blocks user B, then B should also not match with A
        reverse_blocked_key = self._get_blocked_users_key(blocked_user_id)
        await self.redis.sadd(reverse_blocked_key, user_id)
        await self.redis.expire(reverse_blocked_key, ttl)
        
        return True
    
    async def is_user_blocked(self, user_id: int, blocked_user_id: int) -> bool:
        """
        Check if a user is blocked by another user.
        
        Args:
            user_id: User to check
            blocked_user_id: User who might be blocked
            
        Returns:
            True if blocked_user_id is in user_id's blocked list
        """
        blocked_key = self._get_blocked_users_key(user_id)
        is_member = await self.redis.sismember(blocked_key, blocked_user_id)
        return bool(is_member)
    
    async def remove_blocked_user(self, user_id: int, blocked_user_id: int) -> bool:
        """
        Remove a user from another user's blocked list.
        
        Args:
            user_id: User who unblocked
            blocked_user_id: User to unblock
            
        Returns:
            True if removed successfully
        """
        blocked_key = self._get_blocked_users_key(user_id)
        await self.redis.srem(blocked_key, blocked_user_id)
        
        # Also remove reverse blocking
        reverse_blocked_key = self._get_blocked_users_key(blocked_user_id)
        await self.redis.srem(reverse_blocked_key, user_id)
        
        return True


@dataclass
class UserQueueEntry:
    """In-memory representation of a user waiting in the matchmaking queue."""
    telegram_id: int
    gender: Optional[str]
    city: Optional[str]
    age: Optional[int]
    preferred_gender: Optional[str]
    joined_at: float
    # Filter preferences
    filter_same_age: bool = False  # Match with users within ±3 years
    filter_same_city: bool = False  # Match with users from same city
    filter_same_province: bool = False  # Match with users from same province
    province: Optional[str] = None  # User's province for filtering
    is_premium: bool = False  # Whether user has premium subscription
    last_probability_check: float = 0.0  # Timestamp of last probability check (for cooldown)


class InMemoryMatchmakingQueue:
    """
    In-memory matchmaking queue system.

    Designed for low-traffic setups: keeps two simple lists (boys/girls) in memory
    and uses the database to enforce the 7-hour no-rematch rule.
    """

    def __init__(self) -> None:
        # telegram_id -> UserQueueEntry
        self._user_data: Dict[int, UserQueueEntry] = {}
        # Queues by gender (telegram IDs, order preserved)
        self._boys_queue: List[int] = []
        self._girls_queue: List[int] = []

    async def add_user_to_queue(
        self,
        user_id: int,
        gender: Optional[str] = None,
        city: Optional[str] = None,
        age: Optional[int] = None,
        preferred_gender: Optional[str] = None,
        min_age: Optional[int] = None,  # kept for API compatibility, not used
        max_age: Optional[int] = None,  # kept for API compatibility, not used
        preferred_city: Optional[str] = None,  # kept for API compatibility, not used
        filter_same_age: bool = False,
        filter_same_city: bool = False,
        filter_same_province: bool = False,
        province: Optional[str] = None,
        is_premium: bool = False,
    ) -> bool:
        """Add user to in-memory matchmaking queue."""
        # Normalize gender to simple strings
        gender_norm = gender or "other"

        entry = UserQueueEntry(
            telegram_id=user_id,
            gender=gender_norm,
            city=city,
            age=age,
            preferred_gender=preferred_gender,
            joined_at=time.time(),
            filter_same_age=filter_same_age,
            filter_same_city=filter_same_city,
            filter_same_province=filter_same_province,
            province=province,
            is_premium=is_premium,
        )

        self._user_data[user_id] = entry

        if gender_norm == "male":
            if user_id not in self._boys_queue:
                self._boys_queue.append(user_id)
        elif gender_norm == "female":
            if user_id not in self._girls_queue:
                self._girls_queue.append(user_id)
        else:
            # For "other" or unknown genders, just append to girls queue as a fallback
            if user_id not in self._girls_queue:
                self._girls_queue.append(user_id)

        return True

    async def remove_user_from_queue(self, user_id: int) -> bool:
        """Remove user from in-memory queues and data."""
        self._user_data.pop(user_id, None)
        if user_id in self._boys_queue:
            self._boys_queue.remove(user_id)
        if user_id in self._girls_queue:
            self._girls_queue.remove(user_id)
        return True

    async def get_user_data(self, user_id: int) -> Optional[Dict]:
        """Return user matchmaking data in dict form (compatible with Redis version)."""
        entry = self._user_data.get(user_id)
        if not entry:
            return None

        return {
            "user_id": entry.telegram_id,
            "gender": entry.gender,
            "city": entry.city,
            "age": entry.age,
            "preferred_gender": entry.preferred_gender,
            "min_age": None,
            "max_age": None,
            "preferred_city": None,
            "joined_at": entry.joined_at,
        }

    async def _exists_boy_boy_pair(self) -> bool:
        """Check if there is at least one potential boy-boy pair in queue."""
        boys = [uid for uid in self._boys_queue if uid in self._user_data]
        return len(boys) >= 2

    async def find_match(self, user_id: int) -> Optional[int]:
        """
        Find a match for a user using in-memory queues and DB-based 7-hour rule.

        Rules:
        - Boys: try boy-boy first; if none, boy-girl.
        - Girls (random / preferred_gender is None): only match to boys when
          there is no boy-boy pair available.
        - Girls with explicit preferred_gender ('male'/'female'): follow that,
          still respecting the boy-boy priority for 'male'.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        entry = self._user_data.get(user_id)
        if not entry:
            return None

        gender = entry.gender or "other"
        preferred_gender = entry.preferred_gender

        # Helper to check if candidate matches filters
        def matches_filters(user_entry: UserQueueEntry, candidate_entry: UserQueueEntry) -> bool:
            """Check if candidate matches user's filter preferences."""
            # Check same age filter (±3 years)
            if user_entry.filter_same_age and user_entry.age and candidate_entry.age:
                age_diff = abs(user_entry.age - candidate_entry.age)
                if age_diff > 3:
                    return False
            
            # Check same city filter
            if user_entry.filter_same_city:
                if not user_entry.city or not candidate_entry.city:
                    return False
                if user_entry.city != candidate_entry.city:
                    return False
            
            # Check same province filter
            if user_entry.filter_same_province:
                if not user_entry.province or not candidate_entry.province:
                    return False
                if user_entry.province != candidate_entry.province:
                    return False
            
            return True

        # Helper to actually pick and reserve a partner from a given queue
        async def pick_from_queue(queue: List[int], required_gender: Optional[str] = None) -> Optional[int]:
            """
            Pick a partner from queue.
            
            Args:
                queue: The queue to pick from (boys or girls)
                required_gender: If specified, only match with this gender
            """
            for candidate_id in list(queue):
                if candidate_id == user_id:
                    continue
                if candidate_id not in self._user_data:
                    # stale id, clean up
                    queue.remove(candidate_id)
                    continue
                
                candidate_entry = self._user_data[candidate_id]
                
                # Check if candidate matches required gender (if specified)
                if required_gender and candidate_entry.gender != required_gender:
                    logger.debug(f"Skipping candidate {candidate_id}: gender mismatch (required={required_gender}, actual={candidate_entry.gender})")
                    continue
                
                # Check filters
                if not matches_filters(entry, candidate_entry):
                    continue  # Skip this candidate, try next
                
                # Reserve both in queues (remove from queue lists, keep user_data)
                if user_id in self._boys_queue:
                    self._boys_queue.remove(user_id)
                if user_id in self._girls_queue:
                    self._girls_queue.remove(user_id)
                if candidate_id in self._boys_queue:
                    self._boys_queue.remove(candidate_id)
                if candidate_id in self._girls_queue:
                    self._girls_queue.remove(candidate_id)
                return candidate_id
            return None

        # Boys: prefer boy-boy, then boy-girl
        if gender == "male":
            logger.debug(f"Boy {user_id} looking for match. Boys in queue: {len(self._boys_queue)}, Girls in queue: {len(self._girls_queue)}, preferred_gender: {preferred_gender}, is_premium: {entry.is_premium}")
            
            # If user explicitly wants a girl (paid/premium), match directly without probability
            if preferred_gender == "female":
                logger.info(f"Boy {user_id} explicitly wants GIRL. Premium={entry.is_premium}, Boys in queue={len(self._boys_queue)}, Girls in queue={len(self._girls_queue)}")
                # Premium users: SKIP boy-boy priority, match directly with girl if available
                # This ensures premium users get immediate access to real girls
                if entry.is_premium:
                    partner = await pick_from_queue(self._girls_queue, required_gender="female")
                    if partner:
                        partner_entry = self._user_data.get(partner)
                        partner_gender = partner_entry.gender if partner_entry else "unknown"
                        logger.info(f"Boy {user_id} (PREMIUM) matched with user {partner} (gender={partner_gender}) immediately (no boy-boy priority)")
                        return partner
                    logger.debug(f"Boy {user_id} (PREMIUM) wants girl but no girl available, staying in queue")
                    return None
                
                # Non-premium users: Match with girl (no probability check for explicit preference)
                partner = await pick_from_queue(self._girls_queue, required_gender="female")
                if partner:
                    partner_entry = self._user_data.get(partner)
                    partner_gender = partner_entry.gender if partner_entry else "unknown"
                    logger.info(f"Boy {user_id} (non-premium) matched with user {partner} (gender={partner_gender}) (explicit preference for GIRL)")
                    return partner
                logger.debug(f"Boy {user_id} (non-premium) wants girl but no girl available, staying in queue")
                return None
            
            # If user explicitly wants a boy, match with boy
            if preferred_gender == "male":
                partner = await pick_from_queue(self._boys_queue, required_gender="male")
                if partner:
                    logger.info(f"Boy {user_id} matched with boy {partner} (explicit preference)")
                    return partner
                logger.debug(f"Boy {user_id} wants boy but no boy available, staying in queue")
                return None
            
            # If preferred_gender is None (random search), apply probability restriction (unless premium)
            # Try boy-boy first
            partner = await pick_from_queue(self._boys_queue, required_gender="male")
            if partner:
                logger.info(f"Boy {user_id} matched with boy {partner} (random search, boy-boy match)")
                return partner
            # Then boy-girl
            # Premium users: no probability restriction even in random search
            # Non-premium users: check probability to make it harder (encouraging premium)
            if entry.is_premium:
                partner = await pick_from_queue(self._girls_queue, required_gender="female")
                if partner:
                    logger.info(f"Boy {user_id} matched with girl {partner} (random search, premium user, no probability check)")
                    return partner
            else:
                # Non-premium: check probability with cooldown
                current_time = time.time()
                time_since_last_check = current_time - entry.last_probability_check
                
                # Only check probability if cooldown has passed
                if time_since_last_check >= settings.PROBABILITY_CHECK_COOLDOWN_SECONDS:
                    probability_roll = random.random()
                    entry.last_probability_check = current_time  # Update timestamp
                    logger.debug(f"Boy {user_id} random search, probability roll: {probability_roll:.4f}, threshold: {settings.RANDOM_GIRL_BOY_MATCH_PROBABILITY}")
                    if probability_roll < settings.RANDOM_GIRL_BOY_MATCH_PROBABILITY:
                        partner = await pick_from_queue(self._girls_queue, required_gender="female")
                        if partner:
                            logger.info(f"Boy {user_id} matched with girl {partner} (random search, probability check passed: {probability_roll:.4f} < {settings.RANDOM_GIRL_BOY_MATCH_PROBABILITY})")
                            return partner
                    else:
                        logger.debug(f"Boy {user_id} probability check failed for girl match (random search, {probability_roll:.4f} >= {settings.RANDOM_GIRL_BOY_MATCH_PROBABILITY}), staying in queue (cooldown: {settings.PROBABILITY_CHECK_COOLDOWN_SECONDS}s)")
                else:
                    remaining_cooldown = settings.PROBABILITY_CHECK_COOLDOWN_SECONDS - time_since_last_check
                    logger.debug(f"Boy {user_id} probability check on cooldown ({remaining_cooldown:.1f}s remaining), staying in queue")
            # If probability check failed or on cooldown, stay in queue (will be checked again after cooldown)
            return None

        # Girls
        if gender == "female":
            logger.debug(f"Girl {user_id} looking for match. Boys in queue: {len(self._boys_queue)}, Girls in queue: {len(self._girls_queue)}, preferred_gender: {preferred_gender}, is_premium: {entry.is_premium}")
            
            # If user explicitly wants a boy (paid/premium), match directly without probability
            if preferred_gender == "male":
                # If there is any boy-boy pair possible, give priority to them
                if await self._exists_boy_boy_pair():
                    # Let worker handle boy-boy first; don't match this girl now
                    logger.debug(f"Girl {user_id} wants boy but boy-boy pair exists, waiting for boy-boy to match first")
                    return None
                # No boy-boy pair → match directly (no probability check for explicit preference)
                partner = await pick_from_queue(self._boys_queue, required_gender="male")
                if partner:
                    logger.info(f"Girl {user_id} matched with boy {partner} (explicit preference, no probability check)")
                    return partner
                # No boy found, stay in queue and wait
                logger.debug(f"Girl {user_id} wants boy but no boy available, staying in queue")
                return None
            
            # If user explicitly wants a girl, match with girl
            if preferred_gender == "female":
                partner = await pick_from_queue(self._girls_queue, required_gender="female")
                if partner:
                    logger.info(f"Girl {user_id} matched with girl {partner} (explicit preference)")
                    return partner
                logger.debug(f"Girl {user_id} wants girl but no girl available, staying in queue")
                return None
            
            # If preferred_gender is None (random search), apply probability restriction (unless premium)
            # If there is any boy-boy pair possible, give priority to them
            if await self._exists_boy_boy_pair():
                # Let worker handle boy-boy first; don't match this girl now
                logger.debug(f"Girl {user_id} random search but boy-boy pair exists, waiting for boy-boy to match first")
                return None
            # No boy-boy pair → check probability before matching girl with boy (only for random search)
            # Premium users: no probability restriction even in random search
            # Non-premium users: check probability to make it harder (encouraging premium)
            if entry.is_premium:
                partner = await pick_from_queue(self._boys_queue, required_gender="male")
                if partner:
                    logger.info(f"Girl {user_id} matched with boy {partner} (random search, premium user, no probability check)")
                    return partner
            else:
                # Non-premium: check probability with cooldown
                current_time = time.time()
                time_since_last_check = current_time - entry.last_probability_check
                
                # Only check probability if cooldown has passed
                if time_since_last_check >= settings.PROBABILITY_CHECK_COOLDOWN_SECONDS:
                    probability_roll = random.random()
                    entry.last_probability_check = current_time  # Update timestamp
                    logger.debug(f"Girl {user_id} random search, probability roll: {probability_roll:.4f}, threshold: {settings.RANDOM_GIRL_BOY_MATCH_PROBABILITY}")
                    if probability_roll < settings.RANDOM_GIRL_BOY_MATCH_PROBABILITY:
                        partner = await pick_from_queue(self._boys_queue, required_gender="male")
                        if partner:
                            logger.info(f"Girl {user_id} matched with boy {partner} (random search, probability check passed: {probability_roll:.4f} < {settings.RANDOM_GIRL_BOY_MATCH_PROBABILITY})")
                            return partner
                    else:
                        logger.debug(f"Girl {user_id} probability check failed for boy match (random search, {probability_roll:.4f} >= {settings.RANDOM_GIRL_BOY_MATCH_PROBABILITY}), staying in queue (cooldown: {settings.PROBABILITY_CHECK_COOLDOWN_SECONDS}s)")
                else:
                    remaining_cooldown = settings.PROBABILITY_CHECK_COOLDOWN_SECONDS - time_since_last_check
                    logger.debug(f"Girl {user_id} probability check on cooldown ({remaining_cooldown:.1f}s remaining), staying in queue")
            # If probability check failed or on cooldown, stay in queue
            # (will be checked again after cooldown)
            # Don't fallback to girl-girl in random search - wait for probability to pass
            return None

        # Other / unknown genders: simple FIFO across all
        # Build a combined list preserving order (boys first, then girls)
        combined = self._boys_queue + [uid for uid in self._girls_queue if uid not in self._boys_queue]
        for candidate_id in combined:
            if candidate_id == user_id:
                continue
            if candidate_id not in self._user_data:
                continue
            if user_id in self._boys_queue:
                self._boys_queue.remove(user_id)
            if user_id in self._girls_queue:
                self._girls_queue.remove(user_id)
            if candidate_id in self._boys_queue:
                self._boys_queue.remove(candidate_id)
            if candidate_id in self._girls_queue:
                self._girls_queue.remove(candidate_id)
            return candidate_id

        return None

    async def get_queue_count(
        self,
        gender: Optional[str] = None,
        city: Optional[str] = None,  # city not used in in-memory backend
    ) -> int:
        """Get queue count by gender (city is ignored for in-memory backend)."""
        if gender == "male":
            return len([uid for uid in self._boys_queue if uid in self._user_data])
        if gender == "female":
            return len([uid for uid in self._girls_queue if uid in self._user_data])
        # all
        return len(self._user_data)

    async def get_total_queue_count(self) -> int:
        """Get total number of unique users in queues."""
        return len(self._user_data)

    async def get_all_user_ids(self) -> List[int]:
        """Return all user IDs currently present in the in-memory queue."""
        return list(self._user_data.keys())

    async def is_user_in_queue(self, user_id: int) -> bool:
        """Check if user is present in the in-memory queue."""
        return user_id in self._user_data

    async def get_queue_count_by_gender(self) -> Dict[str, int]:
        """Get count of users in queue by gender."""
        counts = {"male": 0, "female": 0, "other": 0}
        for entry in self._user_data.values():
            g = entry.gender or "other"
            if g not in counts:
                g = "other"
            counts[g] += 1
        return counts

    # Block-list APIs are kept for compatibility but implemented as no-ops
    # for the in-memory backend, because the 7-hour rule is enforced via DB.

    async def add_blocked_user(self, user_id: int, blocked_user_id: int, ttl: int = 3600 * 7) -> bool:  # noqa: ARG002
        return True

    async def is_user_blocked(self, user_id: int, blocked_user_id: int) -> bool:  # noqa: ARG002
        return False

    async def remove_blocked_user(self, user_id: int, blocked_user_id: int) -> bool:  # noqa: ARG002
        return True

