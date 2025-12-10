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
VM_PATH="/Users/shaked/Virtual Machines.localized/Ubuntu 64-bit Arm Server 24.04.3.vmwarevm/Ubuntu 64-bit Arm Server 24.04.3.vmx"
SNAPSHOT_NAME="with-ssh"
VMRUN="/Applications/VMware Fusion.app/Contents/Public/vmrun"

# SSH command (using SSH keys, no password needed)
SSH_CMD() {
    ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$REMOTE_USER@$REMOTE_HOST" "$@"
}

SCP_CMD() {
    scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$@"
}

log_info "Testing package installation on remote Ubuntu machine ($REMOTE_USER@$REMOTE_HOST)..."

# Step 0: Revert VM to snapshot
if [ -f "$VMRUN" ] && [ -f "$VM_PATH" ]; then
    log_info "Step 0: Reverting VM to snapshot '$SNAPSHOT_NAME'..."
    
    # Check VM state and stop if running
    VM_STATE=$("$VMRUN" list | grep "$VM_PATH" || echo "")
    if echo "$VM_STATE" | grep -q "running"; then
        log_info "VM is running, stopping it..."
        "$VMRUN" stop "$VM_PATH" hard || {
            log_warning "Failed to stop VM, trying soft stop..."
            "$VMRUN" stop "$VM_PATH" soft || {
                log_error "Failed to stop VM"
                exit 1
            }
        }
        sleep 2
    elif echo "$VM_STATE" | grep -q "suspended"; then
        log_info "VM is suspended, stopping it..."
        "$VMRUN" stop "$VM_PATH" hard || {
            log_error "Failed to stop suspended VM"
            exit 1
        }
        sleep 2
    fi
    
    # Revert to snapshot
    if ! "$VMRUN" revertToSnapshot "$VM_PATH" "$SNAPSHOT_NAME"; then
        log_error "Failed to revert to snapshot '$SNAPSHOT_NAME'"
        log_info "Available snapshots:"
        "$VMRUN" listSnapshots "$VM_PATH" || true
        exit 1
    fi
    log_success "VM reverted to snapshot '$SNAPSHOT_NAME'"
    
    # Start the VM
    log_info "Starting VM..."
    if ! "$VMRUN" start "$VM_PATH" nogui; then
        log_error "Failed to start VM"
        exit 1
    fi
    log_success "VM started"
    
    # Wait for SSH to be available
    log_info "Waiting for SSH to be available..."
    MAX_WAIT=60
    WAIT_COUNT=0
    while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
        if ssh -o ConnectTimeout=2 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$REMOTE_USER@$REMOTE_HOST" "echo 'SSH ready'" >/dev/null 2>&1; then
            log_success "SSH is available"
            break
        fi
        WAIT_COUNT=$((WAIT_COUNT + 1))
        if [ $((WAIT_COUNT % 5)) -eq 0 ]; then
            log_info "Still waiting for SSH... (${WAIT_COUNT}/${MAX_WAIT} seconds)"
        fi
        sleep 1
    done
    
    if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
        log_error "SSH did not become available within $MAX_WAIT seconds"
        exit 1
    fi
else
    log_warning "VM tools not found, skipping VM revert (assuming VM is already running)"
fi

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
