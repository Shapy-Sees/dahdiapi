# dahdi-phone-api/src/dahdi_phone/api/routes.py

from datetime import datetime
from fastapi import APIRouter, WebSocket, HTTPException, Depends
from .models import PhoneState, PhoneStatus, CallStatistics
from ..core.dahdi_interface import DAHDIInterface, DAHDIStateError, DAHDIIOError
from ..core.audio_processor import AudioProcessor, AudioProcessingError
from ..hardware.fxs import FXSPort, FXSError
from .server import get_dahdi_interface

router = APIRouter()

@router.get("/status")
async def get_status(dahdi: DAHDIInterface = Depends(get_dahdi_interface)) -> PhoneStatus:
    """Get current phone line status"""
    try:
        debug_info = await dahdi.get_debug_info()
        # Convert DAHDI state to PhoneState using the mapping function
        current_state = PhoneState.from_dahdi_state(debug_info['state'])
        
        return PhoneStatus(
            state=current_state,
            line_voltage=debug_info.get('fxs_stats', {}).get('voltage', 0.0),
            call_stats=debug_info.get('call_stats', CallStatistics()),
            error_message=debug_info.get('last_error'),
            last_update=datetime.utcnow()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ring")
async def start_ring(duration: int = 2000, dahdi: DAHDIInterface = Depends(get_dahdi_interface)):
    """Start ringing the phone
    
    Args:
        duration: Ring duration in milliseconds
    """
    try:
        # Verify current state allows ringing
        debug_info = await dahdi.get_debug_info()
        current_state = PhoneState.from_dahdi_state(debug_info['state'])
        if current_state not in [PhoneState.IDLE]:
            raise DAHDIStateError(f"Cannot ring phone in {current_state} state")
            
        await dahdi.ring(duration)
        return {"status": "success", "message": f"Ring started for {duration}ms"}
    except DAHDIStateError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DAHDIIOError as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop-ring")
async def stop_ring(dahdi: DAHDIInterface = Depends(get_dahdi_interface)):
    """Stop ringing the phone"""
    try:
        # Verify current state is ringing
        debug_info = await dahdi.get_debug_info()
        current_state = PhoneState.from_dahdi_state(debug_info['state'])
        if current_state != PhoneState.RINGING:
            raise DAHDIStateError("Phone is not currently ringing")
            
        # Ring with 0 duration to stop
        await dahdi.ring(0)
        return {"status": "success", "message": "Ring stopped"}
    except DAHDIStateError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DAHDIIOError as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/play-audio")
async def play_audio(audio_data: bytes, dahdi: DAHDIInterface = Depends(get_dahdi_interface)):
    """Play audio through the phone line
    
    Args:
        audio_data: Raw audio bytes (8kHz, 16-bit, mono)
    """
    try:
        # Verify current state allows audio playback
        debug_info = await dahdi.get_debug_info()
        current_state = PhoneState.from_dahdi_state(debug_info['state'])
        if current_state not in [PhoneState.OFF_HOOK, PhoneState.IN_CALL]:
            raise DAHDIStateError(f"Cannot play audio in {current_state} state")
            
        bytes_written = await dahdi.write_audio(audio_data)
        return {
            "status": "success",
            "bytes_written": bytes_written,
            "message": f"Wrote {bytes_written} bytes of audio data"
        }
    except (DAHDIIOError, FXSError, AudioProcessingError) as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-tone")
async def generate_tone(
    frequency: int,
    duration: int,
    dahdi: DAHDIInterface = Depends(get_dahdi_interface)
):
    """Generate a tone on the phone line
    
    Args:
        frequency: Tone frequency in Hz
        duration: Tone duration in milliseconds
    """
    # Verify current state allows tone generation
    debug_info = await dahdi.get_debug_info()
    current_state = PhoneState.from_dahdi_state(debug_info['state'])
    if current_state not in [PhoneState.OFF_HOOK, PhoneState.IN_CALL]:
        raise DAHDIStateError(f"Cannot generate tone in {current_state} state")
        
    try:
        import numpy as np
        
        # Generate tone samples
        sample_rate = 8000
        num_samples = int((duration / 1000) * sample_rate)
        t = np.linspace(0, duration/1000, num_samples)
        tone = (32767 * np.sin(2 * np.pi * frequency * t)).astype(np.int16)
        
        # Convert to bytes and play
        audio_data = tone.tobytes()
        bytes_written = await dahdi.write_audio(audio_data)
        
        return {
            "status": "success",
            "frequency": frequency,
            "duration": duration,
            "bytes_written": bytes_written,
            "message": f"Generated {duration}ms tone at {frequency}Hz"
        }
    except (DAHDIIOError, FXSError, AudioProcessingError) as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate tone: {str(e)}")
