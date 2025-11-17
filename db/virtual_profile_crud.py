"""
CRUD operations for virtual profiles.
Separate file for better organization.
"""
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from db.models import VirtualProfile, User
import random
import hashlib
import time
import logging

logger = logging.getLogger(__name__)


async def get_available_virtual_profile(
    session: AsyncSession,
    user_age: Optional[int] = None,
    user_city: Optional[str] = None,
    user_province: Optional[str] = None,
    exclude_profile_ids: Optional[List[int]] = None,
    gender: str = "female",  # "female" or "male"
) -> Optional[VirtualProfile]:
    """
    Get an available virtual profile from the database.
    Profiles used in last 3 hours by this specific user are excluded.
    """
    from sqlalchemy.orm import selectinload
    from db.models import User
    
    query = select(VirtualProfile).join(
        User, VirtualProfile.user_id == User.id
    ).options(
        selectinload(VirtualProfile.user)  # Eager load the user relationship
    ).where(
        VirtualProfile.is_active == True,
        User.gender == gender  # Filter by gender
    )
    
    # Filter by age if provided (±3 years)
    if user_age and 18 <= user_age <= 35:
        min_age = max(18, user_age - 3)
        max_age = min(35, user_age + 3)
        query = query.where(
            VirtualProfile.age >= min_age,
            VirtualProfile.age <= max_age
        )
    
    # Filter by city/province if provided
    if user_city:
        query = query.where(VirtualProfile.city == user_city)
    if user_province:
        query = query.where(VirtualProfile.province == user_province)
    
    # Exclude recently used profiles
    if exclude_profile_ids:
        query = query.where(VirtualProfile.id.notin_(exclude_profile_ids))
    
    # Order by: least recently used first (NULLs first in MySQL-compatible way), then by usage count (least used first)
    # MySQL doesn't support NULLS FIRST syntax, so we use IS NULL DESC trick
    from sqlalchemy import case
    query = query.order_by(
        case((VirtualProfile.last_used_at.is_(None), 0), else_=1),  # NULL values first
        VirtualProfile.last_used_at.asc(),
        VirtualProfile.usage_count.asc()
    )
    
    result = await session.execute(query)
    profiles = list(result.scalars().all())
    
    logger.info(f"Found {len(profiles)} available virtual profiles with gender={gender}, age filter={user_age is not None}, city={user_city}, province={user_province}, excluded={len(exclude_profile_ids or [])}")
    
    if not profiles:
        logger.warning(f"No available virtual profiles found with gender={gender}")
        return None
    
    # If we have multiple profiles, prefer ones not used recently
    # Get profiles not used in last 3 hours
    three_hours_ago = datetime.utcnow() - timedelta(hours=3)
    fresh_profiles = [
        p for p in profiles 
        if p.last_used_at is None or p.last_used_at < three_hours_ago
    ]
    
    if fresh_profiles:
        # Randomly select from fresh profiles (to add variety)
        return random.choice(fresh_profiles[:min(5, len(fresh_profiles))])
    else:
        # All profiles were used recently, get the least recently used one
        return profiles[0] if profiles else None


async def mark_virtual_profile_as_used(
    session: AsyncSession,
    profile_id: int
) -> None:
    """Mark a virtual profile as used (update usage count and last used timestamp)."""
    profile = await session.get(VirtualProfile, profile_id)
    if profile:
        profile.usage_count += 1
        profile.last_used_at = datetime.utcnow()
        await session.commit()


