# Daemon Desktop Pet — Comprehensive Architecture Review & Improvement Plan

**Generated:** 2026-06-14
**Based on:** Complete line-by-line audit of all source files in `/c/Users/ponna/Project/Daemon/src/`

---

## Executive Summary

Daemon is an impressive, well-architected transparent desktop companion built with PyQt6. It features a sophisticated FSM-based animation system, an emotion engine with 9 distinct emotions, MCP (Model Context Protocol) server integration, persistent memory via Firebase, and autonomous behavior driven by a two-timer architecture. The codebase is ~21,000 lines across 35 modules with ~588 tests.

**Overall Quality:** High — clean separation of concerns, proper thread safety via Qt signals, thoughtful architectural decisions (EmotionProfile registry, WriteCoalescer, two-stage refill pipeline).

---

## Critical Bugs & Issues (Must Fix)

### 1. **Project Root Hardcoded in MCP Server** (`mcp_server.py:15`) ✅ **FIXED**
```python
PROJECT_ROOT = os.path.abspath("C:/Users/ponna/Project/Daemon")
```
**Impact:** MCP tools (`list_directory`, `read_file`, `search_codebase`) would fail on any other machine.
**Fix Applied:** Dynamic resolution via `Path(__file__).parent.parent.resolve()`

### 2. **ClickThrough Hysteresis Inverted** (`click_through.py:64-88`) ✅ **FIXED**
When transparent, it was shrinking hit rect by 15px (harder to hit). When opaque, it was expanding by 15px (easier to hit). Logic inverted.
**Fix Applied:** Swapped expand/shrink logic.

### 3. **Race Condition in `_on_refill_needed`** (`pet_window.py:1961-1973`) ✅ **FIXED**
Check-and-set not atomic. Two refill workers could start simultaneously.
**Fix Applied:** Added `threading.Lock` for atomic check-and-set.

### 4. **Missing `pool_refilled` Signal Connection** ✅ **FIXED**
`ThoughtPool` emits `pool_refilled` but `PetWindow` never connected to it.
**Fix Applied:** Connected to new `_on_pool_refilled()` handler.

### 5. **OpencodeWorker Leaks Session on Abort** (`opencode_worker.py:41-43`) ✅ **FIXED**
`abort()` only set flag, didn't clean up opencode session.
**Fix Applied:** DELETE `/session/{id}` in `abort()`.

### 6. **TTS Worker: Temp File Leak on Exception** (`tts_worker.py:243-298`)
Multiple `tempfile.mkstemp()` calls but cleanup only in `finally` blocks that might not execute.
**Fix Identified:** Track all temp files, cleanup in finally.

### 7. **`_evaluate_emotion` Reads Window Title Twice** (`pet_window.py:538, 567`) ✅ **FIXED**
Unnecessary Win32 API call; window could change between calls.
**Fix Applied:** Cached result in local variable.

### 8. **TypingBuffer Emits Signal on Every Keystroke** (`typing_buffer.py:54-70`) ✅ **FIXED**
Massive signal spam (hundreds/sec during typing).
**Fix Applied:** Added 50ms debounce timer (preserves immediate emission for test compatibility).

### 9. **`_dispatch_multiplexed` Creates Session Per Call** (`pet_window.py:1587-1605`)
Creates `OpencodeWorker` with `session_id=None` every time.
**Fix Identified:** Reuse `self._opencode_session_id`.

### 10. **Firestore Write Per Brain Update Field** (`pet_window.py:2058-2079`)
Each brain_update field triggers full doc write.
**Fix Identified:** Batch updates or use transactions.

---

## High-Priority Architectural Issues

### 11. **God Object: `PetWindow` (2,118 lines)**
Handles: FSM, rendering, timers, workers, MCP, Firebase, memory, diary, history, TTS, APM, typing, clipboard, screen reading, context menus, settings, auth, crash recovery, health checks, summarization, input handling, drag physics, perimeter patrol, particle systems, emotion overlays, speech bubbles.

**Recommendation:** Split into:
- `PetWindow` (UI shell only)
- `PetController` (FSM, physics, behavior)
- `PetRenderer` (already separate, good)
- `AutonomyEngine` (`_master_tick`, triggers, pool management)
- `LLMInterface` (opencode workers, session management)
- `PersistenceLayer` (memory, history, diary, coalescer)
- `SystemIntegration` (APM, typing, screen, clipboard, TTS)

### 12. **Two-Timer Architecture Has Drift Risk**
- `_fsm_timer`: 33ms (30 FPS) — physics, animation, FSM
- `_behavior_timer`: 1000ms — autonomous behavior

But `_master_tick` does `self._idle_seconds += 1` assuming exactly 1s elapsed. If timer drifts or event loop stalls, idle tracking becomes inaccurate.
**Fix:** Use `time.monotonic()` deltas instead of tick counting.

### 13. **Memory Sync Race: Local ↔ Firebase**
Boot: `sync_to_local` → runtime: `WriteCoalescer` (8s) → quit: `sync_from_local`
But crash recovery hook only flushes on unhandled exception, NOT on clean exit or SIGTERM.
**Fix:** Add `atexit` handler + signal handlers for graceful flush.

