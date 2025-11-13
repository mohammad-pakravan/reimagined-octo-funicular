# 🛠️ رفع خطای Connection Refused در MySQL (Remote Access)

## ⚠️ خطا
```
(2003, "Can't connect to MySQL server on '91.107.169.235' ([Errno 111] Connection refused)")
```

یعنی Flask یا هر کلاینت دیگه نمی‌تونه به MySQL روی پورت 3306 وصل بشه.

---

## 1️⃣ بررسی bind-address در MySQL

ممکنه MySQL فقط روی `localhost` گوش بده.

فایل تنظیمات رو باز کن:
```bash
sudo nano /etc/mysql/mysql.conf.d/mysqld.cnf
```

و این خط رو پیدا کن:
```bash
bind-address = 127.0.0.1
```

اون رو تغییر بده به:
```bash
bind-address = 0.0.0.0
```

سپس MySQL رو ریستارت کن:
```bash
sudo systemctl restart mysql
```

---

## 2️⃣ باز کردن پورت 3306 در فایروال

بررسی وضعیت فایروال:
```bash
sudo ufw status
```

در صورت فعال بودن:
```bash
sudo ufw allow 3306/tcp
sudo ufw reload
```

---

## 3️⃣ بررسی دسترسی کاربر MySQL

با کاربر root وارد شو:
```bash
mysql -u root -p
```

و مجوزهای کاربر رو ببین:
```sql
SHOW GRANTS FOR 'telecaht_user'@'%';
```

در صورت نیاز کاربر رو دوباره بساز:
```sql
DROP USER IF EXISTS 'telecaht_user'@'%';
CREATE USER 'telecaht_user'@'%' IDENTIFIED BY 'telecaht_pass';
GRANT ALL PRIVILEGES ON telecaht.* TO 'telecaht_user'@'%';
FLUSH PRIVILEGES;
```

---

## 4️⃣ تست اتصال از Flask یا ماشین دیگر

از همان جایی که Flask ران شده:
```bash
mysql -h 91.107.169.235 -u telecaht_user -ptelecaht_pass telecaht
```

اگر باز هم خطا داد، مشکل یا از تنظیمات MySQL یا از فایروال است.

---

## 🔒 نکته امنیتی
برای جلوگیری از دسترسی همهٔ IPها، بهتر است فقط IP سرور Flask مجاز باشد:

```sql
CREATE USER 'telecaht_user'@'YOUR_FLASK_SERVER_IP' IDENTIFIED BY 'telecaht_pass';
GRANT ALL PRIVILEGES ON telecaht.* TO 'telecaht_user'@'YOUR_FLASK_SERVER_IP';
FLUSH PRIVILEGES;
```
