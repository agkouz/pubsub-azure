# Getting Your APIM Subscription Key

## Via Azure Portal

1. Go to **Azure Portal** → **API Management** → **simple-inrm-gateway**
2. In the left menu, click **Subscriptions**
3. Find your subscription (usually "Built-in all-access subscription" or create a new one)
4. Click **Show/hide keys** (the eye icon)
5. Copy the **Primary key** or **Secondary key**

## Via Azure CLI

```bash
# List all subscriptions
az apim subscription list \
  --resource-group uniliver-rg \
  --service-name simple-inrm-gateway

# Get a specific subscription key
az apim subscription show \
  --resource-group uniliver-rg \
  --service-name simple-inrm-gateway \
  --sid master \
  --query "{primaryKey:primaryKey, secondaryKey:secondaryKey}"
```

## Create a New Subscription (Recommended)

For production, create a dedicated subscription for your frontend:

```bash
az apim subscription create \
  --resource-group uniliver-rg \
  --service-name simple-inrm-gateway \
  --subscription-id frontend-app \
  --display-name "Frontend Application" \
  --scope /apis \
  --state active
```

Then get its keys:

```bash
az apim subscription show \
  --resource-group uniliver-rg \
  --service-name simple-inrm-gateway \
  --sid frontend-app \
  --query "primaryKey"
```

## Add to Your Frontend

### For Local Development

Create `.env.local`:
```env
REACT_APP_BACKEND_URL=https://simple-inrm-gateway.azure-api.net
REACT_APP_WS_URL=wss://simple-inrm-gateway.azure-api.net/ws
REACT_APP_APIM_SUBSCRIPTION_KEY=your-key-here
```

### For Production Deployment

Update `.env.production`:
```env
REACT_APP_BACKEND_URL=https://simple-inrm-gateway.azure-api.net
REACT_APP_WS_URL=wss://simple-inrm-gateway.azure-api.net/ws
REACT_APP_APIM_SUBSCRIPTION_KEY=your-production-key-here
```

Or set in Azure App Service **Application Settings**:
```bash
az webapp config appsettings set \
  --resource-group uniliver-rg \
  --name your-frontend-app \
  --settings REACT_APP_APIM_SUBSCRIPTION_KEY="your-key-here"
```

## Security Considerations

⚠️ **Important**: Embedding subscription keys in frontend code exposes them to users. For production:

1. **Use Separate Subscription**: Create a dedicated subscription for frontend with limited scope
2. **Rate Limiting**: Set appropriate rate limits on the subscription
3. **Monitor Usage**: Track usage in APIM Analytics
4. **Rotate Keys**: Regularly rotate subscription keys
5. **Consider Backend Proxy**: For sensitive APIs, proxy through a backend that securely calls APIM

## Better Alternative: Backend Proxy

For production, consider this architecture:

```
Frontend → Your Backend (no key) → APIM (with key) → Services
```

This keeps the subscription key secure on the backend.

## How It Works in the Code

The updated frontend code:

**For HTTP Requests:**
```javascript
headers: {
  'Content-Type': 'application/json',
  'Ocp-Apim-Subscription-Key': SUBSCRIPTION_KEY
}
```

**For WebSocket:**
```javascript
const wsUrl = `wss://simple-inrm-gateway.azure-api.net/ws?subscription-key=${SUBSCRIPTION_KEY}`;
const ws = new WebSocket(wsUrl);
```

## Testing

After adding the key, test your application:

1. **HTTP Request Test:**
```bash
curl -X POST https://simple-inrm-gateway.azure-api.net/publish \
  -H "Content-Type: application/json" \
  -H "Ocp-Apim-Subscription-Key: your-key" \
  -d '{"content":"test","timestamp":"2025-11-28T12:00:00Z"}'
```

2. **WebSocket Test:**
Open browser console and run:
```javascript
const ws = new WebSocket('wss://simple-inrm-gateway.azure-api.net/ws?subscription-key=your-key');
ws.onopen = () => console.log('✅ Connected!');
```

## Troubleshooting

### "Access denied due to invalid subscription key"
- Verify the key is correct (copy-paste from Portal)
- Check the subscription is active
- Ensure the API requires subscription (it should)

### "Subscription key is not present"
- Verify environment variable is set correctly
- Check the header name is `Ocp-Apim-Subscription-Key`
- For WebSocket, use `subscription-key` in query string

### Key not working after rotation
- Clear browser cache
- Redeploy frontend application
- Update environment variables in App Service
