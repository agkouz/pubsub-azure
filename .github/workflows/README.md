# GitHub Actions Workflows

This directory contains automated deployment workflows for Azure App Service.

## Workflows

- **deploy-frontend.yml** - Deploys React frontend to `simple-frontend-unlr`
- **deploy-backend.yml** - Deploys FastAPI backend to `simple-backend-unlr`

## Setup

See [GITHUB_ACTIONS_SETUP.md](../../GITHUB_ACTIONS_SETUP.md) for complete setup instructions.

## Quick Start

1. Add secrets to GitHub repository:
   - `AZURE_FRONTEND_PUBLISH_PROFILE`
   - `AZURE_BACKEND_PUBLISH_PROFILE`
   - `REACT_APP_BACKEND_URL`
   - `REACT_APP_WS_URL`
   - `REACT_APP_APIM_SUBSCRIPTION_KEY`

2. Push to `main` branch

3. Workflows run automatically on changes to respective directories

## Manual Trigger

Go to **Actions** tab → Select workflow → **Run workflow**
