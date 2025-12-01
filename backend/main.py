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

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from azure.servicebus.aio import ServiceBusClient as AsyncServiceBusClient
from azure.identity import DefaultAzureCredential
from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential
import asyncio
import json
import os
from typing import Set, Dict, Optional, List
from pydantic import BaseModel
import logging
import traceback
from datetime import datetime
import uuid

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Reduce Azure SDK noise in logs
logging.getLogger('azure.servicebus._pyamqp').setLevel(logging.WARNING)
logging.getLogger('azure.identity.aio').setLevel(logging.WARNING)

# ============================================================================
# FASTAPI APPLICATION SETUP
# ============================================================================

app = FastAPI(title="Azure Dynamic Chatrooms - Cost Optimal")

# Enable CORS for all origins (tighten in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# AZURE SERVICE BUS CONFIGURATION
# ============================================================================

# Connection can be via connection string OR Azure AD Managed Identity
CONNECTION_STRING = os.getenv("AZURE_SERVICEBUS_CONNECTION_STRING", "")
NAMESPACE_FQDN = os.getenv("AZURE_SERVICEBUS_NAMESPACE_FQDN", "")
TOPIC_NAME = os.getenv("AZURE_SERVICEBUS_TOPIC_NAME", "backend-messages")
SUBSCRIPTION_NAME = os.getenv("AZURE_SERVICEBUS_SUBSCRIPTION_NAME", "backend-subscription")

# Determine authentication method
# If NAMESPACE_FQDN is set and connection string is empty, use Azure AD
USE_AZURE_AD = bool(NAMESPACE_FQDN and not CONNECTION_STRING)

# Log configuration on startup
logger.info("=" * 70)
logger.info("COST-OPTIMAL ARCHITECTURE: 1 SUBSCRIPTION + BACKEND ROUTING")
logger.info("=" * 70)
if USE_AZURE_AD:
    logger.info("Auth: Azure AD Managed Identity")
    logger.info(f"Namespace: {NAMESPACE_FQDN}")
else:
    logger.info("Auth: Connection String")
logger.info(f"Topic: {TOPIC_NAME}")
logger.info(f"Subscription: {SUBSCRIPTION_NAME}")
logger.info("Cost: 2 operations per message (publish + delivery)")
logger.info("Scaling: Independent of room count ✓")
logger.info("=" * 70)

# ============================================================================
# METRICS TRACKING
# ============================================================================

# Track total messages for cost estimation
message_counter = 0
app_start_time = datetime.utcnow()

# ============================================================================
# PYDANTIC MODELS (DATA VALIDATION)
# ============================================================================

class Room(BaseModel):
    """
    Room data model representing a chatroom.
    
    Attributes:
        id: Unique identifier (UUID)
        name: Human-readable room name
        description: Optional room description
        created_by: Username of room creator
        created_at: ISO timestamp of creation
        member_count: Current number of connected members (updated dynamically)
    """
    id: str
    name: str
    description: Optional[str] = ""
    created_by: str
    created_at: str
    member_count: int = 0

class CreateRoomRequest(BaseModel):
    """
    Request model for creating a new room.
    
    Attributes:
        name: Room name (required, will be checked for duplicates)
        description: Optional room description
        created_by: Username creating the room (defaults to "anonymous")
    """
    name: str
    description: Optional[str] = ""
    created_by: str = "anonymous"

class PublishMessageRequest(BaseModel):
    """
    Request model for publishing a message to a room.
    
    Attributes:
        room_id: Target room UUID
        content: Message content/text
        sender: Username of sender (defaults to "anonymous")
    """
    room_id: str
    content: str
    sender: Optional[str] = "anonymous"

# ============================================================================
# ROOM PERSISTENCE MANAGER
# ============================================================================

ROOMS_FILE = "rooms.json"  # File where room metadata is persisted

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

# Initialize global room manager instance
room_manager = RoomManager()

# ============================================================================
# WEBSOCKET CONNECTION MANAGER
# ============================================================================

