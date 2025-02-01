# src/dahdi_phone/api/server.py
"""
Main server implementation for the DAHDI Phone API.
Initializes FastAPI application, sets up logging and configuration,
handles WebSocket connections, and manages API routes.
Provides centralized error handling and request logging.
"""

import asyncio
import logging
import os
import sys
import uvicorn
from fastapi import FastAPI, Request, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from typing import Any, Dict, Optional

from ..utils.config import Config, ConfigurationError
from ..utils.logger import DAHDILogger, LoggerConfig, log_function_call
from ..core.dahdi_interface import DAHDIInterface, DAHDIIOError

# Configure module logger
logger = DAHDILogger().get_logger(__name__)

# Global interface instance
_dahdi_interface: Optional[DAHDIInterface] = None

def get_dahdi_interface() -> DAHDIInterface:
    """FastAPI dependency to get the DAHDI interface instance"""
    if _dahdi_interface is None:
        raise RuntimeError("DAHDI interface not initialized")
    return _dahdi_interface

class DAHDIPhoneAPI:
    """
    Main API server class that initializes and manages the FastAPI application.
    Handles configuration, logging setup, and core service initialization.
    """
    def __init__(self):
        # Load configuration
        self.config = Config()
        # Get the already configured logger instance
        self.logger = DAHDILogger()
        
        # Import modules
        from ..core.audio_processor import AudioProcessor, AudioConfig
        from .models import PhoneState, PhoneStatus
        from .routes import router as api_router
        from .websocket import PhoneEventTypes
        
        # Store imports as class attributes
        self.DAHDIInterface = DAHDIInterface
        self.AudioProcessor = AudioProcessor
        self.AudioConfig = AudioConfig
        self.PhoneState = PhoneState
        self.PhoneStatus = PhoneStatus
        self.api_router = api_router
        self.PhoneEventTypes = PhoneEventTypes
        
        self.app = FastAPI(
            title="DAHDI Phone API",
            description="""
            REST and WebSocket API for DAHDI telephony hardware.
            
            ## Features
            
            * Phone line status monitoring
            * Ring control
            * Audio playback and recording
            * DTMF tone detection and generation
            * Real-time event notifications via WebSocket
            
            ## Authentication
            
            This API currently does not require authentication. It is designed for internal network use only.
            
            ## Error Handling
            
            The API uses standard HTTP status codes and returns detailed error messages in JSON format.
            Common error codes:
            * 400: Bad Request - Invalid parameters or state
            * 404: Not Found - Resource not found
            * 500: Internal Server Error - Hardware or system error
            
            ## WebSocket Events
            
            Connect to `/ws` endpoint for real-time events including:
            * Phone state changes
            * DTMF detection
            * Line voltage updates
            * Error notifications
            """,
            version="1.0.0",
            openapi_tags=[
                {
                    "name": "status",
                    "description": "Phone line status operations"
                },
                {
                    "name": "control",
                    "description": "Phone control operations including ring and audio"
                },
                {
                    "name": "websocket",
                    "description": "Real-time event notifications"
                }
            ],
            docs_url="/docs",
            redoc_url="/redoc",
            openapi_url="/openapi.json",
            swagger_ui_parameters={"defaultModelsExpandDepth": -1}
        )
        self.dahdi_interface = None
        self.audio_processor = None
        
        # Store active WebSocket connections
        self.active_connections = set()
        
        # Initialize API
        self._setup_middleware()
        self._setup_exception_handlers()
        self._setup_routes()
        
        logger.info("DAHDI Phone API server initialized")

    @log_function_call(level="DEBUG")
    def _setup_middleware(self) -> None:
        """Configure API middleware including CORS and request logging"""
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=self.config.security.allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Add request logging middleware
        @self.app.middleware("http")
        async def log_requests(request: Request, call_next):
            logger.debug(f"Request: {request.method} {request.url}")
            response = await call_next(request)
            logger.debug(f"Response status: {response.status_code}")
            return response

    @log_function_call(level="DEBUG")
    def _setup_exception_handlers(self) -> None:
        """Configure global exception handlers"""
        @self.app.exception_handler(RequestValidationError)
        async def validation_exception_handler(request: Request, exc: RequestValidationError):
            logger.error(f"Validation error: {str(exc)}")
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={"detail": exc.errors()}
            )

        @self.app.exception_handler(Exception)
        async def general_exception_handler(request: Request, exc: Exception):
            logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"}
            )

    @log_function_call(level="DEBUG")
    def _setup_routes(self) -> None:
        """Configure API routes and startup/shutdown events"""
        # Include API routes
        self.app.include_router(self.api_router)

        @self.app.on_event("startup")
        async def startup_event():
            """Initialize hardware interface and services on startup"""
            try:
                logger.debug("Starting server initialization sequence")
                
                logger.debug(f"Server host: {self.config.server.host}")
                logger.debug(f"REST port: {self.config.server.rest_port}")
                logger.debug(f"WebSocket port: {self.config.server.websocket_port}")
                logger.debug(f"Worker count: {self.config.server.workers}")

                logger.debug("Starting DAHDI hardware detection")
                logger.debug(f"Checking DAHDI device path: {self.config.dahdi.device}")
                logger.debug(f"DAHDI control path: {self.config.dahdi.control}")
                logger.debug(f"DAHDI channel: {self.config.dahdi.channel}")
                if not os.path.exists(self.config.dahdi.device):
                    error_msg = f"DAHDI device not found at {self.config.dahdi.device}"
                    logger.error(error_msg)
                    raise DAHDIIOError(error_msg)

                logger.info("Initializing DAHDI interface")
                logger.debug("DAHDI hardware configuration:")
                logger.debug(f"Sample rate: {self.config.dahdi.sample_rate} Hz")
                logger.debug(f"Channels: {self.config.dahdi.channels}")
                logger.debug(f"Bit depth: {self.config.dahdi.bit_depth} bits")
                logger.debug(f"Buffer size: {self.config.dahdi.buffer_size} bytes")
                self.dahdi_interface = self.DAHDIInterface(self.config.dahdi.device)
                
                logger.debug("Starting DAHDI interface initialization")
                await self.dahdi_interface.initialize()
                logger.debug("DAHDI interface initialization completed")

                logger.info("Initializing audio processor")
                logger.debug("Audio processor configuration:")
                audio_config = self.AudioConfig(
                    sample_rate=self.config.dahdi.sample_rate,
                    frame_size=self.config.dahdi.buffer_size,
                    channels=self.config.dahdi.channels,
                    bit_depth=self.config.dahdi.bit_depth
                )
                self.audio_processor = self.AudioProcessor(audio_config)
                logger.debug("Audio processor initialization completed")
                
                # Store interface globally for dependency injection
                global _dahdi_interface
                _dahdi_interface = self.dahdi_interface
                
                logger.debug("Starting event processing loop")
                asyncio.create_task(self._process_events())
                logger.debug("Event processing loop started")
                
                logger.info("Server startup completed successfully")
                logger.debug("All subsystems initialized and running")
                
            except DAHDIIOError as e:
                logger.error(f"DAHDI hardware error: {str(e)}")
                sys.exit(1)  # Exit with error code
            except Exception as e:
                logger.error(f"Startup failed: {str(e)}", exc_info=True)
                sys.exit(1)  # Exit with error code

        @self.app.on_event("shutdown")
        async def shutdown_event():
            """Clean up resources on server shutdown"""
            try:
                logger.info("Shutting down server")
                
                # Close all WebSocket connections
                for connection in self.active_connections:
                    await connection.close()
                
                # Clean up hardware interface
                if self.dahdi_interface:
                    await self.dahdi_interface.cleanup()
                
                logger.info("Server shutdown completed successfully")
                
            except Exception as e:
                logger.error(f"Shutdown error: {str(e)}", exc_info=True)

    async def _process_events(self) -> None:
        """Process and broadcast hardware events to WebSocket clients"""
        logger.debug("Event processing loop started")
        event_count = 0
        try:
            while True:
                event = await self.dahdi_interface.get_next_event()
                if event:
                    event_count += 1
                    logger.debug(f"Received hardware event #{event_count}: {event}")
                    
                    # Convert hardware event to API event
                    api_event = self._convert_event(event)
                    logger.debug(f"Converted to API event: {api_event}")
                    
                    # Broadcast to all connected clients
                    active_count = len(self.active_connections)
                    logger.debug(f"Broadcasting event to {active_count} active connections")
                    
                    for connection in self.active_connections.copy():  # Use copy to avoid modification during iteration
                        try:
                            await connection.send_json(api_event)
                            logger.debug(f"Successfully sent event to connection {id(connection)}")
                        except Exception as e:
                            logger.error(f"Failed to send event to connection {id(connection)}: {str(e)}")
                            self.active_connections.remove(connection)
                            logger.debug(f"Removed failed connection {id(connection)}, {len(self.active_connections)} remaining")
                            
                await asyncio.sleep(0.01)  # Small delay to prevent CPU spinning
                
        except Exception as e:
            logger.error(f"Event processing error: {str(e)}", exc_info=True)
            sys.exit(1)  # Exit with error code

    def _convert_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Convert hardware events to API event format"""
        try:
            # Map hardware events to API events
            event_type = event.get('type')
            logger.debug(f"Converting event type: {event_type}")
            
            if event_type == 'hook_state':
                converted_event = {
                    'type': self.PhoneEventTypes.OFF_HOOK if event['state'] else self.PhoneEventTypes.ON_HOOK,
                    'timestamp': event['timestamp']
                }
                logger.debug(f"Converted hook_state event: {converted_event}")
                return converted_event
                
            # Add more event type conversions as needed
            logger.debug(f"No conversion needed for event type: {event_type}")
            return event
            
        except Exception as e:
            error_event = {'type': self.PhoneEventTypes.ERROR, 'error': str(e)}
            logger.error(f"Event conversion error: {str(e)}", exc_info=True)
            logger.debug(f"Returning error event: {error_event}")
            return error_event

def run_server(config_path: Optional[str] = None):
    """
    Start the DAHDI Phone API server
    
    Args:
        config_path: Optional path to configuration file. If not provided,
                    configuration should already be loaded by __main__.py
    """
    # Get the already configured logger instance
    logger = DAHDILogger()
    
    # Get configured logger for this module
    server_logger = logger.get_logger(__name__)
    try:
        server_logger.debug("Starting DAHDI Phone API server")
        
        # Create and configure server
        server_logger.debug("Creating DAHDIPhoneAPI instance")
        api = DAHDIPhoneAPI()
        
        # Get existing configuration
        server_logger.debug("Getting server configuration")
        config = Config()  # This will get the singleton instance already configured
        
        # Log server startup details with full configuration info
        server_logger.info("Starting server with configuration:")
        server_logger.debug(f"Host: {config.server.host}")
        server_logger.debug(f"REST Port: {config.server.rest_port}")
        server_logger.debug(f"Workers: {config.server.workers}")
        server_logger.debug(f"Log Level: {config.logging.level}")
        server_logger.debug(f"Log Format: {config.logging.format}")
        server_logger.debug(f"Log Output: {config.logging.output}")
        server_logger.debug(f"Development Mode: {config.development.enabled}")
        
        # Start server
        try:
            server_logger.debug("Initializing uvicorn server")
            uvicorn.run(
                api.app,
                host=config.server.host,
                port=config.server.rest_port,
                workers=config.server.workers,
                log_level=config.logging.level.lower()
            )
        except Exception as e:
            server_logger.error("Server runtime error", exc_info=True)
            server_logger.debug(f"Error details: {str(e)}")
            sys.exit(1)  # Exit with error code
            
    except ConfigurationError as e:
        server_logger.error("Configuration error during server startup", exc_info=True)
        server_logger.debug(f"Configuration error details: {str(e)}")
        sys.exit(1)  # Exit with error code
    except Exception as e:
        server_logger.error("Unexpected error during server startup", exc_info=True)
        server_logger.debug(f"Error details: {str(e)}")
        sys.exit(1)  # Exit with error code
