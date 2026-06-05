# Memory & Storage Hardening + noReply Context Injection

**Date:** 2026-06-08
**Status:** Design (not yet implemented)

---

## 1. Motivation

The current architecture builds LLM prompts by inlining all context (skill file, brain facts, diary, history) into every request. Each autonomous query sends ~2500 tokens of context overhead. With `noReply: true` support in the OpenCode ADK API, we can inject context silently into the session once and send minimal trigger prompts thereafter, cutting per-query token spend by ~95%.

At the same time, the local storage layer has several non-production-grade gaps: code duplication, non-atomic writes in two modules, unbounded diary growth, no crash recovery, no single-instance lock, and no retry for failed Firebase writes.

This design addresses both in a single refactor.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│ daemon.py                                               │
│  • Single-instance lock (~/.daemon.lock)                │
│  • new module: src/brain_schema.py                      │
│  • new module: src/diary_store.py                       │
│  • renamed:  src/context_builder.py → context_manager.py│
└────────────┬────────────────────────────────────────────┘
             │
     ┌───────┴────────┐
     │  PetWindow     │
     │  Session wiring│
     └───┬────────┬───┘
         │        │
    ┌────▼────┐ ┌─▼──────────────┐
    │Context  │ │ OpencodeWorker │
    │Manager  │ │ inject_context │
    │inject   │ │ build_trigger  │
    │trigger  │ │ trigger_ready  │
    └─────────┘ └────────────────┘
```

**Session Lifecycle:**

```
SESSION CREATED
    ├─ inject_full()   [noReply:true]  skill + brain + diary(5) + format + role
    │                                   ~2000 tokens, one-time
    ├─ 100ms cooldown ────────────────────────────────
    │
    ├─ [state changes]
    │   inject_delta()  [noReply:true]  window / APM / new facts / new diary
    │                                   ~50-150 tokens each
    │
    ├─ [timer tick / user input]
    │   build_trigger() [noReply:false] mode + APM + idle_seconds + typing
    │                                   ~30-80 tokens each
    │   → trigger_ready signal returns parsed response
    │
    └─ [15min inactivity]
        reset() → next trigger forces inject_full() again
