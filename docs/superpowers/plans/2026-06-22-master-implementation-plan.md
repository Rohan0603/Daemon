# Daemon — Master Implementation Plan
> Log audit `daemon_2026-06-22_11-40-12.log` · **33 tasks across 5 phases** (finalized 2026-06-22)

> **For agentic workers:** Use `superpowers:subagent-driven-development`. One subagent per phase. Each phase is a self-contained feature branch. Do NOT skip phases.

## Brainstorm Decisions (locked)
| Item | Decision |
|------|----------|
| Task 4.6 typewriter | **Approach A** — local QTimer fake typewriter. Full JSON arrives, reveal char-by-char. No streaming arch changes. |
| Task 3.4 mid-session summary | **DROPPED** — 40-turn window sufficient for real sessions; summary costs tokens and risks context confusion. |
| Task 5.1 Web UI stack | **bare `http.server` + JS `setInterval` polling every 5s** — consistent with MCPServer pattern, zero new deps. |
| Task 5.4 plugin return type | **`Optional[str]` dialogue only** — plugins are for custom reactions, not FSM control. Simple, testable. |
| Task 5.6 TTS mouth-sync | **DROPPED** — TTS voice not planned for near-term implementation. |

---

## Branch Strategy

```bash
git checkout master
git checkout -b task-74-log-audit-phase1   # Phase 1 (Critical)
# ... work, squash merge
git checkout -b task-75-log-audit-phase2   # Phase 2 (Stability)
# ... etc.
```

**Current baseline:** 705 passed, 1 skipped, 54 test files.

---

## Phase 1 — Critical Crashes (B1, B2, B14)
> Branch: `task-74-log-audit-phase1`
> Goal: Zero exceptions per second. Stop crash_dump.log from growing.

---

### Task 1.1 — Fix QRect float crash in `_get_click_geometry`

**Root cause:** `_pet_x` / `_pet_y` are `float` from physics engine. `QRect(int, int, int, int)` is strict in PyQt6. Fires every 50ms in `click_through.py` poll.

**Evidence (crash_dump.log):**
```
TypeError: arguments did not match any overloaded call:
  QRect(int, int, int, int): argument 2 has unexpected type 'float'
```

- [ ] Write failing test in `tests/test_click_through.py`:
```python
def test_get_click_geometry_float_coords(mocker):
    from src.pet_window import PetWindow
    from PyQt6.QtCore import QRect
    win = PetWindow.__new__(PetWindow)
    win._pet_x, win._pet_y = 123.7, 456.2
    win._scale = win._pet_scale = 1.0
    win._bubble_text = ""
    win._input_field = mocker.Mock(isVisible=lambda: False)
    rect = win._get_click_geometry()  # must not raise
    assert isinstance(rect, QRect)
```
- [ ] Run → confirm `FAIL`
- [ ] Fix `pet_window.py:410` — wrap `_pet_x` and `_pet_y` in `int()`:
```python
rect = QRect(
    int(self._pet_x), int(self._pet_y),
    int(PET_WIDTH  * getattr(self, '_scale', 1.0) * getattr(self, '_pet_scale', 1.0)),
    int(PET_HEIGHT * getattr(self, '_scale', 1.0) * getattr(self, '_pet_scale', 1.0))
)
```
- [ ] Run → confirm `PASS`
- [ ] Commit: `fix(click_through): cast pet_x/pet_y to int in _get_click_geometry`

---

### Task 1.2 — Fix `drawLine` float crash in PERIMETER speedlines

**Root cause:** Same float origin. `py = ctx.pet_y` (float) used directly in `painter.drawLine(x, py+20+y_off, ...)`.

**Evidence (crash_dump.log, log line 4400-4406):**
```
TypeError: drawLine(x1,y1,x2,y2): argument 2 has unexpected type 'float'
```

- [ ] Write failing test in `tests/test_pet_renderer.py`:
```python
def test_perimeter_speedlines_float_coords():
    from PyQt6.QtGui import QImage, QPainter
    from src.pet_renderer import PetRenderer, RenderContext
    from src.pet_fsm import PetState
    img = QImage(400, 400, QImage.Format.Format_ARGB32)
    p = QPainter(img)
    ctx = RenderContext(
        state=PetState.PERIMETER, pet_x=50.7, pet_y=100.3,
        scale_x=1.0, scale_y=1.0, rotation=0.0,
        cursor_x=0, cursor_y=0, state_elapsed_ms=0, land_elapsed_ms=0,
        bubble_text="", bubble_alpha=0.0, bubble_rect=None,
        edge="bottom", facing="right", wander_direction=1,
        emotion=None, apm=0,
    )
    PetRenderer.render(p, ctx)  # must not raise
    p.end()
```
- [ ] Run → confirm `FAIL`
- [ ] Fix `pet_renderer.py:463-467` — cast all coords to `int` before drawLine:
```python
dx = -10 * ctx.wander_direction
for i in range(3):
    y_off = (i - 1) * 6
    x1 = int(px + (PET_WIDTH if ctx.wander_direction > 0 else 0) + dx + i * 4 * (-ctx.wander_direction))
    y1 = int(py + 20 + y_off)
    x2 = int(x1 + 8 * (-ctx.wander_direction))
    painter.drawLine(x1, y1, x2, y1)
```
  Also confirm `px = int(ctx.pet_x)` and `py = int(ctx.pet_y)` exist at top of render. Add casts if missing.
- [ ] Run → confirm `PASS`
- [ ] Commit: `fix(renderer): cast float coords to int before drawLine in PERIMETER speedlines`

---

### Task 1.3 — Remove `print(DEBUG:...)` from production `_dispatch_structured`

**Evidence (pet_window.py:1831):**
```python
print(f"DEBUG: _dispatch_structured: thought='{thought}', dialogue='{dialogue}'")
```
Fires on every single dispatch — every bubble, every pool draw, every user response.

