#!/bin/bash
# Lock-Down Service Installation Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SERVICE_NAME="lock-service"
INSTALL_DIR="/usr/local/bin"
CONFIG_DIR="/etc/lock-service"
LOG_DIR="/var/log"
RUN_DIR="/var/run"
SYSTEMD_DIR="/etc/systemd/system"

echo -e "${GREEN}=== Lock-Down Service Installation ===${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: This script must be run as root${NC}"
    exit 1
fi

# Check if systemd is available
if ! command -v systemctl &> /dev/null; then
    echo -e "${RED}Error: systemd is required but not found${NC}"
    exit 1
fi

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not found${NC}"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 6 ]); then
    echo -e "${RED}Error: Python 3.6 or higher is required (found $PYTHON_VERSION)${NC}"
    exit 1
fi

echo -e "${GREEN}✓ System requirements met${NC}"

# Create directories
echo "Creating directories..."
mkdir -p "$CONFIG_DIR"
mkdir -p "$LOG_DIR"
mkdir -p "$RUN_DIR"

# Copy service files
echo "Installing service files..."
cp lock-service.py "$INSTALL_DIR/"
cp lock-cli.py "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/lock-service.py"
chmod +x "$INSTALL_DIR/lock-cli.py"

# Copy configuration files
echo "Installing configuration files..."
cp config/init_config.json "$CONFIG_DIR/config.json"
cp config/security_policies.json "$CONFIG_DIR/"

# Set proper permissions
chmod 644 "$CONFIG_DIR/config.json"
chmod 644 "$CONFIG_DIR/security_policies.json"
chmod 755 "$CONFIG_DIR"

# Create systemd service file
echo "Creating systemd service..."
# Use sed to replace paths in the template
sed -e "s|/usr/local/bin|$INSTALL_DIR|g" \
    -e "s|/etc/lock-service|$CONFIG_DIR|g" \
    -e "s|/var/log|$LOG_DIR|g" \
    -e "s|/var/run|$RUN_DIR|g" \
    "$(dirname "$0")/../config/lock-service.service" > "$SYSTEMD_DIR/lock-service.service"

# Reload systemd and enable service
echo "Configuring systemd service..."
systemctl daemon-reload
systemctl enable lock-service

# Install Python dependencies
echo "Installing Python dependencies..."
python3 -m pip install --upgrade pip --quiet
python3 -m pip install -r requirements.txt --quiet

# Create log rotation configuration
echo "Configuring log rotation..."
cat > /etc/logrotate.d/lock-service << EOF
$LOG_DIR/lock-service.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 root root
    postrotate
        systemctl reload lock-service > /dev/null 2>&1 || true
    endscript
}
EOF

# Set up iptables rules (will be managed by the service)
echo "Configuring firewall rules..."
# Backup existing iptables rules
iptables-save > /etc/iptables/rules.v4.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true

# Create iptables rules directory if it doesn't exist
mkdir -p /etc/iptables

echo -e "${GREEN}✓ Installation completed successfully${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Run 'lock-cli setup' to configure the service"
echo "2. Start the service with 'systemctl start lock-service'"
echo "3. Check status with 'lock-cli status'"
echo ""
echo -e "${YELLOW}Important:${NC}"
echo "- The service will lock the system on startup if a PIN is configured"
echo "- Make sure to complete setup before starting the service"
echo "- Save your recovery code in a secure location"
echo ""
echo -e "${GREEN}Installation complete!${NC}"
