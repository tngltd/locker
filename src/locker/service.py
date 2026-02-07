#!/usr/bin/env python3
"""
Lock-Down Service - Main daemon
A security service for Ubuntu systems to lock down devices when the configured Android device is disconnected.
"""

import os
import socket
import time
import signal
import logging
import daemon
import traceback

from typing import Optional
import argparse
from locker import utils
from locker import config


def _notify_systemd_ready() -> bool:
    """Notify systemd that the service is ready (for Type=notify). Returns True if notified."""
    sock_path = os.environ.get('NOTIFY_SOCKET')
    if not sock_path:
        return False
    # Abstract socket: @path -> bytes with leading null for AF_UNIX
    if sock_path.startswith('@'):
        addr = b'\0' + sock_path[1:].encode('utf-8')
    elif sock_path.startswith('/'):
        addr = sock_path
    else:
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.sendto(b'READY=1\n', addr)
        return True
    except (OSError, ValueError):
        return False


class LockService:
    def __init__(self, config_path: Optional[str] = None, config_dir: Optional[str] = None, config_override: Optional[dict] = None):
        # Use default config path if not provided
        if config_path is None:
            config_path = "/etc/locker/config.json"
        # Validate that config file exists (will raise FileNotFoundError if not)
        self.config_path = config.find_config_file(config_path)
        
        # Set config directory (allow override for testing)
        self.config_dir = config_dir or "/etc/locker"
        
        # Load configuration
        self.config = config.load_config(self.config_path)
        if config_override:
            self.config.update(config_override)
        
        self.running = True
        
        # Setup logging first (needed for error handling)
        # Note: self.config is already loaded above
        self.setup_logging()
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        android_serial = self.config['android_serial']
        if android_serial:
            self.logger.info(f"Lock Service initialized. Configured Android serial: {android_serial}")
        else:
            self.logger.warning("Lock Service initialized. No Android device configured - run \"locker set-android-serial\" first")
    
    def setup_logging(self):
        """Setup logging configuration"""
        # Get log level from config
        log_level_str = self.config['service']['log_level'].upper()
        log_level = getattr(logging, log_level_str, logging.INFO)

        # Setup logger
        self.logger = logging.getLogger('locker')
        self.logger.setLevel(log_level)
        # Close and clear any existing handlers to avoid duplicates
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)

        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # Setup console handler first (for error visibility)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)  # Less verbose on console
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # Setup file handler (always try to create)
        try:
            log_file_path = self.config['service']['log_file']
            # Ensure log directory exists
            log_dir = os.path.dirname(log_file_path)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file_path)
            file_handler.setLevel(logging.DEBUG)  # Verbose logging to file
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            
            # Ensure log file is writable by CLI (non-root) users too
            try:
                os.chmod(log_file_path, 0o666)
            except OSError:
                pass  # Best effort; may fail if not owner
            
            # Log successful file handler setup
            self.logger.info(f"Logging to file: {log_file_path}")
        except (OSError, PermissionError) as e:
            # Log error to console handler (which is already added)
            self.logger.warning(f"Failed to setup file logging to {log_file_path}: {e}")
            self.logger.warning("Logs will only be written to console/systemd journal")
    
    def log_config(self):
        """Log current configuration (sanitized for security)"""
        try:
            # Create a sanitized copy of config for logging
            config_copy = self.config.copy()
            
            # Don't log sensitive information or very long values
            # Keep android_serial but truncate if too long
            sanitized_serial = config_copy.get('android_serial') or 'Not configured'
            if sanitized_serial and sanitized_serial != 'Not configured' and len(sanitized_serial) > 20:
                sanitized_serial = sanitized_serial[:10] + "..." + sanitized_serial[-7:]
            
            # Log configuration in a readable format
            self.logger.info("Current configuration:")
            self.logger.info(f"  Mode: {config_copy['mode']}")
            self.logger.info(f"  Android Serial: {sanitized_serial}")
            self.logger.info(f"  Services: {config_copy['services']}")
            self.logger.info(f"  Monitoring Interval: {config_copy['monitoring']['check_interval_seconds']} seconds")
            self.logger.info(f"  Log Level: {config_copy['service']['log_level']}")
            self.logger.info(f"  Log File: {config_copy['service']['log_file']}")
            
            # Network config logging removed (no longer used)
        except Exception as e:
            self.logger.warning(f"Error logging configuration: {e}")
    
    def lock_system(self, services: list, enforcing: bool):
        """Lock down the system - stop configured services (stateless)
        
        Args:
            services: List of service names to stop
            enforcing: If True, actually stop services. If False, only log actions.
        """
        mode_str = "enforcing" if enforcing else "permissive"
        self.logger.info(f"Locking system (mode: {mode_str})...")
        
        if not services:
            self.logger.info("No services configured to lock")
            return
        
        for service in services:
            is_running = utils.is_service_running(service, logger=self.logger)
            
            if not is_running:
                self.logger.info(f"Service {service} is already stopped - skipping")
                continue

            self.logger.info(f"Service {service} is running - {'would be' if not enforcing else ''} stopping it ({mode_str})")
            
            if not enforcing:
                continue

            utils.stop_service(service, logger=self.logger)
    
        self.logger.info(f"System locked successfully (mode: {mode_str})")
    
    def unlock_system(self, services: list, enforcing: bool):
        """Unlock the system - start configured services (stateless)
        
        Args:
            services: List of service names to start
            enforcing: If True, actually start services. If False, only log actions.
        """
        mode_str = "enforcing" if enforcing else "permissive"
        self.logger.info(f"Unlocking system (mode: {mode_str})...")
        
        if not services:
            self.logger.info("No services configured to unlock")
            return
        
        for service in services:
            is_running = utils.is_service_running(service, logger=self.logger)
            
            if is_running:
                self.logger.info(f"Service {service} is already running - skipping")
                continue

            self.logger.info(f"Service {service} is not running - {'would be' if not enforcing else ''} starting it ({mode_str})")
            
            if not enforcing:
                continue

            utils.start_service(service, logger=self.logger)
    
        self.logger.info(f"System unlocked successfully (mode: {mode_str})")
    
    def is_configured_device_connected(self) -> bool:
        """Check if the configured Android device is connected"""
        android_serial = self.config['android_serial']
        if not android_serial:
            return False
        
        devices = utils.get_connected_devices(logger=self.logger)
        connected_serials = [d[0] for d in devices]
        is_connected = android_serial in connected_serials
        
        if is_connected:
            self.logger.info(f"Android device {android_serial} is connected")
        else:
            self.logger.info(f"Android device {android_serial} is NOT connected")
        
        return is_connected
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def run_once(self, config_override: dict = None):
        """Run a single monitoring check and act accordingly
        
        Args:
            config_override: Optional dict to override config values. If provided,
                            config will be reloaded from file first, then override applied.
        """
        # Phase 1: Load config, apply override, validate
        self.config = config.load_config(self.config_path)
        if config_override:
            self.config.update(config_override)
            config.validate_config(self.config)
        
        # Extract config values
        android_serial = self.config['android_serial']
        mode = self.config['mode']
        services = self.config['services']
        enforcing = (mode == 'enforcing')
        
        self.logger.info("Monitor loop iteration started")
        try:
            # Phase 2: Get android_serial from config and check if device is connected
            is_connected = False
            if android_serial and len(android_serial) > 0:
                self.logger.info(f"Android device configured: {android_serial}")
                is_connected = self.is_configured_device_connected()
                device_status = "CONNECTED" if is_connected else "DISCONNECTED"
                self.logger.info(f"Device {android_serial} connection status: {device_status}")
            else:
                self.logger.info("No Android device configured")
            
            # Phase 3: If connected, unlock - otherwise lock. Pass enforcing bool.
            if is_connected:
                self.logger.info(f"Device connected - unlocking system (mode: {mode})")
                self.unlock_system(services, enforcing)
            else:
                self.logger.info(f"Device disconnected - locking system (mode: {mode})")
                self.lock_system(services, enforcing)
            
        except Exception as e:
            self.logger.error(f"Error in monitoring check: {e}")
            traceback.print_exc()
            raise
    
    def run(self):
        """Main service loop"""
        mode = self.config['mode']
        self.logger.info(f"Lock Service started successfully (mode: {mode})")
        
        # Log configuration on startup
        self.log_config()
        
        # Notify systemd we are ready (when Type=notify)
        _notify_systemd_ready()
        
        while self.running:
            try:
                self.run_once()
                check_interval = self.config['monitoring']['check_interval_seconds']
                self.logger.info(f"Sleeping for {check_interval} seconds before next check")
                time.sleep(check_interval)
            except KeyboardInterrupt:
                self.running = False
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                time.sleep(5)
        
        self.logger.info("Lock Service stopped")


