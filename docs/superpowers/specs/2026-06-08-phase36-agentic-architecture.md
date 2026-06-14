# Phase 36 — Agentic Architecture: Native Agent Skills + MCP FSM Bridge

**Date:** 2026-06-08
**Status:** Draft
**Author:** AI-assisted design, reviewed and refined with user

## Overview

Phase 36 rewrites Daemon's OpenCode integration from a passive noReply context-injection pattern to a native agentic architecture using OpenCode's built-in Agent Skills (SKILL.md), structured JSON Schema outputs, and a local MCP server for real-time FSM control.

Goals:
- Delete ~300 lines of fragile Python bridging code (context injection, JSON regex parsing)
- Save ~2500 tokens per session by eliminating persona re-injection
- Enable real-time FSM reactions via MCP tool calls (asynchronous to dialogue generation)
- Eliminate 4 known bug surfaces in `_parse_json_batch`/`_parse_json_response`

## Section 1 — Native Agent Skills (Replace noReply)

### Current State

- `assets/daemon-skill.md` (385 lines) loaded by `ContextManager.inject_full()` via `POST /session/{id}/message` with `noReply: true`
- ~2500 tokens of persona + instructions injected into session on every new session or 15-min heartbeat
- `inject_delta()` re-sends APM/window/memory deltas
- `ContextManager` manages snapshot timing, re-injection heartbeat, delta accumulation

### Changes

#### Create `.opencode/skills/kenny/SKILL.md`

YAML frontmatter:
```yaml
---
name: kenny
description: 100% Kenny persona from High on Life — desktop companion with Gatlian attitude
license: MIT
compatibility: opencode
metadata:
  role: desktop-pet
  game: high-on-life
---
```

Content migrated from `assets/daemon-skill.md`:
- Identity anchor — Kenny the Gatlian gun
- Verbal tics, fourth-wall breaking, profanity (R-rated)
- Action matrix (all 10 FSM actions with descriptions)
- Multiplexed output contract (active_chat, joke, boredom, curiosity modes)
- JSON output spec with brain_update protocol
- Dialogue examples with stuttering, Kenny-style stammering
- Bickering Pair protocol (kenny_roast / kenny_panic modes)

#### Delete `assets/daemon-skill.md`

Content safely migrated to `.opencode/skills/kenny/SKILL.md`.

#### Refactor `src/context_manager.py`

**Delete:**
- `inject_full()` — no longer needed; SKILL.md provides static persona
- `inject_delta()` — no longer needed; dynamic context in build_context()
- `needs_reinjection()` — no heartbeat timer needed
- `_last_injection_time`, `REINJECTION_HEARTBEAT_SEC` — timer logic removed

**Keep and rename:**
- `_snapshot_current()` → internal, collects APM/window/memory/diary telemetry
- `build_user_trigger()`/`build_autonomous_trigger()` → consolidated into `build_context(mode, user_input="")`
- `reset()` — clears snapshot for new session

**New `build_context()` output spec (~150 tokens):**
```
APM: 0 (idle 183s) | Window: "Stardew Valley" | Mood: devastated
Memory: user hates turn-based games | Diary: "played civ all night"
Thought: "This chucklehead is ignoring me again."
```

#### Refactor `src/opencode_worker.py`

**Delete:**
- `inject_context()` method
- `_handle_injection_response()` method
- `send_trigger()` → renamed to `send()`
- `injection_done` signal
- `session_id` management for injection (PetWindow still tracks session)

**Keep:**
- `session_created` signal (session creation still needed)
- `trigger_ready` signal → renamed to `response_ready`
- Error handling, timeout logic, CLI fallback

#### Refactor `src/pet_window.py`

**Delete:**
- `_injection_worker` cleanup (local variable no longer created)
- `_injection_cooldown_active` flag
- `_injection_cooldown` timer
- Re-injection heartbeat timer (15-min)
- `_on_injection_done` handler
- `_on_injection_error` handler

