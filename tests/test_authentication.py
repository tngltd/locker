#!/usr/bin/env python3
"""
Unit tests for Authentication System (KAN-10)
"""

import unittest
import os
import json
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import hashlib
import hmac
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


class TestAuthenticationSystem(unittest.TestCase):
    """Test cases for Authentication System"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.test_dir, 'etc', 'lock-service')
        self.log_dir = os.path.join(self.test_dir, 'var', 'log')
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)

        self.config_path = os.path.join(self.config_dir, 'config.json')
        self.device_id_file = os.path.join(self.config_dir, 'device_id')
        self.auth_file = os.path.join(self.config_dir, 'auth_data.json')
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
                "blocked_ports": [22]
            },
            "authentication": {
                "enabled": True,
                "require_physical_presence": True,
                "admin_override_enabled": True,
                "emergency_recovery_enabled": True
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
        with open(self.config_path, 'w') as f:
            json.dump(self.default_config, f)

        import logging
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        shutil.rmtree(self.test_dir)
        import logging
        logging.disable(logging.NOTSET)

    def test_generate_challenge(self):
        """Test challenge generation"""
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        challenge = service.generate_challenge()
        
        self.assertTrue(challenge.startswith('CHL-'))
        self.assertIn(service.device_id, challenge)
        self.assertGreater(len(challenge), 20)

    def test_set_pin_generates_recovery_code(self):
        """Test that setting PIN generates recovery code"""
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        recovery_code = service.set_pin("1234")
        
        self.assertTrue(recovery_code.startswith('REC-'))
        self.assertIsNotNone(service.pin_hash)
        self.assertEqual(service.recovery_code, recovery_code)
        self.assertEqual(service.failed_attempts, 0)
        self.assertIsNone(service.lockout_until)

    def test_verify_pin_response_correct(self):
        """Test PIN response verification with correct PIN"""
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        service.set_pin("1234")
        
        challenge = service.generate_challenge()
        pin_hash = service.pin_hash
        
        # Calculate correct response
        expected_response = hmac.new(
            pin_hash.encode(),
            challenge.encode(),
            hashlib.sha256
        ).hexdigest()
        
        result = service.verify_pin_response(challenge, "1234", expected_response)
        self.assertTrue(result)

    def test_verify_pin_response_incorrect(self):
        """Test PIN response verification with incorrect PIN"""
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        service.set_pin("1234")
        
        challenge = service.generate_challenge()
        wrong_response = "wrong_response_hash"
        
        result = service.verify_pin_response(challenge, "1234", wrong_response)
        self.assertFalse(result)

    def test_verify_recovery_code_correct(self):
        """Test recovery code verification with correct code"""
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        recovery_code = service.set_pin("1234")
        
        result = service.verify_recovery_code(recovery_code)
        self.assertTrue(result)

    def test_verify_recovery_code_incorrect(self):
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
        pin_hash = service.pin_hash
        response = hmac.new(
            pin_hash.encode(),
            challenge.encode(),
            hashlib.sha256
        ).hexdigest()
        
        result = service.verify_authentication(challenge, "1234", response)
        self.assertTrue(result)
        self.assertEqual(service.failed_attempts, 0)
        self.assertIsNone(service.lockout_until)

    def test_verify_authentication_failure(self):
        """Test failed authentication"""
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        service.set_pin("1234")
        
        challenge = service.generate_challenge()
        wrong_response = "wrong_response"
        
        result = service.verify_authentication(challenge, "1234", wrong_response)
        self.assertFalse(result)
        self.assertEqual(service.failed_attempts, 1)

    def test_authentication_lockout_after_max_attempts(self):
        """Test that system locks out after max failed attempts"""
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        service.set_pin("1234")
        
        challenge = service.generate_challenge()
        wrong_response = "wrong_response"
        
        # Make max attempts
        for i in range(3):
            service.verify_authentication(challenge, "1234", wrong_response)
        
        self.assertEqual(service.failed_attempts, 3)
        self.assertIsNotNone(service.lockout_until)
        self.assertGreater(service.lockout_until, datetime.now())

    def test_authentication_during_lockout(self):
        """Test that authentication fails during lockout period"""
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        service.set_pin("1234")
        service.failed_attempts = 3
        service.lockout_until = datetime.now() + timedelta(minutes=15)
        
        challenge = service.generate_challenge()
        pin_hash = service.pin_hash
        response = hmac.new(
            pin_hash.encode(),
            challenge.encode(),
            hashlib.sha256
        ).hexdigest()
        
        result = service.verify_authentication(challenge, "1234", response)
        self.assertFalse(result)

    def test_authentication_resets_after_lockout(self):
        """Test that authentication works after lockout expires"""
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        service.set_pin("1234")
        service.failed_attempts = 3
        service.lockout_until = datetime.now() - timedelta(minutes=1)  # Expired
        
        challenge = service.generate_challenge()
        pin_hash = service.pin_hash
        response = hmac.new(
            pin_hash.encode(),
            challenge.encode(),
            hashlib.sha256
        ).hexdigest()
        
        result = service.verify_authentication(challenge, "1234", response)
        self.assertTrue(result)
        self.assertEqual(service.failed_attempts, 0)
        self.assertIsNone(service.lockout_until)

    def test_save_and_load_auth_data(self):
        """Test saving and loading authentication data"""
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        recovery_code = service.set_pin("1234")
        service.failed_attempts = 2
        service.save_auth_data()  # Explicitly save
        
        # Create new service instance to test loading
        service2 = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        
        self.assertEqual(service2.pin_hash, service.pin_hash)
        self.assertEqual(service2.recovery_code, recovery_code)
        self.assertEqual(service2.failed_attempts, 2)

    def test_handle_android_connection_no_pin(self):
        """Test handling Android connection when no PIN is set"""
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        
        result = service.handle_android_connection({})
        self.assertEqual(result['status'], 'no_pin_set')

    def test_handle_android_connection_locked_out(self):
        """Test handling Android connection during lockout"""
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        service.set_pin("1234")
        service.is_locked = True
        service.lockout_until = datetime.now() + timedelta(minutes=15)
        
        result = service.handle_android_connection({})
        self.assertEqual(result['status'], 'locked_out')

    def test_handle_android_connection_sends_challenge(self):
        """Test that Android connection receives challenge"""
        service = LockService(self.config_path, device_id_file=self.device_id_file, auth_file=self.auth_file)
        service.set_pin("1234")
        
        result = service.handle_android_connection({})
        self.assertEqual(result['status'], 'challenge_sent')
        self.assertIn('challenge', result)
        self.assertIn('device_id', result)
        self.assertEqual(result['device_id'], service.device_id)


if __name__ == '__main__':
    unittest.main()

