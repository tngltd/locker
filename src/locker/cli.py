#!/usr/bin/env python3
"""
Lock-Down Service CLI Tool
Command line interface for managing the lock-down service.
"""

import os
import sys
import json
import argparse
import subprocess
import time
from pathlib import Path
from typing import Optional, List
import pyudev


class LockCLI:
    def __init__(self):
        self.config_path = "/etc/locker/config.json"
        self.config_dir = "/etc/locker"
        self.pid_file = "/var/run/locker.pid"
        self.service_pid_file = self.pid_file  # Alias for test compatibility
    
    def load_config(self) -> dict:
        """Load configuration"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print("Error: Configuration file not found.")
            sys.exit(1)
    
    def get_android_serial(self) -> Optional[str]:
        """Get configured Android device serial from config or file"""
        try:
            config = self.load_config()
            serial = config.get('android_serial')
            if serial:
                return serial
        except:
            pass
        
        # Fallback to file (legacy)
        try:
            serial_file = os.path.join(self.config_dir, 'android_serial')
            if os.path.exists(serial_file):
                with open(serial_file, 'r') as f:
                    return f.read().strip()
        except:
            pass
        return None
    
    def save_config(self, config: dict):
        """Save configuration to file and log the change"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)
        os.chmod(self.config_path, 0o644)
        
        # Log configuration change to service log file
        self._log_config_change(config)
    
    def _log_config_change(self, config: dict):
        """Log configuration change to service log file"""
        try:
            log_file = config.get('service', {}).get('log_file', '/var/log/locker.log')
            
            # Setup a logger that writes to the service log file
            import logging
            logger = logging.getLogger('locker.cli')
            logger.setLevel(logging.INFO)
            
            # Remove existing handlers to avoid duplicates
            logger.handlers.clear()
            
            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            
            # Try to add file handler
            try:
                # Ensure log directory exists
                log_dir = os.path.dirname(log_file)
                if log_dir:
                    os.makedirs(log_dir, exist_ok=True)
                
                file_handler = logging.FileHandler(log_file)
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
                
                # Log configuration change
                logger.info("Configuration changed via CLI")
                
                # Log key configuration values
                logger.info(f"  Mode: {config.get('mode', 'permissive')}")
                android_serial = config.get('android_serial', 'Not configured')
                if android_serial and len(android_serial) > 20:
                    android_serial = android_serial[:10] + "..." + android_serial[-7:]
                logger.info(f"  Android Serial: {android_serial}")
                logger.info(f"  Services: {config.get('services', [])}")
                logger.info(f"  Monitoring Interval: {config.get('monitoring', {}).get('check_interval_seconds', 5)} seconds")
                
                # Close handler
                file_handler.close()
                logger.removeHandler(file_handler)
            except (OSError, PermissionError):
                # If we can't write to log file, silently fail (CLI shouldn't require root)
                pass
        except Exception:
            # Silently fail if logging fails
            pass
    
    def get_connected_devices(self) -> List[tuple]:
        """Get list of connected Android devices (serial, model) using ADB and pyudev"""
        devices = []
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
                            serial = parts[0]
                            # Extract model from the line if available
                            model = 'Unknown'
                            for part in parts:
                                if 'model:' in part.lower():
                                    model = part.split(':', 1)[1].replace('_', ' ').title()
                                    break
                            if serial and serial not in seen_serials:
                                devices.append((serial, model))
                                seen_serials.add(serial)
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            # ADB not available, fall back to pyudev
            pass
        
        # Fallback to pyudev detection (less reliable but works without ADB)
        if not devices:
            try:
                context = pyudev.Context()
                
                # Android vendor IDs
                android_vendor_ids = ['18d1', '0bb4', '04e8', '24e3', '0955', '201e', '0e79', '04c5', '2a47']
                
                try:
                    for device in context.list_devices(subsystem='usb'):
                        interfaces = device.get('ID_USB_INTERFACES', '')
                        vendor_id = device.get('ID_VENDOR_ID', '').lower()
                        serial = device.get('ID_SERIAL_SHORT') or device.get('ID_SERIAL')
                        
                        # Skip devices without serials
                        if not serial:
                            continue
                        
                        # Check if this looks like an Android device
                        is_android = False
                        
                        # Method 1: Check vendor ID (most reliable)
                        if vendor_id in android_vendor_ids:
                            is_android = True
                        
                        # Method 2: Check for ADB interface class (0xff) - but only if we have a valid serial
                        # This is less reliable but helps catch devices that might not be in vendor list
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
                                        model = device.get('ID_MODEL', 'Unknown')
                                        model = model.replace('_', ' ').title()
                                        devices.append((serial, model))
                                        seen_serials.add(serial)
                except Exception as e:
                    # Log error but continue
                    pass
                    
            except Exception as e:
                print(f"Error getting devices: {e}")
        
        return devices
    
    def get_android_serial_cmd(self):
        """Get Android serial from config"""
        print("=== Get Android Serial ===")
        print()
        
        serial = self.get_android_serial()
        
        if not serial:
            print("No Android serial configured.")
            print()
            print("Use \"locker set-android-serial\" to configure a device.")
        else:
            print(f"Configured Android serial: {serial}")
    
    def list_devices_cmd(self):
        """List all connected Android devices"""
        print("=== List Connected Devices ===")
        print()
        
        devices = self.get_connected_devices()
        
        if not devices:
            print("No Android devices found.")
            print()
            print("Please ensure:")
            print("  1. Your Android device is connected via USB")
            print("  2. USB debugging is enabled on the device")
            return
        
        print("Connected Android devices:")
        print("-" * 50)
        for i, (serial, model) in enumerate(devices, 1):
            print(f"  {i}. {serial} ({model})")
        print("-" * 50)
        print()
        
        configured_serial = self.get_android_serial()
        if configured_serial:
            if configured_serial in [d[0] for d in devices]:
                print(f"Configured device ({configured_serial}) is currently connected.")
            else:
                print(f"Configured device ({configured_serial}) is not currently connected.")
    
    def set_android_serial(self, serial: Optional[str] = None):
        """Set Android device serial"""
        print("=== Set Android Serial ===")
        print()
        
        # If serial not provided, show connected devices
        if not serial:
            devices = self.get_connected_devices()
            
            if not devices:
                print("No Android devices found.")
                print()
                print("Please ensure:")
                print("  1. Your Android device is connected via USB")
                print("  2. USB debugging is enabled on the device")
                print()
                response = input("Enter device serial manually? (y/N): ")
                if response.lower() == 'y':
                    serial = input("Enter Android device serial: ").strip()
                else:
                    print("Cancelled.")
                    return
            else:
                print("Connected Android devices:")
                print("-" * 50)
                for i, (serial_dev, model) in enumerate(devices, 1):
                    print(f"  {i}. {serial_dev} ({model})")
                print("-" * 50)
                print()
                
                if len(devices) == 1:
                    response = input(f"Use device {devices[0][0]}? (Y/n): ")
                    if response.lower() != 'n':
                        serial = devices[0][0]
                    else:
                        print("Cancelled.")
                        return
                else:
                    try:
                        choice = input(f"Select device (1-{len(devices)}) or enter serial: ").strip()
                        try:
                            idx = int(choice) - 1
                            if 0 <= idx < len(devices):
                                serial = devices[idx][0]
                            else:
                                print("Invalid selection.")
                                return
                        except ValueError:
                            # User entered serial directly
                            serial = choice
                    except KeyboardInterrupt:
                        print("\nCancelled.")
                        return
        
        if not serial:
            print("No serial provided.")
            return
        
        # Save to config
        try:
            config = self.load_config()
            config['android_serial'] = serial
            self.save_config(config)
            print()
            print(f"Android serial configured: {serial}")
        except Exception as e:
            print(f"Error saving configuration: {e}")
    
    
    def add_service(self, service_name: str):
        """Add a service to be managed (started on connection, stopped on disconnection)"""
        print("=== Add Service ===")
        print()
        
        try:
            config = self.load_config()
            if 'services' not in config:
                config['services'] = []
            elif not isinstance(config['services'], list):
                # Convert old format to new format
                if isinstance(config['services'], dict):
                    old_stop = config['services'].get('stop_when_locked', [])
                    old_start = config['services'].get('start_when_unlocked', [])
                    config['services'] = list(set(old_stop + old_start))
                else:
                    config['services'] = []
            
            services_list = config['services']
            if service_name not in services_list:
                services_list.append(service_name)
                config['services'] = services_list
                self.save_config(config)
                print(f"Service \"{service_name}\" added. It will be started when device connects and stopped when device disconnects.")
            else:
                print(f"Service \"{service_name}\" is already in the services list.")
        except Exception as e:
            print(f"Error adding service: {e}")
    
    def remove_service(self, service_name: str):
        """Remove a service from being managed"""
        print("=== Remove Service ===")
        print()
        
        try:
            config = self.load_config()
            if 'services' not in config:
                config['services'] = []
            elif not isinstance(config['services'], list):
                # Convert old format to new format
                if isinstance(config['services'], dict):
                    old_stop = config['services'].get('stop_when_locked', [])
                    old_start = config['services'].get('start_when_unlocked', [])
                    config['services'] = list(set(old_stop + old_start))
                else:
                    config['services'] = []
            
            services_list = config['services']
            if service_name in services_list:
                services_list.remove(service_name)
                config['services'] = services_list
                self.save_config(config)
                print(f"Service \"{service_name}\" removed. It will no longer be managed by the locker service.")
            else:
                print(f"Service \"{service_name}\" is not in the services list.")
        except Exception as e:
            print(f"Error removing service: {e}")
    
    def set_mode(self, mode: Optional[str] = None):
        """Set mode to permissive or enforcing"""
        print("=== Set Mode ===")
        print()
        
        if not mode:
            current_mode = self.load_config().get('mode', 'permissive')
            print(f"Current mode: {current_mode}")
            print()
            print("Modes:")
            print("  permissive - System will not lock even if device is disconnected")
            print("  enforcing - System will lock when device is disconnected")
            print()
            response = input("Enter mode (permissive/enforcing): ").strip().lower()
            if response in ['permissive', 'enforcing']:
                mode = response
            else:
                print("Invalid mode. Must be \"permissive\" or \"enforcing\"")
                return
        
        if mode not in ['permissive', 'enforcing']:
            print("Error: Mode must be \"permissive\" or \"enforcing\"")
            return
        
        try:
            config = self.load_config()
            
            # In enforcing mode, require Android serial to be configured
            if mode == 'enforcing':
                serial = config.get('android_serial')
                if not serial:
                    print("Error: Cannot set enforcing mode without configured Android serial.")
                    print("Run \"locker set-android-serial\" first.")
                    return
            
            config['mode'] = mode
            self.save_config(config)
            print(f"Mode set to: {mode}")
            
            if mode == 'enforcing':
                print()
                print("WARNING: In enforcing mode, the system will lock if the configured")
                print("         Android device is not connected.")
        except Exception as e:
            print(f"Error setting mode: {e}")
    
    def logs(self, lines: int = 50):
        """Show service logs"""
        try:
            config = self.load_config()
            log_file = config.get('service', {}).get('log_file', '/var/log/locker.log')
        except:
            log_file = "/var/log/locker.log"
        
        if not os.path.exists(log_file):
            print(f"No log file found at {log_file}")
            print("The log file will be created when the service starts.")
            print("Start the service with: systemctl start locker")
            print("Or run the service directly: lockerd")
            return
        
        try:
            # Check if file is empty
            if os.path.getsize(log_file) == 0:
                print(f"Log file exists but is empty: {log_file}")
                print("The service may not have started yet or no logs have been written.")
                return
            
            subprocess.run(['tail', '-n', str(lines), log_file])
        except FileNotFoundError:
            # Fallback to reading file directly
            try:
                with open(log_file, 'r') as f:
                    all_lines = f.readlines()
                    if not all_lines:
                        print(f"Log file exists but is empty: {log_file}")
                        return
                    for line in all_lines[-lines:]:
                        print(line.rstrip())
            except Exception as e:
                print(f"Error reading log file: {e}")
    
    def is_service_running(self) -> bool:
        """Check if the locker systemd service is running"""
        # First try systemctl
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', 'locker'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip() == 'active':
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            pass
        
        # Fallback: check PID file
        pid_file = getattr(self, 'service_pid_file', self.pid_file)
        if os.path.exists(pid_file):
            try:
                with open(pid_file, 'r') as f:
                    pid = int(f.read().strip())
                    # Check if process exists (os.kill with 0 signal just checks existence)
                    os.kill(pid, 0)
                    return True
            except (ValueError, OSError):
                return False
        return False
    
    def start_service(self):
        """Start the locker systemd service"""
        if self.is_service_running():
            print("Service is already running.")
            return
        
        try:
            result = subprocess.run(
                ['systemctl', 'start', 'locker'],
                capture_output=True,
                text=True,
                timeout=10,
                check=True
            )
            print("Service started successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to start service: {e.stderr}")
        except FileNotFoundError:
            print("Error: systemctl not found. Cannot start service.")
        except subprocess.TimeoutExpired:
            print("Error: Service start command timed out.")
        except Exception as e:
            print(f"Error starting service: {e}")
    
    def stop_service(self):
        """Stop the locker systemd service"""
        if not self.is_service_running():
            print("Service is not running.")
            return
        
        try:
            result = subprocess.run(
                ['systemctl', 'stop', 'locker'],
                capture_output=True,
                text=True,
                timeout=10,
                check=True
            )
            print("Service stopped successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to stop service: {e.stderr}")
        except FileNotFoundError:
            print("Error: systemctl not found. Cannot stop service.")
        except subprocess.TimeoutExpired:
            print("Error: Service stop command timed out.")
        except Exception as e:
            print(f"Error stopping service: {e}")
    
    def restart_service(self):
        """Restart the locker systemd service"""
        self.stop_service()
        time.sleep(1)  # Brief pause between stop and start
        self.start_service()
    
    def save_android_serial(self, serial: str):
        """Save Android device serial to config"""
        try:
            config = self.load_config()
            config['android_serial'] = serial
            self.save_config(config)
        except Exception as e:
            print(f"Error saving Android serial: {e}")
    
    def setup(self):
        """Interactive setup for configuring the service"""
        print("=== Lock Service Setup ===")
        print()
        
        # Check if already configured
        existing_serial = self.get_android_serial()
        if existing_serial:
            print(f"Current configuration: {existing_serial}")
            print()
            response = input("Reconfigure? (y/N): ").strip().lower()
            if response != 'y':
                print("Setup cancelled.")
                return
        
        # Get connected devices
        devices = self.get_connected_devices()
        
        if not devices:
            print("No Android devices found.")
            print()
            response = input("Enter device serial manually? (y/N): ").strip().lower()
            if response == 'y':
                serial = input("Enter Android device serial: ").strip()
                if serial:
                    self.save_android_serial(serial)
                    print(f"Android serial configured: {serial}")
            else:
                print("Setup cancelled.")
            return
        
        # Show devices
        print("Connected Android devices:")
        print("-" * 50)
        for i, (serial, model) in enumerate(devices, 1):
            print(f"  {i}. {serial} ({model})")
        print("-" * 50)
        print()
        
        if len(devices) == 1:
            response = input(f"Use device {devices[0][0]}? (Y/n): ").strip().lower()
            if response != 'n':
                self.save_android_serial(devices[0][0])
                print(f"Android serial configured: {devices[0][0]}")
        else:
            try:
                choice = input(f"Select device (1-{len(devices)}) or enter serial: ").strip()
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(devices):
                        self.save_android_serial(devices[idx][0])
                        print(f"Android serial configured: {devices[idx][0]}")
                    else:
                        print("Invalid selection.")
                except ValueError:
                    # User entered serial directly
                    if choice:
                        self.save_android_serial(choice)
                        print(f"Android serial configured: {choice}")
            except KeyboardInterrupt:
                print("\nSetup cancelled.")
    
    def emergency_unlock(self):
        """Emergency unlock - manually unlock system without device"""
        print("=== Emergency Unlock ===")
        print()
        print("WARNING: This will unlock the system even if the configured")
        print("Android device is not connected.")
        print()
        
        response = input("Are you sure you want to unlock? (yes/no): ").strip().lower()
        if response != 'yes':
            print("Cancelled.")
            return
        
        try:
            config = self.load_config()
            blocked_interfaces = config.get('network', {}).get('blocked_interfaces', [])
            
            # Restore network interfaces
            for interface in blocked_interfaces:
                try:
                    subprocess.run(['ip', 'link', 'set', interface, 'up'], check=False, timeout=5)
                except Exception as e:
                    print(f"Error restoring interface {interface}: {e}")
            
            # Restore SSH
            try:
                subprocess.run(['systemctl', 'enable', 'ssh'], check=False, timeout=5)
                subprocess.run(['systemctl', 'start', 'ssh'], check=False, timeout=5)
            except Exception as e:
                print(f"Error restoring SSH: {e}")
            
            # Clear iptables
            try:
                subprocess.run(['iptables', '-F'], check=False, timeout=5)
                subprocess.run(['iptables', '-X'], check=False, timeout=5)
            except Exception as e:
                print(f"Error clearing iptables: {e}")
            
            print("System unlocked successfully.")
        except Exception as e:
            print(f"Error unlocking system: {e}")
    
    def status(self):
        """Show service status"""
        print("=== Lock Service Status ===")
        print()
        
        # Service running status
        is_running = self.is_service_running()
        print(f"Service running: {'Yes' if is_running else 'No'}")
        print()
        
        # Device configuration
        serial = self.get_android_serial()
        if not serial:
            print("Android device: Not configured")
        else:
            print(f"Android device: {serial}")
            devices = self.get_connected_devices()
            connected_serials = [d[0] for d in devices]
            if serial in connected_serials:
                print("Status: CONNECTED")
            else:
                print("Status: DISCONNECTED")
        print()
        
        # System lock status (check iptables)
        try:
            result = subprocess.run(
                ['iptables', '-L', 'INPUT', '-n'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                if 'DROP' in result.stdout:
                    print("System status: LOCKED")
                else:
                    print("System status: UNLOCKED")
            else:
                print("System status: Unknown")
        except Exception:
            print("System status: Unknown")


def main():
    """Entry point for locker command"""
    parser = argparse.ArgumentParser(description='Lock-Down Service CLI')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Device commands
    subparsers.add_parser('get-android-serial', help='Get serial of connected Android device')
    set_serial_parser = subparsers.add_parser('set-android-serial', help='Configure Android device serial')
    set_serial_parser.add_argument('serial', nargs='?', help='Android device serial (optional, will prompt if not provided)')
    
    subparsers.add_parser('list-devices', help='List connected Android devices')
    
    # Service management
    add_service_parser = subparsers.add_parser('add-service', help='Add service to be managed (started on connection, stopped on disconnection)')
    add_service_parser.add_argument('service', help='Service name (e.g., ssh, nginx)')
    
    remove_service_parser = subparsers.add_parser('remove-service', help='Remove service from being managed')
    remove_service_parser.add_argument('service', help='Service name (e.g., ssh, nginx)')
    
    # Mode management
    set_mode_parser = subparsers.add_parser('set-mode', help='Set mode (permissive/enforcing)')
    set_mode_parser.add_argument('mode', nargs='?', choices=['permissive', 'enforcing'],
                                help='Mode: permissive (no locking) or enforcing (lock when device disconnected)')
    
    # Utility commands
    subparsers.add_parser('setup', help='Interactive setup for configuring the service')
    logs_parser = subparsers.add_parser('logs', help='Show service logs')
    logs_parser.add_argument('-n', '--lines', type=int, default=50,
                           help='Number of log lines to show')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    cli = LockCLI()
    
    if args.command == 'get-android-serial':
        cli.get_android_serial_cmd()
    elif args.command == 'set-android-serial':
        cli.set_android_serial(getattr(args, 'serial', None))
    elif args.command == 'list-devices':
        cli.list_devices_cmd()
    elif args.command == 'add-service':
        cli.add_service(args.service)
    elif args.command == 'remove-service':
        cli.remove_service(args.service)
    elif args.command == 'set-mode':
        cli.set_mode(getattr(args, 'mode', None))
    elif args.command == 'setup':
        cli.setup()
    elif args.command == 'logs':
        cli.logs(args.lines)


if __name__ == "__main__":
    main()
