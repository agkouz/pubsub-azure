# backend/core/state.py
from __future__ import annotations

from datetime import datetime, timezone

from services.room_manager import RoomManager
from services.connection_manager import ConnectionManager

# Global singletons for app state
room_manager = RoomManager()
connection_manager = ConnectionManager(room_manager=room_manager)

# Metrics
message_counter: int = 0
app_start_time: datetime = datetime.now(timezone.utc)