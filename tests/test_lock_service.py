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
from unittest.mock import Mock, patch, MagicMock, call, mock_open
from datetime import datetime, timedelta

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
        self.config_dir = os.path.join(self.test_dir, 'config')
        self.log_file = os.path.join(self.test_dir, 'test.log')
        
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Create test config
        test_config = {
            "service": {
                "name": "lock-service",
                "version": "1.0.0",
                "log_level": "CRITICAL",
                "log_file": self.log_file,
                "pid_file": os.path.join(self.test_dir, 'test.pid'),
                "config_file": self.config_path
            },
            "network": {
                "usb_interface": "usb0",
                "blocked_interfaces": ["eth0", "wlan0"],
                "allowed_ports": [],
                "blocked_ports": [22, 80, 443]
            },
            "logging": {
                "verbose": True,
                "include_device_info": True,
                "external_logging": {"enabled": False}
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
    
    def test_init_without_android_serial(self):
        """Test initialization without configured Android device"""
        service = LockService(self.config_path, config_dir=self.config_dir)
        self.assertIsNone(service.android_serial)
        self.assertFalse(service.is_configured())
    
    def test_init_with_android_serial(self):
        """Test initialization with configured Android device"""
        # Create android_serial file
        serial_file = os.path.join(self.config_dir, 'android_serial')
        with open(serial_file, 'w') as f:
            f.write('DEVICE123456')
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        self.assertEqual(service.android_serial, 'DEVICE123456')
        self.assertTrue(service.is_configured())
    
    def test_save_android_serial(self):
        """Test saving Android serial"""
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.save_android_serial('TEST_SERIAL')
        
        # Verify file was created
        serial_file = os.path.join(self.config_dir, 'android_serial')
        self.assertTrue(os.path.exists(serial_file))
        
        # Verify content
        with open(serial_file, 'r') as f:
            self.assertEqual(f.read().strip(), 'TEST_SERIAL')
        
        # Verify permissions (should be 600)
        file_stat = os.stat(serial_file)
        self.assertEqual(oct(file_stat.st_mode)[-3:], '600')
    
    def test_load_android_serial_error(self):
        """Test loading Android serial with error"""
        service = LockService(self.config_path, config_dir=self.config_dir)
        
        # Set config_dir to non-existent path
        service.config_dir = '/nonexistent/path'
        result = service.load_android_serial()
        self.assertIsNone(result)
    
    @patch('subprocess.run')
    def test_get_connected_android_serials(self, mock_subprocess):
        """Test getting connected Android device serials"""
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="List of devices attached\nDEVICE123\tdevice\nDEVICE456\tdevice\n"
        )
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        serials = service.get_connected_android_serials()
        
        self.assertEqual(len(serials), 2)
        self.assertIn('DEVICE123', serials)
        self.assertIn('DEVICE456', serials)
    
    @patch('subprocess.run')
    def test_get_connected_android_serials_no_devices(self, mock_subprocess):
        """Test getting serials when no devices connected"""
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="List of devices attached\n"
        )
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        serials = service.get_connected_android_serials()
        
        self.assertEqual(len(serials), 0)
    
    @patch('subprocess.run')
    def test_get_connected_android_serials_adb_error(self, mock_subprocess):
        """Test getting serials when adb fails"""
        mock_subprocess.return_value = Mock(returncode=1, stdout="")
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        serials = service.get_connected_android_serials()
        
        self.assertEqual(len(serials), 0)
    
    @patch('subprocess.run')
    def test_get_connected_android_serials_adb_not_found(self, mock_subprocess):
        """Test getting serials when adb not installed"""
        mock_subprocess.side_effect = FileNotFoundError()
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        serials = service.get_connected_android_serials()
        
        self.assertEqual(len(serials), 0)
    
    @patch('subprocess.run')
    def test_get_connected_android_serials_timeout(self, mock_subprocess):
        """Test getting serials with timeout"""
        import subprocess
        mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd='adb', timeout=5)
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        serials = service.get_connected_android_serials()
        
        self.assertEqual(len(serials), 0)
    
    @patch('subprocess.run')
    def test_is_configured_device_connected_true(self, mock_subprocess):
        """Test checking if configured device is connected - true"""
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="List of devices attached\nDEVICE123\tdevice\n"
        )
        
        # Configure device
        serial_file = os.path.join(self.config_dir, 'android_serial')
        with open(serial_file, 'w') as f:
            f.write('DEVICE123')
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        result = service.is_configured_device_connected()
        
        self.assertTrue(result)
    
    @patch('subprocess.run')
    def test_is_configured_device_connected_false(self, mock_subprocess):
        """Test checking if configured device is connected - false"""
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="List of devices attached\nOTHER_DEVICE\tdevice\n"
        )
        
        # Configure device
        serial_file = os.path.join(self.config_dir, 'android_serial')
        with open(serial_file, 'w') as f:
            f.write('DEVICE123')
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        result = service.is_configured_device_connected()
        
        self.assertFalse(result)
    
    def test_is_configured_device_connected_no_config(self):
        """Test checking if configured device is connected - no config"""
        service = LockService(self.config_path, config_dir=self.config_dir)
        result = service.is_configured_device_connected()
        
        self.assertFalse(result)
    
    @patch('subprocess.run')
    def test_lock_system(self, mock_subprocess):
        """Test system lockdown"""
        mock_subprocess.return_value = Mock(returncode=0)
        
        service = LockService(self.config_path, config_dir=self.config_dir)
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
    def test_lock_system_idempotent(self, mock_subprocess):
        """Test that lock_system is idempotent"""
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.is_locked = True
        
        initial_call_count = mock_subprocess.call_count
        service.lock_system()
        
        # Should not make additional calls if already locked
        self.assertEqual(mock_subprocess.call_count, initial_call_count)
    
    @patch('subprocess.run')
    def test_lock_system_exception(self, mock_subprocess):
        """Test lock_system handles exception"""
        mock_subprocess.side_effect = Exception("System error")
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.security_policies = {'lock_policies': {'disable_ssh': True}}
        
        # Should not raise
        service.lock_system()
    
    @patch('subprocess.run')
    def test_unlock_system(self, mock_subprocess):
        """Test system unlock"""
        mock_subprocess.return_value = Mock(returncode=0)
        
        service = LockService(self.config_path, config_dir=self.config_dir)
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
    
    @patch('subprocess.run')
    def test_unlock_system_idempotent(self, mock_subprocess):
        """Test that unlock_system is idempotent"""
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.is_locked = False
        
        initial_call_count = mock_subprocess.call_count
        service.unlock_system()
        
        # Should not make additional calls if already unlocked
        self.assertEqual(mock_subprocess.call_count, initial_call_count)
    
    @patch('subprocess.run')
    def test_unlock_system_exception(self, mock_subprocess):
        """Test unlock_system handles exception"""
        mock_subprocess.side_effect = Exception("System error")
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.is_locked = True
        service.security_policies = {'unlock_policies': {'restore_ssh': True}}
        
        # Should not raise
        service.unlock_system()
    
    def test_signal_handler(self):
        """Test signal handling"""
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.running = True
        
        service.signal_handler(signal.SIGTERM, None)
        
        self.assertFalse(service.running)
    
    @patch('subprocess.run')
    @patch('time.sleep')
    def test_run_not_configured(self, mock_sleep, mock_subprocess):
        """Test run() when no device is configured"""
        mock_sleep.side_effect = KeyboardInterrupt()
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        
        try:
            service.run()
        except KeyboardInterrupt:
            pass
        
        # Should not lock when not configured
        self.assertFalse(service.is_locked)
    
    @patch('subprocess.run')
    @patch('time.sleep')
    def test_run_device_not_connected_locks(self, mock_sleep, mock_subprocess):
        """Test run() locks when configured device not connected"""
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="List of devices attached\n"
        )
        mock_sleep.side_effect = KeyboardInterrupt()
        
        # Configure device
        serial_file = os.path.join(self.config_dir, 'android_serial')
        with open(serial_file, 'w') as f:
            f.write('DEVICE123')
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.security_policies = {'lock_policies': {}}
        
        try:
            service.run()
        except KeyboardInterrupt:
            pass
        
        # Should lock when device not connected
        self.assertTrue(service.is_locked)
    
    @patch('subprocess.run')
    @patch('time.sleep')
    def test_run_device_connected_unlocks(self, mock_sleep, mock_subprocess):
        """Test run() unlocks when device connects"""
        call_count = [0]
        
        def subprocess_side_effect(*args, **kwargs):
            call_count[0] += 1
            # Call 1: startup check - device not connected
            # Call 2: first loop iteration - device not connected
            # Call 3: second loop iteration - device connected
            if call_count[0] <= 2:
                return Mock(returncode=0, stdout="List of devices attached\n")
            else:
                return Mock(returncode=0, stdout="List of devices attached\nDEVICE123\tdevice\n")
        
        mock_subprocess.side_effect = subprocess_side_effect
        
        sleep_count = [0]
        def sleep_side_effect(seconds):
            sleep_count[0] += 1
            # Allow at least 2 loop iterations (device connects on 2nd iteration)
            if sleep_count[0] >= 3:
                raise KeyboardInterrupt()
        
        mock_sleep.side_effect = sleep_side_effect
        
        # Configure device
        serial_file = os.path.join(self.config_dir, 'android_serial')
        with open(serial_file, 'w') as f:
            f.write('DEVICE123')
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.security_policies = {
            'lock_policies': {
                'disable_ssh': False,
                'disable_network_interfaces': False,
                'block_all_ports': False
            },
            'unlock_policies': {
                'restore_network_interfaces': True,
                'restore_ssh': True,
                'restore_all_ports': True
            }
        }
        
        # Service should start unlocked, then lock on startup if device not connected
        # But we need to check after run() starts
        
        # Initially should be unlocked
        self.assertFalse(service.is_locked)
        
        try:
            service.run()
        except KeyboardInterrupt:
            pass
        
        # Should unlock when device connects in loop (after locking on startup)
        # The device connects on call 3, so after 2 loop iterations it should be unlocked
        self.assertFalse(service.is_locked)
    
    @patch('subprocess.run')
    @patch('time.sleep')
    def test_run_device_disconnects_locks(self, mock_sleep, mock_subprocess):
        """Test run() locks when device disconnects"""
        call_count = [0]
        
        def subprocess_side_effect(*args, **kwargs):
            call_count[0] += 1
            # First few calls: device connected
            # Later calls: device disconnected
            if call_count[0] <= 3:
                return Mock(returncode=0, stdout="List of devices attached\nDEVICE123\tdevice\n")
            else:
                return Mock(returncode=0, stdout="List of devices attached\n")
        
        mock_subprocess.side_effect = subprocess_side_effect
        
        sleep_count = [0]
        def sleep_side_effect(seconds):
            sleep_count[0] += 1
            if sleep_count[0] >= 3:
                raise KeyboardInterrupt()
        
        mock_sleep.side_effect = sleep_side_effect
        
        # Configure device
        serial_file = os.path.join(self.config_dir, 'android_serial')
        with open(serial_file, 'w') as f:
            f.write('DEVICE123')
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.security_policies = {'lock_policies': {}, 'unlock_policies': {}}
        
        try:
            service.run()
        except KeyboardInterrupt:
            pass
        
        # Should lock when device disconnects
        self.assertTrue(service.is_locked)
    
    @patch('time.sleep')
    def test_run_exception_in_loop(self, mock_sleep):
        """Test run() handles exceptions in main loop"""
        service = LockService(self.config_path, config_dir=self.config_dir)
        
        # Configure device
        serial_file = os.path.join(self.config_dir, 'android_serial')
        with open(serial_file, 'w') as f:
            f.write('DEVICE123')
        
        call_count = [0]
        def detect_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("Simulated error")
            return False
        
        sleep_count = [0]
        sleep_durations = []
        def sleep_side_effect(seconds):
            sleep_count[0] += 1
            sleep_durations.append(seconds)
            if sleep_count[0] >= 2:
                raise KeyboardInterrupt()
        
        mock_sleep.side_effect = sleep_side_effect
        
        with patch.object(service, 'is_configured_device_connected', side_effect=detect_side_effect):
            try:
                service.run()
            except KeyboardInterrupt:
                pass
        
        # Should have called sleep with 5 seconds for error recovery
        self.assertIn(5, sleep_durations)


