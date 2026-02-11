#!/usr/bin/env python3
"""
Utility functions for the locker service
"""

import os
import json
import subprocess
import logging
from typing import List, Optional, Tuple
import pyudev


# Android vendor IDs for device detection
ANDROID_VENDOR_IDS = ['2717', '18d1', '0bb4', '04e8', '24e3', '0955', '201e', '0e79', '04c5', '2a47']

# Connected serials file path
CONNECTED_SERIALS_FILE = "connect_android_serials.json"
CONNECTED_SERIALS_DIR = "/etc/locker"


def get_mock_device(config_dir: Optional[str] = None, logger: Optional[logging.Logger] = None) -> Optional[Tuple[str, str]]:
    """Read the connected serials file and return the mock device if present.
    
    If /etc/locker/connect_android_serials.json exists, is valid JSON,
    and contains an 'android_serial' key with a non-empty value,
    returns (serial, 'Mock Device'). Otherwise returns None.
    
    Args:
        config_dir: Directory containing the file (default: /etc/locker)
        logger: Optional logger
    
    Returns:
        Tuple of (serial, model) or None
    """
    directory = config_dir or CONNECTED_SERIALS_DIR
    mock_path = os.path.join(directory, CONNECTED_SERIALS_FILE)
    
    try:
        if not os.path.exists(mock_path):
            return None
        
        with open(mock_path, 'r') as f:
            data = json.load(f)
        
        serial = data.get('android_serial')
        if serial and isinstance(serial, str) and serial.strip():
            return (serial.strip(), 'Mock Device')
        return None
    except (json.JSONDecodeError, OSError, TypeError) as e:
        if logger:
            logger.debug(f"Mock device file check failed: {e}")
        return None


def is_service_running(service_name: str, logger: Optional[logging.Logger] = None, log_check: bool = False) -> bool:
    """Check if a systemd service is currently running"""
    result = subprocess.run(
        ['systemctl', 'is-active', '--quiet', service_name],
        capture_output=True,
        timeout=2
    )
    is_running = result.returncode == 0
    if log_check and logger:
        logger.info(f"Service {service_name} status: {'RUNNING' if is_running else 'STOPPED'}")
    return is_running


def stop_service(service_name: str, logger: Optional[logging.Logger] = None) -> bool:
    """Stop a systemd service and validate it's actually stopped
    
    Args:
        service_name: Name of the service to stop
        logger: Optional logger for logging actions and errors
    
    Returns:
        True if service was successfully stopped, False otherwise
    """
    result = subprocess.run(
        ['systemctl', 'stop', service_name],
        check=False,
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if result.returncode == 0:
        # Validate service is actually stopped
        if not is_service_running(service_name, logger=logger):
            if logger:
                logger.info(f"Service {service_name} stopped successfully")
            return True
        else:
            if logger:
                logger.error(f"Service {service_name} failed to stop - still running after stop command")
            return False
    else:
        if logger:
            logger.error(f"Failed to stop service {service_name}: {result.stderr}")
        return False


def start_service(service_name: str, logger: Optional[logging.Logger] = None) -> bool:
    """Start a systemd service and validate it's actually running
    
    Args:
        service_name: Name of the service to start
        logger: Optional logger for logging actions and errors
    
    Returns:
        True if service was successfully started, False otherwise
    """
    result = subprocess.run(
        ['systemctl', 'start', service_name],
        check=False,
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if result.returncode == 0:
        # Validate service is actually running
        if is_service_running(service_name, logger=logger):
            if logger:
                logger.info(f"Service {service_name} started successfully")
            return True
        else:
            if logger:
                logger.error(f"Service {service_name} failed to start - still stopped after start command")
            return False
    else:
        if logger:
            logger.error(f"Failed to start service {service_name}: {result.stderr}")
        return False


def get_connected_devices(logger: Optional[logging.Logger] = None, config_dir: Optional[str] = None) -> List[tuple]:
    """Get list of connected Android devices (serial, model) using pyudev.
    
    Also checks for a mock device file at /etc/locker/connect_android_serials.json.
    If the file exists and has a valid serial, it is included in the results.
    
    Args:
        logger: Optional logger for logging errors
        config_dir: Directory containing the mock device file (default: /etc/locker)
    
    Returns:
        List of tuples containing (serial, model) for each connected Android device
    """
    devices = []
    seen_serials = set()

    try:
        context = pyudev.Context()
    except Exception as e:
        if logger:
            logger.warning(f"Failed to create pyudev context: {e}")
        # Don't return yet — still check the mock file below
        context = None

    if context is not None:
        try:
            device_list = context.list_devices(subsystem='usb')
        except Exception as e:
            if logger:
                logger.warning(f"Failed to list USB devices: {e}")
            device_list = []

        for device in device_list:
            interfaces = device.get('ID_USB_INTERFACES', '')
            vendor_id = device.get('ID_VENDOR_ID', '').lower()
            serial = device.get('ID_SERIAL_SHORT') or device.get('ID_SERIAL')
            
            # Skip devices without serials
            if not serial:
                continue
            
            # Check if this looks like an Android device
            is_android = False
            
            # Method 1: Check vendor ID (most reliable)
            if vendor_id in ANDROID_VENDOR_IDS:
                is_android = True
            
            # Method 2: Check for Android Debug Bridge interface class (0xff)
            if not is_android and ':' in interfaces:
                interface_parts = interfaces.split(':')
                if len(interface_parts) >= 1:
                    interface_class = interface_parts[0]
                    if interface_class.lower() == 'ff' or interface_class == '255':
                        if len(serial) >= 8 and serial.replace('_', '').replace('-', '').isalnum():
                            is_android = True
            
            if is_android:
                if serial not in seen_serials:
                    if len(serial) >= 8 and serial.replace('_', '').replace('-', '').isalnum():
                        if ':' not in serial or not serial.startswith('0000:'):
                            model = device.get('ID_MODEL', 'Unknown')
                            model = model.replace('_', ' ').title()
                            devices.append((serial, model))
                            seen_serials.add(serial)

    # Also check the mock device file
    mock_device = get_mock_device(config_dir=config_dir, logger=logger)
    if mock_device and mock_device[0] not in seen_serials:
        devices.append(mock_device)
        seen_serials.add(mock_device[0])

    return devices

