# Anonymous Chat Telegram Bot

A scalable anonymous chat Telegram bot built with Python, aiogram, Redis, MySQL, and FastAPI.

## 🏗️ Architecture Overview

The bot follows a modular architecture with clear separation of concerns:

```
telecaht/
├── bot/              # Telegram bot handlers and logic
│   ├── handlers/     # Command and message handlers
│   ├── keyboards/    # Inline keyboard definitions
│   └── middlewares/  # Middleware for rate limiting and channel checks
├── core/             # Core business logic
│   ├── matchmaking.py    # Redis-based matchmaking system
│   ├── chat_manager.py   # Chat room management
│   └── premium.py        # Premium feature logic
├── db/               # Database models and operations
│   ├── models.py     # SQLAlchemy models
│   ├── database.py   # Database connection and session management
│   └── crud.py       # CRUD operations
├── api/              # FastAPI endpoints
│   └── video_call.py # Video call link generation
├── utils/            # Utility functions
│   ├── rate_limiter.py   # Rate limiting utilities
│   └── validators.py      # Input validation
└── config/           # Configuration management
    └── settings.py   # Settings from environment variables
```

## 🚀 Features

### Core Features

1. **User Registration**
   - Multi-step profile creation (gender, age, city, photo)
   - Profile validation and storage
   - Channel membership requirement

2. **Anonymous Chat**
   - Redis-based matchmaking system
   - Queue management with filter support
   - Real-time message forwarding (text, voice, image, video)
   - Uses Telegram file_id for media (no file storage)

3. **Premium Mode**
   - Premium subscription tracking
   - Video call access (at least one user must be premium)
   - Longer chat duration for premium users
   - Advanced filters (age range, city, gender)

4. **Video Call Links**
   - FastAPI endpoint for generating video call rooms
   - Unique room IDs stored in Redis
   - Integration with mini-app domain

5. **Admin Panel**
   - User statistics and management
   - Broadcast messages to all users
   - Ban/unban users
   - View and resolve reports

## 📋 Prerequisites

- Python 3.10+
- Docker and Docker Compose
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- MySQL 8.0+
- Redis 7+
- MinIO (optional, for profile image storage)

## 🔧 Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd telecaht
```

### 2. Set up environment variables

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
BOT_TOKEN=your_bot_token_here
MANDATORY_CHANNEL_ID=@your_channel_username
ADMIN_IDS=123456789,987654321
VIDEO_CALL_DOMAIN=https://your-domain.com
API_SECRET_KEY=your-secret-key-change-this
```

### 3. Start all services with Docker Compose (Recommended)

```bash
docker-compose up -d
```

This will start:
- Redis on port 6379
- MySQL on port 3306
- MinIO on ports 9000 (API) and 9001 (Console)
- **Bot container** (includes FastAPI on port 8000)

The bot will automatically:
- Connect to Redis and MySQL
- Initialize database tables
- Start the Telegram bot polling
- Start the FastAPI server on port 8000

**Alternative: Run bot locally (without Docker)**

If you prefer to run the bot locally without Docker:

```bash
# 3a. Start only infrastructure services
docker-compose up -d redis mysql minio

# 4. Install Python dependencies
pip install -r requirements.txt

# 5. Run the bot
python main.py
```

### View logs

