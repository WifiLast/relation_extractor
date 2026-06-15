#!/bin/bash

# Z3 Backend MCP Server - Linux Service Installation Script
# This script installs the z3_backend.py as a systemd service on Linux

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SERVICE_NAME="z3-backend-mcp"
SERVICE_DESC="Z3 Backend MCP Server"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_EXECUTABLE=$(which python3)
USER="${SUDO_USER:-$USER}"

# Print colored output
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_info() {
    echo -e "${YELLOW}[i]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root"
        echo "Run: sudo bash install_z3_service.sh"
        exit 1
    fi
}

# Check dependencies
check_dependencies() {
    print_info "Checking dependencies..."

    if ! command -v python3 &> /dev/null; then
        print_error "python3 is not installed"
        exit 1
    fi
    print_status "python3 found: $PYTHON_EXECUTABLE"

    if ! command -v systemctl &> /dev/null; then
        print_error "systemd is not available"
        exit 1
    fi
    print_status "systemd found"
}

# Check Python dependencies
check_python_deps() {
    print_info "Checking Python dependencies..."

    local missing_deps=()

    for package in z3 nltk mcp; do
        if ! python3 -c "import $package" 2>/dev/null; then
            missing_deps+=("$package")
        else
            print_status "$package is installed"
        fi
    done

    if [ ${#missing_deps[@]} -ne 0 ]; then
        print_warning "Missing Python packages: ${missing_deps[*]}"
        print_info "Install with: pip3 install ${missing_deps[*]}"
        read -p "Continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Create systemd service file
create_service_file() {
    print_info "Creating systemd service file..."

    local service_file="/etc/systemd/system/${SERVICE_NAME}.service"

    cat > "$service_file" << EOF
[Unit]
Description=${SERVICE_DESC}
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=${USER}
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${PYTHON_EXECUTABLE} ${SCRIPT_DIR}/z3_backend.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
EOF

    print_status "Service file created at: $service_file"
}

# Create log rotation config
create_logrotate_config() {
    print_info "Creating log rotation config..."

    local logrotate_file="/etc/logrotate.d/${SERVICE_NAME}"

    cat > "$logrotate_file" << 'EOF'
/var/log/z3-backend-mcp.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 root root
}
EOF

    print_status "Log rotation config created at: $logrotate_file"
}

# Enable and start service
enable_service() {
    print_info "Enabling and starting service..."

    systemctl daemon-reload
    systemctl enable "${SERVICE_NAME}"
    systemctl start "${SERVICE_NAME}"

    print_status "Service enabled and started"
}

# Create helper script for management
create_management_script() {
    print_info "Creating management script..."

    local mgmt_script="${SCRIPT_DIR}/manage_z3_service.sh"

    cat > "$mgmt_script" << 'EOF'
#!/bin/bash

# Z3 Backend MCP Service Management Script

SERVICE_NAME="z3-backend-mcp"

case "$1" in
    start)
        echo "Starting $SERVICE_NAME..."
        sudo systemctl start "$SERVICE_NAME"
        sudo systemctl status "$SERVICE_NAME" --no-pager
        ;;
    stop)
        echo "Stopping $SERVICE_NAME..."
        sudo systemctl stop "$SERVICE_NAME"
        ;;
    restart)
        echo "Restarting $SERVICE_NAME..."
        sudo systemctl restart "$SERVICE_NAME"
        sudo systemctl status "$SERVICE_NAME" --no-pager
        ;;
    status)
        sudo systemctl status "$SERVICE_NAME" --no-pager
        ;;
    logs)
        sudo journalctl -u "$SERVICE_NAME" -f
        ;;
    enable)
        echo "Enabling $SERVICE_NAME to start on boot..."
        sudo systemctl enable "$SERVICE_NAME"
        ;;
    disable)
        echo "Disabling $SERVICE_NAME from starting on boot..."
        sudo systemctl disable "$SERVICE_NAME"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|enable|disable}"
        exit 1
        ;;
esac
EOF

    chmod +x "$mgmt_script"
    print_status "Management script created at: $mgmt_script"
}

# Verify service installation
verify_installation() {
    print_info "Verifying installation..."

    if systemctl is-enabled "${SERVICE_NAME}" &> /dev/null; then
        print_status "Service is enabled"
    fi

    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        print_status "Service is running"
    else
        print_warning "Service is not running yet"
    fi
}

# Print summary
print_summary() {
    echo ""
    echo "=============================================="
    echo "Installation Complete!"
    echo "=============================================="
    echo ""
    echo "Service Name: ${SERVICE_NAME}"
    echo "Service File: /etc/systemd/system/${SERVICE_NAME}.service"
    echo "Working Directory: ${SCRIPT_DIR}"
    echo "User: ${USER}"
    echo "Port: 5000"
    echo ""
    echo "=============================================="
    echo "Usage:"
    echo "=============================================="
    echo ""
    echo "Using systemctl:"
    echo "  sudo systemctl start ${SERVICE_NAME}"
    echo "  sudo systemctl stop ${SERVICE_NAME}"
    echo "  sudo systemctl restart ${SERVICE_NAME}"
    echo "  sudo systemctl status ${SERVICE_NAME}"
    echo "  sudo systemctl enable/disable ${SERVICE_NAME}"
    echo ""
    echo "Using management script:"
    echo "  ${SCRIPT_DIR}/manage_z3_service.sh start"
    echo "  ${SCRIPT_DIR}/manage_z3_service.sh stop"
    echo "  ${SCRIPT_DIR}/manage_z3_service.sh restart"
    echo "  ${SCRIPT_DIR}/manage_z3_service.sh status"
    echo "  ${SCRIPT_DIR}/manage_z3_service.sh logs"
    echo ""
    echo "View logs:"
    echo "  sudo journalctl -u ${SERVICE_NAME} -f"
    echo ""
    echo "=============================================="
}

# Main execution
main() {
    echo "Z3 Backend MCP Server - Service Installation"
    echo ""

    check_root
    check_dependencies
    check_python_deps
    create_service_file
    create_logrotate_config
    enable_service
    create_management_script
    verify_installation
    print_summary
}

main
