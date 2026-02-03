#!/usr/bin/env python3
"""
Utility functions for the locker service
"""

import subprocess
import logging
from typing import List, Optional
import pyudev


# Android vendor IDs for device detection
ANDROID_VENDOR_IDS = ['2717', '18d1', '0bb4', '04e8', '24e3', '0955', '201e', '0e79', '04c5', '2a47']


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


def get_connected_devices(logger: Optional[logging.Logger] = None) -> List[tuple]:
    """Get list of connected Android devices (serial, model) using pyudev
    
    Args:
        logger: Optional logger for logging errors
    
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
        return []

    try:
        device_list = context.list_devices(subsystem='usb')
    except Exception as e:
        if logger:
            logger.warning(f"Failed to list USB devices: {e}")
        return []

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
        
        # Method 2: Check for Android Debug Bridge interface class (0xff) - but only if we have a valid serial
        # This is less reliable but helps catch devices that might not be in vendor list
        if not is_android and ':' in interfaces:
            interface_parts = interfaces.split(':')
            if len(interface_parts) >= 1:
                interface_class = interface_parts[0]
                # Android devices use vendor-specific class 0xff (255) for debugging interface
                if interface_class.lower() == 'ff' or interface_class == '255':
                    # Additional check: serial should look like an Android serial
                    if len(serial) >= 8 and serial.replace('_', '').replace('-', '').isalnum():
                        is_android = True
        
        if is_android:
            if serial not in seen_serials:
                # Additional validation: Android serials are typically alphanumeric
                # Skip PCI addresses and other non-Android identifiers
                if len(serial) >= 8 and serial.replace('_', '').replace('-', '').isalnum():
                    # Skip PCI-style addresses (e.g., "0000:01:02.0")
                    if ':' not in serial or not serial.startswith('0000:'):
                        model = device.get('ID_MODEL', 'Unknown')
                        model = model.replace('_', ' ').title()
                        devices.append((serial, model))
                        seen_serials.add(serial)

    return devices

