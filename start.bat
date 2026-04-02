@echo off
REM AI Code Review Engine - Windows Deployment Script

echo 🚀 Starting AI Code Review Engine...

REM Check if .env file exists
if not exist ".env" (
    echo ⚠️  .env file not found. Copying from .env.example...
    copy .env.example .env
    echo ✏️  Please edit .env file with your API keys and tokens
)

REM Install dependencies
echo 📦 Installing dependencies...
pip install -r requirements.txt

REM Run the main API server
echo 🌐 Starting main API server on port 8000...
start "Main API" uvicorn app:app --reload --host 0.0.0.0 --port 8000

REM Run GitHub integration (if configured)
if defined GITHUB_TOKEN (
    echo 🐙 Starting GitHub integration on port 8001...
    start "GitHub Integration" python integrations/github_integration.py
)

REM Run Bitbucket integration (if configured)
if defined BITBUCKET_USERNAME (
    echo 🐺 Starting Bitbucket integration on port 8002...
    start "Bitbucket Integration" python integrations/bitbucket_integration.py
) else if defined BITBUCKET_TOKEN (
    echo 🐺 Starting Bitbucket integration on port 8002...
    start "Bitbucket Integration" python integrations/bitbucket_integration.py
)

echo ✅ All services started!
echo.
echo 📋 Service URLs:
echo   Main API: http://localhost:8000
echo   API Docs: http://localhost:8000/docs
if defined GITHUB_TOKEN echo   GitHub Integration: http://localhost:8001
if defined BITBUCKET_USERNAME echo   Bitbucket Integration: http://localhost:8002
if defined BITBUCKET_TOKEN echo   Bitbucket Integration: http://localhost:8002

echo.
echo 🛑 Close the command windows to stop services
pause