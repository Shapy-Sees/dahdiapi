# src/dahdi_phone/__init__.py
"""
DAHDI Phone API package.
Provides REST and WebSocket APIs for controlling DAHDI telephony hardware.
"""

import logging
from .utils.logger import DAHDILogger

# Initialize package-level logger
logger = DAHDILogger().get_logger(__name__)

# Package metadata
__version__ = "1.0.0"
__author__ = "DAHDI Phone API Team"
__description__ = "REST and WebSocket API for DAHDI telephony hardware"

logger.info(f"DAHDI Phone API {__version__} initialized")