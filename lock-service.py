#!/usr/bin/env python3
"""
Lock-Down Service - Main daemon
A security service for Ubuntu systems to lock down devices when the configured Android device is disconnected.
"""

import os
import sys
import json
import time
import signal
import logging
import subprocess
import uuid
from pathlib import Path
from typing import Dict, Optional, List
import argparse


class LockService:
    def __init__(self, config_path: str = "/etc/lock-service/config.json", config_dir: str = None):
        self.config_path = config_path
        self.config = self.load_config()
        self.security_policies = self.load_security_policies()
        self.is_locked = False
        self.running = True
        
        # Setup logging first (needed for error handling)
        self.setup_logging()
        
        # Set config directory (allow override for testing)
        self.config_dir = config_dir or "/etc/lock-service"
        
        # Load configured Android device serial
        self.android_serial = self.load_android_serial()
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        if self.android_serial:
            self.logger.info(f"Lock Service initialized. Configured Android serial: {self.android_serial}")
        else:
            self.logger.warning("Lock Service initialized. No Android device configured - run 'lock-cli setup' first")
        self.logger.info(f"System OS: {self.get_system_info()}")
    
    def load_config(self) -> Dict:
        """Load and validate configuration from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
        except FileNotFoundError:
            # Use default config if file doesn't exist
            default_config_path = Path(__file__).parent / "config" / "init_config.json"
            with open(default_config_path, 'r') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file: {e}")
        
        # Validate required sections
        self.validate_config(config)
        return config
    
    def validate_config(self, config: Dict):
        """Validate configuration structure"""
        required_sections = ['service', 'network', 'monitoring']
        for section in required_sections:
            if section not in config:
                raise ValueError(f"Missing required config section: {section}")
        
        # Validate service section
        if 'log_level' not in config['service']:
            raise ValueError("Missing 'log_level' in service config")
        
        # Validate network section
        if 'blocked_interfaces' not in config['network']:
            raise ValueError("Missing 'blocked_interfaces' in network config")
        
        # Validate monitoring section
        if 'check_interval_seconds' not in config['monitoring']:
            raise ValueError("Missing 'check_interval_seconds' in monitoring config")
    
    def load_security_policies(self) -> Dict:
        """Load security policies from JSON file"""
        try:
            policies_path = Path(__file__).parent / "config" / "security_policies.json"
            with open(policies_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
    
    def setup_logging(self):
        """Setup logging configuration"""
        log_level = getattr(logging, self.config['service']['log_level'].upper())

        # Setup logger
        self.logger = logging.getLogger('lock-service')
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
        """Load configured Android device serial from config"""
        try:
            serial_file = os.path.join(self.config_dir, 'android_serial')
            if os.path.exists(serial_file):
                with open(serial_file, 'r') as f:
                    return f.read().strip()
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"Error loading Android serial: {e}")
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
        """Lock down the system"""
        if self.is_locked:
            return
        
        self.logger.info("Locking system...")
        
        try:
            # Disable SSH
            if self.security_policies.get('lock_policies', {}).get('disable_ssh', True):
                subprocess.run(['systemctl', 'stop', 'ssh'], check=False)
                subprocess.run(['systemctl', 'disable', 'ssh'], check=False)
            
            # Disable network interfaces
            if self.security_policies.get('lock_policies', {}).get('disable_network_interfaces', True):
                for interface in self.config['network']['blocked_interfaces']:
                    subprocess.run(['ip', 'link', 'set', interface, 'down'], check=False)
            
            # Block network ports using iptables
            if self.security_policies.get('lock_policies', {}).get('block_all_ports', True):
                subprocess.run(['iptables', '-A', 'INPUT', '-j', 'DROP'], check=False)
                subprocess.run(['iptables', '-A', 'OUTPUT', '-j', 'DROP'], check=False)
            
            self.is_locked = True
            self.logger.info("System locked successfully")
            
        except Exception as e:
            self.logger.error(f"Error locking system: {e}")
    
    def unlock_system(self):
        """Unlock the system"""
        if not self.is_locked:
            return
        
        self.logger.info("Unlocking system...")
        
        try:
            # Restore network interfaces
            if self.security_policies.get('unlock_policies', {}).get('restore_network_interfaces', True):
                for interface in self.config['network']['blocked_interfaces']:
                    subprocess.run(['ip', 'link', 'set', interface, 'up'], check=False)
            
            # Restore SSH
            if self.security_policies.get('unlock_policies', {}).get('restore_ssh', True):
                subprocess.run(['systemctl', 'enable', 'ssh'], check=False)
                subprocess.run(['systemctl', 'start', 'ssh'], check=False)
            
            # Clear iptables rules
            if self.security_policies.get('unlock_policies', {}).get('restore_all_ports', True):
                subprocess.run(['iptables', '-F'], check=False)
                subprocess.run(['iptables', '-X'], check=False)
            
            self.is_locked = False
            self.logger.info("System unlocked successfully")
            
        except Exception as e:
            self.logger.error(f"Error unlocking system: {e}")
    
    def get_connected_android_serials(self) -> List[str]:
        """Get list of connected Android device serials via ADB"""
        serials = []
        try:
            result = subprocess.run(
                ['adb', 'devices'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return serials
            
            # Parse output - look for devices in "device" state
            lines = result.stdout.strip().split('\n')
            for line in lines[1:]:  # Skip first line "List of devices attached"
                if line.strip() and 'device' in line and 'offline' not in line:
                    parts = line.split()
                    if parts:
                        serials.append(parts[0])
            
        except FileNotFoundError:
            self.logger.debug("ADB not found")
        except subprocess.TimeoutExpired:
            self.logger.warning("ADB command timed out")
        except Exception as e:
            self.logger.debug(f"Error getting Android serials: {e}")
        
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
        self.logger.info("Lock Service started")
        
        if not self.is_configured():
            self.logger.warning("No Android device configured. System will remain unlocked.")
            self.logger.warning("Run 'lock-cli setup' to configure a device.")
        
        # Lock system on startup if configured and device not connected
        if self.is_configured() and not self.is_configured_device_connected():
            self.logger.info("Configured Android device not connected - locking system")
            self.lock_system()
        
        check_interval = self.config.get('monitoring', {}).get('check_interval_seconds', 5)
        was_connected = self.is_configured_device_connected() if self.is_configured() else False
        
        while self.running:
            try:
                if not self.is_configured():
                    # No device configured - just wait
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
                
                elif not is_connected and self.is_configured() and not self.is_locked:
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
    parser = argparse.ArgumentParser(description='Lock-Down Service')
    parser.add_argument('--config', default='/etc/lock-service/config.json',
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