- [ ] Delete line 1831 from `src/pet_window.py`. No test needed — verify with grep:
```
py -m pytest tests/ -v --tb=short -q
grep -n "DEBUG: _dispatch_structured" src/pet_window.py  # should return nothing
```
- [ ] Commit: `fix(pet_window): remove debug print from _dispatch_structured`

---

### Task 1.4 — Rotate `crash_dump.log` on boot

- [ ] Write failing test in `tests/test_daemon.py`:
```python
def test_crash_dump_rotated_when_over_1mb(tmp_path):
    from daemon import _rotate_crash_dump
    log = tmp_path / "crash_dump.log"
    log.write_bytes(b"x" * (1024 * 1024 + 1))
    _rotate_crash_dump(log)
    assert (tmp_path / "crash_dump.log.bak").exists()
    assert not log.exists() or log.stat().st_size == 0
```
- [ ] Run → confirm `FAIL`
- [ ] Add to `daemon.py`:
```python
def _rotate_crash_dump(path: pathlib.Path, max_bytes: int = 1_048_576) -> None:
    if path.exists() and path.stat().st_size > max_bytes:
        bak = path.with_suffix(".log.bak")
        bak.unlink(missing_ok=True)
        path.rename(bak)
        print(f"[daemon] Rotated {path.name} to .bak")
```
  Call `_rotate_crash_dump(pathlib.Path("crash_dump.log"))` early in `main()`.
- [ ] Run → confirm `PASS`
- [ ] Commit: `fix(daemon): rotate crash_dump.log to .bak at boot when >1MB`

---

### Phase 1 Completion

```bash
py -m pytest tests/ -v --tb=short -q   # expect 707+ pass
git checkout master
git merge --squash task-74-log-audit-phase1
git commit -m "fix: phase 1 critical crash fixes — QRect, drawLine, debug print, crash_dump rotation"
git branch -D task-74-log-audit-phase1
```

---

## Phase 2 — Stability Bugs (B3-B15, F6)
> Branch: `task-75-log-audit-phase2`
> Goal: Zero tool failures, correct bubble timing, boredom accuracy, history cap enforcement.

---

### Task 2.1 — Wire `History` into `MCPServer` (`query_memory type=history`)

**Evidence (log):** `Tool execution failed: Store type 'history' is not configured/available.`

- [ ] Write failing test in `tests/test_mcp_server.py`:
```python
def test_query_memory_history_wired():
    from src.mcp_server import MCPHandler
    from unittest.mock import MagicMock
    h = MagicMock()
    h.query.return_value = [{"role": "user", "content": "hi"}]
    handler = MCPHandler.__new__(MCPHandler)
    handler._memory = handler._diary = None
    handler._history = h
    result = handler._handle_query_memory({"type": "history", "limit": 5})
    assert "error" not in result
    assert result["result"]["count"] == 1
```
- [ ] Run → confirm `FAIL`
- [ ] Fix `src/mcp_server.py` — add `history=None` param to `MCPServer.__init__`, store as `self.history`. Pass `history=self.history` when constructing `MCPHandler`.
- [ ] Fix `src/pet_window.py` — pass `history=self._history` when constructing `MCPServer`.
- [ ] Run → confirm `PASS`
- [ ] Commit: `fix(mcp): wire History into MCPServer for query_memory type=history`

---

### Task 2.2 — Fix pool refill JSON parse failures (markdown fences + preamble + forbidden fields)

**Evidence:** 6 parse failures per session. LLM sends `"Here are 5 thoughts:"` preamble or ` ```json ``` ` fences. Items also contain forbidden fields (`action`, `target_x`).

- [ ] Write failing tests in `tests/test_opencode_worker.py`:
```python
def test_parse_pool_strips_md_fences():
    from src.opencode_worker import OpencodeWorker
    raw = '```json\n[{"type":"idle_thought","thought":"ok","dialogue":"ok","priority":2}]\n```'
    r = OpencodeWorker._parse_pool_response(raw)
    assert r and len(r) == 1 and r[0]["type"] == "idle_thought"

def test_parse_pool_prose_returns_none():
    from src.opencode_worker import OpencodeWorker
    assert OpencodeWorker._parse_pool_response("Here are 5 thoughts:") is None

def test_parse_pool_strips_forbidden_fields():
    from src.opencode_worker import OpencodeWorker
    raw = '[{"type":"typing_reaction","dialogue":"ok","thought":"ok","action":"hyper","target_x":0}]'
    r = OpencodeWorker._parse_pool_response(raw)
    assert r and "action" not in r[0] and "target_x" not in r[0]
```
- [ ] Run → confirm `FAIL`
- [ ] Add `_parse_pool_response(raw: str) -> list | None` static method to `OpencodeWorker`:
```python
_POOL_FORBIDDEN = frozenset({"action", "target_x", "target_y", "mode"})

@staticmethod
def _parse_pool_response(raw: str) -> list | None:
    if not raw or not raw.strip():
        return None
    text = raw.strip()
    # Strip markdown fences
    if text.startswith("```"):
        lines, in_fence, inner = text.splitlines(), False, []
        for line in lines:
            if line.startswith("```") and not in_fence: in_fence = True; continue
            if line.startswith("```") and in_fence: break
            if in_fence: inner.append(line)
        text = "\n".join(inner).strip()
    # Find array bounds
    start = text.find("[")
    if start == -1:
        brace = text.find("{")
        if brace == -1: return None
        text = "[" + text[brace:] + "]"
    else:
        text = text[start:]
    end = text.rfind("]")
    if end == -1: return None
    text = text[:end + 1]
    try:
        items = json.loads(text)
        if isinstance(items, dict): items = [items]
        for item in items:
            for f in OpencodeWorker._POOL_FORBIDDEN: item.pop(f, None)
        return items or None
    except json.JSONDecodeError:
        return None
