#!/bin/bash

# Lock-Down Service Build Script
# This script builds both source distributions and RPM packages

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="lock-service"
PACKAGE_NAME="lock_service"  # Python package name (with underscores)
VERSION=$(python3 -c "import setup; print(setup.__version__)" 2>/dev/null || echo "1.0.0")
BUILD_DIR="build"
DIST_DIR="dist"
RPM_BUILD_DIR="rpmbuild"
DOCKER_IMAGE="lock-service-rpm-builder"
DOCKER_CONTAINER="lock-service-build-$$"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_dependencies() {
    log_info "Checking build dependencies..."
    
    # Check for Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python3 is required but not installed"
        exit 1
    fi
    
    # Check for pip
    if ! command -v pip3 &> /dev/null; then
        log_error "pip3 is required but not installed"
        exit 1
    fi
    
    # Check for setuptools
    if ! python3 -c "import setuptools" &> /dev/null; then
        log_warning "setuptools not found, installing..."
        pip3 install setuptools wheel
    fi
    
    # Check for wheel
    if ! python3 -c "import wheel" &> /dev/null; then
        log_warning "wheel not found, installing..."
        pip3 install wheel
    fi
    
    log_success "Dependencies check completed"
}

check_docker() {
    log_info "Checking Docker availability..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker is required but not installed"
        log_error "Please install Docker: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        log_error "Please start Docker and try again"
        exit 1
    fi
    
    log_success "Docker is available and running"
}

build_docker_image() {
    log_info "Building Docker image for RPM builds..."
    
    if [ ! -f "Dockerfile.rpm" ]; then
        log_error "Dockerfile.rpm not found"
        exit 1
    fi
    
    # Build the Docker image
    docker build -f Dockerfile.rpm -t ${DOCKER_IMAGE} . || {
        log_error "Failed to build Docker image"
        exit 1
    }
    
    log_success "Docker image built successfully: ${DOCKER_IMAGE}"
}

cleanup_docker() {
    log_info "Cleaning up Docker container..."
    
    # Remove container if it exists
    if docker ps -a --format "table {{.Names}}" | grep -q "^${DOCKER_CONTAINER}$"; then
        docker rm -f ${DOCKER_CONTAINER} &> /dev/null || true
    fi
    
    log_success "Docker cleanup completed"
}

install_build_dependencies() {
    log_info "Installing build dependencies..."
    
    # Install Python build tools
    pip3 install --upgrade pip setuptools wheel build twine
    
    # Install RPM build tools (if on RPM-based system)
    if command -v rpmbuild &> /dev/null; then
        log_info "RPM build tools found"
    else
        log_warning "RPM build tools not found. Install with:"
        log_warning "  - CentOS/RHEL/Fedora: sudo yum install rpm-build rpmdevtools"
        log_warning "  - Ubuntu/Debian: sudo apt install rpm alien"
    fi
    
    log_success "Build dependencies installed"
}

clean_build() {
    log_info "Cleaning previous builds..."
    
    # Remove build directories
    rm -rf ${BUILD_DIR}
    rm -rf ${DIST_DIR}
    rm -rf ${RPM_BUILD_DIR}
    rm -rf *.egg-info
    
    # Remove Python cache
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
    
    log_success "Build directories cleaned"
}

build_source_distribution() {
    log_info "Building source distribution..."
    
    # Create source distribution
    python3 -m build --sdist
    
    if [ -f "${DIST_DIR}/${PACKAGE_NAME}-${VERSION}.tar.gz" ]; then
        log_success "Source distribution created: ${DIST_DIR}/${PACKAGE_NAME}-${VERSION}.tar.gz"
    else
        log_error "Failed to create source distribution"
        exit 1
    fi
}

build_wheel() {
    log_info "Building wheel distribution..."
    
    # Create wheel distribution
    python3 -m build --wheel
    
    if [ -f "${DIST_DIR}/${PACKAGE_NAME}-${VERSION}-py3-none-any.whl" ]; then
        log_success "Wheel distribution created: ${DIST_DIR}/${PACKAGE_NAME}-${VERSION}-py3-none-any.whl"
    else
        log_error "Failed to create wheel distribution"
        exit 1
    fi
}

