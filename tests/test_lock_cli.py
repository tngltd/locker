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

# Add src directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.join(parent_dir, "src")
sys.path.insert(0, src_dir)

# Import from package
from locker.cli import LockCLI, main


class TestLockCLI(unittest.TestCase):
    """Test cases for LockCLI"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.test_dir, 'config.json')
        self.config_dir = os.path.join(self.test_dir, 'config')
        self.pid_file = os.path.join(self.test_dir, 'locker.pid')
        self.log_file = os.path.join(self.test_dir, 'locker.log')
        
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Create test config
        test_config = {
            "service": {
                "name": "locker",
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
        self.cli.config_dir = self.config_dir
        self.cli.service_pid_file = self.pid_file
    
    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_get_android_serial_existing(self):
        """Test getting existing Android serial"""
        serial_file = os.path.join(self.config_dir, 'android_serial')
        with open(serial_file, 'w') as f:
            f.write("DEVICE123456")
        
        serial = self.cli.get_android_serial()
        self.assertEqual(serial, "DEVICE123456")
    
    def test_get_android_serial_not_found(self):
        """Test getting Android serial when file doesn't exist"""
        serial = self.cli.get_android_serial()
        self.assertIsNone(serial)
    
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
    
    def test_status_no_device_configured(self):
        """Test status when no device is configured"""
        with patch.object(self.cli, 'is_service_running', return_value=False):
            with patch.object(self.cli, 'get_android_serial', return_value=None):
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
                self.assertIn("Service running: No", status_text)
                self.assertIn("Not configured", status_text)
    
    def test_status_with_device_configured(self):
        """Test status when device is configured"""
        with patch.object(self.cli, 'is_service_running', return_value=True):
            with patch.object(self.cli, 'get_android_serial', return_value="DEVICE123"):
                with patch.object(self.cli, 'get_connected_devices', return_value=[("DEVICE123", "Test Device")]):
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
                    self.assertIn("DEVICE123", status_text)
                    self.assertIn("CONNECTED", status_text)
    
    @patch('builtins.input')
    def test_setup_new_config(self, mock_input):
        """Test setup with new configuration - select device from list"""
        mock_input.side_effect = ["1", "n"]  # Select first device, don't reconfigure
        
        with patch.object(self.cli, 'get_connected_devices', return_value=[("DEVICE123", "Test Device")]):
            with patch.object(self.cli, 'save_android_serial') as mock_save:
                self.cli.setup()
                mock_save.assert_called_once_with("DEVICE123")
    
    
    
    @patch('builtins.input')
    def test_emergency_unlock_success(self, mock_input):
        """Test emergency unlock - manual unlock without device"""
        mock_input.return_value = "yes"
        
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = Mock(returncode=0)
            with patch.object(self.cli, 'load_config', return_value={'network': {'blocked_interfaces': ['eth0']}}):
                output = []
                def mock_print(*args, **kwargs):
                    output.append(' '.join(str(a) for a in args))
                
                with patch('builtins.print', side_effect=mock_print):
                    self.cli.emergency_unlock()
                
                output_text = ' '.join(output)
                self.assertIn("unlocked successfully", output_text.lower())
    
    @patch('builtins.input')
    def test_emergency_unlock_cancelled(self, mock_input):
        """Test emergency unlock when user cancels"""
        mock_input.return_value = "no"
        
        output = []
        def mock_print(*args, **kwargs):
            output.append(' '.join(str(a) for a in args))
        
        with patch('builtins.print', side_effect=mock_print):
            self.cli.emergency_unlock()
        
        output_text = ' '.join(output)
        self.assertIn("Cancelled", output_text)
    
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


