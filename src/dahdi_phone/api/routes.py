# dahdi-phone-api/src/dahdi_phone/api/routes.py

from datetime import datetime
from fastapi import APIRouter, WebSocket, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from .models import PhoneState, PhoneStatus, CallStatistics
from typing import Dict, Any
from ..core.dahdi_interface import DAHDIInterface, DAHDIStateError, DAHDIIOError
from ..core.audio_processor import AudioProcessor, AudioProcessingError
from ..hardware.fxs import FXSPort, FXSError
from .server import get_dahdi_interface

router = APIRouter(
    prefix="",
    tags=["control"],
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {"detail": "Internal server error"}
                }
            }
        }
    }
)

@router.get(
    "/status",
    response_model=PhoneStatus,
    summary="Get phone line status",
    description="""
    Retrieves the current status of the phone line including:
    - Current state (idle, off-hook, ringing, in-call)
    - Line voltage
    - Call statistics
    - Last error message if any
    - Timestamp of last update
    """,
    responses={
        200: {
            "description": "Successfully retrieved phone status",
            "content": {
                "application/json": {
                    "example": {
                        "state": "idle",
                        "line_voltage": 48.0,
                        "call_stats": {
                            "total_calls": 10,
                            "successful_calls": 8,
                            "failed_calls": 2,
                            "average_duration": 120.5,
                            "dtmf_digits_received": 42
                        },
                        "error_message": None,
                        "last_update": "2024-01-31T17:29:44.123Z"
                    }
                }
            }
        },
        500: {
            "description": "Hardware or system error",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to read DAHDI device"}
                }
            }
        }
    },
    tags=["status"]
)
async def get_status(dahdi: DAHDIInterface = Depends(get_dahdi_interface)) -> PhoneStatus:
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

@router.post(
    "/ring",
    response_model=Dict[str, str],
    summary="Start phone ringing",
    description="""
    Initiates ringing on the phone line for the specified duration.
    The phone must be in IDLE state to start ringing.
    
    The ring signal will automatically stop after the specified duration,
    or can be stopped early using the /stop-ring endpoint.
    """,
    responses={
        200: {
            "description": "Ring started successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "message": "Ring started for 2000ms"
                    }
                }
            }
        },
        400: {
            "description": "Invalid state for ringing",
            "content": {
                "application/json": {
                    "example": {"detail": "Cannot ring phone in OFF_HOOK state"}
                }
            }
        },
        500: {
            "description": "Hardware error",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to control ring signal"}
                }
            }
        }
    }
)
async def start_ring(duration: int = 2000, dahdi: DAHDIInterface = Depends(get_dahdi_interface)):
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

@router.post(
    "/stop-ring",
    response_model=Dict[str, str],
    summary="Stop phone ringing",
    description="""
    Stops the current ring signal.
    Only valid when the phone is in RINGING state.
    """,
    responses={
        200: {
            "description": "Ring stopped successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "message": "Ring stopped"
                    }
                }
            }
        },
        400: {
            "description": "Phone not ringing",
            "content": {
                "application/json": {
                    "example": {"detail": "Phone is not currently ringing"}
                }
            }
        }
    }
)
async def stop_ring(dahdi: DAHDIInterface = Depends(get_dahdi_interface)):
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

@router.post(
    "/play-audio",
    response_model=Dict[str, Any],
    summary="Play audio on phone line",
    description="""
    Plays raw audio data through the phone line.
    Audio must be in the following format:
    - Sample rate: 8kHz
    - Bit depth: 16-bit
    - Channels: Mono
    - Encoding: PCM
    
    The phone must be in OFF_HOOK or IN_CALL state to play audio.
    """,
    responses={
        200: {
            "description": "Audio played successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "bytes_written": 16000,
                        "message": "Wrote 16000 bytes of audio data"
                    }
                }
            }
        },
        400: {
            "description": "Invalid state for audio playback",
            "content": {
                "application/json": {
                    "example": {"detail": "Cannot play audio in IDLE state"}
                }
            }
        },
        500: {
            "description": "Audio processing error",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to write audio data"}
                }
            }
        }
    }
)
async def play_audio(audio_data: bytes, dahdi: DAHDIInterface = Depends(get_dahdi_interface)):
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

@router.post(
    "/generate-tone",
    response_model=Dict[str, Any],
    summary="Generate tone on phone line",
    description="""
    Generates a sine wave tone on the phone line with specified frequency and duration.
    
    Parameters:
    - frequency: Tone frequency in Hz (typical range: 300-3400 Hz)
    - duration: Tone duration in milliseconds
    
    The phone must be in OFF_HOOK or IN_CALL state to generate tones.
    Commonly used for testing or generating DTMF tones.
    """,
    responses={
        200: {
            "description": "Tone generated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "frequency": 1000,
                        "duration": 500,
                        "bytes_written": 8000,
                        "message": "Generated 500ms tone at 1000Hz"
                    }
                }
            }
        },
        400: {
            "description": "Invalid state for tone generation",
            "content": {
                "application/json": {
                    "example": {"detail": "Cannot generate tone in IDLE state"}
                }
            }
        },
        500: {
            "description": "Tone generation error",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to generate tone"}
                }
            }
        }
    }
)
async def generate_tone(
    frequency: int,
    duration: int,
    dahdi: DAHDIInterface = Depends(get_dahdi_interface)
):
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
