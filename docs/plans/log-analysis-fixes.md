# Log Analysis Fixes — Implementation Plan

**Source:** `logs/daemon_2026-06-24_09-47-45.log` analysis  
**Priority tiers:** P0 (crash/blocker) → P1 (significant degradation) → P2 (bug) → P3 (enhancement)

---

## P0 — CRITICAL BUGS (Crash / Permanent Lock)

### 1. `refill_threshold` AttributeError Crash (pet_window.py ~2600, ~2680)

**Bug:** Two code paths access `thought_pool.refill_threshold` but `ThoughtPool` defines `_threshold` (private). This crashes:
- `_on_refill_needed()` at line ~2601 (before clearing `_refilling` flag — **permanent pool lock**)
- `_on_refill_error()` at line ~2681 (after cleanup, so less severe)

**Fix:**
- Add a `refill_threshold` property to `ThoughtPool`:
  ```python
  @property
  def refill_threshold(self) -> int:
      return self._threshold

  @refill_threshold.setter
  def refill_threshold(self, value: int) -> None:
      self._threshold = value
  ```

**Files to modify:**
- `src/autonomy/response_pool.py` — add `refill_threshold` property

### 2. Crash in `_on_refill_needed` Before `on_refill_result()` (pet_window.py ~2600)

**Bug:** When `_refill_failed_count >= 3` and backoff check passes, the `logger.info` line crashes (due to Bug #1) **before** `on_refill_result(None, intentional_abort=True)` is called. This leaves `pool._refilling = True` permanently, blocking all future refills.

**Fix:**
- Reorder: call `on_refill_result(None, intentional_abort=True)` **first**, then log.
- Add a `try/finally` around the entire block to ensure `on_refill_result` is called defensively.

**Files to modify:**
- `src/ui/pet_window.py` — `_on_refill_needed()` method

### 3. `_batch_cache` / `_batch_dirty` Missing Init (memory_manager.py)

**Bug:** `batch_update_brain()` and `flush_batch()` reference `self._batch_cache` and `self._batch_dirty` but these are never initialized in `__init__`. Will raise `AttributeError` if called.

**Fix:**
- Initialize in `__init__`:
  ```python
  self._batch_cache: dict[str, Any] = {}
  self._batch_dirty: bool = False
  ```

**Files to modify:**
- `src/memory_manager.py`

---

## P1 — HIGH IMPACT (Significant Degradation)

### 4. Strands Pipeline Has No Structured Output Enforcement

**Issue:** StrandsAutonomousWorker sends JSON schema only in the system prompt (natural language). The model (`deepseek-v4-flash-free`) ignores it 70%+ of the time, returning free-form text. All 7 Strands JSON decode failures in the log trace to this.

**Fix:**
- Add `response_format={"type": "json_object"}` or `response_format={"type": "json_schema", ...}` to the OpenAI API call in `strands.Agent` setup, if the model/provider supports it.
- If the Strands library (`strands.Agent`) doesn't expose `response_format`, either:
  - (a) Submit a PR/override to the Strands agent's `__call__` method to pass it
  - (b) Switch autonomous refill to use OpencodeWorker (which already has native structured output) instead of Strands for pool refills
- Add a `json` mode token in the system prompt: `"Your response must be valid JSON. No markdown fences. No prose. Only a JSON array."`

**Investigation needed:** Check if `strands` library's `OpenAIModel` accepts a `response_format` parameter.

**Files to modify:**
- `src/llm/strands_worker.py` — add `response_format` to agent config, tighten prompt

### 5. Typewriter Backpressure Blocks Autonomous System

**Issue:** A 5-page response takes ~40 seconds of typewriter animation. During this time:
- The bubble queue backs up to 3+ items
- Items get TTL-discarded from the queue (25s TTL)
- BehaviorController's GCD is never set from PetWindow (dead code), so FSM-based blocking is the only lock
- `_autonomous_query_pending` blocks new LLM queries

**Short-term fix:**
- Increase typewriter speed (8 chars/tick instead of 4)
- Lower `BUBBLE_MS_PER_CHAR` from 80ms to 50ms
- Expose typewriter speed in config

**Medium-term fix:**
- Allow typewriter to skip to end on click/tap (user interaction cancels the animation)

**Files to modify:**
- `src/ui/pet_window.py` — typewriter speed constants + skip-on-click
- `src/constants.py` — add typewriter config keys
- `data/daemon_config.json` — add typewriter section
- `src/config.py` — wire new config keys

### 6. No Affinity Score Progression

**Issue:** `pet_affinity_score` is stored at -10 but never modified by any code path. No progression logic exists.

**Fix:**
- Add a progression mechanism in `BehaviorController`:
  - Increment by +1 for each user-initiated chat
  - Increment by +1 for each engaged output (user responds/interacts)
  - Decrement by -1 per hour of continuous silence (floor at -20)
  - Trigger milestone events at thresholds (-10, 0, 10, 25, 50) via EventBus
- Write the score back to brain on change via `MemoryManager`

**Files to modify:**
- `src/autonomy/behavior_controller.py` — add affinity progression logic
- `src/memory_manager.py` — add `update_affinity_score()` method
- `src/events.py` — add `AFFINITY_MILESTONE_REACHED` event type

### 7. History at Max Capacity Silently Drops Context

**Issue:** `HISTORY_MAX_ENTRIES = 100` and the buffer is always full. `pop(0)` is O(n) for list.

**Fix:**
- Swap `self._entries` to `collections.deque` for O(1) eviction
- Increase history capacity to 200
- Add a log warning when history reaches 80% capacity

**Files to modify:**
- `src/history.py` — use `deque` instead of `list`, increase capacity to 200

---

## P2 — BUGS (Non-Crashing)

### 8. DiaryStore Fuzzy Dedup Uses Character Sets, Not N-Grams

**Issue:** `_fuzzy_ratio()` computes Jaccard similarity on **character sets**, not n-grams or edit distance. Short strings with similar character sets get 100% overlap despite different meaning (e.g., `"abc"` vs `"abcdef"` → 100%).

**Fix:**
- Replace with character bigram sets:
  ```python
  def _bigram_set(s: str) -> set[str]:
      return {s[i:i+2] for i in range(len(s)-1)}

  def _fuzzy_ratio(a: str, b: str) -> float:
      bigrams_a = _bigram_set(a.casefold())
      bigrams_b = _bigram_set(b.casefold())
      intersection = bigrams_a & bigrams_b
      union = bigrams_a | bigrams_b
      return len(intersection) / len(union) if union else 0.0
  ```

**Files to modify:**
- `src/diary_store.py` — replace `_fuzzy_ratio` with bigram-based version

### 9. TypingBuffer Lacks Proactive Idle Clearing

**Issue:** Idle timeout only checks in `get_context()`. If `get_context()` isn't called for 60+ seconds, stale keystrokes remain in the buffer. Also has a data race on `_last_keystroke_time` (pynput thread writes, main thread reads).

**Fix:**
- Add a `QTimer` in `TypingBuffer` that fires every 30 seconds and clears stale buffer if idle timeout exceeded
- Add `threading.Lock` or use `ctypes.c_long` for the timestamp value

**Files to modify:**
- `src/system/typing_buffer.py` — add proactive timer + thread safety

### 10. `refill_failed` Signal Unhandled

**Issue:** `ThoughtPool.refill_failed` emits when `on_refill_result(None)` is called, but no handler is connected to it.

**Fix:**
- Connect in `pet_window.py` (where other pool signals are connected):
  ```python
  self._response_manager.thought_pool.refill_failed.connect(self._on_refill_failed)
  ```
- Handler resets `_refill_in_progress` and optionally escalates backoff

**Files to modify:**
- `src/ui/pet_window.py` — connect signal + add handler

### 11. `get_all_diary_entries()` Returns `[]` Unconditionally

**Issue:** The method has `return []` hardcoded — not implemented.

**Fix:**
- Implement: read from `self._entries` with optional limit

**Files to modify:**
- `src/diary_store.py`

### 12. Dict Merge in `sync_from_local` Is a No-op

**Issue:** When `existing_val` is a `dict`, the sync does `pass` — user preferences and pomodoro config are never merged during `sync_from_local`.

**Fix:**
- Implement dict merge: update keys from local into remote dict, without overwriting top-level keys

**Files to modify:**
- `src/memory_manager.py` — `sync_from_local()` method

### 13. Content-Hash Collision Risk in Memory Sync

**Issue:** `hash(tuple(sorted(...)))` uses Python's salted hash — not stable across process restarts. Every restart re-pushes all facts.

**Fix:**
- Replace with `hashlib.sha256(json.dumps(...).encode()).hexdigest()[:16]`

**Files to modify:**
- `src/memory_manager.py` — `sync_from_local()` content hash guard

---

## P3 — ENHANCEMENTS / OPTIMIZATIONS

### 14. Repeated MCP `tools/list` Calls

**Issue:** Every SSE reconnection re-queries the full tools list from the MCP server (4+ times in session).

**Fix:**
- Cache the tools list in the MCP client with a timestamp. Re-fetch only if cache is >60s stale.

**Files to modify:**
- `src/mcp_server.py` or the Strands MCP client wrapper

### 15. Strands Tool_Use Budget Cap

**Issue:** A single autonomous query does 8+ tool_use round trips (get_memory → get_diary → list_directory → read_file → ...). For idle thoughts, this is wasteful.

**Fix:**
- Add a `max_tool_calls` parameter to the Strands agent config (initial budget: 3 for autonomous, unlimited for user queries)
- In the system prompt: "You have a budget of 3 tool calls for this response. Use them wisely."

**Files to modify:**
- `src/llm/strands_worker.py` — add tool call budget

### 16. Priority Decay Runs on Empty Pools

**Issue:** `decay()` iterates all items with no guard. Runs every `POOL_DECAY_INTERVAL_SEC` even when pool is empty.

**Fix:**
- Add `if not self._items: return` early guard in `decay()`

**Files to modify:**
- `src/autonomy/response_pool.py` — `decay()` method

### 17. Typewriter Speed Unconfigurable

**Issue:** `_TYPEWRITER_TICK_MS = 30` and `_TYPEWRITER_CHARS_PER_TICK = 4` are hardcoded in pet_window.py.

**Fix:**
- Move to `constants.py` as configurable values
- Add to `daemon_config.json` under `visuals.typewriter_chars_per_tick` and `visuals.typewriter_tick_ms`
- Add to `src/config.py` config mapping

**Files to modify:**
- `src/constants.py` — add typewriter constants
- `src/ui/pet_window.py` — reference constants instead of module-level vars
- `data/daemon_config.json` — add typewriter section
- `src/config.py` — wire new keys

### 18. FSM Thrashing Between IDLE and CHASE

**Issue:** The log shows 5 CHASE transitions with no intervening non-CHASE state logging. Hysteresis helps but cursor near the boundary zone causes repeated transitions.

**Fix:**
- Increase the hysteresis gap between `CHASE_ENTER_RADIUS_PX` and `CHASE_EXIT_RADIUS_PX`

**Files to modify:**
- `src/constants.py` — tune chase radii
- `src/pet_fsm.py` — verify `MIN_CHASE_DURATION_MS` logic

### 19. Empty Stale Files Cleanup

**Issue:** `strands_result.py` at project root is 0 bytes.

**Fix:**
- Add to `.gitignore` or delete if unused

**Files to modify:**
- `.gitignore` — add `strands_result.py`

### 20. Duplicate Diary Entries (Observed in Log)

**Issue:** "He tried to explain his 'ODSD' today" appears twice with different timestamps. SHA-256 exact-hash check passed (they differ slightly) and fuzzy check also passed (same character set issue from Bug #8).

**Fix:**
- Add `difflib.SequenceMatcher` as an additional dedup layer on top of the fixed bigram-based `_fuzzy_ratio`
- Add a cooldown period: reject entries with near-identical first sentence within the last 30 minutes

**Files to modify:**
- `src/diary_store.py` — add `SequenceMatcher` as additional dedup layer

---

## Implementation Order

| Batch | Items | Rationale |
|-------|-------|-----------|
| **Batch 1: Crash Fixes** | P0 #1, #2, #3 | These cause crashes or permanent locks. Ship first. |
| **Batch 2: Core Stability** | P1 #5 (short-term speed bump), P2 #9, #10, #11, #16 | Fix the starvation spiral and reactive recovery |
| **Batch 3: LLM Reliability** | P1 #4, P2 #8, #20, P3 #15 | Fix root cause of JSON parse failures + dedup |
| **Batch 4: Progression & Polish** | P1 #6, #7, P2 #12, #13, P3 #14, #17, #18, #19 | New features + QoL fixes |

---

## Verification

```bash
# Run existing tests for affected modules
py -m pytest tests/test_response_pool.py tests/test_diary_store.py -v
py -m pytest tests/test_history.py tests/test_memory_manager.py -v
py -m pytest tests/test_typing_buffer.py tests/test_brain_schema.py -v

# Run pet_window tests (most integration coverage)
py -m pytest tests/test_pet_window.py -v

# Full regression
py -m pytest tests/ -v
```

**Manual verification:**
1. Start daemon with `--debug --verbose --no-auth`
2. Type several messages, verify typewriter completes quickly
3. Let idle for 2+ minutes, verify ThoughtPool refills work (check pool items in log)
4. Check for `refill_threshold` in debug logs — should not raise AttributeError
5. Verify no `_refilling` permanent lock by observing pool recovery after parse failures
6. Close daemon, check shutdown log for clean sync

---

## Batch 5 — Remaining Issues (From 2026-06-27 Log Deep Analysis)

These 7 items were identified during log analysis but were **not** part of the P0-P3 plan above. They remain open.

### 21. Input Field Off-Screen (Negative X Coordinate)

**Observed:** `_show_input_field()` at 13:05:41 placed input field at `(-110, 727)` — completely off-screen left.
**Root cause:** `field_x = pet_x + PET_WIDTH // 2 - INPUT_WIDTH // 2`. Since INPUT_WIDTH (260px) >> PET_WIDTH (40px), the field starts 110px left of pet. No screen-bounds clamping.
**Fix:**
- Clamp `field_x = max(0, min(field_x, screen.width() - INPUT_WIDTH))`
- Clamp `field_y = max(0, field_y)`
- Also clamp `pet_x/pet_y` in `mouseMoveEvent()` to prevent dragging off-screen

**Files:** `src/ui/pet_window.py` — `_show_input_field()` (~line 1420), `mouseMoveEvent()` (~line 1348)

### 22. FSM State Transition Cooldown (PERIMETER↔CHASE Oscillation)

**Observed:** ~2,500 `PERIMETER -> CHASE` transitions in ~40 seconds (13:04:59 to 13:05:40). Every 33ms tick.
**Root cause:** No guard against CHASE→PERIMETER→CHASE cycling across consecutive ticks. The 800ms `MIN_CHASE_DURATION_MS` delays exit but doesn't prevent re-entry on the next tick. `_tick_perimeter()` moves pet at 2px/tick, oscillating cursor distance across the hysteresis threshold.
**Fix:** Add a state-change cooldown in `_evaluate()`: track `_last_chase_exit_time` and refuse CHASE re-entry for 500ms after exiting CHASE.

**Files:** `src/pet_fsm.py` — `_evaluate()` method

### 23. brain_update Dead Code — LLM Can't Update Memory

**Observed:** `brain_update_ready.emit` — zero matches in entire codebase. The signal is declared + connected but never emitted.
**Root cause:** `OpencodeWorker._parse_json_response()` and `StrandsWorker` result handling extract `thought`, `dialogue`, `type` but ignore `brain_update`. The LLM can generate brain updates in JSON but they're silently dropped.
**Fix:**
- Extract `brain_update` from response items in both `opencode_worker.py` and `strands_worker.py`
- Emit `brain_update_ready` or pass directly to `_on_brain_update()`

**Files:** `src/llm/opencode_worker.py`, `src/llm/strands_worker.py`, `src/ui/pet_window.py`

### 24. No Periodic Firestore Sync — Crash = Data Loss

**Root cause:** `sync_from_local()` is only called on clean Qt app exit. The `WriteCoalescer` (8s timer) only flushes to local disk. No timer pushes brain to Firestore during runtime.
**Fix:** Add a periodic QTimer (5 minutes) that calls `MemoryManager.sync_from_local(memory)`. Also fix `atexit` handler to call `sync_from_local()`.

**Files:** `src/ui/pet_window.py`, `src/write_coalescer.py`, `daemon.py`

### 25. No Retry on Shutdown Sync

**Root cause:** The `sync_from_local()` call in `daemon.py` `finally` block has no retry logic. If Firestore is unavailable during shutdown, all brain updates are lost.
**Fix:** Wrap in retry pattern (3 attempts, 0.5s backoff) matching `firebase_crud._with_retry()`.

**Files:** `daemon.py` — `finally` block

### 26. EventStreamWorker Circuit Breaker

**Observed:** `[ERROR] EventStreamWorker network error` fires every ~10 seconds the entire session when `opencode serve` is unavailable.
**Root cause:** Only 401/403 handled. Connection refused (WinError 10061) has no max-retry limit.
**Fix:** Add a max consecutive failure counter (e.g., 10). After threshold, stop retrying and log "EventStreamWorker disabled" at INFO once.

**Files:** `src/system/event_worker.py`

### 27. Screen Content / Browser URL Detection

**Observed:** Pet doesn't react to browser content (e.g., opening adult sites triggers no reaction).
**Root cause:** Only `get_active_window_title()` is checked against `PROCRASTINATION_DOMAINS`. Browser window titles say "Google Chrome", not the actual URL. `screen_text` is truncated to 500 chars.
**Fix:**
- Expand `screen_text` truncation from 500 to 1500 chars in `_build_context_snapshot()`
- Add URL bar extraction via UIA accessibility tree for Chrome/Edge
- Pass full `screen_text` to LLM prompts

**Files:** `src/system/screen_reader.py`, `src/ui/pet_window.py` (`_build_context_snapshot`)

---

## Implementation Order for Batch 5

| Priority | Items | Rationale |
|----------|-------|-----------|
| **P0** | #21, #22 | Input field unusable, FSM thrash causes pet glitching off-screen |
| **P1** | #23, #24, #25 | brain_update dead code means LLM can't learn; crash = data loss |
| **P2** | #26 | Log spam, no functional impact |
| **P3** | #27 | Enhancement — richer screen context for LLM reactions |
