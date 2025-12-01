# Documentation Index

This project includes comprehensive documentation for all components and processes.

## 📚 Documentation Files

### Core Documentation

**[ARCHITECTURE.md](ARCHITECTURE.md)** ⭐ **START HERE**
- Complete system architecture overview
- All components described in detail
- Message flows and authentication
- Configuration reference
- Troubleshooting guide

**[ARCHITECTURE.pdf](ARCHITECTURE.pdf)** 📄 **PDF VERSION**
- Professional PDF format with styling
- Print-ready documentation
- Same content as ARCHITECTURE.md

### Feature Documentation

**[MULTI_ROOM_QUICKSTART.md](MULTI_ROOM_QUICKSTART.md)** 🚀 **NEW FEATURE**
- Get multi-room chatrooms running in 5 minutes
- Step-by-step deployment guide
- Testing instructions

**[MULTI_ROOM_IMPLEMENTATION.md](MULTI_ROOM_IMPLEMENTATION.md)** 📚 **DETAILED GUIDE**
- Complete multi-room architecture
- 4 implementation options compared
- Message flow diagrams
- Scaling considerations
- Production checklist

### Setup Guides

**[README.md](README.md)**
- Quick start guide
- Project overview
- Basic setup instructions

**[DEPLOYMENT.md](DEPLOYMENT.md)**
- VS Code deployment guide
- Manual deployment steps
- Alternative deployment methods

### Service-Specific Guides

**[SERVICE_BUS_SETUP.md](SERVICE_BUS_SETUP.md)**
- Azure Service Bus configuration
- Topic and subscription creation
- Connection string management

**[AZURE_AD_SETUP.md](AZURE_AD_SETUP.md)**
- Complete Azure AD authentication guide
- Managed Identity setup
- Migration from connection strings
- Security best practices

**[AZURE_AD_QUICK_SETUP.md](AZURE_AD_QUICK_SETUP.md)**
- Quick command reference for Azure AD
- Copy-paste commands
- Verification steps

**[SUBSCRIPTION_KEY_GUIDE.md](SUBSCRIPTION_KEY_GUIDE.md)**
- APIM subscription key management
- How to get and use keys
- Frontend configuration

**[WEBSOCKET_TROUBLESHOOTING.md](WEBSOCKET_TROUBLESHOOTING.md)**
- WebSocket connection debugging
- Common issues and solutions
- APIM configuration tips

**[GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md)**
- CI/CD pipeline setup
- GitHub secrets configuration
- Workflow explanation
- Troubleshooting deployment issues

## 🗂️ Directory Structure

```
azure-pubsub-project/
├── ARCHITECTURE.md                    ⭐ Comprehensive architecture doc
├── README.md                          📖 Main readme
├── DEPLOYMENT.md                      🚀 Deployment guide
├── SERVICE_BUS_SETUP.md              📨 Service Bus setup
├── AZURE_AD_SETUP.md                 🔐 Azure AD guide (detailed)
├── AZURE_AD_QUICK_SETUP.md           ⚡ Azure AD quick reference
├── SUBSCRIPTION_KEY_GUIDE.md         🔑 APIM keys guide
├── WEBSOCKET_TROUBLESHOOTING.md      🔌 WebSocket debugging
├── GITHUB_ACTIONS_SETUP.md           ⚙️ CI/CD setup
│
├── frontend/                          💻 React application
│   ├── src/
│   │   ├── App.js                    Main React component
│   │   └── App.css                   Styling
│   ├── public/
│   ├── server.js                     Production Express server
│   ├── package.json
│   └── .env.production               Environment variables template
│
├── backend/                           🐍 Python FastAPI application
│   ├── main.py                       Main application code
│   ├── requirements.txt              Python dependencies
│   ├── .env.example                  Environment variables template
│   ├── .deployment                   Oryx build config
│   └── runtime.txt                   Python version
│
└── .github/
    └── workflows/
        ├── deploy-frontend.yml       Frontend CI/CD
        └── deploy-backend.yml        Backend CI/CD
```

## 🎯 Quick Navigation

