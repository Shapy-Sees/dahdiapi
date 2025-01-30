# src/__init__.py
"""
DAHDI Phone API package.
Main package initialization for the DAHDI Phone API project.
"""

from . import api
from . import core
from . import hardware
from . import utils

__version__ = "1.0.0"

# src/dahdi_phone/api/__init__.py
"""
API package initialization.
Contains REST and WebSocket API implementations.
"""

from .server import run_server
from .models import PhoneState, PhoneStatus

# src/dahdi_phone/core/__init__.py
"""
Core package initialization.
Contains core DAHDI interface and processing components.
"""

from .dahdi_interface import DAHDIInterface
from .audio_processor import AudioProcessor

# src/dahdi_phone/hardware/__init__.py
"""
Hardware package initialization.
Contains hardware abstraction layer components.
"""

from .fxs import FXSPort
from .audio_buffer import AudioBuffer

# src/dahdi_phone/utils/__init__.py
"""
Utilities package initialization.
Contains shared utility functions and classes.
"""

from .config import Config
from .logger import DAHDILogger, log_function_call