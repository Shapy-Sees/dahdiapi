# dahdi-phone-api/src/dahdi_phone/api/models.py

from pydantic import BaseModel
from enum import Enum
from typing import Optional, List

class PhoneState(str, Enum):
    """Current state of the phone line"""
    IDLE = "idle"
    OFF_HOOK = "off_hook"
    RINGING = "ringing"
    IN_CALL = "in_call"

class DTMFEvent(BaseModel):
    """DTMF tone detection event"""
    digit: str
    duration: int  # Duration in milliseconds
    timestamp: int

class VoiceEvent(BaseModel):
    """Voice activity detection event"""
    start_time: int
    end_time: int
    audio_data: bytes
    is_final: bool

class LineVoltage(BaseModel):
    """Line voltage status"""
    voltage: float
    status: str

class PhoneCommand(BaseModel):
    """Commands that can be sent to the phone"""
    action: str
    parameters: Optional[dict] = None

class PhoneStatus(BaseModel):
    """Complete phone line status"""
    state: PhoneState
    line_voltage: float
    last_dtmf: Optional[str] = None
    is_voice_active: bool