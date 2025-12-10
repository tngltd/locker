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
    def __init__(self, config_path: str = "/etc/locker/config.json", config_dir: str = None):
        self.config_path = config_path
        self.config = self.load_config()
        self.is_locked = False
        self.running = True
        
        # Setup logging first (needed for error handling)
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
                        "network": {"blocked_interfaces": []},
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
        required_sections = ['service', 'monitoring', 'network']
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
        
        # Validate network section
        if 'blocked_interfaces' not in config['network']:
            raise ValueError("Missing \"blocked_interfaces\" in network config")
        
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
        log_level = getattr(logging, self.config['service']['log_level'].upper())

        # Setup logger
        self.logger = logging.getLogger('locker')
        self.logger.setLevel(log_level)

        # Only add handlers if logging is not disabled for tests
        if log_level < logging.CRITICAL:
            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )

            # Setup file handler
            try:
                file_handler = logging.FileHandler(self.config['service']['log_file'])
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)
            except (OSError, PermissionError):
                # In test environments, file handler might fail - skip it
                pass

            # Setup console handler
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
    
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
    
    def lock_system(self):
        """Lock down the system - stop configured services"""
        if self.is_locked:
            return
        
        self.logger.info("Locking system...")
        
        try:
            lock_policies = self.config.get('lock_policies', {})
            
            # Disable SSH if configured
            if lock_policies.get('disable_ssh', False):
                self.logger.info("Disabling SSH")
                subprocess.run(['systemctl', 'stop', 'ssh'], check=False)
                subprocess.run(['systemctl', 'disable', 'ssh'], check=False)
            
            # Disable network interfaces if configured
            if lock_policies.get('disable_network_interfaces', False):
                blocked_interfaces = self.config.get('network', {}).get('blocked_interfaces', [])
                for interface in blocked_interfaces:
                    self.logger.info(f"Disabling network interface: {interface}")
                    subprocess.run(['ip', 'link', 'set', interface, 'down'], check=False)
            
            # Block all ports with iptables if configured
            if lock_policies.get('block_all_ports', False):
                self.logger.info("Blocking all ports with iptables")
                # Block INPUT chain
                subprocess.run(['iptables', '-A', 'INPUT', '-j', 'DROP'], check=False)
                # Block OUTPUT chain
                subprocess.run(['iptables', '-A', 'OUTPUT', '-j', 'DROP'], check=False)
                # Block FORWARD chain
                subprocess.run(['iptables', '-A', 'FORWARD', '-j', 'DROP'], check=False)
            
            # Stop configured services
            services_to_stop = self.config.get('services', [])
            for service in services_to_stop:
                self.logger.info(f"Stopping service: {service}")
                subprocess.run(['systemctl', 'stop', service], check=False)
                subprocess.run(['systemctl', 'disable', service], check=False)
            
            self.is_locked = True
            self.logger.info("System locked successfully")
            
        except Exception as e:
            self.logger.error(f"Error locking system: {e}")
    
    def unlock_system(self):
        """Unlock the system - start configured services"""
        if not self.is_locked:
            return
        
        self.logger.info("Unlocking system...")
        
        try:
            unlock_policies = self.config.get('unlock_policies', {})
            
            # Restore network interfaces if configured
            if unlock_policies.get('restore_network_interfaces', False):
                blocked_interfaces = self.config.get('network', {}).get('blocked_interfaces', [])
                for interface in blocked_interfaces:
                    self.logger.info(f"Restoring network interface: {interface}")
                    subprocess.run(['ip', 'link', 'set', interface, 'up'], check=False)
            
            # Restore SSH if configured
            if unlock_policies.get('restore_ssh', False):
                self.logger.info("Restoring SSH")
                subprocess.run(['systemctl', 'enable', 'ssh'], check=False)
                subprocess.run(['systemctl', 'start', 'ssh'], check=False)
            
            # Restore all ports (clear iptables) if configured
            if unlock_policies.get('restore_all_ports', False):
                self.logger.info("Restoring network ports (clearing iptables)")
                # Flush all chains
                subprocess.run(['iptables', '-F'], check=False)
                # Delete all user-defined chains
                subprocess.run(['iptables', '-X'], check=False)
            
            # Start configured services
            services_to_start = self.config.get('services', [])
            for service in services_to_start:
                self.logger.info(f"Starting service: {service}")
                subprocess.run(['systemctl', 'enable', service], check=False)
                subprocess.run(['systemctl', 'start', service], check=False)
            
            self.is_locked = False
            self.logger.info("System unlocked successfully")
            
        except Exception as e:
            self.logger.error(f"Error unlocking system: {e}")
    
    def get_connected_android_serials(self) -> List[str]:
        """Get list of connected Android device serials using pyudev"""
        serials = []
        seen_serials = set()
        try:
            context = pyudev.Context()
            
            # Find Android devices via USB
            # Android devices typically have vendor ID 18d1 (Google) or other Android vendor IDs
            # We look for USB devices that are Android devices
            android_vendor_ids = ['18d1', '0bb4', '04e8', '24e3', '0955', '201e', '0e79', '04c5']
            
            for vendor_id in android_vendor_ids:
                try:
                    for device in context.list_devices(subsystem='usb', ID_VENDOR_ID=vendor_id):
                        serial = device.get('ID_SERIAL_SHORT') or device.get('ID_SERIAL')
                        if serial and serial not in seen_serials:
                            # Also check if device is in 'device' state (not offline)
                            # We can check the device state via sysfs
                            device_path = device.get('DEVPATH')
                            if device_path:
                                # Check if device is actually connected and active
                                # USB devices that are connected will have a valid serial
                                serials.append(serial)
                                seen_serials.add(serial)
                except Exception:
                    continue
            
            # Also check for devices via usb subsystem more broadly
            # Look for devices with ID_USB_INTERFACES containing Android Debug Bridge protocol
            try:
                for device in context.list_devices(subsystem='usb'):
                    # Check if this is an Android device by looking for Android Debug Bridge interface
                    interfaces = device.get('ID_USB_INTERFACES', '')
                    if 'adb' in interfaces.lower() or ':' in device.get('ID_USB_INTERFACES', ''):
                        serial = device.get('ID_SERIAL_SHORT') or device.get('ID_SERIAL')
                        if serial and serial not in seen_serials:
                            serials.append(serial)
                            seen_serials.add(serial)
            except Exception:
                pass
            
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
            self.logger.debug(f"Configured device {self.android_serial} is connected")
        
        return is_connected
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def run(self):
        """Main service loop"""
        self.logger.info(f"Lock Service started (mode: {self.mode})")
        
        if not self.is_configured():
            self.logger.warning("No Android device configured. System will remain unlocked.")
            self.logger.warning("Run \"locker set-android-serial\" to configure a device.")
            # In permissive mode, just wait
            if self.mode == 'permissive':
                while self.running:
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
            try:
                if not self.is_configured():
                    # No device configured - just wait
                    time.sleep(check_interval)
                    continue
                
                # Only enforce locking in enforcing mode
                if self.mode != 'enforcing':
                    time.sleep(check_interval)
                    continue
                
                # Check if configured device is connected
                is_connected = self.is_configured_device_connected()
                
                if is_connected and not was_connected:
                    # Device just connected - unlock
                    self.logger.info(f"Android device {self.android_serial} connected - unlocking system")
                    self.unlock_system()
                    was_connected = True
                
                elif not is_connected and was_connected:
                    # Device just disconnected - lock
                    self.logger.info(f"Android device {self.android_serial} disconnected - locking system")
                    self.lock_system()
                    was_connected = False
                
                elif not is_connected and not self.is_locked:
                    # Device not connected and system not locked - lock it
                    self.logger.info("Configured device not connected - locking system")
                    self.lock_system()
                
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
    
    args = parser.parse_args()
    
    service = LockService(args.config)
    
    if args.daemon:
        # Run as daemon
        import daemon
        with daemon.DaemonContext():
            service.run()
    else:
        service.run()


if __name__ == "__main__":
    main()
