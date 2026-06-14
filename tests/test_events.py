"""Tests for src/events.py — EventBus, Event, EventType."""
from __future__ import annotations
import pytest
from datetime import datetime

from src.events import EventBus, Event, EventType, get_event_bus, set_event_bus


class TestEventType:
    def test_has_all_expected_event_types(self):
        expected = {
            "FSM_STATE_CHANGED", "FSM_TRANSITION_DENIED",
            "EMOTION_SHIFTED",
            "USER_INPUT_RECEIVED", "USER_HOTKEY_PRESSED",
            "AUTONOMOUS_TRIGGER_FIRED", "AUTONOMOUS_QUERY_STARTED", "AUTONOMOUS_QUERY_COMPLETED",
            "LLM_SESSION_CREATED", "LLM_SESSION_CLOSED", "LLM_REQUEST_SENT", "LLM_RESPONSE_RECEIVED", "LLM_ERROR",
            "MEMORY_UPDATED", "MEMORY_SYNC_COMPLETED", "BRAIN_UPDATE_RECEIVED",
            "DIARY_ENTRY_ADDED", "HISTORY_ENTRY_ADDED",
            "SYSTEM_IDLE_DETECTED", "SYSTEM_ACTIVITY_DETECTED", "SCREEN_CONTENT_CHANGED",
            "APM_THRESHOLD_CROSSED", "TYPING_BURST_DETECTED",
            "BRAIN_DISCONNECTED", "BRAIN_RECONNECTED",
            "MCP_TOOL_CALLED", "MCP_TOOL_BLOCKED",
            "PET_SLEEP_STARTED", "PET_SLEEP_ENDED", "PET_BOOT_COMPLETED", "PET_SHUTDOWN_STARTED",
        }
        actual = {e.name for e in EventType}
        assert actual == expected


class TestEvent:
    def test_event_has_default_timestamp_and_source(self):
        event = Event(type=EventType.FSM_STATE_CHANGED)
        assert isinstance(event.timestamp, datetime)
        assert event.source == "unknown"

    def test_event_accepts_custom_source_and_data(self):
        event = Event(
            type=EventType.FSM_STATE_CHANGED,
            source="test",
            data={"old_state": "IDLE", "new_state": "THINKING"}
        )
        assert event.source == "test"
        assert event.data["old_state"] == "IDLE"

    def test_event_is_immutable(self):
        event = Event(type=EventType.FSM_STATE_CHANGED)
        with pytest.raises(AttributeError):
            event.type = EventType.FSM_STATE_CHANGED


