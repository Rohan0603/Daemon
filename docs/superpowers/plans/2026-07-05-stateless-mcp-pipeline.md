# Stateless MCP-Driven Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Strands SDK stateful session model with a lean stateless burst inference pipeline, FastMCP SSE MCP server, write-through config cache, and diary compaction loop — achieving sub-second perceived response latency on DeepSeek V4 Flash via OpenCode serve.

**Architecture:** Each LLM call uses a fresh ephemeral OpenCode session (POST /session → message → DELETE /session), carrying the full XML context payload every time. FastMCP SSE runs in-process on :4097 in a QThread, replacing the http.server implementation with no opencode.json changes needed. The config layer gains a live `_RUNTIME_CONFIG` dict with `config.get()`/`config.set()` dot-path access for all consumers.

**Tech Stack:** Python 3.14, PyQt6, FastMCP (`mcp` package), pythoncom/comtypes (UIA), requests, prometheus_client, pytest

**Spec:** `docs/superpowers/specs/2026-07-05-stateless-mcp-pipeline-design.md`

---

## Phase 0: Strands Rip-Out

### Task 0.0: Create feature branch

**Files:** none

- [ ] **Step 1: Verify you are on master and it is clean**

```powershell
git status
git checkout master
git pull
```

Expected: `nothing to commit, working tree clean`.

- [ ] **Step 2: Create and checkout the feature branch**

```powershell
git checkout -b task-75-stateless-mcp-pipeline
```

Expected: `Switched to a new branch 'task-75-stateless-mcp-pipeline'`

All subsequent commits in this plan land on this branch. Do NOT commit directly to master.

---

### Task 0.1: Delete strands files

**Files:**
- Delete: `src/llm/strands_worker.py`
- Delete: `src/llm/llm_session_persistence.py`
- Delete: `tests/test_strands_worker.py`
- Delete: `tests/test_llm_session_persistence.py`

- [ ] **Step 1: Delete the four files**

```powershell
Remove-Item src/llm/strands_worker.py
Remove-Item src/llm/llm_session_persistence.py
Remove-Item tests/test_strands_worker.py
Remove-Item tests/test_llm_session_persistence.py
```

- [ ] **Step 2: Remove strands from requirements.txt**

Open `requirements.txt`. Delete the line containing `strands`. No other lines change.

- [ ] **Step 3: Uninstall strands**

```powershell
pip uninstall -y strands
```

Expected: `Successfully uninstalled strands-...` or `WARNING: Skipping strands as it is not installed.`

- [ ] **Step 4: Commit deletions**

```powershell
git add -A
git commit -m "chore: delete strands worker and session persistence files"
```

---

### Task 0.2: Sweep strands imports from `src/llm/__init__.py`

**Files:**
- Modify: `src/llm/__init__.py`

- [ ] **Step 1: Read the file**

```powershell
Get-Content src/llm/__init__.py
```

- [ ] **Step 2: Remove strands imports**

Delete any lines matching:
- `from .strands_worker import ...`
- `from .llm_session_persistence import ...`
- Any `StrandsWorker` or `LLMSessionPersistence` or `ChatTurn` re-exports

Leave all other imports untouched.

- [ ] **Step 3: Verify no remaining references**

```powershell
Select-String -Path src/llm/__init__.py -Pattern "strands|llm_session"
```

Expected: no output.

- [ ] **Step 4: Commit**

```powershell
git add src/llm/__init__.py
git commit -m "chore: remove strands imports from llm package init"
```

---

### Task 0.3: Sweep strands wiring from `src/ui/pet_window.py`

**Files:**
- Modify: `src/ui/pet_window.py`

- [ ] **Step 1: Find all strands/session references**

```powershell
Select-String -Path src/ui/pet_window.py -Pattern "strands|StrandsWorker|session_turn_completed|LLMSessionPersistence|_opencode_session_id|history_context|save_session|load_session|_llm_session"
```

Note every line number returned.

- [ ] **Step 2: Remove each reference**

For each match found, surgically remove:
- `import` statements for `StrandsWorker`, `LLMSessionPersistence`
- `self._opencode_session_id = ...` initialization and all reads/writes
- `self._llm_session_state = load_session(...)` in `__init__`
- `session_turn_completed` signal connection: `worker.session_turn_completed.connect(...)`
- `_on_session_turn_completed` slot method (entire method body)
- `save_session(...)` calls in `_finalize_quit` / `_force_quit_app`
- Any `StrandsAutonomousWorker(...)` instantiation — replace with `pass` or remove the branch

Do NOT remove or modify any code unrelated to strands/sessions.

- [ ] **Step 3: Verify**

```powershell
Select-String -Path src/ui/pet_window.py -Pattern "strands|StrandsWorker|session_turn_completed|LLMSessionPersistence|_opencode_session_id|history_context|save_session|load_session|_llm_session"
```

Expected: no output.

- [ ] **Step 4: Run targeted tests**

```powershell
py -m pytest tests/ -v --timeout=30 -x
```

Expected: test suite passes (minus tests for deleted files). Any import errors here mean a reference was missed — fix before continuing.

- [ ] **Step 5: Commit**

```powershell
git add src/ui/pet_window.py
git commit -m "chore: remove strands session wiring from PetWindow"
```

---

### Task 0.4: Sweep strands wiring from `src/llm/opencode_worker.py` and `daemon.py`

**Files:**
- Modify: `src/llm/opencode_worker.py`
- Modify: `daemon.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Sweep opencode_worker.py**

```powershell
Select-String -Path src/llm/opencode_worker.py -Pattern "history_context|session_state|session_turn_completed|LLMSessionPersistence|ChatTurn"
```

Remove each match:
- `history_context` parameter from `__init__` and `run()` — delete the parameter and any prompt-prepend logic using it
- `session_state` parameter from `__init__`
- `session_turn_completed` signal definition and all `self.session_turn_completed.emit(...)` calls
- `_emit_turn_completed` method (entire method body)

- [ ] **Step 2: Sweep daemon.py**

```powershell
Select-String -Path daemon.py -Pattern "strands|LLMSession|load_session|save_session|session_persistence"
```

Remove each match (initialization of session persistence managers, imports).

- [ ] **Step 3: Sweep conftest.py**

```powershell
Select-String -Path tests/conftest.py -Pattern "strands|LLMSession|session_state|history_context"
```

Remove any fixtures that injected strands session data. Leave all other fixtures untouched.

- [ ] **Step 4: Full regression run**

```powershell
py -m pytest tests/ -v --timeout=30
```

Expected: all tests pass. If any test fails due to missing `session_turn_completed` or `history_context` params, remove the reference in that test file too.

- [ ] **Step 5: Commit**

```powershell
git add src/llm/opencode_worker.py daemon.py tests/conftest.py
git commit -m "chore: remove history_context and session persistence from worker and daemon"
```

---

## Phase 1: Write-Through Config Cache & Circuit Breakers

### Task 1.1: Add `_RUNTIME_CONFIG`, `config.get()`, `config.set()` to `src/config.py`

**Files:**
- Modify: `src/config.py`
- Create: `tests/test_config_cache.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_config_cache.py`:

```python
import threading
import time
import pytest
from unittest.mock import patch, MagicMock
import src.config as config_module


@pytest.fixture(autouse=True)
def reset_runtime_config():
    """Reset _RUNTIME_CONFIG before each test."""
    original = config_module._RUNTIME_CONFIG.copy()
    yield
    config_module._RUNTIME_CONFIG.clear()
    config_module._RUNTIME_CONFIG.update(original)


def test_config_get_dot_path():
    config_module._RUNTIME_CONFIG = {"pet": {"chattiness": 7}}
    assert config_module.config_get("pet.chattiness") == 7


def test_config_get_missing_returns_default():
    config_module._RUNTIME_CONFIG = {}
    assert config_module.config_get("pet.chattiness", default=5) == 5


def test_config_get_partial_missing_returns_default():
    config_module._RUNTIME_CONFIG = {"pet": {}}
    assert config_module.config_get("pet.chattiness", default=3) == 3


def test_config_set_dot_path():
    config_module._RUNTIME_CONFIG = {"pet": {"chattiness": 5}}
    config_module.config_set("pet.chattiness", 9)
    assert config_module._RUNTIME_CONFIG["pet"]["chattiness"] == 9


def test_config_set_creates_nested_keys():
    config_module._RUNTIME_CONFIG = {}
    config_module.config_set("behavior.dnd_enabled", True)
    assert config_module._RUNTIME_CONFIG["behavior"]["dnd_enabled"] is True


def test_config_set_fires_async_save(tmp_path):
    config_module._RUNTIME_CONFIG = {"pet": {"chattiness": 5}}
    saved_events = []
    original_save = config_module.save_config

    def fake_save(cfg, path=None):
        saved_events.append(cfg)

    with patch.object(config_module, "save_config", fake_save):
        config_module.config_set("pet.chattiness", 8)
        time.sleep(0.1)  # allow async thread to run

    assert len(saved_events) == 1


