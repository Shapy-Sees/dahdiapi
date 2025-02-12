# src/dahdi_phone/core/dahdi_interface.py
"""
Core DAHDI hardware interface implementation.
Provides communication with DAHDI hardware through the FXS interface and manages
hardware state, audio streaming, and event handling. This is the primary interface
between the API and the physical telephony hardware. Includes DTMF event handling
and WebSocket event forwarding.
"""

import os
import fcntl
import asyncio
import struct
from typing import Optional, Dict, Any, Set, Callable
from datetime import datetime
import structlog
from ..utils.logger import DAHDILogger, log_function_call
from ..api.models import DTMFEvent, PhoneEventTypes
from ..core.audio_processor import AudioProcessor, AudioConfig
from .interfaces import (
    DAHDIHardwareInterface,
    DAHDIIOError,
    DAHDIStateError,
    DAHDITimeout,
    DAHDICommands,
    DAHDIState,
)

class DAHDIInterface(DAHDIHardwareInterface):
    """
    Primary interface to DAHDI hardware.
    Manages device communication through FXSPort, handles state and events.
    Includes DTMF event handling and WebSocket event forwarding.
    """
    def __init__(self, device_path: str, buffer_size: int = 320):
        self.device_path = device_path
        self.device_fd = None
        self.state = DAHDIState.ONHOOK
        self.event_queue = asyncio.Queue()
        self.voltage_monitor_task = None
        
        # Initialize audio processor
        audio_config = AudioConfig(
            sample_rate=8000,  # Standard DAHDI sample rate
            frame_size=buffer_size,
            channels=1,  # Mono
            bit_depth=16  # 16-bit audio
        )
        self.audio_processor = AudioProcessor(audio_config)
        
        # Initialize FXS port
        fxs_config = FXSConfig(
            channel=1,  # Default channel
            idle_voltage=48.0,
            ring_voltage=90.0
        )
        self.fxs_port = None  # Will be initialized in initialize()
        
        # WebSocket event subscribers
        self._websocket_subscribers: Set[Callable[[Dict[str, Any]], None]] = set()
        
        # Initialize structured logger with context
        self.log = DAHDILogger().get_logger(__name__).bind(
            device_path=device_path,
            buffer_size=buffer_size,
            component="DAHDIInterface"
        )
        
        self._setup_logging()
        self.log.info("dahdi_interface_init", message="Initializing DAHDI interface")

    def _setup_logging(self):
        """Configure interface-specific logging"""
        self.debug_stats = {
            'ioctl_calls': 0,
            'bytes_read': 0,
            'bytes_written': 0,
            'errors': 0,
            'state_changes': 0,
            'dtmf_events': 0,
            'websocket_notifications': 0
        }
        self.log.debug("debug_stats_initialized", 
                      message="DAHDI interface debug statistics initialized",
                      initial_stats=self.debug_stats)

    @log_function_call(level="DEBUG")
    async def initialize(self) -> None:
        """
        Initialize DAHDI device through FXS interface and start monitoring tasks.
        Opens device file and configures initial hardware state.
        """
        try:
            self.log.info("device_open_start", message="Opening DAHDI device")
            
            # Check if device exists first
            if not os.path.exists(self.device_path):
                error_msg = (
                    f"DAHDI device not found: {self.device_path}\n"
                    "Please ensure DAHDI hardware is properly connected and configured.\n"
                    "The DAHDI device file must be present at the configured path."
                )
                self.log.error("device_not_found", message=error_msg)
                raise DAHDIIOError(error_msg)
            
            # Open device for ioctl operations
            self.device_fd = os.open(self.device_path, os.O_RDWR)
            
            # Set non-blocking mode
            flags = fcntl.fcntl(self.device_fd, fcntl.F_GETFL)
            fcntl.fcntl(self.device_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            
            # Initialize FXS port
            self.fxs_port = FXSPort(
                config=FXSConfig(channel=1),
                dahdi=self,  # Pass self for low-level operations
                audio=self.audio_processor
            )
            await self.fxs_port.initialize()
            
            # Start monitoring tasks
            self.voltage_monitor_task = asyncio.create_task(self._monitor_voltage())
            
            self.log.info("init_complete", 
                         message="DAHDI interface initialized successfully",
                         device_fd=self.device_fd)
            
        except Exception as e:
            self.log.error("init_failed",
                          message="Failed to initialize DAHDI device",
                          error=str(e),
                          exc_info=True)
            await self.cleanup()
            raise DAHDIIOError(f"Device initialization failed: {str(e)}") from e

    @log_function_call(level="DEBUG")
    async def subscribe_websocket(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Subscribe to WebSocket events.
        
        Args:
            callback: Function to call for WebSocket events
        """
        self._websocket_subscribers.add(callback)
        self.log.debug("websocket_subscriber_added",
                      message="Added WebSocket subscriber",
                      total_subscribers=len(self._websocket_subscribers))

    @log_function_call(level="DEBUG")
    async def unsubscribe_websocket(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Unsubscribe from WebSocket events.
        
        Args:
            callback: Previously registered callback function
        """
        self._websocket_subscribers.discard(callback)
        self.log.debug("websocket_subscriber_removed",
                      message="Removed WebSocket subscriber",
                      total_subscribers=len(self._websocket_subscribers))

    async def _notify_websocket_subscribers(self, event: Dict[str, Any]) -> None:
        """
        Notify all WebSocket subscribers of an event.
        
        Args:
            event: Event data to broadcast
        """
        notification_tasks = []
        
        for callback in self._websocket_subscribers:
            task = asyncio.create_task(callback(event))
            notification_tasks.append(task)
            
        if notification_tasks:
            self.debug_stats['websocket_notifications'] += len(notification_tasks)
            await asyncio.gather(*notification_tasks, return_exceptions=True)
            
            self.log.debug("websocket_notifications_sent",
                          message="Notified WebSocket subscribers",
                          event_type=event.get('type'),
                          notifications=len(notification_tasks))

    @log_function_call(level="DEBUG")
    async def handle_dtmf_event(self, event: DTMFEvent) -> None:
        """
        Handle DTMF event from audio processor and forward to WebSocket.
        
        Args:
            event: DTMF event from audio processor
        """
        try:
            self.debug_stats['dtmf_events'] += 1
            
            # Create WebSocket event
            websocket_event = {
                'type': PhoneEventTypes.DTMF,
                'digit': event.digit,
                'duration': event.duration,
                'signal_level': event.signal_level,
                'timestamp': event.timestamp.isoformat()
            }
            
            # Add to event queue for any direct subscribers
            await self.event_queue.put(websocket_event)
            
            # Notify WebSocket subscribers
            await self._notify_websocket_subscribers(websocket_event)
            
            self.log.info("dtmf_event_processed",
                         message=f"DTMF event processed: {event.digit}",
                         event=websocket_event)
            
        except Exception as e:
            self.log.error("dtmf_event_processing_failed",
                          message="Failed to process DTMF event",
                          error=str(e),
                          exc_info=True)
            self.debug_stats['errors'] += 1
    
    @log_function_call(level="DEBUG")
    async def cleanup(self) -> None:
        """Clean up resources and close device"""
        try:
            self.log.info("cleanup_start", message="Cleaning up DAHDI interface")
            
            # Clean up FXS port
            if self.fxs_port:
                await self.fxs_port.cleanup()
            
            # Cancel monitoring tasks
            if self.voltage_monitor_task:
                self.voltage_monitor_task.cancel()
                
            # Close device
            if self.device_fd is not None:
                os.close(self.device_fd)
                self.device_fd = None
                
            self.log.info("cleanup_complete", message="DAHDI interface cleanup completed")
            
        except Exception as e:
            self.log.error("cleanup_error",
                          message="Cleanup error",
                          error=str(e),
                          exc_info=True)

    async def _configure_device(self) -> None:
        """Configure initial device parameters"""
        try:
            # Get current parameters
            params = await self._ioctl(DAHDICommands.GET_PARAMS, struct.pack('I', 0))
            
            # Modify parameters as needed
            # (Parameters structure depends on specific DAHDI version)
            
            # Set parameters
            await self._ioctl(DAHDICommands.SET_PARAMS, params)
            
            self.log.debug("device_configured", message="Device parameters configured")
            
        except Exception as e:
            self.log.error("config_failed",
                          message="Device configuration failed",
                          error=str(e),
                          exc_info=True)
            raise DAHDIIOError("Failed to configure device parameters") from e

    @log_function_call(level="DEBUG")
    async def ring(self, duration: int = 2000) -> None:
        """
        Generate ring signal for specified duration using FXS port.
        
        Args:
            duration: Ring duration in milliseconds
        """
        try:
            if self.state != DAHDIState.ONHOOK:
                self.log.error("ring_state_error",
                             message="Cannot ring: line not on-hook",
                             current_state=self.state.name)
                raise DAHDIStateError("Cannot ring: line not on-hook")
            
            self.state = DAHDIState.RINGING
            await self.fxs_port.ring(duration=duration)
            self.state = DAHDIState.ONHOOK
            
            self.log.info("ring_complete",
                         message=f"Ring signal completed: {duration}ms",
                         duration=duration)
            
        except FXSError as e:
            self.log.error("ring_failed",
                          message="Ring operation failed",
                          error=str(e),
                          duration=duration,
                          exc_info=True)
            self.debug_stats['errors'] += 1
            raise DAHDIIOError(f"Ring failed: {str(e)}") from e

    @log_function_call(level="DEBUG")
    async def write_audio(self, audio_data: bytes) -> int:
        """
        Write audio data to device through FXS port.
        
        Args:
            audio_data: Raw audio bytes to write
            
        Returns:
            Number of bytes written
        """
        try:
            await self.fxs_port.play_audio(audio_data)
            bytes_written = len(audio_data)
            self.debug_stats['bytes_written'] += bytes_written
            
            self.log.debug("audio_written",
                          message=f"Wrote {bytes_written} audio bytes",
                          bytes_written=bytes_written,
                          total_bytes=self.debug_stats['bytes_written'])
            return bytes_written
            
        except FXSError as e:
            self.log.error("write_failed",
                          message="Audio write failed",
                          error=str(e),
                          data_size=len(audio_data),
                          exc_info=True)
            self.debug_stats['errors'] += 1
            raise DAHDIIOError("Failed to write audio data") from e

    @log_function_call(level="DEBUG")
    async def read_audio(self, size: int = 160) -> Optional[bytes]:
        """
        Read audio data from device through FXS port.
        
        Args:
            size: Number of bytes to read
            
        Returns:
            Audio data bytes or None if no data available
        """
        try:
            # Read from device
            audio_data = os.read(self.device_fd, size)
            if audio_data:
                # Process through audio processor
                processed_audio, _ = await self.audio_processor.process_frame(audio_data)
                audio_data = processed_audio.tobytes()
                
            self.debug_stats['bytes_read'] += len(audio_data) if audio_data else 0
            
            self.log.debug("audio_read",
                          message=f"Read {len(audio_data) if audio_data else 0} audio bytes",
                          bytes_read=len(audio_data) if audio_data else 0,
                          total_bytes=self.debug_stats['bytes_read'])
            return audio_data
            
        except BlockingIOError:
            # No data available
            return None
        except Exception as e:
            self.log.error("read_failed",
                          message="Audio read failed",
                          error=str(e),
                          requested_size=size,
                          exc_info=True)
            self.debug_stats['errors'] += 1
            raise DAHDIIOError("Failed to read audio data") from e

    async def _monitor_voltage(self) -> None:
        """Monitor line voltage and generate events"""
        while True:
            try:
                # Read line voltage
                voltage_data = await self._ioctl(DAHDICommands.LINE_VOLTAGE, struct.pack('I', 0))
                voltage = struct.unpack('f', voltage_data)[0]
                
                # Generate voltage event
                await self.event_queue.put({
                    'type': 'voltage',
                    'value': voltage,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                self.log.debug("voltage_reading",
                             message=f"Line voltage: {voltage}V",
                             voltage=voltage)
                await asyncio.sleep(1)  # Check voltage every second
                
            except Exception as e:
                self.log.error("voltage_monitor_error",
                             message="Voltage monitoring error",
                             error=str(e),
                             exc_info=True)
                await asyncio.sleep(5)  # Retry after error

    async def _ioctl(self, command: DAHDICommands, data: bytes) -> bytes:
        """
        Execute ioctl command with error handling.
        
        Args:
            command: DAHDI command code
            data: Command data bytes
            
        Returns:
            Response data bytes
        """
        try:
            self.debug_stats['ioctl_calls'] += 1
            result = fcntl.ioctl(self.device_fd, command, data)
            return result
        except Exception as e:
            self.log.error("ioctl_failed",
                          message=f"ioctl failed: {command.name}",
                          command=command.name,
                          error=str(e),
                          exc_info=True)
            self.debug_stats['errors'] += 1
            raise DAHDIIOError(f"ioctl command {command.name} failed") from e

    @log_function_call(level="DEBUG")
    async def get_next_event(self) -> Optional[Dict[str, Any]]:
        """Get next event from queue if available"""
        try:
            event = await self.event_queue.get()
            self.log.debug("event_retrieved",
                          message="Retrieved event from queue",
                          event_type=event.get('type'))
            return event
        except Exception as e:
            self.log.error("event_retrieval_error",
                          message="Event retrieval error",
                          error=str(e),
                          exc_info=True)
            return None

    async def get_debug_info(self) -> dict:
        """Get debug statistics and state information"""
        debug_info = {
            **self.debug_stats,
            'state': self.state.name,
            'device_fd': self.device_fd,
            'event_queue_size': self.event_queue.qsize(),
            'fxs_stats': await self.fxs_port.get_debug_info() if self.fxs_port else None,
            'audio_processor_stats': await self.audio_processor.get_debug_info()
        }
        self.log.debug("debug_info_retrieved",
                      message="Retrieved debug information",
                      debug_info=debug_info)
        return debug_info
