# Screen Reading, APM Priority & Autonomous Framing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Daemon the ability to read foreground window text, prioritize APM as primary signal, fix autonomous vs user response framing, relocate storage to `data/`, and capture CoT thoughts.

**Architecture:** Six tasks: (1) new `src/screen_reader.py` using comtypes UIA, (2) split `build_trigger()` into user/autonomous templates + wire dead delta injection, (3) re-point all path constants to `data/` dir, (4) preserve `thought` field through pipeline and log it, (5) `.gitignore` + final verify, (6) track and kill spawned opencode serve on shutdown.

**Tech Stack:** Python 3.11+, PyQt6, comtypes (new dep), Win32 ctypes, pytest

**No boot-time orphan sweep.** The port-binding check in `ensure_opencode_serve_running()` already prevents duplicate serves. Tracking the spawned PID and killing it on shutdown is sufficient — no heuristic needed.

---

### Task 1: Screen Reader Module

**Files:**
- Create: `src/screen_reader.py`
- Modify: `requirements.txt` (add comtypes)
- Test: `tests/test_screen_reader.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_screen_reader.py
from __future__ import annotations
import sys
from unittest.mock import patch, MagicMock


def test_returns_empty_on_non_windows():
    with patch.object(sys, "platform", "linux"):
        from src.screen_reader import ScreenReader
        result = ScreenReader.get_foreground_text()
        assert result == ""


def test_returns_empty_when_uia_import_fails():
    with patch.dict("sys.modules", {"comtypes": None}):
        import importlib
        import src.screen_reader as sr
        importlib.reload(sr)
        sr._UIA_AVAILABLE = False
        result = sr.ScreenReader.get_foreground_text()
        assert result == ""


def test_returns_empty_when_no_foreground_window():
    with patch.object(sys, "platform", "win32"):
        with patch("src.screen_reader.get_text_via_uia", return_value=""):
            with patch("src.screen_reader.get_text_via_wm_gettext", return_value=""):
                from src.screen_reader import ScreenReader
                result = ScreenReader.get_foreground_text()
                assert result == ""


def test_uia_returns_text():
    with patch.object(sys, "platform", "win32"):
        with patch("src.screen_reader.get_text_via_uia", return_value="Hello world"):
            from src.screen_reader import ScreenReader
            result = ScreenReader.get_foreground_text()
            assert result == "Hello world"


def test_wm_gettext_fallback():
    with patch.object(sys, "platform", "win32"):
        with patch("src.screen_reader.get_text_via_uia", return_value=""):
            with patch("src.screen_reader.get_text_via_wm_gettext", return_value="Fallback text"):
                from src.screen_reader import ScreenReader
                result = ScreenReader.get_foreground_text()
                assert result == "Fallback text"


def test_caps_at_2000_chars():
    long_text = "a" * 3000
    with patch.object(sys, "platform", "win32"):
        with patch("src.screen_reader.get_text_via_uia", return_value=long_text):
            from src.screen_reader import ScreenReader
            result = ScreenReader.get_foreground_text()
            assert len(result) <= 2000
            assert result == "a" * 2000
```

Run: `py -m pytest tests/test_screen_reader.py -v`
Expected: All FAIL (module not found)

- [ ] **Step 2: Write the screen reader module**

```python
# src/screen_reader.py
from __future__ import annotations
import logging
import sys

logger = logging.getLogger(__name__)

_UIA_AVAILABLE = False
try:
    import comtypes.client
    _UIA_AVAILABLE = True
except ImportError:
    pass


def get_text_via_uia() -> str:
    if not _UIA_AVAILABLE:
        return ""
    try:
        import ctypes
        from comtypes.client import CreateObject
        import comtypes

        comtypes.CoInitialize()
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return ""

        clsid = "{ff48dba4-60ef-4201-aa87-54103eef594e}"
        automation = CreateObject(clsid)
        element = automation.ElementFromHandle(hwnd)
        if not element:
            return ""

        pattern = element.GetCurrentPattern(10014)
        if not pattern:
            return ""

        text_range = pattern.DocumentRange
        if not text_range:
            return ""

        text = text_range.GetText(-1) or ""
        text = text.strip()
        return text[:2000]
    except Exception as e:
        logger.debug("get_text_via_uia failed: %s", e)
        return ""


def get_text_via_wm_gettext() -> str:
    try:
        import ctypes
        import ctypes.wintypes

        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return ""
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        text = buf.value.strip()
        return text[:2000]
    except Exception as e:
        logger.debug("get_text_via_wm_gettext failed: %s", e)
        return ""


class ScreenReader:
    @staticmethod
    def get_foreground_text() -> str:
        if sys.platform != "win32":
            return ""
        text = get_text_via_uia()
        if text:
            return text
        return get_text_via_wm_gettext()
```

