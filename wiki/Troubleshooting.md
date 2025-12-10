# Troubleshooting

Solutions to common issues with Lock-Down Service.

## Quick Diagnostics

```bash
# Check service status
sudo systemctl status lock-service

# View recent logs
lock-cli logs --lines 100

# Check detailed journal
sudo journalctl -u lock-service -n 50
```

---

## Installation Issues

### Service Won't Install

**Symptoms:**
- `install.sh` fails
- Permission errors

**Solutions:**
```bash
# Ensure running as root
sudo ./scripts/install.sh

# Check Python version
python3 --version  # Must be 3.6+

# Install missing dependencies
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-dev libudev-dev
sudo pip3 install -r requirements.txt
```

### Python Dependencies Missing

**Symptoms:**
- `ModuleNotFoundError`
- Import errors

**Solutions:**
```bash
# Reinstall dependencies
sudo pip3 install -r requirements.txt --force-reinstall

# Or install system packages
sudo apt-get install -y python3-daemon python3-psutil
sudo pip3 install pyudev
```

### systemd Service Not Found

**Symptoms:**
- `Unit lock-service.service not found`

**Solutions:**
```bash
# Check if service file exists
ls -la /etc/systemd/system/lock-service.service

# Copy service file if missing
sudo cp config/lock-service.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Verify service
sudo systemctl status lock-service
```

---

## Service Issues

### Service Won't Start

**Symptoms:**
- `systemctl start lock-service` fails
- Service immediately stops

**Diagnosis:**
```bash
# Check systemd logs
sudo journalctl -u lock-service -n 50

# Check for errors
sudo journalctl -u lock-service -p err

# Verify configuration
sudo lock-cli status
```

**Common Causes:**

| Cause | Solution |
|-------|----------|
| Config file missing | Copy from `config/init_config.json` |
| Permission denied | Check file permissions |
| Port already in use | Check for conflicting services |
| Python error | Check Python version and dependencies |

### Service Crashes Repeatedly

**Symptoms:**
- Service restarts frequently
- Log shows repeated failures

**Solutions:**
```bash
# Check for error patterns
sudo journalctl -u lock-service | grep -i error

# Increase log verbosity
# Edit /etc/lock-service/config.json
# Set "log_level": "DEBUG"

# Restart and monitor
sudo systemctl restart lock-service
sudo journalctl -u lock-service -f
```

---

## Authentication Issues

### Can't Authenticate

**Symptoms:**
- PIN rejected
- Authentication fails

**Diagnosis:**
```bash
# Check auth data exists
sudo ls -la /etc/lock-service/auth_data.json

# Check lock status
lock-cli status
```

**Solutions:**

| Issue | Solution |
|-------|----------|
| Lockout active | Wait 15 minutes |
| Wrong PIN | Verify correct PIN |
| Corrupted auth data | Run `sudo lock-cli setup` |

### Forgot PIN

**Solutions:**

1. **Use emergency unlock:**
   ```bash
   sudo lock-cli emergency-unlock
   # Enter recovery code
   ```

2. **Reset authentication:**
   ```bash
   sudo lock-cli setup
   # Set new PIN
   ```

### Lost Recovery Code

**If you have Android device:**
```bash
# Unlock normally, then reset
sudo lock-cli setup
# Save new recovery code!
```

**If locked out completely:**
1. Boot from recovery media
2. Mount root filesystem
3. Remove `/etc/lock-service/auth_data.json`
4. Reboot and run `sudo lock-cli setup`

---

## Network Issues

### Network Not Blocked When Locked

**Symptoms:**
- Network still accessible when locked
- SSH still works

**Diagnosis:**
```bash
# Check iptables rules
sudo iptables -L -n

# Check interface status
ip link show

# Check security policies
cat /etc/lock-service/security_policies.json
```

**Solutions:**
```bash
# Verify lock policies are enabled
# In security_policies.json:
{
  "lock_policies": {
    "disable_ssh": true,
    "disable_network_interfaces": true,
    "block_all_ports": true
  }
}

# Restart service
sudo systemctl restart lock-service
```

### Network Not Restored When Unlocked

**Symptoms:**
- System unlocked but network still down
- SSH remains blocked

**Solutions:**
```bash
# Check unlock policies
# In security_policies.json:
{
  "unlock_policies": {
    "restore_ssh": true,
    "restore_network_interfaces": true,
    "restore_all_ports": true
  }
}

# Manual network restore
sudo systemctl restart NetworkManager
# or
sudo ifup eth0
```

---

## Permission Issues

### Permission Denied Errors

**Symptoms:**
- `Permission denied` errors
- Can't read/write config files

**Solutions:**
```bash
# Fix configuration file permissions
sudo chmod 644 /etc/lock-service/config.json
sudo chmod 644 /etc/lock-service/security_policies.json
sudo chmod 600 /etc/lock-service/auth_data.json
sudo chmod 600 /etc/lock-service/device_id

# Fix service file permissions
sudo chmod 755 /usr/local/bin/lock-service.py
sudo chmod 755 /usr/local/bin/lock-cli.py

# Ensure root ownership
sudo chown root:root /etc/lock-service/*
sudo chown root:root /usr/local/bin/lock-*.py
```

---

## Log Issues

### Logs Not Writing

**Symptoms:**
- Log file empty or missing
- No log output

**Solutions:**
```bash
# Check log directory exists
sudo mkdir -p /var/log

# Check permissions
sudo touch /var/log/lock-service.log
sudo chmod 644 /var/log/lock-service.log

# Restart service
sudo systemctl restart lock-service
```

### Logs Too Verbose

**Solution:**
```json
// In /etc/lock-service/config.json
{
  "service": {
    "log_level": "WARNING"  // or "ERROR"
  }
}
```

---

## Recovery Procedures

### Complete System Lockout

If you're completely locked out:

1. **Boot from Ubuntu Live USB**
2. **Mount the root filesystem:**
   ```bash
   sudo mount /dev/sda1 /mnt
   ```
3. **Remove auth data:**
   ```bash
   sudo rm /mnt/etc/lock-service/auth_data.json
   ```
4. **Reboot normally**
5. **Reconfigure:**
   ```bash
   sudo lock-cli setup
   ```

### Corrupted Configuration

```bash
# Restore from backup
sudo cp /etc/lock-service/config.json.backup /etc/lock-service/config.json

# Or restore defaults
sudo cp /path/to/lock-service/config/init_config.json /etc/lock-service/config.json

# Restart service
sudo systemctl restart lock-service
```

---

## Getting Help

If these solutions don't work:

1. **Collect diagnostics:**
   ```bash
   sudo systemctl status lock-service > status.txt
   sudo journalctl -u lock-service -n 200 > logs.txt
   lock-cli status > cli-status.txt
   ```

2. **Check GitHub Issues:**
   [https://github.com/Shakedp/lock-service/issues](https://github.com/Shakedp/lock-service/issues)

3. **Open new issue** with:
   - Ubuntu version
   - Python version
   - Error messages
   - Steps to reproduce

---

## Related Pages

- [[Installation]] - Installation guide
- [[Configuration]] - Configuration reference
- [[Admin-Guide]] - Administration guide
