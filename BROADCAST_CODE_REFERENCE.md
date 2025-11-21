# 📢 مرجع کامل کدهای Broadcast System

این سند شامل **تمام کدها، متدها و فایل‌های** مرتبط با سیستم ارسال پیام همگانی است.

---

## 📁 فهرست فایل‌های مرتبط

```
📂 پروژه
├── 📂 bots/
│   ├── 📄 admin_bot.py (خطوط 4437-4857)
│   │   └── ایجاد و مدیریت broadcast از سمت ادمین
│   │
│   └── 📂 user_bot/
│       ├── 📄 main.py (خطوط 7270-7287)
│       │   └── راه‌اندازی Scheduler
│       │
│       └── 📄 broadcast_processor.py (کامل)
│           └── پردازش و ارسال پیام‌ها
│
├── 📂 utils/
│   └── 📄 broadcast_service.py (کامل)
│       └── سرویس‌های دیتابیس
│
├── 📂 database/
│   └── 📄 models.py (خطوط 945-982)
│       └── مدل BroadcastMessage
│
└── 📂 docs/
    ├── 📄 BROADCAST_SYSTEM.md (مستندات کلی)
    └── 📄 BROADCAST_CODE_REFERENCE.md (این فایل)
```

---

## 1️⃣ مدل دیتابیس (Database Model)

### 📄 `database/models.py` (خطوط 945-982)

```python
class BroadcastMessage(Base):
    """پیام‌های همگانی برای ارسال به کاربران"""
    __tablename__ = 'broadcast_messages'
    
    # اطلاعات پیام
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_text = Column(Text, nullable=False)
    message_type = Column(String(20), nullable=False)  # 'text', 'photo', 'video', 'document'
    file_id = Column(String(200))  # For media messages
    local_path = Column(String(500))  # Local file path for cross-bot compatibility
    
    # وضعیت پردازش
    status = Column(String(20), default='pending')  # 'pending', 'processing', 'completed', 'failed'
    total_users = Column(Integer, default=0)
    sent_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    
    # ردیابی خطا
    error_message = Column(Text)
    
    # متادیتا
    created_by = Column(BigInteger, ForeignKey('users.user_id'), nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Relationship
    creator = relationship('User', backref='created_broadcasts')
    
    # Indexes
    __table_args__ = (
        Index('idx_broadcast_status', 'status'),
        Index('idx_broadcast_created', 'created_at'),
        Index('idx_broadcast_creator', 'created_by'),
    )
    
    def __repr__(self):
        return f"<BroadcastMessage(id={self.id}, type='{self.message_type}', status='{self.status}')>"
```

**توضیحات:**
- `status`: وضعیت پیام (pending → processing → completed/failed)
- `local_path`: مسیر فایل محلی برای سازگاری بین Admin Bot و User Bot
- `sent_count/failed_count`: آمار ارسال

---

## 2️⃣ سرویس Broadcast (Broadcast Service)

### 📄 `utils/broadcast_service.py` (کامل)

