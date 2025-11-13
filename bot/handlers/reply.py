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
from config.settings import settings

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
        
        # Check if user is already in queue
        from bot.handlers.chat import matchmaking_queue as mm_queue
        if mm_queue and await mm_queue.is_user_in_queue(user_id):
            await message.answer(
                "⏳ در حال جستجو هستی ! 🔍\n\n"
                "💡 اگه می‌خوای جستجوی جدیدی شروع کنی، اول جستجوی قبلی رو لغو کن ⏹️"
            )
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
            
            # Get user badges
            from core.badge_manager import BadgeManager
            user_badges_display = await BadgeManager.get_user_badges_display(user.id, limit=5)
            
            from utils.validators import get_display_name
            profile_text = (
                f"📊 پروفایل من\n\n"
                f"• نام: {get_display_name(user)}\n"
                f"• جنسیت: {gender_text}\n"
                f"• استان: {user.province or 'تعیین نشده'}\n"
                f"• شهر: {user.city or 'تعیین نشده'}\n"
                f"• سن: {user.age or 'تعیین نشده'}\n"
                f"• پریمیوم: {'✅ فعال' if user.is_premium else '❌ غیرفعال'}\n"
            )
            
            # Add badges if available
            if user_badges_display:
                profile_text += f"• مدال‌ها: {user_badges_display}\n"
            
            profile_text += f"ID: {user_unique_id}"
            
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
    """Handle 'Premium' reply button - show premium purchase menu."""
    user_id = message.from_user.id
    
    async for db_session in get_db():
        from db.crud import get_user_by_telegram_id, check_user_premium, get_visible_premium_plans
        from bot.keyboards.premium_plan import get_user_premium_plans_keyboard
        from bot.keyboards.common import get_premium_keyboard
        
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await message.answer("❌ کاربر یافت نشد.")
            break
        
        is_premium = await check_user_premium(db_session, user.id)
        
        if is_premium:
            expires_at = user.premium_expires_at.strftime("%Y-%m-%d %H:%M") if user.premium_expires_at else "هرگز"
            await message.answer(
                f"💎 وضعیت پریمیوم\n\n"
                f"✅ شما اشتراک پریمیوم فعال دارید!\n\n"
                f"تاریخ انقضا: {expires_at}\n\n"
                f"ویژگی‌های پریمیوم:\n"
                f"• تماس تصویری در وب اپ ( به زودی )\n"
                f"• ارتباط بدون مصرف سکه\n"
                f"• فیلترهای پیشرفته ( به زودی )\n"
                f"• اولویت در صف (نفر اول صف)"
            )
        else:
            # Get premium plans from database
            plans = await get_visible_premium_plans(db_session)
            
            if plans:
                text = "💎 اشتراک پریمیوم\n\n"
                text += "با خرید پریمیوم از امکانات زیر بهره‌مند شوید:\n\n"
                text += "• تماس تصویری در وب اپ ( به زودی )\n"
                text += "• ارتباط بدون مصرف سکه\n"
                text += "• فیلترهای پیشرفته ( به زودی )\n"
                text += "• اولویت در صف (نفر اول صف)\n\n"
                text += "🎁 پلن‌های موجود:\n\n"
                
                from datetime import datetime
                now = datetime.utcnow()
                for plan in plans:
                    discount_text = ""
                    if plan.discount_start_date and plan.discount_end_date:
                        if plan.discount_start_date <= now <= plan.discount_end_date:
                            discount_text = f" 🔥 {plan.discount_percent}% تخفیف"
                    
                    text += f"💎 {plan.plan_name}\n"
                    if plan.original_price and plan.price < plan.original_price:
                        text += f"   ~~{int(plan.original_price):,}~~ {int(plan.price):,} تومان{discount_text}\n"
                    else:
                        text += f"   {int(plan.price):,} تومان\n"
                    text += f"   ⏰ {plan.duration_days} روز\n\n"
                
                text += "پلن مورد نظر را انتخاب کنید:"
                
                await message.answer(
                    text,
                    reply_markup=get_user_premium_plans_keyboard(plans)
                )
            else:
                # Fallback to default if no plans
                await message.answer(
                    f"💎 اشتراک پریمیوم\n\n"
                    f"با خرید پریمیوم از امکانات زیر بهره‌مند شوید:\n\n"
                    f"• تماس تصویری در وب اپ ( به زودی )\n"
                    f"• ارتباط بدون مصرف سکه\n"
                    f"• فیلترهای پیشرفته ( به زودی )\n"
                    f"• اولویت در صف (نفر اول صف)\n\n"
                    f"قیمت: {settings.PREMIUM_PRICE} تومان\n"
                    f"مدت زمان: {settings.PREMIUM_DURATION_DAYS} روز\n\n"
                    f"آیا می‌خواهید پریمیوم بخرید?",
                    reply_markup=get_premium_keyboard()
                )
        break


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
        from db.crud import is_liked, is_following, is_blocked, get_chat_end_notifications_for_user, check_user_premium
        is_liked_status = await is_liked(db_session, user.id, partner.id)
        is_following_status = await is_following(db_session, user.id, partner.id)
        is_blocked_status = await is_blocked(db_session, user.id, partner.id)
        
        # Get notification status
        notifications = await get_chat_end_notifications_for_user(db_session, user.id)
        is_notifying_status = any(n.watched_user_id == partner.id for n in notifications) if notifications else False
        
        # Check partner premium status
        partner_premium = await check_user_premium(db_session, partner.id)
        
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
        
        # Get partner badges
        from core.badge_manager import BadgeManager
        partner_badges_display = await BadgeManager.get_user_badges_display(partner.id, limit=5)
        
        profile_text = (
            f"• نام: {partner.username or 'تعیین نشده'}\n"
            f"• جنسیت: {gender_text}\n"
            f"• استان: {partner.province or 'تعیین نشده'}\n"
            f"• شهر: {partner.city or 'تعیین نشده'}\n"
            f"• سن: {partner.age or 'تعیین نشده'}\n"
            f"• پریمیوم: {'✅ فعال' if partner_premium else '❌ غیرفعال'}\n"
        )
        
        # Add badges if available
        if partner_badges_display:
            profile_text += f"• مدال‌ها: {partner_badges_display}\n"
        
        profile_text += f"ID: {user_unique_id}"
        
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
            from utils.minio_storage import is_url_accessible_from_internet
            import logging
            logger = logging.getLogger(__name__)
            
            bot = Bot(token=settings.BOT_TOKEN)
            try:
                # Check if it's a URL or file_id
                if profile_image_url.startswith(('http://', 'https://')):
                    # It's a URL - check if accessible
                    if is_url_accessible_from_internet(profile_image_url):
                        # URL is accessible, use directly
                        await bot.send_photo(
                            user_id,
                            profile_image_url,
                            caption=profile_text,
                            reply_markup=profile_keyboard
                        )
                    else:
                        # URL is not accessible, download and re-upload
                        try:
                            import aiohttp
                            async with aiohttp.ClientSession() as session:
                                async with session.get(profile_image_url) as resp:
                                    if resp.status == 200:
                                        image_data = await resp.read()
                                        from aiogram.types import BufferedInputFile
                                        photo_file = BufferedInputFile(image_data, filename="profile.jpg")
                                        await bot.send_photo(
                                            user_id,
                                            photo_file,
                                            caption=profile_text,
                                            reply_markup=profile_keyboard
                                        )
                                    else:
                                        raise Exception(f"Failed to download image: {resp.status}")
                        except Exception as e:
                            logger.warning(f"Failed to download and send MinIO image: {e}")
                            await message.answer(profile_text, reply_markup=profile_keyboard)
                else:
                    # It's a file_id, use directly
                    await bot.send_photo(
                        user_id,
                        profile_image_url,
                        caption=profile_text,
                        reply_markup=profile_keyboard
                    )
                await bot.session.close()
            except Exception as e:
                logger.error(f"Error sending photo: {e}", exc_info=True)
                await message.answer(profile_text, reply_markup=profile_keyboard)
        else:
            await message.answer(profile_text, reply_markup=profile_keyboard)
        
        # Notify partner that their profile was viewed
        try:
            from aiogram import Bot as NotifyBot
            from config.settings import settings
            from db.crud import get_active_chat_room_by_user
            
            # Check if chat is still active
            chat_room = await get_active_chat_room_by_user(db_session, user.id)
            if chat_room and chat_room.is_active:
                notify_bot = NotifyBot(token=settings.BOT_TOKEN)
                try:
                    await notify_bot.send_message(
                        partner.telegram_id,
                        "👁️ مخاطبت پروفایلت رو مشاهده کرد!",
                        reply_markup=get_chat_reply_keyboard()
                    )
                    await notify_bot.session.close()
                except Exception:
                    pass  # Partner might have blocked the bot or left chat
        except Exception:
            pass  # Don't fail if notification fails
        
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