async def create_virtual_profile_from_real_users(
    session: AsyncSession,
    user_age: Optional[int] = None,
    user_city: Optional[str] = None,
    user_province: Optional[str] = None,
    gender: str = "female",  # "female" or "male"
) -> VirtualProfile:
    """
    Create a new virtual profile by mixing data from real users.
    Ensures uniqueness of name, image, and location combination for profiles created in last 3 hours.
    
    Args:
        gender: "female" or "male" - the gender of virtual profile to create
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Get real users of specified gender from database
    query = select(User).where(
        User.gender == gender,
        User.is_active == True,
        User.is_banned == False,
        User.display_name.isnot(None),
    )
    
    # Filter by age range if user_age provided
    if user_age and 18 <= user_age <= 35:
        min_age = max(18, user_age - 3)
        max_age = min(35, user_age + 3)
        query = query.where(User.age >= min_age, User.age <= max_age)
    else:
        query = query.where(User.age >= 18, User.age <= 35)
    
    # Filter by city/province if provided - to ensure matching location
    if user_city:
        query = query.where(User.city == user_city)
    if user_province:
        query = query.where(User.province == user_province)
    
    query = query.limit(50)
    result = await session.execute(query)
    real_users = list(result.scalars().all())
    
    logger.info(f"Found {len(real_users)} real {gender} users to create virtual profile from (age_filter={user_age is not None}, city={user_city}, province={user_province})")
    
    if not real_users:
        raise ValueError(f"No real {gender} users found to create virtual profile from (age_filter={user_age is not None}, city={user_city}, province={user_province})")
    
    # Get existing virtual profiles from last 3 hours
    three_hours_ago = datetime.utcnow() - timedelta(hours=3)
    
    # 1. Get display name from random real user
    # With 1000+ real users, we have plenty of variety without adding suffixes
    display_name = random.choice(real_users).display_name or "کاربر"
    
    logger.info(f"Creating virtual profile with name: {display_name}")
    
    # 2. Get age with random variation
    if user_age and 18 <= user_age <= 35:
        # Add random variation within ±3 years
        min_age = max(18, user_age - 3)
        max_age = min(35, user_age + 3)
        age = random.randint(min_age, max_age)
    else:
        # Random age between 18-30
        age = random.randint(18, 30)
    
    # 3. Get city/province from SAME user (to ensure consistency)
    # IMPORTANT: Only use users who have BOTH city AND province (not None)
    users_with_location = [u for u in real_users if u.city and u.province]
    
    if not users_with_location:
        # Fallback: if no users have both, leave them empty (None)
        logger.warning(f"No users found with both city and province, leaving location empty")
        city = None
        province = None
    else:
        # Select a random user who has BOTH city and province
        location_user = random.choice(users_with_location)
        city = location_user.city
        province = location_user.province
        logger.info(f"Selected location from user: city={city}, province={province}")
    
    # 4. Get profile image (allow duplicates if needed)
    image_users = [u for u in real_users if u.profile_image_url]
    
    logger.info(f"Creating virtual profile: {len(image_users)} users with images available")
    
    profile_image_url = None
    if image_users:
        # Simply select a random image (duplicates are OK since names are unique)
        profile_image_url = random.choice(image_users).profile_image_url
    else:
        logger.warning(f"No users with images found for gender={gender}")
    
    # 5. Get randomized like count (between 0 and 30)
    like_count = random.randint(0, 30)
    
    # Generate unique profile_id and telegram_id
    virtual_telegram_id = -int(time.time() * 1000) - random.randint(1000, 9999)
    profile_id = hashlib.md5(f"virtual_{virtual_telegram_id}".encode()).hexdigest()[:12]
    
    # First create User entry with is_virtual=True
    virtual_user = User(
        telegram_id=virtual_telegram_id,
        username=None,
        display_name=display_name,
        gender=gender,  # Use specified gender
        age=age,
        province=province,
        city=city,
        profile_image_url=profile_image_url,
        like_count=like_count,
        profile_id=profile_id,
        is_virtual=True,
        is_active=True,
        is_banned=False,
        last_seen=datetime.utcnow(),
    )
    session.add(virtual_user)
    await session.flush()  # Get the user.id
    
    # Now create VirtualProfile entry linked to User
    virtual_profile = VirtualProfile(
        user_id=virtual_user.id,
        display_name=display_name,
        age=age,
        province=province,
        city=city,
        profile_image_url=profile_image_url,
        like_count=like_count,
        profile_id=profile_id,
        is_active=True,
        usage_count=0,
        last_used_at=None,
    )
    
    session.add(virtual_profile)
    await session.commit()
    await session.refresh(virtual_profile)
    await session.refresh(virtual_user)
    
    # Eager load the user relationship to prevent lazy loading issues
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select as sql_select
    reload_query = sql_select(VirtualProfile).options(
        selectinload(VirtualProfile.user)
    ).where(VirtualProfile.id == virtual_profile.id)
    result = await session.execute(reload_query)
    virtual_profile = result.scalars().first()
    
    logger.info(f"✅ Created virtual {gender} profile ID={virtual_profile.id}, user_id={virtual_user.id}, telegram_id={virtual_telegram_id}: name='{display_name}', age={age}, city='{city}', province='{province}', has_image={profile_image_url is not None}")
    
    return virtual_profile


async def get_or_create_virtual_profile(
    session: AsyncSession,
    user_age: Optional[int] = None,
    user_city: Optional[str] = None,
    user_province: Optional[str] = None,
    exclude_profile_ids: Optional[List[int]] = None,
    activity_tracker = None,
    gender: str = "female",  # "female" or "male"
    always_create_new: bool = True,  # Always create new profile for maximum variety
) -> VirtualProfile:
    """
    Get an available virtual profile or create a new one if none available.
    This is the main function to use for getting virtual profiles.
    
    With always_create_new=True, we always create a fresh profile to ensure maximum variety.
    """
    # If always_create_new is True, skip checking for existing profiles and create new one
    if not always_create_new:
        # Try to get existing profile
        profile = await get_available_virtual_profile(
            session,
            user_age=user_age,
            user_city=user_city,
            user_province=user_province,
            exclude_profile_ids=exclude_profile_ids,
            gender=gender  # Filter by desired gender
        )
        
        if profile:
            # Mark as used
            await mark_virtual_profile_as_used(session, profile.id)
            
            # Update last_seen for virtual user and set online status
            # Get the user separately to avoid lazy loading issues
            from db.models import User
            virtual_user = await session.get(User, profile.user_id)
            if virtual_user:
                virtual_user.last_seen = datetime.utcnow()
                await session.commit()
                
                # Set online status in Redis (outside of SQLAlchemy session)
                if activity_tracker:
                    try:
                        await activity_tracker.update_activity(virtual_user.telegram_id, db_session=None)
                    except Exception:
                        pass
            
            return profile
    
    # Create new profile (either because always_create_new=True or no existing profile found)
    logger.info(f"Creating NEW virtual profile (always_create_new={always_create_new}, gender={gender})")
    profile = await create_virtual_profile_from_real_users(
        session,
        user_age=user_age,
        user_city=user_city,
        user_province=user_province,
        gender=gender  # Use specified gender
    )
    
    # Mark as used immediately
    await mark_virtual_profile_as_used(session, profile.id)
    
    # Set online status for newly created profile
    # Get the user separately to avoid lazy loading issues
    from db.models import User
    virtual_user = await session.get(User, profile.user_id)
    if virtual_user and activity_tracker:
        try:
            await activity_tracker.update_activity(virtual_user.telegram_id, db_session=None)
        except Exception:
            pass
    
    return profile


async def get_virtual_profile_count(session: AsyncSession) -> int:
    """Get total count of virtual profiles."""
    result = await session.execute(select(func.count(VirtualProfile.id)))
    return result.scalar() or 0


async def cleanup_old_virtual_profiles(session: AsyncSession, days: int = 30) -> int:
    """
    Clean up old virtual profiles that haven't been used in X days.
    Returns count of deleted profiles.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Delete profiles not used in last X days
    result = await session.execute(
        select(VirtualProfile).where(
            or_(
                VirtualProfile.last_used_at < cutoff_date,
                and_(
                    VirtualProfile.last_used_at.is_(None),
                    VirtualProfile.created_at < cutoff_date
                )
            )
        )
    )
    
    profiles_to_delete = result.scalars().all()
    count = len(profiles_to_delete)
    
    for profile in profiles_to_delete:
        await session.delete(profile)
    
    await session.commit()
    
    return count

