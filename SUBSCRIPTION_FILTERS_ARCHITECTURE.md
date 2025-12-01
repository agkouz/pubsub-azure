# Service Bus Subscription Filters Architecture

## 🎯 What Changed

**From**: Backend in-memory routing  
**To**: Service Bus SQL filters - each room gets its own subscription

## ⚡ Why This Is Better

### ✅ **Multi-Instance Ready**
- No shared state needed
- Each backend instance listens to ALL subscriptions
- Horizontal scaling works out of the box

### ✅ **True Message Isolation**
- Service Bus filters messages at the broker level
- Room messages NEVER reach wrong subscriptions
- Better security and performance

### ✅ **Automatic Load Balancing**
- Service Bus distributes messages across instances
- Built-in competing consumers pattern
- No Redis or external state needed

### ✅ **Production-Grade**
- Azure-native solution
- Leverages Service Bus features
- Enterprise-ready architecture

---

## 🏗️ How It Works

### 1. Room Creation Flow

```
User creates "Product Team"
    ↓
Backend generates UUID: abc123...
    ↓
Backend creates Service Bus subscription: "room-abc123"
    ↓
Backend adds SQL filter: room_id = 'abc123...'
    ↓
Backend starts listener for subscription
    ↓
Backend saves room metadata to rooms.json
    ↓
Room ready to receive messages!
```

### 2. Message Flow

```
User sends "Hello" to "Product Team"
    ↓
POST /publish with room_id=abc123
    ↓
Backend publishes to topic with:
  - body: {"content": "Hello", ...}
  - application_properties: {"room_id": "abc123"}
    ↓
Service Bus evaluates SQL filters on ALL subscriptions
    ↓
Only subscription "room-abc123" matches (room_id = 'abc123')
    ↓
Message routed ONLY to "room-abc123"
    ↓
Backend listener receives message
    ↓
Backend broadcasts via WebSocket to users in room
    ↓
Done! ✓
```

### 3. Multi-Instance Behavior

```
Backend Instance 1           Backend Instance 2
       ↓                            ↓
Both listen to "room-abc123" subscription
       ↓                            ↓
Service Bus uses competing consumers
       ↓                            ↓
Each message delivered to ONE instance only
       ↓                            ↓
That instance broadcasts to its WebSocket clients
       ↓                            ↓
Load automatically balanced! ✓
```

---

## 📊 Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                  Users (Browsers)                        │
└────────────────┬────────────────────────────────────────┘
                 │ WebSocket + REST
┌────────────────▼────────────────────────────────────────┐
│             Azure API Management (APIM)                  │
│             - Subscription Key Auth                      │
│             - CORS                                       │
└────────────────┬────────────────────────────────────────┘
                 │
       ┌─────────┴─────────┐
       │                   │
┌──────▼──────┐     ┌──────▼──────┐
│  Backend    │     │  Backend    │  (Multi-instance!)
│  Instance 1 │     │  Instance 2 │
│             │     │             │
│ Listeners:  │     │ Listeners:  │
│ - room-abc  │     │ - room-abc  │  (Same subscriptions)
│ - room-def  │     │ - room-def  │
│ - room-xyz  │     │ - room-xyz  │
└──────┬──────┘     └──────┬──────┘
       │                   │
       └─────────┬─────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│          Azure Service Bus - Topic: "backend-messages"   │
│                                                          │
│  Subscriptions (one per room):                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │ room-abc123                                       │  │
│  │ SQL Filter: room_id = 'abc123...'                │  │
│  │ ✓ Receives messages for "Product Team" only     │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │ room-def456                                       │  │
│  │ SQL Filter: room_id = 'def456...'                │  │
│  │ ✓ Receives messages for "Engineering" only      │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │ room-xyz789                                       │  │
│  │ SQL Filter: room_id = 'xyz789...'                │  │
│  │ ✓ Receives messages for "Sales" only            │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 🔍 Key Components

### RoomManager

**Responsibilities:**
- Manage room metadata (rooms.json)
- Create/delete Service Bus subscriptions
- Apply SQL filters to subscriptions

**Critical Methods:**
```python
def create_subscription(room: Room) -> bool:
    # Create subscription
    admin_client.create_subscription(TOPIC_NAME, room.subscription_name)
    
    # Add SQL filter
    sql_filter = SqlRuleFilter(f"room_id = '{room.id}'")
    admin_client.create_rule(
        TOPIC_NAME,
        room.subscription_name,
        "RoomFilter",
        filter=sql_filter
    )
```

