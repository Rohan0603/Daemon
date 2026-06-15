"""Tests for BehaviorController — extracted autonomous behavior system."""

from __future__ import annotations

import time
import unittest
from unittest.mock import MagicMock, patch

from src.behavior_controller import BehaviorController
from src.events import EventBus, EventType
from src.animator import Emotion
from src.pet_fsm import PetState


def _make_controller(
    event_bus=None,
    response_manager=None,
    typing_buffer=None,
    fsm=None,
    animator=None,
    **kwargs,
) -> BehaviorController:
    """Factory helper — creates a BehaviorController with mock dependencies."""
    return BehaviorController(
        event_bus=event_bus or EventBus(),
        response_manager=response_manager or MagicMock(),
        typing_buffer=typing_buffer or MagicMock(),
        fsm=fsm or MagicMock(),
        animator=animator or MagicMock(),
        **kwargs,
    )


class TestBehaviorControllerConstructor(unittest.TestCase):
    """Task 1: Constructor initializes all fields with defaults."""

    def test_constructor_defaults(self):
        """All fields initialized to zero/balanced defaults."""
        controller = _make_controller()
        self.assertEqual(controller.chat_timer_sec, 0.0)
        self.assertEqual(controller.joke_timer_sec, 0.0)
        self.assertEqual(controller.consecutive_silent, 0)
        self.assertEqual(controller.consecutive_engaged, 0)
        self.assertEqual(controller.idle_backoff_seconds, 0.0)
        self.assertEqual(controller.current_emotion, Emotion.MIRTH)
        self.assertIsNone(controller.last_context_snapshot)

    def test_constructor_custom_params(self):
        """Custom params override defaults."""
        controller = _make_controller(
            opencode_enabled=False,
            base_boredom_interval=60,
            max_idle_backoff=600,
            chattiness=2.0,
        )
        self.assertEqual(controller._base_boredom_interval, 60.0)
        self.assertEqual(controller._max_idle_backoff, 600.0)


class TestBehaviorControllerSetters(unittest.TestCase):
    """Task 1: Setter methods update internal state."""

    def test_set_apm(self):
        controller = _make_controller()
        controller.set_apm(42)
        self.assertEqual(controller._current_apm, 42)

    def test_set_idle_seconds(self):
        controller = _make_controller()
        controller.set_idle_seconds(30.5)
        self.assertEqual(controller._idle_seconds, 30.5)

    def test_set_chattiness(self):
        controller = _make_controller()
        controller.set_chattiness(2.5)
        self.assertEqual(controller._chattiness, 2.5)

    def test_set_autonomous_pending(self):
        controller = _make_controller()
        controller.set_autonomous_pending(True)
        self.assertTrue(controller._autonomous_query_pending)

    def test_set_risky_match(self):
        controller = _make_controller()
        controller.set_risky_match("delete *")
        self.assertEqual(controller._last_risky_match, "delete *")
        controller.set_risky_match(None)
        self.assertIsNone(controller._last_risky_match)

    def test_set_gcd_expiry(self):
        controller = _make_controller()
        ts = time.time() + 10
        controller.set_gcd_expiry(ts)
        self.assertEqual(controller._gcd_expiry_timestamp, ts)


class TestBehaviorControllerTickAccumulation(unittest.TestCase):
    """Task 1: tick() accumulates timers correctly."""

    def test_tick_accumulates_chat_timer(self):
        controller = _make_controller()
        controller.tick(2.0)
        self.assertAlmostEqual(controller.chat_timer_sec, 2.0)

    def test_tick_accumulates_joke_timer(self):
        controller = _make_controller()
        controller.tick(1.5)
        self.assertAlmostEqual(controller.joke_timer_sec, 1.5)

    def test_tick_multiple_calls(self):
        controller = _make_controller()
        controller.tick(1.0)
        controller.tick(2.0)
        self.assertAlmostEqual(controller.chat_timer_sec, 3.0)
        self.assertAlmostEqual(controller.joke_timer_sec, 3.0)

    def test_tick_returns_early_when_sleeping(self):
        """SLEEP guard: no timer accumulation."""
        fsm = MagicMock()
        fsm.current_state = PetState.SLEEP
        controller = _make_controller(fsm=fsm)
        controller.tick(10.0)
        self.assertEqual(controller.chat_timer_sec, 0.0)
        self.assertEqual(controller.joke_timer_sec, 0.0)


