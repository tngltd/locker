#!/bin/bash
# Build Debian package using Docker
# This script builds a .deb package in a Docker container (works on Mac and Linux)

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is available
if ! command -v docker >/dev/null 2>&1; then
    log_error "Docker is not installed. Please install Docker."
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    log_error "Docker daemon is not running. Please start Docker."
    exit 1
fi

# Get project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# Docker image name
IMAGE_NAME="locker-deb-builder"
CONTAINER_NAME="locker-build-$$"

# Build/rebuild Docker image
log_info "Building Docker image..."
docker build -f Dockerfile.deb -t "$IMAGE_NAME" .

# Clean up any existing container
docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

# Run build in Docker container (mount project directory directly)
log_info "Building Debian package in Docker container..."
docker run --rm \
    --name "$CONTAINER_NAME" \
    -v "$PROJECT_DIR:/build" \
    -w /build \
    "$IMAGE_NAME" \
    bash -c "rm -rf debian/locker debian/files debian/*.substvars debian/*.log ../locker_* && cd /build && dpkg-buildpackage -b -us -uc -d && if [ -f ../locker_*.deb ]; then cp ../locker_*.deb /build/; fi"

# Find the built package (debuild puts it in parent directory)
DEB_FILE=$(find "$(dirname "$PROJECT_DIR")" -maxdepth 1 -name "locker_*.deb" -type f 2>/dev/null | head -1)

if [ -z "$DEB_FILE" ]; then
    # Check project directory as fallback
    DEB_FILE=$(find "$PROJECT_DIR" -maxdepth 1 -name "locker_*.deb" -type f 2>/dev/null | head -1)
fi

if [ -z "$DEB_FILE" ] || [ ! -f "$DEB_FILE" ]; then
    log_error "Package not found after build"
    log_error "Checked: $PROJECT_DIR and $(dirname "$PROJECT_DIR")"
    exit 1
fi

# Move to project directory if it's in parent
if [[ "$DEB_FILE" != "$PROJECT_DIR"/* ]]; then
    mv "$DEB_FILE" "$PROJECT_DIR/"
    DEB_FILE="$PROJECT_DIR/$(basename "$DEB_FILE")"
fi

PACKAGE_NAME=$(basename "$DEB_FILE")
log_success "Package built successfully: $PACKAGE_NAME"
echo "$PACKAGE_NAME"