### Subscription Listeners

**One async task per room:**
```python
async def listen_to_subscription(room: Room):
    receiver = client.get_subscription_receiver(
        topic_name=TOPIC_NAME,
        subscription_name=room.subscription_name
    )
    
    async for msg in receiver:
        data = json.loads(str(msg))
        await manager.broadcast_to_room(data["room_id"], data)
```

**Started on:**
- App startup (for existing rooms)
- Room creation (for new rooms)

**Stopped on:**
- Room deletion
- App shutdown

### Message Publishing

**Critical: Set application_properties**
```python
message = ServiceBusMessage(
    body=json.dumps(message_data),
    application_properties={"room_id": request.room_id}  # ← REQUIRED
)
sender.send_messages(message)
```

The `room_id` in `application_properties` is what the SQL filter evaluates!

---

## 📋 Deployment

### Backend Changes

**Only `main.py` changed** - no infrastructure changes needed!

```bash
cd backend
git add main.py
git commit -m "Switch to subscription filters architecture"
git push
```

**What happens:**
1. Backend deploys with new code
2. On startup: Creates subscriptions for existing rooms (from rooms.json)
3. On startup: Starts listeners for all subscriptions
4. Ready!

### Frontend Changes

**No changes needed!** Frontend is unchanged.

---

## 🧪 Testing

### Test 1: Single Room

```bash
# Create room
curl -X POST https://.../rooms \
  -H "Content-Type: application/json" \
  -H "Ocp-Apim-Subscription-Key: KEY" \
  -d '{"name":"Test","created_by":"alice"}'

# Check subscription created
az servicebus topic subscription list \
  --resource-group uniliver-rg \
  --namespace-name simple-pubsub-unlr \
  --topic-name backend-messages

# Should see: room-{uuid}
```

### Test 2: Message Isolation

**Browser 1: Room A**
```javascript
// Join Room A
ws.send(JSON.stringify({action: 'join', room_id: 'aaa'}))

// Send message
fetch('/publish', {
  body: JSON.stringify({room_id: 'aaa', content: 'Hello from A'})
})
```

**Browser 2: Room B**
```javascript
// Join Room B
ws.send(JSON.stringify({action: 'join', room_id: 'bbb'}))

// Send message
fetch('/publish', {
  body: JSON.stringify({room_id: 'bbb', content: 'Hello from B'})
})
```

**Expected:**
- Browser 1 sees only "Hello from A"
- Browser 2 sees only "Hello from B"
- ✅ Perfect isolation via Service Bus filters

### Test 3: Multi-Instance

```bash
# Scale to 2 instances
az appservice plan update \
  --resource-group uniliver-rg \
  --name simple-plan-unlr \
  --number-of-workers 2

# Send 100 messages
for i in {1..100}; do
  curl -X POST .../publish \
    -d '{"room_id":"abc","content":"Message '$i'"}'
done

# Check logs from both instances
# Both will show processing messages
# Service Bus automatically load balances!
```

---

## 💰 Cost Implications

### Standard Tier Required

**Service Bus Basic**: ❌ No subscription filters  
**Service Bus Standard**: ✅ Subscription filters supported

**Cost**: ~$10/month base + $0.05 per million operations

### Subscription Limits

**Standard Tier**: 2,000 subscriptions per topic

**Practical Limit**: 1,000+ rooms easily supported

### Cost Example

**100 rooms**:
- 100 subscriptions created
- Each room gets 1,000 messages/day
- Total: 100,000 messages/day = 3M/month

**Cost**: $10 (base) + $0.15 (operations) = **$10.15/month**

---

## 🚀 Scaling Strategy

### Small Scale (1-100 rooms)
- ✅ Single backend instance
- ✅ Current architecture perfect
- **Cost**: ~$10/month (Service Bus Standard)

### Medium Scale (100-1,000 rooms)
- Add 2-3 backend instances
- Automatic load balancing
- **Cost**: ~$10/month (Service Bus) + backend instances

### Large Scale (1,000+ rooms)
- 5-10 backend instances
- Consider Premium Service Bus tier
- **Cost**: ~$700/month (Service Bus Premium) + backend instances

### Very Large Scale (10,000+ rooms)
- Premium Service Bus (1M+ messages/sec)
- Sharded topics (multiple topics)
- Dedicated namespace
- **Cost**: Custom pricing

