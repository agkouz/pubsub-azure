from __future__ import annotations

from typing import Dict, Set
from fastapi import WebSocket
import logging

from app.services.room_manager import RoomManager

ROOMS_FILE = "rooms.json"  # File where room metadata is persisted

# ============================================================================
# ROOM PERSISTENCE MANAGER
# ============================================================================
class RoomManager:
    """
    Manages room metadata with file-based persistence.
    
    This class handles CRUD operations for rooms and persists them to a JSON file.
    Rooms survive backend restarts. For multi-instance deployments, migrate to
    Redis or Azure Cosmos DB.
    
    Attributes:
        rooms: Dictionary mapping room_id -> Room object
    
    Storage Format (rooms.json):
        {
            "uuid-123": {
                "id": "uuid-123",
                "name": "Product Team",
                "description": "Product discussions",
                "created_by": "alice",
                "created_at": "2025-11-30T20:00:00Z",
                "member_count": 0
            }
        }
    
    Usage:
        room_manager = RoomManager()
        room = room_manager.create_room("New Room", "Description", "alice")
        all_rooms = room_manager.list_rooms()
    """
    
    def __init__(self):
        """Initialize room manager and load existing rooms from file."""
        self.rooms: Dict[str, Room] = {}
        self.load_rooms()
    
    def load_rooms(self):
        """
        Load rooms from persistent storage (rooms.json).
        
        If file doesn't exist or fails to load, creates default rooms.
        This runs on application startup.
        """
        try:
            if os.path.exists(ROOMS_FILE):
                with open(ROOMS_FILE, 'r') as f:
                    data = json.load(f)
                    # Convert dict data to Room objects
                    self.rooms = {k: Room(**v) for k, v in data.items()}
                logger.info(f"✓ Loaded {len(self.rooms)} rooms from {ROOMS_FILE}")
            else:
                # First run - create default rooms
                self.create_default_rooms()
        except Exception as e:
            logger.error(f"Load error: {e}")
            # On error, start fresh with default rooms
            self.create_default_rooms()
    
    def save_rooms(self):
        """
        Persist rooms to file (rooms.json).
        
        Called after any create/delete operation to maintain persistence.
        Converts Room objects to dictionaries for JSON serialization.
        """
        try:
            # Convert Room objects to dicts for JSON
            data = {k: v.dict() for k, v in self.rooms.items()}
            with open(ROOMS_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Save error: {e}")
    
    def create_default_rooms(self):
        """
        Create initial default rooms on first run.
        
        Creates "General" and "Welcome" rooms so users have somewhere
        to start chatting immediately.
        """
        defaults = [
            {"name": "General", "description": "General discussion", "created_by": "system"},
            {"name": "Welcome", "description": "Welcome new users!", "created_by": "system"},
        ]
        
        for rd in defaults:
            room = Room(
                id=str(uuid.uuid4()),  # Generate unique ID
                name=rd["name"],
                description=rd["description"],
                created_by=rd["created_by"],
                created_at=datetime.utcnow().isoformat(),
                member_count=0
            )
            self.rooms[room.id] = room
        
        self.save_rooms()
        logger.info(f"✓ Created {len(defaults)} default rooms")
    
    def create_room(self, name: str, description: str, created_by: str) -> Room:
        """
        Create a new room and persist it.
        
        Args:
            name: Room name
            description: Room description
            created_by: Username of creator
            
        Returns:
            Room: The newly created room object
            
        Note:
            Caller should verify name uniqueness before calling this.
        """
        room = Room(
            id=str(uuid.uuid4()),  # Generate unique UUID
            name=name,
            description=description,
            created_by=created_by,
            created_at=datetime.utcnow().isoformat(),
            member_count=0
        )
        self.rooms[room.id] = room
        self.save_rooms()  # Persist immediately
        logger.info(f"✓ Created room: {room.name}")
        return room
    
    def get_room(self, room_id: str) -> Optional[Room]:
        """
        Get a room by ID.
        
        Args:
            room_id: UUID of the room
            
        Returns:
            Room object if found, None otherwise
        """
        return self.rooms.get(room_id)
    
    def list_rooms(self) -> List[Room]:
        """
        Get all rooms.
        
        Returns:
            List of all Room objects
        """
        return list(self.rooms.values())
    
    def delete_room(self, room_id: str) -> bool:
        """
        Delete a room and persist the change.
        
        Args:
            room_id: UUID of room to delete
            
        Returns:
            True if room was deleted, False if room didn't exist
        """
        if room_id in self.rooms:
            del self.rooms[room_id]
            self.save_rooms()  # Persist deletion
            logger.info(f"✓ Deleted room: {room_id}")
            return True
        return False
    
    def update_member_count(self, room_id: str, count: int):
        """
        Update the member count for a room (in memory only, not persisted).
        
        Args:
            room_id: UUID of room
            count: New member count
            
        Note:
            Member counts are dynamic and not persisted to disk.
        """
        if room_id in self.rooms:
            self.rooms[room_id].member_count = count