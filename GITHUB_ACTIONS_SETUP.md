# GitHub Actions Deployment Setup Guide

This guide explains how to set up automated deployments to Azure App Service using GitHub Actions.

## Overview

Two workflows are configured:
- **Frontend Workflow** (`deploy-frontend.yml`) - Deploys React app to `simple-frontend-unlr`
- **Backend Workflow** (`deploy-backend.yml`) - Deploys FastAPI app to `simple-backend-unlr`

## Prerequisites

- GitHub repository with your code
- Azure App Services created (frontend and backend)
- Permissions to manage GitHub repository secrets

## Step 1: Get Azure Publish Profiles

You need to download publish profiles from Azure for both App Services.

### Via Azure Portal

#### Frontend Publish Profile:
1. Go to **App Service** → **simple-frontend-unlr**
2. Click **Get publish profile** (in the top toolbar)
3. Save the downloaded `.PublishSettings` file

#### Backend Publish Profile:
1. Go to **App Service** → **simple-backend-unlr**
2. Click **Get publish profile** (in the top toolbar)
3. Save the downloaded `.PublishSettings` file

### Via Azure CLI

```bash
# Download frontend publish profile
az webapp deployment list-publishing-profiles \
  --resource-group uniliver-rg \
  --name simple-frontend-unlr \
  --xml > frontend-publish-profile.xml

# Download backend publish profile
az webapp deployment list-publishing-profiles \
  --resource-group uniliver-rg \
  --name simple-backend-unlr \
  --xml > backend-publish-profile.xml
```

## Step 2: Add Secrets to GitHub Repository

### Navigate to GitHub Secrets

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**

### Add These Secrets

#### Required Secrets:

**1. AZURE_FRONTEND_PUBLISH_PROFILE**
- Click **New repository secret**
- Name: `AZURE_FRONTEND_PUBLISH_PROFILE`
- Value: Open the frontend `.PublishSettings` file and copy **entire contents**
- Click **Add secret**

**2. AZURE_BACKEND_PUBLISH_PROFILE**
- Click **New repository secret**
- Name: `AZURE_BACKEND_PUBLISH_PROFILE`
- Value: Open the backend `.PublishSettings` file and copy **entire contents**
- Click **Add secret**

#### Frontend Environment Variables:

**3. REACT_APP_BACKEND_URL**
- Name: `REACT_APP_BACKEND_URL`
- Value: `https://simple-inrm-gateway.azure-api.net`

**4. REACT_APP_WS_URL**
- Name: `REACT_APP_WS_URL`
- Value: `wss://simple-inrm-gateway.azure-api.net/ws`

**5. REACT_APP_APIM_SUBSCRIPTION_KEY**
- Name: `REACT_APP_APIM_SUBSCRIPTION_KEY`
- Value: Your APIM subscription key

### Quick Command to Get Subscription Key

```bash
az apim subscription show \
  --resource-group uniliver-rg \
  --service-name simple-inrm-gateway \
  --sid master \
  --query "primaryKey" -o tsv
```

## Step 3: Configure Repository Structure

Your repository should have this structure:

```
your-repo/
├── .github/
│   └── workflows/
│       ├── deploy-frontend.yml
│       └── deploy-backend.yml
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── ...
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   └── ...
└── README.md
```

## Step 4: Push to GitHub

```bash
# Initialize git repository (if not already done)
git init

# Add all files
git add .

# Commit
git commit -m "Add GitHub Actions workflows"

# Add remote (replace with your repo URL)
git remote add origin https://github.com/your-username/your-repo.git

# Push to main branch
git push -u origin main
```

## How It Works

### Frontend Deployment Triggers

The frontend workflow runs when:
- Code is pushed to `main` branch
- Changes are made in `frontend/` directory
- Workflow is manually triggered (workflow_dispatch)

**Deployment Process:**
1. Checkout code
2. Setup Node.js 20.x
3. Install dependencies (`npm ci`)
4. Build React app with environment variables
5. Deploy `build/` folder to Azure App Service
6. Show deployment summary

### Backend Deployment Triggers

The backend workflow runs when:
- Code is pushed to `main` branch
- Changes are made in `backend/` directory
- Workflow is manually triggered (workflow_dispatch)

**Deployment Process:**
1. Checkout code
2. Setup Python 3.11
3. Install dependencies from `requirements.txt`
4. Create deployment package (zip)
5. Deploy to Azure App Service
6. Show deployment summary

## Manual Deployment

You can manually trigger deployments:

