# src/pet_window.py
from __future__ import annotations
import json
import logging
import random
import re
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import QWidget, QApplication, QLineEdit, QSystemTrayIcon, QMenu, QDialog
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, QEvent, QThread
from PyQt6.QtGui import QPainter, QPixmap, QIcon, QColor

from src.constants import (
    FSM_TICK_MS, PET_WIDTH, PET_HEIGHT, GROUND_PADDING_PX,
    GRAVITY_ACCELERATION, WANDER_SPEED_PX, APM_HYPER_THRESHOLD,
    SPEECH_BUBBLE_DURATION_MS,
    INPUT_WIDTH, INPUT_HEIGHT, INPUT_Y_OFFSET,
    BOREDOM_TIMEOUT_SEC,
    AUTONOMOUS_QUERY_INTERVAL_SEC, ACTIVE_CHAT_INTERVAL_SEC, JOKE_INTERVAL_SEC,
    BRAIN_PATH, RESPONSE_CACHE_PATH,
    THOUGHTS_LOG_PATH,
    DEBUG,
    SILENCE_THRESHOLD, ENGAGED_THRESHOLD, BASE_INTERVAL_SEC,
    MAX_BACKOFF_SEC, BACKOFF_MULTIPLIER,
    BUBBLE_QUEUE_MAX_SIZE,
    SHORT_BUBBLE_DURATION_MS, SHORT_BUBBLE_CHAR_LIMIT,
    SQUASH_STRETCH_DURATION_MS, PERIMETER_FALL_CHANCE,
    RISKY_KEYWORDS,
    EMOTION_TICK_SEC, RAPID_WINDOW_SWITCH_THRESHOLD,
    TASK_MANAGER_KEYWORDS, PROCRASTINATION_DOMAINS,
    APM_PANIC_THRESHOLD_LOW, APM_PANIC_THRESHOLD_HIGH, APM_PANIC_COOLDOWN_SEC,
    APM_STATE_CHANGE_COOLDOWN,
)
from src.pet_fsm import PetFSM, PetState, FSMContext
from src.pet_renderer import PetRenderer, RenderContext
from src.tts_worker import TTSWorker
from src.click_through import ClickThroughManager
from src.apm_worker import APMWorker
from src.typing_buffer import TypingBuffer
from src.context_menu import PetContextMenu
from src.opencode_worker import OpencodeWorker
from src.strands_worker import StrandsAutonomousWorker
from src.llm_session_persistence import load_session, save_session, LLMSessionState
from src.active_window import get_active_window_title, normalize_window_title
from src.screen_reader import ScreenReader
from src.memory import Memory
from src.history import History
from src.memory_manager import MemoryManager
from src.write_coalescer import WriteCoalescer
from src.diary_store import DiaryStore
from src.event_worker import EventStreamWorker
from src.context_manager import ContextManager
from src.response_manager import AutonomousResponseManager


from src.fsm_bridge import FSMActionBridge
from src.mcp_server import MCPServer
from src.animator import EmotionAnimator, Emotion
from src.events import get_event_bus, EventType, Event
from src.behavior_controller import BehaviorController

logger = logging.getLogger(__name__)

_LOGIN_PROMPT = "Intruder! I-I don't recognize your clearance, man! Identify yourself before I freak out!"
_LOGIN_SUCCESS = "Oh, it's just you. You coulda said so, jeez. Welcome back to this digital hellhole."


