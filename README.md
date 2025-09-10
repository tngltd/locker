# Lock-Down Service

A security service for Ubuntu systems designed to lock down devices when they are lost or stolen. The system can only be unlocked by connecting a specific Android device and entering a PIN.

## Features

- **Automatic Lockdown**: System automatically locks when no Android device is connected
- **PIN-based Authentication**: Simple 4-6 digit PIN for easy user authentication
- **Emergency Recovery**: Recovery codes for situations when Android device is lost
- **Network Isolation**: Complete network lockdown when system is locked
- **Audit Logging**: Comprehensive logging of all security events
- **Admin Override**: Administrative unlock capabilities for IT management

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/example/lock-service.git
cd lock-service

# Install the service
sudo ./scripts/install.sh

# Run initial setup
sudo ./scripts/setup.sh
```

### Basic Usage

```bash
# Check service status
lock-cli status

# View logs
lock-cli logs

# Change PIN
lock-cli change-pin

# Emergency unlock
lock-cli emergency-unlock
```

## Authentication Process

### Normal Unlock (Android Device)
1. Connect Android device via USB
2. Open Lock-Unlock Android app
3. Enter 4-6 digit PIN
4. System automatically unlocks

### Emergency Unlock (Recovery Code)
1. Get physical access to locked computer
2. Run: `sudo lock-cli emergency-unlock`
3. Enter recovery code
4. System unlocks and generates new recovery code

## Security Features

### When Locked
- SSH access disabled
- Network interfaces blocked
- All network ports closed
- Only USB communication allowed

### When Unlocked
- All network services restored
- SSH access enabled
- Normal system operation

## Project Structure

```
lock-service/
├── lock-service.py          # Main daemon
├── lock-cli.py             # Command line tool
├── android-app/            # Android application
├── config/
│   ├── init_config.json    # Default configuration
│   └── security_policies.json
├── scripts/
│   ├── install.sh          # Installation script
│   └── setup.sh            # Initial setup
├── docs/
│   ├── user_manual.md
│   └── admin_guide.md
├── requirements.txt
└── setup.py
```

## Requirements

- Ubuntu 18.04 or later
- Python 3.6 or later
- systemd
- iptables
- Root privileges for installation

## Dependencies

- python-daemon
- psutil

## Installation Methods

### From Source
```bash
sudo ./scripts/install.sh
```

### From Package (when available)
```bash
sudo apt install lock-service
```

### Manual Installation
```bash
sudo python3 setup.py install
```

## Configuration

The service uses JSON configuration files:

- `/etc/lock-service/config.json` - Main configuration
- `/etc/lock-service/security_policies.json` - Security policies

## Service Management

```bash
# Start service
sudo systemctl start lock-service

# Stop service
sudo systemctl stop lock-service

# Check status
sudo systemctl status lock-service

# View logs
sudo journalctl -u lock-service -f
```

## CLI Commands

- `lock-cli setup` - Initial configuration
- `lock-cli status` - Show current status
- `lock-cli change-pin` - Change authentication PIN
- `lock-cli emergency-unlock` - Emergency unlock with recovery code
- `lock-cli logs` - View service logs
- `lock-cli test-auth` - Test authentication (development)

## Security Considerations

- PIN is stored using cryptographic hashing
- Failed attempts are tracked and cause lockouts
- All authentication events are logged
- Recovery codes are single-use and time-limited
- System files are monitored for tampering

## Troubleshooting

### Service Issues
```bash
# Check service status
sudo systemctl status lock-service

# View detailed logs
sudo journalctl -u lock-service -n 50

# Restart service
sudo systemctl restart lock-service
```

### Authentication Issues
```bash
# Check authentication data
sudo lock-cli status

# Reset authentication
sudo lock-cli setup

# Test authentication
sudo lock-cli test-auth
```

## Development

### Testing
```bash
# Test Android app simulator
python3 android-app/LockUnlockApp.py

# Test authentication
sudo lock-cli test-auth
```

### Building Packages

The project includes a comprehensive build script that can create multiple package formats:

```bash
# Build source distribution and wheel
./build.sh

# Build source distribution, wheel, and RPM package
./build.sh --rpm

# Build all package types (source, wheel, RPM, and DEB)
./build.sh --rpm --deb

# Clean build directories only
./build.sh --clean-only

# Show help
./build.sh --help
```

#### Package Types Generated

- **Source Distribution**: `dist/lock_service-1.0.0.tar.gz`
- **Wheel Package**: `dist/lock_service-1.0.0-py3-none-any.whl`
- **RPM Package**: `rpmbuild/RPMS/noarch/lock_service-1.0.0-1.noarch.rpm`
- **DEB Package**: `lock_service_1.0.0-2_all.deb`

#### Build Requirements

For RPM packages:
```bash
# CentOS/RHEL/Fedora
sudo yum install rpm-build rpmdevtools

# Ubuntu/Debian
sudo apt install rpm alien
```

#### Installation from Packages

```bash
# Install from RPM
sudo rpm -i rpmbuild/RPMS/noarch/lock_service-1.0.0-1.noarch.rpm

# Install from DEB
sudo dpkg -i lock_service_1.0.0-2_all.deb

# Install from source
pip3 install dist/lock_service-1.0.0.tar.gz
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

- Documentation: [User Manual](docs/user_manual.md) | [Admin Guide](docs/admin_guide.md)
- Issues: [GitHub Issues](https://github.com/example/lock-service/issues)
- Security: security@example.com

## Changelog

### Version 1.0.0
- Initial release
- PIN-based authentication
- Emergency recovery system
- Network lockdown capabilities
- Comprehensive logging
- CLI management tool

## Roadmap

- [ ] Real Android app implementation
- [ ] USB communication protocol
- [ ] Enhanced tamper detection
- [ ] Remote management capabilities
- [ ] Integration with enterprise systems