def main():
    """Entry point for locker command"""
    parser = argparse.ArgumentParser(description='Lock-Down Service')
    parser.add_argument('--config', default='/etc/locker/config.json',
                       help='Configuration file path')
    parser.add_argument('--daemon', action='store_true',
                       help='Run as daemon')
    parser.add_argument('--run-once', action='store_true',
                       help='Run once and exit (check device connection once)')
    parser.add_argument('--mode', choices=['permissive', 'enforcing'],
                       help='Mode: permissive or enforcing (overrides config)')
    parser.add_argument('--android-serial', type=str,
                       help='Android device serial (overrides config)')
    parser.add_argument('--services', nargs='+',
                       help='Services to manage (overrides config)')
    parser.add_argument('--check-interval', type=int,
                       help='Monitoring check interval in seconds (overrides config)')
    
    args = parser.parse_args()
    
    # Build config override from command-line arguments
    config_override = {}
    if args.mode:
        config_override['mode'] = args.mode
    if args.android_serial:
        config_override['android_serial'] = args.android_serial
    if args.services:
        config_override['services'] = args.services
    if args.check_interval:
        if 'monitoring' not in config_override:
            config_override['monitoring'] = {}
        config_override['monitoring']['check_interval_seconds'] = args.check_interval
    
    service = LockService(args.config, config_override=config_override)
    
    # Log service startup
    service.logger.info("=" * 60)
    service.logger.info("Lock-Down Service starting...")
    service.logger.info(f"Configuration file: {args.config}")
    if config_override:
        service.logger.info(f"Command-line overrides: {config_override}")
    service.logger.info("=" * 60)
    
    if args.run_once:
        # Run once mode - check device connection once and act accordingly
        service.logger.info("Running in run-once mode")
        service.log_config()
        service.run_once()
    elif args.daemon:
        # Run as daemon - preserve log file handlers so logging continues
        files_to_preserve = []
        for handler in service.logger.handlers:
            if hasattr(handler, 'stream') and hasattr(handler.stream, 'fileno'):
                try:
                    files_to_preserve.append(handler.stream)
                except Exception:
                    pass
        with daemon.DaemonContext(files_preserve=files_to_preserve):
            service.run()
    else:
        service.run()


if __name__ == "__main__":
    main()