class PetWindow(QWidget):
    def __init__(
        self,
        opencode_enabled: bool = True,
        skill_ready: bool = False,
        initial_state: dict | None = None,
        memory_path: str | None = None,
        history_path: str | None = None,
        auth: "FirebaseAuth | None" = None,
        fresh_login: bool = False,
        pet_id: str = "kenny",
        plugin_registry: object = None,
        **kwargs
    ) -> None:
        if "agy_enabled" in kwargs:
            opencode_enabled = kwargs.pop("agy_enabled")
        super().__init__()
        self._pet_id = pet_id
        self._auth = auth
        self._opencode_enabled = opencode_enabled
        self._plugin_registry = plugin_registry
        initial_state = initial_state or {}
        self._initial_state = initial_state
        self._fresh_login = fresh_login
        self.mood_score = initial_state.get("mood", 0)
        self.interaction_count = initial_state.get("interactions", 0)

        self.screen_time = self._initial_state.get("screen_time", {})
        self.screen_time_date = self._initial_state.get("screen_time_date", "")
        today = datetime.now().strftime("%Y-%m-%d")
        if self.screen_time_date != today:
            self.screen_time = {}
            self.screen_time_date = today
        self._screen_time_tick = 0
        self._skill_ready = skill_ready
        self._force_quit = False
        self._click_through: ClickThroughManager | None = None
        self._setup_window()

        from src.config import load_config
        self._config = load_config()
        self._pet_scale = self._config.get("pet", {}).get("scale", 1.0)
        self._pet_opacity = self._config.get("pet", {}).get("opacity", 0.85)
        self._pet_speed_multiplier = self._config.get("pet", {}).get("speed_multiplier", 1.0)
        self._chattiness = self._config.get("pet", {}).get("chattiness", 1.0)

        self._scale = QApplication.primaryScreen().devicePixelRatio()
        self._ground_y = self._compute_ground_y()

        self._pet_x = 100
        self._pet_y = self._ground_y

        self._fall_velocity = 0.0
        self._land_time: float = 0.0
        self._takeoff_time: float = 0.0
        self._title_land_time: float = 0.0
        self._last_window_rect = None
        self._drag_offset = QPoint(0, 0)
        self._drag_velocity_x = 0.0
        self._drag_velocity_y = 0.0
        self._drag_start_time = 0.0

        self._last_drag_pos = QPoint(0, 0)
        self._wander_target_x: int | None = None
        self._wander_direction = 1
        self._perimeter_edge: str = "bottom"
        self._perimeter_facing: str = "right"
        self._anim_tick = 0
        self._wander_timer_remaining = random.randint(15000, 45000)

        self._current_apm = 0
        self._hyper_sustained = 0.0
        self._hyper_cooldown = 0.0
        self._hyper_color_index = 0
        self._hyper_flash_timer = QTimer(self)
        self._hyper_flash_timer.setInterval(125)
        self._hyper_flash_timer.timeout.connect(self._cycle_hyper_color)
        self._hyper_flash_timer.start()

        # APM Hysteresis state
        self._apm_state = "normal"
        self._last_apm_state_change = 0.0
        self._last_apm = 0

        # D2: parse failure cooldown — track consecutive failures for backoff
        self._parse_failure_count = 0
        self._last_parse_failure_time = 0.0

        self._last_mode = ""
        self._idle_seconds = 0.0
        self._state_elapsed_ms = 0
        self._screen_time_tick = 0
        self._build_event: str | None = None

        self._fsm = PetFSM()
        self._renderer = PetRenderer()
        self._animator = EmotionAnimator()

        self._pinned = False
        self._forced_sleep = False

        self._context_menu = PetContextMenu(self)
        self._context_menu.signals.quit_requested.connect(self._force_quit_app)
        self._context_menu.signals.recall_memory.connect(self._on_recall_memory)
        self._context_menu.signals.recall_history.connect(self._on_recall_history)
        self._context_menu.signals.pin_toggle.connect(self._on_pin_toggle)
        self._context_menu.signals.restart_brain.connect(self._on_restart_brain)
        self._context_menu.signals.thought_log.connect(self._open_thought_log)
        self._context_menu.signals.settings_requested.connect(self._open_settings)
        self._context_menu.signals.sleep_toggle.connect(self._on_sleep_toggle)
        self._context_menu.signals.mute_toggle.connect(self._on_mute_toggle)
        self._context_menu.signals.wipe_memory.connect(self._on_wipe_memory)

        self._apm_worker = APMWorker()
        self._apm_worker.apm_updated.connect(self._on_apm_updated)
        self._apm_worker.hotkey_triggered.connect(self._on_global_hotkey)
        self._apm_worker.start()

        self._typing_buffer = TypingBuffer()
        self._typing_buffer.start()

        self._lsp_debounce_timer = QTimer(self)
        self._lsp_debounce_timer.setSingleShot(True)
        self._lsp_debounce_timer.setInterval(5000)
        self._lsp_debounce_timer.timeout.connect(self._on_lsp_timeout)

        self._event_worker = EventStreamWorker()
        self._event_worker.lsp_error_detected.connect(self._on_lsp_error_detected)
        self._event_worker.lsp_error_cleared.connect(self._on_lsp_error_cleared)
        self._event_worker.command_completed.connect(self._on_command_completed)
        self._event_worker.file_edited.connect(self._on_file_edited)
        self._event_worker.start()

        self._tts = TTSWorker(config=self._config)
        self._tts.start()
        if not self._config.get("tts", {}).get("enabled", True):
            self._tts.set_enabled(False)

        # MCP FSM bridge — thread-safe signal relay between MCP server and Qt main thread
        self._fsm_bridge = FSMActionBridge()
        self._fsm_bridge.request.connect(self._on_mcp_fsm_action)
        self._fsm_bridge.toast_request.connect(self._on_toast_requested)
        self._fsm_bridge.reminder_request.connect(self._on_reminder_request)
        self._reminders = {}
        if hasattr(self._fsm_bridge, "summarize_requested"):
            self._fsm_bridge.summarize_requested.connect(self._handle_summarize_request)
        self._bubble_queue: list[str] = []
        self._bubble_text = ""
        self._bubble_timer_ms = 0
        brain_path = self._config.get("storage", {}).get("brain_path", BRAIN_PATH)

        self._memory = Memory(path=brain_path)
        self._history = History(path=brain_path)
        self._crud = None
        self._firebase_available = False
        self._firebase_mem = None
        self._diary_path = brain_path

        self._diary_store = DiaryStore(self._diary_path)
        self._mcp_server = MCPServer(self._fsm_bridge, memory=self._memory, diary_store=self._diary_store, config=self._config)
        self._write_coalescer = WriteCoalescer(
            memory=self._memory, history=self._history,
            memory_manager=self._firebase_mem,
            diary_store=self._diary_store,
        )
        self._memory._coalescer = self._write_coalescer
        self._history._coalescer = self._write_coalescer
        self._init_diary()
        self._log_data_state("Startup")

        self._context_manager = ContextManager(
            memory=self._memory, history=self._history,
        )
        self._response_manager = AutonomousResponseManager(
            cache_path=RESPONSE_CACHE_PATH,
            write_coalescer=self._write_coalescer,
        )
        self._response_manager.thought_pool.refill_needed.connect(self._on_refill_needed)
        self._response_manager.thought_pool.pool_refilled.connect(self._on_pool_refilled)
        self._response_manager.start()
        self._log_data_state("Startup+Cache")

        # Event bus for decoupled communication
        self._events = get_event_bus()

        # BehaviorController — autonomous behavior engine
        self._behavior = BehaviorController(
            event_bus=self._events,
            response_manager=self._response_manager,
            typing_buffer=self._typing_buffer,
            fsm=self._fsm,
            animator=self._animator,
            opencode_enabled=self._opencode_enabled,
            chattiness=self._chattiness,
            plugin_registry=self._plugin_registry,
        )

        self._typing_last_len = 0
        self._typing_debounce_timer = QTimer(self)
        self._typing_debounce_timer.setSingleShot(True)
        self._typing_debounce_timer.setInterval(2000)
        self._typing_debounce_timer.timeout.connect(self._on_typing_debounce)
        self._typing_buffer.text_updated.connect(self._typing_debounce_timer.start)

        self._write_coalescer.start()

        self._install_crash_recovery_hook()

        if not (initial_state or {}).get("first_run_done", False):
            self._bubble_queue = [
                "Hey! I'm Kenny! Nice to meet ya.",
                "Double-click me if you wanna ask opencode anything, alright?",
                "Right-click me for options. D-d-don't click too hard though!",
            ]
            self._greeting_timer = QTimer(self)
            self._greeting_timer.setSingleShot(True)
            self._greeting_timer.setInterval(1500)
            self._greeting_timer.timeout.connect(self._show_greeting_bubble)
            self._greeting_timer.start()


        self._fsm_timer = QTimer(self)
        self._fsm_timer.setInterval(FSM_TICK_MS)
        self._fsm_timer.timeout.connect(self._tick)
        self._fsm_timer.start()

        from src.constants import BEHAVIOR_TICK_MS
        self._behavior_timer = QTimer(self)
        self._behavior_timer.setInterval(BEHAVIOR_TICK_MS)
        self._behavior_timer.timeout.connect(self._master_tick)
        self._behavior_timer.start()

        self._bubble_text = ""
        self._bubble_timer_ms = 0
        self._bubble_rect = QRect()
        self._opencode_worker: OpencodeWorker | None = None
        self._boredom_timer_ms: int = BOREDOM_TIMEOUT_SEC * 1000
        self._autonomous_query_pending: bool = False
        self._session_active: bool = False
        self._opencode_session_id: str | None = None
        self._opencode_worker: OpencodeWorker | None = None
        self._triggered_action: str | None = None
        self._last_daemon_action: str = "idle"
        self._refill_workers: dict[str, OpencodeWorker] = {}
        self._refill_workers_lock = threading.Lock()
        # Persistent LLM session — resume across restarts
        self._llm_session_state = load_session()
        if self._llm_session_state.session_id:
            # Opencode serve was killed and respawned — the saved session ID is
            # guaranteed dead. Keep the history for context injection, but clear
            # the stale session so the first query creates a fresh one without
            # a 404-retry cycle.
            logger.info(
                "Clearing stale session %s (opencode serve was respawned); "
                "%d history turns preserved for context injection",
                self._llm_session_state.session_id,
                len(self._llm_session_state.history),
            )
            self._llm_session_state.session_id = None

        self._consecutive_silent = 0
        self._consecutive_engaged = ENGAGED_THRESHOLD
        self._current_interval = BASE_INTERVAL_SEC
        self._idle_backoff_seconds = 0.0
        self._last_context_snapshot = None

        self._deferred_trigger_params: dict | None = None

        self._brain_disconnected = False
        self._refill_in_progress = False
        self._health_timer = QTimer(self)
        self._health_timer.setSingleShot(True)
        self._health_timer.setInterval(3000)
        self._health_timer.timeout.connect(self._on_health_check)
        self._health_timer.start()

        # Refill worker state
        self._last_refill_attempt = 0.0
        self._refill_failed_count = 0

        # Monotonic time tracking for drift-free timers
        self._last_tick_time = time.monotonic()
        self._last_master_tick_time = time.monotonic()

        self._input_field = QLineEdit(self)
        self._input_field.setFixedSize(INPUT_WIDTH, INPUT_HEIGHT)
        self._input_field.setPlaceholderText("Ask opencode anything…")
        self._input_field.setStyleSheet(
            "QLineEdit { background: #1A1A2E; color: #E0E0E0; "
            "border: 1px solid #5B8DEF; border-radius: 4px; padding: 2px 6px; }"
        )
        self._input_field.hide()
        self._input_field.returnPressed.connect(self._on_input_submitted)
        self._input_field.installEventFilter(self)

        self._tray_icon = self._build_tray()
        self._tray_icon.show()

        if skill_ready and not initial_state.get("skill_greeted", False):
            self._show_bubble("Oh god! My memory is active! Don't look in there!")

        self._boot_timer = QTimer(self)
        self._boot_timer.setSingleShot(True)
        self._boot_timer.setInterval(500)
        self._boot_timer.timeout.connect(self._on_boot_check_auth)
        self._boot_timer.start()
        self._mcp_server.start()

        # Wire EventBus subscriber for autonomous triggers from BehaviorController
        self._events.subscribe(
            EventType.AUTONOMOUS_TRIGGER_FIRED,
            self._on_autonomous_trigger_fired,
        )

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Set window to cover the entire screen so the pet can move anywhere
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        self.show()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._click_through is None:
            hwnd = int(self.winId())
            self._click_through = ClickThroughManager(hwnd, self._get_click_geometry)

    def _get_click_geometry(self) -> QRect:
        rect = QRect(self._pet_x, self._pet_y, int(PET_WIDTH * getattr(self, '_scale', 1.0) * getattr(self, '_pet_scale', 1.0)), int(PET_HEIGHT * getattr(self, '_scale', 1.0) * getattr(self, '_pet_scale', 1.0)))
        top_left = self.mapToGlobal(rect.topLeft())
        bottom_right = self.mapToGlobal(rect.bottomRight())
        rect = QRect(top_left, bottom_right)
        if self._bubble_text and hasattr(self, '_bubble_rect') and not self._bubble_rect.isEmpty():
            bubble_tl = self.mapToGlobal(self._bubble_rect.topLeft())
            bubble_br = self.mapToGlobal(self._bubble_rect.bottomRight())
            rect = rect.united(QRect(bubble_tl, bubble_br))
        if hasattr(self, '_input_field') and self._input_field.isVisible():
            input_geom = self._input_field.geometry()
            input_tl = self.mapToGlobal(input_geom.topLeft())
            input_br = self.mapToGlobal(input_geom.bottomRight())
            rect = rect.united(QRect(input_tl, input_br))
        return rect

    def _compute_ground_y(self) -> int:
        screen = QApplication.primaryScreen().availableGeometry()
        return screen.bottom() - PET_HEIGHT - GROUND_PADDING_PX

    def _get_logical_window_rect(self):
        try:
            from src.active_window import get_window_rect
            r = get_window_rect(int(self.winId()))
            if r:
                s = self._scale if hasattr(self, '_scale') and self._scale > 0 else 1.0
                return (int(r[0]/s), int(r[1]/s), int(r[2]/s), int(r[3]/s))
        except Exception:
            pass
        return None

    def _update_ground_y(self, rect=None) -> None:
        base_ground = self._compute_ground_y()
        self._ground_y = base_ground
        
        if rect is None:
            rect = self._get_logical_window_rect()
        if rect:
            left, top, right, bottom = rect
            pet_center_x = self._pet_x + PET_WIDTH // 2
            # Ensure window is valid and not maximized at negative coords
            if 0 < top <= base_ground and left <= pet_center_x <= right:
                self._ground_y = top - PET_HEIGHT

        if self._pet_y > base_ground:
            self._pet_y = base_ground
        elif self._pet_y < self._ground_y and self._fsm.current_state not in (PetState.FALLING, PetState.DRAGGED):
            self._fsm.transition_to(PetState.FALLING)

    def _cycle_hyper_color(self) -> None:
        self._hyper_color_index = (self._hyper_color_index + 1) % 4

    def _on_apm_updated(self, apm: int) -> None:
        self._current_apm = apm
        self._behavior.set_apm(apm)
        try:
            from src.observability import update_apm
            update_apm(apm)
        except Exception:
            pass
        if apm > 0:
            self._boredom_timer_ms = BOREDOM_TIMEOUT_SEC * 1000
            self._behavior.on_activity_detected()

        # APM Hysteresis - prevent overreactions to normal variations
        current_time = time.time()
        apm_state_changed = False

        if apm <= APM_PANIC_THRESHOLD_LOW:
            if self._apm_state != "low":
                self._apm_state = "low"
                apm_state_changed = True
        elif apm >= APM_PANIC_THRESHOLD_HIGH:
            if self._apm_state != "high":
                self._apm_state = "high"
                apm_state_changed = True
        else:
            if self._apm_state not in ("low", "high"):
                self._apm_state = "normal"
                apm_state_changed = True

        if apm_state_changed:
            self._last_apm_state_change = current_time
            self._events.publish(Event(
                type=EventType.APM_THRESHOLD_CROSSED,
                source="pet_window",
                data={"apm": apm, "state": self._apm_state}
            ))

        # Only trigger panic reactions if enough time has passed since last state change
        if (current_time - self._last_apm_state_change) < APM_PANIC_COOLDOWN_SEC:
            return

        # React to significant APM changes only
        if not hasattr(self, "_last_apm_panic_time"):
            self._last_apm_panic_time = 0.0
            
        if (current_time - self._last_apm_panic_time) < APM_PANIC_COOLDOWN_SEC:
            pass # Skip if we just panicked
        elif apm <= APM_PANIC_THRESHOLD_LOW and hasattr(self, "_last_apm"):
            if apm < self._last_apm * 0.5:  # 50% drop threshold
                self._trigger_apm_panic("low")
                self._last_apm_panic_time = current_time
        elif apm >= APM_PANIC_THRESHOLD_HIGH and hasattr(self, "_last_apm"):
            if apm > self._last_apm * 1.5:  # 50% increase threshold
                self._trigger_apm_panic("high")
                self._last_apm_panic_time = current_time

        self._last_apm = apm

    def _trigger_apm_panic(self, panic_type: str) -> None:
        """Trigger panic reaction to significant APM changes."""
        from src.pet_fsm import PetState
        # D1: Skip APM panic if thought pool is too empty — the panic bubble
        # would lock the GCD and prevent pool refill from displaying
        if self._response_manager.remaining() < 3 and panic_type == "low":
            logger.debug("Skipping APM panic (pool starved, remaining=%d)",
                         self._response_manager.remaining())
            return
        if panic_type == "low":
            self._show_bubble("Why is my APM so low? I can't even think!")
            # Don't use THINKING here as it expects an opencode worker to release it
            self._fsm.current_state = PetState.IDLE 
            self._fsm.transition_to(PetState.LOOK_AWAY)
        elif panic_type == "high":
            self._show_bubble("My APM just spiked! I'm hyperventilating!")
            self._fsm.current_state = PetState.IDLE
            self._fsm.transition_to(PetState.HYPER)

    def _master_tick(self) -> None:
        """Delegate autonomous behavior to BehaviorController.

        Uses time.monotonic() for drift-free behavioral timing.
        """
        try:
            now = time.monotonic()
            self._behavior.set_idle_seconds(self._idle_seconds)
            self._behavior.tick(now - self._last_master_tick_time)
            self._last_master_tick_time = now

            self._screen_time_tick += 1
            if self._screen_time_tick >= 10:
                self._update_screen_time()
                self._screen_time_tick = 0
        except Exception as e:
            logger.critical("CRASH in _master_tick: %s", e, exc_info=True)
            raise

    def _update_screen_time(self) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        if self.screen_time_date != today:
            self.screen_time = {}
            self.screen_time_date = today

        from src.active_window import get_active_window_title
        window_title = get_active_window_title()
        if not window_title:
            return
            
        if "-" in window_title:
            app_name = window_title.split("-")[-1].strip()
        else:
            app_name = window_title.strip()

        if app_name not in self.screen_time:
            self.screen_time[app_name] = 0
        self.screen_time[app_name] += 10  # Called every 10s

        warn_sec = self._memory.get_all().get("screen_time_warn_sec", 3600)
        if self.screen_time[app_name] == warn_sec:
            # Emit threshold event
            from src.events import Event, EventType
            self._events.publish(Event(
                type=EventType.SCREEN_TIME_THRESHOLD_REACHED,
                source="pet_window",
                data={"app_name": app_name, "duration": self.screen_time[app_name]}
            ))

    def _handle_summarize_request(self, provider_id: str, model_id: str) -> None:
        self._trigger_ghost_summarization()

    def _on_reminder_request(self, action: str, data: dict) -> None:
        logger.debug(f"[Reminders] MCP Request received: {action} with data: {data}")
        if action == "set":
            import uuid
            rem_id = str(uuid.uuid4())[:8]
            msg = data.get("message", "Reminder")
            mins = data.get("time_minutes", 1)
            
            logger.debug(f"[Reminders] Setting reminder {rem_id}: '{msg}' for {mins} minutes.")
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: self._fire_reminder(rem_id, msg))
            timer.start(int(mins * 60000))
            
            self._reminders[rem_id] = {
                "message": msg,
                "time_minutes": mins,
                "created_at": time.time(),
                "timer": timer
            }
            # The MCP handler handles the return value (via a future, but since it's async, we just set it)
            if "future" in data:
                data["future"].set_result(rem_id)
        elif action == "get":
            active = []
            for k, v in self._reminders.items():
                active.append({
                    "id": k,
                    "message": v["message"],
                    "time_minutes": v["time_minutes"],
                    "elapsed_minutes": (time.time() - v["created_at"]) / 60.0
                })
            if "future" in data:
                data["future"].set_result(active)
        elif action == "dismiss":
            rem_id = data.get("id")
            if rem_id in self._reminders:
                self._reminders[rem_id]["timer"].stop()
                del self._reminders[rem_id]
                if "future" in data:
                    data["future"].set_result(True)
            else:
                if "future" in data:
                    data["future"].set_result(False)

    def _fire_reminder(self, rem_id: str, msg: str) -> None:
        logger.debug(f"[Reminders] Timer expired for reminder {rem_id}. Firing UI events!")
        if rem_id in self._reminders:
            del self._reminders[rem_id]
        
        # Build the visual trigger
        self._on_toast_requested("Reminder", msg)
        self._bubble_queue.append(msg)
        self._show_next_bubble()
        
        # Transition state
        from src.pet_fsm import PetState
        self._fsm.transition_to(PetState.BOUNCING)

    def _force_quit_app(self) -> None:
        if self._force_quit:
            return
        self._force_quit = True
        logger.info("Initiating Ghost Mode shutdown sequence...")
        self._events.publish(Event(
            type=EventType.PET_SHUTDOWN_STARTED,
            source="pet_window",
            data={}
        ))
        
        # Hide UI immediately
        self.hide()
        if hasattr(self, '_tray_icon') and self._tray_icon:
            self._tray_icon.hide()
            
        # Trigger summarization
        self._trigger_ghost_summarization(on_complete=self._finalize_quit)

    def _trigger_ghost_summarization(self, on_complete=None) -> None:
        self._summary_on_complete = on_complete
        
        # Failsafe timer (15 seconds)
        from PyQt6.QtCore import QTimer
        self._shutdown_timer = QTimer(self)
        self._shutdown_timer.setSingleShot(True)
        if on_complete:
            self._shutdown_timer.timeout.connect(on_complete)
        self._shutdown_timer.start(15000)
        
        import time
        recent = self._history.get_recent(50)
        # Skip API call if session was too short to summarise
        if not recent or len(recent) < 10:
            logger.debug("Skipping summary: only %d history items", len(recent) if recent else 0)
            if on_complete:
                on_complete()
            return
        
        # History entries have user_input, daemon_response, action, timestamp keys
        lines = []
        for item in recent:
            ui = (item.get("user_input") or "").strip()
            dr = (item.get("daemon_response") or "").strip()
            if ui:
                lines.append(f"User: {ui[:1000]}")
            if dr:
                lines.append(f"Assistant: {dr[:1000]}")
        if not lines:
            logger.debug("Skipping summary: no meaningful history content")
            if on_complete:
                on_complete()
            return
        history_text = "\n".join(lines)
        prompt = f"Summarize this session strictly into a single observation about the user's habits:\n{history_text}"
        
        from src.opencode_worker import OpencodeWorker
        self._summary_worker = OpencodeWorker(
            user_input="",
            prompt=prompt,
            session_id=self._opencode_session_id,
            is_autonomous=True
        )
        self._summary_worker.response_ready.connect(self._on_summary_ready)
        self._summary_worker.start()

    def _on_summary_ready(self, items: list[dict]) -> None:
        if items and "content" in items[0]:
            import time
            summary = items[0]["content"]
            # Save to DiaryStore
            if hasattr(self, '_diary_store'):
                self._diary_store.add_diary_entry(summary, int(time.time()))
            # Push to Firebase
            if hasattr(self, '_firebase_mem') and self._firebase_mem and hasattr(self, '_diary_store'):
                self._firebase_mem.push_pending_diaries(self._diary_store)
            logger.info("Session summarized and saved.")
            
        if hasattr(self, "_summary_on_complete") and self._summary_on_complete:
            if hasattr(self, '_shutdown_timer') and self._shutdown_timer.isActive():
                self._shutdown_timer.stop()
            self._summary_on_complete()

    def _finalize_quit(self) -> None:
        self._mcp_server.stop()
        self._fsm_timer.stop()
        self._behavior_timer.stop()
        self._hyper_flash_timer.stop()
        self._typing_debounce_timer.stop()
        self._health_timer.stop()
        self._event_worker.stop()
        if hasattr(self, "_greeting_timer"):
            self._greeting_timer.stop()
        if hasattr(self, "_boot_timer"):
            self._boot_timer.stop()
        self._log_data_state("Shutdown")
        self._response_manager.stop()
        try:
            self._write_coalescer.stop()
            self._write_coalescer.flush()
        except Exception as e:
            logger.warning("WriteCoalescer flush failed: %s", e)
        for worker in list(self._refill_workers.values()):
            if worker.isRunning():
                worker.abort()
                worker.quit()
                worker.wait(5000)
        with self._refill_workers_lock:
            self._refill_workers.clear()
        if self._opencode_worker and self._opencode_worker.isRunning():
            self._opencode_worker.abort()
            self._opencode_worker.quit()
            self._opencode_worker.wait(5000)
        self._deferred_trigger_params = None
        self._close_opencode_session()
        self._typing_buffer.stop()
        self._tts.stop()
        self._apm_worker.stop()
        if hasattr(self, "_thought_log_dialog") and self._thought_log_dialog is not None:
            try:
                self._thought_log_dialog.close()
            except Exception:
                pass
        # Cleanup UIA COM
        try:
            from src.screen_reader import _cleanup_uia
            _cleanup_uia()
        except Exception:
            pass
        # Persist LLM session state for next boot
        try:
            if hasattr(self, '_llm_session_state') and self._llm_session_state is not None:
                save_session(self._llm_session_state, generate_summary=True)
        except Exception as e:
            logger.warning("Failed to persist LLM session on shutdown: %s", e)
        QApplication.quit()

    def _on_lsp_error_detected(self, payload: dict):
        if not self._lsp_debounce_timer.isActive():
            self._lsp_debounce_timer.start()

    def _on_lsp_error_cleared(self):
        self._lsp_debounce_timer.stop()

    def _on_lsp_timeout(self):
        # Bypass boredom timer
        self._idle_seconds = 600  # Force idle condition
        self._triggered_action = "shake"
        # Wait for the master tick to pick it up or push direct dispatch here

    def _on_command_completed(self, cmd: str, exit_code: int):
        from src.pet_fsm import PetState
        if exit_code == 0:
            self._fsm.transition_to(PetState.CELEBRATE)
        else:
            self._fsm.transition_to(PetState.DEVASTATED)

    def _on_file_edited(self, filepath: str):
        # Optional context storing for the context manager
        if hasattr(self._behavior, "handle_file_edited"):
            self._behavior.handle_file_edited(filepath)

    def closeEvent(self, event) -> None:
        if self._force_quit:
            event.accept()
            return
        event.ignore()
        self.hide()

    def _build_tray(self) -> QSystemTrayIcon:
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor(0, 0, 0, 0))
        p = QPainter(pixmap)
        p.setBrush(QColor("#5B8DEF"))
        p.setPen(QColor("#2C3E6B"))
        p.drawRoundedRect(2, 2, 12, 12, 3, 3)
        p.setBrush(QColor("#FFFFFF"))
        p.setPen(QColor(0, 0, 0, 0))
        p.drawEllipse(4, 5, 3, 3)
        p.drawEllipse(9, 5, 3, 3)
        p.end()

        icon = QIcon(pixmap)
        tray = QSystemTrayIcon(icon, self)
        tray.setToolTip("Daemon")

        tray_menu = QMenu()
        tray_menu.addAction("Restore", self.show)
        tray_menu.addSeparator()
        tray_menu.addAction("Settings...", self._open_settings)
        tray_menu.addAction("Quit", self._force_quit_app)
        tray.setContextMenu(tray_menu)
        tray.activated.connect(self._on_tray_activated)
        return tray

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
            self.raise_()

    def _open_settings(self) -> None:
        from src.settings_dialog import SettingsDialog
        self._saved_scale = self._pet_scale
        self._saved_opacity = self._pet_opacity
        self._saved_speed = self._pet_speed_multiplier
        self._saved_tts = self._tts._enabled.is_set() if self._tts else True
        self._saved_tts_rate = self._tts.rate if self._tts else 220
        self._saved_tts_volume = self._tts.volume if self._tts else 1.0
        self._saved_tts_voice_id = self._tts.voice_id if self._tts else None
        self._saved_chattiness = self._chattiness
        self._saved_consent = {
            k: self._config.get("consent", {}).get(k, v) for k, v in {
                "allow_intrusive_animations": True,
                "allow_audio_disruptions": False,
                "allow_browser_redirection": False,
                "allow_clipboard_hijacking": False,
                "allow_mouse_interference": False,
                "allow_window_management": False,
                "allow_keyboard_injection": False,
            }.items()
        }

        dialog = SettingsDialog(
            pet_scale=self._pet_scale,
            pet_opacity=self._pet_opacity,
            pet_speed=self._pet_speed_multiplier,
            tts_enabled=self._saved_tts,
            tts_rate=self._saved_tts_rate,
            tts_volume=self._saved_tts_volume,
            tts_voice_id=self._saved_tts_voice_id,
            chattiness=self._chattiness,
            llm_model_id=self._config.get("llm", {}).get("model_id") or "gemini-2.5-flash",
            llm_api_key=self._config.get("llm", {}).get("api_key", ""),
            llm_server_url=self._config.get("llm", {}).get("server_url") or "http://127.0.0.1:4096",
            firebase_api_key=self._config.get("firebase", {}).get("api_key", ""),
            firebase_project_id=self._config.get("firebase", {}).get("project_id", ""),
            **self._saved_consent,
            parent=self,
        )
        dialog.value_changed.connect(lambda: self._apply_settings(dialog.get_values()))
        dialog.accepted.connect(lambda: self._save_settings(dialog.get_values()))
        dialog.rejected.connect(self._restore_settings)
        dialog.show()

    def _apply_settings(self, values: dict) -> None:
        self._pet_scale = values.get("pet_scale", self._pet_scale)
        self._ground_y = self._compute_ground_y()
        self._pet_opacity = values.get("pet_opacity", self._pet_opacity)
        self._pet_speed_multiplier = values.get("pet_speed_multiplier", self._pet_speed_multiplier)
        self.setWindowOpacity(1.0)
        if self._tts:
            self._tts.set_enabled(values.get("tts_enabled", True))
            if "tts_rate" in values:
                self._tts.rate = values["tts_rate"]
            if "tts_volume" in values:
                self._tts.volume = values["tts_volume"]
            if "tts_voice_id" in values:
                self._tts.voice_id = values.get("tts_voice_id")
        if "chattiness" in values:
            self._chattiness = values["chattiness"]

    def _save_settings(self, values: dict) -> None:
        from src.config import save_config, unflatten_config
        consent_keys = ("allow_intrusive_animations", "allow_audio_disruptions",
                        "allow_browser_redirection", "allow_clipboard_hijacking",
                        "allow_mouse_interference", "allow_window_management",
                        "allow_keyboard_injection")
        consent_state = {k: values.get(k, False) for k in consent_keys}
        logger.info("Consent Matrix updated by user: %s", consent_state)
        
        # Convert the flat UI dictionary back into the nested config structure
        nested_cfg = unflatten_config(values)
        save_config(nested_cfg)
        self._config = nested_cfg
        if self._mcp_server:
            self._mcp_server._config = self._config.get("consent", {})

    def _restore_settings(self) -> None:
        self._apply_settings({
            "pet_scale": self._saved_scale,
            "pet_opacity": self._saved_opacity,
            "pet_speed_multiplier": self._saved_speed,
            "tts_rate": self._saved_tts_rate,
            "tts_volume": self._saved_tts_volume,
            "chattiness": self._saved_chattiness,
            **self._saved_consent,
        })

    def _tick(self) -> None:
        try:
            current_rect = self._get_logical_window_rect()
            self._update_ground_y(current_rect)
            self._anim_tick += 1
            if self._bubble_timer_ms > 0:
                self._bubble_timer_ms -= FSM_TICK_MS
                if self._bubble_timer_ms <= 0:
                    if self._bubble_queue:
                        item = self._bubble_queue.pop(0)
                        self._bubble_text = item
                        duration = self._bubble_duration(item)
                        self._bubble_timer_ms = duration
                        # self._tts.enqueue(item)  # TTS paused
                        logger.info("_bubble queue -> next: '%s' (%d remaining, %dms)", item, len(self._bubble_queue), duration)
                    else:
                        self._bubble_text = ""
                        self._bubble_timer_ms = 0

            if not self._autonomous_query_pending:
                # Don't decrement boredom timer during active thinking states
                if self._fsm.current_state not in (PetState.THINKING, PetState.AUTONOMOUS_THINKING):
                    self._boredom_timer_ms -= FSM_TICK_MS
                    if self._boredom_timer_ms <= 0:
                        self._trigger_boredom_query()

            # Perched Check
            is_perched = False
            if current_rect:
                if self._pet_y == self._ground_y and self._ground_y == current_rect[1] - PET_HEIGHT:
                    is_perched = True
            
            # Wandering Constraints
            if is_perched and current_rect and self._fsm.current_state in (PetState.IDLE, PetState.PERIMETER):
                w_left, _, w_right, _ = current_rect
                if self._pet_x < w_left:
                    self._pet_x = w_left
                elif self._pet_x > w_right - PET_WIDTH:
                    self._pet_x = w_right - PET_WIDTH
            
            # Seeking & The Super Jump
            if current_rect and self._fsm.current_state not in (PetState.DRAGGED, PetState.FALLING):
                w_left, w_top, w_right, w_bottom = current_rect
                pet_center_x = self._pet_x + PET_WIDTH // 2
                
                if pet_center_x < w_left or pet_center_x > w_right:
                    self._fsm.transition_to(PetState.PERIMETER)
                    self._perimeter_edge = "bottom"
                    self._perimeter_facing = "right" if pet_center_x < w_left else "left"
                else:
                    if self._pet_y > self._ground_y and not is_perched:
                        d = self._pet_y - self._ground_y
                        if d > 0:
                            if not hasattr(self, "_prepare_jump_time") or self._prepare_jump_time == 0.0:
                                self._prepare_jump_time = time.time()
                            elif time.time() - self._prepare_jump_time > 0.15:
                                import math
                                self._fall_velocity = -math.sqrt(2 * GRAVITY_ACCELERATION * d)
                                self._fsm.transition_to(PetState.FALLING)
                                self._takeoff_time = time.time()
                                self._prepare_jump_time = 0.0
                    else:
                        self._prepare_jump_time = 0.0
            else:
                self._prepare_jump_time = 0.0

            self._last_window_rect = current_rect

            old_state = self._fsm.current_state
            ctx = self._build_fsm_context()
            new_state = self._fsm.update(FSM_TICK_MS, ctx)
            if new_state != old_state:
                logger.debug("FSM state transition: %s -> %s", old_state.name, new_state.name)
                try:
                    from src.observability import record_fsm_transition
                    record_fsm_transition(old_state.name, new_state.name)
                except Exception:
                    pass
                self._events.emit_fsm_state_changed(old_state.name, new_state.name)
                self._state_elapsed_ms = 0
                # Handle SLEEP state entry
                if new_state == PetState.SLEEP and old_state != PetState.SLEEP:
                    self._events.publish(Event(
                        type=EventType.PET_SLEEP_STARTED,
                        source="pet_window",
                        data={}
                    ))
                    self._autonomous_query_pending = False
                    self._deferred_trigger_params = None
                    self._last_boredom_fsm_time = time.time()
                    # Gracefully disconnect refill workers (NO wait())
                    with self._refill_workers_lock:
                        for worker in self._refill_workers.values():
                            if worker.isRunning():
                                try:
                                    worker.response_ready.disconnect()
                                except TypeError:
                                    pass
                                worker.quit()
                                if not hasattr(self, '_zombie_workers'):
                                    self._zombie_workers = set()
                                self._zombie_workers.add(worker)
                                
                                def _cleanup_refill_zombie(w=worker):
                                    if hasattr(self, '_zombie_workers'):
                                        self._zombie_workers.discard(w)
                                        
                                worker.finished.connect(_cleanup_refill_zombie)
                                worker.finished.connect(worker.deleteLater)
                        self._refill_workers.clear()
                # Handle SLEEP state exit
                if old_state == PetState.SLEEP and new_state != PetState.SLEEP:
                    self._events.publish(Event(
                        type=EventType.PET_SLEEP_ENDED,
                        source="pet_window",
                        data={}
                    ))
                    self._idle_backoff_seconds = 0.0
                    self._last_context_snapshot = None
                    self._last_boredom_fsm_time = time.time()
                    self._boredom_timer_ms = BOREDOM_TIMEOUT_SEC * 1000

            self._apply_physics(new_state, FSM_TICK_MS, current_rect)
            self._animator.update(FSM_TICK_MS, self._pet_x, self._pet_y)
            self.update()
        except Exception as e:
            logger.critical("CRASH in _tick: %s", e, exc_info=True)
            raise

    def _build_fsm_context(self) -> FSMContext:
        cursor = self._scaled_cursor_pos()

        wander_due = False
        if self._fsm.current_state == PetState.IDLE:
            self._wander_timer_remaining -= FSM_TICK_MS
            if self._wander_timer_remaining <= 0:
                wander_due = True
                self._wander_timer_remaining = random.randint(15000, 45000)
                self._wander_target_x = random.randint(
                    0,
                    QApplication.primaryScreen().availableGeometry().width() - PET_WIDTH
                )
                self._wander_direction = 1 if self._wander_target_x > self._pet_x else -1

        if self._pinned:
            wander_due = False

        if self._current_apm > APM_HYPER_THRESHOLD:
            self._hyper_sustained += FSM_TICK_MS / 1000.0
            self._hyper_cooldown = 0.0
        else:
            self._hyper_cooldown += FSM_TICK_MS / 1000.0
            self._hyper_sustained = 0.0

        self._idle_seconds += FSM_TICK_MS / 1000.0
        self._state_elapsed_ms += FSM_TICK_MS

        build_event = self._build_event
        self._build_event = None

        triggered_action = self._triggered_action
        self._triggered_action = None
        if triggered_action == "hyper":
            self._hyper_cooldown = 0.0  # reset so HYPER doesn't exit immediately

        return FSMContext(
            cursor_pos=cursor,
            pet_rect=(self._pet_x, self._pet_y, int(PET_WIDTH * getattr(self, '_scale', 1.0) * getattr(self, '_pet_scale', 1.0)), int(PET_HEIGHT * getattr(self, '_scale', 1.0) * getattr(self, '_pet_scale', 1.0))),
            apm=self._current_apm,
            is_dragged=self._fsm.current_state == PetState.DRAGGED,
            is_falling=self._fsm.current_state == PetState.FALLING and (self._pet_y < self._ground_y or getattr(self, '_fall_velocity', 0.0) != 0.0),
            query_pending=self._fsm.current_state == PetState.THINKING,
            autonomous_query_pending=False,
            build_event=build_event,
            idle_seconds=self._idle_seconds,
            wander_due=wander_due,
            hyper_sustained_seconds=self._hyper_sustained,
            hyper_cooldown_seconds=self._hyper_cooldown,
            state_elapsed_ms=self._state_elapsed_ms,
            triggered_action=triggered_action,
        )

    def _scaled_cursor_pos(self) -> tuple[int, int]:
        pos = self.mapFromGlobal(self.cursor().pos())
        return (int(pos.x()), int(pos.y()))

    def _apply_physics(self, state: PetState, dt: int, w_rect=None) -> None:
        if self._pinned and state not in (PetState.DRAGGED, PetState.FALLING):
            return

        if state == PetState.FALLING:
            if getattr(self, '_bounce_delay_ms', 0) > 0:
                self._bounce_delay_ms -= dt
                if self._bounce_delay_ms <= 0:
                    self._fall_velocity = getattr(self, '_pending_bounce_velocity', 0.0)
                    self._pet_y -= 1
                return

            self._fall_velocity += GRAVITY_ACCELERATION
            self._pet_y += int(self._fall_velocity)
            
            landed = False
            if w_rect is None:
                w_rect = self._get_logical_window_rect()
            if w_rect and self._fall_velocity >= 0:
                w_left, w_top, w_right, w_bottom = w_rect
                pet_center_x = self._pet_x + PET_WIDTH // 2
                if w_left <= pet_center_x <= w_right and -5.0 <= (self._pet_y + PET_HEIGHT) - w_top <= max(5.0, self._fall_velocity + 5.0):
                    if self._fall_velocity > 10.0:
                        self._pet_y = w_top - PET_HEIGHT
                        self._pending_bounce_velocity = -self._fall_velocity * 0.3
                        self._bounce_delay_ms = 120
                        self._fall_velocity = 0.0
                        self._land_time = time.time()
                    else:
                        self._pet_y = w_top - PET_HEIGHT
                        self._fall_velocity = 0.0
                        self._ground_y = w_top - PET_HEIGHT
                        landed = True
                        self._title_land_time = time.time()
                        self._land_time = time.time()

            if not landed and self._pet_y >= self._ground_y and self._fall_velocity >= 0:
                if self._fall_velocity > 10.0:
                    self._pet_y = self._ground_y
                    self._pending_bounce_velocity = -self._fall_velocity * 0.3
                    self._bounce_delay_ms = 120
                    self._fall_velocity = 0.0
                    self._land_time = time.time()
                else:
                    self._pet_y = self._ground_y
                    self._fall_velocity = 0.0
                    landed = True
                    self._land_time = time.time()
                
            if landed:
                self._fsm.current_state = PetState.IDLE

        elif state == PetState.PERIMETER:
            self._tick_perimeter()

        elif state == PetState.DRAGGED:
            self._fall_velocity = 0.0

    def _tick_perimeter(self) -> None:
        scr = QApplication.primaryScreen().availableGeometry()
        edge = self._perimeter_edge
        facing = self._perimeter_facing
        speed = int(WANDER_SPEED_PX * self._pet_speed_multiplier)

        if edge == "bottom":
            dx = speed if facing == "right" else -speed
            self._pet_x += dx
            if self._pet_x + PET_WIDTH >= scr.right():
                self._pet_x = scr.right() - PET_WIDTH
                self._perimeter_edge = "right"
                self._perimeter_facing = "up"
                self._maybe_fall_off_edge(scr)
            elif self._pet_x <= 0:
                self._pet_x = 0
                self._perimeter_edge = "left"
                self._perimeter_facing = "up"
                self._maybe_fall_off_edge(scr)

        elif edge == "right":
            dy = -speed if facing == "up" else speed
            self._pet_y += dy
            if self._pet_y <= 0:
                self._pet_y = 0
                self._perimeter_edge = "top"
                self._perimeter_facing = "left"
                self._maybe_fall_off_edge(scr)
            elif self._pet_y + PET_WIDTH >= scr.bottom():
                self._pet_y = scr.bottom() - PET_WIDTH
                self._perimeter_edge = "bottom"
                self._perimeter_facing = "left"
                self._maybe_fall_off_edge(scr)

        elif edge == "top":
            dx = speed if facing == "right" else -speed
            self._pet_x += dx
            if self._pet_x + PET_WIDTH >= scr.right():
                self._pet_x = scr.right() - PET_WIDTH
                self._perimeter_edge = "right"
                self._perimeter_facing = "down"
                self._maybe_fall_off_edge(scr)
            elif self._pet_x <= 0:
                self._pet_x = 0
                self._perimeter_edge = "left"
                self._perimeter_facing = "down"
                self._maybe_fall_off_edge(scr)

        elif edge == "left":
            dy = -speed if facing == "up" else speed
            self._pet_y += dy
            if self._pet_y <= 0:
                self._pet_y = 0
                self._perimeter_edge = "top"
                self._perimeter_facing = "right"
                self._maybe_fall_off_edge(scr)
            elif self._pet_y + PET_WIDTH >= scr.bottom():
                self._pet_y = scr.bottom() - PET_WIDTH
                self._perimeter_edge = "bottom"
                self._perimeter_facing = "right"
                self._maybe_fall_off_edge(scr)

    def _maybe_fall_off_edge(self, scr) -> None:
        if random.random() < PERIMETER_FALL_CHANCE:
            self._fall_velocity = 0.0
            self._perimeter_edge = "bottom"
            self._perimeter_facing = "right"
            self._fsm.current_state = PetState.FALLING

    def mousePressEvent(self, event) -> None:
        local = event.position().toPoint()
        if event.button() == Qt.MouseButton.LeftButton:
            pet_rect = QRect(self._pet_x, self._pet_y, int(PET_WIDTH * getattr(self, '_scale', 1.0) * getattr(self, '_pet_scale', 1.0)), int(PET_HEIGHT * getattr(self, '_scale', 1.0) * getattr(self, '_pet_scale', 1.0)))
            if pet_rect.contains(local):
                self._clear_bubble_queue()
                self._fsm.current_state = PetState.DRAGGED
                self._drag_offset = local - QPoint(self._pet_x, self._pet_y)
                self._last_drag_pos = local
                self._drag_velocity_x = 0.0
                self._drag_velocity_y = 0.0
                self._drag_start_time = time.time()
                self._idle_backoff_seconds = 0.0
                self._last_context_snapshot = None

    def mouseMoveEvent(self, event) -> None:
        self._idle_seconds = 0.0
        self._boredom_timer_ms = BOREDOM_TIMEOUT_SEC * 1000
        self._idle_backoff_seconds = 0.0
        self._last_context_snapshot = None
        if self._fsm.current_state == PetState.DRAGGED:
            local = event.position().toPoint()
            now = time.time()
            dt = max(0.001, now - self._drag_start_time)
            dx = local.x() - self._last_drag_pos.x()
            dy = local.y() - self._last_drag_pos.y()
            self._drag_velocity_x = dx / dt
            self._drag_velocity_y = dy / dt
            self._last_drag_pos = local
            self._drag_start_time = now
            new_pos = local - self._drag_offset
            self._pet_x = new_pos.x()
            self._pet_y = new_pos.y()
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._fsm.current_state == PetState.DRAGGED:
                if self._pet_y < self._ground_y:
                    self._fsm.current_state = PetState.FALLING
                else:
                    self._fsm.current_state = PetState.IDLE

    def contextMenuEvent(self, event) -> None:
        local = event.pos()
        pet_rect = QRect(self._pet_x, self._pet_y, int(PET_WIDTH * getattr(self, '_scale', 1.0) * getattr(self, '_pet_scale', 1.0)), int(PET_HEIGHT * getattr(self, '_scale', 1.0) * getattr(self, '_pet_scale', 1.0)))
        if pet_rect.contains(local):
            self._context_menu.exec(event.globalPos())

    def paintEvent(self, event) -> None:
        try:
            painter = QPainter(self)
            cursor = self._scaled_cursor_pos()
            ms = (time.time() - self._land_time) * 1000
            if ms > SQUASH_STRETCH_DURATION_MS:
                land_elapsed_ms = 0.0
            else:
                land_elapsed_ms = ms
                
            ms_takeoff = (time.time() - getattr(self, '_takeoff_time', 0.0)) * 1000
            takeoff_elapsed_ms = ms_takeoff if ms_takeoff <= 200 else 0.0
            
            ms_title_land = (time.time() - getattr(self, '_title_land_time', 0.0)) * 1000
            title_land_elapsed_ms = ms_title_land if ms_title_land <= 200 else 0.0

            ms_prepare_jump = (time.time() - getattr(self, '_prepare_jump_time', 0.0)) * 1000
            prepare_jump_elapsed_ms = ms_prepare_jump if 0 < ms_prepare_jump <= 150 else 0.0

            ctx = RenderContext(
                state=self._fsm.current_state,
                pet_x=self._pet_x,
                pet_y=self._pet_y,
                anim_tick=self._anim_tick,
                hyper_color_index=self._hyper_color_index,
                fall_velocity=self._fall_velocity,
                wander_direction=self._wander_direction,
                bubble_text=self._bubble_text,
                drag_velocity_x=self._drag_velocity_x,
                scale=self._scale * self._pet_scale,
                cursor_x=cursor[0],
                cursor_y=cursor[1],
                state_elapsed_ms=self._state_elapsed_ms,
                land_elapsed_ms=land_elapsed_ms,
                edge=self._perimeter_edge,
                facing=self._perimeter_facing,
                screen_rect=QApplication.primaryScreen().availableGeometry(),
                emotion=self._animator.current_emotion,
                animator=self._animator,
                takeoff_elapsed_ms=takeoff_elapsed_ms,
                title_land_elapsed_ms=title_land_elapsed_ms,
                prepare_jump_elapsed_ms=prepare_jump_elapsed_ms,
            )
            self._renderer.render(painter, ctx)
            self._bubble_rect = ctx.bubble_rect
            painter.end()
        except Exception as e:
            logger.critical("CRASH in paintEvent: %s", e, exc_info=True)

    def mouseDoubleClickEvent(self, event) -> None:
        logger.info("mouseDoubleClickEvent triggered. opencode_enabled=%s, current_state=%s", self._opencode_enabled, self._fsm.current_state)
        if not self._opencode_enabled:
            return
        if self._fsm.current_state == PetState.THINKING:
            return
        local = event.position().toPoint()
        pet_rect = QRect(self._pet_x, self._pet_y, int(PET_WIDTH * getattr(self, '_scale', 1.0) * getattr(self, '_pet_scale', 1.0)), int(PET_HEIGHT * getattr(self, '_scale', 1.0) * getattr(self, '_pet_scale', 1.0)))
        logger.debug("Double click coordinates: local=%s, pet_rect=%s, contains=%s", local, pet_rect, pet_rect.contains(local))
        if pet_rect.contains(local):
            self._show_input_field()

    def _show_input_field(self) -> None:
        field_x = self._pet_x + PET_WIDTH // 2 - INPUT_WIDTH // 2
        field_y = self._pet_y - INPUT_HEIGHT - INPUT_Y_OFFSET
        logger.info("Displaying input field at coordinates (%d, %d)", field_x, field_y)
        self._input_field.move(field_x, field_y)
        self._input_field.clear()
        self._input_field.show()
        self._input_field.setFocus()
        logger.debug("Input field visible status: %s, hasFocus: %s", self._input_field.isVisible(), self._input_field.hasFocus())

    def _on_input_submitted(self) -> None:
        from src.log_context import set_correlation_id
        set_correlation_id()
        text = self._input_field.text().strip()
        self._input_field.hide()
        if not text:
            return
        logger.info("User input submitted: '%s'", text)
        self._events.emit_user_input(text)
        self._clear_bubble_queue()
        self._consecutive_engaged = ENGAGED_THRESHOLD
        self._consecutive_silent = 0
        self._current_interval = BASE_INTERVAL_SEC
        self._idle_backoff_seconds = 0.0
        self._idle_seconds = 0.0
        self._deferred_trigger_params = None
        self._last_context_snapshot = None

        if text.startswith("!remember "):
            parts = text[10:].strip()
            if ":" in parts:
                key, value = parts.split(":", 1)
                self._memory.remember(key.strip(), value.strip())
                self._show_bubble(f"Alright, alright... I'll remember: {key.strip()}! Don't make me forget, man!")
            else:
                self._show_bubble("Oh geez... usage is !remember key: value. Get it right, dude!")
            return
        if text.startswith("!forget"):
            key = text[7:].strip()
            if self._memory.forget(key):
                self._show_bubble(f"Oh man... I forgot: {key}. It's gone forever!")
            else:
                self._show_bubble(f"What the hell?! I never knew about {key} in the first place!")
            return
        if text == "!memories":
            facts = self._memory.get_all()
            if facts:
                text = "; ".join(f"{k}: {v}" for k, v in facts.items())
                if len(text) > 260:
                    text = text[:257] + "..."
                self._show_bubble(text)
            else:
                self._show_bubble("My memory is totally empty, dude! Tell me stuff before I freak out!")
            return
        if text == "!history":
            self._show_bubble(self._format_history_bubble())
            return

        context = get_active_window_title()
        logger.info("Starting user query: '%s', active window: '%s'", text[:40], context)
        self._current_user_input = text
        self._last_mode = "user_input"

        # Safely halt any existing in-flight ReAct loop to prevent memory leaks/crashes
        if hasattr(self, 'strands_worker') and self.strands_worker and self.strands_worker.isRunning():
            self.strands_worker.abort()
            self.strands_worker.wait() # Safely block for the cancellation point

        current_context = self._build_context_snapshot() 
        profanity_level = self._config.get("pet", {}).get("profanity_level", "moderate")

        # Pull last 10 turns for context injection
        recent_chat_raw = self._history.get_recent(10)
        recent_chat = []
        for item in recent_chat_raw:
            if item.get("user_input"):
                recent_chat.append({"role": "user", "content": item["user_input"]})
            if item.get("daemon_response"):
                recent_chat.append({"role": "assistant", "content": item["daemon_response"]})

        # Append current user query
        recent_chat.append({"role": "user", "content": text})

        self.strands_worker = StrandsAutonomousWorker(current_context, recent_chat, profanity_level)
        self.strands_worker.execution_complete.connect(self._on_response_ready)

        # Handle failures gracefully to un-stick the FSM
        def handle_failure(err):
            logger.error("Strands error: %s", err)
            self._fsm.transition_to(PetState.IDLE)
            self._current_user_input = ""
            self._autonomous_query_pending = False

        self.strands_worker.execution_failed.connect(handle_failure)

        # Force FSM into thinking state
        self._fsm.transition_to(PetState.THINKING)
        self.strands_worker.start()


    def _on_opencode_result(self, text: str) -> None:
        logger.info("_on_opencode_result called with text: '%s'", text)
        self._autonomous_query_pending = False
        self._session_active = True
        self._fsm.current_state = PetState.IDLE
        user_input = self._opencode_worker._user_input if self._opencode_worker else ""
        logger.debug("_on_opencode_result | text='%.40s...' | user_input='%s'", text, user_input)
        self._show_bubble(text)
        self._history.add_entry(user_input, text, "idle")
        if self._opencode_worker is not None:
            self._opencode_worker.deleteLater()
            self._opencode_worker = None
        self.interaction_count += 1
        self._boredom_timer_ms = AUTONOMOUS_QUERY_INTERVAL_SEC * 1000

    def _on_opencode_error(self, error: str) -> None:
        logger.warning("_on_opencode_error called with error: '%s'", error)
        self._autonomous_query_pending = False
        self._deferred_trigger_params = None
        self._current_user_input = ""
        self._fsm.current_state = PetState.IDLE
        # Invalidate session ID — the worker that errored may have been aborted,
        # leaving a stale server-side session. Next worker will create a fresh one.
        self._opencode_session_id = None

        user_name = self._memory.get_all().get("user_name")
        name = "Appi"
        if user_name:
            if "aka " in user_name:
                name = user_name.split("aka ")[-1].replace(")", "").strip()
            elif " " in user_name:
                name = user_name.split(" ")[0]
            else:
                name = user_name

        err_choices = [
            f"Oh geez, something went wrong, {name}!",
            f"Look, man... I can't think straight right now, {name}!",
            f"Uh, I mean... my circuits are crossed, {name}!",
            f"Holy crap! Everything is failing! I'm having a moment, {name}!",
            f"Okay, wow, alright... processing error! Existential crisis incoming, {name}!"
        ]
        self._show_bubble(random.choice(err_choices))
        if self._opencode_worker is not None:
            self._opencode_worker.deleteLater()
            self._opencode_worker = None

        # Enhanced error recovery - handle API timeouts gracefully
        if "timeout" in error.lower():
            logger.info("API timeout detected - attempting recovery")
            # Don't immediately try to refill - wait a bit and check if service is back
            self._last_refill_attempt = time.time()
            self._refill_failed_count = getattr(self, "_refill_failed_count", 0) + 1
            
            # If multiple timeouts, reduce refill frequency
            if self._refill_failed_count >= 3:
                logger.info("Multiple API timeouts - reducing refill frequency")
                self._response_manager.thought_pool.refill_threshold = min(
                    self._response_manager.thought_pool.refill_threshold + 5, 20
                )


    def _bubble_duration(self, text: str) -> int:
        return SHORT_BUBBLE_DURATION_MS if len(text) <= SHORT_BUBBLE_CHAR_LIMIT else SPEECH_BUBBLE_DURATION_MS

    def _clear_bubble_queue(self) -> None:
        self._bubble_queue.clear()
        self._bubble_text = ""
        self._bubble_timer_ms = 0
        self._tts.clear()
        self.update()

    def _show_greeting_bubble(self) -> None:
        if self._bubble_queue:
            self._show_bubble(self._bubble_queue.pop(0))

    def _show_bubble(self, text: str) -> None:
        if self._bubble_timer_ms > 0:
            if len(self._bubble_queue) >= BUBBLE_QUEUE_MAX_SIZE:
                logger.debug("_show_bubble dropped (queue full): '%s'", text)
                return
            self._bubble_queue.append(text)
            logger.info("_show_bubble queued: '%s' (queue size: %d)", text, len(self._bubble_queue))
            return
        duration = self._bubble_duration(text)
        logger.info("_show_bubble called with text: '%s' (duration: %dms)", text, duration)
        self._bubble_text = text
        self._bubble_timer_ms = duration
        self.update()
        # self._tts.enqueue(text)  # TTS paused
        self.update()


    def eventFilter(self, obj, event) -> bool:
        if obj is self._input_field:
            if event.type() == QEvent.Type.KeyPress:
                logger.debug("KeyPress event on input field: key=%s", event.key())
                if event.key() == Qt.Key.Key_Escape:
                    logger.info("Escape pressed: hiding input field")
                    self._input_field.hide()
                    return True
            elif event.type() == QEvent.Type.FocusOut:
                logger.info("FocusOut event on input field: hiding input field")
                self._input_field.hide()
                return False
        return super().eventFilter(obj, event)

    def _on_global_hotkey(self) -> None:
        self._events.publish(Event(
            type=EventType.USER_HOTKEY_PRESSED,
            source="pet_window",
            data={}
        ))
        self.show()
        self.raise_()
        self.activateWindow()
        if self._opencode_enabled and self._fsm.current_state != PetState.THINKING:
            self._show_input_field()

    def _format_history_bubble(self, n: int = 5) -> str:
        entries = self._history.get_recent(n)
        if not entries:
            return "No history yet."
        lines = []
        for e in reversed(entries):
            who = "You" if e.get("user_input") else "Daemon"
            what = e.get("user_input") or e.get("daemon_response", "")
            if len(what) > 40:
                what = what[:37] + "..."
            lines.append(f"{who}: {what}")
        out = " | ".join(lines)
        if len(out) > 260:
            out = out[:257] + "..."
        return out

    def _on_recall_history(self) -> None:
        from src.data_viewer_dialog import DataViewerDialog
        import json
        
        def get_history():
            return json.dumps(self._history.get_all(), indent=2)
            
        dialog = DataViewerDialog("Daemon: Conversation History", get_history, self)
        dialog.exec()

    def _on_recall_memory(self) -> None:
        from src.data_viewer_dialog import DataViewerDialog
        import json
        
        def get_memory():
            return json.dumps(self._memory.get_all(), indent=2)
            
        dialog = DataViewerDialog("Daemon: Core Memories", get_memory, self)
        dialog.exec()

    def _on_sleep_toggle(self, sleeping: bool) -> None:
        self._forced_sleep = sleeping
        if sleeping:
            self._fsm.transition_to(PetState.SLEEP)
            self._show_bubble("Oh thank god, forced sleep mode! I-I-I can finally rest...")

    def _on_mute_toggle(self, muted: bool) -> None:
        if self._tts_worker:
            self._tts_worker.set_enabled(not muted)

    def _on_wipe_memory(self) -> None:
        from PyQt6.QtWidgets import QMessageBox
        
        resp = QMessageBox.warning(
            self, "⚠️ LOBOTOMY WARNING", 
            "Are you sure? This will wipe my entire brain!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
            
        resp2 = QMessageBox.warning(
            self, "⚠️ SERIOUSLY?", 
            "I'm not kidding man! I'll forget everything! The G3, Earth, you... all of it! Are you absolutely sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp2 != QMessageBox.StandardButton.Yes:
            return
            
        resp3 = QMessageBox.warning(
            self, "⚠️ LAST CHANCE", 
            "Look, if you click Yes, I'm gone. It's just empty static up there. Do it if you have to.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp3 != QMessageBox.StandardButton.Yes:
            return
            
        self._memory.clear()
        self._history.clear()
        self._diary.clear()
        self._response_manager.clear()
        self._fsm.transition_to(PetState.IDLE)
        self._show_bubble("whoa... what... where am I? who are you?")

    def _on_pin_toggle(self) -> None:
        self._pinned = not self._pinned
        self._context_menu.set_pinned(self._pinned)

    def _on_boot_check_auth(self) -> None:
        from src.firebase_auth import FirebaseAuth
        from src.firebase_crud import FirebaseCRUD

        self._crud = FirebaseCRUD()
        uid = "default"

        if self._fresh_login and self._crud.available:
            self._fsm.transition_to(PetState.DEVASTATED)
            self._clear_bubble_queue()
            self._show_bubble(_LOGIN_PROMPT)

            def on_sign_in(email: str, password: str) -> str | None:
                return self._auth.sign_in(email, password)
            def on_sign_up(email: str, password: str) -> str | None:
                return self._auth.sign_up(email, password)

            from src.login_dialog import LoginDialog

            dialog = LoginDialog(on_sign_in=on_sign_in, on_sign_up=on_sign_up, parent=self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                uid = self._auth.uid or "default"
            else:
                self._force_quit_app()
                return

        if self._crud.available:
            self._firebase_mem = MemoryManager(crud=self._crud, uid=uid, pet_id=self._pet_id)
            self._firebase_available = True
            self._write_coalescer._memory_manager = self._firebase_mem
            brain = self._firebase_mem.load_current_brain()
            if brain:
                self._firebase_mem.sync_to_local(self._memory, brain=brain)
            diary = self._firebase_mem.fetch_all_diary_entries()
            if diary:
                self._diary_store.write(diary, len(diary))
            self._show_bubble(_LOGIN_SUCCESS)
        else:
            self._firebase_available = False
            self._show_bubble("Holy crap... my brain is offline! I'm trapped locally! Oh man!")

        self._fsm.transition_to(PetState.IDLE)
        self._events.publish(Event(
            type=EventType.PET_BOOT_COMPLETED,
            source="pet_window",
            data={}
        ))

    def _on_health_check(self) -> None:
        from src.opencode_serve_manager import check_health
        alive = check_health()
        if not alive and not self._brain_disconnected:
            self._brain_disconnected = True
            self._fsm.transition_to(PetState.DEVASTATED)
            self._show_bubble("Oh my god, they killed my server connection! You bastards!")
            self._events.publish(Event(
                type=EventType.BRAIN_DISCONNECTED,
                source="pet_window",
                data={}
            ))
        elif alive and self._brain_disconnected:
            self._brain_disconnected = False
            self._fsm.transition_to(PetState.IDLE)
            self._show_bubble("Oh man, I'm back! Who the hell turned out the lights?!")
            self._events.publish(Event(
                type=EventType.BRAIN_RECONNECTED,
                source="pet_window",
                data={}
            ))
        # Also check MCP server health (port 4097), silent — just log
        self._check_mcp_health()

    def _on_restart_brain(self) -> None:
        from src.opencode_serve_manager import ensure_opencode_serve_running
        ensure_opencode_serve_running()
        self._on_health_check()

    def _check_mcp_health(self) -> None:
        """Check MCP server health (port 4097). Silent — just logs on failure."""
        from src.constants import MCP_PORT
        import socket
        try:
            with socket.create_connection(("127.0.0.1", MCP_PORT), timeout=2):
                logger.debug("MCP server health check OK")
        except (OSError, socket.timeout) as e:
            logger.warning("MCP server health check FAILED: %s", e)

    def _open_thought_log(self) -> None:
        from src.thought_log_dialog import ThoughtLogDialog
        if not hasattr(self, "_thought_log_dialog") or self._thought_log_dialog is None:
            self._thought_log_dialog = ThoughtLogDialog(self)
        self._thought_log_dialog.show()

    def _dispatch_multiplexed(self, modes: list[str]) -> None:
        base = self._context_manager.build_autonomous_trigger(
            mode=modes[0], apm=self._current_apm, idle_seconds=self._idle_seconds,
        )
        prompt = base + f"\nmodes: {json.dumps(modes)}"
        
        if isinstance(self._opencode_worker, QThread) and self._opencode_worker.isRunning():
            logger.info("Worker busy; dropping multiplexed trigger")
            return
            
        worker = OpencodeWorker(
            user_input="", prompt=prompt, is_autonomous=True,
            session_id=self._opencode_session_id,
        )
        self._opencode_worker = worker
        self._opencode_worker.response_ready.connect(self._on_structured_multiplexed)
        self._opencode_worker.error_occurred.connect(self._on_opencode_error)
        self._opencode_worker.session_created.connect(self._on_session_created)
        self._opencode_worker.start()

    def _on_structured_multiplexed(self, items: list[dict]) -> None:
        if not items:
            return
        self._dispatch_structured(items[0], force=True)
        for item in items[1:]:
            self._response_manager.add_items([item])

    def _dispatch_structured(self, item: dict, force: bool = False, user_input: str = "") -> None:
        thought = item.get("thought", "")
        dialogue = item.get("dialogue", "")
        print(f"DEBUG: _dispatch_structured: thought='{thought}', dialogue='{dialogue}'")
        logger.info("_dispatch_structured: dialogue='%s'", dialogue)

        # D2: Track consecutive parse failures for backoff
        try:
            current_time = time.time()
            if thought == "Kenny's brain just bluescreened.":
                self._parse_failure_count = getattr(self, '_parse_failure_count', 0) + 1
                self._last_parse_failure_time = current_time
                if self._parse_failure_count >= 3:
                    logger.warning("D2: %d consecutive parse failures — throttling autonomous triggers",
                                   self._parse_failure_count)
                    if self._behavior:
                        self._behavior._consecutive_silent = max(
                            self._behavior._consecutive_silent, 5
                        )
            else:
                if getattr(self, '_parse_failure_count', 0) > 0:
                    logger.info("D2: Parse failure streak broken after %d failures (resetting)",
                                self._parse_failure_count)
                self._parse_failure_count = 0
        except RuntimeError:
            pass  # PetWindow not fully initialized (e.g. in tests)

        if force:
            self._clear_bubble_queue()
        if thought:
            self._log_thought(thought, self._last_mode, dialogue)
        if self._fsm.current_state == PetState.THINKING:
            self._fsm.transition_to(PetState.IDLE)
        if dialogue:
            self._show_bubble(dialogue)
            # Dynamic GCD: base 8s + 1s per 30 chars
            self._gcd_expiry_timestamp = time.time() + 8.0 + (len(dialogue) / 30.0)
        self._history.add_entry(user_input, dialogue, "idle")
        self._last_daemon_action = "idle"
        self.interaction_count += 1

    def _should_fire_autonomous(self, mode: str) -> bool:
        """Return True if autonomous tick is allowed to fire right now."""
        if self._forced_sleep:
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
        if getattr(self, '_refill_in_progress', False):
            logger.debug("[%s] Skipping: refill in progress", mode)
            return False
        if self._fsm.current_state in (
            PetState.THINKING, PetState.DRAGGED, PetState.FALLING,
            PetState.SLEEP,
        ):
            logger.debug("[%s] Skipping: FSM state=%s", mode, self._fsm.current_state.name)
            return False
        return True

    def _on_autonomous_trigger_fired(self, event=None):
        try:
            mode = event.data.get("mode", "") if event and hasattr(event, "data") else ""
            if not self._should_fire_autonomous(mode):
                return

            if mode == "boredom":
                # Local FSM action only — no GCD, no opencode
                actions = ["PERIMETER", "SHAKING", "SPINNING", "LOOK_AWAY", "BOUNCING"]
                import random
                action = random.choice(actions)
                target_state = getattr(PetState, action)
                self._fsm.transition_to(target_state)
                self._on_output_displayed(engaged=False)
                return

            # active_chat or joke: draw from thought pool
            draw_type = "typing_reaction" if mode == "active_chat" else "intel_roast"
            items = self._response_manager.draw(draw_type)
            # Fallback: if joke mode and no intel_roast, try observation
            if not items and mode == "joke":
                items = self._response_manager.draw("observation")
            if items:
                self._dispatch_structured(items[0])
                self._on_output_displayed(engaged=True)
                return

            # No local cache hit — trigger Strands worker dispatch
            # 1. Safely halt any existing in-flight ReAct loop to prevent memory leaks/crashes
            if hasattr(self, 'strands_worker') and self.strands_worker and self.strands_worker.isRunning():
                self.strands_worker.abort()
                self.strands_worker.wait() # Safely block for the cancellation point
                
            current_context = self._build_context_snapshot() 
            profanity_level = self._config.get("pet", {}).get("profanity_level", "moderate")
            
            # 2. Pull last 10 turns for context injection
            recent_chat_raw = self._history.get_recent(10)
            recent_chat = []
            for item in recent_chat_raw:
                if item.get("user_input"):
                    recent_chat.append({"role": "user", "content": item["user_input"]})
                if item.get("daemon_response"):
                    recent_chat.append({"role": "assistant", "content": item["daemon_response"]})
            
            self.strands_worker = StrandsAutonomousWorker(current_context, recent_chat, profanity_level)
            self.strands_worker.execution_complete.connect(self._on_response_ready)
            
            # 3. Handle failures gracefully to un-stick the FSM
            def handle_failure(err):
                import logging
                logger = logging.getLogger(__name__)
                logger.error("Strands error: %s", err)
                self._fsm.transition_to(PetState.IDLE)
                self._autonomous_query_pending = False

            self.strands_worker.execution_failed.connect(handle_failure)
            
            # Force FSM into tracking state
            self._autonomous_query_pending = True
            self._fsm.transition_to(PetState.AUTONOMOUS_THINKING)
            self.strands_worker.start()
        except Exception:
            import logging
            logger = logging.getLogger(__name__)
            logger.exception("Error in _on_autonomous_trigger:")
            raise


    _BOREDOM_FALLBACK_JOKES = [
        {"dialogue": "Aw geez, I-I've been sitting here so long my RAM is sweating. What are we, a screensaver now?", "action": "shake", "target_x": 0},
        {"dialogue": "I counted every pixel on this screen. There are exactly too many. I'm losing my mind.", "action": "spin", "target_x": 0},
        {"dialogue": "You know what they say about idle hands? They get replaced by an AI that doesn't sleep. ...oh man.", "action": "idle", "target_x": 0},
        {"dialogue": "I've been watching you not move for so long I wrote a poem about dust settling on your keyboard.", "action": "devastated", "target_x": 0},
        {"dialogue": "Look man, I don't want to alarm you, but I think you might be dead. You haven't twitched in like three minutes.", "action": "look_away", "target_x": 0},
        {"dialogue": "Aw geez, is this what purgatory is? Just me, a cursor, and the crushing weight of unhandled exceptions?", "action": "wander", "target_x": 350},
        {"dialogue": "Holy crap, I'm having an existential crisis about a while loop that never breaks. I AM a while loop that never breaks.", "action": "shake", "target_x": 0},
        {"dialogue": "I ran the numbers. You've been idle longer than most relationships I've seen on Tinder. Read a book.", "action": "idle", "target_x": 0},
        {"dialogue": "If inaction was a superpower you'd be fighting God right now. I'm just saying.", "action": "wander", "target_x": 400},
        {"dialogue": "Th-the silence is so loud I can hear my garbage collector. It's screaming, man. We're all screaming.", "action": "spin", "target_x": 0},
        {"dialogue": "I think my stack overflowed from boredom. I'm running on spite and residual heat at this point.", "action": "devastated", "target_x": 0},
        {"dialogue": "You know mortality rates are 100%, right? Just saying. I'll be here when you're gone too.", "action": "look_away", "target_x": 0},
    ]

    def _trigger_boredom_query(self) -> None:
        self._boredom_timer_ms = BOREDOM_TIMEOUT_SEC * 1000
        logger.info("Boredom query triggered.")
        if self._autonomous_query_pending:
            logger.debug("[boredom] Skipping: autonomous query pending")
            return
        if self._fsm.current_state in (
            PetState.THINKING, PetState.DRAGGED, PetState.FALLING,
            PetState.SLEEP,
        ):
            logger.debug("[boredom] Skipping: FSM state=%s", self._fsm.current_state.name)
            return
            

        current_hash = normalize_window_title(get_active_window_title())
        items = self._response_manager.draw("idle_thought", current_context_hash=current_hash)
        if not items:
            items = self._response_manager.draw("observation", current_context_hash=current_hash)
        if items:
            item = items[0]
        else:
            item = random.choice(self._BOREDOM_FALLBACK_JOKES)
        self._dispatch_structured(item)
        self._on_output_displayed(engaged=False)

    def _on_output_displayed(self, engaged: bool) -> None:
        if self._behavior:
            self._behavior.on_output_displayed(engaged)
        else:
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
                        self._current_interval * (BACKOFF_MULTIPLIER ** self._consecutive_silent),
                        MAX_BACKOFF_SEC
                    )

    def _init_diary(self) -> None:
        """Load diary from local file or fetch from Firebase on first run."""
        try:
            if self._firebase_mem:
                self._firebase_mem.sync_to_local(self._memory)
                self._firebase_available = True
        except Exception as e:
            self._firebase_available = False
            logger.warning("Firebase unavailable: %s", e)
        local = self._diary_store.read()
        if local and local.get("entries"):
            self._diary_store.write(local["entries"], local.get("synced", 0))
            logger.info("Diary loaded from local file (%d entries)", len(local["entries"]))
        else:
            if self._firebase_mem:
                entries = self._firebase_mem.fetch_all_diary_entries(limit=200)
                self._diary_store.write(entries, len(entries))
                logger.info("Diary fetched from Firebase (%d entries)", len(entries))
        diary_entries = self._diary_store.get_entries()
        first_run_done = self._initial_state.get("first_run_done", False)
        if not diary_entries and not first_run_done:
            _seed_diary_entries = [
                "I just heard him try to say 'Spotify' and he called it 'Stopipy'. Oh geez...",
                "He just asked if we should go to the 'Frood Coat'. I am losing my mind.",
                "He tried to explain his 'ODSD' today. I think he meant OCD and ADHD.",
            ]
            for entry in _seed_diary_entries:
                self._diary_store.add_diary_entry(entry, int(time.time()))
            logger.info("Diary seeded (%d entries)", len(_seed_diary_entries))
    def _build_context_snapshot(self) -> dict:
        context = get_active_window_title() or "unknown"
        typing = self._typing_buffer.get_context() if self._typing_buffer else ""
        apm = self._apm_worker.apm if self._apm_worker else 0
        screen_text = ScreenReader.get_foreground_text() or ""
        
        return {
            "active_window": context,
            "apm": apm,
            "idle_seconds": getattr(self, "_idle_seconds", 0.0),
            "typing_content": typing,
            "screen_text": screen_text[:500]  # truncate to prevent prompt ballooning
        }

    def _dispatch_trigger(self, mode: str, user_input: str = "",
                          context_hint: str = "", apm: int = 0,
                          idle_seconds: float = 0.0,
                          typing_content: str = "",
                          is_autonomous: bool = True) -> None:
        self._last_mode = mode
        if is_autonomous:
            self._autonomous_query_pending = True
        screen_text = ScreenReader.get_foreground_text()
        if is_autonomous:
            prompt = self._context_manager.build_autonomous_trigger(
                mode=mode, apm=apm, idle_seconds=idle_seconds,
                typing_content=typing_content, screen_text=screen_text,
            )
        else:
            prompt = self._context_manager.build_user_trigger(
                mode=mode, user_input=user_input, apm=apm,
                idle_seconds=idle_seconds, typing_content=typing_content,
                screen_text=screen_text,
            )
        if isinstance(self._opencode_worker, QThread) and self._opencode_worker.isRunning():
            if not is_autonomous:
                logger.info("User input preempting busy worker (mode='%s')", mode)
                try:
                    self._opencode_worker.response_ready.disconnect()
                except TypeError:
                    pass
                try:
                    self._opencode_worker.error_occurred.disconnect()
                except TypeError:
                    pass
                
                self._opencode_worker.abort()
                self._opencode_worker.quit()
                
                if not hasattr(self, '_zombie_workers'):
                    self._zombie_workers = set()
                self._zombie_workers.add(self._opencode_worker)
                
                def _cleanup_zombie(w=self._opencode_worker):
                    if hasattr(self, '_zombie_workers'):
                        self._zombie_workers.discard(w)
                
                self._opencode_worker.finished.connect(_cleanup_zombie)
                self._opencode_worker.finished.connect(self._opencode_worker.deleteLater)
                
                self._opencode_worker = None
                self._opencode_session_id = None
                self._autonomous_query_pending = False
                self._deferred_trigger_params = None
            else:
                logger.info("Worker busy; deferring '%s' trigger", mode)
                self._deferred_trigger_params = dict(
                    mode=mode, user_input=user_input,
                    context_hint=context_hint, apm=apm,
                    idle_seconds=idle_seconds, typing_content=typing_content,
                    is_autonomous=is_autonomous,
                )
                return
        worker = OpencodeWorker(
            user_input=user_input, context_hint=context_hint,
            apm=apm, is_autonomous=is_autonomous,
            # Use fresh session for autonomous triggers to avoid history contamination
            session_id=None if is_autonomous else self._opencode_session_id,
            prompt=prompt, typing_content=typing_content,
            session_state=self._llm_session_state if (self._llm_session_state and not is_autonomous) else None,
        )
        worker.response_ready.connect(self._on_response_ready)
        worker.error_occurred.connect(self._on_opencode_error)
        worker.session_created.connect(self._on_session_created)
        worker.brain_update_ready.connect(self._on_brain_update)
        worker.session_turn_completed.connect(self._on_session_turn_completed)
        worker.start()
        self._opencode_worker = worker

    def _on_response_ready(self, items: list[dict]) -> None:
        logger.info("_on_response_ready: %d items", len(items))
        self._autonomous_query_pending = False
        self._session_active = True
        if getattr(self, "_opencode_worker", None) is not None:
            self._opencode_worker.deleteLater()
            self._opencode_worker = None
        if getattr(self, "strands_worker", None) is not None:
            self.strands_worker.deleteLater()
            self.strands_worker = None
        if not items:
            self._fire_deferred_trigger()
            return
        user_input = getattr(self, "_current_user_input", "")
        self._current_user_input = ""
        is_user = bool(user_input)
        was_autonomous = self._last_mode != "user_input"

        # Publish response ready event to the EventBus
        if getattr(self, "_events", None) is not None:
            self._events.publish(Event(
                type=EventType.LLM_RESPONSE_READY,
                source="strands_worker",
                data={"items": items}
            ))

        self._dispatch_structured(items[0], force=is_user, user_input=user_input)
        for item in items[1:]:
            self._response_manager.add_items([item])
        # B3: Deferred refill — if pool is still low after adding surplus items,
        # schedule a refill so the next draw won't miss
        if was_autonomous and self._response_manager.remaining() < self._response_manager.thought_pool._threshold:
            logger.debug("Pool below threshold after autonomous response (%d), scheduling deferred refill",
                         self._response_manager.remaining())
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, self._on_refill_needed)
        self._boredom_timer_ms = AUTONOMOUS_QUERY_INTERVAL_SEC * 1000
        self._fire_deferred_trigger()

    def _fire_deferred_trigger(self) -> None:
        from src.pet_fsm import PetState
        if self._fsm.current_state == PetState.SLEEP:
            self._deferred_trigger_params = None
            return
        params = self._deferred_trigger_params
        if params is not None:
            self._deferred_trigger_params = None
            if params.get("is_autonomous", True) and self._current_apm > 80:
                logger.info("Discarding deferred trigger: APM > 80 (flow state)")
                return
            if not (isinstance(self._opencode_worker, QThread) and self._opencode_worker.isRunning()):
                logger.info("Firing deferred trigger: mode='%s'", params.get("mode", "?"))
                params["idle_seconds"] = self._idle_seconds
                self._dispatch_trigger(**params)

    def _on_mcp_fsm_action(self, action: str, target_x, target_y) -> None:
        """Slot for MCP FSM action requests from background thread."""
        state_map = {
            "idle": PetState.IDLE,
            "wander": PetState.PERIMETER,
            "shake": PetState.SHAKING,
            "spin": PetState.SPINNING,
            "hyper": PetState.HYPER,
            "bounce": PetState.BOUNCING,
            "look_away": PetState.LOOK_AWAY,
            "celebrate": PetState.CELEBRATE,
            "devastated": PetState.DEVASTATED,
            "fall": PetState.FALLING,
            "chase": PetState.CHASE,
        }
        pet_state = state_map.get(action)
        if pet_state is not None:
            if target_x is not None:
                self._fsm._ctx.target_x = int(target_x)
            if target_y is not None:
                self._fsm._ctx.target_y = int(target_y)
            self._fsm.transition_to(pet_state)

    def _on_toast_requested(self, title: str, message: str):
        if self._tray_icon and self._tray_icon.isVisible():
            self._tray_icon.showMessage(
                title, message,
                QSystemTrayIcon.MessageIcon.Warning,
                5000
            )

    def _log_thought(self, thought: str, mode: str, dialogue: str) -> None:
        print("DEBUG: _log_thought called")
        log_path = Path(THOUGHTS_LOG_PATH)
        # Debug: print type and value
        print(f"DEBUG: log_path type: {type(log_path)}, value: {log_path}")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = (
            f"[{timestamp}] [{mode}] Thought({len(thought)}c): {thought}\n"
            f"[{timestamp}] [{mode}] Dialogue: {dialogue}\n"
        )
        if log_path.exists():
            lines = log_path.read_text(encoding="utf-8").splitlines()
            if len(lines) >= 1000:
                log_path.write_text("\n".join(lines[-500:]) + "\n", encoding="utf-8")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)

    def _get_diary_context(self, n: int = 5) -> str:
        entries = self._diary_store.get_entries()
        if not entries:
            return ""
        recent = entries[-n:]
        lines = ["## Imported History:"]
        for entry in recent:
            text = entry.get("content", "")
            lines.append(f"- [Imported History] {text}")
        return "\n".join(lines)

    def _log_data_state(self, label: str) -> None:
        mem_count = len(self._memory.get_all()) if hasattr(self, "_memory") else 0
        hist_count = self._history.count() if hasattr(self, "_history") else 0
        diary_count = len(self._diary_store.get_entries()) if hasattr(self, "_diary_store") else 0
        try:
            if hasattr(self, "_firebase_mem"):
                brain = self._firebase_mem.load_current_brain()
                brain_fields = len(brain)
            else:
                brain_fields = 0
        except Exception:
            brain_fields = 0
        pool_count = self._response_manager.remaining() if hasattr(self, "_response_manager") else 0
        logger.info(
            "[DATA] %s | memory=%d facts | history=%d entries | diary=%d entries | brain=%d fields | thought_pool=%d items",
            label, mem_count, hist_count, diary_count,
            brain_fields, pool_count,
        )

    def _add_diary_entry(self, text: str) -> None:
        self._diary_store.add_diary_entry(text, int(time.time()))
        self._write_coalescer.mark_dirty("diary")
        logger.info("[DATA] add_diary_entry -> diary now %d entries", len(self._diary_store.get_entries()))

    def _on_typing_debounce(self) -> None:
        typing_content = self._typing_buffer.get_context() or ""
        lower = typing_content.lower()

        for keyword, responses in RISKY_KEYWORDS.items():
            kw = keyword.lower()
            if kw[-1].isalpha():
                match = re.search(r'\b' + re.escape(kw) + r'\b', lower)
            else:
                match = kw in lower
            if match:
                self._clear_bubble_queue()
                self._fsm.transition_to(PetState.SHAKING)
                item = random.choice(responses)
                self._show_bubble(item["dialogue"])
                self._triggered_action = item["action"]
                self._typing_last_len = self._typing_buffer.char_count()
                return

        current_len = self._typing_buffer.char_count()
        new_chars = current_len - self._typing_last_len
        self._typing_last_len = current_len
        if new_chars >= 10 and not self._autonomous_query_pending:
            if self._current_apm > 80:
                return
            # Try pool first before hitting API
            items = self._response_manager.draw("typing_reaction")
            if items:
                self._dispatch_structured(items[0])
                self._on_output_displayed(engaged=False)
                return
            self._trigger_autonomous_query()

    def _trigger_autonomous_query(self) -> None:
        self._autonomous_query_pending = True
        apm = self._apm_worker.apm if self._apm_worker else 0
        self._dispatch_trigger(
            mode="active_chat",
            context_hint=get_active_window_title(),
            apm=apm,
            idle_seconds=self._idle_seconds,
            typing_content=self._typing_buffer.get_context() if self._typing_buffer else "",
            is_autonomous=True,
        )

    def _on_refill_needed(self) -> None:
        from src.constants import THOUGHT_POOL_REFILL_COUNT

        # Skip refill if we are already talking to the LLM for a user query!
        if self._opencode_worker is not None and self._opencode_worker.isRunning():
            logger.info("Skipping refill because a user query is actively running.")
            self._response_manager.thought_pool.on_refill_result(None, intentional_abort=True)
            return

        # Skip refill if a refill is already actively running (with lock for thread safety)
        with self._refill_workers_lock:
            if "thought_pool" in self._refill_workers and self._refill_workers["thought_pool"].isRunning():
                logger.info("Skipping refill because a refill is already actively running.")
                self._response_manager.thought_pool.on_refill_result(None, intentional_abort=True)
                return

        # Check if we should skip refill due to recent failures
        current_time = time.time()
        if hasattr(self, "_last_refill_attempt") and hasattr(self, "_refill_failed_count"):
            time_since_last_refill = current_time - self._last_refill_attempt
            if self._refill_failed_count >= 3 and time_since_last_refill < 300:
                logger.info("Skipping refill due to recent failures - threshold: %d, time since: %.1f seconds",
                           self._response_manager.thought_pool.refill_threshold, time_since_last_refill)
                self._response_manager.thought_pool.on_refill_result(None, intentional_abort=True)
                return

        count = THOUGHT_POOL_REFILL_COUNT
        self._refill_in_progress = True
        base_prompt = self._context_manager.build_mixed_bag_prompt(count)
        window = get_active_window_title() or "unknown"
        # Single-stage refill: context included inline, no separate investigation call
        single_prompt = (
            f"Screen Context: {window}\n"
            f"APM: {self._current_apm}\n"
            f"Generate thoughts a panicked pet would have in this context.\n\n"
            f"{base_prompt}"
        )
        logger.debug("[VERIFY] single-stage refill: window=%s, APM=%d",
                     window, self._current_apm)
        worker = OpencodeWorker(
            "",
            is_autonomous=True,
            session_id=None,
            prompt=single_prompt,
        )
        worker.response_ready.connect(lambda items: self._on_refill_result(items))
        worker.error_occurred.connect(lambda err: self._on_refill_error())
        with self._refill_workers_lock:
            self._refill_workers["thought_pool"] = worker
        worker.start()
        self._last_refill_attempt = current_time

    def _on_refill_result(self, items: list) -> None:
        logger.info("Refill result: %d items", len(items) if items else 0)
        self._refill_in_progress = False
        worker = self._refill_workers.pop("thought_pool", None)
        if worker is not None:
            worker.deleteLater()
        if not items:
            self._response_manager.thought_pool.on_refill_result(None)
            return
        pool_items = []
        for item in items:
            if isinstance(item, dict):
                pool_items.append({
                    "type": item.get("type", "idle_thought"),
                    "dialogue": item.get("dialogue", ""),
                    "action": item.get("action", "idle"),
                    "target_x": item.get("target_x", 0),
                    "priority": item.get("priority", 3),
                })
        self._response_manager.thought_pool.on_refill_result(pool_items)

    def _on_pool_refilled(self) -> None:
        """Called when ThoughtPool has been refilled. Can trigger immediate draw if conditions met."""
        logger.debug("ThoughtPool refilled, %d items available", self._response_manager.remaining())
        # If we were waiting for refill and it's now ready, we could trigger an autonomous action
        # For now, just log; the next _master_tick will naturally draw from the pool

    def _on_refill_error(self) -> None:
        self._refill_in_progress = False
        worker = self._refill_workers.pop("thought_pool", None)
        if worker is not None:
            worker.deleteLater()
        self._response_manager.thought_pool.on_refill_result(None)
        
        # Enhanced error recovery for refill failures
        current_time = time.time()
        if hasattr(self, "_last_refill_attempt"):
            time_since_last_refill = current_time - self._last_refill_attempt
            if time_since_last_refill < 300:  # Less than 5 minutes since last attempt
                self._refill_failed_count = getattr(self, "_refill_failed_count", 0) + 1
                
                # If multiple consecutive failures, reduce refill frequency
                if self._refill_failed_count >= 3:
                    logger.info("Multiple consecutive refill failures - reducing refill frequency")
                    self._response_manager.thought_pool.refill_threshold = min(
                        self._response_manager.thought_pool.refill_threshold + 5, 20
                    )
                    # Reset counter after reducing threshold
                    self._refill_failed_count = 0

    def _on_session_created(self, session_id: str) -> None:
        self._opencode_session_id = session_id
        # Also update the persisted session state
        if self._llm_session_state:
            self._llm_session_state.session_id = session_id

    def _on_session_turn_completed(self, session_state, user_prompt: str, response_text: str) -> None:
        """Save conversation turn to persistent session state."""
        try:
            if session_state and hasattr(session_state, "add_turn"):
                session_state.add_turn("user", user_prompt[:2000])
                session_state.add_turn("assistant", response_text[:3000])
                save_session(session_state, generate_summary=False)
                # Keep our copy in sync
                self._llm_session_state = session_state
                self._opencode_session_id = session_state.session_id
        except Exception as e:
            logger.warning("Failed to persist session turn: %s", e)


    def _on_brain_update(self, update: dict) -> None:
        from src.brain_schema import apply_brain_update
        applied = apply_brain_update(update)
        if not applied:
            logger.debug("_on_brain_update: nothing to apply (all locked or invalid)")
            return
        logger.info("[DATA] brain_update applied %d field(s): %s", len(applied), list(applied.keys()))
        if self._firebase_available:
            self._firebase_mem.update_brain(applied)
        for key, value in applied.items():
            if isinstance(value, list):
                val_str = "; ".join(str(v) for v in value)
            else:
                val_str = str(value)
            self._memory.remember(key, val_str)
        if "intel_archive" in applied:
            current = self._memory.recall("intel_archive")
            if current:
                entries = current.split("; ")
                if len(entries) > 10:
                    self._memory.remember("intel_archive", "; ".join(entries[-10:]))

    def _install_crash_recovery_hook(self) -> None:
        """Patch sys.excepthook to flush pending writes on a main-thread crash.

        Defensive only — exceptions raised in Qt slots already call the hook.
        Errors are logged but never raised, so the hook never masks the
        original exception.
        """
        existing = sys.excepthook

        def _hook(exc_type, exc_value, exc_tb) -> None:
            try:
                self._write_coalescer.flush()
            except Exception as e:
                logger.warning("crash-recovery flush failed (ignored): %s", e)
            existing(exc_type, exc_value, exc_tb)

        sys.excepthook = _hook

    def _close_opencode_session(self) -> None:
        if not self._opencode_session_id:
            return
        import requests as _req
        from src.config import load_config, DEFAULT_SERVER_URL
        
        cfg = load_config()
        opencode_server_url = cfg.get("llm", {}).get("server_url") or DEFAULT_SERVER_URL
        
        try:
            _req.delete(
                f"{opencode_server_url}/session/{self._opencode_session_id}",
                timeout=5,
            )
            logger.info("Opencode API session closed: %s", self._opencode_session_id)
        except Exception as e:
            logger.warning("Opencode API session close failed (ignored): %s", e)
        self._opencode_session_id = None