create_rpm_spec() {
    log_info "Creating RPM spec file..."
    
    cat > ${PROJECT_NAME}.spec << EOF
Name:           ${PACKAGE_NAME}
Version:        ${VERSION}
Release:        1%{?dist}
Summary:        A security service for Ubuntu systems to lock down devices when lost/stolen

License:        MIT
URL:            https://github.com/example/lock-service
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
Requires:       python3 >= 3.6
Requires:       python3-daemon >= 3.0.0
Requires:       python3-psutil >= 5.8.0
Requires:       systemd
Requires:       iptables

%description
A security service for Ubuntu systems designed to lock down devices when they are lost or stolen. The system can only be unlocked by connecting a specific Android device and entering a PIN.

%prep
%setup -q

%build
python3 setup.py build

%install
python3 setup.py install --root=%{buildroot} --optimize=1

# Create systemd service file
mkdir -p %{buildroot}%{_unitdir}
cat > %{buildroot}%{_unitdir}/lock-service.service << 'SERVICE_EOF'
[Unit]
Description=Lock-Down Service
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/lock-service.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE_EOF

%files
%defattr(-,root,root,-)
%{_bindir}/lock-service.py
%{_bindir}/lock-cli.py
%{_unitdir}/lock-service.service
%config(noreplace) %{_sysconfdir}/lock-service/init_config.json
%config(noreplace) %{_sysconfdir}/lock-service/security_policies.json
%{_datadir}/lock-service/scripts/install.sh
%{_datadir}/lock-service/scripts/setup.sh
%{_datadir}/lock-service/docs/user_manual.md
%{_datadir}/lock-service/docs/admin_guide.md

%pre
# Pre-installation script
getent group lock-service >/dev/null || groupadd -r lock-service

%post
# Post-installation script
systemctl daemon-reload
systemctl enable lock-service

%preun
# Pre-uninstallation script
if [ \$1 -eq 0 ]; then
    systemctl stop lock-service
    systemctl disable lock-service
fi

%postun
# Post-uninstallation script
if [ \$1 -eq 0 ]; then
    systemctl daemon-reload
fi

%changelog
* $(date '+%a %b %d %Y') Lock Service Team <admin@example.com> - ${VERSION}-1
- Initial package release
EOF

    log_success "RPM spec file created: ${PROJECT_NAME}.spec"
}

build_rpm() {
    log_info "Building RPM package..."
    
    if ! command -v rpmbuild &> /dev/null; then
        log_error "rpmbuild not found. Please install rpm-build package"
        return 1
    fi
    
    # Create RPM build directory structure
    mkdir -p ${RPM_BUILD_DIR}/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
    
    # Copy source tarball to SOURCES
    cp ${DIST_DIR}/${PACKAGE_NAME}-${VERSION}.tar.gz ${RPM_BUILD_DIR}/SOURCES/
    
    # Copy spec file to SPECS
    cp ${PROJECT_NAME}.spec ${RPM_BUILD_DIR}/SPECS/
    
    # Build RPM
    rpmbuild --define "_topdir $(pwd)/${RPM_BUILD_DIR}" -ba ${RPM_BUILD_DIR}/SPECS/${PROJECT_NAME}.spec
    
    if [ -f "${RPM_BUILD_DIR}/RPMS/noarch/${PACKAGE_NAME}-${VERSION}-1.noarch.rpm" ]; then
        log_success "RPM package created: ${RPM_BUILD_DIR}/RPMS/noarch/${PACKAGE_NAME}-${VERSION}-1.noarch.rpm"
    else
        log_error "Failed to create RPM package"
        return 1
    fi
}