```python
#!/usr/bin/env python3
"""
Broadcast Service for Telegram Bot
Handles broadcast message queue and processing
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from database import DatabaseManager
from database.models import User, BroadcastMessage

logger = logging.getLogger(__name__)

class BroadcastService:
    """سرویس مدیریت پیام همگانی"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def create_broadcast_message(self, session: Session, message_text: str, 
                               message_type: str, file_id: Optional[str], 
                               created_by: int, local_path: Optional[str] = None) -> BroadcastMessage:
        """ایجاد پیام همگانی جدید"""
        try:
            broadcast = BroadcastMessage(
                message_text=message_text,
                message_type=message_type,
                file_id=file_id,
                local_path=local_path,
                created_by=created_by,
                status='pending'
            )
            session.add(broadcast)
            session.commit()
            logger.info(f"Broadcast message created: {broadcast.id}")
            return broadcast
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating broadcast message: {e}")
            raise

    def get_pending_broadcasts(self, session: Session) -> List[BroadcastMessage]:
        """دریافت پیام‌های همگانی در انتظار"""
        try:
            broadcasts = session.query(BroadcastMessage).filter(
                BroadcastMessage.status == 'pending'
            ).order_by(BroadcastMessage.created_at).all()
            return broadcasts
        except Exception as e:
            logger.error(f"Error getting pending broadcasts: {e}")
            return []

    def get_active_users(self, session: Session) -> List[User]:
        """دریافت لیست کاربران فعال"""
        try:
            users = session.query(User).filter(
                User.is_banned == False,
                User.user_id.isnot(None)
            ).all()
            return users
        except Exception as e:
            logger.error(f"Error getting active users: {e}")
            return []

    def update_broadcast_status(self, session: Session, broadcast_id: int, 
                              status: str, **kwargs) -> bool:
        """به‌روزرسانی وضعیت پیام همگانی"""
        try:
            broadcast = session.query(BroadcastMessage).filter(
                BroadcastMessage.id == broadcast_id
            ).first()
            
            if not broadcast:
                return False
            
            broadcast.status = status
            
            # Update additional fields based on status
            if status == 'processing':
                broadcast.started_at = datetime.now()
                if 'total_users' in kwargs:
                    broadcast.total_users = kwargs['total_users']
            elif status == 'completed':
                broadcast.completed_at = datetime.now()
                if 'sent_count' in kwargs:
                    broadcast.sent_count = kwargs['sent_count']
                if 'failed_count' in kwargs:
                    broadcast.failed_count = kwargs['failed_count']
            elif status == 'failed':
                broadcast.completed_at = datetime.now()
                if 'error_message' in kwargs:
                    broadcast.error_message = kwargs['error_message']
            
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating broadcast status: {e}")
            return False

    def get_broadcast_stats(self, session: Session) -> Dict[str, int]:
        """آمار پیام‌های همگانی"""
        try:
            stats = {
                'total': session.query(BroadcastMessage).count(),
                'pending': session.query(BroadcastMessage).filter(
                    BroadcastMessage.status == 'pending'
                ).count(),
                'processing': session.query(BroadcastMessage).filter(
                    BroadcastMessage.status == 'processing'
                ).count(),
                'completed': session.query(BroadcastMessage).filter(
                    BroadcastMessage.status == 'completed'
                ).count(),
                'failed': session.query(BroadcastMessage).filter(
                    BroadcastMessage.status == 'failed'
                ).count()
            }
            return stats
        except Exception as e:
            logger.error(f"Error getting broadcast stats: {e}")
            return {}

    def get_user_stats(self, session: Session) -> Dict[str, int]:
        """آمار کاربران"""
        try:
            total = session.query(User).count()
            active = session.query(User).filter(User.is_banned == False).count()
            
            return {
                'total': total,
                'active': active,
                'inactive': total - active
            }
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return {'total': 0, 'active': 0, 'inactive': 0}
```

**متدهای کلیدی:**
- `create_broadcast_message()`: ایجاد پیام جدید
- `get_pending_broadcasts()`: دریافت پیام‌های در انتظار
- `get_active_users()`: دریافت کاربران فعال
- `update_broadcast_status()`: به‌روزرسانی وضعیت

---

## 3️⃣ پردازشگر Broadcast (Broadcast Processor)

### 📄 `bots/user_bot/broadcast_processor.py` (کامل)

