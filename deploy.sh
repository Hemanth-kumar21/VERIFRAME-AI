#!/usr/bin/env bash
# Veriframe AI - VPS Deployment Helper Script
set -e

echo "============================================="
echo "   Veriframe AI - Production Deployment"
echo "============================================="

# 1. Check Docker & Docker Compose
if ! command -v docker &> /dev/null; then
    echo "⚠️  Docker is not installed. Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER"
    echo "✅ Docker installed successfully."
fi

# 2. Check for .env file
if [ ! -f .env ]; then
    echo "⚠️  No .env file found. Copying .env.example -> .env..."
    cp .env.example .env
    echo "⚠️  Please update .env with your API keys and domain (SERVER_NAME) before running in production!"
fi

# 3. Choose compose file (default: docker-compose.prod.yml with Caddy SSL reverse proxy)
COMPOSE_FILE="docker-compose.prod.yml"

echo "🚀 Building and starting containers with $COMPOSE_FILE..."
docker compose -f "$COMPOSE_FILE" down --remove-orphans || true
docker compose -f "$COMPOSE_FILE" up -d --build

echo "⏳ Waiting for services to become healthy..."
sleep 10

docker compose -f "$COMPOSE_FILE" ps

echo ""
echo "============================================="
echo "✅ Veriframe AI is now running!"
echo "   - Web & API: Port 80 / 443 (managed by Caddy)"
echo "   - View logs: docker compose -f $COMPOSE_FILE logs -f"
echo "   - Stop app:  docker compose -f $COMPOSE_FILE down"
echo "============================================="