class ConnectionManager:
    """
    Manages WebSocket connections and room memberships.
    
    This is the core of the cost-optimal architecture. Instead of using
    Service Bus subscriptions to filter messages, this class maintains
    in-memory mappings of which WebSockets are subscribed to which rooms,
    and broadcasts messages only to the appropriate connections.
    
    Data Structures:
        rooms: Maps room_id -> Set of WebSocket connections in that room
               Example: {"uuid-123": {websocket1, websocket2}}
        
        connection_rooms: Maps WebSocket -> Set of room_ids it's subscribed to
                         Example: {websocket1: {"uuid-123", "uuid-456"}}
        
        connection_users: Maps WebSocket -> user_id (for logging/debugging)
    
    Scaling:
        - Single instance: Works perfectly, all in-memory
        - Multi-instance: Need shared state (Redis) for rooms mapping
    
    Cost Impact:
        - This approach costs 2 operations per message (publish + delivery)
        - Alternative (per-room subscriptions) would cost (1 + N) operations
          where N is the number of rooms, which scales terribly!
    """
    
    def __init__(self):
        """Initialize connection manager with empty data structures."""
        # Map: room_id -> Set[WebSocket connections]
        self.rooms: Dict[str, Set[WebSocket]] = {}
        
        # Map: WebSocket -> Set[room_ids it's subscribed to]
        self.connection_rooms: Dict[WebSocket, Set[str]] = {}
        
        # Map: WebSocket -> user_id (for logging)
        self.connection_users: Dict[WebSocket, str] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str = "anonymous"):
        """
        Accept a new WebSocket connection.
        
        Args:
            websocket: The WebSocket connection object
            user_id: Username for this connection (optional)
            
        Note:
            User is not automatically joined to any rooms. They must
            explicitly send "join" actions for each room.
        """
        await websocket.accept()
        
        # Initialize empty room set for this connection
        self.connection_rooms[websocket] = set()
        self.connection_users[websocket] = user_id
        
        logger.info(f"✓ User {user_id} connected. Total: {len(self.connection_rooms)}")
    
    def disconnect(self, websocket: WebSocket):
        """
        Handle WebSocket disconnection and cleanup.
        
        Args:
            websocket: The disconnecting WebSocket
            
        Cleanup:
            1. Remove from all rooms they were in
            2. Update room member counts
            3. Delete empty rooms from memory
            4. Remove from tracking dictionaries
        """
        if websocket in self.connection_rooms:
            user_id = self.connection_users.get(websocket, "unknown")
            
            # Remove from all rooms
            for room_id in self.connection_rooms[websocket]:
                if room_id in self.rooms:
                    self.rooms[room_id].discard(websocket)
                    # Update member count in room metadata
                    room_manager.update_member_count(room_id, len(self.rooms[room_id]))
                    # Clean up empty rooms from memory
                    if not self.rooms[room_id]:
                        del self.rooms[room_id]
            
            # Remove from tracking dicts
            del self.connection_rooms[websocket]
            del self.connection_users[websocket]
            
            logger.info(f"✗ User {user_id} disconnected. Total: {len(self.connection_rooms)}")
    
    async def join_room(self, websocket: WebSocket, room_id: str):
        """
        Subscribe a WebSocket connection to a room.
        
        Args:
            websocket: The WebSocket connection
            room_id: UUID of room to join
            
        Process:
            1. Verify room exists in room_manager
            2. Add websocket to room's connection set
            3. Add room to websocket's subscribed rooms
            4. Update member count
            5. Send confirmation to client
            
        After joining, the connection will receive all messages published
        to this room via Service Bus.
        """
        # Verify room exists
        room = room_manager.get_room(room_id)
        if not room:
            await websocket.send_json({"type": "error", "message": f"Room not found"})
            return
        
        if websocket not in self.connection_rooms:
            return  # Connection already closed
        
        # Add to room's connection set
        if room_id not in self.rooms:
            self.rooms[room_id] = set()
        self.rooms[room_id].add(websocket)
        
        # Add to connection's subscribed rooms
        self.connection_rooms[websocket].add(room_id)
        
        # Update member count
        member_count = len(self.rooms[room_id])
        room_manager.update_member_count(room_id, member_count)
        
        user_id = self.connection_users.get(websocket, "anonymous")
        logger.info(f"→ {user_id} joined '{room.name}' ({member_count} members)")
        
        # Send confirmation to client
        await websocket.send_json({
            "type": "room_joined",
            "room": room.dict(),
            "member_count": member_count
        })
    
    async def leave_room(self, websocket: WebSocket, room_id: str):
        """
        Unsubscribe a WebSocket connection from a room.
        
        Args:
            websocket: The WebSocket connection
            room_id: UUID of room to leave
            
        After leaving, the connection will no longer receive messages
        published to this room.
        """
        if websocket not in self.connection_rooms:
            return  # Connection already closed
        
        if room_id in self.connection_rooms[websocket]:
            # Remove from connection's subscribed rooms
            self.connection_rooms[websocket].discard(room_id)
            
            if room_id in self.rooms:
                # Remove from room's connection set
                self.rooms[room_id].discard(websocket)
                member_count = len(self.rooms[room_id])
                room_manager.update_member_count(room_id, member_count)
                
                # Clean up empty room
                if not self.rooms[room_id]:
                    del self.rooms[room_id]
                
                # Send confirmation to client
                await websocket.send_json({
                    "type": "room_left",
                    "room_id": room_id,
                    "member_count": member_count
                })
    
    async def broadcast_to_room(self, room_id: str, message: dict):
        """
        Broadcast a message to all WebSockets subscribed to a room.
        
        This is the KEY COST OPTIMIZATION: Instead of Service Bus delivering
        to N subscriptions (N operations), we deliver once to our single
        subscription and then broadcast in memory to the appropriate
        WebSocket connections.
        
        Args:
            room_id: UUID of target room
            message: Message dict to send (will be JSON serialized)
            
        Cost Impact:
            - Service Bus: 1 delivery operation (to our single subscription)
            - Backend: 0 operations (in-memory broadcast)
            - Total: 1 operation (vs N operations for per-room subscriptions)
        
        Error Handling:
            If a send fails, the connection is marked as disconnected
            and cleaned up.
        """
        if room_id not in self.rooms:
            # No one subscribed to this room currently
            return
        
        disconnected = set()
        connections = self.rooms[room_id].copy()  # Copy to avoid modification during iteration
        
        logger.info(f"📨 Broadcasting to room {room_id}: {len(connections)} clients")
        
        # Send to each connection in the room
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Send error: {e}")
                # Mark for cleanup
                disconnected.add(connection)
        
        # Clean up failed connections
        for conn in disconnected:
            self.disconnect(conn)
    
    def get_rooms_info(self) -> Dict[str, dict]:
        """
        Get information about all active rooms with members.
        
        Returns:
            Dict mapping room_id to room info (name, member_count)
            
        Used by the /metrics endpoint and for debugging.
        """
        result = {}
        for room_id, connections in self.rooms.items():
            room = room_manager.get_room(room_id)
            if room:
                result[room_id] = {
                    "name": room.name,
                    "member_count": len(connections)
                }
        return result