1. Go to **Actions** tab in GitHub
2. Select the workflow (Frontend or Backend)
3. Click **Run workflow**
4. Select branch (usually `main`)
5. Click **Run workflow**

## Monitoring Deployments

### View Workflow Runs

1. Go to **Actions** tab in GitHub repository
2. See list of all workflow runs
3. Click on a run to see details
4. View logs for each step

### Check Deployment Status

After deployment completes, verify:

**Frontend:**
```bash
curl https://simple-frontend-unlr-g9h4bcgkdtfffxd2.westeurope-01.azurewebsites.net
```

**Backend:**
```bash
curl https://simple-backend-unlr-bse7b2cudad6h7gs.westeurope-01.azurewebsites.net/health
```

## Environment-Specific Deployments

If you want separate staging/production environments:

### Option 1: Use Branches

Create separate workflows for different branches:
- `deploy-frontend-staging.yml` - Triggers on `develop` branch
- `deploy-frontend-production.yml` - Triggers on `main` branch

### Option 2: Use Deployment Slots

Azure App Service supports deployment slots:

```yaml
- name: Deploy to Staging Slot
  uses: azure/webapps-deploy@v2
  with:
    app-name: ${{ env.AZURE_WEBAPP_NAME }}
    slot-name: staging
    publish-profile: ${{ secrets.AZURE_FRONTEND_STAGING_PROFILE }}
    package: frontend/build
```

## Troubleshooting

### "Publish profile is invalid"

- Verify you copied the **entire** contents of the `.PublishSettings` file
- Ensure no extra spaces or characters were added
- Re-download the publish profile from Azure

### "Build failed"

- Check the workflow logs in GitHub Actions
- Verify `package.json` or `requirements.txt` are correct
- Test build locally first

### "Environment variables not set"

- Verify secrets are added in GitHub repository settings
- Secret names must match exactly (case-sensitive)
- Re-check the workflow YAML for correct secret references

### "Deployment succeeded but app not working"

- Check Azure App Service logs
- Verify environment variables in App Service Configuration
- Restart the App Service

```bash
# View logs
az webapp log tail \
  --resource-group uniliver-rg \
  --name simple-frontend-unlr

# Restart app
az webapp restart \
  --resource-group uniliver-rg \
  --name simple-frontend-unlr
```

## Security Best Practices

1. **Never commit secrets to repository**
   - Use GitHub Secrets for all sensitive data
   - Add `.env` files to `.gitignore`

2. **Rotate publish profiles regularly**
   - Download new profiles every few months
   - Update GitHub secrets

3. **Use least privilege**
   - Publish profiles have deployment permissions only
   - Don't use admin credentials

4. **Enable branch protection**
   - Require pull request reviews
   - Prevent direct pushes to `main`

## Advanced: Matrix Builds

If you want to test multiple Node.js or Python versions:

```yaml
strategy:
  matrix:
    node-version: [18.x, 20.x]
    
steps:
  - uses: actions/setup-node@v4
    with:
      node-version: ${{ matrix.node-version }}
```

## Cost Optimization

GitHub Actions provides:
- 2,000 minutes/month free for private repos
- Unlimited for public repos

Monitor usage:
- Repository **Settings** → **Actions** → **General**
- View billing and usage

## Next Steps

1. ✅ Add secrets to GitHub
2. ✅ Push code to GitHub
3. ✅ Watch Actions tab for first deployment
4. ✅ Verify apps are working
5. 🚀 Make changes and push - automatic deployment!

## Support

If deployment fails:
1. Check GitHub Actions logs
2. Check Azure App Service logs
3. Verify all secrets are set correctly
4. Test local build first

## Example: Complete Setup Commands

```bash
# 1. Get publish profiles
az webapp deployment list-publishing-profiles \
  --resource-group uniliver-rg \
  --name simple-frontend-unlr \
  --xml > frontend-profile.xml

az webapp deployment list-publishing-profiles \
  --resource-group uniliver-rg \
  --name simple-backend-unlr \
  --xml > backend-profile.xml

# 2. Get APIM subscription key
az apim subscription show \
  --resource-group uniliver-rg \
  --service-name simple-inrm-gateway \
  --sid master \
  --query "primaryKey" -o tsv

# 3. Add to GitHub secrets (via web interface)

# 4. Push to GitHub
git add .
git commit -m "Add workflows"
git push origin main

# 5. Monitor deployment
# Go to: https://github.com/your-username/your-repo/actions
```

Happy deploying! 🚀
