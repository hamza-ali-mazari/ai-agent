#!/bin/bash
# AI Code Review Engine - Deployment Script

echo "🚀 Starting AI Code Review Engine..."

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Copying from .env.example..."
    cp .env.example .env
    echo "✏️  Please edit .env file with your API keys and tokens"
fi

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Run the main API server
echo "🌐 Starting main API server on port 8000..."
uvicorn app:app --reload --host 0.0.0.0 --port 8000 &

# Run GitHub integration (if configured)
if [ ! -z "$GITHUB_TOKEN" ]; then
    echo "🐙 Starting GitHub integration on port 8001..."
    python integrations/github_integration.py &
fi

# Run Bitbucket integration (if configured)
if [ ! -z "$BITBUCKET_USERNAME" ] || [ ! -z "$BITBUCKET_TOKEN" ]; then
    echo "🐺 Starting Bitbucket integration on port 8002..."
    python integrations/bitbucket_integration.py &
fi

echo "✅ All services started!"
echo ""
echo "📋 Service URLs:"
echo "  Main API: http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
if [ ! -z "$GITHUB_TOKEN" ]; then
    echo "  GitHub Integration: http://localhost:8001"
fi
if [ ! -z "$BITBUCKET_USERNAME" ] || [ ! -z "$BITBUCKET_TOKEN" ]; then
    echo "  Bitbucket Integration: http://localhost:8002"
fi

echo ""
echo "🛑 Press Ctrl+C to stop all services"

# Wait for all background processes
wait