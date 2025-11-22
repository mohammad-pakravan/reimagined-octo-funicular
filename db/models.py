"""
SQLAlchemy models for the database.
Defines User, ChatRoom, PremiumSubscription, and Report models.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, ForeignKey, Text, Float, Index, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class VirtualProfile(Base):
    """Virtual profile model for engagement (fake profiles for matchmaking)."""
    __tablename__ = "virtual_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)  # Link to User table
    display_name = Column(String(255), nullable=False)  # نام نمایشی
    age = Column(Integer, nullable=False)
    province = Column(String(255), nullable=False)  # استان
    city = Column(String(255), nullable=False)  # شهر
    profile_image_url = Column(String(512), nullable=True)  # عکس پروفایل
    like_count = Column(Integer, default=0, nullable=False)  # تعداد لایک‌ها
    profile_id = Column(String(50), unique=True, nullable=False, index=True)  # Public profile ID
    
    # Tracking
    is_active = Column(Boolean, default=True, nullable=False)
    usage_count = Column(Integer, default=0, nullable=False)  # تعداد دفعات استفاده
    last_used_at = Column(DateTime, nullable=True)  # آخرین بار استفاده
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship
    user = relationship("User", back_populates="virtual_profile")


class User(Base):
    """User model for storing user profiles and information."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String(255), nullable=True)
    display_name = Column(String(255), nullable=True)  # نام نمایشی کاربر
    
    # Profile information
    gender = Column(String(20), nullable=True)  # 'male', 'female', 'other'
    age = Column(Integer, nullable=True)
    province = Column(String(255), nullable=True)  # استان
    city = Column(String(255), nullable=True)
    profile_image_url = Column(String(512), nullable=True)  # MinIO URL or Telegram file_id
    like_count = Column(Integer, default=0, nullable=False)  # تعداد لایک‌ها
    profile_id = Column(String(50), unique=True, nullable=True, index=True)  # Public profile ID (e.g., /user_15e1576abc70)
    
    # Premium status
    is_premium = Column(Boolean, default=False, nullable=False)
    premium_expires_at = Column(DateTime, nullable=True)
    
    # Account status
    is_banned = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_virtual = Column(Boolean, default=False, nullable=False)  # Virtual/bot profile for engagement
    
    # Chat filter preferences (default settings)
    default_chat_filter_same_age = Column(Boolean, default=True, nullable=False)  # Default: filter by same age (±3 years)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_seen = Column(DateTime, nullable=True)  # آخرین بازدید کاربر
    
    # Relationships
    chat_rooms_user1 = relationship("ChatRoom", foreign_keys="ChatRoom.user1_id", back_populates="user1")
    chat_rooms_user2 = relationship("ChatRoom", foreign_keys="ChatRoom.user2_id", back_populates="user2")
    premium_subscriptions = relationship("PremiumSubscription", back_populates="user")
    reports_sent = relationship("Report", foreign_keys="Report.reporter_id", back_populates="reporter")
    reports_received = relationship("Report", foreign_keys="Report.reported_id", back_populates="reported")
    likes_given = relationship("Like", foreign_keys="Like.user_id", back_populates="user")
    likes_received = relationship("Like", foreign_keys="Like.liked_user_id", back_populates="liked_user")
    follows_given = relationship("Follow", foreign_keys="Follow.follower_id", back_populates="follower")
    follows_received = relationship("Follow", foreign_keys="Follow.followed_id", back_populates="followed")
    blocks_given = relationship("Block", foreign_keys="Block.blocker_id", back_populates="blocker")
    blocks_received = relationship("Block", foreign_keys="Block.blocked_id", back_populates="blocked")
    direct_messages_sent = relationship("DirectMessage", foreign_keys="DirectMessage.sender_id", back_populates="sender")
    direct_messages_received = relationship("DirectMessage", foreign_keys="DirectMessage.receiver_id", back_populates="receiver")
    # Engagement relationships
    user_points = relationship("UserPoints", back_populates="user", uselist=False)
    points_history = relationship("PointsHistory", foreign_keys="PointsHistory.user_id", back_populates="user")
    daily_rewards = relationship("DailyReward", back_populates="user")
    referral_code = relationship("UserReferralCode", back_populates="user", uselist=False)
    referrals_sent = relationship("Referral", foreign_keys="Referral.referrer_id", back_populates="referrer")
    referrals_received = relationship("Referral", foreign_keys="Referral.referred_id", back_populates="referred")
    badges = relationship("UserBadge", back_populates="user")
    achievements = relationship("UserAchievement", back_populates="user")
    challenges = relationship("UserChallenge", back_populates="user")
    virtual_profile = relationship("VirtualProfile", back_populates="user", uselist=False)
    playlist = relationship("UserPlaylist", back_populates="user", uselist=False)

    __table_args__ = (
        Index('idx_telegram_id', 'telegram_id'),
        Index('idx_is_premium', 'is_premium'),
        Index('idx_is_banned', 'is_banned'),
    )

    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.username})>"


