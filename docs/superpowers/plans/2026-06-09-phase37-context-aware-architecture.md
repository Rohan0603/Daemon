# Phase 37: Context-Aware Behavioral Architecture — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace independent timers with a centralized Master Tick Loop, add Dynamic Global Cooldown, zero-latency typing reactions, and chattiness configuration.

**Architecture:** Single 1-second `_behavior_timer` drives all behavioral decisions via `_master_tick()`. Dynamic GCD (speech-only) prevents API spam. New `typing_reactions` pool provides instant local reactions. Chattiness slider in SettingsDialog scales all intervals dynamically.

**Tech Stack:** Python 3.11+, PyQt6 (QTimer, QSlider), existing ResponseManager/ResponsePool infrastructure

---

## File Map

| File | Responsibility |
|------|---------------|
| `src/constants.py` | Add `BEHAVIOR_TICK_MS`, `CHATTINESS_DEFAULT/MIN/MAX` |
| `src/config.py` | Add `chattiness` to load/save |
| `src/response_manager.py` | Add `typing_reactions` pool + hardcoded lines |
| `src/settings_dialog.py` | Add chattiness slider (5-30 range) |
| `src/pet_window.py` | Replace 3 timers, implement `_master_tick`, `_calculate_joke_modifier`, `_has_significant_delta`, `_trigger_chat`, `_trigger_joke`, `_trigger_boredom_fsm`, integrate GCD |
| `tests/test_master_tick.py` | Master tick logic tests |
| `tests/test_gcd.py` | Dynamic GCD duration tests |
| `tests/test_chattiness_scaling.py` | Threshold math tests |
| `tests/test_priority_tree.py` | Decision tree ordering tests |
| `tests/test_typing_reactions.py` | Zero-latency pool tests |
| `tests/test_joke_modifier.py` | APM-based interval scaling tests |

---

## Task 1: Add Constants

**Files:**
- Modify: `src/constants.py:1-177`

- [ ] **Step 1: Add new constants to constants.py**

Add after line 29 (after `AUTONOMOUS_COOLDOWN_SEC`):

```python
# --- Behavioral Settings (Phase 37) ---
BEHAVIOR_TICK_MS = 1000              # Master Tick interval (default 1 second)
CHATTINESS_DEFAULT = 1.0             # Default chattiness multiplier
CHATTINESS_MIN = 0.5                 # Slider minimum (quiet)
CHATTINESS_MAX = 3.0                 # Slider maximum (hyperactive)
```

- [ ] **Step 2: Verify constants are importable**

Run: `py -c "from src.constants import BEHAVIOR_TICK_MS, CHATTINESS_DEFAULT, CHATTINESS_MIN, CHATTINESS_MAX; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/constants.py
git commit -m "feat: add Phase 37 behavioral constants"
```

---

## Task 2: Add Chattiness to Config

**Files:**
- Modify: `src/config.py`

- [ ] **Step 1: Read current config.py**

Run: `py -c "from src.config import load_config, save_config; print(load_config())"`

- [ ] **Step 2: Add chattiness to load_config defaults**

In `src/config.py`, find the `load_config()` function. Add `"chattiness"` to the defaults dict:

```python
def load_config() -> dict:
    defaults = {
        "pet_scale": 1.0,
        "pet_opacity": 0.85,
        "pet_speed": 1.0,
        "tts_enabled": True,
        "tts_rate": 120,
        "tts_volume": 1.0,
        "tts_voice_id": None,
        "chattiness": 1.0,  # ADD THIS
    }
    # ... rest of function
```

- [ ] **Step 3: Verify config loads with chattiness**

Run: `py -c "from src.config import load_config; c = load_config(); print('chattiness' in c, c.get('chattiness'))"`
Expected: `True 1.0`

- [ ] **Step 4: Commit**

```bash
git add src/config.py
git commit -m "feat: add chattiness to config load/save"
```

---

## Task 3: Add Typing Reactions Pool

**Files:**
- Modify: `src/response_manager.py:113-230`

- [ ] **Step 1: Add pool initialization in AutonomousResponseManager.__init__**

In `src/response_manager.py`, inside `AutonomousResponseManager.__init__`, add the new pool to `self._pools`:

