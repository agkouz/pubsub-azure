# Deployment Guide - VS Code to Azure App Service

This guide explains how to deploy the React frontend to Azure App Service using VS Code.

## Prerequisites

1. **VS Code Extensions**:
   - Install "Azure App Service" extension from Microsoft
   - Install "Azure Account" extension

2. **Azure Resources**:
   - Azure App Service (Node.js runtime)
   - Azure API Management configured with backend

## Environment Variables Configuration

The app uses three environment variable files:

### `.env.development` (Local Development)
```env
REACT_APP_BACKEND_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000/ws
```

### `.env.production` (Azure Production)
```env
REACT_APP_BACKEND_URL=https://simple-inrm-gateway.azure-api.net
REACT_APP_WS_URL=wss://simple-inrm-gateway.azure-api.net/ws
```

Update `.env.production` with your actual Azure API Management URLs before deployment.

## Deployment Methods

### Method 1: VS Code Azure Extension (Recommended)

1. **Open VS Code** and open the `frontend` folder

2. **Sign in to Azure**:
   - Press `Ctrl+Shift+P` (Windows/Linux) or `Cmd+Shift+P` (Mac)
   - Type "Azure: Sign In"
   - Follow the authentication flow

3. **Create App Service** (if not exists):
   - Click Azure icon in sidebar
   - In App Service section, click "+"
   - Choose "Create New Web App"
   - Enter a unique name
   - Select Node.js runtime (20 LTS recommended)
   - Select resource group and region

4. **Deploy**:
   - Right-click on the `frontend` folder in VS Code
   - Select "Deploy to Web App..."
   - Choose your App Service
   - Confirm deployment
   - Wait for build and deployment to complete

### Method 2: Azure CLI

```bash
# Login to Azure
az login

# Navigate to frontend directory
cd frontend

# Build the app
npm install
npm run build

# Deploy using zip deployment
az webapp deployment source config-zip \
  --resource-group <your-resource-group> \
  --name <your-app-service-name> \
  --src build.zip
```

### Method 3: GitHub Actions (CI/CD)

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy React App

on:
  push:
    branches: [ main ]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Setup Node.js
      uses: actions/setup-node@v2
      with:
        node-version: '20'
    
    - name: Install and Build
      run: |
        cd frontend
        npm install
        npm run build
    
    - name: Deploy to Azure
      uses: azure/webapps-deploy@v2
      with:
        app-name: <your-app-service-name>
        publish-profile: ${{ secrets.AZURE_WEBAPP_PUBLISH_PROFILE }}
        package: frontend/build
```

## Configure App Service Settings

After deployment, configure these settings in Azure Portal:

### 1. Application Settings (Environment Variables)

Go to your App Service → **Configuration** → **Application settings**:

Add these settings:
```
REACT_APP_BACKEND_URL = https://simple-inrm-gateway.azure-api.net
REACT_APP_WS_URL = wss://simple-inrm-gateway.azure-api.net/ws
```

**Important**: When adding environment variables in Azure App Service, they override the `.env.production` file. Choose one method:
- **Option A**: Use `.env.production` file (no App Settings needed)
- **Option B**: Use App Service Application Settings (more flexible)

### 2. General Settings

- **Stack**: Node
- **Major version**: 20 LTS
- **Startup Command**: `pm2 serve build 8080 --spa` (for React)

### 3. Enable WebSockets

If using WebSocket through App Service directly:
- **Configuration** → **General settings**
- **Web sockets**: On

## Verify Deployment

1. **Check App Service URL**: `https://<your-app-name>.azurewebsites.net`

2. **Test the application**:
   - Open the URL in browser
   - Check if it connects to WebSocket
   - Try publishing a message
   - Verify responses are received

3. **Check logs**:
   - App Service → **Log stream**
   - Or use: `az webapp log tail --name <app-name> --resource-group <rg>`

## Troubleshooting

### Build Fails
- Ensure Node.js version matches (check `package.json` engines)
- Clear npm cache: `npm cache clean --force`
- Delete `node_modules` and reinstall

### Environment Variables Not Working
- In Azure Portal, verify Application Settings are set correctly
- Restart the App Service after adding environment variables
- Check that variable names start with `REACT_APP_`

### WebSocket Connection Fails
- Verify WebSocket is enabled in App Service
- Check APIM WebSocket policy is configured
- Verify `WS_URL` uses `wss://` (not `ws://`) for HTTPS sites
- Check CORS settings in backend

### 404 Errors on Refresh
- Ensure `web.config` or startup command handles SPA routing
- For Node App Service, use: `pm2 serve build 8080 --spa`

### CORS Issues
- Verify backend CORS allows your App Service domain
- Check APIM CORS policy if using API Management

## Production Best Practices

1. **Use Application Settings** for environment variables instead of `.env` files
2. **Enable Application Insights** for monitoring
3. **Set up Custom Domain** and SSL certificate
4. **Configure CDN** for static assets
5. **Enable Auto-scaling** based on load
6. **Set up Deployment Slots** for staging/production
7. **Configure Health Check** endpoint

## Quick Commands

```bash
# View deployment logs
az webapp log tail --name <app-name> --resource-group <rg>

# Restart app service
az webapp restart --name <app-name> --resource-group <rg>

# SSH into container (Linux App Service)
az webapp ssh --name <app-name> --resource-group <rg>

# Update environment variable
az webapp config appsettings set \
  --name <app-name> \
  --resource-group <rg> \
  --settings REACT_APP_BACKEND_URL="https://your-url.com"
```

## Support

If you encounter issues:
1. Check Azure Portal logs
2. Review Application Insights
3. Test locally with production environment variables
4. Verify all Azure resources are in the same region for best performance
