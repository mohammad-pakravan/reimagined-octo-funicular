#!/usr/bin/env python3
"""
Broadcast Processor for Bot
Processes pending broadcast messages from the queue
"""

import logging
import asyncio
import re
from typing import Dict, Any, List
from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter

from db.database import get_db
from db.models import BroadcastMessage, User
from utils.broadcast_service import BroadcastService

logger = logging.getLogger(__name__)


class BroadcastProcessor:
    """پردازشگر پیام‌های همگانی"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.broadcast_service = BroadcastService()

        # Rate limiting settings (based on BROADCAST_SYSTEM.md)
        self.messages_per_second = 15  # Conservative limit to keep bot responsive
        self.delay_between_messages = 1.0 / self.messages_per_second  # ~0.067 seconds
        self.batch_size = 1000  # Process in batches for better memory management

    async def process_pending_broadcasts(self):
        """پردازش پیام‌های همگانی در انتظار"""
        try:
            async for session in get_db():
                try:
                    pending_broadcasts = await self.broadcast_service.get_pending_broadcasts(session)

                    if not pending_broadcasts:
                        return

                    logger.info(f"Found {len(pending_broadcasts)} pending broadcasts")

                    for broadcast in pending_broadcasts:
                        await self._process_single_broadcast(broadcast)
                        
                    break
                except Exception as e:
                    logger.error(f"Error in broadcast session: {e}")
                    await session.rollback()
                    break

        except Exception as e:
            logger.error(f"Error processing pending broadcasts: {e}")

    async def _process_single_broadcast(self, broadcast: BroadcastMessage):
        """پردازش یک پیام همگانی"""
        try:
            logger.info(f"Processing broadcast {broadcast.id}: {broadcast.message_type}")

            async for session in get_db():
                try:
                    # Get active users
                    users = await self.broadcast_service.get_active_users(session)

                    total_users = len(users)

                    if total_users == 0:
                        logger.warning("No active users found for broadcast")
                        await self.broadcast_service.mark_broadcast_completed(
                            session, broadcast.id, sent_count=0, failed_count=0
                        )
                        break

                    # Send messages with rate limiting
                    sent_count = 0
                    failed_count = 0

                    logger.info(
                        f"Starting broadcast to {total_users} users (rate: {self.messages_per_second} msg/sec)"
                    )
                    estimated_time = total_users / self.messages_per_second / 60  # minutes
                    logger.info(f"Estimated completion time: {estimated_time:.1f} minutes")

                    for idx, user in enumerate(users, 1):
                        try:
                            # Send with automatic retry on FloodWait
                            success = await self._send_with_retry(user, broadcast, max_retries=3)

                            if success:
                                sent_count += 1
                            else:
                                failed_count += 1

                            # Log progress every 100 messages
                            if idx % 100 == 0:
                                logger.info(
                                    f"Broadcast progress: {idx}/{total_users} "
                                    f"({(idx/total_users)*100:.1f}%) - "
                                    f"Sent: {sent_count}, Failed: {failed_count}"
                                )

                            # Rate limiting delay
                            await asyncio.sleep(self.delay_between_messages)

                        except Exception as e:
                            failed_count += 1
                            logger.error(f"Failed to send broadcast to user {user.telegram_id}: {e}")

                        # Update progress in database every 500 messages
                        if idx % 500 == 0:
                            await self.broadcast_service.update_broadcast_progress(
                                session, broadcast.id, sent_count=sent_count, failed_count=failed_count
                            )

                    # Mark as completed
                    await self.broadcast_service.mark_broadcast_completed(
                        session, broadcast.id, sent_count=sent_count, failed_count=failed_count
                    )

                    logger.info(f"Broadcast {broadcast.id} completed: {sent_count} sent, {failed_count} failed")
                    
                    break
                except Exception as e:
                    logger.error(f"Error in broadcast processing session: {e}")
                    await session.rollback()
                    break

        except Exception as e:
            logger.error(f"Error processing broadcast {broadcast.id}: {e}")

    async def _send_message_to_user(self, user: User, broadcast: BroadcastMessage):
        """ارسال پیام به یک کاربر"""
        try:
            if broadcast.message_type == 'text':
                await self.bot.send_message(
                    chat_id=user.telegram_id,
                    text=broadcast.message_text,
                    parse_mode='HTML'
                )
            elif broadcast.message_type == 'photo' and broadcast.message_file_id:
                await self.bot.send_photo(
                    chat_id=user.telegram_id,
                    photo=broadcast.message_file_id,
                    caption=broadcast.message_caption,
                    parse_mode='HTML'
                )
            elif broadcast.message_type == 'video' and broadcast.message_file_id:
                await self.bot.send_video(
                    chat_id=user.telegram_id,
                    video=broadcast.message_file_id,
                    caption=broadcast.message_caption,
                    parse_mode='HTML'
                )
            elif broadcast.message_type == 'document' and broadcast.message_file_id:
                await self.bot.send_document(
                    chat_id=user.telegram_id,
                    document=broadcast.message_file_id,
                    caption=broadcast.message_caption,
                    parse_mode='HTML'
                )
            elif broadcast.message_type == 'audio' and broadcast.message_file_id:
                await self.bot.send_audio(
                    chat_id=user.telegram_id,
                    audio=broadcast.message_file_id,
                    caption=broadcast.message_caption,
                    parse_mode='HTML'
                )
            elif broadcast.message_type == 'voice' and broadcast.message_file_id:
                await self.bot.send_voice(
                    chat_id=user.telegram_id,
                    voice=broadcast.message_file_id,
                    caption=broadcast.message_caption,
                    parse_mode='HTML'
                )
            elif broadcast.message_type == 'video_note' and broadcast.message_file_id:
                await self.bot.send_video_note(
                    chat_id=user.telegram_id,
                    video_note=broadcast.message_file_id
                )
            elif broadcast.message_type == 'animation' and broadcast.message_file_id:
                await self.bot.send_animation(
                    chat_id=user.telegram_id,
                    animation=broadcast.message_file_id,
                    caption=broadcast.message_caption,
                    parse_mode='HTML'
                )
            elif broadcast.message_type == 'sticker' and broadcast.message_file_id:
                await self.bot.send_sticker(
                    chat_id=user.telegram_id,
                    sticker=broadcast.message_file_id
                )
            elif broadcast.message_type == 'forward' and broadcast.forwarded_from_chat_id and broadcast.forwarded_from_message_id:
                await self.bot.forward_message(
                    chat_id=user.telegram_id,
                    from_chat_id=broadcast.forwarded_from_chat_id,
                    message_id=broadcast.forwarded_from_message_id
                )
            else:
                raise ValueError(f"Invalid message type or missing data: {broadcast.message_type}")

        except Exception as e:
            logger.error(f"Error sending message to user {user.telegram_id}: {e}")
            raise

    def _extract_flood_wait_time(self, error_message: str) -> int:
        """استخراج زمان انتظار از خطای FloodWait"""
        # Try to extract wait time from error message
        # Common patterns: "Retry in X seconds", "Too Many Requests: retry after X"
        patterns = [
            r'retry after (\d+)',
            r'Retry in (\d+)',
            r'wait (\d+) second',
            r'(\d+) second'
        ]

        for pattern in patterns:
            match = re.search(pattern, error_message, re.IGNORECASE)
            if match:
                return int(match.group(1))

        # Default wait time if pattern not found
        return 60

    async def _send_with_retry(self, user: User, broadcast: BroadcastMessage, max_retries: int = 3):
        """ارسال پیام با retry در صورت خطا"""
        for attempt in range(max_retries):
            try:
                await self._send_message_to_user(user, broadcast)
                return True
            except TelegramRetryAfter as e:
                # FloodWait - wait and retry
                wait_time = e.retry_after
                logger.warning(
                    f"FloodWait on attempt {attempt + 1}/{max_retries}: waiting {wait_time}s"
                )
                await asyncio.sleep(wait_time)
                continue
            except TelegramForbiddenError as e:
                # User blocked bot or deactivated
                logger.debug(f"User {user.telegram_id} blocked the bot or is deactivated")
                return False
            except TelegramBadRequest as e:
                # Bad request (invalid file_id, chat not found, etc.)
                error_str = str(e)
                if "chat not found" in error_str.lower() or "user not found" in error_str.lower():
                    logger.debug(f"User {user.telegram_id} not found")
                    return False
                elif attempt < max_retries - 1:
                    logger.warning(f"Bad request on attempt {attempt + 1}/{max_retries}: {e}")
                    await asyncio.sleep(2)  # Wait 2 seconds before retry
                    continue
                else:
                    raise
            except Exception as e:
                # Other errors
                if attempt < max_retries - 1:
                    logger.warning(f"Error on attempt {attempt + 1}/{max_retries}: {e}")
                    await asyncio.sleep(2)  # Wait 2 seconds before retry
                    continue
                else:
                    raise

        return False

