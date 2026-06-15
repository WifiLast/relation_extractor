#!/bin/bash

# Z3 Backend MCP Service Management Script
# Use this script to manage the z3-backend-mcp service

SERVICE_NAME="z3-backend-mcp"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_info() {
    echo -e "${YELLOW}[i]${NC} $1"
}

case "$1" in
    start)
        print_info "Starting $SERVICE_NAME..."
        sudo systemctl start "$SERVICE_NAME"
        sleep 1
        sudo systemctl status "$SERVICE_NAME" --no-pager
        ;;
    stop)
        print_info "Stopping $SERVICE_NAME..."
        sudo systemctl stop "$SERVICE_NAME"
        sleep 1
        sudo systemctl status "$SERVICE_NAME" --no-pager
        ;;
    restart)
        print_info "Restarting $SERVICE_NAME..."
        sudo systemctl restart "$SERVICE_NAME"
        sleep 2
        sudo systemctl status "$SERVICE_NAME" --no-pager
        ;;
    status)
        print_info "Service status:"
        sudo systemctl status "$SERVICE_NAME" --no-pager
        ;;
    logs)
        print_info "Following service logs (Ctrl+C to exit)..."
        echo ""
        sudo journalctl -u "$SERVICE_NAME" -f
        ;;
    logs-tail)
        print_info "Last 50 lines of service logs:"
        echo ""
        sudo journalctl -u "$SERVICE_NAME" -n 50 --no-pager
        ;;
    enable)
        print_info "Enabling $SERVICE_NAME to start on boot..."
        sudo systemctl enable "$SERVICE_NAME"
        print_status "Service enabled"
        ;;
    disable)
        print_info "Disabling $SERVICE_NAME from starting on boot..."
        sudo systemctl disable "$SERVICE_NAME"
        print_status "Service disabled"
        ;;
    reload)
        print_info "Reloading systemd daemon..."
        sudo systemctl daemon-reload
        print_status "Daemon reloaded"
        ;;
    check)
        print_info "Checking service health..."
        echo ""

        # Check if service is enabled
        if systemctl is-enabled "$SERVICE_NAME" &> /dev/null; then
            print_status "Service is enabled (starts on boot)"
        else
            print_error "Service is NOT enabled"
        fi

        # Check if service is running
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            print_status "Service is RUNNING"
        else
            print_error "Service is NOT running"
        fi

        # Check if port is listening
        if netstat -tln 2>/dev/null | grep -q ":5000 "; then
            print_status "Port 5000 is LISTENING"
        else
            print_error "Port 5000 is NOT listening"
        fi

        echo ""
        sudo systemctl status "$SERVICE_NAME" --no-pager
        ;;
    *)
        echo "Z3 Backend MCP Service Management"
        echo ""
        echo "Usage: $0 {start|stop|restart|status|logs|logs-tail|enable|disable|reload|check}"
        echo ""
        echo "Commands:"
        echo "  start       - Start the service"
        echo "  stop        - Stop the service"
        echo "  restart     - Restart the service"
        echo "  status      - Show service status"
        echo "  logs        - Follow service logs (real-time)"
        echo "  logs-tail   - Show last 50 lines of logs"
        echo "  enable      - Enable service on boot"
        echo "  disable     - Disable service on boot"
        echo "  reload      - Reload systemd configuration"
        echo "  check       - Check service health"
        echo ""
        exit 1
        ;;
esac
