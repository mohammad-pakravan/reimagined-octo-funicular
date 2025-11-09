"""
Redis-based matchmaking system for anonymous chat.
Handles user queues, matching, and queue count tracking.
"""
import json
import time
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
        }
        
        user_data_key = self._get_user_data_key(user_id)
        await self.redis.setex(
            user_data_key,
            settings.MATCHMAKING_TIMEOUT_SECONDS,
            json.dumps(user_data)
        )
        
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
        
        return json.loads(data)
    
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
            await self.remove_user_from_queue(user_id)
            await self.remove_user_from_queue(candidate_id)
            
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

