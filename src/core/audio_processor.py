# src/core/audio_processor.py
"""
Core audio processing module for DAHDI Phone API.
Handles audio buffer management, processing, and streaming with extensive logging.
Includes DTMF tone detection and event notification capabilities.
"""

import logging
import numpy as np
import asyncio
from typing import Optional, Tuple, Set, Callable
from dataclasses import dataclass
from .buffer_manager import CircularBuffer, BufferError
from .dtmf_detector import DTMFDetector, DTMFConfig
from ..api.models import DTMFEvent

# Configure module logger
logger = logging.getLogger(__name__)

@dataclass
class AudioConfig:
    """Audio processing configuration parameters"""
    sample_rate: int = 8000
    frame_size: int = 160  # 20ms @ 8kHz
    channels: int = 1
    bit_depth: int = 16

class AudioProcessor:
    """
    Handles audio processing operations with detailed logging and error tracking.
    Includes DTMF detection and event notification.
    """
    def __init__(self, config: AudioConfig):
        self.config = config
        self.buffer = CircularBuffer(size=config.frame_size * 10)  # 200ms buffer
        
        # Initialize DTMF detector
        dtmf_config = DTMFConfig(
            sample_rate=config.sample_rate,
            frame_size=config.frame_size
        )
        self.dtmf_detector = DTMFDetector(dtmf_config)
        
        # Set up event subscribers
        self._dtmf_subscribers: Set[Callable[[DTMFEvent], None]] = set()
        
        self._setup_logging()
        logger.info(f"Initialized AudioProcessor with config: {config}")
    
    def _setup_logging(self):
        """Configure detailed logging for audio processing operations"""
        self.debug_stats = {
            'frames_processed': 0,
            'buffer_overruns': 0,
            'processing_errors': 0,
            'dtmf_events': 0,
            'subscriber_notifications': 0
        }
        logger.debug("Audio processing debug statistics initialized")

    async def subscribe_dtmf(self, callback: Callable[[DTMFEvent], None]) -> None:
        """
        Subscribe to DTMF events.
        
        Args:
            callback: Function to call when DTMF tone is detected
        """
        self._dtmf_subscribers.add(callback)
        logger.debug(f"Added DTMF subscriber, total subscribers: {len(self._dtmf_subscribers)}")

    async def unsubscribe_dtmf(self, callback: Callable[[DTMFEvent], None]) -> None:
        """
        Unsubscribe from DTMF events.
        
        Args:
            callback: Previously registered callback function
        """
        self._dtmf_subscribers.discard(callback)
        logger.debug(f"Removed DTMF subscriber, total subscribers: {len(self._dtmf_subscribers)}")

    async def _notify_dtmf_subscribers(self, event: DTMFEvent) -> None:
        """
        Notify all subscribers of DTMF event.
        
        Args:
            event: DTMF event to broadcast
        """
        notification_tasks = []
        
        for callback in self._dtmf_subscribers:
            task = asyncio.create_task(callback(event))
            notification_tasks.append(task)
            
        if notification_tasks:
            self.debug_stats['subscriber_notifications'] += len(notification_tasks)
            await asyncio.gather(*notification_tasks, return_exceptions=True)
            logger.debug(f"Notified {len(notification_tasks)} DTMF subscribers of event: {event}")

    async def process_frame(self, raw_data: bytes) -> Tuple[np.ndarray, dict]:
        """
        Process a single frame of audio data with comprehensive error handling.
        Includes DTMF detection and event notification.
        
        Args:
            raw_data: Raw audio bytes from DAHDI
            
        Returns:
            Tuple of processed audio array and frame statistics
            
        Raises:
            AudioProcessingError: If processing fails
        """
        try:
            logger.debug(f"Processing frame of size {len(raw_data)} bytes")
            
            # Convert to numpy array for processing
            audio_array = np.frombuffer(raw_data, dtype=np.int16)
            
            # Apply audio processing pipeline
            processed = await self._apply_processing(audio_array)
            
            # Perform DTMF detection
            dtmf_event = await self.dtmf_detector.process_frame(processed)
            if dtmf_event:
                self.debug_stats['dtmf_events'] += 1
                logger.info(f"DTMF detected: {dtmf_event.digit}")
                await self._notify_dtmf_subscribers(dtmf_event)
            
            # Update statistics
            self.debug_stats['frames_processed'] += 1
            
            # Generate frame statistics
            stats = {
                'peak_amplitude': float(np.max(np.abs(processed))),
                'rms_level': float(np.sqrt(np.mean(processed**2))),
                'frame_number': self.debug_stats['frames_processed'],
                'dtmf_detected': dtmf_event.digit if dtmf_event else None
            }
            
            logger.debug(f"Frame {stats['frame_number']} processed: {stats}")
            return processed, stats
            
        except Exception as e:
            self.debug_stats['processing_errors'] += 1
            logger.error(f"Audio processing error: {str(e)}", exc_info=True)
            raise AudioProcessingError(f"Frame processing failed: {str(e)}") from e

    async def _apply_processing(self, audio_array: np.ndarray) -> np.ndarray:
        """
        Apply audio processing effects pipeline with detailed logging.
        
        Args:
            audio_array: Input audio data as numpy array
            
        Returns:
            Processed audio array
        """
        logger.debug("Starting audio processing pipeline")
        
        try:
            # DC offset removal
            audio_array = audio_array - np.mean(audio_array)
            logger.debug("DC offset removed")

            # Normalize audio
            if np.max(np.abs(audio_array)) > 0:
                audio_array = audio_array / np.max(np.abs(audio_array)) * 32767
                logger.debug("Audio normalized")
            
            # Apply any additional processing here
            
            return audio_array
            
        except Exception as e:
            logger.error("Audio pipeline processing failed", exc_info=True)
            raise AudioProcessingError("Pipeline processing failed") from e

    async def get_debug_info(self) -> dict:
        """Return detailed debug information about audio processing"""
        dtmf_debug = await self.dtmf_detector.get_debug_info()
        return {
            **self.debug_stats,
            'buffer_utilization': self.buffer.utilization,
            'dtmf_debug': dtmf_debug,
            'dtmf_subscribers': len(self._dtmf_subscribers),
            'last_error': getattr(self, 'last_error', None)
        }

class AudioProcessingError(Exception):
    """Custom exception for audio processing errors"""
    pass