# Design Spec: Stateless MCP-Driven Autonomous Pipeline

**Date:** 2026-07-05
**Status:** Approved — ready for implementation planning
**Target:** Sub-second perceived response latency, strict token conservation, DeepSeek V4 Flash via OpenCode serve on :4096

---

## 1. Goals & Non-Goals

### Goals
- Replace the Strands SDK stateful model with a lean, stateless burst inference pipeline
- Replace `http.server` MCP implementation with FastMCP SSE (same port/URL, zero config change)
- Add a write-through in-memory config cache with DND circuit breaker and adaptive thresholds
- Implement pruned UIA XML screen context tool and browser sniper tool in the new MCP layer
- Enforce the ephemeral-session-per-burst pattern to prevent OpenCode SQLite accumulation
- Add diary compaction loop with deferred-retry via existing P4 boredom tick

### Non-Goals
- Firebase realtime listener (boot/quit sync preserved)
- Migrating MCP transport to stdio (SSE HTTP on :4097 confirmed — same `opencode.json` URL)
- New FSM states (ActionLayer handles animation variety)
- Any changes to the rendering pipeline, particle system, or emotion engine

---

## 2. Architecture Overview

```
+---------------------------+       +---------------------------+
|   Workflow 1: User Input  |       | Workflow 2: Autonomous    |
|  - Double-click/hotkey    |       | - BehaviorController tick |
|  - UIA pre-fetch fires    |       | - Minimal telemetry XML   |
|    immediately (async)    |       |   payload sent to LLM     |
|  - 5s TTL on pre-fetch    |       | - LLM uses MCP tools for  |
|  - On submit: inject XML  |       |   additional context      |
+------------+--------------+       +------------+--------------+
             |                                   |
             v                                   v
+-----------------------------------------------------------------------------------+
|                         STATELESS BURST COORDINATOR                               |
|                    src/llm/opencode_worker.py (rewritten)                         |
|  - Ephemeral session per burst: POST /session -> message -> DELETE /session       |
|  - XML payload: static cold block + dynamic hot block                             |
|  - Static block budget: <=1200 tokens (provider-side prefix cache target)         |
+------------------------------------------+----------------------------------------+
                                           |
                               HTTP POST :4096 (OpenCode serve)
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                           LOCAL MCP SERVER (FastMCP SSE)                          |
|                      src/mcp_server.py -- QThread, port :4097                     |
|  +-- get_screen_context()     Pruned interactive UIA XML tree (depth 7)           |
|  +-- get_browser_context()    Sniper URL extraction (depth 5, ValuePattern)       |
|  +-- execute_os_action()      Guarded OS control + clipboard-paste path           |
|  +-- trigger_pet_animation()  6 states -> FSMActionBridge.emit_request()          |
|  +-- [13 existing tools preserved and migrated]                                   |
+-----------------------------------------------------------------------------------+
```

---

## 3. Phase 1 — Config Cache & Circuit Breakers

### 3.1 Write-Through Config Cache (`src/config.py`)

**Module-level runtime dict:**
```python
_RUNTIME_CONFIG: dict = {}  # initialized from load_config() at import time
```

**API surface:**
```python
config.get("pet.chattiness")          # dot-path read
config.set("pet.chattiness", 8)       # dot-path write
```

`config.get(key_path, default=None)`:
- Splits on `.`, walks `_RUNTIME_CONFIG` recursively
- Returns `default` if any segment is missing

`config.set(key_path, value)`:
- Writes to `_RUNTIME_CONFIG` in-place
- Fires `threading.Thread(target=_async_save)` — non-blocking disk write
- Does NOT call Firebase directly; dirty flags let WriteCoalescer handle cloud sync at next 8s flush

**Migration:** All consumers that currently do `cfg["pet"]["chattiness"]` migrate to `config.get("pet.chattiness")`.

### 3.2 DND Circuit Breaker

Added to the entry point of both `src/system/apm_worker.py` and `src/system/event_worker.py`:

```python
def _process_tick(self):
    if config.get("behavior.dnd_enabled"):
        self._reset_internal_metrics()
        return
    # ... existing logic
```

- Listeners remain running (APM data still collected for accuracy)
- All autonomous trigger dispatch drops silently
- DND toggle in `SettingsDialog` calls `config.set("behavior.dnd_enabled", True/False)`

