# dahdi-phone-api/src/dahdi_phone/api/websocket.py

from enum import Enum
from fastapi import WebSocket, WebSocketDisconnect, Depends
from fastapi.routing import APIRouter
from .server import get_dahdi_interface, DAHDIInterface

router = APIRouter(
    tags=["websocket"],
    responses={
        101: {"description": "WebSocket connection established"},
        400: {"description": "Connection error"},
    }
)

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
    """
    WebSocket endpoint for receiving real-time phone events.
    
    Event Types:
    
    * `off_hook`: Phone taken off hook
        ```json
        {
            "type": "off_hook",
            "timestamp": "2024-01-31T17:29:44.123Z"
        }
        ```
    
    * `on_hook`: Phone placed on hook
        ```json
        {
            "type": "on_hook",
            "timestamp": "2024-01-31T17:29:44.123Z"
        }
        ```
    
    * `dtmf`: DTMF digit detected
        ```json
        {
            "type": "dtmf",
            "digit": "5",
            "duration": 100,
            "timestamp": "2024-01-31T17:29:44.123Z"
        }
        ```
    
    * `voice`: Voice activity detected
        ```json
        {
            "type": "voice",
            "energy": -20.5,
            "timestamp": "2024-01-31T17:29:44.123Z"
        }
        ```
    
    * `ring_start`: Ring signal started
        ```json
        {
            "type": "ring_start",
            "duration": 2000,
            "timestamp": "2024-01-31T17:29:44.123Z"
        }
        ```
    
    * `ring_stop`: Ring signal stopped
        ```json
        {
            "type": "ring_stop",
            "timestamp": "2024-01-31T17:29:44.123Z"
        }
        ```
    
    * `error`: Error event
        ```json
        {
            "type": "error",
            "error": "Hardware communication error",
            "timestamp": "2024-01-31T17:29:44.123Z"
        }
        ```
    
    Connection Lifecycle:
    1. Connect to `/ws` endpoint
    2. Connection is accepted and events start streaming
    3. Events are pushed in real-time as they occur
    4. Connection remains open until client disconnects
    
    Error Handling:
    * Connection errors return HTTP 400
    * Runtime errors are sent as error events
    * Connection is auto-closed on fatal errors
    """
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
