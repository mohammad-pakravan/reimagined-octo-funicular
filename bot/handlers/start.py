"""
Start handler for the bot.
Handles /start command and initial user setup.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.exceptions import TelegramBadRequest

from db.database import get_db
from db.crud import get_user_by_telegram_id, get_payment_transaction_by_transaction_id, check_user_premium, get_premium_plan_by_id, get_active_mandatory_channels
from bot.keyboards.common import get_main_menu_keyboard, get_gender_keyboard, get_channel_check_keyboard
from bot.keyboards.reply import remove_keyboard, get_main_reply_keyboard
from bot.keyboards.admin import get_admin_reply_keyboard
from bot.keyboards.engagement import get_premium_rewards_menu_keyboard
from config.settings import settings

router = Router()


async def check_payment_status(message: Message, transaction_id: str):
    """Check payment transaction status and notify user."""
    user_id = message.from_user.id
    
    async for db_session in get_db():
        # Get transaction
        transaction = await get_payment_transaction_by_transaction_id(db_session, transaction_id)
        
        if not transaction:
            await message.answer(
                "❌ تراکنش یافت نشد.\n\n"
                "لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید."
            )
            return
        
        # Check if transaction belongs to this user
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user or transaction.user_id != user.id:
            await message.answer(
                "❌ این تراکنش متعلق به شما نیست."
            )
            return
        
        # Check transaction status
        if transaction.status == 'completed':
            # Get plan name
            plan_name = "اشتراک پریمیوم"
            if transaction.plan_id:
                plan = await get_premium_plan_by_id(db_session, transaction.plan_id)
                if plan:
                    plan_name = plan.plan_name
            
            # Check if user has premium now
            is_premium = await check_user_premium(db_session, user.id)
            
            if is_premium:
                expires_at = user.premium_expires_at.strftime("%Y-%m-%d %H:%M") if user.premium_expires_at else "نامشخص"
                await message.answer(
                    f"✅ پرداخت موفق!\n\n"
                    f"💎 اشتراک پریمیوم «{plan_name}» فعال شد!\n\n"
                    f"📅 تاریخ انقضا: {expires_at}\n\n"
                    f"از این به بعد می‌توانید از تمام امکانات پریمیوم استفاده کنید.",
                    reply_markup=get_premium_rewards_menu_keyboard()
                )
            else:
                await message.answer(
                    f"✅ پرداخت موفق!\n\n"
                    f"💎 اشتراک پریمیوم «{plan_name}» فعال شد!\n\n"
                    f"لطفاً چند لحظه صبر کنید تا اشتراک شما فعال شود."
                )
        elif transaction.status == 'failed':
            await message.answer(
                f"❌ پرداخت ناموفق بود.\n\n"
                f"وضعیت: {transaction.payment_status or 'نامشخص'}\n\n"
                f"لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید."
            )
        elif transaction.status == 'cancelled':
            await message.answer(
                "⚠️ پرداخت لغو شد.\n\n"
                "می‌توانید دوباره تلاش کنید."
            )
        elif transaction.status in ['pending', 'processing']:
            await message.answer(
                "⏳ تراکنش در حال پردازش است.\n\n"
                "لطفاً چند لحظه صبر کنید و دوباره بررسی کنید."
            )
        else:
            await message.answer(
                f"❓ وضعیت تراکنش: {transaction.status}\n\n"
                f"لطفاً با پشتیبانی تماس بگیرید."
            )
        break


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Handle /start command."""
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Check for admin referral link or payment status
    start_param = None
    if message.text and len(message.text.split()) > 1:
        start_param = message.text.split()[1]
    
    # Check if this is a payment status check
    if start_param and start_param.startswith("payment_"):
        transaction_id = start_param.replace("payment_", "")
        await check_payment_status(message, transaction_id)
        return
    
    # Get database session
    async for db_session in get_db():
        # Check if user exists
        user = await get_user_by_telegram_id(db_session, user_id)
        
        if not user:
            # Store referral data for later use
            from bot.handlers.registration import registration_data
            if user_id not in registration_data:
                registration_data[user_id] = {}
            
            # Check if this is an admin referral link
            if start_param and start_param.startswith("admin_"):
                link_code = start_param.replace("admin_", "")
                from db.crud import get_admin_referral_link_by_code, increment_link_click
                
                link = await get_admin_referral_link_by_code(db_session, link_code)
                if link and link.is_active:
                    # Record click
                    await increment_link_click(
                        db_session,
                        link.id,
                        telegram_id=user_id,
                        ip_address=None,
                        user_agent=None
                    )
                    
                    # Store link code for later signup recording
                    registration_data[user_id]["admin_link_code"] = link_code
                    
                    # New user - start registration
                    await message.answer(
                        f"👋 به ربات چت ناشناس خوش آمدی!\n\n"
                        f"برای شروع چت، به اطلاعاتی از تو نیاز داریم.\n"
                        f"بیا پروفایلت رو بسازیم.\n\n"
                        f"اول، لطفاً جنسیت خودت رو انتخاب کن:",
                        reply_markup=get_gender_keyboard()
                    )
                    break
            # Check if this is a user referral link (ref_XXXXX)
            elif start_param and start_param.startswith("ref_"):
                referral_code = start_param.replace("ref_", "").upper()
                from db.crud import get_referral_code_by_code
                
                referral_code_obj = await get_referral_code_by_code(db_session, referral_code)
                if referral_code_obj:
                    # Store referral code for later use after registration
                    registration_data[user_id]["referral_code"] = referral_code
                    
                    # New user - start registration
                    await message.answer(
                        f"👋 به ربات چت ناشناس خوش آمدی!\n\n"
                        f"برای شروع چت، به اطلاعاتی از تو نیاز داریم.\n"
                        f"بیا پروفایلت رو بسازیم.\n\n"
                        f"اول، لطفاً جنسیت خودت رو انتخاب کن:",
                        reply_markup=get_gender_keyboard()
                    )
                    break
            
            # New user - start registration (no referral)
            await message.answer(
                f"👋 به ربات چت ناشناس خوش آمدی!\n\n"
                f"برای شروع چت، به اطلاعاتی از تو نیاز داریم.\n"
                f"بیا پروفایلت رو بسازیم.\n\n"
                f"اول، لطفاً جنسیت خودت رو انتخاب کن:",
                reply_markup=get_gender_keyboard()
            )
        else:
            # Existing user - check for referral links
            if start_param and start_param.startswith("admin_"):
                # Admin referral link - just record click
                link_code = start_param.replace("admin_", "")
                from db.crud import get_admin_referral_link_by_code, increment_link_click
                
                link = await get_admin_referral_link_by_code(db_session, link_code)
                if link and link.is_active:
                    # Record click even for existing users
                    await increment_link_click(
                        db_session,
                        link.id,
                        telegram_id=user_id,
                        ip_address=None,
                        user_agent=None
                    )
            elif start_param and start_param.startswith("ref_"):
                # User referral link - existing user clicked referral link
                # Do NOT award points for existing users, only for new users during registration
                # Just show a message that they're already registered
                pass
            
            # Existing user - show main menu
            if user.is_banned:
                await message.answer("❌ حساب کاربری شما مسدود شده است.")
                return
            
            # Check if user is admin
            from bot.keyboards.reply import get_main_reply_keyboard
            from bot.keyboards.admin import get_admin_reply_keyboard
            
            if user_id in settings.ADMIN_IDS:
                await message.answer(
                    f"👋 خوش برگشتی، {username or 'ادمین'}!\n\n"
                    f"پنل مدیریت ربات:",
                    reply_markup=get_admin_reply_keyboard()
                )
            else:
                await message.answer(
                    f"👋 خوش برگشتی، {username or 'کاربر'}!\n\n"
                    f"یک گزینه انتخاب کن:",
                    reply_markup=get_main_reply_keyboard()
                )
        break


