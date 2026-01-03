#!/usr/bin/env python3
"""
Lock-Down Service - Main daemon
A security service for Ubuntu systems to lock down devices when the configured Android device is disconnected.
"""

import os
import json
import time
import signal
import logging
import subprocess
from pathlib import Path
from typing import Dict, Optional, List
import argparse
import pyudev


class LockService:
    def __init__(self, config_path: str = "/etc/locker/config.json", config_dir: str = None, config_override: dict = None):
        self.config_path = config_path
        self.config = self.load_config()
        if config_override:
            self.config.update(config_override)
        self.running = True
        
        # Setup logging first (needed for error handling)
        # Note: self.config is already loaded above
        self.setup_logging()
        
        # Set config directory (allow override for testing)
        self.config_dir = config_dir or "/etc/locker"
        
        # Load configured Android device serial (from config or file)
        self.android_serial = self.config.get('android_serial') or self.load_android_serial()
        
        # Get mode (permissive or enforcing)
        self.mode = self.config.get('mode', 'permissive')
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGHUP, self.reload_config_handler)
        
        if self.android_serial:
            self.logger.info(f"Lock Service initialized. Configured Android serial: {self.android_serial}")
        else:
            self.logger.warning("Lock Service initialized. No Android device configured - run \"locker setup\" first")
        self.logger.info(f"System OS: {self.get_system_info()}")
    
    def load_config(self) -> Dict:
        """Load and validate configuration from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
        except FileNotFoundError:
            # Use default config if file doesn't exist
            default_config_path = Path("/etc/locker/config.json")
            if default_config_path.exists():
                with open(default_config_path, 'r') as f:
                    config = json.load(f)
            else:
                # Fallback to minimal default config from config/config.json
                # Find the config file relative to this source file
                source_dir = Path(__file__).parent.parent.parent
                fallback_config_path = source_dir / "config" / "config.json"
                if fallback_config_path.exists():
                    with open(fallback_config_path, 'r') as f:
                        config = json.load(f)
                else:
                    # Last resort: minimal config
                    config = {
                        "service": {"log_level": "INFO", "log_file": "/var/log/locker.log", "name": "locker"},
                        "monitoring": {"check_interval_seconds": 5},
                        "mode": "permissive",
                        "android_serial": None,
                        "services": []
                    }
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file: {e}")
        
        # Validate required sections
        self.validate_config(config)
        return config
    
    def validate_config(self, config: Dict):
        """Validate configuration structure"""
        required_sections = ['service', 'monitoring']
        for section in required_sections:
            if section not in config:
                raise ValueError(f"Missing required config section: {section}")
        
        # Validate service section
        if 'log_level' not in config['service']:
            raise ValueError("Missing \"log_level\" in service config")
        
        # Ensure service.name exists
        if 'name' not in config['service']:
            config['service']['name'] = 'locker'
        
        # Validate monitoring section
        if 'check_interval_seconds' not in config['monitoring']:
            raise ValueError("Missing \"check_interval_seconds\" in monitoring config")
        
        # Validate mode
        mode = config.get('mode', 'permissive')
        if mode not in ['permissive', 'enforcing']:
            raise ValueError(f"Invalid mode: {mode}. Must be \"permissive\" or \"enforcing\"")
        
        # Ensure services section exists as a list
        if 'services' not in config:
            config['services'] = []
        elif not isinstance(config['services'], list):
            # Convert old format to new format
            if isinstance(config['services'], dict):
                # Merge stop_when_locked and start_when_unlocked into a single list
                old_stop = config['services'].get('stop_when_locked', [])
                old_start = config['services'].get('start_when_unlocked', [])
                config['services'] = list(set(old_stop + old_start))
            else:
                config['services'] = []
    
    def setup_logging(self):
        """Setup logging configuration"""
        # Get log level from config, default to INFO
        log_level_str = self.config.get('service', {}).get('log_level', 'INFO').upper()
        log_level = getattr(logging, log_level_str, logging.INFO)

        # Setup logger
        self.logger = logging.getLogger('locker')
        self.logger.setLevel(log_level)
        # Clear any existing handlers to avoid duplicates
        self.logger.handlers.clear()

        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # Setup console handler first (for error visibility)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)  # Less verbose on console
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # Setup file handler (always try to create)
        try:
            log_file_path = self.config['service']['log_file']
            # Ensure log directory exists
            log_dir = os.path.dirname(log_file_path)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file_path)
            file_handler.setLevel(logging.DEBUG)  # Verbose logging to file
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            # Log successful file handler setup
            self.logger.info(f"Logging to file: {log_file_path}")
        except (OSError, PermissionError) as e:
            # Log error to console handler (which is already added)
            self.logger.warning(f"Failed to setup file logging to {log_file_path}: {e}")
            self.logger.warning("Logs will only be written to console/systemd journal")
    
    def log_config(self):
        """Log current configuration (sanitized for security)"""
        try:
            # Create a sanitized copy of config for logging
            config_copy = self.config.copy()
            
            # Don't log sensitive information or very long values
            # Keep android_serial but truncate if too long
            sanitized_serial = config_copy.get('android_serial', 'Not configured')
            if sanitized_serial and sanitized_serial != 'Not configured' and len(sanitized_serial) > 20:
                sanitized_serial = sanitized_serial[:10] + "..." + sanitized_serial[-7:]
            
            # Log configuration in a readable format
            self.logger.info("Current configuration:")
            self.logger.info(f"  Mode: {config_copy.get('mode', 'permissive')}")
            self.logger.info(f"  Android Serial: {sanitized_serial}")
            self.logger.info(f"  Services: {config_copy.get('services', [])}")
            self.logger.info(f"  Monitoring Interval: {config_copy.get('monitoring', {}).get('check_interval_seconds', 5)} seconds")
            self.logger.info(f"  Log Level: {config_copy.get('service', {}).get('log_level', 'INFO')}")
            self.logger.info(f"  Log File: {config_copy.get('service', {}).get('log_file', '/var/log/locker.log')}")
            
            # Network config logging removed (no longer used)
        except Exception as e:
            self.logger.warning(f"Error logging configuration: {e}")
    
    def get_system_info(self) -> str:
        """Get system information for logging"""
        try:
            with open('/etc/os-release', 'r') as f:
                lines = f.readlines()
                for line in lines:
                    if line.startswith('PRETTY_NAME='):
                        return line.split('=')[1].strip().strip('"')
        except:
            pass
        return "Unknown Linux System"
    
    def load_android_serial(self) -> Optional[str]:
        """Load configured Android device serial from file (legacy support)"""
        try:
            serial_file = os.path.join(self.config_dir, 'android_serial')
            if os.path.exists(serial_file):
                with open(serial_file, 'r') as f:
                    return f.read().strip()
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.debug(f"Error loading Android serial from file: {e}")
        return None
    
    def save_android_serial(self, serial: str):
        """Save Android device serial to config"""
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            serial_file = os.path.join(self.config_dir, 'android_serial')
            with open(serial_file, 'w') as f:
                f.write(serial)
            os.chmod(serial_file, 0o600)
            self.android_serial = serial
            self.logger.info(f"Android serial configured: {serial}")
        except Exception as e:
            self.logger.error(f"Error saving Android serial: {e}")
    
    def is_configured(self) -> bool:
        """Check if an Android device is configured"""
        return self.android_serial is not None and len(self.android_serial) > 0
    
    def is_service_running(self, service_name: str, log_check: bool = False) -> bool:
        """Check if a service is currently running"""
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', '--quiet', service_name],
                capture_output=True,
                timeout=2
            )
            is_running = result.returncode == 0
            if log_check:
                self.logger.info(f"Service {service_name} status: {'RUNNING' if is_running else 'STOPPED'}")
            return is_running
        except Exception as e:
            if log_check:
                self.logger.warning(f"Error checking service {service_name} status: {e}")
            return False
    
    def lock_system(self):
        """Lock down the system - stop configured services (stateless)"""
        self.logger.info("Locking system...")
        
        try:
            lock_policies = self.config.get('lock_policies', {})
            
            # Block all ports with iptables if configured
            if lock_policies.get('block_all_ports', False):
                # Check if iptables rules already exist before adding
                try:
                    result = subprocess.run(
                        ['iptables', '-C', 'INPUT', '-j', 'DROP'],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    if result.returncode != 0:
                        # Rule doesn't exist, add it
                        self.logger.info("Blocking all ports with iptables")
                        subprocess.run(['iptables', '-A', 'INPUT', '-j', 'DROP'], check=False)
                        subprocess.run(['iptables', '-A', 'OUTPUT', '-j', 'DROP'], check=False)
                        subprocess.run(['iptables', '-A', 'FORWARD', '-j', 'DROP'], check=False)
                    else:
                        self.logger.debug("iptables DROP rules already exist")
                except Exception as e:
                    self.logger.debug(f"Error checking iptables rules: {e}")
                    # Try to add rules anyway (may create duplicates but that's acceptable)
                    self.logger.info("Blocking all ports with iptables")
                    subprocess.run(['iptables', '-A', 'INPUT', '-j', 'DROP'], check=False)
                    subprocess.run(['iptables', '-A', 'OUTPUT', '-j', 'DROP'], check=False)
                    subprocess.run(['iptables', '-A', 'FORWARD', '-j', 'DROP'], check=False)
            
            # Stop configured services (only if running)
            services_to_stop = self.config.get('services', [])
            for service in services_to_stop:
                self.logger.info(f"Checking if service {service} is running...")
                if self.is_service_running(service, log_check=True):
                    self.logger.info(f"Service {service} is running - stopping it")
                    result = subprocess.run(['systemctl', 'stop', service], check=False, capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        self.logger.info(f"Service {service} stopped successfully")
                    else:
                        self.logger.warning(f"Failed to stop service {service}: {result.stderr}")
                else:
                    self.logger.info(f"Service {service} is already stopped")
            
            self.logger.info("System locked successfully")
            
        except Exception as e:
            self.logger.error(f"Error locking system: {e}")
    
    def unlock_system(self):
        """Unlock the system - start configured services (stateless)"""
        self.logger.info("Unlocking system...")
        
        try:
            unlock_policies = self.config.get('unlock_policies', {})
            
            # Restore all ports (clear iptables) if configured
            if unlock_policies.get('restore_all_ports', False):
                self.logger.info("Restoring network ports (clearing iptables)")
                subprocess.run(['iptables', '-F'], check=False)
                subprocess.run(['iptables', '-X'], check=False)
            
            # Start configured services (only if stopped)
            services_to_start = self.config.get('services', [])
            for service in services_to_start:
                self.logger.info(f"Checking if service {service} is running...")
                if not self.is_service_running(service, log_check=True):
                    self.logger.info(f"Service {service} is not running - starting it")
                    result = subprocess.run(['systemctl', 'start', service], check=False, capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        self.logger.info(f"Service {service} started successfully")
                    else:
                        self.logger.warning(f"Failed to start service {service}: {result.stderr}")
                else:
                    self.logger.info(f"Service {service} is already running")
            
            self.logger.info("System unlocked successfully")
            
        except Exception as e:
            self.logger.error(f"Error unlocking system: {e}")
    
    def get_connected_android_serials(self) -> List[str]:
        """Get list of connected Android device serials using pyudev and ADB"""
        serials = []
        seen_serials = set()
        
        # First, try to use ADB directly (most reliable method)
        try:
            result = subprocess.run(
                ['adb', 'devices', '-l'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.strip() and not line.startswith('List of devices'):
                        parts = line.split()
                        if len(parts) >= 2 and parts[1] == 'device':
                            # Extract serial from the line
                            serial = parts[0]
                            if serial and serial not in seen_serials:
                                serials.append(serial)
                                seen_serials.add(serial)
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as e:
            self.logger.debug(f"ADB not available or error: {e}")
        
        # Fallback to pyudev detection (less reliable but works without ADB)
        if not serials:
            try:
                context = pyudev.Context()
                
                # Find Android devices via USB - check for devices with ADB interface
                # Look for USB devices in the usb_device subsystem with specific properties
                try:
                    for device in context.list_devices(subsystem='usb'):
                        # Check for Android-specific properties
                        interfaces = device.get('ID_USB_INTERFACES', '')
                        vendor_id = device.get('ID_VENDOR_ID', '').lower()
                        serial = device.get('ID_SERIAL_SHORT') or device.get('ID_SERIAL')
                        
                        # Skip devices without serials
                        if not serial:
                            continue
                        
                        # Android vendor IDs
                        android_vendor_ids = ['18d1', '0bb4', '04e8', '24e3', '0955', '201e', '0e79', '04c5', '2a47']
                        
                        # Check if this looks like an Android device
                        is_android = False
                        
                        # Method 1: Check vendor ID (most reliable)
                        if vendor_id in android_vendor_ids:
                            is_android = True
                        
                        # Method 2: Check for ADB interface class (0xff) - but only if we have a valid serial
                        if not is_android and ':' in interfaces:
                            interface_parts = interfaces.split(':')
                            if len(interface_parts) >= 1:
                                interface_class = interface_parts[0]
                                # ADB uses vendor-specific class 0xff (255)
                                if interface_class.lower() == 'ff' or interface_class == '255':
                                    # Additional check: serial should look like an Android serial
                                    if len(serial) >= 8 and serial.replace('_', '').replace('-', '').isalnum():
                                        is_android = True
                        
                        if is_android:
                            if serial not in seen_serials:
                                # Additional validation: Android serials are typically alphanumeric
                                # Skip PCI addresses and other non-Android identifiers
                                if len(serial) >= 8 and serial.replace('_', '').replace('-', '').isalnum():
                                    # Skip PCI-style addresses (e.g., "0000:01:02.0")
                                    if ':' not in serial or not serial.startswith('0000:'):
                                        serials.append(serial)
                                        seen_serials.add(serial)
                except Exception as e:
                    self.logger.debug(f"Error listing USB devices: {e}")
                
            except Exception as e:
                self.logger.debug(f"Error getting Android serials via pyudev: {e}")
        
        return serials
    
    def is_configured_device_connected(self) -> bool:
        """Check if the configured Android device is connected"""
        if not self.android_serial:
            return False
        
        connected_serials = self.get_connected_android_serials()
        is_connected = self.android_serial in connected_serials
        
        if is_connected:
            self.logger.info(f"Android device {self.android_serial} is connected")
        else:
            self.logger.info(f"Android device {self.android_serial} is NOT connected")
        
        return is_connected
    
    def reload_config(self):
        """Reload configuration from file and log it"""
        try:
            old_config = self.config.copy()
            self.config = self.load_config()
            
            # Update instance variables
            self.android_serial = self.config.get('android_serial') or self.load_android_serial()
            self.mode = self.config.get('mode', 'permissive')
            
            # Log configuration change
            self.logger.info("Configuration reloaded")
            self.log_config()
            
            return True
        except Exception as e:
            self.logger.error(f"Error reloading configuration: {e}")
            return False
    
    def reload_config_handler(self, signum, frame):
        """Handle SIGHUP signal to reload configuration"""
        self.logger.info(f"Received SIGHUP signal, reloading configuration...")
        self.reload_config()
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def run(self):
        """Main service loop"""
        self.logger.info(f"Lock Service started successfully (mode: {self.mode})")
        self.logger.info(f"Monitoring interval: {self.config.get('monitoring', {}).get('check_interval_seconds', 5)} seconds")
        
        # Log configuration on startup
        self.log_config()
        
        if not self.is_configured():
            self.logger.warning("No Android device configured. System will remain unlocked.")
            self.logger.warning("Run \"locker set-android-serial\" to configure a device.")
            # In permissive mode, just wait
            if self.mode == 'permissive':
                while self.running:
                    self.logger.info(f"Waiting for Android device to be configured...")
                    time.sleep(self.config.get('monitoring', {}).get('check_interval_seconds', 5))
                return
        
        # In permissive mode, don't lock on startup
        if self.mode == 'enforcing' and not self.is_configured_device_connected():
            self.logger.info("Enforcing mode: Configured Android device not connected - locking system")
            self.lock_system()
        elif self.mode == 'permissive':
            self.logger.info("Permissive mode: System will not lock even if device is disconnected")
        
        check_interval = self.config.get('monitoring', {}).get('check_interval_seconds', 5)
        was_connected = self.is_configured_device_connected() if self.is_configured() else False
        
        while self.running:
            self.logger.info("Monitor loop iteration started")
            try:
                # Check service status (always check, even if no device configured)
                services = self.config.get('services', [])
                self.logger.info(f"Checking {len(services)} configured service(s): {services}")
                running_services = []
                for service in services:
                    is_running = self.is_service_running(service)
                    if is_running:
                        running_services.append(service)
                    self.logger.info(f"Service '{service}' status: {'RUNNING' if is_running else 'STOPPED'}")
                self.logger.info(f"Running services: {running_services}")
                
                if not self.is_configured():
                    # No device configured - log status and wait
                    self.logger.info(f"No Android device configured - checking configuration...")
                    self.logger.info(f"Monitor: No Android device configured, Mode: {self.mode}, System: UNLOCKED, Services running: {running_services}")
                    self.logger.info(f"Sleeping for {check_interval} seconds before next check")
                    time.sleep(check_interval)
                    continue
                
                self.logger.info(f"Android device configured: {self.android_serial}")
                
                # Check if configured device is connected
                self.logger.info(f"Checking if device {self.android_serial} is connected...")
                is_connected = self.is_configured_device_connected()
                self.logger.info(f"Device {self.android_serial} connection status: {'CONNECTED' if is_connected else 'DISCONNECTED'}")
                
                # Log current status every iteration
                device_status = "CONNECTED" if is_connected else "DISCONNECTED"
                system_status = "UNLOCKED" if is_connected else "LOCKED"
                self.logger.info(f"Monitor: Device {self.android_serial} {device_status}, Mode: {self.mode}, System: {system_status}, Services running: {running_services}")
                self.logger.info(f"Previous connection state: {'CONNECTED' if was_connected else 'DISCONNECTED'}")
                
                # Only enforce locking in enforcing mode
                if self.mode != 'enforcing':
                    self.logger.info(f"Mode is '{self.mode}' (not enforcing) - skipping lock/unlock actions")
                    self.logger.info(f"Sleeping for {check_interval} seconds before next check")
                    time.sleep(check_interval)
                    continue
                
                self.logger.info(f"Mode is 'enforcing' - checking if action needed...")
                
                if is_connected and not was_connected:
                    # Device just connected - unlock
                    self.logger.info(f"State change detected: Device {self.android_serial} just CONNECTED (was disconnected)")
                    self.logger.info(f"Action: Unlocking system")
                    self.unlock_system()
                    was_connected = True
                    self.logger.info(f"Updated connection state: was_connected = True")
                
                elif not is_connected and was_connected:
                    # Device just disconnected - lock
                    self.logger.info(f"State change detected: Device {self.android_serial} just DISCONNECTED (was connected)")
                    self.logger.info(f"Action: Locking system")
                    self.lock_system()
                    was_connected = False
                    self.logger.info(f"Updated connection state: was_connected = False")
                
                elif not is_connected:
                    # Device not connected - check if services are running and lock if needed
                    self.logger.info(f"Device is disconnected (no state change)")
                    if running_services:
                        self.logger.info(f"Services still running: {running_services} - action needed")
                        self.logger.info(f"Action: Locking system to stop running services")
                        self.lock_system()
                    else:
                        self.logger.info(f"No services running - system already locked or no services to manage")
                else:
                    # Device is connected and was connected (no change)
                    self.logger.info(f"Device is connected (no state change) - no action needed")
                
                self.logger.info(f"Sleeping for {check_interval} seconds before next check")
                time.sleep(check_interval)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                time.sleep(5)
        
        self.logger.info("Lock Service stopped")


def main():
    """Entry point for locker command"""
    parser = argparse.ArgumentParser(description='Lock-Down Service')
    parser.add_argument('--config', default='/etc/locker/config.json',
                       help='Configuration file path')
    parser.add_argument('--daemon', action='store_true',
                       help='Run as daemon')
    parser.add_argument('--run-once', action='store_true',
                       help='Run once and exit (check device connection once)')
    parser.add_argument('--mode', choices=['permissive', 'enforcing'],
                       help='Mode: permissive or enforcing (overrides config)')
    parser.add_argument('--android-serial', type=str,
                       help='Android device serial (overrides config)')
    parser.add_argument('--services', nargs='+',
                       help='Services to manage (overrides config)')
    parser.add_argument('--check-interval', type=int,
                       help='Monitoring check interval in seconds (overrides config)')
    
    args = parser.parse_args()
    
    # Build config override from command-line arguments
    config_override = {}
    if args.mode:
        config_override['mode'] = args.mode
    if args.android_serial:
        config_override['android_serial'] = args.android_serial
    if args.services:
        config_override['services'] = args.services
    if args.check_interval:
        if 'monitoring' not in config_override:
            config_override['monitoring'] = {}
        config_override['monitoring']['check_interval_seconds'] = args.check_interval
    
    service = LockService(args.config, config_override=config_override)
    
    # Log service startup
    service.logger.info("=" * 60)
    service.logger.info("Lock-Down Service starting...")
    service.logger.info(f"Configuration file: {args.config}")
    if config_override:
        service.logger.info(f"Command-line overrides: {config_override}")
    service.logger.info("=" * 60)
    
    if args.run_once:
        # Run once mode - check device connection once and act accordingly
        service.logger.info("Running in run-once mode")
        service.log_config()
        
        if not service.is_configured():
            service.logger.warning("No Android device configured")
            return
        
        is_connected = service.is_configured_device_connected()
        
        if service.mode == 'enforcing':
            if is_connected:
                service.logger.info("Device connected - unlocking system")
                service.unlock_system()
            else:
                service.logger.info("Device not connected - locking system")
                service.lock_system()
        else:
            service.logger.info("Permissive mode - no action taken")
    elif args.daemon:
        # Run as daemon
        import daemon
        with daemon.DaemonContext():
            service.run()
    else:
        service.run()


if __name__ == "__main__":
    main()