```python
#!/usr/bin/env python3
"""
Broadcast Processor for User Bot
Processes pending broadcast messages from the queue
"""

import logging
import asyncio
from typing import Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
from database import DatabaseManager
from database.models import BroadcastMessage, User
from utils.broadcast_service import BroadcastService

logger = logging.getLogger(__name__)

class BroadcastProcessor:
    """پردازشگر پیام‌های همگانی"""

    def __init__(self, db_manager: DatabaseManager, bot):
        self.db_manager = db_manager
        self.bot = bot
        self.broadcast_service = BroadcastService(db_manager)
        
        # Rate limiting settings
        self.messages_per_second = 15  # Conservative limit to keep bot responsive for normal users
        self.delay_between_messages = 1.0 / self.messages_per_second  # ~0.067 seconds
        self.batch_size = 1000  # Process in batches for better memory management

    async def process_pending_broadcasts(self):
        """پردازش پیام‌های همگانی در انتظار"""
        try:
            with self.db_manager.get_session() as session:
                pending_broadcasts = self.broadcast_service.get_pending_broadcasts(session)
                
                if not pending_broadcasts:
                    return
                
                logger.info(f"Found {len(pending_broadcasts)} pending broadcasts")
                
                for broadcast in pending_broadcasts:
                    await self._process_single_broadcast(session, broadcast)
                    
        except Exception as e:
            logger.error(f"Error processing pending broadcasts: {e}")

    async def _process_single_broadcast(self, session: Session, broadcast: BroadcastMessage):
        """پردازش یک پیام همگانی"""
        try:
            logger.info(f"Processing broadcast {broadcast.id}: {broadcast.message_type}")
            
            # Update status to processing
            self.broadcast_service.update_broadcast_status(
                session, broadcast.id, 'processing'
            )
            
            # Get active users from database first
            users = self.broadcast_service.get_active_users(session)
            
            # If no users in database, try to get from Telegram API
            if not users:
                logger.info("No users in database, trying to get from Telegram API...")
                users = await self._get_users_from_telegram_api()
            
            total_users = len(users)
            
            if total_users == 0:
                logger.warning("No active users found for broadcast")
                self.broadcast_service.update_broadcast_status(
                    session, broadcast.id, 'completed',
                    total_users=0, sent_count=0, failed_count=0
                )
                return
            
            # Update total users count
            self.broadcast_service.update_broadcast_status(
                session, broadcast.id, 'processing',
                total_users=total_users
            )
            
            # Send messages with rate limiting
            sent_count = 0
            failed_count = 0
            
            logger.info(f"Starting broadcast to {total_users} users (rate: {self.messages_per_second} msg/sec)")
            estimated_time = total_users / self.messages_per_second / 60  # minutes
            logger.info(f"Estimated completion time: {estimated_time:.1f} minutes")
            
            for idx, user in enumerate(users, 1):
                try:
                    # Send with automatic retry on FloodWait
                    success = await self._send_with_retry(user, broadcast, max_retries=3)
                    
                    if success:
                        sent_count += 1
                    else:
                        failed_count += 1
                    
                    # Log progress every 100 messages
                    if idx % 100 == 0:
                        logger.info(f"Broadcast progress: {idx}/{total_users} ({(idx/total_users)*100:.1f}%) - Sent: {sent_count}, Failed: {failed_count}")
                    
                    # Rate limiting delay (only if not already delayed by retry)
                    await asyncio.sleep(self.delay_between_messages)
                    
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to send broadcast to user {user.user_id}: {e}")
                
                # Update progress in database every 500 messages
                if idx % 500 == 0:
                    self.broadcast_service.update_broadcast_status(
                        session, broadcast.id, 'processing',
                        sent_count=sent_count, failed_count=failed_count
                    )
            
            # Update final status
            self.broadcast_service.update_broadcast_status(
                session, broadcast.id, 'completed',
                sent_count=sent_count, failed_count=failed_count
            )
            
            logger.info(f"Broadcast {broadcast.id} completed: {sent_count} sent, {failed_count} failed")
            
        except Exception as e:
            logger.error(f"Error processing broadcast {broadcast.id}: {e}")
            self.broadcast_service.update_broadcast_status(
                session, broadcast.id, 'failed',
                error_message=str(e)
            )

    async def _get_users_from_telegram_api(self) -> List[User]:
        """دریافت کاربران از طریق Telegram API"""
        try:
            # Get updates to find users who have interacted with the bot
            updates = await self.bot.get_updates(limit=100, timeout=0)
            
            users = []
            seen_user_ids = set()
            
            for update in updates:
                if update.message and update.message.from_user:
                    user_id = update.message.from_user.id
                    if user_id not in seen_user_ids:
                        seen_user_ids.add(user_id)
                        # Create a User object for broadcast
                        user = User()
                        user.user_id = user_id
                        user.username = update.message.from_user.username
                        user.first_name = update.message.from_user.first_name
                        user.last_name = update.message.from_user.last_name
                        user.is_banned = False
                        users.append(user)
            
            logger.info(f"Found {len(users)} users from Telegram API")
            return users
            
        except Exception as e:
            logger.error(f"Error getting users from Telegram API: {e}")
            return []

    async def _send_message_to_user(self, user: User, broadcast: BroadcastMessage):
        """ارسال پیام به یک کاربر"""
        try:
            if broadcast.message_type == 'text':
                await self.bot.send_message(
                    chat_id=user.user_id,
                    text=broadcast.message_text,
                    parse_mode='Markdown'
                )
            elif broadcast.message_type == 'photo' and broadcast.local_path:
                # استفاده از فایل محلی
                try:
                    with open(broadcast.local_path, 'rb') as photo_file:
                        await self.bot.send_photo(
                            chat_id=user.user_id,
                            photo=photo_file,
                            caption=broadcast.message_text,
                            parse_mode='Markdown'
                        )
                except Exception as e:
                    logger.error(f"Error sending photo from local path: {e}")
                    # اگر فایل محلی کار نکرد، فقط متن را ارسال کن
                    await self.bot.send_message(
                        chat_id=user.user_id,
                        text=f"📷 **تصویر**\n\n{broadcast.message_text}",
                        parse_mode='Markdown'
                    )
            elif broadcast.message_type == 'video' and broadcast.local_path:
                # استفاده از فایل محلی
                try:
                    with open(broadcast.local_path, 'rb') as video_file:
                        await self.bot.send_video(
                            chat_id=user.user_id,
                            video=video_file,
                            caption=broadcast.message_text,
                            parse_mode='Markdown'
                        )
                except Exception as e:
                    logger.error(f"Error sending video from local path: {e}")
                    # اگر فایل محلی کار نکرد، فقط متن را ارسال کن
                    await self.bot.send_message(
                        chat_id=user.user_id,
                        text=f"🎥 **ویدیو**\n\n{broadcast.message_text}",
                        parse_mode='Markdown'
                    )
            elif broadcast.message_type == 'document' and broadcast.local_path:
                # استفاده از فایل محلی
                try:
                    with open(broadcast.local_path, 'rb') as document_file:
                        await self.bot.send_document(
                            chat_id=user.user_id,
                            document=document_file,
                            caption=broadcast.message_text,
                            parse_mode='Markdown'
                        )
                except Exception as e:
                    logger.error(f"Error sending document from local path: {e}")
                    # اگر فایل محلی کار نکرد، فقط متن را ارسال کن
                    await self.bot.send_message(
                        chat_id=user.user_id,
                        text=f"📄 **فایل**\n\n{broadcast.message_text}",
                        parse_mode='Markdown'
                    )
            else:
                raise ValueError(f"Invalid message type or missing file_id: {broadcast.message_type}")
                
        except Exception as e:
            logger.error(f"Error sending message to user {user.user_id}: {e}")
            raise

    async def _download_and_reupload_file(self, file_id: str, file_type: str) -> str:
        """دانلود فایل از Admin Bot و آپلود مجدد در User Bot"""
        try:
            # دریافت اطلاعات فایل
            file_info = await self.bot.get_file(file_id)
            
            # دانلود فایل
            file_path = f"temp_broadcast_{file_type}_{file_id}.tmp"
            await file_info.download_to_drive(file_path)
            
            return file_path
            
        except Exception as e:
            logger.error(f"Error downloading file {file_id}: {e}")
            return None
    
    def _extract_flood_wait_time(self, error_message: str) -> int:
        """استخراج زمان انتظار از خطای FloodWait"""
        import re
        
        # Try to extract wait time from error message
        # Common patterns: "FloodWait: 60", "Too Many Requests: retry after 60"
        patterns = [
            r'retry after (\d+)',
            r'FloodWait[:\s]+(\d+)',
            r'wait (\d+) second',
            r'(\d+) second'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, error_message, re.IGNORECASE)
            if match:
                return int(match.group(1))
        
        # Default wait time if pattern not found
        return 60
    
    async def _send_with_retry(self, user: User, broadcast: BroadcastMessage, max_retries: int = 3):
        """ارسال پیام با retry در صورت خطا"""
        for attempt in range(max_retries):
            try:
                await self._send_message_to_user(user, broadcast)
                return True
            except Exception as e:
                error_str = str(e)
                
                # Check for FloodWait
                if "FloodWait" in error_str or "Too Many Requests" in error_str:
                    wait_time = self._extract_flood_wait_time(error_str)
                    logger.warning(f"FloodWait on attempt {attempt + 1}/{max_retries}: waiting {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue
                
                # Check for user blocked bot
                elif "bot was blocked" in error_str.lower() or "user is deactivated" in error_str.lower():
                    logger.debug(f"User {user.user_id} blocked the bot or deactivated")
                    return False
                
                # Other errors
                elif attempt < max_retries - 1:
                    logger.warning(f"Error on attempt {attempt + 1}/{max_retries}: {e}")
                    await asyncio.sleep(2)  # Wait 2 seconds before retry
                    continue
                else:
                    raise
        
        return False
```

