# 🏗️ معماری وب اپلیکیشن تماس صوتی/تصویری
## برای 10,000 کاربر در ساعت (تماس 2 نفره)

---

## 📊 تحلیل مقیاس

### نیازمندی‌ها:
- **10,000 کاربر در ساعت** = حدود **167 کاربر در دقیقه**
- **تماس 2 نفره** (1-to-1 calls)
- **متوسط تماس**: 3-5 دقیقه
- **Concurrent calls**: ~1000 تماس همزمان (در اوج)
- **Concurrent connections**: ~2000 WebSocket connections

### نتیجه‌گیری:
این مقیاس **متوسط** است و با یک سرور مناسب قابل مدیریت است.

---

## ✅ معماری پیشنهادی

### 🎯 **Peer-to-Peer (P2P) با WebRTC**

**چرا P2P؟**
- ✅ برای تماس 2 نفره **بهینه‌ترین** راه است
- ✅ بار سرور **کم** (فقط signaling)
- ✅ کیفیت بهتر (مستقیم بین کاربران)
- ✅ هزینه کمتر (بدون server bandwidth)

### 📐 ساختار:

```
┌─────────────────────────────────────────────────────────┐
│                     Telegram Bot                        │
│  (ارسال لینک، تایید تماس، مدیریت state)                │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              FastAPI Backend (Python)                    │
│  ┌──────────────────────────────────────────────────┐   │
│  │  REST API:                                      │   │
│  │  - POST /api/video-call/create                  │   │
│  │  - GET  /api/video-call/{room_id}/verify        │   │
│  │  - POST /api/video-call/{room_id}/join          │   │
│  └──────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────┐   │
│  │  WebSocket Server (Signaling):                   │   │
│  │  - WS /ws/video-call/{room_id}                   │   │
│  │    - Exchange SDP offers/answers                  │   │
│  │    - Exchange ICE candidates                      │   │
│  │    - User joined/left events                      │   │
│  └──────────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                    Redis Cache                           │
│  - Room data (room_id, user_ids, status)                 │
│  - Token storage                                         │
│  - Active sessions                                       │
└─────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                  MySQL Database                          │
│  - Chat rooms                                            │
│  - User data                                             │
│  - Call history (optional)                               │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│              Frontend Web App (React)                    │
│  ┌──────────────────────────────────────────────────┐   │
│  │  WebRTC Peer Connection:                         │   │
│  │  - getUserMedia() → Local stream                 │   │
│  │  - RTCPeerConnection → Peer-to-peer             │   │
│  │  - Direct media transfer (no server)             │   │
│  └──────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────┐   │
│  │  WebSocket Client:                               │   │
│  │  - Connect to signaling server                   │   │
│  │  - Send/receive SDP and ICE                      │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│              STUN/TURN Servers                          │
│  - STUN: برای NAT traversal (رایگان)                    │
│  - TURN: برای کاربران با NAT strict (اختیاری)          │
└─────────────────────────────────────────────────────────┘
```

---

## 🛠️ تکنولوژی‌های انتخاب شده

### Backend:
1. **FastAPI** ✅ (قبلاً موجود)
   - WebSocket endpoints برای signaling
   - REST API برای room management

2. **Redis** ✅ (قبلاً موجود)
   - Room data storage
   - Token storage
   - Session management

3. **MySQL** ✅ (قبلاً موجود)
   - User data
   - Chat room data

### Frontend:
1. **React + TypeScript + Vite**
   - Fast build
   - Type safety
   - Hot reload

2. **simple-peer** (برای WebRTC)
   - ✅ ساده و سبک
   - ✅ مناسب برای 1-to-1 calls
   - ✅ Documentation خوب
   - ✅ Stable و mature

3. **Socket.io-client** یا native WebSocket
   - برای signaling

4. **Tailwind CSS**
   - سریع برای styling
   - Responsive design

---

## 🔄 جریان کار دقیق

### Step 1: در Bot (قبلاً پیاده‌سازی شده)
```
کاربر A (پریمیوم) → درخواست تماس تصویری
کاربر B → تایید تماس
```

