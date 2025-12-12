# backend/main.py

from __future__ import annotations

import asyncio

from core import state
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.logging import setup_logging, get_logger
from services.redis_pub_sub import AsyncRedisPubSubService
from api.routes import root, health, metrics, rooms
from api import websocket as websocket_module
from services.gcloud_pub_sub import shutdown_pubsub, init_pubsub

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

# WebSocket routes
app.include_router(websocket_module.router)


@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Application starting - Dynamic Chatrooms enabled")

    if settings.PUB_SUB_SERVICE == "redis":
        # Start Redis listener in the background
        redis_service = AsyncRedisPubSubService(host=settings.REDIS_HOST, port=settings.REDIS_PORT) 
        await redis_service.connect()
        
        # Store globally
        state.redis_service = redis_service

        # Start subscriber in background
        asyncio.create_task(redis_service.listen("room:*"))    
    elif settings.PUB_SUB_SERVICE == "google_pub_sub":
        loop = asyncio.get_running_loop()
        init_pubsub(loop)

@app.on_event("shutdown")
async def on_shutdown():
    if settings.PUB_SUB_SERVICE == "google_pub_sub":
        shutdown_pubsub()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)

# ============================================================================
# END OF FILE
# ============================================================================