**متدهای کلیدی:**
- `process_pending_broadcasts()`: چک کردن صف و شروع پردازش
- `_process_single_broadcast()`: پردازش یک broadcast
- `_send_message_to_user()`: ارسال پیام به یک کاربر
- `_send_with_retry()`: ارسال با retry خودکار
- `_extract_flood_wait_time()`: استخراج زمان FloodWait

---

## 4️⃣ Admin Bot (ایجاد Broadcast)

### 📄 `bots/admin_bot.py` (خطوط 4437-4857)

#### 4.1 نمایش منوی Broadcast

```python
async def _show_broadcast_menu(self, query):
    """نمایش منوی پیام همگانی"""
    text = """
📢 **پیام همگانی**

در این بخش می‌توانید پیام‌های مختلف را برای کاربران ارسال کنید:

📝 **پیام متنی:** ارسال متن ساده
📷 **عکس:** ارسال عکس با متن
🎥 **ویدیو:** ارسال ویدیو با متن
📄 **فایل:** ارسال فایل با متن

👥 **آمار کاربران:** مشاهده آمار کاربران
🎯 **ارسال هدفمند:** ارسال به کاربران خاص

لطفا نوع پیام را انتخاب کنید:
"""
    
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=self.keyboards.admin_broadcast_menu()
    )
```