class TestLockCLIEdgeCases(unittest.TestCase):
    """Test edge cases for LockCLI"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.test_dir, 'config.json')
        self.config_dir = os.path.join(self.test_dir, 'config')
        self.pid_file = os.path.join(self.test_dir, 'locker.pid')
        self.log_file = os.path.join(self.test_dir, 'locker.log')
        
        os.makedirs(self.config_dir, exist_ok=True)
        
        test_config = {
            "service": {
                "name": "locker",
                "log_file": self.log_file
            },
            "network": {
                "blocked_interfaces": ["eth0", "wlan0"]
            }
        }
        
        with open(self.config_path, 'w') as f:
            json.dump(test_config, f)
        
        self.cli = LockCLI()
        self.cli.config_path = self.config_path
        self.cli.config_dir = self.config_dir
        self.cli.service_pid_file = self.pid_file
    
    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch('subprocess.run')
    def test_start_service_called_process_error(self, mock_subprocess):
        """Test start_service when subprocess fails"""
        import subprocess
        mock_subprocess.side_effect = subprocess.CalledProcessError(1, 'systemctl')
        
        with patch.object(self.cli, 'is_service_running', return_value=False):
            output = []
            with patch('builtins.print', side_effect=lambda *a, **kw: output.append(' '.join(str(x) for x in a))):
                self.cli.start_service()
            
            self.assertTrue(any('Failed to start' in o for o in output))

    @patch('subprocess.run')
    def test_start_service_file_not_found(self, mock_subprocess):
        """Test start_service when systemctl not found"""
        mock_subprocess.side_effect = FileNotFoundError()
        
        with patch.object(self.cli, 'is_service_running', return_value=False):
            output = []
            with patch('builtins.print', side_effect=lambda *a, **kw: output.append(' '.join(str(x) for x in a))):
                self.cli.start_service()
            
            self.assertTrue(any('systemctl not found' in o for o in output))

    @patch('subprocess.run')
    def test_stop_service_called_process_error(self, mock_subprocess):
        """Test stop_service when subprocess fails"""
        import subprocess
        mock_subprocess.side_effect = subprocess.CalledProcessError(1, 'systemctl')
        
        with patch.object(self.cli, 'is_service_running', return_value=True):
            output = []
            with patch('builtins.print', side_effect=lambda *a, **kw: output.append(' '.join(str(x) for x in a))):
                self.cli.stop_service()
            
            self.assertTrue(any('Failed to stop' in o for o in output))

    @patch('subprocess.run')
    def test_stop_service_file_not_found(self, mock_subprocess):
        """Test stop_service when systemctl not found"""
        mock_subprocess.side_effect = FileNotFoundError()
        
        with patch.object(self.cli, 'is_service_running', return_value=True):
            output = []
            with patch('builtins.print', side_effect=lambda *a, **kw: output.append(' '.join(str(x) for x in a))):
                self.cli.stop_service()
            
            self.assertTrue(any('systemctl not found' in o for o in output))

    @patch('time.sleep')
    def test_restart_service(self, mock_sleep):
        """Test restart_service calls stop and start"""
        with patch.object(self.cli, 'stop_service') as mock_stop:
            with patch.object(self.cli, 'start_service') as mock_start:
                self.cli.restart_service()
                
                mock_stop.assert_called_once()
                mock_start.assert_called_once()

    def test_status_with_iptables_drop(self):
        """Test status shows LOCKED when iptables has DROP"""
        with patch.object(self.cli, 'is_service_running', return_value=True):
            with patch.object(self.cli, 'get_android_serial', return_value="DEVICE123"):
                with patch.object(self.cli, 'get_connected_devices', return_value=[]):
                    output = []
                    with patch('builtins.print', side_effect=lambda *a, **kw: output.append(' '.join(str(x) for x in a))):
                        with patch('subprocess.run') as mock_subprocess:
                            mock_subprocess.return_value = Mock(returncode=0, stdout="DROP all")
                            self.cli.status()
                    
                    status_text = ' '.join(output)
                    self.assertIn("LOCKED", status_text)

    def test_status_iptables_exception(self):
        """Test status handles iptables exception"""
        with patch.object(self.cli, 'is_service_running', return_value=False):
            with patch.object(self.cli, 'get_android_serial', return_value=None):
                output = []
                with patch('builtins.print', side_effect=lambda *a, **kw: output.append(' '.join(str(x) for x in a))):
                    with patch('subprocess.run', side_effect=Exception()):
                        self.cli.status()
                
                status_text = ' '.join(output)
                self.assertIn("Unknown", status_text)

    @patch('builtins.input')
    def test_setup_reconfigure_declined(self, mock_input):
        """Test setup when user declines reconfigure"""
        serial_file = os.path.join(self.config_dir, 'android_serial')
        with open(serial_file, 'w') as f:
            f.write('EXISTING_DEVICE')
        
        mock_input.return_value = 'n'
        
        with patch.object(self.cli, 'get_connected_devices', return_value=[("NEW_DEVICE", "New Device")]):
            self.cli.setup()
        
        # Should not have changed the serial
        with open(serial_file, 'r') as f:
            self.assertEqual(f.read().strip(), 'EXISTING_DEVICE')

    @patch('builtins.input')
    @patch('subprocess.run')
    def test_emergency_unlock_exception(self, mock_subprocess, mock_input):
        """Test emergency_unlock handles exception"""
        mock_input.return_value = "yes"
        mock_subprocess.side_effect = Exception("Error")
        
        output = []
        with patch('builtins.print', side_effect=lambda *a, **kw: output.append(' '.join(str(x) for x in a))):
            with patch.object(self.cli, 'load_config', return_value={'network': {'blocked_interfaces': []}}):
                self.cli.emergency_unlock()
        
        self.assertTrue(any('Error' in o for o in output))

    def test_logs_load_config_exception(self):
        """Test logs when load_config raises exception"""
        self.cli.config_path = '/nonexistent/config.json'
        
        output = []
        with patch('builtins.print', side_effect=lambda *a, **kw: output.append(' '.join(str(x) for x in a))):
            self.cli.logs()
        
        self.assertTrue(any('No log file' in o for o in output))

    @patch('subprocess.run')
    def test_logs_tail_fallback(self, mock_subprocess):
        """Test logs falls back to reading file when tail fails"""
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        with open(self.log_file, 'w') as f:
            f.write("Log line 1\nLog line 2\nLog line 3\n")
        
        mock_subprocess.side_effect = FileNotFoundError()
        
        output = []
        with patch('builtins.print', side_effect=lambda *a, **kw: output.append(' '.join(str(x) for x in a))):
            with patch.object(self.cli, 'load_config', return_value={'service': {'log_file': self.log_file}}):
                self.cli.logs(2)
        
        self.assertTrue(any('Log line' in o for o in output))



class TestLockCLIMain(unittest.TestCase):
    """Test cases for main() function"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.test_dir, 'config.json')
        
        test_config = {
            "service": {"name": "locker", "log_file": "/tmp/test.log"},
            "network": {"blocked_interfaces": ["eth0"]}
        }
        
        with open(self.config_path, 'w') as f:
            json.dump(test_config, f)
    
    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_main_no_command(self):
        """Test main() with no command shows help"""
        with patch('sys.argv', ['locker']):
            main()
            # Should print help when no command provided

    def test_main_get_android_serial_command(self):
        """Test main() with get-android-serial command"""
        with patch('sys.argv', ['locker', 'get-android-serial']):
            with patch.object(LockCLI, 'get_android_serial_cmd') as mock_cmd:
                main()
                mock_cmd.assert_called_once()

    def test_main_set_android_serial_command(self):
        """Test main() with set-android-serial command"""
        with patch('sys.argv', ['locker', 'set-android-serial']):
            with patch.object(LockCLI, 'set_android_serial') as mock_set:
                main()
                mock_set.assert_called_once_with(None)

    def test_main_list_devices_command(self):
        """Test main() with list-devices command"""
        with patch('sys.argv', ['locker', 'list-devices']):
            with patch.object(LockCLI, 'list_devices') as mock_list:
                main()
                mock_list.assert_called_once()

    def test_main_add_service_command(self):
        """Test main() with add-service command"""
        with patch('sys.argv', ['locker', 'add-service', 'ssh']):
            with patch.object(LockCLI, 'add_service') as mock_add:
                main()
                mock_add.assert_called_once_with('ssh')

    def test_main_set_mode_command(self):
        """Test main() with set-mode command"""
        with patch('sys.argv', ['locker', 'set-mode', 'enforcing']):
            with patch.object(LockCLI, 'set_mode') as mock_set:
                main()
                mock_set.assert_called_once_with('enforcing')

    def test_main_logs_command(self):
        """Test main() with logs command"""
        with patch('sys.argv', ['locker', 'logs']):
            with patch.object(LockCLI, 'logs') as mock_logs:
                main()
                mock_logs.assert_called_once_with(50)

    def test_main_logs_command_with_lines(self):
        """Test main() with logs command and line count"""
        with patch('sys.argv', ['locker', 'logs', '-n', '100']):
            with patch.object(LockCLI, 'logs') as mock_logs:
                main()
                mock_logs.assert_called_once_with(100)


if __name__ == '__main__':
    unittest.main()