class TestEventBus:
    def test_publish_returns_zero_for_no_subscribers(self):
        bus = EventBus()
        event = Event(type=EventType.FSM_STATE_CHANGED)
        count = bus.publish(event)
        assert count == 0

    def test_subscribe_single_callback(self):
        bus = EventBus()
        received = []
        def callback(e):
            received.append(e)
        bus.subscribe(EventType.FSM_STATE_CHANGED, callback)
        event = Event(type=EventType.FSM_STATE_CHANGED)
        bus.publish(event)
        assert len(received) == 1
        assert received[0] is event

    def test_subscribe_multiple_event_types(self):
        bus = EventBus()
        received = []
        def callback(e):
            received.append(e)
        bus.subscribe(EventType.FSM_STATE_CHANGED, callback)
        bus.subscribe(EventType.EMOTION_SHIFTED, callback)
        bus.publish(Event(type=EventType.FSM_STATE_CHANGED))
        bus.publish(Event(type=EventType.EMOTION_SHIFTED))
        assert len(received) == 2

    def test_unsubscribe_removes_callback(self):
        bus = EventBus()
        received = []
        def callback(e):
            received.append(e)
        bus.subscribe(EventType.FSM_STATE_CHANGED, callback)
        bus.unsubscribe(EventType.FSM_STATE_CHANGED, callback)
        bus.publish(Event(type=EventType.FSM_STATE_CHANGED))
        assert len(received) == 0

    def test_unsubscribe_returns_true_when_subscribed(self):
        bus = EventBus()
        def callback(e):
            pass
        bus.subscribe(EventType.FSM_STATE_CHANGED, callback)
        assert bus.unsubscribe(EventType.FSM_STATE_CHANGED, callback) is True

    def test_unsubscribe_returns_false_when_not_subscribed(self):
        bus = EventBus()
        def callback(e):
            pass
        assert bus.unsubscribe(EventType.FSM_STATE_CHANGED, callback) is False

    def test_wildcard_subscription(self):
        bus = EventBus()
        received = []
        def callback(e):
            received.append(e)
        bus.subscribe_all(callback)
        bus.publish(Event(type=EventType.FSM_STATE_CHANGED))
        bus.publish(Event(type=EventType.EMOTION_SHIFTED))
        assert len(received) == 2

    def test_history_tracked(self):
        bus = EventBus(history_size=10)
        bus.subscribe_all(lambda e: None)
        for i in range(5):
            bus.publish(Event(type=EventType.FSM_STATE_CHANGED))
        history = bus.get_history()
        assert len(history) == 5

    def test_history_respects_size_limit(self):
        bus = EventBus(history_size=3)
        bus.subscribe_all(lambda e: None)
        for i in range(10):
            bus.publish(Event(type=EventType.FSM_STATE_CHANGED))
        history = bus.get_history()
        assert len(history) == 3

    def test_get_history_filtered_by_type(self):
        bus = EventBus()
        bus.subscribe_all(lambda e: None)
        bus.publish(Event(type=EventType.FSM_STATE_CHANGED))
        bus.publish(Event(type=EventType.EMOTION_SHIFTED))
        bus.publish(Event(type=EventType.FSM_STATE_CHANGED))
        history = bus.get_history(event_type=EventType.FSM_STATE_CHANGED)
        assert len(history) == 2
        assert all(e.type == EventType.FSM_STATE_CHANGED for e in history)

    def test_clear_history(self):
        bus = EventBus()
        bus.subscribe_all(lambda e: None)
        bus.publish(Event(type=EventType.FSM_STATE_CHANGED))
        bus.clear_history()
        assert len(bus.get_history()) == 0

    def test_convenience_emit_methods(self):
        bus = EventBus()
        received = []
        def callback(e):
            received.append(e)
        bus.subscribe(EventType.FSM_STATE_CHANGED, callback)
        bus.emit_fsm_state_changed("IDLE", "THINKING")
        assert len(received) == 1
        assert received[0].data["old_state"] == "IDLE"
        assert received[0].data["new_state"] == "THINKING"

    def test_emit_emotion_shifted(self):
        bus = EventBus()
        received = []
        bus.subscribe(EventType.EMOTION_SHIFTED, lambda e: received.append(e))
        bus.emit_emotion_shifted("MIRTH", "ANGER")
        assert len(received) == 1
        assert received[0].data["old_emotion"] == "MIRTH"

    def test_emit_user_input(self):
        bus = EventBus()
        received = []
        bus.subscribe(EventType.USER_INPUT_RECEIVED, lambda e: received.append(e))
        bus.emit_user_input("hello")
        assert len(received) == 1
        assert received[0].data["text"] == "hello"

    def test_emit_autonomous_trigger(self):
        bus = EventBus()
        received = []
        bus.subscribe(EventType.AUTONOMOUS_TRIGGER_FIRED, lambda e: received.append(e))
        bus.emit_autonomous_trigger("chat", 42, 120.5)
        assert len(received) == 1
        assert received[0].data["mode"] == "chat"
        assert received[0].data["apm"] == 42
        assert received[0].data["idle_seconds"] == 120.5

    def test_reentrant_publish_warning(self, caplog):
        bus = EventBus()
        def reentrant_callback(e):
            if e.type == EventType.FSM_STATE_CHANGED:
                bus.publish(Event(type=EventType.EMOTION_SHIFTED))
        bus.subscribe(EventType.FSM_STATE_CHANGED, reentrant_callback)
        bus.publish(Event(type=EventType.FSM_STATE_CHANGED))
        assert "Re-entrant publish detected" in caplog.text


class TestGlobalEventBus:
    def test_get_event_bus_returns_singleton(self):
        set_event_bus(None)
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2

    def test_set_event_bus_replaces_instance(self):
        set_event_bus(None)
        bus1 = get_event_bus()
        bus2 = EventBus()
        set_event_bus(bus2)
        assert get_event_bus() is bus2
        set_event_bus(None)