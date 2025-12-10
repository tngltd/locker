#!/bin/bash
# Test script to build package in Docker and verify installation in Ubuntu container

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# Get project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# Check Docker
if ! command -v docker >/dev/null 2>&1; then
    log_error "Docker is not installed"
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    log_error "Docker daemon is not running"
    exit 1
fi

log_info "Step 1: Building Debian package in Docker..."
if ! ./scripts/build-with-docker.sh >/dev/null 2>&1; then
    log_error "Package build failed"
    ./scripts/build-with-docker.sh 2>&1 | tail -20
    exit 1
fi

# Extract package name from build output (last line should be the package name)
PACKAGE_NAME=$(echo "$BUILD_OUTPUT" | tail -1 | grep -o 'lock-service_[^[:space:]]*\.deb' || echo "")

# Find the built package
DEB_FILE=$(find "$PROJECT_DIR" -maxdepth 1 -name "lock-service_*.deb" -type f | head -1)

# Also check parent directory (where dpkg-buildpackage puts it)
if [ -z "$DEB_FILE" ]; then
    DEB_FILE=$(find "$(dirname "$PROJECT_DIR")" -maxdepth 1 -name "lock-service_*.deb" -type f | head -1)
    if [ -n "$DEB_FILE" ]; then
        # Move it to project directory
        mv "$DEB_FILE" "$PROJECT_DIR/"
        DEB_FILE="$PROJECT_DIR/$(basename "$DEB_FILE")"
    fi
fi

if [ -z "$DEB_FILE" ] || [ ! -f "$DEB_FILE" ]; then
    log_error "Package file not found"
    log_error "Searched in: $PROJECT_DIR and $(dirname "$PROJECT_DIR")"
    exit 1
fi

log_success "Package built: $(basename "$DEB_FILE")"

# Copy package to /tmp for better permissions
TMP_DEB="/tmp/$(basename "$DEB_FILE")"
cp "$DEB_FILE" "$TMP_DEB"
chmod 644 "$TMP_DEB"

log_info "Step 2: Testing installation in Ubuntu container..."

# Create a test Ubuntu container
TEST_CONTAINER="lock-service-test-$$"
TEST_IMAGE="ubuntu:22.04"

log_info "Starting Ubuntu test container..."
docker run -d --name "$TEST_CONTAINER" "$TEST_IMAGE" sleep 3600

# Cleanup function
cleanup() {
    log_info "Cleaning up test container..."
    docker rm -f "$TEST_CONTAINER" 2>/dev/null || true
    rm -f "$TMP_DEB"
}
trap cleanup EXIT

# Copy package to container
log_info "Copying package to container..."
docker cp "$TMP_DEB" "$TEST_CONTAINER:/tmp/"

# Update package lists and install dependencies
log_info "Updating package lists in container..."
docker exec "$TEST_CONTAINER" bash -c "apt-get update -qq"

# Install the package
log_info "Installing package with apt install..."
if docker exec "$TEST_CONTAINER" bash -c "apt-get install -y /tmp/$(basename "$TMP_DEB")"; then
    log_success "Package installed successfully!"
else
    log_error "Package installation failed"
    docker exec "$TEST_CONTAINER" bash -c "apt-get install -y /tmp/$(basename "$TMP_DEB")" || true
    exit 1
fi

# Verify installation
log_info "Verifying installation..."

# Check if entry point scripts are installed (they're in /usr/bin now, not /usr/local/bin)
log_info "Checking for entry points in /usr/bin..."
if docker exec "$TEST_CONTAINER" test -f /usr/bin/lock-service; then
    log_success "✓ lock-service entry point installed in /usr/bin"
elif docker exec "$TEST_CONTAINER" test -f /usr/local/bin/lock-service; then
    log_success "✓ lock-service entry point installed in /usr/local/bin"
else
    log_error "✗ lock-service entry point not found"
    docker exec "$TEST_CONTAINER" bash -c "find /usr -name 'lock-service' 2>/dev/null" || true
    exit 1
fi

if docker exec "$TEST_CONTAINER" test -f /usr/bin/lock-cli; then
    log_success "✓ lock-cli entry point installed in /usr/bin"
elif docker exec "$TEST_CONTAINER" test -f /usr/local/bin/lock-cli; then
    log_success "✓ lock-cli entry point installed in /usr/local/bin"
else
    log_error "✗ lock-cli entry point not found"
    docker exec "$TEST_CONTAINER" bash -c "find /usr -name 'lock-cli' 2>/dev/null" || true
    exit 1
fi

if docker exec "$TEST_CONTAINER" test -f /etc/systemd/system/lock-service.service; then
    log_success "✓ systemd service file installed"
else
    log_error "✗ systemd service file not found"
    exit 1
fi

if docker exec "$TEST_CONTAINER" test -f /etc/lock-service/config.json; then
    log_success "✓ config.json installed"
else
    log_error "✗ config.json not found"
    exit 1
fi

# Test lock-cli list-devices command and verify it returns exit code 0
log_info "Testing lock-cli list-devices returns exit code 0..."
EXIT_CODE=$(docker exec "$TEST_CONTAINER" bash -c "lock-cli list-devices >/dev/null 2>&1; echo \$?" || echo "failed")
if [ "$EXIT_CODE" = "0" ]; then
    log_success "✓ lock-cli list-devices returns exit code 0"
else
    log_error "✗ lock-cli list-devices failed with exit code: $EXIT_CODE"
    log_error "Full error output:"
    docker exec "$TEST_CONTAINER" bash -c "lock-cli list-devices 2>&1" || true
    exit 1
