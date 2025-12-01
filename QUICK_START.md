# Subscription Filters Architecture - Deployment

## Files Changed

**Only 1 file**: `backend/main.py`

No duplicate files. No `_with_rooms` files. Just clean production code.

---

## Why rooms.json?

**Problem**: Backend restarts but Service Bus subscriptions persist

```
Without rooms.json:
Backend restarts → Forgets all rooms → Can't create listeners → 
Subscriptions accumulate messages → Users can't receive

With rooms.json:
Backend restarts → Reads rooms.json → Knows all rooms → 
Recreates listeners → Everything works
```

**What's stored**:
```json
{
  "abc123-uuid": {
    "id": "abc123-uuid",
    "name": "Product Team",
    "subscription_name": "room-abc123",
    "created_by": "alice",
    "created_at": "2025-12-01T10:00:00Z"
  }
}
```

**Alternative**: Query Service Bus API for all subscriptions on startup (slower, more code)

---

## Deploy

```bash
# 1. Upgrade Service Bus to Standard (required for SQL filters)
az servicebus namespace update \
  --resource-group uniliver-rg \
  --name simple-pubsub-unlr \
  --sku Standard

# 2. Verify backend has Data Owner role
az role assignment create \
  --assignee $(az webapp identity show --name simple-backend-unlr --query principalId -o tsv) \
  --role "Azure Service Bus Data Owner" \
  --scope $(az servicebus namespace show --name simple-pubsub-unlr --query id -o tsv)

# 3. Deploy
cd backend
git add main.py
git commit -m "Production: subscription filters"
git push
```

---

## Verify

```bash
# Check health
curl https://simple-inrm-gateway.azure-api.net/health \
  -H "Ocp-Apim-Subscription-Key: ce29f89ec98d420aaf17b2d49dcbef40"

# Should show: "listeners": 2 (matches "rooms": 2)

# Check subscriptions created
az servicebus topic subscription list \
  --resource-group uniliver-rg \
  --namespace-name simple-pubsub-unlr \
  --topic-name backend-messages

# Should see: room-abc123, room-def456
```

---

## Code Structure

All in `main.py`:

```python
# 1. RoomManager
# - Loads/saves rooms.json
# - Creates/deletes Service Bus subscriptions
# - Applies SQL filters: room_id = 'uuid'

# 2. ConnectionManager  
# - Tracks WebSocket connections
# - Routes messages to correct users

# 3. listen_to_subscription()
# - One async task per room
# - Listens to subscription
# - Broadcasts to WebSockets

# 4. REST API
# - POST /rooms → Create room + subscription + listener
# - DELETE /rooms/{id} → Delete all of above
# - POST /publish → Publish with application_properties
```

---

## Key Implementation Details

### SQL Filter
```python
# Create subscription with filter
sql_filter = SqlRuleFilter(f"room_id = '{room.id}'")
admin_client.create_rule(TOPIC_NAME, sub_name, "RoomFilter", filter=sql_filter)
```

### Publishing (CRITICAL)
```python
# MUST set application_properties - that's what filter checks!
message = ServiceBusMessage(
    body=json.dumps(data),
    application_properties={"room_id": room_id}  # ← Filter checks this
)
```

### Listener
```python
# One per room
async def listen_to_subscription(room: Room):
    receiver = client.get_subscription_receiver(
        topic_name=TOPIC_NAME,
        subscription_name=room.subscription_name  # Each room has own subscription
    )
    async for msg in receiver:
        await manager.broadcast_to_room(room.id, msg)
```

---

## Cost

**Subscriptions**: FREE  
**Standard Tier**: $9.81/month  
**Operations**: $0.05 per million (after 12.5M included)

**100 rooms with 1,000 messages/room/day**: ~$10/month total

---

## Documentation

- **README.md** - Overview and quick reference
- **SUBSCRIPTION_FILTERS_ARCHITECTURE.md** - Deep dive
- **DEPLOYMENT_GUIDE.md** - Step-by-step deployment

All code fully commented with docstrings explaining why things are done.

---

## Summary

✅ **1 file changed** (main.py)  
✅ **rooms.json** for persistence across restarts  
✅ **Fully commented** code with docstrings  
✅ **Multi-instance ready** (competing consumers)  
✅ **Production grade** (Service Bus filters)  
✅ **$10/month** (Standard tier)  

**Just upgrade tier, verify RBAC, and push!**
