#!/usr/bin/env python3
"""
Unit tests for Configuration System (KAN-13)
"""

import unittest
import os
import json
import tempfile
import shutil
from unittest.mock import patch, MagicMock
import sys

# Add src directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.join(parent_dir, "src")
sys.path.insert(0, src_dir)

# Mock pyudev before importing LockService
sys.modules['pyudev'] = MagicMock()

# Import from package
from locker.service import LockService


class TestConfigurationSystem(unittest.TestCase):
    """Test cases for Configuration System"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.test_dir, 'etc', 'locker')
        self.log_dir = os.path.join(self.test_dir, 'var', 'log')
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)

        self.config_path = os.path.join(self.config_dir, 'config.json')
        self.log_file = os.path.join(self.log_dir, 'locker.log')

        self.valid_config = {
            "service": {
                "log_level": "CRITICAL",  # Disable logging for tests
                "log_file": self.log_file
            },
            "monitoring": {
                "check_interval_seconds": 5
            }
        }

        import logging
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        shutil.rmtree(self.test_dir)
        import logging
        logging.disable(logging.NOTSET)

    @patch('signal.signal')
    def test_load_valid_config(self, mock_signal):
        """Test loading valid configuration"""
        with open(self.config_path, 'w') as f:
            json.dump(self.valid_config, f)

        service = LockService(self.config_path, config_dir=self.config_dir)
        # service.name is automatically added if missing
        self.assertEqual(service.config['service']['name'], 'locker')
        # Network section removed - no longer part of config
        self.assertIn('monitoring', service.config)
        self.assertEqual(service.config['service']['log_level'], 'CRITICAL')
        # Network section is optional, no validation needed
        self.assertEqual(service.config['monitoring']['check_interval_seconds'], 5)

    @patch('signal.signal')
    def test_load_config_missing_service_section(self, mock_signal):
        """Test loading config with missing service section"""
        invalid_config = self.valid_config.copy()
        del invalid_config['service']

        with open(self.config_path, 'w') as f:
            json.dump(invalid_config, f)

        with self.assertRaises(ValueError) as context:
            LockService(self.config_path, config_dir=self.config_dir)

        self.assertIn('service', str(context.exception))
        self.assertIn('Missing required config section', str(context.exception))

    # Removed test_load_config_missing_network_section - network section no longer exists

    @patch('signal.signal')
    def test_load_config_missing_monitoring_section(self, mock_signal):
        """Test loading config with missing monitoring section"""
        invalid_config = self.valid_config.copy()
        del invalid_config['monitoring']

        with open(self.config_path, 'w') as f:
            json.dump(invalid_config, f)

        with self.assertRaises(ValueError) as context:
            LockService(self.config_path, config_dir=self.config_dir)

        self.assertIn('monitoring', str(context.exception))
        self.assertIn('Missing required config section', str(context.exception))

    @patch('signal.signal')
    def test_load_config_missing_log_level(self, mock_signal):
        """Test loading config with missing log_level"""
        invalid_config = self.valid_config.copy()
        del invalid_config['service']['log_level']

        with open(self.config_path, 'w') as f:
            json.dump(invalid_config, f)

        with self.assertRaises(ValueError) as context:
            LockService(self.config_path, config_dir=self.config_dir)

        self.assertIn('log_level', str(context.exception))
        self.assertIn('Missing', str(context.exception))

    # Removed test_load_config_missing_blocked_interfaces - blocked_interfaces no longer required

    @patch('signal.signal')
    def test_load_config_missing_check_interval(self, mock_signal):
        """Test loading config with missing check_interval_seconds"""
        invalid_config = self.valid_config.copy()
        del invalid_config['monitoring']['check_interval_seconds']

        with open(self.config_path, 'w') as f:
            json.dump(invalid_config, f)

        with self.assertRaises(ValueError) as context:
            LockService(self.config_path, config_dir=self.config_dir)

        self.assertIn('check_interval_seconds', str(context.exception))
        self.assertIn('Missing', str(context.exception))

    @patch('signal.signal')
    def test_load_config_invalid_json(self, mock_signal):
        """Test loading config with invalid JSON"""
        with open(self.config_path, 'w') as f:
            f.write("{ invalid json }")

        with self.assertRaises(ValueError) as context:
            LockService(self.config_path, config_dir=self.config_dir)

        # The actual error message is "Invalid JSON in config file: ..."
        self.assertIn('Invalid JSON', str(context.exception))



if __name__ == '__main__':
    unittest.main()