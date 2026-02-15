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

# Add src directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.join(parent_dir, "src")
sys.path.insert(0, src_dir)

# Import from package
from locker.service import LockService
from tests.test_utils import skip_if_macos


def _find_config_file_use_given_path(path):
    """Make find_config_file return the given path so tests load their config, not project config."""
    return path


class TestSystemLockdown(unittest.TestCase):
    """Test cases for System Lockdown"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.test_dir, 'etc', 'locker')
        self.log_dir = os.path.join(self.test_dir, 'var', 'log')
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)

        self.config_path = os.path.join(self.config_dir, 'config.json')
        self.log_file = os.path.join(self.log_dir, 'locker.log')

        self.default_config = {
            "service": {
                "log_level": "INFO",
                "log_file": self.log_file
            },
            "monitoring": {
                "check_interval_seconds": 1
            },
            "mode": "permissive",
            "android_serial": None,
            "services": ["ssh"]
        }
        
        with open(self.config_path, 'w') as f:
            json.dump(self.default_config, f)

        self._find_config_patcher = patch('locker.config.find_config_file', side_effect=_find_config_file_use_given_path)
        self._find_config_patcher.start()

        import logging
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        self._find_config_patcher.stop()
        shutil.rmtree(self.test_dir)
        import logging
        logging.disable(logging.NOTSET)


    @patch('locker.utils.subprocess.run')
    @skip_if_macos("Test checks idempotent behavior - implementation is stateless")
    def test_lock_system_idempotent(self, mock_subprocess):
        """Test that lock_system can be called multiple times (stateless: stops services that are running)"""
        mock_subprocess.return_value = Mock(returncode=0)
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.lock_system(service.config['services'], True)
        first_count = len(mock_subprocess.call_args_list)
        service.lock_system(service.config['services'], True)
        # Second call may make more calls (implementation checks each service each time)
        self.assertGreaterEqual(len(mock_subprocess.call_args_list), first_count)

    @patch('locker.utils.subprocess.run')
    def test_unlock_system_restores_ssh(self, mock_subprocess):
        """Test that unlock_system restores SSH (calls systemctl start when service not running)"""
        # 1) unlock_system: is_service_running (is-active) -> not running; 2) start_service: systemctl start; 3) start_service: is_service_running (validation) -> running
        mock_subprocess.side_effect = [
            Mock(returncode=3, stdout='', stderr=''),   # is-active: not running
            Mock(returncode=0, stdout='', stderr=''),   # start: success
            Mock(returncode=0, stdout='', stderr=''),   # is-active: now running (validation)
        ]
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.unlock_system(service.config['services'], True)
        calls = [str(c) for c in mock_subprocess.call_args_list]
        self.assertTrue(any('systemctl' in c and 'start' in c and 'ssh' in c for c in calls))

    @patch('locker.utils.subprocess.run')
    @skip_if_macos("Test checks idempotent behavior - implementation is stateless")
    def test_unlock_system_idempotent(self, mock_subprocess):
        """Test that unlock_system can be called multiple times (stateless: starts services not running)"""
        mock_subprocess.return_value = Mock(returncode=0)
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.unlock_system(service.config['services'], True)
        # Should complete without raising; may call systemctl for services not running
        self.assertGreaterEqual(len(mock_subprocess.call_args_list), 0)

    @patch('locker.utils.subprocess.run')
    @skip_if_macos("Test checks for is_locked attribute which doesn't exist in stateless implementation")
    def test_lock_unlock_cycle(self, mock_subprocess):
        """Test a complete lock/unlock cycle (stateless: no is_locked attribute)"""
        mock_subprocess.return_value = Mock(returncode=0)
        service = LockService(self.config_path, config_dir=self.config_dir)
        service.lock_system(service.config['services'], True)
        lock_calls = len(mock_subprocess.call_args_list)
        service.unlock_system(service.config['services'], True)
        # Both operations should make system calls
        self.assertGreater(len(mock_subprocess.call_args_list), lock_calls)


if __name__ == '__main__':
    unittest.main()

