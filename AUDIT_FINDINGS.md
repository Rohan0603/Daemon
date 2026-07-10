# Daemon Codebase Audit — Findings Report

**Date:** 2026-07-10
**Scope:** Full static audit of `src/` + `tests/` (≈19,800 LOC src / 813 passing tests)
**Method:** Phase-1 structure map, Phase-2 core-loop tracing, Phase-3 cross-cutting audits
(config, persistence, threading, error handling, security), Phase-4 test baseline.

---

## Executive Summary

The codebase is well-factored in places (pure-logic `BehaviorController`, stateless
`opencode_worker`, atomic `BrainStore` writes) but has **two HIGH-severity bugs that are
reachable during normal use**, plus a class of MCP-consent defects that undermine the
app's one security boundary.

| # | Severity | Area | One-line |
|---|----------|------|----------|
| H1 | HIGH | Security | `execute_os_action`/`get_screen_context`/`get_browser_context` bypass consent entirely |
| H2 | HIGH | Security | The 3 tools above aren't even in `CONSENT_TOOL_MAP` |
| H3 | HIGH | Autonomy | `_trigger_code_review_roast` calls non-existent `_set_gcd()` → pet soft-locked in AUTONOMOUS_THINKING |
| H4 | HIGH | Config | MCP consent settings in `daemon_config.json` are ignored until Settings dialog is opened |
| M1 | MED | Security/Stability | `set_log_level` mutates the ROOT logger and runs on the SSE thread |
| M2 | MED | Stability | Reminder handlers block the MCP SSE thread with `future.result(timeout=2.0)` |
| M3 | MED | Threading | `opencode_worker.abort()` cannot interrupt an in-flight HTTP POST |
| M4 | MED | Stability | `tick()`/`_master_tick()` re-raise, crashing the whole behavior loop on any error |
| M5 | MED | Autonomy | Screen-time / code-review roasts bypass the 15s global debounce |
| M6 | MED | Config | `config_get(key)` with no default + unknown-file path not validated |
| M7 | MED | Shutdown | Ghost-summary 15s failsafe is shorter than the 120s LLM timeout; save-after-quit race |
| M8 | MED | MCP | `get_diary` requests 1000 entries but `History.query` is capped at 200 |
| L1–L10 | LOW | Various | See detail below |

---

## HIGH Severity

### H1 — MCP consent bypass for OS-control / screen-read tools
**Files:** `src/mcp_server.py` — `_handle_get_screen_context` (≈L578), `_handle_get_browser_context`
(≈L595), `_handle_execute_os_action` (≈L612); `_is_tool_allowed` (L560–582).

These three handlers call:
```python
allowed, reason = _is_tool_allowed(server_thread, "allow_window_management")
```
i.e. they pass a **consent-key string** where `_is_tool_allowed` expects a **tool name**:
```python
def _is_tool_allowed(server_thread, tool_name: str):
    config = server_thread._config
    consent_key = CONSENT_TOOL_MAP.get(tool_name)   # "allow_window_management" is a VALUE, not a KEY
    if consent_key is None:
        return True, ""                              # ← unconditional allow
    ...
```
`CONSENT_TOOL_MAP` maps `tool_name → consent_key`. Passing a consent-key string makes
`CONSENT_TOOL_MAP.get(...)` return `None`, so the function returns `(True, "")` — the
consent check is a **no-op**.

Impact: `execute_os_action` lets the LLM run UIA actions in the *active* window — including
`type` (types into the focused control, e.g. a terminal or password field) and `click`/`drag`.
This is the most dangerous capability in the app and it is completely ungated.

### H2 — The three tools aren't in CONSENT_TOOL_MAP at all
**File:** `src/mcp_server.py` (≈L331).

`CONSENT_TOOL_MAP` lists only 7 tools (clipboard, mouse, keystroke, screenshot, toast,
visual_state, and …). `execute_os_action`, `get_screen_context`, `get_browser_context`
are absent. So even after fixing H1 (passing the real tool name), they would still be
unconditionally allowed. They must be added to the map.

### H3 — `_set_gcd()` AttributeError soft-locks the pet
**File:** `src/autonomy/behavior_controller.py` — `_trigger_code_review_roast` (L445–456),
`handle_file_edited` (L438).

```python
self._fsm.transition_to(PetState.AUTONOMOUS_THINKING)   # L449
self._set_gcd(8.0)                                       # L450  ← AttributeError: no such method
```
There is **no `_set_gcd` method** (only `set_gcd_expiry` at L168). The FSM is transitioned
to `AUTONOMOUS_THINKING` *before* the crash, so:
- the `emit_autonomous_trigger` at L452 is never reached,
- `_autonomous_query_pending` is never set,
- nothing ever transitions the pet back out → **permanently stuck showing a thinking bubble**.

Reachable: `event_worker.file_edited` → `_on_file_edited` → `behavior.handle_file_edited`
→ 10% chance per file edit to fire the roast (`pet_window.py:238, 1036–1039`).
This is a real, user-visible hang during normal editing.

