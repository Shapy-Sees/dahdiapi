# src/hardware/fxs.py
"""
FXS (Foreign Exchange Station) hardware interface implementation.
Provides high-level interface to FXS ports through DAHDI, handling voltage control,
ring generation, audio routing, and hardware state management.
Includes comprehensive logging and error handling for hardware operations.
"""

import asyncio
import logging
from enum import IntEnum
from typing import Optional, Dict, Any
from dataclasses import dataclass

from ..utils.logger import DAHDILogger, log_function_call
from ..utils.config import Config
from ..core.dahdi_interface import DAHDIInterface, DAHDIIOError
from ..core.audio_processor import AudioProcessor, AudioProcessingError

# Get structured logger
logger = DAHDILogger().get_logger(__name__)

class FXSError(Exception):
    """Custom exception for FXS-specific errors"""
    pass

class RingPattern(IntEnum):
    """Standard telephone ring patterns"""
    NORMAL = 0      # Standard 2s on, 4s off
    DISTINCTIVE1 = 1  # Short-short-long
    DISTINCTIVE2 = 2  # Short-long-short
    CONTINUOUS = 3    # Continuous ring

# DAHDI-specific command codes for voltage control
# These match the Linux kernel DAHDI driver definitions
class DAHDIVoltageCommands(IntEnum):
    """DAHDI voltage control command codes"""
    DAHDI_SET_VOLTAGE = 0x40044001   # Set line voltage
    DAHDI_GET_VOLTAGE = 0x80044002   # Get line voltage
    DAHDI_RING_VOLTAGE = 0x40044003  # Set ring voltage
    DAHDI_BATT_VOLTAGE = 0x40044004  # Set battery voltage

# Voltage control command data structures
class VoltageData(ctypes.Structure):
    """C struct for voltage control data"""
    _fields_ = [
        ("voltage", ctypes.c_float),    # Voltage value in volts
        ("channel", ctypes.c_int),      # DAHDI channel number
        ("flags", ctypes.c_uint32)      # Control flags
    ]

@dataclass
class FXSConfig:
    """FXS port configuration parameters"""
    channel: int
    idle_voltage: float = 48.0
    ring_voltage: float = 90.0
    ring_frequency: float = 20.0  # Hz
    ring_pattern: RingPattern = RingPattern.NORMAL