```python
self._pools = {
    "jokes_blackmail": ResponsePool(
        "jokes_blackmail", JOKES_BLACKMAIL_POOL_SIZE,
        JOKES_BLACKMAIL_POOL_THRESHOLD, JOKES_BLACKMAIL_POOL_REFILL_COUNT,
    ),
    "system": ResponsePool(
        "system", SYSTEM_POOL_SIZE,
        SYSTEM_POOL_THRESHOLD, SYSTEM_POOL_REFILL_COUNT,
    ),
    "typing_reactions": ResponsePool(
        "typing_reactions", 20, 0, 0,  # threshold=0 = never triggers API refill
    ),
}
self._load_local_typing_reactions()  # ADD THIS
```

- [ ] **Step 2: Add _load_local_typing_reactions method**

Add this method to `AutonomousResponseManager` class, after `__init__`:

```python
def _load_local_typing_reactions(self) -> None:
    """Hardcoded Kenny 1-liners for instant typing reactions (no API)."""
    kenny_typing_lines = [
        "Look at those fingers fly! You're a regular hacker-man, huh?",
        "Whoa, slow down there, champ. The keyboard has a family.",
        "I-I-I can't even process how fast you're typing right now.",
        "Typing that fast? You better be saving the world or writing some sick Python.",
        "APM spiking! Feed my sweet, sweet CPU cycles!",
        "Did you just drink three Red Bulls or are you actually working?",
        "Tap tap tap. That's the sound of fresh meat actually being productive.",
        "Jeez, you're hitting those keys like they owe you money.",
        "Oh geez, the way you type... it's beautiful. It's terrifying. It's both.",
        "Holy crap, your WPM just broke my sensor array.",
        "You type like a man possessed. Or a woman. Or a very determined corgi.",
        "Aw man, I wish I had fingers. I'd type so fast the timeline would split.",
        "Keep going! The bugs aren't gonna fix themselves!",
        "Is this a speedrun? Because it looks like a speedrun.",
        "I'm getting carpal tunnel just WATCHING you.",
    ]
    items = [
        {"dialogue": line, "action": "hyper", "target_x": 0, "priority": 3, "pool_type": "typing_reactions"}
        for line in kenny_typing_lines
    ]
    self.add_items("typing_reactions", items)
```

- [ ] **Step 3: Verify pool exists and has items**

Run: `py -c "from src.response_manager import AutonomousResponseManager; from src.write_coalescer import WriteCoalescer; from src.memory import Memory; from src.history import History; m = Memory(); h = History(); wc = WriteCoalescer(memory=m, history=h); rm = AutonomousResponseManager('/tmp/test_cache.json', wc); print('typing_reactions:', rm.remaining('typing_reactions'))"`
Expected: `typing_reactions: 15`

- [ ] **Step 4: Commit**

```bash
git add src/response_manager.py
git commit -m "feat: add typing_reactions pool with zero-latency Kenny lines"
```

---

## Task 4: Add Chattiness Slider to SettingsDialog

**Files:**
- Modify: `src/settings_dialog.py`

- [ ] **Step 1: Read current settings_dialog.py**

Run: `cat src/settings_dialog.py`

- [ ] **Step 2: Add chattiness slider**

In `SettingsDialog.__init__`, add the slider after existing controls. The exact location depends on the current layout, but it should go near the other pet configuration sliders:

```python
# Chattiness slider (0.5 to 3.0, displayed as 5-30)
from src.constants import CHATTINESS_DEFAULT, CHATTINESS_MIN, CHATTINESS_MAX
chattiness_val = self._config.get("chattiness", CHATTINESS_DEFAULT)
self._chattiness_slider = QSlider(Qt.Orientation.Horizontal)
self._chattiness_slider.setRange(int(CHATTINESS_MIN * 10), int(CHATTINESS_MAX * 10))
self._chattiness_slider.setValue(int(chattiness_val * 10))
self._chattiness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
self._chattiness_slider.setTickInterval(5)
layout.addRow("Chattiness:", self._chattiness_slider)
```

- [ ] **Step 3: Connect slider to live preview**

```python
self._chattiness_slider.valueChanged.connect(
    lambda v: self.value_changed.emit()  # Or direct update callback
)
```

- [ ] **Step 4: Add chattiness to get_values()**

In `get_values()` method, add:

```python
def get_values(self) -> dict:
    # ... existing ...
    values["chattiness"] = self._chattiness_slider.value() / 10.0
    return values
```