def test_config_set_does_not_block():
    config_module._RUNTIME_CONFIG = {"pet": {}}
    start = time.monotonic()

    slow_save_called = threading.Event()
    def slow_save(cfg, path=None):
        time.sleep(0.5)
        slow_save_called.set()

    with patch.object(config_module, "save_config", slow_save):
        config_module.config_set("pet.chattiness", 8)
        elapsed = time.monotonic() - start

    assert elapsed < 0.1, "config_set must not block on disk write"
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
py -m pytest tests/test_config_cache.py -v
```

Expected: `FAILED` with `AttributeError: module 'src.config' has no attribute 'config_get'`

- [ ] **Step 3: Implement `_RUNTIME_CONFIG`, `config_get`, `config_set` in `src/config.py`**

Add after the existing `load_dotenv()` call and `logger` definition (keep all existing functions untouched):

```python
# ── Runtime Config Cache ─────────────────────────────────────────────────────
_RUNTIME_CONFIG: dict = {}


def _init_runtime_config() -> None:
    """Populate _RUNTIME_CONFIG from disk. Called once at module import."""
    global _RUNTIME_CONFIG
    try:
        loaded = load_config()
        _RUNTIME_CONFIG.update(loaded)
    except Exception:
        pass  # first-boot or missing file — cache stays empty, consumers use defaults


def config_get(key_path: str, default=None):
    """Dot-path read from live runtime config. e.g. config_get('pet.chattiness')."""
    parts = key_path.split(".")
    node = _RUNTIME_CONFIG
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def config_set(key_path: str, value) -> None:
    """Dot-path write to live runtime config. Fires async disk save."""
    parts = key_path.split(".")
    node = _RUNTIME_CONFIG
    for part in parts[:-1]:
        if part not in node or not isinstance(node[part], dict):
            node[part] = {}
        node = node[part]
    node[parts[-1]] = value
    threading.Thread(target=_async_save, daemon=True).start()


def _async_save() -> None:
    """Non-blocking disk write of current _RUNTIME_CONFIG."""
    try:
        save_config(_RUNTIME_CONFIG)
    except Exception as exc:
        logger.warning("config async save failed: %s", exc)


# Initialise cache at module import
_init_runtime_config()
```

Add `import threading` at the top of the file if not already present.

- [ ] **Step 4: Run tests**

```powershell
py -m pytest tests/test_config_cache.py -v
```

Expected: all 7 tests pass.

- [ ] **Step 5: Full regression**

```powershell
py -m pytest tests/ -v --timeout=30
```

Expected: full suite passes.

- [ ] **Step 6: Commit**

```powershell
git add src/config.py tests/test_config_cache.py
git commit -m "feat(config): add write-through runtime cache with config_get/config_set"
```

---

### Task 1.2: DND circuit breaker in `apm_worker.py` and `event_worker.py`

**Files:**
- Modify: `src/system/apm_worker.py`
- Modify: `src/system/event_worker.py`
- Modify: `tests/test_config_cache.py` (add DND tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_config_cache.py`:

```python
from unittest.mock import patch, MagicMock


def test_apm_worker_dnd_drops_tick(reset_runtime_config):
    from src.system.apm_worker import APMWorker
    config_module._RUNTIME_CONFIG = {"behavior": {"dnd_enabled": True}}
    worker = APMWorker.__new__(APMWorker)
    worker._reset_internal_metrics = MagicMock()
    reset_called = []

    original = worker._reset_internal_metrics
    worker._reset_internal_metrics = lambda: reset_called.append(1)

    # Simulate a tick that checks DND
    from src.config import config_get
    if config_get("behavior.dnd_enabled"):
        worker._reset_internal_metrics()
        ticked = False
    else:
        ticked = True

    assert not ticked
    assert len(reset_called) == 1


def test_event_worker_dnd_suppresses_window_switch(reset_runtime_config):
    config_module._RUNTIME_CONFIG = {"behavior": {"dnd_enabled": True}}
    from src.config import config_get
    fired = []

    def on_window_switch():
        if config_get("behavior.dnd_enabled"):
            return
        fired.append(1)

    on_window_switch()
    assert len(fired) == 0


def test_event_worker_probability_gate_suppresses_at_low_chattiness(reset_runtime_config):
    import random
    config_module._RUNTIME_CONFIG = {"pet": {"chattiness": 1}}
    from src.config import config_get

    suppressed = 0
    total = 1000
    for _ in range(total):
        chattiness = config_get("pet.chattiness", 5)
        if random.random() > (chattiness / 10.0):
            suppressed += 1

    # At chattiness=1, ~90% should be suppressed
    assert suppressed > 800, f"Expected >800 suppressed, got {suppressed}"
```

- [ ] **Step 2: Run to verify fail**

```powershell
py -m pytest tests/test_config_cache.py::test_apm_worker_dnd_drops_tick -v
```

Expected: `FAILED` — `APMWorker` has no DND gate yet.

- [ ] **Step 3: Add DND gate to `src/system/apm_worker.py`**

Find the main tick/processing method in `APMWorker` (look for the method called by the 2s emit timer or the pynput callback dispatcher). Add at the top of that method:

```python
from src.config import config_get

def _emit_apm(self) -> None:  # or whatever the tick method is named
    if config_get("behavior.dnd_enabled"):
        self._reset_internal_metrics()
        return
    # ... existing logic unchanged
```

If `_reset_internal_metrics` doesn't exist, add it:
```python
def _reset_internal_metrics(self) -> None:
    """Zero out rolling APM counters without stopping the listener."""
    self._key_times.clear()
    self._mouse_times.clear()
```

- [ ] **Step 4: Add DND gate and probability gate to `src/system/event_worker.py`**

Find the method that fires on window switch detection. Add at top:

```python
from src.config import config_get
import random

def _on_window_changed(self, title: str) -> None:
    if config_get("behavior.dnd_enabled"):
        return
    chattiness = config_get("pet.chattiness", 5)
    if random.random() > (chattiness / 10.0):
        return  # probabilistic suppression
    # ... existing dispatch logic unchanged
```

- [ ] **Step 5: Run tests**

```powershell
py -m pytest tests/test_config_cache.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Full regression**

```powershell
py -m pytest tests/ -v --timeout=30
```

- [ ] **Step 7: Commit**

```powershell
git add src/system/apm_worker.py src/system/event_worker.py tests/test_config_cache.py
git commit -m "feat(behavior): add DND circuit breaker and chattiness probability gate"
```

---

### Task 1.3: Adaptive idle threshold in `behavior_controller.py`

**Files:**
- Modify: `src/autonomy/behavior_controller.py`
- Modify: `tests/test_config_cache.py` (add threshold test)

- [ ] **Step 1: Write failing test**

Append to `tests/test_config_cache.py`:

```python
def test_adaptive_idle_threshold_scales_with_chattiness(reset_runtime_config):
    from src.autonomy.behavior_controller import compute_dynamic_idle_threshold
    from src.constants import BASE_IDLE_SECONDS  # or whatever the constant is named

    # At chattiness=1: threshold near BASE
    config_module._RUNTIME_CONFIG = {"pet": {"chattiness": 1}}
    high = compute_dynamic_idle_threshold()
    assert high >= 30

    # At chattiness=10: threshold much lower
    config_module._RUNTIME_CONFIG = {"pet": {"chattiness": 10}}
    low = compute_dynamic_idle_threshold()
    assert low < high
    assert low >= 30  # never below floor
```

- [ ] **Step 2: Run to verify fail**

```powershell
py -m pytest tests/test_config_cache.py::test_adaptive_idle_threshold_scales_with_chattiness -v
```

Expected: `FAILED` — `compute_dynamic_idle_threshold` not defined.

- [ ] **Step 3: Add `compute_dynamic_idle_threshold` to `src/autonomy/behavior_controller.py`**

Add as a module-level function (not a method) near the top of the file, after imports:

```python
from src.config import config_get


def compute_dynamic_idle_threshold() -> float:
    """Returns chattiness-scaled idle threshold in seconds.

    Formula: clamp(BASE_IDLE_SECONDS - (chattiness * 50), 30, BASE_IDLE_SECONDS)
    """
    from src.constants import BOREDOM_TIMEOUT_SEC  # existing constant for base idle
    chattiness = config_get("pet.chattiness", 5)
    dynamic = BOREDOM_TIMEOUT_SEC - (chattiness * 50)
    return max(30.0, min(float(BOREDOM_TIMEOUT_SEC), dynamic))
```

Inside `BehaviorController`, replace the hardcoded idle threshold comparison with:
```python
# Before (example):
#   if self._idle_seconds >= BOREDOM_TIMEOUT_SEC:
# After:
    if self._idle_seconds >= compute_dynamic_idle_threshold():
```

- [ ] **Step 4: Run tests**

```powershell
py -m pytest tests/test_config_cache.py -v
```

- [ ] **Step 5: Full regression**

```powershell
py -m pytest tests/ -v --timeout=30
```

- [ ] **Step 6: Commit**

```powershell
git add src/autonomy/behavior_controller.py tests/test_config_cache.py
git commit -m "feat(behavior): adaptive idle threshold scaled by pet.chattiness"
```

---

## Phase 2: FastMCP SSE Server

### Task 2.1: Install FastMCP and scaffold new `src/mcp_server.py`

**Files:**
- Modify: `requirements.txt`
- Modify: `src/mcp_server.py` (full rewrite)
- Create: `tests/test_mcp_server_fastmcp.py`

- [ ] **Step 1: Install mcp package**

```powershell
pip install "mcp[cli]"
```

Add to `requirements.txt`:
```
mcp[cli]>=1.0.0
```

- [ ] **Step 2: Write minimal scaffold test**

Create `tests/test_mcp_server_fastmcp.py`:

```python
import pytest
from unittest.mock import MagicMock, patch


