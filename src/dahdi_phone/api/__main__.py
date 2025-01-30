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
    try:
        # Load configuration first
        config = Config()
        config.load("/etc/dahdi_phone/config.yml")

        # Configure logger before any other imports
        logger = DAHDILogger()
        log_config = LoggerConfig(
            level=config.logging.level,
            format=config.logging.format,
            output_file=config.logging.output,
            max_bytes=10_485_760,  # 10MB
            backup_count=5
        )
        logger.configure(log_config)

        # Get logger for this module
        module_logger = logger.get_logger(__name__)
        module_logger.info("Initializing DAHDI Phone API service...")

        # Import server module after logger is configured
        from .server import run_server
        
        # Start server
        run_server()

    except ConfigurationError as e:
        logger.error(f"Configuration error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