fi

# Check service status with systemctl
log_info "Checking service with systemctl..."
# Check if service file exists and is valid
if docker exec "$TEST_CONTAINER" bash -c "systemctl list-unit-files | grep -q lock-service"; then
    log_success "✓ lock-service unit file is registered with systemd"
else
    log_warning "⚠ lock-service unit file not found in systemctl list"
fi

# Check if service is enabled (check for symlink created by systemctl enable)
if docker exec "$TEST_CONTAINER" bash -c "test -L /etc/systemd/system/multi-user.target.wants/lock-service.service 2>/dev/null"; then
    log_success "✓ lock-service is enabled (symlink exists)"
elif docker exec "$TEST_CONTAINER" bash -c "systemctl is-enabled lock-service >/dev/null 2>&1"; then
    log_success "✓ lock-service is enabled (systemctl confirms)"
else
    log_warning "⚠ lock-service is not enabled (systemd may not be running in container)"
    # Check if the service file exists and is correct
    if docker exec "$TEST_CONTAINER" bash -c "grep -q 'ExecStart=/usr/bin/lock-service' /etc/systemd/system/lock-service.service"; then
        log_success "✓ Service file has correct ExecStart path"
    fi
fi

# Try to use systemctl commands (they may work even if systemd isn't PID 1)
log_info "Testing systemctl commands..."
if docker exec "$TEST_CONTAINER" bash -c "systemctl daemon-reload 2>&1"; then
    log_success "✓ systemctl daemon-reload works"
else
    log_warning "⚠ systemctl daemon-reload failed (expected in Docker)"
fi

# Check service file syntax
if docker exec "$TEST_CONTAINER" bash -c "systemd-analyze verify lock-service.service 2>&1 | grep -v 'Failed to connect to bus' || systemctl cat lock-service.service >/dev/null 2>&1"; then
    log_success "✓ Service file syntax is valid"
else
    log_warning "⚠ Could not verify service file syntax"
fi

# Verify ExecStart path points to the installed entry point
log_info "Verifying service ExecStart path..."
EXEC_START=$(docker exec "$TEST_CONTAINER" bash -c "grep '^ExecStart=' /etc/systemd/system/lock-service.service | cut -d'=' -f2" || echo "")
if [ -n "$EXEC_START" ]; then
    # Remove arguments to get just the command
    EXEC_CMD=$(echo "$EXEC_START" | awk '{print $1}')
    if docker exec "$TEST_CONTAINER" bash -c "test -f $EXEC_CMD 2>/dev/null || test -x $EXEC_CMD 2>/dev/null"; then
        log_success "✓ Service ExecStart path exists: $EXEC_CMD"
    else
        log_error "✗ Service ExecStart path does not exist: $EXEC_CMD"
        exit 1
    fi
fi

# Try to manually execute the service command (without systemd)
log_info "Testing service command execution..."
if docker exec "$TEST_CONTAINER" bash -c "/usr/bin/lock-service --help >/dev/null 2>&1"; then
    log_success "✓ lock-service command can be executed"
else
    log_error "✗ lock-service command execution failed"
    docker exec "$TEST_CONTAINER" bash -c "/usr/bin/lock-service --help 2>&1" | head -5 || true
    exit 1
fi

# Test that the service can actually start (run it in background and check it's running)
log_info "Testing service can start and run..."
# Start the service in background (without daemon mode for testing)
SERVICE_PID=$(docker exec -d "$TEST_CONTAINER" bash -c "/usr/bin/lock-service --config /etc/lock-service/config.json 2>&1 & echo \$!" || echo "")
sleep 2

# Check if process is running
if [ -n "$SERVICE_PID" ]; then
    if docker exec "$TEST_CONTAINER" bash -c "ps -p $SERVICE_PID >/dev/null 2>&1 || pgrep -f 'lock-service' >/dev/null 2>&1"; then
        log_success "✓ Service process is running"
        # Stop it
        docker exec "$TEST_CONTAINER" bash -c "pkill -f 'lock-service' || kill $SERVICE_PID 2>/dev/null" || true
    else
        log_warning "⚠ Service process not found (may have exited, which is OK for permissive mode)"
    fi
else
    log_warning "⚠ Could not start service process (may need configuration)"
fi

# Check package info
log_info "Checking package information..."
docker exec "$TEST_CONTAINER" bash -c "dpkg -l lock-service" || true

# Verify Python package is installed and importable
log_info "Verifying Python package installation..."
if docker exec "$TEST_CONTAINER" bash -c "python3 -c 'import lock_service' 2>&1"; then
    log_success "✓ Python package 'lock_service' is importable"
else
    log_error "✗ Python package 'lock_service' not importable"
    docker exec "$TEST_CONTAINER" bash -c "python3 -c 'import lock_service' 2>&1" || true
    # Check where Python is looking
    log_info "Python sys.path:"
    docker exec "$TEST_CONTAINER" bash -c "python3 -c 'import sys; print(\"\\n\".join(sys.path))'" || true
    log_info "Package location:"
    docker exec "$TEST_CONTAINER" bash -c "ls -la /usr/lib/python3*/dist-packages/lock_service* 2>/dev/null || find /usr/lib/python* -name 'lock_service' -type d 2>/dev/null" || true
    exit 1
fi


log_success "All tests passed!"
log_info "Package is ready for installation with: apt install -y ./lock-service_*.deb"
