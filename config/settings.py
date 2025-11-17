"""
Configuration management for the Telegram bot.
Loads settings from environment variables.
"""
import os
from typing import List, Union
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Bot configuration
    BOT_TOKEN: str = Field(..., description="Telegram bot token from @BotFather")
    
    # Database configuration
    MYSQL_HOST: str = Field(default="localhost", description="MySQL host")
    MYSQL_PORT: int = Field(default=3306, description="MySQL port")
    MYSQL_USER: str = Field(default="telecaht_user", description="MySQL username")
    MYSQL_PASSWORD: str = Field(default="telecaht_pass", description="MySQL password")
    MYSQL_DATABASE: str = Field(default="telecaht", description="MySQL database name")
    
    # Database connection pool configuration
    DB_POOL_SIZE: int = Field(default=150, description="Database connection pool size")
    DB_MAX_OVERFLOW: int = Field(default=50, description="Maximum overflow connections for database pool")
    
    # Redis configuration
    REDIS_HOST: str = Field(default="localhost", description="Redis host")
    REDIS_PORT: int = Field(default=6379, description="Redis port")
    REDIS_DB: int = Field(default=0, description="Redis database number")
    REDIS_PASSWORD: str = Field(default="", description="Redis password (empty if not set)")
    REDIS_MAX_CONNECTIONS: int = Field(default=50, description="Maximum Redis connection pool size")
    
    # MinIO configuration
    MINIO_ENDPOINT: str = Field(default="localhost:9000", description="MinIO endpoint (internal, for Docker)")
    MINIO_PUBLIC_URL: str = Field(default="http://localhost:9000", description="MinIO public URL (accessible from internet)")
    MINIO_ACCESS_KEY: str = Field(default="minioadmin", description="MinIO access key")
    MINIO_SECRET_KEY: str = Field(default="minioadmin", description="MinIO secret key")
    MINIO_BUCKET_NAME: str = Field(default="profile-images", description="MinIO bucket for profile images")
    MINIO_USE_SSL: bool = Field(default=False, description="Use SSL for MinIO")
    
    # Channel configuration
    MANDATORY_CHANNEL_ID: str = Field(..., description="Channel ID that users must join before using chat")
    
    # Support configuration
    SUPPORT_ADMIN: str = Field(default="", description="Telegram link for support/admin contact")
    
    # Admin configuration (comma-separated string in env, converted to list)
    ADMIN_IDS: Union[str, List[int]] = Field(default="", description="Comma-separated admin Telegram user IDs")
    
    @field_validator('ADMIN_IDS', mode='before')
    @classmethod
    def parse_admin_ids(cls, v):
        """Parse comma-separated admin IDs to list."""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            if not v.strip():
                return []
            return [int(id.strip()) for id in v.split(',') if id.strip()]
        return []
    
    # FastAPI configuration
    API_HOST: str = Field(default="0.0.0.0", description="FastAPI host")
    API_PORT: int = Field(default=8000, description="FastAPI port")
    VIDEO_CALL_DOMAIN: str = Field(default="https://your-domain.com", description="Domain for video call links")
    API_SECRET_KEY: str = Field(default="your-secret-key", description="Secret key for API authentication")
    
    # Premium configuration
    PREMIUM_PRICE: float = Field(default=10000.0, description="Premium subscription price")
    PREMIUM_DURATION_DAYS: int = Field(default=30, description="Premium subscription duration in days")
    
    # Chat configuration
    MAX_CHAT_DURATION_MINUTES: int = Field(default=60, description="Maximum chat duration for free users")
    PREMIUM_CHAT_DURATION_MINUTES: int = Field(default=180, description="Maximum chat duration for premium users")
    MATCHMAKING_TIMEOUT_SECONDS: int = Field(default=300, description="Timeout for matchmaking in seconds")
    
    # Cost configuration
    CHAT_REQUEST_COST: int = Field(default=1, description="Cost in coins for sending a chat request (non-premium users)")
    DIRECT_MESSAGE_COST: int = Field(default=1, description="Cost in coins for sending a direct message (non-premium users)")
    
    # Matchmaking worker configuration
    MATCHMAKING_WORKER_INTERVAL: int = Field(default=1, description="Matchmaking worker check interval in seconds")
    MATCHMAKING_WORKER_BATCH_SIZE: int = Field(default=5, description="Number of matches to process per worker cycle")
    MATCHMAKING_BACKEND: str = Field(
        default="redis",
        description="Backend for matchmaking queue: 'redis' or 'memory'"
    )
    
    # Rate limiting
    RATE_LIMIT_MESSAGES_PER_MINUTE: int = Field(default=20, description="Max messages per minute per user")

    # Virtual profile / bot simulation (currently optional, used in some deployments)
    VIRTUAL_PROFILE_BOT_ENABLED: bool = Field(
        default=False,
        description="Enable virtual profile bot (simulated users)",
    )
    VIRTUAL_PROFILE_MIN_WAIT_SECONDS: int = Field(
        default=4,
        description="Minimum wait time in seconds before virtual profile joins queue",
    )
    VIRTUAL_PROFILE_MAX_WAIT_SECONDS: int = Field(
        default=120,
        description="Maximum wait time in seconds before virtual profile joins queue",
    )
    
    # Engagement Features Configuration
    # Points configuration
    POINTS_DAILY_LOGIN: int = Field(default=10, description="Points awarded for daily login")
    POINTS_CHAT_SUCCESS: int = Field(default=50, description="Points awarded for successful chat")
    POINTS_MUTUAL_LIKE: int = Field(default=100, description="Points awarded for mutual like")
    POINTS_REFERRAL_REFERRER: int = Field(default=500, description="Points awarded to referrer when someone uses their code")
    POINTS_REFERRAL_REFERRED: int = Field(default=200, description="Points awarded to referred user")
    POINTS_STREAK_MULTIPLIER: float = Field(default=1.5, description="Multiplier for streak rewards")
    
    # Points conversion
    POINTS_TO_PREMIUM_DAY: int = Field(default=1000, description="Points required for 1 day of premium")
    
    # Daily reward configuration
    DAILY_REWARD_BASE_POINTS: int = Field(default=10, description="Base points for daily login")
    DAILY_REWARD_STREAK_BONUS: int = Field(default=5, description="Additional points per streak day")
    MAX_DAILY_REWARD_STREAK: int = Field(default=7, description="Maximum streak days for bonus calculation")
    
    # Achievement configuration
    ACHIEVEMENT_CHECK_ENABLED: bool = Field(default=True, description="Enable achievement checking")
    
    # Matchmaking probability configuration
    RANDOM_GIRL_BOY_MATCH_PROBABILITY: float = Field(
        default=0.3,
        description="Probability (0.0-1.0) for girls to match with boys in random chat when no boy-boy pairs exist. Lower = harder for girls to match with boys."
    )
    PROBABILITY_CHECK_COOLDOWN_SECONDS: int = Field(
        default=30,
        description="Cooldown in seconds between probability checks for the same user. Prevents rapid retries that would make 2% probability effectively much higher."
    )
    
    # No-rematch rule configuration
    ENABLE_NO_REMATCH_RULE: bool = Field(
        default=True,
        description="Enable the rule that prevents users from matching again within a cooldown period"
    )
    NO_REMATCH_HOURS: int = Field(
        default=7,
        description="Number of hours that must pass before two users can be matched again (only applies if ENABLE_NO_REMATCH_RULE is True)"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    @property
    def mysql_url(self) -> str:
        """Build MySQL connection URL."""
        return f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"

    @property
    def redis_url(self) -> str:
        """Build Redis connection URL."""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


# Global settings instance
settings = Settings()

