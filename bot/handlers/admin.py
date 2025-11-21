"""
Admin handler for the bot.
Handles admin commands like broadcast, ban, stats, etc.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db.database import get_db
from db.crud import (
    get_user_by_telegram_id,
    get_user_by_id,
    get_user_count,
    get_active_chat_count,
    get_premium_count,
    get_all_users,
    ban_user,
    unban_user,
    get_unresolved_reports,
    resolve_report,
    get_admin_referral_links,
    create_admin_referral_link,
    get_admin_referral_link_by_id,
    update_admin_referral_link,
    delete_admin_referral_link,
    get_link_statistics,
    get_all_coin_settings,
    get_coin_setting,
    update_coin_setting,
    get_coins_for_premium_days,
    create_broadcast_message,
    get_broadcast_messages,
    get_broadcast_message_by_id,
    create_broadcast_receipt,
    increment_broadcast_stats,
    get_broadcast_statistics,
    get_top_users_by_points,
    get_top_users_by_referrals,
    get_top_users_by_likes,
    create_premium_plan,
    get_premium_plan_by_id,
    get_all_premium_plans,
    update_premium_plan,
    delete_premium_plan,
    get_all_coin_reward_settings,
    get_coin_reward_setting,
    create_coin_reward_setting,
    update_coin_reward_setting,
    get_system_setting_value,
    set_system_setting,
    delete_coin_reward_setting,
    create_mandatory_channel,
    get_all_mandatory_channels,
    get_mandatory_channel_by_id,
    update_mandatory_channel,
    delete_mandatory_channel,
    get_active_mandatory_channels,
)
from bot.keyboards.common import get_admin_keyboard, get_main_menu_keyboard
from bot.keyboards.admin import (
    get_admin_main_keyboard,
    get_admin_users_keyboard,
    get_admin_referral_links_keyboard,
    get_admin_coin_settings_keyboard,
    get_admin_coin_rewards_keyboard,
    get_coin_reward_list_keyboard,
    get_referral_link_list_keyboard,
    get_referral_link_detail_keyboard,
    get_mandatory_channels_keyboard,
    get_mandatory_channel_list_keyboard,
    get_mandatory_channel_detail_keyboard,
)
from bot.keyboards.leaderboard import (
    get_admin_leaderboard_main_keyboard,
    get_admin_leaderboard_period_keyboard,
)
from bot.keyboards.premium_plan import (
    get_admin_premium_plans_keyboard,
    get_premium_plan_list_keyboard,
    get_premium_plan_detail_keyboard,
)
from config.settings import settings

router = Router()

# Track active broadcasts for pause/resume/cancel functionality
_active_broadcasts: dict[int, dict] = {}  # broadcast_id -> {status, stop_event, pause_event}


def get_gender_emoji(gender: str) -> str:
    """Get emoji for gender."""
    if gender == "male":
        return "👨"
    elif gender == "female":
        return "👩"
    else:
        return "⚪"


def format_profile_id(profile_id: str) -> str:
    """Format profile ID for display."""
    if profile_id:
        # profile_id is stored as "15e1576abc70" (without /user_)
        return f"/user_{profile_id}"
    return ""


class BroadcastStates(StatesGroup):
    """FSM states for broadcast."""
    waiting_message = State()
    waiting_rate = State()


class QueueBroadcastStates(StatesGroup):
    """FSM states for queue-based broadcast."""
    waiting_message = State()
    waiting_confirmation = State()


class CreateReferralLinkStates(StatesGroup):
    """FSM states for creating referral link."""
    waiting_code = State()
    waiting_description = State()


class EditCoinSettingStates(StatesGroup):
    """FSM states for editing coin setting."""
    waiting_coins = State()


class EditCoinRewardStates(StatesGroup):
    """FSM states for editing coin reward settings."""
    waiting_coins = State()


class PremiumPlanStates(StatesGroup):
    """FSM states for premium plan management."""
    waiting_plan_name = State()
    waiting_duration_days = State()
    waiting_price = State()
    waiting_original_price = State()
    waiting_stars = State()
    waiting_payment_methods = State()
    waiting_discount_start = State()
    waiting_discount_end = State()
    waiting_display_order = State()


class MandatoryChannelStates(StatesGroup):
    """FSM states for mandatory channel management."""
    waiting_channel_id = State()
    waiting_channel_name = State()
    waiting_channel_link = State()
    waiting_order_index = State()


def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    return user_id in settings.ADMIN_IDS


@router.message(Command("admin_stats"))
async def cmd_admin_stats(message: Message):
    """Get admin statistics."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Access denied.")
        return
    
    async for db_session in get_db():
        total_users = await get_user_count(db_session)
        active_chats = await get_active_chat_count(db_session)
        premium_users = await get_premium_count(db_session)
        
        await message.answer(
            f"📊 Admin Statistics\n\n"
            f"👥 Total Users: {total_users}\n"
            f"💬 Active Chats: {active_chats}\n"
            f"💎 Premium Users: {premium_users}\n\n"
            f"Admin Panel:",
            reply_markup=get_admin_keyboard()
        )
        break


@router.message(Command("admin_broadcast"))
async def cmd_admin_broadcast(message: Message, state: FSMContext):
    """Start broadcast process."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Access denied.")
        return
    
    await message.answer(
        "📢 Broadcast Message\n\n"
        "Please send the message you want to broadcast to all users:"
    )
    await state.set_state(BroadcastStates.waiting_message)


@router.message(BroadcastStates.waiting_message)
async def process_broadcast_message(message: Message, state: FSMContext):
    """Process broadcast message - supports all message types."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        return
    
    # Determine message type and extract content
    message_type = "text"
    message_text = None
    message_file_id = None
    message_caption = None
    forwarded_from_chat_id = None
    forwarded_from_message_id = None
    
    if message.forward_from_chat or message.forward_from_message_id:
        # Forwarded message
        message_type = "forward"
        forwarded_from_chat_id = message.forward_from_chat.id if message.forward_from_chat else None
        forwarded_from_message_id = message.forward_from_message_id
        message_text = message.text or message.caption
        message_caption = message.caption
    elif message.photo:
        # Photo
        message_type = "photo"
        message_file_id = message.photo[-1].file_id  # Get largest photo
        message_caption = message.caption
        message_text = message.caption
    elif message.video:
        # Video
        message_type = "video"
        message_file_id = message.video.file_id
        message_caption = message.caption
        message_text = message.caption
    elif message.document:
        # Document/File
        message_type = "document"
        message_file_id = message.document.file_id
        message_caption = message.caption
        message_text = message.caption or message.document.file_name
    elif message.audio:
        # Audio
        message_type = "audio"
        message_file_id = message.audio.file_id
        message_caption = message.caption
        message_text = message.caption or (message.audio.title if message.audio.title else "Audio")
    elif message.voice:
        # Voice
        message_type = "voice"
        message_file_id = message.voice.file_id
        message_caption = message.caption
        message_text = message.caption or "Voice message"
    elif message.video_note:
        # Video note
        message_type = "video_note"
        message_file_id = message.video_note.file_id
        message_text = "Video note"
    elif message.sticker:
        # Sticker
        message_type = "sticker"
        message_file_id = message.sticker.file_id
        message_text = "Sticker"
    elif message.text:
        # Text
        message_type = "text"
        message_text = message.text
    else:
        await message.answer("❌ نوع پیام پشتیبانی نمی‌شود.")
        return
    
    # Store message data in FSM
    await state.update_data(
        admin_id=message.from_user.id,
        message_type=message_type,
        message_text=message_text,
        message_file_id=message_file_id,
        message_caption=message_caption,
        forwarded_from_chat_id=forwarded_from_chat_id,
        forwarded_from_message_id=forwarded_from_message_id
    )
    
    # Ask for rate limit
    await message.answer(
        "📨 پیام دریافت شد!\n\n"
        "⚙️ لطفاً سرعت ارسال را مشخص کنید:\n\n"
        "🔢 تعداد پیام در هر دقیقه را وارد کنید:\n"
        "• برای ارسال سریع: 20-30\n"
        "• برای ارسال متوسط: 10-20\n"
        "• برای ارسال آهسته: 1-10\n\n"
        "⚠️ محدودیت تلگرام: حداکثر 30 پیام در ثانیه\n"
        "💡 توصیه: 10-20 پیام در دقیقه (امن)"
    )
    
    # Move to next state
    await state.set_state(BroadcastStates.waiting_rate)


