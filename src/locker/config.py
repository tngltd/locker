#!/usr/bin/env python3
"""
Configuration handling for the locker service
"""

import os
import json
from typing import Dict, Optional


def _find_project_root() -> Optional[str]:
    """Find the project root directory by looking for pyproject.toml
    
    Returns:
        Path to project root, or None if not found
    """
    # Start from the current file's directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Go up to find project root (look for pyproject.toml)
    # src/locker/config.py -> src/locker -> src -> project root
    for _ in range(3):
        if os.path.exists(os.path.join(current_dir, 'pyproject.toml')):
            return current_dir
        parent = os.path.dirname(current_dir)
        if parent == current_dir:  # Reached filesystem root
            break
        current_dir = parent
    
    return None


def find_config_file(config_path: str) -> str:
    """Validate that config file exists
    
    First checks for config/config.json in the project root (for development),
    then falls back to the provided config_path (for production).
    
    Args:
        config_path: Path to the configuration file (required).
    
    Returns:
        The path to the config file if it exists.
    
    Raises:
        FileNotFoundError: If the config file doesn't exist.
    """
    if not config_path:
        raise FileNotFoundError("Configuration file path is required")
    
    # First, try to find config/config.json in project root (for development)
    project_root = _find_project_root()
    if project_root:
        dev_config_path = os.path.join(project_root, 'config', 'config.json')
        if os.path.exists(dev_config_path) and os.path.isfile(dev_config_path):
            return dev_config_path
    
    # Fall back to the provided path (for production)
    if not os.path.exists(config_path) or not os.path.isfile(config_path):
        raise FileNotFoundError(
            f"Configuration file not found at {config_path}"
        )
    
    return config_path


def load_config(config_path: str) -> Dict:
    """Load and validate configuration from JSON file
    
    Args:
        config_path: Path to the configuration file.
    
    Returns:
        Dictionary containing the configuration.
    
    Raises:
        FileNotFoundError: If the config file doesn't exist.
        ValueError: If the config file contains invalid JSON or fails validation.
    """
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Configuration file not found at {config_path}"
        )
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config file {config_path}: {e}")
    
    validate_config(config)
    return config


def validate_config(config: Dict):
    """Validate configuration structure - check that all required values exist
    
    Args:
        config: Configuration dictionary to validate.
    
    Raises:
        ValueError: If the configuration is invalid or missing required values.
    """
    required_sections = ['service', 'monitoring']
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Missing required config section: {section}")
    
    # Validate service section
    if 'log_level' not in config['service']:
        raise ValueError("Missing \"log_level\" in service config")
    
    if 'log_file' not in config['service']:
        raise ValueError("Missing \"log_file\" in service config")
    
    # Validate monitoring section
    if 'check_interval_seconds' not in config['monitoring']:
        raise ValueError("Missing \"check_interval_seconds\" in monitoring config")
    
    # Validate mode exists and is valid
    if 'mode' not in config:
        raise ValueError("Missing \"mode\" in config")
    if config['mode'] not in ['permissive', 'enforcing']:
        raise ValueError(f"Invalid mode: {config['mode']}. Must be \"permissive\" or \"enforcing\"")
    
    # Validate android_serial exists (can be None, but key must exist)
    if 'android_serial' not in config:
        raise ValueError("Missing \"android_serial\" in config")
    
    # Validate services exists and is a list
    if 'services' not in config:
        raise ValueError("Missing \"services\" in config")
    if not isinstance(config['services'], list):
        raise ValueError("Invalid \"services\" format: must be a list")


def save_config(config: Dict, config_path: str, suggested_sudo_cmd: Optional[str] = None):
    """Save configuration to file
    
    Args:
        config: Configuration dictionary to save.
        config_path: Path where the configuration should be saved.
        suggested_sudo_cmd: Optional command to suggest when permission is denied
            (e.g. "sudo locker set-android-serial" or "sudo locker add-service ssh").
    
    Raises:
        OSError: If the file cannot be written.
        PermissionError: If the file cannot be written due to permissions.
    """
    config_dir = os.path.dirname(config_path)
    try:
        os.makedirs(config_dir, exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        os.chmod(config_path, 0o644)
    except PermissionError:
        msg_parts = [
            f"Permission denied: Cannot write to {config_path}. "
            "This file requires root permissions.",
            "",
            "To write configuration, you need write permissions to /etc/locker/config.json",
            "Options:",
        ]
        if suggested_sudo_cmd:
            msg_parts.append(f"  1. Run with sudo: {suggested_sudo_cmd}")
        else:
            msg_parts.append("  1. Run your command with sudo")
        raise PermissionError("\n".join(msg_parts))
    except OSError as e:
        raise OSError(f"Failed to save configuration to {config_path}: {e}")

