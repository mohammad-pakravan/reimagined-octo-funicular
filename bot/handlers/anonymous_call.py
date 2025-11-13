"""
Anonymous call handler for video and voice chat.
Handles anonymous video/voice call matching.
"""
import random
import json
import time
import asyncio
import aiohttp
from aiogram import Router, F
from aiogram.types import CallbackQuery

from db.database import get_db
from db.crud import (
    get_user_by_telegram_id,
    get_user_by_id,
    is_liked,
    is_following,
    is_blocked,
)
from bot.keyboards.anonymous_call import (
    get_gender_preference_keyboard,
    get_match_found_keyboard,
    get_searching_keyboard,
)
from bot.keyboards.profile import get_profile_keyboard
from bot.keyboards.common import get_main_menu_keyboard
from config.settings import settings
from utils.validators import get_display_name

router = Router()

# Redis client will be set from main.py
redis_client = None
anonymous_call_queue_prefix = "anonymous_call:queue"
anonymous_call_user_data_prefix = "anonymous_call:user"


def set_redis_client(client):
    """Set Redis client for anonymous call handler."""
    global redis_client
    redis_client = client


async def add_to_anonymous_queue(
    user_id: int,
    call_type: str,
    preferred_gender: str,
    user_gender: str = None
) -> bool:
    """Add user to anonymous call queue."""
    if not redis_client:
        return False
    
    user_data = {
        "user_id": user_id,
        "call_type": call_type,
        "preferred_gender": preferred_gender,
        "user_gender": user_gender,
        "joined_at": time.time(),
    }
    
    # Store user data
    user_data_key = f"{anonymous_call_user_data_prefix}:{user_id}"
    await redis_client.setex(
        user_data_key,
        300,  # 5 minutes timeout
        json.dumps(user_data)
    )
    
    # Add to queue based on call type and preferred gender
    queue_key = f"{anonymous_call_queue_prefix}:{call_type}:{preferred_gender}"
    await redis_client.sadd(queue_key, user_id)
    await redis_client.expire(queue_key, 300)
    
    return True


async def remove_from_anonymous_queue(user_id: int, call_type: str = None, preferred_gender: str = None) -> bool:
    """Remove user from anonymous call queue."""
    if not redis_client:
        return False
    
    # Remove user data
    user_data_key = f"{anonymous_call_user_data_prefix}:{user_id}"
    await redis_client.delete(user_data_key)
    
    # Remove from all possible queues
    if call_type and preferred_gender:
        queue_key = f"{anonymous_call_queue_prefix}:{call_type}:{preferred_gender}"
        await redis_client.srem(queue_key, user_id)
    else:
        # Remove from all queues
        for call_t in ["video", "voice"]:
            for gender in ["male", "female", "all"]:
                queue_key = f"{anonymous_call_queue_prefix}:{call_t}:{gender}"
                await redis_client.srem(queue_key, user_id)
    
    return True


async def find_match(user_id: int, call_type: str, preferred_gender: str, user_gender: str = None) -> tuple:
    """Find a match for anonymous call."""
    if not redis_client:
        return None, None
    
    # Determine which queues to search based on what user is looking for
    queues_to_search = []
    
    # If user wants "all", search all gender queues
    if preferred_gender == "all":
        for gender in ["male", "female", "all"]:
            queue_key = f"{anonymous_call_queue_prefix}:{call_type}:{gender}"
            queues_to_search.append((queue_key, gender))
    else:
        # Search for specific gender
        queue_key = f"{anonymous_call_queue_prefix}:{call_type}:{preferred_gender}"
        queues_to_search.append((queue_key, preferred_gender))
        
        # Also search "all" queue (users who don't care about gender)
        queue_key_all = f"{anonymous_call_queue_prefix}:{call_type}:all"
        queues_to_search.append((queue_key_all, "all"))
    
    # Search for matches
    candidates = []
    for queue_key, _ in queues_to_search:
        members = await redis_client.smembers(queue_key)
        for member_id in members:
            try:
                member_id_int = int(member_id)
                if member_id_int != user_id:
                    # Check if this member is looking for our user's gender or "all"
                    member_data_key = f"{anonymous_call_user_data_prefix}:{member_id_int}"
                    member_data_str = await redis_client.get(member_data_key)
                    if member_data_str:
                        member_data = json.loads(member_data_str)
                        member_pref = member_data.get("preferred_gender", "all")
                        member_gender = member_data.get("user_gender")
                        
                        # Check compatibility:
                        # 1. Member wants "all" OR
                        # 2. Member wants our user's gender OR
                        # 3. Our user wants "all" and member's gender matches what we want
                        if (member_pref == "all" or 
                            member_pref == user_gender or 
                            (preferred_gender == "all" and member_gender == preferred_gender) or
                            (preferred_gender != "all" and member_gender == preferred_gender)):
                            candidates.append(member_id_int)
            except (ValueError, TypeError):
                continue
    
    if candidates:
        # Randomly select a candidate
        selected_id = random.choice(candidates)
        return selected_id, call_type
    
    return None, None