@router.message(BroadcastStates.waiting_rate)
async def process_broadcast_rate(message: Message, state: FSMContext):
    """Process broadcast rate and send messages."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        return
    
    # Validate rate
    try:
        rate_per_minute = int(message.text)
        if rate_per_minute < 1 or rate_per_minute > 1800:  # Max 1800 = 30 per second
            await message.answer("❌ عدد باید بین 1 تا 1800 باشد.")
            return
    except ValueError:
        await message.answer("❌ لطفاً یک عدد صحیح وارد کنید.")
        return
    
    # Get stored message data
    data = await state.get_data()
    admin_id = data['admin_id']
    message_type = data['message_type']
    message_text = data['message_text']
    message_file_id = data['message_file_id']
    message_caption = data['message_caption']
    forwarded_from_chat_id = data['forwarded_from_chat_id']
    forwarded_from_message_id = data['forwarded_from_message_id']
    
    # Calculate delay between messages (in seconds)
    delay_seconds = 60.0 / rate_per_minute
    
    # Create broadcast message in database first
    async for db_session in get_db():
        # Get all users first (no limit - get ALL users)
        users = await get_all_users(db_session, limit=None)
        
        # Create progress message with control buttons
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        progress_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="⏸ توقف موقت", callback_data=f"broadcast:pause:{0}"),
                InlineKeyboardButton(text="🛑 لغو", callback_data=f"broadcast:cancel:{0}")
            ]
        ])
        
        progress_msg = await message.answer(
            f"✅ شروع ارسال پیام همگانی...\n\n"
            f"⚙️ سرعت: {rate_per_minute} پیام در دقیقه\n"
            f"⏱ تأخیر بین پیام‌ها: {delay_seconds:.2f} ثانیه\n\n"
            f"📊 پیشرفت: 0/{len(users)} (0%)\n"
            f"✅ موفق: 0\n"
            f"❌ ناموفق: 0\n\n"
            f"⏳ در حال ارسال...",
            reply_markup=progress_keyboard
        )
        
        # Create broadcast message in database
        broadcast = await create_broadcast_message(
            db_session,
            admin_id=admin_id,
            message_type=message_type,
            message_text=message_text,
            message_file_id=message_file_id,
            message_caption=message_caption,
            forwarded_from_chat_id=forwarded_from_chat_id,
            forwarded_from_message_id=forwarded_from_message_id
        )
        
        # Update progress message with broadcast ID
        progress_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="⏸ توقف موقت", callback_data=f"broadcast:pause:{broadcast.id}"),
                InlineKeyboardButton(text="🛑 لغو", callback_data=f"broadcast:cancel:{broadcast.id}")
            ]
        ])
        await progress_msg.edit_reply_markup(reply_markup=progress_keyboard)
        
        # Users already loaded above (line 325)
        sent_count = 0
        failed_count = 0
        
        from aiogram import Bot
        import asyncio
        bot = Bot(token=settings.BOT_TOKEN)
        
        # Initialize broadcast control
        _active_broadcasts[broadcast.id] = {
            'status': 'running',  # running, paused, cancelled
            'pause_event': asyncio.Event(),
            'stop_event': asyncio.Event(),
        }
        _active_broadcasts[broadcast.id]['pause_event'].set()  # Start as not paused
        
        last_update_time = asyncio.get_event_loop().time()
        update_interval = 3  # Update progress every 3 seconds
        
        # Send broadcast to all users with rate limiting
        for index, user in enumerate(users, start=1):
            # Check if broadcast was cancelled
            if _active_broadcasts[broadcast.id]['status'] == 'cancelled':
                break
            
            # Check if broadcast is paused
            if _active_broadcasts[broadcast.id]['status'] == 'paused':
                await _active_broadcasts[broadcast.id]['pause_event'].wait()
            
            # Update progress message periodically
            current_time = asyncio.get_event_loop().time()
            if current_time - last_update_time >= update_interval or index == 1:
                last_update_time = current_time
                percent = (index / len(users)) * 100
                status_emoji = "⏸" if _active_broadcasts[broadcast.id]['status'] == 'paused' else "⏳"
                
                try:
                    await progress_msg.edit_text(
                        f"{status_emoji} پیام همگانی در حال ارسال...\n\n"
                        f"⚙️ سرعت: {rate_per_minute} پیام/دقیقه\n"
                        f"⏱ تأخیر: {delay_seconds:.2f} ثانیه/پیام\n\n"
                        f"📊 پیشرفت: {index-1}/{len(users)} ({percent:.1f}%)\n"
                        f"✅ موفق: {sent_count}\n"
                        f"❌ ناموفق: {failed_count}\n\n"
                        f"⏳ در حال ارسال...",
                        reply_markup=progress_keyboard
                    )
                except Exception:
                    pass  # Ignore edit errors
            

            try:
                # Send based on message type
                if message_type == "forward":
                    # Forward message
                    if forwarded_from_chat_id and forwarded_from_message_id:
                        sent_msg = await bot.forward_message(
                            chat_id=user.telegram_id,
                            from_chat_id=forwarded_from_chat_id,
                            message_id=forwarded_from_message_id
                        )
                    else:
                        # Fallback to copy if forward not possible
                        if message_text:
                            sent_msg = await bot.send_message(user.telegram_id, message_text)
                        else:
                            continue
                elif message_type == "photo":
                    sent_msg = await bot.send_photo(
                        chat_id=user.telegram_id,
                        photo=message_file_id,
                        caption=message_caption
                    )
                elif message_type == "video":
                    sent_msg = await bot.send_video(
                        chat_id=user.telegram_id,
                        video=message_file_id,
                        caption=message_caption
                    )
                elif message_type == "document":
                    sent_msg = await bot.send_document(
                        chat_id=user.telegram_id,
                        document=message_file_id,
                        caption=message_caption
                    )
                elif message_type == "audio":
                    sent_msg = await bot.send_audio(
                        chat_id=user.telegram_id,
                        audio=message_file_id,
                        caption=message_caption
                    )
                elif message_type == "voice":
                    sent_msg = await bot.send_voice(
                        chat_id=user.telegram_id,
                        voice=message_file_id,
                        caption=message_caption
                    )
                elif message_type == "video_note":
                    sent_msg = await bot.send_video_note(
                        chat_id=user.telegram_id,
                        video_note=message_file_id
                    )
                elif message_type == "sticker":
                    sent_msg = await bot.send_sticker(
                        chat_id=user.telegram_id,
                        sticker=message_file_id
                    )
                elif message_type == "text":
                    sent_msg = await bot.send_message(
                        chat_id=user.telegram_id,
                        text=message_text
                    )
                else:
                    continue
                
                # Create receipt
                await create_broadcast_receipt(
                    db_session,
                    broadcast_id=broadcast.id,
                    user_id=user.id,
                    telegram_message_id=sent_msg.message_id if sent_msg else None,
                    status="sent"
                )
                await increment_broadcast_stats(db_session, broadcast.id, sent=True)
                sent_count += 1
                
                # Rate limiting: wait between messages
                if index < len(users):  # Don't wait after last message
                    await asyncio.sleep(delay_seconds)
                
            except Exception as e:
                # Create failed receipt
                await create_broadcast_receipt(
                    db_session,
                    broadcast_id=broadcast.id,
                    user_id=user.id,
                    status="failed"
                )
                await increment_broadcast_stats(db_session, broadcast.id, failed=True)
                failed_count += 1
        
        await bot.session.close()
        
        # Cleanup broadcast tracking
        broadcast_status = _active_broadcasts[broadcast.id]['status']
        del _active_broadcasts[broadcast.id]
        
        # Get final statistics
        stats = await get_broadcast_statistics(db_session, broadcast.id)
        
        # Update final progress message
        if broadcast_status == 'cancelled':
            final_emoji = "🛑"
            final_text = "لغو شد"
        else:
            final_emoji = "✅"
            final_text = "تکمیل شد"
        
        try:
            await progress_msg.edit_text(
                f"{final_emoji} پیام همگانی {final_text}!\n\n"
                f"⚙️ سرعت: {rate_per_minute} پیام/دقیقه\n"
                f"⏱ تأخیر: {delay_seconds:.2f} ثانیه/پیام\n\n"
                f"📊 آمار نهایی:\n"
            f"• ارسال موفق: {sent_count}\n"
            f"• ارسال ناموفق: {failed_count}\n"
                f"• کل کاربران: {len(users)}\n"
                f"• درصد موفقیت: {(sent_count/len(users)*100):.1f}%\n\n"
            f"🔗 برای مشاهده آمار کامل:\n"
            f"/admin_broadcast_stats {broadcast.id}",
                reply_markup=None
        )
        except Exception:
            pass
        
        await state.clear()
        break


@router.callback_query(F.data.startswith("broadcast:pause:"))
async def handle_broadcast_pause(callback: CallbackQuery):
    """Pause broadcast."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    broadcast_id = int(callback.data.split(":")[-1])
    
    if broadcast_id not in _active_broadcasts:
        await callback.answer("❌ این broadcast دیگر فعال نیست.", show_alert=True)
        return
    
    # Pause the broadcast
    _active_broadcasts[broadcast_id]['status'] = 'paused'
    _active_broadcasts[broadcast_id]['pause_event'].clear()
    
    # Update keyboard
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    pause_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="▶️ ادامه", callback_data=f"broadcast:resume:{broadcast_id}"),
            InlineKeyboardButton(text="🛑 لغو", callback_data=f"broadcast:cancel:{broadcast_id}")
        ]
    ])
    
    try:
        await callback.message.edit_reply_markup(reply_markup=pause_keyboard)
        await callback.answer("⏸ ارسال متوقف شد. برای ادامه روی دکمه 'ادامه' کلیک کنید.")
    except Exception:
        await callback.answer("❌ خطا در به‌روزرسانی.")


@router.callback_query(F.data.startswith("broadcast:resume:"))
async def handle_broadcast_resume(callback: CallbackQuery):
    """Resume broadcast."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    broadcast_id = int(callback.data.split(":")[-1])
    
    if broadcast_id not in _active_broadcasts:
        await callback.answer("❌ این broadcast دیگر فعال نیست.", show_alert=True)
        return
    
    # Resume the broadcast
    _active_broadcasts[broadcast_id]['status'] = 'running'
    _active_broadcasts[broadcast_id]['pause_event'].set()
    
    # Update keyboard
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    resume_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⏸ توقف موقت", callback_data=f"broadcast:pause:{broadcast_id}"),
            InlineKeyboardButton(text="🛑 لغو", callback_data=f"broadcast:cancel:{broadcast_id}")
        ]
    ])
    
    try:
        await callback.message.edit_reply_markup(reply_markup=resume_keyboard)
        await callback.answer("▶️ ارسال ادامه یافت.")
    except Exception:
        await callback.answer("❌ خطا در به‌روزرسانی.")


@router.callback_query(F.data.startswith("broadcast:cancel:"))
async def handle_broadcast_cancel(callback: CallbackQuery):
    """Cancel broadcast."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    broadcast_id = int(callback.data.split(":")[-1])
    
    if broadcast_id not in _active_broadcasts:
        await callback.answer("❌ این broadcast دیگر فعال نیست.", show_alert=True)
        return
    
    # Cancel the broadcast
    _active_broadcasts[broadcast_id]['status'] = 'cancelled'
    _active_broadcasts[broadcast_id]['pause_event'].set()  # Unpause if paused
    
    await callback.answer("🛑 ارسال لغو شد.", show_alert=True)


