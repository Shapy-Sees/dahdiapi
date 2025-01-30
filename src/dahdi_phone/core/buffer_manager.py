# src/dahdi_phone/core/buffer_manager.py
"""
Circular buffer implementation for audio data management with extensive logging.
"""

import logging
import threading
from typing import Optional
from collections import deque

logger = logging.getLogger(__name__)

class CircularBuffer:
    """
    Thread-safe circular buffer implementation with detailed logging.
    """
    def __init__(self, size: int):
        self.buffer = deque(maxlen=size)
        self.lock = threading.Lock()
        self.size = size
        self._setup_logging()
        logger.info(f"Initialized CircularBuffer with size {size}")
    
    def _setup_logging(self):
        """Configure buffer statistics and logging"""
        self.stats = {
            'total_writes': 0,
            'total_reads': 0,
            'overruns': 0,
            'underruns': 0
        }
    
    def write(self, data: bytes) -> bool:
        """
        Write data to buffer with overflow protection and logging.
        
        Args:
            data: Bytes to write to buffer
            
        Returns:
            Success status
        """
        with self.lock:
            try:
                if len(self.buffer) + len(data) > self.size:
                    self.stats['overruns'] += 1
                    logger.warning(f"Buffer overrun detected. Utilization: {self.utilization:.2f}")
                    return False
                
                self.buffer.extend(data)
                self.stats['total_writes'] += 1
                logger.debug(f"Written {len(data)} bytes. Buffer utilization: {self.utilization:.2f}")
                return True
                
            except Exception as e:
                logger.error(f"Buffer write error: {str(e)}", exc_info=True)
                raise BufferError(f"Write operation failed: {str(e)}") from e
    
    def read(self, size: int) -> Optional[bytes]:
        """
        Read data from buffer with detailed logging.
        
        Args:
            size: Number of bytes to read
            
        Returns:
            Read bytes or None if not enough data
        """
        with self.lock:
            try:
                if len(self.buffer) < size:
                    self.stats['underruns'] += 1
                    logger.warning(f"Buffer underrun. Requested: {size}, Available: {len(self.buffer)}")
                    return None
                
                data = bytes([self.buffer.popleft() for _ in range(size)])
                self.stats['total_reads'] += 1
                logger.debug(f"Read {size} bytes. Buffer utilization: {self.utilization:.2f}")
                return data
                
            except Exception as e:
                logger.error(f"Buffer read error: {str(e)}", exc_info=True)
                raise BufferError(f"Read operation failed: {str(e)}") from e
    
    @property
    def utilization(self) -> float:
        """Calculate current buffer utilization with thread safety"""
        with self.lock:
            return len(self.buffer) / self.size

    def get_stats(self) -> dict:
        """Return detailed buffer statistics"""
        with self.lock:
            return {
                **self.stats,
                'current_utilization': self.utilization,
                'size': self.size,
                'available': self.size - len(self.buffer)
            }

class BufferError(Exception):
    """Custom exception for buffer operations"""
    pass