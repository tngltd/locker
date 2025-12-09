#!/usr/bin/env python3
"""
Unit tests for LockService
"""

import unittest
import os
import json
import tempfile
import shutil
import signal
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timedelta
import hashlib
import hmac

# Add parent directory to path
import sys
import importlib.util

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# Import lock-service module (handle hyphen in filename)
spec = importlib.util.spec_from_file_location(
    "lock_service",
    os.path.join(parent_dir, "lock-service.py")
)
lock_service_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lock_service_module)
LockService = lock_service_module.LockService


class TestLockService(unittest.TestCase):
    """Test cases for LockService"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.test_dir, 'config.json')
        self.auth_file = os.path.join(self.test_dir, 'auth_data.json')
        self.device_id_file = os.path.join(self.test_dir, 'device_id')
        self.log_file = os.path.join(self.test_dir, 'test.log')
        
        # Create test config
        test_config = {
            "service": {
                "name": "lock-service",
                "version": "1.0.0",
                "log_level": "DEBUG",
                "log_file": self.log_file,
                "pid_file": os.path.join(self.test_dir, 'test.pid'),
                "config_file": self.config_path
            },
            "security": {
                "max_pin_attempts": 3,
                "lockout_duration_minutes": 15,
                "recovery_code_expiry_hours": 48,
                "challenge_timeout_seconds": 30,
                "device_id_length": 12,
                "pin_length": 4
            },
            "network": {
                "usb_interface": "usb0",
                "blocked_interfaces": ["eth0", "wlan0"],
                "allowed_ports": [],
                "blocked_ports": [22, 80, 443]
            },
            "authentication": {
                "enabled": True,
                "require_physical_presence": True,
                "admin_override_enabled": True,
                "emergency_recovery_enabled": True
            },
            "logging": {
                "verbose": True,
                "include_device_info": True,
                "external_logging": {
                    "enabled": False
                }
            },
            "monitoring": {
                "check_interval_seconds": 5
            }
        }
        
        with open(self.config_path, 'w') as f:
            json.dump(test_config, f)
        
        # Create default config directory structure
        default_config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config')
        os.makedirs(default_config_dir, exist_ok=True)
    
    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    @patch('subprocess.run')
    def test_detect_android_device_via_usb_found(self, mock_subprocess):
        """Test USB device detection when device is found"""
        # Mock lsusb output with Android device
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="Bus 001 Device 002: ID 18d1:4ee0 Google Inc. Nexus/Pixel Device\n"
        )
        
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        result = service.detect_android_device_via_usb()
        
        self.assertTrue(result)
        mock_subprocess.assert_called_once()
    
    @patch('subprocess.run')
    def test_detect_android_device_via_usb_not_found(self, mock_subprocess):
        """Test USB device detection when no Android device is found"""
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="Bus 001 Device 002: ID 046d:c52b Logitech, Inc.\n"
        )
        
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        result = service.detect_android_device_via_usb()
        
        self.assertFalse(result)
    
    @patch('subprocess.run')
    def test_detect_android_device_via_adb_found(self, mock_subprocess):
        """Test ADB device detection when device is found"""
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="List of devices attached\nemulator-5554    device\n"
        )
        
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        result = service.detect_android_device_via_adb()
        
        self.assertTrue(result)
    
    @patch('subprocess.run')
    def test_detect_android_device_via_adb_not_found(self, mock_subprocess):
        """Test ADB device detection when no device is found"""
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="List of devices attached\n"
        )
        
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        result = service.detect_android_device_via_adb()
        
        self.assertFalse(result)
    
    @patch('subprocess.run')
    def test_detect_android_device_fallback(self, mock_subprocess):
        """Test device detection with USB fallback to ADB"""
        # First call (USB) returns no device, second call (ADB) finds device
        mock_subprocess.side_effect = [
            Mock(returncode=0, stdout="Bus 001 Device 002: ID 046d:c52b Logitech\n"),
            Mock(returncode=0, stdout="List of devices attached\nemulator-5554    device\n")
        ]
        
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        result = service.detect_android_device()
        
        self.assertTrue(result)
        self.assertEqual(mock_subprocess.call_count, 2)
    
    def test_generate_challenge(self):
        """Test challenge generation"""
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        challenge = service.generate_challenge()
        
        self.assertTrue(challenge.startswith("CHL-"))
        self.assertIn(service.device_id, challenge)
        self.assertIn("-", challenge)
    
    def test_set_pin(self):
        """Test PIN setting"""
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        recovery_code = service.set_pin("1234")
        
        self.assertIsNotNone(service.pin_hash)
        self.assertIsNotNone(recovery_code)
        self.assertTrue(recovery_code.startswith("REC-"))
        self.assertEqual(service.failed_attempts, 0)
        self.assertIsNone(service.lockout_until)
    
    def test_verify_pin_response_success(self):
        """Test PIN verification with correct response"""
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        service.set_pin("1234")
        
        challenge = service.generate_challenge()
        expected_response = hmac.new(
            service.pin_hash.encode(),
            challenge.encode(),
            hashlib.sha256
        ).hexdigest()
        
        result = service.verify_pin_response(challenge, "1234", expected_response)
        self.assertTrue(result)
    
    def test_verify_pin_response_failure(self):
        """Test PIN verification with incorrect response"""
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        service.set_pin("1234")
        
        challenge = service.generate_challenge()
        wrong_response = "wrong_response"
        
        result = service.verify_pin_response(challenge, "1234", wrong_response)
        self.assertFalse(result)
    
    def test_verify_recovery_code_success(self):
        """Test recovery code verification with correct code"""
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        recovery_code = service.set_pin("1234")
        
        result = service.verify_recovery_code(recovery_code)
        self.assertTrue(result)
    
    def test_verify_recovery_code_failure(self):
        """Test recovery code verification with incorrect code"""
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        service.set_pin("1234")
        
        result = service.verify_recovery_code("WRONG-CODE")
        self.assertFalse(result)
    
    def test_verify_authentication_success(self):
        """Test successful authentication"""
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        service.set_pin("1234")
        
        challenge = service.generate_challenge()
        expected_response = hmac.new(
            service.pin_hash.encode(),
            challenge.encode(),
            hashlib.sha256
        ).hexdigest()
        
        result = service.verify_authentication(challenge, "1234", expected_response)
        self.assertTrue(result)
        self.assertEqual(service.failed_attempts, 0)
    
    def test_verify_authentication_failure(self):
        """Test failed authentication"""
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        service.set_pin("1234")
        
        challenge = service.generate_challenge()
        wrong_response = "wrong"
        
        result = service.verify_authentication(challenge, "1234", wrong_response)
        self.assertFalse(result)
        self.assertEqual(service.failed_attempts, 1)
    
    def test_verify_authentication_lockout(self):
        """Test authentication lockout after max attempts"""
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        service.set_pin("1234")
        service.config['security']['max_pin_attempts'] = 3
        
        challenge = service.generate_challenge()
        wrong_response = "wrong"
        
        # Fail 3 times
        for _ in range(3):
            service.verify_authentication(challenge, "1234", wrong_response)
        
        self.assertEqual(service.failed_attempts, 3)
        self.assertIsNotNone(service.lockout_until)
        self.assertGreater(service.lockout_until, datetime.now())
    
    @patch('subprocess.run')
    def test_lock_system(self, mock_subprocess):
        """Test system lockdown"""
        mock_subprocess.return_value = Mock(returncode=0)
        
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        service.security_policies = {
            'lock_policies': {
                'disable_ssh': True,
                'disable_network_interfaces': True,
                'block_all_ports': True
            }
        }
        
        service.lock_system()
        
        self.assertTrue(service.is_locked)
        self.assertGreater(mock_subprocess.call_count, 0)
    
    @patch('subprocess.run')
    def test_unlock_system(self, mock_subprocess):
        """Test system unlock"""
        mock_subprocess.return_value = Mock(returncode=0)
        
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        service.is_locked = True
        service.security_policies = {
            'unlock_policies': {
                'restore_network_interfaces': True,
                'restore_ssh': True,
                'restore_all_ports': True
            }
        }
        
        service.unlock_system()
        
        self.assertFalse(service.is_locked)
        self.assertEqual(service.failed_attempts, 0)
        self.assertIsNone(service.lockout_until)
    
    def test_get_or_create_device_id(self):
        """Test device ID creation and retrieval"""
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        device_id = service.get_or_create_device_id()
        
        self.assertIsNotNone(device_id)
        self.assertEqual(len(device_id), 12)
        
        # Should get same ID on second call
        device_id2 = service.get_or_create_device_id()
        self.assertEqual(device_id, device_id2)
    
    def test_load_auth_data(self):
        """Test loading authentication data"""
        # Create auth data file
        auth_data = {
            'pin_hash': 'test_hash',
            'recovery_code': 'REC-TEST-CODE',
            'failed_attempts': 2,
            'lockout_until': (datetime.now() + timedelta(minutes=15)).isoformat()
        }
        
        os.makedirs(os.path.dirname(self.auth_file), exist_ok=True)
        with open(self.auth_file, 'w') as f:
            json.dump(auth_data, f)
        
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        
        self.assertEqual(service.pin_hash, 'test_hash')
        self.assertEqual(service.recovery_code, 'REC-TEST-CODE')
        self.assertEqual(service.failed_attempts, 2)
        self.assertIsNotNone(service.lockout_until)
    
    def test_save_auth_data(self):
        """Test saving authentication data"""
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        service.set_pin("1234")
        
        # Verify file was created
        self.assertTrue(os.path.exists(self.auth_file))
        
        # Verify permissions (should be 600)
        file_stat = os.stat(self.auth_file)
        self.assertEqual(oct(file_stat.st_mode)[-3:], '600')
    
    def test_signal_handler(self):
        """Test signal handling"""
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        service.running = True
        
        service.signal_handler(signal.SIGTERM, None)
        
        self.assertFalse(service.running)
    
    @patch('subprocess.run')
    @patch('time.sleep')
    def test_run_with_device_detection(self, mock_sleep, mock_subprocess):
        """Test main run loop with device detection"""
        mock_subprocess.side_effect = [
            # USB detection - no device
            Mock(returncode=0, stdout="Bus 001 Device 002: ID 046d:c52b Logitech\n"),
            # ADB detection - no device
            Mock(returncode=0, stdout="List of devices attached\n"),
        ]
        mock_sleep.side_effect = [None, KeyboardInterrupt()]
        
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        service.running = True
        
        try:
            service.run()
        except KeyboardInterrupt:
            pass
        
        # Should have called sleep at least once
        self.assertGreater(mock_sleep.call_count, 0)


if __name__ == '__main__':
    unittest.main()

