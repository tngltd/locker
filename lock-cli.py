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


class LockCLI:
    def __init__(self):
        self.config_path = "/etc/lock-service/config.json"
        self.config_dir = "/etc/lock-service"
        self.service_pid_file = "/var/run/lock-service.pid"
    
    def load_config(self) -> dict:
        """Load configuration"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print("Error: Configuration file not found.")
            sys.exit(1)
    
    def get_android_serial(self) -> Optional[str]:
        """Get configured Android device serial"""
        try:
            serial_file = os.path.join(self.config_dir, 'android_serial')
            if os.path.exists(serial_file):
                with open(serial_file, 'r') as f:
                    return f.read().strip()
        except Exception:
            pass
        return None
    
    def save_android_serial(self, serial: str):
        """Save Android device serial"""
        os.makedirs(self.config_dir, exist_ok=True)
        serial_file = os.path.join(self.config_dir, 'android_serial')
        with open(serial_file, 'w') as f:
            f.write(serial)
        os.chmod(serial_file, 0o600)
    
    def get_connected_devices(self) -> List[tuple]:
        """Get list of connected Android devices (serial, model)"""
        devices = []
        try:
            result = subprocess.run(
                ['adb', 'devices', '-l'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return devices
            
            lines = result.stdout.strip().split('\n')
            for line in lines[1:]:  # Skip "List of devices attached"
                if line.strip() and 'device' in line and 'offline' not in line:
                    parts = line.split()
                    if parts:
                        serial = parts[0]
                        # Try to extract model info
                        model = "Unknown"
                        for part in parts:
                            if part.startswith('model:'):
                                model = part.replace('model:', '')
                                break
                        devices.append((serial, model))
        except FileNotFoundError:
            print("Error: ADB not found. Please install Android Debug Bridge (adb).")
        except subprocess.TimeoutExpired:
            print("Error: ADB command timed out.")
        except Exception as e:
            print(f"Error getting connected devices: {e}")
        
        return devices
    
    def is_service_running(self) -> bool:
        """Check if service is running"""
        try:
            with open(self.service_pid_file, 'r') as f:
                pid = int(f.read().strip())
                os.kill(pid, 0)  # Check if process exists
                return True
        except (FileNotFoundError, OSError, ValueError):
            return False
    
    def start_service(self):
        """Start the lock service"""
        if self.is_service_running():
            print("Lock service is already running.")
            return
        
        try:
            subprocess.run(['systemctl', 'start', 'lock-service'], check=True)
            print("Lock service started successfully.")
        except subprocess.CalledProcessError:
            print("Error: Failed to start lock service. Check systemd logs.")
        except FileNotFoundError:
            print("Error: systemctl not found. Service may not be installed.")
    
    def stop_service(self):
        """Stop the lock service"""
        if not self.is_service_running():
            print("Lock service is not running.")
            return
        
        try:
            subprocess.run(['systemctl', 'stop', 'lock-service'], check=True)
            print("Lock service stopped successfully.")
        except subprocess.CalledProcessError:
            print("Error: Failed to stop lock service.")
        except FileNotFoundError:
            print("Error: systemctl not found.")
    
    def restart_service(self):
        """Restart the lock service"""
        self.stop_service()
        time.sleep(2)
        self.start_service()
    
    def status(self):
        """Show service status"""
        print("=== Lock Service Status ===")
        print(f"Service running: {'Yes' if self.is_service_running() else 'No'}")
        
        # Show configured Android device
        serial = self.get_android_serial()
        if serial:
            print(f"Configured Android serial: {serial}")
            
            # Check if device is connected
            devices = self.get_connected_devices()
            connected_serials = [d[0] for d in devices]
            if serial in connected_serials:
                print(f"Device status: CONNECTED")
            else:
                print(f"Device status: NOT CONNECTED")
        else:
            print("Configured Android serial: Not configured")
            print("Run 'lock-cli setup' to configure a device.")
        
        # Check system lock status
        try:
            result = subprocess.run(['iptables', '-L', 'INPUT', '-n'], 
                                  capture_output=True, text=True)
            if 'DROP' in result.stdout:
                print("System status: LOCKED")
            else:
                print("System status: UNLOCKED")
        except:
            print("System status: Unknown")
    
    def setup(self):
        """Initial setup - configure Android device"""
        print("=== Lock Service Setup ===")
        print()
        
        # Check if already configured
        current_serial = self.get_android_serial()
        if current_serial:
            print(f"Currently configured device: {current_serial}")
            response = input("Reconfigure with a different device? (y/N): ")
            if response.lower() != 'y':
                return
            print()
        
        # Get connected devices
        print("Scanning for connected Android devices...")
        devices = self.get_connected_devices()
        
        if not devices:
            print()
            print("No Android devices found.")
            print()
            print("Please ensure:")
            print("  1. Your Android device is connected via USB")
            print("  2. USB debugging is enabled on the device")
            print("  3. ADB is installed on this system")
            print()
            
            # Allow manual entry
            response = input("Enter device serial manually? (y/N): ")
            if response.lower() == 'y':
                serial = input("Enter Android device serial: ").strip()
                if serial:
                    self.save_android_serial(serial)
                    print()
                    print(f"Device configured: {serial}")
                    print("The system will lock when this device is disconnected.")
                else:
                    print("No serial entered. Setup cancelled.")
            return
        
        # Display connected devices
        print()
        print("Connected Android devices:")
        print("-" * 50)
        for i, (serial, model) in enumerate(devices, 1):
            print(f"  {i}. {serial} ({model})")
        print("-" * 50)
        print()
        
        # Let user select a device
        while True:
            if len(devices) == 1:
                response = input(f"Use device {devices[0][0]}? (Y/n): ")
                if response.lower() != 'n':
                    selected_serial = devices[0][0]
                    break
                else:
                    print("Setup cancelled.")
                    return
            else:
                try:
                    choice = input(f"Select device (1-{len(devices)}): ")
                    idx = int(choice) - 1
                    if 0 <= idx < len(devices):
                        selected_serial = devices[idx][0]
                        break
                    else:
                        print("Invalid selection.")
                except ValueError:
                    print("Please enter a number.")
        
        # Save the selected device
        self.save_android_serial(selected_serial)
        
        print()
        print("=" * 50)
        print("Setup completed successfully!")
        print("=" * 50)
        print()
        print(f"Configured device: {selected_serial}")
        print()
        print("The system will now:")
        print("  - UNLOCK when this Android device is connected")
        print("  - LOCK when this Android device is disconnected")
        print()
        print("To start the service, run: lock-cli start")
    
    def list_devices(self):
        """List all connected Android devices"""
        print("=== Connected Android Devices ===")
        
        devices = self.get_connected_devices()
        
        if not devices:
            print("No Android devices found.")
            print()
            print("Please ensure:")
            print("  1. Your Android device is connected via USB")
            print("  2. USB debugging is enabled on the device")
            print("  3. ADB is installed on this system")
            return
        
        print()
        configured_serial = self.get_android_serial()
        
        for serial, model in devices:
            marker = " [CONFIGURED]" if serial == configured_serial else ""
            print(f"  {serial} ({model}){marker}")
        
        print()
        print(f"Total: {len(devices)} device(s)")
    
    def emergency_unlock(self):
        """Emergency unlock - bypass device check"""
        print("=== Emergency Unlock ===")
        print()
        print("WARNING: This will unlock the system without the configured Android device.")
        print()
        
        response = input("Are you sure you want to proceed? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled.")
            return
        
        # Unlock system
        try:
            # Clear iptables rules
            subprocess.run(['iptables', '-F'], check=False)
            subprocess.run(['iptables', '-X'], check=False)
            
            # Restore network interfaces
            try:
                config = self.load_config()
                for interface in config['network']['blocked_interfaces']:
                    subprocess.run(['ip', 'link', 'set', interface, 'up'], check=False)
            except:
                pass
            
            # Restore SSH
            subprocess.run(['systemctl', 'enable', 'ssh'], check=False)
            subprocess.run(['systemctl', 'start', 'ssh'], check=False)
            
            print()
            print("System unlocked successfully!")
            print()
            print("NOTE: The system will lock again if the lock service is running")
            print("      and the configured device is not connected.")
            print()
            print("To permanently disable locking, run: lock-cli clear-config")
            
        except Exception as e:
            print(f"Error unlocking system: {e}")
    
    def clear_config(self):
        """Clear the configured Android device"""
        print("=== Clear Configuration ===")
        
        serial = self.get_android_serial()
        if not serial:
            print("No device is currently configured.")
            return
        
        print(f"Currently configured device: {serial}")
        response = input("Remove this configuration? (y/N): ")
        
        if response.lower() != 'y':
            print("Cancelled.")
            return
        
        try:
            serial_file = os.path.join(self.config_dir, 'android_serial')
            if os.path.exists(serial_file):
                os.remove(serial_file)
            print("Configuration cleared.")
            print("The system will no longer lock/unlock based on device connection.")
        except Exception as e:
            print(f"Error clearing configuration: {e}")
    
    def logs(self, lines: int = 50):
        """Show service logs"""
        try:
            config = self.load_config()
            log_file = config.get('service', {}).get('log_file', '/var/log/lock-service.log')
        except:
            log_file = "/var/log/lock-service.log"
        
        if not os.path.exists(log_file):
            print("No log file found.")
            return
        
        try:
            subprocess.run(['tail', '-n', str(lines), log_file])
        except FileNotFoundError:
            # Fallback to reading file directly
            with open(log_file, 'r') as f:
                all_lines = f.readlines()
                for line in all_lines[-lines:]:
                    print(line.rstrip())


def main():
    parser = argparse.ArgumentParser(description='Lock-Down Service CLI')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Setup command
    subparsers.add_parser('setup', help='Configure Android device for unlock')
    
    # Service management commands
    subparsers.add_parser('start', help='Start the lock service')
    subparsers.add_parser('stop', help='Stop the lock service')
    subparsers.add_parser('restart', help='Restart the lock service')
    subparsers.add_parser('status', help='Show service status')
    
    # Device commands
    subparsers.add_parser('list-devices', help='List connected Android devices')
    
    # Emergency commands
    subparsers.add_parser('emergency-unlock', help='Emergency unlock without device')
    subparsers.add_parser('clear-config', help='Remove configured device')
    
    # Utility commands
    logs_parser = subparsers.add_parser('logs', help='Show service logs')
    logs_parser.add_argument('-n', '--lines', type=int, default=50,
                           help='Number of log lines to show')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    cli = LockCLI()
    
    if args.command == 'setup':
        cli.setup()
    elif args.command == 'start':
        cli.start_service()
    elif args.command == 'stop':
        cli.stop_service()
    elif args.command == 'restart':
        cli.restart_service()
    elif args.command == 'status':
        cli.status()
    elif args.command == 'list-devices':
        cli.list_devices()
    elif args.command == 'emergency-unlock':
        cli.emergency_unlock()
    elif args.command == 'clear-config':
        cli.clear_config()
    elif args.command == 'logs':
        cli.logs(args.lines)


if __name__ == "__main__":
    main()
