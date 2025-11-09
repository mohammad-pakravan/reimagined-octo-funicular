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
    
    async def create_chat(
        self,
        user1_id: int,
        user2_id: int,
        db_session
    ) -> ChatRoom:
        """
        Create a new chat room.
        
        Args:
            user1_id: First user's database ID
            user2_id: Second user's database ID
            db_session: Database session
            
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
        
        return chat_room
    
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
    
    async def end_chat(
        self,
        chat_room_id: int,
        db_session
    ) -> bool:
        """
        End a chat room.
        
        Args:
            chat_room_id: Chat room database ID
            db_session: Database session
            
        Returns:
            True if ended successfully
        """
        # Get chat room before ending to get user IDs
        chat_room = await get_chat_room_by_id(db_session, chat_room_id)
        
        if not chat_room:
            return False
        
        # Save user IDs before ending
        user1_id = chat_room.user1_id
        user2_id = chat_room.user2_id
        
        # Remove from Redis first (to prevent race conditions)
        chat_key = self._get_chat_key(chat_room_id)
        await self.redis.delete(chat_key)
        await self.redis.delete(f"user:chat:{user1_id}")
        await self.redis.delete(f"user:chat:{user2_id}")
        
        # End in database
        success = await end_chat_room(db_session, chat_room_id)
        
        # Double-check Redis cleanup in case of any issues
        if success:
            await self.redis.delete(chat_key)
            await self.redis.delete(f"user:chat:{user1_id}")
            await self.redis.delete(f"user:chat:{user2_id}")
        
        return success
    
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

