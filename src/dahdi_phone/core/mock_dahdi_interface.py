"""
Mock implementation of the DAHDI hardware interface for development and testing.
Simulates basic phone operations, audio I/O, and event generation without requiring
actual DAHDI hardware. Uses FXS port and audio processor for consistent behavior
with the real interface.
"""

import asyncio
import struct
from datetime import datetime
from typing import Optional, Dict, Any, Set, Callable
import os
import random
from .dahdi_interface import (
    DAHDIInterface,
    DAHDIState,
    DAHDIIOError,
    DAHDIStateError,
    DAHDICommands,
)
from ..utils.logger import DAHDILogger, log_function_call
from ..api.models import DTMFEvent, PhoneEventTypes
from ..hardware.fxs import FXSPort, FXSConfig, FXSError
from ..core.audio_processor import AudioProcessor, AudioConfig

class MockDAHDIInterface(DAHDIInterface):
    """
    Mock implementation of DAHDIInterface for development and testing.
    Simulates hardware behavior without requiring actual DAHDI hardware.
    Uses FXS port and audio processor for consistent behavior.
    """
    def __init__(self, device_path: str, buffer_size: int = 320):
        # Initialize audio processor
        audio_config = AudioConfig(
            sample_rate=8000,  # Standard DAHDI sample rate
            frame_size=buffer_size,
            channels=1,  # Mono
            bit_depth=16  # 16-bit audio
        )
        self.audio_processor = AudioProcessor(audio_config)
        
        # Initialize base class
        super().__init__(device_path, buffer_size)
        
        self.log = DAHDILogger().get_logger(__name__).bind(
            device_path=device_path,
            buffer_size=buffer_size,
            component="MockDAHDIInterface"
        )
        self.log.info("mock_interface_init", message="Initializing Mock DAHDI interface")
        
        # Mock state
        self._mock_voltage = 48.0  # Normal line voltage
        self._mock_audio_buffer = bytearray(buffer_size)  # Buffer for mock audio data
        self._ring_task = None

    @log_function_call(level="DEBUG")
    async def initialize(self) -> None:
        """
        Initialize mock interface without requiring hardware.
        Simulates device setup and starts monitoring tasks.
        """
        try:
            self.log.info("mock_init_start", message="Initializing mock DAHDI interface")
            
            # Initialize basic state
            self.state = DAHDIState.ONHOOK
            self.event_queue = asyncio.Queue()
            
            # Initialize FXS port
            self.fxs_port = FXSPort(
                config=FXSConfig(channel=1),
                dahdi=self,  # Pass self for low-level operations
                audio=self.audio_processor
            )
            await self.fxs_port.initialize()
            
            # Start mock monitoring tasks
            self.voltage_monitor_task = asyncio.create_task(self._monitor_voltage())
            
            self.log.info("mock_init_complete", 
                         message="Mock DAHDI interface initialized successfully")
            
        except Exception as e:
            self.log.error("mock_init_failed",
                          message="Failed to initialize mock interface",
                          error=str(e),
                          exc_info=True)
            await self.cleanup()
            raise DAHDIIOError(f"Mock device initialization failed: {str(e)}") from e

    @log_function_call(level="DEBUG")
    async def cleanup(self) -> None:
        """Clean up mock resources"""
        try:
            self.log.info("mock_cleanup_start", message="Cleaning up mock interface")
            
            # Cancel monitoring tasks
            if self.voltage_monitor_task:
                self.voltage_monitor_task.cancel()
                
            # Cancel ring task if active
            if self._ring_task and not self._ring_task.done():
                self._ring_task.cancel()
                
            self.log.info("mock_cleanup_complete", 
                         message="Mock interface cleanup completed")
            
        except Exception as e:
            self.log.error("mock_cleanup_error",
                          message="Mock cleanup error",
                          error=str(e),
                          exc_info=True)

    async def _monitor_voltage(self) -> None:
        """Generate mock line voltage events"""
        while True:
            try:
                # Add small random fluctuation to voltage
                import random
                voltage_noise = random.uniform(-0.5, 0.5)
                self._mock_voltage = 48.0 + voltage_noise
                
                # Generate voltage event
                await self.event_queue.put({
                    'type': 'voltage',
                    'value': self._mock_voltage,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                self.log.debug("mock_voltage_reading",
                             message=f"Mock line voltage: {self._mock_voltage}V",
                             voltage=self._mock_voltage)
                             
                await asyncio.sleep(1)  # Update voltage every second
                
            except Exception as e:
                self.log.error("mock_voltage_monitor_error",
                             message="Mock voltage monitoring error",
                             error=str(e),
                             exc_info=True)
                await asyncio.sleep(5)  # Retry after error

    @log_function_call(level="DEBUG")
    async def ring(self, duration: int = 2000) -> None:
        """
        Simulate ring signal for specified duration.
        
        Args:
            duration: Ring duration in milliseconds
        """
        try:
            if self.state != DAHDIState.ONHOOK:
                self.log.error("mock_ring_state_error",
                             message="Cannot ring: line not on-hook",
                             current_state=self.state.name)
                raise DAHDIStateError("Cannot ring: line not on-hook")
            
            # Start ring signal
            self.state = DAHDIState.RINGING
            self._mock_voltage = 90.0  # Higher voltage during ring
            
            # Notify of ring start
            await self.event_queue.put({
                'type': PhoneEventTypes.RING_START,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Schedule ring stop
            async def stop_ring():
                await asyncio.sleep(duration / 1000)
                self.state = DAHDIState.ONHOOK
                self._mock_voltage = 48.0
                await self.event_queue.put({
                    'type': PhoneEventTypes.RING_STOP,
                    'timestamp': datetime.utcnow().isoformat()
                })
            
            self._ring_task = asyncio.create_task(stop_ring())
            
            self.log.info("mock_ring_started",
                         message=f"Mock ring signal started: {duration}ms",
                         duration=duration)
            
        except Exception as e:
            self.log.error("mock_ring_failed",
                          message="Mock ring operation failed",
                          error=str(e),
                          duration=duration,
                          exc_info=True)
            self.debug_stats['errors'] += 1
            raise

    @log_function_call(level="DEBUG")
    async def write_audio(self, audio_data: bytes) -> int:
        """
        Simulate writing audio data through FXS port.
        
        Args:
            audio_data: Raw audio bytes to write
            
        Returns:
            Number of bytes written
        """
        try:
            # Process through FXS port
            await self.fxs_port.play_audio(audio_data)
            data_len = len(audio_data)
            self.debug_stats['bytes_written'] += data_len
            
            self.log.debug("mock_audio_written",
                          message=f"Mock wrote {data_len} audio bytes",
                          bytes_written=data_len,
                          total_bytes=self.debug_stats['bytes_written'])
            return data_len
            
        except FXSError as e:
            self.log.error("mock_write_failed",
                          message="Mock audio write failed",
                          error=str(e),
                          data_size=len(audio_data),
                          exc_info=True)
            self.debug_stats['errors'] += 1
            raise DAHDIIOError("Failed to write mock audio data") from e

    @log_function_call(level="DEBUG")
    async def read_audio(self, size: int = 160) -> Optional[bytes]:
        """
        Generate mock audio data and process through audio processor.
        
        Args:
            size: Number of bytes to read
            
        Returns:
            Mock audio data bytes (silence)
        """
        try:
            # Generate silence (all zeros)
            audio_data = bytes(size)
            
            # Process through audio processor
            processed_audio, _ = await self.audio_processor.process_frame(audio_data)
            audio_data = processed_audio.tobytes()
            
            self.debug_stats['bytes_read'] += len(audio_data)
            
            self.log.debug("mock_audio_read",
                          message=f"Mock read {len(audio_data)} audio bytes",
                          bytes_read=len(audio_data),
                          total_bytes=self.debug_stats['bytes_read'])
            return audio_data
            
        except Exception as e:
            self.log.error("mock_read_failed",
                          message="Mock audio read failed",
                          error=str(e),
                          requested_size=size,
                          exc_info=True)
            self.debug_stats['errors'] += 1
            raise DAHDIIOError("Failed to read mock audio data") from e

    async def _ioctl(self, command: DAHDICommands, data: bytes) -> bytes:
        """
        Simulate ioctl commands.
        
        Args:
            command: DAHDI command code
            data: Command data bytes
            
        Returns:
            Mock response data bytes
        """
        try:
            self.debug_stats['ioctl_calls'] += 1
            
            # Handle different commands
            if command == DAHDICommands.LINE_VOLTAGE:
                return struct.pack('f', self._mock_voltage)
            elif command == DAHDICommands.GET_PARAMS:
                # Return mock parameters
                return struct.pack('IIII', 0, 0, 0, 0)  # Adjust structure as needed
            elif command == DAHDICommands.SET_PARAMS:
                # Accept any parameters
                return data
            
            # For other commands, just return empty success
            return struct.pack('I', 0)
            
        except Exception as e:
            self.log.error("mock_ioctl_failed",
                          message=f"Mock ioctl failed: {command.name}",
                          command=command.name,
                          error=str(e),
                          exc_info=True)
            self.debug_stats['errors'] += 1
            raise DAHDIIOError(f"Mock ioctl command {command.name} failed") from e
