# Log Audit Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all bugs, crashes, and irregular patterns found in the production log `daemon_2026-06-22_11-40-12.log` and `crash_dump.log`.

**Architecture:** Surgical fixes only — one bug per task. No refactoring of unrelated code. Each fix is verified by a targeted test before merge.

**Tech Stack:** Python 3.14, PyQt6, pytest, structlog, Strands SDK, opencode serve API.

---

## Audit Summary — What the Logs Revealed

| # | Severity | Component | Issue |
|---|----------|-----------|-------|
| 1 | CRITICAL | `pet_window.py:410` + `click_through.py:62` | `QRect` crash loop: `_pet_x`/`_pet_y` are floats, QRect requires ints — 1000+ exceptions in `crash_dump.log` |
| 2 | CRITICAL | `pet_renderer.py:467` | `drawLine` float crash — `py` from `_pet_y` is float, QPainter drawLine y args must be int |
| 3 | HIGH | `mcp_server.py:690` | `query_memory` with `type="history"` fails: `"Store type 'history' is not configured/available."` — History object not wired into MCPServer |
| 4 | HIGH | `opencode_worker.py` | Pool refill JSON parse failures — LLM sends markdown preamble, truncated JSON, or extra forbidden fields (`action`, `target_x`). Fires 6+ times per session |
| 5 | HIGH | `strands_worker.py` | `reasoningContent is not supported in multi-turn conversations` — repeated 8+ times per session. DeepSeek emits reasoning tokens; no suppression |
| 6 | MEDIUM | `mcp_server.py` | LLM uses expression action `float` with `layer="fsm"` — error returned gives no hint of valid actions, LLM retries same mistake |
| 7 | MEDIUM | `click_through.py` | Shutdown poll storm — 10 enable/disable events in 7s during shutdown. No `_stopped` guard in `_poll` |
| 8 | MEDIUM | `pet_window.py` boot log | Startup DATA log fires before Firebase sync: shows `brain=0 fields` instead of correct count |
| 9 | LOW | System prompt / `strands_worker.py` | `{user_nickname}`, `{user_partner_name}`, `{user_engineer_name}` placeholders never interpolated — LLM outputs raw `{user_nickname}` in dialogue |
| 10 | LOW | `daemon.py` | `crash_dump.log` has no rotation or size cap — grows unboundedly |

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/pet_window.py:410` | Modify | Cast `_pet_x`, `_pet_y` to `int` in `_get_click_geometry` |
| `src/pet_renderer.py:463-467` | Modify | Cast all float coords to `int` before `drawLine` calls |
| `src/mcp_server.py` | Modify | MCPServer accept `history=` kwarg; pass to MCPHandler |
| `src/pet_window.py` (MCPServer construction) | Modify | Pass `self._history` into `MCPServer(...)` |
| `src/opencode_worker.py` | Modify | Strip markdown fences, preamble, and forbidden fields in JSON parse |
| `src/strands_worker.py` | Modify | Suppress `reasoningContent` UserWarning at import; add `_interpolate_prompt` |
| `src/click_through.py` | Modify | Add `_stopped` flag and `stop()` method |
| `daemon.py` | Modify | Add `_rotate_crash_dump` helper called at boot |
| `tests/test_click_through.py` | Modify | Add QRect float crash test + shutdown stop test |
| `tests/test_pet_renderer.py` | Modify | Add drawLine float coord test |
| `tests/test_mcp_server.py` | Modify | Add `query_memory type=history` test + FSM mismatch error test |
| `tests/test_opencode_worker.py` | Modify | Add preamble/fence/forbidden-field parse tests |
| `tests/test_strands_worker.py` | Modify | Add warning suppression test + placeholder interpolation test |
| `tests/test_daemon.py` | Modify | Add crash_dump rotation test |
| `memory/project-dev-memory.md` | Modify | Record all fixes and new pitfalls |

---

## Task 1: Fix QRect float crash in `_get_click_geometry`

> CRITICAL — Fires every 50ms. Fills `crash_dump.log` with thousands of identical TypeErrors.

**Root cause:** `_pet_x` and `_pet_y` are `float` (physics engine). `QRect(int, int, int, int)` is strict — PyQt6 will not coerce float arg 2 (`y`) to int.

**Files:**
- Modify: `src/pet_window.py:410`
- Test: `tests/test_click_through.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_click_through.py — add this test
def test_get_click_geometry_with_float_coords(mocker):
    """QRect must not crash when _pet_x/_pet_y are floats."""
    from src.pet_window import PetWindow
    from PyQt6.QtCore import QRect
    win = PetWindow.__new__(PetWindow)
    win._pet_x = 123.7   # floats from physics engine
    win._pet_y = 456.2
    win._scale = 1.0
    win._pet_scale = 1.0
    win._bubble_text = ""
    win._input_field = mocker.Mock(isVisible=lambda: False)
    # Must not raise TypeError
    rect = win._get_click_geometry()
    assert isinstance(rect, QRect)
