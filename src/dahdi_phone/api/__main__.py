# src/api/__main__.py
"""
Main entry point for the DAHDI Phone API service.
Handles startup configuration and server initialization.
"""

import sys
import logging
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
        
        # Load configuration first
        basic_logger.debug("Creating configuration manager")
        config = Config()
        # Load config from project directory or system-wide location
        config_paths = [
            "config/config.yml",            # Project directory config (preferred)
            "/etc/dahdi_phone/config.yml",  # System-wide config (fallback)
        ]
        
        for config_path in config_paths:
            try:
                basic_logger.debug(f"Attempting to load configuration from: {config_path}")
                config.load(config_path)
                basic_logger.debug(f"Successfully loaded configuration from: {config_path}")
                break
            except ConfigurationError:
                basic_logger.debug(f"Failed to load configuration from: {config_path}")
                if config_path == config_paths[-1]:  # If this was the last path to try
                    # No custom config found, fall back to default.yml
                    basic_logger.debug("No custom configuration found, falling back to default.yml")
                    config.load("config/default.yml")
                    basic_logger.debug("Successfully loaded default configuration")
                    break

        # Configure main logger
        basic_logger.debug("Initializing DAHDI logging system")
        logger = DAHDILogger()
        
        # Ensure log directory exists if output file is specified
        if config.logging.output:
            import os
            log_dir = os.path.dirname(config.logging.output)
            basic_logger.debug(f"Setting up log directory: {log_dir}")
            try:
                os.makedirs(log_dir, exist_ok=True)
                basic_logger.debug(f"Created or verified log directory: {log_dir}")
            except PermissionError:
                # Fall back to a local logs directory if we can't write to system path
                basic_logger.debug(f"Permission denied for log directory: {log_dir}")
                log_dir = "logs"
                basic_logger.debug(f"Falling back to local log directory: {log_dir}")
                os.makedirs(log_dir, exist_ok=True)
                config.logging.output = os.path.join(log_dir, "api.log")
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