@router.message(F.text.in_({"🟢 حالت خصوصی", "⚪ حالت خصوصی", "🔒 حالت خصوصی", "🔒 فعال کردن حالت خصوصی", "🔓 غیرفعال کردن حالت خصوصی"}))
async def toggle_private_mode_button(message: Message):
    """Handle 'Private Mode' reply button."""
    user_id = message.from_user.id
    
    async for db_session in get_db():
        from db.crud import get_user_by_telegram_id, get_active_chat_room_by_user
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
        
        # Get chat room
        chat_room = await get_active_chat_room_by_user(db_session, user.id)
        if not chat_room:
            await message.answer(
                "❌ چت فعالی یافت نشد.",
                reply_markup=get_chat_reply_keyboard()
            )
            break
        
        # Get current private mode status
        current_private_mode = await chat_mgr.get_private_mode(chat_room.id, user.id)
        
        # Toggle private mode
        new_private_mode = not current_private_mode
        await chat_mgr.set_private_mode(chat_room.id, user.id, new_private_mode)
        
        # Update keyboard with new private mode status
        updated_keyboard = get_chat_reply_keyboard(private_mode=new_private_mode)
        
        if new_private_mode:
            await message.answer(
                "🔒 حالت خصوصی فعال شد!\n\n"
                "از این به بعد پیام‌های شما غیرقابل فوروارد و ذخیره هستند.",
                reply_markup=updated_keyboard
            )
        else:
            await message.answer(
                "🔓 حالت خصوصی غیرفعال شد!\n\n"
                "پیام‌های شما قابل فوروارد و ذخیره هستند.",
                reply_markup=updated_keyboard
            )
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
        
        # Get user medals
        from core.badge_manager import BadgeManager
        user_badges = await BadgeManager.get_user_badges_list(user.id, limit=5)
        medals_count = len(await BadgeManager.get_user_badges_list(user.id))
        
        # Format medals display
        medals_display = ""
        if user_badges:
            medal_icons = [ub.badge.badge_icon or "🏆" for ub in user_badges]
            medals_display = f"\n🏅 مدال‌های شما: {' '.join(medal_icons)}"
            if medals_count > 5:
                medals_display += f" (+{medals_count - 5} مدال دیگر)"
        
        if is_premium:
            expires_at = user.premium_expires_at.strftime("%Y-%m-%d %H:%M") if user.premium_expires_at else "هرگز"
            text = (
                f"💎 پریمیوم و پاداش‌ها\n\n"
                f"✅ وضعیت پریمیوم: فعال\n"
                f"📅 تاریخ انقضا: {expires_at}\n\n"
                f"💰 سکه‌های شما: {points}\n"
            )
            if medals_display:
                text += medals_display
            text += (
                f"\n\n💡 می‌توانی سکه‌ها را ذخیره کنی و بعداً برای تمدید پریمیوم استفاده کنی!\n\n"
                f"از منوی زیر انتخاب کنید:"
            )
        else:
            text = (
                f"💎 پریمیوم و پاداش‌ها\n\n"
                f"💰 سکه‌های شما: {points}\n"
            )
            if medals_display:
                text += medals_display
            text += (
                f"\n\n🎯 راه‌های دریافت پریمیوم:\n"
                f"1️⃣ ⭐ خرید با استارز تلگرام\n"
                f"2️⃣ 💳 خرید با شاپرک\n"
                f"3️⃣ 💎 تبدیل سکه به پریمیوم\n\n"
                f"✨ چرا پریمیوم بهتره؟\n"
                f"• اولویت در صف جستجو\n"
                f"• چت رایگان (بدون کسر سکه)\n"
                f"• مدت زمان چت بیشتر\n"
                f"• امکانات ویژه و بیشتر\n"
                f"• پشتیبانی اولویت‌دار\n\n"
                f"💡 با تعامل با ربات (پاداش روزانه، چت، دعوت دوستان) سکه کسب کن و پریمیوم بگیر!\n\n"
                f"از منوی زیر انتخاب کنید:"
            )
        
        await message.answer(
            text,
            reply_markup=get_premium_rewards_menu_keyboard(is_premium=is_premium)
        )
        break


