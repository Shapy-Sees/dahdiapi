# DAHDI Phone API Architecture

This document details the architectural decisions, system design, and implementation approach for the DAHDI Phone API project. Our architecture focuses on providing a reliable, maintainable, and efficient interface to DAHDI telephony hardware while ensuring proper abstraction and error handling.

## System Overview

The DAHDI Phone API serves as a bridge between traditional telephony hardware and modern software systems. It transforms low-level DAHDI interactions into a clean, RESTful API with WebSocket support for real-time events. The system operates in a containerized environment while maintaining direct hardware access through the host system.

### Host-Container Architecture

The system utilizes a split architecture where components are divided between the host system and Docker container:

#### Host System Components
1. Kernel Layer
   - DAHDI kernel modules
   - Hardware drivers
   - Interrupt handling
   - Device management
   - Kernel-level configuration

2. Device Layer
   - Device nodes (/dev/dahdi/*)
   - Hardware access permissions
   - System resource allocation
   - Buffer management

#### Container Components
1. Application Layer
   - REST API endpoints
   - WebSocket server
   - Business logic
   - State management

2. DAHDI Tools Layer
   - Userspace utilities
   - Configuration tools
   - Diagnostic tools
   - Device communication

### Core Principles

1. Hardware Isolation
   - Host system handles all kernel-level operations
   - Container restricted to userspace operations
   - Clear separation between hardware and API layers
   - Minimal privileged access requirements

2. Real-time Event Handling
   - Direct hardware event propagation
   - Minimal latency overhead
   - Event buffering and queuing
   - Proper resource cleanup

3. Type Safety
   - Strong typing throughout the system
   - Input validation at all layers
   - Clear interface contracts
   - Error type hierarchies

4. Error Resilience
   - Comprehensive error handling
   - Automatic recovery mechanisms
   - Graceful degradation
   - Detailed error reporting

## Component Architecture

### Layer 1: Hardware Interface

The lowest layer handles direct DAHDI communication:

```python
class DAHDIInterface:
    """
    Direct interface to DAHDI hardware through ioctl calls.
    Manages raw device access and hardware-level operations.
    """
    def __init__(self, device_path: str):
        self.device_fd = None
        self.device_path = device_path
        self.audio_buffer = CircularBuffer(BUFFER_SIZE)
        
    async def initialize(self):
        """
        Opens and configures DAHDI device with proper error handling.
        Sets up initial device state and verifies connectivity.
        """
        try:
            self.device_fd = os.open(self.device_path, os.O_RDWR)
            await self._configure_device()
        except OSError as e:
            raise DAHDIError("Failed to initialize device") from e
```

Key responsibilities:
- Raw device access through ioctl calls
- Buffer management for audio streaming
- Direct hardware control operations
- Low-level error detection

### Layer 2: Hardware Abstraction

Above the raw interface, we provide hardware abstraction:

```python
class FXSPort:
    """
    Abstracts FXS port operations into high-level functionality.
    Manages phone line states and provides clean interface for operations.
    """
    def __init__(self, dahdi: DAHDIInterface):
        self.dahdi = dahdi
        self.state = PhoneState.IDLE
        self.voltage = 48.0  # Normal FXS voltage
        
    async def ring(self, duration: int):
        """
        Generates ring signal with proper timing and voltage control.
        Manages state transitions and event emission.
        """
        try:
            await self._set_ring_voltage()
            await self.dahdi.signal_ring(duration)
            self._emit_ring_start()
        except DAHDIError as e:
            await self._handle_ring_error(e)
```

Key responsibilities:
- High-level phone operations
- State management
- Event generation
- Error recovery logic

### Layer 3: Core Services

The service layer implements business logic:

```python
class PhoneService:
    """
    Coordinates phone operations and manages system state.
    Implements business logic and service integration.
    """
    def __init__(self, fxs: FXSPort):
        self.fxs = fxs
        self.audio_processor = AudioProcessor()
        self.dtmf_detector = DTMFDetector()
        
    async def handle_off_hook(self):
        """
        Processes off-hook state transition with proper sequencing.
        Manages audio streaming and DTMF detection initialization.
        """
        await self.fxs.stop_ring()
        await self.audio_processor.start()
        await self.dtmf_detector.enable()
        self._emit_state_change(PhoneState.OFF_HOOK)
```

Key responsibilities:
- Business logic coordination
- Service integration
- State transitions
- Event processing

### Layer 4: API Interface

The top layer exposes our REST and WebSocket APIs:

```python
class PhoneAPI:
    """
    Implements REST and WebSocket interfaces for phone control.
    Manages client connections and request handling.
    """
    def __init__(self, phone_service: PhoneService):
        self.service = phone_service
        self.clients = set()
        
    async def handle_ring_request(self, duration: int):
        """
        Processes ring requests with parameter validation.
        Manages async operations and client notifications.
        """
        try:
            await self.service.ring(duration)
            await self._notify_clients(Event.RING_START)
        except ServiceError as e:
            await self._handle_api_error(e)
```

Key responsibilities:
- REST endpoint implementation
- WebSocket event distribution
- Request validation
- Response formatting

## Data Flow Architecture

### Audio Processing Pipeline

Our audio processing follows a streaming architecture:

```
[DAHDI Hardware] → [Host Kernel Buffer] → [Container Buffer] → [AudioProcessor] → [DTMFDetector]
                                                                              → [VoiceDetector]
                                                                              → [Clients]
```

Design decisions:
1. Use circular buffers to prevent memory growth
2. Process audio in 20ms frames (160 samples at 8kHz)
3. Implement non-blocking stream processing
4. Provide backpressure mechanisms

### Event System

Events flow through the system in a structured way:

```
[Hardware Events] → [Kernel] → [DAHDI Device] → [Container] → [Event Bus] → [State Manager] → [WebSocket Server]
                                                                         → [Service Layer] → [REST Responses]
```

Event handling features:
1. Typed event definitions
2. Guaranteed delivery ordering
3. Client-specific filtering
4. Automatic reconnection support

## State Management

The system maintains state at multiple levels:

### Hardware State
- Line voltage
- Hook status
- Ring status
- Audio buffers

### Service State
- Phone line state
- Active operations
- Client connections
- Resource usage

### API State
- Client sessions
- WebSocket connections
- Request tracking
- Rate limiting

## Error Handling Architecture

Our error handling follows a layered approach:

### Layer 1: Hardware Errors
- Device access issues
- Buffer overflows
- Timing problems
- Voltage issues

```python
try:
    await self.dahdi.write(buffer)
except DAHDIError as e:
    if isinstance(e, BufferError):
        await self._handle_buffer_error(e)
    elif isinstance(e, TimingError):
        await self._handle_timing_error(e)
    else:
        await self._handle_hardware_error(e)
```

### Layer 2: Service Errors
- State transitions
- Resource allocation
- Operation timing
- Event processing

### Layer 3: API Errors
- Invalid requests
- Client disconnections
- Rate limiting
- Authentication

## Container Security Architecture

### Principle of Least Privilege
1. Container Access Controls
   - Read-only access to DAHDI devices
   - Minimal required capabilities
   - No root access requirement
   - Isolated network access

2. Resource Limitations
   - Memory limits
   - CPU constraints
   - File descriptor limits
   - Network restrictions

### Security Considerations
1. Device Access
   - Proper permissions on host devices
   - Group-based access control
   - SELinux/AppArmor profiles
   - Device node isolation

2. API Security
   - Token-based authentication
   - Request validation
   - Rate limiting
   - Error message sanitization

## Performance Considerations

### Buffer Management
- Fixed-size circular buffers
- Zero-copy operations where possible
- Proper buffer alignment
- Memory pool usage

### Event Processing
- Asynchronous event handling
- Event batching
- Client-side filtering
- Connection pooling

### Resource Management
- Connection limits
- Operation timeouts
- Resource cleanup
- Memory limits

## Monitoring and Diagnostics

### Health Checks
- Hardware status
- Service status
- Resource usage
- Error rates
- Container health

### Logging Architecture
- Structured logging
- Log levels
- Context preservation
- Log rotation
- Container log management

### Metrics
- Operation latency
- Resource usage
- Error rates
- Client activity
- Container performance

## Future Considerations

### Scalability
- Multiple phone line support
- Load balancing
- Resource pooling
- Client scaling
- Container orchestration

### Enhancement Paths
- Additional audio codecs
- Extended DTMF features
- Voice processing
- Call recording
- Container optimization

## Development Guidelines

When extending the system, consider:

1. Hardware Interaction
   - Always use proper error handling
   - Implement timeouts
   - Clean up resources
   - Validate operations

2. State Management
   - Maintain state consistency
   - Handle race conditions
   - Implement proper locking
   - Validate transitions

3. Event Processing
   - Use proper typing
   - Handle backpressure
   - Implement filtering
   - Manage resources

4. Container Development
   - Follow Docker best practices
   - Maintain minimal image size
   - Implement proper health checks
   - Handle graceful shutdown

5. Error Handling
   - Implement recovery mechanisms
   - Provide context
   - Log appropriately
   - Notify clients

This architecture provides a solid foundation for building reliable telephone integration while maintaining clean abstractions and proper resource management in a containerized environment.