@router.message(Command("admin_broadcast_stats"))
async def cmd_broadcast_stats(message: Message):
    """View broadcast message statistics."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        return
    
    # Parse broadcast ID from command
    try:
        broadcast_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.answer("❌ Usage: /admin_broadcast_stats <broadcast_id>")
        return
    
    async for db_session in get_db():
        stats = await get_broadcast_statistics(db_session, broadcast_id)
        
        if not stats:
            await message.answer(f"❌ پیام همگانی با ID {broadcast_id} یافت نشد.")
            return
        
        await message.answer(
            f"📊 آمار پیام همگانی ID: {broadcast_id}\n\n"
            f"📝 نوع پیام: {stats.get('message_type', 'نامشخص')}\n\n"
            f"📈 ارسال:\n"
            f"• موفق: {stats.get('sent_count', 0)}\n"
            f"• ناموفق: {stats.get('failed_count', 0)}\n"
            f"• باز شده: {stats.get('opened_count', 0)}\n\n"
            f"📊 نرخ باز شدن: {stats.get('open_rate', 0)}%\n\n"
            f"📅 تاریخ: {stats.get('created_at').strftime('%Y-%m-%d %H:%M') if stats.get('created_at') else 'نامشخص'}",
            parse_mode=None
        )
        break


@router.message(Command("admin_broadcast_list"))
async def cmd_broadcast_list(message: Message):
    """List all broadcast messages."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        return
    
    async for db_session in get_db():
        broadcasts = await get_broadcast_messages(db_session, admin_id=message.from_user.id, limit=20)
        
        if not broadcasts:
            await message.answer("📋 هیچ پیام همگانی ارسال نشده است.", parse_mode=None)
            return
        
        text = "📋 لیست پیام‌های همگانی\n\n"
        for broadcast in broadcasts:
            text += (
                f"ID: {broadcast.id} - {broadcast.message_type}\n"
                f"  ✅ {broadcast.sent_count} | ❌ {broadcast.failed_count} | 👁️ {broadcast.opened_count}\n"
                f"  📅 {broadcast.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            )
        
        text += "\nبرای مشاهده آمار کامل: /admin_broadcast_stats <id>"
        
        await message.answer(text, parse_mode=None)
        break


# ==================== Queue-Based Broadcast ====================

@router.message(Command("admin_broadcast_queue"))
async def cmd_admin_broadcast_queue(message: Message, state: FSMContext):
    """Start queue-based broadcast process (recommended for 100k+ users)."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        return

    await message.answer(
        "📢 <b>ارسال پیام همگانی (سیستم صف)</b>\n\n"
        "این سیستم برای ارسال به تعداد زیاد کاربر (100k+) بهینه شده است.\n\n"
        "✅ <b>ویژگی‌ها:</b>\n"
        "• ارسال با سرعت 15 پیام/ثانیه\n"
        "• مدیریت خودکار FloodWait\n"
        "• پردازش در پس‌زمینه\n"
        "• تلاش مجدد در صورت خطا\n\n"
        "📝 لطفاً پیام خود را ارسال کنید:\n"
        "• متن\n"
        "• عکس با کپشن\n"
        "• ویدیو با کپشن\n"
        "• فایل با کپشن\n"
        "• پیام فوروارد شده",
        parse_mode='HTML'
    )
    await state.set_state(QueueBroadcastStates.waiting_message)


@router.message(QueueBroadcastStates.waiting_message)
async def process_queue_broadcast_message(message: Message, state: FSMContext):
    """Process broadcast message for queue system."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        return

    # Determine message type and extract content
    message_type = "text"
    message_text = None
    message_file_id = None
    message_caption = None
    forwarded_from_chat_id = None
    forwarded_from_message_id = None

    if message.forward_from_chat or message.forward_from_message_id:
        # Forwarded message
        message_type = "forward"
        forwarded_from_chat_id = message.forward_from_chat.id if message.forward_from_chat else None
        forwarded_from_message_id = message.forward_from_message_id
        message_text = message.text or message.caption
        message_caption = message.caption
    elif message.photo:
        message_type = "photo"
        message_file_id = message.photo[-1].file_id
        message_caption = message.caption
        message_text = message.caption
    elif message.video:
        message_type = "video"
        message_file_id = message.video.file_id
        message_caption = message.caption
        message_text = message.caption
    elif message.document:
        message_type = "document"
        message_file_id = message.document.file_id
        message_caption = message.caption
        message_text = message.caption or message.document.file_name
    elif message.audio:
        message_type = "audio"
        message_file_id = message.audio.file_id
        message_caption = message.caption
        message_text = message.caption
    elif message.voice:
        message_type = "voice"
        message_file_id = message.voice.file_id
        message_caption = message.caption
        message_text = message.caption
    elif message.video_note:
        message_type = "video_note"
        message_file_id = message.video_note.file_id
    elif message.animation:
        message_type = "animation"
        message_file_id = message.animation.file_id
        message_caption = message.caption
        message_text = message.caption
    elif message.sticker:
        message_type = "sticker"
        message_file_id = message.sticker.file_id
    elif message.text:
        message_type = "text"
        message_text = message.text
    else:
        await message.answer("❌ نوع پیام پشتیبانی نمی‌شود.")
        await state.clear()
        return

    # Store message data in FSM
    await state.update_data(
        admin_id=message.from_user.id,
        message_type=message_type,
        message_text=message_text,
        message_file_id=message_file_id,
        message_caption=message_caption,
        forwarded_from_chat_id=forwarded_from_chat_id,
        forwarded_from_message_id=forwarded_from_message_id
    )

    # Get user count
    async for db_session in get_db():
        from utils.broadcast_service import BroadcastService
        broadcast_service = BroadcastService()
        user_stats = await broadcast_service.get_user_stats(db_session)
        total_users = user_stats.get('active', 0)

        # Calculate estimated time
        messages_per_second = 15
        estimated_minutes = total_users / messages_per_second / 60

        # Show preview and ask for confirmation
        preview_text = "📢 <b>پیش‌نمایش پیام همگانی</b>\n\n"
        preview_text += f"📝 نوع: {message_type}\n"
        if message_text:
            preview_text += f"💬 متن: {message_text[:100]}...\n" if len(message_text) > 100 else f"💬 متن: {message_text}\n"
        preview_text += f"\n👥 <b>کاربران فعال:</b> {total_users:,}\n"
        preview_text += f"⏱ <b>زمان تقریبی:</b> {estimated_minutes:.1f} دقیقه\n"
        preview_text += f"🚀 <b>سرعت:</b> 15 پیام/ثانیه\n\n"
        preview_text += "⚠️ <b>توجه:</b> پیام به صف اضافه می‌شود و در پس‌زمینه ارسال خواهد شد.\n\n"
        preview_text += "آیا می‌خواهید ادامه دهید؟"

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ تأیید و ارسال", callback_data="queue_broadcast:confirm"),
                InlineKeyboardButton(text="❌ لغو", callback_data="queue_broadcast:cancel")
            ]
        ])

        await message.answer(preview_text, parse_mode='HTML', reply_markup=confirm_keyboard)
        await state.set_state(QueueBroadcastStates.waiting_confirmation)
        break


@router.callback_query(F.data == "queue_broadcast:confirm")
async def confirm_queue_broadcast(callback: CallbackQuery, state: FSMContext):
    """Confirm and create broadcast in queue."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return

    # Get stored message data
    data = await state.get_data()
    if not data:
        await callback.message.edit_text("❌ خطا: داده‌های پیام یافت نشد.")
        await state.clear()
        return

    async for db_session in get_db():
        try:
            from utils.broadcast_service import BroadcastService
            broadcast_service = BroadcastService()

            # Create broadcast in database
            broadcast = await broadcast_service.create_broadcast_message(
                session=db_session,
                admin_id=data['admin_id'],
                message_type=data['message_type'],
                message_text=data.get('message_text'),
                message_file_id=data.get('message_file_id'),
                message_caption=data.get('message_caption'),
                forwarded_from_chat_id=data.get('forwarded_from_chat_id'),
                forwarded_from_message_id=data.get('forwarded_from_message_id'),
            )

            await callback.message.edit_text(
                f"✅ <b>پیام همگانی در صف قرار گرفت!</b>\n\n"
                f"📋 <b>شناسه:</b> {broadcast.id}\n"
                f"📝 <b>نوع:</b> {broadcast.message_type}\n"
                f"📊 <b>وضعیت:</b> در انتظار پردازش\n\n"
                f"⏳ پیام به زودی توسط سیستم پردازش و ارسال خواهد شد.\n\n"
                f"💡 برای مشاهده وضعیت:\n"
                f"/admin_broadcast_stats {broadcast.id}",
                parse_mode='HTML'
            )
            
            await state.clear()
            await callback.answer("✅ پیام در صف قرار گرفت!")
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error creating queue broadcast: {e}")
            await callback.message.edit_text(
                f"❌ خطا در ایجاد پیام همگانی:\n{str(e)}"
            )
            await state.clear()
        
        break


@router.callback_query(F.data == "queue_broadcast:cancel")
async def cancel_queue_broadcast(callback: CallbackQuery, state: FSMContext):
    """Cancel queue broadcast creation."""
    await callback.message.edit_text("❌ ارسال پیام همگانی لغو شد.")
    await state.clear()
    await callback.answer("لغو شد")


@router.callback_query(F.data.startswith("admin:referral_link:delete:"))
async def delete_referral_link(callback: CallbackQuery):
    """Delete a referral link."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    link_id = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        success = await delete_admin_referral_link(db_session, link_id)
        
        if success:
            await callback.message.edit_text(
                "✅ لینک با موفقیت حذف شد!",
                reply_markup=get_admin_referral_links_keyboard()
            )
        else:
            await callback.answer("❌ خطا در حذف لینک.", show_alert=True)
        
        await callback.answer()
        break


@router.callback_query(F.data.startswith("admin:referral_link:list:"))
async def list_referral_links_pagination(callback: CallbackQuery):
    """List referral links with pagination."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    page = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        links = await get_admin_referral_links(db_session, admin_id=callback.from_user.id)
        
        if not links:
            await callback.message.edit_text(
                "📋 لینک‌های عضویت\n\n"
                "هنوز هیچ لینکی ایجاد نشده است.",
                reply_markup=get_admin_referral_links_keyboard()
            )
        else:
            total_pages = (len(links) + 4) // 5  # 5 links per page
            await callback.message.edit_text(
                f"📋 لینک‌های عضویت\n\n"
                f"تعداد کل: {len(links)}\n"
                f"صفحه {page + 1} از {total_pages}\n\n"
                f"برای مشاهده جزئیات روی لینک کلیک کنید:",
                reply_markup=get_referral_link_list_keyboard(links, page=page, total_pages=total_pages),
                parse_mode=None
            )
        
        await callback.answer()
        break


@router.callback_query(F.data == "admin:user:search")
async def admin_user_search_start(callback: CallbackQuery, state: FSMContext):
    """Start user search."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔍 جستجوی کاربر\n\n"
        "لطفاً ID کاربر، نام کاربری، یا Telegram ID را وارد کنید:"
    )
    await callback.answer()
    # State will be handled in message handler


