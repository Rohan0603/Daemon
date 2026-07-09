# Daemon — Project Dev Memory

> **READ THIS FIRST in every new session.** Authoritative project state: what's built, what's next, known issues.

---

## Project Snapshot

**Last updated:** 2026-07-09
**Branch:** `master` | **Latest commit:** `645b3ff` (agent guidelines design spec)
**Stack:** Python 3.14, PyQt6, pynput, ctypes, requests, comtypes, Pillow, structlog, prometheus-client
**Test count:** 792 passed, 1 skipped (36.24s)

---

## Archive Index

| Archive | Covers | Key Topics |
|---------|--------|------------|
| `memory/archive/phases-01-35.md` | 06-06 to 06-08 | Window engine, opencode bridge, Firebase, auth, TTS, perimeter, storage hardening |
| `memory/archive/phases-36-50.md` | 06-08 to 06-15 | Agentic architecture, MCP, emotion engine, consent matrix, config migration |
| `memory/archive/phases-51-65.md` | 06-15 to 06-23 | Observability, BehaviorController, performance, plugins, Strands, test suite |
| `memory/archive/phases-66-plus.md` | 06-21 to 07-09 | Action palette, typewriter, coding assistant, stateless MCP, log audits |

> **Archives contain detailed phase tables, commit hashes, and design decisions.**
> Look there for historical context before asking about old features.

---

## What Is Built (High-Level)

- **Desktop pet** — Transparent, always-on-top PyQt6 widget with 11-state FSM, emotion engine (9 emotions), physics (gravity, throw, squash/stretch), 24-action expression layer
- **System awareness** — APM tracking, keystroke capture, active window detection, UIA screen reading, IDE detection, browser URL detection
- **LLM integration** — Stateless burst executor via opencode serve (:4096), thought pool caching (40-item unified pool), XML prompt builders
- **MCP server** — In-process JSON-RPC 2.0 on :4097, 13 tools, consent-gated (3 tiers), SSE broadcast
- **Memory** — 3-tier (Firestore → MemoryManager → local JSON), 33-field dynamic brain schema, atomic writes with .bak recovery
- **Autonomy** — BehaviorController (pure logic, no Qt), engagement tracker, adaptive backoff, context-aware boredom, code_assist mode
- **Observability** — structlog with correlation IDs, Prometheus metrics at /metrics, RotatingFileHandler, set_log_level MCP tool

---

## Key Pitfalls (Still Active)

- **No DEFAULT_CONFIG** — Adding a new config key will crash on boot unless `data/daemon_config.json` is updated
- **PetWindow instantiation in tests** — Must use `safe_pet_window` fixture; manual init causes timer/QThread leaks
- **JSON parse fallback chain** — `opencode_worker.py` tries 5 strategies; `_is_fallback_flood` dedup prevents spam
- **Worker lifecycle** — Never reuse QThread after `run()`; store refill workers in `_refill_workers` dict
- **PERIMETER↔CHASE oscillation** — Fixed with state guard + 500ms cooldown (pet_fsm.py)
- **AUTONOMOUS_THINKING never exits** — All callbacks must clear `_autonomous_query_pending`

---

## 2026-07-09 — Agent Guidelines Update (AGENTS.md)

**Branch:** `task-agent-guidelines-update`
**Test count:** 792 passed, 1 skipped in 36.24s

**Changes:**
- Added **Codebase Exploration (Graphify)** section — agents must use graphify before cross-module changes
- Added **Strict Pre-Commit Verification** — full test suite must pass and stay under 50s before any commit
- Added **Common Failures & Troubleshooting** — Qt timer hangs, port binding, circular imports, etc.
- **Archived** project-dev-memory.md (3176→58 lines): created `memory/archive/` with 4 phase archive files
- Updated project snapshot with latest test count and commit hash

**Files changed:**
- `AGENTS.md` — 3 new sections added
- `memory/project-dev-memory.md` — rewritten to <200 lines, archive index
- `memory/archive/phases-01-35.md` — created
- `memory/archive/phases-36-50.md` — created
- `memory/archive/phases-51-65.md` — created
- `memory/archive/phases-66-plus.md` — created

