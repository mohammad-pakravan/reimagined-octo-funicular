# راهنمای Scale کردن سیستم برای تعداد کاربران بیشتر

## 📊 وضعیت فعلی
- **ظرفیت فعلی**: ۱۰,۰۰۰ کاربر همزمان
- **Connection Pool**: ۲۰۰ اتصال (۱۵۰ + ۵۰ overflow)
- **Matchmaking Worker**: ۱ worker با interval 1 ثانیه
- **Storage**: RedisStorage (پشتیبانی از scale افقی)

---

## 🚀 راه‌های Scale کردن

### 1. Scale عمودی (افزایش منابع سرور)

#### افزایش Connection Pool
**فایل**: `config/settings.py` و `.env`

```env
# برای ۲۰,۰۰۰ کاربر همزمان
DB_POOL_SIZE=300
DB_MAX_OVERFLOW=100

# برای ۵۰,۰۰۰ کاربر همزمان
DB_POOL_SIZE=500
DB_MAX_OVERFLOW=200
```

**نکته**: هر اتصال دیتابیس حدود ۱-۲MB RAM مصرف می‌کند. با ۵۰۰ اتصال، حدود ۱GB RAM فقط برای connection pool نیاز دارید.

#### افزایش Redis Connections
```env
# برای ۲۰,۰۰۰ کاربر
REDIS_MAX_CONNECTIONS=100

# برای ۵۰,۰۰۰ کاربر
REDIS_MAX_CONNECTIONS=200
```

#### افزایش Matchmaking Worker Batch Size
```env
# برای صف‌های بزرگ‌تر
MATCHMAKING_WORKER_INTERVAL=0.5  # هر ۰.۵ ثانیه
MATCHMAKING_WORKER_BATCH_SIZE=10  # پردازش ۱۰ match همزمان
```

---

### 2. Scale افقی (چند Instance)

#### راه‌اندازی چند Instance از Bot

**مزایا**:
- توزیع بار بین چند سرور
- افزایش ظرفیت کل
- Fault tolerance بهتر

**نیازها**:
- ✅ RedisStorage (قبلاً اضافه شده)
- ✅ Redis برای state sharing
- ✅ Load Balancer برای توزیع ترافیک

#### تنظیمات برای چند Instance

**1. Redis Configuration**
```env
# همه instance ها باید از یک Redis استفاده کنند
REDIS_HOST=your-redis-server
REDIS_PORT=6379
REDIS_DB=0
```

**2. Database Configuration**
```env
# همه instance ها از یک دیتابیس استفاده می‌کنند
MYSQL_HOST=your-mysql-server
MYSQL_PORT=3306
```

**3. Connection Pool per Instance**
```env
# هر instance باید pool کوچکتری داشته باشد
# مثال: ۳ instance × ۱۵۰ connection = ۴۵۰ total
DB_POOL_SIZE=150
DB_MAX_OVERFLOW=50
```

**4. Load Balancer Setup**
- استفاده از Nginx یا HAProxy
- توزیع ترافیک بین instance ها
- Health check برای instance ها

---

### 3. بهینه‌سازی Database

#### اضافه کردن Index ها
```sql
-- بررسی query های کند
SHOW PROCESSLIST;

-- اضافه کردن index برای جدول users
CREATE INDEX idx_telegram_id ON users(telegram_id);
CREATE INDEX idx_active_chat ON chat_rooms(is_active, user1_id, user2_id);

-- Index برای جدول messages
CREATE INDEX idx_chat_room_created ON messages(chat_room_id, created_at);
```

#### Query Optimization
- استفاده از `EXPLAIN` برای بررسی query ها
- بهینه‌سازی query های پر استفاده
- استفاده از batch operations

#### Database Replication
- Master-Slave setup برای read operations
- کاهش load روی master database

---

### 4. بهینه‌سازی Redis

#### Redis Cluster
```env
# برای scale افقی Redis
REDIS_CLUSTER_MODE=true
REDIS_NODES=node1:6379,node2:6379,node3:6379
```

#### Memory Optimization
```redis
# تنظیمات redis.conf
maxmemory 32gb
maxmemory-policy allkeys-lru
```

#### Redis Persistence
```redis
# برای داده‌های مهم
save 900 1
save 300 10
save 60 10000
```

---

### 5. بهینه‌سازی Matchmaking

#### چند Worker همزمان
**فایل**: `main.py`

```python
# اجرای چند worker همزمان
for i in range(3):  # ۳ worker همزمان
    asyncio.create_task(run_matchmaking_worker())
```

#### بهبود الگوریتم Matchmaking
- استفاده از priority queue
- Match کردن بر اساس location
- Caching برای match های محتمل

---

### 6. Monitoring و Alerting

#### Metrics مهم
- Connection pool usage
- Database query time
- Redis memory usage
- Matchmaking queue size
- Active users count

#### Tools پیشنهادی
- **Prometheus** + **Grafana** برای monitoring
- **Sentry** برای error tracking
- **ELK Stack** برای logging

---

## 📈 جدول راهنمای Scale

