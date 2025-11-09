# 📋 پلان اجرایی وب اپلیکیشن تماس صوتی و تصویری

## 🎯 هدف
ایجاد یک وب اپلیکیشن برای تماس صوتی و تصویری بین کاربران که از طریق Telegram Bot قابل دسترسی باشد.

---

## 🏗️ معماری کلی

### 1. **Backend API** (قبلاً وجود دارد)
- ✅ FastAPI server (`api/video_call.py`)
- ✅ Endpoint برای ایجاد room: `POST /api/video-call/create`
- ✅ Endpoint برای دریافت اطلاعات: `GET /api/video-call/{room_id}`
- ✅ Endpoint برای حذف: `DELETE /api/video-call/{room_id}`
- ✅ Redis برای ذخیره اطلاعات room

### 2. **Frontend Web App** (باید ایجاد شود)
- **Framework**: React.js یا Vue.js (پیشنهاد: React با TypeScript)
- **WebRTC Library**: 
  - `simple-peer` یا 
  - `peerjs` یا
  - `mediasoup-client` (برای scalability بیشتر)
- **UI Framework**: 
  - Tailwind CSS یا
  - Material-UI یا
  - Ant Design
- **State Management**: 
  - Zustand یا
  - Redux Toolkit

### 3. **Signaling Server** (نیاز به پیاده‌سازی)
- **WebSocket Server**: برای exchange کردن signaling messages
- **Options**:
  - FastAPI WebSocket endpoints
  - Socket.io (Node.js) یا
  - Python WebSockets
- **Functionality**:
  - Exchange SDP offers/answers
  - ICE candidate exchange
  - Room management

---

## 🔄 جریان کار (Flow)

### مرحله 1: درخواست تماس (Bot)
1. کاربر پریمیوم روی "شروع تماس تصویری/صوتی" کلیک می‌کند
2. درخواست به کاربر مقابل ارسال می‌شود
3. کاربر مقابل تایید می‌کند

### مرحله 2: ایجاد Room و ارسال لینک
1. Bot با FastAPI ارتباط برقرار می‌کند
2. Room ID منحصر به فرد ایجاد می‌شود
3. اطلاعات در Redis ذخیره می‌شود:
   ```json
   {
     "room_id": "uuid",
     "user1_id": 123,
     "user2_id": 456,
     "chat_room_id": 789,
     "call_type": "video" | "voice",
     "created_at": "timestamp",
     "status": "pending" | "active" | "ended"
   }
   ```
4. لینک به هر دو کاربر ارسال می‌شود:
   ```
   https://your-domain.com/video-call/{room_id}?token={auth_token}
   ```

### مرحله 3: دسترسی به وب اپ
1. کاربر روی لینک کلیک می‌کند
2. صفحه وب اپ باز می‌شود
3. احراز هویت:
   - بررسی token از query parameter
   - بررسی room_id در Redis
   - بررسی اینکه کاربر مجاز به دسترسی به این room است

### مرحله 4: اتصال به تماس
1. **Get User Media**:
   - برای تماس تصویری: `getUserMedia({ video: true, audio: true })`
   - برای تماس صوتی: `getUserMedia({ video: false, audio: true })`
2. **WebSocket Connection**:
   - اتصال به signaling server
   - ارسال room_id و user_id
3. **WebRTC Setup**:
   - ایجاد peer connection
   - Exchange SDP offers/answers via WebSocket
   - Exchange ICE candidates
4. **Media Stream**:
   - نمایش local stream (خود کاربر)
   - نمایش remote stream (کاربر مقابل)

---

## 🔐 احراز هویت و امنیت

### روش پیشنهادی:

#### 1. **Token-Based Authentication**
```python
# در Bot هنگام تایید تماس
import jwt
import secrets

def generate_call_token(user_id: int, room_id: str, expires_in: int = 3600):
    """Generate JWT token for call access."""
    payload = {
        "user_id": user_id,
        "room_id": room_id,
        "exp": datetime.utcnow() + timedelta(seconds=expires_in)
    }
    token = jwt.encode(payload, settings.API_SECRET_KEY, algorithm="HS256")
    return token
```

