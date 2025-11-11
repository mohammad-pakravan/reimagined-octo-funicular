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
    """Check queue and match users periodically. Process multiple matches per cycle."""
    if not matchmaking_queue or not chat_manager or not bot_instance:
        return
    
    # Get all users in queue
    all_users = await matchmaking_queue.get_total_queue_count()
    if all_users < 2:
        return  # Need at least 2 users to match
    
    # Get pattern to find all users in queue
    pattern = f"matchmaking:user:*"
    processed_users = set()
    matches_found = []
    batch_size = settings.MATCHMAKING_WORKER_BATCH_SIZE
    
    # Collect potential matches
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
            # Match found! Add to list for batch processing
            processed_users.add(user_id)
            processed_users.add(match_id)
            matches_found.append((user_id, match_id))
            
            # Stop if we've reached batch size
            if len(matches_found) >= batch_size:
                break
    
    # Process all matches found in this cycle concurrently
    if matches_found:
        tasks = [connect_users(user1_id, user2_id) for user1_id, user2_id in matches_found]
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info(f"Processed {len(matches_found)} matches in this cycle")


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
                # Remove from queue if they have active chat
                await matchmaking_queue.remove_user_from_queue(user1_telegram_id)
                return
            if await chat_manager.is_chat_active(user2.id, db_session):
                logger.info(f"User {user2_telegram_id} already has active chat, skipping match")
                # Remove from queue if they have active chat
                await matchmaking_queue.remove_user_from_queue(user2_telegram_id)
                return
            
            # Get preferred genders from queue data
            # IMPORTANT: Get user data BEFORE removing from queue (find_match removes users from queue)
            # So we need to get data before find_match is called, or get it from a different source
            # Actually, find_match already removed users from queue, so user_data might be None
            # Let's try to get it anyway, but if it's None, we'll handle it
            user1_data = await matchmaking_queue.get_user_data(user1_telegram_id)
            user2_data = await matchmaking_queue.get_user_data(user2_telegram_id)
            
            # If user data is None (was removed from queue), try to get it from find_match's cache
            # Actually, we can't do that. The problem is that find_match removes users from queue
            # So we need to get user data BEFORE find_match removes it, or store it somewhere else
            # For now, let's log and see what happens
            if not user1_data:
                logger.warning(f"User {user1_telegram_id} data not found in queue (might have been removed)")
            if not user2_data:
                logger.warning(f"User {user2_telegram_id} data not found in queue (might have been removed)")
            
            # Get preferred gender - simple logic:
            # - If None or "all" → no coins deducted
            # - If "male" or "female" → coins deducted
            user1_pref_gender_raw = user1_data.get("preferred_gender") if user1_data else None
            user2_pref_gender_raw = user2_data.get("preferred_gender") if user2_data else None
            
            # Log raw values before normalization
            logger.info(f"DEBUG: User {user1_telegram_id} raw preferred_gender: {user1_pref_gender_raw}, type: {type(user1_pref_gender_raw)}")
            logger.info(f"DEBUG: User {user2_telegram_id} raw preferred_gender: {user2_pref_gender_raw}, type: {type(user2_pref_gender_raw)}")
            
            # Normalize: convert "all" or None to None, keep "male" and "female" as is
            # JSON stores None as null, so we need to handle both None and "all"
            # IMPORTANT: If raw value is "male" or "female", keep it as is!
            if user1_pref_gender_raw is None:
                user1_pref_gender = None
            elif user1_pref_gender_raw == "all":
                user1_pref_gender = None
            elif user1_pref_gender_raw in ["male", "female"]:
                user1_pref_gender = user1_pref_gender_raw
            else:
                # Unknown value, treat as None
                logger.warning(f"Unknown preferred_gender value for user {user1_telegram_id}: {user1_pref_gender_raw}")
                user1_pref_gender = None
            
            if user2_pref_gender_raw is None:
                user2_pref_gender = None
            elif user2_pref_gender_raw == "all":
                user2_pref_gender = None
            elif user2_pref_gender_raw in ["male", "female"]:
                user2_pref_gender = user2_pref_gender_raw
            else:
                # Unknown value, treat as None
                logger.warning(f"Unknown preferred_gender value for user {user2_telegram_id}: {user2_pref_gender_raw}")
                user2_pref_gender = None
            
            # Log for debugging
            logger.info(f"User {user1_telegram_id} preferred_gender from queue: {user1_data.get('preferred_gender') if user1_data else None}, normalized: {user1_pref_gender}")
            logger.info(f"User {user2_telegram_id} preferred_gender from queue: {user2_data.get('preferred_gender') if user2_data else None}, normalized: {user2_pref_gender}")
            
            # Check if chat room already exists (might have been created by try_find_match)
            # This prevents duplicate messages
            # Check if either user already has an active chat
            user1_has_chat = await chat_manager.is_chat_active(user1.id, db_session)
            user2_has_chat = await chat_manager.is_chat_active(user2.id, db_session)
            
            if user1_has_chat or user2_has_chat:
                # Chat already exists, don't create again
                logger.info(f"Chat already exists for users {user1_telegram_id} (has_chat: {user1_has_chat}) and {user2_telegram_id} (has_chat: {user2_has_chat}), skipping")
                # Remove from queue anyway
                await matchmaking_queue.remove_user_from_queue(user1_telegram_id)
                await matchmaking_queue.remove_user_from_queue(user2_telegram_id)
                return
            
            # Create chat room with preferred genders
            chat_room = await chat_manager.create_chat(
                user1.id, 
                user2.id, 
                db_session,
                user1_preferred_gender=user1_pref_gender,
                user2_preferred_gender=user2_pref_gender
            )
            
            # Log after creating chat room
            stored_user1_pref = await chat_manager.get_user_preferred_gender(chat_room.id, user1.id)
            stored_user2_pref = await chat_manager.get_user_preferred_gender(chat_room.id, user2.id)
            logger.info(f"After creating chat room {chat_room.id}: user1_pref_gender stored as: {stored_user1_pref}, user2_pref_gender stored as: {stored_user2_pref}")
            
            # Now remove user data from queue (after we've used it)
            await matchmaking_queue.remove_user_from_queue(user1_telegram_id)
            await matchmaking_queue.remove_user_from_queue(user2_telegram_id)
            
            # Notify both users and deduct coins if needed
            from bot.keyboards.reply import get_chat_reply_keyboard
            from db.crud import check_user_premium, spend_points, get_user_points
            from core.points_manager import PointsManager
            from db.crud import get_system_setting_value
            
            # Check premium status
            user1_premium = await check_user_premium(db_session, user1.id)
            user2_premium = await check_user_premium(db_session, user2.id)
            
            # Get chat cost from system settings
            chat_cost_str = await get_system_setting_value(db_session, 'chat_message_cost', '3')
            try:
                chat_cost = int(chat_cost_str)
            except (ValueError, TypeError):
                chat_cost = 3
            
            # Get user points
            user1_points = await get_user_points(db_session, user1.id)
            user2_points = await get_user_points(db_session, user2.id)
            
            # Deduct coins for non-premium users
            # Simple logic: if preferred_gender is "male" or "female", deduct coins
            # If preferred_gender is None (meaning "all"), don't deduct coins
            user1_coins_deducted = False
            user2_coins_deducted = False
            
            # Check if user1 selected specific gender (not "all")
            if not user1_premium and user1_pref_gender is not None and user1_pref_gender in ["male", "female"]:
                # Check if user has enough coins
                if user1_points >= chat_cost:
                    success = await spend_points(
                        db_session,
                        user1.id,
                        chat_cost,
                        "spent",
                        "chat_start",
                        f"Cost for starting chat (will be refunded if chat unsuccessful)"
                    )
                    if success:
                        user1_coins_deducted = True
                        await chat_manager.set_chat_cost_deducted(chat_room.id, user1.id, True)
                        user1_points -= chat_cost
            
            # Check if user2 selected specific gender (not "all")
            if not user2_premium and user2_pref_gender is not None and user2_pref_gender in ["male", "female"]:
                # Check if user has enough coins
                if user2_points >= chat_cost:
                    success = await spend_points(
                        db_session,
                        user2.id,
                        chat_cost,
                        "spent",
                        "chat_start",
                        f"Cost for starting chat (will be refunded if chat unsuccessful)"
                    )
                    if success:
                        user2_coins_deducted = True
                        await chat_manager.set_chat_cost_deducted(chat_room.id, user2.id, True)
                        user2_points -= chat_cost
            
            # Prepare messages with beautiful UI
            user1_msg = (
                "✅ هم‌چت پیدا شد!\n\n"
                "🎉 شما الان به هم متصل شدید!\n"
                "💬 می‌تونید شروع به چت کنید.\n\n"
            )
            
            user2_msg = (
                "✅ هم‌چت پیدا شد!\n\n"
                "🎉 شما الان به هم متصل شدید!\n"
                "💬 می‌تونید شروع به چت کنید.\n\n"
            )
            
            # Add cost information
            # Log for debugging - IMPORTANT: log the actual values
            logger.info(f"User {user1_telegram_id} - premium: {user1_premium}, pref_gender: {user1_pref_gender}, coins_deducted: {user1_coins_deducted}, points: {user1_points}")
            logger.info(f"User {user1_telegram_id} - pref_gender_raw was: {user1_pref_gender_raw}, normalized to: {user1_pref_gender}")
            
            if user1_premium:
                user1_msg += (
                    "💎 وضعیت: پریمیوم\n"
                    "💰 هزینه این چت: رایگان\n\n"
                )
            elif user1_pref_gender is None:
                # "all" was selected - no coins deducted
                user1_msg += (
                    "💰 هزینه این چت: رایگان\n"
                    "🌐 چون «همه» رو انتخاب کردی، هیچ سکه‌ای کسر نمی‌شه.\n\n"
                )
            elif user1_coins_deducted:
                # Specific gender selected and coins were deducted
                # Get required message count from system settings
                required_message_count_str = await get_system_setting_value(db_session, 'chat_success_message_count', '2')
                try:
                    required_message_count = int(required_message_count_str)
                except (ValueError, TypeError):
                    required_message_count = 2
                
                user1_msg += (
                    f"💰 هزینه این چت: {chat_cost} سکه\n"
                    f"💎 سکه‌های باقی‌مانده: {user1_points}\n\n"
                    f"💡 نکته: اگر چت موفقیت‌آمیز باشه (هر دو طرف حداقل {required_message_count} پیام بفرستن)، این سکه کسر می‌مونه.\n"
                    f"در غیر این صورت، سکه‌ها بهت برمی‌گرده.\n\n"
                    f"💎 با خرید پریمیوم:\n"
                    f"• هزینه چت: رایگان\n"
                    f"• نفر اول صف\n"
                    f"• امکانات بیشتر\n\n"
                )
            else:
                # Specific gender selected but coins weren't deducted (probably didn't have enough coins)
                user1_msg += (
                    f"⚠️ سکه کافی نداشتی!\n"
                    f"💰 برای شروع چت به {chat_cost} سکه نیاز داری.\n"
                    f"💎 سکه فعلی تو: {user1_points}\n\n"
                    f"💡 می‌تونی سکه‌هات رو به پریمیوم تبدیل کنی!\n\n"
                    f"💎 با خرید پریمیوم:\n"
                    f"• هزینه چت: رایگان\n"
                    f"• نفر اول صف\n"
                    f"• امکانات بیشتر\n\n"
                )
            
            if user2_premium:
                user2_msg += (
                    "💎 وضعیت: پریمیوم\n"
                    "💰 هزینه این چت: رایگان\n\n"
                )
            elif user2_pref_gender is None:
                # "all" was selected - no coins deducted
                user2_msg += (
                    "💰 هزینه این چت: رایگان\n"
                    "🌐 چون «همه» رو انتخاب کردی، هیچ سکه‌ای کسر نمی‌شه.\n\n"
                )
            elif user2_coins_deducted:
                # Specific gender selected and coins were deducted
                # Get required message count from system settings
                required_message_count_str = await get_system_setting_value(db_session, 'chat_success_message_count', '2')
                try:
                    required_message_count = int(required_message_count_str)
                except (ValueError, TypeError):
                    required_message_count = 2
                
                user2_msg += (
                    f"💰 هزینه این چت: {chat_cost} سکه\n"
                    f"💎 سکه‌های باقی‌مانده: {user2_points}\n\n"
                    f"💡 نکته: اگر چت موفقیت‌آمیز باشه (هر دو طرف حداقل {required_message_count} پیام بفرستن)، این سکه کسر می‌مونه.\n"
                    f"در غیر این صورت، سکه‌ها بهت برمی‌گرده.\n\n"
                    f"💎 با خرید پریمیوم:\n"
                    f"• هزینه چت: رایگان\n"
                    f"• نفر اول صف\n"
                    f"• امکانات بیشتر\n\n"
                )
            else:
                # Specific gender selected but coins weren't deducted (probably didn't have enough coins)
                user2_msg += (
                    f"⚠️ سکه کافی نداشتی!\n"
                    f"💰 برای شروع چت به {chat_cost} سکه نیاز داری.\n"
                    f"💎 سکه فعلی تو: {user2_points}\n\n"
                    f"💡 می‌تونی سکه‌هات رو به پریمیوم تبدیل کنی!\n\n"
                    f"💎 با خرید پریمیوم:\n"
                    f"• هزینه چت: رایگان\n"
                    f"• نفر اول صف\n"
                    f"• امکانات بیشتر\n\n"
                )
            
            
            await bot_instance.send_message(
                user1.telegram_id,
                user1_msg,
                reply_markup=get_chat_reply_keyboard()
            )
            
            await bot_instance.send_message(
                user2.telegram_id,
                user2_msg,
                reply_markup=get_chat_reply_keyboard()
            )
            
            logger.info(f"Successfully matched and connected users: {user1_telegram_id} <-> {user2_telegram_id}")
        except Exception as e:
            # Log error but continue
            logger.error(f"Error connecting users {user1_telegram_id} and {user2_telegram_id}: {e}", exc_info=True)
        
        break


async def run_matchmaking_worker():
    """Run matchmaking worker in background."""
    interval = settings.MATCHMAKING_WORKER_INTERVAL
    logger.info(f"Matchmaking worker started with interval: {interval} seconds, batch size: {settings.MATCHMAKING_WORKER_BATCH_SIZE}")
    
    while True:
        try:
            await check_and_match_users()
        except Exception as e:
            logger.error(f"Matchmaking worker error: {e}", exc_info=True)
        
        # Check at configured interval (default: 1 second)
        await asyncio.sleep(interval)

