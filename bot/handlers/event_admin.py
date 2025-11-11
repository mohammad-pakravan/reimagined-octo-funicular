"""
Admin event handlers for creating and managing events.
"""
import json
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db.database import get_db
from db.crud import (
    get_user_by_telegram_id,
    create_event,
    get_all_events,
    get_event_by_id,
    update_event,
    delete_event,
    get_event_participants,
    get_event_participant_count,
    get_event_rewards,
)
from bot.keyboards.admin import get_admin_main_keyboard
from bot.keyboards.engagement import get_engagement_menu_keyboard
from config.settings import settings
from core.event_engine import EventEngine
from db.crud import get_all_users

router = Router()


async def notify_users_about_event(event, bot):
    """Notify all users about a new event."""
    from datetime import datetime
    
    # Build event notification message
    now = datetime.utcnow()
    days_left = (event.end_date - now).days
    
    # Parse event config for display
    import json
    config = {}
    if event.config_json:
        try:
            config = json.loads(event.config_json)
        except:
            pass
    
    # Build message based on event type
    if event.event_type == "points_multiplier":
        multiplier = config.get("multiplier", 1.0)
        text = (
            f"🎉 ایونت جدید: {event.event_name}\n\n"
            f"✨ ضریب امتیاز: {multiplier}x\n\n"
        )
    elif event.event_type == "referral_reward":
        premium_days = config.get("premium_days", 0)
        text = (
            f"🎉 ایونت جدید: {event.event_name}\n\n"
            f"💎 پاداش: {premium_days} روز پریمیوم برای هر معرفی\n\n"
        )
    elif event.event_type == "challenge_lottery":
        target_metric = config.get("target_metric", "")
        target_value = config.get("target_value", 0)
        reward_type = config.get("reward_type", "")
        reward_value = config.get("reward_value", 0)
        
        metric_names = {
            "chat_count": "چت",
            "referral_count": "معرفی",
            "like_count": "لایک"
        }
        
        text = (
            f"🎉 ایونت جدید: {event.event_name}\n\n"
            f"🎯 چالش: {metric_names.get(target_metric, target_metric)} = {target_value}\n"
            f"🏆 پاداش: {reward_value} {reward_type}\n\n"
        )
    else:
        text = (
            f"🎉 ایونت جدید: {event.event_name}\n\n"
        )
    
    if event.event_description:
        text += f"{event.event_description}\n\n"
    
    text += (
        f"⏰ {days_left} روز باقی مانده\n\n"
        f"💡 برای مشاهده جزئیات بیشتر، به منوی «🎁 پاداش‌ها و تعامل» → «🎯 ایونت‌ها» بروید!"
    )
    
    # Get all users
    async for db_session in get_db():
        users = await get_all_users(db_session)
        
        sent_count = 0
        failed_count = 0
        
        # Send notification to all users
        for user in users:
            try:
                # Skip banned users
                if user.is_banned:
                    continue
                
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=text,
                    reply_markup=get_engagement_menu_keyboard()
                )
                sent_count += 1
                
            except Exception as e:
                failed_count += 1
                # Log error but continue
                pass
        
        break  # Exit after first db session


class EventStates(StatesGroup):
    waiting_event_name = State()
    waiting_event_description = State()
    waiting_event_type = State()
    waiting_event_config = State()
    waiting_start_date = State()
    waiting_end_date = State()