- [ ] **Step 3: Add comtypes to requirements.txt**

Add `comtypes>=1.4.8` to `requirements.txt`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -m pytest tests/test_screen_reader.py -v`
Expected: All 6 PASS

- [ ] **Step 5: Commit**

```bash
git add src/screen_reader.py tests/test_screen_reader.py requirements.txt
git commit -m "feat: add ScreenReader module for foreground window text extraction via UIA"
```

---

### Task 2: Autonomous/User Framing + APM Priority

**Files:**
- Modify: `src/context_manager.py`
- Modify: `src/pet_window.py`
- Test: `tests/test_context_manager.py`

- [ ] **Step 1: Write the failing tests**

```python
# Add to tests/test_context_manager.py

def test_build_user_trigger_has_response_framing():
    cm = ContextManager.__new__(ContextManager)
    cm._snapshot = {}
    cm._full_injected = False
    prompt = cm.build_user_trigger("user_input", "hello", 50, 0.0)
    assert "responding directly" in prompt
    assert "User said: hello" in prompt


def test_build_autonomous_trigger_has_internal_monologue():
    cm = ContextManager.__new__(ContextManager)
    cm._snapshot = {}
    cm._full_injected = False
    prompt = cm.build_autonomous_trigger("active_chat", 50, 30.0)
    assert "internal monologue" in prompt or "thinking to herself" in prompt
    assert "NOT responding" in prompt


def test_autonomous_trigger_has_apm_as_primary_signal():
    cm = ContextManager.__new__(ContextManager)
    cm._snapshot = {}
    cm._full_injected = False
    prompt = cm.build_autonomous_trigger("active_chat", 50, 30.0)
    assert "primary signal" in prompt
    assert "APM: 50" in prompt


def test_user_trigger_has_apm_as_primary_signal():
    cm = ContextManager.__new__(ContextManager)
    cm._snapshot = {}
    cm._full_injected = False
    prompt = cm.build_user_trigger("user_input", "hello", 50, 0.0)
    assert "primary signal" in prompt


def test_autonomous_trigger_includes_screen_text():
    cm = ContextManager.__new__(ContextManager)
    cm._snapshot = {}
    cm._full_injected = False
    prompt = cm.build_autonomous_trigger("active_chat", 50, 30.0, screen_text="VS Code")
    assert "VS Code" in prompt


def test_user_trigger_includes_screen_text():
    cm = ContextManager.__new__(ContextManager)
    cm._snapshot = {}
    cm._full_injected = False
    prompt = cm.build_user_trigger("user_input", "hello", 50, 0.0, screen_text="Notepad")
    assert "Notepad" in prompt


def test_autonomous_trigger_has_5_dialogs_instruction():
    cm = ContextManager.__new__(ContextManager)
    cm._snapshot = {}
    cm._full_injected = False
    prompt = cm.build_autonomous_trigger("active_chat", 50, 30.0)
    assert "5 dialogs" in prompt


def test_user_trigger_has_single_json_object():
    cm = ContextManager.__new__(ContextManager)
    cm._snapshot = {}
    cm._full_injected = False
    prompt = cm.build_user_trigger("user_input", "hello", 50, 0.0)
    assert "single JSON object" in prompt
