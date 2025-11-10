# راهنمای اجرای تست‌ها در Docker

این فایل راهنمای اجرای تست‌ها در محیط Docker است.

## پیش‌نیازها

1. Docker و Docker Compose باید نصب باشند
2. Container های مورد نیاز باید در حال اجرا باشند:
   ```bash
   docker-compose up -d
   ```

## روش‌های اجرای تست

### روش 1: استفاده مستقیم از docker exec (ساده‌ترین روش)

```bash
# اجرای همه تست‌ها
docker exec -it telecaht_bot pytest

# اجرای تست‌های خاص
docker exec -it telecaht_bot pytest tests/test_referral_events.py

# اجرای با جزئیات بیشتر
docker exec -it telecaht_bot pytest -v

# اجرای با نمایش خروجی print
docker exec -it telecaht_bot pytest -s

# اجرای یک تست خاص
docker exec -it telecaht_bot pytest tests/test_referral_events.py::TestReferralEvents::test_referral_profile_complete_without_events

# اجرای با coverage
docker exec -it telecaht_bot pytest --cov=core --cov=bot --cov-report=html
```

### روش 2: استفاده از Script (Linux/Mac)

```bash
# دادن دسترسی اجرا
chmod +x run_tests.sh

# اجرای تست‌ها
./run_tests.sh

# با آرگومان‌های اضافی
./run_tests.sh -v
./run_tests.sh tests/test_referral_events.py
./run_tests.sh -s -v
```

### روش 3: استفاده از Script (Windows PowerShell)

```powershell
# اجرای تست‌ها
.\run_tests.ps1

# با آرگومان‌های اضافی
.\run_tests.ps1 -v
.\run_tests.ps1 tests/test_referral_events.py
.\run_tests.ps1 -s -v
```

### روش 4: استفاده از docker-compose (برای تست جداگانه)

```bash
# اجرای تست‌ها در یک container جداگانه
docker-compose -f docker-compose.yml -f docker-compose.test.yml run --rm test

# با آرگومان‌های اضافی
docker-compose -f docker-compose.yml -f docker-compose.test.yml run --rm test -v
docker-compose -f docker-compose.yml -f docker-compose.test.yml run --rm test tests/test_referral_events.py
```

## بررسی وضعیت Container

```bash
# بررسی اینکه container در حال اجرا است
docker ps | grep telecaht_bot

# مشاهده لاگ‌های container
docker logs telecaht_bot

# ورود به container
docker exec -it telecaht_bot bash
```

## نصب وابستگی‌های جدید

اگر وابستگی جدیدی به `requirements.txt` اضافه کردید:

```bash
# Rebuild container
docker-compose build bot

# یا restart container
docker-compose restart bot
```

## عیب‌یابی

### مشکل: Container در حال اجرا نیست
```bash
# راه‌اندازی container
docker-compose up -d bot
```

### مشکل: pytest پیدا نمی‌شود
```bash
# بررسی نصب pytest در container
docker exec -it telecaht_bot pip list | grep pytest

# نصب مجدد
docker exec -it telecaht_bot pip install pytest pytest-asyncio pytest-mock
```

### مشکل: تست‌ها به دیتابیس یا Redis نیاز دارند
تست‌های فعلی از mock استفاده می‌کنند و نیازی به دیتابیس واقعی ندارند. اما اگر تست‌های integration بنویسید:

```bash
# اطمینان از اجرای همه سرویس‌ها
docker-compose up -d
```

## مثال‌های کاربردی

```bash
# اجرای همه تست‌ها با جزئیات
docker exec -it telecaht_bot pytest -v

# اجرای فقط تست‌های referral events
docker exec -it telecaht_bot pytest tests/test_referral_events.py -v

# اجرای یک تست خاص
docker exec -it telecaht_bot pytest tests/test_referral_events.py::TestReferralEvents::test_referral_profile_complete_without_events -v

# اجرای با نمایش خروجی print
docker exec -it telecaht_bot pytest -s -v

# اجرای با coverage
docker exec -it telecaht_bot pytest --cov=core --cov=bot --cov-report=term-missing

# اجرای فقط تست‌های شکست خورده
docker exec -it telecaht_bot pytest --lf

# اجرای با stop on first failure
docker exec -it telecaht_bot pytest -x
```


