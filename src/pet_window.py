# src/pet_window.py
from __future__ import annotations
import json
import logging
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import QWidget, QApplication, QLineEdit, QSystemTrayIcon, QMenu, QDialog
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, QEvent
from PyQt6.QtGui import QPainter, QPixmap, QIcon, QColor

from src.constants import (
    FSM_TICK_MS, PET_WIDTH, PET_HEIGHT, GROUND_PADDING_PX,
    GRAVITY_ACCELERATION, WANDER_SPEED_PX, APM_HYPER_THRESHOLD,
    SPEECH_BUBBLE_DURATION_MS,
    INPUT_WIDTH, INPUT_HEIGHT, INPUT_Y_OFFSET,
    BOREDOM_TIMEOUT_SEC,
    AUTONOMOUS_QUERY_INTERVAL_SEC, ACTIVE_CHAT_INTERVAL_SEC, JOKE_INTERVAL_SEC,
    DIARY_PATH, RESPONSE_CACHE_PATH,
    THOUGHTS_LOG_PATH,
    DEBUG,
    SILENCE_THRESHOLD, ENGAGED_THRESHOLD, BASE_INTERVAL_SEC,
    MAX_BACKOFF_SEC, BACKOFF_MULTIPLIER,
    BUBBLE_QUEUE_MAX_SIZE,
    SHORT_BUBBLE_DURATION_MS, SHORT_BUBBLE_CHAR_LIMIT,
    TTS_ENABLED, TTS_BASE_RATE, TTS_VOICE_ID,
    SQUASH_STRETCH_DURATION_MS, PERIMETER_FALL_CHANCE,
    RISKY_KEYWORDS,
)
from src.pet_fsm import PetFSM, PetState, FSMContext
from src.pet_renderer import PetRenderer, RenderContext
from src.tts_worker import TTSWorker
from src.click_through import ClickThroughManager
from src.apm_worker import APMWorker
from src.typing_buffer import TypingBuffer
from src.context_menu import PetContextMenu
from src.opencode_worker import OpencodeWorker
from src.active_window import get_active_window_title
from src.screen_reader import ScreenReader
from src.memory import Memory
from src.history import History
from src.memory_manager import MemoryManager
from src.write_coalescer import WriteCoalescer
from src.diary_store import DiaryStore
from src.context_manager import ContextManager
from src.response_manager import AutonomousResponseManager


from src.fsm_bridge import FSMActionBridge
from src.mcp_server import MCPServer

logger = logging.getLogger(__name__)