@router.message(Command("admin_events"))
async def admin_events_command(message: Message):
    """Show admin events menu."""
    if message.from_user.id not in settings.ADMIN_IDS:
        await message.answer("❌ دسترسی محدود به ادمین‌ها")
        return
    
    async for db_session in get_db():
        events = await get_all_events(db_session, skip=0, limit=10)
        
        text = "🎯 مدیریت ایونت‌ها\n\n"
        
        if events:
            text += "📋 ایونت‌های اخیر:\n\n"
            for event in events:
                status = "✅ فعال" if event.is_active else "❌ غیرفعال"
                now = datetime.utcnow()
                if event.start_date <= now <= event.end_date:
                    status += " (در حال اجرا)"
                elif event.end_date < now:
                    status += " (پایان یافته)"
                elif event.start_date > now:
                    status += " (آینده)"
                
                text += f"• {event.event_name}\n"
                text += f"  نوع: {event.event_type}\n"
                text += f"  وضعیت: {status}\n"
                text += f"  تاریخ: {event.start_date.strftime('%Y-%m-%d')} تا {event.end_date.strftime('%Y-%m-%d')}\n\n"
        else:
            text += "هیچ ایونتی وجود ندارد.\n\n"
        
        text += "دستورات:\n"
        text += "/admin_event_create - ایجاد ایونت جدید\n"
        text += "/admin_event_list - لیست همه ایونت‌ها\n"
        text += "/admin_event_lottery - اجرای قرعه‌کشی برای چالش"
        
        await message.answer(text)


@router.message(Command("admin_event_create"))
async def admin_event_create(message: Message, state: FSMContext):
    """Start creating a new event."""
    if message.from_user.id not in settings.ADMIN_IDS:
        await message.answer("❌ دسترسی محدود به ادمین‌ها")
        return
    
    await message.answer(
        "🎯 ایجاد ایونت جدید\n\n"
        "لطفاً نام ایونت را ارسال کنید:"
    )
    await state.set_state(EventStates.waiting_event_name)


@router.message(EventStates.waiting_event_name)
async def process_event_name(message: Message, state: FSMContext):
    """Process event name."""
    await state.update_data(event_name=message.text)
    
    await message.answer(
        "لطفاً توضیحات ایونت را ارسال کنید (یا /skip برای رد کردن):"
    )
    await state.set_state(EventStates.waiting_event_description)


@router.message(EventStates.waiting_event_description)
async def process_event_description(message: Message, state: FSMContext):
    """Process event description."""
    if message.text != "/skip":
        await state.update_data(event_description=message.text)
    else:
        await state.update_data(event_description=None)
    
    await message.answer(
        "نوع ایونت را انتخاب کنید:\n\n"
        "1️⃣ points_multiplier - ضریب امتیاز (مثلاً 2x)\n"
        "2️⃣ referral_reward - پاداش معرفی (پریمیوم)\n"
        "3️⃣ challenge_lottery - چالش با قرعه‌کشی\n\n"
        "عدد یا نام نوع را ارسال کنید:"
    )
    await state.set_state(EventStates.waiting_event_type)


