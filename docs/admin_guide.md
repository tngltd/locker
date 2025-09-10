# Lock-Down Service Administrator Guide

## Overview

This guide is for system administrators who need to deploy, configure, and manage the Lock-Down Service in enterprise environments.

## Installation and Deployment

### System Requirements

- Ubuntu 18.04 or later
- Python 3.6 or later
- systemd
- iptables
- Root privileges for installation

### Package Installation

```bash
# Install from package
sudo apt install lock-service

# Or install from source
sudo ./scripts/install.sh
```

### Initial Configuration

```bash
# Run setup script
sudo ./scripts/setup.sh

# Or configure manually
sudo lock-cli setup
```

## Configuration Management

### Configuration Files

- `/etc/lock-service/config.json` - Main configuration
- `/etc/lock-service/security_policies.json` - Security policies
- `/etc/lock-service/auth_data.json` - Authentication data (encrypted)
- `/etc/lock-service/device_id` - Unique device identifier

### Security Policies

Edit `/etc/lock-service/security_policies.json` to customize:

```json
{
  "lock_policies": {
    "disable_ssh": true,
    "disable_network_interfaces": true,
    "block_all_ports": true,
    "disable_usb_storage": false,
    "disable_bluetooth": true,
    "disable_wifi": true,
    "disable_ethernet": true
  },
  "unlock_policies": {
    "restore_ssh": true,
    "restore_network_interfaces": true,
    "restore_all_ports": true,
    "enable_usb_storage": true,
    "enable_bluetooth": true,
    "enable_wifi": true,
    "enable_ethernet": true
  }
}
```

### Network Configuration

Configure network interfaces to block/unblock:

```json
{
  "network": {
    "usb_interface": "usb0",
    "blocked_interfaces": ["eth0", "wlan0", "wifi0"],
    "allowed_ports": [],
    "blocked_ports": [22, 23, 80, 443, 8080, 8443]
  }
}
```

## Service Management

### systemd Integration

The service is managed via systemd:

```bash
# Service control
sudo systemctl start lock-service
sudo systemctl stop lock-service
sudo systemctl restart lock-service
sudo systemctl status lock-service

# Enable/disable auto-start
sudo systemctl enable lock-service
sudo systemctl disable lock-service

# View logs
sudo journalctl -u lock-service -f
```

### Service Configuration

Edit `/etc/systemd/system/lock-service.service` for custom settings:

```ini
[Unit]
Description=Lock-Down Service
After=network.target
Wants=network.target

[Service]
Type=simple
User=root
Group=root
ExecStart=/usr/local/bin/lock-service.py --config /etc/lock-service/config.json --daemon
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/etc/lock-service /var/log /var/run
```

## Security Considerations

### File Permissions

Ensure proper file permissions:

```bash
# Configuration files
sudo chmod 644 /etc/lock-service/config.json
sudo chmod 644 /etc/lock-service/security_policies.json

# Authentication data
sudo chmod 600 /etc/lock-service/auth_data.json
sudo chmod 600 /etc/lock-service/device_id

# Service files
sudo chmod 755 /usr/local/bin/lock-service.py
sudo chmod 755 /usr/local/bin/lock-cli.py
```

### Firewall Integration

The service manages iptables rules. Ensure compatibility:

```bash
# Backup existing rules
sudo iptables-save > /etc/iptables/rules.v4.backup

# Service will manage rules automatically
# Check current rules
sudo iptables -L -n
```

### Log Management

Configure log rotation in `/etc/logrotate.d/lock-service`:

```
/var/log/lock-service.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 root root
    postrotate
        systemctl reload lock-service > /dev/null 2>&1 || true
    endscript
}
```

## Monitoring and Auditing

### Log Analysis

Monitor security events:

```bash
# View all authentication attempts
sudo grep "authentication" /var/log/lock-service.log

# View failed attempts
sudo grep "Failed authentication" /var/log/lock-service.log

# View emergency unlocks
sudo grep "emergency unlock" /var/log/lock-service.log
```

### External Logging

Configure external logging in `config.json`:

```json
{
  "logging": {
    "external_logging": {
      "enabled": true,
      "elasticsearch_url": "http://elasticsearch:9200",
      "logstash_url": "tcp://logstash:5000",
      "syslog_server": "udp://syslog:514"
    }
  }
}
```

