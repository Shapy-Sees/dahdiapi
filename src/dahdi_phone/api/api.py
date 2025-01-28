# dahdi-phone-api/src/dahdi_phone/api/websocket.py

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
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket connection for real-time phone events"""
    await websocket.accept()
    try:
        # Subscribe to phone events
        while True:
            # Send events as they occur
            event = await get_next_event()
            await websocket.send_json(event.dict())
    except WebSocketDisconnect:
        # Clean up subscription
        pass