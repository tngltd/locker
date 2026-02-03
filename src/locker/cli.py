#!/usr/bin/env python3
"""
Lock-Down Service CLI Tool
Command line interface for managing the lock-down service.
"""

import os
import argparse
import subprocess
import time
import warnings
from typing import Optional, List
from locker import utils
from locker import config


class LockCLI:
    def __init__(self):
        self.config_path = "/etc/locker/config.json"
        self.config_dir = "/etc/locker"
        self.pid_file = "/var/run/locker.pid"
        self.service_pid_file = self.pid_file  # Alias for test compatibility
    
    def load_config(self):
        """Load configuration from config_path. Used by tests and for consistency."""
        return config.load_config(self.config_path)

    def save_config(self, config_dict: dict, suggested_sudo_cmd: Optional[str] = None):
        """Save configuration to config_path. Used by tests and for consistency."""
        config.save_config(config_dict, self.config_path, suggested_sudo_cmd=suggested_sudo_cmd)

    def get_android_serial(self) -> Optional[str]:
        """Get configured Android device serial (try config.json first, then file as fallback)"""
        loaded_config = config.load_config(self.config_path)
        return loaded_config['android_serial']
    
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
        
        devices = utils.get_connected_devices()
        
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
            devices = utils.get_connected_devices()
            
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
            loaded_config = self.load_config()
            loaded_config['android_serial'] = serial
            self.save_config(loaded_config, suggested_sudo_cmd="sudo locker set-android-serial")
            print()
            print(f"Android serial configured: {serial}")
        except PermissionError as e:
            print(e)
            return
        except Exception as e:
            print(f"Error saving configuration: {e}")
            return

    
    def add_service(self, service_name: str):
        """Add a service to be managed (started on connection, stopped on disconnection)"""
        print("=== Add Service ===")
        print()
        
        try:
            loaded_config = self.load_config()
            if 'services' not in loaded_config:
                loaded_config['services'] = []
            elif not isinstance(loaded_config['services'], list):
                # Convert old format to new format
                if isinstance(loaded_config['services'], dict):
                    old_stop = loaded_config['services'].get('stop_when_locked', [])
                    old_start = loaded_config['services'].get('start_when_unlocked', [])
                    loaded_config['services'] = list(set(old_stop + old_start))
                else:
                    loaded_config['services'] = []
            
            services_list = loaded_config['services']
            if service_name not in services_list:
                services_list.append(service_name)
                loaded_config['services'] = services_list
                try:
                    self.save_config(loaded_config, suggested_sudo_cmd=f"sudo locker add-service {service_name}")
                    print(f"Service \"{service_name}\" added. It will be started when device connects and stopped when device disconnects.")
                except PermissionError as e:
                    print(e)
                    return
            else:
                print(f"Service \"{service_name}\" is already in the services list.")
        except Exception as e:
            print(f"Error adding service: {e}")
    
    def remove_service(self, service_name: str):
        """Remove a service from being managed"""
        print("=== Remove Service ===")
        print()
        
        try:
            loaded_config = self.load_config()
            if 'services' not in loaded_config:
                loaded_config['services'] = []
            elif not isinstance(loaded_config['services'], list):
                # Convert old format to new format
                if isinstance(loaded_config['services'], dict):
                    old_stop = loaded_config['services'].get('stop_when_locked', [])
                    old_start = loaded_config['services'].get('start_when_unlocked', [])
                    loaded_config['services'] = list(set(old_stop + old_start))
                else:
                    loaded_config['services'] = []
            
            services_list = loaded_config['services']
            if service_name in services_list:
                services_list.remove(service_name)
                loaded_config['services'] = services_list
                try:
                    self.save_config(loaded_config, suggested_sudo_cmd=f"sudo locker remove-service {service_name}")
                    print(f"Service \"{service_name}\" removed. It will no longer be managed by the locker service.")
                except PermissionError as e:
                    print(e)
                    return
            else:
                print(f"Service \"{service_name}\" is not in the services list.")
        except PermissionError as e:
            print(e)
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
            loaded_config = self.load_config()
            
            # In enforcing mode, require Android serial to be configured
            if mode == 'enforcing':
                serial = loaded_config.get('android_serial')
                if not serial:
                    print("Error: Cannot set enforcing mode without configured Android serial.")
                    print("Run \"locker set-android-serial\" first.")
                    return
            
            loaded_config['mode'] = mode
            try:
                self.save_config(loaded_config, suggested_sudo_cmd=f"sudo locker set-mode {mode}")
                print(f"Mode set to: {mode}")
                
                if mode == 'enforcing':
                    print()
                    print("WARNING: In enforcing mode, the system will lock if the configured")
                    print("         Android device is not connected.")
            except PermissionError as e:
                print(e)
                return
        except PermissionError as e:
            print(e)
        except Exception as e:
            print(f"Error setting mode: {e}")
    
    def logs(self, lines: int = 50, follow: bool = False):
        """Show service logs"""
        try:
            loaded_config = self.load_config()
            log_file = loaded_config['service'].get('log_file', '/var/log/locker.log')
        except:
            log_file = "/var/log/locker.log"
        
        if not os.path.exists(log_file):
            print(f"No log file found at {log_file}")
            print("The log file will be created when the service starts.")
            print("Start the service with: systemctl start locker")
            print("Or run the service directly: lockerd")
            return
        
        # Check if file is empty (only if not following)
        if not follow:
            try:
                if os.path.getsize(log_file) == 0:
                    print(f"Log file exists but is empty: {log_file}")
                    print("The service may not have started yet or no logs have been written.")
                    return
            except OSError:
                # File might have been deleted between exists() and getsize()
                print(f"Log file no longer accessible: {log_file}")
                return
        
        if follow:
            # Follow mode - use tail -f
            try:
                subprocess.run(['tail', '-f', log_file])
            except FileNotFoundError:
                print("Error: tail command not found. Follow mode requires tail.")
            except KeyboardInterrupt:
                print("\nStopped following logs.")
        else:
            # Regular mode - show last N lines
            try:
                subprocess.run(['tail', '-n', str(lines), log_file])
            except FileNotFoundError:
                # tail command not found, fall back to reading file directly
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
        """Check if the locker service is running (check PID file first, then systemctl)"""
        # Check PID file if available
        pid_file = getattr(self, 'service_pid_file', None) or self.pid_file
        if pid_file and os.path.exists(pid_file):
            try:
                with open(pid_file, 'r') as f:
                    pid_str = f.read().strip()
                    if pid_str:
                        pid = int(pid_str)
                        # Check if process is actually running
                        try:
                            os.kill(pid, 0)  # Signal 0 doesn't kill, just checks if process exists
                            return True
                        except (OSError, ProcessLookupError):
                            return False
            except (ValueError, IOError):
                pass
        
        # Fall back to systemctl check
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', 'locker'],
                capture_output=True,
                text=True,
                timeout=5,
                check=False
            )
            return result.returncode == 0 and result.stdout.strip() == 'active'
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
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
            loaded_config = self.load_config()
            loaded_config['android_serial'] = serial
            self.save_config(loaded_config, suggested_sudo_cmd="sudo locker set-android-serial")
        except PermissionError as e:
            print(e)
        except Exception as e:
            print(f"Error saving Android serial: {e}")
    
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
            loaded_config = self.load_config()
            
            # Start configured services (only if not running)
            services = loaded_config.get('services', [])
            for service_name in services:
                try:
                    # Check if service is already running before starting
                    result = subprocess.run(
                        ['systemctl', 'is-active', '--quiet', service_name],
                        capture_output=True,
                        timeout=2
                    )
                    if result.returncode != 0:
                        # Service is not running, start it
                        subprocess.run(['systemctl', 'start', service_name], check=False, timeout=5)
                    else:
                        print(f"Service {service_name} is already running")
                except Exception as e:
                    print(f"Error starting service {service_name}: {e}")
            
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
            devices = utils.get_connected_devices()
            connected_serials = [d[0] for d in devices]
            if serial in connected_serials:
                print("Status: CONNECTED")
            else:
                print("Status: DISCONNECTED")
        print()
        
        # System lock status (based on services)
        loaded_config = self.load_config()
        services = loaded_config.get('services', [])
        if services:
            print("Configured services:")
            for service_name in services:
                try:
                    result = subprocess.run(
                        ['systemctl', 'is-active', '--quiet', service_name],
                        capture_output=True,
                        timeout=2
                    )
                    status = "RUNNING" if result.returncode == 0 else "STOPPED"
                    print(f"  {service_name}: {status}")
                except Exception:
                    print(f"  {service_name}: UNKNOWN")
        else:
            print("No services configured")


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
    logs_parser = subparsers.add_parser('logs', help='Show service logs')
    logs_parser.add_argument('-n', '--lines', type=int, default=50,
                           help='Number of log lines to show')
    logs_parser.add_argument('-f', '--follow', action='store_true',
                           help='Follow log file (like tail -f)')
    
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
    elif args.command == 'logs':
        cli.logs(args.lines, args.follow)


if __name__ == "__main__":
    main()
