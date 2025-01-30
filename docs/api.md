# docs/api.md

# DAHDI Phone API Documentation

## REST API Endpoints

Base URL: `http://your-server:8000`

### Status Endpoints

#### Get Phone Status
```
GET /status
```
Returns current phone line status including current state, voltage, DTMF info, and call statistics.

Response:
```json
{
  "state": "IDLE",
  "line_voltage": 48.0,
  "last_dtmf": null,
  "dtmf_history": [],
  "is_voice_active": false,
  "audio_format": {
    "sample_rate": 8000,
    "channels": 1,
    "bit_depth": 16
  },
  "call_stats": {
    "total_calls": 0,
    "successful_calls": 0,
    "failed_calls": 0,
    "average_duration": 0.0,
    "last_call_timestamp": null,
    "dtmf_digits_received": 0
  },
  "error_message": null,
  "last_update": "2025-01-29T12:00:00Z"
}
```

#### Get Line Voltage
```
GET /voltage
```
Returns detailed line voltage readings.

Response:
```json
{
  "voltage": 48.0,
  "status": "normal",
  "timestamp": "2025-01-29T12:00:00Z",
  "min_voltage": 47.5,
  "max_voltage": 48.5
}
```

#### Get Diagnostics
```
GET /diagnostics
```
Returns comprehensive hardware diagnostic information.

Response:
```json
{
  "hardware_present": true,
  "capabilities": {
    "channels": 1,
    "supports_echo_cancel": true,
    "supports_hwgain": true,
    "supports_ring_detect": true,
    "max_ring_voltage": 90.0,
    "min_idle_voltage": 48.0
  },
  "voltage_tests": {
    "idle_voltage": 48.0,
    "ring_voltage": 90.0
  },
  "signal_quality": {
    "signal_level": -20.0,
    "noise_level": -60.0,
    "snr": 40.0,
    "distortion": 0.1
  },
  "functional_tests": {
    "ring_test": true,
    "audio_test": true,
    "dtmf_test": true
  }
}
```

### Control Endpoints

#### Start Ring
```
POST /ring
```
Start phone ringing with specified pattern.

Request Body:
```json
{
  "pattern": "NORMAL",
  "repeat": 1,
  "custom_pattern": {
    "on_times": [500, 500],
    "off_times": [300, 0]
  }
}
```

Parameters:
- `pattern`: One of:
  - `NORMAL`: Standard 2s on, 4s off
  - `DISTINCTIVE1`: Short-short-long
  - `DISTINCTIVE2`: Short-long-short
  - `CONTINUOUS`: Continuous ring
  - `SINGLE`: Single short ring (500ms) for notifications
  - `TIMER`: Three quick rings (200ms each) for timer completion
  - `URGENT`: Five quick rings (300ms on/off) for urgent notifications
  - `CUSTOM`: Use custom_pattern parameter
- `repeat`: Number of pattern repetitions (0 for infinite, default: 1)
- `custom_pattern`: Required when pattern is "CUSTOM"
  - `on_times`: List of ring-on durations in milliseconds
  - `off_times`: List of ring-off durations in milliseconds (last value can be 0)

Pre-defined Pattern Specifications:
```
NORMAL:
  on_times: [2000]
  off_times: [4000]
  default_repeat: 1

DISTINCTIVE1 (Short-Short-Long):
  on_times: [500, 500, 2000]
  off_times: [500, 500, 4000]
  default_repeat: 1

DISTINCTIVE2 (Short-Long-Short):
  on_times: [500, 2000, 500]
  off_times: [500, 500, 4000]
  default_repeat: 1

CONTINUOUS:
  on_times: [5000]
  off_times: [100]
  default_repeat: 0 (infinite)

SINGLE (Notification):
  on_times: [500]
  off_times: [0]
  default_repeat: 1

TIMER (Timer Completion):
  on_times: [200, 200, 200]
  off_times: [200, 200, 0]
  default_repeat: 1

URGENT (Urgent Notification):
  on_times: [300]
  off_times: [300]
  default_repeat: 5
```

Example Custom Pattern Requests:

Simple Notification:
```json
{
  "pattern": "CUSTOM",
  "repeat": 1,
  "custom_pattern": {
    "on_times": [300],
    "off_times": [0]
  }
}
```

Double Beep:
```json
{
  "pattern": "CUSTOM",
  "repeat": 1,
  "custom_pattern": {
    "on_times": [200, 200],
    "off_times": [200, 0]
  }
}
```

