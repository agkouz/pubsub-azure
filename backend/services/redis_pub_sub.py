# backend/services/redis_pub_sub.py - rewrite as async
import redis.asyncio as redis
from core.config import settings
import json
import logging

logger = logging.getLogger(__name__)

class AsyncRedisPubSubService:
    def __init__(self, host: str = "localhost", port: int = 6379):
        self.host = host
        self.port = port
        self.client = None
        self.pubsub = None
        self.access_key = settings.REDIS_ACCESS_KEY

    async def connect(self):
        """Establish async connection to Redis."""
        self.client = redis.from_url(
            f"rediss://:{self.access_key}@{self.host}:{self.port}",
            decode_responses=True
        )
        await self.client.ping()
        logger.info(f"✓ Connected to Redis at {self.host}:{self.port}")

    async def publish(self, channel: str, message: dict):
        """Publish message to channel."""
        await self.client.publish(channel, json.dumps(message))
        logger.info(f"📤 Published to Redis channel '{channel}'")

    async def broadcast_to_room(self, room_id: str, message: dict):
        """
        Broadcast a message to a specific room via Redis Pub/Sub.
        
        This publishes to a room-specific Redis channel. The listener
        will receive it and forward to WebSocket connections.
        
        Args:
            room_id: Target room UUID
            message: Message dict (must include room_id)
        
        Note: Unlike Service Bus which uses a single topic with routing,
              Redis uses separate channels per room for simplicity.
        """
        channel = f"room:{room_id}"
        await self.publish(channel, message)
        logger.info(f"📨 Broadcasted to room {room_id} via Redis")

    async def listen(self, channel: str):
        """
        Listen to Redis channel and broadcast to WebSockets.
        
        For multi-room support, call this with a pattern:
            await redis_service.listen("room:*")
        """
        from core import state
        
        self.pubsub = self.client.pubsub()
        
        # Support pattern matching for multiple rooms
        if "*" in channel:
            await self.pubsub.psubscribe(channel)
            logger.info(f"✓ Subscribed to Redis pattern '{channel}'")
        else:
            await self.pubsub.subscribe(channel)
            logger.info(f"✓ Subscribed to Redis channel '{channel}'")
        
        async for message in self.pubsub.listen():
            if message["type"] in ("message", "pmessage"):
                try:
                    data = json.loads(message["data"])
                    room_id = data.get("room_id")
                    
                    if room_id:
                        logger.info(
                            f"➡ Redis: Routing to room={room_id}, "
                            f"sender={data.get('sender')}"
                        )
                        await state.connection_manager.broadcast_to_room(room_id, data)
                    else:
                        logger.warning("Redis message without room_id - ignoring")
                    
                except Exception as e:
                    logger.error(f"Error processing Redis message: {e}")

    async def close(self):
        """Close connections."""
        if self.pubsub:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()
        if self.client:
            await self.client.close()
        logger.info("Redis connection closed")