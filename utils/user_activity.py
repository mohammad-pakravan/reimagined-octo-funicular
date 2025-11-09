"""
User activity tracking utilities.
Tracks user online/offline status using Redis.
"""
from datetime import datetime, timedelta
from typing import Optional
import redis.asyncio as redis


class UserActivityTracker:
    """Tracks user activity to determine online/offline status."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.activity_prefix = "user:activity"
        self.online_timeout_seconds = 300  # 5 minutes considered online
    
    def _get_activity_key(self, telegram_id: int) -> str:
        """Get Redis key for user activity."""
        return f"{self.activity_prefix}:{telegram_id}"
    
    async def update_activity(self, telegram_id: int):
        """Update user's last activity timestamp."""
        key = self._get_activity_key(telegram_id)
        timestamp = datetime.utcnow().timestamp()
        # Store as string since Redis decode_responses=False
        try:
            await self.redis.setex(key, self.online_timeout_seconds, str(timestamp))
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error updating activity in Redis for user {telegram_id}: {e}")
            raise
    
    async def is_online(self, telegram_id: int) -> bool:
        """Check if user is currently online."""
        key = self._get_activity_key(telegram_id)
        exists = await self.redis.exists(key)
        return bool(exists)
    
    async def get_last_activity(self, telegram_id: int) -> Optional[datetime]:
        """Get user's last activity timestamp."""
        key = self._get_activity_key(telegram_id)
        timestamp_str = await self.redis.get(key)
        
        if timestamp_str:
            try:
                # Handle both bytes and string
                if isinstance(timestamp_str, bytes):
                    timestamp_str = timestamp_str.decode('utf-8')
                timestamp = float(timestamp_str)
                return datetime.utcfromtimestamp(timestamp)
            except (ValueError, TypeError) as e:
                print(f"Error parsing timestamp: {e}, value: {timestamp_str}")
                return None
        
        return None


def format_last_seen(last_activity: Optional[datetime]) -> str:
    """
    Format last seen time in Persian.
    
    Args:
        last_activity: Last activity datetime or None
        
    Returns:
        Formatted string like "آنلاین" or "یک ساعت پیش"
    """
    if last_activity is None:
        return "🔴 آفلاین"
    
    now = datetime.utcnow()
    time_diff = now - last_activity
    
    # If within 5 minutes, consider online
    if time_diff.total_seconds() < 300:
        return "🟢 آنلاین"
    
    # Format time difference in Persian
    total_seconds = int(time_diff.total_seconds())
    
    if total_seconds < 60:
        return "🔴 چند لحظه پیش"
    elif total_seconds < 3600:  # Less than 1 hour
        minutes = total_seconds // 60
        if minutes == 1:
            return "🔴 یک دقیقه پیش"
        else:
            return f"🔴 {minutes} دقیقه پیش"
    elif total_seconds < 86400:  # Less than 1 day
        hours = total_seconds // 3600
        if hours == 1:
            return "🔴 یک ساعت پیش"
        else:
            return f"🔴 {hours} ساعت پیش"
    elif total_seconds < 604800:  # Less than 1 week
        days = total_seconds // 86400
        if days == 1:
            return "🔴 یک روز پیش"
        else:
            return f"🔴 {days} روز پیش"
    elif total_seconds < 2592000:  # Less than 1 month
        weeks = total_seconds // 604800
        if weeks == 1:
            return "🔴 یک هفته پیش"
        else:
            return f"🔴 {weeks} هفته پیش"
    else:
        months = total_seconds // 2592000
        if months == 1:
            return "🔴 یک ماه پیش"
        elif months < 12:
            return f"🔴 {months} ماه پیش"
        else:
            years = months // 12
            if years == 1:
                return "🔴 یک سال پیش"
            else:
                return f"🔴 {years} سال پیش"