| تعداد کاربر همزمان | Connection Pool | Redis Connections | Worker Count | توصیه |
|-------------------|----------------|-------------------|-------------|--------|
| ۱۰,۰۰۰ | ۲۰۰ (۱۵۰+۵۰) | ۵۰ | ۱ | ✅ فعلی |
| ۲۰,۰۰۰ | ۳۰۰ (۲۰۰+۱۰۰) | ۱۰۰ | ۲ | Scale عمودی |
| ۵۰,۰۰۰ | ۵۰۰ (۳۰۰+۲۰۰) | ۲۰۰ | ۳ | Scale عمودی + افقی |
| ۱۰۰,۰۰۰+ | ۲-۳ Instance | ۲۰۰ per instance | ۳ per instance | Scale افقی |

---

## 🔧 مراحل Scale کردن

### مرحله ۱: افزایش Connection Pool
1. ویرایش `.env`:
   ```env
   DB_POOL_SIZE=300
   DB_MAX_OVERFLOW=100
   ```
2. Restart application
3. Monitor connection pool usage

### مرحله ۲: افزایش Matchmaking Workers
1. ویرایش `main.py`:
   ```python
   # اجرای چند worker
   for i in range(3):
       asyncio.create_task(run_matchmaking_worker())
   ```
2. Restart application
3. Monitor matchmaking performance

### مرحله ۳: Scale افقی
1. Setup Redis server (اگر جداگانه نیست)
2. Setup چند instance از bot
3. Setup Load Balancer
4. Configure health checks
5. Test و monitor

### مرحله ۴: Database Optimization
1. بررسی slow queries
2. اضافه کردن index ها
3. Query optimization
4. Database replication (اختیاری)

---

## ⚠️ نکات مهم

### محدودیت‌های Connection Pool
- هر اتصال دیتابیس RAM مصرف می‌کند
- MySQL `max_connections` را بررسی کنید
- با ۵۰۰+ connection، نیاز به سرور قوی‌تر دارید

### محدودیت‌های Redis
- Redis memory limit را تنظیم کنید
- برای ۱۰۰K+ کاربر، Redis Cluster توصیه می‌شود

### محدودیت‌های Telegram Bot API
- Telegram Bot API rate limits: 30 messages/second
- برای scale بیشتر، نیاز به چند bot token دارید

### Database Bottleneck
- با ۱۰۰K+ کاربر، database ممکن است bottleneck شود
- Database replication و read replicas توصیه می‌شود

---

## 🎯 توصیه‌های نهایی

### برای ۲۰,۰۰۰ کاربر همزمان:
1. ✅ افزایش Connection Pool به ۳۰۰
2. ✅ افزایش Redis connections به ۱۰۰
3. ✅ افزایش Matchmaking batch size به ۱۰
4. ✅ اضافه کردن ۲ worker همزمان

### برای ۵۰,۰۰۰ کاربر همزمان:
1. ✅ همه موارد بالا
2. ✅ ۲-۳ instance از bot
3. ✅ Load Balancer
4. ✅ Database replication
5. ✅ Redis Cluster

### برای ۱۰۰,۰۰۰+ کاربر همزمان:
1. ✅ همه موارد بالا
2. ✅ چند سرور (horizontal scaling)
3. ✅ CDN برای static content
4. ✅ Database sharding (اگر لازم باشد)
5. ✅ Microservices architecture (اختیاری)

---

## 📝 Checklist برای Scale کردن

- [ ] بررسی منابع سرور (RAM, CPU, Network)
- [ ] افزایش Connection Pool در `.env`
- [ ] افزایش Redis connections
- [ ] افزایش Matchmaking workers
- [ ] اضافه کردن monitoring
- [ ] تست load testing
- [ ] بررسی database performance
- [ ] بهینه‌سازی query ها
- [ ] اضافه کردن index ها
- [ ] Setup scale افقی (اگر لازم باشد)

---

## 🔍 Troubleshooting

### مشکل: Connection Pool Exhausted
**راه‌حل**: افزایش `DB_POOL_SIZE` و `DB_MAX_OVERFLOW`

### مشکل: Redis Memory Full
**راه‌حل**: 
- افزایش Redis memory
- تنظیم `maxmemory-policy`
- استفاده از Redis Cluster

### مشکل: Matchmaking کند
**راه‌حل**:
- کاهش `MATCHMAKING_WORKER_INTERVAL`
- افزایش `MATCHMAKING_WORKER_BATCH_SIZE`
- اضافه کردن worker های بیشتر

### مشکل: Database Slow
**راه‌حل**:
- بررسی slow queries
- اضافه کردن index ها
- Query optimization
- Database replication

---

## 📚 منابع بیشتر

- [SQLAlchemy Connection Pooling](https://docs.sqlalchemy.org/en/14/core/pooling.html)
- [Redis Best Practices](https://redis.io/docs/manual/patterns/)
- [Telegram Bot API Limits](https://core.telegram.org/bots/faq#my-bot-is-hitting-limits-how-do-i-avoid-this)
- [Horizontal Scaling Guide](https://en.wikipedia.org/wiki/Scalability#Horizontal_and_vertical_scaling)

