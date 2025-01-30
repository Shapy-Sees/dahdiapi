# src/api/__main__.py
"""
Main entry point for the DAHDI Phone API service.
Handles startup configuration and server initialization.
"""

import sys
import logging
from .server import run_server
from ..utils.logger import DAHDILogger
from ..utils.config import Config, ConfigurationError

def main():
    """
    Main entry point for the API service.
    Configures logging and starts the server.
    """
    try:
        # Initialize logging
        logger = logging.getLogger(__name__)
        logger.info("Initializing DAHDI Phone API service...")

        # Load configuration
        config = Config()
        config.load("/etc/dahdi_phone/config.yml")

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