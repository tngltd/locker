# Lock-Down Service User Manual

## Overview

The Lock-Down Service is a security solution for Ubuntu systems that automatically locks down your device when it's lost or stolen. The system can only be unlocked by connecting a specific Android device and entering a PIN.

## Quick Start

### 1. Installation

```bash
# Install the service
sudo ./scripts/install.sh

# Run initial setup
sudo ./scripts/setup.sh
```

### 2. Basic Usage

```bash
# Check service status
lock-cli status

# View logs
lock-cli logs

# Change PIN
lock-cli change-pin

# Emergency unlock (if you lose your Android device)
lock-cli emergency-unlock
```

## Authentication Process

### Normal Unlock (Android Device)

1. Connect your Android device via USB
2. Open the Lock-Unlock Android app
3. Enter your 4-6 digit PIN
4. The system will automatically unlock

### Emergency Unlock (Recovery Code)

If you lose your Android device:

1. Get physical access to the locked computer
2. Run: `sudo lock-cli emergency-unlock`
3. Enter your recovery code
4. The system will unlock and generate a new recovery code

## Security Features

### When Locked
- SSH access is disabled
- Network interfaces are blocked
- All network ports are closed
- Only USB communication with Android device is allowed

### When Unlocked
- All network services are restored
- SSH access is enabled
- Normal system operation resumes

## Configuration

### PIN Management
- PIN must be 4-6 digits
- PIN is stored securely using cryptographic hashing
- Failed attempts are tracked and cause temporary lockouts

### Recovery Codes
- Generated during initial setup
- Single-use codes that expire in 48 hours
- New recovery code generated after each use

### Lockout Protection
- Maximum 3 failed PIN attempts
- 15-minute lockout after failed attempts
- All attempts are logged for security auditing

## Troubleshooting

### Service Won't Start
```bash
# Check service status
systemctl status lock-service

# View detailed logs
journalctl -u lock-service -f

# Restart service
sudo systemctl restart lock-service
```

### Can't Unlock System
1. Try emergency unlock with recovery code
2. Check if Android device is properly connected
3. Verify PIN is correct
4. Check if system is in lockout period

### Lost Recovery Code
If you lose both your Android device and recovery code:
1. Contact your system administrator
2. Use admin override (if configured)
3. Physical access may be required for recovery

## Security Best Practices

1. **Keep Recovery Code Safe**: Store your recovery code in a secure location separate from your Android device
2. **Regular PIN Changes**: Change your PIN periodically for enhanced security
3. **Monitor Logs**: Regularly check logs for unauthorized access attempts
4. **Backup Configuration**: Keep backups of your configuration files

## Command Reference

### Service Management
- `systemctl start lock-service` - Start the service
- `systemctl stop lock-service` - Stop the service
- `systemctl restart lock-service` - Restart the service
- `systemctl status lock-service` - Check service status

### CLI Commands
- `lock-cli setup` - Initial configuration
- `lock-cli status` - Show current status
- `lock-cli change-pin` - Change authentication PIN
- `lock-cli emergency-unlock` - Emergency unlock with recovery code
- `lock-cli logs` - View service logs
- `lock-cli test-auth` - Test authentication (development)

## Support

For technical support or security concerns:
- Check the logs first: `lock-cli logs`
- Review this manual
- Contact your system administrator
- Report security issues immediately

## Version Information

- Version: 1.0.0
- Compatible with: Ubuntu 18.04+
- Python: 3.6+
- Dependencies: python-daemon, psutil