```

- [ ] **Step 2: Run test to verify it fails**

```
py -m pytest tests/test_click_through.py::test_get_click_geometry_with_float_coords -v
```

Expected: `FAIL` with `TypeError: arguments did not match any overloaded call`

- [ ] **Step 3: Fix `_get_click_geometry` in `pet_window.py:410`**

Replace:
```python
rect = QRect(self._pet_x, self._pet_y, int(PET_WIDTH * getattr(self, '_scale', 1.0) * getattr(self, '_pet_scale', 1.0)), int(PET_HEIGHT * getattr(self, '_scale', 1.0) * getattr(self, '_pet_scale', 1.0)))
```
With:
```python
rect = QRect(int(self._pet_x), int(self._pet_y), int(PET_WIDTH * getattr(self, '_scale', 1.0) * getattr(self, '_pet_scale', 1.0)), int(PET_HEIGHT * getattr(self, '_scale', 1.0) * getattr(self, '_pet_scale', 1.0)))
```

- [ ] **Step 4: Run test to verify it passes**

```
py -m pytest tests/test_click_through.py::test_get_click_geometry_with_float_coords -v
```

Expected: `PASS`

- [ ] **Step 5: Run full suite**

```
py -m pytest tests/ -v --tb=short -q
```

Expected: all existing tests pass, 0 new failures.

- [ ] **Step 6: Commit**

```bash
git add src/pet_window.py tests/test_click_through.py
git commit -m "fix(click_through): cast pet_x/pet_y to int in _get_click_geometry"
```

---

## Task 2: Fix `drawLine` float crash in PERIMETER speedlines

> CRITICAL — Same root cause as Task 1. `py + 20 + y_off` is float because `py` derives from `_pet_y`.

**Files:**
- Modify: `src/pet_renderer.py:463-467`
- Test: `tests/test_pet_renderer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pet_renderer.py — add this test
def test_perimeter_speedlines_with_float_pet_coords():
    """drawLine must not crash when pet coords are floats."""
    from PyQt6.QtGui import QImage, QPainter
    from PyQt6.QtCore import QRect
    from src.pet_renderer import PetRenderer, RenderContext
    from src.pet_fsm import PetState

    img = QImage(400, 400, QImage.Format.Format_ARGB32)
    painter = QPainter(img)

    ctx = RenderContext(
        state=PetState.PERIMETER,
        pet_x=50.7,    # float
        pet_y=100.3,   # float
        scale_x=1.0, scale_y=1.0, rotation=0.0,
        cursor_x=0, cursor_y=0,
        state_elapsed_ms=0, land_elapsed_ms=0,
        bubble_text="", bubble_alpha=0.0, bubble_rect=None,
        edge="bottom", facing="right", wander_direction=1,
        emotion=None, apm=0,
    )

    # Must not raise TypeError
    PetRenderer.render(painter, ctx)
    painter.end()
