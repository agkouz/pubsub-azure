# backend/api/utils.py

from __future__ import annotations

from backend.core import state

async def broadcast_room_list_update():
    """
    Helper function to notify all clients that the room list has changed.
    
    Sends "rooms_updated" message with full room list to all connected
    WebSocket clients. Used after room creation/deletion.
    
    Side Effects:
        Sends JSON message to all WebSocket connections:
        {
            "type": "rooms_updated",
            "rooms": [list of room objects]
        }
    """
    rooms_data = [r.model_dump() for r in state.room_manager.list_rooms()]

    for websocket in list(state.connection_manager.connection_rooms.keys()):
        try:
            await websocket.send_json(
                {
                    "type": "rooms_updated",
                    "rooms": rooms_data,
                }
            )
        except Exception:
            # Ignore send failures (connection may be closing)
            pass