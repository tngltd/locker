# Installation Guide

This guide will help you install and configure the Lock-Down Service on your Ubuntu machine.

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Ubuntu | 18.04 or later |
| Python | 3.6 or later |
| Root/sudo access | Required |
| systemd | Pre-installed |
| iptables | Pre-installed |

## Step 1: Clone the Repository

```bash
git clone https://github.com/Shakedp/lock-service.git
cd lock-service
```

## Step 2: Install System Dependencies

```bash
# Update package list
sudo apt-get update

# Install required system packages
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    libudev-dev \
    iptables \
    systemd
```

## Step 3: Install Python Dependencies

```bash
# Install Python packages
sudo pip3 install -r requirements.txt
```

Or if you prefer using apt packages where available:

```bash
# Install some packages via apt
sudo apt-get install -y python3-daemon python3-psutil

# Install remaining packages via pip
sudo pip3 install pyudev pytest pytest-cov coverage
```

## Step 4: Run Installation Script

```bash
# Make scripts executable
chmod +x scripts/install.sh
chmod +x scripts/setup.sh

# Run installation (requires root)
sudo ./scripts/install.sh
```

The installation script will:
- Create necessary directories (`/etc/lock-service`, `/var/log`, `/var/run`)
- Copy service files to `/usr/local/bin`
- Copy configuration files to `/etc/lock-service`
- Create systemd service file
- Set up log rotation
- Enable the service (but not start it yet)

## Step 5: Initial Setup

```bash
# Run setup script
sudo ./scripts/setup.sh
```

Or manually:

```bash
# Run initial configuration
sudo lock-cli setup
```

During setup, you will be prompted to:
1. Enter a 4-6 digit PIN (twice for confirmation)
2. A recovery code will be generated

> ⚠️ **IMPORTANT**: Write down your recovery code in a safe place. You'll need it if you lose your Android device.

## Step 6: Start the Service

```bash
# Start the service
sudo systemctl start lock-service

# Check status
sudo systemctl status lock-service

# Enable auto-start on boot
sudo systemctl enable lock-service
```

## Step 7: Verify Installation

```bash
# Check service status
lock-cli status

# View logs
lock-cli logs

# Check systemd status
sudo systemctl status lock-service
```

---

## Manual Installation (Alternative)

If you prefer to install manually without using the installation script:

### 1. Create Directories

```bash
sudo mkdir -p /etc/lock-service
sudo mkdir -p /var/log
sudo mkdir -p /var/run
```

### 2. Copy Files

```bash
# Copy service files
sudo cp lock-service.py /usr/local/bin/
sudo cp lock-cli.py /usr/local/bin/
sudo chmod +x /usr/local/bin/lock-service.py
sudo chmod +x /usr/local/bin/lock-cli.py

# Copy configuration
sudo cp config/init_config.json /etc/lock-service/config.json
sudo cp config/security_policies.json /etc/lock-service/
```

### 3. Create systemd Service

```bash
sudo cp config/lock-service.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable lock-service
```

### 4. Configure

```bash
sudo lock-cli setup
```

### 5. Start Service

```bash
sudo systemctl start lock-service
```

---

## Installation from Packages

### From RPM Package

```bash
sudo rpm -i rpmbuild/RPMS/noarch/lock_service-1.0.0-1.noarch.rpm
```

### From DEB Package

```bash
sudo dpkg -i lock_service_1.0.0-2_all.deb
```

### From Source Distribution

```bash
pip3 install dist/lock_service-1.0.0.tar.gz
```

---

## Uninstallation

If you need to remove the service:

```bash
# Stop and disable service
sudo systemctl stop lock-service
sudo systemctl disable lock-service

# Remove service file
sudo rm /etc/systemd/system/lock-service.service
sudo systemctl daemon-reload

# Remove service files
sudo rm /usr/local/bin/lock-service.py
sudo rm /usr/local/bin/lock-cli.py

# Remove configuration (optional - backup first!)
sudo rm -r /etc/lock-service

# Remove log rotation
sudo rm /etc/logrotate.d/lock-service

# Remove logs (optional)
sudo rm /var/log/lock-service.log
```

---

## Next Steps

After installation:

1. **[[Quick-Start]]**: Learn basic usage
2. **[[Configuration]]**: Customize settings
3. **[[User-Guide]]**: Complete user documentation
4. **[[Admin-Guide]]**: Administration guide

---

See also: [[Troubleshooting]] for common installation issues
