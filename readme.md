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

## Hardware Requirements

### DAHDI Hardware Requirements
- Linux system with kernel version 4.x or higher
- OpenVox/Digium FXS card with DAHDI support
- A standard analog telephone for testing
- Physical access to server for hardware installation

### System Requirements
- Linux OS with kernel headers
- DAHDI kernel modules and utilities
- Build tools (gcc, make)
- Python 3.9+
- Docker Engine 20.10+
- Docker Compose 2.0+
- Minimum 2GB RAM
- 20GB available disk space

### DAHDI Configuration
- Required kernel modules: dahdi, card-specific module (e.g., opvxa1200)
- Device nodes: /dev/dahdi/*
- Proper permissions: dialout group access
- DAHDI system configuration file
- Channel configuration matching hardware

## Driver Architecture

### Hardware Communication
- Direct DAHDI device access through ioctl system calls
- Real-time event propagation from kernel to userspace
- Voltage monitoring and control for line status
- Audio streaming with buffer management
- Thread-safe hardware access coordination

### State Management
- Thread-safe phone line state tracking
- Validated state transitions
- Event notification system
- Call statistics monitoring
- DTMF event tracking
- Line voltage monitoring

### Audio Processing
- Real-time audio streaming with buffer management
- DTMF tone detection using Goertzel algorithm
- Voice activity detection
- Audio format conversion
- Configurable buffer sizes
- Sample rate management

## Getting Started

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

## Development Notes

### Debugging

#### Logging System
- Comprehensive logging throughout all components
- Configurable log levels via config.yml
- Structured logging with JSON format support
- Rotated log files with retention policies
- Console and file logging support

#### Diagnostics
- Hardware diagnostics via /diagnostics endpoint
- Real-time state monitoring
- Audio quality metrics
- Line voltage monitoring
- Call statistics tracking
- DTMF detection verification

#### Development Mode
- Hardware simulation mode for development
- DAHDI device mocking capabilities
- Configurable through config.yml
- Separate development configuration

### Testing
- Hardware simulation mode for development
- DAHDI device mocking
- Audio processing verification
- State transition validation
- WebSocket connection testing
- API endpoint testing

## Configuration

### Environment Variables
- `DAHDI_API_HOST`: API host address
- `DAHDI_API_REST_PORT`: REST API port
- `DAHDI_API_WS_PORT`: WebSocket port
- `LOG_LEVEL`: Logging level
- `DAHDI_DEVICE`: DAHDI device path
- `API_TIMEOUT`: API request timeout

### Configuration File
Location: `/etc/dahdi_phone/config.yml` (mounted from `src/dahdi_phone/config/config.yml`)

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

## Project Structure

```
dahdi-phone-api/
├── src/                       # Source code
│   ├── dahdi_phone/          # Main package
│   │   ├── api/              # API implementation
│   │   │   ├── __init__.py
│   │   │   ├── __main__.py   # Entry point
│   │   │   ├── models.py     # Data models
│   │   │   ├── routes.py     # API endpoints
│   │   │   ├── server.py     # Server implementation
│   │   │   └── websocket.py  # WebSocket handling
│   │   │
│   │   ├── config/           # Configuration files
│   │   │   ├── default.yml   # Default configuration
│   │   │   └── config.yml    # Primary configuration
│   │   │
│   │   ├── core/             # Core functionality
│   │   │   ├── __init__.py
│   │   │   ├── audio_processor.py    # Audio processing
│   │   │   ├── buffer_manager.py     # Buffer handling
│   │   │   ├── dahdi_interface.py    # DAHDI communication
│   │   │   ├── dtmf_detector.py      # DTMF detection
│   │   │   └── state_manager.py      # State management
│   │   │
│   │   ├── hardware/         # Hardware abstraction
│   │   │   ├── __init__.py
│   │   │   ├── audio_buffer.py       # Audio buffering
│   │   │   └── fxs.py               # FXS port handling
│   │   │
│   │   ├── utils/            # Utility modules
│   │   │   ├── __init__.py
│   │   │   ├── config.py     # Configuration management
│   │   │   └── logger.py     # Logging system
│   │   │
│   │   └── __init__.py
│   │
│   └── __init__.py
│
├── docs/                      # Documentation
│   └── api.md                # API documentation
│
├── logs/                      # Log files directory
│
├── scripts/                   # Utility scripts
│   └── start.sh              # Service startup script
│
├── tests/                     # Test suite
│   └── __init__.py
│
├── docker-compose.yml         # Docker Compose configuration
├── Dockerfile                 # Docker build instructions
├── README.md                 # Project documentation
├── requirements.txt          # Python dependencies
└── setup.py                  # Package setup
```

## Contributing

### Development Workflow
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add or update tests
5. Run the test suite
6. Submit a pull request

### Coding Standards
- Follow PEP 8 style guide
- Add comprehensive docstrings
- Include type hints
- Add appropriate logging
- Write unit tests
- Update documentation

### Testing Requirements
- Unit tests for new features
- Integration tests for API endpoints
- Hardware simulation tests
- WebSocket connection tests
- Configuration validation tests

## License

[Insert your license information here]

## Support

For support:
- Open an issue on GitHub
- Check the documentation
- Contact the development team

## Acknowledgments

- DAHDI development team
- OpenVox/Digium for hardware specifications
- FastAPI framework developers
- Python asyncio community