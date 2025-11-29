# WebSocket Connection Troubleshooting Guide

This guide helps diagnose and fix WebSocket connection issues through Azure API Management.

## Common Error: "WebSocket connection failed"

### Quick Diagnosis Checklist

- [ ] APIM tier supports WebSocket (not Consumption tier)
- [ ] WebSocket protocol enabled in APIM API settings
- [ ] `/ws` operation exists in APIM
- [ ] Backend App Service has WebSockets enabled
- [ ] Backend is running and accessible
- [ ] APIM policy configured correctly

## Step-by-Step Troubleshooting

### 1. Check APIM Tier

WebSocket is NOT supported on **Consumption** tier. Check your tier:

```bash
az apim show --name simple-inrm-gateway --resource-group <rg> --query sku.name
```

**Required tiers:** Developer, Basic, Standard, or Premium

**If you're on Consumption tier:**
- Option A: Upgrade APIM tier
- Option B: Use direct backend connection (see workaround below)

### 2. Enable WebSocket in APIM

#### Via Azure Portal:

1. Go to **API Management** → **APIs**
2. Select your API (or create one)
3. Click **Settings** tab
4. **Protocols**: Check both `HTTPS` and `WebSocket (WSS)`
5. Save

#### Via Azure CLI:

```bash
az apim api update \
  --resource-group <rg> \
  --service-name simple-inrm-gateway \
  --api-id <api-id> \
  --protocols https,wss
```

### 3. Create WebSocket Operation

In APIM → APIs → Your API → **Design**:

1. Click **+ Add operation**
2. **Display name**: WebSocket
3. **URL**: `GET /ws`
4. Save

### 4. Configure Policy

Click on the `/ws` operation → **Policy code editor** (</> icon):

```xml
<policies>
    <inbound>
        <base />
        <!-- Point to your backend App Service -->
        <set-backend-service base-url="https://your-backend.azurewebsites.net" />
        
        <!-- Optional: Remove subscription key requirement for WebSocket -->
        <choose>
            <when condition="@(context.Request.Url.Path.Contains("/ws"))">
                <authentication-managed-identity resource="https://management.azure.com/" />
            </when>
        </choose>
    </inbound>
    <backend>
        <base />
    </backend>
    <outbound>
        <base />
    </outbound>
    <on-error>
        <base />
    </on-error>
</policies>
```

### 5. Enable WebSockets in Backend App Service

#### Via Azure Portal:

1. Go to your **Backend App Service**
2. **Configuration** → **General settings**
3. **Web sockets**: **On**
4. Save and restart

#### Via Azure CLI:

```bash
az webapp config set \
  --name <backend-app-name> \
  --resource-group <rg> \
  --web-sockets-enabled true
```

### 6. Test Backend Directly

Test if your backend WebSocket works without APIM:

```javascript
// In browser console
const ws = new WebSocket('wss://your-backend.azurewebsites.net/ws');
ws.onopen = () => console.log('Connected!');
ws.onerror = (e) => console.error('Error:', e);
ws.onmessage = (e) => console.log('Message:', e.data);
```

If this works, the issue is with APIM configuration.

### 7. Check Subscription Key Requirement

If APIM requires subscription keys, WebSocket might fail. Options:

**Option A: Disable subscription key for WebSocket**

Add to your `/ws` operation policy:

```xml
<inbound>
    <base />
    <choose>
        <when condition="@(context.Request.Url.Path.Contains("/ws"))">
            <!-- Skip subscription validation for WebSocket -->
        </when>
        <otherwise>
            <validate-jwt header-name="Authorization" />
        </otherwise>
    </choose>
    <set-backend-service base-url="https://your-backend.azurewebsites.net" />
</inbound>
```

**Option B: Pass subscription key in URL**

```javascript
const WS_URL = 'wss://simple-inrm-gateway.azure-api.net/ws?subscription-key=YOUR_KEY';
```