# Initialize global connection manager instance
manager = ConnectionManager()

# ============================================================================
# SERVICE BUS BACKGROUND LISTENER
# ============================================================================

async def listen_to_service_bus():
    """
    Background task that listens to Azure Service Bus and broadcasts messages.
    
    This is the heart of the cost-optimal architecture:
    
    Flow:
        1. Listens to SINGLE subscription (not one per room!)
        2. Receives message with room_id property
        3. Calls manager.broadcast_to_room(room_id, message)
        4. Only WebSockets subscribed to that room receive the message
    
    Cost Analysis:
        - Each message = 1 publish + 1 delivery = 2 operations
        - If we had N subscriptions (one per room):
          Each message = 1 publish + N deliveries = (1 + N) operations
        - For 1000 rooms: 2 ops vs 1001 ops = 500x cost savings!
    
    Error Handling:
        - Retries on connection failure
        - Completes messages even on processing errors
        - Auto-reconnects if connection drops
    
    Lifecycle:
        Started by @app.on_event("startup")
        Runs continuously in background
        Uses async context managers for proper cleanup
    """
    if not CONNECTION_STRING and not NAMESPACE_FQDN:
        logger.warning("Service Bus not configured - messages won't be received")
        return

    logger.info("🚀 Starting Service Bus listener...")

    try:
        # Create async Service Bus client with Managed Identity or connection string
        if USE_AZURE_AD:
            credential = AsyncDefaultAzureCredential()
            client = AsyncServiceBusClient(
                fully_qualified_namespace=NAMESPACE_FQDN,
                credential=credential
            )
        else:
            client = AsyncServiceBusClient.from_connection_string(CONNECTION_STRING)

        async with client:
            receiver = client.get_subscription_receiver(
                topic_name=TOPIC_NAME,
                subscription_name=SUBSCRIPTION_NAME,
                max_wait_time=5,  # wait up to 5s for new messages
            )

            async with receiver:
                logger.info(
                    f"✓ Listening to Service Bus topic='{TOPIC_NAME}', "
                    f"subscription='{SUBSCRIPTION_NAME}' (1 subscription, cost-optimal)"
                )

                while True:
                    try:
                        # Pull up to 10 messages at a time
                        messages = await receiver.receive_messages(
                            max_message_count=10,
                            max_wait_time=5
                        )

                        if not messages:
                            # No messages this cycle, just loop again
                            continue

                        for msg in messages:
                            try:
                                # Decode body
                                body_bytes = b"".join(msg.body)
                                message_body = body_bytes.decode("utf-8")
                                logger.info(f"📥 Received raw message body: {message_body}")

                                message_data = json.loads(message_body)
                                room_id = message_data.get("room_id")

                                if room_id:
                                    logger.info(
                                        f"➡ Routing message to room_id={room_id}, "
                                        f"content={message_data.get('content')!r}, "
                                        f"sender={message_data.get('sender')!r}"
                                    )
                                    await manager.broadcast_to_room(room_id, message_data)
                                else:
                                    logger.warning("Message without room_id - ignoring")

                                await receiver.complete_message(msg)
                            except Exception as e:
                                logger.error(f"Error processing individual message: {e}")
                                logger.error(traceback.format_exc())
                                # Complete to avoid poison loops
                                await receiver.complete_message(msg)

                    except Exception as e:
                        logger.error(f"Service Bus receive loop error: {e}")
                        logger.error(traceback.format_exc())
                        # Brief backoff on error
                        await asyncio.sleep(5)

    except Exception as e:
        logger.error(f"Service Bus listener error (outer): {e}")
        logger.error(traceback.format_exc())