@router.message(EventStates.waiting_event_type)
async def process_event_type(message: Message, state: FSMContext):
    """Process event type."""
    text = message.text.strip()
    
    # Check if user sent JSON instead of event type
    if text.startswith("{") and text.endswith("}"):
        await message.answer(
            "❌ شما JSON ارسال کردید، اما باید ابتدا نوع ایونت را انتخاب کنید!\n\n"
            "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:\n\n"
            "1️⃣ یا عدد 1 برای points_multiplier\n"
            "2️⃣ یا عدد 2 برای referral_reward\n"
            "3️⃣ یا عدد 3 برای challenge_lottery\n\n"
            "یا نام نوع را بنویسید:\n"
            "• points_multiplier\n"
            "• referral_reward\n"
            "• challenge_lottery"
        )
        return
    
    text_lower = text.lower()
    
    event_type_map = {
        "1": "points_multiplier",
        "2": "referral_reward",
        "3": "challenge_lottery",
        "points_multiplier": "points_multiplier",
        "referral_reward": "referral_reward",
        "challenge_lottery": "challenge_lottery",
    }
    
    event_type = event_type_map.get(text_lower)
    
    if not event_type:
        await message.answer(
            "❌ نوع نامعتبر!\n\n"
            "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:\n\n"
            "1️⃣ یا عدد 1 برای points_multiplier\n"
            "2️⃣ یا عدد 2 برای referral_reward\n"
            "3️⃣ یا عدد 3 برای challenge_lottery\n\n"
            "یا نام نوع را بنویسید:\n"
            "• points_multiplier\n"
            "• referral_reward\n"
            "• challenge_lottery"
        )
        return
    
    await state.update_data(event_type=event_type)
    
    # Ask for config based on type
    if event_type == "points_multiplier":
        await message.answer(
            "📝 تنظیمات ضریب امتیاز:\n\n"
            "لطفاً به صورت JSON ارسال کنید:\n\n"
            "📌 نمونه 1 - ضریب 2x برای همه منابع:\n"
            '{"multiplier": 2.0}\n\n'
            "📌 نمونه 2 - ضریب 2x فقط برای چت و ورود روزانه:\n"
            '{"multiplier": 2.0, "apply_to_sources": ["chat_success", "daily_login"]}\n\n'
            "📌 نمونه 3 - ضریب 2x فقط برای دعوت دوستان:\n"
            '{"multiplier": 2.0, "apply_to_sources": ["referral_profile_complete"]}\n\n'
            "📌 نمونه 4 - ضریب 1.5x برای همه منابع:\n"
            '{"multiplier": 1.5}\n\n'
            "💡 توضیحات:\n"
            "• multiplier: ضریب (مثلاً 2.0 برای 2x، 1.5 برای 1.5x)\n"
            "• apply_to_sources: لیست منابع (اختیاری)\n"
            "  - chat_success: چت موفق\n"
            "  - daily_login: ورود روزانه\n"
            "  - mutual_like: لایک متقابل\n"
            "  - referral_profile_complete: تکمیل پروفایل دعوت‌شده\n"
            "  - referral_signup: عضویت با لینک دعوت\n"
            "  - اگر خالی باشد، برای همه منابع اعمال می‌شود\n\n"
            "✅ نمونه کامل برای کپی:\n"
            '{"multiplier": 2.0, "apply_to_sources": ["chat_success", "daily_login"]}'
        )
    elif event_type == "referral_reward":
        await message.answer(
            "📝 تنظیمات پاداش معرفی:\n\n"
            "لطفاً به صورت JSON ارسال کنید:\n\n"
            "📌 نمونه 1 - 2 روز پریمیوم برای هر معرفی:\n"
            '{"premium_days": 2}\n\n'
            "📌 نمونه 2 - 7 روز پریمیوم برای هر معرفی:\n"
            '{"premium_days": 7}\n\n'
            "📌 نمونه 3 - 30 روز پریمیوم برای هر معرفی:\n"
            '{"premium_days": 30}\n\n'
            "💡 توضیحات:\n"
            "• premium_days: تعداد روزهای پریمیوم که به دعوت‌کننده داده می‌شود\n"
            "  (برای هر معرفی جدید)\n\n"
            "✅ نمونه کامل برای کپی:\n"
            '{"premium_days": 2}'
        )
    elif event_type == "challenge_lottery":
        await message.answer(
            "📝 تنظیمات چالش با قرعه‌کشی:\n\n"
            "لطفاً به صورت JSON ارسال کنید:\n\n"
            "📌 نمونه 1 - چالش چت (10 چت = شانس برنده شدن 30 روز پریمیوم):\n"
            '{"target_metric": "chat_count", "target_value": 10, "reward_type": "premium_days", "reward_value": 30}\n\n'
            "📌 نمونه 2 - چالش معرفی (5 معرفی = شانس برنده شدن 1000 سکه):\n"
            '{"target_metric": "referral_count", "target_value": 5, "reward_type": "points", "reward_value": 1000}\n\n'
            "📌 نمونه 3 - چالش لایک (20 لایک = شانس برنده شدن 15 روز پریمیوم):\n"
            '{"target_metric": "like_count", "target_value": 20, "reward_type": "premium_days", "reward_value": 15}\n\n'
            "💡 توضیحات:\n"
            "• target_metric: معیار چالش\n"
            "  - chat_count: تعداد چت‌ها\n"
            "  - referral_count: تعداد معرفی‌ها\n"
            "  - like_count: تعداد لایک‌های دریافتی\n"
            "• target_value: حداقل مقدار برای واجد شرایط بودن در قرعه‌کشی\n"
            "• reward_type: نوع پاداش\n"
            "  - premium_days: روزهای پریمیوم\n"
            "  - points: سکه\n"
            "• reward_value: مقدار پاداش\n\n"
            "✅ نمونه کامل برای کپی:\n"
            '{"target_metric": "chat_count", "target_value": 10, "reward_type": "premium_days", "reward_value": 30}'
        )
    
    await state.set_state(EventStates.waiting_event_config)