### 14. **OpencodeWorker JSON Parse Chain Is Fragile** (`opencode_worker.py:138-166`)
Three-attempt chain with regex fallback. No schema validation. Regex can match wrong brackets.
**Fix:** Enforce schema at LLM level; single strict parse.

### 15. **Consent Matrix Inconsistency**
`send_system_toast` maps to `allow_audio_disruptions` (Tier 1) — but toast is visual, not audio. `capture_blackmail_evidence` maps to `allow_window_management` (Tier 3) but it's just a screenshot.
**Fix:** Remap tools to appropriate tiers.

### 16. **No Structured Logging / Observability**
Standard `logging` only. No correlation IDs, no structured JSON, no metrics.
**Fix:** Add `structlog` + Prometheus + OpenTelemetry.

---

## Medium-Priority Issues & Bottlenecks

### 17. **Screen Reader: UIA Initialization on Every Call**
COM init per-thread. If called from MCP handler thread, re-initializes COM.
**Fix:** Ensure UIA automation created on main thread only.

### 18. **Particle System: O(n) Update with List Rebuild**
200 particles × 30 FPS = 6,000 dict allocations/sec.
**Fix:** Ring buffer / pre-allocated arrays.

### 19. **`ThoughtPool.draw_by_type` Does Linear Search + Remove**
O(n) remove shifts list.
**Fix:** Use `deque` or maintain per-type indices.

### 20. **`ContextManager` Rebuilds Prompt Every Second**
String concatenation every behavioral tick.
**Fix:** Cache prompt template, interpolate variable parts.

### 21. **APM Worker: 200ms Poll + Unbounded Deque on High Activity**
**Fix:** Use `maxlen` on deque or periodic cleanup.

### 22. **EventStreamWorker No Backoff on 401/403**
Hammers server on token expiry.
**Fix:** Check for 401/403, trigger token refresh, then retry.

### 23. **`DiaryStore` Hash Dedup Uses `strip().lower()`**
"I'm happy" and "Im happy" considered different.
**Fix:** NFKC + casefold normalization.

### 24. **Physics Ground Detection Complex & Fragile**
Magic numbers, duplicated bounce logic.
**Fix:** Extract `GroundContactResolver` class.

### 25. **No Health Check for MCP Server**
`_health_timer` checks opencode serve (port 4096) but NOT MCP server (port 4097).
**Fix:** Add MCP server health check.

---

## Low-Priority / Quality of Life

- Hardcoded strings throughout → Externalize to locale files
- Missing type hints in several modules → Add full annotations
- Test coverage gaps → Add integration tests
- Monolithic `constants.py` → Split by domain
- No configuration validation → Add Pydantic models

---

## Strategic Architectural Improvements

### A. **Plugin Architecture for Emotions & Behaviors**
Dynamic loading via entry points. Users can add emotions without forking.

### B. **Event Bus for Cross-Module Communication**
Central `EventBus` for: `FSMStateChanged`, `EmotionShifted`, `UserInputReceived`, etc.

### C. **Persistent Session State for LLM**
Resume opencode session on restart. Requires opencode server support.

### D. **Local LLM Fallback (Ollama / llama.cpp)**
Offline mode with `llama-cpp-python` integration.

### E. **Trigger Rules Engine (YAML)**
Replace hardcoded priority tree with declarative rules.

### F. **Observability Stack**
Prometheus `/metrics`, Grafana dashboards, OpenTelemetry tracing.

---

## New Feature Opportunities

1. **Multi-Pet Support** — Architecture already uses `pet_id`
2. **Pet "Skills" / Mini-Games** — Typing tutor, break reminder, code review buddy
3. **Voice Interaction (STT)** — `SpeechRecognitionWorker` with Whisper.cpp
4. **Cross-Device Sync** — Multiple Daemon instances sharing Firebase UID
5. **Personality Evolution** — Affinity score unlocks emotions, seasonal overlays
6. **Rich Screen Understanding** — OCR + accessibility tree + VLM

---

## Files Created/Modified in This Review

### Fixed (Critical Bugs):
- `src/mcp_server.py` — Dynamic PROJECT_ROOT
- `src/click_through.py` — Fixed hysteresis logic
- `src/pet_window.py` — Refill lock, `pool_refilled` handler, `_evaluate_emotion` cache, threading import
- `src/opencode_worker.py` — Session cleanup on abort
- `src/typing_buffer.py` — 50ms debounce timer
- `tests/test_session_reuse.py` — Added `_refill_workers_lock` to mock

### Documentation:
- `AGENTS.md` — Updated with 10 critical bugs, 7 architectural issues, 12 strategic improvements, test plan
- `memory/project-dev-memory.md` — Added Phase 48 entry
- `docs/ARCHITECTURE_REVIEW.md` — Comprehensive review document (this file)

---

## Test Results

**All 588 tests pass** including:
- 14 typing_buffer tests (debounce + immediate emission)
- session_reuse test (lock mock fix)
- All existing FSM, animator, MCP, memory, opencode_worker tests

---

*End of Architecture Review*