build_rpm_docker() {
    log_info "Building RPM package using Docker..."
    
    # Ensure we have the source distribution
    if [ ! -f "${DIST_DIR}/${PACKAGE_NAME}-${VERSION}.tar.gz" ]; then
        log_error "Source distribution not found. Building it first..."
        build_source_distribution
    fi
    
    # Create RPM build directory structure
    mkdir -p ${RPM_BUILD_DIR}/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
    
    # Copy source tarball to SOURCES
    cp ${DIST_DIR}/${PACKAGE_NAME}-${VERSION}.tar.gz ${RPM_BUILD_DIR}/SOURCES/
    
    # Create spec file
    create_rpm_spec
    
    # Copy spec file to SPECS
    cp ${PROJECT_NAME}.spec ${RPM_BUILD_DIR}/SPECS/
    
    # Create a temporary build script for Docker
    cat > build_rpm_docker.sh << 'EOF'
#!/bin/bash
set -e

# Copy source files to container
cp /host/${PACKAGE_NAME}-${VERSION}.tar.gz /home/builder/rpmbuild/SOURCES/
cp /host/${PROJECT_NAME}.spec /home/builder/rpmbuild/SPECS/

# Build RPM
cd /home/builder
rpmbuild -ba rpmbuild/SPECS/${PROJECT_NAME}.spec

# Copy built RPM back to host
cp rpmbuild/RPMS/noarch/${PACKAGE_NAME}-${VERSION}-1.noarch.rpm /host/
EOF
    
    chmod +x build_rpm_docker.sh
    
    # Run Docker container to build RPM
    log_info "Starting Docker container for RPM build..."
    docker run --rm \
        --name ${DOCKER_CONTAINER} \
        -v "$(pwd)/${RPM_BUILD_DIR}/SOURCES/${PACKAGE_NAME}-${VERSION}.tar.gz:/host/${PACKAGE_NAME}-${VERSION}.tar.gz:ro" \
        -v "$(pwd)/${RPM_BUILD_DIR}/SPECS/${PROJECT_NAME}.spec:/host/${PROJECT_NAME}.spec:ro" \
        -v "$(pwd)/${RPM_BUILD_DIR}/RPMS/noarch:/host" \
        -v "$(pwd)/build_rpm_docker.sh:/home/builder/build_rpm_docker.sh:ro" \
        ${DOCKER_IMAGE} \
        /bin/bash -c "
            export PACKAGE_NAME='${PACKAGE_NAME}'
            export PROJECT_NAME='${PROJECT_NAME}'
            export VERSION='${VERSION}'
            /home/builder/build_rpm_docker.sh
        " || {
        log_error "Docker RPM build failed"
        rm -f build_rpm_docker.sh
        return 1
    }
    
    # Clean up temporary script
    rm -f build_rpm_docker.sh
    
    if [ -f "${RPM_BUILD_DIR}/RPMS/noarch/${PACKAGE_NAME}-${VERSION}-1.noarch.rpm" ]; then
        log_success "RPM package created: ${RPM_BUILD_DIR}/RPMS/noarch/${PACKAGE_NAME}-${VERSION}-1.noarch.rpm"
    else
        log_error "Failed to create RPM package"
        return 1
    fi
}

build_deb() {
    log_info "Building DEB package..."
    
    if ! command -v alien &> /dev/null; then
        log_warning "alien not found. Install with: sudo apt install alien"
        return 1
    fi
    
    if [ -f "${RPM_BUILD_DIR}/RPMS/noarch/${PACKAGE_NAME}-${VERSION}-1.noarch.rpm" ]; then
        alien --to-deb --scripts ${RPM_BUILD_DIR}/RPMS/noarch/${PACKAGE_NAME}-${VERSION}-1.noarch.rpm
        
        if [ -f "${PACKAGE_NAME}_${VERSION}-2_all.deb" ]; then
            log_success "DEB package created: ${PACKAGE_NAME}_${VERSION}-2_all.deb"
        else
            log_error "Failed to create DEB package"
            return 1
        fi
    else
        log_error "RPM package not found. Build RPM first."
        return 1
    fi
}