_LOGIN_PROMPT = "Intruder! I-I don't recognize your clearance, man! Identify yourself!"
_LOGIN_SUCCESS = "Oh, it's just you. You coulda said so, jeez."


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
        **kwargs
    ) -> None:
        if "agy_enabled" in kwargs:
            opencode_enabled = kwargs.pop("agy_enabled")
        super().__init__()
        self._opencode_enabled = opencode_enabled
        initial_state = initial_state or {}
        self._initial_state = initial_state
        self._fresh_login = fresh_login
        self.mood_score = initial_state.get("mood", 0)
        self.interaction_count = initial_state.get("interactions", 0)
        self._skill_ready = skill_ready
        self._force_quit = False
        self._click_through: ClickThroughManager | None = None
        self._setup_window()

        from src.config import load_config
        self._config = load_config()
        self._pet_scale = self._config.get("pet_scale", 1.0)
        self._pet_opacity = self._config.get("pet_opacity", 0.85)
        self._pet_speed_multiplier = self._config.get("pet_speed", 1.0)
        self._chattiness = self._config.get("chattiness", 1.0)

        self._scale = QApplication.primaryScreen().devicePixelRatio()
        self._ground_y = self._compute_ground_y()

        self._pet_x = 100
        self._pet_y = self._ground_y

        self._fall_velocity = 0.0
        self._land_time: float = 0.0
        self._drag_offset = QPoint(0, 0)
        self._drag_velocity_x = 0.0
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
        self._hyper_flash_timer = QTimer()
        self._hyper_flash_timer.setInterval(125)
        self._hyper_flash_timer.timeout.connect(self._cycle_hyper_color)
        self._hyper_flash_timer.start()

        self._last_mode = ""
        self._idle_seconds = 0.0
        self._state_elapsed_ms = 0
        self._build_event: str | None = None

        self._fsm = PetFSM()
        self._renderer = PetRenderer()

        self._pinned = False

        self._context_menu = PetContextMenu(self)
        self._context_menu.signals.quit_requested.connect(self._force_quit_app)
        self._context_menu.signals.recall_memory.connect(self._on_recall_memory)
        self._context_menu.signals.recall_history.connect(self._on_recall_history)
        self._context_menu.signals.pin_toggle.connect(self._on_pin_toggle)

        self._apm_worker = APMWorker()
        self._apm_worker.apm_updated.connect(self._on_apm_updated)
        self._apm_worker.hotkey_triggered.connect(self._on_global_hotkey)
        self._apm_worker.start()

        self._typing_buffer = TypingBuffer()
        self._typing_buffer.start()

        self._tts = TTSWorker(
            rate=self._config.get("tts_rate", TTS_BASE_RATE),
            volume=self._config.get("tts_volume", 1.0),
            voice_id=self._config.get("tts_voice_id") or TTS_VOICE_ID,
        )
        self._tts.start()
        if not self._config.get("tts_enabled", True):
            self._tts.set_enabled(False)

        # MCP FSM bridge — thread-safe signal relay between MCP server and Qt main thread
        self._fsm_bridge = FSMActionBridge()
        self._fsm_bridge.request.connect(self._on_mcp_fsm_action)
        self._fsm_bridge.toast_request.connect(self._on_toast_requested)
        self._mcp_server = MCPServer(self._fsm_bridge)

        self._bubble_queue: list[str] = []

        self._memory = Memory(path=memory_path)
        self._history = History(path=history_path)
        self._crud = None
        self._firebase_available = False
        self._firebase_mem = None
        self._diary_entries: list[str] = []
        self._diary_synced: int = 0
        self._diary_path = DIARY_PATH

        self._diary_store = DiaryStore(self._diary_path)
        self._write_coalescer = WriteCoalescer(
            memory=self._memory, history=self._history,
            memory_manager=self._firebase_mem,
            diary_entries_ref=self._diary_entries, diary_store=self._diary_store,
        )
        self._memory._coalescer = self._write_coalescer
        self._history._coalescer = self._write_coalescer
        self._init_diary()
        self._log_data_state("Startup")

        self._context_manager = ContextManager(
            memory=self._memory, history=self._history,
            diary_entries_ref=self._diary_entries,
        )
        self._response_manager = AutonomousResponseManager(
            cache_path=RESPONSE_CACHE_PATH,
            write_coalescer=self._write_coalescer,
        )
        for pool in self._response_manager._pools.values():
            pool.refill_needed.connect(self._on_refill_needed)
        self._response_manager.start()
        self._log_data_state("Startup+Cache")

        self._typing_last_len = 0
        self._typing_debounce_timer = QTimer()
        self._typing_debounce_timer.setSingleShot(True)
        self._typing_debounce_timer.setInterval(2000)
        self._typing_debounce_timer.timeout.connect(self._on_typing_debounce)
        self._typing_buffer.text_updated.connect(self._typing_debounce_timer.start)

        self._write_coalescer.start()

        self._install_crash_recovery_hook()

        if not (initial_state or {}).get("first_run_done", False):
            self._bubble_queue = [
                "I'm Daemon.",
                "Double-click me to ask opencode anything.",
                "Right-click for options.",
            ]
            QTimer.singleShot(1500, lambda: self._bubble_queue and self._show_bubble(self._bubble_queue.pop(0)))


        self._fsm_timer = QTimer()
        self._fsm_timer.setInterval(FSM_TICK_MS)
        self._fsm_timer.timeout.connect(self._tick)
        self._fsm_timer.start()

        from src.constants import BEHAVIOR_TICK_MS
        self._behavior_timer = QTimer()
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

        self._deferred_trigger_params: dict | None = None

        # Exponential backoff for idle/boredom
        self._last_context_snapshot = None
        self._idle_backoff_seconds = 0.0
        self._base_boredom_interval = BOREDOM_TIMEOUT_SEC
        self._max_idle_backoff = 300
        self._last_boredom_fsm_time = 0.0

        self._consecutive_silent = 0
        self._consecutive_engaged = 0
        self._current_interval = BASE_INTERVAL_SEC

        self._last_active_window = ""
        self._last_typing_snapshot = ""
        self._boredom_tick_count = 0
        self._gcd_expiry_timestamp = 0.0
        self._chat_timer_sec = 0
        self._joke_timer_sec = 0
        self._chattiness = 1.0

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
            self._show_bubble("dae: memory active.")

        QTimer.singleShot(500, self._on_boot_check_auth)
        self._mcp_server.start()

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
        rect = QRect(self._pet_x, self._pet_y, PET_WIDTH, PET_HEIGHT)
        if self._bubble_text:
            rect = rect.united(self._bubble_rect)
        if self._input_field.isVisible():
            rect = rect.united(self._input_field.geometry())
        return rect

    def _compute_ground_y(self) -> int:
        screen = QApplication.primaryScreen().availableGeometry()
        return screen.bottom() - PET_HEIGHT - GROUND_PADDING_PX

    def _cycle_hyper_color(self) -> None:
        self._hyper_color_index = (self._hyper_color_index + 1) % 4

    def _on_apm_updated(self, apm: int) -> None:
        self._current_apm = apm
        if apm > 0:
            self._boredom_timer_ms = BOREDOM_TIMEOUT_SEC * 1000
            self._idle_backoff_seconds = 0.0
            self._last_context_snapshot = None
            self._last_boredom_fsm_time = time.time()

    def _calculate_joke_modifier(self) -> float:
        """Inverse APM scaling: low APM = frequent jokes, high APM = rare jokes."""
        apm = self._current_apm
        if apm < 10:
            return 0.5   # 30s base -> rapid fire
        elif apm < 20:
            return 1.0   # 60s base
        elif apm < 40:
            return 2.0   # 120s base
        else:
            return 3.0   # 180s base — rare

    def _has_significant_delta(self) -> bool:
        """Detect context switches: window change or typing burst."""
        current_window = get_active_window_title()
        current_typing = self._typing_buffer.get_context() if self._typing_buffer else ""

        window_changed = current_window != self._last_active_window and current_window != ""
        typing_burst = len(current_typing) - len(self._last_typing_snapshot) > 20

        self._last_active_window = current_window
        self._last_typing_snapshot = current_typing

        return window_changed or typing_burst

    def _get_context_signature(self) -> tuple:
        """Generate a hashable signature of the current context for stability detection."""
        window = get_active_window_title() or ""
        typing_buffer = getattr(self, '_typing_buffer', None)
        typing = typing_buffer.get_context() if typing_buffer else ""
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

    def _trigger_chat(self) -> None:
        """Handle active chat: instant local reaction + background API call."""
        self._chat_timer_sec = 0  # Reset timer

        # Zero-latency local reaction
        local = self._response_manager.draw("typing_reactions", 1)
        if local:
            self._dispatch_structured(local[0])

        # Background API call
        if not self._autonomous_query_pending and self._opencode_enabled:
            self._dispatch_trigger(
                mode="active_chat",
                context_hint=get_active_window_title(),
                apm=self._current_apm,
                idle_seconds=self._idle_seconds,
                typing_content=self._typing_buffer.get_context() if self._typing_buffer else "",
                is_autonomous=True,
            )

    def _trigger_joke(self) -> None:
        """Handle joke trigger: background API call."""
        self._joke_timer_sec = 0  # Reset timer

        if not self._autonomous_query_pending and self._opencode_enabled:
            self._dispatch_trigger(
                mode="joke",
                context_hint=get_active_window_title(),
                apm=self._current_apm,
                idle_seconds=self._idle_seconds,
                is_autonomous=True,
            )

    def _trigger_boredom_fsm(self) -> None:
        """Handle boredom: local FSM actions only, API every 3rd/4th tick."""
        from src.pet_fsm import PetState

        # Local FSM actions (silent, no GCD)
        actions = ["PERIMETER", "SHAKING", "SPINNING", "LOOK_AWAY", "BOUNCING"]
        action = random.choice(actions)
        target_state = getattr(PetState, action)
        self._fsm.transition_to(target_state)

        # API call every 3rd-4th boredom tick
        self._boredom_tick_count = (self._boredom_tick_count + 1) % 4
        if self._boredom_tick_count == 0 and self._opencode_enabled:
            if not self._autonomous_query_pending:
                self._dispatch_trigger(
                    mode="boredom",
                    context_hint=get_active_window_title(),
                    apm=self._current_apm,
                    idle_seconds=self._idle_seconds,
                    is_autonomous=True,
                )

    def _master_tick(self) -> None:
        """Centralized behavioral tick — runs every BEHAVIOR_TICK_MS."""
        try:
            # 1. Accumulate time
            self._chat_timer_sec += 1
            self._joke_timer_sec += 1

            # 2. GATEKEEPER: Dynamic Global Cooldown
            if time.time() < self._gcd_expiry_timestamp:
                return  # Speech in progress — lockdown

            # 3. Dynamic Thresholds (Chattiness scaling)
            chat_threshold = ACTIVE_CHAT_INTERVAL_SEC / self._chattiness
            joke_mod = self._calculate_joke_modifier()
            joke_threshold = (JOKE_INTERVAL_SEC * joke_mod) / self._chattiness

            # 4. BEHAVIORAL PRIORITY TREE
            # P1: Flow State (APM > 80) — TOTAL SILENCE
            if self._current_apm > 80:
                return

            # P2: Active Chat Delta
            if self._chat_timer_sec >= chat_threshold and self._has_significant_delta():
                self._trigger_chat()
                return

            # P3: Joke (APM < 20)
            if self._joke_timer_sec >= joke_threshold and self._current_apm < 20:
                self._trigger_joke()
                return

            # P4: Boredom (APM == 0, Idle >= 60s) — WITH EXPONENTIAL BACKOFF
            if self._idle_seconds >= 60 and self._current_apm == 0:
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

                    # 3. ONLY increase backoff AFTER we've fired
                    if self._idle_backoff_seconds == 0:
                        self._idle_backoff_seconds = self._base_boredom_interval
                    else:
                        self._idle_backoff_seconds = min(self._idle_backoff_seconds * 2.0, self._max_idle_backoff)
                return

        except Exception as e:
            logger.critical("CRASH in _master_tick: %s", e, exc_info=True)
            raise

    def _force_quit_app(self) -> None:
        logger.info("_force_quit_app called - shutting down")
        self._force_quit = True
        self._mcp_server.stop()
        self._fsm_timer.stop()
        self._behavior_timer.stop()
        self._log_data_state("Shutdown")
        self._response_manager.stop()
        try:
            self._write_coalescer.stop()
            self._write_coalescer.flush()
        except Exception as e:
            logger.warning("WriteCoalescer flush failed: %s", e)
        for pool_type, worker in list(self._refill_workers.items()):
            if worker.isRunning():
                worker.quit()
                worker.wait(15000)
        self._refill_workers.clear()
        if self._opencode_worker and self._opencode_worker.isRunning():
            self._opencode_worker.quit()
            self._opencode_worker.wait(15000)
        self._deferred_trigger_params = None
        self._close_opencode_session()
        self._typing_buffer.stop()
        self._tts.stop()
        self._apm_worker.stop()
        self._tray_icon.hide()
        # Cleanup UIA COM
        try:
            from src.screen_reader import _cleanup_uia
            _cleanup_uia()
        except Exception:
            pass
        QApplication.quit()

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

        dialog = SettingsDialog(
            pet_scale=self._pet_scale,
            pet_opacity=self._pet_opacity,
            pet_speed=self._pet_speed_multiplier,
            tts_enabled=self._saved_tts,
            tts_rate=self._saved_tts_rate,
            tts_volume=self._saved_tts_volume,
            tts_voice_id=self._saved_tts_voice_id,
            chattiness=self._chattiness,
            parent=self,
        )
        dialog.value_changed.connect(lambda: self._apply_settings(dialog.get_values()))
        dialog.accepted.connect(lambda: self._save_settings(dialog.get_values()))
        dialog.rejected.connect(self._restore_settings)
        dialog.show()

    def _apply_settings(self, values: dict) -> None:
        self._pet_scale = values["pet_scale"]
        self._ground_y = self._compute_ground_y()
        self._pet_opacity = values["pet_opacity"]
        self._pet_speed_multiplier = values["pet_speed"]
        self.setFixedSize(
            int(PET_WIDTH * self._pet_scale),
            int(PET_HEIGHT * self._pet_scale),
        )
        self.setWindowOpacity(self._pet_opacity)
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
        from src.config import save_config
        save_config(values)

    def _restore_settings(self) -> None:
        self._apply_settings({
            "pet_scale": self._saved_scale,
            "pet_opacity": self._saved_opacity,
            "pet_speed": self._saved_speed,
            "tts_enabled": self._saved_tts,
            "tts_rate": self._saved_tts_rate,
            "tts_volume": self._saved_tts_volume,
            "tts_voice_id": self._saved_tts_voice_id,
            "chattiness": self._saved_chattiness,
        })

    def _tick(self) -> None:
        try:
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
                self._boredom_timer_ms -= FSM_TICK_MS
                if self._boredom_timer_ms <= 0:
                    self._trigger_boredom_query()

            old_state = self._fsm.current_state
            ctx = self._build_fsm_context()
            new_state = self._fsm.update(FSM_TICK_MS, ctx)
            if new_state != old_state:
                logger.debug(f"FSM state transition: {old_state.name} -> {new_state.name}")
                self._state_elapsed_ms = 0
                # Handle SLEEP state entry
                if new_state == PetState.SLEEP and old_state != PetState.SLEEP:
                    self._autonomous_query_pending = False
                    self._deferred_trigger_params = None
                    self._last_boredom_fsm_time = time.time()
                    # Gracefully disconnect refill workers (NO wait())
                    for worker in self._refill_workers.values():
                        if worker.isRunning():
                            try:
                                worker.response_ready.disconnect()
                            except TypeError:
                                pass
                            worker.quit()
                    self._refill_workers.clear()
                # Handle SLEEP state exit
                if old_state == PetState.SLEEP and new_state != PetState.SLEEP:
                    self._idle_backoff_seconds = 0.0
                    self._last_context_snapshot = None
                    self._last_boredom_fsm_time = time.time()
                    self._boredom_timer_ms = BOREDOM_TIMEOUT_SEC * 1000
            self._apply_physics(new_state, FSM_TICK_MS)
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
            pet_rect=(self._pet_x, self._pet_y, PET_WIDTH, PET_HEIGHT),
            apm=self._current_apm,
            is_dragged=self._fsm.current_state == PetState.DRAGGED,
            is_falling=self._fsm.current_state == PetState.FALLING and self._pet_y < self._ground_y,
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

    def _apply_physics(self, state: PetState, dt: int) -> None:
        if self._pinned and state not in (PetState.DRAGGED, PetState.FALLING):
            return

        if state == PetState.FALLING:
            self._fall_velocity += GRAVITY_ACCELERATION
            self._pet_y += int(self._fall_velocity)
            if self._pet_y >= self._ground_y:
                self._pet_y = self._ground_y
                self._fall_velocity = 0.0
                self._land_time = time.time()
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
            pet_rect = QRect(self._pet_x, self._pet_y, PET_WIDTH, PET_HEIGHT)
            if pet_rect.contains(local):
                self._clear_bubble_queue()
                self._fsm.current_state = PetState.DRAGGED
                self._drag_offset = local - QPoint(self._pet_x, self._pet_y)
                self._last_drag_pos = local
                self._idle_backoff_seconds = 0.0
                self._last_context_snapshot = None

    def mouseMoveEvent(self, event) -> None:
        self._idle_seconds = 0.0
        self._boredom_timer_ms = BOREDOM_TIMEOUT_SEC * 1000
        self._idle_backoff_seconds = 0.0
        self._last_context_snapshot = None
        if self._fsm.current_state == PetState.DRAGGED:
            local = event.position().toPoint()
            self._drag_velocity_x = local.x() - self._last_drag_pos.x()
            self._last_drag_pos = local
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
        pet_rect = QRect(self._pet_x, self._pet_y, PET_WIDTH, PET_HEIGHT)
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
                scale=self._scale,
                cursor_x=cursor[0],
                cursor_y=cursor[1],
                state_elapsed_ms=self._state_elapsed_ms,
                land_elapsed_ms=land_elapsed_ms,
                edge=self._perimeter_edge,
                facing=self._perimeter_facing,
                screen_rect=QApplication.primaryScreen().availableGeometry(),
            )
            self._renderer.render(painter, ctx)
            self._bubble_rect = ctx.bubble_rect
            painter.end()
        except Exception as e:
            logger.critical("CRASH in paintEvent: %s", e, exc_info=True)

    def mouseDoubleClickEvent(self, event) -> None:
        if not self._opencode_enabled:
            return
        if self._fsm.current_state == PetState.THINKING:
            return
        local = event.position().toPoint()
        pet_rect = QRect(self._pet_x, self._pet_y, PET_WIDTH, PET_HEIGHT)
        if pet_rect.contains(local):
            self._show_input_field()

    def _show_input_field(self) -> None:
        field_x = self._pet_x + PET_WIDTH // 2 - INPUT_WIDTH // 2
        field_y = self._pet_y - INPUT_HEIGHT - INPUT_Y_OFFSET
        self._input_field.move(field_x, field_y)
        self._input_field.clear()
        self._input_field.show()
        self._input_field.setFocus()

    def _on_input_submitted(self) -> None:
        text = self._input_field.text().strip()
        self._input_field.hide()
        if not text:
            return
        logger.info("User input submitted: '%s'", text)
        self._clear_bubble_queue()
        self._consecutive_engaged = ENGAGED_THRESHOLD
        self._consecutive_silent = 0
        self._current_interval = BASE_INTERVAL_SEC
        self._idle_backoff_seconds = 0.0
        self._last_context_snapshot = None

        if text.startswith("!remember "):
            parts = text[10:].strip()
            if ":" in parts:
                key, value = parts.split(":", 1)
                self._memory.remember(key.strip(), value.strip())
                self._show_bubble(f"OK, I'll remember: {key.strip()}")
            else:
                self._show_bubble("usage: !remember key: value")
            return
        if text.startswith("!forget "):
            key = text[8:].strip()
            if self._memory.forget(key):
                self._show_bubble(f"Forgot: {key}")
            else:
                self._show_bubble(f"Never knew about: {key}")
            return
        if text == "!memories":
            facts = self._memory.get_all()
            if facts:
                text = "; ".join(f"{k}: {v}" for k, v in facts.items())
                if len(text) > 260:
                    text = text[:257] + "..."
                self._show_bubble(text)
            else:
                self._show_bubble("My memory is empty. Tell me things!")
            return
        if text == "!history":
            self._show_bubble(self._format_history_bubble())
            return

        context = get_active_window_title()
        typing = self._typing_buffer.get_context() if self._typing_buffer else ""
        apm = self._apm_worker.apm if self._apm_worker else 0
        logger.info("Starting user query: '%s', active window: '%s'", text[:40], context)
        self._fsm.current_state = PetState.THINKING
        self._dispatch_trigger(
            mode="user_input",
            user_input=text,
            context_hint=context,
            apm=apm,
            idle_seconds=0.0,
            typing_content=typing,
            is_autonomous=False,
        )


    def _on_opencode_result(self, text: str) -> None:
        logger.info("_on_opencode_result called with text: '%s'", text)
        self._autonomous_query_pending = False
        self._session_active = True
        self._fsm.current_state = PetState.IDLE
        user_input = self._opencode_worker._user_input if self._opencode_worker else ""
        logger.debug(f"_on_opencode_result | text='{text[:40]}...' | user_input='{user_input}'")
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
        self._fsm.current_state = PetState.IDLE

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


    def _bubble_duration(self, text: str) -> int:
        return SHORT_BUBBLE_DURATION_MS if len(text) <= SHORT_BUBBLE_CHAR_LIMIT else SPEECH_BUBBLE_DURATION_MS

    def _clear_bubble_queue(self) -> None:
        self._bubble_queue.clear()
        self._bubble_text = ""
        self._bubble_timer_ms = 0
        self._tts.clear()
        self.update()

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
        if obj is self._input_field and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self._input_field.hide()
                return True
        if obj is self._input_field and event.type() == QEvent.Type.FocusOut:
            self._input_field.hide()
            return False
        return super().eventFilter(obj, event)

    def _on_global_hotkey(self) -> None:
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
        self._show_bubble(self._format_history_bubble())

    def _on_recall_memory(self) -> None:
        facts = self._memory.get_all()
        if not facts:
            self._show_bubble("I don't remember anything yet. Tell me stuff with !remember key: value")
            return
        lines = [f"{k}: {v}" for k, v in facts.items()]
        text = " | ".join(lines)
        if len(text) > 260:
            text = text[:257] + "..."
        self._show_bubble(text)

    def _on_pin_toggle(self) -> None:
        self._pinned = not self._pinned
        self._context_menu.set_pinned(self._pinned)

    def _on_boot_check_auth(self) -> None:
        from src.firebase_auth import FirebaseAuth
        from src.firebase_crud import FirebaseCRUD
        from src.memory_manager import MemoryManager

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

        if self._crud.available:
            self._firebase_mem = MemoryManager(crud=self._crud, uid=uid)
            self._firebase_available = True
            self._write_coalescer._memory_manager = self._firebase_mem
            brain = self._firebase_mem.load_current_brain()
            if brain:
                self._firebase_mem.sync_to_local(self._memory)
            diary = self._firebase_mem.fetch_all_diary_entries()
            if diary:
                self._diary_entries = diary
                self._diary_store.write(diary, len(diary))
            self._show_bubble(_LOGIN_SUCCESS)
        else:
            self._firebase_available = False
            self._show_bubble("Brain offline. Running local.")

        self._fsm.transition_to(PetState.IDLE)

    def _dispatch_multiplexed(self, modes: list[str]) -> None:
        base = self._context_manager.build_autonomous_trigger(
            mode=modes[0], apm=self._current_apm, idle_seconds=self._idle_seconds,
        )
        prompt = base + f"\nmodes: {json.dumps(modes)}"
        worker = OpencodeWorker(
            user_input="", prompt=prompt, is_autonomous=True,
            session_id=self._opencode_session_id,
        )
        worker.response_ready.connect(self._on_structured_multiplexed)
        worker.error_occurred.connect(self._on_opencode_error)
        worker.start()

    def _on_structured_multiplexed(self, items: list[dict]) -> None:
        if not items:
            return
        self._dispatch_structured(items[0], force=True)
        for item in items[1:]:
            pool_type = item.get("pool_type", "jokes_blackmail")
            self._response_manager.add_items(pool_type, [item])

    def _maybe_dispatch_bickering(self) -> bool:
        if random.random() < 0.10:
            self._dispatch_multiplexed(["kenny_roast", "morty_panic"])
            return True
        return False

    def _dispatch_structured(self, item: dict, force: bool = False) -> None:
        thought = item.get("thought", "")
        dialogue = item.get("dialogue", "")
        logger.info("_dispatch_structured: dialogue='%s'", dialogue)
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
        self._history.add_entry("", dialogue, "idle")
        self._last_daemon_action = "idle"
        self.interaction_count += 1

    def _should_fire_autonomous(self, mode: str) -> bool:
        """Return True if autonomous tick is allowed to fire right now."""
        pool_map = {
            "boredom": "jokes_blackmail",
        }
        pool_type = pool_map.get(mode)
        if pool_type:
            if self._response_manager.remaining(pool_type) == 0:
                logger.debug(f"[{mode}] Skipping: {pool_type} pool empty")
                return False
        else:
            if not self._opencode_enabled:
                logger.debug(f"[{mode}] Skipping: opencode disabled")
                return False
        if self._autonomous_query_pending:
            logger.debug(f"[{mode}] Skipping: autonomous query pending")
            return False
        if self._fsm.current_state in (
            PetState.THINKING, PetState.DRAGGED, PetState.FALLING,
            PetState.SLEEP,
        ):
            logger.debug(f"[{mode}] Skipping: FSM state={self._fsm.current_state.name}")
            return False
        return True

    _BOREDOM_FALLBACK_JOKES = [
        {"dialogue": "Holy crap, you're still alive? I was drafting your eulogy in Python comments.", "action": "idle", "target_x": 0},
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
        if self._maybe_dispatch_bickering():
            return
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
        items = self._response_manager.draw("jokes_blackmail", 1)
        if items:
            item = items[0]
        else:
            item = random.choice(self._BOREDOM_FALLBACK_JOKES)
        self._dispatch_structured(item)
        self._on_output_displayed(engaged=False)

    def _on_output_displayed(self, engaged: bool) -> None:
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
            self._diary_entries = local["entries"]
            self._diary_synced = local.get("synced", 0)
            logger.info("Diary loaded from local file (%d entries)", len(self._diary_entries))
        else:
            if self._firebase_mem:
                entries = self._firebase_mem.fetch_all_diary_entries(limit=200)
                self._diary_entries = entries
                self._diary_synced = len(entries)
                self._diary_store.write(entries, len(entries))
                logger.info("Diary fetched from Firebase (%d entries)", len(entries))
        first_run_done = self._initial_state.get("first_run_done", False)
        if not self._diary_entries and not first_run_done:
            _seed_diary_entries = [
                "I just heard him try to say 'Spotify' and he called it 'Stopipy'. Oh geez...",
                "He just asked if we should go to the 'Frood Coat'. I am losing my mind.",
                "He tried to explain his 'ODSD' today. I think he meant OCD and ADHD.",
            ]
            for entry in _seed_diary_entries:
                self._diary_entries.append(entry)
            self._diary_synced = 0
            self._diary_store.write(self._diary_entries, 0)
            logger.info("Diary seeded (%d entries)", len(_seed_diary_entries))

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
        if self._opencode_worker and self._opencode_worker.isRunning():
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
            session_id=self._opencode_session_id,
            prompt=prompt, typing_content=typing_content,
        )
        worker.response_ready.connect(self._on_response_ready)
        worker.error_occurred.connect(self._on_opencode_error)
        worker.session_created.connect(self._on_session_created)
        worker.brain_update_ready.connect(self._on_brain_update)
        worker.pool_items_ready.connect(self._on_pool_items_ready)
        worker.start()
        self._opencode_worker = worker

    def _on_response_ready(self, items: list[dict]) -> None:
        logger.info("_on_response_ready: %d items", len(items))
        self._autonomous_query_pending = False
        self._session_active = True
        if self._opencode_worker is not None:
            self._opencode_worker.deleteLater()
            self._opencode_worker = None
        if not items:
            self._fire_deferred_trigger()
            return
        self._dispatch_structured(items[0])
        for item in items[1:]:
            pool_type = item.get("pool_type", "jokes_blackmail")
            self._response_manager.add_items(pool_type, [item])
        self._boredom_timer_ms = AUTONOMOUS_QUERY_INTERVAL_SEC * 1000
        self._fire_deferred_trigger()

    def _fire_deferred_trigger(self) -> None:
        params = self._deferred_trigger_params
        if params is not None:
            self._deferred_trigger_params = None
            if not (self._opencode_worker and self._opencode_worker.isRunning()):
                logger.info("Firing deferred trigger: mode='%s'", params.get("mode", "?"))
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
            self._fsm.transition_to(
                pet_state,
                target_x=int(target_x) if target_x is not None else None,
                target_y=int(target_y) if target_y is not None else None,
            )

    def _on_toast_requested(self, title: str, message: str):
        if self._tray_icon and self._tray_icon.isVisible():
            self._tray_icon.showMessage(
                title, message,
                QSystemTrayIcon.MessageIcon.Warning,
                5000
            )

    def _log_thought(self, thought: str, mode: str, dialogue: str) -> None:
        if not DEBUG:
            return
        log_path = THOUGHTS_LOG_PATH
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = (
            f"[{timestamp}] [{mode}] Thought({len(thought)}c): {thought}\n"
            f"[{timestamp}] [{mode}] Dialogue: {dialogue}\n"
        )
        if log_path.exists():
            lines = Path(log_path).read_text(encoding="utf-8").splitlines()
            if len(lines) >= 1000:
                Path(log_path).write_text("\n".join(lines[-500:]) + "\n", encoding="utf-8")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)

    def _get_diary_context(self, n: int = 5) -> str:
        if not self._diary_entries:
            return ""
        recent = self._diary_entries[-n:]
        lines = ["## Imported History:"]
        for text in recent:
            lines.append(f"- [Imported History] {text}")
        return "\n".join(lines)

    def _log_data_state(self, label: str) -> None:
        mem_count = len(self._memory.get_all()) if hasattr(self, "_memory") else 0
        hist_count = self._history.count() if hasattr(self, "_history") else 0
        diary_count = len(self._diary_entries) if hasattr(self, "_diary_entries") else 0
        synced = self._diary_synced if hasattr(self, "_diary_synced") else 0
        try:
            if hasattr(self, "_firebase_mem"):
                brain = self._firebase_mem.load_current_brain()
                brain_fields = len(brain)
            else:
                brain_fields = 0
        except Exception:
            brain_fields = 0
        jokes = self._response_manager.remaining("jokes_blackmail") if hasattr(self, "_response_manager") else 0
        system = self._response_manager.remaining("system") if hasattr(self, "_response_manager") else 0
        logger.info(
            "[DATA] %s | memory=%d facts | history=%d entries | diary=%d entries (synced=%d) | brain=%d fields | cache: jokes=%d system=%d",
            label, mem_count, hist_count, diary_count, synced,
            brain_fields, jokes, system,
        )

    def _add_diary_entry(self, text: str) -> None:
        self._diary_entries.append(text)
        self._write_coalescer.mark_dirty("diary")
        logger.info("[DATA] add_diary_entry -> diary now %d entries, synced=%d", len(self._diary_entries), self._diary_synced)

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
            self._trigger_autonomous_query()

    def _trigger_autonomous_query(self) -> None:
        self._clear_bubble_queue()
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

    def _on_refill_needed(self, pool_type: str) -> None:
        from src.constants import (
            JOKES_BLACKMAIL_POOL_REFILL_COUNT, SYSTEM_POOL_REFILL_COUNT,
            TYPING_POOL_REFILL_COUNT,
        )
        if pool_type == "typing_reactions":
            count = TYPING_POOL_REFILL_COUNT
            prompt = self._context_manager.build_pool_refill_prompt(
                "typing_reactions", self._current_apm, count
            )
        elif pool_type == "jokes_blackmail":
            count = JOKES_BLACKMAIL_POOL_REFILL_COUNT
            prompt = (
                f"You are Daemon, the user's desktop pet. Generate {count} random "
                f"autonomous thoughts/jokes about the user's desktop habits as a JSON array. "
                f"Every item MUST contain 'thought' and 'dialogue', and may optionally include 'brain_update'."
            )
        else:
            count = SYSTEM_POOL_REFILL_COUNT
            prompt = (
                f"You are Daemon, the user's desktop pet. Generate {count} random "
                f"autonomous thoughts/jokes about the user's desktop habits as a JSON array. "
                f"Every item MUST contain 'thought' and 'dialogue', and may optionally include 'brain_update'."
            )
        worker = OpencodeWorker(
            "",
            is_autonomous=True,
            prompt=prompt,
        )
        worker.response_ready.connect(lambda items, pt=pool_type: self._on_refill_result(items, pt))
        worker.error_occurred.connect(lambda err, pt=pool_type: self._on_refill_error(pt))
        self._refill_workers[pool_type] = worker
        worker.start()

    def _on_refill_result(self, items: list, pool_type: str) -> None:
        logger.info("Refill result: %s, %d items", pool_type, len(items) if items else 0)
        worker = self._refill_workers.pop(pool_type, None)
        if worker is not None:
            worker.deleteLater()
        if not items:
            self._response_manager._pools[pool_type].on_refill_result(None)
            return
        pool_items = []
        for item in items:
            if isinstance(item, dict):
                pool_items.append({
                    "dialogue": item.get("dialogue", ""),
                    "action": item.get("action", "idle"),
                    "target_x": item.get("target_x", 0),
                    "priority": item.get("priority", 3),
                    "pool_type": pool_type,
                })
        self._response_manager._pools[pool_type].on_refill_result(pool_items)

    def _on_refill_error(self, pool_type: str) -> None:
        worker = self._refill_workers.pop(pool_type, None)
        if worker is not None:
            worker.deleteLater()
        self._response_manager._pools[pool_type].on_refill_result(None)

    def _on_pool_items_ready(self, items: dict) -> None:
        logger.info("Pool items ready from user response: %s", list(items.keys()))
        joke_items = items.get("jokes_blackmail", [])
        system_items = items.get("system", [])
        self._response_manager.prime_from_user_response(joke_items, system_items)

    def _on_session_created(self, session_id: str) -> None:
        self._opencode_session_id = session_id


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
        if "recent_blackmail_log" in applied:
            current = self._memory.recall("recent_blackmail_log")
            if current:
                entries = current.split("; ")
                if len(entries) > 10:
                    self._memory.remember("recent_blackmail_log", "; ".join(entries[-10:]))

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
        from src.constants import OPENCODE_SERVER_URL
        try:
            _req.delete(
                f"{OPENCODE_SERVER_URL}/session/{self._opencode_session_id}",
                timeout=5,
            )
            logger.info("Opencode API session closed: %s", self._opencode_session_id)
        except Exception as e:
            logger.warning("Opencode API session close failed (ignored): %s", e)
        self._opencode_session_id = None



