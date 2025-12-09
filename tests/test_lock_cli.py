#!/usr/bin/env python3
"""
Unit tests for LockCLI
"""

import unittest
import os
import json
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock, mock_open
import sys
import importlib.util

# Import lock-cli module
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "lock_cli",
    os.path.join(parent_dir, "lock-cli.py")
)
lock_cli_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lock_cli_module)
LockCLI = lock_cli_module.LockCLI


class TestLockCLI(unittest.TestCase):
    """Test cases for LockCLI"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.test_dir, 'config.json')
        self.auth_file = os.path.join(self.test_dir, 'auth_data.json')
        self.device_id_file = os.path.join(self.test_dir, 'device_id')
        self.pid_file = os.path.join(self.test_dir, 'lock-service.pid')
        self.log_file = os.path.join(self.test_dir, 'lock-service.log')
        
        # Create test config
        test_config = {
            "service": {
                "name": "lock-service",
                "log_file": self.log_file
            },
            "network": {
                "blocked_interfaces": ["eth0", "wlan0"]
            }
        }
        
        with open(self.config_path, 'w') as f:
            json.dump(test_config, f)
        
        # Create CLI instance with test paths
        self.cli = LockCLI()
        self.cli.config_path = self.config_path
        self.cli.auth_file = self.auth_file
        self.cli.device_id_file = self.device_id_file
        self.cli.service_pid_file = self.pid_file
    
    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_get_device_id_existing(self):
        """Test getting existing device ID"""
        os.makedirs(os.path.dirname(self.device_id_file), exist_ok=True)
        with open(self.device_id_file, 'w') as f:
            f.write("TEST123456")
        
        device_id = self.cli.get_device_id()
        self.assertEqual(device_id, "TEST123456")
    
    def test_get_device_id_not_found(self):
        """Test getting device ID when file doesn't exist"""
        device_id = self.cli.get_device_id()
        self.assertEqual(device_id, "UNKNOWN")
    
    def test_is_service_running_true(self):
        """Test service running check when PID file exists and process is running"""
        os.makedirs(os.path.dirname(self.pid_file), exist_ok=True)
        with open(self.pid_file, 'w') as f:
            f.write(str(os.getpid()))  # Use current process PID
        
        result = self.cli.is_service_running()
        self.assertTrue(result)
    
    def test_is_service_running_false(self):
        """Test service running check when not running"""
        result = self.cli.is_service_running()
        self.assertFalse(result)
    
    @patch('subprocess.run')
    def test_start_service_already_running(self, mock_subprocess):
        """Test starting service when already running"""
        with patch.object(self.cli, 'is_service_running', return_value=True):
            self.cli.start_service()
            mock_subprocess.assert_not_called()
    
    @patch('subprocess.run')
    def test_start_service_success(self, mock_subprocess):
        """Test starting service successfully"""
        mock_subprocess.return_value = Mock(returncode=0)
        with patch.object(self.cli, 'is_service_running', return_value=False):
            self.cli.start_service()
            mock_subprocess.assert_called_once()
    
    @patch('subprocess.run')
    def test_stop_service_not_running(self, mock_subprocess):
        """Test stopping service when not running"""
        with patch.object(self.cli, 'is_service_running', return_value=False):
            self.cli.stop_service()
            mock_subprocess.assert_not_called()
    
    @patch('subprocess.run')
    def test_stop_service_success(self, mock_subprocess):
        """Test stopping service successfully"""
        mock_subprocess.return_value = Mock(returncode=0)
        with patch.object(self.cli, 'is_service_running', return_value=True):
            self.cli.stop_service()
            mock_subprocess.assert_called_once()
    
    def test_status_no_auth_file(self):
        """Test status when auth file doesn't exist"""
        with patch.object(self.cli, 'is_service_running', return_value=False):
            with patch.object(self.cli, 'get_device_id', return_value="TEST123"):
                output = []
                original_print = print
                def mock_print(*args, **kwargs):
                    output.append(' '.join(str(a) for a in args))
                
                with patch('builtins.print', side_effect=mock_print):
                    self.cli.status()
                
                status_text = ' '.join(output)
                self.assertIn("Service running: No", status_text)
                self.assertIn("PIN configured: No", status_text)
    
    def test_status_with_auth_file(self):
        """Test status when auth file exists"""
        os.makedirs(os.path.dirname(self.auth_file), exist_ok=True)
        auth_data = {
            'pin_hash': 'test_hash',
            'failed_attempts': 2,
            'lockout_until': None
        }
        with open(self.auth_file, 'w') as f:
            json.dump(auth_data, f)
        
        with patch.object(self.cli, 'is_service_running', return_value=True):
            with patch.object(self.cli, 'get_device_id', return_value="TEST123"):
                output = []
                def mock_print(*args, **kwargs):
                    output.append(' '.join(str(a) for a in args))
                
                with patch('builtins.print', side_effect=mock_print):
                    with patch('subprocess.run') as mock_subprocess:
                        mock_subprocess.return_value = Mock(
                            returncode=0,
                            stdout="Chain INPUT (policy ACCEPT)"
                        )
                        self.cli.status()
                
                status_text = ' '.join(output)
                self.assertIn("Service running: Yes", status_text)
                self.assertIn("PIN configured: Yes", status_text)
                self.assertIn("Failed attempts: 2", status_text)
    
    @patch('getpass.getpass')
    @patch('builtins.input')
    def test_setup_new_config(self, mock_input, mock_getpass):
        """Test setup with new configuration"""
        mock_getpass.side_effect = ["1234", "1234"]
        # Don't call input if auth file doesn't exist
        if not os.path.exists(self.auth_file):
            mock_input.return_value = "n"
        else:
            mock_input.return_value = "y"  # Reconfigure if exists
        
        with patch.object(self.cli, 'get_device_id', return_value="UNKNOWN"):
            self.cli.setup()
        
        # Verify auth file was created
        self.assertTrue(os.path.exists(self.auth_file))
        with open(self.auth_file, 'r') as f:
            auth_data = json.load(f)
            self.assertIsNotNone(auth_data.get('pin_hash'))
            self.assertIsNotNone(auth_data.get('recovery_code'))
            self.assertTrue(auth_data['recovery_code'].startswith('REC-'))
    
    @patch('getpass.getpass')
    @patch('builtins.input')
    def test_setup_pin_validation(self, mock_input, mock_getpass):
        """Test setup with invalid PIN"""
        # Simulate invalid PIN then valid one
        call_count = [0]
        def getpass_side_effect(prompt):
            call_count[0] += 1
            if call_count[0] == 1:
                return "12"  # Too short
            elif call_count[0] == 2:
                return "1234"  # Valid
            else:
                return "1234"  # Confirm
        
        mock_getpass.side_effect = getpass_side_effect
        mock_input.return_value = "n"
        
        with patch.object(self.cli, 'get_device_id', return_value="UNKNOWN"):
            self.cli.setup()
        
        # Should eventually succeed with valid PIN
        self.assertGreater(call_count[0], 2)
    
    @patch('getpass.getpass')
    @patch('builtins.input')
    def test_change_pin(self, mock_input, mock_getpass):
        """Test changing PIN"""
        # Create existing auth file
        os.makedirs(os.path.dirname(self.auth_file), exist_ok=True)
        auth_data = {
            'pin_hash': 'old_hash',
            'failed_attempts': 0,
            'lockout_until': None
        }
        with open(self.auth_file, 'w') as f:
            json.dump(auth_data, f)
        
        mock_getpass.side_effect = ["1234", "5678", "5678"]  # current, new, confirm
        mock_input.return_value = "n"
        
        with patch.object(self.cli, 'get_device_id', return_value="TEST123"):
            self.cli.change_pin()
        
        # Verify PIN was updated
        with open(self.auth_file, 'r') as f:
            updated_data = json.load(f)
            self.assertNotEqual(updated_data['pin_hash'], 'old_hash')
            self.assertEqual(updated_data['failed_attempts'], 0)
    
    @patch('builtins.input')
    def test_emergency_unlock_success(self, mock_input):
        """Test emergency unlock with valid recovery code"""
        # Create auth file with recovery code
        os.makedirs(os.path.dirname(self.auth_file), exist_ok=True)
        recovery_code = "REC-TEST1234-TEST5678"
        auth_data = {
            'pin_hash': 'test_hash',
            'recovery_code': recovery_code,
            'failed_attempts': 3,
            'lockout_until': None
        }
        with open(self.auth_file, 'w') as f:
            json.dump(auth_data, f)
        
        mock_input.return_value = recovery_code
        
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = Mock(returncode=0)
            self.cli.emergency_unlock()
        
        # Verify new recovery code was generated
        with open(self.auth_file, 'r') as f:
            updated_data = json.load(f)
            self.assertNotEqual(updated_data['recovery_code'], recovery_code)
            self.assertEqual(updated_data['failed_attempts'], 0)
    
    @patch('builtins.input')
    def test_emergency_unlock_invalid_code(self, mock_input):
        """Test emergency unlock with invalid recovery code"""
        os.makedirs(os.path.dirname(self.auth_file), exist_ok=True)
        auth_data = {
            'recovery_code': 'REC-VALID-CODE'
        }
        with open(self.auth_file, 'w') as f:
            json.dump(auth_data, f)
        
        mock_input.return_value = "WRONG-CODE"
        
        self.cli.emergency_unlock()
        
        # Verify recovery code wasn't changed
        with open(self.auth_file, 'r') as f:
            data = json.load(f)
            self.assertEqual(data['recovery_code'], 'REC-VALID-CODE')
    
    def test_logs_file_not_found(self):
        """Test logs command when log file doesn't exist"""
        output = []
        def mock_print(*args, **kwargs):
            output.append(' '.join(str(a) for a in args))
        
        with patch('builtins.print', side_effect=mock_print):
            self.cli.logs()
        
        self.assertIn("No log file found", ' '.join(output))
    
    @patch('subprocess.run')
    def test_logs_with_file(self, mock_subprocess):
        """Test logs command when log file exists"""
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        with open(self.log_file, 'w') as f:
            f.write("Line 1\nLine 2\nLine 3\n")
        
        mock_subprocess.return_value = Mock(returncode=0)
        # Patch load_config to return our test log file path
        with patch.object(self.cli, 'load_config', return_value={'service': {'log_file': self.log_file}}):
            self.cli.logs(2)
        
        # Verify subprocess was called
        mock_subprocess.assert_called()
    
    def test_load_config_success(self):
        """Test loading configuration"""
        config = self.cli.load_config()
        self.assertIsInstance(config, dict)
        self.assertIn('service', config)
    
    def test_load_config_not_found(self):
        """Test loading configuration when file doesn't exist"""
        self.cli.config_path = "/nonexistent/path/config.json"
        
        with patch('sys.exit'):
            try:
                config = self.cli.load_config()
            except SystemExit:
                pass


if __name__ == '__main__':
    unittest.main()

