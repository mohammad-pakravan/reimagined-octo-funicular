"""
CRUD operations for database models.
Provides functions to interact with User, ChatRoom, PremiumSubscription, and Report models.
"""
from datetime import datetime, timedelta, date
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func
from sqlalchemy.orm import joinedload

from db.models import (
    User, ChatRoom, PremiumSubscription, Report, Like, Follow, Block, DirectMessage, ChatEndNotification,                                                       
    UserPoints, PointsHistory, DailyReward, UserReferralCode, Referral, Badge, UserBadge,                                                                       
    Achievement, UserAchievement, WeeklyChallenge, UserChallenge,
    AdminReferralLink, AdminReferralLinkClick, AdminReferralLinkSignup, CoinSetting,                                                                            
    BroadcastMessage, BroadcastMessageReceipt, CoinPackage, PaymentTransaction,
    Event, EventParticipant, EventReward, PremiumPlan, CoinRewardSetting, MandatoryChannel,
    UserPlaylist, PlaylistItem                                                                      
)
from config.settings import settings


# ============= User CRUD =============

async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int, include_inactive: bool = False) -> Optional[User]:
    """
    Get user by Telegram ID.
    
    Args:
        session: Database session
        telegram_id: Telegram user ID
        include_inactive: If True, include inactive (deleted) users. Default is False.
    
    Returns:
        User object or None
    """
    query = select(User).where(User.telegram_id == telegram_id)
    if not include_inactive:
        query = query.where(User.is_active == True)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def search_users(
    session: AsyncSession,
    city: Optional[str] = None,
    province: Optional[str] = None,
    gender: Optional[str] = None,
    online_only: bool = False,
    exclude_user_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    activity_tracker=None
) -> List[User]:
    """
    Search users by filters.
    
    Args:
        session: Database session
        city: Filter by city
        province: Filter by province
        gender: Filter by gender ('male', 'female', 'other')
        online_only: If True, only return online users
        exclude_user_id: User ID to exclude from results
        limit: Maximum number of results
        offset: Number of results to skip
        activity_tracker: Optional UserActivityTracker instance for checking online status
        
    Returns:
        List of User objects
    """
    query = select(User).where(
        User.is_active == True,
        User.is_banned == False,
        User.is_virtual == False  # Exclude virtual profiles from search results
    )
    
    if city:
        query = query.where(User.city == city)
    
    if province:
        query = query.where(User.province == province)
    
    if gender:
        query = query.where(User.gender == gender)
    
    if exclude_user_id:
        query = query.where(User.id != exclude_user_id)
    
    # Only return users with complete profile (gender, age, city)
    query = query.where(
        User.gender.isnot(None),
        User.age.isnot(None),
        User.city.isnot(None)
    )
    
    # If online_only, we need to filter after getting results from DB
    # because online status is in Redis, not DB
    if online_only:
        if not activity_tracker:
            # If activity_tracker is not available, return empty list
            return []
        
        # For online search, fetch ALL matching users for consistent pagination
        # We need to fetch ALL users, filter online ones, sort, then apply offset/limit
        # This ensures consistent results across multiple pagination requests
        result = await session.execute(query)
        all_users = list(result.scalars().all())
            
        # Filter online users and prepare for sorting
        online_candidates = []
        for user in all_users:
            if await activity_tracker.is_online(user.telegram_id):
                last_seen = user.last_seen
                created_at = user.created_at
                online_candidates.append((user, last_seen, created_at))
        
        # Sort online users:
        # 1. last_seen DESC (newest visit first)
        # 2. created_at DESC (newest user first)
        online_candidates.sort(
            key=lambda x: (
                -(x[1].timestamp() if x[1] else 0),   # last_seen DESC
                -(x[2].timestamp() if x[2] else 0)    # created_at DESC
            )
        )
        
        # Apply offset and limit after sorting
        sorted_online = [u[0] for u in online_candidates]
        return sorted_online[offset:offset + limit]
    else:
        # Normal search - fetch ALL matching users for consistent pagination
        # We need to fetch ALL users, sort them once, then apply offset/limit
        # This ensures consistent results across multiple pagination requests
        result = await session.execute(query)
        all_users = list(result.scalars().all())

        # Prepare for sorting
        processed = []
        for u in all_users:
            last_seen = u.last_seen
            created_at = u.created_at
            processed.append((u, last_seen, created_at))

        # Sort priority:
        # 1. last_seen DESC (newest visit first) - users with recent activity first
        # 2. created_at DESC (newest user first) - if last_seen is same or None, newest users first
        processed.sort(
            key=lambda x: (
                -(x[1].timestamp() if x[1] else 0),   # last_seen DESC (newest first)
                -(x[2].timestamp() if x[2] else 0)    # created_at DESC (newest first)
            )
        )

        # Apply offset and limit after sorting
        sorted_users = [u[0] for u in processed]
        return sorted_users[offset:offset + limit]