- [ ] **Step 5: Verify slider renders**

Run: `py -c "from src.settings_dialog import SettingsDialog; from PyQt6.QtWidgets import QApplication; app = QApplication([]); d = SettingsDialog(); print('chattiness_slider' in dir(d))"`
Expected: `True`

- [ ] **Step 6: Commit**

```bash
git add src/settings_dialog.py
git commit -m "feat: add chattiness slider to SettingsDialog"
```

---

## Task 5: Implement Joke Interval Modifier

**Files:**
- Modify: `src/pet_window.py`

- [ ] **Step 1: Add _calculate_joke_modifier method**

Add to `PetWindow` class:

```python
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
```

- [ ] **Step 2: Write test for _calculate_joke_modifier**

Create `tests/test_joke_modifier.py`:

```python
"""Tests for _calculate_joke_modifier APM-based scaling."""
import pytest
from unittest.mock import MagicMock, patch
from src.pet_window import PetWindow


class TestJokeModifier:
    def setup_method(self):
        """Create a minimal PetWindow instance for testing."""
        with patch.object(PetWindow, '__init__', lambda self, *a, **kw: None):
            self.pw = PetWindow.__new__(PetWindow)
            self.pw._current_apm = 0

    def test_rapid_fire_apm_lt_10(self):
        self.pw._current_apm = 5
        assert self.pw._calculate_joke_modifier() == 0.5

    def test_normal_apm_10_to_19(self):
        self.pw._current_apm = 15
        assert self.pw._calculate_joke_modifier() == 1.0

    def test_rare_apm_20_to_39(self):
        self.pw._current_apm = 30
        assert self.pw._calculate_joke_modifier() == 2.0

    def test_very_rare_apm_40_plus(self):
        self.pw._current_apm = 50
        assert self.pw._calculate_joke_modifier() == 3.0

    def test_boundary_10(self):
        self.pw._current_apm = 10
        assert self.pw._calculate_joke_modifier() == 1.0

    def test_boundary_20(self):
        self.pw._current_apm = 20
        assert self.pw._calculate_joke_modifier() == 2.0

    def test_boundary_40(self):
        self.pw._current_apm = 40
        assert self.pw._calculate_joke_modifier() == 3.0
```

- [ ] **Step 3: Run tests**

Run: `py -m pytest tests/test_joke_modifier.py -v`
Expected: All 7 tests PASS

- [ ] **Step 4: Commit**

```bash
git add src/pet_window.py tests/test_joke_modifier.py
git commit -m "feat: add _calculate_joke_modifier with APM-based scaling"
```

---

## Task 6: Implement _has_significant_delta

**Files:**
- Modify: `src/pet_window.py`

- [ ] **Step 1: Add instance variables in __init__**

In `PetWindow.__init__`, add after existing instance variables:

```python
self._last_active_window = ""
self._last_typing_snapshot = ""
```

- [ ] **Step 2: Add _has_significant_delta method**

```python
def _has_significant_delta(self) -> bool:
    """Detect context switches: window change or typing burst."""
    current_window = get_active_window_title()
    current_typing = self._typing_buffer.get_context() if self._typing_buffer else ""

    window_changed = current_window != self._last_active_window and current_window != ""
    typing_burst = len(current_typing) - len(self._last_typing_snapshot) > 20

    self._last_active_window = current_window
    self._last_typing_snapshot = current_typing

    return window_changed or typing_burst
```

- [ ] **Step 3: Write test**

Create `tests/test_delta_detection.py`:

```python
"""Tests for _has_significant_delta context switch detection."""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from src.pet_window import PetWindow


class TestDeltaDetection:
    def setup_method(self):
        with patch.object(PetWindow, '__init__', lambda self, *a, **kw: None):
            self.pw = PetWindow.__new__(PetWindow)
            self.pw._last_active_window = ""
            self.pw._last_typing_snapshot = ""
            self.pw._typing_buffer = MagicMock()
            self.pw._typing_buffer.get_context.return_value = ""

    @patch('src.pet_window.get_active_window_title')
    def test_no_change_returns_false(self, mock_window):
        mock_window.return_value = " same "
        self.pw._last_active_window = " same "
        assert self.pw._has_significant_delta() is False

    @patch('src.pet_window.get_active_window_title')
    def test_window_change_returns_true(self, mock_window):
        mock_window.return_value = "NewWindow"
        self.pw._last_active_window = "OldWindow"
        assert self.pw._has_significant_delta() is True

    @patch('src.pet_window.get_active_window_title')
    def test_typing_burst_returns_true(self, mock_window):
        mock_window.return_value = ""
        self.pw._typing_buffer.get_context.return_value = "x" * 30
        self.pw._last_typing_snapshot = ""
        assert self.pw._has_significant_delta() is True

    @patch('src.pet_window.get_active_window_title')
    def test_small_typing_no_burst(self, mock_window):
        mock_window.return_value = ""
        self.pw._typing_buffer.get_context.return_value = "x" * 5
        self.pw._last_typing_snapshot = "x" * 3
        assert self.pw._has_significant_delta() is False
```