```

- [ ] **Step 2: Run new tests to verify they fail**

Run: `py -m pytest tests/test_context_manager.py::test_build_user_trigger_has_response_framing tests/test_context_manager.py::test_build_autonomous_trigger_has_internal_monologue tests/test_context_manager.py::test_autonomous_trigger_has_apm_as_primary_signal tests/test_context_manager.py::test_user_trigger_has_apm_as_primary_signal tests/test_context_manager.py::test_autonomous_trigger_includes_screen_text tests/test_context_manager.py::test_user_trigger_includes_screen_text tests/test_context_manager.py::test_autonomous_trigger_has_5_dialogs_instruction tests/test_context_manager.py::test_user_trigger_has_single_json_object -v`
Expected: FAIL (methods don't exist)

- [ ] **Step 3: Replace `build_trigger` with two methods in `context_manager.py`**

Replace the existing `build_trigger` method with two new methods. Keep the old method signature as a compatibility wrapper that calls the new ones.

Remove the old `build_trigger` method and add:

```python
def build_user_trigger(self, mode: str, user_input: str, apm: int,
                       idle_seconds: float, typing_content: str = "",
                       screen_text: str = "") -> str:
    self._last_activity = time.monotonic()
    lines = [
        "You are responding directly to the user.",
        f"Mode: {mode}",
        f"APM (actions per minute \u2014 primary signal): {apm}",
        f"Idle seconds: {int(idle_seconds)}",
    ]
    if user_input:
        lines.append(f"User said: {user_input}")
    if typing_content:
        lines.append("")
        lines.append(typing_content)
    if screen_text:
        lines.append("")
        lines.append(f"Screen: {screen_text}")
    lines.append("Respond with a single JSON object.")
    return "\n".join(lines)


def build_autonomous_trigger(self, mode: str, apm: int,
                             idle_seconds: float, typing_content: str = "",
                             screen_text: str = "") -> str:
    self._last_activity = time.monotonic()
    lines = [
        "Daemon is watching the user. She notices something worth thinking about.",
        "APM (actions per minute) is her main signal.",
        f"APM: {apm}",
        f"Mode: {mode}",
        f"Idle seconds: {int(idle_seconds)}",
    ]
    if typing_content:
        lines.append("")
        lines.append(typing_content)
    if screen_text:
        lines.append("")
        lines.append(f"Screen: {screen_text}")
    lines.append("")
    lines.append("She is thinking to herself. This is an internal monologue \u2014 she is NOT responding to the user.")
    lines.append("She should NOT say 'you asked' or 'you said' because the user did not say anything.")
    lines.append("Generate exactly 5 dialogs as a JSON array.")
    return "\n".join(lines)


def build_trigger(self, mode: str, user_input: str, apm: int,
                  idle_seconds: float, typing_content: str = "",
                  is_autonomous: bool = True) -> str:
    if is_autonomous:
        return self.build_autonomous_trigger(mode, apm, idle_seconds, typing_content)
    return self.build_user_trigger(mode, user_input, apm, idle_seconds, typing_content)
```

(Also add `screen_text: str = ""` to `snapshot_context` if needed — not needed, it's for APM/window tracking only.)

- [ ] **Step 4: Wire delta injection — call `inject_delta()` in `_dispatch_trigger()`**

`ContextManager.inject_delta()` (line 60 of context_manager.py) computes window/APM/memory/diary changes since last snapshot but nothing calls it at runtime. Fix: call it after building the trigger, prepend delta before trigger text. Trigger data (Mode, User said, APM) is fresher and takes precedence when it arrives later in the prompt.

In `pet_window.py::_dispatch_trigger()`, after the `build_trigger()` call and before the `OpencodeWorker` construction:

```python
        delta = self._context_manager.inject_delta(context_hint, apm)
        if delta:
            prompt = delta + "\n\n" + prompt
```

No wrapper method needed — `inject_delta` is already public. No changes to `context_manager.py`.

Add test in `tests/test_context_manager.py`:

```python
def test_inject_delta_returns_none_when_no_changes():
    cm = ContextManager.__new__(ContextManager)
    cm._snapshot = {"active_window": "", "apm_bucket": "low", "memory": {}, "diary_len": 0}
    cm._diary_injected_up_to = 0
    cm._full_injected = True
    result = cm.inject_delta("", 30)
    assert result is None


def test_inject_delta_returns_changes_when_window_changed():
    cm = ContextManager.__new__(ContextManager)
    cm._snapshot = {"active_window": "Old", "apm_bucket": "low", "memory": {}, "diary_len": 0}
    cm._diary_injected_up_to = 0
    cm._full_injected = True
    result = cm.inject_delta("New Window", 30)
    assert result is not None
    assert "New Window" in result
```

- [ ] **Step 5: Update `pet_window.py` — integrate screen reader + route to new methods**

In `_dispatch_trigger()` (around line 989):

Change:
```python
def _dispatch_trigger(self, mode: str, user_input: str = "",
                      context_hint: str = "", apm: int = 0,
                      idle_seconds: float = 0.0,
                      typing_content: str = "",
                      is_autonomous: bool = True) -> None:
```

To:
```python
def _dispatch_trigger(self, mode: str, user_input: str = "",
                      context_hint: str = "", apm: int = 0,
                      idle_seconds: float = 0.0,
                      typing_content: str = "",
                      is_autonomous: bool = True) -> None:
```

At the top of the method, after the `needs_reinjection` check and before `build_trigger`:

```python
        screen_text = ScreenReader.get_foreground_text()
```

Add import at top of file:
```python
from src.screen_reader import ScreenReader
```

Then change the `self._context_manager.build_trigger(...)` call to:

```python
        if is_autonomous:
            prompt = self._context_manager.build_autonomous_trigger(
                mode=mode, apm=apm,
                idle_seconds=idle_seconds, typing_content=typing_content,
                screen_text=screen_text,
            )
        else:
            prompt = self._context_manager.build_user_trigger(
                mode=mode, user_input=user_input, apm=apm,
                idle_seconds=idle_seconds, typing_content=typing_content,
                screen_text=screen_text,
            )
```

- [ ] **Step 6: Run all tests**

Run: `py -m pytest tests/test_context_manager.py tests/test_pet_window.py -v`
Expected: All pass (existing tests should still pass since `build_trigger` still works as compatibility wrapper)

- [ ] **Step 7: Commit**

```bash
git add src/context_manager.py src/pet_window.py tests/test_context_manager.py
git commit -m "feat: split autonomous/user trigger templates, wire delta injection, add APM priority and screen context"
```

---

### Task 3: Storage Relocation to `data/`

**Files:**
- Modify: `src/constants.py`
- Modify: `src/config.py`
- Modify: `src/persistence.py`
- Modify: `src/memory.py`
- Modify: `src/history.py`
- Modify: `src/pet_window.py`
- Modify: `src/response_manager.py`
- Modify: `daemon.py`

- [ ] **Step 1: Run existing tests to confirm baseline**

Run: `py -m pytest tests/ -v`
Expected: All 432 pass

- [ ] **Step 2: Add `STORAGE_DIR` and path constants to `src/constants.py`**

Add after the existing imports at top:
```python
STORAGE_DIR = Path(__file__).parent.parent / "data"
STORAGE_DIR.mkdir(exist_ok=True)
```

Replace:
```python
DIARY_PATH = str(Path.home() / ".daemon_diary.json")
```

With:
```python
MEMORY_PATH = STORAGE_DIR / ".daemon_memory.json"
HISTORY_PATH = STORAGE_DIR / ".daemon_history.json"
DIARY_PATH = STORAGE_DIR / ".daemon_diary.json"
STATE_PATH = STORAGE_DIR / ".daemon_state.json"
CONFIG_PATH = STORAGE_DIR / ".daemon_config.json"
LOCK_PATH = STORAGE_DIR / ".daemon.lock"
RESPONSE_CACHE_PATH = STORAGE_DIR / ".daemon_response_cache.json"
THOUGHTS_LOG_PATH = STORAGE_DIR / "thoughts.log"
```

Leave `DIARY_PATH` as is but change its value. Keep all as `str` for backward compat or change to `Path` — check what each consumer expects. (memory.py/history.py use `str`, config.py uses `Path`, persistence.py uses `str`.)

Make `DIARY_PATH` a `str` for backward compat:
```python
DIARY_PATH = str(STORAGE_DIR / ".daemon_diary.json")
```

- [ ] **Step 3: Update `src/config.py`**

Change line 10:
```python
_CONFIG_PATH = Path.home() / ".daemon_config.json"
```
To:
```python
from src.constants import CONFIG_PATH
_CONFIG_PATH = CONFIG_PATH
```

Remove the hardcoded `Path.home()` construction.

- [ ] **Step 4: Update `src/persistence.py`**

Change line 10:
```python
_DEFAULT_PATH = str(Path.home() / ".daemon_state.json")
```
To:
```python
from src.constants import STATE_PATH
_DEFAULT_PATH = STATE_PATH
```

- [ ] **Step 5: Update `src/memory.py`**

Change line 21:
```python
self._path = path or str(Path.home() / ".daemon_memory.json")
```
To:
```python
from src.constants import MEMORY_PATH
self._path = path or MEMORY_PATH
```

- [ ] **Step 6: Update `src/history.py`**

Change line 22:
```python
self._path = path or str(Path.home() / ".daemon_history.json")
```
To:
```python
from src.constants import HISTORY_PATH
self._path = path or HISTORY_PATH
```

- [ ] **Step 7: Update `src/pet_window.py`**

Change line 159:
```python
cache_path=str(Path.home() / ".daemon_response_cache.json"),
```
To:
```python
cache_path=str(RESPONSE_CACHE_PATH),
```

Add import at top of file alongside other constants from `src.constants`:
```python
RESPONSE_CACHE_PATH,
```

- [ ] **Step 8: Update `src/response_manager.py`**

Find where the cache path is constructed (it receives it from pet_window.py — check constructor). If it has a fallback default, update it to use the constant.

- [ ] **Step 9: Update `daemon.py`**

Change line 10:
```python
LOCK_PATH = Path.home() / ".daemon.lock"
```
To:
```python
from src.constants import LOCK_PATH
```

- [ ] **Step 10: Run tests**

Run: `py -m pytest tests/ -v`
Expected: All 432 pass (paths changed but no functional difference)

- [ ] **Step 11: Commit**

```bash
git add src/constants.py src/config.py src/persistence.py src/memory.py src/history.py src/pet_window.py src/response_manager.py daemon.py
git commit -m "refactor: relocate all storage paths from home dir to project data/ directory"
```

---

### Task 4: CoT Thought Capture

**Files:**
- Modify: `src/opencode_worker.py`
- Modify: `src/pet_window.py`
- Modify: `src/constants.py` (THOUGHTS_LOG_PATH already added in Task 3)
- Test: `tests/test_opencode_worker.py`

- [ ] **Step 1: Write the failing tests**

```python
# Add to tests/test_opencode_worker.py