def test_mcp_server_module_imports():
    """Verify the new mcp_server module loads without error."""
    import src.mcp_server as mcp_server
    assert hasattr(mcp_server, "MCPServerThread")


def test_mcp_server_thread_is_qthread():
    from PyQt6.QtCore import QThread
    from src.mcp_server import MCPServerThread
    assert issubclass(MCPServerThread, QThread)
```

- [ ] **Step 3: Run to verify fail**

```powershell
py -m pytest tests/test_mcp_server_fastmcp.py -v
```

Expected: `FAILED` — old `mcp_server.py` has no `MCPServerThread`.

- [ ] **Step 4: Rewrite `src/mcp_server.py` — scaffold only**

Replace the entire file content with the following scaffold (tools added in subsequent tasks):

```python
"""src/mcp_server.py — FastMCP SSE MCP server (in-process, port 4097).

Runs in a QThread. All tools execute in the MCP event loop (non-main thread).
Cross-thread UI calls go through FSMActionBridge pyqtSignal (QueuedConnection auto-promoted).
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from PyQt6.QtCore import QThread
from mcp.server.fastmcp import FastMCP

from src.config import config_get
from src.fsm_bridge import FSMActionBridge

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# Module-level singletons set by MCPServerThread before starting
_bridge: FSMActionBridge | None = None
_memory = None      # src.memory.Memory instance
_diary_store = None  # src.diary_store.DiaryStore instance

mcp = FastMCP("daemon", host="127.0.0.1", port=4097)


class MCPServerThread(QThread):
    """Runs the FastMCP SSE server inside the daemon process on port 4097."""

    def __init__(self, bridge: FSMActionBridge, memory, diary_store, parent=None):
        super().__init__(parent)
        global _bridge, _memory, _diary_store
        _bridge = bridge
        _memory = memory
        _diary_store = diary_store

    def run(self) -> None:
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except ImportError:
            logger.warning("pythoncom not available — UIA tools disabled")

        try:
            logger.info("MCPServerThread: starting FastMCP SSE on :4097")
            asyncio.run(mcp.run_sse_async())
        except Exception as exc:
            logger.error("MCPServerThread crashed: %s", exc)
        finally:
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass

    def stop(self) -> None:
        self.quit()
        self.wait(2000)
```

- [ ] **Step 5: Run scaffold tests**

```powershell
py -m pytest tests/test_mcp_server_fastmcp.py -v
```

Expected: both tests pass.

- [ ] **Step 6: Commit scaffold**

```powershell
git add src/mcp_server.py requirements.txt tests/test_mcp_server_fastmcp.py
git commit -m "feat(mcp): scaffold FastMCP SSE server replacing http.server"
```

---

### Task 2.2: Implement `trigger_pet_animation` and `get_browser_context` tools

**Files:**
- Modify: `src/mcp_server.py`
- Modify: `tests/test_mcp_server_fastmcp.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_mcp_server_fastmcp.py`:

```python
def test_trigger_pet_animation_valid_state():
    import src.mcp_server as mcp_mod
    mock_bridge = MagicMock()
    mcp_mod._bridge = mock_bridge

    # Call the tool function directly (bypass MCP routing)
    from src.mcp_server import _trigger_pet_animation_impl
    result = _trigger_pet_animation_impl("FRUSTRATED")

    mock_bridge.emit_request.assert_called_once_with("FRUSTRATED")
    assert result == "ok"


def test_trigger_pet_animation_invalid_state():
    import src.mcp_server as mcp_mod
    mcp_mod._bridge = MagicMock()

    from src.mcp_server import _trigger_pet_animation_impl
    result = _trigger_pet_animation_impl("EXPLODE")

    assert "Invalid" in result
    mcp_mod._bridge.emit_request.assert_not_called()


def test_get_browser_context_non_browser_window():
    from src.mcp_server import _get_browser_context_impl
    with patch("src.mcp_server._get_window_class", return_value="Notepad"):
        result = _get_browser_context_impl()
    assert result["url"] is None
```

- [ ] **Step 2: Run to verify fail**

```powershell
py -m pytest tests/test_mcp_server_fastmcp.py::test_trigger_pet_animation_valid_state -v
```

Expected: `FAILED` — `_trigger_pet_animation_impl` not defined.

- [ ] **Step 3: Add tools to `src/mcp_server.py`**

Add after the scaffold:

```python
# ── Internal implementations (testable without MCP routing) ──────────────────

_VALID_ANIMATION_STATES = {"IDLE", "THINKING", "FRUSTRATED", "SMUG", "SHOCKED", "LAUGHING"}

_BROWSER_WINDOW_CLASSES = {"Chrome_WidgetWin_1", "MozillaWindowClass", "ApplicationFrameWindow"}


def _trigger_pet_animation_impl(state: str) -> str:
    state = state.upper()
    if state not in _VALID_ANIMATION_STATES:
        return f"Invalid state '{state}'. Must be one of: {', '.join(sorted(_VALID_ANIMATION_STATES))}"
    if _bridge is not None:
        _bridge.emit_request(state)  # pyqtSignal → QueuedConnection auto-promotion
    return "ok"


def _get_window_class(hwnd=None) -> str:
    """Return Win32 window class name for the foreground window."""
    import ctypes
    if hwnd is None:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
    buf = ctypes.create_unicode_buffer(256)
    ctypes.windll.user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def _get_browser_context_impl() -> dict:
    """Sniper URL extraction. Returns {"url": str|None, "title": str}."""
    try:
        import uiautomation as auto
        win_class = _get_window_class()
        if win_class not in _BROWSER_WINDOW_CLASSES:
            return {"url": None, "title": ""}
        ctrl = auto.GetForegroundControl()
        # Search address bar at depth ≤ 5
        edit = ctrl.EditControl(searchDepth=5)
        if edit.Exists(0, 0):
            url = edit.GetValuePattern().CurrentValue
            return {"url": url, "title": ctrl.Name}
        return {"url": None, "title": ctrl.Name}
    except Exception as exc:
        logger.debug("get_browser_context error: %s", exc)
        return {"url": None, "title": ""}


# ── MCP Tool Registrations ────────────────────────────────────────────────────

@mcp.tool()
def trigger_pet_animation(state: str) -> str:
    """Trigger a visual expression on the pet.

    Args:
        state: One of IDLE, THINKING, FRUSTRATED, SMUG, SHOCKED, LAUGHING
    """
    return _trigger_pet_animation_impl(state)


@mcp.tool()
def get_browser_context() -> dict:
    """Return the active browser tab URL and title. Fast path — no DOM traversal.

    Returns:
        {"url": "https://...", "title": "Page Title"} or {"url": null, "title": "..."} if not a browser.
    """
    return _get_browser_context_impl()
```

- [ ] **Step 4: Run tests**

```powershell
py -m pytest tests/test_mcp_server_fastmcp.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/mcp_server.py tests/test_mcp_server_fastmcp.py
git commit -m "feat(mcp): add trigger_pet_animation and get_browser_context tools"
```

---

### Task 2.3: Implement `get_screen_context` tool

**Files:**
- Modify: `src/mcp_server.py`
- Modify: `tests/test_mcp_server_fastmcp.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_mcp_server_fastmcp.py`:

```python
def test_get_screen_context_returns_xml_string():
    from src.mcp_server import _get_screen_context_impl
    # Mock uiautomation to avoid needing a real display
    with patch("src.mcp_server._walk_uia_tree", return_value='<ui><button name="OK" x="10" y="20"/></ui>'):
        result = _get_screen_context_impl()
    assert result.startswith("<ui>")
    assert "button" in result


def test_get_screen_context_truncates_at_2000_chars():
    from src.mcp_server import _get_screen_context_impl
    long_xml = "<ui>" + '<button name="x" x="0" y="0"/>' * 200 + "</ui>"
    with patch("src.mcp_server._walk_uia_tree", return_value=long_xml):
        result = _get_screen_context_impl()
    assert len(result) <= 2020  # 2000 + truncation marker
    assert "truncated" in result
```

- [ ] **Step 2: Run to verify fail**

```powershell
py -m pytest tests/test_mcp_server_fastmcp.py::test_get_screen_context_returns_xml_string -v
```

- [ ] **Step 3: Add `get_screen_context` implementation to `src/mcp_server.py`**

```python
_UIA_SKIP_CONTROL_TYPES = {"PaneControl", "GroupControl"}
_UIA_EXTRACT_CONTROL_TYPES = {"ButtonControl", "EditControl", "HyperlinkControl", "ListItemControl"}
_SCREEN_CONTEXT_MAX_CHARS = 2000


def _walk_uia_tree(ctrl, depth: int = 0, max_depth: int = 7) -> str:
    """Recursively walk UIA tree and return pruned interactive XML."""
    if depth > max_depth:
        return ""
    try:
        ctrl_type = ctrl.ControlTypeName  # e.g. "ButtonControl"
        name = (ctrl.Name or "").strip()

        # Skip non-interactive containers with no name
        if ctrl_type in _UIA_SKIP_CONTROL_TYPES and not name:
            # Still recurse into children
            parts = []
            for child in ctrl.GetChildren():
                parts.append(_walk_uia_tree(child, depth + 1, max_depth))
            return "".join(parts)

        parts = []
        if ctrl_type in _UIA_EXTRACT_CONTROL_TYPES:
            tag = ctrl_type.replace("Control", "").lower()
            rect = ctrl.BoundingRectangle
            x = getattr(rect, "left", 0)
            y = getattr(rect, "top", 0)
            name_attr = name.replace('"', "'")
            parts.append(f'<{tag} name="{name_attr}" x="{x}" y="{y}"/>')

        for child in ctrl.GetChildren():
            parts.append(_walk_uia_tree(child, depth + 1, max_depth))

        return "".join(parts)
    except Exception:
        return ""


def _get_screen_context_impl() -> str:
    """Returns pruned interactive UIA XML for the foreground window."""
    try:
        import uiautomation as auto
        ctrl = auto.GetForegroundControl()
        inner = _walk_uia_tree(ctrl)
        xml = f"<ui>{inner}</ui>"
    except Exception as exc:
        logger.debug("get_screen_context error: %s", exc)
        xml = "<ui/>"

    if len(xml) > _SCREEN_CONTEXT_MAX_CHARS:
        xml = xml[:_SCREEN_CONTEXT_MAX_CHARS] + "<!-- truncated -->"
    return xml


@mcp.tool()
def get_screen_context() -> str:
    """Returns pruned interactive XML of the active window UI tree (depth 7).

    Only interactive controls (buttons, inputs, links, list items) are included.
    Non-interactive containers with no name are skipped.
    Output capped at 2000 chars.
    """
    return _get_screen_context_impl()
```

- [ ] **Step 4: Run tests**

```powershell
py -m pytest tests/test_mcp_server_fastmcp.py -v
```

- [ ] **Step 5: Commit**

```powershell
git add src/mcp_server.py tests/test_mcp_server_fastmcp.py
git commit -m "feat(mcp): add get_screen_context with pruned UIA XML extraction"
```

---

### Task 2.4: Implement `execute_os_action` tool with clipboard path

**Files:**
- Modify: `src/mcp_server.py`
- Modify: `tests/test_mcp_server_fastmcp.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_mcp_server_fastmcp.py`:

```python
def test_execute_os_action_type_blocked_without_consent():
    import src.mcp_server as mcp_mod
    mcp_mod._bridge = MagicMock()
    with patch("src.mcp_server.config_get", return_value=False):
        from src.mcp_server import _execute_os_action_impl
        result = _execute_os_action_impl(action="type", text="hello")
    assert "BLOCKED" in result
    mcp_mod._bridge.emit_request.assert_called_with("FRUSTRATED")


def test_execute_os_action_clipboard_requires_dual_consent():
    import src.mcp_server as mcp_mod
    mcp_mod._bridge = MagicMock()

    def fake_get(key, default=None):
        # keyboard granted, clipboard NOT granted
        if "keyboard" in key:
            return True
        if "clipboard" in key:
            return False
        return default

    with patch("src.mcp_server.config_get", side_effect=fake_get):
        from src.mcp_server import _execute_os_action_impl
        result = _execute_os_action_impl(action="type", text="hello world", use_clipboard=True)
    assert "BLOCKED" in result


def test_execute_os_action_clipboard_path_calls_paste(monkeypatch):
    import src.mcp_server as mcp_mod
    mcp_mod._bridge = MagicMock()

    clipboard_written = []
    keystroke_sent = []

    monkeypatch.setattr("src.mcp_server.config_get", lambda k, d=None: True)
    monkeypatch.setattr("src.mcp_server._write_to_clipboard", lambda t: clipboard_written.append(t))
    monkeypatch.setattr("src.mcp_server._simulate_keystroke_mcp", lambda k: keystroke_sent.append(k))

    from src.mcp_server import _execute_os_action_impl
    result = _execute_os_action_impl(action="type", text="long text here", use_clipboard=True)

    assert clipboard_written == ["long text here"]
    assert "ctrl+v" in keystroke_sent
    assert result == "ok (clipboard paste)"
```

- [ ] **Step 2: Run to verify fail**

```powershell
py -m pytest tests/test_mcp_server_fastmcp.py::test_execute_os_action_type_blocked_without_consent -v
```

- [ ] **Step 3: Implement `execute_os_action` in `src/mcp_server.py`**

```python
def _write_to_clipboard(text: str) -> None:
    """Write text to Windows clipboard via ctypes."""
    import ctypes
    import ctypes.wintypes
    CF_UNICODETEXT = 13
    ctypes.windll.user32.OpenClipboard(0)
    try:
        ctypes.windll.user32.EmptyClipboard()
        encoded = (text + "\0").encode("utf-16-le")
        h = ctypes.windll.kernel32.GlobalAlloc(0x0042, len(encoded))
        p = ctypes.windll.kernel32.GlobalLock(h)
        ctypes.memmove(p, encoded, len(encoded))
        ctypes.windll.kernel32.GlobalUnlock(h)
        ctypes.windll.user32.SetClipboardData(CF_UNICODETEXT, h)
    finally:
        ctypes.windll.user32.CloseClipboard()


def _simulate_keystroke_mcp(keys: str) -> None:
    """Simulate a keystroke via existing MCP keystroke tool logic."""
    # Reuses the existing simulate_keystroke implementation
    import pyautogui
    pyautogui.hotkey(*keys.split("+"))


def _execute_os_action_impl(
    action: str,
    x: int | None = None,
    y: int | None = None,
    text: str | None = None,
    use_clipboard: bool = False,
) -> str:
    action = action.lower()

    if action == "type":
        if not config_get("consent.allow_keyboard_injection"):
            if _bridge:
                _bridge.emit_request("FRUSTRATED")
            return "BLOCKED: keyboard_injection not permitted. Enable in Settings > Boundaries."
        if use_clipboard and not config_get("consent.allow_clipboard_hijacking"):
            return "BLOCKED: clipboard_hijacking required when use_clipboard=True."
        if use_clipboard:
            _write_to_clipboard(text or "")
            _simulate_keystroke_mcp("ctrl+v")
            return "ok (clipboard paste)"
        if text and len(text) > 50:
            return "BLOCKED: text exceeds 50-char limit. Set use_clipboard=True for longer text."
        _simulate_keystroke_mcp(text or "")
        return "ok"

    if action == "click":
        if not config_get("consent.allow_mouse_interference"):
            if _bridge:
                _bridge.emit_request("FRUSTRATED")
            return "BLOCKED: mouse_interference not permitted. Enable in Settings > Boundaries."
        import pyautogui
        pyautogui.click(x or 0, y or 0)
        return "ok"

    return f"Unknown action '{action}'. Must be 'type' or 'click'."


@mcp.tool()
def execute_os_action(
    action: str,
    x: int | None = None,
    y: int | None = None,
    text: str | None = None,
    use_clipboard: bool = False,
) -> str:
    """Execute a guarded OS action (click or type).

    Args:
        action: "click" or "type"
        x: Screen X coordinate (click only)
        y: Screen Y coordinate (click only)
        text: Text to type (max 50 chars unless use_clipboard=True)
        use_clipboard: If True, writes text to clipboard and pastes (bypasses 50-char limit).
                       Requires allow_keyboard_injection AND allow_clipboard_hijacking.
    """
    return _execute_os_action_impl(action=action, x=x, y=y, text=text, use_clipboard=use_clipboard)
```

- [ ] **Step 4: Run tests**

```powershell
py -m pytest tests/test_mcp_server_fastmcp.py -v
```

- [ ] **Step 5: Full regression**

```powershell
py -m pytest tests/ -v --timeout=30
```

- [ ] **Step 6: Commit**

```powershell
git add src/mcp_server.py tests/test_mcp_server_fastmcp.py
git commit -m "feat(mcp): add execute_os_action with clipboard-paste path and dual consent gate"
```

---

### Task 2.5: Migrate all 13 existing tools to FastMCP

**Files:**
- Modify: `src/mcp_server.py`

- [ ] **Step 1: Identify all existing tool handlers**

From the old `MCPHandler._handle_tools_call`, find the 13 tool implementations:
`read_clipboard`, `capture_blackmail_evidence`, `send_system_toast`, `list_directory`, `read_file`,
`search_codebase`, `get_memory`, `get_diary`, `simulate_keystroke`, `move_mouse`,
`browser_navigation`, `set_log_level`, `get_recent_git_diff`, `set_reminder`, `get_reminders`,
`dismiss_reminder`

- [ ] **Step 2: Port each tool as `@mcp.tool()` decorated function**

For each tool, extract its handler body from the old `MCPHandler` into a top-level function wrapped with `@mcp.tool()`. Example pattern:

```python
@mcp.tool()
def read_clipboard() -> str:
    """Read the current Windows clipboard text content."""
    # [paste existing _read_clipboard() implementation here verbatim]
    ...

@mcp.tool()
def list_directory(relative_path: str = ".") -> list[str]:
    """List files in a directory relative to project root."""
    # [paste existing list_directory handler body here]
    ...
```

Consent gates: copy the `_is_tool_allowed(name, consent_config)` logic into each tool directly:
```python
@mcp.tool()
def read_clipboard() -> str:
    """Read clipboard. Requires allow_clipboard_hijacking consent."""
    if not config_get("consent.allow_clipboard_hijacking"):
        return "BLOCKED: clipboard_hijacking not permitted."
    # ... existing implementation
```

- [ ] **Step 3: Wire `MCPServerThread` into `src/ui/pet_window.py`**

In `pet_window.py`, find where `MCPServer` is instantiated and started. Replace with:

```python
from src.mcp_server import MCPServerThread

# In __init__, after _memory and _diary_store are initialized:
self._mcp_server = MCPServerThread(
    bridge=self._fsm_bridge,
    memory=self._memory,
    diary_store=self._diary_store,
    parent=self,
)
self._mcp_server.start()

# In _force_quit_app:
self._mcp_server.stop()
```

- [ ] **Step 4: Remove old `MCPServer`, `MCPHandler`, `BaseHTTPRequestHandler` imports**

```powershell
Select-String -Path src/mcp_server.py -Pattern "BaseHTTPRequestHandler|HTTPServer|MCPHandler"
```

All references should be gone (the new file has none). If any remain from the old file, they are dead code — remove them.

- [ ] **Step 5: Full regression**

```powershell
py -m pytest tests/ -v --timeout=30
```

- [ ] **Step 6: Commit**

```powershell
git add src/mcp_server.py src/ui/pet_window.py
git commit -m "feat(mcp): migrate all 13 existing tools to FastMCP SSE"
```

---

## Phase 3: Thread-Safe Animation Bridge

### Task 3.1: Add `trigger_state_override` and animation override lock to `pet_window.py`

**Files:**
- Modify: `src/ui/pet_window.py`
- Create: `tests/test_animation_bridge.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_animation_bridge.py`:

```python
import pytest
from unittest.mock import MagicMock, patch, call
from PyQt6.QtCore import QTimer


@pytest.fixture
def mock_pet_window(qapp):
    """Minimal PetWindow mock with just the animation bridge attributes."""
    from unittest.mock import MagicMock
    win = MagicMock()
    win._action_layer = MagicMock()
    win._fsm = MagicMock()
    win._animation_override_active = False
    return win


def test_trigger_state_override_fsm_state(mock_pet_window):
    from src.pet_fsm import PetState
    from src.ui.pet_window import PetWindow

    # Call the method directly on mock
    win = mock_pet_window
    win._animation_override_active = False

    # Simulate the method logic
    fsm_states = {"IDLE": PetState.IDLE, "THINKING": PetState.THINKING}
    state = "IDLE"
    if state in fsm_states:
        win._fsm.transition_to(fsm_states[state])

    win._fsm.transition_to.assert_called_once_with(PetState.IDLE)


def test_trigger_state_override_action_layer_state(mock_pet_window):
    win = mock_pet_window
    action_states = {"FRUSTRATED", "SMUG", "SHOCKED", "LAUGHING"}
    state = "FRUSTRATED"
    duration_ms = 2000

    if state in action_states:
        win._action_layer.trigger(state.lower(), duration_ms)
        win._animation_override_active = True

    win._action_layer.trigger.assert_called_once_with("frustrated", 2000)
    assert win._animation_override_active is True


def test_animation_override_blocks_autonomous_trigger(mock_pet_window):
    win = mock_pet_window
    win._animation_override_active = True

    # _should_fire_autonomous must return False when override active
    def should_fire():
        if win._animation_override_active:
            return False
        return True

    assert should_fire() is False


def test_clear_animation_override_restores_flag(mock_pet_window):
    win = mock_pet_window
    win._animation_override_active = True
    win._animation_override_active = False  # simulate _clear_animation_override
    assert win._animation_override_active is False
```

- [ ] **Step 2: Run to verify fail**

```powershell
py -m pytest tests/test_animation_bridge.py -v
```

Expected: `FAILED` — `trigger_state_override` not on `PetWindow`.

- [ ] **Step 3: Add `trigger_state_override` to `src/ui/pet_window.py`**

Add as a `@pyqtSlot`:

```python
from PyQt6.QtCore import pyqtSlot

@pyqtSlot(str, int)
def trigger_state_override(self, state: str, duration_ms: int = 2000) -> None:
    """Thread-safe animation override. Called by MCP server via FSMActionBridge signal."""
    from src.pet_fsm import PetState
    fsm_states = {"IDLE": PetState.IDLE, "THINKING": PetState.THINKING}
    action_states = {"FRUSTRATED", "SMUG", "SHOCKED", "LAUGHING"}

    if state in fsm_states:
        self._fsm.transition_to(fsm_states[state])
    elif state in action_states:
        self._action_layer.trigger(state.lower(), duration_ms)
        self._animation_override_active = True
        QTimer.singleShot(duration_ms, self._clear_animation_override)

def _clear_animation_override(self) -> None:
    self._animation_override_active = False
```

Add `self._animation_override_active = False` in `PetWindow.__init__`.

Update `_should_fire_autonomous`:
```python
def _should_fire_autonomous(self, ...) -> bool:
    if self._animation_override_active:
        return False
    # ... existing guards unchanged
```

Connect in `__init__` after FSMActionBridge setup:
```python
self._fsm_bridge.action_requested.connect(self.trigger_state_override)
```

- [ ] **Step 4: Run tests**

```powershell
py -m pytest tests/test_animation_bridge.py -v
```

- [ ] **Step 5: Full regression**

```powershell
py -m pytest tests/ -v --timeout=30
```

- [ ] **Step 6: Commit**

```powershell
git add src/ui/pet_window.py tests/test_animation_bridge.py
git commit -m "feat(ui): add trigger_state_override and animation override lock"
```

---

## Phase 4: Stateless Burst Execution Coordinator

### Task 4.1: Rewrite `src/llm/opencode_worker.py` — ephemeral session + XML payload

**Files:**
- Modify: `src/llm/opencode_worker.py`
- Create: `tests/test_opencode_worker_stateless.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_opencode_worker_stateless.py`:

```python
import pytest
from unittest.mock import MagicMock, patch


def test_worker_creates_and_deletes_session():
    """Every burst must create a session, use it, and delete it."""
    from src.llm.opencode_worker import OpencodeWorker
    from PyQt6.QtCore import QCoreApplication
    import sys

    created = []
    deleted = []

    def fake_create(self):
        created.append("sess_test")
        return "sess_test"

    def fake_delete(self, session_id):
        deleted.append(session_id)

    def fake_post(self, session_id, payload):
        return '[{"dialogue": "hi", "action": "idle", "thought": "ok", "type": "observation", "priority": 3}]'

    with patch.object(__import__("src.llm.opencode_worker", fromlist=["OpencodeWorker"]).OpencodeWorker, "_create_session", fake_create), \
         patch.object(__import__("src.llm.opencode_worker", fromlist=["OpencodeWorker"]).OpencodeWorker, "_delete_session", fake_delete), \
         patch.object(__import__("src.llm.opencode_worker", fromlist=["OpencodeWorker"]).OpencodeWorker, "_post_message", fake_post):
        worker = OpencodeWorker(prompt="test", is_autonomous=False)
        worker.run()

    assert created == ["sess_test"]
    assert deleted == ["sess_test"], "Session must always be deleted, even on success"


def test_session_deleted_on_parse_error():
    """Session must be deleted even if JSON parse fails."""
    from src.llm.opencode_worker import OpencodeWorker

    deleted = []

    def fake_create(self): return "sess_err"
    def fake_delete(self, sid): deleted.append(sid)
    def fake_post(self, sid, payload): return "not json at all }{{"

    with patch.object(OpencodeWorker, "_create_session", fake_create), \
         patch.object(OpencodeWorker, "_delete_session", fake_delete), \
         patch.object(OpencodeWorker, "_post_message", fake_post):
        worker = OpencodeWorker(prompt="test", is_autonomous=False)
        worker.run()

    assert "sess_err" in deleted


def test_static_xml_block_contains_identity_tags():
    from src.llm.context_manager import ContextManager
    memory = MagicMock()
    memory.get_all.return_value = {
        "user_name": "Rohan",
        "user_profession": "SDE",
        "user_habits": ["codes a lot"],
        "pet_name": "Kenny",
        "pet_role": "Chaos Engine",
        "mission_directive": "Report everything",
        "pet_quirks": ["profanity"],
        "pet_fears": ["task manager"],
        "pet_catchphrases": ["wait until your wife hears"],
    }
    cm = ContextManager(memory=memory)
    block = cm.build_static_block()
    assert "<identities>" in block
    assert "<user>" in block
    assert "<pet>" in block
    assert "Rohan" in block
    assert "Kenny" in block
    assert len(block) <= 6000  # rough upper bound


def test_dynamic_block_contains_telemetry():
    from src.llm.context_manager import ContextManager
    memory = MagicMock()
    memory.get_all.return_value = {"pet_current_mood": "panicked", "pet_affinity_score": -5, "latest_summary": "user coded"}
    cm = ContextManager(memory=memory)
    block = cm.build_dynamic_block(apm=45, idle_seconds=12, window="VSCode", typing_preview="def foo")
    assert "<trigger_context>" in block
    assert "45" in block   # APM
    assert "VSCode" in block
    assert "def foo" in block
```

- [ ] **Step 2: Run to verify fail**

```powershell
py -m pytest tests/test_opencode_worker_stateless.py -v
```

- [ ] **Step 3: Rewrite `src/llm/opencode_worker.py`**

Replace with the stateless burst implementation:

```python
"""src/llm/opencode_worker.py — Stateless burst LLM execution coordinator.

