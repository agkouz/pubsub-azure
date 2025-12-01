# app/api/routes/root.py

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def root():
    """
    Root endpoint - API information.
    
    Returns basic info about the API and its features.
    """
    return {
        "message": "Azure Dynamic Chatrooms - Cost Optimal",
        "version": "2.0",
        "architecture": "1 subscription + backend routing",
        "cost_model": "2 operations per message (independent of room count)",
        "features": ["dynamic_rooms", "room_creation", "cost_optimal", "scalable"],
        "endpoints": {
            "websocket": "/ws",
            "rooms": "/rooms",
            "publish": "/publish",
            "health": "/health",
            "metrics": "/metrics",
        },
    }