```bash
# View all logs
docker-compose logs -f

# View bot logs only
docker-compose logs -f bot

# View specific service
docker-compose logs -f redis mysql

## 📊 Database Schema

### Users Table
- `id`: Primary key
- `telegram_id`: Unique Telegram user ID
- `username`: Telegram username
- `gender`: User gender (male/female/other)
- `age`: User age
- `city`: User city
- `profile_image_url`: Profile image URL or file_id
- `is_premium`: Premium status
- `premium_expires_at`: Premium expiration date
- `is_banned`: Ban status

### Chat Rooms Table
- `id`: Primary key
- `user1_id`: First user ID (foreign key)
- `user2_id`: Second user ID (foreign key)
- `is_active`: Active status
- `created_at`: Creation timestamp
- `ended_at`: End timestamp
- `video_call_room_id`: Video call room ID
- `video_call_link`: Video call link

### Premium Subscriptions Table
- `id`: Primary key
- `user_id`: User ID (foreign key)
- `provider`: Payment provider (myket, local, etc.)
- `transaction_id`: Unique transaction ID
- `amount`: Payment amount
- `start_date`: Subscription start date
- `end_date`: Subscription end date

### Reports Table
- `id`: Primary key
- `reporter_id`: Reporter user ID (foreign key)
- `reported_id`: Reported user ID (foreign key)
- `reason`: Report reason
- `report_type`: Report type (spam, harassment, etc.)
- `is_resolved`: Resolution status

## 🔄 Matchmaking System

The matchmaking system uses Redis for fast queue management:

1. **Queue Structure**: Users are added to queues based on their preferences and filters
2. **Matching Algorithm**: Matches users based on gender preferences, age range, and city
3. **Queue Tracking**: Shows queue count to users while searching
4. **Timeout Handling**: Removes users from queue after timeout

## 💬 Message Flow

1. User sends a message to the bot
2. Bot checks if user has an active chat
3. Bot forwards message to chat partner using file_id
4. Supports text, voice, photo, and video messages
5. Rate limiting applied to prevent abuse

## 🎯 API Endpoints

### Video Call API (FastAPI)

- `POST /api/video-call/create`: Create a new video call room
- `GET /api/video-call/{room_id}`: Get video call room information
- `DELETE /api/video-call/{room_id}`: Delete a video call room
- `GET /health`: Health check endpoint

### Authentication

API endpoints require an `X-API-Key` header with the value from `API_SECRET_KEY` in your `.env` file.

## 🤖 Bot Commands

### User Commands
- `/start`: Start the bot or return to main menu

### Admin Commands
- `/admin_stats`: View bot statistics
- `/admin_broadcast`: Broadcast message to all users
- `/admin_ban <user_id>`: Ban a user
- `/admin_unban <user_id>`: Unban a user
- `/admin_users`: List users (with pagination)
- `/admin_reports`: View unresolved reports

## 🔒 Security Features

- Rate limiting on messages
- Channel membership requirement
- Admin-only commands
- Input validation
- SQL injection protection (SQLAlchemy ORM)
- Redis-based session management

## 📈 Scalability

The bot is designed to handle 100k+ users:

- **Async Architecture**: All I/O operations are async
- **Redis Caching**: Fast lookups for active chats and queues
- **Connection Pooling**: Database connection pooling
- **Message Queue**: Redis-based message routing
- **Stateless Design**: Easy horizontal scaling

## 🛠️ Development

### Project Structure

- **bot/**: Telegram bot logic (aiogram handlers)
- **core/**: Business logic (matchmaking, chat management)
- **db/**: Database models and operations (SQLAlchemy)
- **api/**: FastAPI endpoints (video call API)
- **utils/**: Utility functions (validation, rate limiting)
- **config/**: Configuration management

### Adding New Features

1. Add handlers in `bot/handlers/`
2. Add database models in `db/models.py`
3. Add CRUD operations in `db/crud.py`
4. Register handlers in `main.py`

## 🐛 Troubleshooting

### Bot not responding
- Check if `BOT_TOKEN` is correct
- Verify bot is running and not stopped
- Check logs for errors

### Database connection errors
- Ensure MySQL is running: `docker-compose ps`
- Check database credentials in `.env`
- Verify MySQL container logs

### Redis connection errors
- Ensure Redis is running: `docker-compose ps`
- Check Redis connection settings in `.env`
- Verify Redis container logs

## 📝 Notes

- Profile images can use Telegram file_id (recommended) or MinIO storage
- Video call integration requires a mini-app domain
- Premium purchase integration needs to be implemented with your payment gateway
- Channel membership check requires bot to be admin in the channel

## 📄 License

[Add your license here]

## 🤝 Contributing

[Add contribution guidelines here]

## 📧 Contact

[Add contact information here]