async def create_anonymous_call_room(user1_id: int, user2_id: int, call_type: str) -> dict:
    """Create anonymous call room via API."""
    import uuid
    
    # Generate room ID
    room_id = str(uuid.uuid4())
    
    # Store room data in Redis
    if redis_client:
        room_key = f"anonymous_call:room:{room_id}"
        room_data = {
            "user1_id": user1_id,
            "user2_id": user2_id,
            "call_type": call_type,
            "created_at": time.time(),
        }
        await redis_client.setex(room_key, 3600, json.dumps(room_data))  # 1 hour expiry
    
    # Create call via API
    try:
        import os
        api_host = os.getenv("VIDEO_CALL_API_URL", "http://localhost:8000").replace("http://", "").replace("https://", "").split(":")[0]
        if not api_host or api_host == "localhost" or api_host.startswith("127.0.0.1"):
            api_host = "localhost"
            api_base = f"http://{api_host}:{settings.API_PORT}"
        else:
            api_base = f"http://bot:{settings.API_PORT}"
        
        api_url = f"{api_base}/api/video-call/create"
        headers = {
            "X-API-Key": settings.API_SECRET_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "user1_id": user1_id,
            "user2_id": user2_id,
            "chat_room_id": 0,  # No chat room for anonymous calls
            "call_type": call_type
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "room_id": data.get("room_id", room_id),
                        "link": data.get("link", f"{settings.VIDEO_CALL_DOMAIN}/call/{room_id}")
                    }
    except Exception as e:
        print(f"Error creating call room: {e}")
    
    # Fallback: generate link manually
    return {
        "room_id": room_id,
        "link": f"{settings.VIDEO_CALL_DOMAIN}/call/{room_id}"
    }