### Step 2: ایجاد Room و Token
```python
# در Bot handler (accept_call_request)
1. ایجاد room در Redis:
   - room_id = uuid.uuid4()
   - user1_id, user2_id, chat_room_id, call_type
   - status = "pending"

2. ایجاد token برای هر کاربر:
   - token_a = generate_jwt_token(user_a.id, room_id)
   - token_b = generate_jwt_token(user_b.id, room_id)

3. ارسال لینک به هر دو کاربر:
   - لینک A: https://your-domain.com/call/{room_id}?token={token_a}
   - لینک B: https://your-domain.com/call/{room_id}?token={token_b}
```

### Step 3: Frontend - ورود به Room
```
1. کاربر روی لینک کلیک می‌کند
2. صفحه React باز می‌شود
3. استخراج room_id و token از URL
4. GET /api/video-call/{room_id}/verify?token={token}
   → بررسی دسترسی و دریافت اطلاعات room
5. اتصال به WebSocket: WS /ws/video-call/{room_id}?token={token}
```

### Step 4: WebRTC Setup
```
1. getUserMedia():
   - تماس تصویری: { video: true, audio: true }
   - تماس صوتی: { video: false, audio: true }

2. ایجاد RTCPeerConnection:
   - peer = new RTCPeerConnection({
       iceServers: [
         { urls: "stun:stun.l.google.com:19302" },
         { urls: "stun:stun1.l.google.com:19302" }
       ]
     })

3. اضافه کردن local stream به peer:
   - localStream.getTracks().forEach(track => {
       peer.addTrack(track, localStream)
     })

4. ایجاد offer و ارسال از طریق WebSocket:
   - offer = await peer.createOffer()
   - await peer.setLocalDescription(offer)
   - websocket.send({ type: "offer", sdp: offer.sdp })

5. دریافت offer از طرف مقابل:
   - await peer.setRemoteDescription(remoteOffer)
   - answer = await peer.createAnswer()
   - await peer.setLocalDescription(answer)
   - websocket.send({ type: "answer", sdp: answer.sdp })

6. Exchange ICE candidates:
   - peer.onicecandidate → send via WebSocket
   - receive ICE → peer.addIceCandidate()

7. دریافت remote stream:
   - peer.ontrack → event.streams[0]
   - نمایش remote video/audio
```

### Step 5: در طول تماس
```
- نمایش local و remote streams
- کنترل‌ها:
  - Mute/Unmute
  - Video on/off
  - Hang up
- ارسال events به backend:
  - call-started
  - call-ended
  - duration tracking
```

### Step 6: پایان تماس
```
1. Hang up → cleanup:
   - peer.close()
   - localStream.getTracks().forEach(track => track.stop())
   - websocket.close()

2. اطلاع به Bot:
   - POST /api/video-call/{room_id}/end
   - Bot → به‌روزرسانی status در Redis
   - ارسال پیام به کاربران در Bot
```

---

## 🔐 احراز هویت

### JWT Token Structure:
```json
{
  "user_id": 123,
  "room_id": "uuid",
  "chat_room_id": 789,
  "call_type": "video",
  "exp": 1234567890
}
```

### Token Generation:
```python
import jwt
from datetime import datetime, timedelta

def generate_call_token(user_id: int, room_id: str, chat_room_id: int, call_type: str):
    payload = {
        "user_id": user_id,
        "room_id": room_id,
        "chat_room_id": chat_room_id,
        "call_type": call_type,
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(payload, settings.API_SECRET_KEY, algorithm="HS256")
```

### Token Verification:
```python
@app.get("/api/video-call/{room_id}/verify")
async def verify_token(room_id: str, token: str):
    try:
        payload = jwt.decode(token, settings.API_SECRET_KEY, algorithms=["HS256"])
        if payload["room_id"] != room_id:
            raise HTTPException(403, "Invalid token")
        
        # Check room exists
        room_data = await redis_client.get(f"video_call:room:{room_id}")
        if not room_data:
            raise HTTPException(404, "Room not found")
        
        # Check user is authorized (user_id in room_data)
        return {"authorized": True, "user_id": payload["user_id"]}
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except:
        raise HTTPException(403, "Invalid token")
```

---

## 🌐 WebSocket Signaling