**Fix:** Replace `self._set_gcd(8.0)` with `self._gcd_expiry_timestamp = time.time() + 8.0`
(consistent with `_trigger_screen_time_roast`) or add the `set_gcd_expiry` call.

### H4 — Consent config ignored until Settings dialog is opened
**Files:** `src/ui/pet_window.py` L280, L1158, L1166; `src/mcp_server.py` L567–579.

At construction the MCP thread gets the **full nested config**:
```python
self._mcp_server = MCPServer(config=self._config, ...)   # L280  → server_thread._config = full nested dict
```
`_is_tool_allowed` does `config.get(consent_key, False)`. On the full nested dict the key
(e.g. `allow_clipboard_hijacking`) does not exist at the top level → `get` returns `None` →
`if not allowed` → **all 7 gated tools permanently blocked**.

The consent sub-dict is only assigned to the thread at L1158:
```python
self._mcp_server._config = self._config.get("consent", {})   # inside _apply_settings
```
and `_apply_settings` is wired **only** to the Settings-dialog `valueChanged` signal
(L1122). `_restore_settings` (L1166) — the only place that would apply settings at startup —
is **defined but never called**.

Impact: a user who sets `consent.allow_clipboard_hijacking: true` in `daemon_config.json`
gets no effect until they open Settings and click Apply. (And H1/H2 mean the dangerous tools
are *always* on regardless.)

---

## MEDIUM Severity

### M1 — `set_log_level` changes the ROOT logger on the SSE thread
`src/mcp_server.py` `_handle_set_log_level` (≈L618) calls
`logging.getLogger().setLevel(...)`. This reconfigures **every** module's logger and runs
synchronously on the MCP SSE server thread, so a single LLM call can globally spike log
volume (or silence it) and block the SSE endpoint. Restrict to a named logger and don't
run on the hot path.

### M2 — Reminder handlers block the MCP SSE thread
`src/mcp_server.py` `_handle_reminder_request` (≈L641) forwards to UI and does
`data["future"].result(timeout=2.0)` (and the UI side resolves it in `pet_window.py:669–712`).
This blocks the SSE thread up to 2s per call; concurrent calls serialize. Use an async
callback / `QMetaObject.invokeMethod` with a queued connection instead of blocking the
server thread.

### M3 — `abort()` can't interrupt an in-flight HTTP POST
`src/llm/opencode_worker.py` L69–71, L83–112. `abort()` only sets `self._abort`; the flag is
checked *after* `requests.post(...)` returns (timeout up to 120s for autonomous). On shutdown
(`_force_quit_app` → worker abort) the POST keeps running until its timeout, delaying exit.
Use `requests` `stream` + a `threading.Event`/timer, or a short interruptible socket.

### M4 — `tick()` / `_master_tick()` re-raise crashes the behavior loop
`behavior_controller.py` L432–434, `pet_window.py` L632–634:
```python
except Exception as e:
    logger.critical("CRASH ...")
    raise
```
Any transient error in the autonomous tick propagates out of the Qt timer callback. While
`screen_reader` catches its own COM errors, a controller-level failure (the H3 bug, a plugin
error in `_evaluate_plugin_emotion`, etc.) would re-raise **every tick**, effectively killing
autonomy until restart. Log and `return` instead of re-raising.

### M5 — Roasts bypass the 15s global debounce
`_trigger_screen_time_roast` (L484–501) and `_trigger_code_review_roast` (L450) set
`_gcd_expiry_timestamp` but **not** `_last_autonomous_fire_time`. `_should_fire_autonomous`
debounces off `_last_autonomous_fire_time` (L645, monotonic). So a screen-time roast can fire
and a chat/joke can fire 1s later, defeating the debounce. Update the fire timestamp in both.

### M6 — `config_get` defaults + unknown-file path
`src/config.py` `config_get` (L148–165) returns `None` for unknown keys (no default overload
in some call paths). Callers such as `worker.py` do `int(config_get("llm.timeout_sec") or 30)`
— safe, but other `config_get(key)` calls without `or default` can propagate `None`.
Also `load_unknown_file` (L210) never checks the path exists; a missing file is silently
treated as valid JSON `{...}` (L230 catches `FileNotFoundError` but not a non-existent path
returned by `config_path`). Add an existence check + meaningful error.

### M7 — Ghost-summary shutdown race
`pet_window.py` `_force_quit_app` (L763) starts a 15s failsafe (`_trigger_ghost_summarization`
L783). The summary is an LLM call with up to 120s autonomous timeout, so long summaries are
**discarded at 15s**. Worse, `_on_summary_ready` (L828) may run *after* `_finalize_quit` tore
down state, and `on_complete` (`_summary_on_complete`) can be invoked twice (failsafe + summary).
Make `_finalize_quit` idempotent and stop the summary worker on shutdown.

### M8 — `get_diary` limit ignored
`src/mcp_server.py` `_handle_get_diary` passes `limit=1000` to `History.query`, which is
hard-capped at 200 (`history.py`). The LLM is told to expect up to 1000 but gets 200, and the
arg is silently dropped. Also `read_file` line-range edge cases (start==end, end>len) are
unhandled.