@router.message(EventStates.waiting_event_config)
async def process_event_config(message: Message, state: FSMContext):
    """Process event config."""
    try:
        config = json.loads(message.text)
        await state.update_data(config_json=json.dumps(config))
    except json.JSONDecodeError:
        await message.answer("❌ JSON نامعتبر. لطفاً دوباره تلاش کنید:")
        return
    
    await message.answer(
        "تاریخ شروع ایونت:\n\n"
        "فرمت: YYYY-MM-DD HH:MM\n"
        "مثال: 2025-01-15 10:00\n\n"
        "یا 'now' برای شروع فوری"
    )
    await state.set_state(EventStates.waiting_start_date)


@router.message(EventStates.waiting_start_date)
async def process_start_date(message: Message, state: FSMContext):
    """Process start date."""
    text = message.text.strip()
    
    if text.lower() == "now":
        start_date = datetime.utcnow()
    else:
        try:
            start_date = datetime.strptime(text, "%Y-%m-%d %H:%M")
        except ValueError:
            await message.answer("❌ فرمت تاریخ نامعتبر. لطفاً دوباره تلاش کنید:")
            return
    
    # Convert datetime to ISO format string for JSON serialization
    await state.update_data(start_date=start_date.isoformat())
    
    await message.answer(
        "تاریخ پایان ایونت:\n\n"
        "فرمت: YYYY-MM-DD HH:MM\n"
        "مثال: 2025-01-22 23:59\n\n"
        "یا تعداد روز (مثلاً 7 برای 7 روز)"
    )
    await state.set_state(EventStates.waiting_end_date)


@router.message(EventStates.waiting_end_date)
async def process_end_date(message: Message, state: FSMContext):
    """Process end date and create event."""
    text = message.text.strip()
    data = await state.get_data()
    
    # Convert start_date from ISO string back to datetime
    start_date = datetime.fromisoformat(data["start_date"])
    
    # Calculate end date
    if text.isdigit():
        days = int(text)
        end_date = start_date + timedelta(days=days)
    else:
        try:
            end_date = datetime.strptime(text, "%Y-%m-%d %H:%M")
        except ValueError:
            await message.answer("❌ فرمت تاریخ نامعتبر. لطفاً دوباره تلاش کنید:")
            return
    
    # Generate event_key
    import hashlib
    event_key = hashlib.md5(
        f"{data['event_name']}_{data['event_type']}_{datetime.utcnow()}".encode()
    ).hexdigest()[:16]
    
    async for db_session in get_db():
        event = await create_event(
            db_session,
            event_key=event_key,
            event_name=data["event_name"],
            event_type=data["event_type"],
            start_date=start_date,
            end_date=end_date,
            created_by_admin_id=message.from_user.id,
            event_description=data.get("event_description"),
            config_json=data.get("config_json"),
            is_active=True,
            is_visible=True
        )
        
        await message.answer(
            f"✅ ایونت با موفقیت ایجاد شد!\n\n"
            f"📌 نام: {event.event_name}\n"
            f"🔑 کلید: {event.event_key}\n"
            f"📅 تاریخ: {event.start_date.strftime('%Y-%m-%d %H:%M')} تا {event.end_date.strftime('%Y-%m-%d %H:%M')}\n"
            f"🎯 نوع: {event.event_type}\n\n"
            f"📢 در حال اطلاع‌رسانی به همه کاربران..."
        )
        
        # Notify all users about the new event
        await notify_users_about_event(event, message.bot)
        
        await message.answer("✅ اطلاع‌رسانی به همه کاربران انجام شد!")
    
    await state.clear()