show_build_info() {
    log_info "Build completed successfully!"
    echo
    echo "Generated packages:"
    
    if [ -d "${DIST_DIR}" ]; then
        echo "  Source distribution:"
        ls -la ${DIST_DIR}/*.tar.gz 2>/dev/null || true
        ls -la ${DIST_DIR}/*.whl 2>/dev/null || true
    fi
    
    if [ -d "${RPM_BUILD_DIR}/RPMS" ]; then
        echo "  RPM packages:"
        find ${RPM_BUILD_DIR}/RPMS -name "*.rpm" -exec ls -la {} \;
    fi
    
    if [ -f "${PACKAGE_NAME}_${VERSION}-2_all.deb" ]; then
        echo "  DEB package:"
        ls -la ${PACKAGE_NAME}_${VERSION}-2_all.deb
    fi
    
    echo
    echo "Installation commands:"
    echo "  RPM: sudo rpm -i ${RPM_BUILD_DIR}/RPMS/noarch/${PACKAGE_NAME}-${VERSION}-1.noarch.rpm"
    echo "  DEB: sudo dpkg -i ${PACKAGE_NAME}_${VERSION}-2_all.deb"
    echo "  Source: pip3 install ${DIST_DIR}/${PACKAGE_NAME}-${VERSION}.tar.gz"
}

# Main execution
main() {
    echo "=========================================="
    echo "Lock-Down Service Build Script"
    echo "=========================================="
    echo
    
    # Parse command line arguments
    BUILD_SOURCE=true
    BUILD_WHEEL=true
    BUILD_RPM=false
    BUILD_DEB=false
    CLEAN_ONLY=false
    USE_DOCKER=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --source-only)
                BUILD_RPM=false
                BUILD_DEB=false
                shift
                ;;
            --rpm)
                BUILD_RPM=true
                shift
                ;;
            --deb)
                BUILD_DEB=true
                shift
                ;;
            --docker)
                USE_DOCKER=true
                shift
                ;;
            --clean-only)
                CLEAN_ONLY=true
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo
                echo "Options:"
                echo "  --source-only    Build only source distribution and wheel"
                echo "  --rpm           Build RPM package (requires rpmbuild or Docker)"
                echo "  --deb           Build DEB package (requires alien)"
                echo "  --docker        Use Docker for RPM builds (requires Docker)"
                echo "  --clean-only    Clean build directories only"
                echo "  --help          Show this help message"
                echo
                echo "Examples:"
                echo "  $0                    # Build source distribution and wheel"
                echo "  $0 --rpm             # Build source, wheel, and RPM (native)"
                echo "  $0 --rpm --docker    # Build source, wheel, and RPM (Docker)"
                echo "  $0 --rpm --deb       # Build all package types"
                echo "  $0 --clean-only      # Clean build directories"
                echo
                echo "Docker Requirements:"
                echo "  - Docker must be installed and running"
                echo "  - First run will build the Docker image (may take a few minutes)"
                echo "  - Subsequent runs will reuse the existing image"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
    
    # Execute build steps
    if [ "$CLEAN_ONLY" = true ]; then
        clean_build
        cleanup_docker
        exit 0
    fi
    
    # Set up cleanup trap
    trap cleanup_docker EXIT
    
    check_dependencies
    install_build_dependencies
    clean_build
    
    # Check Docker if needed
    if [ "$USE_DOCKER" = true ] && [ "$BUILD_RPM" = true ]; then
        check_docker
        build_docker_image
    fi
    
    if [ "$BUILD_SOURCE" = true ]; then
        build_source_distribution
    fi
    
    if [ "$BUILD_WHEEL" = true ]; then
        build_wheel
    fi
    
    if [ "$BUILD_RPM" = true ]; then
        if [ "$USE_DOCKER" = true ]; then
            build_rpm_docker
        else
            create_rpm_spec
            build_rpm
        fi
    fi
    
    if [ "$BUILD_DEB" = true ]; then
        build_deb
    fi
    
    show_build_info
}

# Run main function with all arguments
main "$@"
