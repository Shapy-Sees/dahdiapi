# src/dahdi_phone/core/dtmf_detector.py
"""
DTMF tone detection module for DAHDI Phone API.
Implements Goertzel algorithm for efficient DTMF frequency detection.
Handles tone detection, validation, and event generation with detailed logging.
"""

import numpy as np
import logging
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime

from ..utils.logger import DAHDILogger, log_function_call
from ..api.models import DTMFEvent

# Get structured logger
logger = DAHDILogger().get_logger(__name__)

@dataclass
class DTMFConfig:
    """DTMF detection configuration parameters"""
    sample_rate: int = 8000
    frame_size: int = 160  # 20ms @ 8kHz
    detection_threshold: float = -30.0  # dB
    min_duration: int = 40  # Minimum DTMF duration in ms
    energy_threshold: float = 0.1  # Minimum energy threshold

class DTMFDetector:
    """
    DTMF tone detector using Goertzel algorithm.
    Processes audio frames to detect and validate DTMF tones.
    """
    # DTMF frequencies (Hz)
    DTMF_FREQS = {
        'low': [697, 770, 852, 941],
        'high': [1209, 1336, 1477, 1633]
    }

    # DTMF digit mapping
    DTMF_DIGITS = [
        ['1', '2', '3', 'A'],
        ['4', '5', '6', 'B'],
        ['7', '8', '9', 'C'],
        ['*', '0', '#', 'D']
    ]

    def __init__(self, config: DTMFConfig):
        self.config = config
        self._current_digit: Optional[str] = None
        self._digit_start: Optional[datetime] = None
        self._prev_energies: Dict[int, float] = {}
        
        # Initialize Goertzel coefficients
        self._init_goertzel_coeffs()
        
        # Setup logging
        self._setup_logging()
        logger.info("dtmf_detector_init", 
                   message="Initializing DTMF detector",
                   config=vars(config))

    def _setup_logging(self) -> None:
        """Configure DTMF-specific logging"""
        self.debug_stats = {
            'frames_processed': 0,
            'tones_detected': 0,
            'false_positives': 0,
            'detection_errors': 0
        }
        logger.debug("debug_stats_initialized",
                    message="DTMF debug statistics initialized",
                    initial_stats=self.debug_stats)

    def _init_goertzel_coeffs(self) -> None:
        """Initialize Goertzel algorithm coefficients for each DTMF frequency"""
        self.coeffs = {}
        for freq_list in self.DTMF_FREQS.values():
            for freq in freq_list:
                k = int(0.5 + freq * self.config.frame_size / self.config.sample_rate)
                w = 2 * np.pi * k / self.config.frame_size
                self.coeffs[freq] = 2 * np.cos(w)

    @log_function_call(level="DEBUG")
    async def process_frame(self, frame: np.ndarray) -> Optional[DTMFEvent]:
        """
        Process an audio frame for DTMF detection.
        
        Args:
            frame: Audio data as numpy array
            
        Returns:
            DTMFEvent if tone detected, None otherwise
        """
        try:
            self.debug_stats['frames_processed'] += 1
            
            # Calculate energies at DTMF frequencies
            energies = self._calculate_energies(frame)
            
            # Detect DTMF digit
            digit = self._detect_digit(energies)
            
            if digit:
                if self._current_digit != digit:
                    # New digit detected
                    self._current_digit = digit
                    self._digit_start = datetime.utcnow()
                    logger.debug("new_digit_detected",
                               message=f"New DTMF digit detected: {digit}",
                               digit=digit,
                               energies=energies)
                
                elif (datetime.utcnow() - self._digit_start).total_seconds() * 1000 >= self.config.min_duration:
                    # Valid DTMF tone
                    self.debug_stats['tones_detected'] += 1
                    event = DTMFEvent(
                        digit=digit,
                        duration=int((datetime.utcnow() - self._digit_start).total_seconds() * 1000),
                        signal_level=max(energies.values()),
                        timestamp=datetime.utcnow()
                    )
                    logger.info("dtmf_tone_detected",
                              message=f"Valid DTMF tone detected: {digit}",
                              event=vars(event))
                    return event
                    
            else:
                self._current_digit = None
                self._digit_start = None
            
            self._prev_energies = energies
            return None
            
        except Exception as e:
            self.debug_stats['detection_errors'] += 1
            logger.error("dtmf_detection_error",
                        message="DTMF detection failed",
                        error=str(e),
                        exc_info=True)
            raise

    def _calculate_energies(self, frame: np.ndarray) -> Dict[int, float]:
        """
        Calculate signal energy at each DTMF frequency using Goertzel algorithm.
        
        Args:
            frame: Audio frame data
            
        Returns:
            Dictionary of frequency energies
        """
        energies = {}
        
        for freq_list in self.DTMF_FREQS.values():
            for freq in freq_list:
                # Goertzel algorithm implementation
                coeff = self.coeffs[freq]
                s0, s1, s2 = 0.0, 0.0, 0.0
                
                for sample in frame:
                    s0 = sample + coeff * s1 - s2
                    s2 = s1
                    s1 = s0
                
                # Calculate energy
                energy = np.sqrt(s1*s1 + s2*s2 - coeff*s1*s2)
                energy_db = 20 * np.log10(energy) if energy > 0 else -96.0
                energies[freq] = energy_db
                
        return energies

    def _detect_digit(self, energies: Dict[int, float]) -> Optional[str]:
        """
        Detect DTMF digit from frequency energies.
        
        Args:
            energies: Dictionary of frequency energies
            
        Returns:
            Detected digit or None
        """
        # Find strongest frequency in each group
        strongest_low = max(self.DTMF_FREQS['low'], 
                          key=lambda f: energies[f])
        strongest_high = max(self.DTMF_FREQS['high'],
                           key=lambda f: energies[f])
        
        # Check if energies exceed threshold
        if (energies[strongest_low] < self.config.detection_threshold or
            energies[strongest_high] < self.config.detection_threshold):
            return None
            
        # Get indices for digit lookup
        row = self.DTMF_FREQS['low'].index(strongest_low)
        col = self.DTMF_FREQS['high'].index(strongest_high)
        
        return self.DTMF_DIGITS[row][col]

    async def get_debug_info(self) -> dict:
        """Get debug statistics and state information"""
        debug_info = {
            **self.debug_stats,
            'current_digit': self._current_digit,
            'detection_threshold': self.config.detection_threshold,
            'min_duration': self.config.min_duration
        }
        logger.debug("debug_info_retrieved",
                    message="Retrieved debug information",
                    debug_info=debug_info)
        return debug_info