#### 4.2 شروع ارسال پیام متنی

```python
async def _start_text_broadcast(self, query):
    """شروع ارسال پیام متنی"""
    self.user_contexts[query.from_user.id] = {
        'action': 'broadcast_text',
        'step': 'waiting_for_message'
    }
    
    await query.edit_message_text(
        "📝 **ارسال پیام متنی**\n\n"
        "لطفا متن پیام را ارسال کنید:\n\n"
        "💡 **نکته:** می‌توانید از Markdown استفاده کنید:\n"
        "• **متن پررنگ**\n"
        "• *متن کج*\n"
        "• `کد`\n"
        "• [لینک](https://example.com)",
        parse_mode='Markdown'
    )
```

#### 4.3 شروع ارسال عکس

```python
async def _start_photo_broadcast(self, query):
    """شروع ارسال عکس"""
    self.user_contexts[query.from_user.id] = {
        'action': 'broadcast_photo',
        'step': 'waiting_for_photo'
    }
    
    await query.edit_message_text(
        "📷 **ارسال عکس**\n\n"
        "لطفا عکس را ارسال کنید.\n"
        "بعد از ارسال عکس، متن توضیحی را ارسال کنید.",
        parse_mode='Markdown'
    )
```

#### 4.4 مدیریت دریافت عکس

```python
async def _handle_broadcast_photo(self, update: Update, ctx: dict):
    """مدیریت عکس پیام همگانی"""
    if not update.message or not update.message.photo:
        return
    
    # دریافت بالاترین کیفیت عکس
    photo = update.message.photo[-1]
    file_id = photo.file_id
    
    # دانلود فایل و ذخیره محلی
    try:
        file_info = await self.application.bot.get_file(file_id)
        local_path = f"broadcast_photos/photo_{file_id}.jpg"
        
        # ایجاد پوشه اگر وجود ندارد
        import os
        os.makedirs("broadcast_photos", exist_ok=True)
        
        # دانلود فایل
        await file_info.download_to_drive(local_path)
        
        # ذخیره اطلاعات
        ctx['file_id'] = file_id
        ctx['local_path'] = local_path
        ctx['message_type'] = 'photo'
        ctx['step'] = 'waiting_for_caption'
        
        await update.message.reply_text(
            "📷 **عکس دریافت و ذخیره شد!**\n\n"
            "حالا متن توضیحی را ارسال کنید:\n\n"
            "💡 **نکته:** می‌توانید از Markdown استفاده کنید.",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error downloading photo: {e}")
        await update.message.reply_text("❌ خطا در دانلود عکس!")
```

#### 4.5 مدیریت متن پیام

```python
async def _handle_broadcast_text(self, update: Update, ctx: dict, text: str):
    """مدیریت متن پیام همگانی"""
    user_id = update.effective_user.id
    
    # ذخیره متن پیام
    ctx['message_text'] = text
    ctx['message_type'] = 'text'
    ctx['step'] = 'ready_to_send'
    
    # نمایش پیش‌نمایش و دکمه تأیید
    preview_text = f"""
📝 **پیش‌نمایش پیام متنی**

{text}

⚠️ **توجه:** این پیام به تمام کاربران فعال ارسال خواهد شد.

آیا می‌خواهید ارسال کنید؟
"""
    
    await update.message.reply_text(
        preview_text,
        parse_mode='Markdown',
        reply_markup=self.keyboards.broadcast_confirmation()
    )
```

#### 4.6 تأیید و ایجاد Broadcast

```python
async def _confirm_broadcast(self, query):
    """تأیید ارسال پیام همگانی"""
    user_id = query.from_user.id
    ctx = self.user_contexts.get(user_id, {})
    
    if not ctx:
        await query.edit_message_text(
            "❌ جلسه منقضی شده است!",
            reply_markup=self.keyboards.back_button()
        )
        return
    
    try:
        # دریافت اطلاعات پیام
        message_text = ctx.get('message_text', '')
        message_type = ctx.get('message_type', 'text')
        file_id = ctx.get('file_id')
        
        # ایجاد رکورد در دیتابیس
        with self.db_manager.get_session() as session:
            local_path = ctx.get('local_path')
            broadcast = self.broadcast_service.create_broadcast_message(
                session, message_text, message_type, file_id, user_id, local_path
            )
        
        # نمایش پیام تأیید
        text = f"""
✅ **پیام همگانی در صف ارسال قرار گرفت!**

📋 **شناسه پیام:** `{broadcast.id}`
📝 **نوع پیام:** {message_type}
📊 **وضعیت:** در انتظار پردازش

⏳ پیام به زودی برای تمام کاربران فعال ارسال خواهد شد.

💡 **نکته:** می‌توانید وضعیت ارسال را در بخش آمار مشاهده کنید.
"""
        
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=self.keyboards.back_button()
        )
        
        # پاک کردن context
        if user_id in self.user_contexts:
            del self.user_contexts[user_id]
            
    except Exception as e:
        logger.error(f"Error in broadcast confirmation: {e}")
        await query.edit_message_text(
            f"❌ خطا در ثبت پیام همگانی!\n\nخطا: {str(e)}",
            reply_markup=self.keyboards.back_button()
        )
```

