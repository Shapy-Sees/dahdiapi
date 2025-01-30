# src/dahdi_phone/api/server.py
"""
Main server implementation for the DAHDI Phone API.
Initializes FastAPI application, sets up logging and configuration,
handles WebSocket connections, and manages API routes.
Provides centralized error handling and request logging.
"""

import asyncio
import logging
import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from typing import Any, Dict

from ..utils.config import Config, ConfigurationError
from ..utils.logger import DAHDILogger, LoggerConfig, log_function_call

# Configure module logger
logger = logging.getLogger(__name__)

class DAHDIPhoneAPI:
    """
    Main API server class that initializes and manages the FastAPI application.
    Handles configuration, logging setup, and core service initialization.
    """
    def __init__(self):
        # Load and configure logger first
        self.config = Config()
        self.logger = DAHDILogger()
        
        # Now that logger is configured, we can import modules that use it
        from ..core.dahdi_interface import DAHDIInterface
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
            description="REST and WebSocket API for DAHDI telephony hardware",
            version="1.0.0"
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
                logger.info("Initializing DAHDI interface")
                self.dahdi_interface = self.DAHDIInterface(self.config.dahdi.device)
                await self.dahdi_interface.initialize()

                logger.info("Initializing audio processor")
                audio_config = self.AudioConfig(
                    sample_rate=self.config.dahdi.sample_rate,
                    frame_size=self.config.dahdi.buffer_size,
                    channels=self.config.dahdi.channels,
                    bit_depth=self.config.dahdi.bit_depth
                )
                self.audio_processor = self.AudioProcessor(audio_config)
                
                # Start event processing loop
                asyncio.create_task(self._process_events())
                
                logger.info("Server startup completed successfully")
                
            except Exception as e:
                logger.error(f"Startup failed: {str(e)}", exc_info=True)
                raise

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
        try:
            while True:
                event = await self.dahdi_interface.get_next_event()
                if event:
                    # Convert hardware event to API event
                    api_event = self._convert_event(event)
                    
                    # Broadcast to all connected clients
                    for connection in self.active_connections:
                        try:
                            await connection.send_json(api_event)
                        except Exception as e:
                            logger.error(f"Failed to send event: {str(e)}")
                            self.active_connections.remove(connection)
                            
                await asyncio.sleep(0.01)  # Small delay to prevent CPU spinning
                
        except Exception as e:
            logger.error(f"Event processing error: {str(e)}", exc_info=True)

    def _convert_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Convert hardware events to API event format"""
        try:
            # Map hardware events to API events
            event_type = event.get('type')
            if event_type == 'hook_state':
                return {
                    'type': self.PhoneEventTypes.OFF_HOOK if event['state'] else self.PhoneEventTypes.ON_HOOK,
                    'timestamp': event['timestamp']
                }
            # Add more event type conversions as needed
            return event
            
        except Exception as e:
            logger.error(f"Event conversion error: {str(e)}", exc_info=True)
            return {'type': self.PhoneEventTypes.ERROR, 'error': str(e)}

def run_server():
    """Start the DAHDI Phone API server"""
    try:
        # Create and configure server
        api = DAHDIPhoneAPI()
        
        # Get configuration
        config = Config()
        
        # Start server
        uvicorn.run(
            api.app,
            host=config.server.host,
            port=config.server.rest_port,
            workers=config.server.workers
        )
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Server startup failed: {str(e)}", exc_info=True)
        raise
