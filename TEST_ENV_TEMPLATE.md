# راهنمای اجرای محیط تست

## نحوه استفاده

### 1. ساخت فایل .env.test
یک فایل `.env.test` در روت پروژه بسازید و متغیرهای زیر را در آن قرار دهید:

```bash
# Bot Configuration (Test Bot Token)
BOT_TOKEN_TEST=your_test_bot_token_here

# Database Configuration (Test Environment)
MYSQL_ROOT_PASSWORD_TEST=test_root_password_123
MYSQL_DATABASE_TEST=telecaht_test
MYSQL_USER_TEST=test_user
MYSQL_PASSWORD_TEST=test_password_123

# Redis Configuration (Test Environment)
REDIS_DB_TEST=1
REDIS_PASSWORD_TEST=

# MinIO Configuration (Test Environment)
MINIO_ENDPOINT_TEST=your_minio_endpoint
MINIO_PUBLIC_URL_TEST=your_minio_public_url
MINIO_ACCESS_KEY_TEST=your_minio_access_key
MINIO_SECRET_KEY_TEST=your_minio_secret_key
MINIO_BUCKET_NAME_TEST=test-profile-images
MINIO_USE_SSL_TEST=false

# Channel Configuration (Test Environment)
MANDATORY_CHANNEL_ID_TEST=your_test_channel_id

# Admin Configuration (Test Environment)
ADMIN_IDS_TEST=123456789,987654321

# FastAPI Configuration (Test Environment)
VIDEO_CALL_DOMAIN_TEST=http://localhost:3000
VIDEO_CALL_API_URL_TEST=http://localhost:8001
VIDEO_CALL_WS_URL_TEST=ws://localhost:8001
API_SECRET_KEY_TEST=test-secret-key-change-this-in-production

# Premium Configuration (Test Environment)
PREMIUM_PRICE_TEST=5000.0
PREMIUM_DURATION_DAYS_TEST=30

# Chat Configuration (Test Environment)
MAX_CHAT_DURATION_MINUTES_TEST=60
PREMIUM_CHAT_DURATION_MINUTES_TEST=180
MATCHMAKING_TIMEOUT_SECONDS_TEST=300

# Rate Limiting (Test Environment)
RATE_LIMIT_MESSAGES_PER_MINUTE_TEST=20
```

### 2. اجرای محیط تست

برای اجرای محیط تست از دستور زیر استفاده کنید:

```bash
docker-compose -f docker-compose.test.yml --env-file .env.test up -d
```

### 3. متوقف کردن محیط تست

```bash
docker-compose -f docker-compose.test.yml down
```

### 4. مشاهده لاگ‌ها

```bash
docker-compose -f docker-compose.test.yml logs -f
```

### 5. حذف volumes (اگر می‌خواهید دیتابیس را پاک کنید)

```bash
docker-compose -f docker-compose.test.yml down -v
```

## تغییرات نسبت به محیط اصلی

### پورت‌ها:
- **Redis**: 6898 (به جای 6899)
- **MySQL**: 13306 (به جای 3306)
- **phpMyAdmin**: 8081 (به جای 8080)
- **Bot API**: 8001 (به جای 8000)

### نام Container ها:
- `telecaht_test_redis`
- `telecaht_test_mysql`
- `telecaht_test_phpmyadmin`
- `telecaht_test_bot`

### Volumes:
- `redis_test_data`
- `mysql_test_data`

### Network:
- `telecaht_test_network`

### دسترسی به سرویس‌ها:
- **phpMyAdmin**: http://localhost:8081
- **Bot API**: http://localhost:8001
- **MySQL**: localhost:13306

## نکات مهم

1. می‌توانید هر دو محیط (production و test) را همزمان اجرا کنید بدون هیچ تداخلی
2. هر محیط دیتابیس و Redis جداگانه‌ای دارد
3. برای تست حتماً یک Bot Token جداگانه از BotFather بگیرید
4. تنظیمات MinIO را برای محیط تست جدا نگه دارید (یا bucket جدید استفاده کنید)