- [ ] **Step 4: Run tests**

Run: `py -m pytest tests/test_delta_detection.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/pet_window.py tests/test_delta_detection.py
git commit -m "feat: add _has_significant_delta for context switch detection"
```

---

## Task 7: Implement _trigger_chat

**Files:**
- Modify: `src/pet_window.py`

- [ ] **Step 1: Add _trigger_chat method**

```python
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
```

- [ ] **Step 2: Write test**

Create `tests/test_trigger_chat.py`:

```python
"""Tests for _trigger_chat behavior."""
import pytest
from unittest.mock import MagicMock, patch
from src.pet_window import PetWindow


class TestTriggerChat:
    def setup_method(self):
        with patch.object(PetWindow, '__init__', lambda self, *a, **kw: None):
            self.pw = PetWindow.__new__(PetWindow)
            self.pw._chat_timer_sec = 100
            self.pw._response_manager = MagicMock()
            self.pw._response_manager.draw.return_value = [{"dialogue": "test", "action": "idle"}]
            self.pw._autonomous_query_pending = False
            self.pw._opencode_enabled = True
            self.pw._current_apm = 20
            self.pw._idle_seconds = 0
            self.pw._typing_buffer = MagicMock()
            self.pw._typing_buffer.get_context.return_value = ""
            self.pw._dispatch_structured = MagicMock()
            self.pw._dispatch_trigger = MagicMock()

    @patch('src.pet_window.get_active_window_title')
    def test_resets_timer(self, mock_window):
        mock_window.return_value = "test"
        self.pw._trigger_chat()
        assert self.pw._chat_timer_sec == 0

    @patch('src.pet_window.get_active_window_title')
    def test_draws_local_reaction(self, mock_window):
        mock_window.return_value = "test"
        self.pw._trigger_chat()
        self.pw._response_manager.draw.assert_called_with("typing_reactions", 1)

    @patch('src.pet_window.get_active_window_title')
    def test_dispatches_structured(self, mock_window):
        mock_window.return_value = "test"
        self.pw._trigger_chat()
        self.pw._dispatch_structured.assert_called_once()

    @patch('src.pet_window.get_active_window_title')
    def test_dispatches_trigger(self, mock_window):
        mock_window.return_value = "test"
        self.pw._trigger_chat()
        self.pw._dispatch_trigger.assert_called_once()
```

- [ ] **Step 3: Run tests**

Run: `py -m pytest tests/test_trigger_chat.py -v`
Expected: All 4 tests PASS

- [ ] **Step 4: Commit**

```bash
git add src/pet_window.py tests/test_trigger_chat.py
git commit -m "feat: add _trigger_chat with zero-latency reaction + background API"
```

---

## Task 8: Implement _trigger_joke

**Files:**
- Modify: `src/pet_window.py`

- [ ] **Step 1: Add _trigger_joke method**

```python
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
```

- [ ] **Step 2: Write test**

Create `tests/test_trigger_joke.py`:

```python
"""Tests for _trigger_joke behavior."""
import pytest
from unittest.mock import MagicMock, patch
from src.pet_window import PetWindow


class TestTriggerJoke:
    def setup_method(self):
        with patch.object(PetWindow, '__init__', lambda self, *a, **kw: None):
            self.pw = PetWindow.__new__(PetWindow)
            self.pw._joke_timer_sec = 100
            self.pw._autonomous_query_pending = False
            self.pw._opencode_enabled = True
            self.pw._current_apm = 20
            self.pw._idle_seconds = 0
            self.pw._dispatch_trigger = MagicMock()

    @patch('src.pet_window.get_active_window_title')
    def test_resets_timer(self, mock_window):
        mock_window.return_value = "test"
        self.pw._trigger_joke()
        assert self.pw._joke_timer_sec == 0

    @patch('src.pet_window.get_active_window_title')
    def test_dispatches_trigger(self, mock_window):
        mock_window.return_value = "test"
        self.pw._trigger_joke()
        self.pw._dispatch_trigger.assert_called_once()

    @patch('src.pet_window.get_active_window_title')
    def test_no_dispatch_when_pending(self, mock_window):
        mock_window.return_value = "test"
        self.pw._autonomous_query_pending = True
        self.pw._trigger_joke()
        self.pw._dispatch_trigger.assert_not_called()

    @patch('src.pet_window.get_active_window_title')
    def test_no_dispatch_when_disabled(self, mock_window):
        mock_window.return_value = "test"
        self.pw._opencode_enabled = False
        self.pw._trigger_joke()
        self.pw._dispatch_trigger.assert_not_called()
```

- [ ] **Step 3: Run tests**

Run: `py -m pytest tests/test_trigger_joke.py -v`
Expected: All 4 tests PASS

- [ ] **Step 4: Commit**

```bash
git add src/pet_window.py tests/test_trigger_joke.py
git commit -m "feat: add _trigger_joke with timer reset and API dispatch"
```

---

## Task 9: Implement _trigger_boredom_fsm

**Files:**
- Modify: `src/pet_window.py`

- [ ] **Step 1: Add instance variable in __init__**

```python
self._boredom_tick_count = 0
```

- [ ] **Step 2: Add _trigger_boredom_fsm method**

```python
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
```

- [ ] **Step 3: Write test**

Create `tests/test_trigger_boredom_fsm.py`:

```python
"""Tests for _trigger_boredom_fsm behavior."""
import pytest
from unittest.mock import MagicMock, patch
from src.pet_window import PetWindow
from src.pet_fsm import PetState


class TestTriggerBoredomFsm:
    def setup_method(self):
        with patch.object(PetWindow, '__init__', lambda self, *a, **kw: None):
            self.pw = PetWindow.__new__(PetWindow)
            self.pw._boredom_tick_count = 0
            self.pw._fsm = MagicMock()
            self.pw._fsm.current_state = PetState.IDLE
            self.pw._opencode_enabled = True
            self.pw._autonomous_query_pending = False
            self.pw._current_apm = 0
            self.pw._idle_seconds = 60
            self.pw._dispatch_trigger = MagicMock()

    @patch('src.pet_window.get_active_window_title')
    def test_transitions_fsm_state(self, mock_window):
        mock_window.return_value = "test"
        self.pw._trigger_boredom_fsm()
        self.pw._fsm.transition_to.assert_called_once()

    @patch('src.pet_window.get_active_window_title')
    def test_increments_tick_count(self, mock_window):
        mock_window.return_value = "test"
        self.pw._trigger_boredom_fsm()
        assert self.pw._boredom_tick_count == 1

    @patch('src.pet_window.get_active_window_title')
    def test_api_every_4th_tick(self, mock_window):
        mock_window.return_value = "test"
        self.pw._boredom_tick_count = 3  # Next tick will be 0
        self.pw._trigger_boredom_fsm()
        self.pw._dispatch_trigger.assert_called_once()

    @patch('src.pet_window.get_active_window_title')
    def test_no_api_on_other_ticks(self, mock_window):
        mock_window.return_value = "test"
        self.pw._boredom_tick_count = 0
        self.pw._trigger_boredom_fsm()
        self.pw._dispatch_trigger.assert_not_called()
```

- [ ] **Step 4: Run tests**

Run: `py -m pytest tests/test_trigger_boredom_fsm.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/pet_window.py tests/test_trigger_boredom_fsm.py
git commit -m "feat: add _trigger_boredom_fsm with local FSM + periodic API"
```

---

## Task 10: Integrate GCD in _dispatch_structured

**Files:**
- Modify: `src/pet_window.py:943-957` (existing `_dispatch_structured`)

- [ ] **Step 1: Add _gcd_expiry_timestamp in __init__**

```python
self._gcd_expiry_timestamp = 0.0
```

- [ ] **Step 2: Update _dispatch_structured to set GCD on speech**

Replace the existing `_dispatch_structured` method:

