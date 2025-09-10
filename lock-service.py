#!/usr/bin/env python3
"""
Lock-Down Service - Main daemon
A security service for Ubuntu systems to lock down devices when lost/stolen.
"""

import os
import sys
import json
import time
import signal
import logging
import hashlib
import hmac
import subprocess
import threading
import socket
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List
import argparse


class LockService:
    def __init__(self, config_path: str = "/etc/lock-service/config.json"):
        self.config_path = config_path
        self.config = self.load_config()
        self.security_policies = self.load_security_policies()
        self.is_locked = False
        self.device_id = self.get_or_create_device_id()
        self.pin_hash = None
        self.recovery_code = None
        self.failed_attempts = 0
        self.lockout_until = None
        self.running = True
        
        # Setup logging
        self.setup_logging()
        
        # Load existing authentication data
        self.load_auth_data()
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        self.logger.info(f"Lock Service initialized. Device ID: {self.device_id}")
        self.logger.info(f"System OS: {self.get_system_info()}")
    
    def load_config(self) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # Use default config if file doesn't exist
            default_config_path = Path(__file__).parent / "config" / "init_config.json"
            with open(default_config_path, 'r') as f:
                return json.load(f)
    
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
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Setup file handler
        file_handler = logging.FileHandler(self.config['service']['log_file'])
        file_handler.setFormatter(formatter)
        
        # Setup console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # Setup logger
        self.logger = logging.getLogger('lock-service')
        self.logger.setLevel(log_level)
        self.logger.addHandler(file_handler)
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
    
    def get_or_create_device_id(self) -> str:
        """Get or create unique device ID"""
        device_id_file = "/etc/lock-service/device_id"
        try:
            if os.path.exists(device_id_file):
                with open(device_id_file, 'r') as f:
                    return f.read().strip()
            else:
                # Create new device ID
                device_id = str(uuid.uuid4()).replace('-', '')[:12].upper()
                os.makedirs(os.path.dirname(device_id_file), exist_ok=True)
                with open(device_id_file, 'w') as f:
                    f.write(device_id)
                return device_id
        except Exception as e:
            self.logger.error(f"Error managing device ID: {e}")
            return "DEFAULT123"
    
    def load_auth_data(self):
        """Load authentication data from secure storage"""
        auth_file = "/etc/lock-service/auth_data.json"
        try:
            if os.path.exists(auth_file):
                with open(auth_file, 'r') as f:
                    auth_data = json.load(f)
                    self.pin_hash = auth_data.get('pin_hash')
                    self.recovery_code = auth_data.get('recovery_code')
                    self.failed_attempts = auth_data.get('failed_attempts', 0)
                    if auth_data.get('lockout_until'):
                        self.lockout_until = datetime.fromisoformat(auth_data['lockout_until'])
        except Exception as e:
            self.logger.error(f"Error loading auth data: {e}")
    
    def save_auth_data(self):
        """Save authentication data to secure storage"""
        auth_file = "/etc/lock-service/auth_data.json"
        try:
            os.makedirs(os.path.dirname(auth_file), exist_ok=True)
            auth_data = {
                'pin_hash': self.pin_hash,
                'recovery_code': self.recovery_code,
                'failed_attempts': self.failed_attempts,
                'lockout_until': self.lockout_until.isoformat() if self.lockout_until else None
            }
            with open(auth_file, 'w') as f:
                json.dump(auth_data, f)
            # Set secure permissions
            os.chmod(auth_file, 0o600)
        except Exception as e:
            self.logger.error(f"Error saving auth data: {e}")
    
    def generate_challenge(self) -> str:
        """Generate authentication challenge"""
        timestamp = datetime.now().isoformat()
        random_part = str(uuid.uuid4())[:8]
        return f"CHL-{timestamp}-{random_part}-{self.device_id}"
    
    def verify_pin_response(self, challenge: str, pin: str, response: str) -> bool:
        """Verify PIN authentication response"""
        if not self.pin_hash:
            return False
        
        # Calculate expected response
        expected_response = hmac.new(
            self.pin_hash.encode(),
            challenge.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(response, expected_response)
    
    def set_pin(self, pin: str) -> str:
        """Set new PIN and generate recovery code"""
        # Generate salt and hash PIN
        salt = str(uuid.uuid4())
        pin_hash = hashlib.sha256(f"{pin}{self.device_id}{salt}".encode()).hexdigest()
        
        self.pin_hash = pin_hash
        self.failed_attempts = 0
        self.lockout_until = None
        
        # Generate recovery code
        recovery_code = f"REC-{str(uuid.uuid4())[:8].upper()}-{str(uuid.uuid4())[:8].upper()}"
        self.recovery_code = recovery_code
        
        self.save_auth_data()
        
        self.logger.info(f"PIN set successfully. Recovery code: {recovery_code}")
        return recovery_code
    
    def verify_recovery_code(self, code: str) -> bool:
        """Verify recovery code"""
        if not self.recovery_code:
            return False
        
        if code != self.recovery_code:
            return False
        
        # Check if recovery code is expired
        # For simplicity, we'll regenerate recovery code after each use
        return True
    
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
            self.failed_attempts = 0
            self.lockout_until = None
            self.save_auth_data()
            
            self.logger.info("System unlocked successfully")
            
        except Exception as e:
            self.logger.error(f"Error unlocking system: {e}")
    
    def handle_android_connection(self, connection_data: Dict) -> Dict:
        """Handle authentication request from Android device"""
        if self.is_locked and self.lockout_until and datetime.now() < self.lockout_until:
            return {"status": "locked_out", "message": "Too many failed attempts"}
        
        if not self.pin_hash:
            return {"status": "no_pin_set", "message": "No PIN configured"}
        
        # Generate challenge
        challenge = self.generate_challenge()
        
        # For demo purposes, we'll simulate the response verification
        # In real implementation, this would be handled via USB communication
        
        return {
            "status": "challenge_sent",
            "challenge": challenge,
            "device_id": self.device_id
        }
    
    def verify_authentication(self, challenge: str, pin: str, response: str) -> bool:
        """Verify authentication attempt"""
        if self.is_locked and self.lockout_until and datetime.now() < self.lockout_until:
            self.logger.warning("Authentication attempt during lockout period")
            return False
        
        if not self.verify_pin_response(challenge, pin, response):
            self.failed_attempts += 1
            self.logger.warning(f"Failed authentication attempt #{self.failed_attempts}")
            
            if self.failed_attempts >= self.config['security']['max_pin_attempts']:
                self.lockout_until = datetime.now() + timedelta(
                    minutes=self.config['security']['lockout_duration_minutes']
                )
                self.logger.warning(f"System locked out until {self.lockout_until}")
            
            self.save_auth_data()
            return False
        
        # Successful authentication
        self.failed_attempts = 0
        self.lockout_until = None
        self.save_auth_data()
        self.logger.info("Successful authentication")
        return True
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def run(self):
        """Main service loop"""
        self.logger.info("Lock Service started")
        
        # Check if system should be locked on startup
        if self.pin_hash and not self.is_locked:
            self.lock_system()
        
        while self.running:
            try:
                # Monitor for USB connections and handle authentication
                # In a real implementation, this would involve USB communication
                time.sleep(1)
                
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
