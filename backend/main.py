"""
Azure Service Bus Dynamic Chatrooms - Cost-Optimal Implementation

ARCHITECTURE OVERVIEW:
======================
This implementation uses a SINGLE Azure Service Bus subscription with backend routing
to achieve cost-optimal scaling. This avoids the cost disaster of creating one 
subscription per room, which would result in (messages × rooms) operations.

COST MODEL:
===========
- Current: 2 operations per message (1 publish + 1 delivery to single subscription)
- Alternative (per-room subs): (1 + N) operations per message, where N = number of rooms
- Example: 100K messages/day, 1000 rooms
  * Current: 200K ops/day = 6M/month = $0 (free tier)
  * Alternative: 100M ops/day = 3B/month = $149/month ❌

MESSAGE FLOW:
=============
1. User sends message to "Product Team" room
2. Frontend: POST /publish with room_id="uuid-123"
3. Backend: Publishes to Service Bus topic (1 operation)
4. Service Bus: Delivers to single subscription (1 operation)
5. Backend listener: Receives message, reads room_id
6. Backend: Broadcasts ONLY to WebSockets subscribed to room_id="uuid-123"
7. Users in other rooms: Never receive the message ✓

KEY FEATURES:
=============
- Dynamic room creation by users
- Room persistence (survives restarts via rooms.json)
- Real-time WebSocket messaging
- Perfect room isolation
- Cost monitoring via /metrics endpoint
- Scalable to 10K concurrent users (single instance)

SCALING PATH:
=============
- 0-10K users: Current implementation (cost: $0-5/month)
- 10K-100K users: Migrate to Redis Pub/Sub (cost: $46/month fixed)
- 100K+ users: Migrate to Azure SignalR (cost: $489/month)

See COST_ANALYSIS.md for complete cost breakdown and migration guides.

Author: Alkis
Version: 2.0 - Cost-Optimal Dynamic Chatrooms
"""
# backend/main.py

from __future__ import annotations

import asyncio

from core import state
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.logging import setup_logging, get_logger
from services.service_bus import listen_to_service_bus
from services.redis_pub_sub import AsyncRedisPubSubService
from api.routes import root, health, metrics, rooms, publish
from api import websocket as websocket_module
from services.service_bus import  _init_sync_client, shutdown_sync_client

# Configure logging first
setup_logging()
logger = get_logger(__name__)

# FastAPI app
app = FastAPI(title="Azure Dynamic Chatrooms - Cost Optimal")

# CORS (relaxed for now – tighten in prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST routes
app.include_router(root.router)
app.include_router(health.router)
app.include_router(metrics.router)
app.include_router(rooms.router)
app.include_router(publish.router)

# WebSocket routes
app.include_router(websocket_module.router)


@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Application starting - Dynamic Chatrooms enabled")

    if settings.PUB_SUB_SERVICE == "redis":
        # Start Redis listener in the background
        redis_service = AsyncRedisPubSubService(host="localhost", port=6379) 
        await redis_service.connect()
        
        # Store globally
        state.redis_service = redis_service

        # Start subscriber in background
        asyncio.create_task(redis_service.listen("room:*"))    
    elif settings.PUB_SUB_SERVICE == "service_bus":
        from services.async_service_bus_service import AsyncServiceBusService
        service_bus = AsyncServiceBusService()
        await service_bus.connect()
        state.service_bus = service_bus
        asyncio.create_task(service_bus.listen())

@app.on_event("shutdown")
async def on_shutdown():
    shutdown_sync_client()
    if hasattr(state, 'service_bus'):
        await state.service_bus.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)

# ============================================================================
# END OF FILE
# ============================================================================
"""
SUMMARY:
========
This implementation achieves cost optimization by using a SINGLE Azure Service
Bus subscription instead of creating one subscription per room. Messages are
routed in the backend based on room_id, which costs 2 operations per message
regardless of room count.

For detailed cost analysis and scaling strategies, see:
- COST_ANALYSIS.md (complete cost breakdown)
- DEPLOYMENT_READY.md (deployment guide)
- DYNAMIC_CHATROOMS_GUIDE.md (technical reference)

To deploy:
    git add backend/main.py backend/requirements.txt
    git commit -m "Deploy cost-optimal dynamic chatrooms"
    git push

Author: Alkis
Version: 2.0 - Cost-Optimal Dynamic Chatrooms
Last Updated: 2025-12-01
"""