```

- [ ] **Step 2: Run test to verify it fails**

```
py -m pytest tests/test_pet_renderer.py::test_perimeter_speedlines_with_float_pet_coords -v
```

Expected: `FAIL` with `TypeError: arguments did not match any overloaded call: drawLine`

- [ ] **Step 3: Fix `pet_renderer.py:463-467`**

Locate the PERIMETER speedline block:
```python
dx = -10 * ctx.wander_direction
for i in range(3):
    y_off = (i - 1) * 6
    x_start = px + (PET_WIDTH if ctx.wander_direction > 0 else 0) + dx + i * 4 * (-ctx.wander_direction)
    painter.drawLine(x_start, py + 20 + y_off, x_start + 8 * (-ctx.wander_direction), py + 20 + y_off)
```

Change to:
```python
dx = -10 * ctx.wander_direction
for i in range(3):
    y_off = (i - 1) * 6
    x_start = int(px + (PET_WIDTH if ctx.wander_direction > 0 else 0) + dx + i * 4 * (-ctx.wander_direction))
    y_line = int(py + 20 + y_off)
    painter.drawLine(x_start, y_line, x_start + int(8 * (-ctx.wander_direction)), y_line)
```

Also verify that `px` and `py` are already cast to `int` at the top of the render method (look for `px = int(ctx.pet_x)` / `py = int(ctx.pet_y)`). If not, add those casts.

- [ ] **Step 4: Run test to verify it passes**

```
py -m pytest tests/test_pet_renderer.py::test_perimeter_speedlines_with_float_pet_coords -v
```

Expected: `PASS`

- [ ] **Step 5: Run full suite**

```
py -m pytest tests/ -v --tb=short -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/pet_renderer.py tests/test_pet_renderer.py
git commit -m "fix(renderer): cast float coords to int before drawLine in PERIMETER speedlines"
```

---

## Task 3: Wire `History` into `MCPServer` for `query_memory`

> HIGH — LLM calls `query_memory(type="history")` which is in the advertised tools/list but always fails.

**Root cause:** `MCPServer.__init__` has no `history` parameter. `PetWindow` never passes `self._history`. MCPHandler's `_history` is always `None`.

**Files:**
- Modify: `src/mcp_server.py`
- Modify: `src/pet_window.py`
- Test: `tests/test_mcp_server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mcp_server.py — add this test
def test_query_memory_history_returns_entries():
    """query_memory with type='history' must return entries, not a tool error."""
    from src.mcp_server import MCPHandler
    from unittest.mock import MagicMock

    history_mock = MagicMock()
    history_mock.query.return_value = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]

    handler = MCPHandler.__new__(MCPHandler)
    handler._memory = None
    handler._diary = None
    handler._history = history_mock

    result = handler._handle_query_memory({"type": "history", "limit": 10})
    assert "error" not in result
    assert result["result"]["type"] == "history"
    assert len(result["result"]["entries"]) == 2
```

- [ ] **Step 2: Run test to verify it fails**

```
py -m pytest tests/test_mcp_server.py::test_query_memory_history_returns_entries -v
```

Expected: `FAIL` — result contains `"error"` because `_history` is `None`.

- [ ] **Step 3: Add `history=None` to `MCPServer.__init__` and store it**

In `src/mcp_server.py`, in `class MCPServer __init__`:

```python
class MCPServer:
    def __init__(self, fsm_bridge=None, memory=None, diary=None, history=None,
                 config=None, action_layer=None):
        ...
        self.history = history    # add this
        ...
