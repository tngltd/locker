# CLI Reference

Complete reference for the `lock-cli` command-line interface.

## Overview

```bash
lock-cli <command> [options]
```

---

## Commands

### `lock-cli setup`

Initial configuration wizard.

```bash
sudo lock-cli setup
```

**What it does:**
- Prompts for 4-6 digit PIN (entered twice)
- Generates recovery code
- Creates authentication data file
- Initializes device ID

**Example:**
```
$ sudo lock-cli setup
Welcome to Lock-Down Service Setup
===================================
Enter a 4-6 digit PIN: ****
Confirm PIN: ****

✓ PIN configured successfully

Your recovery code is: ABCD-EFGH-IJKL-MNOP-QRST-UVWX

⚠️  IMPORTANT: Save this code in a secure location!
   You will need it if you lose your Android device.

Setup complete!
```

---

### `lock-cli status`

Display current service status.

```bash
lock-cli status
```

**Output includes:**
- Service running status
- Device ID
- PIN configuration status
- Current lock state
- Last authentication time
- Failed attempt count

**Example:**
```
$ lock-cli status
Lock-Down Service Status
========================
Service running:  Yes
Device ID:        a1b2c3d4-e5f6-7890-abcd-ef1234567890
PIN configured:   Yes
System status:    UNLOCKED
Last auth:        2025-12-10 14:32:15
Failed attempts:  0
```

---

### `lock-cli logs`

View service logs.

```bash
lock-cli logs [--lines N] [--follow]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--lines N` | Show last N lines (default: 50) |
| `--follow` | Follow log output in real-time |

**Example:**
```bash
# Show last 50 lines
lock-cli logs

# Show last 100 lines
lock-cli logs --lines 100

# Follow logs in real-time
lock-cli logs --follow
```

---

### `lock-cli change-pin`

Change authentication PIN.

```bash
sudo lock-cli change-pin
```

**Process:**
1. Enter current PIN (for verification)
2. Enter new 4-6 digit PIN
3. Confirm new PIN

**Example:**
```
$ sudo lock-cli change-pin
Enter current PIN: ****
Enter new PIN (4-6 digits): *****
Confirm new PIN: *****

✓ PIN changed successfully
```

---

### `lock-cli emergency-unlock`

Unlock system using recovery code.

```bash
sudo lock-cli emergency-unlock
```

**When to use:**
- Android device lost or damaged
- Normal unlock unavailable

**Process:**
1. Enter recovery code
2. System unlocks
3. New recovery code generated

**Example:**
```
$ sudo lock-cli emergency-unlock
Emergency Unlock
================
Enter recovery code: ABCD-EFGH-IJKL-MNOP-QRST-UVWX

✓ System unlocked successfully

Your NEW recovery code is: WXYZ-9876-5432-1ABC-DEFG-HIJK

⚠️  IMPORTANT: Save this new code! The old code is now invalid.
```

---

### `lock-cli test-auth`

Test authentication system (development/debugging).

```bash
sudo lock-cli test-auth
```

**What it tests:**
- PIN validation
- Challenge-response system
- Authentication flow

> ⚠️ **Note:** This command is for development and testing only.

---

## Service Management

While not part of `lock-cli`, these systemd commands manage the service:

| Command | Description |
|---------|-------------|
| `sudo systemctl start lock-service` | Start the service |
| `sudo systemctl stop lock-service` | Stop the service |
| `sudo systemctl restart lock-service` | Restart the service |
| `sudo systemctl status lock-service` | Check service status |
| `sudo systemctl enable lock-service` | Enable auto-start |
| `sudo systemctl disable lock-service` | Disable auto-start |

### Viewing System Logs

```bash
# View service logs via journalctl
sudo journalctl -u lock-service

# Follow logs in real-time
sudo journalctl -u lock-service -f

# Show last 100 lines
sudo journalctl -u lock-service -n 100
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error |
| `2` | Authentication failed |
| `3` | Configuration error |
| `4` | Service not running |
| `5` | Permission denied |

---

## Related Pages

- [[User-Guide]] - User documentation
- [[Troubleshooting]] - Common issues
- [[Configuration]] - Configuration options
