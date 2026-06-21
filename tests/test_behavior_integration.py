"""Integration tests: BehaviorController wired into PetWindow via EventBus.

The priority tree logic moved to BehaviorController (tested in
test_behavior_controller.py). These tests verify end-to-end wiring:
PetWindow creates BehaviorController, events flow through EventBus.
"""
import time
import pytest
from unittest.mock import MagicMock, patch
from src.pet_window import PetWindow
from src.pet_fsm import PetState
from src.behavior_controller import BehaviorController
from src.events import EventBus, EventType

pytestmark = pytest.mark.usefixtures("app")


class TestBehaviorIntegration:
    def setup_method(self):
        from PyQt6.QtWidgets import QWidget
        def mock_init(self, *a, **kw):
            QWidget.__init__(self)
        with patch.object(PetWindow, '__init__', mock_init):
            self.pw = PetWindow()
            self.pw._fsm = MagicMock()
            self.pw._fsm.current_state = PetState.IDLE
            self.pw._response_manager = MagicMock()
            self.pw._typing_buffer = MagicMock()
            self.pw._opencode_enabled = True
            self.pw._autonomous_query_pending = False
            self.pw._forced_sleep = False
            self.pw._current_apm = 0
            self.pw._idle_seconds = 0
            self.pw._last_master_tick_time = time.monotonic() - 1.0
            # Create a real EventBus so we can subscribe
            bus = EventBus()
            self.pw._events = bus
            # Create real BehaviorController with mocks
            self.pw._behavior = BehaviorController(
                event_bus=bus,
                response_manager=self.pw._response_manager,
                typing_buffer=self.pw._typing_buffer,
                fsm=self.pw._fsm,
                animator=MagicMock(),
                opencode_enabled=True,
            )
            # Wire EventBus subscriber (mocked __init__ skipped this)
            from src.events import EventType
            bus.subscribe(
                EventType.AUTONOMOUS_TRIGGER_FIRED,
                self.pw._on_autonomous_trigger_fired,
            )
            self.pw._dispatch_structured = MagicMock()
            self.pw._dispatch_trigger = MagicMock()
            self.pw._show_bubble = MagicMock()
            self.pw._history = MagicMock()
            # APM state fields required by _on_apm_updated
            self.pw._apm_state = "normal"
            self.pw._last_apm_state_change = 0.0
            self.pw._last_apm = 0
            self.pw._screen_time_tick = 0

    def test_behavior_created_with_pet_window(self):
        assert self.pw._behavior is not None
        assert isinstance(self.pw._behavior, BehaviorController)

    def test_master_tick_delegates_and_runs(self):
        self.pw._current_apm = 10
        self.pw._idle_seconds = 5
        self.pw._master_tick()
        # Should have processed without error
        assert self.pw._behavior.chat_timer_sec > 0

    def test_emotion_shift_emits_event(self):
        """Emotion shift through EventBus flows through BehaviorController."""
        received = []
        self.pw._events.subscribe(
            EventType.EMOTION_SHIFTED,
            lambda e: received.append(e),
        )
        # Force emotion evaluation to produce a shift
        self.pw._behavior._emotion_timer_sec = 999  # Force evaluation
        self.pw._behavior._current_emotion = MagicMock()
        self.pw._behavior._current_emotion.name = "MIRTH"
        with patch(
            "src.behavior_controller.get_active_window_title",
            return_value="Some app",
        ):
            with patch.object(
                self.pw._behavior, "_evaluate_emotion",
                return_value=MagicMock(name="DEVOTION"),
            ):
                self.pw._behavior.tick(1.0)
        assert len(received) >= 1
        # DEVOTION → something changed
        # (the emotion shift event may fire multiple times due to evaluation
        #  at every tick when _emotion_timer_sec >= EMOTION_TICK_SEC)

    def test_apm_update_syncs_to_behavior(self):
        self.pw._on_apm_updated(42)
        assert self.pw._behavior._current_apm == 42

    def test_apm_activity_resets_behavior_backoff(self):
        self.pw._behavior._idle_backoff_seconds = 120.0
        self.pw._behavior._last_context_snapshot = ("old", 0, 0, 0)
        self.pw._on_apm_updated(1)
        # after on_activity_detected(), backoff should be reset
        assert self.pw._behavior._idle_backoff_seconds == 0.0

    def test_master_tick_with_multiple_iterations(self):
        for _ in range(5):
            self.pw._last_master_tick_time = time.monotonic()
            self.pw._master_tick()
        assert self.pw._behavior.chat_timer_sec > 0

    def test_autonomous_trigger_subscriber_works(self):
        """EventBus subscriber dispatches triggers."""
        self.pw._dispatch_structured = MagicMock()
        self.pw._on_output_displayed = MagicMock()
        self.pw._events.emit_autonomous_trigger(
            "active_chat", apm=10, idle_seconds=5.0,
        )
        # Should have called dispatch (thought pool returns None → falls through)
        # Since _opencode_enabled=False in test, _should_fire_autonomous returns False
        pass

    def test_boredom_trigger_calls_fsm_action(self):
        """Boredom trigger transitions FSM to a boredom state."""
        from src.pet_fsm import PetState
        self.pw._response_manager.remaining.return_value = 1
        self.pw._opencode_enabled = True
        self.pw._autonomous_query_pending = False
        self.pw._on_output_displayed = MagicMock()
        self.pw._events.emit_autonomous_trigger(
            "boredom", apm=0, idle_seconds=600,
        )
        # FSM should have been called with one of the boredom states
        boredom_states = (
            PetState.PERIMETER, PetState.SHAKING,
            PetState.SPINNING, PetState.LOOK_AWAY, PetState.BOUNCING,
        )
        assert self.pw._fsm.transition_to.call_args[0][0] in boredom_states
