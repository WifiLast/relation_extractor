# Quick Start - Z3 Backend MCP Service

## 30-Second Installation

```bash
# 1. Make scripts executable
chmod +x install_z3_service.sh manage_z3_service.sh

# 2. Install the service (requires sudo password)
sudo bash install_z3_service.sh

# 3. Service is now running!
```

## Verify It's Working

```bash
# Check service status
./manage_z3_service.sh check

# View logs
./manage_z3_service.sh logs
```

## Common Commands

| Command | Description |
|---------|-------------|
| `./manage_z3_service.sh start` | Start service |
| `./manage_z3_service.sh stop` | Stop service |
| `./manage_z3_service.sh restart` | Restart service |
| `./manage_z3_service.sh status` | Show status |
| `./manage_z3_service.sh logs` | View live logs |
| `./manage_z3_service.sh check` | Health check |

## Test the Server

```bash
# In a new terminal
curl -X POST http://localhost:5000/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'
```

## Default Settings

- **Service Name**: z3-backend-mcp
- **Port**: 5000
- **Host**: 0.0.0.0 (all interfaces)
- **Auto-start**: Yes (enabled)

## Need Help?

See `SERVICE_INSTALLATION.md` for detailed documentation.

## Uninstall

```bash
sudo systemctl stop z3-backend-mcp
sudo systemctl disable z3-backend-mcp
sudo rm /etc/systemd/system/z3-backend-mcp.service
sudo systemctl daemon-reload
```
