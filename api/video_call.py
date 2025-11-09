"""
FastAPI endpoints for video call link generation.
Generates unique video call room IDs and links.
"""
import secrets
import uuid
import json
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Header, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict
import redis.asyncio as redis
import jwt

from config.settings import settings

app = FastAPI(title="Video Call API", version="1.0.0")

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # در production باید محدود کنید
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Redis client
redis_client = None

# WebSocket connections storage
active_connections: Dict[str, Dict[int, WebSocket]] = {}


class VideoCallRequest(BaseModel):
    """Request model for creating video call."""
    user1_id: int
    user2_id: int
    chat_room_id: int
    call_type: str = "video"  # "video" or "voice"


class VideoCallResponse(BaseModel):
    """Response model for video call creation."""
    room_id: str
    link: str
    expires_at: Optional[str] = None


class CallTokenResponse(BaseModel):
    """Response model for call token generation."""
    token: str
    room_id: str
    link: str


class VerifyTokenResponse(BaseModel):
    """Response model for token verification."""
    authorized: bool
    user_id: int
    room_id: str
    call_type: str
    chat_room_id: int


def set_redis_client(client: redis.Redis):
    """Set Redis client instance."""
    global redis_client
    redis_client = client


def verify_api_key_sync(x_api_key: str) -> bool:
    """Verify API key for authentication."""
    return x_api_key == settings.API_SECRET_KEY