### Connection:
```python
@app.websocket("/ws/video-call/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, token: str):
    await websocket.accept()
    
    # Verify token
    payload = jwt.decode(token, settings.API_SECRET_KEY, algorithms=["HS256"])
    user_id = payload["user_id"]
    
    # Check room access
    room_data = await redis_client.get(f"video_call:room:{room_id}")
    if not room_data:
        await websocket.close(code=1008, reason="Room not found")
        return
    
    # Store connection
    await redis_client.sadd(f"room:connections:{room_id}", user_id)
    
    # Notify other user
    await broadcast_to_room(room_id, {"type": "user-joined", "user_id": user_id}, exclude=user_id)
    
    try:
        while True:
            message = await websocket.receive_json()
            
            # Forward message to other user
            if message["type"] in ["offer", "answer", "ice-candidate"]:
                await broadcast_to_room(room_id, message, exclude=user_id)
                
    except WebSocketDisconnect:
        await redis_client.srem(f"room:connections:{room_id}", user_id)
        await broadcast_to_room(room_id, {"type": "user-left", "user_id": user_id}, exclude=user_id)
```

---

## 📦 Package.json پیشنهادی (Frontend)

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0",
    "simple-peer": "^9.11.1",
    "socket.io-client": "^4.5.4",
    "zustand": "^4.4.7",
    "axios": "^1.6.2"
  },
  "devDependencies": {
    "@types/react": "^18.2.43",
    "@types/react-dom": "^18.2.17",
    "@types/simple-peer": "^9.11.8",
    "@vitejs/plugin-react": "^4.2.1",
    "typescript": "^5.3.3",
    "vite": "^5.0.8",
    "tailwindcss": "^3.3.6"
  }
}
```

---

## 🚀 Deployment Strategy

### Option 1: **Docker Compose** (پیشنهادی)
```
docker-compose.yml:
  - bot (Python)
  - mysql
  - redis
  - nginx (برای serve کردن frontend)
  - frontend (build شده)
```

### Option 2: **Separate Hosting**
```
- Bot + FastAPI → VPS یا Cloud
- Frontend → Netlify/Vercel/Cloudflare Pages
- CDN → برای static assets
```

---

## ⚡ Optimization برای 10k Users/Hour

### 1. **WebSocket Scaling**
- استفاده از Redis Pub/Sub برای multi-instance
- Connection pooling
- Message queuing (اگر نیاز باشد)

### 2. **Redis Optimization**
- Connection pooling
- Expire keys مناسب
- Cleanup old rooms

### 3. **Frontend Optimization**
- Code splitting
- Lazy loading
- CDN برای assets
- Compression

### 4. **STUN/TURN Servers**
- استفاده از Google STUN (رایگان)
- TURN server اختیاری (برای NAT strict)
- می‌توانید از Twilio TURN استفاده کنید

---

## 📝 مراحل پیاده‌سازی (Recommended Order)

### ✅ Phase 1: Backend Extensions (1-2 روز)
1. Token generation endpoint
2. WebSocket signaling endpoint
3. Room verification endpoint
4. Integration با Bot handlers

### ✅ Phase 2: Frontend Setup (2-3 روز)
1. React project setup
2. Routing
3. Token extraction از URL
4. API integration

### ✅ Phase 3: WebRTC (3-4 روز)
1. getUserMedia
2. Peer connection setup
3. WebSocket signaling
4. SDP/ICE exchange
5. Stream handling

### ✅ Phase 4: UI/UX (2-3 روز)
1. Call room UI
2. Controls (mute, video, hang up)
3. Loading/error states
4. Responsive design

### ✅ Phase 5: Integration & Testing (2-3 روز)
1. Bot → Web App integration
2. End-to-end testing
3. Performance testing
4. Bug fixes

**Total: ~10-15 روز**

---

## 🎯 توصیه نهایی

### برای 10,000 کاربر در ساعت:
✅ **Peer-to-Peer (P2P)** بهترین انتخاب است
✅ **simple-peer** برای پیاده‌سازی سریع
✅ **FastAPI WebSocket** برای signaling
✅ **Redis** برای room management
✅ **STUN servers** برای NAT traversal (رایگان)

### چرا این معماری؟
1. ✅ **بهینه برای تماس 2 نفره**: P2P مستقیم، بدون server bandwidth
2. ✅ **مقیاس‌پذیر**: فقط signaling server load دارد (سبک است)
3. ✅ **هزینه کم**: استفاده از STUN رایگان، TURN اختیاری
4. ✅ **کیفیت بهتر**: اتصال مستقیم بین کاربران
5. ✅ **پیاده‌سازی ساده**: simple-peer ساده‌تر از mediasoup

---

این معماری برای نیاز شما (10k user/hour, 1-to-1 calls) **بهینه** است. ✅