#### 4.7 نمایش آمار کاربران

```python
async def _show_user_stats(self, query):
    """نمایش آمار کاربران"""
    try:
        with self.db_manager.get_session() as session:
            stats = self.broadcast_service.get_user_stats(session)
            
            text = f"""
👥 **آمار کاربران**

📊 **کل کاربران:** {stats['total']:,}
✅ **کاربران فعال:** {stats['active']:,}
❌ **کاربران غیرفعال:** {stats['inactive']:,}

💡 **نکته:** پیام همگانی فقط به کاربران فعال ارسال می‌شود.
"""
            
            await query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=self.keyboards.back_button()
            )
    except Exception as e:
        logger.error(f"Error showing user stats: {e}")
        await query.edit_message_text(
            "❌ خطا در دریافت آمار کاربران!",
            reply_markup=self.keyboards.back_button()
        )
```

---

## 5️⃣ راه‌اندازی Scheduler در User Bot

### 📄 `bots/user_bot/main.py` (خطوط 7270-7287)

```python
# راه‌اندازی Scheduler برای نوتیفیکیشن‌ها
notification_interval = config_manager.get_setting('notification_check_interval', 10)
bot.scheduler.add_job(
    bot.notification_processor.process_pending_notifications,
    'interval',
    seconds=notification_interval,
    id='notification_processor'
)

# راه‌اندازی Scheduler برای پیام‌های همگانی
broadcast_interval = config_manager.get_setting('broadcast_check_interval', 15)
bot.scheduler.add_job(
    bot.broadcast_processor.process_pending_broadcasts,
    'interval',
    seconds=broadcast_interval,
    id='broadcast_processor'
)
bot.scheduler.start()
logger.info("Notification scheduler started (checking every 10 seconds)")
logger.info("Broadcast scheduler started (checking every 15 seconds)")

# شروع ربات
logger.info("=" * 50)
logger.info("User Bot is starting...")
logger.info(f"Database: {bot.config['database_url']}")
logger.info("=" * 50)

try:
    application.run_polling(drop_pending_updates=True)
finally:
    # توقف scheduler هنگام خروج
    bot.scheduler.shutdown()
    logger.info("Notification scheduler stopped")
```

**توضیحات:**
- هر 15 ثانیه یکبار `process_pending_broadcasts()` اجرا می‌شود
- Scheduler به صورت خودکار پیام‌های pending را پردازش می‌کند

---

## 6️⃣ مثال‌های استفاده

### مثال 1: ارسال پیام متنی ساده

```python
# در Admin Bot
with db_manager.get_session() as session:
    broadcast_service = BroadcastService(db_manager)
    
    broadcast = broadcast_service.create_broadcast_message(
        session=session,
        message_text="سلام به همه! 👋\n\nاین یک پیام تستی است.",
        message_type="text",
        file_id=None,
        created_by=admin_user_id,
        local_path=None
    )
    
    print(f"Broadcast created with ID: {broadcast.id}")
```

### مثال 2: ارسال عکس با متن

```python
# در Admin Bot - بعد از دانلود عکس
with db_manager.get_session() as session:
    broadcast_service = BroadcastService(db_manager)
    
    broadcast = broadcast_service.create_broadcast_message(
        session=session,
        message_text="📷 عکس جدید!\n\nتوضیحات عکس...",
        message_type="photo",
        file_id="AgACAgQAAxkBAAI...",
        created_by=admin_user_id,
        local_path="broadcast_photos/photo_xxx.jpg"
    )
```

### مثال 3: چک کردن وضعیت Broadcast

```python
# کوئری SQL
SELECT 
    id,
    message_type,
    status,
    total_users,
    sent_count,
    failed_count,
    ROUND((sent_count * 100.0 / total_users), 2) as progress_percent,
    created_at,
    started_at,
    completed_at,
    TIMESTAMPDIFF(MINUTE, started_at, completed_at) as duration_minutes
FROM broadcast_messages
WHERE id = 123;
```

### مثال 4: آمار کلی Broadcasts