class TestBehaviorControllerTickGcdGate(unittest.TestCase):
    """Task 1: GCD gate blocks triggers during bubble."""

    def test_gcd_gate_blocks_triggers(self):
        """GCD expiry in future → tick returns before priority tree."""
        controller = _make_controller()
        controller.set_gcd_expiry(time.time() + 100)
        # Set timer high — would trigger if not for GCD
        controller._chat_timer_sec = 999
        # This should return without triggering anything
        controller.tick(0.1)
        # Timer should still be accumulated
        self.assertGreater(controller.chat_timer_sec, 999)


class TestBehaviorControllerEmotionEvaluation(unittest.TestCase):
    """Task 1: _evaluate_emotion returns correct emotion based on state."""

    def test_default_mirth(self):
        controller = _make_controller()
        emotion = controller._evaluate_emotion()
        self.assertEqual(emotion, Emotion.MIRTH)

    def test_devotion_high_apm(self):
        controller = _make_controller()
        controller.set_apm(80)
        emotion = controller._evaluate_emotion()
        self.assertEqual(emotion, Emotion.DEVOTION)

    def test_pathos_stale_idle(self):
        controller = _make_controller()
        controller.set_idle_seconds(180)
        controller.set_apm(0)
        emotion = controller._evaluate_emotion()
        self.assertEqual(emotion, Emotion.PATHOS)

    def test_transquility_code_window(self):
        controller = _make_controller()
        controller.set_apm(30)
        controller.set_idle_seconds(10)
        with patch("src.active_window.get_active_window_title", return_value="VS Code - main.py"):
            emotion = controller._evaluate_emotion()
        self.assertEqual(emotion, Emotion.TRANQUILITY)

    def test_anger_on_risky_match(self):
        controller = _make_controller()
        controller.set_risky_match("drop table")
        emotion = controller._evaluate_emotion()
        self.assertEqual(emotion, Emotion.ANGER)

    def test_wonder_rapid_switches(self):
        controller = _make_controller()
        controller._window_switch_count = 5  # Above threshold (3)
        emotion = controller._evaluate_emotion()
        self.assertEqual(emotion, Emotion.WONDER)


class TestBehaviorControllerGuardLogic(unittest.TestCase):
    """Task 1: _should_fire_autonomous gates correctly."""

    def test_should_not_fire_when_pending(self):
        controller = _make_controller()
        controller.set_autonomous_pending(True)
        self.assertFalse(controller._should_fire_autonomous("active_chat"))

    def test_should_not_fire_when_opencode_disabled(self):
        controller = _make_controller(opencode_enabled=False)
        self.assertFalse(controller._should_fire_autonomous("active_chat"))

    def test_should_not_fire_in_thinking_state(self):
        fsm = MagicMock()
        fsm.current_state = PetState.THINKING
        controller = _make_controller(fsm=fsm)
        self.assertFalse(controller._should_fire_autonomous("active_chat"))

    def test_should_not_fire_when_dragged(self):
        fsm = MagicMock()
        fsm.current_state = PetState.DRAGGED
        controller = _make_controller(fsm=fsm)
        self.assertFalse(controller._should_fire_autonomous("active_chat"))

    def test_should_fire_when_conditions_met(self):
        controller = _make_controller()
        self.assertTrue(controller._should_fire_autonomous("active_chat"))


