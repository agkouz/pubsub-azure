# Azure Dynamic Chatrooms - Setup Guide

## Overview

This application supports two pub/sub backends:
- **Redis** (recommended for local development)
- **Azure Service Bus** (recommended for production)

Both use the same WebSocket-based architecture with backend routing for cost optimization.

---

## Option 1: Run with Redis (Local Development)

### Prerequisites
- Docker installed
- Python 3.9+
- Node.js 16+ (for frontend)

### Step 1: Start Redis

Run Redis in Docker:

```bash
docker run -d --name redis -p 6379:6379 redis:latest
```

Verify Redis is running:

```bash
docker ps
# You should see redis container running on port 6379
```

### Step 2: Configure Backend

Create `.env` file in the `backend/` directory:

```bash
cd backend
```

Create `backend/.env`:

```dotenv
PUB_SUB_SERVICE="redis"
```

### Step 3: Install Dependencies

```bash
# In backend/ directory
pip install -r requirements.txt
```

### Step 4: Run Backend

```bash
# In backend/ directory
python main.py
```

You should see:
```
🚀 Application starting - Dynamic Chatrooms enabled
✓ Connected to Redis at localhost:6379
✓ Subscribed to Redis pattern 'room:*'
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 5: Run Frontend

```bash
# In frontend/ directory
npm install
npm run dev
```

Open http://localhost:5173

---

## Option 2: Run with Azure Service Bus (Production)

### Prerequisites
- Azure subscription
- Azure Service Bus namespace created
- Python 3.9+
- Node.js 16+ (for frontend)

### Step 1: Create Azure Resources

1. **Create Service Bus Namespace:**
   ```bash
   az servicebus namespace create \
     --resource-group <your-rg> \
     --name <your-namespace> \
     --location eastus \
     --sku Standard
   ```

2. **Create Topic:**
   ```bash
   az servicebus topic create \
     --resource-group <your-rg> \
     --namespace-name <your-namespace> \
     --name chatrooms
   ```

3. **Create Subscription:**
   ```bash
   az servicebus topic subscription create \
     --resource-group <your-rg> \
     --namespace-name <your-namespace> \
     --topic-name chatrooms \
     --name chatrooms-subscription
   ```

4. **Get Connection String:**
   ```bash
   az servicebus namespace authorization-rule keys list \
     --resource-group <your-rg> \
     --namespace-name <your-namespace> \
     --name RootManageSharedAccessKey \
     --query primaryConnectionString -o tsv
   ```

### Step 2: Configure Backend

Create `backend/.env`:

```dotenv
PUB_SUB_SERVICE="service_bus"
ENABLE_SERVICE_BUS=true
AZURE_SERVICEBUS_CONNECTION_STRING="Endpoint=sb://..."
TOPIC_NAME="chatrooms"
SUBSCRIPTION_NAME="chatrooms-subscription"
USE_AZURE_AD=false
```

**Alternative: Use Azure AD (Recommended for Production)**

```dotenv
PUB_SUB_SERVICE="service_bus"
ENABLE_SERVICE_BUS=true
AZURE_SERVICEBUS_NAMESPACE_FQDN="<your-namespace>.servicebus.windows.net"
TOPIC_NAME="chatrooms"
SUBSCRIPTION_NAME="chatrooms-subscription"
USE_AZURE_AD=true
```

### Step 3: Install Dependencies

```bash
# In backend/ directory
pip install -r requirements.txt
```

### Step 4: Run Backend

```bash
# In backend/ directory
python main.py
```

You should see:
```
🚀 Application starting - Dynamic Chatrooms enabled
✓ Connected to Service Bus at <your-namespace>.servicebus.windows.net
✓ Subscribed to Service Bus topic 'chatrooms', subscription 'chatrooms-subscription'
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 5: Run Frontend

```bash
# In frontend/ directory
npm install
npm run dev
```

Open http://localhost:5173

---

## Testing the Application

### 1. Create a Room

```bash
curl -X POST http://localhost:8000/rooms \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Room"}'
```

