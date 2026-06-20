"""Event Bus — Decoupled cross-module communication for Daemon.

Replaces direct method calls and tight coupling with a pub/sub pattern.
All events are synchronous (same-thread) for simplicity and determinism.
Thread-safety: Events from worker threads should use Qt signals to reach main thread first.
"""
from __future__ import annotations
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from weakref import WeakSet

logger = logging.getLogger(__name__)


class EventType(Enum):
    """All event types in the system."""

    # FSM Events
    FSM_STATE_CHANGED = "fsm_state_changed"
    FSM_TRANSITION_DENIED = "fsm_transition_denied"

    # Emotion Events
    EMOTION_SHIFTED = "emotion_shifted"

    # Input Events
    USER_INPUT_RECEIVED = "user_input_received"
    USER_HOTKEY_PRESSED = "user_hotkey_pressed"

    # Autonomous Behavior Events
    AUTONOMOUS_TRIGGER_FIRED = "autonomous_trigger_fired"
    AUTONOMOUS_QUERY_STARTED = "autonomous_query_started"
    AUTONOMOUS_QUERY_COMPLETED = "autonomous_query_completed"

    # LLM Events
    LLM_SESSION_CREATED = "llm_session_created"
    LLM_SESSION_CLOSED = "llm_session_closed"
    LLM_REQUEST_SENT = "llm_request_sent"
    LLM_RESPONSE_RECEIVED = "llm_response_received"
    LLM_ERROR = "llm_error"

    # Memory Events
    MEMORY_UPDATED = "memory_updated"
    MEMORY_SYNC_COMPLETED = "memory_sync_completed"
    BRAIN_UPDATE_RECEIVED = "brain_update_received"

    # Diary/History Events
    DIARY_ENTRY_ADDED = "diary_entry_added"
    HISTORY_ENTRY_ADDED = "history_entry_added"

    # System Events
    SYSTEM_IDLE_DETECTED = "system_idle_detected"
    SYSTEM_ACTIVITY_DETECTED = "system_activity_detected"
    SCREEN_CONTENT_CHANGED = "screen_content_changed"
    APM_THRESHOLD_CROSSED = "apm_threshold_crossed"
    TYPING_BURST_DETECTED = "typing_burst_detected"
    SCREEN_TIME_THRESHOLD_REACHED = "screen_time_threshold_reached"

    # Health/Status Events
    BRAIN_DISCONNECTED = "brain_disconnected"
    BRAIN_RECONNECTED = "brain_reconnected"
    MCP_TOOL_CALLED = "mcp_tool_called"
    MCP_TOOL_BLOCKED = "mcp_tool_blocked"

    # Auth Events
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    AUTH_CLEARED = "auth_cleared"
    TOKEN_REFRESHED = "token_refreshed"

    # Pet Lifecycle Events
    PET_SLEEP_STARTED = "pet_sleep_started"
    PET_SLEEP_ENDED = "pet_sleep_ended"
    PET_BOOT_COMPLETED = "pet_boot_completed"
    PET_SHUTDOWN_STARTED = "pet_shutdown_started"


@dataclass(frozen=True)
class Event:
    """Immutable event payload."""
    type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""
    data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.source:
            object.__setattr__(self, 'source', 'unknown')