### 8. Check CORS Policy

Ensure APIM CORS policy allows your frontend domain:

```xml
<inbound>
    <cors allow-credentials="true">
        <allowed-origins>
            <origin>https://your-frontend.azurewebsites.net</origin>
            <origin>http://localhost:3000</origin>
        </allowed-origins>
        <allowed-methods>
            <method>GET</method>
            <method>POST</method>
            <method>OPTIONS</method>
        </allowed-methods>
        <allowed-headers>
            <header>*</header>
        </allowed-headers>
    </cors>
    <base />
</inbound>
```

## Workarounds

### Workaround 1: Direct Backend Connection

If APIM WebSocket doesn't work, connect directly to backend:

**Update `.env.production`:**
```env
REACT_APP_BACKEND_URL=https://simple-inrm-gateway.azure-api.net
REACT_APP_WS_URL=wss://your-backend.azurewebsites.net/ws
```

**Pros:** Simple, works immediately
**Cons:** Bypasses APIM (no rate limiting, logging, policies)

### Workaround 2: Use Azure Web PubSub

Use Azure Web PubSub for WebSocket (recommended for production):

1. Get connection URL from `/negotiate` endpoint
2. Connect to Azure Web PubSub directly
3. Backend publishes messages to PubSub
4. Frontend receives via PubSub WebSocket

This is the most scalable solution.

### Workaround 3: Polling Fallback

If WebSocket fails, fall back to HTTP polling:

```javascript
// Check if WebSocket connected
if (!connected) {
    // Poll REST endpoint instead
    setInterval(async () => {
        const response = await fetch(`${BACKEND_URL}/messages`);
        const messages = await response.json();
        // Update UI with messages
    }, 2000);
}
```

## Debug Commands

### Check APIM Configuration
```bash
# Get API details
az apim api show \
  --resource-group <rg> \
  --service-name simple-inrm-gateway \
  --api-id <api-id>

# List all APIs
az apim api list \
  --resource-group <rg> \
  --service-name simple-inrm-gateway
```

### Check App Service Configuration
```bash
# Get web sockets status
az webapp config show \
  --name <backend-app-name> \
  --resource-group <rg> \
  --query webSocketsEnabled

# View logs
az webapp log tail \
  --name <backend-app-name> \
  --resource-group <rg>
```

### Test with cURL
```bash
# Test WebSocket upgrade
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: $(openssl rand -base64 16)" \
  https://simple-inrm-gateway.azure-api.net/ws
```

Expected response: `101 Switching Protocols`

## Common Issues and Solutions

### Issue: "Connection refused"
**Solution:** Backend is not running or not accessible
- Check backend App Service is running
- Verify backend URL is correct

### Issue: "403 Forbidden"
**Solution:** Subscription key or authentication issue
- Add subscription key to URL or headers
- Check APIM authentication policies

### Issue: "502 Bad Gateway"
**Solution:** APIM can't reach backend
- Verify backend URL in policy
- Check backend is running
- Verify network connectivity

### Issue: "Connection closed immediately"
**Solution:** Protocol mismatch or policy blocking
- Check WebSocket protocol enabled
- Review APIM policies for blocking rules
- Verify backend accepts WebSocket connections

## Recommended Architecture

For production, consider this architecture:

```
Frontend (React)
    ↓ HTTPS
Azure API Management (REST endpoints)
    ↓ HTTPS
Backend (FastAPI)
    ↓ Azure SDK
Azure Web PubSub (WebSocket)
    ↑ WebSocket
Frontend (React)
```

**Benefits:**
- Separate REST and WebSocket concerns
- APIM handles REST API management
- Azure Web PubSub handles real-time connections
- Scalable and reliable

## Get Help

If still stuck:
1. Enable Application Insights in APIM
2. Check APIM diagnostics logs
3. Review backend application logs
4. Use browser DevTools Network tab
5. Consider using Azure Web PubSub instead
