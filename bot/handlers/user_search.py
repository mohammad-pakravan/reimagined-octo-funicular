"""
User search handlers for the bot.
Handles user search by city, province, and gender using inline queries.
"""
from aiogram import Router, F, Bot
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent
from config.settings import settings

from db.database import get_db
from db.crud import get_user_by_telegram_id, search_users, is_blocked
from utils.validators import get_display_name

router = Router()


@router.inline_query(F.query.startswith("search:"))
async def handle_user_search(inline_query: InlineQuery):
    """Handle inline query for user search."""
    user_id = inline_query.from_user.id
    query = inline_query.query
    
    # Parse search query: search:type:value
    # Examples: search:city:تهران, search:province:تهران, search:gender:female
    parts = query.split(":", 2)
    if len(parts) < 3:
        await inline_query.answer(results=[], cache_time=1)
        return
    
    search_type = parts[1]  # city, province, or gender
    search_value = parts[2] if len(parts) > 2 else ""
    
    # Get offset from inline_query.offset (Telegram's built-in pagination)
    offset = 0
    if inline_query.offset:
        try:
            offset = int(inline_query.offset)
        except (ValueError, TypeError):
            offset = 0
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await inline_query.answer(results=[], cache_time=1)
            return
        
        # Determine search parameters
        city = None
        province = None
        gender = None
        
        if search_type == "city":
            city = search_value
        elif search_type == "province":
            province = search_value
        elif search_type == "gender":
            gender = search_value
        
        
        # Search users
        users = await search_users(
            db_session,
            city=city,
            province=province,
            gender=gender,
            exclude_user_id=user.id,
            limit=50,
            offset=offset
        )
        
        if not users:
            await inline_query.answer(
                results=[],
                cache_time=1,
                is_personal=True
            )
            return
        
        # Build results
        results = []
        bot = Bot(token=settings.BOT_TOKEN)
        
        for found_user in users:
            # Skip if user has blocked this user or vice versa
            if await is_blocked(db_session, user.id, found_user.id) or \
               await is_blocked(db_session, found_user.id, user.id):
                continue
            
            # Generate profile_id if not exists
            if not found_user.profile_id:
                import hashlib
                profile_id = hashlib.md5(f"user_{found_user.telegram_id}".encode()).hexdigest()[:12]
                found_user.profile_id = profile_id
                await db_session.commit()
                await db_session.refresh(found_user)
            
            display_name_text = get_display_name(found_user)
            user_unique_id = f"/user_{found_user.profile_id}"
            
            # Get profile image for thumbnail
            profile_image_url = getattr(found_user, 'profile_image_url', None)
            
            # Get thumbnail URL
            from utils.minio_storage import get_telegram_thumbnail_url
            thumbnail_url = get_telegram_thumbnail_url(profile_image_url) if profile_image_url else None
            
            # If it's a file_id and thumbnail_url is None, try to get Telegram file URL
            if not thumbnail_url and profile_image_url and not profile_image_url.startswith(('http://', 'https://')):
                try:
                    file = await bot.get_file(profile_image_url)
                    thumbnail_url = f"https://api.telegram.org/file/bot{settings.BOT_TOKEN}/{file.file_path}"
                except Exception:
                    thumbnail_url = None
            
            # Build description
            gender_map = {"male": "👨 پسر", "female": "👩 دختر", "other": "سایر"}
            gender_text = gender_map.get(found_user.gender, found_user.gender or "نامشخص")
            description_parts = [gender_text]
            
            if found_user.age:
                description_parts.append(f"{found_user.age} سال")
            if found_user.city:
                description_parts.append(found_user.city)
            if found_user.province:
                description_parts.append(found_user.province)
            
            description = " • ".join(description_parts)
            
            results.append(
                InlineQueryResultArticle(
                    id=f"{found_user.id}_{offset}",
                    title=f"👤 {display_name_text[:30]}",
                    description=description[:50],
                    thumbnail_url=thumbnail_url,
                    input_message_content=InputTextMessageContent(
                        message_text=user_unique_id
                    )
                )
            )
        
        await bot.session.close()
        
        # Note: Telegram inline queries support pagination automatically
        # If we return exactly 50 results, Telegram will show a "Next" button
        # The next_offset will be passed in the next query automatically
        # So we don't need to add a "load more" result manually
        
        # Calculate next_offset for pagination
        next_offset = None
        if len(users) == 50:
            next_offset = str(offset + 50)
        
        await inline_query.answer(
            results=results,
            cache_time=1,
            is_personal=True,
            next_offset=next_offset
        )
        break