### 3.3 Adaptive Idle Threshold (`src/autonomy/behavior_controller.py`)

```python
chattiness = config.get("pet.chattiness", 5)  # 1-10
dynamic_idle_threshold = max(30, BASE_IDLE_SECONDS - (chattiness * 50))
```

Clamped to `[30, BASE_IDLE_SECONDS]`. At chattiness=8: threshold = `BASE - 400s`.

### 3.4 Probability Gate (`src/system/event_worker.py`)

On window switch detection:
```python
chattiness = config.get("pet.chattiness", 5)
if random.random() > (chattiness / 10.0):
    return  # suppress LLM call for this window switch
```

At chattiness=8: 80% of window switches fire. At chattiness=3: only 30% fire.

---

## 4. Phase 2 — FastMCP SSE Server

### 4.1 Transport

**No config change.** `opencode.json` already specifies:
```json
"daemon_fsm": { "type": "remote", "url": "http://127.0.0.1:4097", "enabled": true }
```

FastMCP SSE binds to the same address. `MCPServer(QThread)` using `http.server` is removed and
replaced with a `FastMCP` app running in a `QThread` via `asyncio.run()`.

**COM apartment initialization** (required for UIA tools):
```python
class MCPServerThread(QThread):
    def run(self):
        import pythoncom
        pythoncom.CoInitialize()  # COINIT_APARTMENTTHREADED
        try:
            asyncio.run(self._mcp_app.run_sse_async(host="127.0.0.1", port=4097))
        finally:
            pythoncom.CoUninitialize()
```

### 4.2 New Tools

#### `get_screen_context() -> str`
Returns pruned interactive XML of the foreground window.

- Walk UIA tree from `GetForegroundWindow()`, max depth 7
- Skip `PaneControl`/`GroupControl` where `Name == ""`
- Extract `ButtonControl`, `EditControl`, `HyperlinkControl`, `ListItemControl`
- Output: `<ui><button name="OK" x="100" y="200"/><edit name="Search" x="50" y="10"/></ui>`
- Hard cap: 2000 chars (truncate with `<!-- truncated -->`)
- Uses `threading.local()` COM singleton from existing `screen_reader.py`

#### `get_browser_context() -> dict`
Sniper URL extraction — bypasses deep DOM walk.

- Detect window class: `Chrome_WidgetWin_1`, `MozillaWindowClass`, `ApplicationFrameWindow`
- `searchDepth=5` ceiling to find `EditControl` (address bar)
- Pull via `ValuePattern.CurrentValue`
- Returns `{"url": "https://...", "title": "Page Title"}` or `{"url": null, "title": "..."}` if not a browser

#### `execute_os_action(action, x, y, text, use_clipboard) -> str`
Guarded OS control.

| Param | Type | Description |
|-------|------|-------------|
| `action` | `str` | `"click"` or `"type"` |
| `x` | `int\|None` | Screen X for click |
| `y` | `int\|None` | Screen Y for click |
| `text` | `str\|None` | Text to type (<=50 chars if `use_clipboard=False`) |
| `use_clipboard` | `bool` | If True: write to clipboard + simulate Ctrl+V |

Consent gates:
- `action="type"`, `use_clipboard=False`: requires `allow_keyboard_injection`
- `action="type"`, `use_clipboard=True`: requires `allow_keyboard_injection` AND `allow_clipboard_hijacking`
- `action="click"`: requires `allow_mouse_interference`
- On block: call `trigger_pet_animation("FRUSTRATED")`, return descriptive error string to LLM

Clipboard path:
```python
if use_clipboard:
    _write_to_clipboard(text)       # existing Win32 clipboard helper
    _simulate_keystroke("ctrl+v")   # existing keystroke injector
    return "ok (clipboard paste)"
```

#### `trigger_pet_animation(state) -> str`
Valid states: `IDLE`, `THINKING`, `FRUSTRATED`, `SMUG`, `SHOCKED`, `LAUGHING`

```python
@mcp.tool()
def trigger_pet_animation(state: str) -> str:
    valid = {"IDLE", "THINKING", "FRUSTRATED", "SMUG", "SHOCKED", "LAUGHING"}
    if state.upper() not in valid:
        return f"Invalid state. Must be one of: {', '.join(valid)}"
    _bridge.emit_request(state.upper())  # pyqtSignal auto-promotes to QueuedConnection
    return "ok"
```

