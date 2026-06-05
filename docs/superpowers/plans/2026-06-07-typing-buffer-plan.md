# TypingBuffer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture full keystroke content into a ring buffer and include it in every LLM prompt so the daemon can react to what the user types.

**Architecture:** New `TypingBuffer` QObject (separate from `APMWorker`) with its own `pynput.keyboard.Listener`. Ring buffer of last 500 chars. Passed into `ContextBuilder.build_prompt()` and `OpencodeWorker._build_prompt()`. Debounced active reactions via PetWindow timer.

**Tech Stack:** Python 3.11+, PyQt6, pynput

---

### Task 1: Write TypingBuffer tests

**Files:**
- Create: `tests/test_typing_buffer.py`

- [ ] **Step 1: Write all 11 tests**

```python
"""Tests for TypingBuffer (keystroke content capture)."""
from __future__ import annotations
import sys
from unittest.mock import MagicMock, patch
from pynput.keyboard import Key, KeyCode
import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    return app


def _make_buffer(qapp):
    from src.typing_buffer import TypingBuffer
    buf = TypingBuffer()
    buf._listener = MagicMock()
    return buf


def _press(buf, key):
    buf._on_press(key)


def test_prints_appended(qapp):
    buf = _make_buffer(qapp)
    _press(buf, KeyCode.from_char("a"))
    _press(buf, KeyCode.from_char("b"))
    _press(buf, KeyCode.from_char("c"))
    assert "".join(buf._buffer) == "abc"


def test_backspace_removes_last(qapp):
    buf = _make_buffer(qapp)
    _press(buf, KeyCode.from_char("a"))
    _press(buf, KeyCode.from_char("b"))
    _press(buf, Key.backspace)
    assert "".join(buf._buffer) == "a"


def test_backspace_on_empty_no_error(qapp):
    buf = _make_buffer(qapp)
    _press(buf, Key.backspace)  # should not raise
    assert len(buf._buffer) == 0


def test_enter_appends_newline(qapp):
    buf = _make_buffer(qapp)
    _press(buf, KeyCode.from_char("a"))
    _press(buf, Key.enter)
    _press(buf, KeyCode.from_char("b"))
    assert "".join(buf._buffer) == "a\nb"


def test_tab_appends_spaces(qapp):
    buf = _make_buffer(qapp)
    _press(buf, Key.tab)
    assert "".join(buf._buffer) == "  "


def test_lone_modifiers_ignored(qapp):
    buf = _make_buffer(qapp)
    _press(buf, Key.ctrl)
    _press(buf, Key.alt)
    _press(buf, Key.shift)
    _press(buf, Key.cmd)
    assert len(buf._buffer) == 0


def test_caps_lock_ignored(qapp):
    buf = _make_buffer(qapp)
    _press(buf, Key.caps_lock)
    assert len(buf._buffer) == 0


def test_buffer_caps_at_500(qapp):
    buf = _make_buffer(qapp)
    for i in range(510):
        _press(buf, KeyCode.from_char("a"))
    assert len(buf._buffer) == 500


def test_get_context_formatted(qapp):
    buf = _make_buffer(qapp)
    _press(buf, KeyCode.from_char("h"))
    _press(buf, KeyCode.from_char("i"))
    ctx = buf.get_context()
    assert "Recent Typing:" in ctx
    assert "hi" in ctx


def test_get_context_empty(qapp):
    buf = _make_buffer(qapp)
    assert buf.get_context() == ""


def test_get_context_truncates(qapp):
    buf = _make_buffer(qapp)
    for i in range(100):
        _press(buf, KeyCode.from_char("x"))
    ctx = buf.get_context(max_chars=10)
    assert ctx.count("x") == 10  # only last 10
```

- [ ] **Step 2: Run tests to verify failures**

Run: `py -m pytest tests/test_typing_buffer.py -v`
Expected: FAIL (11) — no module `src.typing_buffer`

- [ ] **Step 3: Commit**

```bash
git add tests/test_typing_buffer.py
git commit -m "test: TypingBuffer tests (expect fail)"
```

---

### Task 2: Implement TypingBuffer

**Files:**
- Create: `src/typing_buffer.py`
- Modify: `tests/test_typing_buffer.py` (remove expected-failure markers once implemented)

- [ ] **Step 1: Write TypingBuffer class**

