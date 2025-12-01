# 🚀 Deployment Guide - Subscription Filters Architecture

## What You're Deploying

**Production-ready, multi-instance chatroom system with Service Bus subscription filters.**

- Each room gets its own Service Bus subscription
- SQL filters route messages at the broker level
- Horizontal scaling works out of the box
- No Redis or external state needed
- $10/month for Service Bus Standard tier

---

## Prerequisites

### ✅ You Already Have

- Azure Service Bus namespace (simple-pubsub-unlr)
- Topic: backend-messages
- Backend App Service (simple-backend-unlr)
- Frontend App Service (simple-frontend-unlr)
- APIM (simple-inrm-gateway)
- GitHub Actions configured

### ⚠️ NEW Requirement

**Service Bus Standard Tier** (not Basic)

**Check current tier:**
```bash
az servicebus namespace show \
  --resource-group uniliver-rg \
  --namespace-name simple-pubsub-unlr \
  --query sku.name -o tsv
```

**If Basic, upgrade to Standard:**
```bash
az servicebus namespace update \
  --resource-group uniliver-rg \
  --name simple-pubsub-unlr \
  --sku Standard
```

**Cost**: ~$10/month (vs $0 for Basic)  
**Why**: Basic tier doesn't support subscription filters or rules

---

## Step 1: Verify RBAC Permissions

Backend needs **Data Owner** role to create/delete subscriptions.

```bash
# Get backend's managed identity
PRINCIPAL_ID=$(az webapp identity show \
  --resource-group uniliver-rg \
  --name simple-backend-unlr \
  --query principalId -o tsv)

echo "Backend Principal ID: $PRINCIPAL_ID"

# Get Service Bus ID
SERVICEBUS_ID=$(az servicebus namespace show \
  --resource-group uniliver-rg \
  --namespace-name simple-pubsub-unlr \
  --query id -o tsv)

echo "Service Bus ID: $SERVICEBUS_ID"

# Assign Data Owner role
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Azure Service Bus Data Owner" \
  --scope $SERVICEBUS_ID

echo "✓ Role assigned"
```

**Verify:**
```bash
az role assignment list \
  --assignee $PRINCIPAL_ID \
  --scope $SERVICEBUS_ID \
  --query "[].roleDefinitionName" -o table
```

Should see: `Azure Service Bus Data Owner`

---

## Step 2: Deploy Backend

```bash
cd backend

# Check what changed
git diff main.py

# Stage and commit
git add main.py
git commit -m "Enable subscription filters architecture - production ready"
git push origin main
```

### Watch Deployment

```bash
# Option 1: GitHub Actions
gh workflow view

# Option 2: Azure Portal
# Navigate to simple-backend-unlr → Deployment Center
```

**Expected**: 2-3 minutes deployment time

---

## Step 3: Verify Deployment

### Check Backend Health

```bash
curl https://simple-inrm-gateway.azure-api.net/health \
  -H "Ocp-Apim-Subscription-Key: ce29f89ec98d420aaf17b2d49dcbef40"

# Expected:
{
  "status": "healthy",
  "connections": 0,
  "rooms": 2,
  "listeners": 2
}
```

**Key**: `listeners` should match `rooms` count!

### Check Logs

```bash
az webapp log tail \
  --resource-group uniliver-rg \
  --name simple-backend-unlr

# Look for:
"SERVICE BUS SUBSCRIPTION FILTERS ARCHITECTURE"
"✓ Admin client initialized"
"Loaded 2 rooms"
"Ensuring subscriptions..."
"✓ Created subscription 'room-abc123' with filter: room_id='...'"
"✓ Verified 2 subscriptions"
"Starting all room listeners..."
"✓ Listening: 'General' (room-...)"
"✓ Listening: 'Welcome' (room-...)"
"✓ Started 2 listeners"
```

### Check Subscriptions Created

```bash
az servicebus topic subscription list \
  --resource-group uniliver-rg \
  --namespace-name simple-pubsub-unlr \
  --topic-name backend-messages \
  --query "[].name" -o table

# Expected:
Name
-----------
room-abc123
room-def456
```

### Check SQL Filters

```bash
# Pick one subscription name from above
az servicebus topic subscription rule show \
  --resource-group uniliver-rg \
  --namespace-name simple-pubsub-unlr \
  --topic-name backend-messages \
  --subscription-name room-abc123 \
  --name RoomFilter \
  --query "filter.sqlExpression" -o tsv

# Expected: room_id = 'full-uuid-here'
```

---

## Step 4: Test

### Test 1: Create Room

```bash
curl -X POST https://simple-inrm-gateway.azure-api.net/rooms \
  -H "Content-Type: application/json" \
  -H "Ocp-Apim-Subscription-Key: ce29f89ec98d420aaf17b2d49dcbef40" \
  -d '{"name":"Test Room","description":"Testing filters","created_by":"deployment-test"}'

# Save the room_id from response
```

**Check subscription created:**
```bash
az servicebus topic subscription list ... | grep room-
# Should see new room-XXXXXXXX subscription
```

### Test 2: Send Message

```bash
# Use room_id from Test 1
curl -X POST https://simple-inrm-gateway.azure-api.net/publish \
  -H "Content-Type: application/json" \
  -H "Ocp-Apim-Subscription-Key: ce29f89ec98d420aaf17b2d49dcbef40" \
  -d '{"room_id":"YOUR_ROOM_ID","content":"Test message","sender":"curl"}'

# Expected: {"status":"success"}
```

