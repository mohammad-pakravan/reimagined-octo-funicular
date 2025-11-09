# Video Call Web App

وب اپلیکیشن تماس صوتی و تصویری برای Telegram Bot

## ویژگی‌ها

- ✅ تماس تصویری و صوتی 1-to-1
- ✅ WebRTC Peer-to-Peer
- ✅ کنترل‌های Mute/Unmute و Video on/off
- ✅ UI با Tailwind CSS
- ✅ Responsive design

## نصب و راه‌اندازی

```bash
npm install
npm run dev
```

## Build برای Production

```bash
npm run build
```

## Environment Variables

ایجاد فایل `.env.local`:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_API_WS_URL=ws://localhost:8000
```

## استفاده

کاربران از طریق لینک دریافتی از Telegram Bot وارد می‌شوند:
```
https://your-domain.com/call/{room_id}?token={jwt_token}
```

## تکنولوژی‌ها

- React + TypeScript
- Vite
- simple-peer (WebRTC)
- Tailwind CSS
- React Router