```python
# src/typing_buffer.py
from __future__ import annotations
import logging
from collections import deque
from pynput import keyboard
from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)

# Special keys that produce text content
_TEXT_KEYS = {
    keyboard.Key.enter: "\n",
    keyboard.Key.tab: "  ",
}

# Modifier keys to ignore when pressed alone
_MODIFIERS = {
    keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r,
    keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r,
    keyboard.Key.alt_gr,
    keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r,
    keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r,
}

_IGNORED_KEYS = {
    keyboard.Key.backspace, keyboard.Key.esc,
    keyboard.Key.up, keyboard.Key.down, keyboard.Key.left, keyboard.Key.right,
    keyboard.Key.home, keyboard.Key.end, keyboard.Key.page_up, keyboard.Key.page_down,
    keyboard.Key.insert, keyboard.Key.delete,
    keyboard.Key.f1, keyboard.Key.f2, keyboard.Key.f3, keyboard.Key.f4,
    keyboard.Key.f5, keyboard.Key.f6, keyboard.Key.f7, keyboard.Key.f8,
    keyboard.Key.f9, keyboard.Key.f10, keyboard.Key.f11, keyboard.Key.f12,
    keyboard.Key.print_screen, keyboard.Key.scroll_lock, keyboard.Key.pause,
    keyboard.Key.num_lock, keyboard.Key.caps_lock,
    keyboard.Key.menu,
}

_IGNORED_KEYS.update(_MODIFIERS)


class TypingBuffer(QObject):
    text_updated = pyqtSignal()

    def __init__(self, max_chars: int = 500, parent=None):
        super().__init__(parent)
        self._max_chars = max_chars
        self._buffer: deque[str] = deque(maxlen=max_chars)
        self._listener: keyboard.Listener | None = None

    def start(self):
        if self._listener is not None:
            return
        self._listener = keyboard.Listener(on_press=self._on_press)
        self._listener.start()
        logger.info("TypingBuffer started")

    def stop(self):
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
            logger.info("TypingBuffer stopped")

    def get_context(self, max_chars: int = 300) -> str:
        if not self._buffer:
            return ""
        text = "".join(self._buffer)[-max_chars:]
        lines = text.split("\n")
        quoted = "\n  > ".join(lines)
        return f"Recent Typing:\n  > {quoted}"

    def _on_press(self, key):
        try:
            char = key.char
            if char is not None:
                self._buffer.append(char)
                self.text_updated.emit()
                return
        except AttributeError:
            pass

        if key in _IGNORED_KEYS:
            return

        if key == keyboard.Key.backspace:
            if self._buffer:
                self._buffer.pop()
                self.text_updated.emit()
            return

        text = _TEXT_KEYS.get(key)
        if text is not None:
            self._buffer.append(text)
            self.text_updated.emit()
```

- [ ] **Step 2: Run tests**

Run: `py -m pytest tests/test_typing_buffer.py -v`
Expected: PASS (11)

- [ ] **Step 3: Commit**

```bash
git add src/typing_buffer.py
git commit -m "feat: TypingBuffer with pynput keystroke capture"
```

---

### Task 3: Add `typing_content` to `_build_prompt` and OpencodeWorker

**Files:**
- Modify: `src/opencode_worker.py`

- [ ] **Step 1: Add `typing_content: str = ""` to `_build_prompt` signature**

```python
def _build_prompt(
    user_input: str,
    context_hint: str = "",
    apm: int = 0,
    is_autonomous: bool = False,
    memory_context: str = "",
    history_context: str = "",
    idle_seconds: float = 0.0,
    last_action: str = "idle",
    typing_content: str = "",
) -> str:
```

In the body, after the `last_action` context line, add:

```python
    if typing_content:
        context_lines.append("")
        context_lines.append(typing_content)
```

- [ ] **Step 2: Add `typing_content` param to OpencodeWorker.__init__**

```python
    def __init__(self, user_input: str, context_hint: str = "", apm: int = 0,
                 is_autonomous: bool = False, parent=None,
                 memory_context: str = "", history_context: str = "",
                 idle_seconds: float = 0.0, last_action: str = "idle",
                 continue_session: bool = False,
                 session_id: str | None = None,
                 modes: list[str] | None = None,
                 prompt: str | None = None,
                 typing_content: str = "") -> None:
        ...
        self._typing_content = typing_content
```

In `run()`, pass typing_content to `_build_prompt`:

```python
    prompt = _build_prompt(
        self._user_input, self._context_hint, self._apm, self._is_autonomous,
        memory_context=self._memory_context, history_context=self._history_context,
        idle_seconds=self._idle_seconds, last_action=self._last_action,
        typing_content=self._typing_content,
    )
```

- [ ] **Step 3: Run response_manager tests to verify no regression**

Run: `py -m pytest tests/test_response_manager.py -v`
Expected: PASS (14)

- [ ] **Step 4: Commit**

```bash
git add src/opencode_worker.py
git commit -m "feat: add typing_content support to _build_prompt and OpencodeWorker"
```

---

### Task 4: Add `typing_content` to ContextBuilder

**Files:**
- Modify: `src/context_builder.py`

- [ ] **Step 1: Add `typing_content: str = ""` to `build_prompt` signature**