@router.callback_query(F.data == "channel:check_membership")
async def callback_check_channel_membership(callback: CallbackQuery):
    """Check if user has joined all mandatory channels."""
    user_id = callback.from_user.id
    bot = callback.bot
    
    try:
        # Get active mandatory channels
        async for db_session in get_db():
            mandatory_channels = await get_active_mandatory_channels(db_session)
            break
        else:
            # Fallback to old MANDATORY_CHANNEL_ID if no channels in database
            if settings.MANDATORY_CHANNEL_ID:
                mandatory_channels = [type('obj', (object,), {
                    'channel_id': settings.MANDATORY_CHANNEL_ID,
                    'channel_link': f"https://t.me/{settings.MANDATORY_CHANNEL_ID.lstrip('@')}",
                    'channel_name': None
                })()]
            else:
                mandatory_channels = []
        
        if not mandatory_channels:
            # No mandatory channels, allow access
            await callback.answer("✅ عضویت تایید شد!", show_alert=True)
            await callback.message.delete()
            return
        
        # Check if user is member of all mandatory channels
        missing_channels = []
        all_joined = True
        
        for channel in mandatory_channels:
            try:
                member = await bot.get_chat_member(
                    channel.channel_id,
                    user_id
                )
                
                # Check membership status
                if member.status not in ["member", "administrator", "creator"]:
                    # User hasn't joined this channel
                    channel_link = channel.channel_link or f"https://t.me/{channel.channel_id.lstrip('@')}"
                    channel_name = channel.channel_name or channel.channel_id
                    missing_channels.append({
                        'name': channel_name,
                        'link': channel_link
                    })
                    all_joined = False
            except TelegramBadRequest:
                # Channel doesn't exist or bot can't access it, skip it
                pass
            except Exception:
                # Error checking membership, skip this channel
                pass
        
        if all_joined:
            # User has joined all channels
            await callback.answer("✅ عالی! شما به همه چنل‌ها عضو هستید.", show_alert=True)
            
            # Delete the channel check message
            try:
                await callback.message.delete()
            except:
                pass
            
            # Show welcome message
            async for db_session in get_db():
                user = await get_user_by_telegram_id(db_session, user_id)
                if user:
                    if user.is_banned:
                        await callback.message.answer("❌ حساب کاربری شما مسدود شده است.")
                        return
                    
                    username = callback.from_user.username or 'کاربر'
                    
                    # Check if user is admin
                    if user_id in settings.ADMIN_IDS:
                        await callback.message.answer(
                            f"👋 خوش آمدید، {username}!\n\n"
                            f"پنل مدیریت ربات:",
                            reply_markup=get_admin_reply_keyboard()
                        )
                    else:
                        await callback.message.answer(
                            f"👋 خوش آمدید، {username}!\n\n"
                            f"یک گزینه انتخاب کن:",
                            reply_markup=get_main_reply_keyboard()
                        )
                break
        else:
            # User hasn't joined all channels yet
            channels_list = []
            channel_buttons = []
            
            for idx, channel in enumerate(missing_channels, start=1):
                channel_name = channel.get('name', 'چنل')
                channel_link = channel.get('link', '')
                channels_list.append(f"{idx}. {channel_name}")
                channel_buttons.append({
                    'name': channel_name,
                    'link': channel_link
                })
            
            channels_text = "\n".join(channels_list)
            
            message_text = (
                "━━━━━━━━━━━━━━━━━━━━\n"
                "⚠️ عضویت اجباری در چنل‌ها\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "📺 برای استفاده از ربات، باید به چنل‌های زیر عضو شوید:\n\n"
                f"{channels_text}\n\n"
                "💡 روی دکمه‌های بالا کلیک کنید تا به چنل‌ها بروید.\n"
                "بعد از عضویت، روی دکمه «✅ بررسی عضویت» کلیک کنید."
            )
            
            await callback.answer("⚠️ هنوز به همه چنل‌ها عضو نشده‌اید.", show_alert=True)
            await callback.message.edit_text(
                message_text,
                reply_markup=get_channel_check_keyboard(channel_buttons),
                parse_mode="HTML"
            )
    except Exception as e:
        await callback.answer("❌ خطا در بررسی عضویت. لطفاً دوباره تلاش کنید.", show_alert=True)