@router.callback_query(F.data == "admin:users:banned")
async def admin_banned_users(callback: CallbackQuery):
    """Show banned users."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    async for db_session in get_db():
        from sqlalchemy import select
        from db.models import User
        
        result = await db_session.execute(
            select(User).where(User.is_banned == True).limit(20)
        )
        banned_users = result.scalars().all()
        
        if not banned_users:
            await callback.message.edit_text(
                "🚫 کاربران مسدود شده\n\n"
                "هیچ کاربری مسدود نشده است.",
                reply_markup=get_admin_users_keyboard()
            )
        else:
            text = "🚫 کاربران مسدود شده\n\n"
            for user in banned_users:
                text += f"• ID: {user.id} | @{user.username or 'بدون نام'}\n"
            
            await callback.message.edit_text(
                text,
                reply_markup=get_admin_users_keyboard()
            )
        
        await callback.answer()
        break


@router.callback_query(F.data == "admin:users:premium")
async def admin_premium_users(callback: CallbackQuery):
    """Show premium users."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    async for db_session in get_db():
        premium_count = await get_premium_count(db_session)
        
        from sqlalchemy import select
        from db.models import User
        from datetime import datetime
        
        result = await db_session.execute(
            select(User)
            .where(User.is_premium == True)
            .where(User.premium_expires_at > datetime.utcnow())
            .limit(20)
        )
        users = result.scalars().all()
        
        if not users:
            await callback.message.edit_text(
                "💎 کاربران پریمیوم\n\n"
                "هیچ کاربر پریمیومی وجود ندارد.",
                reply_markup=get_admin_users_keyboard()
            )
        else:
            text = f"💎 کاربران پریمیوم ({premium_count} نفر)\n\n"
            for user in users:
                expires = user.premium_expires_at.strftime("%Y-%m-%d") if user.premium_expires_at else "نامشخص"
                text += f"• ID: {user.id} | @{user.username or 'بدون نام'} | انقضا: {expires}\n"
            
            await callback.message.edit_text(
                text,
                reply_markup=get_admin_users_keyboard()
            )
        
        await callback.answer()
        break


@router.message(Command("admin_ban"))
async def cmd_admin_ban(message: Message):
    """Ban a user."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Access denied.")
        return
    
    # Parse user ID from command
    try:
        user_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.answer("❌ Usage: /admin_ban <user_id>")
        return
    
    async for db_session in get_db():
        user = await get_user_by_id(db_session, user_id)
        
        if not user:
            await message.answer(f"❌ User with ID {user_id} not found.")
            return
        
        success = await ban_user(db_session, user_id)
        
        if success:
            await message.answer(f"✅ User {user_id} has been banned.")
        else:
            await message.answer(f"❌ Failed to ban user {user_id}.")
        break


@router.message(Command("admin_unban"))
async def cmd_admin_unban(message: Message):
    """Unban a user."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Access denied.")
        return
    
    # Parse user ID from command
    try:
        user_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.answer("❌ Usage: /admin_unban <user_id>")
        return
    
    async for db_session in get_db():
        user = await get_user_by_id(db_session, user_id)
        
        if not user:
            await message.answer(f"❌ User with ID {user_id} not found.")
            return
        
        success = await unban_user(db_session, user_id)
        
        if success:
            await message.answer(f"✅ User {user_id} has been unbanned.")
        else:
            await message.answer(f"❌ Failed to unban user {user_id}.")
        break


@router.message(Command("admin_users"))
async def cmd_admin_users(message: Message):
    """List users with pagination."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Access denied.")
        return
    
    async for db_session in get_db():
        users = await get_all_users(db_session, skip=0, limit=10)
        
        if not users:
            await message.answer("No users found.")
            return
        
        user_list = []
        for user in users:
            status = "🚫 Banned" if user.is_banned else "✅ Active"
            premium = "💎 Premium" if user.is_premium else ""
            user_list.append(f"{user.id}. {user.username or 'No username'} {status} {premium}")
        
        await message.answer(
            f"👥 Users (showing first 10):\n\n" + "\n".join(user_list)
        )
        break


@router.message(Command("admin_reports"))
async def cmd_admin_reports(message: Message):
    """View unresolved reports."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Access denied.")
        return
    
    async for db_session in get_db():
        reports = await get_unresolved_reports(db_session, skip=0, limit=10)
        
        if not reports:
            await message.answer("No unresolved reports.")
            return
        
        report_list = []
        for report in reports:
            report_list.append(
                f"Report ID: {report.id}\n"
                f"Reporter: {report.reporter_id}\n"
                f"Reported: {report.reported_id}\n"
                f"Type: {report.report_type}\n"
                f"Reason: {report.reason[:50] if report.reason else 'N/A'}...\n"
            )
        
        await message.answer(
            f"⚠️ Unresolved Reports (showing first 10):\n\n" + "\n\n".join(report_list),
            parse_mode=None
        )
        break


# ============= Admin Panel Handlers (Reply Keyboard) =============

@router.message(F.text == "📊 آمار و گزارشات")
async def admin_stats_button(message: Message):
    """Handle admin stats button."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        return
    
    async for db_session in get_db():
        total_users = await get_user_count(db_session)
        active_chats = await get_active_chat_count(db_session)
        premium_users = await get_premium_count(db_session)
        
        # Get coin statistics
        from db.crud import get_all_users
        from core.points_manager import PointsManager
        users = await get_all_users(db_session)
        total_coins = 0
        for user in users:
            total_coins += await PointsManager.get_balance(user.id)
        
        await message.answer(
            f"📊 آمار ربات\n\n"
            f"👥 کل کاربران: {total_users}\n"
            f"💬 چت‌های فعال: {active_chats}\n"
            f"💎 کاربران پریمیوم: {premium_users}\n"
            f"💰 کل سکه‌های توزیع شده: {total_coins}\n\n"
            f"پنل مدیریت:",
            reply_markup=get_admin_main_keyboard()
        )
        break


@router.message(F.text == "👥 مدیریت کاربران")
async def admin_users_button(message: Message):
    """Handle admin users management button."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        return
    
    await message.answer(
        "👥 مدیریت کاربران\n\n"
        "از منوی زیر انتخاب کنید:",
        reply_markup=get_admin_users_keyboard()
    )


@router.message(F.text == "🔗 لینک‌های عضویت")
async def admin_referral_links_button(message: Message):
    """Handle admin referral links button."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        return
    
    await message.answer(
        "🔗 لینک‌های عضویت\n\n"
        "از منوی زیر انتخاب کنید:",
        reply_markup=get_admin_referral_links_keyboard()
    )


@router.message(F.text == "💰 تنظیمات سکه")
async def admin_coin_settings_button(message: Message):
    """Handle admin coin settings button."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        return
    
    async for db_session in get_db():
        settings_list = await get_all_coin_settings(db_session)
        
        text = "💰 تنظیمات قیمت سکه‌ها\n\n"
        for setting in settings_list:
            status = "✅ فعال" if setting.is_active else "❌ غیرفعال"
            text += f"{setting.premium_days} روز: {setting.coins_required} سکه ({status})\n"
        
        text += "\nبرای ویرایش یکی از گزینه‌ها را انتخاب کنید:"
        
        await message.answer(
            text,
            reply_markup=get_admin_coin_settings_keyboard()
        )
        break


@router.message(F.text == "📢 ارسال پیام همگانی")
async def admin_broadcast_button(message: Message, state: FSMContext):
    """Handle admin broadcast button."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        return
    
    await message.answer(
        "📢 ارسال پیام همگانی\n\n"
        "لطفاً پیامی که می‌خواهید برای همه کاربران ارسال شود را ارسال کنید:\n\n"
        "✅ پشتیبانی از:\n"
        "• متن\n"
        "• عکس\n"
        "• ویدیو\n"
        "• فایل\n"
        "• صدا\n"
        "• استیکر\n"
        "• فوروارد\n"
        "و...\n\n"
        "همچنین می‌توانید پیام را فوروارد کنید."
    )
    await state.set_state(BroadcastStates.waiting_message)


@router.message(F.text == "🎯 مدیریت ایونت‌ها")
async def admin_events_button(message: Message):
    """Handle admin events management button."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        return
    
    from bot.keyboards.event_admin import get_admin_events_keyboard
    from db.crud import get_all_events
    
    async for db_session in get_db():
        events = await get_all_events(db_session, skip=0, limit=10)
        
        text = "🎯 مدیریت ایونت‌ها\n\n"
        
        if events:
            text += "📋 ایونت‌های اخیر:\n\n"
            from datetime import datetime
            now = datetime.utcnow()
            for event in events[:5]:
                status = "✅ فعال" if event.is_active else "❌ غیرفعال"
                if event.start_date <= now <= event.end_date:
                    status += " (در حال اجرا)"
                elif event.end_date < now:
                    status += " (پایان یافته)"
                elif event.start_date > now:
                    status += " (آینده)"
                
                text += f"• {event.event_name}\n"
                text += f"  نوع: {event.event_type}\n"
                text += f"  وضعیت: {status}\n\n"
        else:
            text += "هیچ ایونتی وجود ندارد.\n\n"
        
        text += "از منوی زیر انتخاب کنید:"
        
        await message.answer(
            text,
            reply_markup=get_admin_events_keyboard()
        )
        break


@router.message(F.text == "⚙️ تنظیمات")
async def admin_settings_button(message: Message):
    """Handle admin settings button."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        return
    
    await message.answer(
        "⚙️ تنظیمات\n\n"
        "از منوی زیر انتخاب کنید:",
        reply_markup=get_admin_main_keyboard()
    )


# ============= Admin Panel Callback Handlers =============

@router.callback_query(F.data == "admin:main")
async def admin_main_panel(callback: CallbackQuery):
    """Show admin main panel."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔧 پنل مدیریت ربات\n\n"
        "از منوی زیر انتخاب کنید:",
        reply_markup=get_admin_main_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:events")
async def admin_events_panel(callback: CallbackQuery):
    """Show admin events management panel."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    from bot.keyboards.event_admin import get_admin_events_keyboard
    from db.crud import get_all_events
    
    async for db_session in get_db():
        events = await get_all_events(db_session, skip=0, limit=10)
        
        text = "🎯 مدیریت ایونت‌ها\n\n"
        
        if events:
            text += "📋 ایونت‌های اخیر:\n\n"
            from datetime import datetime
            now = datetime.utcnow()
            for event in events[:5]:
                status = "✅ فعال" if event.is_active else "❌ غیرفعال"
                if event.start_date <= now <= event.end_date:
                    status += " (در حال اجرا)"
                elif event.end_date < now:
                    status += " (پایان یافته)"
                elif event.start_date > now:
                    status += " (آینده)"
                
                text += f"• {event.event_name}\n"
                text += f"  نوع: {event.event_type}\n"
                text += f"  وضعیت: {status}\n\n"
        else:
            text += "هیچ ایونتی وجود ندارد.\n\n"
        
        text += "از منوی زیر انتخاب کنید:"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_admin_events_keyboard()
        )
        await callback.answer()
        break


@router.callback_query(F.data == "admin:event:create")
async def admin_event_create_callback(callback: CallbackQuery, state: FSMContext):
    """Start creating a new event."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🎯 ایجاد ایونت جدید\n\n"
        "لطفاً نام ایونت را ارسال کنید:"
    )
    from bot.handlers.event_admin import EventStates
    await state.set_state(EventStates.waiting_event_name)
    await callback.answer()


