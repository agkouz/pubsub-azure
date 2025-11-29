#!/bin/bash

# Azure PubSub Project Startup Script

echo "🚀 Starting Azure PubSub Demo Project"
echo "======================================"
echo ""

# Check if .env exists in backend
if [ ! -f "backend/.env" ]; then
    echo "⚠️  Warning: backend/.env file not found!"
    echo "Please create it from backend/.env.example and add your Azure connection string"
    echo ""
    read -p "Press Enter to continue anyway or Ctrl+C to exit..."
fi

# Start backend
echo "📦 Starting Backend (FastAPI)..."
cd backend
python3 -m venv venv 2>/dev/null || true
source venv/bin/activate 2>/dev/null || . venv/Scripts/activate 2>/dev/null
pip install -q -r requirements.txt
python main.py &
BACKEND_PID=$!
cd ..

echo "✅ Backend started (PID: $BACKEND_PID)"
echo ""

# Wait for backend to be ready
sleep 3

# Start frontend
echo "🎨 Starting Frontend (React)..."
cd frontend
npm install
npm start &
FRONTEND_PID=$!
cd ..

echo "✅ Frontend started (PID: $FRONTEND_PID)"
echo ""
echo "======================================"
echo "🎉 Both servers are running!"
echo ""
echo "📍 Backend:  http://localhost:8000"
echo "📍 Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both servers"
echo "======================================"

# Wait for Ctrl+C
trap "echo ''; echo '🛑 Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT
wait
