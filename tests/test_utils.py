#!/usr/bin/env python3
"""
Test utilities for platform detection and skipping
"""

import sys
import platform
import unittest


def is_linux():
    """Check if running on Linux"""
    return sys.platform.startswith('linux')


def is_macos():
    """Check if running on macOS"""
    return sys.platform == 'darwin'


def skip_if_not_linux(reason="Test requires Linux"):
    """Skip test if not running on Linux"""
    return unittest.skipUnless(is_linux(), reason)


def skip_if_macos(reason="Test requires Linux, skipping on macOS"):
    """Skip test if running on macOS"""
    return unittest.skipIf(is_macos(), reason)


def has_systemctl():
    """Check if systemctl command is available"""
    import subprocess
    try:
        subprocess.run(['systemctl', '--version'], 
                      capture_output=True, 
                      timeout=1)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return False


def skip_if_no_systemctl(reason="Test requires systemctl"):
    """Skip test if systemctl is not available"""
    return unittest.skipUnless(has_systemctl(), reason)