#### 2. **Token در Query Parameter**
- لینک: `https://your-domain.com/video-call/{room_id}?token={jwt_token}`
- Frontend token را ذخیره می‌کند
- در هر request به backend، token ارسال می‌شود

#### 3. **Backend Verification**
```python
@app.get("/api/video-call/{room_id}/verify")
async def verify_call_access(room_id: str, token: str):
    """Verify user has access to this call room."""
    try:
        payload = jwt.decode(token, settings.API_SECRET_KEY, algorithms=["HS256"])
        if payload["room_id"] != room_id:
            raise HTTPException(403, "Invalid token")
        
        # Check room exists and user is authorized
        room_data = await redis_client.get(f"video_call:room:{room_id}")
        if not room_data:
            raise HTTPException(404, "Room not found")
        
        return {"authorized": True, "user_id": payload["user_id"]}
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except:
        raise HTTPException(403, "Invalid token")
```

---

## 🎨 ساختار Frontend

```
webapp/
├── public/
│   └── index.html
├── src/
│   ├── components/
│   │   ├── VideoCall/
│   │   │   ├── VideoCallRoom.tsx
│   │   │   ├── LocalVideo.tsx
│   │   │   ├── RemoteVideo.tsx
│   │   │   ├── CallControls.tsx
│   │   │   └── CallSettings.tsx
│   │   ├── VoiceCall/
│   │   │   ├── VoiceCallRoom.tsx
│   │   │   └── VoiceControls.tsx
│   │   └── Common/
│   │       ├── Loading.tsx
│   │       └── Error.tsx
│   ├── services/
│   │   ├── api.ts          # FastAPI calls
│   │   ├── websocket.ts    # WebSocket signaling
│   │   └── webrtc.ts       # WebRTC peer connection
│   ├── hooks/
│   │   ├── useWebRTC.ts
│   │   ├── useWebSocket.ts
│   │   └── useMediaStream.ts
│   ├── stores/
│   │   └── callStore.ts    # State management
│   ├── utils/
│   │   ├── auth.ts
│   │   └── constants.ts
│   ├── App.tsx
│   └── main.tsx
├── package.json
└── vite.config.ts (یا webpack.config.js)
```

---

## 📡 API Endpoints پیشنهادی

### 1. **احراز هویت**
```
GET /api/video-call/{room_id}/verify?token={token}
POST /api/video-call/{room_id}/join
```

### 2. **WebSocket Signaling**
```
WS /ws/video-call/{room_id}?token={token}
Messages:
  - "offer": { type: "offer", sdp: "...", from: user_id }
  - "answer": { type: "answer", sdp: "...", from: user_id }
  - "ice-candidate": { candidate: "...", from: user_id }
  - "user-joined": { user_id: ... }
  - "user-left": { user_id: ... }
```

### 3. **Room Management**
```
GET /api/video-call/{room_id}/status
POST /api/video-call/{room_id}/end
```

---

## 🔧 تکنولوژی‌های پیشنهادی

### Frontend Stack:
- **Framework**: React 18 + TypeScript
- **Build Tool**: Vite (سریع و سبک)
- **Styling**: Tailwind CSS
- **WebRTC**: 
  - `simple-peer` (ساده و سبک) یا
  - `mediasoup-client` (برای scalability)
- **WebSocket**: `socket.io-client` یا native WebSocket
- **State**: Zustand (سبک و سریع)

### Backend (قبلاً وجود دارد):
- **Framework**: FastAPI ✅
- **WebSocket**: FastAPI WebSocket یا Socket.io
- **Database**: MySQL (برای user data) ✅
- **Cache**: Redis (برای room data) ✅

---

## 🔄 جریان کار کامل

### 1. **در Bot:**
```
کاربر A (پریمیوم) → درخواست تماس → کاربر B
کاربر B → تایید → Bot
Bot → ایجاد room → ارسال لینک به A و B
```

### 2. **در Web App:**
```
کاربر A → کلیک روی لینک → صفحه وب اپ
→ احراز هویت → دریافت media → اتصال WebSocket
→ ایجاد peer connection → exchange SDP
→ شروع تماس

کاربر B → همان روند
```

### 3. **در طول تماس:**
```
- نمایش local video/audio
- نمایش remote video/audio
- کنترل‌های تماس (mute, video on/off, hang up)
- ارسال events به Bot (تماس تمام شد، زمان تماس)
```

