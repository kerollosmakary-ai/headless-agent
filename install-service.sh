#!/bin/bash
# Install as systemd service (no Docker needed)

SERVICE_NAME="headless-agent"
INSTALL_DIR="/opt/headless-agent"
USER="headless-agent"

# Create user
id -u "$USER" &>/dev/null || useradd -r -s /bin/bash -d "$INSTALL_DIR" "$USER"

# Create dirs
mkdir -p "$INSTALL_DIR"/{backend/app,static,workspace,logs}
chown -R "$USER:$USER" "$INSTALL_DIR"

# Copy files (assuming you're in the repo root)
cp -r backend/app "$INSTALL_DIR/backend/"
cp -r pwa/dist "$INSTALL_DIR/static/"
cp backend/requirements.txt "$INSTALL_DIR/backend/"

# Python venv
cd "$INSTALL_DIR/backend"
sudo -u "$USER" python3 -m venv venv
sudo -u "$USER" venv/bin/pip install -r requirements.txt

# Systemd service
cat > /etc/systemd/system/$SERVICE_NAME.service << SVC_EOF
[Unit]
Description=Headless Agent Swarm
After=network.target redis.service
Wants=redis.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR/backend
Environment=PATH=$INSTALL_DIR/backend/venv/bin
Environment=REDIS_URL=redis://localhost:6379/0
Environment=LOG_LEVEL=INFO
Environment=STATIC_DIR=../static
ExecStart=$INSTALL_DIR/backend/venv/bin/python -m app.main
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SVC_EOF

# Redis service (if not installed)
if ! systemctl list-unit-files | grep -q redis; then
    apt-get update && apt-get install -y redis-server
    systemctl enable --now redis-server
fi

# Enable & start
systemctl daemon-reload
systemctl enable --now $SERVICE_NAME

echo "✅ Service installed! Check status: systemctl status $SERVICE_NAME"
echo "📝 Logs: journalctl -u $SERVICE_NAME -f"