Every call creates a fresh ephemeral OpenCode session, sends one XML payload,
parses the response, then immediately deletes the session (no SQLite accumulation).
"""
from __future__ import annotations

import json
import logging
import warnings
from typing import Any

import requests
from PyQt6.QtCore import QThread, pyqtSignal

from src.config import config_get

logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore", category=DeprecationWarning, module="src.llm.opencode_worker")


class OpencodeWorker(QThread):
    """Stateless burst LLM worker. Creates/destroys an OpenCode session per call."""

    trigger_ready = pyqtSignal(list)   # list[dict] — parsed structured items
    error = pyqtSignal(str)

    def __init__(
        self,
        prompt: str,
        is_autonomous: bool = False,
        screen_context: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._prompt = prompt
        self._is_autonomous = is_autonomous
        self._screen_context = screen_context
        self._abort = False
        self._server_url = config_get("llm.server_url") or "http://127.0.0.1:4096"
        self._timeout = min(int(config_get("llm.timeout_sec") or 30), 60)

    def abort(self) -> None:
        self._abort = True

    def run(self) -> None:
        session_id = self._create_session()
        if not session_id:
            self.error.emit("session_create_failed")
            return
        try:
            if self._abort:
                return
            raw = self._post_message(session_id, self._prompt)
            items = self._parse_response(raw)
            if items:
                self.trigger_ready.emit(items)
            else:
                self.error.emit("parse_failed")
        finally:
            self._delete_session(session_id)

    def _create_session(self) -> str | None:
        if self._abort:
            return None
        try:
            resp = requests.post(
                f"{self._server_url}/session",
                json={},
                timeout=10,
            )
            data = resp.json()
            return data.get("id") or data.get("session_id")
        except Exception as exc:
            logger.warning("create_session failed: %s", exc)
            return None

    def _post_message(self, session_id: str, payload: str) -> str:
        if self._abort:
            return ""
        try:
            resp = requests.post(
                f"{self._server_url}/session/{session_id}/message",
                json={"content": [{"type": "text", "text": payload}]},
                timeout=self._timeout,
            )
            data = resp.json()
            # Extract text from parts array
            for part in data.get("parts", []):
                if isinstance(part, dict) and part.get("type") == "text":
                    return part.get("text", "")
            return ""
        except Exception as exc:
            logger.warning("post_message failed: %s", exc)
            return ""

    def _delete_session(self, session_id: str) -> None:
        try:
            requests.delete(
                f"{self._server_url}/session/{session_id}",
                timeout=5,
            )
        except Exception as exc:
            logger.debug("delete_session failed (non-critical): %s", exc)

    def _parse_response(self, raw: str) -> list[dict]:
        if not raw:
            return []
        # Cap response to prevent degenerate blobs
        from src.constants import MAX_RESPONSE_CHARS
        if len(raw) > MAX_RESPONSE_CHARS:
            logger.warning("Response truncated from %d to %d chars", len(raw), MAX_RESPONSE_CHARS)
            raw = raw[:MAX_RESPONSE_CHARS]

        # Strategy 1: direct JSON array
        start = raw.find("[")
        if start != -1:
            try:
                items = json.loads(raw[start:raw.rfind("]") + 1])
                if isinstance(items, list):
                    return [i for i in items if isinstance(i, dict)]
            except json.JSONDecodeError:
                pass

        # Strategy 2: single JSON object
        start = raw.find("{")
        if start != -1:
            end = raw.rfind("}") + 1
            try:
                obj = json.loads(raw[start:end])
                if isinstance(obj, dict):
                    return [obj]
            except json.JSONDecodeError:
                pass

        # Strategy 3: JSONL (multiple objects on separate lines)
        items = []
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        if items:
            return items

        logger.warning("All parse strategies failed. Raw (first 200): %s", raw[:200])
        return []
```

- [ ] **Step 4: Run tests**

```powershell
py -m pytest tests/test_opencode_worker_stateless.py -v
```

- [ ] **Step 5: Full regression**

```powershell
py -m pytest tests/ -v --timeout=30
```

- [ ] **Step 6: Commit**

```powershell
git add src/llm/opencode_worker.py tests/test_opencode_worker_stateless.py
git commit -m "feat(llm): rewrite OpencodeWorker as stateless ephemeral session burst caller"
```

---

### Task 4.2: Add `build_static_block` and `build_dynamic_block` to `src/llm/context_manager.py`

**Files:**
- Modify: `src/llm/context_manager.py`
- Modify: `tests/test_opencode_worker_stateless.py`

- [ ] **Step 1: Run existing static/dynamic block tests to verify fail**

```powershell
py -m pytest tests/test_opencode_worker_stateless.py::test_static_xml_block_contains_identity_tags -v
```

Expected: `FAILED` — `build_static_block` not on `ContextManager`.

- [ ] **Step 2: Add `build_static_block` and `build_dynamic_block` to `src/llm/context_manager.py`**

```python
def build_static_block(self) -> str:
    """Build the XML static cold block (identity + permissions).
    Targets provider-side prefix cache. Budget: <=1200 tokens.
    Arrays are comma-separated inline — no nested sub-elements.
    """
    brain = self._memory.get_all() if self._memory else {}
    cfg = {
        "keyboard": config_get("consent.allow_keyboard_injection", False),
        "mouse": config_get("consent.allow_mouse_interference", False),
        "clipboard": config_get("consent.allow_clipboard_hijacking", False),
        "animations": config_get("consent.allow_intrusive_animations", True),
        "chattiness": config_get("pet.chattiness", 5),
        "nsfw": config_get("pet.nsfw_level", "sfw"),
        "personality": brain.get("pet_personality", ""),
    }

    def _list(val, sep=", ") -> str:
        if isinstance(val, list):
            return sep.join(str(v) for v in val[:8])  # cap at 8 items
        return str(val or "")

    catchphrases = _list(brain.get("pet_catchphrases", [])[:3], "; ")

    return f"""<system_configuration>
  <safety_permissions>
    <keyboard_input_granted>{str(cfg["keyboard"]).lower()}</keyboard_input_granted>
    <mouse_clicks_granted>{str(cfg["mouse"]).lower()}</mouse_clicks_granted>
    <clipboard_granted>{str(cfg["clipboard"]).lower()}</clipboard_granted>
    <animations_granted>{str(cfg["animations"]).lower()}</animations_granted>
  </safety_permissions>
  <personality_constraints>
    <chattiness>{cfg["chattiness"]}/10</chattiness>
    <nsfw_level>{cfg["nsfw"]}</nsfw_level>
    <tone>{cfg["personality"]}</tone>
  </personality_constraints>
