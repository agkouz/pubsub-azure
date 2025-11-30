from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from azure.servicebus.aio import ServiceBusClient as AsyncServiceBusClient
import asyncio
import json
import os
from typing import Set
import logging
import traceback
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Azure Service Bus configuration
CONNECTION_STRING = os.getenv("AZURE_SERVICEBUS_CONNECTION_STRING", "")
TOPIC_NAME = os.getenv("AZURE_SERVICEBUS_TOPIC_NAME", "messages")
SUBSCRIPTION_NAME = os.getenv("AZURE_SERVICEBUS_SUBSCRIPTION_NAME", "backend-subscription")

logger.info("=" * 60)
logger.info("AZURE SERVICE BUS CONFIGURATION")
logger.info("=" * 60)
logger.info(f"Connection String Configured: {'YES' if CONNECTION_STRING else 'NO'}")
if CONNECTION_STRING:
    # Log only the endpoint, not the key
    endpoint = CONNECTION_STRING.split(';')[0].replace('Endpoint=', '')
    logger.info(f"Service Bus Endpoint: {endpoint}")
logger.info(f"Topic Name: {TOPIC_NAME}")
logger.info(f"Subscription Name: {SUBSCRIPTION_NAME}")
logger.info("=" * 60)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        disconnected = set()
        logger.debug(f"Broadcasting message to {len(self.active_connections)} clients: {message}")
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to client: {e}")
                disconnected.add(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

# Background task to listen to Service Bus messages
async def listen_to_service_bus():
    """Listen to Service Bus topic and broadcast to WebSocket clients"""
    if not CONNECTION_STRING:
        logger.warning("Service Bus connection string not configured. Skipping listener.")
        return
    
    logger.info("Starting Service Bus listener...")
    
    try:
        async with AsyncServiceBusClient.from_connection_string(CONNECTION_STRING) as client:
            receiver = client.get_subscription_receiver(
                topic_name=TOPIC_NAME,
                subscription_name=SUBSCRIPTION_NAME,
                max_wait_time=5
            )
            
            async with receiver:
                logger.info(f"✓ Listening to Service Bus topic '{TOPIC_NAME}', subscription '{SUBSCRIPTION_NAME}'")
                while True:
                    try:
                        messages = await receiver.receive_messages(max_message_count=10, max_wait_time=5)
                        if messages:
                            logger.info(f"Received {len(messages)} message(s) from Service Bus")
                        
                        for msg in messages:
                            try:
                                message_body = str(msg)
                                logger.info(f"Processing Service Bus message: {message_body[:100]}...")
                                
                                # Parse message
                                try:
                                    data = json.loads(message_body)
                                except Exception as parse_error:
                                    logger.warning(f"Could not parse message as JSON: {parse_error}")
                                    data = {"content": message_body}
                                
                                # Broadcast to WebSocket clients
                                response = {
                                    "type": "service_bus_message",
                                    "data": f"Message from Service Bus: {data.get('content', message_body)}",
                                    "timestamp": data.get('timestamp', ''),
                                    "original": data
                                }
                                await manager.broadcast(response)
                                
                                # Complete the message
                                await receiver.complete_message(msg)
                                logger.info("Message processed and completed successfully")
                            except Exception as e:
                                logger.error(f"Error processing message: {e}")
                                logger.error(traceback.format_exc())
                                await receiver.abandon_message(msg)
                    except Exception as e:
                        logger.error(f"Error receiving messages: {e}")
                        logger.error(traceback.format_exc())
                        await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"Service Bus listener fatal error: {e}")
        logger.error(traceback.format_exc())

@app.on_event("startup")
async def startup_event():
    """Start background tasks on application startup"""
    logger.info("Application startup initiated")
    if CONNECTION_STRING:
        # Start Service Bus listener in background
        asyncio.create_task(listen_to_service_bus())
        logger.info("✓ Service Bus listener task started")
    else:
        logger.warning("⚠ Service Bus connection string not configured - listener not started")

@app.get("/")
async def root():
    return {"message": "Azure Service Bus Backend is running"}

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service_bus_configured": bool(CONNECTION_STRING),
        "active_websocket_connections": len(manager.active_connections)
    }

@app.post("/publish")
async def publish_message(message: dict):
    """Publish a message to Azure Service Bus Topic"""
    logger.info(f"Publish request received: {message}")
    
    if not CONNECTION_STRING:
        logger.error("Publish failed: Azure Service Bus connection string not configured")
        return {"error": "Azure Service Bus connection string not configured"}
    
    try:
        logger.info(f"Publishing to topic '{TOPIC_NAME}'...")
        
        # Send to Service Bus Topic
        with ServiceBusClient.from_connection_string(CONNECTION_STRING) as client:
            sender = client.get_topic_sender(topic_name=TOPIC_NAME)
            with sender:
                # Create message
                service_bus_message = ServiceBusMessage(
                    json.dumps(message),
                    content_type="application/json"
                )
                sender.send_messages(service_bus_message)
                logger.info(f"✓ Message sent to Service Bus successfully: {message.get('content', 'N/A')}")
        
        # Also send immediate response to WebSocket clients
        response_message = {
            "type": "publish_confirmation",
            "data": f"Message published to Service Bus: {message.get('content', 'N/A')}",
            "timestamp": message.get('timestamp', '')
        }
        await manager.broadcast(response_message)
        logger.info("✓ Confirmation broadcast to WebSocket clients")
        
        return {"status": "success", "message": "Message published to Service Bus"}
        
    except Exception as e:
        error_msg = str(e)
        error_trace = traceback.format_exc()
        
        logger.error("=" * 60)
        logger.error("ERROR PUBLISHING TO SERVICE BUS")
        logger.error("=" * 60)
        logger.error(f"Error Type: {type(e).__name__}")
        logger.error(f"Error Message: {error_msg}")
        logger.error(f"Topic Name: {TOPIC_NAME}")
        logger.error(f"Message Content: {message}")
        logger.error("Full Traceback:")
        logger.error(error_trace)
        logger.error("=" * 60)
        
        # Check for common errors
        if "amqp:client-error" in error_msg:
            logger.error("DIAGNOSIS: Topic or subscription may not exist, or authentication issue")
            logger.error(f"ACTION NEEDED: Verify topic '{TOPIC_NAME}' exists in Service Bus namespace")
        elif "Endpoint" in error_msg or "connection" in error_msg.lower():
            logger.error("DIAGNOSIS: Connection string or network issue")
            logger.error("ACTION NEEDED: Verify connection string and network connectivity")
        
        return {"error": error_msg, "details": "Check backend logs for full error trace"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication"""
    await manager.connect(websocket)
    try:
        while True:
            # Keep the connection alive and listen for messages from client
            data = await websocket.receive_text()
            logger.info(f"WebSocket message received: {data[:100]}...")
            message = json.loads(data)
            
            # Echo back or process the message
            response = {
                "type": "echo",
                "data": f"Server received: {message.get('content', 'N/A')}",
                "timestamp": message.get('timestamp', '')
            }
            await manager.broadcast(response)
            logger.debug(f"Echo response sent")
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket client disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        logger.error(traceback.format_exc())
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
