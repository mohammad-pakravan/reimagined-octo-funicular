"""
Start handler for the bot.
Handles /start command and initial user setup.
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart

from db.database import get_db
from db.crud import get_user_by_telegram_id, get_payment_transaction_by_transaction_id, check_user_premium, get_premium_plan_by_id
from bot.keyboards.common import get_main_menu_keyboard, get_gender_keyboard
from bot.keyboards.reply import remove_keyboard
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
                # User referral link - process referral for existing user
                referral_code = start_param.replace("ref_", "").upper()
                from db.crud import get_referral_code_by_code, create_referral
                from core.points_manager import PointsManager
                from core.achievement_system import AchievementSystem
                
                referral_code_obj = await get_referral_code_by_code(db_session, referral_code)
                if referral_code_obj:
                    # Check if user is trying to use their own code
                    if referral_code_obj.user_id != user.id:
                        # Check if already referred by this user
                        existing = await create_referral(
                            db_session,
                            referral_code_obj.user_id,
                            user.id,
                            referral_code
                        )
                        
                        if existing is not None:
                            # Award points
                            await PointsManager.award_referral(
                                referral_code_obj.user_id,
                                user.id
                            )
                            
                            # Check achievements
                            from db.crud import get_referral_count
                            referral_count = await get_referral_count(db_session, referral_code_obj.user_id)
                            await AchievementSystem.check_referral_achievement(
                                referral_code_obj.user_id,
                                referral_count
                            )
                            
                            await message.answer(
                                f"✅ کد دعوت '{referral_code}' با موفقیت ثبت شد!\n\n"
                                f"🎁 {settings.POINTS_REFERRAL_REFERRED} سکه به شما اهدا شد!"
                            )
            
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