```
  Update all pool refill parse call sites in `opencode_worker.py` to use `_parse_pool_response`.
- [ ] Run → confirm `PASS`
- [ ] Commit: `fix(opencode_worker): strip fences/preamble/forbidden fields in pool refill parse`

---

### Task 2.3 — Suppress `reasoningContent` Strands warning

**Evidence:** 8+ occurrences of `"reasoningContent is not supported in multi-turn conversations"` per session. DeepSeek model behaviour — not actionable.

- [ ] Write test in `tests/test_strands_worker.py`:
```python
import warnings
def test_reasoningcontent_warning_suppressed():
    import src.strands_worker
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        warnings.warn(
            "reasoningContent is not supported in multi-turn conversations with the Chat Completions API.",
            UserWarning
        )
    assert not any("reasoningContent" in str(w.message) for w in caught)
```
- [ ] Run → confirm `FAIL`
- [ ] Add at top of `src/strands_worker.py` (after imports):
```python
import warnings
warnings.filterwarnings(
    "ignore",
    message="reasoningContent is not supported in multi-turn conversations",
    category=UserWarning,
)
```
- [ ] Run → confirm `PASS`
- [ ] Commit: `fix(strands_worker): suppress DeepSeek reasoningContent UserWarning`

---

### Task 2.4 — FSM layer mismatch error includes valid action list

**Evidence:** `"Tool execution failed: Action 'float' is not valid for fsm layer"` — LLM retries same wrong action because error gives no hint.

- [ ] Write test in `tests/test_mcp_server.py`:
```python
def test_fsm_invalid_action_error_includes_valid_list():
    from src.mcp_server import MCPHandler
    from unittest.mock import MagicMock
    h = MCPHandler.__new__(MCPHandler)
    h._fsm_bridge = MagicMock(); h._action_layer = MagicMock(); h._config = {}
    h._history = h._memory = h._diary = None
    result = h._handle_change_visual_state({"action": "float", "layer": "fsm"})
    msg = result["error"]["message"]
    assert "idle" in msg.lower() or "valid" in msg.lower() or "bounce" in msg.lower()
```
- [ ] Run → confirm `FAIL`
- [ ] In `_handle_change_visual_state` where FSM action validation fails, change:
```python
# before
return {"error": {"code": -32602, "message": f"Action '{action}' is not valid for fsm layer"}}
# after
valid = ", ".join(sorted(FSM_ACTIONS))
return {"error": {"code": -32602, "message": f"Action '{action}' is not valid for fsm layer. Valid FSM actions: {valid}"}}
```
- [ ] Run → confirm `PASS`
- [ ] Commit: `fix(mcp): include valid FSM action list in layer mismatch error`

---

### Task 2.5 — Click-through shutdown poll storm

**Evidence:** 10 enable/disable events in 7s during shutdown window. `_poll` has no exit guard.

- [ ] Write test in `tests/test_click_through.py`:
```python
def test_poll_exits_after_stop(mocker):
    from src.click_through import ClickThroughManager
    get_geom = mocker.Mock(return_value=None)
    mgr = ClickThroughManager(hwnd=0, get_geometry=get_geom)
    mgr.stop()
    assert mgr._stopped is True
    get_geom.reset_mock()
    mgr._poll()
    get_geom.assert_not_called()
```
- [ ] Run → confirm `FAIL`
- [ ] Add to `ClickThroughManager` in `src/click_through.py`:
```python
def __init__(self, ...):
    ...
    self._stopped = False

def stop(self):
    self._stopped = True

def _poll(self):
    if self._stopped:
        return
    # ... existing poll logic unchanged
```
- [ ] In `pet_window.py` `_force_quit_app`, add before `QApplication.quit()`:
```python
if self._click_through is not None:
    self._click_through.stop()
```
- [ ] Run → confirm `PASS`
- [ ] Commit: `fix(click_through): add stop() guard to prevent poll storm during shutdown`

---

### Task 2.6 — Remove premature `brain=0` startup DATA log

**Evidence:** `[DATA] Startup | brain=0 fields` fires before Firebase sync. Misleading in log audits.

- [ ] Search `pet_window.py` for `_log_data_state("Startup")`. Find the one that fires before `sync_to_local` completes. Delete it. Keep only the post-sync call.
- [ ] Verify:
```
py daemon.py --no-opencode --debug 2>&1 | Select-String "\[DATA\].*Startup"
```
  Expected: single line with correct `brain=N fields` (not 0).
- [ ] Commit: `fix(pet_window): remove premature brain=0 startup DATA log line`

---

### Task 2.7 — Interpolate brain placeholders into system prompt

**Evidence:** Every API call payload contains literal `{user_nickname}`, `{user_partner_name}`, `{user_engineer_name}`. LLM outputs these verbatim in dialogue.

- [ ] Write test in `tests/test_strands_worker.py`:
```python
def test_interpolate_prompt_replaces_placeholders():
    from src.strands_worker import StrandsWorker
    w = StrandsWorker.__new__(StrandsWorker)
    mem = {"user_name": "Rohan", "pet_name": "Kenny", "user_partner_name": "Ammi"}
    raw = "Monitor {user_nickname}. You are {pet_name}. Boss is {user_partner_name}."
    result = w._interpolate_prompt(raw, mem)
    assert "{user_nickname}" not in result
    assert "Rohan" in result and "Kenny" in result and "Ammi" in result
```
- [ ] Run → confirm `FAIL`
- [ ] Add to `src/strands_worker.py`:
```python
_PLACEHOLDER_MAP = {
    "user_nickname":      "user_name",
    "user_partner_name":  "user_partner_name",
    "user_engineer_name": "user_engineer_name",
    "pet_name":           "pet_name",
}

def _interpolate_prompt(self, prompt: str, memory: dict) -> str:
    for placeholder, key in _PLACEHOLDER_MAP.items():
        val = memory.get(key, "")
        if val:
            prompt = prompt.replace("{" + placeholder + "}", str(val))
    return prompt
