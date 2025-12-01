# app/api/routes/rooms.py

from typing import List

from fastapi import APIRouter, HTTPException
import asyncio

from app.models.room import Room, CreateRoomRequest
from app.core import state
from app.api.utils import broadcast_room_list_update

router = APIRouter()

# ============================================================================
# ROOM CRUD ENDPOINTS
# ============================================================================

@app.get("/rooms", response_model=List[Room])
async def list_rooms():
    """
    List all available rooms.
    
    Returns room metadata with current member counts updated from
    active WebSocket connections.
    
    Returns:
        List[Room]: All rooms with updated member counts
    """
    rooms = state.room_manager.list_rooms()

    for room in rooms:
        if room.id in state.connection_manager.rooms:
            room.member_count = len(state.connection_manager.rooms[room.id])

    return rooms

@app.post("/rooms", response_model=Room)
async def create_room(request: CreateRoomRequest):
    """
    Create a new chatroom.
    
    Users can create unlimited rooms. Room is persisted to disk and
    broadcasts to all connected clients.
    
    Args:
        request: CreateRoomRequest with name, description, created_by
    
    Returns:
        Room: The newly created room
    
    Raises:
        HTTPException: 400 if name is empty or already exists
    
    Side Effects:
        - Room saved to rooms.json
        - "rooms_updated" message broadcast to all WebSocket clients
    """
    if not request.name.strip():
        raise HTTPException(status_code=400, detail="Room name required")

    existing = state.room_manager.list_rooms()
    if any(r.name.lower() == request.name.lower() for r in existing):
        raise HTTPException(status_code=400, detail="Room name exists")

    room = state.room_manager.create_room(
        name=request.name,
        description=request.description,
        created_by=request.created_by,
    )

    asyncio.create_task(broadcast_room_list_update())
    return room

@app.delete("/rooms/{room_id}")
async def delete_room(room_id: str):
    """
    Delete a room.
    
    Kicks all users from the room, deletes from persistence, and
    notifies all clients.
    
    Args:
        room_id: UUID of room to delete
    
    Returns:
        dict: Status message with room_id
    
    Raises:
        HTTPException: 404 if room not found
    
    Side Effects:
        - All users in room are sent "room_left" messages
        - Room removed from rooms.json
        - "rooms_updated" broadcast to all clients
    
    TODO: Add authorization check (only creator should be able to delete)
    """
    room = state.room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Kick all users from room
    if room_id in state.connection_manager.rooms:
        connections = state.connection_manager.rooms[room_id].copy()
        for conn in connections:
            await state.connection_manager.leave_room(conn, room_id)

    deleted = state.room_manager.delete_room(room_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Room not found")

    asyncio.create_task(broadcast_room_list_update())
    return {"status": "deleted", "room_id": room_id}


@app.get("/rooms/{room_id}", response_model=Room)
async def get_room(room_id: str):
    """
    Get details of a specific room.
    
    Args:
        room_id: UUID of room
    
    Returns:
        Room: Room object with current member count
    
    Raises:
        HTTPException: 404 if room not found
    """
    room = state.room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if room_id in state.connection_manager.rooms:
        room.member_count = len(state.connection_manager.rooms[room_id])

    return room