---

## LOW Severity

- **L1 (mcp_server):** tool-name vs consent-key confusion. Once H1/H2 are fixed, the 7
  correctly-mapped handlers must pass the *tool name* (e.g. `"clipboard_hijack"`), not the
  consent key, to `_is_tool_allowed`.
- **L2 (mcp_server):** `trigger_pet_animation` is not in `CONSENT_TOOL_MAP`, so intrusive
  animations are ungated while `change_visual_state` requires `allow_intrusive_animations`.
  Inconsistent.
- **L3 (storage):** `StorageBackend` ABC declares `query(filters: dict)`, `get(key)→dict`,
  but `DiaryStore`/`Memory`/`History` implement `query(filter_fn=None)`, `get` for hashes, etc.
  Duck-typed so no runtime error, but a maintenance hazard.
- **L4 (storage):** `BrainStore` is a singleton that overwrites the *whole* file on each
  `save()`. `Memory`/`History` use `brain_path`; `DiaryStore` uses a *different* `diary_path`,
  so two BrainStore files exist. Currently safe (each file read only by its owner), but if
  paths ever collide or a store is reused with another path, `save()` silently drops the other
  stores' data. Latent data-loss footgun.
- **L5 (tts_worker):** `pyttsx3` engine is created/used on the worker thread without explicit
  `CoInitialize` (SAPI COM needs an STA thread); can fail/hang — hence it's only a fallback.
  Also `_process_utterance` doesn't check `_cancel` during the network-bound edge-tts
  generation, so a cancel can't interrupt an in-flight synthesis.
- **L6 (screen_reader):** module-level cache globals (`_last_screen_hash`, `_cached_uia_text`,
  `_cached_uia_timestamp`) are mutated without locks across the MCP server thread and the main
  Qt thread. GIL makes individual str writes atomic, but the "[Screen unchanged]" sentinel can
  be cross-thread-confused. Low risk.
- **L7 (behavior_controller):** `_get_context_signature()` (L693) does a full UIA foreground-text
  walk (depth-4 tree, up to 2000 chars) on every boredom-eligibility tick (idle≥60s & apm==0).
  On the main Qt thread this can cause periodic UI jank. Throttle/cache.
- **L8 (docs):** `AGENTS.md` file map describes ≈13 MCP tools and a `strands_worker`-based
  architecture that no longer matches (≈30 tools; `opencode_worker` is stateless;
  `strands_worker.py` removed). Misleads contributors.
- **L9 (dead code):** `compute_dynamic_idle_threshold()` (L730) is unused; the tick derives
  thresholds from `ACTIVE_CHAT_INTERVAL_SEC / chattiness` directly.
- **L10 (smell):** `_has_significant_delta()` (L672) mutates `_last_active_window` /
  `_last_typing_snapshot` as a side effect inside a boolean condition — fragile.

---

## Performance / Optimization Notes

- **O1:** `opencode_worker` creates a fresh HTTP session + full XML payload every call
  (stateless by design — good for SQLite hygiene) but could reuse a `requests.Session` and
  compress the payload for high-frequency bursts.
- **O2:** UIA walk cost on the main thread (see L7).
- **O3:** `config_get` is recomputed on each access; cache the flattened runtime config once
  per load.

---

## Test Coverage Gaps

Baseline: **813 passed, 1 skipped in 43.39 s** (under the 50s budget). But coverage is
concentrated on low-risk modules:

- **T1:** No tests for `mcp_server` (consent gating, handlers) — the highest-risk security
  surface has **zero** coverage. H1/H2/H4 would be caught by a consent-gating unit test.
- **T2:** No tests exercising `BehaviorController` `tick` / `_trigger_code_review_roast` —
  the H3 `_set_gcd` bug would have been caught by a smoke test.
- **T3:** No tests for `opencode_worker` parse strategies (network-dependent; mock `requests`).
- **T4:** No integration test for the MCP `_is_tool_allowed` ↔ `CONSENT_TOOL_MAP` mapping.
- **T5:** Several tests are likely module-import smoke tests; the real logic (MCP, autonomy,
  workers) is under-tested relative to its risk.

---

## Recommended Fix Order

1. **H3** — `_set_gcd` → `set_gcd_expiry` / direct `_gcd_expiry_timestamp`. Trivial, high impact.
2. **H1 + H2** — fix `_is_tool_allowed` call sites to pass tool names; add the 3 missing tools
   to `CONSENT_TOOL_MAP`. Security boundary.
3. **H4** — apply the consent sub-dict to the MCP thread at startup (call `_apply_settings` /
   `_restore_settings` in `__init__`, or pass the consent dict at construction).
4. **M4** — stop re-raising in `tick()`; log and continue. Stability.
5. **M1 + M2** — don't mutate the root logger or block the SSE thread from MCP handlers.
6. **M3 + M7** — interruptible worker abort + idempotent shutdown.
7. **M5 + M8 + L-series** — debounce consistency, diary limit, docs, dead code.

After H3/H1/H4, add regression tests (T1–T4) so these don't regress.