---

## 2026-07-10 — Master Optimization Plan (19 Tasks, 24 Findings)

**Test count:** 792 passed, 1 skipped in 28.81s

**Fixed Bugs (8):**
- B1: Removed stray `print("DEBUG: ...")` from `_log_thought`
- B2: Removed duplicate `_opencode_worker` declaration in `PetWindow.__init__`
- B3: Fixed `_on_mute_toggle` referencing nonexistent `_tts_worker` → `_tts`
- B4: Fixed `_on_wipe_memory` calling `self._diary.clear()` → `self._diary_store.clear()`; added `DiaryStore.clear()`
- B5: Fixed screen-time event using wrong data key `minutes` → `duration`
- B6/B7: Parented orphan QTimers in `WriteCoalescer.start()` (`QTimer(parent_obj)`) and `_schedule_boredom_retry` (`QTimer(self)`)
- B8: Removed duplicate `trigger_ready.emit(items)` from `OpencodeWorker.run()`

**Performance Fixes (7):**
- P1: Cached Win32 window rect in `_tick`, throttled from 30/s → 3/s
- P2: Deduplicated `get_active_window_title()` from 3 calls/tick → 1 call/tick in `BehaviorController.tick`
- P5: Replaced O(file_size) log rotation with stat-based rotation in `_log_thought`
- P6: Added 30s TTL cache for Firestore user-data GET in `sync_to_local`
- P7: Cached screen geometry in `PetWindow.__init__`, updated on geometry change signals
- MCP: Added `_FILE_CACHE_MAX_ENTRIES=50` and `_evict_stale_file_cache()` for bounded cache

**Enhancements (6):**
- E1: Added 5s GCD after boredom local actions (prevents rapid re-trigger)
- E2: Changed `_last_autonomous_fire_time` init from `0.0` to `time.monotonic()`; switched all fire-time tracking to monotonic time; guards at 15s now work correctly at boot
- E5: Wrapped `Event.data` in `MappingProxyType` to enforce immutability on frozen dataclass
- E7: Removed `QApplication.quit()` from `_on_mode_changed` (mode changes are not shutdowns)
- E8: Moved `self._dirty[kind] = False` into `finally` block so flags clear even on flush exceptions
- E9: Re-enabled TTS speech output by uncommenting `self._tts.enqueue(text)` in `_show_bubble`

**Files changed:**
- `src/ui/pet_window.py` — B1, B2, B3, B4, B7, E1, E7, E9, P1, P5, P7
- `src/autonomy/behavior_controller.py` — B5, E2, P2
- `src/write_coalescer.py` — B6, E8
- `src/llm/opencode_worker.py` — B8
- `src/memory_manager.py` — P6
- `src/mcp_server.py` — E6
- `src/events.py` — E5
- `src/diary_store.py` — B4 (added `clear()`)
- `tests/test_write_coalescer.py` — Updated test for new E8 behavior
- `tests/test_behavior_controller.py` — Set `_last_autonomous_fire_time = 0.0` for guard test
- `tests/test_behavior_controller_ide.py` — Set `_last_autonomous_fire_time = 0.0` for guard tests
- `tests/test_memory_manager.py` — Added cache fields to `__new__`-based test
- `tests/test_trigger_boredom_fsm.py` — Mocked `_schedule_boredom_retry` for `__new__`-based test

---

## What To Do Next

All planned development phases through Phase 75+ are complete. Potential future work:
- EventStreamWorker 401/403 handling (declined, not yet worth it)
- Constants.py domain split (skipped, YAGNI)
- Sensitive data redaction filter (skipped, low-value until prod)
- Multi-pet support (core infrastructure exists, UI work pending)

---

## Agent Instructions

**CLAUDE.md and GEMINI.md replaced by `AGENTS.md`** — all agent instructions in that single file.
Update `AGENTS.md` and this file (or an archive entry) after each task.
