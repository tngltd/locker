#!/usr/bin/env python3
"""
Unit tests for System Lockdown (KAN-11)
"""

import unittest
import os
import json
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime
import sys
import importlib.util

# Import lock-service module
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "lock_service",
    os.path.join(parent_dir, "lock-service.py")
)
lock_service_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lock_service_module)
LockService = lock_service_module.LockService


class TestSystemLockdown(unittest.TestCase):
    """Test cases for System Lockdown"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.test_dir, 'etc', 'lock-service')
        self.log_dir = os.path.join(self.test_dir, 'var', 'log')
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)

        self.config_path = os.path.join(self.config_dir, 'config.json')
        self.log_file = os.path.join(self.log_dir, 'lock-service.log')

        self.default_config = {
            "service": {
                "name": "lock-service",
                "version": "1.0.0",
                "log_level": "INFO",
                "log_file": self.log_file,
                "pid_file": "/var/run/lock-service.pid",
                "config_file": self.config_path
            },
            "network": {
                "usb_interface": "usb0",
                "blocked_interfaces": ["eth0", "wlan0"],
                "allowed_ports": [],
                "blocked_ports": [22]
            },
            "monitoring": {
                "check_interval_seconds": 1
            },
            "logging": {
                "verbose": True,
                "include_device_info": True,
                "external_logging": {"enabled": False}
            }
        }
        
        # Create security policies
        self.security_policies = {
            "lock_policies": {
                "disable_ssh": True,
                "disable_network_interfaces": True,
                "block_all_ports": True
            },
            "unlock_policies": {
                "restore_network_interfaces": True,
                "restore_ssh": True,
                "restore_all_ports": True
            }
        }
        
        with open(self.config_path, 'w') as f:
            json.dump(self.default_config, f)
        
        # Create security policies file
        policies_path = os.path.join(self.config_dir, 'security_policies.json')
        with open(policies_path, 'w') as f:
            json.dump(self.security_policies, f)

        import logging
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        shutil.rmtree(self.test_dir)
        import logging
        logging.disable(logging.NOTSET)

    @patch('subprocess.run')
    def test_lock_system_disables_ssh(self, mock_subprocess):
        """Test that lock_system disables SSH"""
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.is_locked = False
        
        service.lock_system()
        
        # Verify systemctl stop and disable were called
        systemctl_calls = [c for c in mock_subprocess.call_args_list if len(c[0]) > 0 and 'systemctl' in str(c[0][0])]
        stop_found = False
        disable_found = False
        for call_args in systemctl_calls:
            args = call_args[0][0] if isinstance(call_args[0], (list, tuple)) else call_args[0]
            if isinstance(args, list):
                if 'stop' in args and 'ssh' in args:
                    stop_found = True
                if 'disable' in args and 'ssh' in args:
                    disable_found = True
        self.assertTrue(stop_found, "systemctl stop ssh not called")
        self.assertTrue(disable_found, "systemctl disable ssh not called")
        self.assertTrue(service.is_locked)

    @patch('subprocess.run')
    def test_lock_system_disables_network_interfaces(self, mock_subprocess):
        """Test that lock_system disables network interfaces"""
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.is_locked = False
        
        service.lock_system()
        
        # Verify ip link set down was called for each interface
        ip_calls = [c for c in mock_subprocess.call_args_list if len(c[0]) > 0 and 'ip' in str(c[0][0])]
        for interface in self.default_config['network']['blocked_interfaces']:
            found = False
            for call_args in ip_calls:
                args = call_args[0][0] if isinstance(call_args[0], (list, tuple)) else call_args[0]
                if isinstance(args, list) and len(args) >= 4:
                    if args[0] == 'ip' and args[1] == 'link' and args[2] == 'set' and args[3] == interface and 'down' in args:
                        found = True
                        break
            self.assertTrue(found, f"ip link set {interface} down not called")

    @patch('subprocess.run')
    def test_lock_system_blocks_ports(self, mock_subprocess):
        """Test that lock_system blocks ports with iptables"""
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.is_locked = False
        
        service.lock_system()
        
        # Verify iptables DROP rules were added
        iptables_calls = [c for c in mock_subprocess.call_args_list if len(c[0]) > 0 and 'iptables' in str(c[0][0])]
        drop_found = False
        for call_args in iptables_calls:
            args = call_args[0][0] if isinstance(call_args[0], (list, tuple)) else call_args[0]
            if isinstance(args, list) and '-j' in args and 'DROP' in args:
                drop_found = True
                break
        self.assertTrue(drop_found, "iptables DROP rule not added")

    @patch('subprocess.run')
    def test_lock_system_idempotent(self, mock_subprocess):
        """Test that lock_system is idempotent"""
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.is_locked = True
        
        initial_call_count = len(mock_subprocess.call_args_list)
        service.lock_system()
        
        # Should not make additional calls if already locked
        self.assertEqual(len(mock_subprocess.call_args_list), initial_call_count)

    @patch('subprocess.run')
    def test_unlock_system_restores_network_interfaces(self, mock_subprocess):
        """Test that unlock_system restores network interfaces"""
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.is_locked = True
        
        service.unlock_system()
        
        # Verify ip link set up was called for each interface
        # Check the actual call arguments
        ip_calls = [c for c in mock_subprocess.call_args_list if len(c[0]) > 0 and 'ip' in c[0][0]]
        for interface in self.default_config['network']['blocked_interfaces']:
            found = False
            for call_args in ip_calls:
                args = call_args[0][0] if isinstance(call_args[0], (list, tuple)) else call_args[0]
                if isinstance(args, list) and len(args) >= 4:
                    if args[0] == 'ip' and args[1] == 'link' and args[2] == 'set' and args[3] == interface and 'up' in args:
                        found = True
                        break
            self.assertTrue(found, f"ip link set {interface} up not called")
        self.assertFalse(service.is_locked)

    @patch('subprocess.run')
    def test_unlock_system_restores_ssh(self, mock_subprocess):
        """Test that unlock_system restores SSH"""
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.is_locked = True
        
        service.unlock_system()
        
        # Verify systemctl enable and start were called
        calls = [str(call) for call in mock_subprocess.call_args_list]
        self.assertTrue(any('systemctl' in str(c) and 'enable' in str(c) and 'ssh' in str(c) for c in calls))
        self.assertTrue(any('systemctl' in str(c) and 'start' in str(c) and 'ssh' in str(c) for c in calls))

    @patch('subprocess.run')
    def test_unlock_system_clears_iptables(self, mock_subprocess):
        """Test that unlock_system clears iptables rules"""
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.is_locked = True
        
        service.unlock_system()
        
        # Verify iptables -F and -X were called
        iptables_calls = [c for c in mock_subprocess.call_args_list if len(c[0]) > 0 and 'iptables' in str(c[0][0])]
        flush_found = False
        delete_found = False
        for call_args in iptables_calls:
            args = call_args[0][0] if isinstance(call_args[0], (list, tuple)) else call_args[0]
            if isinstance(args, list):
                if '-F' in args:
                    flush_found = True
                if '-X' in args:
                    delete_found = True
        self.assertTrue(flush_found, "iptables -F not called")
        self.assertTrue(delete_found, "iptables -X not called")

    @patch('subprocess.run')
    def test_unlock_system_idempotent(self, mock_subprocess):
        """Test that unlock_system is idempotent"""
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.is_locked = False
        
        initial_call_count = len(mock_subprocess.call_args_list)
        service.unlock_system()
        
        # Should not make additional calls if already unlocked
        self.assertEqual(len(mock_subprocess.call_args_list), initial_call_count)

    @patch('subprocess.run')
    def test_lock_unlock_cycle(self, mock_subprocess):
        """Test a complete lock/unlock cycle"""
        service = LockService(self.config_path, config_dir=self.config_dir)
        
        # Lock
        service.lock_system()
        self.assertTrue(service.is_locked)
        
        # Unlock
        service.unlock_system()
        self.assertFalse(service.is_locked)
        
        # Verify both operations made system calls
        self.assertGreater(len(mock_subprocess.call_args_list), 0)


if __name__ == '__main__':
    unittest.main()

