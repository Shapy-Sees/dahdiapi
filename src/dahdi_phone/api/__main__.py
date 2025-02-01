# src/api/__main__.py
"""
Main entry point for the DAHDI Phone API service.
Handles startup configuration and server initialization.
"""

import sys
import logging
from pathlib import Path
from ..utils.logger import DAHDILogger, LoggerConfig
from ..utils.config import Config, ConfigurationError

def main():
    """
    Main entry point for the API service.
    Configures logging and starts the server.
    """
    # Initialize basic logging first
    basic_logger = logging.getLogger(__name__)
    basic_logger.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s - %(message)s'))
    basic_logger.addHandler(console_handler)
    
    try:
        basic_logger.debug("Starting DAHDI Phone API initialization")
        
        # Load configuration
        basic_logger.debug("Creating configuration manager")
        config = Config()
        
        # Get the package root directory (2 levels up from __main__.py)
        package_root = Path(__file__).parent.parent
        basic_logger.debug(f"Package root directory: {package_root}")
        
        # Always start with default configuration
        default_config = package_root / "config" / "default.yml"
        basic_logger.debug(f"Loading default configuration from {default_config}")
        config.load(default_config)
        basic_logger.debug("Successfully loaded default configuration")
        
        # Try to load and merge custom configuration
        config_paths = [
            package_root / "config" / "config.yml",  # Package config (preferred)
            Path("/etc/dahdi_phone/config.yml"),    # System-wide config (fallback)
        ]
        
        for config_path in config_paths:
            try:
                basic_logger.debug(f"Attempting to load custom configuration from: {config_path}")
                config.load(config_path)
                basic_logger.debug(f"Successfully loaded custom configuration from: {config_path}")
                break
            except ConfigurationError:
                basic_logger.debug(f"No custom configuration found at: {config_path}")
                continue

        # Configure main logger
        basic_logger.debug("Initializing DAHDI logging system")
        logger = DAHDILogger()
        
        # Ensure log directory exists with proper permissions
        if config.logging.output:
            import os
            log_dir = os.path.dirname(config.logging.output)
            basic_logger.debug(f"Setting up log directory: {log_dir}")
            try:
                # Create directory with full permissions
                os.makedirs(log_dir, mode=0o777, exist_ok=True)
                # Create log file if it doesn't exist
                if not os.path.exists(config.logging.output):
                    with open(config.logging.output, 'a'):
                        pass
                # Set permissions on log file
                os.chmod(config.logging.output, 0o666)
                basic_logger.debug(f"Created or verified log directory and file: {config.logging.output}")
            except PermissionError:
                # Fall back to a local logs directory if we can't write to system path
                basic_logger.debug(f"Permission denied for log directory: {log_dir}")
                log_dir = "logs"
                basic_logger.debug(f"Falling back to local log directory: {log_dir}")
                os.makedirs(log_dir, mode=0o777, exist_ok=True)
                config.logging.output = os.path.join(log_dir, "dahdi_phone.log")
                with open(config.logging.output, 'a'):
                    pass
                os.chmod(config.logging.output, 0o666)
                basic_logger.debug(f"Using fallback log file: {config.logging.output}")
            
        # Configure the main logger
        log_config = LoggerConfig(
            level=config.logging.level,
            format=config.logging.format,
            output_file=config.logging.output,
            max_bytes=10_485_760,  # 10MB
            backup_count=5
        )
        basic_logger.debug(f"Configuring DAHDI logger with level={config.logging.level}, format={config.logging.format}")
        logger.configure(log_config)
        
        # Get configured logger for this module
        module_logger = logger.get_logger(__name__)
        module_logger.info("DAHDI logging system initialized")
        module_logger.info("Initializing DAHDI Phone API service...")
        
        # Import server module after logger is configured
        module_logger.debug("Importing server module")
        from .server import run_server
        
        # Start server
        module_logger.debug("Starting server")
        run_server()
        module_logger.debug("Server startup initiated")

    except ConfigurationError as e:
        basic_logger.error(f"Configuration error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        basic_logger.error(f"Startup failed: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