def generate_call_token(user_id: int, room_id: str, chat_room_id: int, call_type: str) -> str:
    """Generate JWT token for call access."""
    payload = {
        "user_id": user_id,
        "room_id": room_id,
        "chat_room_id": chat_room_id,
        "call_type": call_type,
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(payload, settings.API_SECRET_KEY, algorithm="HS256")


def verify_call_token(token: str) -> dict:
    """Verify and decode call token."""
    try:
        payload = jwt.decode(token, settings.API_SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=403, detail="Invalid token")


@app.post("/api/video-call/create", response_model=VideoCallResponse)
async def create_video_call(
    request: VideoCallRequest,
    x_api_key: str = Header(...)
):
    """
    Create a new video call room.
    
    Args:
        request: Video call request with user IDs and chat room ID
        x_api_key: API key for authentication
        
    Returns:
        Video call response with room ID and link
    """
    # Verify API key
    if not verify_api_key_sync(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Generate unique room ID
    room_id = str(uuid.uuid4())
    
    # Store room information in Redis (expires in 1 hour)
    if redis_client:
        room_key = f"video_call:room:{room_id}"
        room_data = {
            "user1_id": request.user1_id,
            "user2_id": request.user2_id,
            "chat_room_id": request.chat_room_id,
            "call_type": request.call_type,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
        }
        await redis_client.setex(room_key, 3600, json.dumps(room_data))
    
    # Generate video call link
    video_call_link = f"{settings.VIDEO_CALL_DOMAIN}/call/{room_id}"
    
    return VideoCallResponse(
        room_id=room_id,
        link=video_call_link,
        expires_at=None
    )


@app.post("/api/video-call/{room_id}/tokens", response_model=Dict[str, str])
async def generate_call_tokens(
    room_id: str,
    x_api_key: str = Header(...)
):
    """
    Generate tokens for both users in a call room.
    
    Args:
        room_id: Room ID
        x_api_key: API key for authentication
        
    Returns:
        Dictionary with tokens for both users
    """
    # Verify API key
    if not verify_api_key_sync(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis not available")
    
    # Get room data
    room_key = f"video_call:room:{room_id}"
    room_data_str = await redis_client.get(room_key)
    if not room_data_str:
        raise HTTPException(status_code=404, detail="Room not found")
    
    room_data = json.loads(room_data_str)
    user1_id = room_data["user1_id"]
    user2_id = room_data["user2_id"]
    chat_room_id = room_data["chat_room_id"]
    call_type = room_data.get("call_type", "video")
    
    # Generate tokens
    token1 = generate_call_token(user1_id, room_id, chat_room_id, call_type)
    token2 = generate_call_token(user2_id, room_id, chat_room_id, call_type)
    
    # Update room status
    room_data["status"] = "active"
    await redis_client.setex(room_key, 3600, json.dumps(room_data))
    
    return {
        "user1_token": token1,
        "user2_token": token2,
        "room_id": room_id
    }


@app.get("/api/video-call/{room_id}/verify", response_model=VerifyTokenResponse)
async def verify_call_access(room_id: str, token: str):
    """
    Verify user has access to this call room.
    
    Args:
        room_id: Room ID
        token: JWT token
        
    Returns:
        Verification result with user info
    """
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis not available")
    
    # Verify token
    try:
        payload = verify_call_token(token)
    except HTTPException:
        raise
    
    # Check room_id matches
    if payload["room_id"] != room_id:
        raise HTTPException(status_code=403, detail="Invalid token for this room")
    
    # Get room data
    room_key = f"video_call:room:{room_id}"
    room_data_str = await redis_client.get(room_key)
    if not room_data_str:
        raise HTTPException(status_code=404, detail="Room not found")
    
    room_data = json.loads(room_data_str)
    user_id = payload["user_id"]
    
    # Check user is authorized
    if user_id not in [room_data["user1_id"], room_data["user2_id"]]:
        raise HTTPException(status_code=403, detail="User not authorized for this room")
    
    return VerifyTokenResponse(
        authorized=True,
        user_id=user_id,
        room_id=room_id,
        call_type=payload["call_type"],
        chat_room_id=payload["chat_room_id"]
    )


@app.get("/api/video-call/{room_id}")
async def get_video_call_info(room_id: str):
    """
    Get video call room information.
    
    Args:
        room_id: Video call room ID
        
    Returns:
        Room information
    """
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis not available")
    
    room_key = f"video_call:room:{room_id}"
    room_data_str = await redis_client.get(room_key)
    
    if not room_data_str:
        raise HTTPException(status_code=404, detail="Room not found")
    
    room_data = json.loads(room_data_str)
    return {"room_id": room_id, "data": room_data}


@app.delete("/api/video-call/{room_id}")
async def delete_video_call(room_id: str, x_api_key: str = Header(...)):
    """
    Delete a video call room.
    
    Args:
        room_id: Video call room ID
        x_api_key: API key for authentication
        
    Returns:
        Success message
    """
    # Verify API key
    if not verify_api_key_sync(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis not available")
    
    room_key = f"video_call:room:{room_id}"
    deleted = await redis_client.delete(room_key)
    
    if deleted:
        return {"message": "Room deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Room not found")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "video-call-api"}


async def broadcast_to_room(room_id: str, message: dict, exclude_user_id: Optional[int] = None):
    """Broadcast message to all users in a room except excluded user."""
    if room_id not in active_connections:
        return
    
    connections = active_connections[room_id]
    for user_id, websocket in connections.items():
        if user_id != exclude_user_id:
            try:
                await websocket.send_json(message)
            except:
                # Connection closed, remove it
                if room_id in active_connections:
                    active_connections[room_id].pop(user_id, None)


@app.websocket("/ws/video-call/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, token: str):
    """
    WebSocket endpoint for WebRTC signaling.
    
    Handles:
    - SDP offer/answer exchange
    - ICE candidate exchange
    - User joined/left events
    """
    await websocket.accept()
    
    # Verify token
    try:
        payload = verify_call_token(token)
    except HTTPException as e:
        await websocket.close(code=1008, reason=e.detail)
        return
    
    # Check room_id matches
    if payload["room_id"] != room_id:
        await websocket.close(code=1008, reason="Invalid token for this room")
        return
    
    # Check room exists
    if not redis_client:
        await websocket.close(code=1011, reason="Server error")
        return
    
    room_key = f"video_call:room:{room_id}"
    room_data_str = await redis_client.get(room_key)
    if not room_data_str:
        await websocket.close(code=1008, reason="Room not found")
        return
    
    user_id = payload["user_id"]
    
    # Store connection
    if room_id not in active_connections:
        active_connections[room_id] = {}
    active_connections[room_id][user_id] = websocket
    
    # Notify other user that this user joined
    await broadcast_to_room(room_id, {
        "type": "user-joined",
        "user_id": user_id
    }, exclude_user_id=user_id)
    
    try:
        while True:
            # Receive message
            message = await websocket.receive_json()
            message_type = message.get("type")
            
            # Forward signaling messages to other user
            if message_type in ["offer", "answer", "ice-candidate"]:
                await broadcast_to_room(room_id, message, exclude_user_id=user_id)
            elif message_type == "call-ended":
                # Notify other user
                await broadcast_to_room(room_id, message, exclude_user_id=user_id)
                # Update room status in Redis
                room_data = json.loads(room_data_str)
                room_data["status"] = "ended"
                room_data["ended_at"] = datetime.utcnow().isoformat()
                await redis_client.setex(room_key, 3600, json.dumps(room_data))
                break
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        # Handle errors
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"WebSocket error: {e}")
    finally:
        # Remove connection
        if room_id in active_connections:
            active_connections[room_id].pop(user_id, None)
        
        # Notify other user that this user left
        await broadcast_to_room(room_id, {
            "type": "user-left",
            "user_id": user_id
        }, exclude_user_id=user_id)