@router.message(F.text == "💰 سکه ی رایگان")
async def free_coins_menu(message: Message):
    """Show daily reward menu when user clicks free coins button."""
    user_id = message.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await message.answer("❌ کاربر یافت نشد.")
            return
        
        from core.reward_system import RewardSystem
        from bot.keyboards.engagement import get_daily_reward_keyboard
        
        # Get streak info
        streak_info = await RewardSystem.get_streak_info(user.id)
        
        # Check if can claim today
        can_claim_today = streak_info.get('can_claim_today', False)
        
        if can_claim_today:
            text = (
                "💰 سکه ی رایگان روزانه\n\n"
                "🎁 امروز می‌توانی سکه رایگان دریافت کنی!\n\n"
                "روی دکمه زیر کلیک کن تا سکه‌هایت را دریافت کنی:"
            )
        else:
            points_claimed = streak_info.get('points_claimed', 0)
            streak_count = streak_info.get('streak_count', 0)
            text = (
                "💰 سکه ی رایگان روزانه\n\n"
                f"✅ شما امروز سکه خود را دریافت کرده‌اید!\n\n"
                f"💰 سکه دریافت شده: {points_claimed}\n"
            )
            if streak_count > 0:
                text += f"🔥 سکه ی روزانه: {streak_count} روز\n\n"
            text += "فردا دوباره بیا تا سکه ی روزانه‌ات را ادامه بدهی!"
        
        await message.answer(
            text,
            reply_markup=get_daily_reward_keyboard(already_claimed=not can_claim_today)
        )
        break


