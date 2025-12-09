#!/usr/bin/env python3
"""
Lock-Down Service CLI Tool
Command line interface for managing the lock-down service.
"""

import os
import sys
import json
import argparse
import getpass
import hashlib
import hmac
import subprocess
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional


class LockCLI:
    def __init__(self):
        self.config_path = "/etc/lock-service/config.json"
        self.auth_file = "/etc/lock-service/auth_data.json"
        self.device_id_file = "/etc/lock-service/device_id"
        self.service_pid_file = "/var/run/lock-service.pid"
    
    def load_config(self) -> dict:
        """Load configuration"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print("Error: Configuration file not found. Run 'lock-cli setup' first.")
            sys.exit(1)
    
    def get_device_id(self) -> str:
        """Get device ID"""
        try:
            with open(self.device_id_file, 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            return "UNKNOWN"
    
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
        print(f"Device ID: {self.get_device_id()}")
        
        # Check if PIN is set
        try:
            with open(self.auth_file, 'r') as f:
                auth_data = json.load(f)
                pin_set = bool(auth_data.get('pin_hash'))
                failed_attempts = auth_data.get('failed_attempts', 0)
                lockout_until = auth_data.get('lockout_until')
                
                print(f"PIN configured: {'Yes' if pin_set else 'No'}")
                print(f"Failed attempts: {failed_attempts}")
                if lockout_until:
                    print(f"Locked out until: {lockout_until}")
        except FileNotFoundError:
            print("PIN configured: No")
        
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
        """Initial setup of the lock service"""
        print("=== Lock Service Setup ===")
        
        # Check if already configured
        if os.path.exists(self.auth_file):
            response = input("Service already configured. Reconfigure? (y/N): ")
            if response.lower() != 'y':
                return
        
        # Get PIN from user
        while True:
            pin = getpass.getpass("Enter 4-6 digit PIN for Android authentication: ")
            if len(pin) < 4 or len(pin) > 6 or not pin.isdigit():
                print("Error: PIN must be 4-6 digits.")
                continue
            
            pin_confirm = getpass.getpass("Confirm PIN: ")
            if pin != pin_confirm:
                print("Error: PINs do not match.")
                continue
            
            break
        
        # Generate device ID if not exists
        device_id = self.get_device_id()
        if device_id == "UNKNOWN":
            import uuid
            device_id = str(uuid.uuid4()).replace('-', '')[:12].upper()
            os.makedirs(os.path.dirname(self.device_id_file), exist_ok=True)
            with open(self.device_id_file, 'w') as f:
                f.write(device_id)
        
        # Generate PIN hash and recovery code
        salt = str(uuid.uuid4())
        pin_hash = hashlib.sha256(f"{pin}{device_id}{salt}".encode()).hexdigest()
        
        import uuid
        recovery_code = f"REC-{str(uuid.uuid4())[:8].upper()}-{str(uuid.uuid4())[:8].upper()}"
        
        # Save authentication data
        auth_data = {
            'pin_hash': pin_hash,
            'recovery_code': recovery_code,
            'failed_attempts': 0,
            'lockout_until': None
        }
        
        os.makedirs(os.path.dirname(self.auth_file), exist_ok=True)
        with open(self.auth_file, 'w') as f:
            json.dump(auth_data, f, indent=2)
        os.chmod(self.auth_file, 0o600)
        
        print(f"\nSetup completed successfully!")
        print(f"Device ID: {device_id}")
        print(f"Recovery code: {recovery_code}")
        print(f"Recovery code expires in 48 hours.")
        print(f"\nIMPORTANT: Save the recovery code in a secure location!")
        print(f"You will need it if you lose your Android device.")
    
    def emergency_unlock(self):
        """Emergency unlock using recovery code"""
        print("=== Emergency Unlock ===")
        
        if not os.path.exists(self.auth_file):
            print("Error: No authentication data found. Run 'lock-cli setup' first.")
            return
        
        # Load auth data
        with open(self.auth_file, 'r') as f:
            auth_data = json.load(f)
        
        recovery_code = auth_data.get('recovery_code')
        if not recovery_code:
            print("Error: No recovery code found.")
            return
        
        # Get recovery code from user
        entered_code = input("Enter recovery code: ").strip()
        
        if entered_code != recovery_code:
            print("Error: Invalid recovery code.")
            return
        
        # Unlock system
        try:
            # Clear iptables rules
            subprocess.run(['iptables', '-F'], check=False)
            subprocess.run(['iptables', '-X'], check=False)
            
            # Restore network interfaces
            config = self.load_config()
            for interface in config['network']['blocked_interfaces']:
                subprocess.run(['ip', 'link', 'set', interface, 'up'], check=False)
            
            # Restore SSH
            subprocess.run(['systemctl', 'enable', 'ssh'], check=False)
            subprocess.run(['systemctl', 'start', 'ssh'], check=False)
            
            # Reset failed attempts
            auth_data['failed_attempts'] = 0
            auth_data['lockout_until'] = None
            
            # Generate new recovery code
            import uuid
            new_recovery_code = f"REC-{str(uuid.uuid4())[:8].upper()}-{str(uuid.uuid4())[:8].upper()}"
            auth_data['recovery_code'] = new_recovery_code
            
            with open(self.auth_file, 'w') as f:
                json.dump(auth_data, f, indent=2)
            
            print("System unlocked successfully!")
            print(f"New recovery code: {new_recovery_code}")
            print("Recovery code expires in 48 hours.")
            
        except Exception as e:
            print(f"Error unlocking system: {e}")
    
    def change_pin(self):
        """Change the PIN"""
        print("=== Change PIN ===")
        
        if not os.path.exists(self.auth_file):
            print("Error: No authentication data found. Run 'lock-cli setup' first.")
            return
        
        # Get current PIN
        current_pin = getpass.getpass("Enter current PIN: ")
        
        # Verify current PIN (simplified - in real implementation would use challenge/response)
        with open(self.auth_file, 'r') as f:
            auth_data = json.load(f)
        
        # Get new PIN
        while True:
            new_pin = getpass.getpass("Enter new 4-6 digit PIN: ")
            if len(new_pin) < 4 or len(new_pin) > 6 or not new_pin.isdigit():
                print("Error: PIN must be 4-6 digits.")
                continue
            
            new_pin_confirm = getpass.getpass("Confirm new PIN: ")
            if new_pin != new_pin_confirm:
                print("Error: PINs do not match.")
                continue
            
            break
        
        # Update PIN hash
        device_id = self.get_device_id()
        import uuid
        salt = str(uuid.uuid4())
        new_pin_hash = hashlib.sha256(f"{new_pin}{device_id}{salt}".encode()).hexdigest()
        
        auth_data['pin_hash'] = new_pin_hash
        auth_data['failed_attempts'] = 0
        auth_data['lockout_until'] = None
        
        with open(self.auth_file, 'w') as f:
            json.dump(auth_data, f, indent=2)
        
        print("PIN changed successfully!")
    
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
    
    def test_auth(self):
        """Test authentication (for development)"""
        print("=== Test Authentication ===")
        
        if not os.path.exists(self.auth_file):
            print("Error: No authentication data found. Run 'lock-cli setup' first.")
            return
        
        pin = getpass.getpass("Enter PIN to test: ")
        
        # Load auth data
        with open(self.auth_file, 'r') as f:
            auth_data = json.load(f)
        
        device_id = self.get_device_id()
        
        # Generate test challenge
        import uuid
        challenge = f"CHL-{datetime.now().isoformat()}-{str(uuid.uuid4())[:8]}-{device_id}"
        
        # Calculate expected response
        pin_hash = auth_data.get('pin_hash')
        if not pin_hash:
            print("Error: No PIN hash found.")
            return
        
        expected_response = hmac.new(
            pin_hash.encode(),
            challenge.encode(),
            hashlib.sha256
        ).hexdigest()
        
        print(f"Challenge: {challenge}")
        print(f"Expected response: {expected_response}")
        print("Use this data to test Android app authentication.")


def main():
    parser = argparse.ArgumentParser(description='Lock-Down Service CLI')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Setup command
    subparsers.add_parser('setup', help='Initial setup of the lock service')
    
    # Service management commands
    subparsers.add_parser('start', help='Start the lock service')
    subparsers.add_parser('stop', help='Stop the lock service')
    subparsers.add_parser('restart', help='Restart the lock service')
    subparsers.add_parser('status', help='Show service status')
    
    # Authentication commands
    subparsers.add_parser('emergency-unlock', help='Emergency unlock using recovery code')
    subparsers.add_parser('change-pin', help='Change the PIN')
    
    # Utility commands
    logs_parser = subparsers.add_parser('logs', help='Show service logs')
    logs_parser.add_argument('-n', '--lines', type=int, default=50,
                           help='Number of log lines to show')
    
    subparsers.add_parser('test-auth', help='Test authentication (development)')
    
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
    elif args.command == 'emergency-unlock':
        cli.emergency_unlock()
    elif args.command == 'change-pin':
        cli.change_pin()
    elif args.command == 'logs':
        cli.logs(args.lines)
    elif args.command == 'test-auth':
        cli.test_auth()


if __name__ == "__main__":
    main()