def test_thought_field_preserved_in_normalized():
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker.__new__(OpencodeWorker)
    items = [{"dialogue": "hello", "action": "idle", "thought": "deep thought"}]
    result = worker._normalize_parsed(items)
    assert result[0]["thought"] == "deep thought"


def test_thought_field_defaults_to_empty():
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker.__new__(OpencodeWorker)
    items = [{"dialogue": "hello", "action": "idle"}]
    result = worker._normalize_parsed(items)
    assert result[0]["thought"] == ""
```

- [ ] **Step 2: Run new tests to verify they fail**

Run: `py -m pytest tests/test_opencode_worker.py::test_thought_field_preserved_in_normalized tests/test_opencode_worker.py::test_thought_field_defaults_to_empty -v`
Expected: FAIL (thought not in normalized dict)

- [ ] **Step 3: Update `_normalize_parsed` in `opencode_worker.py`**

Add `"thought"` to the returned dict:

```python
normalized.append({
    "dialogue": dialogue,
    "action": action,
    "target_x": target_x,
    "priority": priority,
    "thought": item.get("thought", ""),
})
```

- [ ] **Step 4: Verify the tests pass**

Run: `py -m pytest tests/test_opencode_worker.py::test_thought_field_preserved_in_normalized tests/test_opencode_worker.py::test_thought_field_defaults_to_empty -v`
Expected: Both PASS

- [ ] **Step 5: Add `_log_thought` and wire it in `pet_window.py`**

Add import at top:
```python
from datetime import datetime
from src.constants import DEBUG, THOUGHTS_LOG_PATH
```

Add new method after `_on_trigger_ready`:

```python
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
```

In `_on_trigger_ready` (line 1032), after `dialogue = first.get("dialogue", "")` and before `self._dispatch_structured`:

```python
        thought = first.get("thought", "")
        if thought:
            self._log_thought(thought, mode, dialogue)
```

- [ ] **Step 6: Add test for thought logging in `pet_window`**

```python
# Add to tests/test_pet_window.py

def test_thought_logged_when_debug_true(monkeypatch, qtbot):
    from src import constants
    monkeypatch.setattr(constants, "DEBUG", True)
    window = _create_window()
    window._log_thought("deep thought", "active_chat", "hello")
    log_path = constants.THOUGHTS_LOG_PATH
    assert log_path.exists()
    content = Path(log_path).read_text(encoding="utf-8")
    assert "deep thought" in content
    assert "Thought(11c)" in content
    # Cleanup
    log_path.unlink(missing_ok=True)


def test_thought_not_logged_when_debug_false(monkeypatch, qtbot):
    from src import constants
    monkeypatch.setattr(constants, "DEBUG", False)
    window = _create_window()
    window._log_thought("deep thought", "active_chat", "hello")
    log_path = constants.THOUGHTS_LOG_PATH
    assert not log_path.exists() or Path(log_path).read_text(encoding="utf-8") == ""
