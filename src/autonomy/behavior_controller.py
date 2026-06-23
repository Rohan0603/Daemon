"""BehaviorController — Autonomous behavior system for Daemon.

Extracted from PetWindow (Phase 52). Owns all autonomous behavior state:
|- Timer accumulation (chat, joke, emotion, idle, boredom)
|- Engagement tracking (consecutive silent/engaged, silence backoff)
|- Boredom backoff (exponential, context-sensitive)
|- Context stability detection
|- Emotion evaluation (OS-context → Emotion)
|- FSM trigger dispatch via EventBus

This class has NO Qt imports — pure business logic.
Communication with PetWindow is via EventBus pub/sub.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from src.active_window import get_active_window_title
from src.animator import Emotion, EmotionAnimator
from src.constants import (
    ACTIVE_CHAT_INTERVAL_SEC,
    BACKOFF_MULTIPLIER,
    BASE_INTERVAL_SEC,
    BOREDOM_TIMEOUT_SEC,
    EMOTION_TICK_SEC,
    ENGAGED_THRESHOLD,
    JOKE_INTERVAL_SEC,
    MAX_BACKOFF_SEC,
    PROCRASTINATION_DOMAINS,
    RAPID_WINDOW_SWITCH_THRESHOLD,
    SILENCE_THRESHOLD,
    TASK_MANAGER_KEYWORDS,
)
from src.events import EventBus, EventType
from src.pet_fsm import PetFSM, PetState
from .response_manager import AutonomousResponseManager
from src.screen_reader import ScreenReader
from src.typing_buffer import TypingBuffer

logger = logging.getLogger(__name__)


class BehaviorController:
    """Autonomous behavior brain for Daemon.

    Owns all behavior state (timers, counters, backoff) and business logic.
    Publishes events to EventBus when triggers fire.
    PetWindow subscribes to those events for UI dispatch.
    """

    def __init__(
        self,
        event_bus: EventBus,
        response_manager: AutonomousResponseManager,
        typing_buffer: TypingBuffer,
        fsm: PetFSM,
        animator: EmotionAnimator,
        opencode_enabled: bool = True,
        base_boredom_interval: int = BOREDOM_TIMEOUT_SEC,
        max_idle_backoff: int = 300,
        chattiness: float = 1.0,
        plugin_registry: object = None,
    ) -> None:
        self._event_bus = event_bus
        self._response_manager = response_manager
        self._typing_buffer = typing_buffer
        self._fsm = fsm
        self._animator = animator
        self._plugin_registry = plugin_registry

        # External state (updated by PetWindow)
        self._opencode_enabled = opencode_enabled
        self._current_apm = 0
        self._idle_seconds = 0.0
        self._chattiness = chattiness
        self._autonomous_query_pending = False
        self._brain_disconnected = False
        self._last_risky_match: str | None = None

        # Timer accumulators (accumulated via tick())
        self._chat_timer_sec = 0.0
        self._joke_timer_sec = 0.0
        self._emotion_timer_sec = 0.0

        # GCD (global cooldown) — set externally by PetWindow when bubble active
        self._gcd_expiry_timestamp = 0.0

        # Window switch tracking for WONDER emotion
        self._window_switch_count = 0
        self._last_evaluated_window = ""

        # Engagement tracking
        self._consecutive_silent = 0
        self._consecutive_engaged = 0
        self._current_interval = BASE_INTERVAL_SEC

        # Boredom backoff
        self._last_context_snapshot: tuple | None = None
        self._idle_backoff_seconds = 0.0
        self._base_boredom_interval = float(base_boredom_interval)
        self._max_idle_backoff = float(max_idle_backoff)
        self._last_boredom_fsm_time = 0.0
        self._last_boredom_trigger_time = 0.0
        self._last_active_window = ""
        self._last_typing_snapshot = ""

        # Monotonic time for drift-free behavioral timers
        self._last_master_tick_time = time.monotonic()
        self._last_autonomous_fire_time = 0.0

        self._boredom_tick_count = 0

        # Currently evaluated emotion
        self._current_emotion = Emotion.MIRTH
        
        # Distractions
        self._distraction_apps = []
        self._event_bus.subscribe(EventType.SCREEN_TIME_THRESHOLD_REACHED, self._on_screen_time_threshold)

    # ── Public setters (called by PetWindow) ──────────────────────────

    def set_apm(self, apm: int) -> None:
        """Update current APM value from PetWindow's worker."""
        self._current_apm = apm

    def set_idle_seconds(self, seconds: float) -> None:
        """Update current idle duration."""
        self._idle_seconds = seconds

    def set_chattiness(self, value: float) -> None:
        """Update chattiness multiplier."""
        self._chattiness = value

    def set_opencode_enabled(self, enabled: bool) -> None:
        """Update opencode availability."""
        self._opencode_enabled = enabled

    def set_autonomous_pending(self, pending: bool) -> None:
        """Set whether an autonomous query is in flight."""
        self._autonomous_query_pending = pending

    def set_brain_disconnected(self, disconnected: bool) -> None:
        """Set brain connection status."""
        self._brain_disconnected = disconnected

    def set_risky_match(self, keyword: str | None) -> None:
        """Set last matched risky keyword (for ANGER emotion)."""
        self._last_risky_match = keyword

    def set_gcd_expiry(self, timestamp: float) -> None:
        """Set global cooldown expiry (bubble active → silence)."""
        self._gcd_expiry_timestamp = timestamp

    # ── Events (called by PetWindow) ─────────────────────────────────

    def on_user_input(self) -> None:
        """Reset idle and backoff state on user interaction."""
        self._idle_seconds = 0.0
        self._idle_backoff_seconds = 0.0
        self._last_boredom_fsm_time = time.time()
        self._consecutive_silent = 0
        self._consecutive_engaged = 0
        self._current_interval = BASE_INTERVAL_SEC

    def on_sleep_entered(self) -> None:
        """Freeze behavioral timers when sleeping."""
        pass  # tick() checks fsm state and early-returns

    def on_sleep_exited(self) -> None:
        """Reset boredom counter on wake."""
        self._idle_backoff_seconds = 0.0

    def on_activity_detected(self) -> None:
        """Reset counters on mouse/keyboard activity."""
        self._idle_backoff_seconds = 0.0
        self._consecutive_silent = 0
        self._consecutive_engaged = 0
        self._current_interval = BASE_INTERVAL_SEC

    def on_output_displayed(self, engaged: bool) -> None:
        """Update engagement counters based on output reception."""
        if engaged:
            self._consecutive_engaged += 1
            self._consecutive_silent = 0
            if self._consecutive_engaged >= ENGAGED_THRESHOLD:
                self._current_interval = BASE_INTERVAL_SEC
        else:
            self._consecutive_engaged = 0
            self._consecutive_silent += 1
            if self._consecutive_silent >= SILENCE_THRESHOLD:
                self._current_interval = min(
                    self._current_interval * (
                        BACKOFF_MULTIPLIER ** self._consecutive_silent
                    ),
                    MAX_BACKOFF_SEC,
                )

    # ── Public property access for PetWindow ─────────────────────────

    @property
    def current_emotion(self) -> Emotion:
        return self._current_emotion

    @property
    def chat_timer_sec(self) -> float:
        return self._chat_timer_sec

    @property
    def joke_timer_sec(self) -> float:
        return self._joke_timer_sec

    @property
    def consecutive_silent(self) -> int:
        return self._consecutive_silent

    @property
    def consecutive_engaged(self) -> int:
        return self._consecutive_engaged

    @property
    def current_interval(self) -> float:
        return self._current_interval

    @property
    def idle_backoff_seconds(self) -> float:
        return self._idle_backoff_seconds

    @property
    def last_context_snapshot(self) -> tuple | None:
        return self._last_context_snapshot

    # ── Main Tick ────────────────────────────────────────────────────

    def tick(self, master_dt: float) -> None:
        """Main behavioral tick — runs every BEHAVIOR_TICK_MS.

        Args:
            master_dt: Elapsed seconds since last tick (monotonic delta).
        """
        try:
            # SLEEP guard: freeze all behavioral timers
            if self._fsm.current_state == PetState.SLEEP:
                # Reset accumulated timers so they don't fire immediately on wake
                self._chat_timer_sec = 0.0
                self._joke_timer_sec = 0.0
                self._emotion_timer_sec = 0.0
                return

            # Window switch tracking for WONDER
            current_window = get_active_window_title()
            if current_window and current_window != self._last_evaluated_window:
                self._window_switch_count += 1
                self._last_evaluated_window = current_window

            # Emotion evaluation every EMOTION_TICK_SEC seconds
            self._emotion_timer_sec += master_dt
            if self._emotion_timer_sec >= EMOTION_TICK_SEC:
                self._emotion_timer_sec = 0.0
                old_emotion = self._current_emotion
                self._current_emotion = self._evaluate_emotion()
                if old_emotion != self._current_emotion:
                    self._event_bus.emit_emotion_shifted(
                        old_emotion.name, self._current_emotion.name
                    )
                self._window_switch_count = 0
                if self._current_emotion == Emotion.FEAR:
                    # Publish FSM action for FEAR → FALLING
                    from src.events import Event
                    self._event_bus.publish(
                        Event(
                            type=EventType.FSM_STATE_CHANGED,
                            source="behavior_controller",
                            data={
                                "old_state": self._fsm.current_state.name,
                                "new_state": PetState.FALLING.name,
                                "trigger": "fear",
                            }
                        )
                    )

            # Accumulate chat and joke timers
            self._chat_timer_sec += master_dt
            self._joke_timer_sec += master_dt

            # GATEKEEPER: Dynamic Global Cooldown
            if time.time() < self._gcd_expiry_timestamp:
                return  # Speech in progress — lockdown

            # Dynamic Thresholds (Chattiness scaling)
            chat_threshold = ACTIVE_CHAT_INTERVAL_SEC / max(self._chattiness, 0.1)
            joke_mod = self._calculate_joke_modifier()
            joke_threshold = (JOKE_INTERVAL_SEC * joke_mod) / max(self._chattiness, 0.1)

            # BEHAVIORAL PRIORITY TREE
            # P1: Flow State (APM > 80) — TOTAL SILENCE
            if self._current_apm > 80:
                return

            # P2: Active Chat Delta
            if self._chat_timer_sec >= chat_threshold and self._has_significant_delta():
                self._trigger_chat()
                return

            # P3: Joke (APM < 20) — only if no active backoff
            if self._joke_timer_sec >= joke_threshold and self._current_apm < 20:
                elapsed_since_boredom = time.time() - self._last_boredom_fsm_time
                if elapsed_since_boredom >= self._idle_backoff_seconds:
                    self._trigger_joke()
                    return

            # P4: Boredom (APM == 0, Idle >= 60s) — WITH EXPONENTIAL BACKOFF
            if self._idle_seconds >= 60 and self._current_apm == 0:
                current_time = time.time()
                if hasattr(self, "_last_boredom_trigger_time"):
                    time_since_last_boredom = current_time - self._last_boredom_trigger_time
                    if time_since_last_boredom < 30:  # 30 second cooldown between boredom triggers
                        return

                # 1. Update stability and base timer first
                if not self._is_context_stable():
                    self._idle_backoff_seconds = self._base_boredom_interval
                    self._last_context_snapshot = self._get_context_signature()
                    self._last_boredom_fsm_time = time.time()

                # 2. Check if it's time to fire
                elapsed = time.time() - self._last_boredom_fsm_time
                if elapsed >= self._idle_backoff_seconds:
                    self._trigger_boredom_fsm()
                    self._last_boredom_fsm_time = time.time()
                    self._last_boredom_trigger_time = current_time

                    # 3. ONLY increase backoff AFTER we've fired
                    if self._idle_backoff_seconds == 0:
                        self._idle_backoff_seconds = self._base_boredom_interval
                    else:
                        self._idle_backoff_seconds = min(
                            self._idle_backoff_seconds * 2.0,
                            self._max_idle_backoff,
                        )
                    return

        except Exception as e:
            logger.critical("CRASH in BehaviorController.tick: %s", e, exc_info=True)
            raise

    # ── Trigger Dispatch (via EventBus) ──────────────────────────────

    def handle_file_edited(self, file_path: str):
        # 10% chance to roast the file change autonomously
        import random
        if random.random() < 0.1:
            logger.debug(f"[Code Review] Triggering autonomous code review for {file_path}")
            self._trigger_code_review_roast(file_path)

    def _trigger_code_review_roast(self, file_path: str):
        logger.debug(f"[Code Review] Generating roast for recent git diff involving {file_path}")
        if self._fsm.current_state != PetState.IDLE:
            self._fsm.transition_to(PetState.IDLE)
        self._fsm.transition_to(PetState.AUTONOMOUS_THINKING)
        self._set_gcd(8.0)
        
        self._event_bus.emit_autonomous_trigger(
            mode=f"code_review:{file_path}",
            apm=self._current_apm,
            idle_seconds=self._idle_seconds
        )

    def _on_screen_time_threshold(self, event):
        app_name = event.data.get("app_name")
        minutes = event.data.get("minutes")
        logger.debug(f"[Screen Time] Threshold reached for {app_name}: {minutes} mins. Triggering roast!")
        
        # Check if distraction
        if app_name.lower() in [d.lower() for d in PROCRASTINATION_DOMAINS]:
            self._trigger_screen_time_roast(app_name, minutes * 60)

    def _trigger_screen_time_roast(self, app_name: str, duration: int) -> None:
        if self._gcd_expiry_timestamp > time.time():
            return
            
        logger.info("Triggering screen time roast for %s (%d sec)", app_name, duration)
        
        if self._fsm.current_state != PetState.IDLE:
            self._fsm.transition_to(PetState.IDLE)
        self._fsm.transition_to(PetState.AUTONOMOUS_THINKING)
        
        # Set short GCD so the bubble shows
        self._gcd_expiry_timestamp = time.time() + 8.0
        
        self._event_bus.emit_autonomous_trigger(
            mode=f"screen_time_roast:{app_name}",
            apm=self._current_apm,
            idle_seconds=self._idle_seconds
        )

    def _trigger_chat(self) -> None:
        """Handle active chat: publish event, draw from thought pool."""
        from src.log_context import set_correlation_id
        set_correlation_id()
        self._chat_timer_sec = 0.0  # Reset timer

        if not self._should_fire_autonomous("active_chat"):
            return

        self._last_autonomous_fire_time = time.time()
        self._event_bus.emit_autonomous_trigger(
            "active_chat", self._current_apm, self._idle_seconds
        )
        try:
            from src.observability import record_autonomous_trigger
            record_autonomous_trigger("active_chat", True)
        except Exception:
            pass

    def _trigger_joke(self) -> None:
        """Handle joke trigger: publish event, draw from thought pool."""
        from src.log_context import set_correlation_id
        set_correlation_id()
        self._joke_timer_sec = 0.0  # Reset timer

        if not self._should_fire_autonomous("joke"):
            return

        self._last_autonomous_fire_time = time.time()
        self._event_bus.emit_autonomous_trigger(
            "joke", self._current_apm, self._idle_seconds
        )
        try:
            from src.observability import record_autonomous_trigger
            record_autonomous_trigger("joke", True)
        except Exception:
            pass

    def _trigger_boredom_fsm(self) -> None:
        """Handle boredom: publish event."""
        from src.log_context import set_correlation_id
        set_correlation_id()
        if not self._should_fire_autonomous("boredom"):
            return

        self._last_autonomous_fire_time = time.time()
        self._event_bus.emit_autonomous_trigger(
            "boredom", self._current_apm, self._idle_seconds
        )
        try:
            from src.observability import record_autonomous_trigger
            record_autonomous_trigger("boredom", True)
        except Exception:
            pass

    # ── Emotion Evaluation ──────────────────────────────────────────

    def _evaluate_emotion(self) -> Emotion:
        """Determine current emotion from OS context.

        Pure function based on current state — no side effects.
        First checks plugin-registered emotion rules (if any), then
        falls back to the built-in priority chain.
        """
        # ── Plugin rules (higher precedence) ──
        plugin_emotion = self._evaluate_plugin_emotion()
        if plugin_emotion is not None:
            return plugin_emotion

        # ── Built-in rules ──
        window = get_active_window_title().lower()
        win_title = window  # Reuse cached value

        # FEAR: Task manager / activity monitor
        for kw in TASK_MANAGER_KEYWORDS:
            if kw.lower() in window:
                return Emotion.FEAR

        # DISGUST: Procrastination sites
        for domain in PROCRASTINATION_DOMAINS:
            if domain in window:
                return Emotion.DISGUST

        # WONDER: Rapid window switching
        if self._window_switch_count >= RAPID_WINDOW_SWITCH_THRESHOLD:
            return Emotion.WONDER

        # ANGER: Risky keyword match
        if self._last_risky_match:
            return Emotion.ANGER

        # DEVOTION: High APM (> 60)
        if self._current_apm > 60:
            return Emotion.DEVOTION

        # PATHOS: Stale idle (>= 120s, no APM)
        if self._idle_seconds >= 120 and self._current_apm == 0:
            return Emotion.PATHOS

        # TRANQUILITY: Steady coding in IDE
        if self._current_apm > 0 and self._current_apm <= 60 and ("code" in win_title):
            return Emotion.TRANQUILITY

        # MIRTH: Default
        return Emotion.MIRTH

    def _evaluate_plugin_emotion(self) -> Emotion | None:
        """Check plugin emotion rules. Returns an Emotion or None.

        Plugins run at their registered priority order (lower = first).
        The first rule that returns a non-None Emotion wins.
        """
        registry = getattr(self, "_plugin_registry", None)
        if registry is None:
            return None
        # Lazy import to avoid circular dependency at module level
        from src.plugin_registry import PluginRegistry
        if not isinstance(registry, PluginRegistry):
            return None
        context = {
            "apm": self._current_apm,
            "idle_seconds": self._idle_seconds,
            "window_title": get_active_window_title() or "",
            "typing_content": self._typing_buffer.get_context() if self._typing_buffer else "",
            "window_switch_count": self._window_switch_count,
            "last_risky_match": self._last_risky_match,
        }
        return registry.evaluate_emotion(context)

    # ── Guard Logic ──────────────────────────────────────────────────

    def _should_fire_autonomous(self, mode: str) -> bool:
        """Return True if autonomous tick is allowed to fire right now."""
        # Global debounce: never fire more than once per 15s regardless of mode
        elapsed = time.time() - self._last_autonomous_fire_time
        if elapsed < 15.0:
            logger.debug("[%s] Skipping: debounce (%.1fs < 15s)", mode, elapsed)
            return False
        if mode == "boredom":
            if self._response_manager.remaining() == 0:
                logger.debug("[%s] Skipping: thought pool empty", mode)
                return False
        elif not self._opencode_enabled:
            logger.debug("[%s] Skipping: opencode disabled", mode)
            return False
        if self._autonomous_query_pending:
            logger.debug("[%s] Skipping: autonomous query pending", mode)
            return False
        if self._fsm.current_state in (
            PetState.THINKING, PetState.DRAGGED, PetState.FALLING,
            PetState.SLEEP,
        ):
            logger.debug(
                "[%s] Skipping: FSM state=%s",
                mode, self._fsm.current_state.name,
            )
            return False
        return True

    # ── Context Stability ───────────────────────────────────────────

    def _has_significant_delta(self) -> bool:
        """Detect context switches: window change or typing burst."""
        current_window = get_active_window_title()
        current_typing = self._typing_buffer.get_context() if self._typing_buffer else ""

        window_changed = (
            current_window != self._last_active_window and current_window != ""
        )
        typing_burst = (
            len(current_typing) - len(self._last_typing_snapshot) > 20
        )

        if window_changed:
            clear_screen_cache()

        self._last_active_window = current_window
        self._last_typing_snapshot = current_typing

        return window_changed or typing_burst

    def _get_context_signature(self) -> tuple:
        """Generate a hashable signature of the current context."""
        window = get_active_window_title() or ""
        typing = self._typing_buffer.get_context() if self._typing_buffer else ""
        screen = ScreenReader.get_foreground_text() or ""
        screen_hash = hash(screen[:500]) if screen else 0
        return (window, self._current_apm, len(typing), screen_hash)

    def _is_context_stable(self) -> bool:
        """Check if context has remained unchanged since last snapshot."""
        current = self._get_context_signature()
        if self._last_context_snapshot is None:
            self._last_context_snapshot = current
            return False
        return current == self._last_context_snapshot

    # ── Helpers ─────────────────────────────────────────────────────

    def _calculate_joke_modifier(self) -> float:
        """Inverse APM scaling: low APM = frequent jokes, high APM = rare jokes."""
        apm = self._current_apm
        if apm < 10:
            return 0.5   # 30s base → rapid fire
        elif apm < 20:
            return 1.0   # 60s base
        elif apm < 40:
            return 2.0   # 120s base
        else:
            return 3.0   # 180s base — rare


def clear_screen_cache() -> None:
    """Clear screen reader cache when window changes."""
    from src.system.screen_reader import clear_screen_cache as _clear
    _clear()


# ── Export public class ───────────────────────────────────────────

__all__ = ["BehaviorController"]