"""
Background worker for matchmaking.
Periodically checks queue and connects matching users.
"""
import asyncio
import logging
from typing import Optional
from db.database import get_db
from db.crud import get_user_by_telegram_id, get_user_by_id
from core.matchmaking import MatchmakingQueue
from core.chat_manager import ChatManager
from config.settings import settings
from aiogram import Bot

logger = logging.getLogger(__name__)

matchmaking_queue = None
chat_manager = None
bot_instance = None


def set_matchmaking_queue(queue: MatchmakingQueue):
    """Set matchmaking queue instance."""
    global matchmaking_queue
    matchmaking_queue = queue


def set_chat_manager(manager: ChatManager):
    """Set chat manager instance."""
    global chat_manager
    chat_manager = manager


def set_bot(bot: Bot):
    """Set bot instance."""
    global bot_instance
    bot_instance = bot


async def check_and_match_users():
    """Check queue and match users periodically."""
    if not matchmaking_queue or not chat_manager or not bot_instance:
        return
    
    # Get all users in queue
    all_users = await matchmaking_queue.get_total_queue_count()
    if all_users < 2:
        return  # Need at least 2 users to match
    
    # Get pattern to find all users in queue
    pattern = f"matchmaking:user:*"
    processed_users = set()
    
    async for key in matchmaking_queue.redis.scan_iter(match=pattern):
        user_id_str = key.decode().split(":")[-1] if isinstance(key, bytes) else key.split(":")[-1]
        try:
            user_id = int(user_id_str)
        except ValueError:
            continue
        
        # Skip if already processed in this cycle
        if user_id in processed_users:
            continue
        
        # Check if user is still in queue (might have been matched)
        if not await matchmaking_queue.is_user_in_queue(user_id):
            continue
        
        # Try to find a match
        match_id = await matchmaking_queue.find_match(user_id)
        
        if match_id:
            # Match found! Connect users
            processed_users.add(user_id)
            processed_users.add(match_id)
            await connect_users(user_id, match_id)
            # Break to avoid processing more users in this cycle
            # (Let next cycle handle remaining users)
            break


async def connect_users(user1_telegram_id: int, user2_telegram_id: int):
    """Connect two matched users."""
    if not chat_manager or not bot_instance:
        logger.warning("chat_manager or bot_instance not set, cannot connect users")
        return
    
    async for db_session in get_db():
        try:
            user1 = await get_user_by_telegram_id(db_session, user1_telegram_id)
            user2 = await get_user_by_telegram_id(db_session, user2_telegram_id)
            
            if not user1 or not user2:
                logger.warning(f"User not found: user1={user1_telegram_id}, user2={user2_telegram_id}")
                return
            
            # Check if either user already has active chat
            if await chat_manager.is_chat_active(user1.id, db_session):
                logger.info(f"User {user1_telegram_id} already has active chat, skipping match")
                return
            if await chat_manager.is_chat_active(user2.id, db_session):
                logger.info(f"User {user2_telegram_id} already has active chat, skipping match")
                return
            
            # Create chat room
            chat_room = await chat_manager.create_chat(user1.id, user2.id, db_session)
            
            # Notify both users
            from bot.keyboards.reply import get_chat_reply_keyboard
            
            await bot_instance.send_message(
                user1.telegram_id,
                "✅ هم‌چت پیدا شد! شما الان به هم متصل شدید.\n\n"
                "شروع به چت کنید:",
                reply_markup=get_chat_reply_keyboard()
            )
            
            await bot_instance.send_message(
                user2.telegram_id,
                "✅ هم‌چت پیدا شد! شما الان به هم متصل شدید.\n\n"
                "شروع به چت کنید:",
                reply_markup=get_chat_reply_keyboard()
            )
            
            logger.info(f"Successfully matched and connected users: {user1_telegram_id} <-> {user2_telegram_id}")
        except Exception as e:
            # Log error but continue
            logger.error(f"Error connecting users {user1_telegram_id} and {user2_telegram_id}: {e}", exc_info=True)
        
        break


async def run_matchmaking_worker():
    """Run matchmaking worker in background."""
    while True:
        try:
            await check_and_match_users()
        except Exception as e:
            print(f"Matchmaking worker error: {e}")
        
        # Check every 3 seconds
        await asyncio.sleep(3)

