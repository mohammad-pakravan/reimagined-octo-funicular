"""
Reply keyboard handlers for normal keyboard buttons.
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from db.database import get_db
from db.crud import get_user_by_telegram_id
from bot.keyboards.reply import get_main_reply_keyboard, get_chat_reply_keyboard
from bot.keyboards.common import get_chat_keyboard, get_preferred_gender_keyboard
from core.chat_manager import ChatManager

router = Router()

chat_manager = None

def set_chat_manager(manager: ChatManager):
    """Set chat manager instance."""
    global chat_manager
    chat_manager = manager


@router.message(F.text == "💬 شروع چت")
async def start_chat_button(message: Message, state: FSMContext):
    """Handle 'Start Chat' reply button."""
    from bot.keyboards.common import get_preferred_gender_keyboard
    
    user_id = message.from_user.id
    
    async for db_session in get_db():
        from db.crud import get_user_by_telegram_id
        user = await get_user_by_telegram_id(db_session, user_id)
        
        if not user or not user.gender or not user.age or not user.city:
            await message.answer(
                "❌ لطفاً ابتدا پروفایل خودت را کامل کن. /start را بزنید."
            )
            return
        
        # Check if user already has active chat
        from bot.handlers.chat import chat_manager as chat_mgr
        
        if chat_mgr and await chat_mgr.is_chat_active(user.id, db_session):
            await message.answer("❌ شما در حال حاضر یک چت فعال دارید!")
            return
        
        # Ask for preferred gender
        await message.answer(
            "💬 شروع چت ناشناس\n\n"
            "به دنبال چه جنسیتی هستی؟",
            reply_markup=get_preferred_gender_keyboard()
        )
        
        # Set state to wait for gender selection
        from bot.handlers.chat import ChatStates
        await state.set_state(ChatStates.waiting_preferred_gender)
        break


@router.message(F.text == "📊 پروفایل من")
async def my_profile_button(message: Message):
    """Handle 'My Profile' reply button."""
    user_id = message.from_user.id
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if user:
            gender_map = {"male": "پسر 🧑", "female": "دختر 👩", "other": "سایر"}
            gender_text = gender_map.get(user.gender, user.gender or "تعیین نشده")
            
            # Generate user ID
            user_unique_id = f"/user_{user.profile_id or 'unknown'}"
            
            profile_text = (
                f"📊 پروفایل من\n\n"
                f"• نام: {user.username or 'تعیین نشده'}\n"
                f"• جنسیت: {gender_text}\n"
                f"• استان: {user.province or 'تعیین نشده'}\n"
                f"• شهر: {user.city or 'تعیین نشده'}\n"
                f"• سن: {user.age or 'تعیین نشده'}\n"
                f"• پریمیوم: {'✅ فعال' if user.is_premium else '❌ غیرفعال'}\n"
                f"ID: {user_unique_id}"
            )
            
            from bot.keyboards.my_profile import get_my_profile_keyboard
            profile_keyboard = get_my_profile_keyboard()
            
            # Send profile with photo if available
            profile_image_url = getattr(user, 'profile_image_url', None)
            if profile_image_url:
                try:
                    await message.answer_photo(
                        photo=profile_image_url,
                        caption=profile_text,
                        reply_markup=profile_keyboard
                    )
                except Exception:
                    await message.answer(profile_text, reply_markup=profile_keyboard)
            else:
                await message.answer(profile_text, reply_markup=profile_keyboard)
        else:
            await message.answer(
                "❌ پروفایل شما یافت نشد. لطفاً /start را بزنید.",
                reply_markup=get_main_reply_keyboard()
            )
        break


@router.message(F.text == "💎 پریمیوم")
async def premium_button(message: Message):
    """Handle 'Premium' reply button."""
    # Redirect to unified premium and rewards menu
    await engagement_button(message)


@router.message(F.text == "👤 پروفایل مخاطب")
async def partner_profile_button(message: Message):
    """Handle 'Partner Profile' reply button."""
    user_id = message.from_user.id
    
    async for db_session in get_db():
        from db.crud import get_user_by_telegram_id
        from bot.handlers.chat import chat_manager as chat_mgr
        
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await message.answer(
                "❌ پروفایل شما یافت نشد. لطفاً /start را بزنید.",
                reply_markup=get_chat_reply_keyboard()
            )
            break
        
        # Check if user has active chat
        if not chat_mgr or not await chat_mgr.is_chat_active(user.id, db_session):
            await message.answer(
                "❌ شما در حال حاضر یک چت فعال ندارید!",
                reply_markup=get_main_reply_keyboard()
            )
            break
        
        # Get partner ID
        partner_id = await chat_mgr.get_partner_id(user.id, db_session)
        if not partner_id:
            await message.answer(
                "❌ هم‌چت پیدا نشد.",
                reply_markup=get_chat_reply_keyboard()
            )
            break
        
        # Get partner user
        from db.crud import get_user_by_id
        partner = await get_user_by_id(db_session, partner_id)
        if not partner:
            await message.answer(
                "❌ اطلاعات مخاطب یافت نشد.",
                reply_markup=get_chat_reply_keyboard()
            )
            break
        
        # Get like, follow, block status
        from db.crud import is_liked, is_following, is_blocked
        is_liked_status = await is_liked(db_session, user.id, partner.id)
        is_following_status = await is_following(db_session, user.id, partner.id)
        is_blocked_status = await is_blocked(db_session, user.id, partner.id)
        
        # Display partner profile
        gender_map = {"male": "پسر 🧑", "female": "دختر 👩", "other": "سایر"}
        gender_text = gender_map.get(partner.gender, partner.gender or "تعیین نشده")
        
        # Generate user ID (use existing profile_id or generate)
        if not partner.profile_id:
            # Generate and save profile_id if not exists
            import hashlib
            profile_id = hashlib.md5(f"user_{partner.telegram_id}".encode()).hexdigest()[:12]
            from db.crud import update_user_profile_id
            if hasattr(update_user_profile_id, '__call__'):
                await update_user_profile_id(db_session, partner.id, profile_id)
                partner.profile_id = profile_id
        
        user_unique_id = f"/user_{partner.profile_id or 'unknown'}"
        
        # Calculate distance (simplified - based on same province/city)
        distance = "نامشخص"
        if user.city and partner.city and user.province and partner.province:
            if user.city == partner.city:
                distance = "همشهری"
            elif user.province == partner.province:
                distance = "هم‌استان"
            else:
                distance = "شهرهای مختلف"
        
        profile_text = (
            f"• نام: {partner.username or 'تعیین نشده'}\n"
            f"• جنسیت: {gender_text}\n"
            f"• استان: {partner.province or 'تعیین نشده'}\n"
            f"• شهر: {partner.city or 'تعیین نشده'}\n"
            f"• سن: {partner.age or 'تعیین نشده'}\n"
            f"ID: {user_unique_id}\n"
            f"فاصله : {distance}"
        )
        
        # Get profile keyboard
        from bot.keyboards.profile import get_profile_keyboard
        profile_keyboard = get_profile_keyboard(
            partner_id=partner.id,
            is_liked=is_liked_status,
            is_following=is_following_status,
            is_blocked=is_blocked_status,
            like_count=partner.like_count or 0,
            is_notifying=is_notifying_status
        )
        
        # Send profile with photo if available
        profile_image_url = getattr(partner, 'profile_image_url', None)
        if profile_image_url:
            from aiogram import Bot
            from config.settings import settings
            bot = Bot(token=settings.BOT_TOKEN)
            try:
                await bot.send_photo(
                    user_id,
                    profile_image_url,
                    caption=profile_text,
                    reply_markup=profile_keyboard
                )
                await bot.session.close()
            except Exception:
                # If photo fails, send text only
                await message.answer(profile_text, reply_markup=profile_keyboard)
        else:
            await message.answer(profile_text, reply_markup=profile_keyboard)
        
        break


@router.message(F.text == "📹 شروع تماس تصویری")
async def start_video_call_button(message: Message):
    """Handle 'Start Video Call' reply button."""
    from bot.handlers.chat import request_video_call
    from aiogram.types import CallbackQuery
    
    class MockCallback:
        def __init__(self):
            self.from_user = message.from_user
            self.message = message
            self.data = 'chat:video_call'
        async def answer(self, *args, **kwargs):
            pass
    
    callback = MockCallback()
    await request_video_call(callback)


@router.message(F.text == "📞 شروع تماس صوتی")
async def start_voice_call_button(message: Message):
    """Handle 'Start Voice Call' reply button."""
    user_id = message.from_user.id
    
    async for db_session in get_db():
        from db.crud import get_user_by_telegram_id, check_user_premium
        from bot.handlers.chat import chat_manager as chat_mgr
        
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await message.answer(
                "❌ پروفایل شما یافت نشد. لطفاً /start را بزنید.",
                reply_markup=get_chat_reply_keyboard()
            )
            break
        
        # Check if user has active chat
        if not chat_mgr or not await chat_mgr.is_chat_active(user.id, db_session):
            await message.answer(
                "❌ شما در حال حاضر یک چت فعال ندارید!",
                reply_markup=get_main_reply_keyboard()
            )
            break
        
        # Get partner ID
        partner_id = await chat_mgr.get_partner_id(user.id, db_session)
        if not partner_id:
            await message.answer(
                "❌ هم‌چت پیدا نشد.",
                reply_markup=get_chat_reply_keyboard()
            )
            break
        
        # Check premium status
        user_premium = await check_user_premium(db_session, user.id)
        
        # Only premium users can start voice call
        if not user_premium:
            from bot.keyboards.common import get_premium_keyboard
            from config.settings import settings
            await message.answer(
                f"❌ شما عضویت ویژه ندارید.\n\n"
                f"💎 اشتراک پریمیوم\n\n"
                f"با خرید پریمیوم از امکانات زیر بهره‌مند شوید:\n"
                f"• تماس تصویری\n"
                f"• تماس صوتی\n"
                f"• زمان چت بیشتر ({settings.PREMIUM_CHAT_DURATION_MINUTES} دقیقه در مقابل {settings.MAX_CHAT_DURATION_MINUTES} دقیقه)\n"
                f"• فیلترهای پیشرفته\n"
                f"• اولویت در صف (نفر اول صف)\n\n"
                f"قیمت: {settings.PREMIUM_PRICE} تومان\n"
                f"مدت زمان: {settings.PREMIUM_DURATION_DAYS} روز\n\n"
                f"آیا می‌خواهید پریمیوم بخرید?",
                reply_markup=get_premium_keyboard()
            )
            break
        
        # Request voice call
        from db.crud import get_user_by_id
        from aiogram import Bot
        from config.settings import settings
        from bot.keyboards.common import get_call_request_keyboard
        
        partner = await get_user_by_id(db_session, partner_id)
        if not partner:
            await message.answer(
                "❌ مخاطب یافت نشد.",
                reply_markup=get_chat_reply_keyboard()
            )
            break
        
        # Notify user that request was sent
        await message.answer(
            "📞 درخواست تماس صوتی ارسال شد!\n\n"
            "در انتظار تایید مخاطب...",
            reply_markup=get_chat_reply_keyboard()
        )
        
        # Notify partner with accept/reject buttons
        bot = Bot(token=settings.BOT_TOKEN)
        try:
            call_keyboard = get_call_request_keyboard("voice", user.id)
            await bot.send_message(
                partner.telegram_id,
                "📞 درخواست تماس صوتی از مخاطب شما\n\n"
                "آیا می‌خواهید تماس صوتی را بپذیرید?",
                reply_markup=call_keyboard
            )
            await bot.session.close()
        except Exception as e:
            pass
        
        break


@router.message(F.text == "❌ قطع مکالمه")
async def end_chat_button(message: Message):
    """Handle 'End Chat' reply button."""
    from bot.handlers.chat import end_chat_request
    from aiogram.types import CallbackQuery
    
    class MockCallback:
        def __init__(self):
            self.from_user = message.from_user
            self.message = message
            self.data = 'chat:end'
        async def answer(self, *args, **kwargs):
            pass
    
    callback = MockCallback()
    await end_chat_request(callback)


@router.message(F.text == "❌ خروج از صف")
async def leave_queue_button(message: Message):
    """Handle 'Leave Queue' reply button."""
    user_id = message.from_user.id
    
    async for db_session in get_db():
        from db.crud import get_user_by_telegram_id
        from bot.handlers.chat import matchmaking_queue as mm_queue
        
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await message.answer(
                "❌ پروفایل شما یافت نشد. لطفاً /start را بزنید.",
                reply_markup=get_main_reply_keyboard()
            )
            break
        
        # Check if user is in queue
        if mm_queue and await mm_queue.is_user_in_queue(user_id):
            # Remove from queue
            await mm_queue.remove_user_from_queue(user_id)
            
            await message.answer(
                "✅ شما از صف خارج شدید.\n\n"
                "می‌توانید دوباره شروع به جستجو کنید.",
                reply_markup=get_main_reply_keyboard()
            )
        else:
            await message.answer(
                "❌ شما در صف نیستید.",
                reply_markup=get_main_reply_keyboard()
            )
        break


@router.message(F.text == "📹 چت تصویری ناشناس")
async def anonymous_video_call_button(message: Message):
    """Handle 'Anonymous Video Call' reply button."""
    user_id = message.from_user.id
    
    async for db_session in get_db():
        from db.crud import get_user_by_telegram_id, check_user_premium
        from bot.keyboards.anonymous_call import get_gender_preference_keyboard
        from bot.keyboards.common import get_premium_keyboard
        from config.settings import settings
        
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await message.answer("❌ پروفایل شما یافت نشد. لطفاً /start را بزنید.")
            break
        
        # Check premium status
        is_premium = await check_user_premium(db_session, user.id)
        
        if not is_premium:
            await message.answer(
                f"❌ شما عضویت ویژه ندارید.\n\n"
                f"💎 اشتراک پریمیوم\n\n"
                f"برای استفاده از چت تصویری ناشناس نیاز به پریمیوم دارید.\n\n"
                f"با خرید پریمیوم از امکانات زیر بهره‌مند شوید:\n"
                f"• چت تصویری ناشناس\n"
                f"• چت صوتی ناشناس\n"
                f"• زمان چت بیشتر ({settings.PREMIUM_CHAT_DURATION_MINUTES} دقیقه در مقابل {settings.MAX_CHAT_DURATION_MINUTES} دقیقه)\n"
                f"• فیلترهای پیشرفته\n"
                f"• اولویت در صف (نفر اول صف)\n\n"
                f"قیمت: {settings.PREMIUM_PRICE} تومان\n"
                f"مدت زمان: {settings.PREMIUM_DURATION_DAYS} روز\n\n"
                f"آیا می‌خواهید پریمیوم بخرید?",
                reply_markup=get_premium_keyboard()
            )
            break
        
        await message.answer(
            "📹 چت تصویری ناشناس\n\n"
            "مخاطب شما چه جنسیتی باشه؟",
            reply_markup=get_gender_preference_keyboard("video")
        )
        break


@router.message(F.text == "📞 چت صوتی ناشناس")
async def anonymous_voice_call_button(message: Message):
    """Handle 'Anonymous Voice Call' reply button."""
    user_id = message.from_user.id
    
    async for db_session in get_db():
        from db.crud import get_user_by_telegram_id, check_user_premium
        from bot.keyboards.anonymous_call import get_gender_preference_keyboard
        from bot.keyboards.common import get_premium_keyboard
        from config.settings import settings
        
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await message.answer("❌ پروفایل شما یافت نشد. لطفاً /start را بزنید.")
            break
        
        # Check premium status
        is_premium = await check_user_premium(db_session, user.id)
        
        if not is_premium:
            await message.answer(
                f"❌ شما عضویت ویژه ندارید.\n\n"
                f"💎 اشتراک پریمیوم\n\n"
                f"برای استفاده از چت صوتی ناشناس نیاز به پریمیوم دارید.\n\n"
                f"با خرید پریمیوم از امکانات زیر بهره‌مند شوید:\n"
                f"• چت تصویری ناشناس\n"
                f"• چت صوتی ناشناس\n"
                f"• زمان چت بیشتر ({settings.PREMIUM_CHAT_DURATION_MINUTES} دقیقه در مقابل {settings.MAX_CHAT_DURATION_MINUTES} دقیقه)\n"
                f"• فیلترهای پیشرفته\n"
                f"• اولویت در صف (نفر اول صف)\n\n"
                f"قیمت: {settings.PREMIUM_PRICE} تومان\n"
                f"مدت زمان: {settings.PREMIUM_DURATION_DAYS} روز\n\n"
                f"آیا می‌خواهید پریمیوم بخرید?",
                reply_markup=get_premium_keyboard()
            )
            break
        
        await message.answer(
            "📞 چت صوتی ناشناس\n\n"
            "مخاطب شما چه جنسیتی باشه؟",
            reply_markup=get_gender_preference_keyboard("voice")
        )
        break


@router.message(F.text == "🎁 پاداش‌ها و تعامل")
async def engagement_button(message: Message):
    """Handle 'Engagement' reply button."""
    user_id = message.from_user.id
    
    async for db_session in get_db():
        from db.crud import get_user_by_telegram_id, check_user_premium
        from core.points_manager import PointsManager
        from bot.keyboards.engagement import get_premium_rewards_menu_keyboard
        from config.settings import settings
        
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await message.answer("❌ پروفایل شما یافت نشد. لطفاً /start را بزنید.")
            break
        
        is_premium = await check_user_premium(db_session, user.id)
        points = await PointsManager.get_balance(user.id)
        
        if is_premium:
            expires_at = user.premium_expires_at.strftime("%Y-%m-%d %H:%M") if user.premium_expires_at else "هرگز"
            text = (
                f"💎 پریمیوم و پاداش‌ها\n\n"
                f"✅ وضعیت پریمیوم: فعال\n"
                f"📅 تاریخ انقضا: {expires_at}\n\n"
                f"💰 سکه‌های شما: {points}\n\n"
                f"💡 می‌توانی سکه‌ها را ذخیره کنی و بعداً برای تمدید پریمیوم استفاده کنی!\n\n"
                f"از منوی زیر انتخاب کنید:"
            )
        else:
            text = (
                f"💎 پریمیوم و پاداش‌ها\n\n"
                f"💰 سکه‌های شما: {points}\n\n"
                f"🎯 راه‌های دریافت پریمیوم:\n"
                f"1️⃣ 💎 تبدیل سکه به پریمیوم (اولویت)\n"
                f"   • 200 سکه = 1 روز\n"
                f"   • 3000 سکه = 1 ماه\n\n"
                f"2️⃣ 💳 خرید مستقیم\n"
                f"   • {settings.PREMIUM_PRICE} تومان = {settings.PREMIUM_DURATION_DAYS} روز\n\n"
                f"💡 با تعامل با ربات (پاداش روزانه، چت، دعوت دوستان) سکه کسب کن و پریمیوم بگیر!\n\n"
                f"از منوی زیر انتخاب کنید:"
            )
        
        await message.answer(
            text,
            reply_markup=get_premium_rewards_menu_keyboard(is_premium=is_premium)
        )
        break

