# Tests

این پوشه شامل تست‌های واحد برای سیستم ربات است.

## نصب وابستگی‌ها

### در محیط محلی:
```bash
pip install -r requirements.txt
```

### در Docker (اتوماتیک نصب می‌شود):
وابستگی‌ها در Dockerfile نصب می‌شوند.

## اجرای تست‌ها

### در Docker (پیشنهادی):

#### روش 1: استفاده از container موجود
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
```

#### روش 2: استفاده از script (Linux/Mac)
```bash
chmod +x run_tests.sh
./run_tests.sh

# با آرگومان‌های اضافی
./run_tests.sh -v
./run_tests.sh tests/test_referral_events.py
```

#### روش 3: استفاده از script (Windows PowerShell)
```powershell
.\run_tests.ps1

# با آرگومان‌های اضافی
.\run_tests.ps1 -v
.\run_tests.ps1 tests/test_referral_events.py
```

#### روش 4: استفاده از docker-compose (برای تست جداگانه)
```bash
# اجرای تست‌ها در یک container جداگانه
docker-compose -f docker-compose.yml -f docker-compose.test.yml run --rm test

# با آرگومان‌های اضافی
docker-compose -f docker-compose.yml -f docker-compose.test.yml run --rm test -v
docker-compose -f docker-compose.yml -f docker-compose.test.yml run --rm test tests/test_referral_events.py
```

### در محیط محلی:
```bash
# اجرای همه تست‌ها
pytest

# اجرای تست‌های خاص
pytest tests/test_referral_events.py

# اجرای با جزئیات بیشتر
pytest -v

# اجرای با نمایش خروجی print
pytest -s
```

## تست‌های موجود

### `test_referral_events.py`
تست‌های مربوط به سیستم دعوت و تأثیر ایونت‌ها روی نرخ سکه:

1. **تست بدون ایونت**: بررسی عملکرد عادی بدون ایونت فعال
2. **تست با points_multiplier برای همه منابع**: بررسی ضرب شدن سکه‌ها وقتی `apply_to_sources` خالی است
3. **تست با points_multiplier برای source خاص**: بررسی ضرب شدن فقط برای `referral_profile_complete`
4. **تست با points_multiplier که referral را شامل نمی‌شود**: بررسی عدم ضرب شدن وقتی source در `apply_to_sources` نیست
5. **تست با referral_reward**: بررسی دادن پریمیوم به جای سکه
6. **تست خواندن سکه از دیتابیس**: بررسی اینکه سکه‌ها از دیتابیس خوانده می‌شوند
7. **تست fallback به settings**: بررسی اینکه اگر در دیتابیس نباشد، از settings استفاده می‌شود