State -> Daemon mapping:

| MCP State | Daemon Mapping |
|-----------|---------------|
| `IDLE` | `PetState.IDLE` |
| `THINKING` | `PetState.THINKING` |
| `FRUSTRATED` | ActionLayer `frustrated` expression |
| `SMUG` | ActionLayer `smug` expression |
| `SHOCKED` | ActionLayer `shocked` expression |
| `LAUGHING` | ActionLayer `laughing` expression |

### 4.3 Preserved Tools (migrated to FastMCP)

All 13 existing tools re-implemented as `@mcp.tool()` decorated functions:
`read_clipboard`, `capture_blackmail_evidence`, `send_system_toast`, `list_directory`, `read_file`,
`search_codebase`, `get_memory`, `get_diary`, `simulate_keystroke`, `move_mouse`,
`browser_navigation`, `set_log_level`, `get_recent_git_diff`, `set_reminder`, `get_reminders`,
`dismiss_reminder`

Consent map (`_CONSENT_TOOL_MAP`) migrates directly to tool-level consent checks.

### 4.4 Removed Infrastructure

- `MCPServer(QThread)` with `http.server.HTTPServer`
- `BaseHTTPRequestHandler` / `MCPHandler`
- SSE broadcast connection registry (`_active_sse_handlers`)
- `/health`, `/metrics` HTTP endpoints (Prometheus via `prometheus_client.start_http_server()` on separate port, or log-only)

---

## 5. Phase 3 — Thread-Safe Animation Bridge

### 5.1 `trigger_state_override(state, duration_ms)` in `src/ui/pet_window.py`

```python
@pyqtSlot(str, int)
def trigger_state_override(self, state: str, duration_ms: int = 2000):
    """Thread-safe. Routes MCP animation requests to FSM/ActionLayer."""
    fsm_states = {"IDLE": PetState.IDLE, "THINKING": PetState.THINKING}
    action_states = {"FRUSTRATED", "SMUG", "SHOCKED", "LAUGHING"}
    if state in fsm_states:
        self._fsm.transition_to(fsm_states[state])
    elif state in action_states:
        self._action_layer.trigger(state.lower(), duration_ms)
        self._animation_override_active = True
        QTimer.singleShot(duration_ms, self._clear_animation_override)
```

`FSMActionBridge` connects `action_requested` signal to `trigger_state_override` slot on init.

### 5.2 Animation Override Lock

```python
def _clear_animation_override(self):
    self._animation_override_active = False

def _should_fire_autonomous(self) -> bool:
    if self._animation_override_active:
        return False
    # ... existing guards
```

Prevents autonomous triggers from interrupting MCP-initiated expressions.

---

## 6. Phase 4 — Stateless Burst Execution Coordinator

### 6.1 Rip-Out List

Remove entirely:
- `src/llm/strands_worker.py`
- `src/llm/llm_session_persistence.py`
- All `session_turn_completed` signal wiring in `pet_window.py`
- `_opencode_session_id` persistent state in `pet_window.py`
- `history_context` injection logic in `opencode_worker.py`
- `strands` from `requirements.txt`
- `tests/test_llm_session_persistence.py`
- `tests/test_strands_worker.py`

### 6.2 Ephemeral Session Pattern

Every burst:
1. `POST /session` → `{"id": "sess_abc123"}`
2. `POST /session/sess_abc123/message` → full XML payload → response
3. `DELETE /session/sess_abc123` → cleanup, zero SQLite accumulation

Session lifecycle entirely inside `OpencodeWorker.run()`. Nothing persisted to disk.

```python
def run(self):
    session_id = self._create_session()
    if not session_id:
        self.error.emit("session_create_failed")
        return
    try:
        payload = self._build_xml_payload()
        raw = self._post_message(session_id, payload)
        self._parse_and_emit(raw)
    finally:
        self._delete_session(session_id)  # always cleanup
```

### 6.3 Dual-Trigger Dispatcher

