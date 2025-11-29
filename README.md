# Azure Service Bus Demo Project

A full-stack application demonstrating Azure Service Bus integration (Azure's equivalent to Google Cloud Pub/Sub) with React frontend and FastAPI backend.

## Architecture

- **Frontend**: React application that publishes messages to Azure Service Bus Topic via backend API
- **Backend**: FastAPI server that publishes to Service Bus and subscribes to receive messages
- **Azure Service Bus**: Message broker with Topic/Subscription pattern
- **WebSocket**: Real-time communication to send messages from backend to frontend

## Features

- ✅ Publish messages to Azure Service Bus Topic
- ✅ Subscribe to Service Bus messages in backend
- ✅ Real-time WebSocket communication between frontend and backend
- ✅ Message broadcasting to all connected clients
- ✅ Auto-reconnection on WebSocket disconnect
- ✅ Beautiful, responsive UI with message history
- ✅ APIM integration for API management

## Prerequisites

- Python 3.8+
- Node.js 16+
- Azure account with:
  - Azure Service Bus namespace
  - Service Bus Topic and Subscription
  - Azure API Management (optional)

## Azure Service Bus Setup

See [SERVICE_BUS_SETUP.md](SERVICE_BUS_SETUP.md) for detailed setup instructions.

### Quick Setup

1. **Create Topic and Subscription**:
```bash
# Create topic
az servicebus topic create \
  --resource-group uniliver-rg \
  --namespace-name simple-pubsub-unlr \
  --name messages

# Create subscription
az servicebus topic subscription create \
  --resource-group uniliver-rg \
  --namespace-name simple-pubsub-unlr \
  --topic-name messages \
  --name backend-subscription
```

2. **Get Connection String**:
```bash
az servicebus namespace authorization-rule keys list \
  --resource-group uniliver-rg \
  --namespace-name simple-pubsub-unlr \
  --name RootManageSharedAccessKey \
  --query primaryConnectionString -o tsv
```

## Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
```

Edit `.env` and add your Azure Web PubSub connection string:
```
AZURE_PUBSUB_CONNECTION_STRING=Endpoint=https://your-resource.webpubsub.azure.com;AccessKey=your-key;Version=1.0;
AZURE_PUBSUB_HUB_NAME=sample_hub
```

5. Run the backend:
```bash
python main.py
```

The backend will start on `http://localhost:8000`

## Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm start
```

The frontend will start on `http://localhost:3000`

## Usage

1. Start both the backend and frontend servers
2. Open `http://localhost:3000` in your browser
3. Once connected, type a message and click "Publish to Azure PubSub"
4. The backend will receive the message via Azure PubSub and send a response via WebSocket
5. The response will appear in the message list

## API Endpoints

### Backend

- `GET /` - Health check
- `GET /health` - Health status
- `GET /negotiate` - Get Azure PubSub client access token
- `POST /publish` - Publish message to Azure PubSub
- `WS /ws` - WebSocket endpoint for real-time communication

## Project Structure

```
azure-pubsub-project/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── requirements.txt     # Python dependencies
│   └── .env.example        # Environment variables template
├── frontend/
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── App.js          # Main React component
│   │   ├── App.css         # Styling
│   │   ├── index.js        # React entry point
│   │   └── index.css       # Global styles
│   └── package.json        # Node dependencies
└── README.md
```

## Troubleshooting

### Backend Issues

- **Connection string error**: Verify your Azure PubSub connection string is correct
- **Port already in use**: Change the port in `main.py` (default: 8000)

### Frontend Issues

- **WebSocket connection failed**: Ensure the backend is running on `http://localhost:8000`
- **CORS errors**: The backend is configured to allow all origins (update in production)

### Azure PubSub Issues

- **Authentication failed**: Check your connection string and ensure the resource is active
- **Hub not found**: Hubs are created automatically on first use, no manual creation needed

## Production Considerations

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions using VS Code.

1. **Environment Variables**: Configure via `.env.production` or Azure App Service Application Settings
2. **CORS**: Restrict allowed origins in the backend
3. **Authentication**: Implement proper user authentication
4. **Rate Limiting**: Add rate limiting to API endpoints
5. **Error Handling**: Enhance error handling and logging
6. **SSL/TLS**: Use HTTPS for production deployments

## Deployment

For deploying to Azure App Service via VS Code, see the [DEPLOYMENT.md](DEPLOYMENT.md) guide.

## License

MIT
