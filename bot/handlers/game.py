"""
Game handlers for chat games with coin betting.
Games: Dice (تاس) and Dart (دارت)
"""
import json
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter

from db.database import get_db
from db.crud import (
    get_user_by_telegram_id,
    get_user_by_id,
    get_active_chat_room_by_user,
    check_user_premium,
    get_user_points,
    spend_points,
    add_points
)
from core.chat_manager import ChatManager
from bot.keyboards.reply import get_chat_reply_keyboard
from config.settings import settings

router = Router()

# Game emojis
DICE_EMOJI = "🎲"
DART_EMOJI = "🎯"
BASKETBALL_EMOJI = "🏀"
SLOT_MACHINE_EMOJI = "🎰"

# Game types
GAME_TYPE_DICE = "dice"
GAME_TYPE_DART = "dart"
GAME_TYPE_BASKETBALL = "basketball"
GAME_TYPE_SLOT_MACHINE = "slot_machine"

# Coin options
COIN_OPTIONS = [1, 2, 3, 4]


class GameStates(StatesGroup):
    """FSM states for game."""
    waiting_game_type = State()
    waiting_coin_amount = State()
    waiting_game_emoji = State()


# Global chat manager instance
chat_manager: ChatManager = None


def set_chat_manager(manager: ChatManager):
    """Set chat manager instance."""
    global chat_manager
    chat_manager = manager


def _get_game_request_key(chat_room_id: int) -> str:
    """Get Redis key for game request."""
    return f"game:request:{chat_room_id}"


def _get_game_active_key(chat_room_id: int) -> str:
    """Get Redis key for active game."""
    return f"game:active:{chat_room_id}"


def _get_game_emoji_key(chat_room_id: int, user_id: int) -> str:
    """Get Redis key for storing user's game emoji."""
    return f"game:emoji:{chat_room_id}:{user_id}"


async def get_game_request(chat_room_id: int) -> dict:
    """Get game request from Redis."""
    if not chat_manager:
        return None
    key = _get_game_request_key(chat_room_id)
    data = await chat_manager.redis.get(key)
    if data:
        return json.loads(data)
    return None


async def set_game_request(chat_room_id: int, game_data: dict, ttl: int = 300):
    """Set game request in Redis (5 minutes TTL)."""
    if not chat_manager:
        return False
    key = _get_game_request_key(chat_room_id)
    await chat_manager.redis.setex(key, ttl, json.dumps(game_data))
    return True


async def delete_game_request(chat_room_id: int):
    """Delete game request from Redis."""
    if not chat_manager:
        return
    key = _get_game_request_key(chat_room_id)
    await chat_manager.redis.delete(key)


async def set_active_game(chat_room_id: int, game_data: dict, ttl: int = 600):
    """Set active game in Redis (10 minutes TTL)."""
    if not chat_manager:
        return False
    key = _get_game_active_key(chat_room_id)
    await chat_manager.redis.setex(key, ttl, json.dumps(game_data))
    return True


async def get_active_game(chat_room_id: int) -> dict:
    """Get active game from Redis."""
    if not chat_manager:
        return None
    key = _get_game_active_key(chat_room_id)
    data = await chat_manager.redis.get(key)
    if data:
        return json.loads(data)
    return None


async def delete_active_game(chat_room_id: int):
    """Delete active game from Redis."""
    if not chat_manager:
        return
    key = _get_game_active_key(chat_room_id)
    await chat_manager.redis.delete(key)


async def set_user_game_emoji(chat_room_id: int, user_id: int, emoji: str, ttl: int = 600):
    """Store user's game emoji in Redis."""
    if not chat_manager:
        return False
    key = _get_game_emoji_key(chat_room_id, user_id)
    await chat_manager.redis.setex(key, ttl, emoji)
    return True


async def get_user_game_emoji(chat_room_id: int, user_id: int) -> str:
    """Get user's game emoji from Redis."""
    if not chat_manager:
        return None
    key = _get_game_emoji_key(chat_room_id, user_id)
    emoji = await chat_manager.redis.get(key)
    return emoji.decode() if emoji else None


async def delete_user_game_emoji(chat_room_id: int, user_id: int):
    """Delete user's game emoji from Redis."""
    if not chat_manager:
        return
    key = _get_game_emoji_key(chat_room_id, user_id)
    await chat_manager.redis.delete(key)


