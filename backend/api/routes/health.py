# backend/api/routes/health.py

from fastapi import APIRouter

from backend.core import state

router = APIRouter()

@router.get("/health")
async def health():
    """
    Health check endpoint.
    
    Returns current system status, connection counts, and room counts.
    Used by Azure App Service health probes and monitoring.
    
    Returns:
        dict: Status, connection count, room count, active room count
    """
    return {
        "status": "healthy",
        "connections": len(state.connection_manager.connection_rooms),
        "rooms": len(state.room_manager.rooms),
        "active_rooms_with_members": len(state.connection_manager.rooms),
    }