### I want to...

**Understand the overall system**
→ Read [ARCHITECTURE.md](ARCHITECTURE.md)

**Deploy the application**
→ Follow [GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md)

**Set up Azure Service Bus**
→ Follow [SERVICE_BUS_SETUP.md](SERVICE_BUS_SETUP.md)

**Configure Azure AD authentication**
→ Follow [AZURE_AD_SETUP.md](AZURE_AD_SETUP.md) (detailed)
→ Or [AZURE_AD_QUICK_SETUP.md](AZURE_AD_QUICK_SETUP.md) (quick commands)

**Fix WebSocket issues**
→ Check [WEBSOCKET_TROUBLESHOOTING.md](WEBSOCKET_TROUBLESHOOTING.md)

**Get APIM subscription keys**
→ See [SUBSCRIPTION_KEY_GUIDE.md](SUBSCRIPTION_KEY_GUIDE.md)

**Troubleshoot deployment**
→ Check [GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md) troubleshooting section

## 📊 Component Documentation

### Frontend (React)
- **Main file**: `frontend/src/App.js`
- **Server**: `frontend/server.js` (Express)
- **Config**: `frontend/.env.production`
- **Docs**: See "Frontend Application" section in ARCHITECTURE.md

### Backend (FastAPI)
- **Main file**: `backend/main.py`
- **Dependencies**: `backend/requirements.txt`
- **Config**: Environment variables (see ARCHITECTURE.md)
- **Docs**: See "Backend Application" section in ARCHITECTURE.md

### Azure Service Bus
- **Resource**: simple-pubsub-unlr
- **Topic**: backend-messages
- **Subscription**: backend-subscription
- **Docs**: SERVICE_BUS_SETUP.md, ARCHITECTURE.md

### API Management
- **Resource**: simple-inrm-gateway
- **APIs**: backend-api-via-api-gateway, websocket-api
- **Docs**: See "Azure API Management" section in ARCHITECTURE.md

### CI/CD
- **Workflows**: `.github/workflows/*.yml`
- **Docs**: GITHUB_ACTIONS_SETUP.md

## 🔍 Key Concepts

### Message Flow
See "Message Flow" section in ARCHITECTURE.md for detailed diagrams

### Authentication
- **Frontend → APIM**: Subscription keys (SUBSCRIPTION_KEY_GUIDE.md)
- **APIM → Backend**: IP whitelisting (ARCHITECTURE.md)
- **Backend → Service Bus**: Azure AD Managed Identity (AZURE_AD_SETUP.md)

### Deployment
- **Automated**: GitHub Actions (GITHUB_ACTIONS_SETUP.md)
- **Manual**: VS Code (DEPLOYMENT.md)

## 📝 Quick Reference

### Important URLs
```
Frontend: https://simple-frontend-unlr-g9h4bcgkdtfffxd2.westeurope-01.azurewebsites.net
Backend:  https://simple-backend-unlr-bse7b2cudad6h7gs.westeurope-01.azurewebsites.net
APIM:     https://simple-inrm-gateway.azure-api.net
```

### Important Commands
```bash
# View backend logs
az webapp log tail --resource-group uniliver-rg --name simple-backend-unlr

# Restart backend
az webapp restart --resource-group uniliver-rg --name simple-backend-unlr

# Get APIM subscription key
az apim subscription show --resource-group uniliver-rg --service-name simple-inrm-gateway --sid master --query "primaryKey" -o tsv
```

### Environment Variables
See "Configuration Reference" in ARCHITECTURE.md for complete list

## 🆘 Getting Help

1. **Check logs first**: `az webapp log tail ...`
2. **Review troubleshooting sections** in relevant docs
3. **Verify configuration** against ARCHITECTURE.md
4. **Check Azure Portal** for resource status

## 📦 Complete Package

All documentation and code is available in:
`azure-pubsub-project.tar.gz`

Extract with:
```bash
tar -xzf azure-pubsub-project.tar.gz
cd azure-pubsub-project
```

---

**Last Updated**: 2025-11-30  
**Version**: 1.0