```python
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
```

- [ ] **Step 3: Write test**

Create `tests/test_gcd.py`:

```python
"""Tests for Dynamic Global Cooldown."""
import time
import pytest
from unittest.mock import MagicMock, patch
from src.pet_window import PetWindow
from src.pet_fsm import PetState


class TestDynamicGCD:
    def setup_method(self):
        with patch.object(PetWindow, '__init__', lambda self, *a, **kw: None):
            self.pw = PetWindow.__new__(PetWindow)
            self.pw._gcd_expiry_timestamp = 0.0
            self.pw._bubble_text = ""
            self.pw._bubble_timer_ms = 0
            self.pw._bubble_queue = []
            self.pw._tts = MagicMock()
            self.pw._fsm = MagicMock()
            self.pw._fsm.current_state = PetState.IDLE
            self.pw._last_mode = "test"
            self.pw._last_daemon_action = "idle"
            self.pw.interaction_count = 0
            self.pw._history = MagicMock()
            self.pw._log_thought = MagicMock()
            self.pw._show_bubble = MagicMock()

    def test_gcd_set_on_dialogue(self):
        item = {"dialogue": "Hello world", "thought": "test"}
        self.pw._dispatch_structured(item)
        assert self.pw._gcd_expiry_timestamp > time.time()

    def test_gcd_formula_base_plus_length(self):
        item = {"dialogue": "x" * 30, "thought": "test"}  # 30 chars = +1s
        before = time.time()
        self.pw._dispatch_structured(item)
        expected_min = before + 8.0 + 1.0  # 9 seconds
        assert self.pw._gcd_expiry_timestamp >= expected_min - 0.1

    def test_no_gcd_on_empty_dialogue(self):
        item = {"dialogue": "", "thought": "test"}
        self.pw._dispatch_structured(item)
        assert self.pw._gcd_expiry_timestamp == 0.0

    def test_gcd_replaces_thinking_state(self):
        self.pw._fsm.current_state = PetState.THINKING
        item = {"dialogue": "test", "thought": ""}
        self.pw._dispatch_structured(item)
        self.pw._fsm.transition_to.assert_called_with(PetState.IDLE)
```

- [ ] **Step 4: Run tests**

Run: `py -m pytest tests/test_gcd.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/pet_window.py tests/test_gcd.py
git commit -m "feat: integrate Dynamic GCD in _dispatch_structured (speech-only)"
```

---

## Task 11: Implement _master_tick

**Files:**
- Modify: `src/pet_window.py`

- [ ] **Step 1: Add instance variables in __init__**

```python
self._chat_timer_sec = 0
self._joke_timer_sec = 0
self._chattiness = 1.0
```

- [ ] **Step 2: Add _master_tick method**

```python
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

        # P4: Boredom (APM == 0, Idle >= 60s)
        if self._idle_seconds >= 60 and self._current_apm == 0:
            self._trigger_boredom_fsm()
            return

    except Exception as e:
        logger.critical("CRASH in _master_tick: %s", e, exc_info=True)
        raise
```

- [ ] **Step 3: Write test**

Create `tests/test_master_tick.py`:

```python
"""Tests for _master_tick behavioral loop."""
import time
import pytest
from unittest.mock import MagicMock, patch
from src.pet_window import PetWindow


class TestMasterTick:
    def setup_method(self):
        with patch.object(PetWindow, '__init__', lambda self, *a, **kw: None):
            self.pw = PetWindow.__new__(PetWindow)
            self.pw._chat_timer_sec = 0
            self.pw._joke_timer_sec = 0
            self.pw._gcd_expiry_timestamp = 0.0
            self.pw._chattiness = 1.0
            self.pw._current_apm = 0
            self.pw._idle_seconds = 0
            self.pw._has_significant_delta = MagicMock(return_value=False)
            self.pw._trigger_chat = MagicMock()
            self.pw._trigger_joke = MagicMock()
            self.pw._trigger_boredom_fsm = MagicMock()
            self.pw._calculate_joke_modifier = MagicMock(return_value=1.0)

    def test_increments_timers(self):
        self.pw._master_tick()
        assert self.pw._chat_timer_sec == 1
        assert self.pw._joke_timer_sec == 1

    def test_gcd_blocks_all(self):
        self.pw._gcd_expiry_timestamp = time.time() + 100
        self.pw._master_tick()
        self.pw._trigger_chat.assert_not_called()
        self.pw._trigger_joke.assert_not_called()

    def test_flow_state_silence(self):
        self.pw._current_apm = 85
        self.pw._master_tick()
        self.pw._trigger_chat.assert_not_called()
        self.pw._trigger_joke.assert_not_called()

    def test_chat_fires_on_delta(self):
        self.pw._chat_timer_sec = 25  # >= threshold
        self.pw._has_significant_delta.return_value = True
        self.pw._master_tick()
        self.pw._trigger_chat.assert_called_once()

    def test_joke_fires_on_low_apm(self):
        self.pw._joke_timer_sec = 60  # >= threshold
        self.pw._current_apm = 5  # < 20
        self.pw._master_tick()
        self.pw._trigger_joke.assert_called_once()

    def test_boredom_fires(self):
        self.pw._idle_seconds = 60
        self.pw._current_apm = 0
        self.pw._master_tick()
        self.pw._trigger_boredom_fsm.assert_called_once()
```