class TestLockServiceConfig(unittest.TestCase):
    """Test configuration handling"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.test_dir, 'config.json')
        self.config_dir = os.path.join(self.test_dir, 'config')
        os.makedirs(self.config_dir, exist_ok=True)
    
    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_load_config_default_fallback(self):
        """Test loading default config when file not found"""
        nonexistent_path = os.path.join(self.test_dir, 'nonexistent.json')
        service = LockService(nonexistent_path, config_dir=self.config_dir)
        self.assertIsNotNone(service.config)
    
    def test_load_config_invalid_json(self):
        """Test loading config with invalid JSON"""
        with open(self.config_path, 'w') as f:
            f.write("{ invalid json }")
        
        with self.assertRaises(ValueError) as context:
            LockService(self.config_path, config_dir=self.config_dir)
        
        self.assertIn('Invalid JSON', str(context.exception))
    
    def test_validate_config_missing_service(self):
        """Test config validation with missing service section"""
        config = {"network": {}, "monitoring": {}}
        with open(self.config_path, 'w') as f:
            json.dump(config, f)
        
        with self.assertRaises(ValueError) as context:
            LockService(self.config_path, config_dir=self.config_dir)
        
        self.assertIn('service', str(context.exception))
    
    def test_validate_config_missing_network(self):
        """Test config validation with missing network section"""
        config = {
            "service": {"log_level": "INFO", "log_file": "/tmp/test.log"},
            "monitoring": {"check_interval_seconds": 5}
        }
        with open(self.config_path, 'w') as f:
            json.dump(config, f)
        
        with self.assertRaises(ValueError) as context:
            LockService(self.config_path, config_dir=self.config_dir)
        
        self.assertIn('network', str(context.exception))
    
    def test_validate_config_missing_monitoring(self):
        """Test config validation with missing monitoring section"""
        config = {
            "service": {"log_level": "INFO", "log_file": "/tmp/test.log"},
            "network": {"blocked_interfaces": []}
        }
        with open(self.config_path, 'w') as f:
            json.dump(config, f)
        
        with self.assertRaises(ValueError) as context:
            LockService(self.config_path, config_dir=self.config_dir)
        
        self.assertIn('monitoring', str(context.exception))
    
    def test_load_security_policies_not_found(self):
        """Test loading security policies when file not found"""
        config = {
            "service": {"log_level": "CRITICAL", "log_file": "/tmp/test.log"},
            "network": {"blocked_interfaces": []},
            "monitoring": {"check_interval_seconds": 5}
        }
        with open(self.config_path, 'w') as f:
            json.dump(config, f)
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        # Should return empty dict, not raise
        self.assertIsInstance(service.security_policies, dict)
    
    def test_get_system_info_success(self):
        """Test get_system_info reads /etc/os-release"""
        config = {
            "service": {"log_level": "CRITICAL", "log_file": "/tmp/test.log"},
            "network": {"blocked_interfaces": []},
            "monitoring": {"check_interval_seconds": 5}
        }
        with open(self.config_path, 'w') as f:
            json.dump(config, f)
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        with patch('builtins.open', mock_open(read_data='PRETTY_NAME="Ubuntu 22.04"\n')):
            result = service.get_system_info()
            self.assertEqual(result, "Ubuntu 22.04")
    
    def test_get_system_info_file_not_found(self):
        """Test get_system_info when file not found"""
        config = {
            "service": {"log_level": "CRITICAL", "log_file": "/tmp/test.log"},
            "network": {"blocked_interfaces": []},
            "monitoring": {"check_interval_seconds": 5}
        }
        with open(self.config_path, 'w') as f:
            json.dump(config, f)
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        with patch('builtins.open', side_effect=FileNotFoundError()):
            result = service.get_system_info()
            self.assertEqual(result, "Unknown Linux System")


class TestLockServiceMain(unittest.TestCase):
    """Test cases for main() function"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.test_dir, 'config.json')
        self.config_dir = os.path.join(self.test_dir, 'config')
        os.makedirs(self.config_dir, exist_ok=True)
        
        test_config = {
            "service": {
                "name": "lock-service",
                "version": "1.0.0",
                "log_level": "CRITICAL",
                "log_file": os.path.join(self.test_dir, 'test.log'),
                "pid_file": os.path.join(self.test_dir, 'test.pid'),
                "config_file": self.config_path
            },
            "network": {
                "usb_interface": "usb0",
                "blocked_interfaces": ["eth0", "wlan0"],
                "allowed_ports": [],
                "blocked_ports": [22, 80, 443]
            },
            "monitoring": {
                "check_interval_seconds": 5
            }
        }
        
        with open(self.config_path, 'w') as f:
            json.dump(test_config, f)
    
    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch.object(LockService, 'run')
    def test_main_default_args(self, mock_run):
        """Test main() with default arguments"""
        mock_run.return_value = None
        
        with patch('sys.argv', ['lock-service.py', '--config', self.config_path]):
            lock_service_module.main()
        
        mock_run.assert_called_once()

    @patch.object(LockService, 'run')
    def test_main_with_daemon_flag(self, mock_run):
        """Test main() with --daemon flag"""
        mock_run.return_value = None
        
        with patch('sys.argv', ['lock-service.py', '--config', self.config_path, '--daemon']):
            with patch('daemon.DaemonContext') as mock_daemon:
                mock_daemon.return_value.__enter__ = Mock()
                mock_daemon.return_value.__exit__ = Mock(return_value=False)
                lock_service_module.main()


if __name__ == '__main__':
    unittest.main()