@router.message(Command("admin_event_list"))
async def admin_event_list(message: Message):
    """List all events."""
    if message.from_user.id not in settings.ADMIN_IDS:
        await message.answer("❌ دسترسی محدود به ادمین‌ها")
        return
    
    async for db_session in get_db():
        events = await get_all_events(db_session, skip=0, limit=50)
        
        if not events:
            await message.answer("هیچ ایونتی وجود ندارد.")
            return
        
        text = f"📋 لیست ایونت‌ها ({len(events)})\n\n"
        
        for event in events:
            status = "✅ فعال" if event.is_active else "❌ غیرفعال"
            now = datetime.utcnow()
            if event.start_date <= now <= event.end_date:
                status += " (در حال اجرا)"
            elif event.end_date < now:
                status += " (پایان یافته)"
            elif event.start_date > now:
                status += " (آینده)"
            
            participant_count = await get_event_participant_count(db_session, event.id)
            
            text += f"🎯 {event.event_name}\n"
            text += f"   ID: {event.id}\n"
            text += f"   نوع: {event.event_type}\n"
            text += f"   وضعیت: {status}\n"
            text += f"   شرکت‌کنندگان: {participant_count}\n"
            text += f"   تاریخ: {event.start_date.strftime('%Y-%m-%d')} تا {event.end_date.strftime('%Y-%m-%d')}\n\n"
        
        await message.answer(text)


@router.message(Command("admin_event_lottery"))
async def admin_event_lottery(message: Message):
    """Execute lottery for challenge event."""
    if message.from_user.id not in settings.ADMIN_IDS:
        await message.answer("❌ دسترسی محدود به ادمین‌ها")
        return
    
    # Parse command: /admin_event_lottery <event_id> [winner_count]
    parts = message.text.split()
    
    if len(parts) < 2:
        await message.answer(
            "❌ فرمت دستور:\n"
            "/admin_event_lottery <event_id> [winner_count]\n\n"
            "مثال: /admin_event_lottery 1 10"
        )
        return
    
    try:
        event_id = int(parts[1])
        winner_count = int(parts[2]) if len(parts) > 2 else 10
    except ValueError:
        await message.answer("❌ ID ایونت یا تعداد برندگان نامعتبر")
        return
    
    async for db_session in get_db():
        event = await get_event_by_id(db_session, event_id)
        if not event:
            await message.answer("❌ ایونت یافت نشد")
            return
        
        if event.event_type != "challenge_lottery":
            await message.answer("❌ این ایونت از نوع challenge_lottery نیست")
            return
        
        await message.answer("⏳ در حال اجرای قرعه‌کشی...")
        
        winners = await EventEngine.execute_lottery(event_id, winner_count)
        
        if not winners:
            await message.answer("❌ هیچ برنده‌ای یافت نشد")
            return
        
        text = f"🎉 قرعه‌کشی اجرا شد!\n\n"
        text += f"📊 تعداد برندگان: {len(winners)}\n\n"
        
        for winner in winners[:10]:  # Show first 10
            text += f"🏆 رتبه {winner['rank']}: کاربر {winner['user_id']}\n"
            text += f"   پیشرفت: {winner['progress']}\n"
            text += f"   پاداش: {winner['reward_value']} {winner['reward_type']}\n\n"
        
        if len(winners) > 10:
            text += f"... و {len(winners) - 10} برنده دیگر"
        
        await message.answer(text)