```

(Note: `_create_window` is a helper — check existing tests in `test_pet_window.py` for the fixture pattern used there.)

- [ ] **Step 7: Run all tests**

Run: `py -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 8: Commit**

```bash
git add src/opencode_worker.py src/pet_window.py tests/test_opencode_worker.py tests/test_pet_window.py
git commit -m "feat: preserve CoT thought field through pipeline with verbose logging"
```

---

### Task 5: .gitignore + Verify

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add `data/` to `.gitignore`**

Append to `.gitignore`:
```
# Local storage (memory, history, diary, config, lock, cache, thoughts)
data/
```

- [ ] **Step 2: Final full test run**

Run: `py -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: add data/ directory to gitignore"
```

---

### Task 6: Orphaned opencode Process Cleanup (Shutdown)

**Files:**
- Modify: `src/opencode_serve_manager.py`
- Modify: `daemon.py`

**Problem:** When Daemon exits, the `opencode serve` process spawned by `ensure_opencode_serve_running()` stays alive. It continues serving on port 4096, which is fine for reuse, but if Daemon stays closed, the orphan lingers.

**Fix:** Track the spawned PID in `opencode_serve_manager.py` and add a `stop_opencode_serve()` function called during Daemon shutdown.

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_opencode_serve_manager.py

def test_stop_opencode_serve_kills_tracked_pid(monkeypatch):
    import src.opencode_serve_manager as osm
    osm._SERVE_PID = 12345
    killed_pid = [None]

    def mock_run(cmd, **kw):
        if "taskkill" in str(cmd):
            killed_pid[0] = cmd[3] if len(cmd) > 3 else None
        return FakeCompletedProcess(stdout="", returncode=0)

    monkeypatch.setattr("subprocess.run", mock_run)
    osm.stop_opencode_serve()
    assert killed_pid[0] == "12345"
    assert osm._SERVE_PID is None


def test_stop_opencode_serve_noop_when_no_pid(monkeypatch):
    import src.opencode_serve_manager as osm
    osm._SERVE_PID = None
    called = [False]

    def mock_run(cmd, **kw):
        called[0] = True
        return FakeCompletedProcess(stdout="", returncode=0)

    monkeypatch.setattr("subprocess.run", mock_run)
    osm.stop_opencode_serve()
    assert not called[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest tests/test_opencode_serve_manager.py::test_stop_opencode_serve_kills_tracked_pid tests/test_opencode_serve_manager.py::test_stop_opencode_serve_noop_when_no_pid -v`
Expected: FAIL (function not defined)

- [ ] **Step 3: Add PID tracking and stop function to `opencode_serve_manager.py`**

Add module-level variable:
```python
_SERVE_PID: int | None = None
```

In `ensure_opencode_serve_running()`, after `proc = subprocess.Popen(...)`, store the PID:
```python
    global _SERVE_PID
    _SERVE_PID = proc.pid
```

Add stop function:
```python
def stop_opencode_serve() -> None:
    """Kill the tracked opencode serve process if it was spawned by us."""
    global _SERVE_PID
    if _SERVE_PID is None:
        return
    try:
        subprocess.run(
            ["taskkill", "/F", "/PID", str(_SERVE_PID)],
            capture_output=True, timeout=5,
        )
        logger.info("Killed opencode serve (PID %d)", _SERVE_PID)
    except Exception as e:
        logger.debug("stop_opencode_serve failed: %s", e)
    finally:
        _SERVE_PID = None
```

- [ ] **Step 4: Wire into shutdown in `daemon.py`**

In the shutdown sequence (around the `atexit` or signal handler that calls `_force_quit_app`), add:
```python
from src.opencode_serve_manager import stop_opencode_serve
stop_opencode_serve()
```

Called AFTER the session close but BEFORE the final logging shutdown. Best place: `daemon.py`'s shutdown block — right after `window.cleanup()` or equivalent.

- [ ] **Step 5: Run tests**

Run: `py -m pytest tests/test_opencode_serve_manager.py -v`
Expected: 10 tests pass (8 existing + 2 new for Task 6)

- [ ] **Step 6: Commit**

```bash
git add src/opencode_serve_manager.py daemon.py tests/test_opencode_serve_manager.py
git commit -m "fix: track and kill spawned opencode serve process on shutdown"
```

---

### Task 7: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `py -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 2: Quick smoke test**

Run: `py daemon.py --debug`
Expected: Starts in debug simulation, no errors. FSM ticks through states. Check `data/` directory exists with state files.
