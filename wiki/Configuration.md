# Configuration

Complete guide to configuring Lock-Down Service.

## Configuration Files

| File | Location | Purpose |
|------|----------|---------|
| Main config | `/etc/lock-service/config.json` | Service settings |
| Security policies | `/etc/lock-service/security_policies.json` | Lock/unlock behavior |
| Auth data | `/etc/lock-service/auth_data.json` | Encrypted credentials |
| Device ID | `/etc/lock-service/device_id` | Unique identifier |

---

## Main Configuration

### `/etc/lock-service/config.json`

```json
{
  "service": {
    "name": "lock-service",
    "version": "1.0.0",
    "log_level": "INFO",
    "log_file": "/var/log/lock-service.log",
    "pid_file": "/var/run/lock-service.pid"
  },
  "authentication": {
    "pin_length_min": 4,
    "pin_length_max": 6,
    "max_failed_attempts": 3,
    "lockout_duration_minutes": 15,
    "recovery_code_expiry_hours": 48
  },
  "network": {
    "usb_interface": "usb0",
    "blocked_interfaces": ["eth0", "wlan0", "wifi0"],
    "allowed_ports": [],
    "blocked_ports": [22, 23, 80, 443, 8080, 8443]
  },
  "logging": {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "external_logging": {
      "enabled": false,
      "elasticsearch_url": null,
      "logstash_url": null,
      "syslog_server": null
    }
  }
}
```

### Configuration Options

#### Service Section

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `log_level` | string | `"INFO"` | Logging level: DEBUG, INFO, WARNING, ERROR |
| `log_file` | string | `/var/log/lock-service.log` | Log file path |
| `pid_file` | string | `/var/run/lock-service.pid` | PID file path |

#### Authentication Section

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `pin_length_min` | int | `4` | Minimum PIN length |
| `pin_length_max` | int | `6` | Maximum PIN length |
| `max_failed_attempts` | int | `3` | Attempts before lockout |
| `lockout_duration_minutes` | int | `15` | Lockout duration |
| `recovery_code_expiry_hours` | int | `48` | Recovery code validity |

#### Network Section

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `usb_interface` | string | `"usb0"` | USB interface name |
| `blocked_interfaces` | array | `["eth0", "wlan0"]` | Interfaces to block |
| `blocked_ports` | array | `[22, 23, 80, 443...]` | Ports to block |

---

## Security Policies

### `/etc/lock-service/security_policies.json`

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

### Policy Options

#### Lock Policies

| Policy | Default | Description |
|--------|---------|-------------|
| `disable_ssh` | `true` | Block SSH when locked |
| `disable_network_interfaces` | `true` | Bring down network interfaces |
| `block_all_ports` | `true` | Block all network ports |
| `disable_usb_storage` | `false` | Block USB storage devices |
| `disable_bluetooth` | `true` | Disable Bluetooth |
| `disable_wifi` | `true` | Disable WiFi |
| `disable_ethernet` | `true` | Disable Ethernet |

#### Unlock Policies

| Policy | Default | Description |
|--------|---------|-------------|
| `restore_ssh` | `true` | Enable SSH when unlocked |
| `restore_network_interfaces` | `true` | Bring up network interfaces |
| `restore_all_ports` | `true` | Unblock network ports |
| `enable_usb_storage` | `true` | Allow USB storage |
| `enable_bluetooth` | `true` | Enable Bluetooth |
| `enable_wifi` | `true` | Enable WiFi |
| `enable_ethernet` | `true` | Enable Ethernet |

---

## External Logging

### Elasticsearch

```json
{
  "logging": {
    "external_logging": {
      "enabled": true,
      "elasticsearch_url": "http://elasticsearch.example.com:9200"
    }
  }
}
```

### Logstash

```json
{
  "logging": {
    "external_logging": {
      "enabled": true,
      "logstash_url": "tcp://logstash.example.com:5000"
    }
  }
}
```

### Syslog

```json
{
  "logging": {
    "external_logging": {
      "enabled": true,
      "syslog_server": "udp://syslog.example.com:514"
    }
  }
}
```

---

## File Permissions

Ensure proper permissions:

```bash
# Configuration files (readable)
sudo chmod 644 /etc/lock-service/config.json
sudo chmod 644 /etc/lock-service/security_policies.json

# Sensitive files (restricted)
sudo chmod 600 /etc/lock-service/auth_data.json
sudo chmod 600 /etc/lock-service/device_id

# All owned by root
sudo chown root:root /etc/lock-service/*
```

---

## Applying Changes

After modifying configuration:

```bash
# Restart service to apply changes
sudo systemctl restart lock-service

# Verify configuration was loaded
lock-cli status
```

---

## Related Pages

- [[Admin-Guide]] - Administrator documentation
- [[Security]] - Security configuration
- [[Service-Management]] - Managing the service
