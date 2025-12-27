#!/bin/bash
# Test the built .deb package in a Docker Ubuntu container
# This script installs the package and tests the CLI

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

# Find the .deb package
DEB_FILE=$(find "$PROJECT_DIR" -maxdepth 1 -name "locker_*.deb" -type f | head -1)

# Also check parent directory (where dpkg-buildpackage puts it)
if [ -z "$DEB_FILE" ]; then
    DEB_FILE=$(find "$(dirname "$PROJECT_DIR")" -maxdepth 1 -name "locker_*.deb" -type f | head -1)
fi

if [ -z "$DEB_FILE" ] || [ ! -f "$DEB_FILE" ]; then
    log_error "Package file not found"
    log_error "Please build the package first with: ./scripts/build-deb.sh"
    log_error "Searched in: $PROJECT_DIR and $(dirname "$PROJECT_DIR")"
    exit 1
fi

log_success "Found package: $(basename "$DEB_FILE")"

# Copy package to /tmp for better permissions
TMP_DEB="/tmp/$(basename "$DEB_FILE")"
cp "$DEB_FILE" "$TMP_DEB"
chmod 644 "$TMP_DEB"

log_info "Step 1: Starting Ubuntu test container..."
TEST_CONTAINER="locker-test-$$"
TEST_IMAGE="ubuntu:22.04"

# Create a test Ubuntu container
docker run -d --name "$TEST_CONTAINER" "$TEST_IMAGE" sleep 3600

# Cleanup function
cleanup() {
    log_info "Cleaning up test container..."
    docker rm -f "$TEST_CONTAINER" 2>/dev/null || true
    rm -f "$TMP_DEB"
}
trap cleanup EXIT

# Copy package to container
log_info "Step 2: Copying package to container..."
docker cp "$TMP_DEB" "$TEST_CONTAINER:/tmp/"

# Update package lists and install dependencies
log_info "Step 3: Updating package lists in container..."
docker exec "$TEST_CONTAINER" bash -c "apt-get update -qq"

# Install the package
log_info "Step 4: Installing package..."
if docker exec "$TEST_CONTAINER" bash -c "apt-get install -y /tmp/$(basename "$TMP_DEB")" 2>&1 | grep -v "^WARNING: apt does not have a stable CLI interface"; then
    log_success "Package installed successfully!"
else
    log_error "Package installation failed"
    docker exec "$TEST_CONTAINER" bash -c "apt-get install -y /tmp/$(basename "$TMP_DEB")" 2>&1 | tail -20 || true
    exit 1
fi

# Verify installation
log_info "Step 5: Verifying installation..."

# Check if entry point scripts are installed
if docker exec "$TEST_CONTAINER" test -f /usr/bin/locker; then
    log_success "✓ locker entry point installed in /usr/bin"
elif docker exec "$TEST_CONTAINER" test -f /usr/local/bin/locker; then
    log_success "✓ locker entry point installed in /usr/local/bin"
else
    log_error "✗ locker entry point not found"
    docker exec "$TEST_CONTAINER" bash -c "find /usr -name 'locker' 2>/dev/null" || true
    exit 1
fi

if docker exec "$TEST_CONTAINER" test -f /etc/systemd/system/locker.service; then
    log_success "✓ systemd service file installed"
else
    log_error "✗ systemd service file not found"
    exit 1
fi

if docker exec "$TEST_CONTAINER" test -f /etc/locker/config.json; then
    log_success "✓ config.json installed"
else
    log_error "✗ config.json not found"
    exit 1
fi

# Test CLI - list-devices command
log_info "Step 6: Testing CLI - locker list-devices..."
EXIT_CODE=$(docker exec "$TEST_CONTAINER" bash -c "locker list-devices 2>&1; echo \$?" | tail -1)
if [ "$EXIT_CODE" = "0" ]; then
    log_success "✓ locker list-devices works (exit code 0)"
    log_info "Output:"
    docker exec "$TEST_CONTAINER" bash -c "locker list-devices" || true
else
    log_error "✗ locker list-devices failed with exit code: $EXIT_CODE"
    log_error "Full error output:"
    docker exec "$TEST_CONTAINER" bash -c "locker list-devices 2>&1" || true
    exit 1
fi

# Test CLI - help command
log_info "Step 7: Testing CLI - locker --help..."
if docker exec "$TEST_CONTAINER" bash -c "locker --help >/dev/null 2>&1"; then
    log_success "✓ locker --help works"
else
    log_warning "⚠ locker --help failed (may not have --help flag)"
fi

# Verify Python package is importable
log_info "Step 8: Verifying Python package installation..."
if docker exec "$TEST_CONTAINER" bash -c "python3 -c 'import locker' 2>&1"; then
    log_success "✓ Python package 'locker' is importable"
else
    log_error "✗ Python package 'locker' not importable"
    docker exec "$TEST_CONTAINER" bash -c "python3 -c 'import locker' 2>&1" || true
    exit 1
fi

# Check package info
log_info "Step 9: Checking package information..."
docker exec "$TEST_CONTAINER" bash -c "dpkg -l locker" || true

log_success "All tests passed!"
log_info ""
log_info "Package is ready for installation with: apt install -y ./locker_*.deb"
log_info "CLI is working correctly!"

