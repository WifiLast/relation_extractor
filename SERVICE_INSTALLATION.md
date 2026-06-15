# Z3 Backend MCP - Linux Service Installation

This guide explains how to install and manage the Z3 Backend MCP server as a Linux systemd service.

## Prerequisites

- Linux system with systemd
- Python 3.7+
- Required Python packages: `z3-solver`, `nltk`, `mcp`

## Installation Steps

### 1. Install Python Dependencies

```bash
pip3 install z3-solver nltk mcp
```

### 2. Make Scripts Executable

```bash
chmod +x install_z3_service.sh
chmod +x manage_z3_service.sh
```

### 3. Run Installation Script (as root)

```bash
sudo bash install_z3_service.sh
```

This script will:
- ✅ Check system dependencies
- ✅ Verify Python environment
- ✅ Create systemd service file
- ✅ Create log rotation configuration
- ✅ Enable and start the service
- ✅ Create a management script
- ✅ Verify installation

### Expected Output

```
============================================
Installation Complete!
============================================

Service Name: z3-backend-mcp
Service File: /etc/systemd/system/z3-backend-mcp.service
Working Directory: /path/to/relation_extractor
User: your-username
Port: 5000
```

## Managing the Service

### Using Management Script (Recommended)

```bash
# Start the service
./manage_z3_service.sh start

# Stop the service
./manage_z3_service.sh stop

# Restart the service
./manage_z3_service.sh restart

# Check service status
./manage_z3_service.sh status

# View live logs
./manage_z3_service.sh logs

# View last 50 lines of logs
./manage_z3_service.sh logs-tail

# Enable service on boot
./manage_z3_service.sh enable

# Disable service on boot
./manage_z3_service.sh disable

# Check service health
./manage_z3_service.sh check
```

### Using systemctl Directly

```bash
# Start
sudo systemctl start z3-backend-mcp

# Stop
sudo systemctl stop z3-backend-mcp

# Restart
sudo systemctl restart z3-backend-mcp

# Status
sudo systemctl status z3-backend-mcp

# Enable on boot
sudo systemctl enable z3-backend-mcp

# Disable on boot
sudo systemctl disable z3-backend-mcp

# View logs
sudo journalctl -u z3-backend-mcp -f

# View last 50 lines
sudo journalctl -u z3-backend-mcp -n 50
```

## Verification

### Check if Service is Running

```bash
./manage_z3_service.sh check
```

### Check Port

```bash
# Port 5000 should be listening
netstat -tln | grep 5000
# or
lsof -i :5000
```

### Test MCP Server

```bash
# Query a tool
curl -X POST http://localhost:5000/tools \
  -H "Content-Type: application/json" \
  -d '{"name": "get_status"}'
```

## Service Details

### Service File Location
```
/etc/systemd/system/z3-backend-mcp.service
```

### Service Configuration
- **Type**: simple
- **User**: Your username
- **WorkingDirectory**: Script directory
- **Port**: 5000
- **Restart**: Always (with 10-second delay)
- **Logging**: systemd journal

### Log Files

View service logs:
```bash
# Follow live logs
sudo journalctl -u z3-backend-mcp -f

# View today's logs
sudo journalctl -u z3-backend-mcp --since today

# View last 100 lines
sudo journalctl -u z3-backend-mcp -n 100
```

## Troubleshooting

### Service Won't Start

Check logs for errors:
```bash
./manage_z3_service.sh logs-tail
```

Check service status:
```bash
sudo systemctl status z3-backend-mcp
```

### Port Already in Use

If port 5000 is already in use:
```bash
# Find what's using port 5000
sudo lsof -i :5000

# Kill the process (if needed)
sudo kill -9 <PID>
```

### Python Dependencies Missing

```bash
# Install all required packages
pip3 install z3-solver nltk mcp

# Verify installation
python3 -c "import z3; import nltk; import mcp; print('All packages OK')"
```

### Permission Denied

If you get permission errors, ensure the script is executable:
```bash
chmod +x manage_z3_service.sh
chmod +x install_z3_service.sh
```

## Uninstallation

To remove the service:

```bash
# Stop the service
sudo systemctl stop z3-backend-mcp

# Disable the service
sudo systemctl disable z3-backend-mcp

# Remove service file
sudo rm /etc/systemd/system/z3-backend-mcp.service

# Remove log rotation config
sudo rm /etc/logrotate.d/z3-backend-mcp

# Reload systemd
sudo systemctl daemon-reload
```

## Auto-Start on Boot

The service is enabled by default after installation. To verify:

```bash
./manage_z3_service.sh status
```

Look for "Loaded: loaded (.../z3-backend-mcp.service; **enabled**; ..."

## Environment Variables

The service runs with:
- `PYTHONUNBUFFERED=1` - Unbuffered Python output for real-time logs

To add more environment variables, edit the service file:
```bash
sudo nano /etc/systemd/system/z3-backend-mcp.service
```

## Security Considerations

1. **User Privileges**: Service runs as your user, not root
2. **Port Access**: Port 5000 is accessible on all interfaces (0.0.0.0)
3. **Firewall**: Consider restricting access:
   ```bash
   sudo ufw allow from 192.168.1.0/24 to any port 5000
   ```

## Additional Resources

- [systemd Documentation](https://www.freedesktop.org/software/systemd/man/)
- [journalctl Manual](https://www.freedesktop.org/software/systemd/man/journalctl.html)
- [MCP Documentation](https://modelcontextprotocol.io/)