```python
def build_prompt(self, user_input: str, context_hint: str, apm: int,
                 is_autonomous: bool, modes: list[str],
                 idle_seconds: float, last_action: str,
                 session_duration_minutes: int = 0,
                 current_fsm_state: str = "IDLE",
                 fsm_history: str = "",
                 typing_content: str = "") -> str:
```

- [ ] **Step 2: Pass typing_content into `_build_full` and `_build_delta`**

In `_build_full`, after the context_lines block and before `context_block = "\n".join(context_lines)`, add:

```python
if typing_content:
    context_lines.append("")
    context_lines.append(typing_content)
```

In `_build_delta`, after the APM bucket line, add:

```python
if typing_content:
    lines.append(f"Recent Typing: {typing_content}")
```

But wait — `typing_content` from `get_context()` already includes the "Recent Typing:" header and blockquote formatting. So append it directly.

- [ ] **Step 3: Run context_builder tests**

Run: `py -m pytest tests/ -k "context" -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/context_builder.py
git commit -m "feat: add typing_content param to ContextBuilder"
```

---

### Task 5: Wire TypingBuffer into PetWindow

**Files:**
- Modify: `src/pet_window.py`

- [ ] **Step 1: Instantiate TypingBuffer in `__init__`**

After the APMWorker block (~line 99), add:

```python
self._typing_buffer = TypingBuffer()
self._typing_buffer.start()
```

Add import at top: `from src.typing_buffer import TypingBuffer`

- [ ] **Step 2: Add debounced reaction logic**

After the response_manager block (~line 133), add:

```python
self._typing_last_len = 0
self._typing_debounce_timer = QTimer()
self._typing_debounce_timer.setSingleShot(True)
self._typing_debounce_timer.setInterval(2000)
self._typing_debounce_timer.timeout.connect(self._on_typing_debounce)
self._typing_buffer.text_updated.connect(self._typing_debounce_timer.start)
```

- [ ] **Step 3: Implement `_on_typing_debounce`**

```python
def _on_typing_debounce(self):
    current_len = len(self._typing_buffer._buffer)
    new_chars = current_len - self._typing_last_len
    self._typing_last_len = current_len
    if new_chars >= 30 and not self._autonomous_query_pending:
        self._trigger_autonomous_query()
```

- [ ] **Step 4: Pass typing context to all prompt builders**

In `_on_refill_needed` (~line 853), add `typing_content=` to `build_prompt()`:

```python
prompt = self._context_builder.build_prompt(
    user_input="",
    context_hint=get_active_window_title() or "Desktop",
    apm=self._current_apm,
    is_autonomous=True,
    modes=[pool_type],
    idle_seconds=self._idle_seconds,
    last_action=self._last_daemon_action,
    typing_content=self._typing_buffer.get_context(),
)
```

In the main query path (~line 535), add `typing_content=` to OpencodeWorker:

```python
self._opencode_worker = OpencodeWorker(
    text, context_hint=context, apm=self._current_apm,
    memory_context=mem_ctx, history_context=hist_ctx,
    continue_session=self._session_active,
    session_id=self._opencode_session_id,
    typing_content=self._typing_buffer.get_context(),
)
```

- [ ] **Step 5: Stop TypingBuffer on shutdown**

In `_force_quit_app` (~line 247), add before APMWorker stop:

```python
self._typing_buffer.stop()
```

- [ ] **Step 6: Run full test suite**

Run: `py -m pytest tests/ -v`
Expected: 268 passed, 2 failed (pre-existing memory_manager), 1 skipped

- [ ] **Step 7: Commit**

```bash
git add src/pet_window.py
git commit -m "feat: integrate TypingBuffer into PetWindow with debounced reactions"
```

---

### Task 6: Clean up diagnostic logs

**Files:**
- Modify: `src/response_manager.py`

- [ ] **Step 1: Remove POOL_DRAW and POOL_DECAY temporary INFO logs**

Revert the debug logging added earlier — the priority system is verified.

```python
    def draw(self, count: int = 1) -> list[dict]:
        if not self._items:
            if not self._refilling:
                self._request_refill()
            return []
        # ... remove POOL_DRAW log line ...
        weights = [max(1, item.get("priority", 3)) for item in self._items]
```

```python
    def decay(self):
        for item in self._items:
            item["priority"] = max(1, item.get("priority", 3) - 1)
        # Remove the before/after logging, keep method clean
```

- [ ] **Step 2: Run tests**

Run: `py -m pytest tests/test_response_manager.py -v`
Expected: PASS (14)

- [ ] **Step 3: Commit**

```bash
git add src/response_manager.py
git commit -m "chore: remove temporary priority diagnostic logs"
```

---

### Task 7: Squash-merge to master

**Files:**
- N/A — git workflow

- [ ] **Step 1: Switch to master, merge, push**

```bash
git checkout master
git merge --squash task-typing-buffer
git commit -m "feat: capture keystroke content into LLM prompt context"
git branch -D task-typing-buffer
```
