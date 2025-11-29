from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from azure.servicebus.aio import ServiceBusClient as AsyncServiceBusClient
import asyncio
import json
import os
from typing import Set
import threading

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

print("========================== VARIABLES ==========================")
print(f"Connection String: {'*' * 20 if CONNECTION_STRING else 'NOT SET'}")
print(f"Topic Name: {TOPIC_NAME}")
print(f"Subscription Name: {SUBSCRIPTION_NAME}")
print("==============================================================")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f"Client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        print(f"Client disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Error sending to client: {e}")
                disconnected.add(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

# Background task to listen to Service Bus messages
async def listen_to_service_bus():
    """Listen to Service Bus topic and broadcast to WebSocket clients"""
    if not CONNECTION_STRING:
        print("Service Bus connection string not configured. Skipping listener.")
        return
    
    print("Starting Service Bus listener...")
    
    try:
        async with AsyncServiceBusClient.from_connection_string(CONNECTION_STRING) as client:
            receiver = client.get_subscription_receiver(
                topic_name=TOPIC_NAME,
                subscription_name=SUBSCRIPTION_NAME,
                max_wait_time=5
            )
            
            async with receiver:
                print(f"Listening to Service Bus topic '{TOPIC_NAME}', subscription '{SUBSCRIPTION_NAME}'")
                while True:
                    try:
                        messages = await receiver.receive_messages(max_message_count=10, max_wait_time=5)
                        for msg in messages:
                            try:
                                message_body = str(msg)
                                print(f"Received from Service Bus: {message_body}")
                                
                                # Parse message
                                try:
                                    data = json.loads(message_body)
                                except:
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
                            except Exception as e:
                                print(f"Error processing message: {e}")
                                await receiver.abandon_message(msg)
                    except Exception as e:
                        print(f"Error receiving messages: {e}")
                        await asyncio.sleep(1)
    except Exception as e:
        print(f"Service Bus listener error: {e}")

@app.on_event("startup")
async def startup_event():
    """Start background tasks on application startup"""
    if CONNECTION_STRING:
        # Start Service Bus listener in background
        asyncio.create_task(listen_to_service_bus())
        print("Service Bus listener task started")
    else:
        print("Warning: Service Bus connection string not configured")

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
    if not CONNECTION_STRING:
        return {"error": "Azure Service Bus connection string not configured"}
    
    try:
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
                print(f"Message sent to Service Bus: {message}")
        
        # Also send immediate response to WebSocket clients
        response_message = {
            "type": "publish_confirmation",
            "data": f"Message published to Service Bus: {message.get('content', 'N/A')}",
            "timestamp": message.get('timestamp', '')
        }
        await manager.broadcast(response_message)
        
        return {"status": "success", "message": "Message published to Service Bus"}
    except Exception as e:
        print(f"Error publishing message: {e}")
        return {"error": str(e)}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication"""
    await manager.connect(websocket)
    try:
        while True:
            # Keep the connection alive and listen for messages from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Echo back or process the message
            response = {
                "type": "echo",
                "data": f"Server received: {message.get('content', 'N/A')}",
                "timestamp": message.get('timestamp', '')
            }
            await manager.broadcast(response)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("Client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