def get_game_type_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for selecting game type."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎲 تاس", callback_data="game:type:dice"),
            InlineKeyboardButton(text="🎯 دارت", callback_data="game:type:dart"),
        ],
        [
            InlineKeyboardButton(text="🏀 بسکتبال", callback_data="game:type:basketball"),
            InlineKeyboardButton(text="🎰 اسلوت", callback_data="game:type:slot_machine"),
        ],
        [
            InlineKeyboardButton(text="❌ لغو", callback_data="game:cancel"),
        ],
    ])
    return keyboard


def get_coin_amount_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for selecting coin amount."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 سکه", callback_data="game:coin:1"),
            InlineKeyboardButton(text="2 سکه", callback_data="game:coin:2"),
        ],
        [
            InlineKeyboardButton(text="3 سکه", callback_data="game:coin:3"),
            InlineKeyboardButton(text="4 سکه", callback_data="game:coin:4"),
        ],
        [
            InlineKeyboardButton(text="❌ لغو", callback_data="game:cancel"),
        ],
    ])
    return keyboard


def get_game_request_keyboard(chat_room_id: int) -> InlineKeyboardMarkup:
    """Get keyboard for accepting/rejecting game request."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ قبول", callback_data=f"game:accept:{chat_room_id}"),
            InlineKeyboardButton(text="❌ رد", callback_data=f"game:reject:{chat_room_id}"),
        ],
    ])
    return keyboard


@router.message(F.text == "🎮 بازی")
async def start_game(message: Message, state: FSMContext):
    """Start game - show game type selection."""
    user_id = message.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await message.answer("❌ کاربر یافت نشد.")
            return
        
        # Check if user has active chat
        chat_room = await get_active_chat_room_by_user(db_session, user.id)
        if not chat_room:
            await message.answer("❌ شما در حال حاضر یک چت فعال ندارید!")
            return
        
        # Check if there's already an active game
        active_game = await get_active_game(chat_room.id)
        if active_game:
            await message.answer("⚠️ یک بازی در حال انجام است. لطفاً صبر کنید.")
            return
        
        # Check if there's already a pending request
        game_request = await get_game_request(chat_room.id)
        if game_request:
            await message.answer("⚠️ یک درخواست بازی در انتظار است. لطفاً صبر کنید.")
            return
        
        # Show game type selection
        await message.answer(
            "🎮 بازی با شرط‌بندی\n\n"
            "نوع بازی را انتخاب کنید:",
            reply_markup=get_game_type_keyboard()
        )
        
        await state.set_state(GameStates.waiting_game_type)
        break


@router.callback_query(F.data.startswith("game:type:"), StateFilter(GameStates.waiting_game_type))
async def select_game_type(callback: CallbackQuery, state: FSMContext):
    """Handle game type selection."""
    game_type = callback.data.split(":")[2]  # dice or dart
    
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        chat_room = await get_active_chat_room_by_user(db_session, user.id)
        if not chat_room:
            await callback.answer("❌ شما در حال حاضر یک چت فعال ندارید!", show_alert=True)
            return
        
        # Store game type in state
        await state.update_data(game_type=game_type)
        
        # Show coin amount selection
        game_names = {
            GAME_TYPE_DICE: "تاس",
            GAME_TYPE_DART: "دارت",
            GAME_TYPE_BASKETBALL: "بسکتبال",
            GAME_TYPE_SLOT_MACHINE: "اسلوت"
        }
        game_name = game_names.get(game_type, "بازی")
        await callback.message.edit_text(
            f"🎮 بازی {game_name}\n\n"
            "تعداد سکه شرط را انتخاب کنید:",
            reply_markup=get_coin_amount_keyboard()
        )
        
        await state.set_state(GameStates.waiting_coin_amount)
        await callback.answer()
        break


@router.callback_query(F.data.startswith("game:coin:"), StateFilter(GameStates.waiting_coin_amount))
async def select_coin_amount(callback: CallbackQuery, state: FSMContext):
    """Handle coin amount selection and send request to partner."""
    coin_amount = int(callback.data.split(":")[2])
    
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        chat_room = await get_active_chat_room_by_user(db_session, user.id)
        if not chat_room:
            await callback.answer("❌ شما در حال حاضر یک چت فعال ندارید!", show_alert=True)
            return
        
        # Get game type from state
        state_data = await state.get_data()
        game_type = state_data.get("game_type")
        if not game_type:
            await callback.answer("❌ خطا در دریافت نوع بازی.", show_alert=True)
            return
        
        # Get partner
        partner_id = chat_room.user1_id if chat_room.user2_id == user.id else chat_room.user2_id
        partner = await get_user_by_id(db_session, partner_id)
        if not partner:
            await callback.answer("❌ مخاطب یافت نشد.", show_alert=True)
            return
        
        # Check if user has enough coins
        user_points = await get_user_points(db_session, user.id)
        if user_points < coin_amount:
            await callback.answer(
                f"❌ سکه کافی نداری! شما {user_points} سکه داری و {coin_amount} سکه نیاز داری.",
                show_alert=True
            )
            return
        
        # Store game request in Redis
        game_data = {
            "initiator_id": user.id,
            "initiator_telegram_id": user.telegram_id,
            "partner_id": partner_id,
            "partner_telegram_id": partner.telegram_id,
            "game_type": game_type,
            "coin_amount": coin_amount,
            "chat_room_id": chat_room.id
        }
        await set_game_request(chat_room.id, game_data)
        
        # Send request to partner
        game_names = {
            GAME_TYPE_DICE: "تاس",
            GAME_TYPE_DART: "دارت",
            GAME_TYPE_BASKETBALL: "بسکتبال",
            GAME_TYPE_SLOT_MACHINE: "اسلوت"
        }
        game_name = game_names.get(game_type, "بازی")
        from utils.validators import get_display_name
        user_display_name = get_display_name(user)
        bot = Bot(token=settings.BOT_TOKEN)
        try:
            await bot.send_message(
                partner.telegram_id,
                f"🎮 درخواست بازی\n\n"
                f"👤 {user_display_name} می‌خواهد با شما بازی {game_name} کند.\n"
                f"💰 شرط: {coin_amount} سکه\n\n"
                f"آیا می‌خواهید بازی را بپذیرید؟",
                reply_markup=get_game_request_keyboard(chat_room.id)
            )
        except Exception:
            pass
        finally:
            await bot.session.close()
        
        await callback.message.edit_text(
            f"✅ درخواست بازی ارسال شد!\n\n"
            f"⏳ در انتظار تایید مخاطب..."
        )
        
        await state.clear()
        await callback.answer()
        break


@router.callback_query(F.data.startswith("game:accept:"))
async def accept_game_request(callback: CallbackQuery):
    """Accept game request and start the game."""
    chat_room_id = int(callback.data.split(":")[2])
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Get game request
        game_request = await get_game_request(chat_room_id)
        if not game_request:
            await callback.answer("❌ درخواست بازی یافت نشد یا منقضی شده است.", show_alert=True)
            return
        
        # Verify this is the partner
        if game_request["partner_id"] != user.id:
            await callback.answer("❌ این درخواست برای شما نیست!", show_alert=True)
            return
        
        # Check if user has enough coins
        user_points = await get_user_points(db_session, user.id)
        coin_amount = game_request["coin_amount"]
        if user_points < coin_amount:
            await callback.answer(
                f"❌ سکه کافی نداری! شما {user_points} سکه داری و {coin_amount} سکه نیاز داری.",
                show_alert=True
            )
            return
        
        # Deduct coins from both users
        initiator = await get_user_by_id(db_session, game_request["initiator_id"])
        if not initiator:
            await callback.answer("❌ کاربر ارسال‌کننده یافت نشد.", show_alert=True)
            return
        
        # Deduct from initiator
        initiator_points = await get_user_points(db_session, initiator.id)
        if initiator_points < coin_amount:
            await callback.answer("❌ کاربر ارسال‌کننده سکه کافی ندارد.", show_alert=True)
            await delete_game_request(chat_room_id)
            return
        
        # Deduct coins
        await spend_points(
            db_session,
            initiator.id,
            coin_amount,
            "spent",
            "game_bet",
            f"Bet for {game_request['game_type']} game"
        )
        await spend_points(
            db_session,
            user.id,
            coin_amount,
            "spent",
            "game_bet",
            f"Bet for {game_request['game_type']} game"
        )
        
        # Create active game
        active_game_data = {
            "initiator_id": game_request["initiator_id"],
            "initiator_telegram_id": game_request["initiator_telegram_id"],
            "partner_id": user.id,
            "partner_telegram_id": user.telegram_id,
            "game_type": game_request["game_type"],
            "coin_amount": coin_amount,
            "chat_room_id": chat_room_id,
            "initiator_emoji": None,
            "partner_emoji": None
        }
        await set_active_game(chat_room_id, active_game_data)
        
        # Delete request
        await delete_game_request(chat_room_id)
        
        # Notify both users
        game_names = {
            GAME_TYPE_DICE: "تاس",
            GAME_TYPE_DART: "دارت",
            GAME_TYPE_BASKETBALL: "بسکتبال",
            GAME_TYPE_SLOT_MACHINE: "اسلوت"
        }
        game_emojis = {
            GAME_TYPE_DICE: DICE_EMOJI,
            GAME_TYPE_DART: DART_EMOJI,
            GAME_TYPE_BASKETBALL: BASKETBALL_EMOJI,
            GAME_TYPE_SLOT_MACHINE: SLOT_MACHINE_EMOJI
        }
        game_name = game_names.get(game_request["game_type"], "بازی")
        game_emoji = game_emojis.get(game_request["game_type"], DICE_EMOJI)
        
        # Create keyboard with game emoji button
        from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
        from aiogram.utils.keyboard import ReplyKeyboardBuilder
        game_keyboard = ReplyKeyboardBuilder()
        game_keyboard.add(KeyboardButton(text=game_emoji))
        game_keyboard.adjust(1)
        game_keyboard_markup = game_keyboard.as_markup(resize_keyboard=True, one_time_keyboard=True)
        
        bot = Bot(token=settings.BOT_TOKEN)
        try:
            # Notify initiator
            await bot.send_message(
                game_request["initiator_telegram_id"],
                f"✅ بازی پذیرفته شد!\n\n"
                f"🎮 بازی: {game_name}\n"
                f"💰 شرط: {coin_amount} سکه\n\n"
                f"🚀 شروع کنید! {game_emoji} را ارسال کنید.",
                reply_markup=game_keyboard_markup
            )
            
            # Notify partner
            await bot.send_message(
                user.telegram_id,
                f"✅ بازی شروع شد!\n\n"
                f"🎮 بازی: {game_name}\n"
                f"💰 شرط: {coin_amount} سکه\n\n"
                f"🚀 شروع کنید! {game_emoji} را ارسال کنید.",
                reply_markup=game_keyboard_markup
            )
        except Exception:
            pass
        finally:
            await bot.session.close()
        
        await callback.message.edit_text("✅ بازی شروع شد! 🚀")
        await callback.answer()
        break


@router.callback_query(F.data.startswith("game:reject:"))
async def reject_game_request(callback: CallbackQuery):
    """Reject game request."""
    chat_room_id = int(callback.data.split(":")[2])
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Get game request
        game_request = await get_game_request(chat_room_id)
        if not game_request:
            await callback.answer("❌ درخواست بازی یافت نشد یا منقضی شده است.", show_alert=True)
            return
        
        # Verify this is the partner
        if game_request["partner_id"] != user.id:
            await callback.answer("❌ این درخواست برای شما نیست!", show_alert=True)
            return
        
        # Notify initiator
        bot = Bot(token=settings.BOT_TOKEN)
        try:
            await bot.send_message(
                game_request["initiator_telegram_id"],
                "❌ درخواست بازی شما رد شد."
            )
        except Exception:
            pass
        finally:
            await bot.session.close()
        
        # Delete request
        await delete_game_request(chat_room_id)
        
        await callback.message.edit_text("❌ درخواست بازی رد شد.")
        await callback.answer()
        break


@router.callback_query(F.data == "game:cancel")
async def cancel_game(callback: CallbackQuery, state: FSMContext):
    """Cancel game setup."""
    await state.clear()
    await callback.message.edit_text("❌ بازی لغو شد.")
    await callback.answer()


@router.message(F.text.in_([DICE_EMOJI, DART_EMOJI, BASKETBALL_EMOJI, SLOT_MACHINE_EMOJI]))
async def handle_game_emoji_button(message: Message):
    """Handle game emoji button click - send actual dice/dart message."""
    user_id = message.from_user.id
    emoji_text = message.text
    
    # Map emoji text to dice emoji for Telegram API
    emoji_to_dice = {
        DICE_EMOJI: "🎲",
        DART_EMOJI: "🎯",
        BASKETBALL_EMOJI: "🏀",
        SLOT_MACHINE_EMOJI: "🎰"
    }
    
    dice_emoji = emoji_to_dice.get(emoji_text)
    if not dice_emoji:
        return
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            return
        
        # Check if user has active chat
        chat_room = await get_active_chat_room_by_user(db_session, user.id)
        if not chat_room:
            return
        
        # Check if there's an active game
        active_game = await get_active_game(chat_room.id)
        if not active_game:
            return
        
        # Map emoji to game type
        emoji_to_type = {
            DICE_EMOJI: GAME_TYPE_DICE,
            DART_EMOJI: GAME_TYPE_DART,
            BASKETBALL_EMOJI: GAME_TYPE_BASKETBALL,
            SLOT_MACHINE_EMOJI: GAME_TYPE_SLOT_MACHINE
        }
        game_type = emoji_to_type.get(emoji_text)
        
        # Check if this is the correct game type
        if active_game["game_type"] != game_type:
            return
        
        # Check if user is part of this game
        if user.id != active_game["initiator_id"] and user.id != active_game["partner_id"]:
            return
        
        # Send dice/dart message for user
        bot = Bot(token=settings.BOT_TOKEN)
        try:
            sent_message = await bot.send_dice(
                chat_id=user.telegram_id,
                emoji=dice_emoji
            )
            # Restore normal chat keyboard after sending dice
            from bot.keyboards.reply import get_chat_reply_keyboard
            await bot.send_message(
                chat_id=user.telegram_id,
                text="✅ ایموجی ارسال شد!",
                reply_markup=get_chat_reply_keyboard()
            )
            # The dice message will trigger handle_game_emoji when it arrives
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error sending game dice: {e}")
        finally:
            await bot.session.close()
        
        break


@router.message(F.dice)
async def handle_game_emoji(message: Message):
    """Handle dice or dart message sent by users."""
    user_id = message.from_user.id
    
    # In Telegram, both dice and dart are sent as dice messages
    # We need to check the emoji to determine the type
    if not message.dice:
        return
    
    dice_emoji = message.dice.emoji
    value = message.dice.value
    
    # Determine game type based on emoji
    if dice_emoji == "🎲":  # Dice emoji
        emoji = DICE_EMOJI
        game_type_check = GAME_TYPE_DICE
    elif dice_emoji == "🎯":  # Dart emoji
        emoji = DART_EMOJI
        game_type_check = GAME_TYPE_DART
    elif dice_emoji == "🏀":  # Basketball emoji
        emoji = BASKETBALL_EMOJI
        game_type_check = GAME_TYPE_BASKETBALL
    elif dice_emoji == "🎰":  # Slot machine emoji
        emoji = SLOT_MACHINE_EMOJI
        game_type_check = GAME_TYPE_SLOT_MACHINE
    else:
        # Unknown emoji type, ignore
        return
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            return
        
        # Check if user has active chat
        chat_room = await get_active_chat_room_by_user(db_session, user.id)
        if not chat_room:
            return
        
        # Check if there's an active game
        active_game = await get_active_game(chat_room.id)
        if not active_game:
            return
        
        # Check if this is the correct game type
        if active_game["game_type"] != game_type_check:
            return
        
        # Check if user is part of this game
        if user.id != active_game["initiator_id"] and user.id != active_game["partner_id"]:
            return
        
        # Store user's emoji and value
        if user.id == active_game["initiator_id"]:
            active_game["initiator_emoji"] = emoji
            active_game["initiator_value"] = value
        else:
            active_game["partner_emoji"] = emoji
            active_game["partner_value"] = value
        
        await set_active_game(chat_room.id, active_game)
        await set_user_game_emoji(chat_room.id, user.id, emoji)
        
        # Restore normal chat keyboard after sending dice
        from bot.keyboards.reply import get_chat_reply_keyboard
        bot = Bot(token=settings.BOT_TOKEN)
        try:
            # Restore keyboard for user
            await bot.send_message(
                chat_id=user.telegram_id,
                text="✅ ایموجی ارسال شد!",
                reply_markup=get_chat_reply_keyboard()
            )
            
            # Copy dice/dart message to partner (without forward mark)
            partner_id = await chat_manager.get_partner_id(user.id, db_session)
            if partner_id:
                partner = await get_user_by_id(db_session, partner_id)
                if partner:
                    # Copy dice message to partner without forward mark
                    await bot.copy_message(
                        chat_id=partner.telegram_id,
                        from_chat_id=user.telegram_id,
                        message_id=message.message_id
                    )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in game emoji handling: {e}")
        finally:
            await bot.session.close()
        
        # Check if both users have sent their emojis
        if (active_game.get("initiator_emoji") and active_game.get("partner_emoji") and
            active_game.get("initiator_value") is not None and active_game.get("partner_value") is not None):
            # Determine winner
            winner_id = determine_winner(
                active_game["game_type"],
                active_game.get("initiator_value"),
                active_game.get("partner_value"),
                active_game["initiator_id"],
                active_game["partner_id"]
            )
            
            # Get users
            initiator = await get_user_by_id(db_session, active_game["initiator_id"])
            partner = await get_user_by_id(db_session, active_game["partner_id"])
            
            # Calculate winnings (both bet, winner gets both)
            coin_amount = active_game["coin_amount"]
            total_winnings = coin_amount * 2
            
            bot = Bot(token=settings.BOT_TOKEN)
            try:
                if winner_id == active_game["initiator_id"]:
                    # Initiator wins
                    await add_points(
                        db_session,
                        initiator.id,
                        total_winnings,
                        "earned",
                        "game_win",
                        f"Won {active_game['game_type']} game"
                    )
                    await bot.send_message(
                        active_game["initiator_telegram_id"],
                        f"🎉 برنده شدی!\n\n"
                        f"💰 {total_winnings} سکه برنده شدی!"
                    )
                    await bot.send_message(
                        active_game["partner_telegram_id"],
                        f"😔 باختی!\n\n"
                        f"💰 {coin_amount} سکه از دست دادی."
                    )
                elif winner_id == active_game["partner_id"]:
                    # Partner wins
                    await add_points(
                        db_session,
                        partner.id,
                        total_winnings,
                        "earned",
                        "game_win",
                        f"Won {active_game['game_type']} game"
                    )
                    await bot.send_message(
                        active_game["partner_telegram_id"],
                        f"🎉 برنده شدی!\n\n"
                        f"💰 {total_winnings} سکه برنده شدی!"
                    )
                    await bot.send_message(
                        active_game["initiator_telegram_id"],
                        f"😔 باختی!\n\n"
                        f"💰 {coin_amount} سکه از دست دادی."
                    )
                else:
                    # Draw
                    # Refund both users
                    await add_points(
                        db_session,
                        initiator.id,
                        coin_amount,
                        "earned",
                        "game_draw",
                        f"Draw in {active_game['game_type']} game"
                    )
                    await add_points(
                        db_session,
                        partner.id,
                        coin_amount,
                        "earned",
                        "game_draw",
                        f"Draw in {active_game['game_type']} game"
                    )
                    await bot.send_message(
                        active_game["initiator_telegram_id"],
                        "🤝 مساوی شد!\n\n💰 سکه‌های شما برگشت داده شد."
                    )
                    await bot.send_message(
                        active_game["partner_telegram_id"],
                        "🤝 مساوی شد!\n\n💰 سکه‌های شما برگشت داده شد."
                    )
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error in game result: {e}")
            finally:
                await bot.session.close()
            
            # Clean up
            await delete_active_game(chat_room.id)
            await delete_user_game_emoji(chat_room.id, active_game["initiator_id"])
            await delete_user_game_emoji(chat_room.id, active_game["partner_id"])
        else:
            # Wait for other user
            await message.answer("✅ دریافت شد! در انتظار مخاطب...")
        
        break


def determine_winner(game_type: str, value1: int, value2: int, user1_id: int, user2_id: int) -> int:
    """
    Determine winner based on game type and values.
    
    Args:
        game_type: Type of game (dice, dart, basketball, slot_machine)
        value1: First user's value
        value2: Second user's value
        user1_id: First user's ID
        user2_id: Second user's ID
    
    Returns:
        user_id of winner, or None for draw
    """
    # All games: higher value wins
    # Dice: 1-6, Dart: 1-6, Basketball: 1-5, Slot: 1-64
    if game_type in [GAME_TYPE_DICE, GAME_TYPE_DART, GAME_TYPE_BASKETBALL, GAME_TYPE_SLOT_MACHINE]:
        if value1 > value2:
            return user1_id
        elif value2 > value1:
            return user2_id
        else:
            return None  # Draw
    
    return None

