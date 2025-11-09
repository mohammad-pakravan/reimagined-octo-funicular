# راهنمای Deployment برای تماس تصویری

## تنظیمات Docker Compose

پس از به‌روزرسانی، Docker Compose شامل سرویس‌های زیر است:

1. **redis** - Redis cache
2. **mysql** - MySQL database
3. **minio** - MinIO storage
4. **bot** - Telegram Bot + FastAPI (port 8000)
5. **webapp** - React Frontend + Nginx (port 3000)

## راه‌اندازی

### 1. تنظیمات Environment Variables

ایجاد/ویرایش فایل `.env`:

```env
# Video Call Configuration
VIDEO_CALL_DOMAIN=http://localhost:3000
VIDEO_CALL_API_URL=http://bot:8000
VIDEO_CALL_WS_URL=ws://bot:8000
API_SECRET_KEY=your-secret-key-change-this

# Other settings...
BOT_TOKEN=your_bot_token
# ...
```

### 2. Build و Run

```bash
# Build همه سرویس‌ها
docker-compose build

# اجرای سرویس‌ها
docker-compose up -d

# مشاهده لاگ‌ها
docker-compose logs -f webapp
docker-compose logs -f bot
```

### 3. بررسی وضعیت

```bash
# بررسی وضعیت containers
docker-compose ps

# تست API
curl http://localhost:8000/health

# تست Frontend
curl http://localhost:3000
```

## پورت‌ها

- **8000**: FastAPI Backend (bot container)
- **3000**: Frontend Web App (webapp container)
- **6379**: Redis
- **3309**: MySQL (mapped from container port 3306)
- **9000**: MinIO API
- **9001**: MinIO Console

## Network

همه سرویس‌ها در شبکه `telecaht_network` هستند و می‌توانند از طریق نام container با هم ارتباط برقرار کنند:

- `bot` → FastAPI Backend
- `webapp` → Frontend
- `mysql` → MySQL Database
- `redis` → Redis Cache
- `minio` → MinIO Storage

## Frontend Environment Variables

در Docker، environment variables در `docker-compose.yml` تنظیم می‌شوند:

```yaml
environment:
  - VITE_API_BASE_URL=http://bot:8000
  - VITE_API_WS_URL=ws://bot:8000
```

این مقادیر در زمان build استفاده می‌شوند.

## Production Deployment

برای production:

1. تنظیم `VIDEO_CALL_DOMAIN` به دامنه واقعی:
   ```env
   VIDEO_CALL_DOMAIN=https://yourdomain.com
   ```

2. تنظیم SSL/TLS برای nginx (در production)

3. تنظیم CORS در FastAPI (در حال حاضر `allow_origins=["*"]` است)

4. تنظیم `API_SECRET_KEY` به یک کلید قوی و امن

## Troubleshooting

### Frontend نمی‌تواند به API متصل شود:

- بررسی کنید که `bot` container در حال اجرا است
- بررسی network connectivity:
  ```bash
  docker-compose exec webapp ping bot
  ```

### WebSocket Connection Failed:

- بررسی کنید که `/ws` endpoint در nginx درست configure شده
- بررسی firewall settings

### Build Error:

- مطمئن شوید که Node.js dependencies نصب شده‌اند:
  ```bash
  cd webapp
  npm install
  ```

