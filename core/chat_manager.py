"""
Chat manager for handling chat rooms, message routing, and media forwarding.
Manages active chat sessions and routes messages between users.
"""
from typing import Optional, Dict
import redis.asyncio as redis

from db.models import ChatRoom, User
from db.crud import (
    create_chat_room,
    get_active_chat_room_by_user,
    get_chat_room_by_id,
    end_chat_room,
    get_user_by_id,
)
from db.database import get_db


class ChatManager:
    """Manages chat rooms and message routing."""
    
    def __init__(self, redis_client: redis.Redis):
        """
        Initialize chat manager with Redis client.
        
        Args:
            redis_client: Redis async client instance
        """
        self.redis = redis_client
        self.active_chat_prefix = "active:chat"
    
    def _get_chat_key(self, chat_room_id: int) -> str:
        """Get Redis key for chat room."""
        return f"{self.active_chat_prefix}:{chat_room_id}"
    
    def _get_message_count_key(self, chat_room_id: int, user_id: int) -> str:
        """Get Redis key for user message count in a chat."""
        return f"chat:message_count:{chat_room_id}:{user_id}"
    
    def _get_message_ids_key(self, chat_room_id: int, user_id: int) -> str:
        """Get Redis key for storing message IDs for a user in a chat."""
        return f"chat:message_ids:{chat_room_id}:{user_id}"
    
    def _get_message_pair_key(self, chat_room_id: int, user_msg_id: int) -> str:
        """Get Redis key for storing message pair mapping (user_msg_id -> partner_msg_id)."""
        return f"chat:msg_pair:{chat_room_id}:{user_msg_id}"
    
    async def create_chat(
        self,
        user1_id: int,
        user2_id: int,
        db_session,
        user1_preferred_gender: Optional[str] = None,
        user2_preferred_gender: Optional[str] = None
    ) -> ChatRoom:
        """
        Create a new chat room.
        
        Args:
            user1_id: First user's database ID
            user2_id: Second user's database ID
            db_session: Database session
            user1_preferred_gender: First user's preferred gender (None means "all")
            user2_preferred_gender: Second user's preferred gender (None means "all")
            
        Returns:
            Created ChatRoom object
        """
        # Create chat room in database
        chat_room = await create_chat_room(db_session, user1_id, user2_id)
        
        # Store chat mapping in Redis for fast lookup
        chat_key = self._get_chat_key(chat_room.id)
        chat_data = {
            "user1_id": user1_id,
            "user2_id": user2_id,
            "chat_room_id": chat_room.id,
        }
        await self.redis.setex(chat_key, 86400, str(chat_data))  # 24 hours TTL
        
        # Store user -> chat room mapping for both users
        await self.redis.setex(f"user:chat:{user1_id}", 86400, str(chat_room.id))
        await self.redis.setex(f"user:chat:{user2_id}", 86400, str(chat_room.id))
        
        # Store preferred genders for coin deduction logic
        # Always store preferred_gender (even if None/"all") so we can check it later
        # Store "all" as explicit string to distinguish from None
        user1_pref_to_store = user1_preferred_gender if user1_preferred_gender is not None else "all"
        user2_pref_to_store = user2_preferred_gender if user2_preferred_gender is not None else "all"
        await self.redis.setex(f"chat:pref_gender:{chat_room.id}:{user1_id}", 86400, user1_pref_to_store)
        await self.redis.setex(f"chat:pref_gender:{chat_room.id}:{user2_id}", 86400, user2_pref_to_store)
        
        # Store chat cost status (whether coins were deducted at start)
        # This will be set when chat starts
        await self.redis.setex(f"chat:cost_deducted:{chat_room.id}:{user1_id}", 86400, "0")
        await self.redis.setex(f"chat:cost_deducted:{chat_room.id}:{user2_id}", 86400, "0")
        
        # Store private mode status (protect_content) for each user (default: False)
        await self.redis.setex(f"chat:private_mode:{chat_room.id}:{user1_id}", 86400, "0")
        await self.redis.setex(f"chat:private_mode:{chat_room.id}:{user2_id}", 86400, "0")
        
        return chat_room
    
    async def set_chat_cost_deducted(
        self,
        chat_room_id: int,
        user_id: int,
        deducted: bool = True
    ) -> None:
        """Mark that chat cost was deducted for a user."""
        cost_key = f"chat:cost_deducted:{chat_room_id}:{user_id}"
        await self.redis.setex(cost_key, 86400, "1" if deducted else "0")
    
    async def was_chat_cost_deducted(
        self,
        chat_room_id: int,
        user_id: int
    ) -> bool:
        """Check if chat cost was deducted for a user."""
        cost_key = f"chat:cost_deducted:{chat_room_id}:{user_id}"
        deducted = await self.redis.get(cost_key)
        return deducted.decode() == "1" if deducted else False
    
    async def get_user_preferred_gender(
        self,
        chat_room_id: int,
        user_id: int
    ) -> Optional[str]:
        """
        Get user's preferred gender for a chat room.
        Returns None if "all" was selected, or "male"/"female" if specific gender was selected.
        
        Args:
            chat_room_id: Chat room database ID
            user_id: User's database ID
            
        Returns:
            Preferred gender ("male", "female") or None if "all"
        """
        pref_key = f"chat:pref_gender:{chat_room_id}:{user_id}"
        pref_gender = await self.redis.get(pref_key)
        if not pref_gender:
            return None
        
        pref_gender_str = pref_gender.decode() if isinstance(pref_gender, bytes) else pref_gender
        
        # Convert "all" to None, keep "male" and "female" as is
        if pref_gender_str == "all":
            return None
        
        return pref_gender_str if pref_gender_str in ["male", "female"] else None
    
    async def set_private_mode(
        self,
        chat_room_id: int,
        user_id: int,
        enabled: bool = True
    ) -> None:
        """Set private mode (protect_content) for a user in a chat room."""
        private_key = f"chat:private_mode:{chat_room_id}:{user_id}"
        await self.redis.setex(private_key, 86400, "1" if enabled else "0")
    
    async def get_private_mode(
        self,
        chat_room_id: int,
        user_id: int
    ) -> bool:
        """Get private mode (protect_content) status for a user in a chat room."""
        private_key = f"chat:private_mode:{chat_room_id}:{user_id}"
        private_mode = await self.redis.get(private_key)
        return private_mode.decode() == "1" if private_mode else False
    
    async def get_partner_id(
        self,
        user_id: int,
        db_session
    ) -> Optional[int]:
        """
        Get partner's database ID for a user in active chat.
        
        Args:
            user_id: User's database ID
            db_session: Database session
            
        Returns:
            Partner's database ID or None
        """
        # First try Redis lookup
        chat_room_id = await self.redis.get(f"user:chat:{user_id}")
        
        if chat_room_id:
            chat_room_id = int(chat_room_id)
            chat_key = self._get_chat_key(chat_room_id)
            chat_data = await self.redis.get(chat_key)
            
            if chat_data:
                # Parse chat data (simplified, should use JSON)
                chat_room = await get_active_chat_room_by_user(db_session, user_id)
                if chat_room:
                    if chat_room.user1_id == user_id:
                        return chat_room.user2_id
                    else:
                        return chat_room.user1_id
        
        # Fallback to database lookup
        chat_room = await get_active_chat_room_by_user(db_session, user_id)
        if chat_room:
            if chat_room.user1_id == user_id:
                return chat_room.user2_id
            else:
                return chat_room.user1_id
        
        return None
    
    async def get_partner_telegram_id(
        self,
        user_id: int,
        db_session
    ) -> Optional[int]:
        """
        Get partner's Telegram ID for a user in active chat.
        
        Args:
            user_id: User's database ID
            db_session: Database session
            
        Returns:
            Partner's Telegram ID or None
        """
        partner_id = await self.get_partner_id(user_id, db_session)
        if not partner_id:
            return None
        
        partner_user = await get_user_by_id(db_session, partner_id)
        if partner_user:
            return partner_user.telegram_id
        
        return None
    
    async def increment_message_count(
        self,
        chat_room_id: int,
        user_id: int
    ) -> int:
        """
        Increment message count for a user in a chat room.
        
        Args:
            chat_room_id: Chat room database ID
            user_id: User's database ID
            
        Returns:
            New message count for the user
        """
        count_key = self._get_message_count_key(chat_room_id, user_id)
        new_count = await self.redis.incr(count_key)
        # Set expiration to 7 days (in case chat ends without cleanup)
        await self.redis.expire(count_key, 604800)
        return new_count
    
    async def get_message_count(
        self,
        chat_room_id: int,
        user_id: int
    ) -> int:
        """
        Get message count for a user in a chat room.
        
        Args:
            chat_room_id: Chat room database ID
            user_id: User's database ID
            
        Returns:
            Message count for the user (0 if not found)
        """
        count_key = self._get_message_count_key(chat_room_id, user_id)
        count = await self.redis.get(count_key)
        return int(count) if count else 0
    
    async def get_chat_message_counts(
        self,
        chat_room_id: int,
        user1_id: int,
        user2_id: int
    ) -> tuple[int, int]:
        """
        Get message counts for both users in a chat room.
        
        Args:
            chat_room_id: Chat room database ID
            user1_id: First user's database ID
            user2_id: Second user's database ID
            
        Returns:
            Tuple of (user1_count, user2_count)
        """
        user1_count = await self.get_message_count(chat_room_id, user1_id)
        user2_count = await self.get_message_count(chat_room_id, user2_id)
        return (user1_count, user2_count)
    
    async def clear_message_counts(
        self,
        chat_room_id: int,
        user1_id: int,
        user2_id: int
    ) -> None:
        """
        Clear message counts for both users in a chat room.
        
        Args:
            chat_room_id: Chat room database ID
            user1_id: First user's database ID
            user2_id: Second user's database ID
        """
        count_key1 = self._get_message_count_key(chat_room_id, user1_id)
        count_key2 = self._get_message_count_key(chat_room_id, user2_id)
        await self.redis.delete(count_key1)
        await self.redis.delete(count_key2)
    
    async def add_message_id(
        self,
        chat_room_id: int,
        user_id: int,
        message_id: int
    ) -> None:
        """
        Add a message ID to the list for a user in a chat room.
        
        Args:
            chat_room_id: Chat room database ID
            user_id: User's database ID
            message_id: Telegram message ID
        """
        import json
        message_ids_key = self._get_message_ids_key(chat_room_id, user_id)
        # Get existing message IDs
        existing = await self.redis.get(message_ids_key)
        if existing:
            message_ids = json.loads(existing)
        else:
            message_ids = []
        
        # Add new message ID
        message_ids.append(message_id)
        
        # Save back to Redis
        await self.redis.setex(message_ids_key, 604800, json.dumps(message_ids))  # 7 days TTL
    
    async def get_message_ids(
        self,
        chat_room_id: int,
        user_id: int
    ) -> list[int]:
        """
        Get all message IDs for a user in a chat room.
        
        Args:
            chat_room_id: Chat room database ID
            user_id: User's database ID
            
        Returns:
            List of message IDs
        """
        import json
        message_ids_key = self._get_message_ids_key(chat_room_id, user_id)
        existing = await self.redis.get(message_ids_key)
        if existing:
            return json.loads(existing)
        return []
    
    async def clear_message_ids(
        self,
        chat_room_id: int,
        user_id: int,
        user2_id: int = None
    ) -> None:
        """
        Clear message IDs for users in a chat room.
        
        Args:
            chat_room_id: Chat room database ID
            user_id: First user's database ID
            user2_id: Second user's database ID (optional, if None, only clear user_id)
        """
        message_ids_key1 = self._get_message_ids_key(chat_room_id, user_id)
        await self.redis.delete(message_ids_key1)
        
        if user2_id is not None:
            message_ids_key2 = self._get_message_ids_key(chat_room_id, user2_id)
            await self.redis.delete(message_ids_key2)
    
    async def end_chat(
        self,
        chat_room_id: int,
        db_session
    ) -> tuple[bool, tuple[int, int]]:
        """
        End a chat room.
        
        Args:
            chat_room_id: Chat room database ID
            db_session: Database session
            
        Returns:
            Tuple of (success, (user1_count, user2_count))
        """
        # Get chat room before ending to get user IDs
        chat_room = await get_chat_room_by_id(db_session, chat_room_id)
        
        if not chat_room:
            return False, (0, 0)
        
        # Save user IDs before ending
        user1_id = chat_room.user1_id
        user2_id = chat_room.user2_id
        
        # Get message counts before clearing
        message_counts = await self.get_chat_message_counts(chat_room_id, user1_id, user2_id)
        
        # Remove from Redis first (to prevent race conditions)
        chat_key = self._get_chat_key(chat_room_id)
        await self.redis.delete(chat_key)
        await self.redis.delete(f"user:chat:{user1_id}")
        await self.redis.delete(f"user:chat:{user2_id}")
        
        # Clear message counts
        await self.clear_message_counts(chat_room_id, user1_id, user2_id)
        
        # Don't clear message IDs immediately - keep them for user deletion request
        # They will be cleared after 7 days (TTL) or when user requests deletion
        
        # End in database
        success = await end_chat_room(db_session, chat_room_id)
        
        # Double-check Redis cleanup in case of any issues
        if success:
            await self.redis.delete(chat_key)
            await self.redis.delete(f"user:chat:{user1_id}")
            await self.redis.delete(f"user:chat:{user2_id}")
            await self.clear_message_counts(chat_room_id, user1_id, user2_id)
            # Don't clear message IDs - keep them for user deletion request
        
        # Return success and message counts for notification
        return success, message_counts
    
    async def is_chat_active(
        self,
        user_id: int,
        db_session
    ) -> bool:
        """
        Check if user has an active chat.
        
        Args:
            user_id: User's database ID
            db_session: Database session
            
        Returns:
            True if user has active chat
        """
        # First check Redis (fast)
        chat_room_id = await self.redis.get(f"user:chat:{user_id}")
        if chat_room_id:
            # Verify in database that chat is still active
            try:
                chat_room_id_int = int(chat_room_id)
                chat_room = await get_chat_room_by_id(db_session, chat_room_id_int)
                if chat_room and chat_room.is_active:
                    return True
                else:
                    # Chat room not active, clean up Redis
                    await self.redis.delete(f"user:chat:{user_id}")
            except (ValueError, TypeError):
                # Invalid chat_room_id, clean up Redis
                await self.redis.delete(f"user:chat:{user_id}")
        
        # Database check
        chat_room = await get_active_chat_room_by_user(db_session, user_id)
        if chat_room:
            # Chat exists in DB, update Redis cache
            chat_key = self._get_chat_key(chat_room.id)
            await self.redis.setex(chat_key, 3600, "1")  # Cache for 1 hour
            await self.redis.setex(f"user:chat:{user_id}", 3600, str(chat_room.id))
            return True
        
        return False
    
    async def update_video_call_info(
        self,
        chat_room_id: int,
        video_call_room_id: str,
        video_call_link: str,
        db_session
    ) -> bool:
        """
        Update chat room with video call information.
        
        Args:
            chat_room_id: Chat room database ID
            video_call_room_id: Video call room ID
            video_call_link: Video call link
            db_session: Database session
            
        Returns:
            True if updated successfully
        """
        from db.crud import update_chat_room_video_call
        
        success = await update_chat_room_video_call(
            db_session,
            chat_room_id,
            video_call_room_id,
            video_call_link
        )
        
        if success:
            # Update Redis cache
            chat_key = self._get_chat_key(chat_room_id)
            chat_data = await self.redis.get(chat_key)
            if chat_data:
                # Update with video call info (should use JSON properly)
                await self.redis.setex(chat_key, 86400, str(chat_data))
        
        return success

