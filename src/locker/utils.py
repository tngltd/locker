#!/usr/bin/env python3
"""
Utility functions for the locker service
"""

import subprocess
import logging
from typing import List, Optional
import pyudev


# Android vendor IDs for device detection
ANDROID_VENDOR_IDS = ['18d1', '0bb4', '04e8', '24e3', '0955', '201e', '0e79', '04c5', '2a47']


def is_service_running(service_name: str, logger: Optional[logging.Logger] = None, log_check: bool = False) -> bool:
    """Check if a systemd service is currently running"""
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', '--quiet', service_name],
            capture_output=True,
            timeout=2
        )
        is_running = result.returncode == 0
        if log_check and logger:
            logger.info(f"Service {service_name} status: {'RUNNING' if is_running else 'STOPPED'}")
        return is_running
    except Exception as e:
        if log_check and logger:
            logger.warning(f"Error checking service {service_name} status: {e}")
        return False


def get_connected_android_serials(logger: Optional[logging.Logger] = None) -> List[str]:
    """Get list of connected Android device serials using pyudev
    
    Raises:
        Exception: If pyudev context creation fails or device listing fails
    """
    serials = []
    seen_serials = set()
    
    try:
        context = pyudev.Context()
    except Exception as e:
        error_msg = f"Failed to create pyudev context: {e}"
        if logger:
            logger.error(error_msg)
        raise Exception(error_msg) from e
    
    # Find Android devices via USB - check for devices with Android interface
    # Look for USB devices in the usb_device subsystem with specific properties
    try:
        for device in context.list_devices(subsystem='usb'):
            # Check for Android-specific properties
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
                            serials.append(serial)
                            seen_serials.add(serial)
    except Exception as e:
        error_msg = f"Failed to list USB devices: {e}"
        if logger:
            logger.error(error_msg)
        raise Exception(error_msg) from e
    
    return serials

