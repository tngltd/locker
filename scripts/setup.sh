#!/bin/bash
# Lock-Down Service Setup Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Lock-Down Service Setup ===${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: This script must be run as root${NC}"
    exit 1
fi

# Check if lock-cli is available
if ! command -v lock-cli &> /dev/null; then
    echo -e "${RED}Error: lock-cli not found. Please install the service first.${NC}"
    exit 1
fi

echo -e "${BLUE}This script will help you set up the Lock-Down Service.${NC}"
echo -e "${YELLOW}The service will lock your system when no Android device is connected.${NC}"
echo ""

# Ask for confirmation
read -p "Do you want to continue with the setup? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Setup cancelled."
    exit 0
fi

echo ""
echo -e "${BLUE}Step 1: Initial Configuration${NC}"
echo "This will set up your PIN and generate a recovery code."
echo ""

# Run the setup command
lock-cli setup

echo ""
echo -e "${BLUE}Step 2: Service Configuration${NC}"

# Ask if user wants to start the service
read -p "Do you want to start the Lock-Down Service now? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Starting the service..."
    systemctl start lock-service
    
    # Wait a moment for service to start
    sleep 2
    
    # Check if service is running
    if systemctl is-active --quiet lock-service; then
        echo -e "${GREEN}✓ Service started successfully${NC}"
    else
        echo -e "${RED}✗ Failed to start service${NC}"
        echo "Check the logs with: journalctl -u lock-service"
    fi
else
    echo "Service not started. You can start it later with: systemctl start lock-service"
fi

echo ""
echo -e "${BLUE}Step 3: Testing Setup${NC}"

# Show current status
echo "Current service status:"
lock-cli status

echo ""
echo -e "${GREEN}=== Setup Complete ===${NC}"
echo ""
echo -e "${YELLOW}Important Information:${NC}"
echo "• Your system is now configured with the Lock-Down Service"
echo "• The service will automatically lock the system when no Android device is connected"
echo "• To unlock, connect your Android device and enter your PIN"
echo "• If you lose your Android device, use the recovery code for emergency unlock"
echo "• You can change your PIN anytime with: lock-cli change-pin"
echo ""
echo -e "${YELLOW}Useful Commands:${NC}"
echo "• Check status: lock-cli status"
echo "• View logs: lock-cli logs"
echo "• Emergency unlock: lock-cli emergency-unlock"
echo "• Change PIN: lock-cli change-pin"
echo "• Start service: systemctl start lock-service"
echo "• Stop service: systemctl stop lock-service"
echo ""
echo -e "${GREEN}Setup completed successfully!${NC}"
