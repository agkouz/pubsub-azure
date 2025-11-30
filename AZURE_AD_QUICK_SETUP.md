# Quick Setup Commands for Azure AD Authentication

## 1. Enable Managed Identity

```bash
az webapp identity assign \
  --resource-group uniliver-rg \
  --name simple-backend-unlr
```

## 2. Grant Permissions

```bash
# Set variables
SERVICEBUS_ID=$(az servicebus namespace show \
  --resource-group uniliver-rg \
  --name simple-pubsub-unlr \
  --query id -o tsv)

PRINCIPAL_ID=$(az webapp identity show \
  --resource-group uniliver-rg \
  --name simple-backend-unlr \
  --query principalId -o tsv)

# Grant access
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Azure Service Bus Data Owner" \
  --scope $SERVICEBUS_ID
```

## 3. Configure Environment Variables

```bash
# Set namespace FQDN
az webapp config appsettings set \
  --resource-group uniliver-rg \
  --name simple-backend-unlr \
  --settings \
    AZURE_SERVICEBUS_NAMESPACE_FQDN="simple-pubsub-unlr.servicebus.windows.net"

# (Optional) Remove connection string to force Azure AD
az webapp config appsettings delete \
  --resource-group uniliver-rg \
  --name simple-backend-unlr \
  --setting-names AZURE_SERVICEBUS_CONNECTION_STRING
```

## 4. Deploy Updated Code

```bash
git add backend/main.py backend/requirements.txt AZURE_AD_SETUP.md
git commit -m "Add Azure AD authentication for Service Bus"
git push origin main
```

## 5. Restart and Verify

```bash
# Restart
az webapp restart \
  --resource-group uniliver-rg \
  --name simple-backend-unlr

# Check logs
az webapp log tail \
  --resource-group uniliver-rg \
  --name simple-backend-unlr

# Check health
curl https://simple-backend-unlr-bse7b2cudad6h7gs.westeurope-01.azurewebsites.net/health
```

## Expected Success Output

**Logs:**
```
Authentication Method: Azure AD (Managed Identity)
Service Bus Namespace FQDN: simple-pubsub-unlr.servicebus.windows.net
Using Azure AD authentication (Managed Identity)
✓ Listening to Service Bus topic 'backend-messages', subscription 'backend-suscription'
```

**Health Endpoint:**
```json
{
  "status": "healthy",
  "service_bus_configured": true,
  "authentication_method": "Azure AD",
  "active_websocket_connections": 0
}
```

## Troubleshooting

**If it fails:**
1. Check managed identity is enabled
2. Verify role assignment
3. Ensure FQDN is correct
4. Check logs for detailed errors

**Quick rollback to connection string:**
```bash
# Re-add connection string
az webapp config appsettings set \
  --resource-group uniliver-rg \
  --name simple-backend-unlr \
  --settings \
    AZURE_SERVICEBUS_CONNECTION_STRING="your-connection-string"

# Remove FQDN
az webapp config appsettings delete \
  --resource-group uniliver-rg \
  --name simple-backend-unlr \
  --setting-names AZURE_SERVICEBUS_NAMESPACE_FQDN
```