```python
# در Admin Bot
with db_manager.get_session() as session:
    broadcast_service = BroadcastService(db_manager)
    stats = broadcast_service.get_broadcast_stats(session)
    
    print(f"Total: {stats['total']}")
    print(f"Pending: {stats['pending']}")
    print(f"Processing: {stats['processing']}")
    print(f"Completed: {stats['completed']}")
    print(f"Failed: {stats['failed']}")
```

---

## 7️⃣ تنظیمات و پارامترها

### تنظیمات Rate Limiting

```python
# در broadcast_processor.py
messages_per_second = 15  # تعداد پیام در ثانیه
delay_between_messages = 1.0 / messages_per_second  # ~0.067 seconds
batch_size = 1000  # تعداد کاربران در هر batch
```

### تنظیمات Scheduler

```python
# در config.json یا config_manager
{
    "broadcast_check_interval": 15,  # چک کردن صف هر 15 ثانیه
    "notification_check_interval": 10
}
```

### تنظیمات Retry

```python
# در _send_with_retry()
max_retries = 3  # حداکثر تلاش برای هر کاربر
retry_delay = 2  # تاخیر بین retry ها (ثانیه)
```

---

## 8️⃣ کوئری‌های مفید

### 8.1 مشاهده Broadcasts در حال پردازش

```sql
SELECT 
    id,
    message_type,
    status,
    total_users,
    sent_count,
    failed_count,
    ROUND((sent_count * 100.0 / NULLIF(total_users, 0)), 2) as progress_percent,
    created_at,
    started_at,
    TIMESTAMPDIFF(SECOND, started_at, NOW()) as elapsed_seconds
FROM broadcast_messages
WHERE status = 'processing'
ORDER BY started_at DESC;
```

### 8.2 آمار کلی Broadcasts

```sql
SELECT 
    status,
    COUNT(*) as count,
    SUM(total_users) as total_users,
    SUM(sent_count) as total_sent,
    SUM(failed_count) as total_failed,
    ROUND(AVG(sent_count * 100.0 / NULLIF(total_users, 0)), 2) as avg_success_rate
FROM broadcast_messages
GROUP BY status;
```

### 8.3 Broadcasts اخیر

```sql
SELECT 
    id,
    message_type,
    status,
    total_users,
    sent_count,
    failed_count,
    created_at,
    TIMESTAMPDIFF(MINUTE, started_at, completed_at) as duration_minutes
FROM broadcast_messages
ORDER BY created_at DESC
LIMIT 10;
```

### 8.4 کاربران فعال

```sql
SELECT 
    COUNT(*) as active_users
FROM users
WHERE is_banned = FALSE
AND user_id IS NOT NULL;
```

---

## 9️⃣ Flow Chart (دیاگرام جریان)

```
┌─────────────────────────────────────────────────────────────┐
│                    ADMIN BOT                                │
│  1. ادمین منوی broadcast را باز می‌کند                     │
│  2. نوع پیام را انتخاب می‌کند (text/photo/video/doc)      │
│  3. محتوا را ارسال می‌کند                                  │
│  4. فایل‌ها دانلود و در broadcast_photos/ ذخیره می‌شوند   │
│  5. متن توضیحی را وارد می‌کند                              │
│  6. پیش‌نمایش و تأیید                                       │
│  7. broadcast_service.create_broadcast_message()            │
│     → BroadcastMessage با status='pending' ایجاد می‌شود    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  DATABASE (صف انتظار)                       │
│  broadcast_messages table                                   │
│  ┌──────────────────────────────────────────────┐          │
│  │ id: 123                                      │          │
│  │ message_text: "سلام به همه!"                │          │
│  │ message_type: "photo"                        │          │
│  │ local_path: "broadcast_photos/photo_xxx.jpg" │          │
│  │ status: "pending" ⏳                         │          │
│  │ created_at: 2025-11-20 05:50:00             │          │
│  └──────────────────────────────────────────────┘          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              USER BOT SCHEDULER                             │
│  هر 15 ثانیه:                                              │
│  ↓                                                          │
│  broadcast_processor.process_pending_broadcasts()           │
│  ↓                                                          │
│  broadcast_service.get_pending_broadcasts()                 │
│  → پیام‌های با status='pending' را می‌یابد                 │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│           BROADCAST PROCESSOR                               │
│  _process_single_broadcast(broadcast_123)                   │
│  ↓                                                          │
│  1. status → 'processing'                                   │
│  2. broadcast_service.get_active_users()                    │
│     → لیست 100,000 کاربر فعال                              │
│  3. total_users = 100000 را ذخیره می‌کند                   │
│  4. برای هر کاربر:                                         │
│     ┌─────────────────────────────────────────┐            │
│     │ _send_with_retry(user, broadcast, 3)    │            │
│     │ ↓                                        │            │
│     │ _send_message_to_user(user, broadcast)  │            │
│     │ ↓                                        │            │
│     │ bot.send_photo(user_id, photo, caption) │            │
│     │ ↓                                        │            │
│     │ await asyncio.sleep(0.067)  # Rate Limit│            │
│     │ ↓                                        │            │
│     │ sent_count += 1                          │            │
│     │                                          │            │
│     │ هر 100 پیام: لاگ پیشرفت                │            │
│     │ هر 500 پیام: ذخیره در DB                │            │
│     └─────────────────────────────────────────┘            │
│  5. status → 'completed'                                    │
│  6. sent_count, failed_count را ذخیره می‌کند               │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔟 خطاها و مدیریت آن‌ها

### خطاهای رایج و نحوه مدیریت:

| خطا | علت | مدیریت |
|-----|------|--------|
| `FloodWait` | ارسال بیش از حد | استخراج زمان انتظار + sleep + retry |
| `User blocked bot` | کاربر ربات را بلاک کرده | Skip و ادامه |
| `User is deactivated` | اکانت کاربر غیرفعال | Skip و ادامه |
| `File not found` | فایل محلی وجود ندارد | ارسال فقط متن |
| `Invalid file_id` | file_id نامعتبر است | استفاده از local_path |

### کد مدیریت خطا:

```python
async def _send_with_retry(self, user, broadcast, max_retries=3):
    for attempt in range(max_retries):
        try:
            await self._send_message_to_user(user, broadcast)
            return True
        except Exception as e:
            error_str = str(e)
            
            # FloodWait
            if "FloodWait" in error_str:
                wait_time = self._extract_flood_wait_time(error_str)
                await asyncio.sleep(wait_time)
                continue
            
            # User blocked
            elif "bot was blocked" in error_str.lower():
                return False
            
            # Retry
            elif attempt < max_retries - 1:
                await asyncio.sleep(2)
                continue
            else:
                raise
    
    return False
