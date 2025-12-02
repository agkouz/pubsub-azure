# backend/api/publish.py
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from models.models import PublishMessageRequest
from core import state
from services.service_bus import publish_to_service_bus

# ============================================================================
# MESSAGE PUBLISHING ENDPOINT
# ============================================================================

router = APIRouter()

@router.post("/publish")
async def publish_message(request: PublishMessageRequest):
    """
    Publish a message to a specific room via Service Bus.
    
    This is where the cost optimization happens:
    
    Flow:
        1. Validate room exists
        2. Create message with room_id property
        3. Publish to Service Bus topic (1 operation)
        4. Service Bus delivers to our SINGLE subscription (1 operation)
        5. Background listener receives it
        6. Background listener calls manager.broadcast_to_room(room_id, ...)
        7. Only WebSockets subscribed to room_id receive the message
    
    Total: 2 Service Bus operations, regardless of how many rooms exist!
    
    Compare to alternative (1 subscription per room):
        - Would need to publish to N subscriptions
        - Total: 1 publish + N deliveries = (1 + N) operations
        - For 1000 rooms: 1001 operations per message! 💸
    
    Args:
        request: PublishMessageRequest with room_id, content, sender
    
    Returns:
        dict: Success status and room name
    
    Raises:
        HTTPException: 404 if room not found, 500 on publish error
    
    Side Effects:
        - Increments global message_counter (for /metrics)
        - Publishes message to Service Bus
    """
    room = state.room_manager.get_room(request.room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    message_data = {
        "room_id": request.room_id,
        "room_name": room.name,
        "content": request.content,
        "sender": request.sender,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        publish_to_service_bus(message_data)
        state.message_counter += 1
        return {"status": "success", "room": room.name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))