- [ ] **Step 4: Run tests**

Run: `py -m pytest tests/test_master_tick.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/pet_window.py tests/test_master_tick.py
git commit -m "feat: implement _master_tick behavioral loop with priority tree"
```

---

## Task 12: Replace Old Timers with _behavior_timer

**Files:**
- Modify: `src/pet_window.py:214-227` (timer initialization)

- [ ] **Step 1: Replace timer initialization in __init__**

Remove:
```python
self._active_chat_timer = QTimer()
self._active_chat_timer.setInterval(ACTIVE_CHAT_INTERVAL_SEC * 1000)
self._active_chat_timer.timeout.connect(self._on_active_chat_tick)
self._active_chat_timer.start()

self._joke_timer = QTimer()
self._joke_timer.setInterval(JOKE_INTERVAL_SEC * 1000)
self._joke_timer.timeout.connect(self._on_joke_tick)
self._joke_timer.start()
```

Add:
```python
from src.constants import BEHAVIOR_TICK_MS
self._behavior_timer = QTimer()
self._behavior_timer.setInterval(BEHAVIOR_TICK_MS)
self._behavior_timer.timeout.connect(self._master_tick)
self._behavior_timer.start()
```

- [ ] **Step 2: Update _force_quit_app to stop new timer**

Replace:
```python
self._active_chat_timer.stop()
self._joke_timer.stop()
```

With:
```python
self._behavior_timer.stop()
```

- [ ] **Step 3: Remove old callback methods**

