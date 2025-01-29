# DAHDI Phone API

A Python-based REST and WebSocket API that provides a clean interface to DAHDI (Digium Asterisk Hardware Device Interface) telephony hardware. This service enables high-level control of analog telephone lines through FXS (Foreign Exchange Station) hardware.

## Core Features

- Complete DAHDI hardware abstraction
- Real-time phone line state management
- DTMF tone detection and generation
- Voice activity detection
- Audio streaming support
- WebSocket-based event system
- Comprehensive error handling and diagnostics
- Docker containerized deployment
- Host-Container architecture for hardware access
- Pydantic-based data validation and serialization
- Automatic API documentation via FastAPI

## Getting Started

### Prerequisites

#### Hardware Requirements
- Linux system with kernel version 4.x or higher
- OpenVox/Digium FXS card (TDM400P supported)
- Minimum 2GB RAM
- 20GB available disk space

#### Software Requirements
- Docker Engine 20.10+
- Docker Compose 2.0+
- Python 3.9+
- Linux kernel headers
- Build tools (gcc, make)
- FastAPI and Pydantic for API functionality

### Host System Setup

1. Install kernel headers and build tools:
```bash
sudo apt-get update
sudo apt-get install linux-headers-$(uname -r) build-essential gcc make
```

2. Install DAHDI kernel modules:
```bash
# Download and install DAHDI Linux
wget http://downloads.asterisk.org/pub/telephony/dahdi-linux/dahdi-linux-current.tar.gz
tar xvfz dahdi-linux-current.tar.gz
cd dahdi-linux-*
make
sudo make install
sudo make config
```

3. Load DAHDI kernel modules:
```bash
sudo modprobe dahdi
sudo modprobe your_card_module  # Replace with your specific card module (e.g., opvxa1200)
```

4. Configure DAHDI:
```bash
sudo dahdi_genconf
sudo dahdi_cfg -vv
```

5. Set up device permissions:
```bash
sudo chown root:dialout /dev/dahdi/*
sudo chmod 660 /dev/dahdi/*
sudo usermod -a -G dialout $USER  # Add your user to dialout group
```

6. Verify hardware detection:
```bash
sudo dahdi_hardware
sudo dahdi_scan
ls -l /dev/dahdi/*  # Verify device nodes exist
```

### Development Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/dahdi-phone-api.git
cd dahdi-phone-api
```

2. Build and start the container:
```bash
docker-compose build
docker-compose up -d
```

3. View logs:
```bash
docker-compose logs -f
```

4. Verify the installation:
```bash
curl http://localhost:8000/status  # Should return phone line status
```

## API Documentation

### Data Models

The API uses Pydantic models for data validation and serialization. Key models include:

#### Phone States
```python
PhoneState:
    IDLE        # Phone is on-hook and not ringing
    OFF_HOOK    # Phone is off-hook
    RINGING     # Phone is ringing
    IN_CALL     # Active call in progress
    ERROR       # Hardware or system error
    INITIALIZING # System startup state
```

#### Event Models
- `DTMFEvent`: DTMF tone detection events
  - digit: Detected digit (0-9, *, #, A-D)
  - duration: Duration in milliseconds
  - signal_level: Signal strength in dBm
  
- `VoiceEvent`: Voice activity detection
  - start_time: Event start timestamp
  - end_time: Event end timestamp
  - energy_level: Voice energy in dB
  
- `LineVoltage`: Line voltage monitoring
  - voltage: Current voltage
  - status: Voltage status description
  - min/max voltage readings

#### Status Models
- `PhoneStatus`: Complete phone line status
  - state: Current PhoneState
  - line_voltage: Current line voltage
  - call_stats: Call statistics
  - audio_format: Current audio configuration

### REST Endpoints

The API provides the following endpoints for phone control:

#### Status Endpoints
- `GET /status` - Get current phone line status
- `GET /voltage` - Get line voltage readings
- `GET /diagnostics` - Run and return hardware diagnostics

#### Control Endpoints
- `POST /ring` - Start phone ringing
- `POST /stop-ring` - Stop phone ringing
- `POST /play-audio` - Play audio through phone line
- `POST /generate-tone` - Generate specific tones
- `POST /reset` - Reset hardware interface

### WebSocket Events

Real-time events are sent through WebSocket connections:

#### Phone State Events
- `off_hook` - Phone went off hook
- `on_hook` - Phone went on hook
- `dtmf` - DTMF tone detected
- `voice` - Voice activity detected
- `ring_start` - Ring signal started
- `ring_stop` - Ring signal stopped

#### System Events
- `error` - Error occurred
- `voltage_change` - Line voltage changed
- `hardware_status` - Hardware status update

Full API documentation available in `/docs/api.md`

## Project Structure

```
src/
├── dahdi_phone/          # Main package
│   ├── core/            # Core DAHDI interaction
│   │   ├── dahdi_interface.py
│   │   ├── audio_processor.py
│   │   └── state_manager.py
│   ├── hardware/        # Hardware abstraction
│   │   ├── fxs.py
│   │   └── audio_buffer.py
│   ├── api/            # API implementation
│   │   ├── server.py
│   │   ├── routes.py
│   │   ├── models.py   # Data models and validation
│   │   └── websocket.py
│   └── utils/          # Utilities
│       ├── logger.py
│       └── config.py
```

## Data Models

The API uses Pydantic models for data validation and serialization, defined in `api/models.py`. These models ensure:

- Type safety throughout the application
- Automatic validation of input/output data
- Clear API documentation
- Consistent data structures
- Runtime data validation

Key model categories:

1. State Models
   - Phone state management
   - Line voltage monitoring
   - Call statistics

2. Event Models
   - DTMF detection events
   - Voice activity events
   - System status events

3. Command Models
   - Phone control commands
   - Configuration commands
   - Diagnostic commands

4. Status Models
   - Complete phone status
   - Diagnostic information
   - Statistical data

## Configuration

Configuration is managed through YAML files in the `config` directory:

```yaml
# config/default.yml
dahdi:
  device: /dev/dahdi/channel001
  control: /dev/dahdi/ctl
  channel: 1
  audio:
    sample_rate: 8000
    channels: 1
    bit_depth: 16
  buffer_size: 320  # 20ms @ 8kHz/16-bit
```

[Rest of the README remains unchanged...]