@router.callback_query(F.data == "admin:event:list")
async def admin_event_list_callback(callback: CallbackQuery):
    """Show event list."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    from bot.keyboards.event_admin import get_event_list_keyboard
    from db.crud import get_all_events
    
    async for db_session in get_db():
        events = await get_all_events(db_session, skip=0, limit=100)
        
        if not events:
            await callback.message.edit_text(
                "📋 لیست ایونت‌ها\n\n"
                "هیچ ایونتی وجود ندارد.",
                reply_markup=get_admin_events_keyboard()
            )
            await callback.answer()
            return
        
        # Pagination
        page = 0
        total_pages = (len(events) + 4) // 5  # 5 events per page
        
        text = f"📋 لیست ایونت‌ها ({len(events)})\n\n"
        from datetime import datetime
        now = datetime.utcnow()
        
        for event in events[:5]:
            status = "✅ فعال" if event.is_active else "❌ غیرفعال"
            if event.start_date <= now <= event.end_date:
                status += " (در حال اجرا)"
            elif event.end_date < now:
                status += " (پایان یافته)"
            elif event.start_date > now:
                status += " (آینده)"
            
            text += f"🎯 {event.event_name}\n"
            text += f"   نوع: {event.event_type}\n"
            text += f"   وضعیت: {status}\n\n"
        
        if len(events) > 5:
            text += f"... و {len(events) - 5} ایونت دیگر"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_event_list_keyboard(events, page, total_pages)
        )
        await callback.answer()
        break


@router.callback_query(F.data.startswith("admin:event:list:"))
async def admin_event_list_page(callback: CallbackQuery):
    """Show event list with pagination."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    try:
        page = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer("❌ خطا", show_alert=True)
        return
    
    from bot.keyboards.event_admin import get_event_list_keyboard
    from db.crud import get_all_events
    
    async for db_session in get_db():
        events = await get_all_events(db_session, skip=0, limit=100)
        
        total_pages = (len(events) + 4) // 5
        start_idx = page * 5
        end_idx = min(start_idx + 5, len(events))
        
        text = f"📋 لیست ایونت‌ها ({len(events)})\n\n"
        from datetime import datetime
        now = datetime.utcnow()
        
        for event in events[start_idx:end_idx]:
            status = "✅ فعال" if event.is_active else "❌ غیرفعال"
            if event.start_date <= now <= event.end_date:
                status += " (در حال اجرا)"
            elif event.end_date < now:
                status += " (پایان یافته)"
            elif event.start_date > now:
                status += " (آینده)"
            
            text += f"🎯 {event.event_name}\n"
            text += f"   نوع: {event.event_type}\n"
            text += f"   وضعیت: {status}\n\n"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_event_list_keyboard(events, page, total_pages)
        )
        await callback.answer()
        break


@router.callback_query(F.data.startswith("admin:event:view:"))
async def admin_event_view(callback: CallbackQuery):
    """View event details."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    try:
        event_id = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer("❌ خطا", show_alert=True)
        return
    
    from bot.keyboards.event_admin import get_event_detail_keyboard
    from db.crud import get_event_by_id, get_event_participant_count, get_event_rewards
    
    async for db_session in get_db():
        event = await get_event_by_id(db_session, event_id)
        if not event:
            await callback.answer("❌ ایونت یافت نشد.", show_alert=True)
            return
        
        participant_count = await get_event_participant_count(db_session, event_id)
        rewards = await get_event_rewards(db_session, event_id, limit=10)
        
        from datetime import datetime
        now = datetime.utcnow()
        status = "✅ فعال" if event.is_active else "❌ غیرفعال"
        if event.start_date <= now <= event.end_date:
            status += " (در حال اجرا)"
        elif event.end_date < now:
            status += " (پایان یافته)"
        elif event.start_date > now:
            status += " (آینده)"
        
        text = f"🎯 جزئیات ایونت\n\n"
        text += f"📌 نام: {event.event_name}\n"
        text += f"🔑 کلید: {event.event_key}\n"
        text += f"🎯 نوع: {event.event_type}\n"
        text += f"📅 تاریخ: {event.start_date.strftime('%Y-%m-%d %H:%M')} تا {event.end_date.strftime('%Y-%m-%d %H:%M')}\n"
        text += f"📊 وضعیت: {status}\n"
        text += f"👥 شرکت‌کنندگان: {participant_count}\n"
        text += f"🎁 پاداش‌های توزیع شده: {len(rewards)}\n"
        
        if event.event_description:
            text += f"\n📝 توضیحات:\n{event.event_description}\n"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_event_detail_keyboard(event_id)
        )
        await callback.answer()
        break


@router.callback_query(F.data.startswith("admin:event:delete:"))
async def admin_event_delete(callback: CallbackQuery):
    """Delete an event."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    try:
        event_id = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer("❌ خطا", show_alert=True)
        return
    
    from db.crud import get_event_by_id, delete_event
    
    async for db_session in get_db():
        event = await get_event_by_id(db_session, event_id)
        if not event:
            await callback.answer("❌ ایونت یافت نشد.", show_alert=True)
            return
        
        await delete_event(db_session, event_id)
        
        await callback.answer(f"✅ ایونت «{event.event_name}» حذف شد.", show_alert=True)
        await admin_event_list_callback(callback)
        break


@router.callback_query(F.data.startswith("admin:event:stats:"))
async def admin_event_stats(callback: CallbackQuery):
    """Show event statistics and participants."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    try:
        event_id = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer("❌ خطا", show_alert=True)
        return
    
    from bot.keyboards.event_admin import get_event_detail_keyboard
    from db.crud import get_event_by_id, get_event_participant_count, get_event_rewards, get_event_participants
    from db.crud import get_user_by_id
    
    async for db_session in get_db():
        event = await get_event_by_id(db_session, event_id)
        if not event:
            await callback.answer("❌ ایونت یافت نشد.", show_alert=True)
            return
        
        participant_count = await get_event_participant_count(db_session, event_id)
        participants = await get_event_participants(db_session, event_id, skip=0, limit=20, order_by_progress=True)
        rewards = await get_event_rewards(db_session, event_id, limit=100)
        
        # Parse event config
        import json
        config = {}
        if event.config_json:
            try:
                config = json.loads(event.config_json)
            except:
                pass
        
        from datetime import datetime
        now = datetime.utcnow()
        status = "✅ فعال" if event.is_active else "❌ غیرفعال"
        if event.start_date <= now <= event.end_date:
            status += " (در حال اجرا)"
        elif event.end_date < now:
            status += " (پایان یافته)"
        elif event.start_date > now:
            status += " (آینده)"
        
        text = f"📊 آمار و شرکت‌کنندگان ایونت\n\n"
        text += f"🎯 {event.event_name}\n\n"
        text += f"📊 آمار کلی:\n"
        text += f"• شرکت‌کنندگان: {participant_count}\n"
        text += f"• پاداش‌های توزیع شده: {len(rewards)}\n"
        text += f"• وضعیت: {status}\n\n"
        
        # Show top participants
        if participants:
            text += f"🏆 برترین شرکت‌کنندگان:\n\n"
            for idx, participant in enumerate(participants[:10], 1):
                user = await get_user_by_id(db_session, participant.user_id)
                if user:
                    username = user.username or user.first_name or f"User {user.telegram_id}"
                else:
                    username = f"User {participant.user_id}"
                
                if event.event_type == "challenge_lottery":
                    target_value = config.get("target_value", 0)
                    text += f"{idx}. {username}: {participant.progress_value}/{target_value}\n"
                else:
                    text += f"{idx}. {username}: {participant.progress_value}\n"
        
        # Show rewards summary
        if rewards:
            premium_rewards = sum(1 for r in rewards if r.reward_type == "premium_days")
            points_rewards = sum(1 for r in rewards if r.reward_type == "points")
            lottery_winners = sum(1 for r in rewards if r.is_lottery_winner)
            
            text += f"\n🎁 پاداش‌ها:\n"
            if premium_rewards > 0:
                text += f"• پریمیوم: {premium_rewards}\n"
            if points_rewards > 0:
                text += f"• سکه: {points_rewards}\n"
            if lottery_winners > 0:
                text += f"• برندگان قرعه‌کشی: {lottery_winners}\n"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_event_detail_keyboard(event_id)
        )
        await callback.answer()
        break


@router.callback_query(F.data.startswith("admin:event:edit:"))
async def admin_event_edit(callback: CallbackQuery, state: FSMContext):
    """Start editing an event."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    try:
        event_id = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer("❌ خطا", show_alert=True)
        return
    
    from db.crud import get_event_by_id
    from bot.keyboards.event_admin import get_event_detail_keyboard
    
    async for db_session in get_db():
        event = await get_event_by_id(db_session, event_id)
        if not event:
            await callback.answer("❌ ایونت یافت نشد.", show_alert=True)
            return
        
        await callback.message.edit_text(
            f"✏️ ویرایش ایونت\n\n"
            f"📌 نام فعلی: {event.event_name}\n"
            f"🎯 نوع: {event.event_type}\n\n"
            f"⚠️ در حال حاضر ویرایش ایونت از طریق رابط کاربری پشتیبانی نمی‌شود.\n\n"
            f"💡 برای ویرایش ایونت:\n"
            f"• می‌توانید ایونت را حذف و دوباره ایجاد کنید\n"
            f"• یا از دستورات SQL استفاده کنید\n\n"
            f"🔧 گزینه‌های موجود:\n"
            f"• فعال/غیرفعال کردن ایونت\n"
            f"• حذف ایونت\n"
            f"• مشاهده آمار",
            reply_markup=get_event_detail_keyboard(event_id)
        )
        await callback.answer()
        break