class EventBus:
    """Central event bus for decoupled communication.

    Features:
    - Sync delivery (callbacks execute in publisher's thread)
    - Weak references to avoid memory leaks
    - Per-event-type subscription
    - Wildcard subscription for debugging/logging
    - Event history buffer for replay/debugging
    """

    def __init__(self, history_size: int = 1000):
        self._subscribers: Dict[EventType, Set[Callable[[Event], None]]] = defaultdict(set)
        self._wildcard_subscribers: WeakSet[Callable[[Event], None]] = WeakSet()
        self._history: List[Event] = []
        self._history_size = history_size
        self._publishing = False

    def subscribe(self, event_type: EventType, callback: Callable[[Event], None]) -> None:
        """Subscribe to a specific event type."""
        self._subscribers[event_type].add(callback)
        logger.debug("Subscribed %s to %s", callback.__qualname__, event_type.value)

    def unsubscribe(self, event_type: EventType, callback: Callable[[Event], None]) -> bool:
        """Unsubscribe from a specific event type. Returns True if was subscribed."""
        if callback in self._subscribers[event_type]:
            self._subscribers[event_type].discard(callback)
            logger.debug("Unsubscribed %s from %s", callback.__qualname__, event_type.value)
            return True
        return False

    def subscribe_all(self, callback: Callable[[Event], None]) -> None:
        """Subscribe to ALL events (wildcard). Useful for logging/tracing."""
        self._wildcard_subscribers.add(callback)

    def unsubscribe_all(self, callback: Callable[[Event], None]) -> bool:
        """Unsubscribe from wildcard."""
        try:
            self._wildcard_subscribers.discard(callback)
            return True
        except ValueError:
            return False

    def publish(self, event: Event) -> int:
        """Publish event to all subscribers. Returns number of callbacks invoked."""
        if self._publishing:
            logger.warning("Re-entrant publish detected for %s", event.type.value)

        self._publishing = True
        try:
            # Add to history
            self._history.append(event)
            if len(self._history) > self._history_size:
                self._history.pop(0)

            count = 0

            # Specific subscribers
            for callback in self._subscribers[event.type]:
                try:
                    callback(event)
                    count += 1
                except Exception as e:
                    logger.exception("Event callback %s failed for %s: %s",
                                     callback.__qualname__, event.type.value, e)

            # Wildcard subscribers
            for callback in list(self._wildcard_subscribers):
                try:
                    callback(event)
                    count += 1
                except Exception as e:
                    logger.exception("Wildcard callback %s failed for %s: %s",
                                     callback.__qualname__, event.type.value, e)

            return count
        finally:
            self._publishing = False

    def publish_async(self, event: Event) -> None:
        """Publish event from non-main thread via Qt signal (placeholder).
        
        In practice, this would emit a Qt signal connected to a slot that calls
        `publish()`. The actual implementation depends on Qt integration.
        """
        # This is a hook - actual implementation would use Qt signals
        # For now, just call directly (caller must ensure thread-safety)
        self.publish(event)

    # Convenience methods for common events

    def emit_fsm_state_changed(self, old_state: str, new_state: str, source: str = "fsm") -> None:
        self.publish(Event(
            type=EventType.FSM_STATE_CHANGED,
            source=source,
            data={"old_state": old_state, "new_state": new_state}
        ))

    def emit_emotion_shifted(self, old_emotion: str, new_emotion: str, source: str = "animator") -> None:
        self.publish(Event(
            type=EventType.EMOTION_SHIFTED,
            source=source,
            data={"old_emotion": old_emotion, "new_emotion": new_emotion}
        ))

    def emit_user_input(self, text: str, source: str = "input") -> None:
        self.publish(Event(
            type=EventType.USER_INPUT_RECEIVED,
            source=source,
            data={"text": text}
        ))

    def emit_autonomous_trigger(self, mode: str, apm: int, idle_seconds: float, source: str = "autonomy") -> None:
        self.publish(Event(
            type=EventType.AUTONOMOUS_TRIGGER_FIRED,
            source=source,
            data={"mode": mode, "apm": apm, "idle_seconds": idle_seconds}
        ))

    def emit_llm_response(self, session_id: str, items_count: int, source: str = "llm") -> None:
        self.publish(Event(
            type=EventType.LLM_RESPONSE_RECEIVED,
            source=source,
            data={"session_id": session_id, "items_count": items_count}
        ))

    def emit_memory_updated(self, key: str, value: str, source: str = "memory") -> None:
        self.publish(Event(
            type=EventType.MEMORY_UPDATED,
            source=source,
            data={"key": key, "value": value}
        ))

    def emit_brain_update(self, applied_fields: Dict[str, Any], source: str = "llm") -> None:
        self.publish(Event(
            type=EventType.BRAIN_UPDATE_RECEIVED,
            source=source,
            data={"applied_fields": applied_fields}
        ))

    def emit_mcp_tool_called(self, tool_name: str, allowed: bool, source: str = "mcp") -> None:
        self.publish(Event(
            type=EventType.MCP_TOOL_CALLED if allowed else EventType.MCP_TOOL_BLOCKED,
            source=source,
            data={"tool_name": tool_name, "allowed": allowed}
        ))

    def get_history(self, event_type: Optional[EventType] = None, limit: int = 100) -> List[Event]:
        """Get recent event history, optionally filtered by type."""
        if event_type is None:
            return self._history[-limit:]
        return [e for e in self._history if e.type == event_type][-limit:]

    def clear_history(self) -> None:
        """Clear event history."""
        self._history.clear()


# Global event bus instance
_global_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get or create the global event bus."""
    global _global_bus
    if _global_bus is None:
        _global_bus = EventBus()
    return _global_bus


def set_event_bus(bus: EventBus) -> None:
    """Set the global event bus (for testing)."""
    global _global_bus
    _global_bus = bus