# Lock-Down Service

Welcome to the Lock-Down Service Wiki! This is a comprehensive security solution for Ubuntu systems that automatically locks down your device when it's lost or stolen.

![Python](https://img.shields.io/badge/python-3.6+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Platform](https://img.shields.io/badge/platform-Ubuntu%2018.04+-orange.svg)

## 🔐 What is Lock-Down Service?

A security service designed to protect Ubuntu systems by automatically locking them down when a specific Android device is disconnected. The system can only be unlocked by:

- Connecting the authorized Android device and entering a PIN
- Using a single-use emergency recovery code

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| **Automatic Lockdown** | System locks when Android device is disconnected |
| **PIN Authentication** | Simple 4-6 digit PIN for easy user authentication |
| **Emergency Recovery** | Recovery codes for when Android device is lost |
| **Network Isolation** | Complete network lockdown when system is locked |
| **Audit Logging** | Comprehensive logging of all security events |
| **Admin Override** | Administrative unlock capabilities for IT management |

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/Shakedp/lock-service.git
cd lock-service

# Install the service
sudo ./scripts/install.sh

# Run initial setup
sudo ./scripts/setup.sh
```

## 📚 Documentation

| Guide | Description |
|-------|-------------|
| [[Installation]] | Step-by-step installation instructions |
| [[User-Guide]] | End-user documentation |
| [[Admin-Guide]] | System administrator documentation |
| [[Security]] | Security features and considerations |
| [[Troubleshooting]] | Common issues and solutions |
| [[CLI-Reference]] | Command-line interface reference |

## 🔒 Security When Locked

- ❌ SSH access disabled
- ❌ Network interfaces blocked
- ❌ All network ports closed
- ✅ Only USB communication with Android device allowed

## 🔓 Security When Unlocked

- ✅ All network services restored
- ✅ SSH access enabled
- ✅ Normal system operation

## 📋 Requirements

- Ubuntu 18.04 or later
- Python 3.6 or later
- systemd
- iptables
- Root privileges for installation

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/Shakedp/lock-service/issues)
- **Security Concerns**: See [[Security]] page

---

**Version**: 1.0.0 | **License**: MIT