```
  Call `_interpolate_prompt(system_prompt, memory_dict)` on the system prompt before passing to the Strands session.
- [ ] Run → confirm `PASS`
- [ ] Commit: `fix(strands_worker): interpolate brain memory into system prompt placeholders`

---

### Task 2.8 — Enrich single-stage refill prompt with Kenny persona + schema

**Evidence (log lines 61-71):** Single-stage refill sends only window title + APM + "Generate 5 thoughts". No persona, no schema, no stammer requirement. LLM ignores the JSON format because it has no context for it.

- [ ] Write test in `tests/test_opencode_worker.py`:
```python
def test_single_stage_refill_prompt_has_persona():
    from src.opencode_worker import OpencodeWorker
    prompt = OpencodeWorker.build_single_stage_refill_prompt(
        window="VS Code", apm=15, count=5
    )
    assert "Kenny" in prompt or "kenny" in prompt or "JSON" in prompt
    assert "typing_reaction" in prompt
    assert "dialogue" in prompt
```
- [ ] Run → confirm `FAIL`
- [ ] Add `build_single_stage_refill_prompt(window, apm, count)` classmethod to `OpencodeWorker`. Include a condensed 3-line persona preamble + JSON schema reminder:
```python
@classmethod
def build_single_stage_refill_prompt(cls, window: str, apm: int, count: int) -> str:
    return (
        f"You are Kenny — anxious Python process. Speak with stammers. RAM obsessed.\n"
        f"Screen: {window}  APM: {apm}\n"
        f"Return ONLY a JSON array of exactly {count} objects. "
        f'Each: {{"type": one of typing_reaction|observation|intel_roast|idle_thought, '
        f'"thought": str max 150 chars, "dialogue": str max 100 chars with stammers, "priority": 1-5}}\n'
        f"No markdown. No preamble. Raw JSON array only."
    )
```
  Wire it into the single-stage refill call site in `opencode_worker.py` or `response_manager.py`.
- [ ] Run → confirm `PASS`
- [ ] Commit: `fix(opencode_worker): add persona+schema to single-stage refill prompt`

---

### Task 2.9 — Bubble queue TTL (stale reactions)

**Evidence:** Queue hits 10 items. Items queued at 11:46 (APM=0 reaction) displayed at 12:07. Context entirely stale.

**Design:** Convert `_bubble_queue: list[str]` to `list[tuple[str, float]]` where float is `time.time()` at enqueue. When popping next item from queue, discard any item older than `BUBBLE_QUEUE_TTL_SECS` (new constant, default 25).

- [ ] Write test in `tests/test_pet_window.py`:
```python
import time
def test_bubble_queue_discards_stale_items(pet_window_fixture, mocker):
    win = pet_window_fixture
    mocker.patch("time.time", return_value=1000.0)
    win._show_bubble("stale message")  # enqueued at t=1000 while bubble active
    # simulate current bubble finishing, then check TTL
    mocker.patch("time.time", return_value=1030.0)  # 30s later — past TTL=25
    win._bubble_text = ""  # current bubble expired
    win._advance_bubble_queue()  # should discard stale item
    assert win._bubble_text == ""  # stale item discarded, not shown
```
- [ ] Run → confirm `FAIL`
- [ ] Add `BUBBLE_QUEUE_TTL_SECS = 25` to `src/constants.py`.
- [ ] In `src/pet_window.py`:
  - Change `_bubble_queue: list[str]` to `list[tuple[str, float]]`
  - When enqueuing: `self._bubble_queue.append((text, time.time()))`
  - When popping next: filter out entries where `time.time() - enqueue_time > BUBBLE_QUEUE_TTL_SECS`, log each discard at DEBUG level
- [ ] Run → confirm `PASS`
- [ ] Commit: `fix(pet_window): add TTL to bubble queue — discard stale reactions after 25s`

---

### Task 2.10 — Clear bubble queue on SLEEP entry + reset boredom timer

**Evidence:**
- Queue not cleared on SLEEP → 7 stale items delivered as wake-up non-sequiturs
- `_boredom_timer_ms` accumulates during SLEEP → spurious boredom fires on wake

- [ ] Write test in `tests/test_pet_window.py`:
```python
def test_bubble_queue_cleared_on_sleep_entry(pet_window_fixture):
    win = pet_window_fixture
    win._bubble_queue = [("msg1", time.time()), ("msg2", time.time())]
    win._enter_sleep_state()  # or however sleep is triggered
    assert len(win._bubble_queue) == 0

def test_boredom_timer_reset_on_sleep_entry(pet_window_fixture):
    win = pet_window_fixture
    win._behavior._boredom_timer_ms = 90000  # 90s accumulated
    win._enter_sleep_state()
    assert win._behavior._boredom_timer_ms == 0
```
- [ ] Run → confirm `FAIL`
- [ ] In the FSM transition handler for SLEEP entry in `pet_window.py`:
  - Call `self._clear_bubble_queue()`
  - Call `self._behavior._boredom_timer_ms = 0` (or equivalent reset)
- [ ] Run → confirm `PASS`
- [ ] Commit: `fix(pet_window): clear bubble queue and reset boredom timer on SLEEP entry`

---

### Task 2.11 — Audit and fix `History` 100-entry cap

**Evidence:** `history=418 entries` at shutdown. Cap is documented as 100 in AGENTS.md.

- [ ] Inspect `src/history.py` — find `add_entry` and `_save`. Verify cap is enforced. Check if `HISTORY_MAX_ENTRIES` is read or if hard `100` is used.
- [ ] Write test:
```python
def test_history_cap_enforced():
    from src.history import History
    import tempfile, pathlib
    with tempfile.TemporaryDirectory() as tmp:
        h = History(path=pathlib.Path(tmp) / "hist.json")
        for i in range(150):
            h.add_entry(f"user {i}", f"assistant {i}", "idle")
        assert len(h._entries) <= 100
