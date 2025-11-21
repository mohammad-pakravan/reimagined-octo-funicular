"""
Main entry point for the Telegram bot.
Initializes bot, database, Redis, handlers, and FastAPI server.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
import redis.asyncio as redis
from fastapi import FastAPI
import uvicorn

from config.settings import settings
from db.database import init_db, close_db, get_db
from core.matchmaking import MatchmakingQueue, InMemoryMatchmakingQueue
from core.chat_manager import ChatManager
from utils.rate_limiter import MessageRateLimiter
from utils.user_activity import UserActivityTracker
from bot.middlewares.activity_tracker import ActivityTrackerMiddleware

# Import handlers
from bot.handlers import start, registration, chat, message, premium, admin, reply, profile
import bot.handlers.profile_view as profile_view
import bot.handlers.my_profile as my_profile
import bot.handlers.direct_message as direct_message
import bot.handlers.dm_list as dm_list
import bot.handlers.chat_request as chat_request
import bot.handlers.daily_reward as daily_reward
import bot.handlers.points as points
import bot.handlers.referral as referral
import bot.handlers.achievements as achievements
import bot.handlers.leaderboard as leaderboard
import bot.handlers.anonymous_call as anonymous_call
import bot.handlers.premium_plan_admin as premium_plan_admin
from bot.middlewares.rate_limit import RateLimitMiddleware
from bot.middlewares.channel_check import ChannelCheckMiddleware

# Import API
from api.video_call import app as fastapi_app, set_redis_client as set_api_redis

# Import matchmaking worker
from core.matchmaking_worker import set_matchmaking_queue as set_worker_queue, set_chat_manager as set_worker_chat_manager, set_bot as set_worker_bot, run_matchmaking_worker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
redis_client = None
matchmaking_queue = None
chat_manager = None
rate_limiter = None
activity_tracker = None


async def setup_redis():
    """Setup Redis connection with connection pooling."""
    global redis_client
    
    try:
        # Create Redis connection pool for better performance
        redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
            decode_responses=False,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
        
        # Test connection
        await redis_client.ping()
        logger.info("✅ Redis connected successfully with connection pooling")
        
        return redis_client
    except Exception as e:
        logger.error(f"❌ Failed to connect to Redis: {e}")
        raise


async def setup_matchmaking():
    """Setup matchmaking queue."""
    global matchmaking_queue, redis_client
    
    # For Redis-based storage we still need a Redis client; for in-memory backend
    # we only use Redis for other features (FSM, rate limiting, etc.).
    if not redis_client:
        redis_client = await setup_redis()
    
    if getattr(settings, "MATCHMAKING_BACKEND", "redis") == "memory":
        matchmaking_queue = InMemoryMatchmakingQueue()
        logger.info("✅ Matchmaking queue initialized (in-memory backend)")
    else:
        matchmaking_queue = MatchmakingQueue(redis_client)
        logger.info("✅ Matchmaking queue initialized (redis backend)")
    
    return matchmaking_queue


async def setup_chat_manager():
    """Setup chat manager."""
    global chat_manager, redis_client
    
    if not redis_client:
        redis_client = await setup_redis()
    
    chat_manager = ChatManager(redis_client)
    logger.info("✅ Chat manager initialized")
    
    return chat_manager


async def setup_rate_limiter():
    """Setup rate limiter."""
    global rate_limiter, redis_client
    
    if not redis_client:
        redis_client = await setup_redis()
    
    rate_limiter = MessageRateLimiter(redis_client)
    logger.info("✅ Rate limiter initialized")
    
    return rate_limiter


async def setup_activity_tracker():
    """Setup activity tracker."""
    global activity_tracker, redis_client
    
    if not redis_client:
        redis_client = await setup_redis()
    
    activity_tracker = UserActivityTracker(redis_client)
    logger.info("✅ Activity tracker initialized")
    
    return activity_tracker


async def setup_bot():
    """Setup and configure the Telegram bot."""
    # Initialize bot
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Setup Redis first (needed for RedisStorage)
    await setup_redis()
    
    # Initialize dispatcher with Redis storage for horizontal scaling
    # RedisStorage accepts redis client directly in aiogram 3.x
    storage = RedisStorage(redis=redis_client)
    dp = Dispatcher(storage=storage)
    
    # Setup broadcast processor
    from core.broadcast_processor import BroadcastProcessor
    broadcast_processor = BroadcastProcessor(bot)
    
    # Store broadcast processor for scheduler
    dp['broadcast_processor'] = broadcast_processor
    
    # Setup matchmaking, chat manager, rate limiter, and activity tracker
    await setup_matchmaking()
    await setup_chat_manager()
    await setup_rate_limiter()
    await setup_activity_tracker()
    
    # Set instances in handlers
    chat.set_matchmaking_queue(matchmaking_queue)
    chat.set_chat_manager(chat_manager)
    message.set_chat_manager(chat_manager)
    message.set_rate_limiter(rate_limiter)
    reply.set_chat_manager(chat_manager)
    profile.set_chat_manager(chat_manager)
    anonymous_call.set_redis_client(redis_client)
    # Set chat manager for game handler
    from bot.handlers.game import set_chat_manager as set_game_chat_manager
    set_game_chat_manager(chat_manager)
    chat_request.set_redis_client(redis_client)
    
    # Set Redis client in API
    set_api_redis(redis_client)
    
    # Set instances in matchmaking worker
    set_worker_queue(matchmaking_queue)
    set_worker_chat_manager(chat_manager)
    set_worker_bot(bot)
    
    # Start matchmaking worker in background
    asyncio.create_task(run_matchmaking_worker())
    
    # Start activity checker worker in background
    asyncio.create_task(run_activity_checker())
    
    # Start broadcast processor worker in background
    asyncio.create_task(run_broadcast_processor(dp['broadcast_processor']))
    
    # Register middlewares
    dp.message.middleware(RateLimitMiddleware(rate_limiter))
    dp.callback_query.middleware(RateLimitMiddleware(rate_limiter))
    dp.message.middleware(ChannelCheckMiddleware())
    dp.callback_query.middleware(ChannelCheckMiddleware())
    # Activity tracker middleware (should be early to track all activity)
    dp.message.middleware(ActivityTrackerMiddleware(activity_tracker))
    dp.callback_query.middleware(ActivityTrackerMiddleware(activity_tracker))
    
    # Register routers (handlers)
    # Order matters! Registration should come before message handler
    dp.include_router(start.router)
    dp.include_router(registration.router)  # Registration should be checked first
    dp.include_router(profile_view.router)  # Profile view via /user_XXXXX
    dp.include_router(chat.router)
    dp.include_router(premium.router)
    import bot.handlers.admin as admin_handler
    dp.include_router(admin_handler.router)  # Admin handlers
    import bot.handlers.mandatory_channels as mandatory_channels
    dp.include_router(mandatory_channels.router)  # Mandatory channels handlers
    dp.include_router(profile.router)  # Profile interaction handlers
    dp.include_router(my_profile.router)  # My profile edit and management
    import bot.handlers.user_search as user_search
    dp.include_router(user_search.router)  # User search handlers (must be before message handler for inline queries)
    dp.include_router(dm_list.router)  # Direct message list handlers (must be before direct_message for reply handling)
    dp.include_router(direct_message.router)  # Direct message handlers
    dp.include_router(chat_request.router)  # Chat request handlers
    from bot.handlers import call_request
    dp.include_router(call_request.router)  # Call request handlers
    dp.include_router(daily_reward.router)  # Daily reward handlers
    dp.include_router(points.router)  # Points handlers
    import bot.handlers.events as events
    dp.include_router(events.router)  # Events handlers
    import bot.handlers.event_admin as event_admin
    dp.include_router(event_admin.router)  # Event admin handlers (must be before referral)
    dp.include_router(referral.router)  # Referral handlers
    dp.include_router(achievements.router)  # Achievements handlers
    dp.include_router(leaderboard.router)  # Leaderboard handlers
    dp.include_router(anonymous_call.router)  # Anonymous call handlers
    dp.include_router(premium_plan_admin.router)  # Premium plan admin handlers
    import bot.handlers.system_settings as system_settings
    dp.include_router(system_settings.router)  # System settings handlers
    dp.include_router(reply.router)  # Reply keyboard handlers
    import bot.handlers.help as help_handler
    dp.include_router(help_handler.router)  # Help menu handlers
    import bot.handlers.game as game
    dp.include_router(game.router)  # Game handlers (must be before message handler for dice/dart)
    dp.include_router(message.router)  # Message handler should be last
    
    # Set chat manager for handlers
    reply.set_chat_manager(chat_manager)
    chat_request.set_chat_manager(chat_manager)
    call_request.set_chat_manager(chat_manager)
    
    logger.info("✅ Bot handlers registered")
    
    return bot, dp


async def run_broadcast_processor(broadcast_processor):
    """Background task to process pending broadcast messages."""
    import logging
    logger = logging.getLogger(__name__)
    
    # Wait a bit before starting to ensure everything is initialized
    await asyncio.sleep(5)
    logger.info("📢 Broadcast processor worker started (checking every 15 seconds)")
    
    while True:
        try:
            await asyncio.sleep(15)  # Check every 15 seconds
            
            if not broadcast_processor:
                continue
            
            # Process pending broadcasts
            await broadcast_processor.process_pending_broadcasts()
            
        except Exception as e:
            logger.error(f"Error in broadcast processor: {e}", exc_info=True)
            await asyncio.sleep(60)  # Wait longer on error


async def run_activity_checker():
    """Background task to check and mark users as offline after 1 minute of inactivity."""
    import logging
    logger = logging.getLogger(__name__)
    
    while True:
        try:
            await asyncio.sleep(30)  # Check every 30 seconds
            
            if not activity_tracker or not redis_client:
                continue
            
            # Get all activity keys from Redis
            pattern = f"{activity_tracker.activity_prefix}:*"
            keys = []
            async for key in redis_client.scan_iter(match=pattern):
                if isinstance(key, bytes):
                    key = key.decode('utf-8')
                keys.append(key)
            
            # Check each key
            now = datetime.utcnow()
            for key in keys:
                try:
                    # Get timestamp from Redis
                    timestamp_str = await redis_client.get(key)
                    if not timestamp_str:
                        continue
                    
                    if isinstance(timestamp_str, bytes):
                        timestamp_str = timestamp_str.decode('utf-8')
                    
                    timestamp = float(timestamp_str)
                    last_activity = datetime.utcfromtimestamp(timestamp)
                    time_diff = (now - last_activity).total_seconds()
                    
                    # If more than 1 minute, user is offline (key will expire automatically)
                    # But we should update last_seen in database
                    if time_diff > 60:
                        # Extract telegram_id from key
                        telegram_id_str = key.split(":")[-1]
                        telegram_id = int(telegram_id_str)
                        
                        # Update last_seen in database
                        try:
                            async for db_session in get_db():
                                try:
                                    from db.crud import get_user_by_telegram_id
                                    user = await get_user_by_telegram_id(db_session, telegram_id)
                                    if user:
                                        user.last_seen = last_activity
                                        await db_session.commit()
                                except Exception as db_error:
                                    logger.warning(f"Error updating last_seen for user {telegram_id}: {db_error}")
                                    await db_session.rollback()
                                break
                        except Exception as db_error:
                            logger.warning(f"Error getting DB session for user {telegram_id}: {db_error}")
                except Exception as e:
                    logger.warning(f"Error processing activity key {key}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in activity checker: {e}", exc_info=True)
            await asyncio.sleep(60)  # Wait longer on error


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI app."""
    # Startup
    logger.info("🚀 Starting application...")
    
    # Initialize database
    try:
        await init_db()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
    
    # Run migrations
    try:
        from db.database import run_migration
        import os
        migration_file = os.path.join(os.path.dirname(__file__), "db", "migration_add_last_seen.sql")
        await run_migration(migration_file)
        migration_file = os.path.join(os.path.dirname(__file__), "db", "migration_add_default_chat_filter.sql")
        await run_migration(migration_file)
        migration_file = os.path.join(os.path.dirname(__file__), "db", "migration_add_is_virtual.sql")
        await run_migration(migration_file)
        migration_file = os.path.join(os.path.dirname(__file__), "db", "migration_create_virtual_profiles_table.sql")
        await run_migration(migration_file)
        logger.info("✅ Migrations completed")
    except Exception as e:
        logger.error(f"❌ Failed to run migrations: {e}")
    
    # Setup Redis
    await setup_redis()
    
    # Setup API Redis client
    set_api_redis(redis_client)
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down application...")
    
    # Close database
    try:
        await close_db()
        logger.info("✅ Database closed")
    except Exception as e:
        logger.error(f"❌ Error closing database: {e}")
    
    # Close Redis
    if redis_client:
        await redis_client.close()
        logger.info("✅ Redis closed")


# Note: FastAPI app lifespan is set up in run_fastapi


async def run_bot():
    """Run the Telegram bot."""
    bot, dp = await setup_bot()
    
    try:
        # Start polling
        logger.info("🤖 Bot is starting...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.error(f"❌ Bot error: {e}")
    finally:
        await bot.session.close()


async def run_fastapi():
    """Run FastAPI server."""
    # Set lifespan before running
    fastapi_app.router.lifespan_context = lifespan
    
    config = uvicorn.Config(
        fastapi_app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    """Main function to run bot and FastAPI concurrently."""
    # Run bot and FastAPI in parallel
    await asyncio.gather(
        run_bot(),
        run_fastapi(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Application stopped by user")
    except Exception as e:
        logger.error(f"❌ Application error: {e}")