```

Then in the request handler creation (wherever `MCPHandler(...)` is instantiated inside MCPServer), pass `history=self.history`:

```python
handler = MCPHandler(
    request, client_address, server,
    fsm_bridge=self.fsm_bridge,
    memory=self.memory,
    diary=self.diary,
    history=self.history,   # add this
    config=self.config,
    action_layer=self.action_layer,
)
```

- [ ] **Step 4: Pass `self._history` in `pet_window.py` MCPServer construction**

Find `MCPServer(` in `src/pet_window.py` and add `history=self._history`:

```python
self._mcp_server = MCPServer(
    fsm_bridge=self._fsm_bridge,
    memory=self._memory,
    diary=self._diary,
    history=self._history,    # add this
    config=self._config,
    action_layer=self._action_layer,
)
```

- [ ] **Step 5: Run test to verify it passes**

```
py -m pytest tests/test_mcp_server.py::test_query_memory_history_returns_entries -v
```

Expected: `PASS`

- [ ] **Step 6: Run full suite**

```
py -m pytest tests/ -v --tb=short -q
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/mcp_server.py src/pet_window.py tests/test_mcp_server.py
git commit -m "fix(mcp): wire History into MCPServer so query_memory type=history works"
```

---

## Task 4: Fix pool refill JSON parse failures

> HIGH — 6 parse failures per session. LLM sends ` ```json ` fences, truncated JSON, prose preambles, or extra forbidden schema fields. Only 1 malformed item recovered per failure.

**Files:**
- Modify: `src/opencode_worker.py`
- Test: `tests/test_opencode_worker.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_opencode_worker.py — add these tests

def test_parse_response_strips_markdown_fences():
    """JSON inside ```json fences should be parsed correctly."""
    from src.opencode_worker import OpencodeWorker
    raw = '```json\n[{"thought": "hi", "dialogue": "yo", "type": "idle_thought"}]\n```'
    result = OpencodeWorker._parse_pool_response(raw)
    assert result is not None
    assert len(result) == 1
    assert result[0]["type"] == "idle_thought"

def test_parse_response_prose_preamble_returns_none():
    """Plain prose with no JSON array must return None (triggers fallback)."""
    from src.opencode_worker import OpencodeWorker
    raw = "Here are 5 panicked Kenny thoughts keyed to this context:"
    result = OpencodeWorker._parse_pool_response(raw)
    assert result is None

def test_parse_response_strips_forbidden_fields():
    """Items with forbidden fields (action, target_x) have those keys removed."""
    from src.opencode_worker import OpencodeWorker
    raw = '[{"type": "typing_reaction", "thought": "ok", "dialogue": "ok", "action": "hyper", "target_x": 0}]'
    result = OpencodeWorker._parse_pool_response(raw)
    assert result is not None
    assert "action" not in result[0]
    assert "target_x" not in result[0]
    assert result[0]["dialogue"] == "ok"
```

- [ ] **Step 2: Run tests to verify they fail**

```
py -m pytest tests/test_opencode_worker.py::test_parse_response_strips_markdown_fences tests/test_opencode_worker.py::test_parse_response_prose_preamble_returns_none tests/test_opencode_worker.py::test_parse_response_strips_forbidden_fields -v
```

Expected: all `FAIL`

- [ ] **Step 3: Add `_parse_pool_response` static method to `OpencodeWorker`**

```python
import json as _json

_POOL_FORBIDDEN_FIELDS = frozenset({"action", "target_x", "target_y", "mode"})

@staticmethod
def _parse_pool_response(raw: str) -> list | None:
    """Parse pool refill LLM output into a list of dicts. Returns None on failure."""
    if not raw or not raw.strip():
        return None

    text = raw.strip()

    # Strip markdown code fences (```json ... ``` or ``` ... ```)
    if text.startswith("```"):
        inner_lines = []
        in_fence = False
        for line in text.splitlines():
            if line.startswith("```") and not in_fence:
                in_fence = True
                continue
            if line.startswith("```") and in_fence:
                break
            if in_fence:
                inner_lines.append(line)
        text = "\n".join(inner_lines).strip()

    # Find JSON array start
    start = text.find("[")
    if start == -1:
        # No array found — could be object or pure prose
        start = text.find("{")
        if start == -1:
            return None
        text = "[" + text[start:] + "]"
    else:
        text = text[start:]

    # Find array end
    end = text.rfind("]")
    if end == -1:
        return None
    text = text[:end + 1]

    try:
        items = _json.loads(text)
        if not isinstance(items, list):
            items = [items]
        # Remove forbidden fields silently
        for item in items:
            for field in _POOL_FORBIDDEN_FIELDS:
                item.pop(field, None)
        return items if items else None
    except _json.JSONDecodeError:
        return None
```

Update all pool refill parse call sites in `opencode_worker.py` to call `OpencodeWorker._parse_pool_response(raw)`.

- [ ] **Step 4: Run tests to verify they pass**

```
py -m pytest tests/test_opencode_worker.py::test_parse_response_strips_markdown_fences tests/test_opencode_worker.py::test_parse_response_prose_preamble_returns_none tests/test_opencode_worker.py::test_parse_response_strips_forbidden_fields -v
```

Expected: all `PASS`

- [ ] **Step 5: Run full suite**

```
py -m pytest tests/ -v --tb=short -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/opencode_worker.py tests/test_opencode_worker.py
git commit -m "fix(opencode_worker): strip markdown fences/preamble/forbidden-fields in pool refill parse"
```

---

## Task 5: Suppress `reasoningContent` Strands warnings

> HIGH — Emitted 8+ times per session. DeepSeek V4 Flash emits `reasoning_content` tokens on every turn. Strands SDK warns because it cannot include these in multi-turn history.

**Fix:** `warnings.filterwarnings("ignore", ...)` at import time in the module that initialises the Strands session.

**Files:**
- Modify: `src/strands_worker.py`
- Test: `tests/test_strands_worker.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_strands_worker.py — add this test
import warnings

def test_reasoningcontent_warning_suppressed():
    """The strands reasoningContent UserWarning must not propagate after module import."""
    import src.strands_worker  # ensure filter is installed
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        warnings.warn(
            "reasoningContent is not supported in multi-turn conversations with the Chat Completions API.",
            UserWarning,
            stacklevel=1,
        )
    reasoning_warns = [w for w in caught if "reasoningContent" in str(w.message)]
    assert len(reasoning_warns) == 0, "reasoningContent warning should be filtered"
```

- [ ] **Step 2: Run test to verify it fails**

```
py -m pytest tests/test_strands_worker.py::test_reasoningcontent_warning_suppressed -v
```

Expected: `FAIL` — warning is not filtered.

- [ ] **Step 3: Add warning filter in `src/strands_worker.py`**

At the top of `src/strands_worker.py`, after all imports:

```python
import warnings
# DeepSeek models emit reasoning_content tokens in every assistant turn.
# Strands SDK warns because it can't include them in multi-turn Chat Completions history.
# This is expected behaviour for this model — suppress the warning.
warnings.filterwarnings(
    "ignore",
    message="reasoningContent is not supported in multi-turn conversations",
    category=UserWarning,
)
```

- [ ] **Step 4: Run test to verify it passes**

```
py -m pytest tests/test_strands_worker.py::test_reasoningcontent_warning_suppressed -v
```

Expected: `PASS`

- [ ] **Step 5: Run full suite**

```
py -m pytest tests/ -v --tb=short -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/strands_worker.py tests/test_strands_worker.py
git commit -m "fix(strands_worker): suppress DeepSeek reasoningContent UserWarning for multi-turn chat"
```

---

## Task 6: Return valid-action list in FSM layer mismatch error

> MEDIUM — LLM calls `change_visual_state(action="float", layer="fsm")`. Error message gives no guidance; LLM retries the same wrong action.

**Files:**
- Modify: `src/mcp_server.py` (`_handle_change_visual_state`)
- Test: `tests/test_mcp_server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mcp_server.py — add this test
def test_fsm_layer_invalid_action_error_includes_valid_list():
    """Error for invalid FSM action must include list of valid FSM actions."""
    from src.mcp_server import MCPHandler
    from unittest.mock import MagicMock

    handler = MCPHandler.__new__(MCPHandler)
    handler._fsm_bridge = MagicMock()
    handler._action_layer = MagicMock()
    handler._config = {}
    handler._history = None
    handler._memory = None
    handler._diary = None

    result = handler._handle_change_visual_state({"action": "float", "layer": "fsm"})
    assert "error" in result
    msg = result["error"]["message"]
    # Must include some hint of valid options
    assert "idle" in msg.lower() or "valid" in msg.lower() or "bounce" in msg.lower()
```

- [ ] **Step 2: Run test to verify it fails**

```
py -m pytest tests/test_mcp_server.py::test_fsm_layer_invalid_action_error_includes_valid_list -v
```

Expected: `FAIL` — error message is generic.

- [ ] **Step 3: Update the FSM action validation error in `_handle_change_visual_state`**

Locate the block that validates `action` against `FSM_ACTIONS` (or equivalent constant). Change:

```python
if action not in FSM_ACTIONS:
    return {"error": {"code": -32602, "message": f"Action '{action}' is not valid for fsm layer"}}
```

To:

```python
if action not in FSM_ACTIONS:
    valid_list = ", ".join(sorted(FSM_ACTIONS))
    return {"error": {"code": -32602, "message": f"Action '{action}' is not valid for fsm layer. Valid FSM actions: {valid_list}"}}
```

Apply same pattern to expression layer validation if it exists.

- [ ] **Step 4: Run test to verify it passes**

```
py -m pytest tests/test_mcp_server.py::test_fsm_layer_invalid_action_error_includes_valid_list -v
```

Expected: `PASS`

- [ ] **Step 5: Run full suite**

```
py -m pytest tests/ -v --tb=short -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/mcp_server.py tests/test_mcp_server.py
git commit -m "fix(mcp): include valid action list in change_visual_state layer mismatch error"
```

---

## Task 7: Stop click-through poll storm during shutdown

> MEDIUM — After `_force_quit_app()` is called, `ClickThroughManager._poll` continues firing for ~7 seconds.

**Files:**
- Modify: `src/click_through.py`
- Modify: `src/pet_window.py` (call `stop()` in shutdown)
- Test: `tests/test_click_through.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_click_through.py — add this test
def test_poll_exits_immediately_after_stop():
    """_poll must return without toggling after stop() is called."""
    from src.click_through import ClickThroughManager
    from unittest.mock import MagicMock

    get_geom = MagicMock(return_value=None)
    mgr = ClickThroughManager(hwnd=0, get_geometry=get_geom)
    mgr.stop()
    assert mgr._stopped is True

    # _poll after stop must not call get_geometry (would risk touching torn-down Qt objects)
    get_geom.reset_mock()
    mgr._poll()
    get_geom.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

```
py -m pytest tests/test_click_through.py::test_poll_exits_immediately_after_stop -v
```

Expected: `FAIL` — `_stopped` attribute does not exist.

- [ ] **Step 3: Add `stop()` and `_stopped` flag to `ClickThroughManager`**

In `src/click_through.py`:

```python
class ClickThroughManager:
    def __init__(self, hwnd, get_geometry):
        ...
        self._stopped = False    # add this line

    def stop(self):              # add this method
        """Signal the poll loop to exit — call from main thread during shutdown."""
        self._stopped = True

    def _poll(self):
        if self._stopped:        # add at very top of _poll
            return
        # ... rest of _poll unchanged
```

- [ ] **Step 4: Call `stop()` in `_force_quit_app` in `pet_window.py`**

In `_force_quit_app`, before `QApplication.quit()`, add:

```python
if self._click_through is not None:
    self._click_through.stop()
```

- [ ] **Step 5: Run test to verify it passes**

```
py -m pytest tests/test_click_through.py::test_poll_exits_immediately_after_stop -v
```

Expected: `PASS`

- [ ] **Step 6: Run full suite**

```
py -m pytest tests/ -v --tb=short -q
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/click_through.py src/pet_window.py tests/test_click_through.py
git commit -m "fix(click_through): add stop() guard to prevent poll storm during shutdown"
```

---

## Task 8: Fix misleading `brain=0 fields` in startup DATA log

> MEDIUM — Premature log line fires before Firebase sync completes. Causes confusion in log audits.

**Files:**
- Modify: `src/pet_window.py`

- [ ] **Step 1: Find the two startup DATA log calls**

In `src/pet_window.py`, search for:
```python
_log_data_state("Startup")
```

There will be two nearby calls — one before Firebase sync, one after seed data loads.

- [ ] **Step 2: Remove the premature log call**

Delete or comment out the first `_log_data_state("Startup")` call. Keep only the post-sync one. If there's a "Startup+Cache" variant, rename it to just `"Startup"`.

- [ ] **Step 3: Verify manually**

Run Daemon with `--no-opencode --debug` for 5 seconds then quit. Check logs:

```
py daemon.py --no-opencode --debug 2>&1 | Select-String "\[DATA\].*Startup"
```

Expected: exactly ONE `[DATA] Startup` line with `brain=19 fields` (not 0).

- [ ] **Step 4: Commit**

```bash
git add src/pet_window.py
git commit -m "fix(pet_window): remove premature brain=0 startup DATA log before Firebase sync"
```

---

## Task 9: Interpolate brain placeholders into system prompt

> LOW — `{user_nickname}`, `{user_partner_name}`, `{user_engineer_name}` appear literally in every API call payload. LLM outputs them verbatim in dialogue.

**Files:**
- Modify: `src/strands_worker.py`
- Test: `tests/test_strands_worker.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_strands_worker.py — add this test
def test_interpolate_prompt_replaces_placeholders():
    """System prompt placeholders must be replaced with memory values."""
    from src.strands_worker import StrandsWorker

    worker = StrandsWorker.__new__(StrandsWorker)
    memory = {
        "user_name": "Rohan",
        "pet_name": "Kenny",
        "user_partner_name": "Ammi",
        "user_engineer_name": "Rohan",
    }
    raw = "You monitor {user_nickname}. You are {pet_name}. Deployed by {user_partner_name}."
    result = worker._interpolate_prompt(raw, memory)
    assert "{user_nickname}" not in result
    assert "{pet_name}" not in result
    assert "{user_partner_name}" not in result
    assert "Rohan" in result
    assert "Kenny" in result
    assert "Ammi" in result
```

- [ ] **Step 2: Run test to verify it fails**

```
py -m pytest tests/test_strands_worker.py::test_interpolate_prompt_replaces_placeholders -v
```

Expected: `FAIL` — `_interpolate_prompt` method does not exist.

- [ ] **Step 3: Add `_interpolate_prompt` to `strands_worker.py`**

```python
_PROMPT_PLACEHOLDER_MAP = {
    "user_nickname":      "user_name",
    "user_partner_name":  "user_partner_name",
    "user_engineer_name": "user_engineer_name",
    "pet_name":           "pet_name",
}

def _interpolate_prompt(self, prompt: str, memory: dict) -> str:
    """Replace {placeholder} tokens in the system prompt with brain memory values."""
    for placeholder, key in _PROMPT_PLACEHOLDER_MAP.items():
        value = memory.get(key, "")
        if value:
            prompt = prompt.replace("{" + placeholder + "}", str(value))
    return prompt
```

Call `self._interpolate_prompt(system_prompt, memory_dict)` on the system prompt string before passing it to `StrandsSession` or the model initialisation. The memory dict should come from `self._memory.all()` or equivalent.

- [ ] **Step 4: Run test to verify it passes**

```
py -m pytest tests/test_strands_worker.py::test_interpolate_prompt_replaces_placeholders -v
```

Expected: `PASS`

- [ ] **Step 5: Run full suite**

```
py -m pytest tests/ -v --tb=short -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/strands_worker.py tests/test_strands_worker.py
git commit -m "fix(strands_worker): interpolate brain memory into system prompt placeholders"
```

---

## Task 10: Rotate `crash_dump.log` on boot

> LOW — `crash_dump.log` grows without bound. Already 82KB / 1268 entries from one session of a single repeating error.

**Files:**
- Modify: `daemon.py`
- Test: `tests/test_daemon.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_daemon.py — add this test
import pathlib

def test_crash_dump_rotated_when_over_1mb(tmp_path):
    """crash_dump.log > 1MB on boot should be renamed to crash_dump.log.bak."""
    crash_log = tmp_path / "crash_dump.log"
    bak_log   = tmp_path / "crash_dump.log.bak"

    crash_log.write_bytes(b"x" * (1024 * 1024 + 1))  # 1MB + 1 byte

    from daemon import _rotate_crash_dump
    _rotate_crash_dump(crash_log)

    assert bak_log.exists()
    assert not crash_log.exists() or crash_log.stat().st_size == 0
```

- [ ] **Step 2: Run test to verify it fails**

```
py -m pytest tests/test_daemon.py::test_crash_dump_rotated_when_over_1mb -v
```

Expected: `FAIL` — `_rotate_crash_dump` does not exist.

- [ ] **Step 3: Add `_rotate_crash_dump` to `daemon.py`**

```python
def _rotate_crash_dump(crash_path: pathlib.Path, max_bytes: int = 1024 * 1024) -> None:
    """Rotate crash_dump.log to crash_dump.log.bak if it exceeds max_bytes."""
    if crash_path.exists() and crash_path.stat().st_size > max_bytes:
        bak = crash_path.with_suffix(".log.bak")
        bak.unlink(missing_ok=True)
        crash_path.rename(bak)
        # Use print here — logging not yet initialised at this point in boot
        print(f"[daemon] Rotated {crash_path.name} ({crash_path.stat().st_size // 1024}KB -> .bak)")
```

Call it early in `main()` before crash instrumentation is installed:

```python
def main():
    crash_dump_path = pathlib.Path("crash_dump.log")
    _rotate_crash_dump(crash_dump_path)
    # ... rest of main()
```

- [ ] **Step 4: Run test to verify it passes**

```
py -m pytest tests/test_daemon.py::test_crash_dump_rotated_when_over_1mb -v
```

Expected: `PASS`

- [ ] **Step 5: Run full suite**

```
py -m pytest tests/ -v --tb=short -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add daemon.py tests/test_daemon.py
git commit -m "fix(daemon): rotate crash_dump.log to .bak when it exceeds 1MB on boot"
```

---

## Final: Update dev memory and squash to master

- [ ] **Step 1: Update `memory/project-dev-memory.md`**

Record:
- Date: 2026-06-22
- All 10 bugs fixed with task numbers and commit hashes
- New pitfalls:
  - `_pet_x` / `_pet_y` are always `float` — cast to `int` before any `QRect` or `drawLine` call
  - `MCPServer` needs `history=` kwarg or `query_memory(type=history)` always fails silently
  - DeepSeek V4 Flash emits `reasoningContent` tokens — suppress `UserWarning` at module import
  - `{placeholder}` tokens in SKILL.md are not handled by opencode serve — must interpolate in Python before session init
  - `crash_dump.log` has no rotation — add size check on boot
- Updated test count

- [ ] **Step 2: Final test run**

```
py -m pytest tests/ -v --tb=short
```

Expected: all tests pass (705 + ~12 new = ~717+), 1 skipped, 0 failures.

- [ ] **Step 3: Squash merge to master**

```bash
git checkout master
git merge --squash task-<N>-log-audit-fixes
git commit -m "fix: resolve 10 bugs found in production log audit 2026-06-22"
git branch -D task-<N>-log-audit-fixes
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] QRect float crash → Task 1
- [x] drawLine float crash → Task 2
- [x] query_memory history wiring → Task 3
- [x] JSON parse failures (preamble/fences/forbidden fields) → Task 4
- [x] reasoningContent warnings → Task 5
- [x] FSM layer mismatch error hint → Task 6
- [x] Click-through shutdown poll storm → Task 7
- [x] brain=0 premature boot log → Task 8
- [x] System prompt placeholder interpolation → Task 9
- [x] crash_dump.log rotation → Task 10

**Placeholder scan:** None — all steps have concrete, runnable code.

**Type consistency:**
- `_parse_pool_response` is `@staticmethod` on `OpencodeWorker` — consistent with existing `_handle_schema_error`
- `_interpolate_prompt` is instance method on `StrandsWorker` — call site must pass memory dict
- `_rotate_crash_dump` is module-level function in `daemon.py` — matches `_ensure_ffmpeg_on_path` pattern
- `ClickThroughManager.stop()` returns `None` — callers do not check return value