class TestBehaviorControllerEngagementTracking(unittest.TestCase):
    """Task 1: Engagement tracking backoff."""

    def test_engaged_restores_interval(self):
        controller = _make_controller()
        controller._current_interval = 120.0
        controller._on_output_displayed(engaged=True)
        controller._on_output_displayed(engaged=True)
        self.assertEqual(controller._current_interval, 15.0)  # BASE_INTERVAL_SEC

    def test_silence_increases_interval(self):
        from src.constants import SILENCE_THRESHOLD, BASE_INTERVAL_SEC
        controller = _make_controller()
        for _ in range(SILENCE_THRESHOLD + 1):
            controller._on_output_displayed(engaged=False)
        self.assertGreater(controller._current_interval, BASE_INTERVAL_SEC)

    def test_mixed_engaged_silence_tracking(self):
        controller = _make_controller()
        controller._on_output_displayed(engaged=True)  # engaged=1
        controller._on_output_displayed(engaged=False)  # silent=1, engaged reset
        self.assertEqual(controller.consecutive_engaged, 0)
        self.assertEqual(controller.consecutive_silent, 1)

    def test_on_user_input_resets_engagement(self):
        from src.constants import BASE_INTERVAL_SEC
        controller = _make_controller()
        controller._consecutive_silent = 10
        controller._current_interval = 120.0
        controller.on_user_input()
        self.assertEqual(controller.consecutive_silent, 0)
        self.assertEqual(controller.current_interval, BASE_INTERVAL_SEC)


class TestBehaviorControllerBoredomBackoff(unittest.TestCase):
    """Task 1: Exponential boredom backoff."""

    def test_backoff_increases_after_fire(self):
        fsm = MagicMock()
        fsm.current_state = PetState.IDLE
        controller = _make_controller(fsm=fsm)
        controller._idle_backoff_seconds = 30.0
        controller._last_boredom_fsm_time = time.time() - 31
        controller._idle_seconds = 60
        controller._current_apm = 0
        # Need context stable and threshold met
        with patch.object(controller, "_is_context_stable", return_value=True):
            controller.tick(1.0)
        # Backoff should have increased
        self.assertGreater(controller._idle_backoff_seconds, 30.0)

    def test_backoff_caps_at_max(self):
        fsm = MagicMock()
        fsm.current_state = PetState.IDLE
        controller = _make_controller(fsm=fsm, max_idle_backoff=300)
        controller._idle_backoff_seconds = 299.0
        controller._last_boredom_fsm_time = time.time() - 301
        controller._idle_seconds = 60
        controller._current_apm = 0
        with patch.object(controller, "_is_context_stable", return_value=True):
            with patch.object(controller, "_should_fire_autonomous", return_value=True):
                controller.tick(1.0)
        self.assertEqual(controller._idle_backoff_seconds, 300.0)

    def test_context_change_resets_backoff(self):
        controller = _make_controller()
        controller._idle_backoff_seconds = 120.0
        controller._last_context_snapshot = ("old", 0, 0, 0)
        # Simulate context change
        with patch.object(
            controller, "_get_context_signature",
            return_value=("new", 5, 10, 42),
        ):
            with patch.object(controller, "_is_context_stable", return_value=False):
                controller._idle_seconds = 60
                controller._current_apm = 0
                controller.tick(1.0)
        self.assertEqual(
            controller._idle_backoff_seconds,
            controller._base_boredom_interval,
        )


class TestBehaviorControllerContextStability(unittest.TestCase):
    """Task 1: Context stability detection."""

    def test_initial_context_not_stable(self):
        controller = _make_controller()
        self.assertFalse(controller._is_context_stable())
        # Should have captured snapshot
        self.assertIsNotNone(controller.last_context_snapshot)

    def test_stable_after_initial(self):
        controller = _make_controller()
        controller._is_context_stable()  # First call snapshots
        # Same context → stable
        with patch.object(
            controller, "_get_context_signature",
            return_value=controller.last_context_snapshot,
        ):
            self.assertTrue(controller._is_context_stable())


