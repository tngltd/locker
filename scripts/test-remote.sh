#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Configuration
REMOTE_HOST="192.168.155.129"
REMOTE_USER="user"
REMOTE_PASS="user"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Check dependencies
if ! command -v sshpass &> /dev/null; then
    log_error "sshpass is required. Install with: brew install hudochenkov/sshpass/sshpass"
    exit 1
fi

# SSH command with password
SSH_CMD() {
    sshpass -p "$REMOTE_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$REMOTE_USER@$REMOTE_HOST" "$@"
}

SCP_CMD() {
    sshpass -p "$REMOTE_PASS" scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$@"
}

log_info "Testing package installation on remote Ubuntu machine ($REMOTE_USER@$REMOTE_HOST)..."

# Step 1: Build the package locally
log_info "Step 1: Building Debian package..."
if ! ./scripts/build-with-docker.sh >/dev/null 2>&1; then
    log_error "Package build failed"
    ./scripts/build-with-docker.sh 2>&1 | tail -20
    exit 1
fi

# Find the built package
DEB_FILE=$(find "$PROJECT_DIR" -maxdepth 1 -name "lock-service_*.deb" -type f | head -1)

if [ -z "$DEB_FILE" ] || [ ! -f "$DEB_FILE" ]; then
    log_error "Package file not found"
    exit 1
fi

log_success "Package built: $(basename "$DEB_FILE")"

# Step 2: Upload package to remote machine
log_info "Step 2: Uploading package to remote machine..."
SCP_CMD "$DEB_FILE" "$REMOTE_USER@$REMOTE_HOST:/tmp/" || {
    log_error "Failed to upload package"
    exit 1
}
log_success "Package uploaded to /tmp/$(basename "$DEB_FILE")"

# Step 3: Install package on remote machine
log_info "Step 3: Installing package on remote machine..."
REMOTE_DEB="/tmp/$(basename "$DEB_FILE")"

# Uninstall old version if exists
SSH_CMD "echo '$REMOTE_PASS' | sudo -S dpkg -r lock-service 2>/dev/null || true" || true
SSH_CMD "echo '$REMOTE_PASS' | sudo -S apt-get purge -y lock-service 2>/dev/null || true" || true

# Install new package
if ! SSH_CMD "echo '$REMOTE_PASS' | sudo -S apt-get install -y $REMOTE_DEB"; then
    log_error "Package installation failed"
    log_info "Attempting to fix dependencies..."
    SSH_CMD "echo '$REMOTE_PASS' | sudo -S apt-get install -f -y" || true
    if ! SSH_CMD "echo '$REMOTE_PASS' | sudo -S apt-get install -y $REMOTE_DEB"; then
        log_error "Package installation failed after fixing dependencies"
        exit 1
    fi
fi
log_success "Package installed successfully!"

# Step 4: Test lock-cli list-devices returns exit code 0
log_info "Step 4: Testing lock-cli list-devices returns exit code 0..."
EXIT_CODE=$(SSH_CMD "lock-cli list-devices >/dev/null 2>&1; echo \$?" || echo "failed")

if [ "$EXIT_CODE" = "0" ]; then
    log_success "✓ lock-cli list-devices returns exit code 0"
else
    log_error "✗ lock-cli list-devices failed with exit code: $EXIT_CODE"
    log_error "Full error output:"
    SSH_CMD "lock-cli list-devices 2>&1" || true
    
    # Debug information
    log_info "Debug information:"
    log_info "Python version:"
    SSH_CMD "python3 --version" || true
    log_info "Python executable:"
    SSH_CMD "python3 -c 'import sys; print(sys.executable)'" || true
    log_info "Python sys.path:"
    SSH_CMD "python3 -c 'import sys; print(\"\\n\".join(sys.path))'" || true
    log_info "lock-cli location:"
    SSH_CMD "which lock-cli || echo 'not in PATH'" || true
    log_info "lock-cli file:"
    SSH_CMD "ls -la /usr/bin/lock-cli 2>/dev/null || echo 'file not found'" || true
    log_info "lock-cli content (first 10 lines):"
    SSH_CMD "head -10 /usr/bin/lock-cli 2>/dev/null || echo 'cannot read file'" || true
    log_info "Python package location:"
    SSH_CMD "find /usr/lib/python* -name 'lock_service' -type d 2>/dev/null || echo 'package not found'" || true
    log_info "Python import test:"
    SSH_CMD "python3 -c 'import lock_service; print(\"Import OK\")' 2>&1 || echo 'import failed'" || true
    
    exit 1
fi

log_success "All tests passed!"
log_info "Package is working correctly on remote machine"
