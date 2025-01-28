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

## Getting Started

### Prerequisites

- Linux system with DAHDI drivers installed
- Docker and Docker Compose
- OpenVox/Digium FXS card (TDM400P supported)
- Python 3.9+

### Hardware Setup

1. Install DAHDI drivers on the host machine:
```bash
sudo apt-get update
sudo apt-get install dahdi dahdi-linux dahdi-tools
```

2. Load DAHDI kernel modules:
```bash
sudo modprobe dahdi
sudo modprobe opvxa1200
```

3. Configure DAHDI:
```bash
sudo dahdi_genconf
sudo dahdi_cfg -vv
```

4. Verify card detection:
```bash
sudo dahdi_hardware
sudo dahdi_scan
```

### Development Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/dahdi-phone-api.git
cd dahdi-phone-api
```

2. Start the development environment:
```bash
docker-compose up -d
```

3. View logs:
```bash
docker-compose logs -f
```

## API Documentation

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

## Development

### Project Structure

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
│   │   └── websocket.py
│   └── utils/          # Utilities
│       ├── logger.py
│       └── config.py
```

### Configuration

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

### Running Tests

```bash
# Run all tests
docker-compose run --rm api pytest

# Run specific test category
docker-compose run --rm api pytest tests/test_hardware.py

# Run with coverage
docker-compose run --rm api pytest --cov=dahdi_phone
```

### Debugging

1. Access debug console:
```bash
docker-compose exec api python debug_console.py
```

2. View DAHDI device status:
```bash
docker-compose exec api dahdi_status
```

3. Monitor real-time events:
```bash
docker-compose exec api python -m dahdi_phone.tools.event_monitor
```

## Error Handling

The API uses structured error responses:

```json
{
  "error": {
    "code": "HARDWARE_ERROR",
    "message": "Failed to open DAHDI device",
    "details": {
      "device": "/dev/dahdi/channel001",
      "errno": 13
    }
  }
}
```

Common error codes are documented in `/docs/errors.md`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

Please read CONTRIBUTING.md for details on our code of conduct and development process.

### Development Guidelines

- Use type hints for all function definitions
- Maintain 90% or higher test coverage
- Follow PEP 8 style guide
- Document all public interfaces
- Add logging for significant operations

## Architecture Decisions

Key architectural decisions are documented in `/docs/architecture.md`, including:

- DAHDI hardware abstraction approach
- Event system design
- Buffer management strategy
- Error handling philosophy
- API contract design

## Troubleshooting

Common issues and solutions are documented in `/docs/troubleshooting.md`, covering:

- Hardware detection problems
- Driver configuration issues
- Audio quality problems
- Event timing issues
- Resource conflicts


## License

This project is licensed under the MIT License - see LICENSE.md

## Acknowledgments

- DAHDI Project Team
- OpenVox Hardware Documentation
- Python Telephony Community