### Health Checks

Create monitoring scripts:

```bash
#!/bin/bash
# health_check.sh

# Check if service is running
if ! systemctl is-active --quiet lock-service; then
    echo "CRITICAL: Lock service is not running"
    exit 2
fi

# Check if system is properly locked/unlocked
if iptables -L INPUT | grep -q "DROP"; then
    echo "INFO: System is locked"
else
    echo "INFO: System is unlocked"
fi

echo "OK: Service is healthy"
exit 0
```

## Troubleshooting

### Common Issues

1. **Service won't start**
   ```bash
   # Check systemd logs
   sudo journalctl -u lock-service -n 50
   
   # Check configuration
   sudo lock-cli status
   ```

2. **Network interfaces not blocked**
   ```bash
   # Check iptables rules
   sudo iptables -L -n
   
   # Check interface status
   ip link show
   ```

3. **Authentication failures**
   ```bash
   # Check auth data
   sudo cat /etc/lock-service/auth_data.json
   
   # Reset authentication
   sudo lock-cli setup
   ```

### Recovery Procedures

1. **Complete system lockout**
   ```bash
   # Boot from recovery media
   # Mount root filesystem
   # Remove or rename auth_data.json
   # Reboot and reconfigure
   ```

2. **Corrupted configuration**
   ```bash
   # Restore from backup
   sudo cp /etc/lock-service/config.json.backup /etc/lock-service/config.json
   
   # Restart service
   sudo systemctl restart lock-service
   ```

## Backup and Recovery

### Backup Strategy

```bash
#!/bin/bash
# backup_lock_service.sh

BACKUP_DIR="/backup/lock-service/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

# Backup configuration
cp -r /etc/lock-service "$BACKUP_DIR/"

# Backup iptables rules
iptables-save > "$BACKUP_DIR/iptables.rules"

# Backup systemd service
cp /etc/systemd/system/lock-service.service "$BACKUP_DIR/"

echo "Backup completed: $BACKUP_DIR"
```

### Recovery Procedure

```bash
#!/bin/bash
# restore_lock_service.sh

BACKUP_DIR="$1"
if [ -z "$BACKUP_DIR" ]; then
    echo "Usage: $0 <backup_directory>"
    exit 1
fi

# Stop service
sudo systemctl stop lock-service

# Restore configuration
sudo cp -r "$BACKUP_DIR/lock-service" /etc/

# Restore iptables rules
sudo iptables-restore < "$BACKUP_DIR/iptables.rules"

# Restore systemd service
sudo cp "$BACKUP_DIR/lock-service.service" /etc/systemd/system/
sudo systemctl daemon-reload

# Start service
sudo systemctl start lock-service

echo "Recovery completed"
```

## Performance Tuning

### Resource Limits

Configure systemd resource limits:

```ini
[Service]
# Memory limits
MemoryLimit=256M
MemoryHigh=200M

# CPU limits
CPUQuota=50%

# File limits
LimitNOFILE=1024
```

### Log Level Configuration

Adjust logging verbosity in `config.json`:

```json
{
  "service": {
    "log_level": "INFO"  // DEBUG, INFO, WARNING, ERROR
  }
}
```

## Security Hardening

### Additional Security Measures

1. **Disable unnecessary services**
   ```bash
   sudo systemctl disable bluetooth
   sudo systemctl disable cups
   sudo systemctl disable avahi-daemon
   ```

2. **Configure fail2ban**
   ```bash
   # Install fail2ban
   sudo apt install fail2ban
   
   # Configure for lock service
   sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local
   ```

3. **Enable audit logging**
   ```bash
   # Install auditd
   sudo apt install auditd
   
   # Configure audit rules
   sudo auditctl -w /etc/lock-service/ -p rwxa -k lock_service
   ```

## Support and Maintenance

### Regular Maintenance Tasks

1. **Weekly**
   - Review logs for security events
   - Check service status
   - Verify backup integrity

2. **Monthly**
   - Update system packages
   - Review and rotate logs
   - Test recovery procedures

3. **Quarterly**
   - Security audit
   - Configuration review
   - Performance analysis

### Contact Information

- Technical Support: admin@example.com
- Security Issues: security@example.com
- Documentation: https://github.com/example/lock-service/wiki
