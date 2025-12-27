#!/bin/bash
# Build Debian package natively on Ubuntu
# This script builds a .deb package directly on the host system

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

# Get project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# Check if we're on Ubuntu/Debian
if ! command -v dpkg-buildpackage >/dev/null 2>&1; then
    log_error "dpkg-buildpackage not found. Installing build dependencies..."
    log_info "Please run: sudo apt-get update && sudo apt-get install -y build-essential debhelper dh-python python3-all python3-setuptools python3-pip pybuild-plugin-pyproject python3-hatchling"
    exit 1
fi

# Check for required build dependencies
log_info "Checking build dependencies..."
MISSING_DEPS=()
for dep in debhelper dh-python python3-all python3-setuptools python3-pip pybuild-plugin-pyproject python3-hatchling; do
    if ! dpkg -l | grep -q "^ii.*$dep"; then
        MISSING_DEPS+=("$dep")
    fi
done

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    log_error "Missing build dependencies: ${MISSING_DEPS[*]}"
    log_info "Install them with: sudo apt-get update && sudo apt-get install -y ${MISSING_DEPS[*]}"
    exit 1
fi

# Clean previous builds
log_info "Cleaning previous build artifacts..."
rm -rf debian/locker debian/files debian/*.substvars debian/*.log ../locker_*.deb ../locker_*.buildinfo ../locker_*.changes 2>/dev/null || true

# Build the package
log_info "Building Debian package..."
dpkg-buildpackage -b -us -uc

# Find the built package
DEB_FILE=$(find "$(dirname "$PROJECT_DIR")" -maxdepth 1 -name "locker_*.deb" -type f 2>/dev/null | head -1)

if [ -z "$DEB_FILE" ] || [ ! -f "$DEB_FILE" ]; then
    log_error "Package not found after build"
    log_error "Checked: $(dirname "$PROJECT_DIR")"
    exit 1
fi

# Move to project directory for convenience
if [[ "$DEB_FILE" != "$PROJECT_DIR"/* ]]; then
    mv "$DEB_FILE" "$PROJECT_DIR/"
    DEB_FILE="$PROJECT_DIR/$(basename "$DEB_FILE")"
fi

PACKAGE_NAME=$(basename "$DEB_FILE")
log_success "Package built successfully: $PACKAGE_NAME"
log_info "Package location: $DEB_FILE"
echo "$DEB_FILE"