class ChatRoom(Base):
    """Chat room model for storing active chat sessions."""
    __tablename__ = "chat_rooms"

    id = Column(Integer, primary_key=True, index=True)
    user1_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user2_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Chat status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    
    # Video call information
    video_call_room_id = Column(String(255), nullable=True)
    video_call_link = Column(String(512), nullable=True)
    
    # Relationships
    user1 = relationship("User", foreign_keys=[user1_id], back_populates="chat_rooms_user1")
    user2 = relationship("User", foreign_keys=[user2_id], back_populates="chat_rooms_user2")

    __table_args__ = (
        Index('idx_user1_id', 'user1_id'),
        Index('idx_user2_id', 'user2_id'),
        Index('idx_is_active', 'is_active'),
        Index('idx_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<ChatRoom(id={self.id}, user1_id={self.user1_id}, user2_id={self.user2_id}, is_active={self.is_active})>"


class PremiumSubscription(Base):
    """Premium subscription model for tracking premium purchases."""
    __tablename__ = "premium_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Payment information
    provider = Column(String(50), nullable=False)  # 'myket', 'local', etc.
    transaction_id = Column(String(255), unique=True, nullable=False)
    amount = Column(Float, nullable=False)
    
    # Subscription details
    start_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    end_date = Column(DateTime, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="premium_subscriptions")

    __table_args__ = (
        Index('idx_user_id', 'user_id'),
        Index('idx_transaction_id', 'transaction_id'),
        Index('idx_is_active', 'is_active'),
    )

    def __repr__(self):
        return f"<PremiumSubscription(id={self.id}, user_id={self.user_id}, provider={self.provider})>"


class Report(Base):
    """Report model for storing user reports."""
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reported_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Report details
    reason = Column(Text, nullable=True)
    report_type = Column(String(50), nullable=True)  # 'spam', 'harassment', 'inappropriate', etc.
    
    # Status
    is_resolved = Column(Boolean, default=False, nullable=False)
    resolved_by = Column(Integer, nullable=True)  # Admin user ID
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    
    # Relationships
    reporter = relationship("User", foreign_keys=[reporter_id], back_populates="reports_sent")
    reported = relationship("User", foreign_keys=[reported_id], back_populates="reports_received")

    __table_args__ = (
        Index('idx_reporter_id', 'reporter_id'),
        Index('idx_reported_id', 'reported_id'),
        Index('idx_is_resolved', 'is_resolved'),
    )

    def __repr__(self):
        return f"<Report(id={self.id}, reporter_id={self.reporter_id}, reported_id={self.reported_id})>"


class Like(Base):
    """Like model for storing user likes."""
    __tablename__ = "likes"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # User who liked
    liked_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # User who was liked
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="likes_given")
    liked_user = relationship("User", foreign_keys=[liked_user_id], back_populates="likes_received")
    
    __table_args__ = (
        Index('idx_user_id', 'user_id'),
        Index('idx_liked_user_id', 'liked_user_id'),
        Index('idx_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Like(id={self.id}, user_id={self.user_id}, liked_user_id={self.liked_user_id})>"


class Follow(Base):
    """Follow model for storing user follows."""
    __tablename__ = "follows"
    
    id = Column(Integer, primary_key=True, index=True)
    follower_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # User who follows
    followed_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # User who is followed
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    follower = relationship("User", foreign_keys=[follower_id], back_populates="follows_given")
    followed = relationship("User", foreign_keys=[followed_id], back_populates="follows_received")
    
    __table_args__ = (
        Index('idx_follower_id', 'follower_id'),
        Index('idx_followed_id', 'followed_id'),
        Index('idx_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Follow(id={self.id}, follower_id={self.follower_id}, followed_id={self.followed_id})>"


class Block(Base):
    """Block model for storing user blocks."""
    __tablename__ = "blocks"
    
    id = Column(Integer, primary_key=True, index=True)
    blocker_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # User who blocked
    blocked_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # User who is blocked
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    blocker = relationship("User", foreign_keys=[blocker_id], back_populates="blocks_given")
    blocked = relationship("User", foreign_keys=[blocked_id], back_populates="blocks_received")
    
    __table_args__ = (
        Index('idx_blocker_id', 'blocker_id'),
        Index('idx_blocked_id', 'blocked_id'),
        Index('idx_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Block(id={self.id}, blocker_id={self.blocker_id}, blocked_id={self.blocked_id})>"


class DirectMessage(Base):
    """Direct message model for storing direct messages between users."""
    __tablename__ = "direct_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # User who sent
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # User who receives
    message_text = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    is_rejected = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    sender = relationship("User", foreign_keys=[sender_id], back_populates="direct_messages_sent")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="direct_messages_received")
    
    __table_args__ = (
        Index('idx_sender_id', 'sender_id'),
        Index('idx_receiver_id', 'receiver_id'),
        Index('idx_is_read', 'is_read'),
        Index('idx_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<DirectMessage(id={self.id}, sender_id={self.sender_id}, receiver_id={self.receiver_id})>"


class ChatEndNotification(Base):
    """Chat end notification model for storing user requests to be notified when someone's chat ends."""
    __tablename__ = "chat_end_notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    watcher_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # User who wants to be notified
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # User whose chat end will trigger notification
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    watcher = relationship("User", foreign_keys=[watcher_id])
    target_user = relationship("User", foreign_keys=[target_user_id])
    
    __table_args__ = (
        Index('idx_watcher_id', 'watcher_id'),
        Index('idx_target_user_id', 'target_user_id'),
        Index('idx_created_at', 'created_at'),
        # Unique constraint: one user can only have one notification request per target user
        Index('idx_watcher_target_unique', 'watcher_id', 'target_user_id', unique=True),
    )
    
    def __repr__(self):
        return f"<ChatEndNotification(id={self.id}, watcher_id={self.watcher_id}, target_user_id={self.target_user_id})>"


# ============= Engagement Features Models =============

class UserPoints(Base):
    """User points model for tracking user points balance."""
    __tablename__ = "user_points"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    points = Column(Integer, default=0, nullable=False)
    total_earned = Column(Integer, default=0, nullable=False)
    total_spent = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="user_points")
    
    __table_args__ = (
        Index('idx_user_id', 'user_id'),
        Index('idx_points', 'points'),
    )
    
    def __repr__(self):
        return f"<UserPoints(id={self.id}, user_id={self.user_id}, points={self.points})>"


class PointsHistory(Base):
    """Points history model for tracking all point transactions."""
    __tablename__ = "points_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    points = Column(Integer, nullable=False)
    transaction_type = Column(String(50), nullable=False)  # 'earned', 'spent', 'reward', 'purchase', 'referral'
    source = Column(String(100), nullable=False)  # 'daily_login', 'chat_success', 'mutual_like', 'referral'
    description = Column(Text, nullable=True)
    related_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="points_history")
    related_user = relationship("User", foreign_keys=[related_user_id])
    
    __table_args__ = (
        Index('idx_user_id', 'user_id'),
        Index('idx_transaction_type', 'transaction_type'),
        Index('idx_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<PointsHistory(id={self.id}, user_id={self.user_id}, points={self.points}, type={self.transaction_type})>"


class DailyReward(Base):
    """Daily reward model for tracking daily login rewards."""
    __tablename__ = "daily_rewards"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reward_date = Column(Date, nullable=False)
    points_rewarded = Column(Integer, nullable=False)
    streak_count = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="daily_rewards")
    
    __table_args__ = (
        Index('idx_user_id', 'user_id'),
        Index('idx_reward_date', 'reward_date'),
        Index('idx_streak_count', 'streak_count'),
        Index('unique_user_date', 'user_id', 'reward_date', unique=True),
    )
    
    def __repr__(self):
        return f"<DailyReward(id={self.id}, user_id={self.user_id}, date={self.reward_date}, streak={self.streak_count})>"


class UserReferralCode(Base):
    """User referral code model for storing each user's referral code."""
    __tablename__ = "user_referral_codes"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    referral_code = Column(String(50), nullable=False, unique=True)
    usage_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="referral_code")
    
    __table_args__ = (
        Index('idx_user_id', 'user_id'),
    )
    
    def __repr__(self):
        return f"<UserReferralCode(id={self.id}, user_id={self.user_id}, code={self.referral_code})>"


class Referral(Base):
    """Referral model for tracking referral relationships."""
    __tablename__ = "referrals"
    
    id = Column(Integer, primary_key=True, index=True)
    referrer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    referred_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    referral_code = Column(String(50), nullable=False)
    points_rewarded_referrer = Column(Integer, default=0, nullable=False)
    points_rewarded_referred = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    referrer = relationship("User", foreign_keys=[referrer_id], back_populates="referrals_sent")
    referred = relationship("User", foreign_keys=[referred_id], back_populates="referrals_received")
    
    __table_args__ = (
        Index('idx_referrer_id', 'referrer_id'),
        Index('idx_referred_id', 'referred_id'),
        Index('unique_referral', 'referrer_id', 'referred_id', unique=True),
        Index('unique_referral_code', 'referral_code'),
    )
    
    def __repr__(self):
        return f"<Referral(id={self.id}, referrer_id={self.referrer_id}, referred_id={self.referred_id})>"


class Badge(Base):
    """Badge model for defining available badges."""
    __tablename__ = "badges"
    
    id = Column(Integer, primary_key=True, index=True)
    badge_key = Column(String(50), nullable=False, unique=True)
    badge_name = Column(String(100), nullable=False)
    badge_description = Column(Text, nullable=True)
    badge_icon = Column(String(20), nullable=True)
    badge_type = Column(String(50), nullable=False)  # 'achievement', 'milestone', 'special'
    required_points = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user_badges = relationship("UserBadge", back_populates="badge")
    
    __table_args__ = (
        Index('idx_badge_key', 'badge_key'),
        Index('idx_badge_type', 'badge_type'),
    )
    
    def __repr__(self):
        return f"<Badge(id={self.id}, badge_key={self.badge_key}, name={self.badge_name})>"


class UserBadge(Base):
    """User badge model for tracking which badges users have earned."""
    __tablename__ = "user_badges"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    badge_id = Column(Integer, ForeignKey("badges.id"), nullable=False)
    earned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="badges")
    badge = relationship("Badge", back_populates="user_badges")
    
    __table_args__ = (
        Index('idx_user_id', 'user_id'),
        Index('idx_badge_id', 'badge_id'),
        Index('idx_earned_at', 'earned_at'),
        Index('unique_user_badge', 'user_id', 'badge_id', unique=True),
    )
    
    def __repr__(self):
        return f"<UserBadge(id={self.id}, user_id={self.user_id}, badge_id={self.badge_id})>"


class Achievement(Base):
    """Achievement model for defining achievement types."""
    __tablename__ = "achievements"
    
    id = Column(Integer, primary_key=True, index=True)
    achievement_key = Column(String(50), nullable=False, unique=True)
    achievement_name = Column(String(100), nullable=False)
    achievement_description = Column(Text, nullable=True)
    achievement_type = Column(String(50), nullable=False)  # 'chat_count', 'like_count', 'streak', 'referral'
    target_value = Column(Integer, nullable=False)
    points_reward = Column(Integer, default=0, nullable=False)
    badge_id = Column(Integer, ForeignKey("badges.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    badge = relationship("Badge")
    user_achievements = relationship("UserAchievement", back_populates="achievement")
    
    __table_args__ = (
        Index('idx_achievement_key', 'achievement_key'),
        Index('idx_achievement_type', 'achievement_type'),
    )
    
    def __repr__(self):
        return f"<Achievement(id={self.id}, achievement_key={self.achievement_key}, name={self.achievement_name})>"


class UserAchievement(Base):
    """User achievement model for tracking user progress towards achievements."""
    __tablename__ = "user_achievements"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    achievement_id = Column(Integer, ForeignKey("achievements.id"), nullable=False)
    current_progress = Column(Integer, default=0, nullable=False)
    is_completed = Column(Boolean, default=False, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="achievements")
    achievement = relationship("Achievement", back_populates="user_achievements")
    
    __table_args__ = (
        Index('idx_user_id', 'user_id'),
        Index('idx_achievement_id', 'achievement_id'),
        Index('idx_is_completed', 'is_completed'),
        Index('unique_user_achievement', 'user_id', 'achievement_id', unique=True),
    )
    
    def __repr__(self):
        return f"<UserAchievement(id={self.id}, user_id={self.user_id}, achievement_id={self.achievement_id}, progress={self.current_progress})>"


class WeeklyChallenge(Base):
    """Weekly challenge model for defining weekly challenges."""
    __tablename__ = "weekly_challenges"
    
    id = Column(Integer, primary_key=True, index=True)
    challenge_key = Column(String(50), nullable=False, unique=True)
    challenge_name = Column(String(100), nullable=False)
    challenge_description = Column(Text, nullable=True)
    challenge_type = Column(String(50), nullable=False)  # 'chat_count', 'like_count', 'streak'
    target_value = Column(Integer, nullable=False)
    points_reward = Column(Integer, nullable=False)
    week_start_date = Column(Date, nullable=False)
    week_end_date = Column(Date, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user_challenges = relationship("UserChallenge", back_populates="challenge")
    
    __table_args__ = (
        Index('idx_challenge_key', 'challenge_key'),
        Index('idx_week_dates', 'week_start_date', 'week_end_date'),
        Index('idx_is_active', 'is_active'),
    )
    
    def __repr__(self):
        return f"<WeeklyChallenge(id={self.id}, challenge_key={self.challenge_key}, name={self.challenge_name})>"


class UserChallenge(Base):
    """User challenge model for tracking user progress in weekly challenges."""
    __tablename__ = "user_challenges"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("weekly_challenges.id"), nullable=False)
    current_progress = Column(Integer, default=0, nullable=False)
    is_completed = Column(Boolean, default=False, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    points_rewarded = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="challenges")
    challenge = relationship("WeeklyChallenge", back_populates="user_challenges")
    
    __table_args__ = (
        Index('idx_user_id', 'user_id'),
        Index('idx_challenge_id', 'challenge_id'),
        Index('idx_is_completed', 'is_completed'),
        Index('unique_user_challenge', 'user_id', 'challenge_id', unique=True),
    )
    
    def __repr__(self):
        return f"<UserChallenge(id={self.id}, user_id={self.user_id}, challenge_id={self.challenge_id}, progress={self.current_progress})>"


# ============= Admin Features Models =============

class AdminReferralLink(Base):
    """Admin referral link model for tracking admin-created referral links."""
    __tablename__ = "admin_referral_links"
    
    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(BigInteger, nullable=False, index=True)  # Telegram ID of admin
    link_code = Column(String(50), nullable=False, unique=True, index=True)
    link_url = Column(String(512), nullable=False)
    description = Column(Text, nullable=True)
    click_count = Column(Integer, default=0, nullable=False)
    signup_count = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    clicks = relationship("AdminReferralLinkClick", back_populates="link", cascade="all, delete-orphan")
    signups = relationship("AdminReferralLinkSignup", back_populates="link", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<AdminReferralLink(id={self.id}, link_code={self.link_code}, clicks={self.click_count}, signups={self.signup_count})>"


class AdminReferralLinkClick(Base):
    """Track individual clicks on admin referral links."""
    __tablename__ = "admin_referral_link_clicks"
    
    id = Column(Integer, primary_key=True, index=True)
    link_id = Column(Integer, ForeignKey("admin_referral_links.id"), nullable=False, index=True)
    telegram_id = Column(BigInteger, nullable=True, index=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    clicked_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    link = relationship("AdminReferralLink", back_populates="clicks")
    
    __table_args__ = (
        Index('idx_link_id', 'link_id'),
        Index('idx_clicked_at', 'clicked_at'),
    )
    
    def __repr__(self):
        return f"<AdminReferralLinkClick(id={self.id}, link_id={self.link_id}, telegram_id={self.telegram_id})>"


class AdminReferralLinkSignup(Base):
    """Track signups via admin referral links."""
    __tablename__ = "admin_referral_link_signups"
    
    id = Column(Integer, primary_key=True, index=True)
    link_id = Column(Integer, ForeignKey("admin_referral_links.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    clicked_at = Column(DateTime, nullable=True)
    signed_up_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    link = relationship("AdminReferralLink", back_populates="signups")
    user = relationship("User")
    
    __table_args__ = (
        Index('idx_link_id', 'link_id'),
        Index('idx_user_id', 'user_id'),
        Index('idx_signed_up_at', 'signed_up_at'),
        Index('unique_user_link', 'link_id', 'user_id', unique=True),
    )
    
    def __repr__(self):
        return f"<AdminReferralLinkSignup(id={self.id}, link_id={self.link_id}, user_id={self.user_id})>"


class CoinSetting(Base):
    """Coin settings for premium conversion (admin configurable)."""
    __tablename__ = "coin_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    premium_days = Column(Integer, nullable=False, unique=True, index=True)
    coins_required = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index('idx_premium_days', 'premium_days'),
        Index('idx_is_active', 'is_active'),
    )
    
    def __repr__(self):
        return f"<CoinSetting(id={self.id}, premium_days={self.premium_days}, coins_required={self.coins_required})>"


class CoinRewardSetting(Base):
    """Coin reward settings for different activities (admin configurable)."""
    __tablename__ = "coin_reward_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    activity_type = Column(String(50), nullable=False, unique=True, index=True)  # 'daily_login', 'chat_success', 'mutual_like', 'referral_referrer', 'referral_referred'
    coins_amount = Column(Integer, nullable=False)  # Amount of coins to award
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    description = Column(String(200), nullable=True)  # Human-readable description
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index('idx_activity_type', 'activity_type'),
        Index('idx_is_active', 'is_active'),
    )
    
    def __repr__(self):
        return f"<CoinRewardSetting(id={self.id}, activity_type={self.activity_type}, coins_amount={self.coins_amount})>"


class BroadcastMessage(Base):
    """Broadcast message model for storing broadcast messages with statistics."""
    __tablename__ = "broadcast_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(BigInteger, nullable=False, index=True)  # Telegram ID of admin
    message_type = Column(String(50), nullable=False)  # 'text', 'photo', 'video', 'document', 'forward', etc.
    message_text = Column(Text, nullable=True)
    message_file_id = Column(String(512), nullable=True)  # Telegram file_id
    message_caption = Column(Text, nullable=True)
    forwarded_from_chat_id = Column(BigInteger, nullable=True)  # If forwarded
    forwarded_from_message_id = Column(Integer, nullable=True)  # If forwarded
    sent_count = Column(Integer, default=0, nullable=False)
    failed_count = Column(Integer, default=0, nullable=False)
    opened_count = Column(Integer, default=0, nullable=False)
    delay_seconds = Column(Float, default=0.067, nullable=False)  # Delay between messages in seconds (default ~15 msg/sec)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    receipts = relationship("BroadcastMessageReceipt", back_populates="broadcast", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_admin_id', 'admin_id'),
        Index('idx_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<BroadcastMessage(id={self.id}, message_type={self.message_type}, sent={self.sent_count}, failed={self.failed_count})>"


class BroadcastMessageReceipt(Base):
    """Track individual broadcast message deliveries."""
    __tablename__ = "broadcast_message_receipts"
    
    id = Column(Integer, primary_key=True, index=True)
    broadcast_id = Column(Integer, ForeignKey("broadcast_messages.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    telegram_message_id = Column(BigInteger, nullable=True)
    status = Column(String(50), nullable=False, index=True)  # 'sent', 'failed', 'opened'
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    opened_at = Column(DateTime, nullable=True)
    
    # Relationships
    broadcast = relationship("BroadcastMessage", back_populates="receipts")
    user = relationship("User")
    
    __table_args__ = (
        Index('idx_broadcast_id', 'broadcast_id'),
        Index('idx_user_id', 'user_id'),
        Index('idx_status', 'status'),
        Index('unique_broadcast_user', 'broadcast_id', 'user_id', unique=True),
    )
    
    def __repr__(self):
        return f"<BroadcastMessageReceipt(id={self.id}, broadcast_id={self.broadcast_id}, user_id={self.user_id}, status={self.status})>"


# ============= Event System Models =============

class Event(Base):
    """Event model for admin-created special events and campaigns."""
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, index=True)
    event_key = Column(String(100), nullable=False, unique=True, index=True)  # Unique identifier
    event_name = Column(String(200), nullable=False)  # Display name
    event_description = Column(Text, nullable=True)  # Description shown to users
    event_type = Column(String(50), nullable=False, index=True)  # 'points_multiplier', 'referral_reward', 'challenge_lottery'
    
    # Event configuration (stored as JSON-like structure in Text field, or separate columns)
    # For points_multiplier: multiplier value (e.g., 2.0 for 2x)
    # For referral_reward: premium_days value (e.g., 2 for 2 days premium)
    # For challenge_lottery: target_metric (e.g., 'chat_count'), target_value, reward_type, reward_value
    config_json = Column(Text, nullable=True)  # JSON configuration for flexible event rules
    
    # Event timing
    start_date = Column(DateTime, nullable=False, index=True)
    end_date = Column(DateTime, nullable=False, index=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    is_visible = Column(Boolean, default=True, nullable=False)  # Show to users or not
    
    # Admin info
    created_by_admin_id = Column(BigInteger, nullable=False, index=True)  # Telegram ID of admin
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    participants = relationship("EventParticipant", back_populates="event", cascade="all, delete-orphan")
    rewards = relationship("EventReward", back_populates="event", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_event_type', 'event_type'),
        Index('idx_start_end_date', 'start_date', 'end_date'),
        Index('idx_is_active', 'is_active'),
    )
    
    def __repr__(self):
        return f"<Event(id={self.id}, event_key={self.event_key}, event_type={self.event_type}, is_active={self.is_active})>"


class EventParticipant(Base):
    """Track user participation and progress in events."""
    __tablename__ = "event_participants"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Progress tracking (varies by event type)
    progress_value = Column(Integer, default=0, nullable=False)  # e.g., chat count, referral count
    additional_data = Column(Text, nullable=True)  # JSON for flexible data storage
    
    # Status
    is_eligible = Column(Boolean, default=True, nullable=False)  # Can participate in lottery/rewards
    has_received_reward = Column(Boolean, default=False, nullable=False)  # For one-time rewards
    
    # Timestamps
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    event = relationship("Event", back_populates="participants")
    user = relationship("User")
    
    __table_args__ = (
        Index('idx_event_user', 'event_id', 'user_id'),
        Index('idx_user_id', 'user_id'),
        Index('idx_progress_value', 'progress_value'),
        Index('unique_event_user', 'event_id', 'user_id', unique=True),
    )
    
    def __repr__(self):
        return f"<EventParticipant(id={self.id}, event_id={self.event_id}, user_id={self.user_id}, progress={self.progress_value})>"


class EventReward(Base):
    """Track rewards distributed to users from events."""
    __tablename__ = "event_rewards"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Reward details
    reward_type = Column(String(50), nullable=False)  # 'points', 'premium_days', 'badge', 'lottery_win'
    reward_value = Column(Integer, nullable=False)  # Points amount, premium days, etc.
    reward_description = Column(Text, nullable=True)
    
    # For lottery events
    is_lottery_winner = Column(Boolean, default=False, nullable=False)
    lottery_rank = Column(Integer, nullable=True)  # 1st, 2nd, 3rd place, etc.
    
    # Timestamps
    awarded_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    event = relationship("Event", back_populates="rewards")
    user = relationship("User")
    
    __table_args__ = (
        Index('idx_event_id', 'event_id'),
        Index('idx_user_id', 'user_id'),
        Index('idx_reward_type', 'reward_type'),
        Index('idx_awarded_at', 'awarded_at'),
        Index('idx_is_lottery_winner', 'is_lottery_winner'),
    )
    
    def __repr__(self):
        return f"<EventReward(id={self.id}, event_id={self.event_id}, user_id={self.user_id}, reward_type={self.reward_type}, reward_value={self.reward_value})>"


class PremiumPlan(Base):
    """Premium plan model for managing premium subscription plans."""
    __tablename__ = "premium_plans"
    
    id = Column(Integer, primary_key=True, index=True)
    plan_name = Column(String(200), nullable=False)  # e.g., "1 روز", "3 روز", "1 ماه"
    duration_days = Column(Integer, nullable=False, index=True)  # Duration in days
    price = Column(Float, nullable=False)  # Price in Toman
    original_price = Column(Float, nullable=True)  # Original price before discount
    discount_percent = Column(Integer, default=0, nullable=False)  # Discount percentage (0-100)
    
    # Stars payment
    stars_required = Column(Integer, nullable=True)  # Stars required for payment (null if not available)
    
    # Payment methods (JSON: ["shaparak", "stars"] or ["shaparak"] or ["stars"])
    payment_methods_json = Column(Text, nullable=True)  # JSON array of payment methods
    
    # Discount period (optional - for limited time offers)
    discount_start_date = Column(DateTime, nullable=True)
    discount_end_date = Column(DateTime, nullable=True)
    
    # Features (JSON for flexibility)
    features_json = Column(Text, nullable=True)  # JSON array of features
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    is_visible = Column(Boolean, default=True, nullable=False)  # Show to users
    
    # Display order
    display_order = Column(Integer, default=0, nullable=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index('idx_duration_days', 'duration_days'),
        Index('idx_is_active', 'is_active'),
        Index('idx_display_order', 'display_order'),
    )
    
    def __repr__(self):
        return f"<PremiumPlan(id={self.id}, plan_name={self.plan_name}, duration_days={self.duration_days}, price={self.price})>"


class CoinPackage(Base):
    """Coin package model for managing coin purchase packages."""
    __tablename__ = "coin_packages"
    
    id = Column(Integer, primary_key=True, index=True)
    package_name = Column(String(200), nullable=False)  # e.g., "100 سکه", "500 سکه", "1000 سکه"
    coin_amount = Column(Integer, nullable=False, index=True)  # Number of coins in package
    price = Column(Float, nullable=False)  # Price in Toman
    original_price = Column(Float, nullable=True)  # Original price before discount
    discount_percent = Column(Integer, default=0, nullable=False)  # Discount percentage (0-100)
    
    # Stars payment
    stars_required = Column(Integer, nullable=True)  # Stars required for payment (null if not available)
    
    # Payment methods (JSON: ["shaparak", "stars"] or ["shaparak"] or ["stars"])
    payment_methods_json = Column(Text, nullable=True)  # JSON array of payment methods
    
    # Discount period (optional - for limited time offers)
    discount_start_date = Column(DateTime, nullable=True)
    discount_end_date = Column(DateTime, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    is_visible = Column(Boolean, default=True, nullable=False)  # Show to users
    
    # Display order
    display_order = Column(Integer, default=0, nullable=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index('idx_coin_amount', 'coin_amount'),
        Index('idx_coin_is_active', 'is_active'),
        Index('idx_coin_display_order', 'display_order'),
    )
    
    def __repr__(self):
        return f"<CoinPackage(id={self.id}, package_name={self.package_name}, coin_amount={self.coin_amount}, price={self.price})>"


class PaymentTransaction(Base):
    """Payment transaction model for tracking payment gateway transactions."""
    __tablename__ = "payment_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("premium_plans.id"), nullable=True, index=True)
    coin_package_id = Column(Integer, ForeignKey("coin_packages.id"), nullable=True, index=True)  # For coin purchases
    
    # Transaction details
    transaction_id = Column(String(255), unique=True, nullable=False, index=True)  # Unique transaction ID
    amount = Column(Float, nullable=False)  # Amount in Toman
    currency = Column(String(10), default="IRT", nullable=False)  # Currency (IRT for Toman)
    
    # Payment gateway details
    gateway = Column(String(50), default="zarinpal", nullable=False)  # Payment gateway (zarinpal, etc.)
    authority = Column(String(255), nullable=True, index=True)  # Gateway authority code
    ref_id = Column(String(255), nullable=True, index=True)  # Gateway reference ID after payment
    
    # Status
    status = Column(String(50), default="pending", nullable=False, index=True)  # pending, processing, completed, failed, cancelled
    payment_status = Column(String(50), nullable=True)  # Gateway payment status
    
    # Metadata
    callback_url = Column(Text, nullable=True)  # Callback URL for payment gateway
    return_url = Column(Text, nullable=True)  # Return URL after payment
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    paid_at = Column(DateTime, nullable=True)  # When payment was completed
    
    # Relationships
    user = relationship("User")
    plan = relationship("PremiumPlan")
    
    __table_args__ = (
        Index('idx_user_id', 'user_id'),
        Index('idx_plan_id', 'plan_id'),
        Index('idx_transaction_id', 'transaction_id'),
        Index('idx_authority', 'authority'),
        Index('idx_ref_id', 'ref_id'),
        Index('idx_status', 'status'),
        Index('idx_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<PaymentTransaction(id={self.id}, user_id={self.user_id}, transaction_id={self.transaction_id}, status={self.status})>"


class SystemSetting(Base):
    """System settings model for storing configurable system settings."""
    __tablename__ = "system_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    setting_key = Column(String(100), unique=True, nullable=False, index=True)  # Unique setting key
    setting_value = Column(Text, nullable=True)  # Setting value (can be JSON, string, etc.)
    setting_type = Column(String(50), default="string", nullable=False)  # string, json, int, float, bool
    description = Column(Text, nullable=True)  # Human-readable description
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index('idx_setting_key', 'setting_key'),
    )
    
    def __repr__(self):
        return f"<SystemSetting(id={self.id}, setting_key={self.setting_key}, setting_value={self.setting_value})>"


class MandatoryChannel(Base):
    """Model for storing mandatory channels that users must join."""
    __tablename__ = "mandatory_channels"
    
    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(String(255), unique=True, nullable=False, index=True)  # Channel ID or username (e.g., @channel or -1001234567890)
    channel_name = Column(String(255), nullable=True)  # Display name for the channel
    channel_link = Column(String(512), nullable=True)  # Full link to the channel (e.g., https://t.me/channel)
    is_active = Column(Boolean, default=True, nullable=False)  # Whether this channel requirement is active
    order_index = Column(Integer, default=0, nullable=False)  # Order for displaying channels
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by_admin_id = Column(Integer, nullable=True)  # Admin who created this channel requirement
    
    __table_args__ = (
        Index('idx_channel_id', 'channel_id'),
        Index('idx_is_active', 'is_active'),
        Index('idx_order_index', 'order_index'),
    )
    
    def __repr__(self):
        return f"<MandatoryChannel(id={self.id}, channel_id={self.channel_id}, is_active={self.is_active})>"


# ============= Playlist Models =============

class UserPlaylist(Base):
    """User playlist model for storing user playlists."""
    __tablename__ = "user_playlists"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    name = Column(String(255), default="پلی‌لیست من", nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="playlist")
    items = relationship("PlaylistItem", back_populates="playlist", cascade="all, delete-orphan", order_by="PlaylistItem.added_at.desc()")
    
    __table_args__ = (
        Index('idx_user_id', 'user_id'),
    )
    
    def __repr__(self):
        return f"<UserPlaylist(id={self.id}, user_id={self.user_id}, name={self.name})>"


class PlaylistItem(Base):
    """Playlist item model for storing individual music items in playlists."""
    __tablename__ = "playlist_items"
    
    id = Column(Integer, primary_key=True, index=True)
    playlist_id = Column(Integer, ForeignKey("user_playlists.id"), nullable=False, index=True)
    
    # Message type: 'audio', 'voice', 'forwarded'
    message_type = Column(String(50), nullable=False)
    
    # Telegram file_id for the music
    file_id = Column(String(512), nullable=False)
    
    # Optional metadata
    title = Column(String(255), nullable=True)  # Song title
    performer = Column(String(255), nullable=True)  # Artist name
    duration = Column(Integer, nullable=True)  # Duration in seconds
    
    # For forwarded messages
    forwarded_from_chat_id = Column(BigInteger, nullable=True)
    forwarded_from_message_id = Column(Integer, nullable=True)
    
    # Timestamps
    added_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    playlist = relationship("UserPlaylist", back_populates="items")
    
    __table_args__ = (
        Index('idx_playlist_id', 'playlist_id'),
        Index('idx_message_type', 'message_type'),
        Index('idx_added_at', 'added_at'),
    )
    
    def __repr__(self):
        return f"<PlaylistItem(id={self.id}, playlist_id={self.playlist_id}, message_type={self.message_type})>"

