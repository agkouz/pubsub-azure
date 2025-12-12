# backend/api/websocket.py

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.gcloud_pub_sub import publish_event
from core import state
from core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================================
# WEBSOCKET ENDPOINT
# ============================================================================

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, user_id: str = "anonymous"):
    """
    WebSocket endpoint for real-time bidirectional communication.
    
    Protocol:
    =========
    
    Client -> Server Actions:
    -------------------------
    Join Room:
        {"action": "join", "room_id": "uuid-123"}
        Response: {"type": "room_joined", "room": {...}, "member_count": 5}
    
    Leave Room:
        {"action": "leave", "room_id": "uuid-123"}
        Response: {"type": "room_left", "room_id": "uuid-123", "member_count": 4}
    
    List Rooms:
        {"action": "list_rooms"}
        Response: {"type": "rooms_list", "rooms": [...]}
    
    Get Room Info:
        {"action": "get_rooms_info"}
        Response: {"type": "rooms_info", "rooms": {"uuid-123": {"name": "...", "member_count": 5}}}

    Publish Message:
        {
            "action": "message_publish", 
            "data": {
                "room_id": "<room_id>", 
                "content": "<content>", 
                "sender": "<username>"
            }
        }
        Response: {"type": "message_published", "message_content"}

    Server -> Client Messages:
    -------------------------
    Regular Message:
        {"room_id": "uuid-123", "content": "Hello!", "sender": "alice", "timestamp": "..."}
    
    Room List Updated:
        {"type": "rooms_updated", "rooms": [...]}
    
    Error:
        {"type": "error", "message": "..."}
    
    Lifecycle:
    ==========
    1. Client connects with user_id parameter
    2. Connection accepted, user_id tracked
    3. Client sends "join" actions for desired rooms
    4. Client receives messages from subscribed rooms only
    5. On disconnect, automatically removed from all rooms
    
    Args:
        websocket: WebSocket connection object
        user_id: Query parameter for username (defaults to "anonymous")
    
    Error Handling:
        - Invalid JSON: Sends error message
        - Unknown actions: Sends error message
        - Connection errors: Cleanup and log
    """
    await state.connection_manager.connect(websocket, user_id)

    try:
        while True:
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                action = message.get("action")
                logger.info(f"Websocket input: Action: {action}, Message: {message}")

                if action == "join":
                    room_id = message.get("room_id")
                    if room_id:
                        await state.connection_manager.join_room(websocket, room_id)

                elif action == "leave":
                    room_id = message.get("room_id")
                    if room_id:
                        await state.connection_manager.leave_room(websocket, room_id)

                elif action == "list_rooms":
                    rooms_data = [
                        r.model_dump() for r in state.room_manager.list_rooms()
                    ]
                    await websocket.send_json(
                        {"type": "rooms_list", "rooms": rooms_data}
                    )

                elif action == "get_rooms_info":
                    info = {
                        rid: {
                            "name": state.room_manager.get_room(rid).name
                            if state.room_manager.get_room(rid)
                            else "Unknown",
                            "member_count": len(conns),
                        }
                        for rid, conns in state.connection_manager.rooms.items()
                    }
                    await websocket.send_json(
                        {
                            "type": "rooms_info",
                            "rooms": info,
                        }
                    )

                elif action == "message_publish":
                    if settings.PUB_SUB_SERVICE == "redis":
                        data = message.get('data')
                        room = state.room_manager.get_room(data['room_id'])
                        
                        if not room:
                            await websocket.send_json({"type": "error", "message": "Room not found"})
                            return
                        
                        message_data = {
                            "room_id": room.id,
                            "content": data['content'],
                            "sender": data['sender'],
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                        
                        # Publish to Redis
                        await state.redis_service.broadcast_to_room(room.id, message_data)
                        state.message_counter += 1
                        await websocket.send_json({"type": "message_publish", "status": "success"})
                    elif settings.PUB_SUB_SERVICE == "google_pub_sub":
                        data = message.get('data')
                        room = state.room_manager.get_room(data['room_id'])
                        
                        if not room:
                            await websocket.send_json({"type": "message_publish", "error": "Room not found"})
                        
                        message_data = {
                            "room_id":  room.id,
                            "room_name": room.name,
                            "content": data['content'],
                            "sender": data['sender'],
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    
                        try:
                            publish_event(message_data)
                            state.message_counter += 1
                            await websocket.send_json({"type": "message_publish", "status": "success"})
                        except Exception as e:
                            await websocket.send_json({"type": "message_publish", "error": f"Internal Error: {str(e)}"})

                else:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": f"Unknown action: {action}",
                        }
                    )

            except json.JSONDecodeError:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Invalid JSON",
                    }
                )

    except WebSocketDisconnect:
        state.connection_manager.disconnect(websocket)
    except Exception as e:
        logger.error("WebSocket error: %s", e)
        state.connection_manager.disconnect(websocket)
