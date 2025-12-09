# Lock-Down Service Installation Guide

This guide will help you install and configure the Lock-Down Service on your Ubuntu machine.

## Prerequisites

- Ubuntu 18.04 or later
- Python 3.6 or later
- Root/sudo access
- systemd (usually pre-installed)
- iptables (usually pre-installed)

## Step 1: Clone the Repository

```bash
# Clone the repository
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
2. A recovery code will be generated - **SAVE THIS SECURELY**

**IMPORTANT**: Write down your recovery code in a safe place. You'll need it if you lose your Android device.

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

## Manual Installation (Alternative)

If you prefer to install manually:

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

## Testing the Installation

### Test 1: Service Status

```bash
lock-cli status
```

Expected output should show:
- Service running: Yes
- Device ID: [your device ID]
- PIN configured: Yes
- System status: UNLOCKED (initially)

### Test 2: View Logs

```bash
lock-cli logs
```

Should show service startup messages.

### Test 3: Change PIN

```bash
sudo lock-cli change-pin
```

### Test 4: Emergency Unlock

```bash
sudo lock-cli emergency-unlock
```

Enter your recovery code to test emergency unlock functionality.

## Troubleshooting

### Issue: Service won't start

```bash
# Check systemd logs
sudo journalctl -u lock-service -n 50

# Check for errors
sudo journalctl -u lock-service -p err

# Verify configuration
sudo lock-cli status
```

### Issue: Permission denied errors

```bash
# Check file permissions
ls -la /etc/lock-service/
ls -la /usr/local/bin/lock-*

# Fix permissions if needed
sudo chmod 644 /etc/lock-service/config.json
sudo chmod 600 /etc/lock-service/auth_data.json
sudo chmod 755 /usr/local/bin/lock-service.py
sudo chmod 755 /usr/local/bin/lock-cli.py
```

### Issue: Python dependencies missing

```bash
# Reinstall dependencies
sudo pip3 install -r requirements.txt --force-reinstall

# Check Python version
python3 --version  # Should be 3.6+
```

### Issue: systemd service not found

```bash
# Reload systemd
sudo systemctl daemon-reload

# Check service file exists
ls -la /etc/systemd/system/lock-service.service

# Verify service file syntax
sudo systemd-analyze verify /etc/systemd/system/lock-service.service
```

### Issue: iptables errors

```bash
# Check if iptables is installed
which iptables

# Install if missing
sudo apt-get install -y iptables

# Check current rules
sudo iptables -L -n
```

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

## Next Steps

After installation:

1. **Configure Android App**: Set up the Android companion app to connect to this service
2. **Test Lock/Unlock**: Test the complete lock/unlock cycle
3. **Review Security Policies**: Customize `/etc/lock-service/security_policies.json` if needed
4. **Set Up Monitoring**: Configure external logging if desired
5. **Backup Configuration**: Backup your configuration files

## Security Notes

- The service runs as root (required for system-level operations)
- Authentication data is stored with 600 permissions
- Recovery codes should be stored securely offline
- Regular backups of configuration are recommended
- Monitor logs for unauthorized access attempts

## Support

For issues or questions:
- Check logs: `lock-cli logs` or `sudo journalctl -u lock-service`
- Review documentation in `docs/` directory
- Check GitHub issues: https://github.com/Shakedp/lock-service/issues

## Version Information

- Service Version: 1.0.0
- Compatible with: Ubuntu 18.04+
- Python: 3.6+
- Last Updated: 2025-12-09