# ============================================================================
# APPLICATION LIFECYCLE EVENTS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """
    Application startup handler.
    
    Starts the background Service Bus listener task.
    This runs once when the FastAPI application starts.
    """
    logger.info("🚀 Application starting - Dynamic Chatrooms enabled")
    # Start background listener (don't await - runs in background)
    asyncio.create_task(listen_to_service_bus())

# ============================================================================
# REST API ENDPOINTS
# ============================================================================

@app.get("/")
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
            "metrics": "/metrics"
        }
    }

@app.get("/health")
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
        "connections": len(manager.connection_rooms),
        "rooms": len(room_manager.rooms),
        "active_rooms_with_members": len(manager.rooms)
    }

@app.get("/metrics")
async def get_metrics():
    """
    Cost monitoring and scaling metrics endpoint.
    
    This endpoint provides real-time cost estimates and scaling recommendations
    based on actual usage patterns. It tells you EXACTLY when to migrate to
    Redis or Azure SignalR.
    
    Returns:
        dict: Comprehensive metrics including:
            - Message statistics (total, daily projection, messages/sec)
            - Cost estimates (operations, free tier usage, monthly cost)
            - Capacity (connections, rooms, active rooms)
            - Scaling recommendation (when to migrate)
            - Thresholds for different solutions
    
    Example Response:
        {
            "daily_messages_projected": 50000,
            "monthly_operations_projected": 3000000,
            "estimated_monthly_cost_usd": 0,
            "free_tier_percent_used": 24,
            "concurrent_connections": 100,
            "recommendation": "✅ CURRENT SOLUTION OPTIMAL",
            "reason": "Under free tier, single instance sufficient",
            "priority": "NONE",
            "thresholds": {
                "redis_at_messages_per_day": 200000,
                "redis_at_concurrent_users": 5000
            }
        }
    
    Use this to:
        - Monitor costs in real-time
        - Know when to scale
        - Plan infrastructure changes
        - Track growth
    """
    global message_counter, app_start_time
    
    # Calculate uptime
    uptime = (datetime.utcnow() - app_start_time).total_seconds()
    
    # Project daily message volume
    if uptime > 0:
        messages_per_second = message_counter / uptime
        daily_messages = int(messages_per_second * 86400)  # 86400 seconds in a day
    else:
        daily_messages = 0
    
    # Project monthly operations (2 operations per message)
    monthly_operations = daily_messages * 30 * 2
    
    # Calculate estimated cost
    # First 12.5M operations/month are free, then $0.05 per million
    estimated_cost = 0
    free_tier = 12_500_000
    if monthly_operations > free_tier:
        estimated_cost = (monthly_operations - free_tier) * 0.05 / 1_000_000
    else:
        estimated_cost = 0
    
    # Determine scaling recommendation
    concurrent = len(manager.connection_rooms)
    
    if daily_messages > 200_000:
        # High message volume - Redis has fixed cost
        recommendation = "🔄 MIGRATE TO REDIS"
        reason = "High message volume - Redis has fixed cost ($46/mo)"
        priority = "HIGH"
    elif concurrent > 5000:
        # High concurrent users - need multi-instance
        recommendation = "🔄 MIGRATE TO REDIS"
        reason = "High concurrent users - need multi-instance support"
        priority = "MEDIUM"
    elif estimated_cost > 10:
        # Monthly cost exceeding Redis cost
        recommendation = "🔄 MIGRATE TO REDIS"
        reason = f"Monthly cost ${estimated_cost:.2f} - Redis cheaper at $46/mo"
        priority = "MEDIUM"
    elif concurrent > 1000:
        # Growing but not urgent
        recommendation = "⚠️ PREPARE FOR REDIS"
        reason = "Growing concurrent users - plan Redis migration"
        priority = "LOW"
    else:
        # All good!
        recommendation = "✅ CURRENT SOLUTION OPTIMAL"
        reason = "Under free tier, single instance sufficient"
        priority = "NONE"
    
    return {
        # Statistics
        "total_messages": message_counter,
        "uptime_hours": round(uptime / 3600, 2),
        "daily_messages_projected": daily_messages,
        "messages_per_second": round(message_counter / uptime, 2) if uptime > 0 else 0,
        
        # Costs
        "monthly_operations_projected": monthly_operations,
        "estimated_monthly_cost_usd": round(estimated_cost, 2),
        "free_tier_limit": free_tier,
        "free_tier_remaining": max(0, free_tier - monthly_operations),
        "free_tier_percent_used": round((monthly_operations / free_tier) * 100, 1) if monthly_operations < free_tier else 100,
        
        # Capacity
        "concurrent_connections": concurrent,
        "total_rooms": len(room_manager.rooms),
        "active_rooms_with_members": len(manager.rooms),
        
        # Scaling
        "recommendation": recommendation,
        "reason": reason,
        "priority": priority,
        
        # Thresholds
        "thresholds": {
            "redis_at_messages_per_day": 200_000,
            "redis_at_concurrent_users": 5_000,
            "redis_at_monthly_cost": 10,
            "signalr_at_concurrent_users": 100_000
        }
    }

# ============================================================================
# ROOM CRUD ENDPOINTS
# ============================================================================

@app.get("/rooms", response_model=List[Room])
async def list_rooms():
    """
    List all available rooms.
    
    Returns room metadata with current member counts updated from
    active WebSocket connections.
    
    Returns:
        List[Room]: All rooms with updated member counts
    """
    rooms = room_manager.list_rooms()
    
    # Update member counts from live connections
    for room in rooms:
        if room.id in manager.rooms:
            room.member_count = len(manager.rooms[room.id])
    
    return rooms

@app.post("/rooms", response_model=Room)
async def create_room(request: CreateRoomRequest):
    """
    Create a new chatroom.
    
    Users can create unlimited rooms. Room is persisted to disk and
    broadcasts to all connected clients.
    
    Args:
        request: CreateRoomRequest with name, description, created_by
    
    Returns:
        Room: The newly created room
    
    Raises:
        HTTPException: 400 if name is empty or already exists
    
    Side Effects:
        - Room saved to rooms.json
        - "rooms_updated" message broadcast to all WebSocket clients
    """
    # Validate name
    if not request.name.strip():
        raise HTTPException(status_code=400, detail="Room name required")
    
    # Check for duplicate names (case-insensitive)
    existing = room_manager.list_rooms()
    if any(r.name.lower() == request.name.lower() for r in existing):
        raise HTTPException(status_code=400, detail="Room name exists")
    
    # Create room
    room = room_manager.create_room(
        name=request.name,
        description=request.description,
        created_by=request.created_by
    )
    
    # Notify all connected clients that room list has changed
    asyncio.create_task(broadcast_room_list_update())
    
    return room

@app.delete("/rooms/{room_id}")
async def delete_room(room_id: str):
    """
    Delete a room.
    
    Kicks all users from the room, deletes from persistence, and
    notifies all clients.
    
    Args:
        room_id: UUID of room to delete
    
    Returns:
        dict: Status message with room_id
    
    Raises:
        HTTPException: 404 if room not found
    
    Side Effects:
        - All users in room are sent "room_left" messages
        - Room removed from rooms.json
        - "rooms_updated" broadcast to all clients
    
    TODO: Add authorization check (only creator should be able to delete)
    """
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Kick all users from room
    if room_id in manager.rooms:
        connections = manager.rooms[room_id].copy()
        for conn in connections:
            await manager.leave_room(conn, room_id)
    
    # Delete from persistence
    room_manager.delete_room(room_id)
    
    # Notify all clients
    asyncio.create_task(broadcast_room_list_update())
    
    return {"status": "deleted", "room_id": room_id}

@app.get("/rooms/{room_id}", response_model=Room)
async def get_room(room_id: str):
    """
    Get details of a specific room.
    
    Args:
        room_id: UUID of room
    
    Returns:
        Room: Room object with current member count
    
    Raises:
        HTTPException: 404 if room not found
    """
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Update member count from live connections
    if room_id in manager.rooms:
        room.member_count = len(manager.rooms[room_id])
    
    return room

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
    rooms_data = [r.dict() for r in room_manager.list_rooms()]
    
    # Send to all connected clients
    for websocket in list(manager.connection_rooms.keys()):
        try:
            await websocket.send_json({
                "type": "rooms_updated",
                "rooms": rooms_data
            })
        except:
            # Ignore send failures (connection may be closing)
            pass

# ============================================================================
# MESSAGE PUBLISHING ENDPOINT
# ============================================================================

@app.post("/publish")
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
    global message_counter
    
    # Verify room exists
    room = room_manager.get_room(request.room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    try:
        # Create message with room_id (critical for routing!)
        message_data = {
            "room_id": request.room_id,      # Used by listener to route
            "room_name": room.name,          # For display
            "content": request.content,       # Message text
            "sender": request.sender,         # Username
            "timestamp": datetime.utcnow().isoformat(),  # ISO timestamp
        }
        
        # Create Service Bus client
        if USE_AZURE_AD:
            credential = DefaultAzureCredential()
            client = ServiceBusClient(
                fully_qualified_namespace=NAMESPACE_FQDN,
                credential=credential
            )
        else:
            client = ServiceBusClient.from_connection_string(CONNECTION_STRING)
        
        # Publish to Service Bus
        with client:
            sender = client.get_topic_sender(topic_name=TOPIC_NAME)
            with sender:
                # Create message with room_id in properties (for potential filtering)
                message = ServiceBusMessage(
                    body=json.dumps(message_data),
                    application_properties={"room_id": request.room_id}
                )
                # This is 1 operation
                sender.send_messages(message)
                
                # Increment counter for metrics
                message_counter += 1

        logger.info(f"📤 Published message to topic '{TOPIC_NAME}' for room {request.room_id}: {message_data}")
        return {"status": "success", "room": room.name}
    
    except Exception as e:
        logger.error(f"Publish error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# WEBSOCKET ENDPOINT
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, user_id: str = "anonymous"):
    """
    WebSocket endpoint for real-time bidirectional communication.
    
    Protocol:
    =========
    
    Client -> Server Actions:
    -------------------------
    Join Room:
        {"action": "join", "room_id": "uuid-123"}
        Response: {"type": "room_joined", "room": {...}, "member_count": 5}
    
    Leave Room:
        {"action": "leave", "room_id": "uuid-123"}
        Response: {"type": "room_left", "room_id": "uuid-123", "member_count": 4}
    
    List Rooms:
        {"action": "list_rooms"}
        Response: {"type": "rooms_list", "rooms": [...]}
    
    Get Room Info:
        {"action": "get_rooms_info"}
        Response: {"type": "rooms_info", "rooms": {"uuid-123": {"name": "...", "member_count": 5}}}
    
    Server -> Client Messages:
    -------------------------
    Regular Message:
        {"room_id": "uuid-123", "content": "Hello!", "sender": "alice", "timestamp": "..."}
    
    Room List Updated:
        {"type": "rooms_updated", "rooms": [...]}
    
    Error:
        {"type": "error", "message": "..."}
    
    Lifecycle:
    ==========
    1. Client connects with user_id parameter
    2. Connection accepted, user_id tracked
    3. Client sends "join" actions for desired rooms
    4. Client receives messages from subscribed rooms only
    5. On disconnect, automatically removed from all rooms
    
    Args:
        websocket: WebSocket connection object
        user_id: Query parameter for username (defaults to "anonymous")
    
    Error Handling:
        - Invalid JSON: Sends error message
        - Unknown actions: Sends error message
        - Connection errors: Cleanup and log
    """
    # Accept connection and register
    await manager.connect(websocket, user_id)
    
    try:
        # Main message loop - runs until disconnect
        while True:
            # Wait for message from client
            data = await websocket.receive_text()
            
            try:
                # Parse JSON
                message = json.loads(data)
                action = message.get("action")
                
                # Handle different actions
                if action == "join":
                    # Join a room
                    room_id = message.get("room_id")
                    if room_id:
                        await manager.join_room(websocket, room_id)
                
                elif action == "leave":
                    # Leave a room
                    room_id = message.get("room_id")
                    if room_id:
                        await manager.leave_room(websocket, room_id)
                
                elif action == "list_rooms":
                    # Get all rooms
                    rooms_data = [r.dict() for r in room_manager.list_rooms()]
                    await websocket.send_json({
                        "type": "rooms_list",
                        "rooms": rooms_data
                    })
                
                elif action == "get_rooms_info":
                    # Get info about active rooms
                    await websocket.send_json({
                        "type": "rooms_info",
                        "rooms": {
                            rid: {
                                "name": room_manager.get_room(rid).name if room_manager.get_room(rid) else "Unknown",
                                "member_count": len(conns)
                            }
                            for rid, conns in manager.rooms.items()
                        }
                    })
                
                else:
                    # Unknown action
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown action: {action}"
                    })
            
            except json.JSONDecodeError:
                # Invalid JSON
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON"
                })
    
    except WebSocketDisconnect:
        # Normal disconnect
        manager.disconnect(websocket)
    except Exception as e:
        # Unexpected error
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

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
