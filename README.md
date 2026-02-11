# Locker

**Android-based service lockdown for Ubuntu servers.**

Locker ties your server's critical services to a physical Android device. When the device is connected, services run normally. When it's disconnected, Locker stops them — and keeps them stopped, even if someone tries to restart them manually.

## How It Works

1. **Configure** which services to protect (`ssh`, `nginx`, `cron`, etc.)
2. **Pair** your Android device by its USB serial number
3. **Switch to enforcing mode** — Locker now actively monitors the device connection

The background daemon (`lockerd`) checks every 5 seconds. If the paired device disappears, all managed services are stopped. When it reconnects, they start back up automatically.

## Quick Start

```bash
# Install the package
sudo apt install -y ./locker_1.0.0-1_all.deb

# Add services to protect
sudo locker add-service ssh
sudo locker add-service cron

# Pair your Android device
locker list-devices
sudo locker set-android-serial <YOUR_SERIAL>

# Activate enforcement
sudo locker set-mode enforcing
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `locker list-devices` | List connected Android devices |
| `locker get-android-serial` | Show configured device serial |
| `sudo locker set-android-serial [serial]` | Set the device serial |
| `sudo locker add-service <name>` | Add a service to protect |
| `sudo locker remove-service <name>` | Remove a service from protection |
| `locker list-services` | List managed services with status |
| `sudo locker set-mode <permissive\|enforcing>` | Set operating mode |
| `locker get-status` | Show current mode, device, and services |
| `locker logs [-n N] [-f]` | View audit log (use `-f` to follow) |

## Modes

- **Permissive** (default) — Monitors device connection but does not stop/start services. Safe for configuration.
- **Enforcing** — Actively stops services when the device is disconnected and starts them when it reconnects.

## Mock Device (for testing/demos)

For environments without a physical Android device, create a mock device file:

```bash
# Simulate a connected device
sudo bash -c 'echo '\''{"android_serial": "any_serial_value"}'\'' > /etc/locker/connect_android_serials.json'

# Remove it to simulate disconnection
sudo rm /etc/locker/connect_android_serials.json
```

The mock file is recognized by all commands (`list-devices`, `get-android-serial`, `set-mode`, `get-status`) and the service daemon. If no serial is configured via `set-android-serial`, the mock file's serial is used automatically as a fallback.

## Development

```bash
# Run tests
make test

# Build the .deb package
make build

# Build and install
make install

# Run the interactive end-to-end demo
make demo

# Show all Makefile targets
make help
```

## Project Structure

```
locker/
├── src/locker/             # Python package
│   ├── service.py          # Daemon: monitoring, locking, unlocking
│   ├── cli.py              # CLI: user-facing commands
│   ├── config.py           # Configuration management
│   └── utils.py            # Device detection, service control
├── config/                 # Default configs and systemd unit
├── debian/                 # Debian packaging metadata
├── tests/                  # Unit tests (211 tests)
├── scripts/                # Build scripts
├── docs/                   # HTML documentation
├── Makefile                # Build, test, install, demo
├── Makefile.demo           # Standalone 16-step customer demo
└── pyproject.toml          # Python package config (hatchling)
```

## Documentation

Full documentation is available at `docs/documentation.html`. Run `make help-web` to serve it locally, or open the file directly in a browser.

## License

MIT