Complex Pattern:
```json
{
  "pattern": "CUSTOM",
  "repeat": 2,
  "custom_pattern": {
    "on_times": [300, 300, 600],
    "off_times": [200, 200, 0]
  }
}
```

#### Stop Ring
```
POST /stop-ring
```
Stops any active ringing.

#### Play Audio
```
POST /play-audio
```
Play audio through phone line.

Request Body: Raw audio bytes (8kHz, 16-bit, mono)

Headers:
- `Content-Type: application/octet-stream`

#### Generate Tone
```
POST /generate-tone
```
Generate specific tone on phone line.

Request Body:
```json
{
  "frequency": 1000,
  "duration": 1000
}
```

Parameters:
- `frequency`: Tone frequency in Hz
- `duration`: Tone duration in milliseconds

## WebSocket Interface

Base URL: `ws://your-server:8001`

### Connection
```
WebSocket /ws
```

### Events

#### Phone State Events

##### Off Hook Event
```json
{
  "type": "off_hook",
  "timestamp": "2025-01-29T12:00:00Z"
}
```

##### On Hook Event
```json
{
  "type": "on_hook",
  "timestamp": "2025-01-29T12:00:00Z"
}
```

##### DTMF Event
```json
{
  "type": "dtmf",
  "digit": "5",
  "duration": 100,
  "signal_level": -20.0,
  "timestamp": "2025-01-29T12:00:00Z"
}
```

##### Voice Event
```json
{
  "type": "voice",
  "start_time": "2025-01-29T12:00:00Z",
  "end_time": "2025-01-29T12:00:01Z",
  "energy_level": -30.0
}
```

##### Ring Events
```json
{
  "type": "ring_start",
  "pattern": "NORMAL",
  "timestamp": "2025-01-29T12:00:00Z"
}
```
```json
{
  "type": "ring_stop",
  "timestamp": "2025-01-29T12:00:02Z"
}
```

#### System Events

##### Error Event
```json
{
  "type": "error",
  "error_message": "Hardware communication failed",
  "error_code": "HW001",
  "timestamp": "2025-01-29T12:00:00Z"
}
```

##### Voltage Change Event
```json
{
  "type": "voltage_change",
  "voltage": 48.0,
  "timestamp": "2025-01-29T12:00:00Z"
}
```

##### Hardware Status Event
```json
{
  "type": "hardware_status",
  "status": "operational",
  "details": {
    "temperature": 25,
    "uptime": 3600
  },
  "timestamp": "2025-01-29T12:00:00Z"
}
```

## Data Models

### Phone States
```python
PhoneState:
    IDLE         # Phone is on-hook and not ringing
    OFF_HOOK     # Phone is off-hook
    RINGING      # Phone is ringing
    IN_CALL      # Active call in progress
    ERROR        # Hardware or system error
    INITIALIZING # System startup state
```

### Call Statistics
```python
CallStatistics:
    total_calls: int          # Total number of calls
    successful_calls: int     # Successfully completed calls
    failed_calls: int         # Failed or interrupted calls
    average_duration: float   # Average call duration in seconds
    last_call_timestamp: datetime  # Last call time
    dtmf_digits_received: int # Total DTMF digits received
```

### Audio Format
```python
AudioFormat:
    sample_rate: int    # Sample rate in Hz (default: 8000)
    channels: int       # Number of channels (default: 1)
    bit_depth: int      # Bits per sample (default: 16)
```

## Configuration

### Environment Variables
- `DAHDI_API_HOST`: API host address
- `DAHDI_API_REST_PORT`: REST API port
- `DAHDI_API_WS_PORT`: WebSocket port
- `LOG_LEVEL`: Logging level
- `DAHDI_DEVICE`: DAHDI device path
- `API_TIMEOUT`: API request timeout

### Configuration File
Location: `/etc/dahdi_phone/config.yml`

Example configuration:
```yaml
server:
  host: "0.0.0.0"
  rest_port: 8000
  websocket_port: 8001
  workers: 4

dahdi:
  device: "/dev/dahdi/channel001"
  control: "/dev/dahdi/ctl"
  channel: 1
  audio:
    sample_rate: 8000
    channels: 1
    bit_depth: 16
  buffer_size: 320

logging:
  level: "INFO"
  format: "json"
  output: "/var/log/dahdi_phone/api.log"
  rotation: "1 day"
  retention: "30 days"
```