**Keep:**
- `_opencode_session_id` tracking
- Session creation on first message

#### Refactor `daemon.py`

**Delete:**
- `ContextManager` import and construction
- `context_manager` argument passed to PetWindow

### Data Flow After

```
User input / timer tick
  → PetWindow._dispatch_trigger() or tick handler
  → ContextManager.build_context(mode, user_input)
  → OpencodeWorker.send(prompt)
  → POST /session/{id}/message  # SKILL.md applied server-side
  → LLM returns schema-validated JSON array
  → PetWindow dispatches actions to FSM + renders dialogue
```

### Token Impact

| Operation | Before | After | Savings |
|-----------|--------|-------|---------|
| Session start | 2500 tokens injection | 0 | 2500 |
| Per trigger | 100 tokens prompt | 250 tokens (includes context) | -150 |
| Re-injection (15min) | 2500 tokens | 0 | 2500 |
| Break-even | 1 query | — | Massive net savings |

## Section 2 — JSON Schema Structured Outputs

### Current State

- `_parse_json_batch()` (~60 lines) — regex brace-depth splitter for JSON arrays
- `_parse_json_response()` (~40 lines) — regex fallback for single objects
- `_normalize_parsed()` (~20 lines) — field normalization
- `_brace_split_depth()` (~15 lines) — brace-depth counter helper
- 4 known bug surfaces (unquoted keys, nested brackets in strings, markdown fences, trailing commas)
- 4 bugfix rounds across Phases 8, 9, 17, 31

### Changes

#### Add schema to `src/constants.py` or `src/opencode_worker.py`

```python
STRUCTURED_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "thought":      {"type": "string", "maxLength": 200},
            "dialogue":     {"type": "string", "maxLength": 150},
            "action":       {"type": "string", "enum": list(Action)},
            "mode":         {"type": "string", "enum": list(Mode)},
            "target_x":     {"type": ["integer", "null"]},
            "target_y":     {"type": ["integer", "null"]},
            "brain_update": {
                "type": "object",
                "description": "Optional dict to update user memory facts.",
                "additionalProperties": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            }
        },
        "required": ["thought", "dialogue", "action"],
        "additionalProperties": False,
    },
    "minItems": 1,
    "maxItems": 5,
}
```

#### Pass schema in POST body

```python
requests.post(url, json={
    "message": prompt,
    "structured": STRUCTURED_SCHEMA,
})
```

#### Delete from `src/opencode_worker.py`

- `_parse_json_batch()` — entire method
- `_parse_json_response()` — entire method
- `_normalize_parsed()` — entire method
- `_brace_split_depth()` — entire helper

#### Delete from `src/pet_window.py`

- Any parsing logic that assumed `_parse_json_batch` output format

#### Add fallback handler

```python
def _handle_schema_error(self, raw_response: str) -> list[dict]:
    """Return safe default when schema validation fails."""
    logger.error("Schema validation failed: %s", raw_response)
    return [{
        "thought": "Schema parse failed",
        "dialogue": "Holy crap, my brain just segfaulted.",
        "action": "devastated"
    }]
```

### Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Schema validation error from API | `_handle_schema_error()` returns safe default |
| Model exceeds maxLength | Schema enforces server-side truncation |
| AdditionalProperties rejection | Explicit `additionalProperties: False` catches drift |
| Missing required fields | Schema returns clear error, fallback handles |

### Net Result

- ~100 lines of parsing code deleted
- 4 known bug surfaces eliminated
- Zero regex in the Python codebase

## Section 3 — MCP Server for FSM Actions

### Architecture

In-process stdlib `http.server` on a daemon thread, port 4097. Implements MCP JSON-RPC 2.0 over HTTP with SSE initialization.

