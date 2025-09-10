# Lock-Down service
This service is a service designed to ubuntu syste in order to lock the device when it's lost / stoled by someone else.
We want the service to make the system "locked" and hardend so that a 3rd party person would have hard time to break in if they get their hands on it.

## General Requirements

*⁠ The service should ⁠be written in Python language
*⁠ It need to ⁠be installed by apt, in a single command (we want to build the service as an RPM package).
*⁠ The service should ⁠be configurable by a command line tool that is installed with the same package
*⁠ Have a default configuration file in the repo (an init_config.json file that will present the initial config)
* Logs should be verbose, and include the connected system (Mac, Linux, Android etc.)
* Loges also should be accessible through the command line delivered with the package.

## Main Goal
The service is responsible for locking the device on autonomous mode, hence, when there is no physical connection to an Android device.
The device should be unlocked when the mode changed (for example, the relevant Android device connected).

## Locking the system
When the system is locked:
* There should be no SSH access 
* No network interfaces should be available from the outside
* Any communication that it's not the USB to the Android device shuold be forbidden.

## Authentication System

### Primary Unlock (Normal Operation)
* Android device connects via USB only
* User enters 4-6 digit PIN on Android app
* System sends challenge, app responds with PIN + HMAC (challenge + PIN + device_id)
* PIN attempts limited (3-5 attempts before lockout)

### Emergency Recovery (Lost Android Device)
* Physical console access required
* Single-use recovery code (24-48 hour expiry)
* New recovery code generated after successful unlock

### Admin Override (Network Recovery)
* Available only when system unlocked
* Multi-factor admin authentication required
* Can reset user PIN and generate new recovery codes

## Service Structure
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
└── docs/
    ├── user_manual.md
    └── admin_guide.md
```

## Comments:
* Bonus - the system can send logs to an elastic or any other logging service that can be set up easily in the internal network, to make the installation process easier.