# Azure AD Authentication for Service Bus

This guide explains how to configure Azure AD (Entra ID) authentication for Azure Service Bus instead of using connection strings.

## Benefits of Azure AD Authentication

✅ **More Secure** - No connection strings stored in environment variables  
✅ **Managed Identity** - Azure handles credentials automatically  
✅ **Better Auditing** - Track which identity accessed what  
✅ **Principle of Least Privilege** - Grant only necessary permissions  
✅ **Automatic Credential Rotation** - Azure handles token refresh  

## Prerequisites

- Azure Service Bus namespace created
- Backend App Service deployed
- Azure CLI installed

## Step 1: Enable Managed Identity

Enable system-assigned managed identity on your backend App Service:

```bash
# Enable managed identity
az webapp identity assign \
  --resource-group uniliver-rg \
  --name simple-backend-unlr
```

**Save the `principalId` from the output** - you'll need it for the next step.

Or get it separately:

```bash
# Get the principal ID
PRINCIPAL_ID=$(az webapp identity show \
  --resource-group uniliver-rg \
  --name simple-backend-unlr \
  --query principalId -o tsv)

echo $PRINCIPAL_ID
```

## Step 2: Grant Service Bus Permissions

Assign the "Azure Service Bus Data Owner" role to the managed identity:

```bash
# Get the Service Bus namespace resource ID
SERVICEBUS_ID=$(az servicebus namespace show \
  --resource-group uniliver-rg \
  --name simple-pubsub-unlr \
  --query id -o tsv)

# Get the managed identity principal ID (if not already set)
PRINCIPAL_ID=$(az webapp identity show \
  --resource-group uniliver-rg \
  --name simple-backend-unlr \
  --query principalId -o tsv)

# Assign "Azure Service Bus Data Owner" role
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Azure Service Bus Data Owner" \
  --scope $SERVICEBUS_ID
```

### Available Roles

| Role | Permissions |
|------|------------|
| **Azure Service Bus Data Owner** | Full access (send, receive, manage) |
| **Azure Service Bus Data Sender** | Send messages only |
| **Azure Service Bus Data Receiver** | Receive messages only |

**For this application, use "Data Owner"** since the backend both sends and receives messages.

## Step 3: Configure Environment Variables

### Remove Connection String (Optional but Recommended)

If you want to use ONLY Azure AD authentication:

```bash
# Remove the connection string
az webapp config appsettings delete \
  --resource-group uniliver-rg \
  --name simple-backend-unlr \
  --setting-names AZURE_SERVICEBUS_CONNECTION_STRING
```

### Set Namespace FQDN

```bash
# Set the fully qualified domain name
az webapp config appsettings set \
  --resource-group uniliver-rg \
  --name simple-backend-unlr \
  --settings \
    AZURE_SERVICEBUS_NAMESPACE_FQDN="simple-pubsub-unlr.servicebus.windows.net"
```

**Note:** The FQDN format is: `<namespace-name>.servicebus.windows.net`

### Keep Topic and Subscription Names

These should already be configured:

```bash
# Verify they're set
az webapp config appsettings list \
  --resource-group uniliver-rg \
  --name simple-backend-unlr \
  --query "[?name=='AZURE_SERVICEBUS_TOPIC_NAME' || name=='AZURE_SERVICEBUS_SUBSCRIPTION_NAME']"
```

If not set:

```bash
az webapp config appsettings set \
  --resource-group uniliver-rg \
  --name simple-backend-unlr \
  --settings \
    AZURE_SERVICEBUS_TOPIC_NAME="backend-messages" \
    AZURE_SERVICEBUS_SUBSCRIPTION_NAME="backend-suscription"
```

## Step 4: Deploy Updated Code

The backend code now supports both authentication methods:

**Priority:**
1. If `AZURE_SERVICEBUS_NAMESPACE_FQDN` is set → Use Azure AD
2. Otherwise, if `AZURE_SERVICEBUS_CONNECTION_STRING` is set → Use connection string

### Deploy via GitHub Actions

```bash
git add backend/main.py backend/requirements.txt
git commit -m "Add Azure AD authentication support for Service Bus"
git push origin main
```

### Or Manual Deployment

```bash
cd backend
# Install new dependency
pip install azure-identity==1.15.0 --break-system-packages

# Deploy
# ... your deployment process
```

## Step 5: Restart and Verify

```bash
# Restart the backend
az webapp restart \
  --resource-group uniliver-rg \
  --name simple-backend-unlr

# Watch the logs
az webapp log tail \
  --resource-group uniliver-rg \
  --name simple-backend-unlr
```

## Expected Log Output

With Azure AD authentication, you should see:

```
============================================================
AZURE SERVICE BUS CONFIGURATION
============================================================
Authentication Method: Azure AD (Managed Identity)
Service Bus Namespace FQDN: simple-pubsub-unlr.servicebus.windows.net
Topic Name: backend-messages
Subscription Name: backend-suscription
============================================================
✓ Service Bus listener task started
Starting Service Bus listener...
Using Azure AD authentication (Managed Identity)
✓ Listening to Service Bus topic 'backend-messages', subscription 'backend-suscription'
```