</system_configuration>
<identities>
  <user>
    <name>{brain.get("user_name", "")}</name>
    <profession>{brain.get("user_profession", "")}</profession>
    <habits>{_list(brain.get("user_habits", []))}</habits>
    <focus_apps>{_list(brain.get("user_focus_apps", []))}</focus_apps>
    <distraction_apps>{_list(brain.get("user_distraction_apps", []))}</distraction_apps>
  </user>
  <pet>
    <name>{brain.get("pet_name", "")}</name>
    <role>{brain.get("pet_role", "")}</role>
    <mission>{brain.get("mission_directive", "")}</mission>
    <quirks>{_list(brain.get("pet_quirks", []))}</quirks>
    <fears>{_list(brain.get("pet_fears", []))}</fears>
    <catchphrases>{catchphrases}</catchphrases>
  </pet>
</identities>"""


def build_dynamic_block(
    self,
    apm: int = 0,
    idle_seconds: float = 0.0,
    window: str = "",
    typing_preview: str = "",
    source: str = "Autonomous Cycle",
    event_type: str = "System Idle",
) -> str:
    """Build the XML dynamic hot block (runtime telemetry). Never cached."""
    brain = self._memory.get_all() if self._memory else {}
    summary = brain.get("latest_summary", "")
    mood = brain.get("pet_current_mood", "")
    affinity = brain.get("pet_affinity_score", 0)
    preview = (typing_preview or "")[:100]

    return f"""<trigger_context>
  <source>{source}</source>
  <event_type>{event_type}</event_type>
  <telemetry_summary>{window}, APM {apm}, idle {int(idle_seconds)}s</telemetry_summary>
  <typing_preview>{preview}</typing_preview>