@router.callback_query(F.data.startswith("admin:event:toggle:"))
async def admin_event_toggle(callback: CallbackQuery):
    """Toggle event active status."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    try:
        event_id = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer("❌ خطا", show_alert=True)
        return
    
    from db.crud import get_event_by_id, update_event
    
    async for db_session in get_db():
        event = await get_event_by_id(db_session, event_id)
        if not event:
            await callback.answer("❌ ایونت یافت نشد.", show_alert=True)
            return
        
        new_status = not event.is_active
        await update_event(db_session, event_id, is_active=new_status)
        
        status_text = "فعال" if new_status else "غیرفعال"
        await callback.answer(f"✅ ایونت «{event.event_name}» {status_text} شد.", show_alert=True)
        await admin_event_view(callback)
        break


@router.callback_query(F.data == "admin:event:lottery")
async def admin_event_lottery_menu(callback: CallbackQuery):
    """Show lottery menu."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🎲 اجرای قرعه‌کشی\n\n"
        "برای اجرای قرعه‌کشی یک ایونت چالش، از دستور زیر استفاده کنید:\n\n"
        "/admin_event_lottery <event_id> [winner_count]\n\n"
        "مثال:\n"
        "/admin_event_lottery 1 10\n\n"
        "این دستور برای ایونت با ID=1، 10 برنده انتخاب می‌کند.",
        reply_markup=get_admin_events_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:leaderboard:main")
async def admin_leaderboard_main(callback: CallbackQuery):
    """Show admin leaderboard main menu."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🏆 رتبه‌بندی کاربران (پنل ادمین)\n\n"
        "انتخاب کنید:",
        reply_markup=get_admin_leaderboard_main_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:leaderboard:points"))
async def admin_leaderboard_points(callback: CallbackQuery):
    """Show admin points leaderboard."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    data = callback.data.split(":")
    period = data[3] if len(data) > 3 else None
    
    if period is None:
        await callback.message.edit_text(
            "💰 رتبه‌بندی بر اساس امتیاز\n\n"
            "انتخاب کنید:",
            reply_markup=get_admin_leaderboard_period_keyboard("points")
        )
        await callback.answer()
        return
    
    period_filter = None if period == "all" else period
    
    async for db_session in get_db():
        top_users = await get_top_users_by_points(db_session, limit=20, period=period_filter)
        
        period_text = {
            "week": "هفته",
            "month": "ماه",
            "all": "همه زمان‌ها"
        }.get(period, "همه زمان‌ها")
        
        text = f"💰 رتبه‌بندی بر اساس امتیاز ({period_text})\n\n"
        
        if top_users:
            text += "🏆 برترین کاربران:\n\n"
            medals = ["🥇", "🥈", "🥉"]
            for user_id, points, rank, display_name, profile_id, gender in top_users:
                medal = medals[rank - 1] if rank <= 3 else f"{rank}."
                gender_emoji = get_gender_emoji(gender)
                profile_id_str = format_profile_id(profile_id)
                text += f"{medal} {gender_emoji} {display_name} {profile_id_str}: {points:,} امتیاز\n"
        else:
            text += "📭 هنوز کاربری وجود ندارد.\n"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_admin_leaderboard_period_keyboard("points")
        )
        await callback.answer()
        break


@router.callback_query(F.data.startswith("admin:leaderboard:referrals"))
async def admin_leaderboard_referrals(callback: CallbackQuery):
    """Show admin referrals leaderboard."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    data = callback.data.split(":")
    period = data[3] if len(data) > 3 else None
    
    if period is None:
        await callback.message.edit_text(
            "👥 رتبه‌بندی بر اساس دعوت\n\n"
            "انتخاب کنید:",
            reply_markup=get_admin_leaderboard_period_keyboard("referrals")
        )
        await callback.answer()
        return
    
    period_filter = None if period == "all" else period
    
    async for db_session in get_db():
        top_users = await get_top_users_by_referrals(db_session, limit=20, period=period_filter)
        
        period_text = {
            "week": "هفته",
            "month": "ماه",
            "all": "همه زمان‌ها"
        }.get(period, "همه زمان‌ها")
        
        text = f"👥 رتبه‌بندی بر اساس دعوت ({period_text})\n\n"
        
        if top_users:
            text += "🏆 برترین کاربران:\n\n"
            medals = ["🥇", "🥈", "🥉"]
            for user_id, count, rank, display_name, profile_id, gender in top_users:
                medal = medals[rank - 1] if rank <= 3 else f"{rank}."
                gender_emoji = get_gender_emoji(gender)
                profile_id_str = format_profile_id(profile_id)
                text += f"{medal} {gender_emoji} {display_name} {profile_id_str}: {count} دعوت\n"
        else:
            text += "📭 هنوز کاربری وجود ندارد.\n"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_admin_leaderboard_period_keyboard("referrals")
        )
        await callback.answer()
        break


@router.callback_query(F.data.startswith("admin:leaderboard:likes"))
async def admin_leaderboard_likes(callback: CallbackQuery):
    """Show admin likes leaderboard."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    data = callback.data.split(":")
    period = data[3] if len(data) > 3 else None
    
    if period is None:
        await callback.message.edit_text(
            "❤️ رتبه‌بندی بر اساس لایک\n\n"
            "انتخاب کنید:",
            reply_markup=get_admin_leaderboard_period_keyboard("likes")
        )
        await callback.answer()
        return
    
    period_filter = None if period == "all" else period
    
    async for db_session in get_db():
        top_users = await get_top_users_by_likes(db_session, limit=20, period=period_filter)
        
        period_text = {
            "week": "هفته",
            "month": "ماه",
            "all": "همه زمان‌ها"
        }.get(period, "همه زمان‌ها")
        
        text = f"❤️ رتبه‌بندی بر اساس لایک ({period_text})\n\n"
        
        if top_users:
            text += "🏆 برترین کاربران:\n\n"
            medals = ["🥇", "🥈", "🥉"]
            for user_id, count, rank, display_name, profile_id, gender in top_users:
                medal = medals[rank - 1] if rank <= 3 else f"{rank}."
                gender_emoji = get_gender_emoji(gender)
                profile_id_str = format_profile_id(profile_id)
                text += f"{medal} {gender_emoji} {display_name} {profile_id_str}: {count} لایک\n"
        else:
            text += "📭 هنوز کاربری وجود ندارد.\n"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_admin_leaderboard_period_keyboard("likes")
        )
        await callback.answer()
        break


@router.callback_query(F.data == "admin:stats")
async def admin_stats_callback(callback: CallbackQuery):
    """Show admin statistics."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    async for db_session in get_db():
        total_users = await get_user_count(db_session)
        active_chats = await get_active_chat_count(db_session)
        premium_users = await get_premium_count(db_session)
        
        # Get coin statistics
        from core.points_manager import PointsManager
        users = await get_all_users(db_session)
        total_coins = 0
        for user in users:
            total_coins += await PointsManager.get_balance(user.id)
        
        await callback.message.edit_text(
            f"📊 آمار ربات\n\n"
            f"👥 کل کاربران: {total_users}\n"
            f"💬 چت‌های فعال: {active_chats}\n"
            f"💎 کاربران پریمیوم: {premium_users}\n"
            f"💰 کل سکه‌های توزیع شده: {total_coins}\n\n",
            reply_markup=get_admin_main_keyboard()
        )
        await callback.answer()
        break


@router.callback_query(F.data == "admin:users")
async def admin_users_callback(callback: CallbackQuery):
    """Show admin users management."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "👥 مدیریت کاربران\n\n"
        "از منوی زیر انتخاب کنید:",
        reply_markup=get_admin_users_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:referral_links")
async def admin_referral_links_callback(callback: CallbackQuery):
    """Show admin referral links."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔗 لینک‌های عضویت\n\n"
        "از منوی زیر انتخاب کنید:",
        reply_markup=get_admin_referral_links_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:coin_settings")
async def admin_coin_settings_callback(callback: CallbackQuery):
    """Show admin coin settings."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    async for db_session in get_db():
        settings_list = await get_all_coin_settings(db_session)
        
        text = "💰 تنظیمات قیمت سکه‌ها\n\n"
        for setting in settings_list:
            status = "✅ فعال" if setting.is_active else "❌ غیرفعال"
            text += f"{setting.premium_days} روز: {setting.coins_required} سکه ({status})\n"
        
        text += "\nبرای ویرایش یکی از گزینه‌ها را انتخاب کنید:"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_admin_coin_settings_keyboard()
        )
        await callback.answer()
        break


@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_callback(callback: CallbackQuery, state: FSMContext):
    """Start broadcast process."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📢 ارسال پیام همگانی\n\n"
        "لطفاً پیامی که می‌خواهید برای همه کاربران ارسال شود را ارسال کنید:\n\n"
        "✅ پشتیبانی از:\n"
        "• متن\n"
        "• عکس\n"
        "• ویدیو\n"
        "• فایل\n"
        "• صدا\n"
        "• استیکر\n"
        "• فوروارد\n"
        "و...\n\n"
        "همچنین می‌توانید پیام را فوروارد کنید."
    )
    await callback.answer()
    await state.set_state(BroadcastStates.waiting_message)


@router.callback_query(F.data == "admin:broadcast:list")
async def admin_broadcast_list_callback(callback: CallbackQuery):
    """List broadcast messages."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    async for db_session in get_db():
        broadcasts = await get_broadcast_messages(db_session, admin_id=callback.from_user.id, limit=20)
        
        if not broadcasts:
            await callback.message.edit_text(
                "📋 لیست پیام‌های همگانی\n\n"
                "هیچ پیام همگانی ارسال نشده است.",
                reply_markup=get_admin_main_keyboard()
            )
        else:
            text = "📋 لیست پیام‌های همگانی\n\n"
            for broadcast in broadcasts[:10]:  # Show first 10
                # Escape # to avoid parsing errors
                broadcast_id = str(broadcast.id).replace("#", "\\#")
                text += (
                    f"ID: {broadcast_id} - {broadcast.message_type}\n"
                    f"  ✅ {broadcast.sent_count} | ❌ {broadcast.failed_count} | 👁️ {broadcast.opened_count}\n"
                    f"  📅 {broadcast.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
                )
            
            text += "\nبرای مشاهده آمار کامل: /admin_broadcast_stats <id>"
            
            await callback.message.edit_text(
                text,
                reply_markup=get_admin_main_keyboard(),
                parse_mode=None  # Disable parsing to avoid entity errors
            )
        
        await callback.answer()
        break


# ============= Referral Links Handlers =============

