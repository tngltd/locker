# Security

Lock-Down Service is designed with security as the primary focus. This page documents the security features, policies, and best practices.

## Security Architecture

### Authentication Layers

| Layer | Method | Purpose |
|-------|--------|---------|
| **Primary** | Android Device + PIN | Normal daily unlock |
| **Emergency** | Recovery Code | Lost device recovery |
| **Admin** | Multi-factor Auth | IT management override |

### When System is Locked

| Component | State | Details |
|-----------|-------|---------|
| SSH | ❌ Disabled | Port 22 blocked |
| Network interfaces | ❌ Blocked | All interfaces down |
| Network ports | ❌ Closed | iptables DROP rules |
| USB | ✅ Allowed | Only Android communication |
| Local console | ✅ Allowed | Emergency access |

### When System is Unlocked

| Component | State |
|-----------|-------|
| SSH | ✅ Enabled |
| Network interfaces | ✅ Active |
| Network ports | ✅ Open (per policy) |
| All services | ✅ Normal operation |

---

## Authentication Details

### PIN Authentication

- **Length**: 4-6 digits
- **Storage**: Cryptographic hash (not plaintext)
- **Attempts**: 3 failed attempts before lockout
- **Lockout**: 15-minute cooldown period

### Challenge-Response Protocol

```
1. Android connects via USB
2. Service sends random challenge
3. App responds with: HMAC(challenge + PIN + device_id)
4. Service verifies response
5. System unlocks on success
```

### Recovery Codes

| Property | Value |
|----------|-------|
| Format | 24-character alphanumeric |
| Validity | 48 hours from generation |
| Usage | Single-use only |
| Storage | Securely hashed |

---

## Security Policies

### Default Lock Policies

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
  }
}
```

### Customizable Options

| Policy | Description | Default |
|--------|-------------|---------|
| `disable_ssh` | Block SSH access | `true` |
| `disable_network_interfaces` | Bring down network | `true` |
| `block_all_ports` | iptables DROP all | `true` |
| `disable_usb_storage` | Block USB drives | `false` |
| `disable_bluetooth` | Disable Bluetooth | `true` |

---

## Audit Logging

All security events are logged:

```bash
# View authentication logs
sudo grep "authentication" /var/log/lock-service.log

# View failed attempts
sudo grep "Failed" /var/log/lock-service.log

# View state changes
sudo grep "state changed" /var/log/lock-service.log
```

### Logged Events

| Event | Logged Data |
|-------|-------------|
| Authentication attempt | Timestamp, success/fail, method |
| State change | Lock/unlock, trigger |
| Configuration change | What changed, who |
| Service start/stop | Timestamp, reason |
| Failed attempts | Count, lockout status |

---

## Security Best Practices

### For Users

| Practice | Why |
|----------|-----|
| 🔐 Store recovery code securely | It's your backup access |
| 🔄 Change PIN regularly | Limit exposure window |
| 📱 Keep Android device updated | Security patches |
| 👀 Review logs periodically | Detect anomalies |

### For Administrators

| Practice | Why |
|----------|-----|
| 🔒 Restrict config file permissions | Prevent tampering |
| 📊 Enable external logging | Centralized monitoring |
| 🔄 Regular security audits | Catch misconfigurations |
| 💾 Backup auth data securely | Disaster recovery |

---

## Threat Model

### Protected Against

| Threat | Protection |
|--------|------------|
| Unauthorized network access | Complete network isolation |
| Remote SSH attacks | SSH disabled when locked |
| Stolen device | Requires specific Android + PIN |
| Brute force PIN | Lockout after 3 attempts |
| Recovery code theft | 48-hour expiry, single-use |

### Assumptions

- Physical console access is trusted for emergency recovery
- Android device is kept secure by user
- Recovery code is stored safely offline

---

## Vulnerability Reporting

If you discover a security vulnerability:

1. **Do not** open a public GitHub issue
2. Email security concerns to the maintainer
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We take all security reports seriously and will respond within 48 hours.

---

## Related Pages

- [[Admin-Guide]] - Security configuration details
- [[Configuration]] - Security policy settings
- [[Troubleshooting]] - Security-related issues