**Workflow 1 — User Initiated:**
```
double-click -> overlay opens
  -> UIA pre-fetch fires in QThreadPool (async, non-blocking)
  -> _prefetch_result = None, _prefetch_timestamp = time.monotonic()

user presses Enter -> _on_input_submitted()
  -> if time.monotonic() - _prefetch_timestamp > 5.0:
       _prefetch_result = _fetch_screen_context_sync()  # TTL expired: synchronous re-fetch
  -> build payload: static_block + dynamic_block + screen_context_block + user_input
  -> OpencodeWorker(prompt=payload, is_autonomous=False).start()
```

**Workflow 2 — Autonomous:**
```
BehaviorController fires CHAT/BOREDOM/JOKE event
  -> build payload: static_block + dynamic_block + minimal telemetry XML
  -> OpencodeWorker(prompt=payload, is_autonomous=True).start()
  -> LLM uses MCP tools (get_screen_context, get_memory, etc.) for additional context if needed
```

Pre-fetch runs in `QThreadPool` (not `QThread`) to avoid thread creation overhead for a short operation.

### 6.4 XML Payload Structure

**Static cold block** (<=1200 tokens, injected in every burst — targets provider prefix cache):

```xml
<system_configuration>
  <safety_permissions>
    <keyboard_input_granted>{bool}</keyboard_input_granted>
    <mouse_clicks_granted>{bool}</mouse_clicks_granted>
    <clipboard_granted>{bool}</clipboard_granted>
    <animations_granted>{bool}</animations_granted>
  </safety_permissions>
  <personality_constraints>
    <chattiness>{n}/10</chattiness>
    <nsfw_level>{level}</nsfw_level>
    <tone>{pet.personality}</tone>
  </personality_constraints>
</system_configuration>
<identities>
  <user>
    <name>{user_name}</name>
    <profession>{user_profession}</profession>
    <habits>{comma-separated}</habits>
    <focus_apps>{comma-separated}</focus_apps>
    <distraction_apps>{comma-separated}</distraction_apps>
  </user>
  <pet>
    <name>{pet_name}</name>
    <role>{pet_role}</role>
    <mission>{mission_directive}</mission>
    <quirks>{comma-separated}</quirks>
    <fears>{comma-separated}</fears>
    <catchphrases>{top 3, semicolon-separated}</catchphrases>
  </pet>
</identities>
```

**Condensation rules:**
- Arrays → comma-separated inline strings. No nested sub-elements.
- Narrative prose stripped to one dense sentence per field.
- `<catchphrases>` trimmed to top 3 most character-defining lines.

**Dynamic hot block** (appended per burst, never cached):

```xml
<trigger_context>
  <source>{Autonomous Cycle | User Input}</source>
  <event_type>{Context Switch | System Idle | User Query}</event_type>
  <telemetry_summary>{window}, APM {n}, idle {n}s</telemetry_summary>
  <typing_preview>{last 100 chars of typing buffer, if present}</typing_preview>
</trigger_context>
<memory_state>
  <mood>{pet_current_mood}</mood>
  <affinity>{pet_affinity_score}</affinity>
  <latest_summary>{memory.latest_summary}</latest_summary>
</memory_state>
```

**Screen context block** (Workflow 1 only, when pre-fetch available):
```xml
<screen_context>
  {pruned UIA XML from get_screen_context()}
</screen_context>
```

**Memory builder split in `src/llm/context_manager.py`:**
- `build_static_block() -> str` — reads `Memory` + `config`, rarely changes
- `build_dynamic_block(apm, idle, window, typing) -> str` — runtime telemetry, called per trigger

### 6.5 ThoughtPool — Unchanged

Cache-first logic preserved. Burst fires only when:
1. Pool below `THOUGHT_POOL_THRESHOLD` (15)
2. User-initiated query (always fires regardless of pool state)

---

## 7. Phase 5 — Firebase & Diary Compaction

### 7.1 Firebase Sync (minimal change)

Boot/quit sync preserved. No persistent listener added.
`config.set()` mutations mark WriteCoalescer dirty flags — cloud sync at next 8s flush.

### 7.2 Rolling Diary Compaction (`src/diary_store.py`)

Trigger: `COMPACTION_TRIGGER_COUNT = 10` fresh (unsummarized) entries.

```python
def check_compaction_needed(self) -> bool:
    fresh = sum(1 for e in self._entries if not e.get("summarized"))
    return fresh >= COMPACTION_TRIGGER_COUNT
```

