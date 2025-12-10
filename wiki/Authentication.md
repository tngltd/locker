# Authentication

Detailed documentation of the Lock-Down Service authentication system.

## Overview

Lock-Down Service uses a multi-layer authentication system:

```
┌──────────────────────────────────────────────────┐
│              Authentication Layers                │
├──────────────────────────────────────────────────┤
│  Layer 1: Android Device + PIN (Primary)         │
│  Layer 2: Recovery Code (Emergency)              │
│  Layer 3: Admin Override (Management)            │
└──────────────────────────────────────────────────┘
```

---

## Primary Authentication (Android + PIN)

### How It Works

```
┌─────────────┐     USB      ┌─────────────────┐
│   Android   │◄────────────►│  Ubuntu System  │
│    Device   │              │  (lock-service) │
└──────┬──────┘              └────────┬────────┘
       │                              │
       │ 1. Connect via USB           │
       │─────────────────────────────►│
       │                              │
       │ 2. Request challenge         │
       │─────────────────────────────►│
       │                              │
       │ 3. Send challenge (random)   │
       │◄─────────────────────────────│
       │                              │
       │ 4. User enters PIN           │
       │                              │
       │ 5. Send response:            │
       │    HMAC(challenge+PIN+device)│
       │─────────────────────────────►│
       │                              │
       │ 6. Verify & unlock           │
       │◄─────────────────────────────│
```

### Challenge-Response Protocol

1. **Connection**: Android connects via USB
2. **Challenge**: Service generates random 32-byte challenge
3. **Response**: App computes `HMAC-SHA256(challenge || PIN || device_id)`
4. **Verification**: Service verifies response
5. **Result**: System unlocks on success

### PIN Requirements

| Requirement | Value |
|-------------|-------|
| Length | 4-6 digits |
| Characters | Numeric only (0-9) |
| Storage | Hashed (not plaintext) |

---

## Emergency Authentication (Recovery Code)

### When to Use

- Android device lost/stolen
- Android device damaged
- App not working

### How It Works

```bash
sudo lock-cli emergency-unlock
Enter recovery code: ABCD-EFGH-IJKL-MNOP-QRST-UVWX
```

### Recovery Code Properties

| Property | Value |
|----------|-------|
| Format | 24 alphanumeric characters (with dashes) |
| Validity | 48 hours from generation |
| Usage | Single-use only |
| Generation | After setup, after each use |

### Code Lifecycle

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Initial Setup  │────►│  Code Active    │────►│   Code Used     │
│  Code Generated │     │  (48 hours)     │     │   (Invalidated) │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                        ┌─────────────────┐              │
                        │  New Code       │◄─────────────┘
                        │  Generated      │
                        └─────────────────┘
```

---

## Admin Override

### Purpose

IT administrators can override locks for:
- User support
- Device recovery
- PIN reset

### Requirements

- Multi-factor authentication
- Admin credentials
- System must be accessible (unlocked or console access)

### Available Actions

| Action | Description |
|--------|-------------|
| Reset PIN | Set new user PIN |
| Generate recovery | Create new recovery code |
| Force unlock | Override lock state |

---

## Security Features

### Brute Force Protection

| Protection | Value |
|------------|-------|
| Max failed attempts | 3 |
| Lockout duration | 15 minutes |
| Attempt logging | All attempts logged |

### After 3 Failed Attempts

```
Authentication locked.
Too many failed attempts.
Please wait 15 minutes before trying again.
```

### Lockout Reset

Lockout resets automatically after:
- 15 minutes elapsed
- Successful authentication via other method

---

## Credential Storage

### PIN Storage

```
PIN → SHA-256 + Salt → Stored Hash
```

- Never stored in plaintext
- Salted before hashing
- Salt stored separately

### Recovery Code Storage

```
Code → SHA-256 + Salt + Timestamp → Stored
```

- Hashed like PIN
- Includes expiration timestamp
- Marked invalid after use

### File Locations

| Data | File |
|------|------|
| PIN hash | `/etc/lock-service/auth_data.json` |
| Recovery hash | `/etc/lock-service/auth_data.json` |
| Device ID | `/etc/lock-service/device_id` |

### File Permissions

```bash
-rw------- root root /etc/lock-service/auth_data.json
-rw------- root root /etc/lock-service/device_id
```

---

## Authentication Events

### Logged Events

| Event | Data Logged |
|-------|-------------|
| Auth attempt | Timestamp, method, result |
| Failed attempt | Timestamp, method, attempt count |
| Lockout triggered | Timestamp, unlock time |
| Recovery used | Timestamp, new code generated |
| PIN changed | Timestamp |

### Viewing Auth Logs

```bash
# View all auth events
sudo grep "auth" /var/log/lock-service.log

# View failed attempts
sudo grep "Failed" /var/log/lock-service.log

# View lockouts
sudo grep "lockout" /var/log/lock-service.log
```

---

## Troubleshooting

### "Authentication Failed"

1. Verify correct PIN
2. Check device connection
3. Ensure not in lockout period

### "Recovery Code Invalid"

1. Check code not expired (48 hours)
2. Verify code entered correctly
3. Check code not already used

### "Device Not Recognized"

1. Verify USB connection
2. Check device_id matches
3. Restart lock-service

---

## Related Pages

- [[Security]] - Security overview
- [[CLI-Reference]] - Authentication commands
- [[Troubleshooting]] - Common issues