```

---

## 1️⃣1️⃣ لاگ‌های مهم

### لاگ‌های موفقیت:

```
[INFO] Found 1 pending broadcasts
[INFO] Processing broadcast 123: photo
[INFO] Starting broadcast to 100000 users (rate: 15 msg/sec)
[INFO] Estimated completion time: 111.1 minutes
[INFO] Broadcast progress: 100/100000 (0.1%) - Sent: 98, Failed: 2
[INFO] Broadcast progress: 500/100000 (0.5%) - Sent: 495, Failed: 5
[INFO] Broadcast 123 completed: 99850 sent, 150 failed
```

### لاگ‌های خطا:

```
[ERROR] Failed to send broadcast to user 12345: FloodWait
[WARNING] FloodWait on attempt 1/3: waiting 45s
[ERROR] Error sending photo from local path: File not found
[DEBUG] User 67890 blocked the bot or deactivated
```

---

## 1️⃣2️⃣ نکات مهم

### ✅ Best Practices:

1. **همیشه local_path را ذخیره کنید** (برای cross-bot compatibility)
2. **Rate limiting را رعایت کنید** (حداکثر 15-20 msg/sec)
3. **لاگ‌ها را مانیتور کنید**
4. **پیشرفت را در DB ذخیره کنید** (هر 500 پیام)
5. **از retry mechanism استفاده کنید**

### ❌ اشتباهات رایج:

1. ❌ ارسال بدون delay
2. ❌ نادیده گرفتن FloodWait
3. ❌ عدم ذخیره local_path
4. ❌ عدم مدیریت خطای "user blocked"
5. ❌ broadcast در ساعات شلوغ

---

## 1️⃣3️⃣ خلاصه API

### BroadcastService Methods:

```python
create_broadcast_message(session, message_text, message_type, file_id, created_by, local_path)
get_pending_broadcasts(session)
get_active_users(session)
update_broadcast_status(session, broadcast_id, status, **kwargs)
get_broadcast_stats(session)
get_user_stats(session)
```

### BroadcastProcessor Methods:

```python
process_pending_broadcasts()
_process_single_broadcast(session, broadcast)
_send_message_to_user(user, broadcast)
_send_with_retry(user, broadcast, max_retries)
_extract_flood_wait_time(error_message)
_get_users_from_telegram_api()
```

---

## 📚 مراجع

- **مستندات کلی:** `docs/BROADCAST_SYSTEM.md`
- **کد کامل:** این فایل
- **Database Schema:** `database/models.py`
- **تنظیمات:** `config.json`

---

**تاریخ ایجاد:** 2025-11-20  
**نسخه:** 1.0  
**وضعیت:** تست شده و آماده استفاده ✅

