#!/bin/bash
# Start MiroThinker HTTP API Server

set -e

cd "$(dirname "$0")"

echo "🚀 Starting MiroThinker HTTP API Server..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found!"
    echo "Please copy .env.example to .env and configure your API keys:"
    echo "  cp .env.example .env"
    echo "Then edit .env with your actual API keys."
    exit 1
fi

# Install dependencies if needed
echo "📦 Installing dependencies..."
uv sync

# Start server
echo "🌐 Starting server on http://localhost:8080"
echo "📚 API Documentation: http://localhost:8080/docs"
echo ""
uv run python main.py "$@"