Response:
```json
{
  "id": "uuid-here",
  "name": "Test Room",
  "created_at": "2025-12-05T10:00:00Z"
}
```

### 2. Connect WebSocket

Open your browser console and test:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/uuid-here?user_id=user1');

ws.onopen = () => {
  console.log('Connected');
  
  // Send a message
  ws.send(JSON.stringify({
    action: 'message_publish',
    data: {
      room_id: 'uuid-here',
      content: 'Hello world!',
      sender: 'user1'
    }
  }));
};

ws.onmessage = (event) => {
  console.log('Received:', JSON.parse(event.data));
};
```

### 3. Monitor Metrics

```bash
curl http://localhost:8000/metrics
```

Response:
```json
{
  "total_messages": 42,
  "active_connections": 5,
  "active_rooms": 3,
  "pub_sub_service": "redis"
}
```

---

## Switching Between Redis and Service Bus

Simply change the `PUB_SUB_SERVICE` value in `backend/.env`:

**For Redis:**
```dotenv
PUB_SUB_SERVICE="redis"
```

**For Service Bus:**
```dotenv
PUB_SUB_SERVICE="service_bus"
ENABLE_SERVICE_BUS=true
AZURE_SERVICEBUS_CONNECTION_STRING="..."
```

Restart the backend server - no code changes needed!

---

## Troubleshooting

### Redis Connection Failed

```bash
# Check if Redis is running
docker ps | grep redis

# Check Redis logs
docker logs redis

# Restart Redis
docker restart redis
```

### Service Bus Connection Failed

```bash
# Test connection string
az servicebus namespace show \
  --resource-group <your-rg> \
  --name <your-namespace>

# Check topic exists
az servicebus topic show \
  --resource-group <your-rg> \
  --namespace-name <your-namespace> \
  --name chatrooms
```

### WebSocket Connection Refused

- Check backend is running: `curl http://localhost:8000/health`
- Check CORS settings in `backend/main.py`
- Verify room_id is valid: `curl http://localhost:8000/rooms`

---

## Architecture Comparison

### Redis Architecture
```
Client → WebSocket → Backend → Redis Pub/Sub → Backend → WebSocket → Clients
         (room:*)                 (pattern matching)
```

**Pros:**
- Simple setup
- Fast (in-memory)
- Great for development
- Predictable costs ($46/month for 100K users)

**Cons:**
- Single point of failure (needs Redis Cluster for HA)
- Memory-bound

### Service Bus Architecture
```
Client → WebSocket → Backend → Service Bus Topic → Backend → WebSocket → Clients
         (single sub)              (body routing)
```

**Pros:**
- Azure-native
- High durability
- Built-in retry/dead-letter
- Auto-scaling

**Cons:**
- Higher cost at small scale
- Network latency

---

## Cost Analysis

| Users    | Redis          | Service Bus    | Recommendation |
|----------|----------------|----------------|----------------|
| 0-10K    | $0 (local)     | $0 (free tier) | Either         |
| 10K-100K | $46/month      | $50-100/month  | Redis          |
| 100K+    | $46-200/month  | $100-500/month | Service Bus    |

See `COST_ANALYSIS.md` for detailed breakdown.

---

## Next Steps

- **Production deployment**: See `DEPLOYMENT_READY.md`
- **Cost optimization**: See `COST_ANALYSIS.md`
- **API reference**: See `API_DOCUMENTATION.md`
- **Architecture deep-dive**: See `DYNAMIC_CHATROOMS_GUIDE.md`

---

## Quick Commands Reference

```bash
# Start Redis
docker run -d --name redis -p 6379:6379 redis:latest

# Stop Redis
docker stop redis

# Remove Redis
docker rm redis

# Backend
cd backend
python main.py

# Frontend
cd frontend
npm run dev

# Health check
curl http://localhost:8000/health

# Metrics
curl http://localhost:8000/metrics

# List rooms
curl http://localhost:8000/rooms
```

---

**Questions?** Check the troubleshooting section or raise an issue on GitHub.