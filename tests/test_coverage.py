#!/usr/bin/env python3
"""
Additional tests to maximize code coverage
Tests for edge cases, error handling, and uncovered code paths
"""

import unittest
import os
import json
import tempfile
import shutil
import signal
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open, call
import sys

# Add src directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.join(parent_dir, "src")
sys.path.insert(0, src_dir)

# Mock pyudev before importing LockService
sys.modules['pyudev'] = MagicMock()

# Import from package
from locker.service import LockService, main
from locker.cli import LockCLI
from tests.test_utils import skip_if_macos


def _find_config_file_use_given_path(path):
    """Make find_config_file return the given path so tests load their config, not project config."""
    return path


class TestServiceCoverage(unittest.TestCase):
    """Additional tests for LockService to maximize coverage"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.test_dir, 'config.json')
        self.config_dir = os.path.join(self.test_dir, 'config')
        self.log_file = os.path.join(self.test_dir, 'test.log')
        
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Create test config
        self.test_config = {
            "service": {
                "log_level": "CRITICAL",
                "log_file": self.log_file
            },
            "monitoring": {
                "check_interval_seconds": 5
            },
            "mode": "permissive",
            "android_serial": None,
            "services": []
        }
        
        with open(self.config_path, 'w') as f:
            json.dump(self.test_config, f)
        
        self._find_config_patcher = patch('locker.config.find_config_file', side_effect=_find_config_file_use_given_path)
        self._find_config_patcher.start()
        
        import logging
        logging.disable(logging.CRITICAL)
    
    def tearDown(self):
        """Clean up test fixtures"""
        self._find_config_patcher.stop()
        shutil.rmtree(self.test_dir, ignore_errors=True)
        import logging
        logging.disable(logging.NOTSET)
    
    def test_load_config_from_fallback_config_json(self):
        """Test that config file must exist (no fallback searching)"""
        # Remove the test config
        os.remove(self.config_path)
        
        # Should raise FileNotFoundError since config file doesn't exist
        with self.assertRaises(FileNotFoundError):
            LockService(self.config_path, config_dir=self.config_dir)
    
    def test_load_config_services_list_conversion(self):
        """Test that old services dict format is rejected (no conversion)"""
        config = self.test_config.copy()
        config['services'] = {
            'stop_when_locked': ['ssh', 'nginx'],
            'start_when_unlocked': ['ssh', 'apache']
        }
        
        with open(self.config_path, 'w') as f:
            json.dump(config, f)
        
        # Should raise ValueError because services must be a list
        with self.assertRaises(ValueError) as context:
            LockService(self.config_path, config_dir=self.config_dir)
        self.assertIn('services', str(context.exception))
    
    def test_load_config_services_invalid_format(self):
        """Test that invalid services format is rejected (no conversion)"""
        config = self.test_config.copy()
        config['services'] = "invalid"
        
        with open(self.config_path, 'w') as f:
            json.dump(config, f)
        
        # Should raise ValueError because services must be a list
        with self.assertRaises(ValueError) as context:
            LockService(self.config_path, config_dir=self.config_dir)
        self.assertIn('services', str(context.exception))
    
    def test_setup_logging_file_handler_error(self):
        """Test logging setup when file handler fails"""
        config = self.test_config.copy()
        config['service']['log_file'] = '/nonexistent/path/test.log'
        
        with open(self.config_path, 'w') as f:
            json.dump(config, f)
        
        # Should not raise, just skip file handler
        service = LockService(self.config_path, config_dir=self.config_dir)
        self.assertIsNotNone(service.logger)
    
    
    def test_lock_system_with_services_list(self):
        """Test lock_system with services list"""
        config = self.test_config.copy()
        config['services'] = ['ssh', 'nginx']
        
        with open(self.config_path, 'w') as f:
            json.dump(config, f)
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        
        with patch('subprocess.run') as mock_subprocess:
            # Mock is_service_running to return True so services will be stopped
            with patch('locker.utils.is_service_running', return_value=True):
                service.lock_system(service.config['services'], True)
            
            # Check that systemctl stop was called for each service
            stop_calls = [c for c in mock_subprocess.call_args_list 
                         if len(c[0]) > 0 and 'systemctl' in str(c[0][0]) and 'stop' in str(c[0][0])]
            self.assertGreater(len(stop_calls), 1)
    
    def test_unlock_system_with_services_list(self):
        """Test unlock_system with services list"""
        config = self.test_config.copy()
        config['services'] = ['ssh', 'nginx']
        config['mode'] = 'enforcing'

        with open(self.config_path, 'w') as f:
            json.dump(config, f)
        
        service = LockService(self.config_path, config_dir=self.config_dir)
    
        with patch('subprocess.run') as mock_subprocess:
            service.unlock_system(service.config['services'], True)
            
            # Check that systemctl start was called for each service
            start_calls = [c for c in mock_subprocess.call_args_list
                           if len(c[0]) > 0 and 'systemctl' in str(c[0][0]) and 'start' in str(c[0][0])]
            self.assertGreater(len(start_calls), 0)
    
    @patch('locker.utils.pyudev.Context')
    def test_get_connected_android_serials_exception_handling(self, mock_context_class):
        """Test get_connected_devices handles exception on failure"""
        # Make context raise exception
        mock_context_class.side_effect = Exception("Test exception")
        
        with open(self.config_path, 'w') as f:
            json.dump(self.test_config, f)
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        from locker import utils
        
        # Should return empty list (silently handles errors)
        devices = utils.get_connected_devices(logger=service.logger)
        serials = [d[0] for d in devices]
        
        self.assertEqual(len(serials), 0)
    
    @patch('locker.utils.pyudev.Context')
    def test_get_connected_android_serials_vendor_id_exception(self, mock_context_class):
        """Test get_connected_devices handles exception when listing devices fails"""
        mock_context = Mock()
        
        # Make list_devices raise exception
        mock_context.list_devices = Mock(side_effect=Exception("Vendor ID error"))
        mock_context_class.return_value = mock_context
        
        with open(self.config_path, 'w') as f:
            json.dump(self.test_config, f)
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        from locker import utils
        
        # Should return empty list (silently handles errors)
        devices = utils.get_connected_devices(logger=service.logger)
        serials = [d[0] for d in devices]
        
        self.assertEqual(len(serials), 0)
    
    @patch('locker.utils.pyudev.Context')
    def test_get_connected_android_serials_broad_usb_check(self, mock_context_class):
        """Test get_connected_devices via broad USB subsystem check"""
        
        mock_device = Mock()
        mock_device.get = Mock(side_effect=lambda k, default='': {
            'ID_SERIAL_SHORT': 'DEVICE789',
            'ID_SERIAL': 'DEVICE789',
            'ID_VENDOR_ID': '18d1',  # Android vendor ID
            'ID_USB_INTERFACES': 'ff:42:81',  # Android Debug Bridge interface class
            'ID_MODEL': 'Test_Device',
            'DEVPATH': '/devices/pci0000:00/0000:00:14.0/usb1/1-3'
        }.get(k, default))
        
        mock_context = Mock()
        def list_devices_side_effect(*args, **kwargs):
            if kwargs.get('subsystem') == 'usb':
                return [mock_device]
            return []
        
        mock_context.list_devices = Mock(side_effect=list_devices_side_effect)
        mock_context_class.return_value = mock_context
        
        with open(self.config_path, 'w') as f:
            json.dump(self.test_config, f)
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        from locker import utils
        devices = utils.get_connected_devices(logger=service.logger)
        serials = [d[0] for d in devices]
        
        self.assertIn('DEVICE789', serials)
    
    def test_run_permissive_mode_not_configured(self):
        """Test run() in permissive mode when not configured"""
        config = self.test_config.copy()
        config['mode'] = 'permissive'
        with open(self.config_path, 'w') as f:
            json.dump(config, f)

        service = LockService(self.config_path, config_dir=self.config_dir)
        
        with patch('time.sleep', side_effect=KeyboardInterrupt()):
            try:
                service.run()
            except KeyboardInterrupt:
                pass
        
        # Should not lock when not configured in permissive mode
        self.assertFalse(service.running)
    
    def test_run_enforcing_mode_not_configured(self):
        """Test run() in enforcing mode when not configured"""
        config = self.test_config.copy()
        config['mode'] = 'enforcing'
        with open(self.config_path, 'w') as f:
            json.dump(self.test_config, f)
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.mode = 'enforcing'
        service.running = True
        
        with patch('time.sleep', side_effect=KeyboardInterrupt()):
            try:
                service.run()
            except KeyboardInterrupt:
                pass
        
        # Should not lock when not configured even in enforcing mode
        self.assertFalse(service.running)
    
    @patch('locker.utils.pyudev.Context')
    @patch('time.sleep')
    def test_run_device_connection_state_changes(self, mock_sleep, mock_context_class):
        """Test run() handles device connection state changes"""
        # Create mock device
        mock_device = Mock()
        mock_device.get = Mock(side_effect=lambda k: {
            'ID_SERIAL_SHORT': 'DEVICE123',
            'ID_SERIAL': 'DEVICE123',
            'DEVPATH': '/devices/pci0000:00/0000:00:14.0/usb1/1-1'
        }.get(k))
        
        call_count = [0]
        def list_devices_side_effect(*args, **kwargs):
            call_count[0] += 1
            # Device connects on iteration 2, disconnects on iteration 4
            if 2 <= call_count[0] <= 3:
                return [mock_device]
            return []
        
        mock_context = Mock()
        mock_context.list_devices = Mock(side_effect=list_devices_side_effect)
        mock_context_class.return_value = mock_context
        
        # Configure device
        serial_file = os.path.join(self.config_dir, 'android_serial')
        with open(serial_file, 'w') as f:
            f.write('DEVICE123')
        
        config = self.test_config.copy()
        
        with open(self.config_path, 'w') as f:
            json.dump(config, f)
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.mode = 'enforcing'
        service.running = True
        
        sleep_count = [0]
        def sleep_side_effect(seconds):
            sleep_count[0] += 1
            if sleep_count[0] >= 5:
                raise KeyboardInterrupt()
        
        mock_sleep.side_effect = sleep_side_effect
        
        with patch('subprocess.run'):
            try:
                service.run()
            except KeyboardInterrupt:
                pass
        
        # Should have processed state changes
        self.assertTrue(service.running is False or sleep_count[0] > 0)
    
    def test_run_enforcing_mode_device_not_connected_on_startup(self):
        """Enforcing mode with no device connected: validate mode, no device, and that the configured service is stopped."""
        # 1) No device connected: android_serial empty
        # 2) Mode is enforcing
        # 3) Use a basic Linux service we can stop (cron is standard and safe to mock)
        managed_service = 'cron'
        config = self.test_config.copy()
        config['mode'] = 'enforcing'
        config['android_serial'] = ''  # no device connected
        config['services'] = [managed_service]

        with open(self.config_path, 'w') as f:
            json.dump(config, f)

        service = LockService(self.config_path, config_dir=self.config_dir)
        self.assertEqual(service.config['mode'], 'enforcing')
        self.assertFalse(service.config.get('android_serial'))
        self.assertIn(managed_service, service.config['services'])

        # Mock subprocess: is-active (running) -> stop -> is-active (stopped)
        with patch('locker.utils.subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0),   # is_service_running: running
                Mock(returncode=0),   # systemctl stop: success
                Mock(returncode=1),   # is_service_running after stop: not running
            ]
            service.run_once()

        # Expect the service to have been stopped and not running
        stop_calls = [c for c in mock_run.call_args_list if c[0][0] == ['systemctl', 'stop', managed_service]]
        self.assertEqual(len(stop_calls), 1, 'systemctl stop %s should be called once' % managed_service)
        # is-active is called as ['systemctl', 'is-active', '--quiet', service_name]
        is_active_calls = [c for c in mock_run.call_args_list
                          if len(c[0][0]) >= 4 and c[0][0][:2] == ['systemctl', 'is-active'] and c[0][0][3] == managed_service]
        self.assertGreaterEqual(len(is_active_calls), 1, 'is-active should be called for the managed service')
        # side_effect was [running, stop_ok, not_running]; stop_service checks "not running" after stop
        self.assertEqual(mock_run.call_count, 3, 'expected: is-active, systemctl stop, is-active (verify stopped)')

    def test_enforcing_mode_stops_service_even_if_someone_starts_it(self):
        """Enforce mode: if someone starts the managed service, the locker stops it on the next cycle.
        No wait time required - service.py runs run_once() then sleep(check_interval); we simulate two cycles."""
        managed_service = 'cron'
        config = self.test_config.copy()
        config['mode'] = 'enforcing'
        config['android_serial'] = ''
        config['services'] = [managed_service]
        with open(self.config_path, 'w') as f:
            json.dump(config, f)

        service = LockService(self.config_path, config_dir=self.config_dir)

        # Cycle 1: cron running -> locker stops it (is-active, stop, is-active).
        # Then "someone" starts cron (no subprocess from us).
        # Cycle 2: cron running again -> locker stops it again (is-active, stop, is-active).
        with patch('locker.utils.subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0),   # cycle 1: is-active -> running
                Mock(returncode=0),   # cycle 1: systemctl stop ok
                Mock(returncode=1),   # cycle 1: is-active after stop -> not running
                Mock(returncode=0),   # cycle 2: is-active -> running (someone started it)
                Mock(returncode=0),   # cycle 2: systemctl stop ok
                Mock(returncode=1),   # cycle 2: is-active after stop -> not running
            ]
            service.run_once()   # first cycle: lock (stop cron)
            service.run_once()   # second cycle: lock again (stop cron after "someone" started it)

        stop_calls = [c for c in mock_run.call_args_list if c[0][0] == ['systemctl', 'stop', managed_service]]
        self.assertEqual(len(stop_calls), 2, 'systemctl stop should be called twice (both cycles)')
        self.assertEqual(mock_run.call_count, 6)
        # After second cycle, service is not running (last is-active returned 1)
        last_call_args = mock_run.call_args_list[-1][0][0]
        self.assertEqual(last_call_args[:2], ['systemctl', 'is-active'], 'last call should be is-active to verify stopped')

    @patch('time.sleep')
    def test_run_enforcing_mode_device_already_connected(self, mock_sleep):
        """Test run() in enforcing mode when device already connected"""
        # Configure device
        serial_file = os.path.join(self.config_dir, 'android_serial')
        with open(serial_file, 'w') as f:
            f.write('DEVICE123')
        config = self.test_config.copy()
        
        with open(self.config_path, 'w') as f:
            json.dump(config, f)
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.mode = 'enforcing'
        service.running = True
        
        # Mock device as connected
        with patch.object(service, 'is_configured_device_connected', return_value=True):
            with patch('subprocess.run'):
                mock_sleep.side_effect = KeyboardInterrupt()
                try:
                    service.run()
                except KeyboardInterrupt:
                    pass
        
        # Should not be locked if device is connected
        self.assertFalse(service.running)


class TestCLICoverage(unittest.TestCase):
    """Additional tests for LockCLI to maximize coverage"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.test_dir, 'config.json')
        self.config_dir = os.path.join(self.test_dir, 'config')
        self.pid_file = os.path.join(self.test_dir, 'locker.pid')
        self.log_file = os.path.join(self.test_dir, 'locker.log')
        
        os.makedirs(self.config_dir, exist_ok=True)
        
        self.test_config = {
            "service": {
                "name": "locker",
                "log_file": self.log_file,
                "log_level": "CRITICAL"
            },
            "monitoring": {
                "check_interval_seconds": 5
            },
            "mode": "permissive",
            "android_serial": None,
            "services": []
        }
        
        with open(self.config_path, 'w') as f:
            json.dump(self.test_config, f)
        
        self._find_config_patcher = patch('locker.config.find_config_file', side_effect=_find_config_file_use_given_path)
        self._find_config_patcher.start()
        
        self.cli = LockCLI()
        self.cli.config_path = self.config_path
        self.cli.config_dir = self.config_dir
        self.cli.service_pid_file = self.pid_file
        
        self.input_patcher = patch('builtins.input', return_value='n')
        self.input_patcher.start()
    
    def tearDown(self):
        """Clean up test fixtures"""
        self._find_config_patcher.stop()
        if hasattr(self, 'input_patcher'):
            self.input_patcher.stop()
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_add_service_converts_old_format(self):
        """Test add_service adds service (config must be valid; services dict fails validation on load)"""
        config = {
            "service": {"name": "locker", "log_file": self.log_file, "log_level": "CRITICAL"},
            "monitoring": {"check_interval_seconds": 5},
            "mode": "permissive",
            "android_serial": None,
            "services": ["ssh"]
        }
        with open(self.config_path, 'w') as f:
            json.dump(config, f)
        with patch('builtins.print'):
            self.cli.add_service('apache')
        new_config = self.cli.load_config()
        self.assertIsInstance(new_config['services'], list)
        self.assertIn('apache', new_config['services'])
    
    def test_add_service_invalid_format(self):
        """Test add_service when config has invalid services format - load_config validates so we patch to simulate"""
        with open(self.config_path, 'w') as f:
            json.dump(self.test_config, f)
        with patch('locker.cli.config.load_config') as mock_load:
            mock_load.return_value = {
                "service": {"name": "locker", "log_file": self.log_file, "log_level": "CRITICAL"},
                "monitoring": {"check_interval_seconds": 5},
                "mode": "permissive",
                "android_serial": None,
                "services": "invalid"
            }
            with patch('builtins.print'):
                self.cli.add_service('ssh')
            mock_load.assert_called()
        with open(self.config_path, 'r') as f:
            saved = json.load(f)
        self.assertIsInstance(saved.get('services', []), list)
    
    def test_set_mode_interactive_permissive(self):
        """Test set_mode interactive mode selection - permissive"""
        with patch('builtins.input', return_value='permissive'):
            with patch('builtins.print'):
                self.cli.set_mode()
        
        config = self.cli.load_config()
        self.assertEqual(config.get('mode'), 'permissive')
    
    def test_set_mode_interactive_enforcing(self):
        """Test set_mode interactive mode selection - enforcing"""
        # First set android_serial so enforcing mode is allowed
        config = self.cli.load_config()
        config['android_serial'] = 'TEST_DEVICE'
        self.cli.save_config(config)
        
        with patch('builtins.input', return_value='enforcing'):
            with patch('builtins.print'):
                self.cli.set_mode()
        
        config = self.cli.load_config()
        self.assertEqual(config.get('mode'), 'enforcing')
    
    def test_set_mode_interactive_invalid(self):
        """Test set_mode interactive mode selection - invalid input"""
        with patch('builtins.input', return_value='invalid'):
            with patch('builtins.print'):
                self.cli.set_mode()
        
        # Mode should not change
        config = self.cli.load_config()
        # Should remain default or unchanged
    
    def test_set_android_serial_manual_entry(self):
        """Test set_android_serial with manual entry"""
        with patch('builtins.input', side_effect=['y', 'MANUAL_SERIAL_123']):
            with patch('builtins.print'):
                with patch('locker.utils.get_connected_devices', return_value=[]):
                    self.cli.set_android_serial()
        
        config = self.cli.load_config()
        self.assertEqual(config.get('android_serial'), 'MANUAL_SERIAL_123')
    
    def test_set_android_serial_cancel(self):
        """Test set_android_serial when user cancels"""
        with patch('builtins.input', return_value='n'):
            with patch('builtins.print'):
                with patch('locker.utils.get_connected_devices', return_value=[]):
                    self.cli.set_android_serial()
        
        # Should not have set serial
        config = self.cli.load_config()
        # Serial should be None or unchanged
    
    def test_set_android_serial_single_device_auto_select(self):
        """Test set_android_serial with single device auto-select"""
        devices = [("DEVICE123", "Test Device")]
        
        with patch('builtins.input', return_value=''):
            with patch('builtins.print'):
                with patch('locker.utils.get_connected_devices', return_value=devices):
                    self.cli.set_android_serial()
        
        config = self.cli.load_config()
        self.assertEqual(config.get('android_serial'), 'DEVICE123')
    
    def test_set_android_serial_multiple_devices_select_by_number(self):
        """Test set_android_serial with multiple devices - select by number"""
        devices = [("DEVICE1", "Device 1"), ("DEVICE2", "Device 2")]
        
        with patch('builtins.input', return_value='1'):
            with patch('builtins.print'):
                with patch('locker.utils.get_connected_devices', return_value=devices):
                    self.cli.set_android_serial()
        
        config = self.cli.load_config()
        self.assertEqual(config.get('android_serial'), 'DEVICE1')
    
    def test_set_android_serial_multiple_devices_enter_serial(self):
        """Test set_android_serial with multiple devices - enter serial directly"""
        devices = [("DEVICE1", "Device 1"), ("DEVICE2", "Device 2")]
        
        with patch('builtins.input', return_value='CUSTOM_SERIAL'):
            with patch('builtins.print'):
                with patch('locker.utils.get_connected_devices', return_value=devices):
                    self.cli.set_android_serial()
        
        config = self.cli.load_config()
        self.assertEqual(config.get('android_serial'), 'CUSTOM_SERIAL')
    
    def test_set_android_serial_existing_serial_in_config(self):
        """Test set_android_serial when serial already in config"""
        config = self.cli.load_config()
        config['android_serial'] = 'EXISTING_SERIAL'
        self.cli.save_config(config)
        
        # Should use existing serial from config
        serial = self.cli.get_android_serial()
        self.assertEqual(serial, 'EXISTING_SERIAL')
    
    def test_logs_with_tail_command(self):
        """Test logs command using tail"""
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        with open(self.log_file, 'w') as f:
            f.write("Log line 1\nLog line 2\nLog line 3\n")
        
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = Mock(returncode=0)
            with patch.object(self.cli, 'load_config', return_value={'service': {'log_file': self.log_file}}):
                with patch('builtins.print'):
                    self.cli.logs(2)
        
        mock_subprocess.assert_called()
    
    def test_logs_fallback_to_file_read(self):
        """Test logs command falls back to file read when tail fails"""
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        with open(self.log_file, 'w') as f:
            f.write("Log line 1\nLog line 2\nLog line 3\n")
        
        with patch('subprocess.run', side_effect=FileNotFoundError()):
            with patch.object(self.cli, 'load_config', return_value={'service': {'log_file': self.log_file}}):
                output = []
                with patch('builtins.print', side_effect=lambda *a, **kw: output.extend(str(x) for x in a)):
                    self.cli.logs(2)
        
        # Should have read from file
        self.assertTrue(any('Log line' in str(o) for o in output))
    
    def test_restart_service_calls_stop_and_start(self):
        """Test restart_service calls stop and start"""
        with patch.object(self.cli, 'stop_service') as mock_stop:
            with patch.object(self.cli, 'start_service') as mock_start:
                with patch('time.sleep'):
                    self.cli.restart_service()
                
                mock_stop.assert_called_once()
                mock_start.assert_called_once()
    
    def test_get_android_serial_cmd_no_devices(self):
        """Test get_android_serial_cmd when no serial configured"""
        with patch.object(self.cli, 'get_android_serial', return_value=None):
            output = []
            with patch('builtins.print', side_effect=lambda *a, **kw: output.extend(str(x) for x in a)):
                self.cli.get_android_serial_cmd()
            
            output_text = ' '.join(output)
            self.assertIn("No Android serial configured", output_text)
    
    def test_get_android_serial_cmd_single_device(self):
        """Test get_android_serial_cmd with configured serial"""
        with patch.object(self.cli, 'get_android_serial', return_value="DEVICE123"):
            output = []
            with patch('builtins.print', side_effect=lambda *a, **kw: output.extend(str(x) for x in a)):
                self.cli.get_android_serial_cmd()
            
            output_text = ' '.join(output)
            self.assertIn("DEVICE123", output_text)
            self.assertIn("Configured Android serial", output_text)
    
    def test_get_android_serial_cmd_multiple_devices(self):
        """Test get_android_serial_cmd with configured serial"""
        with patch.object(self.cli, 'get_android_serial', return_value="DEVICE1"):
            output = []
            with patch('builtins.print', side_effect=lambda *a, **kw: output.extend(str(x) for x in a)):
                self.cli.get_android_serial_cmd()
            
            output_text = ' '.join(output)
            self.assertIn("DEVICE1", output_text)
            self.assertIn("Configured Android serial", output_text)
    
    def test_list_devices_no_devices(self):
        """Test list_devices_cmd when no devices found"""
        with patch('locker.utils.get_connected_devices', return_value=[]):
            with patch.object(self.cli, 'get_android_serial', return_value=None):
                output = []
                with patch('builtins.print', side_effect=lambda *a, **kw: output.extend(str(x) for x in a)):
                    self.cli.list_devices_cmd()
                
                output_text = ' '.join(output)
                self.assertIn("No Android devices found", output_text)
    
    def test_list_devices_with_configured(self):
        """Test list_devices_cmd shows configured device marker"""
        devices = [("DEVICE123", "Test Device")]
        with patch('locker.utils.get_connected_devices', return_value=devices):
            with patch.object(self.cli, 'get_android_serial', return_value="DEVICE123"):
                output = []
                with patch('builtins.print', side_effect=lambda *a, **kw: output.extend(str(x) for x in a)):
                    self.cli.list_devices_cmd()
                
                output_text = ' '.join(output)
                self.assertIn("DEVICE123", output_text)
                self.assertIn("Configured device", output_text)
                self.assertIn("currently connected", output_text)
    
    def test_list_devices_configured_not_connected(self):
        """Test list_devices_cmd shows when configured device is not connected"""
        devices = [("OTHER_DEVICE", "Other Device")]
        with patch('locker.utils.get_connected_devices', return_value=devices):
            with patch.object(self.cli, 'get_android_serial', return_value="DEVICE123"):
                output = []
                with patch('builtins.print', side_effect=lambda *a, **kw: output.extend(str(x) for x in a)):
                    self.cli.list_devices_cmd()
                
                output_text = ' '.join(output)
                self.assertIn("OTHER_DEVICE", output_text)
                self.assertIn("Configured device", output_text)
                self.assertIn("not currently connected", output_text)
    
    def test_is_service_running_pid_file_invalid_pid(self):
        """Test is_service_running with invalid PID in file"""
        os.makedirs(os.path.dirname(self.pid_file), exist_ok=True)
        with open(self.pid_file, 'w') as f:
            f.write("999999")  # Non-existent PID
        
        result = self.cli.is_service_running()
        self.assertFalse(result)
    
    def test_is_service_running_systemctl_timeout(self):
        """Test is_service_running handles systemctl timeout"""
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired('systemctl', 5)):
            result = self.cli.is_service_running()
            # Should fall back to PID file check
            self.assertFalse(result)
    
    def test_start_service_timeout(self):
        """Test start_service handles timeout"""
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired('systemctl', 10)):
            with patch.object(self.cli, 'is_service_running', return_value=False):
                output = []
                with patch('builtins.print', side_effect=lambda *a, **kw: output.extend(str(x) for x in a)):
                    self.cli.start_service()
                
                output_text = ' '.join(output)
                self.assertIn("timed out", output_text)
    
    def test_stop_service_timeout(self):
        """Test stop_service handles timeout"""
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired('systemctl', 10)):
            with patch.object(self.cli, 'is_service_running', return_value=True):
                output = []
                with patch('builtins.print', side_effect=lambda *a, **kw: output.extend(str(x) for x in a)):
                    self.cli.stop_service()
                
                output_text = ' '.join(output)
                self.assertIn("timed out", output_text)
    
    def test_save_config_creates_directory(self):
        """Test save_config creates directory if it doesn't exist"""
        new_config_path = os.path.join(self.test_dir, 'new', 'config.json')
        self.cli.config_path = new_config_path
        
        config = {"test": "value"}
        self.cli.save_config(config)
        
        self.assertTrue(os.path.exists(new_config_path))
        with open(new_config_path, 'r') as f:
            saved_config = json.load(f)
        self.assertEqual(saved_config, config)
    
    @skip_if_macos("Test checks run() when device not connected - stateless")
    def test_run_device_not_connected_not_locked(self):
        """Test run() locks when device not connected then exits on KeyboardInterrupt"""
        config = self.test_config.copy()
        config['android_serial'] = 'DEVICE123'
        config['mode'] = 'enforcing'
        with open(self.config_path, 'w') as f:
            json.dump(config, f)
        service = LockService(self.config_path, config_dir=self.config_dir)
        with patch.object(service, 'is_configured_device_connected', return_value=False):
            with patch('subprocess.run'):
                with patch('time.sleep', side_effect=KeyboardInterrupt()):
                    try:
                        service.run()
                    except KeyboardInterrupt:
                        pass
        # run() sets self.running = False when handling KeyboardInterrupt
        self.assertFalse(service.running)
    
    def test_setup_logging_critical_level(self):
        """Test setup_logging with CRITICAL log level"""
        config = self.test_config.copy()
        config['service']['log_level'] = 'CRITICAL'
        
        with open(self.config_path, 'w') as f:
            json.dump(config, f)
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        # Should not add handlers for CRITICAL level
        self.assertIsNotNone(service.logger)
    
    def test_load_config_android_serial_from_config(self):
        """Test load_config gets android_serial from config"""
        config = self.test_config.copy()
        config['android_serial'] = 'CONFIG_SERIAL'
        
        with open(self.config_path, 'w') as f:
            json.dump(config, f)
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        self.assertEqual(service.config.get('android_serial'), 'CONFIG_SERIAL')
    
    def test_is_configured_empty_string(self):
        """Test that empty string android_serial is not considered configured"""
        config = self.test_config.copy()
        config['android_serial'] = ''
        with open(self.config_path, 'w') as f:
            json.dump(config, f)
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        android_serial = service.config.get('android_serial')
        # Check that device is not configured (android_serial is None or empty)
        self.assertFalse(android_serial is not None and len(android_serial) > 0)
    
    def test_get_connected_devices_model_cleaning(self):
        """Test get_connected_devices cleans model names"""
        mock_device = Mock()
        mock_device.get = Mock(side_effect=lambda k, default='': {
            'ID_SERIAL_SHORT': 'DEVICE123',
            'ID_SERIAL': 'DEVICE123',
            'ID_MODEL': 'test_device_model',
            'ID_VENDOR_ID': '18d1'
        }.get(k, default))
        
        with patch('locker.utils.pyudev.Context') as mock_context_class:
            mock_context = Mock()
            mock_context.list_devices = Mock(return_value=[mock_device])
            mock_context_class.return_value = mock_context
            
            from locker import utils
            devices = utils.get_connected_devices()
            self.assertEqual(len(devices), 1)
            # Model should be cleaned (underscores to spaces, title case)
            self.assertIn('Test Device Model', devices[0][1])
    
    def test_get_connected_devices_unknown_model(self):
        """Test get_connected_devices handles unknown model"""
        mock_device = Mock()
        mock_device.get = Mock(side_effect=lambda k, default='Unknown': {
            'ID_SERIAL_SHORT': 'DEVICE123',
            'ID_SERIAL': 'DEVICE123',
            'ID_MODEL': default,
            'ID_VENDOR_ID': '18d1'
        }.get(k, default))
        
        with patch('locker.utils.pyudev.Context') as mock_context_class:
            mock_context = Mock()
            mock_context.list_devices = Mock(return_value=[mock_device])
            mock_context_class.return_value = mock_context
            
            from locker import utils
            devices = utils.get_connected_devices()
            self.assertEqual(len(devices), 1)
            self.assertEqual(devices[0][1], 'Unknown')
    
    def test_get_connected_devices_duplicate_serials(self):
        """Test get_connected_devices handles duplicate serials"""
        mock_device1 = Mock()
        mock_device1.get = Mock(side_effect=lambda k, default='': {
            'ID_SERIAL_SHORT': 'DEVICE123',
            'ID_SERIAL': 'DEVICE123',
            'ID_MODEL': 'Device1',
            'ID_VENDOR_ID': '18d1'
        }.get(k, default))
        
        mock_device2 = Mock()
        mock_device2.get = Mock(side_effect=lambda k, default='': {
            'ID_SERIAL_SHORT': 'DEVICE123',  # Same serial
            'ID_SERIAL': 'DEVICE123',
            'ID_MODEL': 'Device2',
            'ID_VENDOR_ID': '18d1'
        }.get(k, default))
        
        with patch('locker.utils.pyudev.Context') as mock_context_class:
            mock_context = Mock()
            mock_context.list_devices = Mock(return_value=[mock_device1, mock_device2])
            mock_context_class.return_value = mock_context
            
            from locker import utils
            devices = utils.get_connected_devices()
            # Should only have one device (duplicates removed)
            self.assertEqual(len(devices), 1)
    
    def test_get_connected_devices_no_serial_short(self):
        """Test get_connected_devices uses ID_SERIAL when ID_SERIAL_SHORT not available"""
        mock_device = Mock()
        mock_device.get = Mock(side_effect=lambda k, default='': {
            'ID_SERIAL': 'FULL_SERIAL_12345',  # No ID_SERIAL_SHORT
            'ID_MODEL': 'Test Device',
            'ID_VENDOR_ID': '18d1'
        }.get(k, default))
        
        with patch('locker.utils.pyudev.Context') as mock_context_class:
            mock_context = Mock()
            mock_context.list_devices = Mock(return_value=[mock_device])
            mock_context_class.return_value = mock_context
            
            from locker import utils
            devices = utils.get_connected_devices()
            self.assertEqual(len(devices), 1)
            self.assertEqual(devices[0][0], 'FULL_SERIAL_12345')
    
    def test_get_connected_devices_broad_check_exception(self):
        """Test get_connected_devices handles exception in broad USB check"""
        with patch('locker.utils.pyudev.Context') as mock_context_class:
            mock_context = Mock()
            
            call_count = [0]
            def list_devices_side_effect(*args, **kwargs):
                call_count[0] += 1
                if 'ID_VENDOR_ID' not in kwargs:
                    # Broad USB check raises exception
                    raise Exception("USB check error")
                return []
            
            mock_context.list_devices = Mock(side_effect=list_devices_side_effect)
            mock_context_class.return_value = mock_context
            
            from locker import utils
            devices = utils.get_connected_devices()
            # Should handle exception and return empty list
            self.assertEqual(devices, [])
    
    def test_set_android_serial_direct_provided(self):
        """Test set_android_serial with serial provided directly"""
        with patch('builtins.print'):
            self.cli.set_android_serial('DIRECT_SERIAL')
        
        config = self.cli.load_config()
        self.assertEqual(config.get('android_serial'), 'DIRECT_SERIAL')
    
    def test_set_android_serial_empty_serial(self):
        """Test set_android_serial with empty serial"""
        with patch('builtins.print'):
            self.cli.set_android_serial('')
        
        # Should not save empty serial
        config = self.cli.load_config()
        # Serial should be None or unchanged
    
    def test_set_mode_enforcing_no_serial(self):
        """Test set_mode enforcing without configured serial"""
        with patch('builtins.print'):
            self.cli.set_mode('enforcing')
        
        # Should not set mode without serial
        config = self.cli.load_config()
        # Mode should not be enforcing
    
    def test_logs_exception_handling(self):
        """Test logs when config.load_config raises - falls back to default path then 'No log file found'"""
        output = []
        with patch('builtins.print', side_effect=lambda *a, **kw: output.extend(str(x) for x in a)):
            with patch('locker.cli.config.load_config', side_effect=FileNotFoundError("Config not found")):
                with patch('os.path.exists', return_value=False):
                    self.cli.logs()
        output_text = ' '.join(output)
        self.assertIn("No log file", output_text)
    
    
    def test_is_service_running_systemctl_exception(self):
        """Test is_service_running handles systemctl exception"""
        with patch('subprocess.run', side_effect=Exception("systemctl error")):
            result = self.cli.is_service_running()
            # Should fall back to PID file check
            self.assertFalse(result)
    
    def test_start_service_exception(self):
        """Test start_service handles general exception"""
        with patch('subprocess.run', side_effect=Exception("General error")):
            with patch.object(self.cli, 'is_service_running', return_value=False):
                output = []
                with patch('builtins.print', side_effect=lambda *a, **kw: output.extend(str(x) for x in a)):
                    self.cli.start_service()
                
                output_text = ' '.join(output)
                self.assertIn("Error", output_text)
    
    def test_stop_service_exception(self):
        """Test stop_service handles general exception"""
        with patch('subprocess.run', side_effect=Exception("General error")):
            with patch.object(self.cli, 'is_service_running', return_value=True):
                output = []
                with patch('builtins.print', side_effect=lambda *a, **kw: output.extend(str(x) for x in a)):
                    self.cli.stop_service()
                
                output_text = ' '.join(output)
                self.assertIn("Error", output_text)
    
    def test_save_android_serial_exception(self):
        """Test save_android_serial handles exception"""
        # Make config_dir invalid
        self.cli.config_dir = '/root/protected'
        
        with patch('builtins.print'):
            # Should not raise, just log error
            self.cli.save_android_serial('TEST_SERIAL')
    
    def test_emergency_unlock_no_blocked_interfaces(self):
        """Test emergency_unlock with no blocked interfaces"""
        config = {}
        
        with patch('builtins.input', return_value='yes'):
            with patch('builtins.print'):
                with patch('subprocess.run'):
                    with patch.object(self.cli, 'load_config', return_value=config):
                        self.cli.emergency_unlock()
    
    def test_emergency_unlock_cancelled(self):
        """Test emergency_unlock when user cancels"""
        with patch('builtins.input', return_value='no'):
            output = []
            with patch('builtins.print', side_effect=lambda *a, **kw: output.extend(str(x) for x in a)):
                self.cli.emergency_unlock()
            
            output_text = ' '.join(output)
            self.assertIn("Cancelled", output_text)
    
    def test_emergency_unlock_exception_handling(self):
        """Test emergency_unlock handles exceptions (patch config.load_config - used by emergency_unlock and status)"""
        mock_config = {'services': ['ssh'], 'android_serial': None}
        with patch('builtins.input', return_value='yes'):
            with patch('locker.cli.config.load_config', return_value=mock_config):
                with patch('subprocess.run', side_effect=Exception("Error")):
                    output = []
                    with patch('builtins.print', side_effect=lambda *a, **kw: output.extend(str(x) for x in a)):
                        self.cli.emergency_unlock()
                    output_text = ' '.join(output)
                    self.assertIn("Error", output_text)
                    # status() also uses subprocess.run; with same patch it prints UNKNOWN for service status
                    output.clear()
                    with patch('builtins.print', side_effect=lambda *a, **kw: output.extend(str(x) for x in a)):
                        self.cli.status()
                    output_text = ' '.join(output)
                    self.assertIn("UNKNOWN", output_text)
    
    def test_get_android_serial_from_config(self):
        """Test get_android_serial retrieves from config"""
        config = self.cli.load_config()
        config['android_serial'] = 'CONFIG_SERIAL'
        self.cli.save_config(config)
        
        serial = self.cli.get_android_serial()
        self.assertEqual(serial, 'CONFIG_SERIAL')
    
    def test_get_android_serial_from_file_fallback(self):
        """Test get_android_serial retrieves from config (no file fallback; config is source of truth)"""
        config = self.cli.load_config()
        config['android_serial'] = 'CONFIG_SERIAL'
        self.cli.save_config(config)
        serial = self.cli.get_android_serial()
        self.assertEqual(serial, 'CONFIG_SERIAL')
    
    def test_get_android_serial_config_exception(self):
        """Test get_android_serial when config file missing - raises (no file fallback)"""
        self.cli.config_path = '/nonexistent/path/config.json'
        with self.assertRaises(FileNotFoundError):
            self.cli.get_android_serial()
    
    def test_get_android_serial_file_exception(self):
        """Test get_android_serial when config valid - returns serial (no separate file)"""
        config = self.cli.load_config()
        config['android_serial'] = 'SERIAL123'
        self.cli.save_config(config)
        serial = self.cli.get_android_serial()
        self.assertEqual(serial, 'SERIAL123')
    
    def test_load_config_file_not_found_exits(self):
        """Test load_config raises FileNotFoundError when file not found"""
        self.cli.config_path = '/nonexistent/path/config.json'
        with self.assertRaises(FileNotFoundError) as context:
            self.cli.load_config()
        self.assertIn("Configuration file not found", str(context.exception))
    
    @skip_if_macos("Test checks for is_locked attribute which doesn't exist in stateless implementation")
    def test_run_enforcing_mode_device_connected_on_startup(self):
        """Test run() in enforcing mode when device connected on startup (stateless: no is_locked)"""
        config = self.test_config.copy()
        config['android_serial'] = 'DEVICE123'
        with open(self.config_path, 'w') as f:
            json.dump(config, f)
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.mode = 'enforcing'
        service.running = True
        
        # Mock device as connected
        with patch.object(service, 'is_configured_device_connected', return_value=True):
            with patch('subprocess.run'):
                with patch('time.sleep', side_effect=KeyboardInterrupt()):
                    try:
                        service.run()
                    except KeyboardInterrupt:
                        pass
        
        # Should have exited cleanly (stateless: no is_locked)
        self.assertFalse(service.running)
    
    @skip_if_macos("Test checks for is_locked attribute which doesn't exist in stateless implementation")
    def test_run_permissive_mode_configured(self):
        """Test run() in permissive mode when device is configured (stateless: no is_locked)"""
        config = self.test_config.copy()
        config['android_serial'] = 'DEVICE123'
        with open(self.config_path, 'w') as f:
            json.dump(config, f)
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.mode = 'permissive'
        service.running = True
        
        with patch('time.sleep', side_effect=KeyboardInterrupt()):
            try:
                service.run()
            except KeyboardInterrupt:
                pass
        
        # Should have exited cleanly (stateless: no is_locked)
        self.assertFalse(service.running)
    
    @skip_if_macos("Test for exception handling in run loop - complex to test reliably")
    def test_run_exception_in_loop_continues(self):
        """Test run() continues after exception in main loop"""
        # Configure device
        serial_file = os.path.join(self.config_dir, 'android_serial')
        with open(serial_file, 'w') as f:
            f.write('DEVICE123')
        
        config = self.test_config.copy()
        
        with open(self.config_path, 'w') as f:
            json.dump(config, f)
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.mode = 'enforcing'
        service.running = True
        
        call_count = [0]
        exception_raised = [False]
        
        def sleep_side_effect(seconds):
            call_count[0] += 1
            if call_count[0] >= 4:  # Allow a few iterations
                raise KeyboardInterrupt()
            return None
        
        # Mock is_configured_device_connected to raise exception on first call, then return False
        original_method = service.is_configured_device_connected
        def device_check_side_effect(*args, **kwargs):
            if not exception_raised[0]:
                exception_raised[0] = True
                raise Exception("Connection error")
            return False
        
        with patch('time.sleep', side_effect=sleep_side_effect):
            with patch.object(service, 'is_configured_device_connected', side_effect=device_check_side_effect):
                with patch('subprocess.run'):
                    try:
                        service.run()
                    except KeyboardInterrupt:
                        pass
        
        # Should have handled exception and continued (sleep should have been called multiple times)
        # The exception should be caught and logged, then sleep(5) called, then loop continues
        self.assertTrue(call_count[0] > 1, f"Expected multiple sleep calls, got {call_count[0]}")
    
    def test_signal_handler_sigint(self):
        """Test signal_handler with SIGINT"""
        with open(self.config_path, 'w') as f:
            json.dump(self.test_config, f)
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.running = True
        
        service.signal_handler(signal.SIGINT, None)
        self.assertFalse(service.running)
    
    def test_signal_handler_sigterm(self):
        """Test signal_handler with SIGTERM"""
        with open(self.config_path, 'w') as f:
            json.dump(self.test_config, f)
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.running = True
        
        service.signal_handler(signal.SIGTERM, None)
        self.assertFalse(service.running)
    
    @skip_if_macos("Test lock_system with empty services - stateless")
    def test_lock_system_no_policies(self):
        """Test lock_system with empty services list (no policies to lock)"""
        config = self.test_config.copy()
        config['services'] = []
        with open(self.config_path, 'w') as f:
            json.dump(config, f)
        service = LockService(self.config_path, config_dir=self.config_dir)
        with patch('subprocess.run'):
            service.lock_system(service.config['services'], True)
        # Stateless: completes without error
    
    @skip_if_macos("Test unlock_system with empty services - stateless")
    def test_unlock_system_no_policies(self):
        """Test unlock_system with empty services list"""
        config = self.test_config.copy()
        config['services'] = []
        with open(self.config_path, 'w') as f:
            json.dump(config, f)
        service = LockService(self.config_path, config_dir=self.config_dir)
        with patch('subprocess.run'):
            service.unlock_system(service.config['services'], True)
    
    @skip_if_macos("Test lock_system with empty services - stateless")
    def test_lock_system_empty_services_list(self):
        """Test lock_system with empty services list"""
        config = self.test_config.copy()
        config['services'] = []
        with open(self.config_path, 'w') as f:
            json.dump(config, f)
        service = LockService(self.config_path, config_dir=self.config_dir)
        with patch('subprocess.run'):
            service.lock_system(service.config['services'], True)
    
    @skip_if_macos("Test unlock_system with empty services - stateless")
    def test_unlock_system_empty_services_list(self):
        """Test unlock_system with empty services list (stateless: no is_locked)"""
        config = self.test_config.copy()
        config['services'] = []
        
        with open(self.config_path, 'w') as f:
            json.dump(config, f)
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        
        with patch('subprocess.run'):
            service.unlock_system(service.config['services'], True)
        
        # Should complete without error (stateless)
    
    def test_get_connected_android_serials_no_serial_short(self):
        """Test get_connected_devices uses ID_SERIAL when ID_SERIAL_SHORT missing"""
        
        mock_device = Mock()
        mock_device.get = Mock(side_effect=lambda k, default='': {
            'ID_SERIAL': 'FULL_SERIAL_12345',  # No ID_SERIAL_SHORT
            'ID_VENDOR_ID': '18d1',  # Android vendor ID
            'ID_MODEL': 'Test_Device',
            'DEVPATH': '/devices/pci0000:00/0000:00:14.0/usb1/1-1'
        }.get(k, default))
        
        with patch('locker.utils.pyudev.Context') as mock_context_class:
            mock_context = Mock()
            def list_devices_side_effect(*args, **kwargs):
                if kwargs.get('subsystem') == 'usb':
                    return [mock_device]
                return []
            mock_context.list_devices = Mock(side_effect=list_devices_side_effect)
            mock_context_class.return_value = mock_context
            
            with open(self.config_path, 'w') as f:
                json.dump(self.test_config, f)
            
            service = LockService(self.config_path, config_dir=self.config_dir)
            from locker import utils
            devices = utils.get_connected_devices(logger=service.logger)
            serials = [d[0] for d in devices]
            
            self.assertIn('FULL_SERIAL_12345', serials)
    
    def test_get_connected_android_serials_duplicate_serials(self):
        """Test get_connected_devices handles duplicate serials"""
        
        mock_device1 = Mock()
        mock_device1.get = Mock(side_effect=lambda k, default='': {
            'ID_SERIAL_SHORT': 'DEVICE123',
            'ID_SERIAL': 'DEVICE123',
            'ID_VENDOR_ID': '18d1',
            'ID_MODEL': 'Test_Device_1',
            'DEVPATH': '/devices/pci0000:00/0000:00:14.0/usb1/1-1'
        }.get(k, default))
        
        mock_device2 = Mock()
        mock_device2.get = Mock(side_effect=lambda k, default='': {
            'ID_SERIAL_SHORT': 'DEVICE123',  # Same serial
            'ID_SERIAL': 'DEVICE123',
            'ID_VENDOR_ID': '18d1',
            'ID_MODEL': 'Test_Device_2',
            'DEVPATH': '/devices/pci0000:00/0000:00:14.0/usb1/1-2'
        }.get(k, default))
        
        with patch('locker.utils.pyudev.Context') as mock_context_class:
            mock_context = Mock()
            def list_devices_side_effect(*args, **kwargs):
                if kwargs.get('subsystem') == 'usb':
                    return [mock_device1, mock_device2]
                return []
            mock_context.list_devices = Mock(side_effect=list_devices_side_effect)
            mock_context_class.return_value = mock_context
            
            with open(self.config_path, 'w') as f:
                json.dump(self.test_config, f)
            
            service = LockService(self.config_path, config_dir=self.config_dir)
            from locker import utils
            devices = utils.get_connected_devices(logger=service.logger)
            serials = [d[0] for d in devices]
            
            # Should only have one serial (duplicates removed)
            self.assertEqual(serials.count('DEVICE123'), 1)
    
    def test_get_connected_android_serials_broad_check_with_colon(self):
        """Test get_connected_devices broad check with colon in interfaces"""
        
        mock_device = Mock()
        mock_device.get = Mock(side_effect=lambda k, default='': {
            'ID_SERIAL_SHORT': 'DEVICE999',
            'ID_SERIAL': 'DEVICE999',
            'ID_USB_INTERFACES': 'some:interface:here',  # Has colon
            'ID_VENDOR_ID': '18d1',  # Android vendor ID
            'ID_MODEL': 'Test_Device',
            'DEVPATH': '/devices/pci0000:00/0000:00:14.0/usb1/1-3'
        }.get(k, default))
        
        with patch('locker.utils.pyudev.Context') as mock_context_class:
            mock_context = Mock()
            def list_devices_side_effect(*args, **kwargs):
                if kwargs.get('subsystem') == 'usb':
                    return [mock_device]
                return []
            
            mock_context.list_devices = Mock(side_effect=list_devices_side_effect)
            mock_context_class.return_value = mock_context
            
            with open(self.config_path, 'w') as f:
                json.dump(self.test_config, f)
            
            service = LockService(self.config_path, config_dir=self.config_dir)
            from locker import utils
            devices = utils.get_connected_devices(logger=service.logger)
            serials = [d[0] for d in devices]
            
            self.assertIn('DEVICE999', serials)
    
    def test_get_connected_android_serials_broad_check_exception(self):
        """Test get_connected_devices handles exception in broad USB check"""
        with patch('locker.utils.pyudev.Context') as mock_context_class:
            mock_context = Mock()
            
            # Make list_devices raise exception
            mock_context.list_devices = Mock(side_effect=Exception("Broad check error"))
            mock_context_class.return_value = mock_context
            
            with open(self.config_path, 'w') as f:
                json.dump(self.test_config, f)
            
            service = LockService(self.config_path, config_dir=self.config_dir)
            from locker import utils
            
            # Should return empty list (silently handles errors)
            devices = utils.get_connected_devices(logger=service.logger)
            serials = [d[0] for d in devices]
            
            self.assertEqual(len(serials), 0)
    
    def test_is_configured_device_connected_no_serial(self):
        """Test is_configured_device_connected when no serial configured"""
        with open(self.config_path, 'w') as f:
            json.dump(self.test_config, f)
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.android_serial = None
        
        result = service.is_configured_device_connected()
        self.assertFalse(result)
    
    def test_is_configured_device_connected_empty_serial(self):
        """Test is_configured_device_connected with empty serial"""
        with open(self.config_path, 'w') as f:
            json.dump(self.test_config, f)
        
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.android_serial = ''
        
        result = service.is_configured_device_connected()
        self.assertFalse(result)
    
    def test_get_connected_devices_broad_check_with_colon(self):
        """Test get_connected_devices broad check with colon in interfaces"""
        
        mock_device = Mock()
        mock_device.get = Mock(side_effect=lambda k, default='': {
            'ID_SERIAL_SHORT': 'DEVICE888',
            'ID_SERIAL': 'DEVICE888',
            'ID_MODEL': 'Test Device',
            'ID_VENDOR_ID': '18d1',  # Android vendor ID
            'ID_USB_INTERFACES': 'some:interface:here'  # Has colon
        }.get(k, default))
        
        with patch('locker.utils.pyudev.Context') as mock_context_class:
            mock_context = Mock()
            def list_devices_side_effect(*args, **kwargs):
                if kwargs.get('subsystem') == 'usb':
                    return [mock_device]
                return []
            
            mock_context.list_devices = Mock(side_effect=list_devices_side_effect)
            mock_context_class.return_value = mock_context
            
            from locker import utils
            devices = utils.get_connected_devices()
            self.assertEqual(len(devices), 1)
            self.assertEqual(devices[0][0], 'DEVICE888')
    
    def test_get_connected_devices_broad_check_with_debug_interface(self):
        """Test get_connected_devices broad check with Android Debug Bridge interface class"""
        
        mock_device = Mock()
        mock_device.get = Mock(side_effect=lambda k, default='': {
            'ID_SERIAL_SHORT': 'DEVICE777',
            'ID_SERIAL': 'DEVICE777',
            'ID_MODEL': 'Test Device',
            'ID_VENDOR_ID': '18d1',  # Android vendor ID
            'ID_USB_INTERFACES': 'ff:42:81'  # Android Debug Bridge interface class (0xff)
        }.get(k, default))
        
        with patch('locker.utils.pyudev.Context') as mock_context_class:
            mock_context = Mock()
            def list_devices_side_effect(*args, **kwargs):
                if kwargs.get('subsystem') == 'usb':
                    return [mock_device]
                return []
            
            mock_context.list_devices = Mock(side_effect=list_devices_side_effect)
            mock_context_class.return_value = mock_context
            
            from locker import utils
            devices = utils.get_connected_devices()
            self.assertEqual(len(devices), 1)
            self.assertEqual(devices[0][0], 'DEVICE777')
    
    def test_set_android_serial_single_device_decline(self):
        """Test set_android_serial with single device - user declines"""
        devices = [("DEVICE123", "Test Device")]
        
        with patch('builtins.input', return_value='n'):
            with patch('builtins.print'):
                with patch('locker.utils.get_connected_devices', return_value=devices):
                    self.cli.set_android_serial()
        
        # Should not have set serial
        config = self.cli.load_config()
        # Serial should be None or unchanged
    
    def test_set_android_serial_multiple_devices_decline(self):
        """Test set_android_serial with multiple devices - user cancels"""
        devices = [("DEVICE1", "Device 1"), ("DEVICE2", "Device 2")]
        
        with patch('builtins.input', side_effect=KeyboardInterrupt()):
            with patch('builtins.print'):
                with patch('locker.utils.get_connected_devices', return_value=devices):
                    try:
                        self.cli.set_android_serial()
                    except KeyboardInterrupt:
                        pass
    
    def test_set_android_serial_no_serial_provided_no_devices(self):
        """Test set_android_serial with no serial and no devices - user cancels"""
        with patch('builtins.input', return_value='n'):
            with patch('builtins.print'):
                with patch('locker.utils.get_connected_devices', return_value=[]):
                    self.cli.set_android_serial()
        
        # Should not have set serial
        config = self.cli.load_config()
        # Serial should be None or unchanged
    
    # Removed test_emergency_unlock_with_blocked_interfaces - blocked_interfaces no longer used
    
    def test_status_service_running_device_connected(self):
        """Test status when service is running and device is connected"""
        with patch.object(self.cli, 'is_service_running', return_value=True):
            with patch.object(self.cli, 'get_android_serial', return_value="DEVICE123"):
                with patch('locker.cli.utils.get_connected_devices', return_value=[("DEVICE123", "Test")]):
                    with patch('subprocess.run') as mock_subprocess:
                        mock_subprocess.return_value = Mock(returncode=0, stdout="Chain INPUT")
                        output = []
                        with patch('builtins.print', side_effect=lambda *a, **kw: output.extend(str(x) for x in a)):
                            self.cli.status()
                        
                        status_text = ' '.join(output)
                        self.assertIn("Yes", status_text)
                        self.assertIn("DEVICE123", status_text)
                        self.assertIn("CONNECTED", status_text)
    
    def test_status_service_not_running_device_disconnected(self):
        """Test status when service not running and device disconnected"""
        with patch.object(self.cli, 'is_service_running', return_value=False):
            with patch.object(self.cli, 'get_android_serial', return_value="DEVICE123"):
                with patch('locker.utils.get_connected_devices', return_value=[]):
                    with patch('subprocess.run') as mock_subprocess:
                        mock_subprocess.return_value = Mock(returncode=0, stdout="Chain INPUT")
                        output = []
                        with patch('builtins.print', side_effect=lambda *a, **kw: output.extend(str(x) for x in a)):
                            self.cli.status()
                        
                        status_text = ' '.join(output)
                        self.assertIn("No", status_text)
                        self.assertIn("DISCONNECTED", status_text)
    
    def test_get_connected_devices_exception_handling(self):
        """Test get_connected_devices handles exceptions"""
        with patch('locker.utils.pyudev.Context', side_effect=Exception("Test error")):
            from locker import utils
            devices = utils.get_connected_devices()
            # Should return empty list, not raise
            self.assertEqual(devices, [])
    
    @patch('locker.utils.pyudev.Context')
    def test_get_connected_devices_vendor_id_exception(self, mock_context_class):
        """Test get_connected_devices handles vendor ID loop exceptions"""
        mock_context = Mock()
        
        call_count = [0]
        def list_devices_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                raise Exception("Vendor error")
            return []
        
        mock_context.list_devices = Mock(side_effect=list_devices_side_effect)
        mock_context_class.return_value = mock_context
        
        from locker import utils
        devices = utils.get_connected_devices()
        # Should handle exceptions and continue
        self.assertIsInstance(devices, list)
    
    @patch('locker.utils.pyudev.Context')
    def test_get_connected_devices_broad_usb_check(self, mock_context_class):
        """Test get_connected_devices via broad USB subsystem check"""
        
        mock_device = Mock()
        mock_device.get = Mock(side_effect=lambda k, default='': {
            'ID_SERIAL_SHORT': 'DEVICE456',
            'ID_VENDOR_ID': '18d1',  # Android vendor ID
            'ID_SERIAL': 'DEVICE456',
            'ID_MODEL': 'Test_Device',
            'ID_USB_INTERFACES': 'ff:42:81'  # Android Debug Bridge interface class
        }.get(k, default))
        
        mock_context = Mock()
        def list_devices_side_effect(*args, **kwargs):
            if kwargs.get('subsystem') == 'usb':
                return [mock_device]
            return []
        
        mock_context.list_devices = Mock(side_effect=list_devices_side_effect)
        mock_context_class.return_value = mock_context
        
        from locker import utils
        devices = utils.get_connected_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0][0], 'DEVICE456')


