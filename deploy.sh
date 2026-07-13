#!/usr/bin/env bash
set -euo pipefail

# Headless Agent Swarm - Server Deployment Script
# Run on your Contabo VPS (161.97.64.179) after SSH access is configured

REPO_URL="https://github.com/${GITHUB_REPO:-your-org/headless-agent-swarm}.git"
DEPLOY_DIR="/opt/headless-agent"
BRANCH="${BRANCH:-main}"

echo "🚀 Deploying Headless Agent Swarm to $(hostname)"

# ──────────────────────────────────────────────
# Prerequisites
# ──────────────────────────────────────────────
echo "📦 Installing prerequisites..."
apt-get update -qq
apt-get install -y -qq git docker.io docker-compose-plugin curl jq

# Start Docker
systemctl enable --now docker

# ──────────────────────────────────────────────
# Clone / Update Repository
# ──────────────────────────────────────────────
if [[ -d "$DEPLOY_DIR/.git" ]]; then
    echo "🔄 Updating existing deployment..."
    cd "$DEPLOY_DIR"
    git fetch origin
    git checkout "$BRANCH"
    git pull origin "$BRANCH"
else
    echo "📥 Cloning repository..."
    git clone -b "$BRANCH" "$REPO_URL" "$DEPLOY_DIR"
    cd "$DEPLOY_DIR"
fi

# ──────────────────────────────────────────────
# Environment Setup
# ──────────────────────────────────────────────
echo "⚙️  Setting up environment..."
cat > .env << ENVEOF
REDIS_URL=redis://redis:6379/0
LOG_LEVEL=INFO
MAX_CONCURRENT_TASKS=10
OPENAI_API_KEY=${OPENAI_API_KEY:-}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
GRAFANA_PASSWORD=${GRAFANA_PASSWORD:-$(openssl rand -base64 16)}
ENVEOF

# ──────────────────────────────────────────────
# Build & Start
# ──────────────────────────────────────────────
echo "🔨 Building containers..."
docker compose -f docker-compose.yml build --pull

echo "🚀 Starting services..."
docker compose -f docker-compose.yml up -d

# ──────────────────────────────────────────────
# Health Check
# ──────────────────────────────────────────────
echo "🏥 Waiting for health checks..."
sleep 10

for i in {1..30}; do
    if curl -sf http://localhost:8000/health > /dev/null; then
        echo "✅ Backend healthy"
        break
    fi
    echo "⏳ Waiting... ($i/30)"
    sleep 2
done

# ──────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Deployment Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 Backend API:     http://$(curl -s ifconfig.me):8000"
echo "📊 PWA Dashboard:   http://$(curl -s ifconfig.me):3000"
echo "📈 Prometheus:      http://$(curl -s ifconfig.me):9090"
echo "📊 Grafana:         http://$(curl -s ifconfig.me):3001 (admin / \$GRAFANA_PASSWORD)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Useful commands:"
echo "   docker compose logs -f           # View logs"
echo "   docker compose ps                # Service status"
echo "   docker compose restart           # Restart all"
echo "   docker compose down && ./deploy.sh  # Full redeploy"
