#!/usr/bin/env python3
"""
Lock-Down Service CLI Tool
Command line interface for managing the lock-down service.
"""

import os
import argparse
import subprocess
import time
import warnings
import logging
from typing import Optional, List
from locker import utils
from locker import config


class LockCLI:
    def __init__(self):
        self.config_path = "/etc/locker/config.json"
        self.config_dir = "/etc/locker"
        self.pid_file = "/var/run/locker.pid"
        self.service_pid_file = self.pid_file  # Alias for test compatibility
        self.logger = None
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging to write to the same log file as the service"""
        try:
            # Try to load config to get log file path
            try:
                loaded_config = config.load_config(self.config_path)
                log_file_path = loaded_config['service'].get('log_file', '/var/log/locker.log')
                log_level_str = loaded_config['service'].get('log_level', 'INFO').upper()
            except (FileNotFoundError, KeyError, Exception):
                # If config doesn't exist or can't be loaded, use defaults
                log_file_path = '/var/log/locker.log'
                log_level_str = 'INFO'
            
            # Setup logger
            self.logger = logging.getLogger('locker.cli')
            log_level = getattr(logging, log_level_str, logging.INFO)
            self.logger.setLevel(log_level)
            
            # Clear existing handlers to avoid duplicates (especially in tests)
            for handler in self.logger.handlers[:]:
                handler.close()
                self.logger.removeHandler(handler)
            
            # Add handlers if we don't have any
            if not self.logger.handlers:
                # Create formatter
                formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                
                # Setup file handler (try to write to same log file as service)
                try:
                    log_dir = os.path.dirname(log_file_path)
                    if log_dir:
                        os.makedirs(log_dir, exist_ok=True)
                    
                    file_handler = logging.FileHandler(log_file_path)
                    file_handler.setLevel(logging.INFO)
                    file_handler.setFormatter(formatter)
                    self.logger.addHandler(file_handler)
                except (OSError, PermissionError):
                    # If we can't write to log file, that's okay - CLI can still work
                    # Just won't log to file
                    pass
        except Exception:
            # If logging setup fails, continue without logging
            # CLI should still function
            pass
    
    def _log_command(self, command_name: str, *args, **kwargs):
        """Log CLI command execution"""
        if self.logger:
            args_str = ' '.join(str(a) for a in args) if args else ''
            kwargs_str = ' '.join(f'{k}={v}' for k, v in kwargs.items()) if kwargs else ''
            cmd_str = f"{command_name} {args_str} {kwargs_str}".strip()
            self.logger.info(f"CLI: Executing command: {cmd_str}")
    
    def _log_output(self, output: str):
        """Log CLI command output"""
        if self.logger and output:
            # Log each line of output
            for line in output.split('\n'):
                if line.strip():
                    self.logger.info(f"CLI: Output: {line}")
    
    def load_config(self):
        """Load configuration from config_path. Used by tests and for consistency."""
        return config.load_config(self.config_path)

    def save_config(self, config_dict: dict, suggested_sudo_cmd: Optional[str] = None):
        """Save configuration to config_path. Used by tests and for consistency."""
        config.save_config(config_dict, self.config_path, suggested_sudo_cmd=suggested_sudo_cmd)

    def get_android_serial(self) -> Optional[str]:
        """Get configured Android device serial.
        
        Priority:
        1. config.json android_serial (explicitly configured by user)
        2. Mock device file serial (if /etc/locker/connect_android_serials.json exists)
        """
        loaded_config = config.load_config(self.config_path)
        serial = loaded_config.get('android_serial')
        if serial:
            return serial
        
        # Fall back to mock device file
        mock_device = utils.get_mock_device(config_dir=self.config_dir)
        if mock_device:
            return mock_device[0]
        
        return None
    
    def get_android_serial_cmd(self):
        """Get Android serial from config and check mock device file"""
        self._log_command("get-android-serial")
        
        output_lines = []
        output_lines.append("=== Get Android Serial ===")
        output_lines.append("")
        
        serial = self.get_android_serial()
        
        if not serial:
            output_lines.append("No Android serial configured.")
            output_lines.append("")
            output_lines.append("Use \"locker set-android-serial\" to configure a device.")
        else:
            output_lines.append(f"Configured Android serial: {serial}")
        
        # Also check mock device file
        mock_device = utils.get_mock_device(config_dir=self.config_dir)
        if mock_device:
            output_lines.append("")
            output_lines.append(f"Mock device detected: {mock_device[0]} (from {self.config_dir}/connect_android_serials.json)")
        
        output = "\n".join(output_lines)
        for line in output_lines:
            print(line)
        self._log_output(output)
    
    def list_devices_cmd(self):
        """List all connected Android devices"""
        self._log_command("list-devices")
        
        output_lines = []
        output_lines.append("=== List Connected Devices ===")
        output_lines.append("")
        
        devices = utils.get_connected_devices()
        
        if not devices:
            output_lines.append("No Android devices found.")
            output_lines.append("")
            output_lines.append("Please ensure:")
            output_lines.append("  1. Your Android device is connected via USB")
            output_lines.append("  2. USB debugging is enabled on the device")
            output = "\n".join(output_lines)
            for line in output_lines:
                print(line)
            self._log_output(output)
            return
        
        output_lines.append("Connected Android devices:")
        output_lines.append("-" * 50)
        for i, (serial, model) in enumerate(devices, 1):
            output_lines.append(f"  {i}. {serial} ({model})")
        output_lines.append("-" * 50)
        output_lines.append("")
        
        configured_serial = self.get_android_serial()
        if configured_serial:
            if configured_serial in [d[0] for d in devices]:
                output_lines.append(f"Configured device ({configured_serial}) is currently connected.")
            else:
                output_lines.append(f"Configured device ({configured_serial}) is not currently connected.")
        
        output = "\n".join(output_lines)
        for line in output_lines:
            print(line)
        self._log_output(output)
    
    def set_android_serial(self, serial: Optional[str] = None):
        """Set Android device serial"""
        self._log_command("set-android-serial", serial=serial)
        
        output_lines = []
        output_lines.append("=== Set Android Serial ===")
        output_lines.append("")
        
        # If serial not provided, show connected devices
        if not serial:
            devices = utils.get_connected_devices()
            
            if not devices:
                output_lines.append("No Android devices found.")
                output_lines.append("")
                output_lines.append("Please ensure:")
                output_lines.append("  1. Your Android device is connected via USB")
                output_lines.append("  2. USB debugging is enabled on the device")
                output_lines.append("")
                for line in output_lines:
                    print(line)
                self._log_output("\n".join(output_lines))
                
                response = input("Enter device serial manually? (y/N): ")
                if self.logger:
                    self.logger.info(f"CLI: User input for manual entry: {response}")
                if response.lower() == 'y':
                    serial = input("Enter Android device serial: ").strip()
                    if self.logger:
                        self.logger.info(f"CLI: User entered serial manually: {serial}")
                else:
                    msg = "Cancelled."
                    print(msg)
                    if self.logger:
                        self.logger.info(f"CLI: {msg}")
                    return
            else:
                output_lines.append("Connected Android devices:")
                output_lines.append("-" * 50)
                for i, (serial_dev, model) in enumerate(devices, 1):
                    output_lines.append(f"  {i}. {serial_dev} ({model})")
                output_lines.append("-" * 50)
                output_lines.append("")
                for line in output_lines:
                    print(line)
                self._log_output("\n".join(output_lines))
                
                if len(devices) == 1:
                    response = input(f"Use device {devices[0][0]}? (Y/n): ")
                    if self.logger:
                        self.logger.info(f"CLI: User input for single device: {response}")
                    if response.lower() != 'n':
                        serial = devices[0][0]
                    else:
                        msg = "Cancelled."
                        print(msg)
                        if self.logger:
                            self.logger.info(f"CLI: {msg}")
                        return
                else:
                    try:
                        choice = input(f"Select device (1-{len(devices)}) or enter serial: ").strip()
                        if self.logger:
                            self.logger.info(f"CLI: User input for device selection: {choice}")
                        try:
                            idx = int(choice) - 1
                            if 0 <= idx < len(devices):
                                serial = devices[idx][0]
                            else:
                                msg = "Invalid selection."
                                print(msg)
                                if self.logger:
                                    self.logger.warning(f"CLI: {msg}")
                                return
                        except ValueError:
                            # User entered serial directly
                            serial = choice
                    except KeyboardInterrupt:
                        msg = "\nCancelled."
                        print(msg)
                        if self.logger:
                            self.logger.info(f"CLI: Cancelled via KeyboardInterrupt")
                        return
        
        if not serial:
            msg = "No serial provided."
            print(msg)
            if self.logger:
                self.logger.warning(f"CLI: {msg}")
            return
        
        # Save to config
        try:
            loaded_config = self.load_config()
            loaded_config['android_serial'] = serial
            self.save_config(loaded_config, suggested_sudo_cmd="sudo locker set-android-serial")
            if self.logger:
                self.logger.info(f"CLI: Set Android serial to '{serial}'")
            output_lines.append("")
            output_lines.append(f"Android serial configured: {serial}")
            output = "\n".join(output_lines)
            for line in output_lines:
                print(line)
            self._log_output(output)
        except PermissionError as e:
            output_lines.append(str(e))
            output = "\n".join(output_lines)
            for line in output_lines:
                print(line)
            self._log_output(output)
            return
        except Exception as e:
            msg = f"Error saving configuration: {e}"
            output_lines.append(msg)
            output = "\n".join(output_lines)
            for line in output_lines:
                print(line)
            self._log_output(output)
            if self.logger:
                self.logger.error(f"CLI: {msg}")
            return

    
    def add_service(self, service_name: str):
        """Add a service to be managed (started on connection, stopped on disconnection)"""
        self._log_command("add-service", service_name)
        
        output_lines = []
        output_lines.append("=== Add Service ===")
        output_lines.append("")
        
        try:
            loaded_config = self.load_config()
            if 'services' not in loaded_config:
                loaded_config['services'] = []
            elif not isinstance(loaded_config['services'], list):
                # Convert old format to new format
                if isinstance(loaded_config['services'], dict):
                    old_stop = loaded_config['services'].get('stop_when_locked', [])
                    old_start = loaded_config['services'].get('start_when_unlocked', [])
                    loaded_config['services'] = list(set(old_stop + old_start))
                else:
                    loaded_config['services'] = []
            
            services_list = loaded_config['services']
            if service_name not in services_list:
                services_list.append(service_name)
                loaded_config['services'] = services_list
                try:
                    self.save_config(loaded_config, suggested_sudo_cmd=f"sudo locker add-service {service_name}")
                    if self.logger:
                        self.logger.info(f"CLI: Added service '{service_name}' to managed services list")
                    msg = f"Service \"{service_name}\" added. It will be started when device connects and stopped when device disconnects."
                    output_lines.append(msg)
                    print(msg)
                except PermissionError as e:
                    output_lines.append(str(e))
                    print(e)
                    self._log_output("\n".join(output_lines))
                    return
            else:
                if self.logger:
                    self.logger.info(f"CLI: Attempted to add service '{service_name}' but it is already in the services list")
                msg = f"Service \"{service_name}\" is already in the services list."
                output_lines.append(msg)
                print(msg)
            
            self._log_output("\n".join(output_lines))
        except Exception as e:
            msg = f"Error adding service: {e}"
            print(msg)
            if self.logger:
                self.logger.error(f"CLI: {msg}")
    
    def remove_service(self, service_name: str):
        """Remove a service from being managed"""
        self._log_command("remove-service", service_name)
        
        output_lines = []
        output_lines.append("=== Remove Service ===")
        output_lines.append("")
        
        try:
            loaded_config = self.load_config()
            if 'services' not in loaded_config:
                loaded_config['services'] = []
            elif not isinstance(loaded_config['services'], list):
                # Convert old format to new format
                if isinstance(loaded_config['services'], dict):
                    old_stop = loaded_config['services'].get('stop_when_locked', [])
                    old_start = loaded_config['services'].get('start_when_unlocked', [])
                    loaded_config['services'] = list(set(old_stop + old_start))
                else:
                    loaded_config['services'] = []
            
            services_list = loaded_config['services']
            if service_name in services_list:
                services_list.remove(service_name)
                loaded_config['services'] = services_list
                try:
                    self.save_config(loaded_config, suggested_sudo_cmd=f"sudo locker remove-service {service_name}")
                    if self.logger:
                        self.logger.info(f"CLI: Removed service '{service_name}' from managed services list")
                    msg = f"Service \"{service_name}\" removed. It will no longer be managed by the locker service."
                    output_lines.append(msg)
                    print(msg)
                except PermissionError as e:
                    output_lines.append(str(e))
                    print(e)
                    self._log_output("\n".join(output_lines))
                    return
            else:
                if self.logger:
                    self.logger.info(f"CLI: Attempted to remove service '{service_name}' but it is not in the services list")
                msg = f"Service \"{service_name}\" is not in the services list."
                output_lines.append(msg)
                print(msg)
            
            self._log_output("\n".join(output_lines))
        except Exception as e:
            msg = f"Error removing service: {e}"
            print(msg)
            if self.logger:
                self.logger.error(f"CLI: {msg}")
    
    def list_services(self):
        """List all configured services"""
        self._log_command("list-services")
        
        output_lines = []
        output_lines.append("=== Configured Services ===")
        output_lines.append("")
        
        try:
            loaded_config = self.load_config()
            services = loaded_config.get('services', [])
            
            if not services:
                output_lines.append("No services configured.")
                output_lines.append("")
                output_lines.append("Use \"locker add-service <service>\" to add a service.")
            else:
                output_lines.append(f"Configured services ({len(services)}):")
                output_lines.append("-" * 50)
                for i, service_name in enumerate(services, 1):
                    # Check service status
                    try:
                        result = subprocess.run(
                            ['systemctl', 'is-active', '--quiet', service_name],
                            capture_output=True,
                            timeout=2
                        )
                        status = "RUNNING" if result.returncode == 0 else "STOPPED"
                        output_lines.append(f"  {i}. {service_name} ({status})")
                    except Exception:
                        output_lines.append(f"  {i}. {service_name} (UNKNOWN)")
                output_lines.append("-" * 50)
            
            output = "\n".join(output_lines)
            for line in output_lines:
                print(line)
            self._log_output(output)
        except Exception as e:
            error_msg = f"Error listing services: {e}"
            print(error_msg)
            if self.logger:
                self.logger.error(f"CLI: {error_msg}")
    
    def set_mode(self, mode: Optional[str] = None):
        """Set mode to permissive or enforcing"""
        print("=== Set Mode ===")
        print()
        
        if not mode:
            current_mode = self.load_config().get('mode', 'permissive')
            print(f"Current mode: {current_mode}")
            print()
            print("Modes:")
            print("  permissive - System will not lock even if device is disconnected")
            print("  enforcing - System will lock when device is disconnected")
            print()
            response = input("Enter mode (permissive/enforcing): ").strip().lower()
            if response in ['permissive', 'enforcing']:
                mode = response
            else:
                print("Invalid mode. Must be \"permissive\" or \"enforcing\"")
                return
        
        if mode not in ['permissive', 'enforcing']:
            print("Error: Mode must be \"permissive\" or \"enforcing\"")
            return
        
        try:
            loaded_config = self.load_config()
            
            # In enforcing mode, require Android serial to be configured
            # (either in config or via mock device file)
            if mode == 'enforcing':
                serial = self.get_android_serial()
                if not serial:
                    output_lines = [
                        "Error: Cannot set enforcing mode without configured Android serial.",
                        "Run \"locker set-android-serial\" first,",
                        "or create a mock device file at /etc/locker/connect_android_serials.json"
                    ]
                    output = "\n".join(output_lines)
                    for line in output_lines:
                        print(line)
                    self._log_output(output)
                    if self.logger:
                        self.logger.warning("CLI: Attempted to set enforcing mode without Android serial")
                    return
            
            loaded_config['mode'] = mode
            try:
                self.save_config(loaded_config, suggested_sudo_cmd=f"sudo locker set-mode {mode}")
                if self.logger:
                    self.logger.info(f"CLI: Set mode to '{mode}'")
                output_lines = [f"Mode set to: {mode}"]
                
                if mode == 'enforcing':
                    output_lines.append("")
                    output_lines.append("WARNING: In enforcing mode, the system will lock if the configured")
                    output_lines.append("         Android device is not connected.")
                
                output = "\n".join(output_lines)
                for line in output_lines:
                    print(line)
                self._log_output(output)
            except PermissionError as e:
                msg = str(e)
                print(msg)
                if self.logger:
                    self.logger.error(f"CLI: {msg}")
                return
        except Exception as e:
            msg = f"Error setting mode: {e}"
            print(msg)
            if self.logger:
                self.logger.error(f"CLI: {msg}")
    
    def logs(self, lines: int = 50, follow: bool = False):
        """Show service logs"""
        self._log_command("logs", lines=lines, follow=follow)
        
        try:
            loaded_config = self.load_config()
            log_file = loaded_config['service'].get('log_file', '/var/log/locker.log')
        except:
            log_file = "/var/log/locker.log"
        
        if not os.path.exists(log_file):
            output_lines = [
                f"No log file found at {log_file}",
                "The log file will be created when the service starts.",
                "Start the service with: systemctl start locker",
                "Or run the service directly: lockerd"
            ]
            output = "\n".join(output_lines)
            for line in output_lines:
                print(line)
            self._log_output(output)
            return
        
        # Check if file is empty (only if not following)
        if not follow:
            try:
                if os.path.getsize(log_file) == 0:
                    print(f"Log file exists but is empty: {log_file}")
                    print("The service may not have started yet or no logs have been written.")
                    return
            except OSError:
                # File might have been deleted between exists() and getsize()
                print(f"Log file no longer accessible: {log_file}")
                return
        
        if follow:
            # Follow mode - use tail -f
            try:
                # Use Popen instead of run to allow proper signal handling
                tail_process = subprocess.Popen(['tail', '-f', log_file])
                try:
                    tail_process.wait()
                except KeyboardInterrupt:
                    tail_process.terminate()
                    tail_process.wait()
                    print("\nStopped following logs.")
            except FileNotFoundError:
                print("Error: tail command not found. Follow mode requires tail.")
            except Exception as e:
                print(f"Error following logs: {e}")
        else:
            # Regular mode - show last N lines
            try:
                subprocess.run(['tail', '-n', str(lines), log_file])
            except FileNotFoundError:
                # tail command not found, fall back to reading file directly
                try:
                    with open(log_file, 'r') as f:
                        all_lines = f.readlines()
                        if not all_lines:
                            print(f"Log file exists but is empty: {log_file}")
                            return
                        for line in all_lines[-lines:]:
                            print(line.rstrip())
                except Exception as e:
                    print(f"Error reading log file: {e}")
    
    def is_service_running(self) -> bool:
        """Check if the locker service is running (check PID file first, then systemctl)"""
        # Check PID file if available
        pid_file = getattr(self, 'service_pid_file', None) or self.pid_file
        if pid_file and os.path.exists(pid_file):
            try:
                with open(pid_file, 'r') as f:
                    pid_str = f.read().strip()
                    if pid_str:
                        pid = int(pid_str)
                        # Check if process is actually running
                        try:
                            os.kill(pid, 0)  # Signal 0 doesn't kill, just checks if process exists
                            return True
                        except (OSError, ProcessLookupError):
                            return False
            except (ValueError, IOError):
                pass
        
        # Fall back to systemctl check
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', 'locker'],
                capture_output=True,
                text=True,
                timeout=5,
                check=False
            )
            return result.returncode == 0 and result.stdout.strip() == 'active'
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            return False
    
    def start_service(self):
        """Start the locker systemd service"""
        self._log_command("start-service")
        
        if self.is_service_running():
            msg = "Service is already running."
            print(msg)
            if self.logger:
                self.logger.info(f"CLI: {msg}")
            return
        
        try:
            result = subprocess.run(
                ['systemctl', 'start', 'locker'],
                capture_output=True,
                text=True,
                timeout=10,
                check=True
            )
            msg = "Service started successfully."
            print(msg)
            if self.logger:
                self.logger.info(f"CLI: {msg}")
        except subprocess.CalledProcessError as e:
            msg = f"Failed to start service: {e.stderr}"
            print(msg)
            if self.logger:
                self.logger.error(f"CLI: {msg}")
        except FileNotFoundError:
            msg = "Error: systemctl not found. Cannot start service."
            print(msg)
            if self.logger:
                self.logger.error(f"CLI: {msg}")
        except subprocess.TimeoutExpired:
            msg = "Error: Service start command timed out."
            print(msg)
            if self.logger:
                self.logger.error(f"CLI: {msg}")
        except Exception as e:
            msg = f"Error starting service: {e}"
            print(msg)
            if self.logger:
                self.logger.error(f"CLI: {msg}")
    
    def stop_service(self):
        """Stop the locker systemd service"""
        self._log_command("stop-service")
        
        if not self.is_service_running():
            msg = "Service is not running."
            print(msg)
            if self.logger:
                self.logger.info(f"CLI: {msg}")
            return
        
        try:
            result = subprocess.run(
                ['systemctl', 'stop', 'locker'],
                capture_output=True,
                text=True,
                timeout=10,
                check=True
            )
            msg = "Service stopped successfully."
            print(msg)
            if self.logger:
                self.logger.info(f"CLI: {msg}")
        except subprocess.CalledProcessError as e:
            msg = f"Failed to stop service: {e.stderr}"
            print(msg)
            if self.logger:
                self.logger.error(f"CLI: {msg}")
        except FileNotFoundError:
            msg = "Error: systemctl not found. Cannot stop service."
            print(msg)
            if self.logger:
                self.logger.error(f"CLI: {msg}")
        except subprocess.TimeoutExpired:
            msg = "Error: Service stop command timed out."
            print(msg)
            if self.logger:
                self.logger.error(f"CLI: {msg}")
        except Exception as e:
            msg = f"Error stopping service: {e}"
            print(msg)
            if self.logger:
                self.logger.error(f"CLI: {msg}")
    
    def restart_service(self):
        """Restart the locker systemd service"""
        self._log_command("restart-service")
        self.stop_service()
        time.sleep(1)  # Brief pause between stop and start
        self.start_service()
        if self.logger:
            self.logger.info("CLI: Service restart completed")
    
    def save_android_serial(self, serial: str):
        """Save Android device serial to config"""
        try:
            loaded_config = self.load_config()
            loaded_config['android_serial'] = serial
            self.save_config(loaded_config, suggested_sudo_cmd="sudo locker set-android-serial")
        except PermissionError as e:
            print(e)
        except Exception as e:
            print(f"Error saving Android serial: {e}")
    
    def emergency_unlock(self):
        """Emergency unlock - manually unlock system without device"""
        self._log_command("emergency-unlock")
        
        output_lines = []
        output_lines.append("=== Emergency Unlock ===")
        output_lines.append("")
        output_lines.append("WARNING: This will unlock the system even if the configured")
        output_lines.append("Android device is not connected.")
        output_lines.append("")
        
        for line in output_lines:
            print(line)
        self._log_output("\n".join(output_lines))
        
        response = input("Are you sure you want to unlock? (yes/no): ").strip().lower()
        if self.logger:
            self.logger.info(f"CLI: Emergency unlock confirmation: {response}")
        
        if response != 'yes':
            msg = "Cancelled."
            print(msg)
            if self.logger:
                self.logger.info(f"CLI: {msg}")
            return
        
        try:
            loaded_config = self.load_config()
            
            # Start configured services (only if not running)
            services = loaded_config.get('services', [])
            output_lines = []
            for service_name in services:
                try:
                    # Check if service is already running before starting
                    result = subprocess.run(
                        ['systemctl', 'is-active', '--quiet', service_name],
                        capture_output=True,
                        timeout=2
                    )
                    if result.returncode != 0:
                        # Service is not running, start it
                        subprocess.run(['systemctl', 'start', service_name], check=False, timeout=5)
                        if self.logger:
                            self.logger.info(f"CLI: Started service {service_name} during emergency unlock")
                    else:
                        msg = f"Service {service_name} is already running"
                        output_lines.append(msg)
                        print(msg)
                except Exception as e:
                    msg = f"Error starting service {service_name}: {e}"
                    output_lines.append(msg)
                    print(msg)
                    if self.logger:
                        self.logger.error(f"CLI: {msg}")
            
            msg = "System unlocked successfully."
            output_lines.append(msg)
            print(msg)
            self._log_output("\n".join(output_lines))
            if self.logger:
                self.logger.info(f"CLI: {msg}")
        except Exception as e:
            msg = f"Error unlocking system: {e}"
            print(msg)
            if self.logger:
                self.logger.error(f"CLI: {msg}")
    
    def get_status(self):
        """Show current mode and overall status"""
        self._log_command("get-status")
        
        output_lines = []
        output_lines.append("=== Locker Status ===")
        output_lines.append("")
        
        loaded_config = self.load_config()
        mode = loaded_config.get('mode', 'permissive')
        output_lines.append(f"Mode: {mode}")
        
        # Service running status
        is_running = self.is_service_running()
        output_lines.append(f"Service running: {'Yes' if is_running else 'No'}")
        output_lines.append("")
        
        # Device configuration
        serial = self.get_android_serial()
        if not serial:
            output_lines.append("Android device: Not configured")
        else:
            output_lines.append(f"Android device: {serial}")
            devices = utils.get_connected_devices(config_dir=self.config_dir)
            connected_serials = [d[0] for d in devices]
            if serial in connected_serials:
                output_lines.append("Device status: CONNECTED")
            else:
                output_lines.append("Device status: DISCONNECTED")
        output_lines.append("")
        
        # Configured services
        services = loaded_config.get('services', [])
        if services:
            output_lines.append(f"Managed services ({len(services)}):")
            for service_name in services:
                try:
                    result = subprocess.run(
                        ['systemctl', 'is-active', '--quiet', service_name],
                        capture_output=True,
                        timeout=2
                    )
                    status = "RUNNING" if result.returncode == 0 else "STOPPED"
                    output_lines.append(f"  {service_name}: {status}")
                except Exception:
                    output_lines.append(f"  {service_name}: UNKNOWN")
        else:
            output_lines.append("No services configured")
        
        output = "\n".join(output_lines)
        for line in output_lines:
            print(line)
        self._log_output(output)


def main():
    """Entry point for locker command"""
    parser = argparse.ArgumentParser(description='Lock-Down Service CLI')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Device commands
    subparsers.add_parser('get-android-serial', help='Get serial of connected Android device')
    set_serial_parser = subparsers.add_parser('set-android-serial', help='Configure Android device serial')
    set_serial_parser.add_argument('serial', nargs='?', help='Android device serial (optional, will prompt if not provided)')
    
    subparsers.add_parser('list-devices', help='List connected Android devices')
    
    # Service management
    add_service_parser = subparsers.add_parser('add-service', help='Add service to be managed (started on connection, stopped on disconnection)')
    add_service_parser.add_argument('service', help='Service name (e.g., ssh, nginx)')
    
    remove_service_parser = subparsers.add_parser('remove-service', help='Remove service from being managed')
    remove_service_parser.add_argument('service', help='Service name (e.g., ssh, nginx)')
    
    subparsers.add_parser('list-services', help='List all configured services')
    
    # Mode management
    set_mode_parser = subparsers.add_parser('set-mode', help='Set mode (permissive/enforcing)')
    set_mode_parser.add_argument('mode', nargs='?', choices=['permissive', 'enforcing'],
                                help='Mode: permissive (no locking) or enforcing (lock when device disconnected)')
    
    # Status
    subparsers.add_parser('get-status', help='Show current mode and service status')
    
    # Utility commands
    logs_parser = subparsers.add_parser('logs', help='Show service logs')
    logs_parser.add_argument('-n', '--lines', type=int, default=50,
                           help='Number of log lines to show')
    logs_parser.add_argument('-f', '--follow', action='store_true',
                           help='Follow log file (like tail -f)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    cli = LockCLI()
    
    if args.command == 'get-android-serial':
        cli.get_android_serial_cmd()
    elif args.command == 'set-android-serial':
        cli.set_android_serial(getattr(args, 'serial', None))
    elif args.command == 'list-devices':
        cli.list_devices_cmd()
    elif args.command == 'add-service':
        cli.add_service(args.service)
    elif args.command == 'remove-service':
        cli.remove_service(args.service)
    elif args.command == 'list-services':
        cli.list_services()
    elif args.command == 'set-mode':
        cli.set_mode(getattr(args, 'mode', None))
    elif args.command == 'get-status':
        cli.get_status()
    elif args.command == 'logs':
        cli.logs(args.lines, args.follow)


if __name__ == "__main__":
    main()