@router.callback_query(F.data.startswith("anonymous_call:video"))
async def anonymous_video_call(callback: CallbackQuery):
    """Start anonymous video call."""
    if callback.data == "anonymous_call:video":
        user_id = callback.from_user.id
        
        async for db_session in get_db():
            from db.crud import get_user_by_telegram_id, check_user_premium
            user = await get_user_by_telegram_id(db_session, user_id)
            if not user:
                await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
                return
            
            # Check premium status
            is_premium = await check_user_premium(db_session, user.id)
            
            if not is_premium:
                from bot.keyboards.common import get_premium_keyboard
                await callback.message.edit_text(
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
                await callback.answer()
                break
            
            # Show gender preference selection
            await callback.message.edit_text(
                "📹 چت تصویری ناشناس\n\n"
                "مخاطب شما چه جنسیتی باشه؟",
                reply_markup=get_gender_preference_keyboard("video")
            )
            await callback.answer()
            break
    else:
        # Handle gender selection
        parts = callback.data.split(":")
        if len(parts) >= 4:
            call_type = parts[2]
            preferred_gender = parts[3]
            
            user_id = callback.from_user.id
            
            async for db_session in get_db():
                from db.crud import get_user_by_telegram_id, check_user_premium
                user = await get_user_by_telegram_id(db_session, user_id)
                if not user:
                    await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
                    return
                
                # Check premium status
                is_premium = await check_user_premium(db_session, user.id)
                
                if not is_premium:
                    from bot.keyboards.common import get_premium_keyboard
                    call_type_text = "تصویری" if call_type == "video" else "صوتی"
                    await callback.message.edit_text(
                        f"❌ شما عضویت ویژه ندارید.\n\n"
                        f"💎 اشتراک پریمیوم\n\n"
                        f"برای استفاده از چت {call_type_text} ناشناس نیاز به پریمیوم دارید.\n\n"
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
                    await callback.answer()
                    return
                
                # Add to queue
                await add_to_anonymous_queue(
                    user.id,
                    call_type,
                    preferred_gender,
                    user.gender
                )
                
                await callback.message.edit_text(
                    "🔍 در حال جستجوی مخاطب...\n\n"
                    "لطفاً صبر کنید...",
                    reply_markup=get_searching_keyboard(call_type)
                )
                
                # Try to find match multiple times
                max_attempts = 10
                partner_id = None
                
                for attempt in range(max_attempts):
                    await asyncio.sleep(2)  # Wait a bit for other users to join
                    partner_id, _ = await find_match(user.id, call_type, preferred_gender, user.gender)
                    
                    if partner_id:
                        break
                    
                    # Update message to show still searching
                    if attempt < max_attempts - 1:
                        await callback.message.edit_text(
                            f"🔍 در حال جستجوی مخاطب...\n\n"
                            f"لطفاً صبر کنید... (تلاش {attempt + 1}/{max_attempts})",
                            reply_markup=get_searching_keyboard(call_type)
                        )
                
                if partner_id:
                    # Match found!
                    await remove_from_anonymous_queue(user.id, call_type, preferred_gender)
                    await remove_from_anonymous_queue(partner_id, call_type, preferred_gender)
                    
                    # Create call room
                    call_data = await create_anonymous_call_room(user.id, partner_id, call_type)
                    
                    call_type_text = "تصویری" if call_type == "video" else "صوتی"
                    await callback.message.edit_text(
                        f"✅ مخاطبت رو پیدا کردم!\n\n"
                        f"📹 چت {call_type_text} ناشناس\n\n"
                        f"با کلیک روی لینک زیر وارد چت شو:",
                        reply_markup=get_match_found_keyboard(
                            call_type,
                            partner_id,
                            call_data["room_id"],
                            call_data["link"]
                        )
                    )
                    
                    # Notify partner (if they're still in queue)
                    try:
                        from db.crud import get_user_by_id
                        partner_user = await get_user_by_id(db_session, partner_id)
                        if partner_user:
                            from aiogram import Bot
                            from config.settings import settings
                            bot = Bot(token=settings.BOT_TOKEN)
                            partner_call_data = await create_anonymous_call_room(partner_id, user.id, call_type)
                            await bot.send_message(
                                partner_user.telegram_id,
                                f"✅ مخاطبت رو پیدا کردم!\n\n"
                                f"📹 چت {call_type_text} ناشناس\n\n"
                                f"با کلیک روی لینک زیر وارد چت شو:",
                                reply_markup=get_match_found_keyboard(
                                    call_type,
                                    user.id,
                                    partner_call_data["room_id"],
                                    partner_call_data["link"]
                                )
                            )
                            await bot.session.close()
                    except Exception as e:
                        print(f"Error notifying partner: {e}")
                else:
                    # No match found
                    await callback.message.edit_text(
                        "❌ متأسفانه مخاطبی پیدا نشد!\n\n"
                        "می‌توانی دوباره تلاش کنی یا بعداً برگردی.",
                        reply_markup=get_main_menu_keyboard()
                    )
                
                await callback.answer()
                break


@router.callback_query(F.data.startswith("anonymous_call:voice"))
async def anonymous_voice_call(callback: CallbackQuery):
    """Start anonymous voice call."""
    if callback.data == "anonymous_call:voice":
        user_id = callback.from_user.id
        
        async for db_session in get_db():
            from db.crud import get_user_by_telegram_id, check_user_premium
            user = await get_user_by_telegram_id(db_session, user_id)
            if not user:
                await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
                return
            
            # Check premium status
            is_premium = await check_user_premium(db_session, user.id)
            
            if not is_premium:
                from bot.keyboards.common import get_premium_keyboard
                await callback.message.edit_text(
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
                await callback.answer()
                break
            
            # Show gender preference selection
            await callback.message.edit_text(
                "📞 چت صوتی ناشناس\n\n"
                "مخاطب شما چه جنسیتی باشه؟",
                reply_markup=get_gender_preference_keyboard("voice")
            )
            await callback.answer()
            break
    else:
        # Handle gender selection (same as video)
        await anonymous_video_call(callback)


@router.callback_query(F.data.startswith("anonymous_call:gender:"))
async def handle_gender_selection(callback: CallbackQuery):
    """Handle gender preference selection."""
    # Format: anonymous_call:gender:{call_type}:{gender}
    parts = callback.data.split(":")
    if len(parts) >= 4:
        call_type = parts[2]
        preferred_gender = parts[3]
        
        user_id = callback.from_user.id
        
        async for db_session in get_db():
            from db.crud import get_user_by_telegram_id, check_user_premium
            user = await get_user_by_telegram_id(db_session, user_id)
            if not user:
                await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
                return
            
            # Check premium status
            is_premium = await check_user_premium(db_session, user.id)
            
            if not is_premium:
                from bot.keyboards.common import get_premium_keyboard
                call_type_text = "تصویری" if call_type == "video" else "صوتی"
                await callback.message.edit_text(
                    f"❌ شما عضویت ویژه ندارید.\n\n"
                    f"💎 اشتراک پریمیوم\n\n"
                    f"برای استفاده از چت {call_type_text} ناشناس نیاز به پریمیوم دارید.\n\n"
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
                await callback.answer()
                return
            
            # Add to queue
            await add_to_anonymous_queue(
                user.id,
                call_type,
                preferred_gender,
                user.gender
            )
            
            await callback.message.edit_text(
                "🔍 در حال جستجوی مخاطب...\n\n"
                "لطفاً صبر کنید...",
                reply_markup=get_searching_keyboard(call_type)
            )
            
            # Try to find match multiple times
            max_attempts = 10
            partner_id = None
            
            for attempt in range(max_attempts):
                await asyncio.sleep(2)  # Wait a bit for other users to join
                partner_id, _ = await find_match(user.id, call_type, preferred_gender, user.gender)
                
                if partner_id:
                    break
                
                # Update message to show still searching
                if attempt < max_attempts - 1:
                    await callback.message.edit_text(
                        f"🔍 در حال جستجوی مخاطب...\n\n"
                        f"لطفاً صبر کنید... (تلاش {attempt + 1}/{max_attempts})",
                        reply_markup=get_searching_keyboard(call_type)
                    )
            
            if partner_id:
                # Match found!
                await remove_from_anonymous_queue(user.id, call_type, preferred_gender)
                await remove_from_anonymous_queue(partner_id, call_type, preferred_gender)
                
                # Create call room
                call_data = await create_anonymous_call_room(user.id, partner_id, call_type)
                
                call_type_text = "تصویری" if call_type == "video" else "صوتی"
                await callback.message.edit_text(
                    f"✅ مخاطبت رو پیدا کردم!\n\n"
                    f"📹 چت {call_type_text} ناشناس\n\n"
                    f"با کلیک روی لینک زیر وارد چت شو:",
                    reply_markup=get_match_found_keyboard(
                        call_type,
                        partner_id,
                        call_data["room_id"],
                        call_data["link"]
                    )
                )
                
                # Notify partner (if they're still in queue)
                try:
                    from db.crud import get_user_by_id
                    partner_user = await get_user_by_id(db_session, partner_id)
                    if partner_user:
                        from aiogram import Bot
                        from config.settings import settings
                        bot = Bot(token=settings.BOT_TOKEN)
                        partner_call_data = await create_anonymous_call_room(partner_id, user.id, call_type)
                        await bot.send_message(
                            partner_user.telegram_id,
                            f"✅ مخاطبت رو پیدا کردم!\n\n"
                            f"📹 چت {call_type_text} ناشناس\n\n"
                            f"با کلیک روی لینک زیر وارد چت شو:",
                            reply_markup=get_match_found_keyboard(
                                call_type,
                                user.id,
                                partner_call_data["room_id"],
                                partner_call_data["link"]
                            )
                        )
                        await bot.session.close()
                except Exception as e:
                    print(f"Error notifying partner: {e}")
            else:
                # No match found
                await callback.message.edit_text(
                    "❌ متأسفانه مخاطبی پیدا نشد!\n\n"
                    "می‌توانی دوباره تلاش کنی یا بعداً برگردی.",
                    reply_markup=get_main_menu_keyboard()
                )
            
            await callback.answer()
            break


@router.callback_query(F.data.startswith("anonymous_call:profile:"))
async def view_partner_profile(callback: CallbackQuery):
    """View partner profile from anonymous call."""
    partner_id = int(callback.data.split(":")[-1])
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        partner = await get_user_by_id(db_session, partner_id)
        
        if not user or not partner:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Get like, follow, block status
        is_liked_status = await is_liked(db_session, user.id, partner.id)
        is_following_status = await is_following(db_session, user.id, partner.id)
        is_blocked_status = await is_blocked(db_session, user.id, partner.id)
        
        # Display profile
        gender_map = {"male": "پسر 🧑", "female": "دختر 👩", "other": "سایر"}
        gender_text = gender_map.get(partner.gender, partner.gender or "تعیین نشده")
        
        profile_text = (
            f"👤 پروفایل کاربر\n\n"
            f"• نام: {get_display_name(partner) or 'تعیین نشده'}\n"
            f"• جنسیت: {gender_text}\n"
            f"• استان: {partner.province or 'تعیین نشده'}\n"
            f"• شهر: {partner.city or 'تعیین نشده'}\n"
            f"• سن: {partner.age or 'تعیین نشده'}\n"
            f"• لایک‌ها: {partner.like_count or 0}\n"
        )
        
        # Get profile keyboard
        profile_keyboard = get_profile_keyboard(
            partner_id=partner.id,
            is_liked=is_liked_status,
            is_following=is_following_status,
            is_blocked=is_blocked_status,
            like_count=partner.like_count or 0,
            is_notifying=False
        )
        
        # Send new message instead of editing/deleting previous one
        # This preserves access to the call link in the previous message
        try:
            if partner.profile_image_url:
                await callback.bot.send_photo(
                    user_id,
                    partner.profile_image_url,
                    caption=profile_text,
                    reply_markup=profile_keyboard
                )
            else:
                await callback.message.answer(
                    profile_text,
                    reply_markup=profile_keyboard
                )
        except Exception:
            await callback.message.answer(
                profile_text,
                reply_markup=profile_keyboard
            )
        
        await callback.answer()
        break


@router.callback_query(F.data.startswith("anonymous_call:next:"))
async def find_next_match(callback: CallbackQuery):
    """Find next match for anonymous call."""
    call_type = callback.data.split(":")[-1]
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Get user's previous preference
        user_data_key = f"{anonymous_call_user_data_prefix}:{user.id}"
        if redis_client:
            user_data_str = await redis_client.get(user_data_key)
            if user_data_str:
                user_data = json.loads(user_data_str)
                preferred_gender = user_data.get("preferred_gender", "all")
            else:
                preferred_gender = "all"
        else:
            preferred_gender = "all"
        
        # Add to queue again
        await add_to_anonymous_queue(
            user.id,
            call_type,
            preferred_gender,
            user.gender
        )
        
        await callback.message.edit_text(
            "🔍 در حال جستجوی مخاطب بعدی...\n\n"
            "لطفاً صبر کنید...",
            reply_markup=get_searching_keyboard(call_type)
        )
        
        # Try to find match multiple times
        max_attempts = 10
        partner_id = None
        
        for attempt in range(max_attempts):
            await asyncio.sleep(2)
            partner_id, _ = await find_match(user.id, call_type, preferred_gender, user.gender)
            
            if partner_id:
                break
            
            # Update message to show still searching
            if attempt < max_attempts - 1:
                await callback.message.edit_text(
                    f"🔍 در حال جستجوی مخاطب بعدی...\n\n"
                    f"لطفاً صبر کنید... (تلاش {attempt + 1}/{max_attempts})",
                    reply_markup=get_searching_keyboard(call_type)
                )
        
        if partner_id:
            # Match found!
            await remove_from_anonymous_queue(user.id, call_type, preferred_gender)
            await remove_from_anonymous_queue(partner_id, call_type, preferred_gender)
            
            # Create call room
            call_data = await create_anonymous_call_room(user.id, partner_id, call_type)
            
            call_type_text = "تصویری" if call_type == "video" else "صوتی"
            await callback.message.edit_text(
                f"✅ مخاطب بعدی رو پیدا کردم!\n\n"
                f"📹 چت {call_type_text} ناشناس\n\n"
                f"با کلیک روی لینک زیر وارد چت شو:",
                reply_markup=get_match_found_keyboard(
                    call_type,
                    partner_id,
                    call_data["room_id"],
                    call_data["link"]
                )
            )
            
            # Notify partner
            try:
                from db.crud import get_user_by_id
                partner_user = await get_user_by_id(db_session, partner_id)
                if partner_user:
                    from aiogram import Bot
                    from config.settings import settings
                    bot = Bot(token=settings.BOT_TOKEN)
                    partner_call_data = await create_anonymous_call_room(partner_id, user.id, call_type)
                    await bot.send_message(
                        partner_user.telegram_id,
                        f"✅ مخاطبت رو پیدا کردم!\n\n"
                        f"📹 چت {call_type_text} ناشناس\n\n"
                        f"با کلیک روی لینک زیر وارد چت شو:",
                        reply_markup=get_match_found_keyboard(
                            call_type,
                            user.id,
                            partner_call_data["room_id"],
                            partner_call_data["link"]
                        )
                    )
                    await bot.session.close()
            except Exception as e:
                print(f"Error notifying partner: {e}")
        else:
            # No match found
            await callback.message.edit_text(
                "❌ متأسفانه مخاطبی پیدا نشد!\n\n"
                "می‌توانی دوباره تلاش کنی یا بعداً برگردی.",
                reply_markup=get_main_menu_keyboard()
            )
        
        await callback.answer()
        break


@router.callback_query(F.data == "anonymous_call:cancel")
async def cancel_anonymous_call(callback: CallbackQuery):
    """Cancel anonymous call search."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        # Remove from queue
        await remove_from_anonymous_queue(user.id)
        
        await callback.message.edit_text(
            "❌ جستجو لغو شد.",
            reply_markup=get_main_menu_keyboard()
        )
        await callback.answer()
        break