async def get_user_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
    """Get user by internal ID."""
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_profile_id(session: AsyncSession, profile_id: str) -> Optional[User]:
    """Get user by profile ID (public ID like /user_15e1576abc70)."""
    result = await session.execute(select(User).where(User.profile_id == profile_id))
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    telegram_id: int,
    username: Optional[str] = None,
    display_name: Optional[str] = None,
    gender: Optional[str] = None,
    age: Optional[int] = None,
    province: Optional[str] = None,
    city: Optional[str] = None,
    profile_image_url: Optional[str] = None,
    is_virtual: bool = False,
) -> User:
    """Create a new user."""
    import hashlib
    # Generate unique profile_id
    profile_id = hashlib.md5(f"user_{telegram_id}".encode()).hexdigest()[:12]
    
    user = User(
        telegram_id=telegram_id,
        username=username,
        display_name=display_name,
        gender=gender,
        age=age,
        province=province,
        city=city,
        profile_image_url=profile_image_url,
        profile_id=profile_id,
        is_virtual=is_virtual,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_or_create_virtual_profile_from_pool(
    session: AsyncSession,
    user_age: Optional[int] = None,
    user_city: Optional[str] = None,
    user_province: Optional[str] = None,
    activity_tracker=None,
    exclude_profile_ids: Optional[list[int]] = None,
) -> User:
    """
    Get a virtual profile from the pool, or create new ones if pool is empty.
    Maintains a pool of virtual profiles to avoid creating new ones each time.
    """
    from sqlalchemy import select
    from config.settings import settings
    import random
    
    # Try to get an available virtual profile from pool
    # Look for virtual profiles that are not currently in an active chat
    query = select(User).where(
        User.is_virtual == True,
        User.is_active == True,
        User.gender == "female",
    )
    
    # Filter by age if provided
    if user_age and 18 <= user_age <= 35:
        min_age = max(18, user_age - 3)
        max_age = min(35, user_age + 3)
        query = query.where(User.age >= min_age, User.age <= max_age)
    
    # Filter by city/province if provided
    if user_city:
        query = query.where(User.city == user_city)
    if user_province:
        query = query.where(User.province == user_province)
    
    result = await session.execute(query)
    all_profiles = list(result.scalars().all())
    
    # Filter out excluded profiles (recently used)
    if exclude_profile_ids:
        available_profiles = [p for p in all_profiles if p.id not in exclude_profile_ids]
    else:
        available_profiles = all_profiles
    
    # If no profiles available after filtering, use all profiles (fallback)
    if not available_profiles:
        available_profiles = all_profiles
    
    if available_profiles:
        # Filter out profiles that are currently in active chats
        # We'll do a simple check: if there are many profiles, prefer ones not recently used
        # For now, just select randomly but try to avoid the same profile if possible
        
        # If we have multiple profiles, shuffle and try to get a different one
        if len(available_profiles) > 1:
            # Shuffle to ensure randomness
            random.shuffle(available_profiles)
            
            # Prefer profiles with unique names (not duplicate names)
            # This helps avoid obvious patterns
            unique_name_profiles = []
            name_counts = {}
            for profile in available_profiles:
                name = profile.display_name or ""
                name_counts[name] = name_counts.get(name, 0) + 1
            
            # Prioritize profiles with unique names
            for profile in available_profiles:
                name = profile.display_name or ""
                if name_counts.get(name, 0) == 1:
                    unique_name_profiles.append(profile)
            
            # If we have unique name profiles, prefer them
            if unique_name_profiles:
                selected_profile = random.choice(unique_name_profiles[:min(5, len(unique_name_profiles))])
            else:
                # Otherwise, just pick randomly
                selected_profile = random.choice(available_profiles[:min(5, len(available_profiles))])
        else:
            selected_profile = available_profiles[0]
        
        # Update last_seen to make it appear online
        selected_profile.last_seen = datetime.utcnow()
        await session.commit()
        await session.refresh(selected_profile)
        
        # Set online status in Redis
        if activity_tracker:
            try:
                await activity_tracker.update_activity(selected_profile.telegram_id, db_session=None)
            except Exception:
                pass
        
        return selected_profile
    
    # No available profile in pool, check pool size and create new ones if needed
    pool_size_query = select(func.count(User.id)).where(
        User.is_virtual == True,
        User.is_active == True,
        User.gender == "female",
    )
    pool_size_result = await session.execute(pool_size_query)
    current_pool_size = pool_size_result.scalar() or 0
    
    # If pool is smaller than desired size, create new profiles
    if current_pool_size < settings.VIRTUAL_PROFILE_POOL_SIZE:
        # Create multiple profiles to fill the pool
        profiles_to_create = settings.VIRTUAL_PROFILE_POOL_SIZE - current_pool_size
        for _ in range(profiles_to_create):
            await create_virtual_female_profile(
                session,
                user_age=user_age,
                user_city=user_city,
                user_province=user_province,
                activity_tracker=activity_tracker,
            )
        
        # Now get one from the pool
        result = await session.execute(query)
        available_profiles = list(result.scalars().all())
        if available_profiles:
            selected_profile = random.choice(available_profiles)
            selected_profile.last_seen = datetime.utcnow()
            await session.commit()
            await session.refresh(selected_profile)
            
            if activity_tracker:
                try:
                    await activity_tracker.update_activity(selected_profile.telegram_id, db_session=None)
                except Exception:
                    pass
            
            return selected_profile
    
    # If still no profile available, create one on the fly
    return await create_virtual_female_profile(
        session,
        user_age=user_age,
        user_city=user_city,
        user_province=user_province,
        activity_tracker=activity_tracker,
    )


async def create_virtual_female_profile(
    session: AsyncSession,
    user_age: Optional[int] = None,
    user_city: Optional[str] = None,
    user_province: Optional[str] = None,
    activity_tracker=None,
) -> User:
    """
    Create a virtual female profile for engagement using data from real users.
    Used when a boy is searching for a girl but no match is found after timeout.
    Combines data from different real female users to create a realistic virtual profile.
    """
    import hashlib
    import random
    import time
    from sqlalchemy import select, func
    
    # Generate unique telegram_id for virtual profile (negative number to avoid conflicts)
    virtual_telegram_id = -int(time.time() * 1000) - random.randint(1000, 9999)
    
    # Generate unique profile_id
    profile_id = hashlib.md5(f"virtual_{virtual_telegram_id}".encode()).hexdigest()[:12]
    
    # Get real female users from database (exclude virtual profiles)
    query = select(User).where(
        User.gender == "female",
        User.is_active == True,
        User.is_banned == False,
        User.is_virtual == False,  # Only real users
        User.display_name.isnot(None),  # Must have display name
    )
    
    # Filter by age range if user_age provided
    if user_age and 18 <= user_age <= 35:
        min_age = max(18, user_age - 3)
        max_age = min(35, user_age + 3)
        query = query.where(User.age >= min_age, User.age <= max_age)
    else:
        # Default age range
        query = query.where(User.age >= 18, User.age <= 35)
    
    # Filter by city/province if provided
    if user_city:
        query = query.where(User.city == user_city)
    if user_province:
        query = query.where(User.province == user_province)
    
    # Get at least 10-20 real users to mix data from
    query = query.limit(50)
    result = await session.execute(query)
    real_users = list(result.scalars().all())
    
    if not real_users:
        # Fallback: if no real users found, use default values
        virtual_age = random.randint(18, 28) if not user_age else user_age
        virtual_city = user_city or "تهران"
        virtual_province = user_province or "تهران"
        virtual_display_name = "کاربر"
        virtual_profile_image = None
        virtual_like_count = 0
    else:
        # Mix data from different real users
        # Ensure each virtual profile has unique combination of attributes
        
        # 1. Display name from one user - check for uniqueness
        max_name_attempts = 50
        virtual_display_name = None
        used_names = set()
        
        # Get virtual profile names created in last 3 hours to avoid duplicates
        from datetime import timedelta
        import logging
        logger = logging.getLogger(__name__)
        
        three_hours_ago = datetime.utcnow() - timedelta(hours=3)
        existing_names_query = select(User.display_name).where(
            User.is_virtual == True,
            User.display_name.isnot(None),
            User.created_at >= three_hours_ago  # Only check profiles from last 3 hours
        )
        existing_names_result = await session.execute(existing_names_query)
        existing_names = {name for name in existing_names_result.scalars().all() if name}
        logger.info(f"Creating virtual profile: {len(existing_names)} unique names used in last 3 hours")
        
        for attempt in range(max_name_attempts):
            name_user = random.choice(real_users)
            candidate_name = name_user.display_name or "کاربر"
            
            # Check if this name is already used by another virtual profile
            if candidate_name not in existing_names and candidate_name not in used_names:
                virtual_display_name = candidate_name
                break
            
            used_names.add(candidate_name)
        
        # If all names are taken, add a unique suffix based on timestamp
        if not virtual_display_name:
            base_name = random.choice(real_users).display_name or "کاربر"
            # Use timestamp + random to ensure uniqueness
            import time
            unique_suffix = int(time.time() * 1000) % 10000  # Last 4 digits of timestamp
            virtual_display_name = f"{base_name}{unique_suffix}"
            
            # Double check this name is unique (in last 3 hours)
            final_check = select(func.count(User.id)).where(
                User.is_virtual == True,
                User.display_name == virtual_display_name,
                User.created_at >= three_hours_ago
            )
            final_result = await session.execute(final_check)
            final_count = final_result.scalar() or 0
            
            # If still duplicate (in last 3 hours), add more randomness
            if final_count > 0:
                extra_random = random.randint(1000, 9999)
                virtual_display_name = f"{base_name}{unique_suffix}{extra_random}"
        
        # 2. Age from another user (or calculate based on user_age)
        if user_age and 18 <= user_age <= 35:
            # Find users with similar age
            age_candidates = [u for u in real_users if u.age and abs(u.age - user_age) <= 3]
            if age_candidates:
                age_user = random.choice(age_candidates)
                virtual_age = age_user.age
            else:
                min_age = max(18, user_age - 3)
                max_age = min(35, user_age + 3)
                virtual_age = random.randint(min_age, max_age)
        else:
            age_user = random.choice(real_users)
            virtual_age = age_user.age or random.randint(18, 28)
        
        # 3. City and province from another user (or use provided)
        # Check for unique city/province combination in last 3 hours
        if user_city and user_province:
            virtual_city = user_city
            virtual_province = user_province
        else:
            # Get existing city/province combinations from last 3 hours
            existing_locations_query = select(User.city, User.province).where(
                User.is_virtual == True,
                User.created_at >= three_hours_ago,
                User.city.isnot(None),
                User.province.isnot(None)
            )
            existing_locations_result = await session.execute(existing_locations_query)
            existing_locations = {(city, province) for city, province in existing_locations_result.all() if city and province}
            logger.info(f"Creating virtual profile: {len(existing_locations)} unique city/province combinations used in last 3 hours")
            
            # Try to find unique location
            max_location_attempts = 30
            virtual_city = None
            virtual_province = None
            for _ in range(max_location_attempts):
                location_user = random.choice(real_users)
                candidate_city = location_user.city or user_city or "تهران"
                candidate_province = location_user.province or user_province or "تهران"
                
                if (candidate_city, candidate_province) not in existing_locations:
                    virtual_city = candidate_city
                    virtual_province = candidate_province
                    break
            
            # If no unique location found, use a random one
            if not virtual_city or not virtual_province:
                location_user = random.choice(real_users)
                virtual_city = location_user.city or user_city or "تهران"
                virtual_province = location_user.province or user_province or "تهران"
        
        # 4. Profile image from another user (prefer users with images)
        # Try to get a unique image
        image_users = [u for u in real_users if u.profile_image_url]
        virtual_profile_image = None
        if image_users:
            # Get virtual profile images created in last 3 hours to avoid duplicates
            existing_images_query = select(User.profile_image_url).where(
                User.is_virtual == True,
                User.profile_image_url.isnot(None),
                User.created_at >= three_hours_ago  # Only check profiles from last 3 hours
            )
            existing_images_result = await session.execute(existing_images_query)
            existing_images = {img for img in existing_images_result.scalars().all() if img}
            logger.info(f"Creating virtual profile: {len(existing_images)} unique images used in last 3 hours")
            
            max_image_attempts = 30
            used_images = set()
            for attempt in range(max_image_attempts):
                image_user = random.choice(image_users)
                candidate_image = image_user.profile_image_url
                
                # Check if this image is already used by another virtual profile
                if candidate_image not in existing_images and candidate_image not in used_images:
                    virtual_profile_image = candidate_image
                    break
                
                used_images.add(candidate_image)
            
            # If all images are taken in last 3 hours, use a random one anyway (but log it)
            if not virtual_profile_image:
                image_user = random.choice(image_users)
                virtual_profile_image = image_user.profile_image_url
                logger.warning(f"All images from real users are used in last 3 hours, using duplicate image for virtual profile")
        
        # 5. Like count from another user (randomize a bit)
        like_user = random.choice(real_users)
        base_like_count = like_user.like_count or 0
        # Add some randomness to like count (±20%)
        like_variation = int(base_like_count * 0.2) if base_like_count > 0 else 5
        virtual_like_count = max(0, base_like_count + random.randint(-like_variation, like_variation))
    
    # Create virtual user with mixed data from real users
    user = User(
        telegram_id=virtual_telegram_id,
        username=None,
        display_name=virtual_display_name,
        gender="female",
        age=virtual_age,
        province=virtual_province,
        city=virtual_city,
        profile_image_url=virtual_profile_image,
        like_count=virtual_like_count,
        profile_id=profile_id,
        is_virtual=True,
        is_active=True,
        is_banned=False,
        last_seen=datetime.utcnow(),  # Set as online
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    
    # Log created virtual profile details
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"✅ Created virtual profile ID={user.id}: name='{virtual_display_name}', age={virtual_age}, city='{virtual_city}', province='{virtual_province}', has_image={virtual_profile_image is not None}")
    
    # Set online status in Redis (for virtual profile only, not real users)
    if activity_tracker:
        try:
            await activity_tracker.update_activity(virtual_telegram_id, db_session=None)
        except Exception as e:
            logger.warning(f"Failed to set online status for virtual profile {virtual_telegram_id}: {e}")
    
    return user


async def update_user_profile(
    session: AsyncSession,
    telegram_id: int,
    username: Optional[str] = None,
    display_name: Optional[str] = None,
    gender: Optional[str] = None,
    age: Optional[int] = None,
    province: Optional[str] = None,
    city: Optional[str] = None,
    profile_image_url: Optional[str] = None,
) -> Optional[User]:
    """Update user profile information."""
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        return None
    
    # Generate profile_id if not exists
    if not user.profile_id:
        import hashlib
        profile_id = hashlib.md5(f"user_{telegram_id}".encode()).hexdigest()[:12]
        user.profile_id = profile_id
    
    if username is not None:
        user.username = username
    if display_name is not None:
        user.display_name = display_name
    if gender is not None:
        user.gender = gender
    if age is not None:
        user.age = age
    if province is not None:
        user.province = province
    if city is not None:
        user.city = city
    if profile_image_url is not None:
        user.profile_image_url = profile_image_url
    
    user.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(user)
    return user


async def ban_user(session: AsyncSession, user_id: int) -> bool:
    """Ban a user."""
    result = await session.execute(
        update(User).where(User.id == user_id).values(is_banned=True)
    )
    await session.commit()
    return result.rowcount > 0


async def delete_user_account(session: AsyncSession, user_id: int) -> bool:
    """
    Delete user account (soft delete by setting is_active=False).
    
    Args:
        session: Database session
        user_id: User database ID
        
    Returns:
        bool: True if account was deleted, False otherwise
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Get user first to verify it exists
    user = await session.get(User, user_id)
    if not user:
        logger.warning(f"User {user_id} not found for deletion")
        return False
    
    logger.info(f"Deleting account for user {user_id} (telegram_id: {user.telegram_id}), current is_active: {user.is_active}, is_banned: {user.is_banned}")
    
    # Use direct UPDATE statement to ensure the change is applied
    result = await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(
            is_active=False,
            is_banned=True,
            updated_at=datetime.utcnow()
        )
    )
    
    logger.info(f"UPDATE statement executed for user {user_id}, rows affected: {result.rowcount}")
    
    # Commit the transaction
    await session.commit()
    logger.info(f"Committed changes for user {user_id}")
    
    # Verify the update was successful by querying database directly
    # This ensures we get the actual state from database, not from session cache
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    updated_user = result.scalar_one_or_none()
    
    if updated_user:
        logger.info(f"Verified user {user_id} from database, is_active: {updated_user.is_active}, is_banned: {updated_user.is_banned}")
        if not updated_user.is_active:
            return True
        else:
            logger.error(f"User {user_id} deletion failed: is_active is still True after commit!")
            return False
    else:
        logger.error(f"User {user_id} not found in database after deletion attempt!")
        return False


async def unban_user(session: AsyncSession, user_id: int) -> bool:
    """Unban a user."""
    result = await session.execute(
        update(User).where(User.id == user_id).values(is_banned=False)
    )
    await session.commit()
    return result.rowcount > 0


async def get_all_users(session: AsyncSession, skip: int = 0, limit: int = None) -> List[User]:
    """Get all users with pagination. If limit is None, returns all users."""
    query = select(User).offset(skip)
    if limit is not None:
        query = query.limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_user_count(session: AsyncSession) -> int:
    """Get total user count."""
    result = await session.execute(select(func.count(User.id)))
    return result.scalar() or 0


# ============= ChatRoom CRUD =============

async def create_chat_room(session: AsyncSession, user1_id: int, user2_id: int) -> ChatRoom:
    """Create a new chat room."""
    chat_room = ChatRoom(user1_id=user1_id, user2_id=user2_id)
    session.add(chat_room)
    await session.commit()
    await session.refresh(chat_room)
    return chat_room


async def get_active_chat_room_by_user(session: AsyncSession, user_id: int) -> Optional[ChatRoom]:
    """Get active chat room for a user."""
    result = await session.execute(
        select(ChatRoom).where(
            and_(
                ChatRoom.is_active == True,
                or_(ChatRoom.user1_id == user_id, ChatRoom.user2_id == user_id)
            )
        ).order_by(ChatRoom.created_at.desc())
    )
    # If multiple active chats exist, return the most recent one
    # This can happen if there's a race condition or bug
    chat_rooms = result.scalars().all()
    if len(chat_rooms) > 1:
        # Log warning and deactivate older chats
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"User {user_id} has {len(chat_rooms)} active chats. Deactivating older ones.")
        # Keep the first (most recent), deactivate others
        for chat_room in chat_rooms[1:]:
            await end_chat_room(session, chat_room.id)
        await session.commit()
    return chat_rooms[0] if chat_rooms else None


async def get_chat_room_by_id(session: AsyncSession, chat_room_id: int) -> Optional[ChatRoom]:
    """Get chat room by ID."""
    result = await session.execute(
        select(ChatRoom).where(ChatRoom.id == chat_room_id)
    )
    return result.scalar_one_or_none()


async def end_chat_room(session: AsyncSession, chat_room_id: int) -> bool:
    """End a chat room."""
    result = await session.execute(
        update(ChatRoom)
        .where(ChatRoom.id == chat_room_id)
        .values(is_active=False, ended_at=datetime.utcnow())
    )
    await session.commit()
    return result.rowcount > 0


async def update_chat_room_video_call(
    session: AsyncSession,
    chat_room_id: int,
    video_call_room_id: str,
    video_call_link: str,
) -> bool:
    """Update chat room with video call information."""
    result = await session.execute(
        update(ChatRoom)
        .where(ChatRoom.id == chat_room_id)
        .values(video_call_room_id=video_call_room_id, video_call_link=video_call_link)
    )
    await session.commit()
    return result.rowcount > 0


async def get_active_chat_count(session: AsyncSession) -> int:
    """Get count of active chats."""
    result = await session.execute(
        select(func.count(ChatRoom.id)).where(ChatRoom.is_active == True)
    )
    return result.scalar() or 0


async def had_recent_chat(
    session: AsyncSession,
    user1_id: int,
    user2_id: int,
    hours: int = 7,
) -> bool:
    """
    Check if two users have had a chat that ended within the given number of hours.

    This is used to enforce the rule that two users should not be matched again
    within a cooldown window (e.g. 7 hours).
    """
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    result = await session.execute(
        select(ChatRoom)
        .where(
            ChatRoom.is_active == False,
            ChatRoom.ended_at.isnot(None),
            ChatRoom.ended_at >= cutoff,
            or_(
                and_(ChatRoom.user1_id == user1_id, ChatRoom.user2_id == user2_id),
                and_(ChatRoom.user1_id == user2_id, ChatRoom.user2_id == user1_id),
            ),
        )
        .order_by(ChatRoom.ended_at.desc())
        .limit(1)
    )

    last_chat = result.scalar_one_or_none()
    return last_chat is not None


# ============= PremiumSubscription CRUD =============

async def create_premium_subscription(
    session: AsyncSession,
    user_id: int,
    provider: str,
    transaction_id: str,
    amount: float,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> PremiumSubscription:
    """Create a new premium subscription."""
    if start_date is None:
        start_date = datetime.utcnow()
    
    # Get user to check existing premium
    user = await get_user_by_id(session, user_id)
    
    if end_date is None:
        # If end_date not provided, calculate from default duration
        end_date = start_date + timedelta(days=settings.PREMIUM_DURATION_DAYS)
        # Extend existing premium if user has active premium
        if user and user.premium_expires_at and user.premium_expires_at > datetime.utcnow():
            end_date = user.premium_expires_at + (end_date - start_date)
    # If end_date is provided, use it directly (already calculated in handler)
    # No need to recalculate - handler already handled extension logic
    
    subscription = PremiumSubscription(
        user_id=user_id,
        provider=provider,
        transaction_id=transaction_id,
        amount=amount,
        start_date=start_date,
        end_date=end_date,
    )
    session.add(subscription)
    
    # Update user premium status
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(is_premium=True, premium_expires_at=end_date)
    )
    
    await session.commit()
    await session.refresh(subscription)
    return subscription


async def check_user_premium(session: AsyncSession, user_id: int) -> bool:
    """Check if user has active premium subscription."""
    user = await get_user_by_id(session, user_id)
    if not user:
        return False
    
    if user.is_premium and user.premium_expires_at:
        return user.premium_expires_at > datetime.utcnow()
    
    return False


async def get_premium_count(session: AsyncSession) -> int:
    """Get count of premium users."""
    now = datetime.utcnow()
    result = await session.execute(
        select(func.count(User.id)).where(
            and_(User.is_premium == True, User.premium_expires_at > now)
        )
    )
    return result.scalar() or 0


# ============= Report CRUD =============

async def create_report(
    session: AsyncSession,
    reporter_id: int,
    reported_id: int,
    reason: Optional[str] = None,
    report_type: Optional[str] = None,
) -> Report:
    """Create a new report."""
    report = Report(
        reporter_id=reporter_id,
        reported_id=reported_id,
        reason=reason,
        report_type=report_type,
    )
    session.add(report)
    await session.commit()
    await session.refresh(report)
    return report


async def get_unresolved_reports(session: AsyncSession, skip: int = 0, limit: int = 100) -> List[Report]:
    """Get unresolved reports with pagination."""
    result = await session.execute(
        select(Report)
        .where(Report.is_resolved == False)
        .offset(skip)
        .limit(limit)
        .order_by(Report.created_at.desc())
    )
    return list(result.scalars().all())


async def resolve_report(session: AsyncSession, report_id: int, resolved_by: int) -> bool:
    """Mark a report as resolved."""
    result = await session.execute(
        update(Report)
        .where(Report.id == report_id)
        .values(is_resolved=True, resolved_by=resolved_by, resolved_at=datetime.utcnow())
    )
    await session.commit()
    return result.rowcount > 0


# ============= Like CRUD =============

async def like_user(session: AsyncSession, user_id: int, liked_user_id: int) -> Optional[Like]:
    """Like a user."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Check if already liked
        existing = await session.execute(
            select(Like).where(
                and_(Like.user_id == user_id, Like.liked_user_id == liked_user_id)
            )
        )
        if existing.scalar_one_or_none():
            logger.debug(f"User {user_id} already liked user {liked_user_id}")
            return None  # Already liked
        
        like = Like(user_id=user_id, liked_user_id=liked_user_id)
        session.add(like)
        
        # Update like count
        await session.execute(
            update(User)
            .where(User.id == liked_user_id)
            .values(like_count=User.like_count + 1)
        )
        
        await session.commit()
        await session.refresh(like)
        logger.info(f"Successfully liked: User {user_id} -> {liked_user_id}, like_id: {like.id}")
        return like
    except Exception as e:
        logger.error(f"Error in like_user: {e}", exc_info=True)
        await session.rollback()
        raise


async def unlike_user(session: AsyncSession, user_id: int, liked_user_id: int) -> bool:
    """Unlike a user."""
    result = await session.execute(
        select(Like).where(
            and_(Like.user_id == user_id, Like.liked_user_id == liked_user_id)
        )
    )
    like = result.scalar_one_or_none()
    if not like:
        return False
    
    await session.delete(like)
    
    # Update like count
    await session.execute(
        update(User)
        .where(User.id == liked_user_id)
        .values(like_count=func.greatest(User.like_count - 1, 0))
    )
    
    await session.commit()
    return True


async def is_liked(session: AsyncSession, user_id: int, liked_user_id: int) -> bool:
    """Check if user has liked another user."""
    result = await session.execute(
        select(Like).where(
            and_(Like.user_id == user_id, Like.liked_user_id == liked_user_id)
        )
    )
    return result.scalar_one_or_none() is not None


# ============= Follow CRUD =============

async def follow_user(session: AsyncSession, follower_id: int, followed_id: int) -> Optional[Follow]:
    """Follow a user."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Check if already following
        existing = await session.execute(
            select(Follow).where(
                and_(Follow.follower_id == follower_id, Follow.followed_id == followed_id)
            )
        )
        if existing.scalar_one_or_none():
            logger.debug(f"User {follower_id} already following user {followed_id}")
            return None  # Already following
        
        follow = Follow(follower_id=follower_id, followed_id=followed_id)
        session.add(follow)
        await session.commit()
        await session.refresh(follow)
        logger.info(f"Successfully followed: User {follower_id} -> {followed_id}, follow_id: {follow.id}")
        return follow
    except Exception as e:
        logger.error(f"Error in follow_user: {e}", exc_info=True)
        await session.rollback()
        raise


async def unfollow_user(session: AsyncSession, follower_id: int, followed_id: int) -> bool:
    """Unfollow a user."""
    result = await session.execute(
        select(Follow).where(
            and_(Follow.follower_id == follower_id, Follow.followed_id == followed_id)
        )
    )
    follow = result.scalar_one_or_none()
    if not follow:
        return False
    
    await session.delete(follow)
    await session.commit()
    return True


async def is_following(session: AsyncSession, follower_id: int, followed_id: int) -> bool:
    """Check if user is following another user."""
    result = await session.execute(
        select(Follow).where(
            and_(Follow.follower_id == follower_id, Follow.followed_id == followed_id)
        )
    )
    return result.scalar_one_or_none() is not None


# ============= Block CRUD =============

async def block_user(session: AsyncSession, blocker_id: int, blocked_id: int) -> Optional[Block]:
    """Block a user."""
    # Check if already blocked
    existing = await session.execute(
        select(Block).where(
            and_(Block.blocker_id == blocker_id, Block.blocked_id == blocked_id)
        )
    )
    if existing.scalar_one_or_none():
        return None  # Already blocked
    
    block = Block(blocker_id=blocker_id, blocked_id=blocked_id)
    session.add(block)
    await session.commit()
    await session.refresh(block)
    return block


async def unblock_user(session: AsyncSession, blocker_id: int, blocked_id: int) -> bool:
    """Unblock a user."""
    result = await session.execute(
        select(Block).where(
            and_(Block.blocker_id == blocker_id, Block.blocked_id == blocked_id)
        )
    )
    block = result.scalar_one_or_none()
    if not block:
        return False
    
    await session.delete(block)
    await session.commit()
    return True


async def is_blocked(session: AsyncSession, blocker_id: int, blocked_id: int) -> bool:
    """Check if user has blocked another user."""
    result = await session.execute(
        select(Block).where(
            and_(Block.blocker_id == blocker_id, Block.blocked_id == blocked_id)
        )
    )
    return result.scalar_one_or_none() is not None


async def get_following_list(session: AsyncSession, user_id: int) -> List[tuple]:
    """
    Get list of users that a user is following.
    
    Returns:
        List of tuples: (user_id, username, profile_id)
    """
    result = await session.execute(
        select(Follow, User).join(User, Follow.followed_id == User.id)
        .where(Follow.follower_id == user_id)
        .order_by(Follow.created_at.desc())
    )
    
    following_list = []
    for follow, user in result.all():
        following_list.append((user.id, user.username, user.profile_id))
    
    return following_list


async def get_blocked_list(session: AsyncSession, user_id: int) -> List[tuple]:
    """
    Get list of users that a user has blocked.
    
    Returns:
        List of tuples: (user_id, username, profile_id)
    """
    result = await session.execute(
        select(Block, User).join(User, Block.blocked_id == User.id)
        .where(Block.blocker_id == user_id)
        .order_by(Block.created_at.desc())
    )
    
    blocked_list = []
    for block, user in result.all():
        blocked_list.append((user.id, user.username, user.profile_id))
    
    return blocked_list


async def get_liked_list(session: AsyncSession, user_id: int) -> List[tuple]:
    """
    Get list of users that a user has liked.
    
    Returns:
        List of tuples: (user_id, username, profile_id)
    """
    result = await session.execute(
        select(Like, User).join(User, Like.liked_user_id == User.id)
        .where(Like.user_id == user_id)
        .order_by(Like.created_at.desc())
    )
    
    liked_list = []
    for like, user in result.all():
        liked_list.append((user.id, user.username, user.profile_id))
    
    return liked_list


async def update_user_profile_id(session: AsyncSession, user_id: int, profile_id: str) -> bool:
    """Update user profile_id."""
    result = await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(profile_id=profile_id)
    )
    await session.commit()
    return result.rowcount > 0


# ============= Direct Message CRUD =============

async def create_direct_message(
    session: AsyncSession,
    sender_id: int,
    receiver_id: int,
    message_text: str
) -> DirectMessage:
    """Create a new direct message."""
    dm = DirectMessage(
        sender_id=sender_id,
        receiver_id=receiver_id,
        message_text=message_text
    )
    session.add(dm)
    await session.commit()
    await session.refresh(dm)
    return dm


async def get_direct_message_by_id(session: AsyncSession, dm_id: int) -> Optional[DirectMessage]:
    """Get direct message by ID."""
    result = await session.execute(select(DirectMessage).where(DirectMessage.id == dm_id))
    return result.scalar_one_or_none()


async def mark_direct_message_read(session: AsyncSession, dm_id: int) -> bool:
    """Mark a direct message as read."""
    result = await session.execute(
        update(DirectMessage)
        .where(DirectMessage.id == dm_id)
        .values(is_read=True)
    )
    await session.commit()
    return result.rowcount > 0


async def reject_direct_message(session: AsyncSession, dm_id: int) -> bool:
    """Reject a direct message."""
    result = await session.execute(
        update(DirectMessage)
        .where(DirectMessage.id == dm_id)
        .values(is_rejected=True)
    )
    await session.commit()
    return result.rowcount > 0


async def get_direct_messages_received(
    session: AsyncSession,
    receiver_id: int,
    limit: int = 50
) -> List[DirectMessage]:
    """Get direct messages received by a user, sorted by newest first."""
    result = await session.execute(
        select(DirectMessage)
        .where(DirectMessage.receiver_id == receiver_id)
        .where(DirectMessage.is_rejected == False)
        .order_by(DirectMessage.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_direct_messages_sent(
    session: AsyncSession,
    sender_id: int,
    limit: int = 50
) -> List[DirectMessage]:
    """Get direct messages sent by a user, sorted by newest first."""
    result = await session.execute(
        select(DirectMessage)
        .where(DirectMessage.sender_id == sender_id)
        .order_by(DirectMessage.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_direct_message_list(
    session: AsyncSession,
    user_id: int
) -> List[tuple]:
    """
    Get list of unique users who sent messages to this user.
    Returns list of tuples: (sender_id, sender_username, sender_gender, latest_message_created_at)
    Sorted by newest first.
    """
    # Get unique senders with their latest message timestamp
    subquery = (
        select(
            DirectMessage.sender_id,
            func.max(DirectMessage.created_at).label('latest_date')
        )
        .where(DirectMessage.receiver_id == user_id)
        .where(DirectMessage.is_rejected == False)
        .group_by(DirectMessage.sender_id)
        .subquery()
    )
    
    result = await session.execute(
        select(User.id, User.username, User.gender, subquery.c.latest_date)
        .join(subquery, User.id == subquery.c.sender_id)
        .order_by(subquery.c.latest_date.desc())
    )
    
    message_list = []
    for user_id_val, username, gender, latest_date in result.all():
        message_list.append((user_id_val, username, gender, latest_date))
    
    return message_list


async def delete_conversation(
    session: AsyncSession,
    user1_id: int,
    user2_id: int
) -> int:
    """
    Delete all direct messages between two users (both sent and received).
    Returns the number of deleted messages.
    
    Args:
        session: Database session
        user1_id: First user ID
        user2_id: Second user ID
    """
    result = await session.execute(
        delete(DirectMessage)
        .where(
            or_(
                and_(DirectMessage.sender_id == user1_id, DirectMessage.receiver_id == user2_id),
                and_(DirectMessage.sender_id == user2_id, DirectMessage.receiver_id == user1_id)
            )
        )
    )
    await session.commit()
    return result.rowcount


# ============= Chat End Notification CRUD =============

async def create_chat_end_notification(
    session: AsyncSession,
    watcher_id: int,
    target_user_id: int
) -> Optional[ChatEndNotification]:
    """Create a chat end notification request."""
    # Check if notification already exists
    result = await session.execute(
        select(ChatEndNotification)
        .where(ChatEndNotification.watcher_id == watcher_id)
        .where(ChatEndNotification.target_user_id == target_user_id)
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        return existing  # Already exists
    
    notification = ChatEndNotification(
        watcher_id=watcher_id,
        target_user_id=target_user_id
    )
    session.add(notification)
    await session.commit()
    await session.refresh(notification)
    return notification


async def delete_chat_end_notification(
    session: AsyncSession,
    watcher_id: int,
    target_user_id: int
) -> bool:
    """Delete a chat end notification request."""
    result = await session.execute(
        select(ChatEndNotification)
        .where(ChatEndNotification.watcher_id == watcher_id)
        .where(ChatEndNotification.target_user_id == target_user_id)
    )
    notification = result.scalar_one_or_none()
    
    if not notification:
        return False
    
    await session.delete(notification)
    await session.commit()
    return True


async def is_chat_end_notification_active(
    session: AsyncSession,
    watcher_id: int,
    target_user_id: int
) -> bool:
    """Check if chat end notification is active."""
    result = await session.execute(
        select(ChatEndNotification)
        .where(ChatEndNotification.watcher_id == watcher_id)
        .where(ChatEndNotification.target_user_id == target_user_id)
    )
    return result.scalar_one_or_none() is not None


async def get_chat_end_notifications_for_user(
    session: AsyncSession,
    user_id: int
) -> List[ChatEndNotification]:
    """
    Get all chat end notifications for a user (when this user's chat ends, notify watchers).
    Returns list of notifications where target_user_id == user_id.
    """
    result = await session.execute(
        select(ChatEndNotification)
        .where(ChatEndNotification.target_user_id == user_id)
    )
    return list(result.scalars().all())


# ============= Engagement Features CRUD =============

# ============= User Points CRUD =============

async def get_or_create_user_points(session: AsyncSession, user_id: int) -> UserPoints:
    """Get or create user points record."""
    result = await session.execute(
        select(UserPoints).where(UserPoints.user_id == user_id)
    )
    user_points = result.scalar_one_or_none()
    
    if not user_points:
        user_points = UserPoints(user_id=user_id, points=0, total_earned=0, total_spent=0)
        session.add(user_points)
        await session.commit()
        await session.refresh(user_points)
    
    return user_points


async def add_points(
    session: AsyncSession,
    user_id: int,
    points: int,
    transaction_type: str,
    source: str,
    description: Optional[str] = None,
    related_user_id: Optional[int] = None
) -> bool:
    """Add points to user and create history record."""
    user_points = await get_or_create_user_points(session, user_id)
    
    user_points.points += points
    user_points.total_earned += points
    
    # Create history record
    history = PointsHistory(
        user_id=user_id,
        points=points,
        transaction_type=transaction_type,
        source=source,
        description=description,
        related_user_id=related_user_id
    )
    session.add(history)
    
    await session.commit()
    return True


async def spend_points(
    session: AsyncSession,
    user_id: int,
    points: int,
    transaction_type: str,
    source: str,
    description: Optional[str] = None
) -> bool:
    """Spend points from user and create history record."""
    user_points = await get_or_create_user_points(session, user_id)
    
    if user_points.points < points:
        return False  # Insufficient points
    
    user_points.points -= points
    user_points.total_spent += points
    
    # Create history record
    history = PointsHistory(
        user_id=user_id,
        points=-points,
        transaction_type=transaction_type,
        source=source,
        description=description
    )
    session.add(history)
    
    await session.commit()
    return True


async def get_user_points(session: AsyncSession, user_id: int) -> int:
    """Get user's current points balance."""
    user_points = await get_or_create_user_points(session, user_id)
    return user_points.points


async def get_points_history(
    session: AsyncSession,
    user_id: int,
    limit: int = 50
) -> List[PointsHistory]:
    """Get user's points history."""
    result = await session.execute(
        select(PointsHistory)
        .where(PointsHistory.user_id == user_id)
        .order_by(PointsHistory.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# ============= Daily Rewards CRUD =============

async def get_daily_reward(
    session: AsyncSession,
    user_id: int,
    reward_date: datetime.date
) -> Optional[DailyReward]:
    """Get daily reward for user on specific date."""
    result = await session.execute(
        select(DailyReward)
        .where(DailyReward.user_id == user_id)
        .where(DailyReward.reward_date == reward_date)
    )
    return result.scalar_one_or_none()


async def get_last_daily_reward(session: AsyncSession, user_id: int) -> Optional[DailyReward]:
    """Get user's last daily reward."""
    result = await session.execute(
        select(DailyReward)
        .where(DailyReward.user_id == user_id)
        .order_by(DailyReward.reward_date.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def create_daily_reward(
    session: AsyncSession,
    user_id: int,
    reward_date: datetime.date,
    points_rewarded: int,
    streak_count: int
) -> DailyReward:
    """Create a daily reward record."""
    reward = DailyReward(
        user_id=user_id,
        reward_date=reward_date,
        points_rewarded=points_rewarded,
        streak_count=streak_count
    )
    session.add(reward)
    await session.commit()
    await session.refresh(reward)
    return reward


# ============= Referral CRUD =============

async def get_or_create_user_referral_code(session: AsyncSession, user_id: int) -> UserReferralCode:
    """Get or create user's referral code."""
    result = await session.execute(
        select(UserReferralCode).where(UserReferralCode.user_id == user_id)
    )
    referral_code = result.scalar_one_or_none()
    
    if not referral_code:
        import hashlib
        import random
        # Generate unique referral code
        code = f"REF{user_id}{hashlib.md5(f'ref_{user_id}_{random.randint(1000, 9999)}'.encode()).hexdigest()[:8].upper()}"
        referral_code = UserReferralCode(user_id=user_id, referral_code=code)
        session.add(referral_code)
        await session.commit()
        await session.refresh(referral_code)
    
    return referral_code


async def get_referral_code_by_code(session: AsyncSession, code: str) -> Optional[UserReferralCode]:
    """Get referral code by code string."""
    result = await session.execute(
        select(UserReferralCode).where(UserReferralCode.referral_code == code)
    )
    return result.scalar_one_or_none()


async def get_referral_by_users(
    session: AsyncSession,
    referrer_id: int,
    referred_id: int
) -> Optional[Referral]:
    """Get referral relationship between two users."""
    result = await session.execute(
        select(Referral)
        .where(Referral.referrer_id == referrer_id)
        .where(Referral.referred_id == referred_id)
    )
    return result.scalar_one_or_none()


async def check_telegram_id_used_referral_code(
    session: AsyncSession,
    telegram_id: int,
    referral_code: str
) -> bool:
    """
    Check if a telegram_id has previously used a referral code (even after account deletion).
    This prevents abuse where users delete and recreate accounts to reuse referral codes.
    
    Args:
        session: Database session
        telegram_id: Telegram user ID
        referral_code: Referral code to check
        
    Returns:
        True if telegram_id has used this referral code before, False otherwise
    """
    result = await session.execute(
        select(Referral)
        .join(User, Referral.referred_id == User.id)
        .where(User.telegram_id == telegram_id)
        .where(Referral.referral_code == referral_code)
    )
    return result.scalar_one_or_none() is not None


async def check_telegram_id_claimed_daily_reward(
    session: AsyncSession,
    telegram_id: int,
    reward_date: date
) -> bool:
    """
    Check if a telegram_id has claimed daily reward on a specific date (even after account deletion).
    This prevents abuse where users delete and recreate accounts to claim daily rewards multiple times.
    
    Args:
        session: Database session
        telegram_id: Telegram user ID
        reward_date: Date to check
        
    Returns:
        True if telegram_id has claimed reward on this date before, False otherwise
    """
    result = await session.execute(
        select(DailyReward)
        .join(User, DailyReward.user_id == User.id)
        .where(User.telegram_id == telegram_id)
        .where(DailyReward.reward_date == reward_date)
    )
    return result.scalar_one_or_none() is not None


async def check_telegram_id_received_profile_completion_reward(
    session: AsyncSession,
    telegram_id: int,
    referrer_id: int
) -> bool:
    """
    Check if a telegram_id has received profile completion reward for a specific referrer (even after account deletion).
    This prevents abuse where users delete and recreate accounts to get profile completion rewards multiple times.
    
    Args:
        session: Database session
        telegram_id: Telegram user ID (referred user)
        referrer_id: Referrer user ID
        
    Returns:
        True if telegram_id has received profile completion reward for this referrer before, False otherwise
    """
    result = await session.execute(
        select(PointsHistory)
        .join(User, PointsHistory.user_id == User.id)
        .where(User.telegram_id == telegram_id)
        .where(PointsHistory.source == "referral_profile_complete")
        .where(PointsHistory.related_user_id == referrer_id)
    )
    return result.scalar_one_or_none() is not None


async def create_referral(
    session: AsyncSession,
    referrer_id: int,
    referred_id: int,
    referral_code: str,
    points_rewarded_referrer: int = 0,
    points_rewarded_referred: int = 0,
    check_telegram_id: Optional[int] = None
) -> Optional[Referral]:
    """
    Create a referral relationship.
    
    Args:
        session: Database session
        referrer_id: Referrer user ID
        referred_id: Referred user ID
        referral_code: Referral code
        points_rewarded_referrer: Points rewarded to referrer
        points_rewarded_referred: Points rewarded to referred user
        check_telegram_id: Optional telegram_id to check if this telegram_id has used this code before
        
    Returns:
        Referral object if created, None if already exists or telegram_id has used this code before
    """
    # Check if telegram_id has used this referral code before (prevent abuse)
    if check_telegram_id:
        if await check_telegram_id_used_referral_code(session, check_telegram_id, referral_code):
            return None  # Telegram ID has used this code before
    
    # Check if referral already exists
    result = await session.execute(
        select(Referral)
        .where(Referral.referrer_id == referrer_id)
        .where(Referral.referred_id == referred_id)
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        return None  # Already exists
    
    referral = Referral(
        referrer_id=referrer_id,
        referred_id=referred_id,
        referral_code=referral_code,
        points_rewarded_referrer=points_rewarded_referrer,
        points_rewarded_referred=points_rewarded_referred
    )
    session.add(referral)
    
    # Update usage count
    user_referral_code = await get_referral_code_by_code(session, referral_code)
    if user_referral_code:
        user_referral_code.usage_count += 1
    
    await session.commit()
    await session.refresh(referral)
    return referral


async def get_referral_count(session: AsyncSession, user_id: int) -> int:
    """Get user's referral count."""
    result = await session.execute(
        select(func.count(Referral.id))
        .where(Referral.referrer_id == user_id)
    )
    return result.scalar() or 0


# ============= User Activity Count Functions =============

async def get_user_chat_count(session: AsyncSession, user_id: int) -> int:
    """Get count of successful chats for a user (ended chats only)."""
    result = await session.execute(
        select(func.count(ChatRoom.id))
        .where(
            and_(
                ChatRoom.is_active == False,
                ChatRoom.ended_at.isnot(None),
                or_(
                    ChatRoom.user1_id == user_id,
                    ChatRoom.user2_id == user_id
                )
            )
        )
    )
    return result.scalar() or 0


async def get_user_message_count(session: AsyncSession, user_id: int) -> int:
    """
    Get total count of messages sent by user in chats.
    Note: This is an approximation based on chat rooms.
    For exact count, we would need to track messages in a separate table.
    For now, we'll use a placeholder that returns 0 and can be improved later.
    """
    # TODO: Implement proper message counting if needed
    # For now, return 0 as we don't have a messages table
    return 0


async def get_user_follow_given_count(session: AsyncSession, user_id: int) -> int:
    """Get count of follows given by user."""
    result = await session.execute(
        select(func.count(Follow.id))
        .where(Follow.follower_id == user_id)
    )
    return result.scalar() or 0


async def get_user_follow_received_count(session: AsyncSession, user_id: int) -> int:
    """Get count of follows received by user."""
    result = await session.execute(
        select(func.count(Follow.id))
        .where(Follow.followed_id == user_id)
    )
    return result.scalar() or 0


async def get_user_dm_sent_count(session: AsyncSession, user_id: int) -> int:
    """Get count of direct messages sent by user."""
    result = await session.execute(
        select(func.count(DirectMessage.id))
        .where(DirectMessage.sender_id == user_id)
    )
    return result.scalar() or 0


async def get_user_premium_days(session: AsyncSession, user_id: int) -> int:
    """Get total premium days user has had (approximate)."""
    from datetime import datetime, timedelta
    
    user = await get_user_by_id(session, user_id)
    if not user or not user.is_premium or not user.premium_expires_at:
        return 0
    
    # Get all premium subscriptions
    result = await session.execute(
        select(PremiumSubscription)
        .where(PremiumSubscription.user_id == user_id)
        .order_by(PremiumSubscription.created_at)
    )
    subscriptions = result.scalars().all()
    
    total_days = 0
    for sub in subscriptions:
        if sub.end_date and sub.start_date:
            days = (sub.end_date - sub.start_date).days
            total_days += days
        elif sub.end_date:
            # If only end_date exists, estimate from created_at
            days = (sub.end_date - sub.created_at).days
            total_days += days
    
    # Also check current premium status
    if user.premium_expires_at and user.premium_expires_at > datetime.utcnow():
        # Add remaining days
        remaining = (user.premium_expires_at - datetime.utcnow()).days
        total_days += remaining
    
    return total_days


# ============= Badges CRUD =============

async def get_badge_by_key(session: AsyncSession, badge_key: str) -> Optional[Badge]:
    """Get badge by key."""
    result = await session.execute(
        select(Badge).where(Badge.badge_key == badge_key)
    )
    return result.scalar_one_or_none()


async def get_all_badges(session: AsyncSession) -> List[Badge]:
    """Get all badges."""
    result = await session.execute(select(Badge))
    return list(result.scalars().all())


async def award_badge_to_user(
    session: AsyncSession,
    user_id: int,
    badge_id: int
) -> Optional[UserBadge]:
    """Award a badge to user."""
    # Check if user already has this badge
    result = await session.execute(
        select(UserBadge)
        .where(UserBadge.user_id == user_id)
        .where(UserBadge.badge_id == badge_id)
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        return existing  # Already has badge
    
    user_badge = UserBadge(user_id=user_id, badge_id=badge_id)
    session.add(user_badge)
    await session.commit()
    await session.refresh(user_badge)
    return user_badge


async def get_user_badges(session: AsyncSession, user_id: int) -> List[UserBadge]:
    """Get all badges for a user."""
    result = await session.execute(
        select(UserBadge)
        .where(UserBadge.user_id == user_id)
        .order_by(UserBadge.earned_at.desc())
        .options(joinedload(UserBadge.badge))
    )
    return list(result.scalars().all())


async def user_has_badge(session: AsyncSession, user_id: int, badge_key: str) -> bool:
    """Check if user has a specific badge."""
    badge = await get_badge_by_key(session, badge_key)
    if not badge:
        return False
    
    result = await session.execute(
        select(UserBadge)
        .where(UserBadge.user_id == user_id)
        .where(UserBadge.badge_id == badge.id)
    )
    return result.scalar_one_or_none() is not None


# ============= Achievements CRUD =============

async def get_achievement_by_key(session: AsyncSession, achievement_key: str) -> Optional[Achievement]:
    """Get achievement by key."""
    result = await session.execute(
        select(Achievement).where(Achievement.achievement_key == achievement_key)
    )
    return result.scalar_one_or_none()


async def get_all_achievements(session: AsyncSession) -> List[Achievement]:
    """Get all achievements with badge relationship loaded."""
    result = await session.execute(
        select(Achievement)
        .options(joinedload(Achievement.badge))
    )
    # Use unique() to avoid duplicate results from joinedload
    return list(result.unique().scalars().all())


async def get_or_create_user_achievement(
    session: AsyncSession,
    user_id: int,
    achievement_id: int
) -> UserAchievement:
    """Get or create user achievement progress."""
    result = await session.execute(
        select(UserAchievement)
        .where(UserAchievement.user_id == user_id)
        .where(UserAchievement.achievement_id == achievement_id)
    )
    user_achievement = result.scalar_one_or_none()
    
    if not user_achievement:
        user_achievement = UserAchievement(
            user_id=user_id,
            achievement_id=achievement_id,
            current_progress=0,
            is_completed=False
        )
        session.add(user_achievement)
        await session.commit()
        await session.refresh(user_achievement)
    
    return user_achievement


async def update_user_achievement_progress(
    session: AsyncSession,
    user_id: int,
    achievement_id: int,
    progress_increment: int = 1
) -> Optional[UserAchievement]:
    """Update user achievement progress."""
    user_achievement = await get_or_create_user_achievement(session, user_id, achievement_id)
    
    if user_achievement.is_completed:
        return user_achievement  # Already completed
    
    user_achievement.current_progress += progress_increment
    
    # Get achievement to check target
    achievement_result = await session.execute(
        select(Achievement).where(Achievement.id == achievement_id)
    )
    achievement = achievement_result.scalar_one_or_none()
    
    if achievement and user_achievement.current_progress >= achievement.target_value:
        user_achievement.is_completed = True
        user_achievement.completed_at = datetime.utcnow()
        
        # Award points if achievement has points reward
        if achievement.points_reward > 0:
            await add_points(
                session,
                user_id,
                achievement.points_reward,
                "earned",
                "achievement",
                f"Achievement: {achievement.achievement_name}"
            )
        
        # Award badge if achievement has badge
        # Note: Badge notification will be sent by the calling code if needed
        # We don't send notification here to avoid duplicate notifications
        if achievement.badge_id:
            await award_badge_to_user(session, user_id, achievement.badge_id)
    
    await session.commit()
    await session.refresh(user_achievement)
    return user_achievement


async def get_user_achievements(
    session: AsyncSession,
    user_id: int,
    completed_only: bool = False
) -> List[UserAchievement]:
    """Get user achievements."""
    query = select(UserAchievement).where(UserAchievement.user_id == user_id)
    
    if completed_only:
        query = query.where(UserAchievement.is_completed == True)
    
    result = await session.execute(query.order_by(UserAchievement.completed_at.desc()))
    return list(result.scalars().all())


# ============= Weekly Challenges CRUD =============

async def get_active_weekly_challenges(session: AsyncSession) -> List[WeeklyChallenge]:
    """Get all active weekly challenges."""
    from datetime import date
    today = date.today()
    
    result = await session.execute(
        select(WeeklyChallenge)
        .where(WeeklyChallenge.is_active == True)
        .where(WeeklyChallenge.week_start_date <= today)
        .where(WeeklyChallenge.week_end_date >= today)
    )
    return list(result.scalars().all())


async def get_weekly_challenge_by_key(session: AsyncSession, challenge_key: str) -> Optional[WeeklyChallenge]:
    """Get weekly challenge by key."""
    result = await session.execute(
        select(WeeklyChallenge).where(WeeklyChallenge.challenge_key == challenge_key)
    )
    return result.scalar_one_or_none()


async def get_or_create_user_challenge(
    session: AsyncSession,
    user_id: int,
    challenge_id: int
) -> UserChallenge:
    """Get or create user challenge progress."""
    result = await session.execute(
        select(UserChallenge)
        .where(UserChallenge.user_id == user_id)
        .where(UserChallenge.challenge_id == challenge_id)
    )
    user_challenge = result.scalar_one_or_none()
    
    if not user_challenge:
        user_challenge = UserChallenge(
            user_id=user_id,
            challenge_id=challenge_id,
            current_progress=0,
            is_completed=False
        )
        session.add(user_challenge)
        await session.commit()
        await session.refresh(user_challenge)
    
    return user_challenge


async def update_user_challenge_progress(
    session: AsyncSession,
    user_id: int,
    challenge_id: int,
    progress_increment: int = 1
) -> Optional[UserChallenge]:
    """Update user challenge progress."""
    user_challenge = await get_or_create_user_challenge(session, user_id, challenge_id)
    
    if user_challenge.is_completed:
        return user_challenge  # Already completed
    
    user_challenge.current_progress += progress_increment
    
    # Get challenge to check target
    challenge_result = await session.execute(
        select(WeeklyChallenge).where(WeeklyChallenge.id == challenge_id)
    )
    challenge = challenge_result.scalar_one_or_none()
    
    if challenge and user_challenge.current_progress >= challenge.target_value:
        user_challenge.is_completed = True
        user_challenge.completed_at = datetime.utcnow()
        user_challenge.points_rewarded = challenge.points_reward
        
        # Award points
        if challenge.points_reward > 0:
            await add_points(
                session,
                user_id,
                challenge.points_reward,
                "earned",
                "weekly_challenge",
                f"Challenge: {challenge.challenge_name}"
            )
    
    await session.commit()
    await session.refresh(user_challenge)
    return user_challenge


async def get_user_challenges(
    session: AsyncSession,
    user_id: int,
    completed_only: bool = False
) -> List[UserChallenge]:
    """Get user challenges."""
    query = select(UserChallenge).where(UserChallenge.user_id == user_id)
    
    if completed_only:
        query = query.where(UserChallenge.is_completed == True)
    
    result = await session.execute(query.order_by(UserChallenge.completed_at.desc()))
    return list(result.scalars().all())


# ============= Admin Features CRUD =============

# Admin Referral Links CRUD

async def create_admin_referral_link(
    session: AsyncSession,
    admin_id: int,
    link_code: str,
    link_url: str,
    description: Optional[str] = None
) -> AdminReferralLink:
    """Create a new admin referral link."""
    link = AdminReferralLink(
        admin_id=admin_id,
        link_code=link_code,
        link_url=link_url,
        description=description
    )
    session.add(link)
    await session.commit()
    await session.refresh(link)
    return link


async def get_admin_referral_link_by_code(
    session: AsyncSession,
    link_code: str
) -> Optional[AdminReferralLink]:
    """Get admin referral link by code."""
    result = await session.execute(
        select(AdminReferralLink).where(AdminReferralLink.link_code == link_code)
    )
    return result.scalar_one_or_none()


async def get_admin_referral_link_by_id(
    session: AsyncSession,
    link_id: int
) -> Optional[AdminReferralLink]:
    """Get admin referral link by ID."""
    result = await session.execute(
        select(AdminReferralLink).where(AdminReferralLink.id == link_id)
    )
    return result.scalar_one_or_none()


async def get_admin_referral_links(
    session: AsyncSession,
    admin_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50
) -> List[AdminReferralLink]:
    """Get admin referral links."""
    query = select(AdminReferralLink)
    
    if admin_id:
        query = query.where(AdminReferralLink.admin_id == admin_id)
    
    query = query.order_by(AdminReferralLink.created_at.desc()).offset(skip).limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


async def increment_link_click(
    session: AsyncSession,
    link_id: int,
    telegram_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> bool:
    """Increment click count for a referral link."""
    link = await get_admin_referral_link_by_id(session, link_id)
    if not link:
        return False
    
    # Create click record
    click = AdminReferralLinkClick(
        link_id=link_id,
        telegram_id=telegram_id,
        ip_address=ip_address,
        user_agent=user_agent
    )
    session.add(click)
    
    # Update click count
    link.click_count += 1
    await session.commit()
    return True


async def record_link_signup(
    session: AsyncSession,
    link_id: int,
    user_id: int,
    clicked_at: Optional[datetime] = None
) -> bool:
    """Record a signup via referral link."""
    link = await get_admin_referral_link_by_id(session, link_id)
    if not link:
        return False
    
    # Check if already recorded
    result = await session.execute(
        select(AdminReferralLinkSignup).where(
            and_(
                AdminReferralLinkSignup.link_id == link_id,
                AdminReferralLinkSignup.user_id == user_id
            )
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        return False  # Already recorded
    
    # Create signup record
    signup = AdminReferralLinkSignup(
        link_id=link_id,
        user_id=user_id,
        clicked_at=clicked_at
    )
    session.add(signup)
    
    # Update signup count
    link.signup_count += 1
    await session.commit()
    return True


async def update_admin_referral_link(
    session: AsyncSession,
    link_id: int,
    link_code: Optional[str] = None,
    link_url: Optional[str] = None,
    description: Optional[str] = None,
    is_active: Optional[bool] = None
) -> bool:
    """Update admin referral link."""
    link = await get_admin_referral_link_by_id(session, link_id)
    if not link:
        return False
    
    if link_code is not None:
        link.link_code = link_code
    if link_url is not None:
        link.link_url = link_url
    if description is not None:
        link.description = description
    if is_active is not None:
        link.is_active = is_active
    
    await session.commit()
    await session.refresh(link)
    return True


async def delete_admin_referral_link(
    session: AsyncSession,
    link_id: int
) -> bool:
    """Delete admin referral link."""
    link = await get_admin_referral_link_by_id(session, link_id)
    if not link:
        return False
    
    await session.delete(link)
    await session.commit()
    return True


async def get_link_statistics(
    session: AsyncSession,
    link_id: int
) -> dict:
    """Get detailed statistics for a referral link."""
    link = await get_admin_referral_link_by_id(session, link_id)
    if not link:
        return {}
    
    # Get click details
    clicks_result = await session.execute(
        select(func.count(AdminReferralLinkClick.id))
        .where(AdminReferralLinkClick.link_id == link_id)
    )
    total_clicks = clicks_result.scalar() or 0
    
    # Get unique telegram IDs
    unique_users_result = await session.execute(
        select(func.count(func.distinct(AdminReferralLinkClick.telegram_id)))
        .where(
            and_(
                AdminReferralLinkClick.link_id == link_id,
                AdminReferralLinkClick.telegram_id.isnot(None)
            )
        )
    )
    unique_users = unique_users_result.scalar() or 0
    
    # Get signup details
    signups_result = await session.execute(
        select(func.count(AdminReferralLinkSignup.id))
        .where(AdminReferralLinkSignup.link_id == link_id)
    )
    total_signups = signups_result.scalar() or 0
    
    # Calculate conversion rate
    conversion_rate = (total_signups / total_clicks * 100) if total_clicks > 0 else 0
    
    return {
        "link_id": link.id,
        "link_code": link.link_code,
        "click_count": link.click_count,
        "signup_count": link.signup_count,
        "total_clicks": total_clicks,
        "unique_users": unique_users,
        "total_signups": total_signups,
        "conversion_rate": round(conversion_rate, 2),
        "is_active": link.is_active,
        "created_at": link.created_at
    }


# Coin Settings CRUD

async def get_coin_setting(
    session: AsyncSession,
    premium_days: int
) -> Optional[CoinSetting]:
    """Get coin setting for specific premium days."""
    result = await session.execute(
        select(CoinSetting).where(CoinSetting.premium_days == premium_days)
    )
    return result.scalar_one_or_none()


async def get_all_coin_settings(
    session: AsyncSession,
    active_only: bool = False
) -> List[CoinSetting]:
    """Get all coin settings."""
    query = select(CoinSetting)
    
    if active_only:
        query = query.where(CoinSetting.is_active == True)
    
    query = query.order_by(CoinSetting.premium_days.asc())
    result = await session.execute(query)
    return list(result.scalars().all())


async def update_coin_setting(
    session: AsyncSession,
    premium_days: int,
    coins_required: Optional[int] = None,
    is_active: Optional[bool] = None
) -> bool:
    """Update coin setting."""
    setting = await get_coin_setting(session, premium_days)
    
    if not setting:
        # Create new setting
        setting = CoinSetting(
            premium_days=premium_days,
            coins_required=coins_required or 200,
            is_active=is_active if is_active is not None else True
        )
        session.add(setting)
    else:
        if coins_required is not None:
            setting.coins_required = coins_required
        if is_active is not None:
            setting.is_active = is_active
    
    await session.commit()
    await session.refresh(setting)
    return True


async def get_coins_for_premium_days(
    session: AsyncSession,
    days: int
) -> Optional[int]:
    """Get required coins for premium days."""
    setting = await get_coin_setting(session, days)
    if setting and setting.is_active:
        return setting.coins_required
    return None


# ============= Broadcast Messages CRUD =============

async def create_broadcast_message(
    session: AsyncSession,
    admin_id: int,
    message_type: str,
    message_text: Optional[str] = None,
    message_file_id: Optional[str] = None,
    message_caption: Optional[str] = None,
    forwarded_from_chat_id: Optional[int] = None,
    forwarded_from_message_id: Optional[int] = None,
    delay_seconds: float = 0.067  # Default ~15 msg/sec
) -> BroadcastMessage:
    """Create a new broadcast message."""
    broadcast = BroadcastMessage(
        admin_id=admin_id,
        message_type=message_type,
        message_text=message_text,
        message_file_id=message_file_id,
        message_caption=message_caption,
        forwarded_from_chat_id=forwarded_from_chat_id,
        forwarded_from_message_id=forwarded_from_message_id,
        delay_seconds=delay_seconds
    )
    session.add(broadcast)
    await session.commit()
    await session.refresh(broadcast)
    return broadcast


async def get_broadcast_message_by_id(
    session: AsyncSession,
    broadcast_id: int
) -> Optional[BroadcastMessage]:
    """Get broadcast message by ID."""
    result = await session.execute(
        select(BroadcastMessage).where(BroadcastMessage.id == broadcast_id)
    )
    return result.scalar_one_or_none()


async def get_broadcast_messages(
    session: AsyncSession,
    admin_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50
) -> List[BroadcastMessage]:
    """Get broadcast messages."""
    query = select(BroadcastMessage)
    
    if admin_id:
        query = query.where(BroadcastMessage.admin_id == admin_id)
    
    query = query.order_by(BroadcastMessage.created_at.desc()).offset(skip).limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


async def create_broadcast_receipt(
    session: AsyncSession,
    broadcast_id: int,
    user_id: int,
    telegram_message_id: Optional[int] = None,
    status: str = "sent"
) -> BroadcastMessageReceipt:
    """Create a broadcast message receipt."""
    receipt = BroadcastMessageReceipt(
        broadcast_id=broadcast_id,
        user_id=user_id,
        telegram_message_id=telegram_message_id,
        status=status
    )
    session.add(receipt)
    await session.commit()
    await session.refresh(receipt)
    return receipt


async def update_broadcast_receipt_status(
    session: AsyncSession,
    broadcast_id: int,
    user_id: int,
    status: str
) -> bool:
    """Update broadcast receipt status."""
    result = await session.execute(
        select(BroadcastMessageReceipt).where(
            and_(
                BroadcastMessageReceipt.broadcast_id == broadcast_id,
                BroadcastMessageReceipt.user_id == user_id
            )
        )
    )
    receipt = result.scalar_one_or_none()
    
    if not receipt:
        return False
    
    receipt.status = status
    if status == "opened":
        from datetime import datetime
        receipt.opened_at = datetime.utcnow()
    
    await session.commit()
    await session.refresh(receipt)
    return True


async def increment_broadcast_stats(
    session: AsyncSession,
    broadcast_id: int,
    sent: bool = False,
    failed: bool = False,
    opened: bool = False
) -> bool:
    """Increment broadcast statistics."""
    broadcast = await get_broadcast_message_by_id(session, broadcast_id)
    if not broadcast:
        return False
    
    if sent:
        broadcast.sent_count += 1
    if failed:
        broadcast.failed_count += 1
    if opened:
        broadcast.opened_count += 1
    
    await session.commit()
    await session.refresh(broadcast)
    return True


async def get_broadcast_statistics(
    session: AsyncSession,
    broadcast_id: int
) -> dict:
    """Get detailed statistics for a broadcast message."""
    broadcast = await get_broadcast_message_by_id(session, broadcast_id)
    if not broadcast:
        return {}
    
    # Get receipt details
    receipts_result = await session.execute(
        select(func.count(BroadcastMessageReceipt.id))
        .where(BroadcastMessageReceipt.broadcast_id == broadcast_id)
    )
    total_receipts = receipts_result.scalar() or 0
    
    # Get status counts
    sent_result = await session.execute(
        select(func.count(BroadcastMessageReceipt.id))
        .where(
            and_(
                BroadcastMessageReceipt.broadcast_id == broadcast_id,
                BroadcastMessageReceipt.status == "sent"
            )
        )
    )
    sent_count = sent_result.scalar() or 0
    
    failed_result = await session.execute(
        select(func.count(BroadcastMessageReceipt.id))
        .where(
            and_(
                BroadcastMessageReceipt.broadcast_id == broadcast_id,
                BroadcastMessageReceipt.status == "failed"
            )
        )
    )
    failed_count = failed_result.scalar() or 0
    
    opened_result = await session.execute(
        select(func.count(BroadcastMessageReceipt.id))
        .where(
            and_(
                BroadcastMessageReceipt.broadcast_id == broadcast_id,
                BroadcastMessageReceipt.status == "opened"
            )
        )
    )
    opened_count = opened_result.scalar() or 0
    
    # Calculate open rate
    open_rate = (opened_count / sent_count * 100) if sent_count > 0 else 0
    
    return {
        "broadcast_id": broadcast.id,
        "message_type": broadcast.message_type,
        "sent_count": broadcast.sent_count,
        "failed_count": broadcast.failed_count,
        "opened_count": broadcast.opened_count,
        "total_receipts": total_receipts,
        "sent_count_detail": sent_count,
        "failed_count_detail": failed_count,
        "opened_count_detail": opened_count,
        "open_rate": round(open_rate, 2),
        "created_at": broadcast.created_at
    }


# ============= Event System CRUD =============

async def create_event(
    session: AsyncSession,
    event_key: str,
    event_name: str,
    event_type: str,
    start_date: datetime,
    end_date: datetime,
    created_by_admin_id: int,
    event_description: Optional[str] = None,
    config_json: Optional[str] = None,
    is_active: bool = True,
    is_visible: bool = True
) -> Event:
    """Create a new event."""
    event = Event(
        event_key=event_key,
        event_name=event_name,
        event_description=event_description,
        event_type=event_type,
        config_json=config_json,
        start_date=start_date,
        end_date=end_date,
        is_active=is_active,
        is_visible=is_visible,
        created_by_admin_id=created_by_admin_id
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event


async def get_event_by_id(session: AsyncSession, event_id: int) -> Optional[Event]:
    """Get event by ID."""
    result = await session.execute(select(Event).where(Event.id == event_id))
    return result.scalar_one_or_none()


async def get_event_by_key(session: AsyncSession, event_key: str) -> Optional[Event]:
    """Get event by event_key."""
    result = await session.execute(select(Event).where(Event.event_key == event_key))
    return result.scalar_one_or_none()


async def get_active_events(session: AsyncSession, event_type: Optional[str] = None) -> List[Event]:
    """Get all active events (currently running)."""
    now = datetime.utcnow()
    query = select(Event).where(
        and_(
            Event.is_active == True,
            Event.start_date <= now,
            Event.end_date >= now
        )
    )
    
    if event_type:
        query = query.where(Event.event_type == event_type)
    
    query = query.order_by(Event.start_date.desc())
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_visible_events(session: AsyncSession) -> List[Event]:
    """Get all visible active events for users."""
    now = datetime.utcnow()
    result = await session.execute(
        select(Event).where(
            and_(
                Event.is_active == True,
                Event.is_visible == True,
                Event.start_date <= now,
                Event.end_date >= now
            )
        ).order_by(Event.start_date.desc())
    )
    return list(result.scalars().all())


async def get_all_events(session: AsyncSession, skip: int = 0, limit: int = 100) -> List[Event]:
    """Get all events (for admin)."""
    result = await session.execute(
        select(Event)
        .order_by(Event.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def update_event(
    session: AsyncSession,
    event_id: int,
    event_name: Optional[str] = None,
    event_description: Optional[str] = None,
    config_json: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    is_active: Optional[bool] = None,
    is_visible: Optional[bool] = None
) -> Optional[Event]:
    """Update event."""
    event = await get_event_by_id(session, event_id)
    if not event:
        return None
    
    if event_name is not None:
        event.event_name = event_name
    if event_description is not None:
        event.event_description = event_description
    if config_json is not None:
        event.config_json = config_json
    if start_date is not None:
        event.start_date = start_date
    if end_date is not None:
        event.end_date = end_date
    if is_active is not None:
        event.is_active = is_active
    if is_visible is not None:
        event.is_visible = is_visible
    
    event.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(event)
    return event


async def delete_event(session: AsyncSession, event_id: int) -> bool:
    """Delete event (cascade will handle participants and rewards)."""
    event = await get_event_by_id(session, event_id)
    if not event:
        return False
    
    await session.delete(event)
    await session.commit()
    return True


async def get_or_create_event_participant(
    session: AsyncSession,
    event_id: int,
    user_id: int
) -> EventParticipant:
    """Get or create event participant."""
    result = await session.execute(
        select(EventParticipant).where(
            and_(
                EventParticipant.event_id == event_id,
                EventParticipant.user_id == user_id
            )
        )
    )
    participant = result.scalar_one_or_none()
    
    if not participant:
        participant = EventParticipant(
            event_id=event_id,
            user_id=user_id,
            progress_value=0
        )
        session.add(participant)
        await session.commit()
        await session.refresh(participant)
    
    return participant


async def update_event_participant_progress(
    session: AsyncSession,
    event_id: int,
    user_id: int,
    progress_increment: int = 1
) -> Optional[EventParticipant]:
    """Update participant progress."""
    participant = await get_or_create_event_participant(session, event_id, user_id)
    participant.progress_value += progress_increment
    participant.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(participant)
    return participant


async def get_event_participant(
    session: AsyncSession,
    event_id: int,
    user_id: int
) -> Optional[EventParticipant]:
    """Get event participant."""
    result = await session.execute(
        select(EventParticipant).where(
            and_(
                EventParticipant.event_id == event_id,
                EventParticipant.user_id == user_id
            )
        )
    )
    return result.scalar_one_or_none()


async def get_event_participants(
    session: AsyncSession,
    event_id: int,
    skip: int = 0,
    limit: int = 100,
    order_by_progress: bool = True
) -> List[EventParticipant]:
    """Get event participants."""
    query = select(EventParticipant).where(EventParticipant.event_id == event_id)
    
    if order_by_progress:
        query = query.order_by(EventParticipant.progress_value.desc())
    else:
        query = query.order_by(EventParticipant.joined_at.desc())
    
    query = query.offset(skip).limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_event_participant_count(session: AsyncSession, event_id: int) -> int:
    """Get total participant count for an event."""
    result = await session.execute(
        select(func.count(EventParticipant.id)).where(EventParticipant.event_id == event_id)
    )
    return result.scalar() or 0


async def create_event_reward(
    session: AsyncSession,
    event_id: int,
    user_id: int,
    reward_type: str,
    reward_value: int,
    reward_description: Optional[str] = None,
    is_lottery_winner: bool = False,
    lottery_rank: Optional[int] = None
) -> EventReward:
    """Create event reward."""
    reward = EventReward(
        event_id=event_id,
        user_id=user_id,
        reward_type=reward_type,
        reward_value=reward_value,
        reward_description=reward_description,
        is_lottery_winner=is_lottery_winner,
        lottery_rank=lottery_rank
    )
    session.add(reward)
    await session.commit()
    await session.refresh(reward)
    return reward


async def get_event_rewards(
    session: AsyncSession,
    event_id: int,
    user_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100
) -> List[EventReward]:
    """Get event rewards."""
    query = select(EventReward).where(EventReward.event_id == event_id)
    
    if user_id:
        query = query.where(EventReward.user_id == user_id)
    
    query = query.order_by(EventReward.awarded_at.desc()).offset(skip).limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_user_event_rewards(
    session: AsyncSession,
    user_id: int,
    event_id: Optional[int] = None
) -> List[EventReward]:
    """Get user's event rewards."""
    query = select(EventReward).where(EventReward.user_id == user_id)
    
    if event_id:
        query = query.where(EventReward.event_id == event_id)
    
    query = query.order_by(EventReward.awarded_at.desc())
    result = await session.execute(query)
    return list(result.scalars().all())


async def mark_participant_reward_received(
    session: AsyncSession,
    event_id: int,
    user_id: int
) -> bool:
    """Mark that participant has received reward (for one-time rewards)."""
    participant = await get_event_participant(session, event_id, user_id)
    if not participant:
        return False
    
    participant.has_received_reward = True
    await session.commit()
    await session.refresh(participant)
    return True


# ============= Leaderboard CRUD =============

async def get_top_users_by_points(
    session: AsyncSession,
    limit: int = 10,
    skip: int = 0,
    period: Optional[str] = None  # 'week', 'month', None for all-time
) -> List[tuple]:
    """
    Get top users by points.
    Returns list of tuples: (user_id, points, rank)
    """
    from datetime import datetime, timedelta
    
    query = select(
        UserPoints.user_id,
        UserPoints.points,
        User.id,
        User.display_name,
        User.username,
        User.telegram_id,
        User.profile_id,
        User.gender
    ).join(
        User, UserPoints.user_id == User.id
    ).where(
        User.is_banned == False,
        User.is_active == True
    )
    
    # Filter by period if specified
    if period == 'week':
        week_ago = datetime.utcnow() - timedelta(days=7)
        query = query.join(
            PointsHistory, UserPoints.user_id == PointsHistory.user_id
        ).where(
            PointsHistory.created_at >= week_ago
        ).group_by(UserPoints.user_id)
    elif period == 'month':
        month_ago = datetime.utcnow() - timedelta(days=30)
        query = query.join(
            PointsHistory, UserPoints.user_id == PointsHistory.user_id
        ).where(
            PointsHistory.created_at >= month_ago
        ).group_by(UserPoints.user_id)
    
    query = query.order_by(UserPoints.points.desc()).offset(skip).limit(limit)
    result = await session.execute(query)
    
    leaderboard = []
    for idx, row in enumerate(result.all(), 1):
        user_id, points, user_db_id, display_name, username, telegram_id, profile_id, gender = row
        # Use display_name if available, otherwise fall back to username, then telegram_id
        final_display_name = display_name or username or f"User {telegram_id}"
        leaderboard.append((user_id, points, idx, final_display_name, profile_id, gender))
    
    return leaderboard


async def get_top_users_by_referrals(
    session: AsyncSession,
    limit: int = 10,
    skip: int = 0,
    period: Optional[str] = None  # 'week', 'month', None for all-time
) -> List[tuple]:
    """
    Get top users by referral count.
    Returns list of tuples: (user_id, referral_count, rank, display_name)
    """
    from datetime import datetime, timedelta
    
    # Count referrals per user
    referral_counts = select(
        Referral.referrer_id,
        func.count(Referral.id).label('count')
    ).group_by(Referral.referrer_id).subquery()
    
    query = select(
        referral_counts.c.referrer_id,
        referral_counts.c.count,
        User.id,
        User.display_name,
        User.username,
        User.telegram_id,
        User.profile_id,
        User.gender
    ).join(
        User, referral_counts.c.referrer_id == User.id
    ).where(
        User.is_banned == False,
        User.is_active == True
    )
    
    # Filter by period if specified
    if period:
        period_start = datetime.utcnow() - timedelta(days=7 if period == 'week' else 30)
        referral_counts = select(
            Referral.referrer_id,
            func.count(Referral.id).label('count')
        ).where(
            Referral.created_at >= period_start
        ).group_by(Referral.referrer_id).subquery()
        
        query = select(
            referral_counts.c.referrer_id,
            referral_counts.c.count,
            User.id,
            User.display_name,
            User.username,
            User.telegram_id,
            User.profile_id,
            User.gender
        ).join(
            User, referral_counts.c.referrer_id == User.id
        ).where(
            User.is_banned == False,
            User.is_active == True
        )
    
    query = query.order_by(referral_counts.c.count.desc()).offset(skip).limit(limit)
    result = await session.execute(query)
    
    leaderboard = []
    for idx, row in enumerate(result.all(), 1):
        user_id, count, user_db_id, display_name, username, telegram_id, profile_id, gender = row
        # Use display_name if available, otherwise fall back to username, then telegram_id
        final_display_name = display_name or username or f"User {telegram_id}"
        leaderboard.append((user_id, count, idx, final_display_name, profile_id, gender))
    
    return leaderboard


async def get_top_users_by_likes(
    session: AsyncSession,
    limit: int = 10,
    skip: int = 0,
    period: Optional[str] = None  # 'week', 'month', None for all-time
) -> List[tuple]:
    """
    Get top users by like count (likes received).
    Returns list of tuples: (user_id, like_count, rank, display_name)
    """
    from datetime import datetime, timedelta
    
    # Count likes received per user
    like_counts = select(
        Like.liked_user_id,
        func.count(Like.id).label('count')
    ).group_by(Like.liked_user_id).subquery()
    
    query = select(
        like_counts.c.liked_user_id,
        like_counts.c.count,
        User.id,
        User.display_name,
        User.username,
        User.telegram_id,
        User.profile_id,
        User.gender
    ).join(
        User, like_counts.c.liked_user_id == User.id
    ).where(
        User.is_banned == False,
        User.is_active == True
    )
    
    # Filter by period if specified
    if period:
        period_start = datetime.utcnow() - timedelta(days=7 if period == 'week' else 30)
        like_counts = select(
            Like.liked_user_id,
            func.count(Like.id).label('count')
        ).where(
            Like.created_at >= period_start
        ).group_by(Like.liked_user_id).subquery()
        
        query = select(
            like_counts.c.liked_user_id,
            like_counts.c.count,
            User.id,
            User.display_name,
            User.username,
            User.telegram_id,
            User.profile_id,
            User.gender
        ).join(
            User, like_counts.c.liked_user_id == User.id
        ).where(
            User.is_banned == False,
            User.is_active == True
        )
    
    query = query.order_by(like_counts.c.count.desc()).offset(skip).limit(limit)
    result = await session.execute(query)
    
    leaderboard = []
    for idx, row in enumerate(result.all(), 1):
        user_id, count, user_db_id, display_name, username, telegram_id, profile_id, gender = row
        # Use display_name if available, otherwise fall back to username, then telegram_id
        final_display_name = display_name or username or f"User {telegram_id}"
        leaderboard.append((user_id, count, idx, final_display_name, profile_id, gender))
    
    return leaderboard


async def get_user_rank_by_points(
    session: AsyncSession,
    user_id: int,
    period: Optional[str] = None
) -> Optional[int]:
    """Get user's rank by points."""
    from datetime import datetime, timedelta
    
    user_points = await get_user_points(session, user_id)
    if user_points is None:
        return None
    
    query = select(func.count(UserPoints.user_id)).where(
        UserPoints.points > user_points,
        UserPoints.user_id != user_id
    ).join(
        User, UserPoints.user_id == User.id
    ).where(
        User.is_banned == False,
        User.is_active == True
    )
    
    # Filter by period if specified
    if period:
        period_start = datetime.utcnow() - timedelta(days=7 if period == 'week' else 30)
        query = query.join(
            PointsHistory, UserPoints.user_id == PointsHistory.user_id
        ).where(
            PointsHistory.created_at >= period_start
        )
    
    result = await session.execute(query)
    rank = result.scalar() or 0
    return rank + 1


async def get_user_rank_by_referrals(
    session: AsyncSession,
    user_id: int,
    period: Optional[str] = None
) -> Optional[int]:
    """Get user's rank by referrals."""
    from datetime import datetime, timedelta
    
    user_referral_count = await get_referral_count(session, user_id)
    
    # Count users with more referrals
    referral_counts = select(
        Referral.referrer_id,
        func.count(Referral.id).label('count')
    ).group_by(Referral.referrer_id).subquery()
    
    query = select(func.count(referral_counts.c.referrer_id)).where(
        referral_counts.c.count > user_referral_count,
        referral_counts.c.referrer_id != user_id
    ).join(
        User, referral_counts.c.referrer_id == User.id
    ).where(
        User.is_banned == False,
        User.is_active == True
    )
    
    # Filter by period if specified
    if period:
        period_start = datetime.utcnow() - timedelta(days=7 if period == 'week' else 30)
        referral_counts = select(
            Referral.referrer_id,
            func.count(Referral.id).label('count')
        ).where(
            Referral.created_at >= period_start
        ).group_by(Referral.referrer_id).subquery()
        
        query = select(func.count(referral_counts.c.referrer_id)).where(
            referral_counts.c.count > user_referral_count,
            referral_counts.c.referrer_id != user_id
        ).join(
            User, referral_counts.c.referrer_id == User.id
        ).where(
            User.is_banned == False,
            User.is_active == True
        )
    
    result = await session.execute(query)
    rank = result.scalar() or 0
    return rank + 1


async def get_user_rank_by_likes(
    session: AsyncSession,
    user_id: int,
    period: Optional[str] = None
) -> Optional[int]:
    """Get user's rank by likes received."""
    from datetime import datetime, timedelta
    
    # Get user's like count
    like_count_query = select(func.count(Like.id)).where(Like.liked_user_id == user_id)
    if period:
        period_start = datetime.utcnow() - timedelta(days=7 if period == 'week' else 30)
        like_count_query = like_count_query.where(Like.created_at >= period_start)
    
    result = await session.execute(like_count_query)
    user_like_count = result.scalar() or 0
    
    # Count users with more likes
    like_counts = select(
        Like.liked_user_id,
        func.count(Like.id).label('count')
    ).group_by(Like.liked_user_id).subquery()
    
    query = select(func.count(like_counts.c.liked_user_id)).where(
        like_counts.c.count > user_like_count,
        like_counts.c.liked_user_id != user_id
    ).join(
        User, like_counts.c.liked_user_id == User.id
    ).where(
        User.is_banned == False,
        User.is_active == True
    )
    
    # Filter by period if specified
    if period:
        period_start = datetime.utcnow() - timedelta(days=7 if period == 'week' else 30)
        like_counts = select(
            Like.liked_user_id,
            func.count(Like.id).label('count')
        ).where(
            Like.created_at >= period_start
        ).group_by(Like.liked_user_id).subquery()
        
        query = select(func.count(like_counts.c.liked_user_id)).where(
            like_counts.c.count > user_like_count,
            like_counts.c.liked_user_id != user_id
        ).join(
            User, like_counts.c.liked_user_id == User.id
        ).where(
            User.is_banned == False,
            User.is_active == True
        )
    
    result = await session.execute(query)
    rank = result.scalar() or 0
    return rank + 1


# ============= Premium Plan CRUD =============

async def create_premium_plan(
    session: AsyncSession,
    plan_name: str,
    duration_days: int,
    price: float,
    original_price: Optional[float] = None,
    discount_percent: int = 0,
    stars_required: Optional[int] = None,
    payment_methods_json: Optional[str] = None,
    discount_start_date: Optional[datetime] = None,
    discount_end_date: Optional[datetime] = None,
    features_json: Optional[str] = None,
    is_active: bool = True,
    is_visible: bool = True,
    display_order: int = 0
) -> PremiumPlan:
    """Create a new premium plan."""
    # Set default payment method if not provided
    if payment_methods_json is None:
        payment_methods_json = '["shaparak"]'
    
    plan = PremiumPlan(
        plan_name=plan_name,
        duration_days=duration_days,
        price=price,
        original_price=original_price,
        discount_percent=discount_percent,
        stars_required=stars_required,
        payment_methods_json=payment_methods_json,
        discount_start_date=discount_start_date,
        discount_end_date=discount_end_date,
        features_json=features_json,
        is_active=is_active,
        is_visible=is_visible,
        display_order=display_order
    )
    session.add(plan)
    await session.commit()
    await session.refresh(plan)
    return plan


async def get_premium_plan_by_id(session: AsyncSession, plan_id: int) -> Optional[PremiumPlan]:
    """Get premium plan by ID."""
    result = await session.execute(select(PremiumPlan).where(PremiumPlan.id == plan_id))
    return result.scalar_one_or_none()


async def get_all_premium_plans(
    session: AsyncSession,
    active_only: bool = False,
    visible_only: bool = False
) -> List[PremiumPlan]:
    """Get all premium plans."""
    query = select(PremiumPlan)
    
    if active_only:
        query = query.where(PremiumPlan.is_active == True)
    if visible_only:
        query = query.where(PremiumPlan.is_visible == True)
    
    query = query.order_by(PremiumPlan.display_order.asc(), PremiumPlan.duration_days.asc())
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_visible_premium_plans(session: AsyncSession) -> List[PremiumPlan]:
    """Get visible premium plans for users (with active discount check)."""
    now = datetime.utcnow()
    query = select(PremiumPlan).where(
        PremiumPlan.is_active == True,
        PremiumPlan.is_visible == True
    ).order_by(PremiumPlan.display_order.asc(), PremiumPlan.duration_days.asc())
    
    result = await session.execute(query)
    plans = list(result.scalars().all())
    
    # Calculate effective price based on discount period
    for plan in plans:
        if plan.discount_start_date and plan.discount_end_date:
            if plan.discount_start_date <= now <= plan.discount_end_date:
                # Discount is active
                if plan.original_price:
                    plan.price = plan.original_price * (1 - plan.discount_percent / 100)
            else:
                # Discount period passed, use original price if available
                if plan.original_price:
                    plan.price = plan.original_price
    
    return plans


async def update_premium_plan(
    session: AsyncSession,
    plan_id: int,
    plan_name: Optional[str] = None,
    duration_days: Optional[int] = None,
    price: Optional[float] = None,
    original_price: Optional[float] = None,
    discount_percent: Optional[int] = None,
    stars_required: Optional[int] = None,
    payment_methods_json: Optional[str] = None,
    discount_start_date: Optional[datetime] = None,
    discount_end_date: Optional[datetime] = None,
    features_json: Optional[str] = None,
    is_active: Optional[bool] = None,
    is_visible: Optional[bool] = None,
    display_order: Optional[int] = None
) -> bool:
    """Update premium plan."""
    plan = await get_premium_plan_by_id(session, plan_id)
    if not plan:
        return False
    
    if plan_name is not None:
        plan.plan_name = plan_name
    if duration_days is not None:
        plan.duration_days = duration_days
    if price is not None:
        plan.price = price
    if original_price is not None:
        plan.original_price = original_price
    if discount_percent is not None:
        plan.discount_percent = discount_percent
    if stars_required is not None:
        plan.stars_required = stars_required
    if payment_methods_json is not None:
        plan.payment_methods_json = payment_methods_json
    if discount_start_date is not None:
        plan.discount_start_date = discount_start_date
    if discount_end_date is not None:
        plan.discount_end_date = discount_end_date
    if features_json is not None:
        plan.features_json = features_json
    if is_active is not None:
        plan.is_active = is_active
    if is_visible is not None:
        plan.is_visible = is_visible
    if display_order is not None:
        plan.display_order = display_order
    
    await session.commit()
    await session.refresh(plan)
    return True


async def delete_premium_plan(session: AsyncSession, plan_id: int) -> bool:
    """Delete premium plan."""
    plan = await get_premium_plan_by_id(session, plan_id)
    if not plan:
        return False
    
    await session.delete(plan)
    await session.commit()
    return True


# ============= Coin Reward Setting CRUD =============

async def get_coin_reward_setting(
    session: AsyncSession,
    activity_type: str
) -> Optional[CoinRewardSetting]:
    """Get coin reward setting for specific activity type."""
    result = await session.execute(
        select(CoinRewardSetting).where(CoinRewardSetting.activity_type == activity_type)
    )
    return result.scalar_one_or_none()


async def get_all_coin_reward_settings(
    session: AsyncSession,
    active_only: bool = False
) -> List[CoinRewardSetting]:
    """Get all coin reward settings."""
    query = select(CoinRewardSetting)
    
    if active_only:
        query = query.where(CoinRewardSetting.is_active == True)
    
    query = query.order_by(CoinRewardSetting.activity_type.asc())
    result = await session.execute(query)
    return list(result.scalars().all())


async def create_coin_reward_setting(
    session: AsyncSession,
    activity_type: str,
    coins_amount: int,
    description: Optional[str] = None,
    is_active: bool = True
) -> CoinRewardSetting:
    """Create or update coin reward setting."""
    # Check if exists
    existing = await get_coin_reward_setting(session, activity_type)
    
    if existing:
        existing.coins_amount = coins_amount
        if description is not None:
            existing.description = description
        existing.is_active = is_active
        await session.commit()
        await session.refresh(existing)
        return existing
    else:
        setting = CoinRewardSetting(
            activity_type=activity_type,
            coins_amount=coins_amount,
            description=description,
            is_active=is_active
        )
        session.add(setting)
        await session.commit()
        await session.refresh(setting)
        return setting


async def update_coin_reward_setting(
    session: AsyncSession,
    activity_type: str,
    coins_amount: Optional[int] = None,
    description: Optional[str] = None,
    is_active: Optional[bool] = None
) -> bool:
    """Update coin reward setting."""
    setting = await get_coin_reward_setting(session, activity_type)
    
    if not setting:
        return False
    
    if coins_amount is not None:
        setting.coins_amount = coins_amount
    if description is not None:
        setting.description = description
    if is_active is not None:
        setting.is_active = is_active
    
    await session.commit()
    await session.refresh(setting)
    return True


async def delete_coin_reward_setting(session: AsyncSession, activity_type: str) -> bool:
    """Delete coin reward setting."""
    setting = await get_coin_reward_setting(session, activity_type)
    if not setting:
        return False
    
    await session.delete(setting)
    await session.commit()
    return True


async def get_coins_for_activity(session: AsyncSession, activity_type: str) -> Optional[int]:
    """Get coins amount for activity type (returns None if not found or inactive)."""
    setting = await get_coin_reward_setting(session, activity_type)
    if setting and setting.is_active:
        return setting.coins_amount
    return None


# ============= PaymentTransaction CRUD =============

async def create_payment_transaction(
    session: AsyncSession,
    user_id: int,
    plan_id: Optional[int],
    amount: float,
    gateway: str = "zarinpal",
    currency: str = "IRT",
    callback_url: Optional[str] = None,
    return_url: Optional[str] = None,
    coin_package_id: Optional[int] = None
) -> "PaymentTransaction":
    """Create a new payment transaction."""
    from db.models import PaymentTransaction
    import uuid
    
    # Generate unique transaction ID
    transaction_id = f"txn_{user_id}_{plan_id or coin_package_id or 0}_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:8]}"
    
    transaction = PaymentTransaction(
        user_id=user_id,
        plan_id=plan_id,
        coin_package_id=coin_package_id,
        transaction_id=transaction_id,
        amount=amount,
        currency=currency,
        gateway=gateway,
        callback_url=callback_url,
        return_url=return_url,
        status="pending"
    )
    session.add(transaction)
    await session.commit()
    await session.refresh(transaction)
    return transaction


async def get_payment_transaction_by_id(
    session: AsyncSession,
    transaction_id: int
) -> Optional["PaymentTransaction"]:
    """Get payment transaction by ID."""
    from db.models import PaymentTransaction
    result = await session.execute(
        select(PaymentTransaction).where(PaymentTransaction.id == transaction_id)
    )
    return result.scalar_one_or_none()


async def get_payment_transaction_by_transaction_id(
    session: AsyncSession,
    transaction_id: str
) -> Optional["PaymentTransaction"]:
    """Get payment transaction by transaction_id."""
    from db.models import PaymentTransaction
    result = await session.execute(
        select(PaymentTransaction).where(PaymentTransaction.transaction_id == transaction_id)
    )
    return result.scalar_one_or_none()


async def get_payment_transaction_by_authority(
    session: AsyncSession,
    authority: str
) -> Optional["PaymentTransaction"]:
    """Get payment transaction by authority code."""
    from db.models import PaymentTransaction
    result = await session.execute(
        select(PaymentTransaction).where(PaymentTransaction.authority == authority)
    )
    return result.scalar_one_or_none()


async def update_payment_transaction(
    session: AsyncSession,
    transaction_id: int,
    authority: Optional[str] = None,
    ref_id: Optional[str] = None,
    status: Optional[str] = None,
    payment_status: Optional[str] = None,
    paid_at: Optional[datetime] = None
) -> bool:
    """Update payment transaction."""
    from db.models import PaymentTransaction
    transaction = await get_payment_transaction_by_id(session, transaction_id)
    if not transaction:
        return False
    
    if authority is not None:
        transaction.authority = authority
    if ref_id is not None:
        transaction.ref_id = ref_id
    if status is not None:
        transaction.status = status
    if payment_status is not None:
        transaction.payment_status = payment_status
    if paid_at is not None:
        transaction.paid_at = paid_at
    
    await session.commit()
    await session.refresh(transaction)
    return True


# ============= SystemSetting CRUD =============

async def get_system_setting(
    session: AsyncSession,
    setting_key: str
) -> Optional["SystemSetting"]:
    """Get system setting by key."""
    from db.models import SystemSetting
    result = await session.execute(
        select(SystemSetting).where(SystemSetting.setting_key == setting_key)
    )
    return result.scalar_one_or_none()


async def get_system_setting_value(
    session: AsyncSession,
    setting_key: str,
    default_value: Optional[str] = None
) -> Optional[str]:
    """Get system setting value by key."""
    setting = await get_system_setting(session, setting_key)
    if setting:
        return setting.setting_value
    return default_value


async def set_system_setting(
    session: AsyncSession,
    setting_key: str,
    setting_value: str,
    setting_type: str = "string",
    description: Optional[str] = None
) -> "SystemSetting":
    """Create or update system setting."""
    from db.models import SystemSetting
    setting = await get_system_setting(session, setting_key)
    
    if setting:
        setting.setting_value = setting_value
        setting.setting_type = setting_type
        if description is not None:
            setting.description = description
    else:
        setting = SystemSetting(
            setting_key=setting_key,
            setting_value=setting_value,
            setting_type=setting_type,
            description=description
        )
        session.add(setting)
    
    await session.commit()
    await session.refresh(setting)
    return setting


# ============= Mandatory Channel CRUD =============

async def create_mandatory_channel(
    session: AsyncSession,
    channel_id: str,
    channel_name: Optional[str] = None,
    channel_link: Optional[str] = None,
    is_active: bool = True,
    order_index: int = 0,
    created_by_admin_id: Optional[int] = None
) -> MandatoryChannel:
    """Create a new mandatory channel."""
    channel = MandatoryChannel(
        channel_id=channel_id,
        channel_name=channel_name,
        channel_link=channel_link,
        is_active=is_active,
        order_index=order_index,
        created_by_admin_id=created_by_admin_id
    )
    session.add(channel)
    await session.commit()
    await session.refresh(channel)
    return channel


async def get_mandatory_channel_by_id(session: AsyncSession, channel_id: int) -> Optional[MandatoryChannel]:
    """Get mandatory channel by ID."""
    result = await session.execute(select(MandatoryChannel).where(MandatoryChannel.id == channel_id))
    return result.scalar_one_or_none()


async def get_mandatory_channel_by_channel_id(session: AsyncSession, channel_id: str) -> Optional[MandatoryChannel]:
    """Get mandatory channel by channel ID (username or numeric ID)."""
    result = await session.execute(select(MandatoryChannel).where(MandatoryChannel.channel_id == channel_id))
    return result.scalar_one_or_none()


async def get_all_mandatory_channels(session: AsyncSession, active_only: bool = False) -> List[MandatoryChannel]:
    """Get all mandatory channels, optionally filtered by active status."""
    query = select(MandatoryChannel)
    if active_only:
        query = query.where(MandatoryChannel.is_active == True)
    query = query.order_by(MandatoryChannel.order_index.asc(), MandatoryChannel.id.asc())
    result = await session.execute(query)
    return list(result.scalars().all())


async def update_mandatory_channel(
    session: AsyncSession,
    channel_id: int,
    channel_name: Optional[str] = None,
    channel_link: Optional[str] = None,
    is_active: Optional[bool] = None,
    order_index: Optional[int] = None
) -> Optional[MandatoryChannel]:
    """Update a mandatory channel."""
    channel = await get_mandatory_channel_by_id(session, channel_id)
    if not channel:
        return None
    
    if channel_name is not None:
        channel.channel_name = channel_name
    if channel_link is not None:
        channel.channel_link = channel_link
    if is_active is not None:
        channel.is_active = is_active
    if order_index is not None:
        channel.order_index = order_index
    
    await session.commit()
    await session.refresh(channel)
    return channel


async def delete_mandatory_channel(session: AsyncSession, channel_id: int) -> bool:
    """Delete a mandatory channel."""
    channel = await get_mandatory_channel_by_id(session, channel_id)
    if not channel:
        return False
    
    await session.delete(channel)
    await session.commit()
    return True


async def get_active_mandatory_channels(session: AsyncSession) -> List[MandatoryChannel]:
    """Get all active mandatory channels ordered by order_index."""
    result = await session.execute(
        select(MandatoryChannel)
        .where(MandatoryChannel.is_active == True)
        .order_by(MandatoryChannel.order_index.asc(), MandatoryChannel.id.asc())
    )
    return list(result.scalars().all())


# ============= Coin Package CRUD =============

async def create_coin_package(
    session: AsyncSession,
    package_name: str,
    coin_amount: int,
    price: float,
    original_price: Optional[float] = None,
    discount_percent: int = 0,
    stars_required: Optional[int] = None,
    payment_methods_json: Optional[str] = None,
    discount_start_date: Optional[datetime] = None,
    discount_end_date: Optional[datetime] = None,
    is_active: bool = True,
    is_visible: bool = True,
    display_order: int = 0
) -> CoinPackage:
    """Create a new coin package."""
    # Set default payment method if not provided
    if payment_methods_json is None:
        payment_methods_json = '["shaparak"]'
    
    package = CoinPackage(
        package_name=package_name,
        coin_amount=coin_amount,
        price=price,
        original_price=original_price,
        discount_percent=discount_percent,
        stars_required=stars_required,
        payment_methods_json=payment_methods_json,
        discount_start_date=discount_start_date,
        discount_end_date=discount_end_date,
        is_active=is_active,
        is_visible=is_visible,
        display_order=display_order
    )
    session.add(package)
    await session.commit()
    await session.refresh(package)
    return package


async def get_coin_package_by_id(session: AsyncSession, package_id: int) -> Optional[CoinPackage]:
    """Get coin package by ID."""
    result = await session.execute(select(CoinPackage).where(CoinPackage.id == package_id))
    return result.scalar_one_or_none()


async def get_all_coin_packages(
    session: AsyncSession,
    active_only: bool = False,
    visible_only: bool = False
) -> List[CoinPackage]:
    """Get all coin packages."""
    query = select(CoinPackage).order_by(CoinPackage.display_order.asc(), CoinPackage.coin_amount.asc())
    
    if active_only:
        query = query.where(CoinPackage.is_active == True)
    
    if visible_only:
        query = query.where(CoinPackage.is_visible == True)
    
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_visible_coin_packages(session: AsyncSession) -> List[CoinPackage]:
    """Get visible and active coin packages for users."""
    result = await session.execute(
        select(CoinPackage)
        .where(CoinPackage.is_active == True, CoinPackage.is_visible == True)
        .order_by(CoinPackage.display_order.asc(), CoinPackage.coin_amount.asc())
    )
    return list(result.scalars().all())


async def update_coin_package(
    session: AsyncSession,
    package_id: int,
    package_name: Optional[str] = None,
    coin_amount: Optional[int] = None,
    price: Optional[float] = None,
    original_price: Optional[float] = None,
    discount_percent: Optional[int] = None,
    stars_required: Optional[int] = None,
    payment_methods_json: Optional[str] = None,
    discount_start_date: Optional[datetime] = None,
    discount_end_date: Optional[datetime] = None,
    is_active: Optional[bool] = None,
    is_visible: Optional[bool] = None,
    display_order: Optional[int] = None
) -> Optional[CoinPackage]:
    """Update coin package."""
    package = await get_coin_package_by_id(session, package_id)
    
    if not package:
        return None
    
    if package_name is not None:
        package.package_name = package_name
    if coin_amount is not None:
        package.coin_amount = coin_amount
    if price is not None:
        package.price = price
    if original_price is not None:
        package.original_price = original_price
    if discount_percent is not None:
        package.discount_percent = discount_percent
    if stars_required is not None:
        package.stars_required = stars_required
    if payment_methods_json is not None:
        package.payment_methods_json = payment_methods_json
    if discount_start_date is not None:
        package.discount_start_date = discount_start_date
    if discount_end_date is not None:
        package.discount_end_date = discount_end_date
    if is_active is not None:
        package.is_active = is_active
    if is_visible is not None:
        package.is_visible = is_visible
    if display_order is not None:
        package.display_order = display_order
    
    await session.commit()
    await session.refresh(package)
    return package


async def delete_coin_package(session: AsyncSession, package_id: int) -> bool:
    """Delete coin package."""
    package = await get_coin_package_by_id(session, package_id)
    
    if not package:
        return False
    
    await session.delete(package)
    await session.commit()
    return True


async def get_user_gender_counts(session: AsyncSession) -> dict[str, int]:
    """Return counts of users grouped by gender."""
    stmt = (
        select(User.gender, func.count(User.id))
        .where(
            User.is_active == True,
            User.is_banned == False
        )
        .group_by(User.gender)
    )
    result = await session.execute(stmt)
    return {row[0] or "نامشخص": row[1] for row in result.all()}


async def get_new_user_count(session: AsyncSession, since: datetime) -> int:
    """Count users created since the provided datetime."""
    if not since:
        return 0
    stmt = select(func.count(User.id)).where(User.created_at >= since, User.is_active == True)
    result = await session.execute(stmt)
    return result.scalar() or 0


async def get_referral_count(session: AsyncSession, since: Optional[datetime] = None) -> int:
    """Count referrals optionally filtered by time."""
    stmt = select(func.count(Referral.id))
    if since:
        stmt = stmt.where(Referral.created_at >= since)
    result = await session.execute(stmt)
    return result.scalar() or 0


async def get_daily_reward_count(
    session: AsyncSession,
    since: Optional[datetime] = None
) -> int:
    """Count daily rewards optionally filtered by time."""
    stmt = select(func.count(DailyReward.id))
    if since:
        stmt = stmt.where(DailyReward.created_at >= since)
    result = await session.execute(stmt)
    return result.scalar() or 0


async def get_payment_summary(
    session: AsyncSession,
    since: Optional[datetime] = None,
    plan_only: bool = False,
    coin_only: bool = False
) -> tuple[int, float]:
    """Summarize payment transactions as count and amount."""
    filters = [
        or_(
            PaymentTransaction.status == "completed",
            PaymentTransaction.status == "success",
            PaymentTransaction.payment_status.in_(["success", "completed"])
        )
    ]
    if since:
        filters.append(PaymentTransaction.created_at >= since)
    if plan_only:
        filters.append(PaymentTransaction.plan_id.isnot(None))
    if coin_only:
        filters.append(PaymentTransaction.coin_package_id.isnot(None))
    stmt = (
        select(
            func.count(PaymentTransaction.id),
            func.coalesce(func.sum(PaymentTransaction.amount), 0.0)
        )
        .where(*filters)
    )
    result = await session.execute(stmt)
    count, total = result.one()
    return int(count or 0), float(total or 0.0)


async def get_chat_summary(session: AsyncSession) -> dict[str, int]:
    """Return counts for active and ended chats."""
    active_stmt = select(func.count(ChatRoom.id)).where(ChatRoom.is_active == True)
    ended_stmt = select(func.count(ChatRoom.id)).where(ChatRoom.ended_at.isnot(None))
    active = await session.execute(active_stmt)
    ended = await session.execute(ended_stmt)
    return {
        "active": active.scalar() or 0,
        "ended": ended.scalar() or 0,
    }


# ============= Playlist CRUD =============

async def create_user_playlist(session: AsyncSession, user_id: int, name: str = "پلی‌لیست من") -> UserPlaylist:
    """Create a playlist for a user."""
    playlist = UserPlaylist(user_id=user_id, name=name)
    session.add(playlist)
    await session.commit()
    await session.refresh(playlist)
    return playlist


async def get_user_playlist(session: AsyncSession, user_id: int) -> Optional[UserPlaylist]:
    """Get user's playlist, creating it if it doesn't exist."""
    query = select(UserPlaylist).where(UserPlaylist.user_id == user_id)
    result = await session.execute(query)
    playlist = result.scalar_one_or_none()
    
    if not playlist:
        # Create playlist if it doesn't exist
        playlist = await create_user_playlist(session, user_id)
    
    return playlist


async def get_partner_playlist(session: AsyncSession, partner_user_id: int) -> Optional[UserPlaylist]:
    """Get partner's playlist for viewing in chat."""
    query = select(UserPlaylist).where(UserPlaylist.user_id == partner_user_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def add_item_to_playlist(
    session: AsyncSession,
    playlist_id: int,
    message_type: str,
    file_id: str,
    title: Optional[str] = None,
    performer: Optional[str] = None,
    duration: Optional[int] = None,
    forwarded_from_chat_id: Optional[int] = None,
    forwarded_from_message_id: Optional[int] = None,
) -> PlaylistItem:
    """Add a music item to a playlist."""
    item = PlaylistItem(
        playlist_id=playlist_id,
        message_type=message_type,
        file_id=file_id,
        title=title,
        performer=performer,
        duration=duration,
        forwarded_from_chat_id=forwarded_from_chat_id,
        forwarded_from_message_id=forwarded_from_message_id,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def remove_item_from_playlist(session: AsyncSession, item_id: int) -> bool:
    """Remove an item from a playlist."""
    query = select(PlaylistItem).where(PlaylistItem.id == item_id)
    result = await session.execute(query)
    item = result.scalar_one_or_none()
    
    if not item:
        return False
    
    await session.delete(item)
    await session.commit()
    return True


async def get_playlist_items(
    session: AsyncSession,
    playlist_id: int,
    limit: int = 50,
    offset: int = 0,
) -> List[PlaylistItem]:
    """Get playlist items with pagination."""
    query = (
        select(PlaylistItem)
        .where(PlaylistItem.playlist_id == playlist_id)
        .order_by(PlaylistItem.added_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_playlist_item_count(session: AsyncSession, playlist_id: int) -> int:
    """Get total count of items in a playlist."""
    query = select(func.count(PlaylistItem.id)).where(PlaylistItem.playlist_id == playlist_id)
    result = await session.execute(query)
    return result.scalar() or 0


async def check_item_exists_in_playlist(session: AsyncSession, playlist_id: int, file_id: str) -> bool:
    """Check if an item with the same file_id already exists in the playlist."""
    query = select(PlaylistItem).where(
        PlaylistItem.playlist_id == playlist_id,
        PlaylistItem.file_id == file_id
    )
    result = await session.execute(query)
    return result.scalar_one_or_none() is not None


