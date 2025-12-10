# Quick Start Guide

Get up and running with Lock-Down Service in minutes.

## 5-Minute Setup

### 1️⃣ Install

```bash
git clone https://github.com/Shakedp/lock-service.git
cd lock-service
sudo ./scripts/install.sh
```

### 2️⃣ Configure

```bash
sudo ./scripts/setup.sh
```

You'll be prompted to:
- Enter a 4-6 digit PIN
- Save your recovery code (⚠️ **Write this down!**)

### 3️⃣ Start

```bash
sudo systemctl start lock-service
sudo systemctl enable lock-service
```

### 4️⃣ Verify

```bash
lock-cli status
```

---

## Basic Commands

| Command | What it does |
|---------|--------------|
| `lock-cli status` | Check current status |
| `lock-cli logs` | View recent logs |
| `lock-cli change-pin` | Change your PIN |
| `lock-cli emergency-unlock` | Unlock with recovery code |

---

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│                    LOCKED STATE                         │
│  • SSH disabled    • Network blocked    • Ports closed  │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  Connect Android    │
              │  device via USB     │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │   Enter PIN in      │
              │   Android app       │
              └──────────┬──────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   UNLOCKED STATE                        │
│  • SSH enabled    • Network restored   • Normal ops     │
└─────────────────────────────────────────────────────────┘
```

---

## Emergency Recovery

Lost your Android device? No problem:

```bash
sudo lock-cli emergency-unlock
# Enter your recovery code when prompted
```

> 💡 A new recovery code is generated after each use

---

## Next Steps

- [[User-Guide]] - Complete user documentation
- [[Configuration]] - Customize your setup
- [[Security]] - Security best practices
- [[Troubleshooting]] - If something goes wrong
