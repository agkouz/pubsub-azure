# Azure Service Bus Setup Guide

This project uses **Azure Service Bus** (the Azure equivalent of Google Cloud Pub/Sub) for message publishing and subscription.

## Architecture

1. **Frontend** → Publishes message to Service Bus Topic (via backend API)
2. **Service Bus Topic** → Receives and distributes messages
3. **Service Bus Subscription** → Backend subscribes to receive messages
4. **Backend** → Receives messages and broadcasts to WebSocket clients
5. **WebSocket** → Sends real-time updates to frontend

## Prerequisites

You already have an Azure Service Bus namespace: `simple-pubsub-unlr`

## Step 1: Create Topic and Subscription

### Via Azure Portal

1. Go to **Service Bus** → **simple-pubsub-unlr**
2. Click **Topics** → **+ Topic**
3. Create topic:
   - **Name**: `messages`
   - Click **Create**
4. Click on the `messages` topic
5. Click **+ Subscription**
6. Create subscription:
   - **Name**: `backend-subscription`
   - **Max delivery count**: 10
   - Click **Create**

### Via Azure CLI

```bash
# Create topic
az servicebus topic create \
  --resource-group uniliver-rg \
  --namespace-name simple-pubsub-unlr \
  --name messages

# Create subscription
az servicebus topic subscription create \
  --resource-group uniliver-rg \
  --namespace-name simple-pubsub-unlr \
  --topic-name messages \
  --name backend-subscription
```

## Step 2: Configure Backend App Service

Set the environment variables in your backend App Service:

```bash
az webapp config appsettings set \
  --resource-group uniliver-rg \
  --name simple-backend-unlr-bse7b2cudad6h7gs \
  --settings \
    AZURE_SERVICEBUS_CONNECTION_STRING="Endpoint=sb://simple-pubsub-unlr.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=rdOcdkRg7qToYdk61zqP3hIeiB8MY9TMd+ASbNlbDiY=" \
    AZURE_SERVICEBUS_TOPIC_NAME="messages" \
    AZURE_SERVICEBUS_SUBSCRIPTION_NAME="backend-subscription"
```

## Step 3: Restart Backend

```bash
az webapp restart \
  --resource-group uniliver-rg \
  --name simple-backend-unlr-bse7b2cudad6h7gs
```

## How It Works

### 1. Frontend Publishes Message

```javascript
// Frontend sends HTTP POST to backend
fetch('https://simple-inrm-gateway.azure-api.net/publish', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Ocp-Apim-Subscription-Key': 'your-key'
  },
  body: JSON.stringify({
    content: 'Hello World',
    timestamp: new Date().toISOString()
  })
});
```

### 2. Backend Publishes to Service Bus Topic

```python
# Backend receives HTTP request and publishes to Service Bus
service_bus_message = ServiceBusMessage(json.dumps(message))
sender.send_messages(service_bus_message)
```

### 3. Backend Receives from Subscription

```python
# Background task continuously listens to subscription
receiver = client.get_subscription_receiver(
    topic_name=TOPIC_NAME,
    subscription_name=SUBSCRIPTION_NAME
)
messages = await receiver.receive_messages()
```

### 4. Backend Broadcasts to WebSocket

```python
# When message is received from Service Bus, broadcast to all WebSocket clients
await manager.broadcast({
    "type": "service_bus_message",
    "data": message_content
})
```

### 5. Frontend Receives via WebSocket

```javascript
// Frontend WebSocket receives the message
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};
```

## Testing

### 1. Test Backend Health

```bash
curl https://simple-backend-unlr-bse7b2cudad6h7gs.westeurope-01.azurewebsites.net/health
```

Expected:
```json
{
  "status": "healthy",
  "service_bus_configured": true,
  "active_websocket_connections": 0
}
```

### 2. Test Publishing

```bash
curl -X POST https://simple-inrm-gateway.azure-api.net/publish \
  -H "Content-Type: application/json" \
  -H "Ocp-Apim-Subscription-Key: your-key" \
  -d '{
    "content": "Test message",
    "timestamp": "2025-11-28T12:00:00Z",
    "sender": "Test"
  }'
```

Expected:
```json
{
  "status": "success",
  "message": "Message published to Service Bus"
}
```

### 3. Test Full Flow

1. Open frontend in browser
2. Connect to WebSocket (should see "Connected")
3. Type a message and click "Publish"
4. You should see:
   - "Message published to Service Bus" (immediate confirmation)
   - "Message from Service Bus: ..." (received from subscription)

## Troubleshooting

### "Connection string not configured"

Check environment variables are set:
```bash
az webapp config appsettings list \
  --resource-group uniliver-rg \
  --name simple-backend-unlr-bse7b2cudad6h7gs \
  --query "[?name=='AZURE_SERVICEBUS_CONNECTION_STRING']"
```

### "Topic does not exist"

Create the topic:
```bash
az servicebus topic create \
  --resource-group uniliver-rg \
  --namespace-name simple-pubsub-unlr \
  --name messages
```

### "Subscription does not exist"

Create the subscription:
```bash
az servicebus topic subscription create \
  --resource-group uniliver-rg \
  --namespace-name simple-pubsub-unlr \
  --topic-name messages \
  --name backend-subscription
```

### Backend not receiving messages

Check application logs:
```bash
az webapp log tail \
  --resource-group uniliver-rg \
  --name simple-backend-unlr-bse7b2cudad6h7gs
```

Look for:
- "Starting Service Bus listener..."
- "Listening to Service Bus topic..."
- "Received from Service Bus: ..."

### WebSocket not receiving messages

1. Check WebSocket is connected in frontend
2. Check backend logs show messages being received from Service Bus
3. Verify broadcast is working (check console logs)

## Service Bus Concepts

**Topic**: Like a Pub/Sub topic - receives messages and distributes to subscriptions
**Subscription**: Like a Pub/Sub subscription - receives copies of messages from topic
**Message**: JSON payload sent through the topic

## Architecture Diagram

```
┌──────────┐     HTTP POST      ┌──────────┐
│ Frontend │ ───────────────────>│  Backend │
│  (React) │                     │ (FastAPI)│
└──────────┘                     └────┬─────┘
     │                                │
     │                                │ Publish
     │                                ▼
     │                          ┌──────────┐
     │                          │ Service  │
     │                          │   Bus    │
     │                          │  Topic   │
     │                          └────┬─────┘
     │                               │
     │                               │ Distribute
     │                               ▼
     │                          ┌──────────┐
     │                          │ Service  │
     │                          │   Bus    │
     │        ┌─────────────────│Subscript.│
     │        │ Receive          └──────────┘
     │        │
     │        ▼
     │  ┌──────────┐
     │  │  Backend │
     │  │ Listener │
     │  └────┬─────┘
     │       │
     │       │ Broadcast
     │       ▼
     │  ┌──────────┐
     └──│WebSocket │
        │Connection│
        └──────────┘
```

## Cleanup

To remove resources:

```bash
# Delete subscription
az servicebus topic subscription delete \
  --resource-group uniliver-rg \
  --namespace-name simple-pubsub-unlr \
  --topic-name messages \
  --name backend-subscription

# Delete topic
az servicebus topic delete \
  --resource-group uniliver-rg \
  --namespace-name simple-pubsub-unlr \
  --name messages
```
