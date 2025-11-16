"""
Game handlers for chat games with coin betting.
Games: Dice (تاس) and Dart (دارت)
"""
import json
import asyncio
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
TIC_TAC_TOE_EMOJI = "⭕"
ROCK_PAPER_SCISSORS_EMOJI = "✂️"

# Game types
GAME_TYPE_DICE = "dice"
GAME_TYPE_DART = "dart"
GAME_TYPE_BASKETBALL = "basketball"
GAME_TYPE_SLOT_MACHINE = "slot_machine"
GAME_TYPE_TIC_TAC_TOE = "tic_tac_toe"
GAME_TYPE_ROCK_PAPER_SCISSORS = "rock_paper_scissors"

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
            InlineKeyboardButton(text="🎰 اسلات", callback_data="game:type:slot_machine"),
        ],
        [
            InlineKeyboardButton(text="⭕ دوز", callback_data="game:type:tic_tac_toe"),
            InlineKeyboardButton(text="✂️ سنگ کاغذ قیچی", callback_data="game:type:rock_paper_scissors"),
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
            InlineKeyboardButton(text="🆓 رایگان", callback_data="game:coin:0"),
        ],
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
        
        # Get user points to show
        user_points = await get_user_points(db_session, user.id)
        
        # Show coin amount selection
        game_names = {
            GAME_TYPE_DICE: "تاس",
            GAME_TYPE_DART: "دارت",
            GAME_TYPE_BASKETBALL: "بسکتبال",
            GAME_TYPE_SLOT_MACHINE: "اسلات",
            GAME_TYPE_TIC_TAC_TOE: "دوز",
            GAME_TYPE_ROCK_PAPER_SCISSORS: "سنگ کاغذ قیچی"
        }
        game_name = game_names.get(game_type, "بازی")
        await callback.message.edit_text(
            f"🎮 بازی {game_name}\n\n"
            f"💎 سکه‌های فعلی شما: {user_points}\n\n"
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
        
        # Check if user has enough coins (only if not free game)
        if coin_amount > 0:
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
            GAME_TYPE_SLOT_MACHINE: "اسلات",
            GAME_TYPE_TIC_TAC_TOE: "دوز",
            GAME_TYPE_ROCK_PAPER_SCISSORS: "سنگ کاغذ قیچی"
        }
        game_name = game_names.get(game_type, "بازی")
        from utils.validators import get_display_name
        user_display_name = get_display_name(user)
        
        # Get partner points to show
        partner_points = await get_user_points(db_session, partner_id)
        
        bot = Bot(token=settings.BOT_TOKEN)
        try:
            # Format coin amount text
            if coin_amount == 0:
                coin_text = "🆓 رایگان"
            else:
                coin_text = f"💰 شرط: {coin_amount} سکه"
            
            await bot.send_message(
                partner.telegram_id,
                f"🎮 درخواست بازی\n\n"
                f"👤 {user_display_name} می‌خواهد با شما بازی {game_name} کند.\n"
                f"{coin_text}\n"
                f"💎 سکه‌های فعلی شما: {partner_points}\n\n"
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
        
        # Check if user has enough coins (only if not free game)
        coin_amount = game_request["coin_amount"]
        if coin_amount > 0:
            user_points = await get_user_points(db_session, user.id)
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
        else:
            # Free game - no coins deducted
            initiator = await get_user_by_id(db_session, game_request["initiator_id"])
            if not initiator:
                await callback.answer("❌ کاربر ارسال‌کننده یافت نشد.", show_alert=True)
                return
        
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
        
        # For tic-tac-toe, initialize board and current player
        if game_request["game_type"] == GAME_TYPE_TIC_TAC_TOE:
            active_game_data["board"] = create_tic_tac_toe_board()
            active_game_data["current_player_id"] = game_request["initiator_id"]  # Initiator starts (X)
            active_game_data["initiator_symbol"] = "X"
            active_game_data["partner_symbol"] = "O"
        
        await set_active_game(chat_room_id, active_game_data)
        
        # Delete request
        await delete_game_request(chat_room_id)
        
        # Notify both users
        game_names = {
            GAME_TYPE_DICE: "تاس",
            GAME_TYPE_DART: "دارت",
            GAME_TYPE_BASKETBALL: "بسکتبال",
            GAME_TYPE_SLOT_MACHINE: "اسلات",
            GAME_TYPE_TIC_TAC_TOE: "دوز",
            GAME_TYPE_ROCK_PAPER_SCISSORS: "سنگ کاغذ قیچی"
        }
        game_emojis = {
            GAME_TYPE_DICE: DICE_EMOJI,
            GAME_TYPE_DART: DART_EMOJI,
            GAME_TYPE_BASKETBALL: BASKETBALL_EMOJI,
            GAME_TYPE_SLOT_MACHINE: SLOT_MACHINE_EMOJI,
            GAME_TYPE_TIC_TAC_TOE: TIC_TAC_TOE_EMOJI,
            GAME_TYPE_ROCK_PAPER_SCISSORS: ROCK_PAPER_SCISSORS_EMOJI
        }
        game_name = game_names.get(game_request["game_type"], "بازی")
        game_emoji = game_emojis.get(game_request["game_type"], DICE_EMOJI)
        
        bot = Bot(token=settings.BOT_TOKEN)
        try:
            # Get current points before starting game
            initiator_current_points = await get_user_points(db_session, initiator.id)
            partner_current_points = await get_user_points(db_session, user.id)
            
            # Check if free game
            is_free_game = coin_amount == 0
            
            # Handle rock paper scissors differently
            if game_request["game_type"] == GAME_TYPE_ROCK_PAPER_SCISSORS:
                # Start rock paper scissors game - show selection menu
                # Format coin text
                if is_free_game:
                    coin_text = "🆓 رایگان"
                else:
                    coin_text = f"💰 شرط: {coin_amount} سکه"
                
                # Send selection menu to both players
                rps_keyboard = get_rock_paper_scissors_keyboard(chat_room_id)
                
                # Message for initiator
                if is_free_game:
                    initiator_rps_text = (
                        f"✅ بازی شروع شد!\n\n"
                        f"🎮 بازی: {game_name}\n\n"
                        f"انتخاب خود را انجام دهید:"
                    )
                else:
                    initiator_rps_text = (
                        f"✅ بازی شروع شد!\n\n"
                        f"🎮 بازی: {game_name}\n"
                        f"{coin_text}\n"
                        f"💎 سکه‌های شما: {initiator_current_points}\n\n"
                        f"انتخاب خود را انجام دهید:"
                    )
                
                initiator_rps_msg = await bot.send_message(
                    game_request["initiator_telegram_id"],
                    initiator_rps_text,
                    reply_markup=rps_keyboard
                )
                active_game_data["initiator_message_id"] = initiator_rps_msg.message_id
                
                # Message for partner
                if is_free_game:
                    partner_rps_text = (
                        f"✅ بازی شروع شد!\n\n"
                        f"🎮 بازی: {game_name}\n\n"
                        f"انتخاب خود را انجام دهید:"
                    )
                else:
                    partner_rps_text = (
                        f"✅ بازی شروع شد!\n\n"
                        f"🎮 بازی: {game_name}\n"
                        f"{coin_text}\n"
                        f"💎 سکه‌های شما: {partner_current_points}\n\n"
                        f"انتخاب خود را انجام دهید:"
                    )
                
                partner_rps_msg = await bot.send_message(
                    user.telegram_id,
                    partner_rps_text,
                    reply_markup=rps_keyboard
                )
                active_game_data["partner_message_id"] = partner_rps_msg.message_id
                
                # Update active game with message IDs
                await set_active_game(chat_room_id, active_game_data)
            
            # Handle tic-tac-toe differently
            elif game_request["game_type"] == GAME_TYPE_TIC_TAC_TOE:
                # Start tic-tac-toe game immediately
                from utils.validators import get_display_name
                initiator_name = get_display_name(initiator)
                partner_name = get_display_name(user)
                
                # Send board to both players
                board = active_game_data["board"]
                current_player_id = active_game_data["current_player_id"]
                
                # Format coin text
                if coin_amount == 0:
                    coin_text = "🆓 رایگان"
                else:
                    coin_text = f"💰 شرط: {coin_amount} سکه"
                
                # Board for initiator (X, starts first)
                initiator_keyboard = get_tic_tac_toe_keyboard(
                    board, current_player_id, initiator.id, chat_room_id
                )
                # Format message text
                if is_free_game:
                    initiator_start_text = (
                        f"✅ بازی شروع شد!\n\n"
                        f"🎮 بازی: {game_name}\n\n"
                        f"شما ❌ هستید و شروع می‌کنید.\n\n"
                        f"{format_tic_tac_toe_board_text(board, initiator_name)}"
                    )
                else:
                    initiator_start_text = (
                        f"✅ بازی شروع شد!\n\n"
                        f"🎮 بازی: {game_name}\n"
                        f"{coin_text}\n"
                        f"💎 سکه‌های شما: {initiator_current_points}\n\n"
                        f"شما ❌ هستید و شروع می‌کنید.\n\n"
                        f"{format_tic_tac_toe_board_text(board, initiator_name)}"
                    )
                
                initiator_msg = await bot.send_message(
                    game_request["initiator_telegram_id"],
                    initiator_start_text,
                    reply_markup=initiator_keyboard
                )
                # Store message ID
                active_game_data["initiator_message_id"] = initiator_msg.message_id
                
                # Board for partner (O, waits)
                partner_keyboard = get_tic_tac_toe_keyboard(
                    board, current_player_id, user.id, chat_room_id
                )
                # Format message text for partner
                if is_free_game:
                    partner_start_text = (
                        f"✅ بازی شروع شد!\n\n"
                        f"🎮 بازی: {game_name}\n\n"
                        f"شما ⭕ هستید. منتظر نوبت خود باشید.\n\n"
                        f"{format_tic_tac_toe_board_text(board, initiator_name)}"
                    )
                else:
                    partner_start_text = (
                        f"✅ بازی شروع شد!\n\n"
                        f"🎮 بازی: {game_name}\n"
                        f"{coin_text}\n"
                        f"💎 سکه‌های شما: {partner_current_points}\n\n"
                        f"شما ⭕ هستید. منتظر نوبت خود باشید.\n\n"
                        f"{format_tic_tac_toe_board_text(board, initiator_name)}"
                    )
                
                partner_msg = await bot.send_message(
                    user.telegram_id,
                    partner_start_text,
                    reply_markup=partner_keyboard
                )
                # Store message ID
                active_game_data["partner_message_id"] = partner_msg.message_id
                
                # Update active game with message IDs
                await set_active_game(chat_room_id, active_game_data)
            else:
                # For dice-based games, use "شروع" button
                from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
                from aiogram.utils.keyboard import ReplyKeyboardBuilder
                game_keyboard = ReplyKeyboardBuilder()
                game_keyboard.add(KeyboardButton(text="🚀 شروع"))
                game_keyboard.adjust(1)
                game_keyboard_markup = game_keyboard.as_markup(resize_keyboard=True, one_time_keyboard=True)
                
                # Notify initiator
                await bot.send_message(
                    game_request["initiator_telegram_id"],
                    f"✅ بازی پذیرفته شد!\n\n"
                    f"🎮 بازی: {game_name}\n"
                    f"💰 شرط: {coin_amount} سکه\n"
                    f"💎 سکه‌های شما: {initiator_current_points}\n\n"
                    f"🚀 روی دکمه «شروع» کلیک کنید تا ربات تاس را برای شما بفرستد.",
                    reply_markup=game_keyboard_markup
                )
                
                # Notify partner
                await bot.send_message(
                    user.telegram_id,
                    f"✅ بازی شروع شد!\n\n"
                    f"🎮 بازی: {game_name}\n"
                    f"💰 شرط: {coin_amount} سکه\n"
                    f"💎 سکه‌های شما: {partner_current_points}\n\n"
                    f"🚀 روی دکمه «شروع» کلیک کنید تا ربات تاس را برای شما بفرستد.",
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


@router.message(F.text == "🚀 شروع")
async def handle_game_start_button(message: Message):
    """Handle game start button click - bot sends dice for user."""
    user_id = message.from_user.id
    
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
        
        # Get game type and emoji from active game
        game_type = active_game["game_type"]
        
        # Tic-tac-toe doesn't use dice, ignore this handler
        if game_type == GAME_TYPE_TIC_TAC_TOE:
            return
        
        # Map game type to dice emoji
        game_type_to_dice = {
            GAME_TYPE_DICE: "🎲",
            GAME_TYPE_DART: "🎯",
            GAME_TYPE_BASKETBALL: "🏀",
            GAME_TYPE_SLOT_MACHINE: "🎰"
        }
        dice_emoji = game_type_to_dice.get(game_type)
        if not dice_emoji:
            return
        
        # Check if user is part of this game
        if user.id != active_game["initiator_id"] and user.id != active_game["partner_id"]:
            return
        
        # Check if this user has already sent their dice
        if user.id == active_game["initiator_id"]:
            if active_game.get("initiator_value") is not None:
                # User already sent, ignore
                return
        else:
            if active_game.get("partner_value") is not None:
                # User already sent, ignore
                return
        
        # Bot sends trigger message and dice for this user
        bot = Bot(token=settings.BOT_TOKEN)
        try:
            # Send trigger message
            game_names = {
                GAME_TYPE_DICE: "🎲 تاس",
                GAME_TYPE_DART: "🎯 دارت",
                GAME_TYPE_BASKETBALL: "🏀 بسکتبال",
                GAME_TYPE_SLOT_MACHINE: "🎰 اسلات",
                GAME_TYPE_TIC_TAC_TOE: "⭕ دوز",
                GAME_TYPE_ROCK_PAPER_SCISSORS: "✂️ سنگ کاغذ قیچی"
            }
            game_name = game_names.get(game_type, "بازی")
            await bot.send_message(
                chat_id=user.telegram_id,
                text=f"{game_name} شما"
            )
            
            # Send dice for user (from bot)
            # IMPORTANT: send_dice() returns immediately with value=0
            # Telegram will send an edited_message update when animation completes with final value
            import logging
            logger = logging.getLogger(__name__)
            
            logger.info(f"Sending dice for user {user.telegram_id}, game_type: {game_type}, emoji: {dice_emoji}")
            sent_message = await bot.send_dice(
                chat_id=user.telegram_id,
                emoji=dice_emoji
            )
            
            # Log the initial response
            initial_value = sent_message.dice.value if sent_message.dice else None
            logger.info(f"Dice sent: message_id={sent_message.message_id}, initial_value={initial_value}, has_dice={sent_message.dice is not None}")
            
            # IMPORTANT: Telegram doesn't send webhook updates for messages sent by the bot itself
            # So we need to process the dice value directly from send_dice() return value
            # The value might be 0 initially, but Telegram will update it
            # We'll check the value and process it if > 0, or wait for edited_message update
            
            if sent_message.dice and sent_message.dice.value > 0:
                # Value is already available, process it immediately
                logger.info(f"Dice value is ready immediately: {sent_message.dice.value}, processing...")
                # Process the dice message directly
                await _process_dice_message_from_send(sent_message, user.id, chat_room.id, game_type, dice_emoji, db_session)
            else:
                # Value is 0, wait for edited_message update
                logger.info(f"Dice value is 0, waiting for edited_message update...")
                # Store message ID and chat ID in Redis to process when value is ready
                if chat_manager and chat_manager.redis:
                    await chat_manager.redis.setex(
                        f"game:dice:{chat_room.id}:{user.id}",
                        60,  # 60 seconds TTL
                        json.dumps({
                            "message_id": sent_message.message_id,
                            "chat_id": user.telegram_id,
                            "game_type": game_type,
                            "dice_emoji": dice_emoji,
                            "user_id": user.id,
                            "chat_room_id": chat_room.id
                        })
                    )
                    logger.info(f"Stored dice info in Redis for user {user.id}, message_id: {sent_message.message_id}")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error sending game dice: {e}")
        finally:
            await bot.session.close()
        
        break


async def _process_dice_message_from_send(sent_message: Message, user_db_id: int, chat_room_id: int, game_type: str, dice_emoji: str, db_session):
    """Process dice message directly from send_dice() return value."""
    import logging
    logger = logging.getLogger(__name__)
    
    if not sent_message.dice:
        logger.warning("No dice in sent_message")
        return
    
    value = sent_message.dice.value
    if value == 0:
        logger.warning("Dice value is 0, cannot process")
        return
    
    logger.info(f"Processing dice from send_dice(): value={value}, user_id={user_db_id}, chat_room_id={chat_room_id}")
    
    # Get active game
    active_game = await get_active_game(chat_room_id)
    if not active_game:
        logger.warning(f"No active game found for chat_room {chat_room_id}")
        return
    
    # Check if this is the correct game type
    if active_game["game_type"] != game_type:
        logger.warning(f"Game type mismatch: expected {game_type}, got {active_game['game_type']}")
        return
    
    # Check if user is part of this game
    if user_db_id != active_game["initiator_id"] and user_db_id != active_game["partner_id"]:
        logger.warning(f"User {user_db_id} is not part of game")
        return
    
    # Map dice emoji to game emoji constant
    emoji_map = {
        "🎲": DICE_EMOJI,
        "🎯": DART_EMOJI,
        "🏀": BASKETBALL_EMOJI,
        "🎰": SLOT_MACHINE_EMOJI
    }
    emoji = emoji_map.get(dice_emoji, DICE_EMOJI)
    
    # Store user's emoji and value
    if user_db_id == active_game["initiator_id"]:
        active_game["initiator_emoji"] = emoji
        active_game["initiator_value"] = value
    else:
        active_game["partner_emoji"] = emoji
        active_game["partner_value"] = value
    
    await set_active_game(chat_room_id, active_game)
    await set_user_game_emoji(chat_room_id, user_db_id, emoji)
    
    # Get user and partner
    user = await get_user_by_id(db_session, user_db_id)
    partner_id = await chat_manager.get_partner_id(user_db_id, db_session)
    
    # Forward dice to partner
    bot = Bot(token=settings.BOT_TOKEN)
    try:
        if partner_id:
            partner = await get_user_by_id(db_session, partner_id)
            if partner:
                logger.info(f"Forwarding dice message {sent_message.message_id} from {user.telegram_id} to {partner.telegram_id}")
                try:
                    forwarded_msg = await bot.forward_message(
                        chat_id=partner.telegram_id,
                        from_chat_id=user.telegram_id,
                        message_id=sent_message.message_id
                    )
                    logger.info(f"Successfully forwarded dice to partner: {forwarded_msg.message_id}")
                    
                    # Send message to partner showing their dice and opponent's dice
                    # Get partner's dice value if they've already sent
                    partner_dice_value = None
                    if user_db_id == active_game["initiator_id"]:
                        partner_dice_value = active_game.get("partner_value")
                    else:
                        partner_dice_value = active_game.get("initiator_value")
                    
                    # Get emoji based on game type
                    emoji_map = {
                        "🎲": "🎲",
                        "🎯": "🎯",
                        "🏀": "🏀",
                        "🎰": "🎰"
                    }
                    game_emoji = emoji_map.get(dice_emoji, "🎯")
                    
                    # Wait for dice animation to complete (2-3 seconds)
                    await asyncio.sleep(2.5)
                    
                    dice_text = f"{game_emoji} امتیاز حریف: {value}"
                    if partner_dice_value is not None:
                        dice_text = f"{game_emoji} امتیاز شما: {partner_dice_value}\n{dice_text}"
                    
                    await bot.send_message(
                        partner.telegram_id,
                        dice_text
                    )
                    
                    # Send message to user showing their dice and opponent's dice (if available)
                    user_dice_text = f"{game_emoji} امتیاز شما: {value}"
                    if partner_dice_value is not None:
                        user_dice_text = f"{user_dice_text}\n{game_emoji} امتیاز حریف: {partner_dice_value}"
                    
                    await bot.send_message(
                        user.telegram_id,
                        user_dice_text
                    )
                except Exception as forward_error:
                    logger.warning(f"Could not forward dice: {forward_error}")
                    # Get emoji based on game type
                    emoji_map = {
                        "🎲": "🎲",
                        "🎯": "🎯",
                        "🏀": "🏀",
                        "🎰": "🎰"
                    }
                    game_emoji = emoji_map.get(dice_emoji, "🎯")
                    await bot.send_message(
                        partner.telegram_id,
                        f"{game_emoji} امتیاز حریف: {value}"
                    )
        
        # Restore normal chat keyboard
        from bot.keyboards.reply import get_chat_reply_keyboard
        await bot.send_message(
            chat_id=user.telegram_id,
            text=" ",
            reply_markup=get_chat_reply_keyboard()
        )
    except Exception as e:
        logger.error(f"Error forwarding dice: {e}", exc_info=True)
    finally:
        await bot.session.close()
    
    # Check if both users have sent their dice
    await _check_and_complete_game(active_game, db_session, chat_room_id)


async def _process_dice_message(message: Message, is_edited: bool = False):
    """Process dice message - handles both regular and edited messages."""
    import logging
    logger = logging.getLogger(__name__)
    
    # Log for debugging
    logger.info(f"Dice message received (edited={is_edited}): from_user={message.from_user}, chat_id={message.chat.id}, message_id={message.message_id}")
    
    # Only process dice messages sent by the bot (not by users)
    # When bot sends dice to user, message.from_user is the bot and message.chat.id is user's telegram_id
    if not message.from_user:
        logger.warning("No from_user in dice message")
        return
    
    if not message.from_user.is_bot:
        # Message is from user, ignore (users don't send dice directly in games)
        logger.info("Dice message from user (not bot), ignoring")
        return
    
    # Get user's telegram_id from chat.id (when bot sends to user, chat.id is user's telegram_id)
    user_id = message.chat.id
    
    # In Telegram, both dice and dart are sent as dice messages
    # We need to check the emoji to determine the type
    if not message.dice:
        logger.warning(f"No dice in message (edited={is_edited})")
        return
    
    dice_emoji = message.dice.emoji
    value = message.dice.value
    
    logger.info(f"Dice emoji: {dice_emoji}, value: {value}, edited: {is_edited}")
    
    # IMPORTANT: Telegram may send the dice with value already set (not 0)
    # In some cases, the initial message already has the final value
    # We should process it immediately if value > 0
    if value == 0:
        # Animation hasn't completed, wait for the update
        logger.info(f"Dice animation not completed yet (value=0), waiting for edited_message update...")
        return
    
    # Value is > 0, process it immediately
    logger.info(f"Dice value is ready: {value}, processing...")
    
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
            logger.warning(f"No active game found for chat_room {chat_room.id}")
            return
        
        logger.info(f"Active game found: {active_game}")
        
        # Check if this is the correct game type
        if active_game["game_type"] != game_type_check:
            logger.warning(f"Game type mismatch: expected {game_type_check}, got {active_game['game_type']}")
            return
        
        # Check if user is part of this game
        if user.id != active_game["initiator_id"] and user.id != active_game["partner_id"]:
            logger.warning(f"User {user.id} is not part of game: initiator={active_game['initiator_id']}, partner={active_game['partner_id']}")
            return
        
        logger.info(f"Processing dice for user {user.id}, value: {value}")
        
        # Store user's emoji and value
        if user.id == active_game["initiator_id"]:
            active_game["initiator_emoji"] = emoji
            active_game["initiator_value"] = value
        else:
            active_game["partner_emoji"] = emoji
            active_game["partner_value"] = value
        
        await set_active_game(chat_room.id, active_game)
        await set_user_game_emoji(chat_room.id, user.id, emoji)
        
        # Forward the same dice message to partner so they can see the result
        bot = Bot(token=settings.BOT_TOKEN)
        try:
            partner_id = await chat_manager.get_partner_id(user.id, db_session)
            if partner_id:
                partner = await get_user_by_id(db_session, partner_id)
                if partner:
                    # Forward the exact same dice message to partner
                    # message.chat.id is the user's telegram_id when bot sends dice to user
                    # We need to forward from the user's chat to partner's chat
                    logger.info(f"Forwarding dice message {message.message_id} from {message.chat.id} to {partner.telegram_id}")
                    try:
                        forwarded_msg = await bot.forward_message(
                            chat_id=partner.telegram_id,
                            from_chat_id=message.chat.id,  # This is user's telegram_id
                            message_id=message.message_id
                        )
                        logger.info(f"Successfully forwarded dice to partner: {forwarded_msg.message_id}")
                        
                        # Send message to partner showing their dice and opponent's dice
                        # Get partner's dice value if they've already sent
                        partner_dice_value = None
                        if user.id == active_game["initiator_id"]:
                            partner_dice_value = active_game.get("partner_value")
                        else:
                            partner_dice_value = active_game.get("initiator_value")
                        
                        # Get emoji based on game type
                        emoji_map = {
                            "🎲": "🎲",
                            "🎯": "🎯",
                            "🏀": "🏀",
                            "🎰": "🎰"
                        }
                        game_emoji = emoji_map.get(dice_emoji, "🎯")
                        
                        # Wait for dice animation to complete (2-3 seconds)
                        await asyncio.sleep(2.5)
                        
                        dice_text = f"{game_emoji} امتیاز حریف: {value}"
                        if partner_dice_value is not None:
                            dice_text = f"{game_emoji} امتیاز شما: {partner_dice_value}\n{dice_text}"
                        
                        await bot.send_message(
                            partner.telegram_id,
                            dice_text
                        )
                        
                        # Send message to user showing their dice and opponent's dice (if available)
                        user_dice_text = f"{game_emoji} امتیاز شما: {value}"
                        if partner_dice_value is not None:
                            user_dice_text = f"{user_dice_text}\n{game_emoji} امتیاز حریف: {partner_dice_value}"
                        
                        await bot.send_message(
                            user.telegram_id,
                            user_dice_text
                        )
                    except Exception as forward_error:
                        # If forward fails (e.g., privacy settings), send a copy instead
                        logger.warning(f"Could not forward dice, trying copy: {forward_error}")
                        # Get emoji based on game type
                        emoji_map = {
                            "🎲": "🎲",
                            "🎯": "🎯",
                            "🏀": "🏀",
                            "🎰": "🎰"
                        }
                        game_emoji = emoji_map.get(dice_emoji, "🎯")
                        await bot.send_message(
                            partner.telegram_id,
                            f"{game_emoji} امتیاز حریف: {value}"
                        )
            
            # Restore normal chat keyboard after sending dice
            from bot.keyboards.reply import get_chat_reply_keyboard
            await bot.send_message(
                chat_id=user.telegram_id,
                text=" ",
                reply_markup=get_chat_reply_keyboard()
            )
        except Exception as e:
            logger.error(f"Error forwarding dice to partner: {e}", exc_info=True)
        finally:
            await bot.session.close()
        
        # Check if both users have sent their emojis
        await _check_and_complete_game(active_game, db_session, chat_room.id)
        
        break


async def _check_and_complete_game(active_game: dict, db_session, chat_room_id: int = None):
    """Check if both users have sent dice and complete the game if so."""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Checking game completion: initiator_value={active_game.get('initiator_value')}, partner_value={active_game.get('partner_value')}")
    if (active_game.get("initiator_emoji") and active_game.get("partner_emoji") and
        active_game.get("initiator_value") is not None and active_game.get("partner_value") is not None):
        logger.info("Both users have sent dice, determining winner...")
        # Determine winner
        winner_id = determine_winner(
            active_game["game_type"],
            active_game.get("initiator_value"),
            active_game.get("partner_value"),
            active_game["initiator_id"],
            active_game["partner_id"]
        )
        logger.info(f"Winner determined: {winner_id}")
        
        # Get users
        initiator = await get_user_by_id(db_session, active_game["initiator_id"])
        partner = await get_user_by_id(db_session, active_game["partner_id"])
        
        # Calculate winnings (both bet, winner gets both)
        coin_amount = active_game["coin_amount"]
        total_winnings = coin_amount * 2
        
        # Get chat room to check private mode status (needed for keyboard)
        chat_room = None
        if chat_room_id:
            from db.crud import get_chat_room_by_id
            chat_room = await get_chat_room_by_id(db_session, chat_room_id)
        else:
            from db.crud import get_active_chat_room_by_user
            chat_room = await get_active_chat_room_by_user(db_session, initiator.id)
        
        # Get private mode status from Redis via chat_manager
        initiator_private_mode = False
        partner_private_mode = False
        if chat_room and chat_manager:
            initiator_private_mode = await chat_manager.get_private_mode(chat_room.id, initiator.id)
            partner_private_mode = await chat_manager.get_private_mode(chat_room.id, partner.id)
        
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
                # Get final points
                initiator_final_points = await get_user_points(db_session, initiator.id)
                partner_final_points = await get_user_points(db_session, partner.id)
                
                await bot.send_message(
                    active_game["initiator_telegram_id"],
                    f"🎉 برنده شدی!\n\n"
                    f"💰 {total_winnings} سکه برنده شدی!\n"
                    f"💎 سکه‌های شما: {initiator_final_points}",
                    reply_markup=get_chat_reply_keyboard(private_mode=initiator_private_mode)
                )
                await bot.send_message(
                    active_game["partner_telegram_id"],
                    f"😔 باختی!\n\n"
                    f"💰 {coin_amount} سکه از دست دادی.\n"
                    f"💎 سکه‌های شما: {partner_final_points}",
                    reply_markup=get_chat_reply_keyboard(private_mode=partner_private_mode)
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
                # Get final points
                initiator_final_points = await get_user_points(db_session, initiator.id)
                partner_final_points = await get_user_points(db_session, partner.id)
                
                await bot.send_message(
                    active_game["partner_telegram_id"],
                    f"🎉 برنده شدی!\n\n"
                    f"💰 {total_winnings} سکه برنده شدی!\n"
                    f"💎 سکه‌های شما: {partner_final_points}",
                    reply_markup=get_chat_reply_keyboard(private_mode=partner_private_mode)
                )
                await bot.send_message(
                    active_game["initiator_telegram_id"],
                    f"😔 باختی!\n\n"
                    f"💰 {coin_amount} سکه از دست دادی.\n"
                    f"💎 سکه‌های شما: {initiator_final_points}",
                    reply_markup=get_chat_reply_keyboard(private_mode=initiator_private_mode)
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
                # Get final points
                initiator_final_points = await get_user_points(db_session, initiator.id)
                partner_final_points = await get_user_points(db_session, partner.id)
                
                await bot.send_message(
                    active_game["initiator_telegram_id"],
                    f"🤝 مساوی شد!\n\n"
                    f"💰 سکه‌های شما برگشت داده شد.\n"
                    f"💎 سکه‌های شما: {initiator_final_points}",
                    reply_markup=get_chat_reply_keyboard(private_mode=initiator_private_mode)
                )
                await bot.send_message(
                    active_game["partner_telegram_id"],
                    f"🤝 مساوی شد!\n\n"
                    f"💰 سکه‌های شما برگشت داده شد.\n"
                    f"💎 سکه‌های شما: {partner_final_points}",
                    reply_markup=get_chat_reply_keyboard(private_mode=partner_private_mode)
                )
        except Exception as e:
            logger.error(f"Error in game result: {e}", exc_info=True)
        finally:
            await bot.session.close()
        
        # Clean up
        if chat_room_id:
            await delete_active_game(chat_room_id)
            await delete_user_game_emoji(chat_room_id, active_game["initiator_id"])
            await delete_user_game_emoji(chat_room_id, active_game["partner_id"])
        else:
            # Fallback: find chat_room from user
            from db.crud import get_active_chat_room_by_user
            if not chat_room:
                chat_room = await get_active_chat_room_by_user(db_session, initiator.id)
            if chat_room:
                await delete_active_game(chat_room.id)
                await delete_user_game_emoji(chat_room.id, active_game["initiator_id"])
                await delete_user_game_emoji(chat_room.id, active_game["partner_id"])


@router.message(F.dice)
async def handle_game_emoji(message: Message):
    """Handle dice or dart message sent by bot (initial message with value=0)."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"handle_game_emoji called: message_id={message.message_id}, chat_id={message.chat.id}, from_user={message.from_user}")
    await _process_dice_message(message, is_edited=False)


@router.edited_message(F.dice)
async def handle_game_emoji_edited(message: Message):
    """Handle dice or dart message when animation completes (edited_message with value>0)."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"handle_game_emoji_edited called: message_id={message.message_id}, chat_id={message.chat.id}, from_user={message.from_user}")
    await _process_dice_message(message, is_edited=True)


def determine_winner(game_type: str, value1: int, value2: int, user1_id: int, user2_id: int) -> int:
    """
    Determine winner based on game type and values.
    
    Args:
        game_type: Type of game (dice, dart, basketball, slot_machine, rock_paper_scissors)
        value1: First user's value
        value2: Second user's value
        user1_id: First user's ID
        user2_id: Second user's ID
    
    Returns:
        user_id of winner, or None for draw
    """
    # Rock Paper Scissors: 1=Rock, 2=Paper, 3=Scissors
    if game_type == GAME_TYPE_ROCK_PAPER_SCISSORS:
        # Rock (1) beats Scissors (3)
        # Paper (2) beats Rock (1)
        # Scissors (3) beats Paper (2)
        if value1 == value2:
            return None  # Draw
        elif (value1 == 1 and value2 == 3) or (value1 == 2 and value2 == 1) or (value1 == 3 and value2 == 2):
            return user1_id
        else:
            return user2_id
    
    # All other games: higher value wins
    # Dice: 1-6, Dart: 1-6, Basketball: 1-5, Slot: 1-64
    if game_type in [GAME_TYPE_DICE, GAME_TYPE_DART, GAME_TYPE_BASKETBALL, GAME_TYPE_SLOT_MACHINE]:
        if value1 > value2:
            return user1_id
        elif value2 > value1:
            return user2_id
        else:
            return None  # Draw
    
    return None


# ==================== Tic-Tac-Toe Functions ====================

def create_tic_tac_toe_board() -> list:
    """Create an empty 3x3 tic-tac-toe board."""
    return [["", "", ""], ["", "", ""], ["", "", ""]]


def get_tic_tac_toe_keyboard(board: list, current_player_id: int, user_id: int, chat_room_id: int) -> InlineKeyboardMarkup:
    """
    Create inline keyboard for tic-tac-toe board.
    
    Args:
        board: 3x3 board state
        current_player_id: ID of player whose turn it is
        user_id: ID of user viewing the board
        chat_room_id: Chat room ID for callback data
    """
    keyboard = []
    
    for i in range(3):
        row = []
        for j in range(3):
            position = i * 3 + j
            cell = board[i][j]
            
            if cell == "":
                # Empty cell - show as clickable if it's user's turn
                if current_player_id == user_id:
                    row.append(InlineKeyboardButton(
                        text="⬜",
                        callback_data=f"ttt:move:{chat_room_id}:{position}"
                    ))
                else:
                    row.append(InlineKeyboardButton(
                        text="⬜",
                        callback_data="ttt:not_your_turn"
                    ))
            elif cell == "X":
                row.append(InlineKeyboardButton(text="❌", callback_data="ttt:occupied"))
            elif cell == "O":
                row.append(InlineKeyboardButton(text="⭕", callback_data="ttt:occupied"))
            else:
                row.append(InlineKeyboardButton(text="⬜", callback_data="ttt:occupied"))
        
        keyboard.append(row)
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def check_tic_tac_toe_winner(board: list) -> str:
    """
    Check if there's a winner in tic-tac-toe.
    
    Args:
        board: 3x3 board state
    
    Returns:
        "X" if X wins, "O" if O wins, "draw" if board is full with no winner, None if game continues
    """
    # Check rows
    for row in board:
        if row[0] == row[1] == row[2] != "":
            return row[0]
    
    # Check columns
    for col in range(3):
        if board[0][col] == board[1][col] == board[2][col] != "":
            return board[0][col]
    
    # Check diagonals
    if board[0][0] == board[1][1] == board[2][2] != "":
        return board[0][0]
    if board[0][2] == board[1][1] == board[2][0] != "":
        return board[0][2]
    
    # Check for draw (board full)
    is_full = all(cell != "" for row in board for cell in row)
    if is_full:
        return "draw"
    
    return None


def format_tic_tac_toe_board_text(board: list, current_player_name: str = None) -> str:
    """Format board as text for display."""
    lines = []
    for i, row in enumerate(board):
        # Convert X to ❌ and O to ⭕ for display
        display_row = []
        for cell in row:
            if cell == "X":
                display_row.append("❌")
            elif cell == "O":
                display_row.append("⭕")
            else:
                display_row.append("⬜")
        row_text = " | ".join(display_row)
        lines.append(row_text)
        if i < 2:
            lines.append("─────────")
    
    text = "\n".join(lines)
    if current_player_name:
        text = f"نوبت: {current_player_name}\n\n{text}"
    
    return text


def get_rock_paper_scissors_keyboard(chat_room_id: int) -> InlineKeyboardMarkup:
    """Get keyboard for selecting rock, paper, or scissors."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🪨 سنگ", callback_data=f"rps:choose:{chat_room_id}:1"),
            InlineKeyboardButton(text="📄 کاغذ", callback_data=f"rps:choose:{chat_room_id}:2"),
            InlineKeyboardButton(text="✂️ قیچی", callback_data=f"rps:choose:{chat_room_id}:3"),
        ],
    ])
    return keyboard


@router.callback_query(F.data.startswith("ttt:move:"))
async def handle_tic_tac_toe_move(callback: CallbackQuery):
    """Handle tic-tac-toe move."""
    import logging
    logger = logging.getLogger(__name__)
    
    # Parse callback data: ttt:move:chat_room_id:position
    parts = callback.data.split(":")
    if len(parts) != 4:
        await callback.answer("❌ خطا در پردازش حرکت.", show_alert=True)
        return
    
    chat_room_id = int(parts[2])
    position = int(parts[3])
    
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Get active game
        active_game = await get_active_game(chat_room_id)
        if not active_game:
            await callback.answer("❌ بازی یافت نشد.", show_alert=True)
            return
        
        # Check if it's tic-tac-toe
        if active_game["game_type"] != GAME_TYPE_TIC_TAC_TOE:
            await callback.answer("❌ این بازی دوز نیست.", show_alert=True)
            return
        
        # Check if it's user's turn
        if active_game["current_player_id"] != user.id:
            await callback.answer("⏳ نوبت شما نیست! منتظر نوبت خود باشید.", show_alert=True)
            return
        
        # Check if position is valid
        if position < 0 or position > 8:
            await callback.answer("❌ موقعیت نامعتبر.", show_alert=True)
            return
        
        # Get board
        board = active_game.get("board")
        if not board:
            board = create_tic_tac_toe_board()
            active_game["board"] = board
        
        # Convert position to row/col
        row = position // 3
        col = position % 3
        
        # Check if cell is empty
        if board[row][col] != "":
            await callback.answer("❌ این خانه قبلاً انتخاب شده است!", show_alert=True)
            return
        
        # Make move
        if user.id == active_game["initiator_id"]:
            symbol = active_game.get("initiator_symbol", "X")
        else:
            symbol = active_game.get("partner_symbol", "O")
        
        board[row][col] = symbol
        
        # Check for winner
        winner = check_tic_tac_toe_winner(board)
        
        # Update current player
        if winner is None:
            # Switch turn
            if active_game["current_player_id"] == active_game["initiator_id"]:
                active_game["current_player_id"] = active_game["partner_id"]
            else:
                active_game["current_player_id"] = active_game["initiator_id"]
        
        # Save game state
        active_game["board"] = board
        await set_active_game(chat_room_id, active_game)
        
        # Get users for display
        initiator = await get_user_by_id(db_session, active_game["initiator_id"])
        partner = await get_user_by_id(db_session, active_game["partner_id"])
        from utils.validators import get_display_name
        
        bot = Bot(token=settings.BOT_TOKEN)
        try:
            if winner:
                # Game over
                await _handle_tic_tac_toe_game_over(
                    active_game, board, winner, db_session, chat_room_id, bot
                )
            else:
                # Continue game - update boards for both players
                current_player_id = active_game["current_player_id"]
                current_player = initiator if current_player_id == initiator.id else partner
                current_player_name = get_display_name(current_player)
                
                # Update board for both players
                initiator_keyboard = get_tic_tac_toe_keyboard(
                    board, current_player_id, initiator.id, chat_room_id
                )
                partner_keyboard = get_tic_tac_toe_keyboard(
                    board, current_player_id, partner.id, chat_room_id
                )
                
                # Get message IDs from active game
                initiator_message_id = active_game.get("initiator_message_id")
                partner_message_id = active_game.get("partner_message_id")
                
                # Prepare text for both players
                initiator_text = f"⭕ دوز\n\n{format_tic_tac_toe_board_text(board, current_player_name)}"
                if current_player_id == initiator.id:
                    initiator_text += "\n\n✅ نوبت شماست!"
                else:
                    initiator_text += "\n\n⏳ منتظر نوبت حریف..."
                
                partner_text = f"⭕ دوز\n\n{format_tic_tac_toe_board_text(board, current_player_name)}"
                if current_player_id == partner.id:
                    partner_text += "\n\n✅ نوبت شماست!"
                else:
                    partner_text += "\n\n⏳ منتظر نوبت حریف..."
                
                # Update initiator's message
                if initiator_message_id:
                    try:
                        await bot.edit_message_text(
                            chat_id=active_game["initiator_telegram_id"],
                            message_id=initiator_message_id,
                            text=initiator_text,
                            reply_markup=initiator_keyboard
                        )
                    except Exception as e:
                        logger.warning(f"Could not edit initiator message: {e}")
                        # If edit fails, send new message and update message ID
                        new_msg = await bot.send_message(
                            chat_id=active_game["initiator_telegram_id"],
                            text=initiator_text,
                            reply_markup=initiator_keyboard
                        )
                        active_game["initiator_message_id"] = new_msg.message_id
                        await set_active_game(chat_room_id, active_game)
                
                # Update partner's message
                if partner_message_id:
                    try:
                        await bot.edit_message_text(
                            chat_id=active_game["partner_telegram_id"],
                            message_id=partner_message_id,
                            text=partner_text,
                            reply_markup=partner_keyboard
                        )
                    except Exception as e:
                        logger.warning(f"Could not edit partner message: {e}")
                        # If edit fails, send new message and update message ID
                        new_msg = await bot.send_message(
                            chat_id=active_game["partner_telegram_id"],
                            text=partner_text,
                            reply_markup=partner_keyboard
                        )
                        active_game["partner_message_id"] = new_msg.message_id
                        await set_active_game(chat_room_id, active_game)
            
            await callback.answer()
        except Exception as e:
            logger.error(f"Error handling tic-tac-toe move: {e}", exc_info=True)
            await callback.answer("❌ خطا در پردازش حرکت.", show_alert=True)
        finally:
            await bot.session.close()
        
        break


@router.callback_query(F.data == "ttt:not_your_turn")
async def handle_ttt_not_your_turn(callback: CallbackQuery):
    """Handle when user tries to move but it's not their turn."""
    await callback.answer("⏳ نوبت شما نیست! منتظر نوبت خود باشید.", show_alert=True)


@router.callback_query(F.data == "ttt:occupied")
async def handle_ttt_occupied(callback: CallbackQuery):
    """Handle when user tries to move to occupied cell."""
    await callback.answer("❌ این خانه قبلاً انتخاب شده است!", show_alert=True)


async def _handle_tic_tac_toe_game_over(
    active_game: dict,
    board: list,
    winner: str,
    db_session,
    chat_room_id: int,
    bot: Bot
):
    """Handle tic-tac-toe game over (win or draw)."""
    import logging
    logger = logging.getLogger(__name__)
    
    coin_amount = active_game["coin_amount"]
    total_winnings = coin_amount * 2
    is_free_game = coin_amount == 0
    
    # Get chat room for private mode
    from db.crud import get_chat_room_by_id
    chat_room = await get_chat_room_by_id(db_session, chat_room_id)
    
    initiator_private_mode = False
    partner_private_mode = False
    if chat_room and chat_manager:
        initiator_private_mode = await chat_manager.get_private_mode(chat_room_id, active_game["initiator_id"])
        partner_private_mode = await chat_manager.get_private_mode(chat_room_id, active_game["partner_id"])
    
    initiator = await get_user_by_id(db_session, active_game["initiator_id"])
    partner = await get_user_by_id(db_session, active_game["partner_id"])
    from utils.validators import get_display_name
    
    if winner == "draw":
        # Draw - refund both (only if not free game)
        if not is_free_game:
            await add_points(
                db_session,
                initiator.id,
                coin_amount,
                "earned",
                "game_draw",
                "Draw in tic-tac-toe game"
            )
            await add_points(
                db_session,
                partner.id,
                coin_amount,
                "earned",
                "game_draw",
                "Draw in tic-tac-toe game"
            )
        
        final_board_text = format_tic_tac_toe_board_text(board)
        
        # Format draw message
        if is_free_game:
            draw_message = "🤝 مساوی شد!\n\n🆓 بازی رایگان بود."
            initiator_draw_text = f"{draw_message}\n\n{final_board_text}"
            partner_draw_text = f"{draw_message}\n\n{final_board_text}"
        else:
            initiator_final_points = await get_user_points(db_session, initiator.id)
            partner_final_points = await get_user_points(db_session, partner.id)
            draw_message = f"🤝 مساوی شد!\n\n💰 سکه‌های شما برگشت داده شد."
            initiator_draw_text = f"{draw_message}\n💎 سکه‌های شما: {initiator_final_points}\n\n{final_board_text}"
            partner_draw_text = f"{draw_message}\n💎 سکه‌های شما: {partner_final_points}\n\n{final_board_text}"
        
        await bot.send_message(
            active_game["initiator_telegram_id"],
            initiator_draw_text,
            reply_markup=get_chat_reply_keyboard(private_mode=initiator_private_mode)
        )
        await bot.send_message(
            active_game["partner_telegram_id"],
            partner_draw_text,
            reply_markup=get_chat_reply_keyboard(private_mode=partner_private_mode)
        )
    else:
        # Determine winner
        if winner == "X":
            winner_id = active_game["initiator_id"]
            loser_id = active_game["partner_id"]
            winner_telegram_id = active_game["initiator_telegram_id"]
            loser_telegram_id = active_game["partner_telegram_id"]
            winner_private_mode = initiator_private_mode
            loser_private_mode = partner_private_mode
        else:  # winner == "O"
            winner_id = active_game["partner_id"]
            loser_id = active_game["initiator_id"]
            winner_telegram_id = active_game["partner_telegram_id"]
            loser_telegram_id = active_game["initiator_telegram_id"]
            winner_private_mode = partner_private_mode
            loser_private_mode = initiator_private_mode
        
        # Award winnings (only if not free game)
        if not is_free_game:
            await add_points(
                db_session,
                winner_id,
                total_winnings,
                "earned",
                "game_win",
                "Won tic-tac-toe game"
            )
        
        winner_final_points = await get_user_points(db_session, winner_id)
        loser_final_points = await get_user_points(db_session, loser_id)
        
        final_board_text = format_tic_tac_toe_board_text(board)
        winner_name = get_display_name(await get_user_by_id(db_session, winner_id))
        
        # Format winner message
        if is_free_game:
            winner_message = "🎉 برنده شدی!\n\n🆓 بازی رایگان بود."
            loser_message = "😔 باختی!\n\n🆓 بازی رایگان بود."
            winner_text = f"{winner_message}\n\n{final_board_text}"
            loser_text = f"{loser_message}\n\n{final_board_text}"
        else:
            winner_message = f"🎉 برنده شدی!\n\n💰 {total_winnings} سکه برنده شدی!"
            loser_message = f"😔 باختی!\n\n💰 {coin_amount} سکه از دست دادی."
            winner_text = f"{winner_message}\n💎 سکه‌های شما: {winner_final_points}\n\n{final_board_text}"
            loser_text = f"{loser_message}\n💎 سکه‌های شما: {loser_final_points}\n\n{final_board_text}"
        
        await bot.send_message(
            winner_telegram_id,
            winner_text,
            reply_markup=get_chat_reply_keyboard(private_mode=winner_private_mode)
        )
        await bot.send_message(
            loser_telegram_id,
            loser_text,
            reply_markup=get_chat_reply_keyboard(private_mode=loser_private_mode)
        )
    
    # Clean up
    await delete_active_game(chat_room_id)
    await delete_user_game_emoji(chat_room_id, active_game["initiator_id"])
    await delete_user_game_emoji(chat_room_id, active_game["partner_id"])


@router.callback_query(F.data.startswith("rps:choose:"))
async def handle_rock_paper_scissors_choice(callback: CallbackQuery):
    """Handle rock paper scissors choice."""
    import logging
    logger = logging.getLogger(__name__)
    
    # Parse: rps:choose:chat_room_id:choice (1=Rock, 2=Paper, 3=Scissors)
    parts = callback.data.split(":")
    if len(parts) != 4:
        await callback.answer("❌ خطا در پردازش انتخاب.", show_alert=True)
        return
    
    chat_room_id = int(parts[2])
    choice = int(parts[3])  # 1=Rock, 2=Paper, 3=Scissors
    
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Get active game
        active_game = await get_active_game(chat_room_id)
        if not active_game:
            await callback.answer("❌ بازی یافت نشد.", show_alert=True)
            return
        
        # Check if it's rock paper scissors
        if active_game["game_type"] != GAME_TYPE_ROCK_PAPER_SCISSORS:
            await callback.answer("❌ این بازی سنگ کاغذ قیچی نیست.", show_alert=True)
            return
        
        # Check if user is part of this game
        if user.id != active_game["initiator_id"] and user.id != active_game["partner_id"]:
            await callback.answer("❌ شما در این بازی شرکت ندارید!", show_alert=True)
            return
        
        # Check if user has already chosen
        if user.id == active_game["initiator_id"]:
            if active_game.get("initiator_value") is not None:
                await callback.answer("❌ شما قبلاً انتخاب کرده‌اید!", show_alert=True)
                return
        else:
            if active_game.get("partner_value") is not None:
                await callback.answer("❌ شما قبلاً انتخاب کرده‌اید!", show_alert=True)
                return
        
        # Store user's choice
        if user.id == active_game["initiator_id"]:
            active_game["initiator_value"] = choice
        else:
            active_game["partner_value"] = choice
        
        await set_active_game(chat_room_id, active_game)
        
        # Get choice names
        choice_names = {1: "🪨 سنگ", 2: "📄 کاغذ", 3: "✂️ قیچی"}
        choice_name = choice_names.get(choice, "نامشخص")
        
        # Update message to show selection
        bot = Bot(token=settings.BOT_TOKEN)
        try:
            message_id = active_game.get("initiator_message_id") if user.id == active_game["initiator_id"] else active_game.get("partner_message_id")
            
            if message_id:
                try:
                    await bot.edit_message_text(
                        chat_id=user.telegram_id,
                        message_id=message_id,
                        text=f"✅ شما {choice_name} را انتخاب کردید!\n\n⏳ منتظر انتخاب حریف...",
                        reply_markup=None
                    )
                except Exception as e:
                    logger.warning(f"Could not edit message: {e}")
            
            await callback.answer(f"✅ {choice_name} انتخاب شد!")
        except Exception as e:
            logger.error(f"Error handling RPS choice: {e}", exc_info=True)
            await callback.answer("❌ خطا در پردازش انتخاب.", show_alert=True)
        finally:
            await bot.session.close()
        
        # Check if both users have chosen
        # Re-read active_game from Redis to get latest state
        updated_active_game = await get_active_game(chat_room_id)
        if updated_active_game and updated_active_game.get("initiator_value") is not None and updated_active_game.get("partner_value") is not None:
            # Both have chosen - process result
            await _process_rock_paper_scissors_result(updated_active_game, db_session, chat_room_id)
        
        break


async def _process_rock_paper_scissors_result(active_game: dict, db_session, chat_room_id: int):
    """Process rock paper scissors result after both players have chosen."""
    import logging
    logger = logging.getLogger(__name__)
    
    initiator_value = active_game.get("initiator_value")
    partner_value = active_game.get("partner_value")
    
    # Validate values
    if initiator_value is None or partner_value is None:
        logger.error(f"Missing values: initiator_value={initiator_value}, partner_value={partner_value}")
        return
    
    logger.info(f"Processing RPS result: initiator_value={initiator_value} (user_id={active_game['initiator_id']}), partner_value={partner_value} (user_id={active_game['partner_id']})")
    
    # Determine winner
    winner_id = determine_winner(
        GAME_TYPE_ROCK_PAPER_SCISSORS,
        initiator_value,
        partner_value,
        active_game["initiator_id"],
        active_game["partner_id"]
    )
    
    logger.info(f"Winner determined: {winner_id}")
    
    # Get users
    initiator = await get_user_by_id(db_session, active_game["initiator_id"])
    partner = await get_user_by_id(db_session, active_game["partner_id"])
    
    coin_amount = active_game["coin_amount"]
    total_winnings = coin_amount * 2
    is_free_game = coin_amount == 0
    
    # Get chat room for private mode
    from db.crud import get_chat_room_by_id
    chat_room = await get_chat_room_by_id(db_session, chat_room_id)
    
    initiator_private_mode = False
    partner_private_mode = False
    if chat_room and chat_manager:
        initiator_private_mode = await chat_manager.get_private_mode(chat_room_id, active_game["initiator_id"])
        partner_private_mode = await chat_manager.get_private_mode(chat_room_id, active_game["partner_id"])
    
    choice_names = {1: "🪨 سنگ", 2: "📄 کاغذ", 3: "✂️ قیچی"}
    initiator_choice = choice_names.get(initiator_value, "نامشخص")
    partner_choice = choice_names.get(partner_value, "نامشخص")
    
    bot = Bot(token=settings.BOT_TOKEN)
    try:
        if winner_id is None:
            # Draw
            if not is_free_game:
                await add_points(
                    db_session,
                    initiator.id,
                    coin_amount,
                    "earned",
                    "game_draw",
                    "Draw in rock paper scissors game"
                )
                await add_points(
                    db_session,
                    partner.id,
                    coin_amount,
                    "earned",
                    "game_draw",
                    "Draw in rock paper scissors game"
                )
            
            initiator_final_points = await get_user_points(db_session, initiator.id)
            partner_final_points = await get_user_points(db_session, partner.id)
            
            if is_free_game:
                draw_text = "🤝 مساوی شد!\n\n🆓 بازی رایگان بود."
                initiator_draw_msg = f"{draw_text}\n\nشما: {initiator_choice}\nحریف: {partner_choice}"
                partner_draw_msg = f"{draw_text}\n\nشما: {partner_choice}\nحریف: {initiator_choice}"
            else:
                draw_text = f"🤝 مساوی شد!\n\n💰 سکه‌های شما برگشت داده شد."
                initiator_draw_msg = f"{draw_text}\n💎 سکه‌های شما: {initiator_final_points}\n\nشما: {initiator_choice}\nحریف: {partner_choice}"
                partner_draw_msg = f"{draw_text}\n💎 سکه‌های شما: {partner_final_points}\n\nشما: {partner_choice}\nحریف: {initiator_choice}"
            
            await bot.send_message(
                active_game["initiator_telegram_id"],
                initiator_draw_msg,
                reply_markup=get_chat_reply_keyboard(private_mode=initiator_private_mode)
            )
            await bot.send_message(
                active_game["partner_telegram_id"],
                partner_draw_msg,
                reply_markup=get_chat_reply_keyboard(private_mode=partner_private_mode)
            )
        else:
            # There's a winner
            if winner_id == active_game["initiator_id"]:
                winner_telegram_id = active_game["initiator_telegram_id"]
                loser_telegram_id = active_game["partner_telegram_id"]
                winner_choice = initiator_choice
                loser_choice = partner_choice
                loser_id = active_game["partner_id"]
            else:
                winner_telegram_id = active_game["partner_telegram_id"]
                loser_telegram_id = active_game["initiator_telegram_id"]
                winner_choice = partner_choice
                loser_choice = initiator_choice
                loser_id = active_game["initiator_id"]
            
            if not is_free_game:
                await add_points(
                    db_session,
                    winner_id,
                    total_winnings,
                    "earned",
                    "game_win",
                    "Won rock paper scissors game"
                )
            
            winner_final_points = await get_user_points(db_session, winner_id)
            loser_final_points = await get_user_points(db_session, loser_id)
            
            if is_free_game:
                winner_msg = f"🎉 برنده شدی!\n\n🆓 بازی رایگان بود.\n\nشما: {winner_choice}\nحریف: {loser_choice}"
                loser_msg = f"😔 باختی!\n\n🆓 بازی رایگان بود.\n\nشما: {loser_choice}\nحریف: {winner_choice}"
            else:
                winner_msg = f"🎉 برنده شدی!\n\n💰 {total_winnings} سکه برنده شدی!\n💎 سکه‌های شما: {winner_final_points}\n\nشما: {winner_choice}\nحریف: {loser_choice}"
                loser_msg = f"😔 باختی!\n\n💰 {coin_amount} سکه از دست دادی.\n💎 سکه‌های شما: {loser_final_points}\n\nشما: {loser_choice}\nحریف: {winner_choice}"
            
            await bot.send_message(
                winner_telegram_id,
                winner_msg,
                reply_markup=get_chat_reply_keyboard(private_mode=initiator_private_mode if winner_id == active_game["initiator_id"] else partner_private_mode)
            )
            await bot.send_message(
                loser_telegram_id,
                loser_msg,
                reply_markup=get_chat_reply_keyboard(private_mode=initiator_private_mode if loser_id == active_game["initiator_id"] else partner_private_mode)
            )
    except Exception as e:
        logger.error(f"Error processing RPS result: {e}", exc_info=True)
    finally:
        await bot.session.close()
    
    # Clean up
    await delete_active_game(chat_room_id)
    await delete_user_game_emoji(chat_room_id, active_game["initiator_id"])
    await delete_user_game_emoji(chat_room_id, active_game["partner_id"])