## Verification

### Check Health Endpoint

```bash
curl https://simple-backend-unlr-bse7b2cudad6h7gs.westeurope-01.azurewebsites.net/health
```

Should return:

```json
{
  "status": "healthy",
  "service_bus_configured": true,
  "authentication_method": "Azure AD",
  "active_websocket_connections": 0
}
```

### Test Publishing

Publish a message through the frontend or via API:

```bash
curl -X POST https://simple-inrm-gateway.azure-api.net/publish \
  -H "Content-Type: application/json" \
  -H "Ocp-Apim-Subscription-Key: your-key-here" \
  -d '{"content":"Hello from Azure AD!","timestamp":"2025-11-30T00:00:00Z"}'
```

Check logs for:
```
Using Azure AD for publish
✓ Message sent to Service Bus successfully: Hello from Azure AD!
```

## Troubleshooting

### Error: "not authorized to perform action"

**Problem:** Managed identity doesn't have permissions

**Solution:**
```bash
# Verify role assignment
az role assignment list \
  --assignee $PRINCIPAL_ID \
  --scope $SERVICEBUS_ID

# If missing, add it:
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Azure Service Bus Data Owner" \
  --scope $SERVICEBUS_ID
```

### Error: "Managed identity not configured"

**Problem:** Managed identity not enabled on App Service

**Solution:**
```bash
# Enable it
az webapp identity assign \
  --resource-group uniliver-rg \
  --name simple-backend-unlr
```

### Error: "credential chain failed"

**Problem:** Azure identity library can't find credentials

**Solution in Azure App Service:** This should work automatically. The issue might be:
- Managed identity not enabled
- Not running in Azure (local development requires different setup)

**For Local Development:**
```bash
# Use Azure CLI authentication
az login

# Or set connection string for local dev
export AZURE_SERVICEBUS_CONNECTION_STRING="Endpoint=sb://..."
```

### Fallback to Connection String

If Azure AD isn't working, you can temporarily fall back:

```bash
# Re-add connection string
az webapp config appsettings set \
  --resource-group uniliver-rg \
  --name simple-backend-unlr \
  --settings \
    AZURE_SERVICEBUS_CONNECTION_STRING="your-connection-string"

# Remove FQDN to force connection string usage
az webapp config appsettings delete \
  --resource-group uniliver-rg \
  --name simple-backend-unlr \
  --setting-names AZURE_SERVICEBUS_NAMESPACE_FQDN
```

## Security Best Practices

1. ✅ **Use Azure AD when possible** - More secure than connection strings
2. ✅ **Don't commit credentials** - Never put connection strings in code
3. ✅ **Use minimum necessary permissions** - Use Data Sender/Receiver roles when possible
4. ✅ **Enable diagnostic logging** - Monitor Service Bus access
5. ✅ **Regular access reviews** - Audit who has access

## Migration Checklist

- [ ] Enable managed identity on App Service
- [ ] Grant Service Bus Data Owner role to managed identity
- [ ] Set `AZURE_SERVICEBUS_NAMESPACE_FQDN` environment variable
- [ ] Deploy updated code with azure-identity package
- [ ] Verify authentication method in logs
- [ ] Test message publishing and receiving
- [ ] (Optional) Remove `AZURE_SERVICEBUS_CONNECTION_STRING` environment variable
- [ ] Update documentation

## Hybrid Mode (Both Methods Supported)

The code supports both authentication methods simultaneously:

**Configuration Priority:**
1. If `NAMESPACE_FQDN` is set → Azure AD
2. Else if `CONNECTION_STRING` is set → Connection String
3. Else → Error

This allows for:
- **Gradual migration** - Test Azure AD without removing connection string
- **Fallback option** - If Azure AD fails, you can quickly switch back
- **Different environments** - Use Azure AD in production, connection string in dev

## Cost Considerations

Azure AD authentication for Service Bus is **free** - there's no additional cost for using managed identities or Azure AD authentication. You only pay for Service Bus operations (send/receive messages).

## Next Steps

After successful Azure AD configuration:

1. **Remove connection strings** from all environments
2. **Document the setup** for your team
3. **Apply to other services** - Use managed identities for other Azure resources
4. **Set up monitoring** - Track authentication events in Azure Monitor

## Support

If you encounter issues:

1. Check Azure Service Bus logs
2. Verify managed identity is enabled
3. Confirm role assignments are correct
4. Review application logs for detailed error messages

For more information:
- [Azure Managed Identities Documentation](https://docs.microsoft.com/azure/active-directory/managed-identities-azure-resources/)
- [Azure Service Bus Authentication](https://docs.microsoft.com/azure/service-bus-messaging/service-bus-authentication-and-authorization)