```
- [ ] Run → confirm `FAIL` (if cap is broken) or investigate why 418 entries appeared
- [ ] Fix the cap enforcement in `History.add_entry()`. Trim to `HISTORY_MAX_ENTRIES` on every add.
- [ ] Run → confirm `PASS`
- [ ] Commit: `fix(history): enforce 100-entry cap in add_entry`

---

### Phase 2 Completion

```bash
py -m pytest tests/ -v --tb=short -q   # expect 720+ pass
git checkout master
git merge --squash task-75-log-audit-phase2
git commit -m "fix: phase 2 stability — history wire, JSON parse, prompt placeholders, bubble TTL, sleep/boredom, history cap"
git branch -D task-75-log-audit-phase2
```

---

## Phase 3 — Performance & Observability (P1-P4, B12-partially, E7, E8)
> Branch: `task-76-log-audit-phase3`

---

### Task 3.1 — Stagger pool item TTLs to prevent bulk expiry cascade

**Evidence:** `TTL purge: removed 4 stale items (pool 4→0)` — all generated in same refill batch, all same timestamp → all expire simultaneously → emergency refill at bad time.

- [ ] In `response_pool.py` or wherever items are added, apply jitter to `created_at`:
```python
import random
item["_created_at"] = time.time() + random.uniform(-60, 60)
```
  This spreads expiry across ±60s of the nominal TTL so they don't cluster.
- [ ] Write test:
```python
def test_pool_items_have_staggered_expiry():
    # Add 5 items; verify _created_at values differ by at least 1s between some
    ...
    timestamps = [item["_created_at"] for item in pool._items]
    assert max(timestamps) - min(timestamps) > 1.0
