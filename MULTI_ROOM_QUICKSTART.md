# Quick Start: Multi-Room Chatrooms

Get multi-room chatrooms running in 5 minutes!

## Option 1: Use New Files (Recommended)

### Backend
```bash
# Replace main.py with room-enabled version
cd backend
mv main.py main_single_room_backup.py
cp main_with_rooms.py main.py

# Push to trigger deployment
git add main.py
git commit -m "Enable multi-room support"
git push
```

### Frontend
```bash
# Replace App.js and CSS with room-enabled versions
cd frontend/src
mv App.js App_single_room_backup.js
mv App.css App_single_room_backup.css
cp App_with_rooms.js App.js
cp App_with_rooms.css App.css

# Push to trigger deployment
git add App.js App.css
git commit -m "Add multi-room UI"
git push
```

**Done!** Wait 2-3 minutes for GitHub Actions to deploy.

---

## Option 2: Manual Testing (Local)

### Test Backend Locally
```bash
cd backend

# Install dependencies (if needed)
pip install fastapi uvicorn azure-servicebus azure-identity websockets --break-system-packages

# Set environment variables
export AZURE_SERVICEBUS_NAMESPACE_FQDN="simple-pubsub-unlr.servicebus.windows.net"
export AZURE_SERVICEBUS_TOPIC_NAME="backend-messages"
export AZURE_SERVICEBUS_SUBSCRIPTION_NAME="backend-subscription"

# Run with rooms
python main_with_rooms.py
```

### Test Frontend Locally
```bash
cd frontend

# Replace files temporarily
cp src/App_with_rooms.js src/App.js
cp src/App_with_rooms.css src/App.css

# Update URLs in App.js to localhost
# BACKEND_URL = 'http://localhost:8000'
# WS_URL = 'ws://localhost:8000/ws'

# Run
npm start
```

---

## Testing the Feature

### 1. Open the App
Navigate to: https://simple-frontend-unlr-g9h4bcgkdtfffxd2.westeurope-01.azurewebsites.net

### 2. You'll See:
- **Sidebar** with rooms: general, dev, support, sales
- **General room** auto-joined
- **Green checkmark** (✓) on joined rooms

### 3. Try It Out:

**Join multiple rooms:**
1. Click "+" button next to "dev"
2. Click "+" button next to "support"
3. See checkmarks appear

**Send messages:**
1. Select "general" room
2. Type "Hello general!"
3. Press Enter
4. Switch to "dev" - message NOT there ✓

**Test isolation:**
1. Open in another browser/incognito
2. Browser 1: Join "general"
3. Browser 2: Join "dev"
4. Send message from Browser 1 to "general"
5. Browser 2 doesn't see it ✓

**View room info:**
1. Click 🔄 (refresh button)
2. See member counts appear: "general (2)"

---

## Key Features

### Rooms Sidebar
- 💬 **general** - Default room (auto-join)
- 💻 **dev** - Developer discussions
- 🎧 **support** - Customer support
- 💼 **sales** - Sales team

### Actions
- **Click room name** - Switch to that room
- **Click + button** - Join room
- **Click ✓ button** - Leave room
- **Click 🔄** - Refresh member counts

### Message Flow
1. Select room (e.g., "dev")
2. Type message
3. Press "Send to #dev"
4. Only users in "dev" receive it

---

## Verify It Works

### Check Backend Logs
```bash
az webapp log tail --resource-group uniliver-rg --name simple-backend-unlr
```

**Look for:**
```
✓ Listening to Service Bus topic 'backend-messages'
Client joined room 'general'. Room now has 1 members.
Broadcasting to room 'general': 1 clients
```

### Check Browser Console
Press F12 → Console tab

**Look for:**
```
WebSocket connected
WebSocket message received: {"type":"room_joined","room_id":"general"}
```

---

## Architecture

```
User → Frontend
   ↓
   Joins "general" room via WebSocket
   ↓
Backend → Tracks: {general: [WebSocket1, WebSocket2]}
   ↓
User sends message to "general"
   ↓
POST /publish?room_id=general
   ↓
Service Bus Topic (with room_id metadata)
   ↓
Backend receives → Checks room_id
   ↓
Broadcasts ONLY to WebSockets in "general"
   ↓
Users in "general" see message ✓
Users in "dev" do NOT see message ✓
```

---

## API Changes

### New WebSocket Commands

**Join room:**
```json
{
  "action": "join",
  "room_id": "dev"
}
```

**Leave room:**
```json
{
  "action": "leave",
  "room_id": "dev"
}
```

**Get rooms info:**
```json
{
  "action": "get_rooms"
}
```

### New REST Endpoint

**Publish to room:**
```bash
curl -X POST "https://simple-inrm-gateway.azure-api.net/publish?content=Hello&room_id=dev" \
  -H "Ocp-Apim-Subscription-Key: YOUR_KEY"
```

**Publish to all:**
```bash
curl -X POST "https://simple-inrm-gateway.azure-api.net/publish?content=Hello" \
  -H "Ocp-Apim-Subscription-Key: YOUR_KEY"
```

---

## Troubleshooting

### Messages going to all rooms
**Problem**: room_id not being sent  
**Fix**: Check `/publish` URL includes `room_id` parameter

### Can't join rooms
**Problem**: WebSocket not connected  
**Fix**: Check connection status indicator (should be green)

### Room member count not updating
**Problem**: Need to refresh  
**Fix**: Click 🔄 button in sidebar

### Backend restart loses rooms
**Expected**: Room membership is in-memory only  
**Solution**: Users auto-rejoin on reconnect

---

## Adding New Rooms

### Frontend
Edit `App_with_rooms.js`:
```javascript
const [availableRooms, setAvailableRooms] = useState([
  'general', 'dev', 'support', 'sales', 'marketing'  // ← Add here
]);
```

### Backend
No changes needed! Rooms created automatically when first user joins.

---

## Production Considerations

### Current Setup ✅
- Works great for single backend instance
- No additional Azure costs
- Unlimited rooms
- Easy to maintain

### For Multiple Backend Instances 🔄
Need shared state (Redis):
```python
# Install Redis
pip install redis

# Update ConnectionManager to use Redis
self.redis = redis.Redis(host='...')
```

### For Very Large Scale 🔄
Consider Azure SignalR Service:
- Built-in room support
- Auto-scaling
- ~$50/month for 1000 concurrent users

---

## What's Different?

### Before (Single Room)
```
All users → All messages
```

### After (Multi Room)
```
Users in "general" → Only "general" messages
Users in "dev" → Only "dev" messages
```

**Privacy ✓ Efficiency ✓ Scalability ✓**

---

## Next Steps

1. **Deploy** (5 minutes)
2. **Test** (2 minutes)
3. **Use** (Forever!)

Optional enhancements:
- Add authentication
- Add user presence
- Add typing indicators
- Persist chat history

---

## Support

**Documentation**: See `MULTI_ROOM_IMPLEMENTATION.md` for complete details

**Issues**: Check backend logs and browser console

**Questions**: Review the FAQ in main documentation

---

## Success Checklist

- ✅ Deployed new backend code
- ✅ Deployed new frontend code
- ✅ Can join multiple rooms
- ✅ Messages stay in their rooms
- ✅ Multiple users can chat in same room
- ✅ Multiple users in different rooms don't interfere

**All checked? You're done! 🎉**
