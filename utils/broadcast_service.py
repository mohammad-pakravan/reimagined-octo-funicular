#!/usr/bin/env python3
"""
Broadcast Service for Telegram Bot
Handles broadcast message queue and processing
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import User, BroadcastMessage

logger = logging.getLogger(__name__)


class BroadcastService:
    """سرویس مدیریت پیام همگانی"""

    async def create_broadcast_message(
        self,
        session: AsyncSession,
        message_text: Optional[str],
        message_type: str,
        admin_id: int,
        message_file_id: Optional[str] = None,
        message_caption: Optional[str] = None,
        forwarded_from_chat_id: Optional[int] = None,
        forwarded_from_message_id: Optional[int] = None,
    ) -> BroadcastMessage:
        """ایجاد پیام همگانی جدید"""
        try:
            broadcast = BroadcastMessage(
                admin_id=admin_id,
                message_type=message_type,
                message_text=message_text,
                message_file_id=message_file_id,
                message_caption=message_caption,
                forwarded_from_chat_id=forwarded_from_chat_id,
                forwarded_from_message_id=forwarded_from_message_id,
                sent_count=0,
                failed_count=0,
                opened_count=0,
            )
            session.add(broadcast)
            await session.commit()
            await session.refresh(broadcast)
            logger.info(f"Broadcast message created: {broadcast.id}")
            return broadcast
        except Exception as e:
            await session.rollback()
            logger.error(f"Error creating broadcast message: {e}")
            raise

    async def get_pending_broadcasts(self, session: AsyncSession) -> List[BroadcastMessage]:
        """دریافت پیام‌های همگانی در انتظار (sent_count = 0 و failed_count کم)"""
        try:
            result = await session.execute(
                select(BroadcastMessage)
                .where(BroadcastMessage.sent_count == 0)
                .where(BroadcastMessage.failed_count < 100)  # Skip if too many failures
                .order_by(BroadcastMessage.created_at)
            )
            broadcasts = result.scalars().all()
            return list(broadcasts)
        except Exception as e:
            logger.error(f"Error getting pending broadcasts: {e}")
            return []

    async def get_active_users(self, session: AsyncSession) -> List[User]:
        """دریافت لیست کاربران فعال (غیر بن شده)"""
        try:
            result = await session.execute(
                select(User)
                .where(User.is_banned == False)
                .where(User.is_active == True)
                .where(User.telegram_id.isnot(None))
            )
            users = result.scalars().all()
            logger.info(f"Found {len(list(users))} active users for broadcast")
            return list(users)
        except Exception as e:
            logger.error(f"Error getting active users: {e}")
            return []

    async def update_broadcast_progress(
        self,
        session: AsyncSession,
        broadcast_id: int,
        sent_count: int,
        failed_count: int,
    ) -> bool:
        """به‌روزرسانی پیشرفت ارسال پیام همگانی"""
        try:
            result = await session.execute(
                select(BroadcastMessage).where(BroadcastMessage.id == broadcast_id)
            )
            broadcast = result.scalar_one_or_none()

            if not broadcast:
                return False

            broadcast.sent_count = sent_count
            broadcast.failed_count = failed_count

            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            logger.error(f"Error updating broadcast progress: {e}")
            return False

    async def mark_broadcast_completed(
        self,
        session: AsyncSession,
        broadcast_id: int,
        sent_count: int,
        failed_count: int,
    ) -> bool:
        """علامت‌گذاری پیام همگانی به عنوان تکمیل شده"""
        try:
            result = await session.execute(
                select(BroadcastMessage).where(BroadcastMessage.id == broadcast_id)
            )
            broadcast = result.scalar_one_or_none()

            if not broadcast:
                return False

            broadcast.sent_count = sent_count
            broadcast.failed_count = failed_count

            await session.commit()
            logger.info(f"Broadcast {broadcast_id} marked as completed: {sent_count} sent, {failed_count} failed")
            return True
        except Exception as e:
            await session.rollback()
            logger.error(f"Error marking broadcast as completed: {e}")
            return False

    async def get_broadcast_stats(self, session: AsyncSession) -> Dict[str, int]:
        """آمار پیام‌های همگانی"""
        try:
            # Get total broadcasts
            result = await session.execute(select(BroadcastMessage))
            all_broadcasts = result.scalars().all()
            
            total = len(all_broadcasts)
            pending = sum(1 for b in all_broadcasts if b.sent_count == 0 and b.failed_count < 100)
            processing = sum(1 for b in all_broadcasts if b.sent_count > 0 and b.sent_count < 1000)  # Arbitrary threshold
            completed = sum(1 for b in all_broadcasts if b.sent_count >= 1000 or b.failed_count >= 100)

            return {
                'total': total,
                'pending': pending,
                'processing': processing,
                'completed': completed,
            }
        except Exception as e:
            logger.error(f"Error getting broadcast stats: {e}")
            return {}

    async def get_user_stats(self, session: AsyncSession) -> Dict[str, int]:
        """آمار کاربران"""
        try:
            result = await session.execute(select(User))
            all_users = result.scalars().all()
            
            total = len(all_users)
            active = sum(1 for u in all_users if not u.is_banned)

            return {
                'total': total,
                'active': active,
                'inactive': total - active
            }
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return {'total': 0, 'active': 0, 'inactive': 0}

