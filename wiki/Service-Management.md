# Service Management

Guide to managing the Lock-Down Service daemon.

## systemd Commands

### Basic Operations

| Action | Command |
|--------|---------|
| Start service | `sudo systemctl start lock-service` |
| Stop service | `sudo systemctl stop lock-service` |
| Restart service | `sudo systemctl restart lock-service` |
| Reload config | `sudo systemctl reload lock-service` |
| Check status | `sudo systemctl status lock-service` |

### Auto-start Management

| Action | Command |
|--------|---------|
| Enable on boot | `sudo systemctl enable lock-service` |
| Disable on boot | `sudo systemctl disable lock-service` |
| Check if enabled | `sudo systemctl is-enabled lock-service` |

---

## Viewing Logs

### Using lock-cli

```bash
# Show last 50 log lines
lock-cli logs

# Show last 100 lines
lock-cli logs --lines 100

# Follow logs in real-time
lock-cli logs --follow
```

### Using journalctl

```bash
# View all logs
sudo journalctl -u lock-service

# Follow in real-time
sudo journalctl -u lock-service -f

# Show last N lines
sudo journalctl -u lock-service -n 100

# Show errors only
sudo journalctl -u lock-service -p err

# Show logs since boot
sudo journalctl -u lock-service -b

# Show logs for today
sudo journalctl -u lock-service --since today

# Show logs from specific time
sudo journalctl -u lock-service --since "2025-12-10 10:00" --until "2025-12-10 12:00"
```

### Log File

```bash
# Direct log file access
sudo tail -f /var/log/lock-service.log

# Search logs
sudo grep "authentication" /var/log/lock-service.log
sudo grep "error" /var/log/lock-service.log
```

---

## Service Status

### Checking Health

```bash
# Quick status check
sudo systemctl is-active lock-service

# Detailed status
sudo systemctl status lock-service

# CLI status
lock-cli status
```

### Status Output Explained

```
$ sudo systemctl status lock-service
● lock-service.service - Lock-Down Service
     Loaded: loaded (/etc/systemd/system/lock-service.service; enabled)
     Active: active (running) since Mon 2025-12-10 10:00:00 UTC
   Main PID: 1234 (lock-service.py)
      Tasks: 2 (limit: 4096)
     Memory: 32.0M
        CPU: 1.234s
     CGroup: /system.slice/lock-service.service
             └─1234 /usr/bin/python3 /usr/local/bin/lock-service.py
```

| Field | Meaning |
|-------|---------|
| Loaded | Service file loaded, enabled/disabled status |
| Active | Current state (running, stopped, failed) |
| Main PID | Process ID of the daemon |
| Memory | Current memory usage |
| CPU | Total CPU time used |

---

## Service File Configuration

### Location

```
/etc/systemd/system/lock-service.service
```

### Default Configuration

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

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/etc/lock-service /var/log /var/run

[Install]
WantedBy=multi-user.target
```

### Modifying Service File

```bash
# Edit service file
sudo nano /etc/systemd/system/lock-service.service

# Reload systemd after changes
sudo systemctl daemon-reload

# Restart service
sudo systemctl restart lock-service
```

---

## Resource Limits

### Setting Memory Limits

```ini
[Service]
MemoryLimit=256M
MemoryHigh=200M
```

### Setting CPU Limits

```ini
[Service]
CPUQuota=50%
```

### Setting File Limits

```ini
[Service]
LimitNOFILE=1024
```

---

## Monitoring

### Simple Health Check Script

```bash
#!/bin/bash
# /usr/local/bin/check-lock-service.sh

if systemctl is-active --quiet lock-service; then
    echo "OK: Lock service is running"
    exit 0
else
    echo "CRITICAL: Lock service is not running"
    exit 2
fi
```

### Cron Job for Monitoring

```bash
# Add to crontab
*/5 * * * * /usr/local/bin/check-lock-service.sh >> /var/log/lock-service-monitor.log 2>&1
```

---

## Maintenance

### Safe Restart Procedure

```bash
# Check current status
lock-cli status

# Restart service
sudo systemctl restart lock-service

# Verify service started
sudo systemctl status lock-service

# Check for errors
sudo journalctl -u lock-service -n 20
```

### Updating the Service

```bash
# Stop service
sudo systemctl stop lock-service

# Update files
sudo cp new-lock-service.py /usr/local/bin/lock-service.py

# Restart service
sudo systemctl start lock-service

# Verify
lock-cli status
```

---

## Related Pages

- [[Admin-Guide]] - Full admin documentation
- [[Configuration]] - Configuration options
- [[Troubleshooting]] - Common issues