@router.callback_query(F.data == "admin:referral_link:create")
async def create_referral_link_start(callback: CallbackQuery, state: FSMContext):
    """Start creating a referral link."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "➕ ایجاد لینک عضویت جدید\n\n"
        "لطفاً کد لینک را وارد کنید (مثلاً: summer2024):"
    )
    await callback.answer()
    await state.set_state(CreateReferralLinkStates.waiting_code)


@router.message(CreateReferralLinkStates.waiting_code)
async def process_referral_link_code(message: Message, state: FSMContext):
    """Process referral link code."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        return
    
    link_code = message.text.strip().upper()
    
    # Validate code
    if not link_code or len(link_code) < 3:
        await message.answer("❌ کد لینک باید حداقل 3 کاراکتر باشد.")
        return
    
    async for db_session in get_db():
        from db.crud import get_admin_referral_link_by_code
        existing = await get_admin_referral_link_by_code(db_session, link_code)
        if existing:
            await message.answer(f"❌ لینک با کد '{link_code}' قبلاً وجود دارد.")
            return
        
        # Store code and ask for description
        await state.update_data(link_code=link_code)
        await message.answer(
            f"✅ کد لینک: {link_code}\n\n"
            f"لطفاً توضیحات لینک را وارد کنید (اختیاری):\n"
            f"یا /skip را برای رد کردن بزنید."
        )
        await state.set_state(CreateReferralLinkStates.waiting_description)
        break


@router.message(CreateReferralLinkStates.waiting_description)
async def process_referral_link_description(message: Message, state: FSMContext):
    """Process referral link description and create link."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        return
    
    description = message.text if message.text != "/skip" else None
    data = await state.get_data()
    link_code = data.get("link_code")
    
    async for db_session in get_db():
        from aiogram import Bot
        bot_info = await message.bot.get_me()
        bot_username = bot_info.username or "bot"
        
        link_url = f"https://t.me/{bot_username}?start=admin_{link_code}"
        
        link = await create_admin_referral_link(
            db_session,
            message.from_user.id,
            link_code,
            link_url,
            description
        )
        
        await message.answer(
            f"✅ لینک عضویت ایجاد شد!\n\n"
            f"🔑 کد: {link_code}\n"
            f"🔗 لینک: {link_url}\n"
            f"📝 توضیحات: {description or 'ندارد'}\n\n"
            f"این لینک را می‌توانید با دیگران به اشتراک بگذارید."
        )
        
        await state.clear()
        break


@router.callback_query(F.data.startswith("admin:referral_link:delete:"))
async def delete_referral_link(callback: CallbackQuery):
    """Delete a referral link."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    link_id = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        success = await delete_admin_referral_link(db_session, link_id)
        
        if success:
            await callback.message.edit_text(
                "✅ لینک با موفقیت حذف شد!",
                reply_markup=get_admin_referral_links_keyboard()
            )
        else:
            await callback.answer("❌ خطا در حذف لینک.", show_alert=True)
        
        await callback.answer()
        break


@router.callback_query(F.data.startswith("admin:referral_link:list:"))
async def list_referral_links_pagination(callback: CallbackQuery):
    """List referral links with pagination."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    page = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        links = await get_admin_referral_links(db_session, admin_id=callback.from_user.id)
        
        if not links:
            await callback.message.edit_text(
                "📋 لینک‌های عضویت\n\n"
                "هنوز هیچ لینکی ایجاد نشده است.",
                reply_markup=get_admin_referral_links_keyboard()
            )
        else:
            total_pages = (len(links) + 4) // 5  # 5 links per page
            await callback.message.edit_text(
                f"📋 لینک‌های عضویت\n\n"
                f"تعداد کل: {len(links)}\n"
                f"صفحه {page + 1} از {total_pages}\n\n"
                f"برای مشاهده جزئیات روی لینک کلیک کنید:",
                reply_markup=get_referral_link_list_keyboard(links, page=page, total_pages=total_pages),
                parse_mode=None
            )
        
        await callback.answer()
        break


@router.callback_query(F.data == "admin:user:search")
async def admin_user_search_start(callback: CallbackQuery, state: FSMContext):
    """Start user search."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔍 جستجوی کاربر\n\n"
        "لطفاً ID کاربر، نام کاربری، یا Telegram ID را وارد کنید:"
    )
    await callback.answer()
    # State will be handled in message handler


@router.callback_query(F.data == "admin:users:banned")
async def admin_banned_users(callback: CallbackQuery):
    """Show banned users."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    async for db_session in get_db():
        from sqlalchemy import select
        from db.models import User
        
        result = await db_session.execute(
            select(User).where(User.is_banned == True).limit(20)
        )
        banned_users = result.scalars().all()
        
        if not banned_users:
            await callback.message.edit_text(
                "🚫 کاربران مسدود شده\n\n"
                "هیچ کاربری مسدود نشده است.",
                reply_markup=get_admin_users_keyboard()
            )
        else:
            text = "🚫 کاربران مسدود شده\n\n"
            for user in banned_users:
                text += f"• ID: {user.id} | @{user.username or 'بدون نام'}\n"
            
            await callback.message.edit_text(
                text,
                reply_markup=get_admin_users_keyboard()
            )
        
        await callback.answer()
        break


@router.callback_query(F.data == "admin:users:premium")
async def admin_premium_users(callback: CallbackQuery):
    """Show premium users."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    async for db_session in get_db():
        premium_count = await get_premium_count(db_session)
        
        from sqlalchemy import select
        from db.models import User
        from datetime import datetime
        
        result = await db_session.execute(
            select(User)
            .where(User.is_premium == True)
            .where(User.premium_expires_at > datetime.utcnow())
            .limit(20)
        )
        users = result.scalars().all()
        
        if not users:
            await callback.message.edit_text(
                "💎 کاربران پریمیوم\n\n"
                "هیچ کاربر پریمیومی وجود ندارد.",
                reply_markup=get_admin_users_keyboard()
            )
        else:
            text = f"💎 کاربران پریمیوم ({premium_count} نفر)\n\n"
            for user in users:
                expires = user.premium_expires_at.strftime("%Y-%m-%d") if user.premium_expires_at else "نامشخص"
                text += f"• ID: {user.id} | @{user.username or 'بدون نام'} | انقضا: {expires}\n"
            
            await callback.message.edit_text(
                text,
                reply_markup=get_admin_users_keyboard()
            )
        
        await callback.answer()
        break


@router.callback_query(F.data == "admin:referral_link:list")
async def list_referral_links(callback: CallbackQuery):
    """List all referral links."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    async for db_session in get_db():
        links = await get_admin_referral_links(db_session, admin_id=callback.from_user.id)
        
        if not links:
            await callback.message.edit_text(
                "📋 لینک‌های عضویت\n\n"
                "هنوز هیچ لینکی ایجاد نشده است.",
                reply_markup=get_admin_referral_links_keyboard()
            )
        else:
            total_pages = (len(links) + 4) // 5  # 5 links per page
            await callback.message.edit_text(
                f"📋 لینک‌های عضویت\n\n"
                f"تعداد کل: {len(links)}\n\n"
                f"برای مشاهده جزئیات روی لینک کلیک کنید:",
                reply_markup=get_referral_link_list_keyboard(links, page=0, total_pages=total_pages),
                parse_mode=None
            )
        
        await callback.answer()
        break


@router.callback_query(F.data.startswith("admin:referral_link:view:"))
async def view_referral_link(callback: CallbackQuery):
    """View referral link details."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    link_id = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        link = await get_admin_referral_link_by_id(db_session, link_id)
        if not link:
            await callback.answer("❌ لینک یافت نشد.", show_alert=True)
            return
        
        stats = await get_link_statistics(db_session, link_id)
        
        status = "✅ فعال" if link.is_active else "❌ غیرفعال"
        
        await callback.message.edit_text(
            f"🔗 جزئیات لینک عضویت\n\n"
            f"🔑 کد: {link.link_code}\n"
            f"🔗 لینک: {link.link_url}\n"
            f"📝 توضیحات: {link.description or 'ندارد'}\n"
            f"📊 وضعیت: {status}\n\n"
            f"📈 آمار:\n"
            f"• تعداد کلیک: {stats.get('total_clicks', 0)}\n"
            f"• کاربران منحصر به فرد: {stats.get('unique_users', 0)}\n"
            f"• تعداد عضویت: {stats.get('total_signups', 0)}\n"
            f"• نرخ تبدیل: {stats.get('conversion_rate', 0)}%\n\n"
            f"📅 ایجاد شده: {link.created_at.strftime('%Y-%m-%d %H:%M')}",
            reply_markup=get_referral_link_detail_keyboard(link_id)
        )
        await callback.answer()
        break


@router.callback_query(F.data.startswith("admin:referral_link:stats:"))
async def view_referral_link_stats(callback: CallbackQuery):
    """View detailed referral link statistics."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    link_id = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        stats = await get_link_statistics(db_session, link_id)
        
        if not stats:
            await callback.answer("❌ آمار یافت نشد.", show_alert=True)
            return
        
        await callback.message.edit_text(
            f"📊 آمار کامل لینک\n\n"
            f"🔑 کد: {stats['link_code']}\n\n"
            f"📈 کلیک‌ها:\n"
            f"• کل کلیک‌ها: {stats['total_clicks']}\n"
            f"• کاربران منحصر به فرد: {stats['unique_users']}\n\n"
            f"👥 عضویت‌ها:\n"
            f"• کل عضویت‌ها: {stats['total_signups']}\n\n"
            f"📊 نرخ تبدیل: {stats['conversion_rate']}%\n\n"
            f"📅 ایجاد شده: {stats['created_at'].strftime('%Y-%m-%d %H:%M')}",
            reply_markup=get_referral_link_detail_keyboard(link_id)
        )
        await callback.answer()
        break


# ============= Coin Settings Handlers =============

@router.callback_query(F.data == "admin:coin:view")
async def view_coin_settings(callback: CallbackQuery):
    """View all coin settings."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    async for db_session in get_db():
        settings_list = await get_all_coin_settings(db_session)
        
        text = "💰 تنظیمات قیمت سکه‌ها\n\n"
        for setting in settings_list:
            status = "✅ فعال" if setting.is_active else "❌ غیرفعال"
            text += f"{setting.premium_days} روز: {setting.coins_required} سکه ({status})\n"
        
        text += "\nبرای ویرایش یکی از گزینه‌ها را انتخاب کنید:"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_admin_coin_settings_keyboard()
        )
        await callback.answer()
        break


