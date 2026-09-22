#!/bin/bash

# Z3 Backend MCP Service Installation Script
# This script installs z3_backend.py as a systemd service on Linux

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SERVICE_NAME="z3-backend-mcp"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONDA_ENV_PATH="/mnt/data/miniconda3/envs/py310_amd"
PYTHON_PATH="$CONDA_ENV_PATH/bin/python"
# Run as the owner of the script directory (typically your own home-dir user)
# rather than a dedicated system account, since a system user cannot traverse
# into another user's home directory to chdir into WorkingDirectory.
SERVICE_USER="$(stat -c '%U' "$SCRIPT_DIR")"
SERVICE_GROUP="$(stat -c '%G' "$SCRIPT_DIR")"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root${NC}"
   exit 1
fi

echo -e "${YELLOW}Installing Z3 Backend MCP as systemd service...${NC}"

# Check that the conda environment's Python exists
if [[ ! -x "$PYTHON_PATH" ]]; then
    echo -e "${RED}Python interpreter not found at $PYTHON_PATH${NC}"
    echo -e "${RED}Make sure the conda env exists at $CONDA_ENV_PATH${NC}"
    exit 1
fi

echo "Running service as existing user: $SERVICE_USER:$SERVICE_GROUP"

# Make sure the script is executable
chmod 755 "$SCRIPT_DIR/z3_backend.py"

# Create systemd service file
echo "Creating systemd service file..."
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Z3 Backend MCP Server
Documentation=https://github.com/anthropics/mcp-servers
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_GROUP
WorkingDirectory=$SCRIPT_DIR
ExecStart=$PYTHON_PATH $SCRIPT_DIR/z3_backend.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=z3-backend-mcp

# Environment variables (customize as needed)
# NOTE: Port/path differ from math-solver-mcp and math-plus-mcp so all
# services can run on the same host at the same time.
Environment="Z3_BACKEND_HOST=0.0.0.0"
Environment="Z3_BACKEND_PORT=2002"
Environment="Z3_BACKEND_PATH=/relation"
Environment="Z3_BACKEND_TRANSPORT=streamable-http"

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=false
ReadWritePaths=$SCRIPT_DIR

[Install]
WantedBy=multi-user.target
EOF

chmod 644 "$SERVICE_FILE"
echo -e "${GREEN}✓ Service file created at $SERVICE_FILE${NC}"

# Reload systemd daemon
echo "Reloading systemd daemon..."
systemctl daemon-reload
echo -e "${GREEN}✓ Systemd reloaded${NC}"

# Enable the service
echo "Enabling service to start on boot..."
systemctl enable "$SERVICE_NAME"
echo -e "${GREEN}✓ Service enabled${NC}"

# Start the service
echo "Starting service..."
systemctl start "$SERVICE_NAME"
echo -e "${GREEN}✓ Service started${NC}"

# Check status
echo ""
echo -e "${YELLOW}Service Status:${NC}"
systemctl status "$SERVICE_NAME" --no-pager

echo ""
echo -e "${GREEN}Installation complete!${NC}"
echo ""
echo -e "${YELLOW}Useful commands:${NC}"
echo "  View logs:          journalctl -u $SERVICE_NAME -f"
echo "  Check status:       systemctl status $SERVICE_NAME"
echo "  Restart service:    systemctl restart $SERVICE_NAME"
echo "  Stop service:       systemctl stop $SERVICE_NAME"
echo "  View config:        cat $SERVICE_FILE"
echo ""
echo "Service is listening on: http://0.0.0.0:2002/relation"