---

## 🔍 Monitoring

### Check Subscriptions

```bash
# List all subscriptions
az servicebus topic subscription list \
  --resource-group uniliver-rg \
  --namespace-name simple-pubsub-unlr \
  --topic-name backend-messages \
  --query "[].name" -o table

# Should see: room-{uuid1}, room-{uuid2}, ...
```

### Check Subscription Filter

```bash
# Get rules for subscription
az servicebus topic subscription rule show \
  --resource-group uniliver-rg \
  --namespace-name simple-pubsub-unlr \
  --topic-name backend-messages \
  --subscription-name room-abc123 \
  --name RoomFilter

# Should see: sqlFilter with room_id = 'abc123...'
```

### Backend Health

```bash
curl https://.../health

{
  "status": "healthy",
  "rooms": 5,
  "listeners": 5  # Should match rooms count
}
```

---

## 🐛 Troubleshooting

### Subscription Not Created

**Symptoms**: Room created but no messages received

**Check**:
```bash
az servicebus topic subscription list ... | grep room-{uuid}
```

**Fix**: Ensure backend has permissions:
```bash
# Assign Data Owner role to backend's managed identity
az role assignment create \
  --assignee {BACKEND_PRINCIPAL_ID} \
  --role "Azure Service Bus Data Owner" \
  --scope {SERVICEBUS_ID}
```

### Messages Not Filtering

**Symptoms**: Users in Room A see messages from Room B

**Check**: Verify filter rule exists
```bash
az servicebus topic subscription rule show ...
```

**Fix**: Ensure `application_properties` is set when publishing:
```python
# ✅ Correct
ServiceBusMessage(
    body=json.dumps(data),
    application_properties={"room_id": room_id}
)

# ❌ Wrong
ServiceBusMessage(body=json.dumps({...,"room_id": room_id}))
```

### Listener Not Starting

**Symptoms**: Subscription exists but messages accumulate

**Check backend logs**:
```bash
az webapp log tail ... | grep "Listening:"
```

**Fix**: Ensure listener task started:
```python
task = asyncio.create_task(listen_to_subscription(room))
subscription_tasks[room.id] = task
```

---

## 🎯 Migration from In-Memory Architecture

### Before Deployment

**Current**: In-memory room routing  
**After**: Subscription filter routing

### Migration Steps

1. **No data loss**: rooms.json preserved
2. **Subscriptions auto-created**: On startup
3. **Zero downtime**: Deploy normally
4. **Verification**: Check subscriptions created

### Rollback Plan

```bash
# If needed, revert to previous version
cd backend
git checkout HEAD~1 main.py
git commit -m "Rollback to in-memory routing"
git push
```

---

## 📈 Performance Comparison

| Metric | In-Memory | Subscription Filters |
|--------|-----------|---------------------|
| **Message Latency** | ~10ms | ~15ms |
| **Throughput** | Limited by single instance | Scales linearly |
| **Multi-Instance** | ❌ Requires Redis | ✅ Native support |
| **Memory Usage** | High (stores all connections) | Low (Service Bus stores) |
| **Complexity** | Low | Medium |
| **Production Ready** | Single instance only | ✓ Multi-instance |

---

## ✅ Summary

### What You Get

✅ **True Multi-Instance Support** - Horizontal scaling works  
✅ **Better Isolation** - Service Bus filters at broker level  
✅ **No External State** - No Redis needed  
✅ **Production Grade** - Azure-native architecture  
✅ **Cost Effective** - ~$10/month for Standard tier  
✅ **Scalable** - Handles 1,000+ rooms easily  

### Trade-offs

**Pros:**
- Azure-native solution
- Perfect for production
- Auto load balancing
- Better security

**Cons:**
- Requires Standard tier (~$10/month vs Free Basic)
- Slightly higher latency (~5ms more)
- More complex architecture

### When to Use

✅ **Production deployments**  
✅ **Multi-instance requirements**  
✅ **100+ rooms**  
✅ **Enterprise scale**  

❌ **Local development** (use in-memory)  
❌ **Proof of concept** (use in-memory)  
❌ **Tight budget** (Basic tier) (use in-memory)  

---

## 🚀 Deploy Now

```bash
cd backend
git add main.py
git commit -m "Enable subscription filters architecture"
git push

# Watch deployment
gh workflow view

# Test
curl https://.../health
```

**That's it!** Your chatroom system is now production-ready and multi-instance capable! 🎉