@router.callback_query(F.data.startswith("admin:coin:edit:"))
async def edit_coin_setting_start(callback: CallbackQuery, state: FSMContext):
    """Start editing coin setting."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    premium_days = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        setting = await get_coin_setting(db_session, premium_days)
        current_coins = setting.coins_required if setting else 200
        
        await callback.message.edit_text(
            f"✏️ ویرایش تنظیمات\n\n"
            f"مدت زمان: {premium_days} روز\n"
            f"قیمت فعلی: {current_coins} سکه\n\n"
            f"لطفاً تعداد سکه جدید را وارد کنید:"
        )
        await state.update_data(premium_days=premium_days)
        await state.set_state(EditCoinSettingStates.waiting_coins)
        await callback.answer()
        break


@router.message(EditCoinSettingStates.waiting_coins)
async def process_coin_setting(message: Message, state: FSMContext):
    """Process coin setting update."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        return
    
    try:
        coins_required = int(message.text.strip())
        if coins_required < 0:
            await message.answer("❌ تعداد سکه نمی‌تواند منفی باشد.")
            return
    except ValueError:
        await message.answer("❌ لطفاً یک عدد معتبر وارد کنید.")
        return
    
    data = await state.get_data()
    premium_days = data.get("premium_days")
    
    async for db_session in get_db():
        success = await update_coin_setting(
            db_session,
            premium_days,
            coins_required=coins_required
        )
        
        if success:
            await message.answer(
                f"✅ تنظیمات به‌روزرسانی شد!\n\n"
                f"{premium_days} روز: {coins_required} سکه"
            )
        else:
            await message.answer("❌ خطا در به‌روزرسانی تنظیمات.")
        
        await state.clear()
        break


# ============= Coin Reward Settings Handlers =============

@router.callback_query(F.data == "admin:coin_rewards")
async def admin_coin_rewards(callback: CallbackQuery):
    """Show coin rewards management menu."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🎁 مدیریت پاداش‌های سکه\n\n"
        "از منوی زیر انتخاب کنید:",
        reply_markup=get_admin_coin_rewards_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:coin_reward:list")
async def admin_coin_reward_list(callback: CallbackQuery):
    """Show coin reward settings list."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    async for db_session in get_db():
        settings = await get_all_coin_reward_settings(db_session, active_only=False)
        
        # Activity type names in Persian
        activity_names = {
            "daily_login": "ورود روزانه",
            "chat_success": "چت موفق",
            "mutual_like": "لایک متقابل",
            "referral_referrer": "دعوت‌کننده",
            "referral_referred": "دعوت‌شده",
        }
        
        if not settings:
            # Create default settings if none exist
            default_settings = [
                ("daily_login", 10, "ورود روزانه"),
                ("chat_success", 50, "چت موفق"),
                ("mutual_like", 100, "لایک متقابل"),
                ("referral_referrer", 500, "دعوت‌کننده"),
                ("referral_referred", 200, "دعوت‌شده"),
            ]
            
            for activity_type, coins_amount, description in default_settings:
                await create_coin_reward_setting(
                    db_session,
                    activity_type,
                    coins_amount,
                    description,
                    is_active=True
                )
            
            settings = await get_all_coin_reward_settings(db_session, active_only=False)
        
        text = "🎁 تنظیمات پاداش سکه\n\n"
        for setting in settings:
            activity_name = activity_names.get(setting.activity_type, setting.activity_type)
            status = "✅ فعال" if setting.is_active else "❌ غیرفعال"
            text += f"{activity_name}: {setting.coins_amount} سکه ({status})\n"
        
        text += "\nبرای ویرایش یکی از گزینه‌ها را انتخاب کنید:"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_coin_reward_list_keyboard(settings)
        )
        await callback.answer()
        break


@router.callback_query(F.data.startswith("admin:coin_reward:edit:"))
async def edit_coin_reward_start(callback: CallbackQuery, state: FSMContext):
    """Start editing coin reward setting."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    activity_type = callback.data.split(":")[-1]
    
    # Activity type names in Persian
    activity_names = {
        "daily_login": "ورود روزانه",
        "chat_success": "چت موفق",
        "mutual_like": "لایک متقابل",
        "referral_referrer": "دعوت‌کننده",
        "referral_referred": "دعوت‌شده",
    }
    
    activity_name = activity_names.get(activity_type, activity_type)
    
    async for db_session in get_db():
        setting = await get_coin_reward_setting(db_session, activity_type)
        current_coins = setting.coins_amount if setting else 0
        
        await callback.message.edit_text(
            f"✏️ ویرایش تنظیمات پاداش سکه\n\n"
            f"فعالیت: {activity_name}\n"
            f"مقدار فعلی: {current_coins} سکه\n\n"
            f"لطفاً تعداد سکه جدید را وارد کنید:"
        )
        await state.update_data(activity_type=activity_type)
        await state.set_state(EditCoinRewardStates.waiting_coins)
        await callback.answer()
        break


@router.message(EditCoinRewardStates.waiting_coins)
async def process_coin_reward_setting(message: Message, state: FSMContext):
    """Process coin reward setting update."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ دسترسی محدود است.")
        await state.clear()
        return
    
    try:
        coins_amount = int(message.text.strip())
        if coins_amount < 0:
            await message.answer("❌ تعداد سکه نمی‌تواند منفی باشد.")
            return
    except ValueError:
        await message.answer("❌ لطفاً یک عدد معتبر وارد کنید.")
        return
    
    data = await state.get_data()
    activity_type = data.get("activity_type")
    
    # Activity type names in Persian
    activity_names = {
        "daily_login": "ورود روزانه",
        "chat_success": "چت موفق",
        "mutual_like": "لایک متقابل",
        "referral_referrer": "دعوت‌کننده",
        "referral_referred": "دعوت‌شده",
    }
    
    activity_name = activity_names.get(activity_type, activity_type)
    
    async for db_session in get_db():
        # Get description from existing setting or use default
        existing = await get_coin_reward_setting(db_session, activity_type)
        description = existing.description if existing else activity_name
        
        success = await create_coin_reward_setting(
            db_session,
            activity_type,
            coins_amount,
            description,
            is_active=True
        )
        
        if success:
            await message.answer(
                f"✅ تنظیمات به‌روزرسانی شد!\n\n"
                f"{activity_name}: {coins_amount} سکه"
            )
        else:
            await message.answer("❌ خطا در به‌روزرسانی تنظیمات.")
        
        await state.clear()
        break


@router.callback_query(F.data.startswith("admin:referral_link:delete:"))
async def delete_referral_link(callback: CallbackQuery):
    """Delete a referral link."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    link_id = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        success = await delete_admin_referral_link(db_session, link_id)
        
        if success:
            await callback.message.edit_text(
                "✅ لینک با موفقیت حذف شد!",
                reply_markup=get_admin_referral_links_keyboard()
            )
        else:
            await callback.answer("❌ خطا در حذف لینک.", show_alert=True)
        
        await callback.answer()
        break


@router.callback_query(F.data.startswith("admin:referral_link:list:"))
async def list_referral_links_pagination(callback: CallbackQuery):
    """List referral links with pagination."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    page = int(callback.data.split(":")[-1])
    
    async for db_session in get_db():
        links = await get_admin_referral_links(db_session, admin_id=callback.from_user.id)
        
        if not links:
            await callback.message.edit_text(
                "📋 لینک‌های عضویت\n\n"
                "هنوز هیچ لینکی ایجاد نشده است.",
                reply_markup=get_admin_referral_links_keyboard()
            )
        else:
            total_pages = (len(links) + 4) // 5  # 5 links per page
            await callback.message.edit_text(
                f"📋 لینک‌های عضویت\n\n"
                f"تعداد کل: {len(links)}\n"
                f"صفحه {page + 1} از {total_pages}\n\n"
                f"برای مشاهده جزئیات روی لینک کلیک کنید:",
                reply_markup=get_referral_link_list_keyboard(links, page=page, total_pages=total_pages),
                parse_mode=None
            )
        
        await callback.answer()
        break


@router.callback_query(F.data == "admin:user:search")
async def admin_user_search_start(callback: CallbackQuery, state: FSMContext):
    """Start user search."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔍 جستجوی کاربر\n\n"
        "لطفاً ID کاربر، نام کاربری، یا Telegram ID را وارد کنید:"
    )
    await callback.answer()
    # State will be handled in message handler


@router.callback_query(F.data == "admin:users:banned")
async def admin_banned_users(callback: CallbackQuery):
    """Show banned users."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    async for db_session in get_db():
        from sqlalchemy import select
        from db.models import User
        
        result = await db_session.execute(
            select(User).where(User.is_banned == True).limit(20)
        )
        banned_users = result.scalars().all()
        
        if not banned_users:
            await callback.message.edit_text(
                "🚫 کاربران مسدود شده\n\n"
                "هیچ کاربری مسدود نشده است.",
                reply_markup=get_admin_users_keyboard()
            )
        else:
            text = "🚫 کاربران مسدود شده\n\n"
            for user in banned_users:
                text += f"• ID: {user.id} | @{user.username or 'بدون نام'}\n"
            
            await callback.message.edit_text(
                text,
                reply_markup=get_admin_users_keyboard()
            )
        
        await callback.answer()
        break


@router.callback_query(F.data == "admin:users:premium")
async def admin_premium_users(callback: CallbackQuery):
    """Show premium users."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود است.", show_alert=True)
        return
    
    async for db_session in get_db():
        premium_count = await get_premium_count(db_session)
        
        from sqlalchemy import select
        from db.models import User
        from datetime import datetime
        
        result = await db_session.execute(
            select(User)
            .where(User.is_premium == True)
            .where(User.premium_expires_at > datetime.utcnow())
            .limit(20)
        )
        users = result.scalars().all()
        
        if not users:
            await callback.message.edit_text(
                "💎 کاربران پریمیوم\n\n"
                "هیچ کاربر پریمیومی وجود ندارد.",
                reply_markup=get_admin_users_keyboard()
            )
        else:
            text = f"💎 کاربران پریمیوم ({premium_count} نفر)\n\n"
            for user in users:
                expires = user.premium_expires_at.strftime("%Y-%m-%d") if user.premium_expires_at else "نامشخص"
                text += f"• ID: {user.id} | @{user.username or 'بدون نام'} | انقضا: {expires}\n"
            
            await callback.message.edit_text(
                text,
                reply_markup=get_admin_users_keyboard()
            )
        
        await callback.answer()
        break