**Check logs:**
```bash
az webapp log tail ... | grep "Published:"

# Should see:
"Published: room_id='...' → sub 'room-XXXXXXXX'"
```

### Test 3: Browser Test

1. Open: https://simple-frontend-unlr-g9h4bcgkdtfffxd2.westeurope-01.azurewebsites.net
2. Should see "General" and "Welcome" rooms
3. Click ➕ to create "Test Room"
4. Room should appear
5. Join room, send message
6. ✓ Message should appear

### Test 4: Multi-Browser Isolation

**Browser 1:**
1. Create/join "Room A"
2. Send "Hello from A"

**Browser 2:**
1. Create/join "Room B"
2. Send "Hello from B"

**Expected:**
- Browser 1 sees only "Hello from A"
- Browser 2 sees only "Hello from B"
- ✅ Perfect isolation via SQL filters

---

## Step 5: Scale Test (Optional)

```bash
# Scale to 2 instances
az webapp scale \
  --resource-group uniliver-rg \
  --name simple-backend-unlr \
  --number-of-workers 2

# Wait 2 minutes for scale

# Send messages
for i in {1..10}; do
  curl -X POST .../publish \
    -d '{"room_id":"YOUR_ROOM_ID","content":"Message '$i'"}'
done

# Check logs - both instances will show processing
az webapp log tail ... | grep "Published:"

# Should see logs from both instances!
```

---

## Troubleshooting

### Issue: Subscription not created

**Symptoms:**
- Room created but not in subscription list
- No messages received

**Fix:**
```bash
# Verify RBAC role
az role assignment list --assignee $PRINCIPAL_ID

# Should see: Azure Service Bus Data Owner

# If missing, add:
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Azure Service Bus Data Owner" \
  --scope $SERVICEBUS_ID

# Restart backend
az webapp restart --name simple-backend-unlr --resource-group uniliver-rg
```

### Issue: Messages not filtering

**Symptoms:**
- All rooms receive all messages

**Check:**
```bash
# Verify filter exists
az servicebus topic subscription rule show ...

# Should see: sqlFilter with room_id = '...'
```

**Fix:**
- Verify `application_properties` set in publish
- Check backend logs for "Published: room_id='...'"
- If filter missing, delete and recreate room

### Issue: Listener not starting

**Symptoms:**
- Subscription exists but messages accumulate
- Health shows `listeners < rooms`

**Check logs:**
```bash
az webapp log tail ... | grep "Listening:"
```

**Fix:**
```bash
# Restart backend
az webapp restart --name simple-backend-unlr --resource-group uniliver-rg

# Check logs again
az webapp log tail ... | grep "Started.*listeners"
```

### Issue: Tier not Standard

**Symptoms:**
- Error: "Subscription filters not supported"

**Fix:**
```bash
az servicebus namespace update \
  --resource-group uniliver-rg \
  --name simple-pubsub-unlr \
  --sku Standard
```

---

## Rollback Plan

If issues occur:

```bash
cd backend
git log --oneline

# Find previous commit
git checkout HEAD~1 main.py
git commit -m "Rollback to in-memory architecture"
git push

# Cleanup subscriptions (optional)
az servicebus topic subscription delete \
  --resource-group uniliver-rg \
  --namespace-name simple-pubsub-unlr \
  --topic-name backend-messages \
  --name room-XXXXXXXX
```

---

## Post-Deployment Checklist

- [ ] Service Bus upgraded to Standard tier
- [ ] Backend has Data Owner RBAC role
- [ ] Backend deployed successfully
- [ ] Health endpoint shows `listeners` = `rooms`
- [ ] Backend logs show subscriptions created
- [ ] Subscriptions visible in Azure Portal
- [ ] SQL filters verified
- [ ] Test room created successfully
- [ ] Messages routing correctly
- [ ] Browser test passed
- [ ] Multi-browser isolation verified
- [ ] (Optional) Multi-instance test passed

---

## Monitoring

### Daily

```bash
# Check health
curl https://.../health

# Should see: "status": "healthy", "listeners": X
```

### Weekly

```bash
# List subscriptions
az servicebus topic subscription list ...

# Count should match rooms count
```

### Alerts (Recommended)

```bash
# Create alert for unhealthy backend
az monitor metrics alert create \
  --name "Backend Unhealthy" \
  --resource-group uniliver-rg \
  --scopes /subscriptions/.../simple-backend-unlr \
  --condition "avg Http5xx > 10" \
  --description "Backend returning 5xx errors"
```

---

## Success Criteria

✅ Health endpoint returns healthy  
✅ Listeners count = Rooms count  
✅ Subscriptions created in Service Bus  
✅ SQL filters applied correctly  
✅ Messages route to correct rooms only  
✅ Multi-browser isolation works  
✅ Backend logs show no errors  
✅ Frontend works normally  

**Congratulations!** Your chatroom system is now production-ready with multi-instance support! 🎉

---

## Next Steps

1. **Monitor for 24 hours** - Check logs for issues
2. **Load test** - Use tools like `wrk` or `k6`
3. **Scale** - Add more instances as needed
4. **Enhance** - Add authentication, analytics, etc.

---

## Support

**Issues**: Check backend logs first  
**Questions**: See SUBSCRIPTION_FILTERS_ARCHITECTURE.md  
**Scaling**: See README.md for scaling strategies
