# src/core/state_manager.py
"""
Core state management module for DAHDI Phone API.
Handles phone line state transitions, state validation, event generation, and DTMF tracking.
Maintains state history and provides thread-safe state access with comprehensive logging.
Integrates with project-wide logging and configuration systems.
"""

import asyncio
import threading
from datetime import datetime
from typing import Optional, Dict, List, Any
from enum import Enum
from dataclasses import dataclass, asdict

from ..utils.logger import DAHDILogger, log_function_call
from ..utils.config import Config
from ..api.models import PhoneState, PhoneStatus, LineVoltage, CallStatistics, DTMFEvent

# Get structured logger instance
logger = DAHDILogger().get_logger(__name__)

class StateTransitionError(Exception):
    """Custom exception for invalid state transitions"""
    pass

@dataclass
class StateTransition:
    """Records a state transition with metadata"""
    from_state: PhoneState
    to_state: PhoneState
    timestamp: datetime
    reason: str
    metadata: Dict[str, Any]

@dataclass
class DTMFHistory:
    """Tracks DTMF tone history"""
    digit: str
    timestamp: datetime
    duration: int
    signal_level: float

class StateManager:
    """
    Manages phone line state with thread-safe operations and comprehensive logging.
    Validates state transitions and maintains state history.
    Now includes DTMF tracking capabilities.
    """
    def __init__(self):
        self._state = PhoneState.INITIALIZING
        self._lock = threading.Lock()
        self._state_history: List[StateTransition] = []
        self._subscribers = set()
        self._line_voltage = 48.0  # Default FXS voltage
        self._call_stats = CallStatistics()
        self._config = Config()
        self._last_error: Optional[str] = None
        
        # DTMF tracking
        self._last_dtmf: Optional[DTMFHistory] = None
        self._dtmf_history: List[DTMFHistory] = []
        self._max_dtmf_history = 100  # Keep last 100 DTMF events
        
        # Initialize logger with context
        self.log = logger.bind(
            component="StateManager",
            initial_state=self._state
        )
        
        self._setup_logging()
        self.log.info("state_manager_init", message="Initializing state manager")

    def _setup_logging(self) -> None:
        """Configure state manager specific logging"""
        self.debug_stats = {
            'total_transitions': 0,
            'invalid_transitions': 0,
            'error_states': 0,
            'subscriber_notifications': 0,
            'dtmf_events': 0
        }
        self.log.debug("debug_stats_initialized",
                      message="State manager debug statistics initialized",
                      initial_stats=self.debug_stats)

    @log_function_call(level="DEBUG")
    async def initialize(self) -> None:
        """Initialize state manager and validate initial state"""
        try:
            self.log.info("initialization_start", message="Starting state manager initialization")
            
            # Validate initial state
            await self.set_state(PhoneState.IDLE, "Initialization complete")
            
            self.log.info("initialization_complete", message="State manager initialized successfully")
            
        except Exception as e:
            self.log.error("initialization_failed",
                          message="Failed to initialize state manager",
                          error=str(e),
                          exc_info=True)
            await self.set_state(PhoneState.ERROR, f"Initialization failed: {str(e)}")
            raise

    @property
    def current_state(self) -> PhoneState:
        """Thread-safe access to current state"""
        with self._lock:
            return self._state

    @log_function_call(level="DEBUG")
    async def handle_dtmf_event(self, event: DTMFEvent) -> None:
        """
        Process and store DTMF event information.
        
        Args:
            event: DTMF event to process
        """
        try:
            with self._lock:
                # Create DTMF history entry
                dtmf_entry = DTMFHistory(
                    digit=event.digit,
                    timestamp=event.timestamp,
                    duration=event.duration,
                    signal_level=event.signal_level
                )
                
                # Update last DTMF and history
                self._last_dtmf = dtmf_entry
                self._dtmf_history.append(dtmf_entry)
                
                # Trim history if needed
                if len(self._dtmf_history) > self._max_dtmf_history:
                    self._dtmf_history = self._dtmf_history[-self._max_dtmf_history:]
                
                self.debug_stats['dtmf_events'] += 1
                
                self.log.info("dtmf_event_processed",
                            message=f"DTMF event processed: {event.digit}",
                            digit=event.digit,
                            timestamp=event.timestamp.isoformat())
                
        except Exception as e:
            self.log.error("dtmf_processing_failed",
                          message="Failed to process DTMF event",
                          error=str(e),
                          exc_info=True)
            raise

    @log_function_call(level="DEBUG")
    async def set_state(self, new_state: PhoneState, reason: str, metadata: Dict[str, Any] = None) -> None:
        """
        Set new phone state with validation and event notification.
        
        Args:
            new_state: Target phone state
            reason: Reason for state change
            metadata: Optional additional state change information
        """
        if metadata is None:
            metadata = {}

        try:
            with self._lock:
                if not self._is_valid_transition(self._state, new_state):
                    self.log.error("invalid_transition",
                                 message="Invalid state transition",
                                 from_state=self._state,
                                 to_state=new_state)
                    self.debug_stats['invalid_transitions'] += 1
                    raise StateTransitionError(
                        f"Invalid transition: {self._state} -> {new_state}"
                    )

                old_state = self._state
                self._state = new_state
                
                # Record transition
                transition = StateTransition(
                    from_state=old_state,
                    to_state=new_state,
                    timestamp=datetime.utcnow(),
                    reason=reason,
                    metadata=metadata
                )
                self._state_history.append(transition)
                
                # Update statistics
                self.debug_stats['total_transitions'] += 1
                if new_state == PhoneState.ERROR:
                    self.debug_stats['error_states'] += 1

                # Update call statistics
                self._update_call_stats(old_state, new_state)

                self.log.info("state_changed",
                            message=f"State changed: {old_state} -> {new_state}",
                            from_state=old_state,
                            to_state=new_state,
                            reason=reason,
                            metadata=metadata)

            # Notify subscribers (outside lock to prevent deadlocks)
            await self._notify_subscribers(old_state, new_state, reason, metadata)
            
        except Exception as e:
            self.log.error("state_change_failed",
                          message="Failed to change state",
                          error=str(e),
                          exc_info=True)
            self._last_error = str(e)
            raise

    def _is_valid_transition(self, from_state: PhoneState, to_state: PhoneState) -> bool:
        """
        Validate state transition according to phone line state machine rules.
        
        Args:
            from_state: Current state
            to_state: Target state
            
        Returns:
            True if transition is valid
        """
        # Define valid transitions
        valid_transitions = {
            PhoneState.INITIALIZING: {PhoneState.IDLE, PhoneState.ERROR},
            PhoneState.IDLE: {PhoneState.RINGING, PhoneState.OFF_HOOK, PhoneState.ERROR},
            PhoneState.RINGING: {PhoneState.IDLE, PhoneState.OFF_HOOK, PhoneState.ERROR},
            PhoneState.OFF_HOOK: {PhoneState.IDLE, PhoneState.IN_CALL, PhoneState.ERROR},
            PhoneState.IN_CALL: {PhoneState.OFF_HOOK, PhoneState.IDLE, PhoneState.ERROR},
            PhoneState.ERROR: {PhoneState.INITIALIZING, PhoneState.IDLE}
        }

        return to_state in valid_transitions.get(from_state, set())

    def _update_call_stats(self, old_state: PhoneState, new_state: PhoneState) -> None:
        """Update call statistics based on state transition"""
        if old_state != PhoneState.IN_CALL and new_state == PhoneState.IN_CALL:
            self._call_stats.total_calls += 1
        elif old_state == PhoneState.IN_CALL and new_state != PhoneState.IN_CALL:
            if new_state == PhoneState.IDLE:
                self._call_stats.successful_calls += 1
            else:
                self._call_stats.failed_calls += 1
            self._call_stats.last_call_timestamp = datetime.utcnow()

    @log_function_call(level="DEBUG")
    async def subscribe(self, callback: callable) -> None:
        """
        Subscribe to state change notifications.
        
        Args:
            callback: Async function to call on state change
        """
        with self._lock:
            self._subscribers.add(callback)
        self.log.debug("subscriber_added",
                      message="Added state change subscriber",
                      total_subscribers=len(self._subscribers))

    @log_function_call(level="DEBUG")
    async def unsubscribe(self, callback: callable) -> None:
        """
        Unsubscribe from state change notifications.
        
        Args:
            callback: Previously registered callback
        """
        with self._lock:
            self._subscribers.discard(callback)
        self.log.debug("subscriber_removed",
                      message="Removed state change subscriber",
                      total_subscribers=len(self._subscribers))

    async def _notify_subscribers(self, old_state: PhoneState, new_state: PhoneState,
                                reason: str, metadata: Dict[str, Any]) -> None:
        """Notify all subscribers of state change"""
        notification_tasks = []
        
        for callback in self._subscribers:
            task = asyncio.create_task(callback(old_state, new_state, reason, metadata))
            notification_tasks.append(task)
            
        self.debug_stats['subscriber_notifications'] += len(notification_tasks)
        
        # Wait for all notifications to complete
        if notification_tasks:
            await asyncio.gather(*notification_tasks, return_exceptions=True)

    @log_function_call(level="DEBUG")
    async def update_line_voltage(self, voltage: float) -> None:
        """
        Update current line voltage measurement.
        
        Args:
            voltage: New line voltage reading
        """
        with self._lock:
            self._line_voltage = voltage
        self.log.debug("voltage_updated",
                      message=f"Line voltage updated: {voltage}V",
                      voltage=voltage)

    @log_function_call(level="DEBUG")
    async def get_status(self) -> PhoneStatus:
        """
        Get complete current phone status including DTMF information.
        
        Returns:
            PhoneStatus object with current state information
        """
        with self._lock:
            status = PhoneStatus(
                state=self._state,
                line_voltage=self._line_voltage,
                call_stats=self._call_stats,
                error_message=self._last_error,
                last_update=datetime.utcnow(),
                last_dtmf=self._last_dtmf.digit if self._last_dtmf else None,
                dtmf_history=[{
                    'digit': dtmf.digit,
                    'timestamp': dtmf.timestamp.isoformat(),
                    'duration': dtmf.duration,
                    'signal_level': dtmf.signal_level
                } for dtmf in self._dtmf_history[-10:]]  # Include last 10 DTMF events
            )
        
        self.log.debug("status_retrieved",
                      message="Retrieved phone status",
                      status=asdict(status))
        return status

    async def get_state_history(self) -> List[StateTransition]:
        """Get list of state transitions"""
        with self._lock:
            return self._state_history.copy()

    async def get_dtmf_history(self, limit: int = None) -> List[DTMFHistory]:
        """
        Get DTMF event history.
        
        Args:
            limit: Optional limit on number of events to return
            
        Returns:
            List of DTMF history entries
        """
        with self._lock:
            history = self._dtmf_history.copy()
            if limit:
                history = history[-limit:]
            return history

    async def get_debug_info(self) -> dict:
        """Get debug statistics and state information"""
        debug_info = {
            **self.debug_stats,
            'current_state': self._state,
            'subscribers': len(self._subscribers),
            'history_length': len(self._state_history),
            'last_error': self._last_error,
            'dtmf_history_length': len(self._dtmf_history),
            'last_dtmf': asdict(self._last_dtmf) if self._last_dtmf else None
        }
        self.log.debug("debug_info_retrieved",
                      message="Retrieved debug information",
                      debug_info=debug_info)
        return debug_info