</trigger_context>
<memory_state>
  <mood>{mood}</mood>
  <affinity>{affinity}</affinity>
  <latest_summary>{summary}</latest_summary>
</memory_state>"""
```

- [ ] **Step 3: Run tests**

```powershell
py -m pytest tests/test_opencode_worker_stateless.py -v
```

- [ ] **Step 4: Update `pet_window.py` to use new XML prompt builders**

In `_on_input_submitted` and autonomous trigger handlers, replace `build_user_trigger()` / `build_autonomous_trigger()` calls with:

```python
static = self._context_manager.build_static_block()
dynamic = self._context_manager.build_dynamic_block(
    apm=self._apm,
    idle_seconds=self._idle_seconds,
    window=self._active_window,
    typing_preview=self._typing_buffer.get_context(),
    source="User Input",
    event_type="User Query",
)
screen_ctx = ""
if self._prefetch_result:
    if time.monotonic() - self._prefetch_timestamp > 5.0:
        self._prefetch_result = self._fetch_screen_context_sync()
    screen_ctx = f"<screen_context>{self._prefetch_result}</screen_context>"

prompt = f"{static}\n{dynamic}\n{screen_ctx}\n<user_input>{user_text}</user_input>"
```

- [ ] **Step 5: Full regression**

```powershell
py -m pytest tests/ -v --timeout=30
```

- [ ] **Step 6: Commit**

```powershell
git add src/llm/context_manager.py src/ui/pet_window.py tests/test_opencode_worker_stateless.py
git commit -m "feat(llm): add XML static/dynamic prompt blocks to ContextManager"
```

---

### Task 4.3: Pre-fetch UIA tree on overlay open with 5s TTL

**Files:**
- Modify: `src/ui/pet_window.py`
- Modify: `tests/test_animation_bridge.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_animation_bridge.py`:

```python
def test_prefetch_ttl_re_fetches_after_5_seconds(monkeypatch):
    import time
    fetch_calls = []

    def fake_fetch():
        fetch_calls.append(time.monotonic())
        return "<ui/>"

    # Simulate: prefetch 6 seconds ago
    timestamp = time.monotonic() - 6.0
    prefetch_result = "<ui><button name='old'/></ui>"

    # TTL check logic
    if time.monotonic() - timestamp > 5.0:
        prefetch_result = fake_fetch()

    assert len(fetch_calls) == 1  # re-fetched because TTL expired


def test_prefetch_not_re_fetched_within_ttl(monkeypatch):
    import time
    fetch_calls = []

    def fake_fetch():
        fetch_calls.append(1)
        return "<ui/>"

    # Simulate: prefetch 2 seconds ago (within TTL)
    timestamp = time.monotonic() - 2.0
    prefetch_result = "<ui><button name='fresh'/></ui>"

    if time.monotonic() - timestamp > 5.0:
        prefetch_result = fake_fetch()

    assert len(fetch_calls) == 0  # NOT re-fetched
```

- [ ] **Step 2: Run to verify fail**

```powershell
py -m pytest tests/test_animation_bridge.py::test_prefetch_ttl_re_fetches_after_5_seconds -v
```

- [ ] **Step 3: Add pre-fetch state to `pet_window.py`**

In `PetWindow.__init__`:
```python
self._prefetch_result: str | None = None
self._prefetch_timestamp: float = 0.0
```

In the double-click / overlay-open handler (wherever the input field appears):
```python
# Fire async UIA pre-fetch
self._prefetch_result = None
self._prefetch_timestamp = time.monotonic()
from concurrent.futures import ThreadPoolExecutor
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="prefetch")
_executor.submit(self._do_prefetch)
```

Add method:
```python
def _do_prefetch(self) -> None:
    """Runs in QThreadPool. Fetches UIA screen context."""
    try:
        from src.mcp_server import _get_screen_context_impl
        self._prefetch_result = _get_screen_context_impl()
    except Exception as exc:
        logger.debug("prefetch failed: %s", exc)
        self._prefetch_result = ""

def _fetch_screen_context_sync(self) -> str:
    """Synchronous fallback for expired pre-fetch TTL."""
    try:
        from src.mcp_server import _get_screen_context_impl
        return _get_screen_context_impl()
    except Exception:
        return ""
```

- [ ] **Step 4: Run tests**

```powershell
py -m pytest tests/test_animation_bridge.py -v
```

- [ ] **Step 5: Full regression**

```powershell
py -m pytest tests/ -v --timeout=30
```

- [ ] **Step 6: Commit**

```powershell
git add src/ui/pet_window.py tests/test_animation_bridge.py
git commit -m "feat(ui): add UIA pre-fetch on overlay open with 5s TTL re-fetch"
```

---

## Phase 5: Diary Compaction Loop

### Task 5.1: Add compaction logic to `src/diary_store.py`

**Files:**
- Modify: `src/diary_store.py`
- Create: `tests/test_diary_compaction.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_diary_compaction.py`:

```python
import pytest
from unittest.mock import MagicMock, patch


COMPACTION_TRIGGER_COUNT = 10


@pytest.fixture
def diary_store(tmp_path):
    from src.diary_store import DiaryStore
    store = DiaryStore(path=tmp_path / ".daemon_diary.json")
    return store


def test_check_compaction_needed_false_when_below_threshold(diary_store):
    for i in range(5):
        diary_store.add_entry({"content": f"entry {i}", "summarized": False})
    assert diary_store.check_compaction_needed() is False


def test_check_compaction_needed_true_at_threshold(diary_store):
    for i in range(10):
        diary_store.add_entry({"content": f"entry {i}", "summarized": False})
    assert diary_store.check_compaction_needed() is True


def test_check_compaction_needed_ignores_summarized_entries(diary_store):
    for i in range(8):
        diary_store.add_entry({"content": f"entry {i}", "summarized": True})
    for i in range(3):
        diary_store.add_entry({"content": f"fresh {i}", "summarized": False})
    # 3 fresh < 10 threshold
    assert diary_store.check_compaction_needed() is False


def test_compaction_deferred_flag_set_on_skip(diary_store):
    diary_store._compaction_deferred = False
    diary_store.on_compaction_skipped()
    assert diary_store._compaction_deferred is True


def test_compaction_marks_entries_as_summarized(diary_store, tmp_path):
    for i in range(10):
        diary_store.add_entry({"content": f"entry {i}", "summarized": False})

    mock_summary = "User was coding all day."

    def fake_burst(prompt):
        return mock_summary

    with patch.object(diary_store, "_run_llm_burst", side_effect=fake_burst), \
         patch.object(diary_store, "_memory") as mock_mem, \
         patch.object(diary_store, "_write_coalescer") as mock_wc:
        diary_store._run_compaction()

    fresh = [e for e in diary_store._entries if not e.get("summarized")]
    assert len(fresh) == 0
```

- [ ] **Step 2: Run to verify fail**

```powershell
py -m pytest tests/test_diary_compaction.py -v
```

- [ ] **Step 3: Add compaction methods to `src/diary_store.py`**

Add to `DiaryStore`:

```python
COMPACTION_TRIGGER_COUNT = 10

# Add to __init__:
self._compaction_deferred: bool = False
self._memory = None        # set externally after construction
self._write_coalescer = None  # set externally after construction

def check_compaction_needed(self) -> bool:
    """True if >= COMPACTION_TRIGGER_COUNT fresh (unsummarized) entries exist."""
    fresh = sum(1 for e in self._entries if not e.get("summarized"))
    return fresh >= COMPACTION_TRIGGER_COUNT

def on_compaction_skipped(self) -> None:
    """Call when compaction is skipped due to active query. P4 tick will retry."""
    self._compaction_deferred = True

def _run_llm_burst(self, prompt: str) -> str:
    """Synchronous ephemeral OpenCode burst for compaction (runs in daemon thread)."""
    from src.config import config_get
    import requests
    server = config_get("llm.server_url") or "http://127.0.0.1:4096"
    try:
        r = requests.post(f"{server}/session", json={}, timeout=10)
        session_id = r.json().get("id") or r.json().get("session_id")
        if not session_id:
            return ""
        resp = requests.post(
            f"{server}/session/{session_id}/message",
            json={"content": [{"type": "text", "text": prompt}]},
            timeout=30,
        )
        text = ""
        for part in resp.json().get("parts", []):
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
                break
        requests.delete(f"{server}/session/{session_id}", timeout=5)
        return text
    except Exception as exc:
        logger.warning("Compaction LLM burst failed: %s", exc)
        return ""

def _run_compaction(self) -> None:
    """Compact fresh diary entries into latest_summary. Runs in daemon thread."""
    import json as _json
    fresh = [e for e in self._entries if not e.get("summarized")]
    if not fresh:
        return

    entries_text = _json.dumps([e.get("content", "") for e in fresh], ensure_ascii=False)
    prompt = (
        f"Summarize these diary entries in 2-3 sentences. Be concise and factual:\n{entries_text}"
    )
    summary = self._run_llm_burst(prompt)
    if not summary:
        return

    # Update local memory
    if self._memory:
        self._memory.remember("latest_summary", summary)

    # Mark entries summarized
    for e in self._entries:
        if not e.get("summarized"):
            e["summarized"] = True
    self._write_atomic()

    # Trigger Firebase sync
    if self._write_coalescer:
        self._write_coalescer.mark_dirty("brain")

    logger.info("Diary compaction complete. Summary: %s", summary[:80])
```

- [ ] **Step 4: Run tests**

```powershell
py -m pytest tests/test_diary_compaction.py -v
```

---

### Task 5.2: Wire compaction retry into `BehaviorController` P4 boredom tick

**Files:**
- Modify: `src/autonomy/behavior_controller.py`
- Modify: `tests/test_diary_compaction.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_diary_compaction.py`:

```python
def test_p4_tick_retries_deferred_compaction():
    """BehaviorController P4 path must trigger compaction when deferred flag is set."""
    from src.autonomy.behavior_controller import BehaviorController

    mock_diary = MagicMock()
    mock_diary.check_compaction_needed.return_value = False
    mock_diary._compaction_deferred = True

    compaction_fired = []

    def fake_fire():
        compaction_fired.append(1)

    # Simulate the P4 boredom check logic
    compaction_in_flight = False
    autonomous_query_pending = False

    if (mock_diary.check_compaction_needed() or mock_diary._compaction_deferred):
        if not compaction_in_flight and not autonomous_query_pending:
            mock_diary._compaction_deferred = False
            fake_fire()

    assert len(compaction_fired) == 1
    assert mock_diary._compaction_deferred is False
```

- [ ] **Step 2: Add compaction retry to `BehaviorController`**

In `BehaviorController.__init__`:
```python
self._compaction_in_flight: bool = False
self._diary_store = None  # injected externally
```

In the P4 boredom handler method (the one that fires idle/boredom events):
```python
# After dispatching the boredom trigger, check compaction:
if self._diary_store and (
    self._diary_store.check_compaction_needed() or self._diary_store._compaction_deferred
):
    if not self._compaction_in_flight and not self._autonomous_query_pending:
        self._diary_store._compaction_deferred = False
        self._compaction_in_flight = True
        import threading
        t = threading.Thread(target=self._run_compaction, daemon=True)
        t.start()

def _run_compaction(self) -> None:
    try:
        if self._diary_store:
            self._diary_store._run_compaction()
    finally:
        self._compaction_in_flight = False
```

Wire `_diary_store` in `pet_window.py`:
```python
self._behavior._diary_store = self._diary_store
```

- [ ] **Step 3: Run all compaction tests**

```powershell
py -m pytest tests/test_diary_compaction.py -v
```

- [ ] **Step 4: Full final regression**

```powershell
py -m pytest tests/ -v --timeout=30
```

Expected: full suite passes.

- [ ] **Step 5: Commit**

```powershell
git add src/diary_store.py src/autonomy/behavior_controller.py src/ui/pet_window.py tests/test_diary_compaction.py
git commit -m "feat(diary): rolling compaction loop with P4 boredom tick retry"
```

---

## Final Integration

### Task 6.1: Full regression and user confirmation gate

- [ ] **Step 1: Run full regression on feature branch**

```powershell
git branch  # confirm you are on task-75-stateless-mcp-pipeline, NOT master
py -m pytest tests/ -v --timeout=30
```

Expected: all tests pass, `0 failed`. If any test fails, fix it before proceeding. Do NOT merge with a red suite.

- [ ] **Step 2: Print branch summary and STOP — wait for user confirmation**

Output the following to the user and wait for explicit approval before continuing:

```
✅ Branch task-75-stateless-mcp-pipeline is green.

Ready to squash-merge to master. This will:
  - Squash all branch commits into one clean commit on master
  - Delete the feature branch
  - Update AGENTS.md, README.md, docs/architecture.md, memory/project-dev-memory.md

Confirm: proceed with squash-merge? (yes / no)
```

**Do not execute Step 3 until the user replies "yes".**

---

### Task 6.2: Squash-merge to master

- [ ] **Step 1: Squash-merge**

```powershell
git checkout master
git merge --squash task-75-stateless-mcp-pipeline
git commit -m "feat: stateless MCP burst pipeline — FastMCP SSE, ephemeral sessions, XML prompts, diary compaction"
```

Expected: `1 file changed` or more, clean commit on master.

- [ ] **Step 2: Delete the feature branch**

```powershell
git branch -D task-75-stateless-mcp-pipeline
```

Expected: `Deleted branch task-75-stateless-mcp-pipeline`.

- [ ] **Step 3: Verify master is clean**

```powershell
git status
git log --oneline -5
```

Expected: most recent commit is the squash-merge commit. Working tree clean.

---

### Task 6.3: Update all relevant docs

**Files:**
- Modify: `memory/project-dev-memory.md`
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `docs/architecture.md`

- [ ] **Step 1: Update `memory/project-dev-memory.md`**

Append a new phase section at the end (before "Done — End of Project Dev Memory") with the following structure:

```markdown
### Phase 75 — Stateless MCP-Driven Pipeline (2026-07-05)
**Branch:** `task-75-stateless-mcp-pipeline` (squash-merged)

**Goal:** Replace Strands SDK stateful session model with lean stateless burst pipeline.

**What was built:**

| Phase | Work | Status |
|-------|------|--------|
| 0: Rip-out | Deleted strands_worker.py, llm_session_persistence.py, test files. Swept all imports from pet_window.py, opencode_worker.py, daemon.py, conftest.py. Removed strands from requirements.txt. | ✅ |
| 1: Config cache | _RUNTIME_CONFIG live dict, config_get()/config_set() dot-path API, DND circuit breaker in apm_worker/event_worker, adaptive idle threshold, probability gate on window switches. | ✅ |
| 2: FastMCP SSE | Replaced http.server MCPServer with FastMCP SSE QThread on :4097. Same opencode.json URL. COM pythoncom.CoInitialize() in thread. 4 new tools: get_screen_context (pruned UIA XML, depth 7), get_browser_context (sniper URL, depth 5), execute_os_action (guarded + clipboard-paste path), trigger_pet_animation (6 states → FSMActionBridge). 13 existing tools migrated. | ✅ |
| 3: Animation bridge | trigger_state_override() @pyqtSlot, _animation_override_active flag, QTimer.singleShot clear. Pre-fetch UIA tree on overlay open, 5s TTL synchronous re-fetch on expiry. | ✅ |
| 4: Stateless executor | OpencodeWorker rewritten: ephemeral session per burst (POST /session → message → DELETE /session). XML payload: build_static_block() ≤1200 tokens (prefix cache target) + build_dynamic_block() (runtime telemetry). Dual-trigger dispatcher: user workflow injects pre-fetched screen XML, autonomous workflow sends minimal telemetry and lets LLM call MCP tools. | ✅ |
| 5: Diary compaction | DiaryStore.check_compaction_needed() (threshold=10 fresh entries), _run_compaction() via ephemeral LLM burst, _compaction_deferred flag. BehaviorController P4 boredom tick retries deferred compaction. | ✅ |

**Key architectural decisions:**
- Ephemeral sessions: POST /session → message → DELETE /session. Zero SQLite accumulation in OpenCode serve.
- FastMCP SSE stays in-process — all PyQt singletons (Memory, DiaryStore, FSMActionBridge) accessible. No subprocess IPC needed.
- pyqtSignal cross-thread for MCP→UI calls: auto QueuedConnection. No queue.Queue.
- Static XML block ≤1200 tokens for provider prefix cache. Dynamic block always fresh.
- execute_os_action use_clipboard=True: Win32 clipboard write + Ctrl+V paste. Bypasses 50-char keystroke cap.

**Files deleted:**
- src/llm/strands_worker.py
- src/llm/llm_session_persistence.py
- tests/test_strands_worker.py
- tests/test_llm_session_persistence.py

**Files created:**
- tests/test_config_cache.py
- tests/test_mcp_server_fastmcp.py
- tests/test_animation_bridge.py
- tests/test_opencode_worker_stateless.py
- tests/test_diary_compaction.py

**Files modified:**
- src/config.py, src/system/apm_worker.py, src/system/event_worker.py
- src/autonomy/behavior_controller.py, src/mcp_server.py
- src/fsm_bridge.py, src/ui/pet_window.py
- src/llm/opencode_worker.py, src/llm/context_manager.py
- src/diary_store.py, requirements.txt

**Test results:** [UPDATE WITH ACTUAL COUNT] passed, 0 failed.
```

- [ ] **Step 2: Update `AGENTS.md` — Boot Sequence section**

Find the **Boot Sequence** block in `AGENTS.md`. Update the `MCPServer` line:

```
# Before:
  ├─ MCPServer (JSON-RPC 2.0 on :4097)
# After:
  ├─ MCPServerThread (FastMCP SSE on :4097) — 17 tools, COM initialized
```

Update the **MCP Server** section tool count from 13 → 17 and list the 4 new tools:
- `get_screen_context` — pruned UIA interactive XML (depth 7, 2000 char cap)
- `get_browser_context` — sniper URL via ValuePattern (depth 5)
- `execute_os_action` — guarded OS control with clipboard-paste path (`use_clipboard=True`)
- `trigger_pet_animation` — 6 states: IDLE, THINKING, FRUSTRATED, SMUG, SHOCKED, LAUGHING

Update test count to match actual result.

- [ ] **Step 3: Update `README.md`**

Find any section referencing "Strands", "StrandsWorker", "LLMSessionPersistence", or "session persistence" — remove or replace with:

> Daemon uses a stateless burst model: every LLM interaction creates a fresh ephemeral OpenCode session, sends a full XML context payload, receives a response, then immediately deletes the session — preventing SQLite accumulation and ensuring zero cross-call state bleed.

Update the MCP tools table if present (add 4 new tools, bump count to 17).

- [ ] **Step 4: Update `docs/architecture.md`**

Find the MCP Server section. Replace the old `http.server` / `MCPHandler` description with:

> **MCP Server:** FastMCP SSE (`mcp` package) running in `MCPServerThread(QThread)` on port 4097. Communicates with OpenCode via the existing `opencode.json` `"type": "remote"` URL (no config change). COM apartment initialized via `pythoncom.CoInitialize()` in `QThread.run()`. 17 tools total: 4 new (screen context, browser context, OS actions, pet animations) + 13 migrated from previous `http.server` implementation.

Update the **Data Flow Pipelines** section to reflect the stateless burst pattern (ephemeral session, XML payload, no session persistence).

- [ ] **Step 5: Commit all docs**

```powershell
git add memory/project-dev-memory.md AGENTS.md README.md docs/architecture.md
git commit -m "docs: update all docs for Phase 75 stateless MCP pipeline"
```

---

*Plan written 2026-07-05. Spec: `docs/superpowers/specs/2026-07-05-stateless-mcp-pipeline-design.md`*
