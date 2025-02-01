# src/dahdi_phone/core/interfaces.py
"""
Core interfaces and types for DAHDI hardware communication.
Defines base classes, enums, and exceptions used by both the low-level DAHDI interface
and high-level FXS implementation.
"""

from enum import IntEnum
from typing import Protocol, Dict, Any, Optional
import asyncio

class DAHDIIOError(Exception):
    """Custom exception for DAHDI I/O operations"""
    pass

class DAHDIStateError(Exception):
    """Custom exception for invalid state transitions"""
    pass

class DAHDITimeout(Exception):
    """Custom exception for operation timeouts"""
    pass

class DAHDICommands(IntEnum):
    """DAHDI ioctl command codes"""
    GET_PARAMS = 0x40024801
    SET_PARAMS = 0x40024802
    HOOK_STATE = 0x40044803
    RING_START = 0x40044804
    RING_STOP = 0x40044805
    GET_BUFINFO = 0x40044806
    SET_BUFINFO = 0x40044807
    AUDIO_GAIN = 0x40044808
    LINE_VOLTAGE = 0x40044809

class DAHDIState(IntEnum):
    """DAHDI hardware states"""
    ONHOOK = 0
    OFFHOOK = 1
    RINGING = 2
    BUSY = 3
    DIALING = 4
    ERROR = 5

class DAHDIHardwareInterface(Protocol):
    """Protocol defining the interface for DAHDI hardware communication"""
    device_path: str
    device_fd: Optional[int]
    state: DAHDIState
    event_queue: asyncio.Queue

    async def initialize(self) -> None:
        """Initialize hardware interface"""
        ...

    async def cleanup(self) -> None:
        """Clean up hardware resources"""
        ...

    async def _ioctl(self, command: DAHDICommands, data: bytes) -> bytes:
        """Execute ioctl command"""
        ...

    async def write_audio(self, audio_data: bytes) -> int:
        """Write audio data to device"""
        ...

    async def read_audio(self, size: int = 160) -> Optional[bytes]:
        """Read audio data from device"""
        ...

    async def get_debug_info(self) -> Dict[str, Any]:
        """Get debug statistics and state information"""
        ...
