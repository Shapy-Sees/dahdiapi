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
│   │   └── websocket.py
│   └── utils/          # Utilities
│       ├── logger.py
│       └── config.py
```

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

## Running Tests

```bash
# Run all tests
docker-compose run --rm api pytest

# Run specific test category
docker-compose run --rm api pytest tests/test_hardware.py

# Run with coverage
docker-compose run --rm api pytest --cov=dahdi_phone
```

## Debugging

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

## Troubleshooting

### Common Issues

1. Device Permission Errors
   - Verify host device permissions: `ls -l /dev/dahdi/*`
   - Check group membership: `groups $USER`
   - Review container logs: `docker-compose logs api`

2. Module Loading Issues
   - Check kernel module status: `lsmod | grep dahdi`
   - View kernel messages: `dmesg | grep dahdi`
   - Verify module parameters: `modinfo dahdi`

3. Container Access Problems
   - Check volume mounts: `docker-compose config`
   - Verify SELinux context: `ls -Z /dev/dahdi/*`
   - Review container privileges: `docker inspect dahdi-api`

4. API Connection Issues
   - Verify ports are exposed: `docker-compose ps`
   - Check network connectivity: `curl localhost:8000/status`
   - Review API logs: `docker-compose logs api | grep ERROR`

### Logging

Logs are available in several locations:

1. Container Logs:
   - API logs: `/var/log/dahdi_phone/api.log`
   - Installation logs: `/var/log/dahdi_phone/install.log`

2. Host System Logs:
   - Kernel messages: `dmesg`
   - System logs: `/var/log/syslog`

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

### Development Guidelines

- Use type hints for all function definitions
- Maintain 90% or higher test coverage
- Follow PEP 8 style guide
- Document all public interfaces
- Add logging for significant operations

## Architecture

Key architectural components are documented in `/docs/architecture.md`, including:

- Host-Container relationship
- DAHDI hardware abstraction approach
- Event system design
- Buffer management strategy
- Error handling philosophy
- API contract design

## Security

- API uses token-based authentication
- All device access is read-only where possible
- Container runs with minimal required privileges
- Regular security updates via Docker base image

## License

This project is licensed under the MIT License - see LICENSE.md

## Acknowledgments

- DAHDI Project Team
- OpenVox Hardware Documentation
- Python Telephony Community
- Docker Community

## Support

For support:
1. Check the documentation in `/docs`
2. Review closed issues on GitHub
3. Open a new issue with logs and configuration
4. Join our community chat

## Roadmap

Planned features:
1. Multiple line support
2. Advanced audio processing
3. Call recording capabilities
4. WebRTC integration
5. Enhanced monitoring tools

For detailed status, see our project roadmap in `/docs/roadmap.md`