class FXSPort:
    """
    High-level interface to FXS port hardware.
    Manages phone line states, voltage control, and audio routing.
    """
    def __init__(self, config: FXSConfig, dahdi: DAHDIInterface, audio: AudioProcessor):
        self.config = config
        self.dahdi = dahdi
        self.audio = audio
        self._ring_task: Optional[asyncio.Task] = None
        self._monitoring = False
        
        # Initialize logger with context
        self.log = logger.bind(
            channel=config.channel,
            component="FXSPort"
        )
        
        self._setup_logging()
        self.log.info("fxs_port_init", message="Initializing FXS port")

    def _setup_logging(self) -> None:
        """Configure FXS-specific logging"""
        self.debug_stats = {
            'ring_cycles': 0,
            'off_hook_events': 0,
            'voltage_changes': 0,
            'audio_errors': 0,
            'hardware_errors': 0
        }
        self.log.debug("debug_stats_initialized", 
                      message="FXS debug statistics initialized",
                      initial_stats=self.debug_stats)

    @log_function_call(level="DEBUG")
    async def initialize(self) -> None:
        """Initialize FXS port hardware"""
        try:
            self.log.info("initialization_start", message="Starting FXS port initialization")
            
            # Set initial line voltage
            await self._set_voltage(self.config.idle_voltage)
            
            # Start monitoring task
            self._monitoring = True
            asyncio.create_task(self._monitor_hardware())
            
            self.log.info("initialization_complete", 
                         message="FXS port initialized successfully")
            
        except Exception as e:
            self.log.error("initialization_failed",
                          message="Failed to initialize FXS port",
                          error=str(e),
                          exc_info=True)
            self.debug_stats['hardware_errors'] += 1
            raise FXSError(f"FXS initialization failed: {str(e)}") from e

    @log_function_call(level="DEBUG")
    async def cleanup(self) -> None:
        """Clean up resources and stop monitoring"""
        try:
            self.log.info("cleanup_start", message="Starting FXS port cleanup")
            
            # Stop monitoring
            self._monitoring = False
            
            # Cancel ring task if active
            if self._ring_task:
                self._ring_task.cancel()
                
            # Reset line voltage
            await self._set_voltage(self.config.idle_voltage)
            
            self.log.info("cleanup_complete", message="FXS port cleanup completed")
            
        except Exception as e:
            self.log.error("cleanup_failed",
                          message="Cleanup failed",
                          error=str(e),
                          exc_info=True)

    async def _monitor_hardware(self) -> None:
        """Monitor hardware state and voltage"""
        while self._monitoring:
            try:
                # Check line voltage
                voltage = await self._get_voltage()
                self.log.debug("voltage_reading",
                             message=f"Line voltage: {voltage}V",
                             voltage=voltage)
                
                # Check for off-hook state
                if voltage < self.config.idle_voltage * 0.8:  # 20% voltage drop indicates off-hook
                    self.debug_stats['off_hook_events'] += 1
                    self.log.info("off_hook_detected",
                                message="Off-hook state detected",
                                voltage=voltage)
                    
                await asyncio.sleep(0.1)  # Check every 100ms
                
            except Exception as e:
                self.log.error("monitoring_error",
                             message="Hardware monitoring error",
                             error=str(e),
                             exc_info=True)
                self.debug_stats['hardware_errors'] += 1
                await asyncio.sleep(1)  # Longer delay after error

    @log_function_call(level="DEBUG")
    async def ring(self, pattern: RingPattern = RingPattern.NORMAL, duration: int = 2000) -> None:
        """
        Generate ring signal with specified pattern.
        
        Args:
            pattern: Ring pattern to generate
            duration: Total ring duration in milliseconds
        """
        try:
            self.log.info("ring_start",
                         message="Starting ring signal",
                         pattern=pattern.name,
                         duration=duration)
            
            if self._ring_task and not self._ring_task.done():
                self.log.warning("ring_busy",
                               message="Ring already in progress, canceling previous")
                self._ring_task.cancel()
                
            self._ring_task = asyncio.create_task(
                self._generate_ring_pattern(pattern, duration)
            )
            
            await self._ring_task
            
            self.log.info("ring_complete",
                         message="Ring signal completed",
                         pattern=pattern.name)
            
        except asyncio.CancelledError:
            self.log.info("ring_cancelled", message="Ring signal cancelled")
        except Exception as e:
            self.log.error("ring_failed",
                          message="Ring signal failed",
                          error=str(e),
                          exc_info=True)
            self.debug_stats['hardware_errors'] += 1
            raise FXSError(f"Ring generation failed: {str(e)}") from e

    async def _generate_ring_pattern(self, pattern: RingPattern, duration: int) -> None:
        """Generate specific ring pattern"""
        end_time = asyncio.get_event_loop().time() + (duration / 1000)
        
        try:
            while asyncio.get_event_loop().time() < end_time:
                if pattern == RingPattern.NORMAL:
                    await self._ring_cycle(2000, 4000)  # 2s on, 4s off
                elif pattern == RingPattern.DISTINCTIVE1:
                    await self._ring_cycle(500, 500)    # Short
                    await self._ring_cycle(500, 500)    # Short
                    await self._ring_cycle(2000, 4000)  # Long
                elif pattern == RingPattern.DISTINCTIVE2:
                    await self._ring_cycle(500, 500)    # Short
                    await self._ring_cycle(2000, 500)   # Long
                    await self._ring_cycle(500, 4000)   # Short
                elif pattern == RingPattern.CONTINUOUS:
                    await self._ring_cycle(5000, 100)   # Almost continuous
                    
                self.debug_stats['ring_cycles'] += 1
                
        finally:
            # Ensure voltage is reset
            await self._set_voltage(self.config.idle_voltage)

    async def _ring_cycle(self, on_time: int, off_time: int) -> None:
        """Execute single ring cycle"""
        try:
            # Set ring voltage
            await self._set_voltage(self.config.ring_voltage)
            await asyncio.sleep(on_time / 1000)
            
            # Reset to idle voltage
            await self._set_voltage(self.config.idle_voltage)
            await asyncio.sleep(off_time / 1000)
            
        except Exception as e:
            self.log.error("ring_cycle_failed",
                          message="Ring cycle failed",
                          error=str(e),
                          exc_info=True)
            raise

    async def _set_voltage(self, voltage: float) -> None:
        """
        Set line voltage using DAHDI ioctl calls.
        
        Args:
            voltage: Desired line voltage in volts
            
        Raises:
            FXSError: If voltage setting fails
        """
        try:
            # Prepare voltage control data structure
            voltage_data = VoltageData()
            voltage_data.voltage = voltage
            voltage_data.channel = self.config.channel
            voltage_data.flags = 0  # Normal voltage set operation
            
            # Convert to bytes for ioctl
            data_bytes = bytes(voltage_data)
            
            # Determine appropriate command based on voltage type
            if voltage == self.config.ring_voltage:
                command = DAHDIVoltageCommands.DAHDI_RING_VOLTAGE
            else:
                command = DAHDIVoltageCommands.DAHDI_SET_VOLTAGE
            
            # Execute ioctl call through DAHDI interface
            await self.dahdi._ioctl(command, data_bytes)
            
            self.debug_stats['voltage_changes'] += 1
            
            self.log.debug("voltage_set",
                          message=f"Set line voltage to {voltage}V",
                          voltage=voltage,
                          command=command.name,
                          channel=self.config.channel)
            
        except DAHDIIOError as e:
            self.log.error("voltage_set_failed",
                          message="Failed to set line voltage",
                          voltage=voltage,
                          error=str(e),
                          exc_info=True)
            raise FXSError(f"Failed to set voltage to {voltage}V") from e

    async def _get_voltage(self) -> float:
        """
        Get current line voltage using DAHDI ioctl call.
        
        Returns:
            Current line voltage in volts
            
        Raises:
            FXSError: If voltage reading fails
        """
        try:
            # Prepare voltage query structure
            query_data = VoltageData()
            query_data.channel = self.config.channel
            query_data.flags = 0
            
            # Convert to bytes for ioctl
            data_bytes = bytes(query_data)
            
            # Execute ioctl call
            result_bytes = await self.dahdi._ioctl(
                DAHDIVoltageCommands.DAHDI_GET_VOLTAGE, 
                data_bytes
            )
            
            # Convert result back to voltage data structure
            result_data = VoltageData.from_buffer_copy(result_bytes)
            voltage = result_data.voltage
            
            self.log.debug("voltage_read",
                          message=f"Read line voltage: {voltage}V",
                          voltage=voltage,
                          channel=self.config.channel)
            
            return voltage
            
        except DAHDIIOError as e:
            self.log.error("voltage_read_failed",
                          message="Failed to read line voltage",
                          error=str(e),
                          exc_info=True)
            raise FXSError("Failed to read line voltage") from e


    @log_function_call(level="DEBUG")
    async def play_audio(self, audio_data: bytes) -> None:
        """
        Play audio through FXS port.
        
        Args:
            audio_data: Raw audio bytes to play
        """
        try:
            # Process audio through audio processor
            processed_audio, stats = await self.audio.process_frame(audio_data)
            
            # Write to hardware
            await self.dahdi.write_audio(processed_audio.tobytes())
            
            self.log.debug("audio_played",
                          message="Audio data played",
                          bytes_played=len(audio_data),
                          audio_stats=stats)
            
        except (AudioProcessingError, DAHDIIOError) as e:
            self.log.error("audio_play_failed",
                          message="Failed to play audio",
                          error=str(e),
                          exc_info=True)
            self.debug_stats['audio_errors'] += 1
            raise FXSError(f"Audio playback failed: {str(e)}") from e

    async def get_debug_info(self) -> dict:
        """Get debug statistics and state information"""
        debug_info = {
            **self.debug_stats,
            'ring_active': bool(self._ring_task and not self._ring_task.done()),
            'monitoring_active': self._monitoring,
            'dahdi_stats': await self.dahdi.get_debug_info(),
            'audio_stats': await self.audio.get_debug_info()
        }
        self.log.debug("debug_info_retrieved",
                      message="Retrieved debug information",
                      debug_info=debug_info)
        return debug_info