@router.message(F.text == "👥 دعوت دوستان( سکه رایگان )")
async def referral_menu(message: Message):
    """Show referral menu when user clicks referral button."""
    user_id = message.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await message.answer("❌ کاربر یافت نشد.")
            return
        
        from db.crud import get_or_create_user_referral_code, get_referral_count, get_coins_for_activity
        from bot.keyboards.engagement import get_referral_menu_keyboard
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        referral_code_obj = await get_or_create_user_referral_code(db_session, user.id)
        referral_count = await get_referral_count(db_session, user.id)
        
        # Get coin rewards from database
        coins_profile_complete = await get_coins_for_activity(db_session, "referral_profile_complete")
        if coins_profile_complete is None:
            # Try fallback to old referral_referrer
            coins_profile_complete = await get_coins_for_activity(db_session, "referral_referrer")
            if coins_profile_complete is None:
                coins_profile_complete = 0
        
        # Get bot username
        try:
            bot_info = await message.bot.get_me()
            bot_username = bot_info.username or "bot"
        except Exception:
            bot_username = "bot"
        
        referral_link = f"https://t.me/{bot_username}?start=ref_{referral_code_obj.referral_code}"
        
        # Calculate total points (approximate, as we don't know how many completed profile)
        total_points = referral_count * coins_profile_complete
        
        # First message: Statistics and instructions
        stats_text = (
            f"👥 دعوت دوستان (سکه رایگان)\n\n"
            f"📊 آمار شما:\n"
            f"• تعداد دعوت‌ها: {referral_count}\n"
        )
        
        if coins_profile_complete > 0:
            stats_text += f"• سکه برای هر دعوت: {coins_profile_complete}\n"
            stats_text += f"• سکه کل (تقریبی): {total_points}\n\n"
        
        stats_text += (
            "💡 چگونه دعوت کنم؟\n"
            "1️⃣ لینک دعوت را از پیام بعدی کپی کنید\n"
            "2️⃣ برای دوستان خود ارسال کنید\n"
            "3️⃣ وقتی دوست شما ثبت‌نام کند، هر دو نفر سکه دریافت می‌کنید!\n\n"
            "🎁 پاداش‌ها:\n"
            "• وقتی دوست شما ثبت‌نام کند: هر دو نفر سکه می‌گیرید\n"
            "• وقتی دوست شما پروفایل را تکمیل کند: هر دو نفر سکه بیشتری می‌گیرید"
        )
        
        await message.answer(
            stats_text,
            reply_markup=get_referral_menu_keyboard()
        )
        
        # Second message: Forwardable referral link message
        forward_text = (
            f"🎉 به ربات چت ناشناس خوش آمدید!\n\n"
            f"💬 با این ربات می‌توانید:\n"
            f"• با کاربران دیگر چت کنید\n"
            f"• دوستان جدید پیدا کنید\n"
            f"• سکه رایگان دریافت کنید\n\n"
            f"🔗 برای عضویت روی لینک زیر کلیک کنید:\n"
            f"{referral_link}\n\n"
            f"🎁 با عضویت از طریق این لینک، هر دو نفر سکه رایگان دریافت می‌کنید!"
        )
        
        # Create keyboard with referral link button
        share_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 عضویت در ربات",
                    url=referral_link
                )
            ]
        ])
        
        await message.answer(
            forward_text,
            reply_markup=share_keyboard
        )
        break