**Compaction worker** (runs in `daemon=True` thread):
1. Collect fresh entries
2. Ephemeral OpenCode session burst (same POST/DELETE pattern as Phase 4)
3. On response: `memory.remember("latest_summary", summary)`
4. Mark entries `summarized=True`, `_write_atomic()`
5. `write_coalescer.mark_dirty("brain")` → Firebase sync at next flush

**Deferred retry via P4 boredom tick:**
- If compaction skipped (query in flight): `_compaction_deferred = True`
- `BehaviorController` P4 boredom path checks flag
- Retries on next qualifying idle cycle (APM == 0, no query pending, `_compaction_in_flight == False`)

---

## 8. Key Decisions Reference

| Decision | Rationale |
|----------|-----------|
| FastMCP SSE on :4097 | `opencode.json` already `type=remote` HTTP. In-process SSE preserves singleton access. |
| Ephemeral session per burst | Prevents SQLite accumulation. XML payload carries all context. |
| `pyqtSignal` cross-thread, not `queue.Queue` | PyQt6 auto-promotes to `QueuedConnection`. FSMActionBridge already uses this. |
| 5s TTL on UIA pre-fetch | Stale tree re-fetched synchronously. Happy path (type <5s) is zero-latency. |
| `use_clipboard=True` for long text | Bypasses 50-char keystroke cap. Requires both clipboard + keyboard consent. |
| `pythoncom.CoInitialize()` in `MCPServerThread.run()` | Required for UIA in non-main threads. `CoUninitialize()` in `finally` block. |
| Diary compaction retry via P4 boredom tick | Decoupled from APMWorker. Uses existing idle-detection path. No new timers. |
| Static XML block <=1200 tokens | Targets provider prefix cache. Dynamic block always fresh. |
| `StrandsWorker` + `LLMSessionPersistence` fully removed | Full clean rip-out. No shim compatibility layer. |
| BehaviorController, ThoughtPool, WriteCoalescer untouched | Core autonomous loop is solid. Only LLM execution layer changes. |

---

## 9. Files Touched Summary

| File | Action |
|------|--------|
| `src/config.py` | Add `_RUNTIME_CONFIG`, `config.get()`, `config.set()`, `_async_save()` |
| `src/system/apm_worker.py` | DND gate, adaptive idle threshold |
| `src/system/event_worker.py` | DND gate, probability gate |
| `src/autonomy/behavior_controller.py` | Adaptive threshold, diary compaction retry in P4 |
| `src/mcp_server.py` | Full rewrite: FastMCP SSE, 4 new tools, 13 migrated tools, COM init |
| `src/fsm_bridge.py` | Verify `emit_request()` callable cross-thread via `pyqtSignal` |
| `src/ui/pet_window.py` | `trigger_state_override()`, `_animation_override_active`, pre-fetch TTL, remove session wiring |
| `src/llm/opencode_worker.py` | Full rewrite: ephemeral session, dual-trigger, XML payload builder |
| `src/llm/context_manager.py` | `build_static_block()`, `build_dynamic_block()`, XML format |
| `src/diary_store.py` | `check_compaction_needed()`, `_run_compaction()`, `_compaction_deferred` flag |
| `src/llm/strands_worker.py` | **DELETE** |
| `src/llm/llm_session_persistence.py` | **DELETE** |
| `requirements.txt` | Remove `strands` |
| `tests/test_strands_worker.py` | **DELETE** |
| `tests/test_llm_session_persistence.py` | **DELETE** |

---

## 10. Test Strategy

Each phase must leave the full test suite green before the next phase begins.
Regression gate: `py -m pytest tests/ -v --timeout=30`

| Phase | New tests required |
|-------|--------------------|
| 1 | `test_config_cache.py` — `config.get/set`, dot-path, async save, DND gate, adaptive threshold, probability gate |
| 2 | `test_mcp_server.py` rewrite — FastMCP tool dispatch, consent gates, UIA XML pruning, browser sniper, clipboard path |
| 3 | `test_animation_bridge.py` — `trigger_state_override`, override lock, `_clear_animation_override` |
| 4 | `test_opencode_worker.py` rewrite — ephemeral session lifecycle, XML payload, pre-fetch TTL, dual-trigger paths |
| 5 | `test_diary_compaction.py` — trigger threshold, deferred flag, P4 retry, `_compaction_in_flight` guard |

---

*Spec written 2026-07-05. Approved for implementation planning.*