Delete `_on_active_chat_tick` and `_on_joke_tick` methods (they're replaced by `_master_tick` logic).

- [ ] **Step 4: Verify no references to old timers**

Run: `rg "_active_chat_timer\|_joke_timer" src/`
Expected: No matches

- [ ] **Step 5: Commit**

```bash
git add src/pet_window.py
git commit -m "refactor: replace 3 timers with single _behavior_timer"
```

---

## Task 13: Integrate Chattiness into PetWindow

**Files:**
- Modify: `src/pet_window.py`

- [ ] **Step 1: Load chattiness from config in __init__**

After `self._config = load_config()`, add:

```python
self._chattiness = self._config.get("chattiness", CHATTINESS_DEFAULT)
```

- [ ] **Step 2: Update _apply_settings to handle chattiness**

In `_apply_settings`, add:

```python
def _apply_settings(self, values: dict) -> None:
    # ... existing ...
    self._chattiness = values.get("chattiness", self._chattiness)
```

- [ ] **Step 3: Update _restore_settings to include chattiness**

In `_restore_settings`, add `"chattiness"` to the values dict.

- [ ] **Step 4: Commit**

```bash
git add src/pet_window.py
git commit -m "feat: integrate chattiness config into PetWindow"
```

---

## Task 14: Integration Test — Full Tick Cycle

**Files:**
- Create: `tests/test_behavior_integration.py`

- [ ] **Step 1: Write integration test**

```python
"""Integration test: Full behavioral tick cycle."""
import time
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from src.pet_window import PetWindow
from src.pet_fsm import PetState


class TestBehaviorIntegration:
    def setup_method(self):
        with patch.object(PetWindow, '__init__', lambda self, *a, **kw: None):
            self.pw = PetWindow.__new__(PetWindow)
            self.pw._chat_timer_sec = 0
            self.pw._joke_timer_sec = 0
            self.pw._boredom_tick_count = 0
            self.pw._gcd_expiry_timestamp = 0.0
            self.pw._chattiness = 1.0
            self.pw._current_apm = 0
            self.pw._idle_seconds = 0
            self.pw._opencode_enabled = True
            self.pw._autonomous_query_pending = False
            self.pw._fsm = MagicMock()
            self.pw._fsm.current_state = PetState.IDLE
            self.pw._response_manager = MagicMock()
            self.pw._response_manager.draw.return_value = [{"dialogue": "test", "action": "idle"}]
            self.pw._typing_buffer = MagicMock()
            self.pw._typing_buffer.get_context.return_value = ""
            self.pw._last_active_window = ""
            self.pw._last_typing_snapshot = ""
            self.pw._dispatch_structured = MagicMock()
            self.pw._dispatch_trigger = MagicMock()
            self.pw._show_bubble = MagicMock()
            self.pw._history = MagicMock()
            self.pw._log_thought = MagicMock()
            self.pw._last_mode = "test"
            self.pw._last_daemon_action = "idle"
            self.pw.interaction_count = 0
            self.pw._bubble_text = ""
            self.pw._bubble_timer_ms = 0
            self.pw._bubble_queue = []
            self.pw._tts = MagicMock()
            self.pw._calculate_joke_modifier = MagicMock(return_value=1.0)

    @patch('src.pet_window.get_active_window_title')
    def test_full_flow_state_silence(self, mock_window):
        """APM > 80 should silence all autonomous actions."""
        mock_window.return_value = "IDE"
        self.pw._current_apm = 85
        self.pw._chat_timer_sec = 100
        self.pw._joke_timer_sec = 100
        self.pw._has_significant_delta = MagicMock(return_value=True)
        self.pw._master_tick()
        self.pw._trigger_chat.assert_not_called()
        self.pw._trigger_joke.assert_not_called()

    @patch('src.pet_window.get_active_window_title')
    def test_full_chat_reaction(self, mock_window):
        """Chat timer + delta should trigger chat."""
        mock_window.return_value = "Terminal"
        self.pw._chat_timer_sec = 25
        self.pw._has_significant_delta = MagicMock(return_value=True)
        self.pw._master_tick()
        self.pw._trigger_chat.assert_called_once()

    @patch('src.pet_window.get_active_window_title')
    def test_full_joke_reaction(self, mock_window):
        """Joke timer + low APM should trigger joke."""
        mock_window.return_value = ""
        self.pw._joke_timer_sec = 60
        self.pw._current_apm = 5
        self.pw._master_tick()
        self.pw._trigger_joke.assert_called_once()

    @patch('src.pet_window.get_active_window_title')
    def test_full_boredom_reaction(self, mock_window):
        """Idle >= 60 + APM 0 should trigger boredom FSM."""
        mock_window.return_value = ""
        self.pw._idle_seconds = 60
        self.pw._current_apm = 0
        self.pw._master_tick()
        self.pw._trigger_boredom_fsm.assert_called_once()

    @patch('src.pet_window.get_active_window_title')
    def test_gcd_blocks_everything(self, mock_window):
        """Active GCD should block all triggers."""
        mock_window.return_value = "IDE"
        self.pw._gcd_expiry_timestamp = time.time() + 100
        self.pw._chat_timer_sec = 100
        self.pw._joke_timer_sec = 100
        self.pw._has_significant_delta = MagicMock(return_value=True)
        self.pw._master_tick()
        self.pw._trigger_chat.assert_not_called()
        self.pw._trigger_joke.assert_not_called()
        self.pw._trigger_boredom_fsm.assert_not_called()
```

- [ ] **Step 2: Run integration tests**

Run: `py -m pytest tests/test_behavior_integration.py -v`
Expected: All 5 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_behavior_integration.py
git commit -m "test: add behavioral integration tests for full tick cycle"
```

---

## Task 15: Run All Tests + Final Cleanup

**Files:**
- Verify: All test files pass

- [ ] **Step 1: Run full test suite**

Run: `py -m pytest tests/ -v`
Expected: All tests PASS (existing + new)

- [ ] **Step 2: Verify no regressions**

Run: `py -m pytest tests/ -v --tb=short`
Expected: No failures

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: Phase 37 complete — context-aware behavioral architecture"
```