```

---

## 3. New & Modified Files

### 3.1 `src/brain_schema.py` (NEW)

Extracted shared brain schema from `memory_manager.py` and `seed_brain.py` (100% duplication today).

**Exports:**
- `BRAIN_SCHEMA: dict` — field definitions (locked/unlocked, type)
- `DEFAULT_BRAIN: dict` — default values
- `apply_brain_update(update: dict) -> dict` — validates and applies an update dict
- `CREDS_PATH: str` — path to Firebase credentials

**Consumers:** `memory_manager.py`, `seed_brain.py` (import instead of define)

### 3.2 `src/diary_store.py` (NEW)

Local diary file I/O — extracted from `MemoryManager` where it didn't belong.

**API:**
- `DiaryStore(path)` — constructor
- `read() -> dict | None` — returns `{"entries": [...], "synced": N}` or `None`
- `write(entries, synced)` — atomic tmp+replace, caps at `MAX_DIARY_ENTRIES = 200`
- `prune(entries)` — drops oldest entries beyond max

**Backup:** Before write, copies existing file to `path.bak`. On `read()` failure, tries `path.bak`.

### 3.3 `src/memory_manager.py` (MODIFIED)

**Removed:**
- `_BRAIN_SCHEMA`, `_DEFAULT_BRAIN`, `apply_brain_update()` — imported from `brain_schema.py`
- `read_local_diary()` / `write_local_diary()` — moved to `DiaryStore`

**Added:**
- Retry queue (`_pending_writes: deque`) for failed `add_diary_entry()` and `update_brain()` calls
- `retry_pending_writes() -> int` — flushes queue, returns count of succeeded retries
- `fetch_all_diary_entries(limit=200)` — capped fetch

**Changed:**
- `push_pending_diaries()` accepts `DiaryStore` instance instead of raw path

### 3.4 `src/memory.py` (MODIFIED)

**Added:** `.bak` backup pattern.
- `_save()`: copies existing file to `path.bak` before writing tmp
- `_load()`: on JSON decode failure, attempts `path.bak` before returning empty dict

### 3.5 `src/history.py` (MODIFIED)

Same `.bak` backup pattern as `memory.py`.

### 3.6 `src/response_manager.py` (MODIFIED)

**Atomic write:** `_save()` uses tmp+replace pattern.

**TTL cleanup:** `_load()` drops items where `last_used` > 7 days ago. New `last_used` field added to each item on draw.

### 3.7 `src/persistence.py` (MODIFIED)

**Atomic write:** `save_state()` uses tmp+replace pattern.

### 3.8 `src/write_coalescer.py` (MODIFIED)

**New dirty flag:** `"brain"` — set when local memory facts change that should be pushed to Firebase on sync_from_local. `flush()` calls `memory_manager.retry_pending_writes()`.

**New consumer:** `DiaryStore.write()` is called by the `"diary"` flush path (instead of `memory_manager.write_local_diary`).

### 3.9 `src/opencode_worker.py` (MODIFIED)

**New method:**
```
inject_context(prompt: str) -> None
```
Sends `POST /session/{id}/message` with `{"noReply": true, "parts": [...]}`. On success, emits `context_injected`. On failure, emits `injection_failed`.

**Consolidated signals:**
- `trigger_ready(list[dict])` — replaces `structured_ready`, `structured_batch_ready`, `structured_multiplexed`, `result_ready`
- `context_injected()` — emitted after successful noReply injection
- `injection_failed(str)` — emitted on injection error

**Session management:**
- `create_session()` — creates session AND immediately calls inject_full internally. Only emits `session_created(session_id)` after injection completes.
- `run(prompt)` — renamed to `send_trigger(prompt)`. Sends minimal prompt without noReply.
- CLI fallback code preserved but dead (not called by PetWindow)

**Cooldown:** OpencodeWorker tracks `_injection_in_flight` flag. `send_trigger()` returns early if injection hasn't completed. PetWindow queues deferred triggers.

### 3.10 `src/context_manager.py` (RENAMED from `context_builder.py`)

**Renamed class:** `ContextBuilder` → `ContextManager`

**New API:**

```
inject_full() -> str
```
Builds the one-time full injection payload:
- Full `daemon-skill.md` (cached at module level)
- All brain facts from Memory (`get_context_block(None)`)
- Last 5 diary entries
- Format instructions (JSON schema)
- Role instruction

```
inject_delta() -> str | None
```
Builds delta injection payload. Returns `None` if nothing changed.
- Window changed since last snapshot
- APM bucket changed
- New memory facts since last snapshot
- New diary entries (by index: `_diary_injected_up_to`)
- New history entries

```
build_trigger(mode, user_input, apm, idle_seconds, typing_content) -> str
```
Builds minimal trigger prompt:
- Mode instruction
- Current APM
- Idle seconds
- Typing content (if any)

```
snapshot() -> void
```
Records current state for delta calculation. Diary snapshot tracks index (`_diary_injected_up_to`), not content.

```
reset() -> void
```
Forces next call to use `inject_full()`.

**Safety heartbeat:**
- `last_activity: float` — monotonic timestamp of last trigger
- `needs_reinjection() -> bool` — returns True if > 15 minutes since last activity
- Called before `build_trigger()`. If true, resets and caller must inject_full first.

**Signals:** None (pure data class, same as ContextBuilder was).

### 3.11 `src/pet_window.py` (MODIFIED)

**Session wiring:**

- `_on_session_created(session_id)` — stores session_id, blocks trigger queue, calls `context_manager.inject_full()` → `worker.inject_context()`
- `_on_context_injected()` — starts 100ms cooldown QTimer; when it fires, unblocks trigger queue and drains any deferred triggers
- `_on_trigger_ready(items)` — unified handler for all response types; routes by pool_type/mode tag
- `_deferred_triggers: list` — holds trigger requests that arrived during injection window

**State change injection:**
- New method `_maybe_inject_delta()` — called after memory/history mutations and on window change. If session is active and context_manager reports changes, injects delta via noReply.

**Diary seeding fix:**
- `_init_diary()`: only seeds hardcoded entries when `first_run_done=False` AND `fetch_all_diary_entries()` returns empty.

**Coalescer wiring:**
- WriteCoalescer gets `brain` flag wired to dirty-tracking
- `_force_quit_app()` calls `write_coalescer.flush()` which now includes `retry_pending_writes()`

**Timer tick handlers (active_chat, joke, boredom):**
- Check `needs_reinjection()`. If true, re-inject full context before trigger.
- Check injection cooldown. If injection in flight, queue trigger.
- If clear, call `context_manager.build_trigger()` → `worker.send_trigger()`

### 3.12 `daemon.py` (MODIFIED)

**Single-instance lock:**
```python
LOCK_PATH = Path.home() / ".daemon.lock"
```
On startup: if `LOCK_PATH` exists and PID in file is alive, print message and `sys.exit(1)`. Otherwise write current PID.

On shutdown: remove lock file.

**DiaryStore integration:**
- Construct `DiaryStore` and pass to PetWindow + MemoryManager
- `push_pending_diaries()` signature updated

---

## 4. Data Flow: Full Autonomous Cycle

```
1. PetWindow timer fires (active_chat, 25s)
2. _should_fire_autonomous(mode) → True
3. ContextManager.needs_reinjection() → False (been active)
4. prompt = ContextManager.build_trigger("active_chat", "", apm, idle, typing)
5. worker = OpencodeWorker(session_id=..., prompt=prompt)
6. worker.send_trigger()
7. POST /session/{id}/message  {"parts": [{"type":"text","text":prompt}]}
8. Response parsed → worker.trigger_ready.emit(items)
9. PetWindow._on_trigger_ready(items):
   - Dispatch first item → _show_bubble + FSM action
   - Cache remaining items → _response_manager.add_items()
   - Prime pools from user query responses
   - ContextManager.snapshot()  (resets delta tracking)