```
                    ┌──────────────────────────┐
  opencode serve    │  localhost:4097           │
  (MCP remote)      │  GET /sse → SSE init      │
                    │  POST /message → JSON-RPC │
                    └─────┬────────────────────┘
                          │ pyqtSignal
                    ┌─────┴────────────────────┐
                    │ FSMActionBridge(QObject)  │
                    │  .request.emit()         │
                    └─────┬────────────────────┘
                          │ main thread slot
                    ┌─────┴────────────────────┐
                    │ PetWindow                │
                    │  ._on_fsm_action()       │
                    │  .transition_to()        │
                    │  .update()               │
                    └──────────────────────────┘
```

### Single MCP Tool

```python
MCP_TOOLS = [{
    "name": "change_visual_state",
    "description": "Change Daemon's visual state (shake, spin, hyper, etc.)",
    "inputSchema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["idle", "wander", "shake", "spin", "hyper",
                         "bounce", "look_away", "celebrate", "devastated", "fall"]
            },
            "target_x": {"type": "integer", "description": "X target for chase/wander"},
            "target_y": {"type": "integer", "description": "Y target for chase/wander"}
        },
        "required": ["action"]
    }
}]
```

Rationale for single tool:
- LLM reads one schema instead of 10
- Mirror the `action` enum already defined in JSON schema
- Token-efficient (<50 tokens in MCP tool definition)

### Transport Layer

#### GET /sse

```
Content-Type: text/event-stream

event: endpoint
data: /message

: keepalive (every 30s)

```

No actual event streaming needed for Phase 36 — MCP `tools/list` and `tools/call` are synchronous request/response. The SSE endpoint exists solely to satisfy the MCP initialization protocol.

#### POST /message

Accepts JSON-RPC 2.0 requests:

```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "change_visual_state",
        "arguments": {"action": "shake"}
    }
}
```

Response:
```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "content": [{"type": "text", "text": "ok"}]
    }
}
```

### Thread Safety (FSMActionBridge)

```python
class FSMActionBridge(QObject):
    request = pyqtSignal(str, object, object)  # action, target_x, target_y

    def __init__(self):
        super().__init__()
        self._mutex = QMutex()

    def emit_request(self, action: str, target_x=None, target_y=None):
        with QMutexLocker(self._mutex):
            self.request.emit(action, target_x, target_y)

    def _do_fsm_action(self, action: str, target_x, target_y):
        """Called from main thread via signal-slot connection."""
        # PetFSM.transition_to(action, target_x, target_y)
```

### Data Flow After MCP

```
LLM decides: "Kenny should shake in terror"

Phase 1 (immediate): MCP tool call
  → POST /message (tools/call change_visual_state {"action": "shake"})
  → http.server handler
  → FSMActionBridge.emit_request("shake")
  → pyqtSignal → main thread
  → PetFSM.transition_to(SHAKING)
  → QWidget.update() → visual shake instantly

Phase 2 (parallel): Dialogue generation continues
  → LLM finishes generating JSON
  → Returns structured array with dialogue + thought
  → PetWindow renders speech bubble

Result: Pet reacts visually before dialogue finishes rendering
```

### Configuration

In `opencode.json`:
```json
{
    "mcp": {
        "daemon_fsm": {
            "type": "remote",
            "url": "http://127.0.0.1:4097",
            "enabled": true
        }
    }
}
```

### MCP Server Lifecycle

| Event | Action |
|-------|--------|
| Daemon boot | Start MCP server thread on port 4097 |
| Daemon quit | Stop MCP server thread (join with 3s timeout) |
| Port occupied | Log warning, skip MCP (non-fatal) |
| Handler error | Log + return JSON-RPC error response |

### New Files

| File | Purpose | Lines (est) |
|------|---------|-------------|
| `src/fsm_bridge.py` | `FSMActionBridge(QObject)` + signal | 15 |
| `src/mcp_server.py` | `MCPServer` — HTTP server, JSON-RPC dispatch, SSE init | 120 |
| `.opencode/skills/kenny/SKILL.md` | Full Kenny persona + action matrix + output contract | 200 |
| `opencode.json` | MCP server config | 8 |

### Files Deleted

