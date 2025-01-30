# dahdi-phone-api/src/dahdi_phone/api/models.py
"""
Data models for the DAHDI Phone API.
Defines the core data structures and type definitions used throughout the API,
including phone states, events, commands, and status information.
Uses Pydantic for automatic validation and serialization.
Includes comprehensive DTMF event handling and tracking.
"""

from enum import Enum
from typing import Optional, List, Dict, Union, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
import logging

# Configure module logger
logger = logging.getLogger(__name__)

class PhoneState(str, Enum):
    """
    Represents the current state of a phone line.
    Used for state tracking and event notifications.
    """
    IDLE = "idle"           # Phone is on-hook and not ringing
    OFF_HOOK = "off_hook"   # Phone is off-hook
    RINGING = "ringing"     # Phone is ringing
    IN_CALL = "in_call"     # Active call in progress
    ERROR = "error"         # Hardware or system error
    INITIALIZING = "initializing"  # System startup state
    
    def __str__(self) -> str:
        return self.value

class AudioFormat(BaseModel):
    """Audio format specification for streaming operations"""
    sample_rate: int = Field(default=8000, description="Sample rate in Hz")
    channels: int = Field(default=1, description="Number of audio channels")
    bit_depth: int = Field(default=16, description="Bits per sample")
    
    @validator('sample_rate')
    def validate_sample_rate(cls, v):
        """Validate sample rate is supported"""
        if v not in [8000, 16000]:
            raise ValueError("Sample rate must be 8000 or 16000 Hz")
        return v

class DTMFEvent(BaseModel):
    """
    DTMF tone detection event.
    Includes timing and signal strength information.
    """
    digit: str = Field(..., description="Detected DTMF digit")
    duration: int = Field(..., description="Duration in milliseconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    signal_level: float = Field(default=-30.0, description="Signal level in dBm")
    
    @validator('digit')
    def validate_digit(cls, v):
        """Validate DTMF digit is valid"""
        valid_digits = set('0123456789*#ABCD')
        if v not in valid_digits:
            raise ValueError(f"Invalid DTMF digit: {v}")
        logger.debug(f"Valid DTMF digit detected: {v}")
        return v
        
    class Config:
        """Allow converting to/from JSON with datetime"""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class DTMFHistory(BaseModel):
    """
    Historical DTMF event record.
    Used for tracking and reporting DTMF activity.
    """
    digit: str = Field(..., description="DTMF digit detected")
    timestamp: datetime = Field(..., description="When digit was detected")
    duration: int = Field(..., description="Duration in milliseconds")
    signal_level: float = Field(..., description="Signal level in dBm")
    
    class Config:
        """Allow converting to/from JSON with datetime"""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class VoiceEvent(BaseModel):
    """Voice activity detection event with audio data"""
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    audio_data: Optional[bytes] = None
    is_final: bool = Field(default=False)
    energy_level: float = Field(default=-30.0, description="Voice energy in dB")
    
    class Config:
        arbitrary_types_allowed = True

class LineVoltage(BaseModel):
    """
    Phone line voltage status with detailed measurements.
    Used for line status monitoring and diagnostics.
    """
    voltage: float = Field(..., description="Line voltage in volts")
    status: str = Field(..., description="Voltage status description")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    min_voltage: float = Field(..., description="Minimum observed voltage")
    max_voltage: float = Field(..., description="Maximum observed voltage")
    
    @validator('voltage')
    def validate_voltage(cls, v):
        """Validate voltage is within acceptable range"""
        if not 0 <= v <= 100:
            logger.warning(f"Voltage outside normal range: {v}V")
        return v

class PhoneCommand(BaseModel):
    """
    Command structure for phone control operations.
    Supports various phone control actions with parameters.
    """
    action: str = Field(..., description="Command action to perform")
    parameters: Dict[str, Union[str, int, float, bool]] = Field(
        default_factory=dict,
        description="Command parameters"
    )
    timeout: Optional[int] = Field(default=30, description="Command timeout in seconds")
    
    @validator('action')
    def validate_action(cls, v):
        """Validate command action is supported"""
        valid_actions = {
            'ring', 'stop_ring', 'play_audio', 'generate_tone',
            'reset', 'calibrate', 'diagnostic'
        }
        if v not in valid_actions:
            raise ValueError(f"Unsupported action: {v}")
        logger.debug(f"Valid command action: {v}")
        return v

class CallStatistics(BaseModel):
    """Detailed call statistics for monitoring"""
    total_calls: int = Field(default=0)
    successful_calls: int = Field(default=0)
    failed_calls: int = Field(default=0)
    average_duration: float = Field(default=0.0)
    last_call_timestamp: Optional[datetime] = None
    dtmf_digits_received: int = Field(default=0, description="Total DTMF digits received")

class PhoneStatus(BaseModel):
    """
    Complete phone line status including all relevant state information.
    Used for status reporting and monitoring.
    """
    state: PhoneState = Field(..., description="Current phone state")
    line_voltage: float = Field(..., description="Current line voltage")
    last_dtmf: Optional[str] = Field(default=None, description="Last detected DTMF digit")
    dtmf_history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Recent DTMF event history"
    )
    is_voice_active: bool = Field(default=False, description="Voice activity status")
    audio_format: AudioFormat = Field(default_factory=AudioFormat)
    call_stats: CallStatistics = Field(default_factory=CallStatistics)
    error_message: Optional[str] = None
    last_update: datetime = Field(default_factory=datetime.utcnow)
    
    def log_state_change(self, old_state: PhoneState):
        """Log phone state changes"""
        logger.info(f"Phone state changed: {old_state} -> {self.state}")
    
    class Config:
        """Pydantic configuration"""
        validate_assignment = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class DTMFConfiguration(BaseModel):
    """
    DTMF detection and processing configuration.
    Controls DTMF detection sensitivity and validation parameters.
    """
    min_duration: int = Field(
        default=40,
        description="Minimum duration (ms) for valid DTMF tone"
    )
    detection_threshold: float = Field(
        default=-30.0,
        description="Signal level threshold (dBm) for DTMF detection"
    )
    inter_digit_timeout: int = Field(
        default=2000,
        description="Maximum time (ms) between digits for multi-digit sequences"
    )
    validation_enabled: bool = Field(
        default=True,
        description="Enable additional DTMF validation checks"
    )
    history_size: int = Field(
        default=100,
        description="Number of DTMF events to keep in history"
    )
    
    @validator('min_duration')
    def validate_duration(cls, v):
        """Validate minimum duration is reasonable"""
        if not 20 <= v <= 1000:
            raise ValueError("Minimum duration must be between 20 and 1000 ms")
        return v
    
    @validator('detection_threshold')
    def validate_threshold(cls, v):
        """Validate detection threshold is reasonable"""
        if not -60.0 <= v <= 0.0:
            raise ValueError("Detection threshold must be between -60.0 and 0.0 dBm")
        return v
    
    @validator('history_size')
    def validate_history_size(cls, v):
        """Validate history size is reasonable"""
        if not 10 <= v <= 1000:
            raise ValueError("History size must be between 10 and 1000")
        return v