```

---

## 5. Data Flow: Session Creation + Injection

```
1. First API call succeeds → worker.session_created.emit(session_id)
2. PetWindow._on_session_created(session_id):
   a. Store session_id
   b. Set _injection_cooldown = True (blocks triggers)
   c. prompt = ContextManager.inject_full()
   d. worker.inject_context(prompt)
3. POST /session/{id}/message  {"noReply":true, "parts":[...]}
4. worker.context_injected.emit()
5. PetWindow._on_context_injected():
   a. Start 100ms QTimer
   b. When timer fires: _injection_cooldown = False
   c. Drain _deferred_triggers → replay each
```

---

## 6. Error Handling

| Scenario | Behavior |
|----------|----------|
| `inject_full()` API failure | `injection_failed` signal → PetWindow marks session dead, falls back to creating new session on next trigger |
| `inject_delta()` API failure | Logged, skipped. Next trigger has slightly stale context. |
| `send_trigger()` API failure | Worker emits `error_ready(str)`. PetWindow logs, resets boredom timer. |
| Firebase write failure mid-session | Queued in `_pending_writes`. Retried on next WriteCoalescer flush. |
| File corruption on boot | `.bak` file loaded if main file fails. Both fail → empty state. |
| Server context window evicted (15min idle) | `needs_reinjection()` → `reset()` → `inject_full()` on next trigger. |
| Multiple daemon instances | PID lock file check → `sys.exit(1)` with message. |

---

## 7. Test Plan

**New test files:**
- `tests/test_brain_schema.py` — moved from `test_memory_manager.py` (schema validation, apply_brain_update)
- `tests/test_diary_store.py` — atomic write, cap, backup, read
- `tests/test_context_manager.py` — renamed from `test_context_builder.py`, new injection/trigger tests

**New tests (~25):**
- `test_inject_full_includes_skill_and_brain` (ContextManager)
- `test_inject_delta_returns_none_when_no_changes` (ContextManager)
- `test_inject_delta_includes_new_facts` (ContextManager)
- `test_inject_delta_tracks_diary_index` (ContextManager)
- `test_build_trigger_is_minimal` (ContextManager)
- `test_needs_reinjection_after_15min` (ContextManager)
- `test_inject_context_sends_no_reply_true` (OpencodeWorker)
- `test_send_trigger_sends_no_reply_false` (OpencodeWorker)
- `test_context_injected_signal` (OpencodeWorker)
- `test_trigger_ready_consolidates_signals` (OpencodeWorker)
- `test_session_created_injects_full_context` (PetWindow)
- `test_injection_cooldown_blocks_triggers` (PetWindow)
- `test_deferred_triggers_replay_after_injection` (PetWindow)
- `test_safety_heartbeat_forces_reinjection` (PetWindow)
- `test_diary_seeded_only_on_first_run` (PetWindow)
- `test_atomic_write_for_response_cache` (ResponseManager)
- `test_atomic_write_for_persistence` (Persistence)
- `test_bak_fallback_on_corrupt_memory` (Memory)
- `test_memory_bak_created_on_save` (Memory)
- `test_diary_store_capped_at_200` (DiaryStore)
- `test_diary_store_atomic_write` (DiaryStore)
- `test_single_instance_lock_blocks_second` (daemon.py integration)
- `test_firebase_retry_queue_flushed` (MemoryManager)
- `test_sync_from_local_only_pushes_dirty` (PetWindow)
- `test_fetch_all_diary_respects_limit` (MemoryManager)

**Existing test changes:**
- All references to `ContextBuilder` → `ContextManager`
- All references to `structured_ready` / `structured_batch_ready` / `structured_multiplexed` → `trigger_ready`
- Tests expecting `read_local_diary`/`write_local_diary` on MemoryManager → DiaryStore
- Schema/apply tests moved from `test_memory_manager.py` to `test_brain_schema.py`

**Target:** ~335 tests (309 existing + ~25 new, minus 0 removed but redistributed)

---

## 8. Migration Notes

- `ContextBuilder` class removed; `ContextManager` replaces it. Any external code importing `ContextBuilder` must update.
- `structured_ready`, `structured_batch_ready`, `structured_multiplexed`, `result_ready` signals removed from OpencodeWorker. Only `trigger_ready(list[dict])` remains.
- CLI fallback code (`_run_cli`, `_build_prompt`) preserved in OpencodeWorker but not called by PetWindow. Can be fully removed in a later cleanup phase.
- `seed_brain.py` continues to work — it imports from `brain_schema.py` now.

---

## 9. Rollback Safety

- All changes are additive or consolidation. No data format migrations.
- Local JSON files keep same structure. `.bak` files are an addition.
- Old files (`context_builder.py`) renamed, not deleted — git tracks the rename.
- If the `noReply` feature doesn't work with the current opencode serve version, PetWindow can fall back to building full prompts via ContextManager's `inject_full()` path (which has the same content as old full prompts).