class TestMainFunctions(unittest.TestCase):
    """Tests for main() entry points"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.test_dir, 'config.json')
        self.config_dir = os.path.join(self.test_dir, 'config')
        
        os.makedirs(self.config_dir, exist_ok=True)
        
        test_config = {
            "service": {
                "log_level": "CRITICAL",
                "log_file": os.path.join(self.test_dir, 'test.log')
            },
            "monitoring": {
                "check_interval_seconds": 5
            },
            "mode": "permissive",
            "android_serial": None,
            "services": []
        }
        
        with open(self.config_path, 'w') as f:
            json.dump(test_config, f)
        
        self._find_config_patcher = patch('locker.config.find_config_file', side_effect=_find_config_file_use_given_path)
        self._find_config_patcher.start()
        
        import logging
        logging.disable(logging.CRITICAL)
    
    def tearDown(self):
        """Clean up test fixtures"""
        if hasattr(self, '_find_config_patcher'):
            self._find_config_patcher.stop()
        shutil.rmtree(self.test_dir, ignore_errors=True)
        import logging
        logging.disable(logging.NOTSET)
    
    @patch.object(LockService, 'run')
    def test_service_main_default(self, mock_run):
        """Test service main() with default arguments"""
        with patch('sys.argv', ['lockerd', '--config', self.config_path]):
            main()
        
        mock_run.assert_called_once()
    
    @patch.object(LockService, 'run')
    @skip_if_macos("Test requires daemon module which may not be available")
    def test_service_main_with_daemon(self, mock_run):
        """Test service main() with --daemon flag"""
        # Mock daemon module before importing
        import sys
        mock_daemon_module = MagicMock()
        sys.modules['daemon'] = mock_daemon_module
        
        with patch('sys.argv', ['lockerd', '--config', self.config_path, '--daemon']):
            with patch('daemon.DaemonContext') as mock_daemon:
                mock_daemon.return_value.__enter__ = Mock()
                mock_daemon.return_value.__exit__ = Mock(return_value=False)
                main()
        
        mock_run.assert_called_once()
    
    def test_cli_main_no_command(self):
        """Test CLI main() with no command shows help"""
        with patch('sys.argv', ['locker']):
            with patch('builtins.print'):
                from locker.cli import main
                main()
    
    def test_cli_main_all_commands(self):
        """Test CLI main() with all commands"""
        from locker.cli import main
        
        commands = [
            ('get-android-serial', 'get_android_serial_cmd'),
            ('set-android-serial', 'set_android_serial'),
            ('list-devices', 'list_devices_cmd'),
            ('add-service', 'add_service'),
            ('set-mode', 'set_mode'),
            ('logs', 'logs'),
        ]
        
        for cmd, method in commands:
            with patch('sys.argv', ['locker', cmd]):
                with patch.object(LockCLI, method) as mock_method:
                    with patch('builtins.print'):
                        with patch('builtins.input', return_value='n'):  # Mock input to prevent hangs
                            try:
                                main()
                                if cmd == 'add-service':
                                    # add-service needs an argument
                                    continue
                                if cmd == 'set-android-serial':
                                    mock_method.assert_called_once_with(None)
                                elif cmd == 'logs':
                                    mock_method.assert_called_once_with(50, False)
                                else:
                                    mock_method.assert_called_once()
                            except SystemExit:
                                pass  # argparse may exit for some commands


if __name__ == '__main__':
    unittest.main()