### 4. **پایان تماس:**
```
- Hang up → cleanup WebRTC
- اطلاع به Bot → به‌روزرسانی status در Redis
- بازگشت به Bot chat
```

---

## 🛠️ مراحل پیاده‌سازی

### Phase 1: Backend API Extensions
1. ✅ اضافه کردن endpoint برای احراز هویت
2. ✅ اضافه کردن WebSocket endpoint برای signaling
3. ✅ به‌روزرسانی endpoint ایجاد room برای شامل کردن call_type
4. ✅ ذخیره token در Redis با room data

### Phase 2: Frontend Setup
1. ✅ ایجاد React project با Vite
2. ✅ Setup routing (React Router)
3. ✅ Setup state management
4. ✅ ایجاد صفحه اصلی Call Room

### Phase 3: WebRTC Integration
1. ✅ پیاده‌سازی getUserMedia
2. ✅ پیاده‌سازی peer connection
3. ✅ پیاده‌سازی WebSocket signaling
4. ✅ پیاده‌سازی SDP exchange
5. ✅ پیاده‌سازی ICE candidate exchange

### Phase 4: UI/UX
1. ✅ طراحی رابط کاربری
2. ✅ اضافه کردن کنترل‌های تماس
3. ✅ اضافه کردن loading states
4. ✅ اضافه کردن error handling

### Phase 5: Bot Integration
1. ✅ به‌روزرسانی handler تایید تماس
2. ✅ ایجاد room در FastAPI
3. ✅ ارسال لینک به کاربران
4. ✅ دریافت callback از web app (پایان تماس)

---

## 🔒 امنیت

### 1. **Token Security**
- JWT با expiration time
- Validation در هر request
- یکبار مصرف بودن (اگر نیاز باشد)

### 2. **Room Access Control**
- بررسی اینکه کاربر در room مجاز است
- بررسی status room (فعال/بسته)
- Timeout خودکار برای room ها

### 3. **WebRTC Security**
- استفاده از secure RTCPeerConnection
- STUN/TURN servers با authentication
- Encryption در transit

---

## 📊 State Management در Frontend

```typescript
interface CallState {
  roomId: string | null;
  token: string | null;
  userInfo: {
    id: number;
    telegramId: number;
    username: string;
  } | null;
  callType: "video" | "voice" | null;
  status: "connecting" | "connected" | "ended" | "error";
  localStream: MediaStream | null;
  remoteStream: MediaStream | null;
  peerConnection: RTCPeerConnection | null;
  isMuted: boolean;
  isVideoEnabled: boolean;
}
```

---

## 🌐 Deployment

### Option 1: **Static Hosting** (Frontend)
- **Netlify** یا
- **Vercel** یا
- **Cloudflare Pages**

### Option 2: **Docker Container**
- اضافه کردن frontend به docker-compose
- Nginx برای serve کردن static files
- Integration با FastAPI

---

## 📝 Next Steps

1. **تصمیم‌گیری در مورد تکنولوژی‌ها**
   - React vs Vue?
   - simple-peer vs mediasoup?
   - Tailwind vs Material-UI?

2. **Setup Project Structure**
   - ایجاد frontend directory
   - Setup build tools
   - Setup development environment

3. **پیاده‌سازی Backend Extensions**
   - WebSocket endpoints
   - Token generation
   - Room management improvements

4. **پیاده‌سازی Frontend**
   - Basic routing
   - WebRTC integration
   - UI components

5. **Testing**
   - Local testing
   - Integration testing
   - Production deployment

---

## 🎯 پیشنهادات اولیه

### برای شروع سریع:
1. **React + Vite + TypeScript** (محبوب و مستندات زیاد)
2. **simple-peer** (ساده‌ترین راه برای WebRTC)
3. **Tailwind CSS** (سریع برای styling)
4. **FastAPI WebSocket** (هماهنگی با backend موجود)

### برای scalability بیشتر:
1. **mediasoup** (برای چند کاربر و advanced features)
2. **Socket.io** (برای better WebSocket management)
3. **Redis Pub/Sub** (برای signaling بهتر)

---

این پلان را می‌توان بر اساس نیازهای خاص پروژه و منابع در دسترس تطبیق داد.

