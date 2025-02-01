# dahdi-phone-api/src/dahdi_phone/api/websocket.py

from enum import Enum
from fastapi import WebSocket, WebSocketDisconnect, Depends
from fastapi.routing import APIRouter
from .server import get_dahdi_interface, DAHDIInterface

router = APIRouter()

class PhoneEventTypes(str, Enum):
    """Types of events that can be sent over WebSocket"""
    OFF_HOOK = "off_hook"
    ON_HOOK = "on_hook"
    DTMF = "dtmf"
    VOICE = "voice"
    RING_START = "ring_start"
    RING_STOP = "ring_stop"
    ERROR = "error"

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    dahdi_interface: DAHDIInterface = Depends(get_dahdi_interface)
):
    """WebSocket connection for real-time phone events"""
    await websocket.accept()
    try:
        # Subscribe to phone events
        while True:
            # Send events as they occur
            event = await dahdi_interface.get_next_event()
            if event:
                await websocket.send_json(event)
    except WebSocketDisconnect:
        # Clean up subscription
        pass
