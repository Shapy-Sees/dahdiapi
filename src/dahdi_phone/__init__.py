"""
DAHDI Phone API package.
Main package initialization for the DAHDI Phone API project.
"""

from .utils.logger import DAHDILogger, LoggerConfig

# Configure basic logger before importing modules
logger = DAHDILogger()
log_config = LoggerConfig(
    level="INFO",
    format="json",
    output_file="logs/dahdi_phone.log"
)
logger.configure(log_config)

# Now it's safe to import submodules
from . import utils
from . import hardware
from . import core
from . import api

__version__ = "1.0.0"