```
- [ ] Commit: `perf(response_pool): stagger item TTLs with ±60s jitter to prevent bulk expiry`

---

### Task 3.2 — Propagate correlation ID into worker threads

**Evidence:** All `opencode_worker`, `strands_worker`, `httpcore` lines show `cid=-`. Worker threads inherit blank ContextVar.

- [ ] In `OpencodeWorker.__init__` and `StrandsWorker.__init__`, accept `correlation_id: str = ""` parameter.
- [ ] At top of `run()` in each worker, call `set_correlation_id(self._correlation_id)`.
- [ ] At all call sites where workers are instantiated, pass `correlation_id=get_correlation_id()`.
- [ ] Test: verify that worker log lines appear with parent cid after the fix.
- [ ] Commit: `fix(workers): propagate correlation ID into OpencodeWorker and StrandsWorker threads`

---

### Task 3.3 — Cache Strands tool manifest (prevent 4x redundant fetches)

**Evidence:** 4 separate `tool configuration` fetches per session init.

- [ ] Add class-level `_tool_manifest_cache: dict = {}` to `StrandsWorker` or wherever the Strands session is initialised.
- [ ] Before `MCPClient` tool fetch, check cache keyed by `(server_url, session_id)`.
- [ ] Invalidate cache on MCP server restart.
- [ ] Commit: `perf(strands_worker): cache tool manifest to avoid redundant fetches per session`

---

### ~~Task 3.4~~ — DROPPED: Mid-session LLM context summary

> **Decision:** Dropped. The 40-turn sliding window is large enough for real sessions (average session ~15 turns observed in logs). Mid-session injection risks confusing multi-turn history — a synthetic assistant summary turn could cause hallucinations. Token cost not justified.

---

### Task 3.4 — Log rejected `brain_update` fields as structured WARNING (E7)

> *(Renumbered from 3.5 — replaces dropped context summary task)*

**Evidence:** `brain_update` invalid writes silently dropped. No visibility into LLM trying to override locked fields.

- [ ] In `src/brain_schema.py` `apply_brain_update()`, when a field is rejected (locked or invalid type), emit:
```python
logger.warning("brain_update: rejected '%s' (locked field)", field_name)
```
- [ ] Add Prometheus counter `daemon_brain_update_rejections_total` to observability.
- [ ] Test: mock a brain_update with a locked field and assert warning is logged.
- [ ] Commit: `feat(brain_schema): log and count rejected brain_update writes`

---

### Task 3.5 — Prometheus counters (bubble queue depth, TTL purges, SLEEP entries) (E8)

> *(Renumbered from 3.6)*

---

### Task 3.6 — Prometheus counters for bubble queue depth, TTL purges, SLEEP entries (E8)

- [ ] Add to `src/observability.py`:
  - `daemon_bubble_queue_depth` gauge (poll from `PetWindow._bubble_queue` every 1s)
  - `daemon_pool_ttl_purge_total` counter (increment in `response_pool.py` TTL purge)
  - `daemon_sleep_entries_total` counter (increment in FSM SLEEP transition handler)
  - `daemon_json_parse_failures_total` counter (increment in `_parse_pool_response` on `None`)
- [ ] Wire counters at each call site.
- [ ] Test: confirm counters are registered and accessible via `/metrics`.
- [ ] Commit: `feat(observability): add bubble queue, pool TTL, sleep, parse-failure Prometheus counters`

---

### Phase 3 Completion

```bash
py -m pytest tests/ -v --tb=short -q
git checkout master
git merge --squash task-76-log-audit-phase3
git commit -m "perf: phase 3 — TTL jitter, cid propagation, tool cache, session summary, brain_update logging, metrics"
git branch -D task-76-log-audit-phase3
```

---

## Phase 4 — Enhancements (E1-E6)
> Branch: `task-77-log-audit-phase4`
> Goal: Visible UX improvements. Each enhancement is independently shippable.

---

### Task 4.1 — Bubble queue hard cap at 5 + TTL (E1 prerequisite)

Already partially done in Task 2.9 (TTL). Add the hard cap:

- [ ] When `_show_bubble` is called and `len(self._bubble_queue) >= BUBBLE_QUEUE_MAX_SIZE` (or a new `BUBBLE_QUEUE_SOFT_CAP = 5`), drop the oldest item (not the new one). Pool surplus goes to `ThoughtPool`, not queue.
- [ ] Test: add 10 items to queue, assert only 5 retained.
- [ ] Commit: `fix(pet_window): cap bubble queue at 5 items — drop oldest on overflow`

---

### Task 4.2 — `!command` autocomplete hint popover (E3)

When user types `!` in input field, show a Qt tooltip listing all `!commands`:

- [ ] In `pet_window.py`, connect `_input_field.textChanged` signal.
- [ ] When text starts with `!`, call `QToolTip.showText(pos, hint)` with list:
```
!remember key: value — store a fact
!forget key — remove a fact
!memories — list all facts
!history — show recent conversation
```
- [ ] Tooltip hides when text no longer starts with `!` or input field loses focus.
- [ ] Test: simulate textChanged signal with `"!"` and verify tooltip is triggered (mock QToolTip).
- [ ] Commit: `feat(pet_window): show !command autocomplete tooltip in input field`

---

### Task 4.3 — Global hotkey to open input field (E6)

Extend existing `APMWorker` hotkey infra (`Ctrl+Alt+D`) to add a second hotkey `Ctrl+Alt+K`:

- [ ] In `src/apm_worker.py`, add `Ctrl+Alt+K` to the hotkey combination listener.
- [ ] Emit a new `input_field_requested = pyqtSignal()` signal.
- [ ] In `pet_window.py`, connect `apm_worker.input_field_requested` to `_show_input_field()` (or equivalent method).
- [ ] If pet is in SLEEP state, wake it first then show input field.
- [ ] Test: mock hotkey combination press, assert `input_field_requested` signal emitted.
- [ ] Commit: `feat(apm_worker): Ctrl+Alt+K global hotkey to open Daemon input field`

---

### Task 4.4 — APM sparkline in system tray icon (E5)

Every 5s, repaint the tray icon as a 16×16 APM bar chart:

- [ ] In `pet_window.py`, maintain `_apm_history: deque[int] = deque(maxlen=16)` — one sample per tray refresh.
- [ ] Add `_refresh_tray_icon()` called by a 5s `QTimer`.
- [ ] Draw a 16×16 `QPixmap`: 16 bars, each 1px wide, height = `max(1, int(apm/200*15))`, dark background, green bars. Use `QPainter`.
- [ ] Set on `self._tray.setIcon(QIcon(pixmap))`.
- [ ] Test: call `_refresh_tray_icon()` and assert `_tray.setIcon` was called with a valid QIcon.
- [ ] Commit: `feat(pet_window): APM sparkline in system tray icon (5s refresh)`

---

### Task 4.5 — Diary auto-summary morning briefing (E4)

On first boot of the day, if diary has ≥ 3 entries since last session, Kenny delivers a morning briefing:

- [ ] Add `last_session_date: str` to `data/.daemon_state.json` (date string `YYYY-MM-DD`).
- [ ] On boot, compare `last_session_date` with today's date.
- [ ] If new day AND `len(recent_diary_entries) >= 3`: trigger a one-shot LLM call with last 5 diary entries, request a single-sentence Kenny-persona summary. Show as bubble.
- [ ] Set `progression_flags["morning_briefing_done_today"]` to prevent re-firing on restart.
- [ ] Test: mock diary with 3+ entries and a new day → assert briefing trigger fires.
- [ ] Commit: `feat(pet_window): morning briefing bubble on first boot of day if diary has entries`

---

### Task 4.6 — Typewriter bubble effect (E1)

> **Design: Approach A — local fake typewriter. No streaming architecture changes.**

Full JSON arrives as normal → parsed → full `dialogue` text stored in `_typewriter_buffer`. A 30ms `QTimer` reveals it at ~4 chars/tick into `_bubble_text`. TTS still receives the full text immediately. No changes to `StrandsWorker` or token pipeline.

**Why A over B/C:** JSON tokens are not displayable mid-stream (`{"type": "typi...` is garbage). Regex-intercept (B) is fragile against schema changes. Field-ordering (C) relies on LLM respecting JSON key order — not guaranteed. A gives identical UX with zero risk.

- [ ] Add `TYPEWRITER_CHARS_PER_TICK = 4` and `TYPEWRITER_TICK_MS = 30` to `src/constants.py`.
- [ ] Add to `PetWindow.__init__`:
  - `self._typewriter_buffer: str = ""`
  - `self._typewriter_pos: int = 0`
  - `self._typewriter_timer = QTimer(self); self._typewriter_timer.timeout.connect(self._tick_typewriter)`
- [ ] Add `_tick_typewriter()` method:
```python
def _tick_typewriter(self) -> None:
    end = min(self._typewriter_pos + TYPEWRITER_CHARS_PER_TICK, len(self._typewriter_buffer))
    self._bubble_text = self._typewriter_buffer[:end]
    self._typewriter_pos = end
    self.update()
    if self._typewriter_pos >= len(self._typewriter_buffer):
        self._typewriter_timer.stop()
```
- [ ] Modify `_show_bubble(text)` to feed typewriter instead of setting `_bubble_text` directly:
```python
self._typewriter_buffer = text
self._typewriter_pos = 0
self._bubble_text = ""
self._typewriter_timer.start(TYPEWRITER_TICK_MS)
```
  TTS enqueue still uses full `text` (unchanged).
- [ ] Ensure `_clear_bubble_queue()` also stops typewriter timer + resets buffer.
- [ ] Test: call `_show_bubble("hello world")` → assert `_bubble_text == ""` initially → after N timer ticks → assert `_bubble_text == "hello world"`.
- [ ] Commit: `feat(pet_window): typewriter bubble effect via local QTimer reveal`

---

### Phase 4 Completion

```bash
py -m pytest tests/ -v --tb=short -q
git checkout master
git merge --squash task-77-log-audit-phase4
git commit -m "feat: phase 4 — bubble cap, !command hint, global hotkey, tray sparkline, morning briefing, typewriter stream"
git branch -D task-77-log-audit-phase4
```

---

## Phase 5 — Future Features (F1-F7)
> Branch: `task-78-log-audit-phase5`
> These are larger features. Each should be sub-specced before implementation if complex. Mark incomplete ones as `[ ] TODO` if time-boxed.

---

### Task 5.1 — Web UI for memory/diary/pool inspection (F3)

**Port:** 4098.
**Stack decision: bare `http.server` (consistent with MCPServer) + inline HTML + JS `setInterval` polling every 5s. Zero new dependencies.**

- [ ] Create `src/web_server.py` — `WebServer(QThread)` using `http.server.HTTPServer` in a daemon thread (same pattern as `MCPServer`).
- [ ] Endpoints:
  - `GET /` — serves inline dark-theme HTML/JS dashboard (no external files)
  - `GET /api/memory` — returns `Memory.all()` as JSON
  - `GET /api/diary` — returns `DiaryStore.all()` as JSON
  - `GET /api/pool` — returns `ThoughtPool._items` as JSON (type, priority, dialogue preview)
  - `GET /api/brain` — returns full brain schema fields as JSON
  - `POST /api/memory` — update a single memory fact `{key, value}`
- [ ] Dashboard: dark `#0d1117` background, monospace font, one collapsible section per store. No frameworks — pure `fetch()` + DOM manipulation.
- [ ] Start in `PetWindow.__init__` after `MCPServer.start()`. Stop in `_force_quit_app`.
- [ ] Test: `GET /api/memory` returns JSON with expected keys. `POST /api/memory` mutates Memory.
- [ ] Commit: `feat(web_server): local web UI on port 4098 — bare http.server + inline HTML`

---

### Task 5.2 — SHA-256 context hash (prevent hash collisions) (F7)

- [ ] Find `context_hash` computation in `response_pool.py` or `behavior_controller.py`.
- [ ] Replace current hash with `hashlib.sha256(context_str.encode()).hexdigest()[:8]`.
- [ ] Test: two distinct context strings → distinct hashes (regression test).
- [ ] Commit: `fix(response_pool): use SHA-256 context hash to prevent collisions`

---

### Task 5.3 — Emotion history timeline (F4)

- [ ] Add `_emotion_log: list[tuple[float, str]] = []` to `EmotionAnimator`.
- [ ] On `set_emotion(emotion)`, append `(time.time(), emotion.name)` to log (cap at 200 entries).
- [ ] New MCP tool `get_emotion_history` in `mcp_server.py` — returns last N log entries.
- [ ] Add to `thought_log_dialog.py` a second tab "Emotion Timeline" with timestamped list.
- [ ] Test: transition through 3 emotions, assert log has 3 entries.
- [ ] Commit: `feat(animator+mcp): emotion history timeline log + get_emotion_history MCP tool`

---

### Task 5.4 — Plugin system for custom reaction triggers (F2)

**Design decision: plugins return `Optional[str]` (dialogue only). Not `TriggerEvent`, not EventBus. Plugins are for custom _reactions_ — they surface text into the bubble pipeline. FSM control stays internal.**

- [ ] Define `DaemonPlugin` ABC in `src/plugin_base.py`:
```python
from abc import ABC, abstractmethod
from src.pet_fsm import FSMContext
from typing import Optional

class DaemonPlugin(ABC):
    name: str = "unnamed_plugin"

    @abstractmethod
    def on_tick(self, ctx: FSMContext) -> Optional[str]:
        """Return a dialogue string to show in bubble, or None to do nothing."""

    def on_load(self) -> None:
        """Called once when plugin is loaded. Optional setup."""

    def on_unload(self) -> None:
        """Called on shutdown. Optional cleanup."""
```
- [ ] In `BehaviorController._master_tick()`, after the built-in priority tree (lowest priority — never overrides P1-P4), iterate `_plugins: list[DaemonPlugin]`. First non-None return wins → bubble shown.
- [ ] In `daemon.py` at boot, scan `plugins/*.py` for classes implementing `DaemonPlugin`. Import + instantiate. Call `on_load()`. Store in list passed to `BehaviorController`.
- [ ] Ship one example: `plugins/example_git_commit.py` — detects if active window is a git terminal and reacts with a random "oh no you committed WHAT" line.
- [ ] Test:
  - Mock plugin returning `"hello"` → verify fires in master_tick after priority tree
  - Mock plugin returning `None` → verify no bubble
  - Empty plugins dir → no error
- [ ] Commit: `feat(behavior_controller): plugin system — DaemonPlugin ABC, plugins/ dir loader, Optional[str] return`

---

### Task 5.5 — Multi-pet colony mode (F1)

**Requires:** F2 (plugin system) and stable architecture.

- [ ] Make single-instance lock (`data/.daemon.lock`) optional via `--allow-multi` CLI flag.
- [ ] Each instance uses `--pet-id <name>` (already supported) for separate Firebase docs.
- [ ] Per-instance `MCPServer` port derived from `pet_id` hash (e.g., `4097 + hash(pet_id) % 100`).
- [ ] Per-instance `crash_dump.log` named `crash_dump_<pet_id>.log`.
- [ ] Test: verify two instances with different `--pet-id` values don't share PID lock.
- [ ] Commit: `feat(daemon): multi-pet colony mode via --allow-multi flag`

---

### ~~Task 5.6~~ — DROPPED: Streamed TTS with mouth-sync

> **Decision:** Dropped. TTS voice feature is not planned for near-term implementation. Mouth-sync has no base to build on without streamed TTS. Revisit if TTS becomes a focus later.

---

### Task 5.7 — Per-emotion distinct particle behaviours (E2)

Currently `ParticleSystem` is generic. Apply emotion-specific configs:

- [ ] In `animator.py` `EMOTION_PROFILES`, add `particle_config: dict | None` per emotion:
```python
ANGER:      {"color": "#E74C3C", "drift_x": -0.5, "gravity": 0.02, "size": 3}
DEVOTION:   {"color": "#FF69B4", "shape": "heart", "drift_y": -0.3, "size": 5}
FEAR:       {"color": "#6B5B95", "scatter": True, "speed": 3.0}
WONDER:     {"color": "#FFFFFF", "flash": True, "burst_count": 20}
```
- [ ] Update `ParticleSystem.emit()` to accept and apply `particle_config`.
- [ ] Test each emotion's particle config renders without exception.
- [ ] Commit: `feat(animator): per-emotion distinct particle behaviours`

---

### Phase 5 Completion

```bash
py -m pytest tests/ -v --tb=short -q
git checkout master
git merge --squash task-78-log-audit-phase5
git commit -m "feat: phase 5 — web UI, SHA-256 hash, emotion timeline, plugin system, multi-pet, TTS mouth-sync, emotion particles"
git branch -D task-78-log-audit-phase5
```

---

## Update Dev Memory

After all phases complete:

- [ ] Update `memory/project-dev-memory.md`:
  - New test count
  - All 35 tasks recorded with commit hashes
  - New pitfalls:
    - `_pet_x`/`_pet_y` always `float` — cast to `int` before ANY Qt geometry call
    - `MCPServer` needs `history=` kwarg or `query_memory(type=history)` silently fails
    - DeepSeek V4 Flash emits `reasoningContent` tokens — suppress `UserWarning` at import
    - `{placeholder}` in SKILL.md not handled by opencode serve — must interpolate in Python
    - Bubble queue has no TTL by default — stale reactions accumulate across minutes
    - All pool items generated in same batch expire simultaneously — use TTL jitter
    - Worker QThreads inherit blank ContextVar → `cid=-` in all worker logs
  - Phase numbers: this work = Phase 74-78

---

## Full Task Inventory

> 🔴 Critical · 🟠 High · 🟡 Medium · 🟢 Low · 🔵 Feature · ~~strikethrough~~ = Dropped

| Task | Phase | Category | Sev | File(s) | Status |
|------|-------|----------|-----|---------|--------|
| 1.1 | 1 | Bug | 🔴 | `pet_window.py:410` | `[ ]` |
| 1.2 | 1 | Bug | 🔴 | `pet_renderer.py:463` | `[ ]` |
| 1.3 | 1 | Bug | 🟢 | `pet_window.py:1831` | `[ ]` |
| 1.4 | 1 | Bug | 🟢 | `daemon.py` | `[ ]` |
| 2.1 | 2 | Bug | 🟠 | `mcp_server.py`, `pet_window.py` | `[ ]` |
| 2.2 | 2 | Bug | 🟠 | `opencode_worker.py` | `[ ]` |
| 2.3 | 2 | Bug | 🟠 | `strands_worker.py` | `[ ]` |
| 2.4 | 2 | Bug | 🟡 | `mcp_server.py` | `[ ]` |
| 2.5 | 2 | Bug | 🟡 | `click_through.py`, `pet_window.py` | `[ ]` |
| 2.6 | 2 | Bug | 🟡 | `pet_window.py` | `[ ]` |
| 2.7 | 2 | Bug | 🟢 | `strands_worker.py` | `[ ]` |
| 2.8 | 2 | Bug | 🟡 | `opencode_worker.py` | `[ ]` |
| 2.9 | 2 | Bug | 🟠 | `pet_window.py`, `constants.py` | `[ ]` |
| 2.10 | 2 | Bug | 🟡 | `pet_window.py`, `behavior_controller.py` | `[ ]` |
| 2.11 | 2 | Audit | 🟡 | `history.py` | `[ ]` |
| 3.1 | 3 | Perf | 🟡 | `response_pool.py` | `[ ]` |
| 3.2 | 3 | Perf | 🟢 | `opencode_worker.py`, `strands_worker.py` | `[ ]` |
| 3.3 | 3 | Perf | 🟢 | `strands_worker.py` | `[ ]` |
| ~~3.4~~ | ~~3~~ | ~~Perf~~ | — | ~~`strands_worker.py`~~ | **DROPPED** |
| 3.4 | 3 | Enhancement | 🟢 | `brain_schema.py`, `observability.py` | `[ ]` |
| 3.5 | 3 | Enhancement | 🟢 | `observability.py` | `[ ]` |
| 4.1 | 4 | Enhancement | 🟡 | `pet_window.py` | `[ ]` |
| 4.2 | 4 | Enhancement | 🟢 | `pet_window.py` | `[ ]` |
| 4.3 | 4 | Enhancement | 🟢 | `apm_worker.py`, `pet_window.py` | `[ ]` |
| 4.4 | 4 | Enhancement | 🟢 | `pet_window.py` (tray) | `[ ]` |
| 4.5 | 4 | Enhancement | 🟢 | `pet_window.py`, `diary_store.py` | `[ ]` |
| 4.6 | 4 | Enhancement | 🟢 | `pet_window.py` only (Approach A) | `[ ]` |
| 5.1 | 5 | Feature | 🔵 | `src/web_server.py` (new, bare http.server) | `[ ]` |
| 5.2 | 5 | Feature | 🟡 | `response_pool.py` | `[ ]` |
| 5.3 | 5 | Feature | 🔵 | `animator.py`, `mcp_server.py` | `[ ]` |
| 5.4 | 5 | Feature | 🔵 | `src/plugin_base.py` (new, Optional[str] return) | `[ ]` |
| 5.5 | 5 | Feature | 🔵 | `daemon.py` | `[ ]` |
| ~~5.6~~ | ~~5~~ | ~~Feature~~ | — | ~~`tts_worker.py`~~ | **DROPPED** |
| 5.6 | 5 | Enhancement | 🟢 | `animator.py` | `[ ]` |

**Total: 33 active tasks across 5 phases. 2 dropped (3.4 context summary, 5.6 TTS mouth-sync).**

---

## Pitfalls to Carry Forward (add to dev memory after each phase)

- `_pet_x`/`_pet_y` are always `float` — cast to `int` before ANY Qt geometry/draw call
- `MCPServer` needs `history=` kwarg or `query_memory(type=history)` silently fails
- DeepSeek V4 Flash emits `reasoningContent` tokens — suppress `UserWarning` at module import in `strands_worker.py`
- `{placeholder}` in SKILL.md not interpolated by opencode serve — must interpolate in Python before session init
- Bubble queue has no TTL — stale reactions accumulate; use `(text, time.time())` tuples and discard on pop if age > 25s
- Pool items generated in same batch expire simultaneously — apply `random.uniform(-60, 60)` jitter at insertion
- Worker `QThread`s inherit blank `ContextVar` → `cid=-` in all worker logs; pass cid in constructor, call `set_correlation_id` at top of `run()`
- Plugin `on_tick()` must return `Optional[str]` only — no FSM calls, no direct pet state mutation