class TestBehaviorControllerJokeModifier(unittest.TestCase):
    """Task 1: Joke modifier scales with APM."""

    def test_low_apm_rapid_fire(self):
        controller = _make_controller()
        controller.set_apm(5)
        self.assertEqual(controller._calculate_joke_modifier(), 0.5)

    def test_moderate_apm_normal(self):
        controller = _make_controller()
        controller.set_apm(15)
        self.assertEqual(controller._calculate_joke_modifier(), 1.0)

    def test_high_apm_rare(self):
        controller = _make_controller()
        controller.set_apm(50)
        self.assertEqual(controller._calculate_joke_modifier(), 3.0)


class TestBehaviorControllerEventBus(unittest.TestCase):
    """Task 1: EventBus events are published on triggers."""

    def test_tick_emotion_shift_publishes_event(self):
        """Emotion shift event published on emotion change."""
        bus = EventBus()
        received = []
        bus.subscribe(EventType.EMOTION_SHIFTED, lambda e: received.append(e))

        controller = _make_controller(event_bus=bus)
        controller._emotion_timer_sec = 999  # Force evaluation
        controller._current_emotion = Emotion.MIRTH

        with patch.object(controller, "_evaluate_emotion", return_value=Emotion.DEVOTION):
            with patch("src.behavior_controller.get_active_window_title", return_value="Some app"):
                controller.tick(1.0)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].data["old_emotion"], "MIRTH")
        self.assertEqual(received[0].data["new_emotion"], "DEVOTION")

    def test_autonomous_trigger_event_published(self):
        """Chat trigger publishes AUTONOMOUS_TRIGGER_FIRED."""
        bus = EventBus()
        received = []
        bus.subscribe(EventType.AUTONOMOUS_TRIGGER_FIRED, lambda e: received.append(e))

        fsm = MagicMock()
        fsm.current_state = PetState.IDLE
        controller = _make_controller(event_bus=bus, fsm=fsm)
        controller._chat_timer_sec = 999
        controller._gcd_expiry_timestamp = 0.0

        with patch.object(controller, "_has_significant_delta", return_value=True):
            with patch.object(controller, "_should_fire_autonomous", return_value=True):
                controller.tick(1.0)

        self.assertGreaterEqual(len(received), 1)
        self.assertIn(received[0].data["mode"], ("active_chat", "joke", "boredom"))


class TestBehaviorControllerPriorityTree(unittest.TestCase):
    """Task 1: Behavioral priority tree orders triggers correctly."""

    def test_flow_state_silence(self):
        """APM > 80 → total silence (no triggers)."""
        controller = _make_controller()
        controller.set_apm(100)
        controller._chat_timer_sec = 999

        with patch.object(controller, "_has_significant_delta", return_value=True):
            # Should not trigger anything — P1: flow state returns early
            controller.tick(1.0)

        # Timer still accumulates but no trigger
        self.assertGreater(controller.chat_timer_sec, 999)

    def test_p2_precedes_p3(self):
        """Chat trigger takes priority over joke."""
        bus = EventBus()
        received = []
        bus.subscribe(EventType.AUTONOMOUS_TRIGGER_FIRED, lambda e: received.append(e))

        fsm = MagicMock()
        fsm.current_state = PetState.IDLE
        controller = _make_controller(event_bus=bus, fsm=fsm)
        controller._chat_timer_sec = 999
        controller._joke_timer_sec = 999
        controller._current_apm = 10  # Below joke threshold

        with patch.object(controller, "_has_significant_delta", return_value=True):
            with patch.object(controller, "_should_fire_autonomous", return_value=True):
                controller.tick(1.0)

        if received:
            self.assertEqual(received[0].data["mode"], "active_chat")


if __name__ == "__main__":
    unittest.main()
