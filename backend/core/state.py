# app/core/state.py
from datetime import datetime
from app.services.room_manager import RoomManager
from app.services.connection_manager import ConnectionManager

room_manager = RoomManager()
connection_manager = ConnectionManager()

# Metrics
message_counter: int = 0
app_start_time: datetime = datetime.utcnow()
