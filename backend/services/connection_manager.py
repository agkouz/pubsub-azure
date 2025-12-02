# backend/services/connection_manager.py

from __future__ import annotations

from typing import Dict, Set
from fastapi import WebSocket
import logging

from services.room_manager import RoomManager

logger = logging.getLogger(__name__)

# ============================================================================
# WEBSOCKET CONNECTION MANAGER
# ============================================================================

class ConnectionManager:
    """
    Manages WebSocket connections and room memberships.
    
    This is the core of the cost-optimal architecture. Instead of using
    Service Bus subscriptions to filter messages, this class maintains
    in-memory mappings of which WebSockets are subscribed to which rooms,
    and broadcasts messages only to the appropriate connections.
    
    Data Structures:
        rooms: Maps room_id -> Set of WebSocket connections in that room
               Example: {"uuid-123": {websocket1, websocket2}}
        
        connection_rooms: Maps WebSocket -> Set of room_ids it's subscribed to
                         Example: {websocket1: {"uuid-123", "uuid-456"}}
        
        connection_users: Maps WebSocket -> user_id (for logging/debugging)
    
    Scaling:
        - Single instance: Works perfectly, all in-memory
        - Multi-instance: Need shared state (Redis) for rooms mapping
    
    Cost Impact:
        - This approach costs 2 operations per message (publish + delivery)
        - Alternative (per-room subscriptions) would cost (1 + N) operations
          where N is the number of rooms, which scales terribly!
    """
    
    def __init__(self, room_manager: RoomManager) -> None:
        """Initialize connection manager with empty data structures."""
        # Map: room_id -> Set[WebSocket connections]
        self.rooms: Dict[str, Set[WebSocket]] = {}
        
        # Map: WebSocket -> Set[room_ids it's subscribed to]
        self.connection_rooms: Dict[WebSocket, Set[str]] = {}
        
        # Map: WebSocket -> user_id (for logging)
        self.connection_users: Dict[WebSocket, str] = {}
        self.room_manager = room_manager

    async def connect(self, websocket: WebSocket, user_id: str = "anonymous") -> None:
        """
        Accept a new WebSocket connection.
        
        Args:
            websocket: The WebSocket connection object
            user_id: Username for this connection (optional)
            
        Note:
            User is not automatically joined to any rooms. They must
            explicitly send "join" actions for each room.
        """
        await websocket.accept()
        
        # Initialize empty room set for this connection
        self.connection_rooms[websocket] = set()
        self.connection_users[websocket] = user_id
        
        logger.info("✓ User %s connected. Total: %d", user_id, len(self.connection_rooms))
    
    def disconnect(self, websocket: WebSocket) -> None:
        """
        Handle WebSocket disconnection and cleanup.
        
        Args:
            websocket: The disconnecting WebSocket
            
        Cleanup:
            1. Remove from all rooms they were in
            2. Update room member counts
            3. Delete empty rooms from memory
            4. Remove from tracking dictionaries
        """
        if websocket in self.connection_rooms:
            user_id = self.connection_users.get(websocket, "unknown")
            
            # Remove from all rooms
            for room_id in self.connection_rooms[websocket]:
                if room_id in self.rooms:
                    self.rooms[room_id].discard(websocket)
                    # Update member count in room metadata
                    self.room_manager.update_member_count(room_id, len(self.rooms[room_id]))
                    # Clean up empty rooms from memory
                    if not self.rooms[room_id]:
                        del self.rooms[room_id]
            
            # Remove from tracking dicts
            del self.connection_rooms[websocket]
            del self.connection_users[websocket]
            
            logger.info("✗ User %s disconnected. Total: %d", user_id, len(self.connection_rooms))
    
    async def join_room(self, websocket: WebSocket, room_id: str) -> None:
        """
        Subscribe a WebSocket connection to a room.
        
        Args:
            websocket: The WebSocket connection
            room_id: UUID of room to join
            
        Process:
            1. Verify room exists in room_manager
            2. Add websocket to room's connection set
            3. Add room to websocket's subscribed rooms
            4. Update member count
            5. Send confirmation to client
            
        After joining, the connection will receive all messages published
        to this room via Service Bus.
        """
        # Verify room exists
        room = self.room_manager.get_room(room_id)
        if not room:
            await websocket.send_json({"type": "error", "message": "Room not found"})
            return
        
        if websocket not in self.connection_rooms:
            return  # Connection already closed
        
        # Add to room's connection set
        if room_id not in self.rooms:
            self.rooms[room_id] = set()
        self.rooms[room_id].add(websocket)
        
        # Add to connection's subscribed rooms
        self.connection_rooms[websocket].add(room_id)
        
        # Update member count
        member_count = len(self.rooms[room_id])
        self.room_manager.update_member_count(room_id, member_count)
        
        user_id = self.connection_users.get(websocket, "anonymous")
        logger.info("→ %s joined '%s' (%s members)", user_id, room.name, member_count)
        
        # Send confirmation to client
        await websocket.send_json(
            {
                "type": "room_joined",
                "room": room.model_dump(),
                "member_count": member_count,
            }
        )

    async def leave_room(self, websocket: WebSocket, room_id: str) -> None:
        """
        Unsubscribe a WebSocket connection from a room.
        
        Args:
            websocket: The WebSocket connection
            room_id: UUID of room to leave
            
        After leaving, the connection will no longer receive messages
        published to this room.
        """
        if websocket not in self.connection_rooms:
            return  # Connection already closed
        
        if room_id in self.connection_rooms[websocket]:
            # Remove from connection's subscribed rooms
            self.connection_rooms[websocket].discard(room_id)
            
            if room_id in self.rooms:
                # Remove from room's connection set
                self.rooms[room_id].discard(websocket)
                member_count = len(self.rooms[room_id])
                self.room_manager.update_member_count(room_id, member_count)
                
                # Clean up empty room
                if not self.rooms[room_id]:
                    del self.rooms[room_id]
                
                # Send confirmation to client
                await websocket.send_json(
                    {
                        "type": "room_left",
                        "room_id": room_id,
                        "member_count": member_count,
                    }
                )
    
    async def broadcast_to_room(self, room_id: str, message: dict) -> None:
        """
        Broadcast a message to all WebSockets subscribed to a room.
        
        This is the KEY COST OPTIMIZATION: Instead of Service Bus delivering
        to N subscriptions (N operations), we deliver once to our single
        subscription and then broadcast in memory to the appropriate
        WebSocket connections.
        
        Args:
            room_id: UUID of target room
            message: Message dict to send (will be JSON serialized)
            
        Cost Impact:
            - Service Bus: 1 delivery operation (to our single subscription)
            - Backend: 0 operations (in-memory broadcast)
            - Total: 1 operation (vs N operations for per-room subscriptions)
        
        Error Handling:
            If a send fails, the connection is marked as disconnected
            and cleaned up.
        """
        if room_id not in self.rooms:
            # No one subscribed to this room currently
            logger.info("[routing] Skipped broadcast: room=%s has 0 subscribers", room_id)
            return
        
        disconnected = set()
        connections = self.rooms[room_id].copy()  # Copy to avoid modification during iteration
        
        logger.info("📨 Broadcasting to room %s: %d clients", room_id, len(connections))
        
        # Send to each connection in the room
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Send error: {e}")
                # Mark for cleanup
                disconnected.add(connection)
        
        # Clean up failed connections
        for conn in disconnected:
            self.disconnect(conn)
    
    def get_rooms_info(self) -> Dict[str, dict]:
        """
        Get information about all active rooms with members.
        
        Returns:
            Dict mapping room_id to room info (name, member_count)
            
        Used by the /metrics endpoint and for debugging.
        """
        result: Dict[str, dict] = {}
        for room_id, connections in self.rooms.items():
            room = self.room_manager.get_room(room_id)
            if room:
                result[room_id] = {
                    "name": room.name,
                    "member_count": len(connections),
                }
        return result