| File | Lines | Reason |
|------|-------|--------|
| `assets/daemon-skill.md` | ~385 | Migrated to SKILL.md |

### Modified Files

| File | Change |
|------|--------|
| `src/context_manager.py` | Gut inject_*, heartbeat; rename to build_context |
| `src/opencode_worker.py` | Remove inject_context, _parse_*, rename send_trigger → send |
| `src/pet_window.py` | Remove injection cooldown, heartbeat, parsing signals |
| `daemon.py` | Remove ContextManager wiring, add MCP server start/stop |
| `src/constants.py` | Add STRUCTURED_SCHEMA, MCP_PORT, MCP_HOST |

### Net Line Count

- **Deleted:** ~300 lines (parsing, injection, heartbeat, skill file)
- **Added:** ~340 lines (SKILL.md, MCP server, FSM bridge, schema, config)
- **Net:** ~40 lines added, but vastly reduced fragility

## Files Not Touched

| File | Reason |
|------|--------|
| `src/pet_fsm.py` | No changes needed — FSM actions already defined |
| `src/pet_renderer.py` | No changes — already handles all visual states |
| `src/response_manager.py` | Response pool pattern unchanged |
| `src/tts_worker.py` | No changes |
| `src/settings_dialog.py` | No changes |
| `src/memory_manager.py` | No changes |
| `src/firebase_crud.py` | No changes |
| `src/memory.py` | No changes |
| `src/history.py` | No changes |
| `src/apm_worker.py` | No changes |
| `src/typing_buffer.py` | No changes |
| `src/screen_reader.py` | No changes |
| `src/click_through.py` | No changes |
| `src/persistence.py` | No changes |
| `src/config.py` | No changes |

## Testing

### Unit Tests

| File | Tests |
|------|-------|
| `tests/test_context_manager.py` | Rewrite: remove injection tests, test build_context() |
| `tests/test_opencode_worker.py` | Remove parse tests, add schema validation tests |
| `tests/test_mcp_server.py` | New: JSON-RPC dispatch, tools/list, tools/call, error handling |
| `tests/test_fsm_bridge.py` | New: signal emission, thread safety |

### Key Test Cases

**MCP Server:**
- `tools/list` returns single `change_visual_state` tool with correct schema
- `tools/call` with valid action returns `{"content": [{"type": "text", "text": "ok"}]}`
- `tools/call` with invalid action returns JSON-RPC error
- `tools/call` with missing `action` returns JSON-RPC error
- Unknown method returns JSON-RPC MethodNotFound error

**FSMBridge:**
- Signal emission from background thread triggers slot on main thread
- Mutex prevents concurrent state changes
- Safe to call before PetWindow initializes (no-op guard)

**OpencodeWorker (schema):**
- Response matching schema routes to `response_ready`
- Response failing schema routes to `_handle_schema_error`
- HTTP error routes to error handler

### Integration Test

- Start Daemon → MCP server on 4097
- POST to `tools/list` → verify single tool
- POST to `tools/call` with `shake` → verify FSM transitions to SHAKING

## Rollout

1. Create `.opencode/skills/kenny/SKILL.md` (migrate from `assets/daemon-skill.md`)
2. Delete `assets/daemon-skill.md`
3. Refactor `src/context_manager.py` (gut injection, keep build_context)
4. Refactor `src/opencode_worker.py` (remove injection, remove parsers, add schema)
5. Write `src/fsm_bridge.py` + `src/mcp_server.py`
6. Write `opencode.json` MCP config
7. Refactor `src/pet_window.py` (remove injection wiring, add MCP start/stop)
8. Refactor `daemon.py` (remove ContextManager, add MCP lifecycle)
9. Update `src/constants.py` (add STRUCTURED_SCHEMA, MCP constants)
10. Write/update tests
11. Run full test suite: `py -m pytest tests/ -v`
12. Test with live `opencode serve` (E2E)
13. Remove `assets/daemon-skill.md` commit
