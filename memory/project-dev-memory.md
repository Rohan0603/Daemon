# Daemon — Project Dev Memory

> **READ THIS FIRST in every new session** (Claude or Antigravity). It holds the authoritative state of the project: what's done, what's next, known issues, and agent recommendations.

---

## Project Snapshot

**Date updated:** 2026-06-21 (ActionLayer Phase 73 Task 6)
**Current branch:** `task-73-renderer-compositing`
**Test count:** 705 passed, 1 skipped across 54 test files
**Git history:** Phase 1-35 → Phase 36 → Phase 37 → Phase 38 → Phase 39 → Phase 39.5 → Phase 40 → Phase 42 → Phase 43 → Phase 44 → Phase 44.5 → Phase 44.6 → Phase 45 → Phase 46 → Phase 50 → Phase 51 → Phase 52 → Phase 54 → Phase 59 → Latest fixes

---

## What Is Built

### Phase 1 — Window Engine ✅ COMPLETE (6 of 6 tasks)

| Task | File | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 1.1 Constants | `src/constants.py` | ✅ | `9d811ad` | HYPER_FLASH changed list→tuple |
| 1.2 PetFSM 4-state | `src/pet_fsm.py`, `tests/test_fsm.py` | ✅ | `c0d9495` | 6/6 tests pass |
| 1.3 PetRenderer | `src/pet_renderer.py` | ✅ | `3c77a42` | Fixed: abs(jump_y), painter save/restore, QFontMetrics type |
| 1.4 ClickThroughManager | `src/click_through.py` | ✅ | `325ebd9` | Callable type added |
| 1.5 PetWindow Phase 1 | `src/pet_window.py` | ✅ | `bcf6e8d` | HiDPI coord handling |
| 1.6 daemon.py entry point | `daemon.py` | ✅ | `1fef6fa` | dataclasses.replace() in sim, tick ranges for drag/fall |
| 2.1 PetFSM 11-state | `src/pet_fsm.py`, `tests/test_fsm.py` | ✅ | `508f038` | All 20 tests pass; added SLEEP, CHASE, HYPER, THINKING, CELEBRATE, DEVASTATED, POOP |

| 2.2 APMWorker | `src/apm_worker.py` | ✅ | `ce03986` | Rolling 60s APM, pynput listeners, 2s emit interval |
| 2.3 PetContextMenu | `src/context_menu.py` | ✅ | `ce03986` | 3 actions: build success/failure, quit; _Signals(QObject) for decoupling |
| 2.4 Wire Phase 2 | `src/pet_window.py`, `daemon.py` | ✅ | `e91892b` | APMWorker start, context menu, full FSM wiring |

### Phase 3 — opencode Bridge

| Task | File | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 3.2 Speech bubble + input | `src/pet_window.py` | ✅ | `6e6a594` | Double-click opens QLineEdit, submits to OpencodeWorker, displays speech bubble for 8s (migrated from AgyWorker) |

### Phase 4 — Polish

| Task | File | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 4.1 Persistence | `src/persistence.py`, `tests/test_persistence.py` | ✅ | latest | save_state/load_state, corrupt-file recovery, 4/4 tests pass |
| 4.2 System tray | `src/pet_window.py`, `daemon.py` | ✅ | latest | Programmatic 16×16 tray icon, hide-to-tray closeEvent, double-click to restore, right-click menu |
| 4.3 dae: skill setup | (deleted) | ✅ | `c6dfe9f` | Deleted as part of opencode migration (direct script execution instead of skill setup) |
| 4.4 Council additions | multiple | ✅ | latest | Hotkey, config.json, onboarding, idle quips, pin, memory UX |

See plans: `docs/superpowers/plans/2026-06-06-daemon-desktop-pet.md` and `docs/superpowers/plans/2026-06-06-opencode-integration.md`.

### Phase 5 — Opencode Integration

| Task | File | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 5.1 Config/Constants | `src/constants.py`, `src/config.py` | ✅ | `48e4ab1` | Replaced AGY constants with OPENCODE; added to overridables |
| 5.2 Rename FSM pending | `src/pet_fsm.py`, `tests/test_fsm.py` | ✅ | `b7f21e8` | Renamed agy_pending to query_pending, updated all references and tests |
| 5.3 OpencodeWorker | `src/opencode_worker.py`, `tests/test_opencode_worker.py` | ✅ | `5c003bc` | Implemented OpencodeWorker and unit tests |
| 5.4 PetWindow integration | `src/pet_window.py` | ✅ | `6e6a594` | Renamed agy to opencode, replaced AgyWorker, updated tests |
| 5.5 Setup cleanup & CLI args | `daemon.py` | ✅ | `c6dfe9f` | Removed agy setup, renamed CLI arg to --no-opencode |
| 5.6 Council additions tests | `tests/test_council_additions.py` | ✅ | `a5da584` | Aligned tests to opencode parameter names |
| 5.7 Docs & Dev Memory | `CLAUDE.md`, `GEMINI.md`, `memory/project-dev-memory.md` | ✅ | latest | Update documentation and project dev memory for opencode |
| 5.8 PowerShell Windows Migration | `src/opencode_worker.py`, `tests/test_opencode_worker.py` | ✅ | latest | Execute powershell.exe with bypass execution policy and UTF-8 encoding on Windows |

### Phase 6 — Autonomous Behavior & Context Awareness

| Task | File | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 6.1 AUTONOMOUS_THINKING FSM | `src/pet_fsm.py`, `src/constants.py`, `tests/test_fsm.py` | ✅ | `250a207` | New state priority 9 (between POOP and WANDER), BOREDOM_TIMEOUT_SEC=300, 25 FSM tests pass |
| 6.2 Active window module | `src/active_window.py`, `tests/test_active_window.py` | ✅ | `3e0f60f` | Win32 ctypes GetForegroundWindow, non-Windows returns "" |
| 6.3 OpencodeWorker JSON mode | `src/opencode_worker.py`, `tests/test_opencode_worker.py` | ✅ | `9146099` | structured_ready(str,str,int), _parse_json_response, fallback to result_ready |
| 6.4 Boredom timer + wiring | `src/pet_window.py`, `daemon.py` | ✅ | `35dcaae` | 5-min timer, resets on APM/mouse, _trigger_boredom_query, _on_structured_result |
| 6.5 Eye tracking | `src/pet_renderer.py`, `src/pet_window.py` | ✅ | `7d6ac5f` | atan2 pupil offset, cursor_x/cursor_y in RenderContext, #9B7EC8 AUTONOMOUS_THINKING visual |

| Bugfix | `src/opencode_worker.py`, `src/pet_renderer.py`, `src/constants.py` | ✅ | `a5bd66e` | Brace-search JSON parser (handles LLM preamble), eye atan2 from eye-centre (not body-centre), GROUND_PADDING_PX=0 (pet stands on taskbar); BOREDOM_TIMEOUT_SEC=10 (dev testing) |

### Phase 7 — API-First Pipeline

| Task | File | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 7.1 API-first CLI-fallback | `src/opencode_worker.py`, `src/constants.py`, `tests/test_opencode_worker.py` | ✅ | `4092c0d` | requests HTTP to Zen API; PowerShell/subprocess as fallback; 6 new tests; 92 total pass |

### Phase 8 — Active Chatter Timers

| Task | File | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 8.1 Constants | `src/constants.py`, `tests/test_opencode_worker.py` | ✅ | `98783d8` | ACTIVE_CHAT_INTERVAL_SEC=45, BOREDOM_TIMEOUT_SEC=30; 2 tests |
| 8.2 Prompt contract tests | `tests/test_opencode_worker.py` | ✅ | `6ff612a` | 2 tests: inactive context + active-window context verbatim in prompt |
| 8.3 Active chatter QTimer | `src/pet_window.py` | ✅ | `4d99ebe` | _active_chat_timer (45s) + _on_active_chat_tick(); _autonomous_query_pending guard |
| 8.4 Boredom trigger cleanup | `src/pet_window.py` | ✅ | `35a2c1a` | "User is completely inactive" context; concurrency guard added; 92 tests pass |
| 8.5 Personality rewrite | `assets/daemon-skill.md` | ✅ | pending | High on Life / Kenny Gatlian persona; detailed action matrix and context examples |
| 8.6 JSON parser improvements | `src/opencode_worker.py` | ✅ | pending | Better unquoted-key fallback; .lower().strip() on action; debug prints |

---

### Phase 9 — Action Matrix Expansion + Dialog Caching

| Task | File | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 9.1 Duration constants | `src/constants.py` | ✅ | `54ea040` | SHAKE/BOUNCE/SPIN/LOOK_AWAY duration ms + DIALOG_CACHE_SIZE=3 |
| 9.2 FSM new states | `src/pet_fsm.py`, `tests/test_fsm.py` | ✅ | `932179c` | SHAKING/BOUNCING/SPINNING/LOOK_AWAY states + triggered_action field; 35 FSM tests pass |
| 9.3 Renderer visuals | `src/pet_renderer.py` | ✅ | `ceaef8d` | _state_offset, color overrides, overlays per new state; LOOK_AWAY eye avert; state_elapsed_ms in RenderContext |
| 9.4 Batch dialogs + context | `src/opencode_worker.py`, `tests/test_opencode_worker.py` | ✅ | `4a2ec33` | _parse_json_batch (array of 3), structured_batch_ready signal, enriched prompt (time_of_day, idle_seconds, last_action) |
| 9.5 PetWindow wiring | `src/pet_window.py` | ✅ | `eef49a8` | _dispatch_structured for all 10 actions, _dialog_cache queue, _on_structured_batch, cache-first in tick handlers |
| 9.6 daemon-skill.md | `assets/daemon-skill.md` | ✅ | `53952bb` | 10-action matrix, 3 new examples (shake/look_away/spin), autonomous array format spec |
| 9.7 Integration | — | ✅ | `ff3bc9b` | 134 tests pass, 1 skipped; squash merged to master |

---

### Phase 10 — Cloud Memory Persistence (Firebase)

| Task | File | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 10.1 MemoryManager | `src/memory_manager.py`, `tests/test_memory_manager.py` | ✅ | b2e61a6 | Firebase dual-brain: core_brain doc + daemon_diary collection; graceful no-op when creds absent; 17 tests pass |
| 10.2 Wiring (Boot/Quit Sync) | `src/pet_window.py`, `daemon.py`, `assets/daemon-skill.md` | ✅ | f57b0b4 | Wired sync_to_local on boot, sync_from_local on quit, trimmed duplicate prompt context, removed obsolete files |

---

### Phase 11 — OpenRouter SDK Migration

| Task | File | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 11.1 OpenRouter SDK migration | `src/opencode_worker.py`, `src/constants.py`, `requirements.txt`, `tests/test_opencode_worker.py` | ✅ | 945c5e7 | Replaced raw requests with openai SDK; model → meta-llama/llama-3.3-70b-instruct:free; 3 new tests; 162 pass |

---

### Phase 12 — Council Stability Fixes

| Task | File | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 12.1 Clear dialog cache on user input | `src/pet_window.py` | ✅ | 1d4efdb | Clears `_dialog_cache` on message submit |
| 12.2 Tuning: Dialog Cache 3→6, Active Chat 45→15s | `src/constants.py`, `src/opencode_worker.py`, `assets/daemon-skill.md` | ✅ | 1d4efdb | Faster autonomous checks + pre-fetched dialogues |
| 12.3 429 rate-limit backoff | `src/opencode_worker.py`, `src/pet_window.py` | ✅ | 1d4efdb | Detects OpenRouter 429s, backs off timers |
| 12.4 Firebase failure flag | `src/pet_window.py` | ✅ | 1d4efdb | Catch connection exceptions, set `_firebase_available` flag |
| 12.5 Shutdown cleanup | `src/pet_window.py` | ✅ | 1d4efdb | Stops FSM/active/joke timers, quits and waits on workers |

---

### Phase 13 — Verbose Diagnostic Logs

| Task | File | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 13.1 Add diagnostic logging | `src/opencode_worker.py`, `src/pet_window.py` | ✅ | e322920 | Detailed logs for API & CLI fallback start, output, and failure |

---

### Phase 14 — Configurable API Key

| Task | File | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 14.1 Load API Key from config | `src/config.py`, `src/constants.py`, `src/opencode_worker.py` | ✅ | 4296f40 | Read OPENROUTER_API_KEY from ~/.daemon_config.json if not in env |

---

### Phase 15 — Overridable OpenRouter Model

| Task | File | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 15.1 Load model from config | `src/config.py` | ✅ | 81702c1 | Support overriding OPENROUTER_MODEL in ~/.daemon_config.json |

---

### Phase 16 — Local-First Diary + Curiosity + Prompt Fix

| Task | File | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 16.1 Remove OpenRouter API | `src/constants.py`, `src/opencode_worker.py`, `src/pet_window.py`, `src/config.py` | ✅ | — | Removed all OPENROUTER_* constants, `_try_api`, `rate_limited` signal |
| 16.3 Fix autonomous dialog framing | `src/opencode_worker.py`, `src/pet_window.py` | ✅ | — | Added `mode_instruction` in prompt (internal monologue vs user response); fixed joke context_hint from command to state description |
| 16.4 Local-first diary | `src/memory_manager.py`, `src/pet_window.py`, `daemon.py`, `src/constants.py`, `tests/` | ✅ | — | Diary read/written locally during session; Firebase only at startup (fetch all) and quit (push pending). Removed `get_recent_diary()`, added `fetch_all_diary_entries()`, local file ops, `push_pending_diaries()` |
| 16.5 Dynamic sync_to_local | `src/memory_manager.py` | ✅ | — | `sync_to_local` now iterates all brain fields dynamically — new fields auto-sync without code changes |
| 16.6 Curiosity feature | `src/pet_window.py`, `src/constants.py`, `tests/` | ✅ | — | 120s timer detects memory gaps, asks in-character questions, stores answers locally + syncs to Firebase, 9 new tests |

### Phase 26 — TTS with Voice Modulation (2026-06-07)
**Branch:** `master` (squash-merged, commit `3af97d2`)

**What was built:**
- New `src/tts_worker.py` — `TTSWorker(QThread)` with pyttsx3 TTS generation, pydub pitch shift (+0.5 octave), 1.2x speedup, simpleaudio playback. Uses `queue.Queue` for thread safety, `threading.Event` for shutdown/enabled flags.
- `tests/test_tts_worker.py` — 9 tests covering enqueue, stop, signals, generate pipeline, pitch shift, error handling, clear
- PetWindow wiring: TTSWorker instantiated in __init__, started. `_show_bubble` calls `_tts.enqueue(text)`, `_clear_bubble_queue` calls `_tts.clear()`, `_force_quit_app` stops TTS
- Constants: TTS_ENABLED, TTS_BASE_RATE=200, TTS_PITCH_OCTAVES=0.5, TTS_SPEEDUP=1.2

**Dependencies:** pyttsx3, pydub, simpleaudio, ffmpeg (system requirement)

### Phase 27 — Landing Squash/Stretch (2026-06-07)
**Branch:** `master` (squash-merged, commit `706e053`)

**What was built:**
- `land_elapsed_ms` field added to `RenderContext` (pet_renderer.py)
- Squash→stretch→settle animation in `_state_transform`: 0-120ms squash (sx 1.25→1.30, sy 0.85→0.70), 120-240ms stretch (sx→0.75, sy→1.25), 240-400ms settle to identity
- PetWindow records `_land_time` when FALLING hits ground in `_apply_physics`, passes `land_elapsed_ms` to RenderContext in `paintEvent`
- Constant: SQUASH_STRETCH_DURATION_MS=400

### Phase 28 — Perimeter Patrol (2026-06-07)
**Branch:** `master` (squash-merged, commit `dee842e`)

**What was built:**
- Renamed `PetState.WANDER` → `PetState.PERIMETER` across all files (fsm.py, renderer.py, pet_window.py, tests)
- Added `edge: str` and `facing: str` fields to `FSMContext` and `RenderContext`
- Full 8-way renderer transform: each edge (bottom/left/right/top) × each facing direction → correct rotate/scale combo
- `_tick_perimeter()` method: counter-clockwise patrol of all 4 screen edges, corner detection switches edge, 20% random fall at vertical midpoints
- `_maybe_fall_off_edge()`: resets to "bottom"/"right" and transitions to FALLING
- Constant: PERIMETER_FALL_CHANCE=0.2

### Phase 29 — Settings Panel (2026-06-07)
**Branch:** `master` (squash-merged, commit `a8798b3`)

**What was built:**
- New `src/settings_dialog.py` — `SettingsDialog(QDialog)` with size/opacity/speed sliders + voice toggle, `value_changed` signal for live preview
- `tests/test_settings_dialog.py` — 5 tests: initial values, defaults, ranges, get_values, signal emission
- PetWindow wiring: "Settings..." entry in tray menu, `_open_settings`/`_apply_settings`/`_save_settings`/`_restore_settings` methods, live-preview on slider move, save to `~/.daemon_config.json` on OK, restore on Cancel
- `config.py`: added `save_config()` function, new overridable keys (pet_scale, pet_opacity, pet_speed, tts_enabled)
- Speed multiplier applied in `_tick_perimeter` for PERIMETER speed
- TTS enabled/disabled flag loaded from config on boot
- Constants: SETTINGS_SCALE_MIN/MAX, SETTINGS_OPACITY_MIN/MAX, SETTINGS_SPEED_MIN/MAX

**Test count:** 309 collected, 0 skipped (14 new: 9 TTSWorker + 5 SettingsDialog)

### Phase 30 — TTS Polish (Stuttering + Winsound) (2026-06-07)
**Branch:** `master` (to be squashed)

**What was built:**
- `TTS_PITCH_FACTOR = 1.38` constant added to `src/constants.py`
- Textual stuttering instruction added to `assets/daemon-skill.md` — LLM writes hyphens (I-I-I don't know), trailing dots, dasher panic words directly into dialogue strings. 40%+ of dialogue should contain stammers.
- Updated Example B and D in daemon-skill.md with stuttering dialogue
- `_play_via_winsound()` method added to `TTSWorker` — uses `winsound.SND_SYNC` (safe because it blocks the worker QThread, not the UI thread)
- `run()` method: when `simpleaudio` import fails, falls back to winsound with WAV header pitch shift using `TTS_PITCH_FACTOR` times the actual sample rate
- `_apply_kenny_filter_wave()` now uses `TTS_PITCH_FACTOR` instead of hardcoded `2.0**(4/12.0)`

---

### Phase 31 — Storage Hardening + noReply Context Injection (2026-06-08)
**Branch:** `task-storage-noreply` (squash-merged, commit `fe03225`)

**What was built:**
- **Durability fixes:**
  - `src/brain_schema.py` (NEW) — shared brain schema, defaults, `apply_brain_update` extracted from duplicated copies in `memory_manager.py` and `seed_brain.py`
  - `src/diary_store.py` (NEW) — atomic local diary I/O with backup and 200-entry cap (was on MemoryManager)
  - `.bak` backup/fallback on `Memory`, `History`, `Persistence`, `ResponseManager`, `DiaryStore` — crash recovery via tmp+replace atomic writes
  - TTL cleanup (7-day) on response cache load
  - Firebase retry queue — failed `add_diary_entry()`/`update_brain()` writes queued, retried on WriteCoalescer flush
  - `fetch_all_diary_entries(limit=200)` — capped Firebase reads
  - `DiaryStore` integration in `WriteCoalescer` + `"brain"` dirty flag
  - Diary seeded only on `first_run_done=False` AND empty Firebase (no duplicates)
  - Single-instance PID lock (`~/.daemon.lock`) with `try/finally` cleanup

- **noReply architecture:**
  - `src/opencode_worker.py` — rewritten with `inject_context()` (noReply:true), `send_trigger()` (noReply:false), consolidated `trigger_ready(list[dict])` signal replacing 4 old signals
  - `src/context_manager.py` — renamed from `context_builder.py`. New API: `inject_full()`, `inject_delta()`, `build_trigger()`, `needs_reinjection()` (15min `time.monotonic()` heartbeat), `reset()`
  - `src/pet_window.py` — session wiring with injection cooldown (100ms), deferred trigger queue, `_dispatch_trigger()` unified method, safety heartbeat re-injection
  - Timer ticks (`active_chat`, `joke`) use `_dispatch_trigger` → minimal ~50-token prompts after initial ~2000-token injection
  - `daemon.py` — DiaryStore wiring, lock lifecycle

- **Token savings:** ~2500 tokens/injection (once per session) → ~100 tokens/trigger (~95% per-query savings after break-even at ~1 query)

- **CLI fallback code preserved but dead** (not called by PetWindow)

**Key pitfalls added:**

| Pitfall | Fix |
|---------|------|
| `pet_window.py` imports `apply_brain_update` from `memory_manager` not `brain_schema` | Import from canonical `src.brain_schema` |
| `DiaryStore._write_atomic` only creates `.bak` on second write | First write now creates `.bak` too via `os.replace` of main file |
| `_parse_json_batch` confused by nested `[ ]` in `jokes_blackmail_items` | Pre-check: single `{...}` objects route to `_parse_json_response` first |
| `_snapshot_current` loses `active_window`/`apm_bucket` on re-snapshot | `snapshot_context()` method added for delta injection updates |
| `_on_refill_needed` creates `OpencodeWorker` as local var — QThread GC'd while running | Store in `self._refill_workers[pool_type]` before `start()`; add `_on_refill_error` cleanup method |

**Test count:** 343 passed (34 new tests from baseline 309), 0 skipped.

---

### Phase 32 — Reusable Firebase CRUD Layer (2026-06-08)
**Branch:** `master` (commit `8d72130`)

**What was built:**
- `src/firebase_crud.py` (NEW) — generic `FirebaseCRUD` class wrapping `firestore.Client` with lazy init, one method per CRUD verb (`get`, `set`, `add`, `delete`, `query`, `read_all_text`), and transparent 3-attempt retry with 0.5s backoff. All methods return fallback values (None/False/[]) on failure — no exceptions propagate.
- `src/memory_manager.py` — refactored: removes all raw `self.db.collection().document().get/set/add()` chains and Firebase init boilerplate (~40 lines removed). Delegates all Firestore I/O to `FirebaseCRUD`. `_pending_writes` deque kept as last-resort fallback after CRUD's 3 retries.
- `seed_brain.py` — refactored: ~40 lines of duplicated Firebase init (`credentials.Certificate` → `get_app` → `initialize_app` → `firestore.client()`) and `get_brain`/`set_brain` helpers removed. Uses `FirebaseCRUD` directly.
- `tests/test_firebase_crud.py` (NEW) — 22 tests covering every CRUD method, retry logic, unavailable client, and edge cases.

**Files changed:**
- **Created:** `src/firebase_crud.py`, `tests/test_firebase_crud.py`
- **Modified:** `src/memory_manager.py`, `tests/test_memory_manager.py`, `seed_brain.py`

**Key decisions:**
- Class-based over module-level functions: more testable (inject mock client), cleaner retry encapsulation
- All methods return fallback values (no exception propagation): callers never need try/except
- `_pending_writes` in MemoryManager kept as two-tier fallback: CRUD retries 3x → if all fail → queue for WriteCoalescer retry
- Lazy init: `firebase_admin` not touched until first CRUD call; `available=False` on init failure
- `seed_brain.py` imports from `src.firebase_crud` instead of re-initializing Firebase

**Test count:** 432 passed, 0 skipped (89 new tests from baseline 343).

---

### Phase 33 — noReply Bug Fixes + E2E Verification (2026-06-08)
**Branch:** `master` (pending commit — uncommitted)

**What was done:**
- **Bug A fix** (`src/pet_window.py:1123-1133`): Added `_injection_cooldown` guard + `session_created` signal connection on injection worker to prevent redundant injections and propagate the real session ID from server to PetWindow.
- **Bug B fix** (`src/opencode_worker.py:190-192,233-239`): Changed `_post_message` to return `""` instead of `None` for 200 OK with empty text (noReply success). Updated `send_trigger` to use `if raw:` (rejects `""`/`None`). `inject_context` uses `if raw is not None` (accepts `""`).
- **E2E test with live `opencode serve`** (v1.16.2 on port 4096):
  - Session creation ✓
  - Context injection via `noReply: true` ✓ (server returns UserMessage with input echoed back, DOES NOT generate AI response)
  - Trigger with model spec returns valid JSON array ✓ (5 dialogs, correct schema)
  - Session reuse: second trigger returns different content ✓
  - Context persistence: model remembered facts from injection ✓
  - Model output uses ```json code fences — parser handles via `find('{')`/`find('[')` ✓
- **Documentation refresh**: README.md fully rewritten, AGENTS.md updated, project-dev-memory.md updated, stale plan docs deleted.

**Key noReply behavior learned:**
- `noReply: true` stores the message in session context but returns the UserMessage (not AssistantMessage)
- The returned `parts` contain the user's original text — NOT a generated response
- This is correct and expected — injection stores context without LLM generation
- Token cost: injection prompt (~2500 tokens) is stored; no response tokens wasted
- Later triggers use the stored context for generation

**Test count:** 432 passed, 0 skipped (unchanged from Phase 32 — no test changes needed).

---

### Phase 34 — Screen Reading, APM Priority, Autonomous Framing, Storage Relocation, CoT Logging (2026-06-08)
**Branch:** `master` (commit `79ea960`)

**What was built:**
- **`src/screen_reader.py`** (NEW) — UIA text extraction via comtypes, 2000-char cap, WM_GETTEXT fallback. Returns foreground window text content.
- **Autonomous/User framing** — `build_trigger()` split into `build_user_trigger()`/`build_autonomous_trigger()` in context_manager.py. Autonomous template says "thinking to herself — NOT responding to user." APM labeled "primary signal" in both templates.
- **Delta injection wired** — `inject_delta()` called in `_dispatch_trigger()` with delta prepended before trigger text (trigger data takes precedence as fresher context).
- **Storage relocation** — All state files moved from `Path.home()` to `data/` dir in project root. 7 new path constants in constants.py. Portable dev, one-line production switch.
- **CoT thought capture** — `thought` field preserved through pipeline in `_normalize_parsed()`, logged to `data/thoughts.log` on `--verbose`. Rotates at 1000 lines, keeps last 500.
- **opencode serve PID tracking** — `_SERVE_PID` tracked in `opencode_serve_manager.py`, `stop_opencode_serve()` kills on Daemon shutdown.
- **`data/` added to `.gitignore`**, `comtypes>=1.4.8` added to `requirements.txt`.

**Test count:** 452 passed, 0 failed (20 new tests).

**New pitfalls:**
| Pitfall | Fix |
|---------|------|
| comtypes `CoUninitialize()` logging errors at shutdown | Harmless — I/O on closed stream during test teardown. Suppress by redirecting comtypes logger. |
| `importlib.reload()` can't simulate missing comtypes on system with comtypes | Don't test import failure via reload. Test fallback chain directly by mocking both UIA and WM_GETTEXT. |
| Delta injection must precede trigger text, not follow | Build trigger first, then prepend delta. Trigger data (Mode, APM, User said) is fresher and acts as override when it appears later in the prompt. |
| opencode serve has no window title (CREATE_NO_WINDOW) | Don't use window-title-based taskkill. Track spawned PID explicitly, kill by PID on shutdown. |

---

## Architecture Summary

### opencode Communication (noReply Pattern)

The daemon uses a **two-phase context injection** pattern:

1. **Session creation + Injection** (one-time, ~2500 tokens):
   - `POST /session` → get `session_id`
   - `POST /session/{id}/message` with `noReply: true` → injects full skill file, memory, diary, format instructions
   - Server stores context; no response text returned

2. **Triggers** (per-query, ~50-100 tokens):
   - `POST /session/{id}/message` with minimal prompt (mode, APM, idle seconds)
   - Server has full context from injection → contextualized JSON response
   - `ContextManager.build_trigger()` builds the minimal prompt
   - `ContextManager.needs_reinjection()` → 15-min heartbeat triggers re-injection

**Session reuse:** All triggers share one `session_id`. The model maintains message history server-side.

### Memory System (3-Tier)

| Layer | Store | Contents |
|-------|-------|----------|
| 3 (Cloud) | Firestore `daemon_data/core_brain` + `daemon_diary` | Source of truth |
| 2 (Bridge) | MemoryManager + FirebaseCRUD | sync + retry queue + 3x retry |
| 1 (Local) | Memory + History + DiaryStore | Fast cache, .bak recovery |

- **Boot:** Firestore → MemoryManager.sync_to_local() → local Memory
- **Runtime:** Local reads/writes with WriteCoalescer (8s batched flush)
- **Quit:** MemoryManager.sync_from_local() → Firestore, push_pending_diaries()

### Response Pool Cache

Single unified ThoughtPool with type filtering (typing_reaction, idle_thought, observation, intel_roast), spatial TTL, and priority decay. Eliminates API calls for routine autonomous chatter.

### Engagement Tracker

Adaptive backoff: 5 consecutive silent outputs → exponential interval increase (max 120s). 2 engaged → reset to 15s base. Prevents spamming an inattentive user.

### Storage Durability

All local JSON: atomic tmp+replace writes, .bak fallback on read failure. Single-instance PID lock (data/.daemon.lock). Crash recovery via sys.excepthook that calls WriteCoalescer.flush().

---

## ✅ CRITICAL BUGS FIXED

| Bug | Location | Severity | Status | Fix Applied |
|-----|----------|----------|--------|-------------|
| **Hardcoded PROJECT_ROOT (security.py)** | `src/utils/security.py:3` | CRITICAL | ✅ Fixed | Changed to `Path(__file__).parent.parent.parent.resolve()` |
| **Hardcoded PROJECT_ROOT (mcp_server.py)** | `src/mcp_server.py:20` | CRITICAL | ✅ Fixed | `Path(__file__).parent.parent.resolve()` |

---

### Phase 35 — Firebase Auth Login + Firestore REST API + PyInstaller (2026-06-08)
**Branch:** `master` (commit `8834179`)

**What was built:**
- **`src/firebase_auth.py`** (NEW) — Firebase Auth REST API: sign-in, sign-up, token refresh, JWT expiry parsing, token persistence to `data/.daemon_auth.json`. Uses `requests` (no new deps).
- **`src/login_dialog.py`** (NEW) — PyQt6 modal dialog with email/password fields, sign-in/sign-up toggle, error display, loading state.
- **`src/firebase_crud.py`** (REWRITE) — Replaced `firebase_admin` SDK with Firestore REST API. Constructor accepts `(token_provider, project_id)`. Field flattening/unflattening. Same 6 CRUD verbs with 3-attempt retry.
- **`src/memory_manager.py`** — Constructor changed to `(crud, uid)`. All paths scoped per uid: `daemon_data/{uid}/core_brain`, `daemon_diary/{uid}/entries`.
- **`daemon.py`** — Auth gate: LoginDialog on first run, auto-refresh on subsequent runs.
- **`src/pet_window.py`** — Accepts `auth` + `crud`, conditional MemoryManager creation.
- **`seed_brain.py`** — Reads auth from saved session, supports `--uid`.
- **`daemon.spec`** (NEW) — PyInstaller `--onefile` spec.

**Key decisions:** No service account in .exe. Per-user Firestore isolation via Security Rules. Token auto-refresh with 60s buffer. Auth gate after QApplication creation.

**One-time Firebase Console setup:** Enable Email/Password auth, set `FIREBASE_API_KEY` + `FIREBASE_PROJECT_ID` in `src/constants.py`, deploy Security Rules.

**Files changed:** 14 files, +925/-332 lines
**New files:** `firebase_auth.py`, `login_dialog.py`, `test_firebase_auth.py`, `test_login_dialog.py`, `daemon.spec`
**Removed:** `firebase-credentials.json`, `firebase-admin` dep

### Phase 35b — Persona Auth + Dialogue Expansion (2026-06-08)
**Branch:** `master` (commit `410a47b`)

**What was built:**
- **Persona-infused LoginDialog** — Kenny+Kenny UI strings ("Daemon: Clearance Check", "Access the Brain"), `_butcher_email()` helper for roasted error messages, persona error messages
- **PetFSM.transition_to()** — Centralized state transition method with optional callback; replaces direct `self.current_state = PetState.X`
- **RISKY_KEYWORDS dict** in `src/constants.py` — 6 keyword groups with 12 hardcoded roast lines for zero-latency interruptive reactions
- **daemon-skill.md Bickering Pair protocol** — `kenny_roast`/`kenny_panic` modes and protocol rules for LLM-generated two-voice arguments
- **Hostile onboarding** — PetWindow shows DEVASTATED state + "Intruder!" bubble when fresh login needed; LoginDialog appears natively over the panicking pet; CRUD+MemoryManager created lazily on login success
- **Interruptive Interrogator** — `_on_typing_debounce` checks typing buffer for keywords using regex word boundaries; zero-latency bypass of OpencodeWorker
- **Bickering Pair dispatcher** — `_dispatch_multiplexed(modes)`, `_on_structured_multiplexed(items)` with QTimer.singleShot(3500ms) sequencing; 10% trigger chance in autonomous timers
- **Auth gate moved** — LoginDialog moved from daemon.py into PetWindow so pet is visible on screen during authentication

**Files changed:** 8 files, +358/-61 lines
**New tests:** 4 (constants) + 3 (pet_fsm) + 3 unique (login_dialog) + ~10 (pet_window)
**Key decisions:** Bickering Pair dialogue is LLM-generated (no local constants). Risky keywords hardcoded for zero latency. Regex `\b` boundaries prevent false alpha matches. No new FSM states needed.

---

## Phase 36 — Agentic Architecture ✅ COMPLETE

**Commits:** `7739044` → `d037a66` (7 commits, squash-merged to master)

**What was built:**
1. **Native Agent Skills** — Created `.opencode/skills/kenny/SKILL.md` (169 lines, YAML frontmatter, full Kenny persona). Deleted `assets/daemon-skill.md`. Deleted noReply injection logic from ContextManager/OpencodeWorker/PetWindow (~280 lines removed).
2. **JSON Schema Structured Output** — Added `STRUCTURED_SCHEMA` to constants. Rewrote `OpencodeWorker.send()` to pass schema in API POST. Deleted `_parse_json_batch`/`_parse_json_response`/`_normalize_parsed` (~100 lines of regex parsing). Added `_handle_schema_error()` fallback.
3. **MCP FSM Bridge** — Created `src/fsm_bridge.py` (FSMActionBridge with pyqtSignal, no mutex). Created `src/mcp_server.py` (in-process http.server on port 4097, JSON-RPC 2.0, SSE init, single `change_visual_state` tool). 14 tests across both modules.
4. **Telemetry preserved** — `ContextManager.build_context()` retained, produces ~150-token APM/window/memory context. `build_user_trigger`/`build_autonomous_trigger` retained for trigger coalescer.
5. **MCP lifecycle in PetWindow** — FSMActionBridge + MCPServer started on boot, stopped on shutdown. `_on_mcp_fsm_action` dispatches all 11 visual states.
6. **E2E verified** — MCP `tools/list` returns single tool. `tools/call` with valid action returns ok. Invalid action returns -32602 error.

### Key Decisions
- No mutex on FSMActionBridge — PyQt6 QueuedConnection handles cross-thread safety
- Single `change_visual_state` tool (not 11 separate tools) — saves MCP token overhead
- JSON `action` field is informational only — MCP tool call is sole state change path
- Memory kept as text injection (not MCP tool) — prevents LLM from corrupting local facts
- Node.js plugin deferred — session management stays in Python
- `parse_raw` static method retained for stateless JSON-RPC testing without server startup

---

---

### Phase 40 — The Sentinel Update (2026-06-11)
**Branch:** `master` (squashed, commit `abce769`)

**What was built:**

**Task 1 — The Guardian (Health Monitoring):**
- `check_health(port=4096, timeout=1.0) -> bool` added to `src/opencode_serve_manager.py` — uses `socket.create_connection` to check if the opencode serve port is accepting TCP connections
- Heartbeat QTimer (10s interval) in `PetWindow.__init__` with `_brain_disconnected` flag tracking
- `_on_health_check()` — transitions to DEVASTATED + shows "brain disconnected" bubble on failure; transitions to IDLE + shows "back online" bubble on recovery
- `_on_restart_brain()` — calls `ensure_opencode_serve_running()` then rechecks health
- "Restart Brain" context menu action with `restart_brain` signal
- 7 new tests (3 health check + 4 PetWindow health monitor), all pass

**Task 2 — The Critic (Thought Log UI):**
- `src/thought_log_dialog.py` (NEW) — `ThoughtLogDialog(QDialog)` with Matrix-style green-on-black QTextEdit, 1s auto-refresh timer, reads `data/.daemon_thoughts.log`, handles missing file gracefully ("No thoughts recorded yet...")
- Removed `if not DEBUG: return` guard from `_log_thought` in `pet_window.py` — thoughts now always written to log, not just in verbose mode
- "View Brain Scan" context menu action with `thought_log` signal
- `_open_thought_log()` creates/show dialog (lazy singleton)
- Cleanup in `_force_quit_app` to close dialog on shutdown
- 5 new tests, all pass

**Task 3 — The Observer (Screen Text Delta):**
- `get_foreground_text_delta() -> str` — SHA-256 delta hashing, returns `"[Screen unchanged]"` when content matches last call, returns `""` for empty/no-window (never caches empty)
- `clear_screen_cache()` — resets hash to force fresh read
- `ScreenReader.get_foreground_text()` delegates to `get_foreground_text_delta()` internally (backward compatible)
- `_has_significant_delta()` in `pet_window.py` calls `clear_screen_cache()` on window change
- 6 new tests (5 delta + 1 window change), all 11 screen reader tests pass

**Files changed:** 9 files, +352/-6 lines

**Key adjustments from original spec:**
- Used socket-based `_is_port_bound` pattern instead of HTTP health endpoint (opencode serve has no documented `/global/health`)
- Removed DEBUG guard from `_log_thought` — otherwise thought log dialog has no content
- `get_foreground_text_delta()` returns `""` for empty text (avoids caching "no window" state)
- All existing callers (like `_get_context_signature()`) automatically get delta-aware results

---

### Phase 39.5 — Two-Step Agentic Refill (2026-06-11)

**Commit:** `83039f6`

**What was built:**
- Fixed the "Fake Agency" bug: LLM was hallucinating MCP tool usage because the `structured` JSON schema in the payload prevented emitting tool-call tokens
- Added `two_stage_prompts` parameter to `OpencodeWorker.__init__`
- Added `_send_two_stage()` method that sends two messages: Turn 1 (no schema, tools available) → LLM calls MCP tools; Turn 2 (with schema, enriched with Turn 1 results) → LLM generates structured JSON
- Updated `run()` to dispatch to `_send_two_stage()` when `two_stage_prompts` is set
- Wired `_on_refill_needed()` in `PetWindow` to pass investigation + generation prompts via `two_stage_prompts`
- Stage 1 prompt: "INVESTIGATION — DO NOT generate JSON yet. Investigate user context (active window, APM, refill type) using MCP tools"
- Stage 2 prompt: Existing refill prompt (typing_reactions/jokes_blackmail/system), enriched with investigation results
- Zero changes to `ResponsePool`, `AutonomousResponseManager`, or MCP server
- 32/32 tests pass (new `test_two_stage_worker_sends_two_messages` test)

**Key decisions:**
- `send_two_stage()` lives on `OpencodeWorker` as `_send_two_stage()` — no new class needed
- JSON parsing fallback chain matches existing `send()` (main parse → regex extraction → `_handle_schema_error`)
- Investigation prompt is generic (active window + APM + pool type), not pool-type-specific — LLM's MCP tools handle the specifics

---

---

### Phase 42 — Stream of Consciousness (2026-06-11)

**Branch:** `master` (squashed, commit `35d55f4`)

**What was built:**

Collapsed the legacy 3-pool system (jokes_blackmail, system, typing_reactions) into a single unified ThoughtPool with type filtering, spatial TTL invalidation, and Mixed-Bag JSON schema.

**Task 1 — Constants & ThoughtPool (`c3632ba`):**
- Deleted 9 legacy pool constants (`JOKES_BLACKMAIL_POOL_*`, `SYSTEM_POOL_*`, `TYPING_POOL_*`)
- Added `THOUGHT_POOL_SIZE=20`, `THOUGHT_POOL_THRESHOLD=5`, `THOUGHT_POOL_REFILL_COUNT=5`
- Renamed `ResponsePool` → `ThoughtPool`, removed `pool_type` from `__init__`
- Added `draw_by_type(target_type, current_context_hash)` with spatial TTL invalidation
- Items with mismatched `context_hash` get discarded after 3 consecutive stale draws
- Items without `context_hash` are always valid (backward compat)
- `refill_needed` signal changed from `pyqtSignal(str)` → `pyqtSignal()`
- 6 pool tests

**Task 2 — Mixed-Bag Manager (`f3d6732`):**
- Replaced `build_pool_refill_prompt(pool_type, apm, count)` with `build_mixed_bag_prompt(count)` — produces single prompt requesting all 4 types (`typing_reaction`, `observation`, `intel_roast`, `idle_thought`)
- Collapsed `AutonomousResponseManager` to single `thought_pool` instance
- Removed `_load_local_typing_reactions()` → renamed `_load_local_seeds()`
- Removed `prime_from_user_response()` (dead code — no system pool to feed)
- 10 manager tests + 2 context manager tests

**Task 3 — PetWindow Wiring (`8b6a0b2`, amended to `35d55f4`):**
- `_trigger_chat()`: draws `typing_reaction` with `current_context_hash`
- `_trigger_boredom_query()`: draws `idle_thought` then `observation` with hash
- `_should_fire_autonomous()`: checks `thought_pool.remaining()` for boredom
- `_on_structured_multiplexed()`: adds surplus items to single pool (no pool_type dispatch)
- `_on_refill_needed()`: uses `build_mixed_bag_prompt()`, no `pool_type` param
- `_log_data_state`: single `thought_pool` count instead of jokes+system
- Removed `_on_pool_items_ready()` dead code
- 15 hardcoded Kenny typing reactions seeded into ThoughtPool on boot

**Files changed:** 9 files, +305/-484 lines

**Key decisions:**
- 4 types: `typing_reaction`, `observation`, `intel_roast`, `idle_thought` — no `system_announcement` (health check handled in Python, Phase 40)
- Field name stays `dialogue` — consistent with `_dispatch_structured()` downstream
- Items without `context_hash` always valid — backward compatible for seeded/manual items
- `count` param removed from `AutonomousResponseManager.draw()` — type-filtered draws always return 1 item
- `_BOREDOM_FALLBACK_JOKES` kept in `pet_window.py` as last-resort fallback

**Review fixes applied:**
- `draw_by_type()` no longer mutates `self._items` while iterating (uses `candidates` copy)
- Vestigial `pool_type` param removed from `_on_refill_needed()`

### Phase 43 — The Consent Matrix (2026-06-11)

**Branch:** `master` (squashed, commit `1918e7f`)

**What was built:**

7-tier boolean permission matrix that gates MCP tool execution at the routing layer. Settings UI Tab 3 "Boundaries" with 3 tier-grouped QGroupBoxes.

**Files changed:** `src/config.py`, `src/settings_dialog.py`, `src/pet_window.py`, `tests/test_settings_dialog.py`, `tests/test_config.py`

**Key details:**
- Tier 1 (Low Risk): `allow_intrusive_animations` = True
- Tier 2 (Medium Risk): `allow_audio_disruptions`, `allow_browser_redirection` = False
- Tier 3 (High Risk, red text): `allow_clipboard_hijacking`, `allow_mouse_interference`, `allow_window_management`, `allow_keyboard_injection` = False
- API-first, config keys only read in MCP dispatcher, never in renderer/FSM

### Phase 44 — The Emotion Engine (2026-06-11)

**Branch:** `master` (3 commits: `029f7d6`, `32b3031`, `61a034e`)

**Architecture:** Modifier Pattern — EmotionAnimator is pure visual overlay, never writes X/Y.

**Task 1 — Particle System + Emotion Expressions (`029f7d6`, amended):**
- `ParticleSystem` — emit/update/draw with gravity, alpha fade, 200-particle cap
- `Emotion` enum — 9 states: MIRTH, ANGER, FEAR, DISGUST, PATHOS, DEVOTION, HEROISM, WONDER, TRANQUILITY
- `EmotionAnimator` — transform curves, body color overrides, overlay descriptors, per-emotion particle emission
- Wired through `RenderContext` → `PetRenderer` → paint pipeline (transform composition, overlay drawing)
- 40 tests in `tests/test_animator.py`

**Task 2 — Throw Physics (`32b3031`):**
- Velocity-based drag tracking in `mouseMoveEvent` (dx/dt per frame)
- `THROW_VELOCITY_THRESHOLD=5.0`, `THROW_FRICTION=0.95`
- Throw trajectory as FALLING sub-state with horizontal friction + gravity
- 3 throw physics tests

**Task 3 — Window Tracking + Emotion FSM (`61a034e`):**
- `_evaluate_emotion()` — 7-rule priority chain: FEAR > DISGUST > WONDER > ANGER > DEVOTION > PATHOS > TRANQUILITY > MIRTH
- FEAR→FALLING macro transition (Task Manager detected)
- Window switch tracking for WONDER detection, 5s evaluation tick
- 7 context-driven emotion tests

### Phase 44.5 — QA & Integration Sweep (2026-06-11)

**Commit:** `00f5b6c`

**What was fixed (3 gaps found by verification matrix):**

| # | Gap | Fix |
|---|-----|-----|
| 1 | MCP firewall wasn't gated | `_CONSENT_TOOL_MAP` dict + `_is_tool_allowed()` routing gate in `_handle_tools_call`; config passed from PetWindow → MCPServer → MCPHandler |
| 2 | No animator constraint test | `test_constraint_never_writes_xy` — asserts no `_pet_x`/`_pet_y` across all 9 emotions |
| 3 | Missing logging + test coverage | `INFO` emotion transition logging in `set_emotion()`, `WARNING` MCP block logging; body color/overlay/particle tests for all 9 emotions |

**Bonus fix:** SSE keepalive loop (`_handle_sse`) — persistent `: keepalive\n\n` every 15s prevents opencode "Unable to connect" error.

**Test results:** 104/104 passed (animator: 54, mcp_server: 47, active_window: 4)

---

### Phase 44.6 — Production Log Audit Bugfixes (2026-06-12)

**Commit:** `d3fbd49`

**Bugs found in** `logs/daemon_2026-06-12_00-04-04.log` **audit:**

| # | Bug | Severity | Fix |
|---|-----|----------|-----|
| 1 | Zombie worker on shutdown — `OpencodeWorker.run()` blocking on `requests.post(180s timeout)` ignores `QThread.quit()` | CRITICAL | `_abort` flag checked before each blocking call in `_post_message()`, `send()`, `_send_two_stage()`; `abort()` method called before `worker.quit()` in `_force_quit_app()` |
| 2 | Click-through thrashing — binary `geom.contains(cursor)` toggles rapidly when cursor near pet edge during CHASE movement | MEDIUM | Hysteresis deadzone: expanded geometry for entry (15px margin), shrunk geometry for exit (15px margin) — eliminates edge jitter during movement |
| 3 | FSM double-fire in logs — two `IDLE→CHASE` transitions logged at same second | LOW | Guard in `PetFSM.update()`: `if next_state == self.current_state: return` skips redundant state assignment |
| 4 | Preemption timer stale — `_idle_seconds` never reset on user input; deferred triggers carry pre-interaction idle time | MEDIUM | `_idle_seconds = 0.0` and `_deferred_trigger_params = None` in `_on_input_submitted()`; deferred trigger re-reads `self._idle_seconds` via `params["idle_seconds"] = self._idle_seconds` at fire time |
| 5 | Firebase config undocumented | LOW | Comment block in `constants.py` with GCP service account instructions |

**Additional finding:** Deferred autonomous triggers carry stale `idle_seconds` — fixed by re-reading current `self._idle_seconds` at fire time rather than using captured params.

**Test results:** 208/208 in targeted pass (FSM, hysteresis, animator, MCP, config, constants, brain_schema, diary, history). 11 pre-existing failures in `test_master_tick.py` + `test_behavior_integration.py` (mock PetWindow lacks Phase 44's `_emotion_timer_sec`).

---

### Phase 45 — The Puppeteer ✅ COMPLETE (Phase 45.1-45.3)

**Commit:** `dadd9c1`

**Tasks:**

| Task | File | Status | Notes |
|------|------|--------|-------|
| 45.1 Add 3 new MCP tools | `src/mcp_server.py` | ✅ | `simulate_keystroke`, `move_mouse`, `browser_navigation` with pynput Controllers, consent gating, safety checks |
| 45.2 Add 9 new tests | `tests/test_mcp_server.py` | ✅ | 3 per tool: allowed (patched), blocked (consent), edge case (window key, bad URL, negative coords) |
| 45.3 Update config model ID | `data/.daemon_config.json` | ✅ | Fix stale `deepseek-v4-flash` → `deepseek-v4-flash-free` |

**Changes:**
- `src/mcp_server.py`: Added 3 tool handlers with pynput, 50-char keystroke limit, Windows-key blocking, screen-space mouse clamping, http/https-only browser navigation
- `tests/test_mcp_server.py`: Added 9 new tests, updated 3 existing tests (tools_list_count, tools_list, consent tests)
- `data/.daemon_config.json`: Fixed model ID to `deepseek-v4-flash-free`

**Test results:** 58/58 MCP + config tests pass (all 49 MCP server tests + 9 new Puppeteer tests).

---

### Phase 45.4 — Unified Config Migration ✅ COMPLETE

**Commit:** `e0b0d0b`

**Tasks:**
- Created `data/daemon_config.json` with nested schema
- Rewrote `src/config.py` to support deep merging, flat-to-nested adapters, and valid key filtering
- Stripped user-configurable values from `src/constants.py`
- Updated `src/pet_window.py` to use nested access + pass flat to SettingsDialog + update `_save_settings`
- Updated `src/opencode_worker.py` and `src/firebase_auth.py` to retrieve values from configuration
- Updated `src/tts_worker.py` to accept nested configuration
- Fixed pre-existing PyQt6 test constructor bypasses in `tests/test_master_tick.py` and `tests/test_behavior_integration.py`
- Deleted old dot config file `data/.daemon_config.json`
- Verified all unit and integration tests pass successfully

**Test results:** All targeted and full test runs pass, including the previously failing `test_master_tick.py` and `test_behavior_integration.py` tests.

---

### Phase 48 — Consent Matrix Migration (2026-06-14)

**Commit:** `f069860`

**What was done:**
- Migrated from 11-tier consent matrix to 7-tool consent matrix in `src/config.py`, `src/mcp_server.py`, `src/settings_dialog.py`, `src/pet_window.py`
- Renamed tools and consent keys:
  - `capture_screenshot` → consent key: `allow_window_management`
  - `allow_system_notifications` → `allow_audio_disruptions`
  - `allow_clipboard_reading` → `allow_clipboard_hijacking`
  - Removed: `allow_screenshot_capture`, `allow_file_listing`, `allow_file_reading`, `allow_codebase_search`, `allow_memory_access`, `allow_diary_access` (read-only tools now always allowed)
- Updated `_CONSENT_TOOL_MAP` in `mcp_server.py` to new 7-tool mapping
- Updated all tests in `tests/test_mcp_server.py` and `tests/test_settings_dialog.py`
- Set correct defaults per AGENTS.md: Tier 1 = True, Tier 2/3 = False

**Test results:** 68/68 tests pass in affected modules

**Files Changed:**
- `src/config.py` — Updated DEFAULT_CONFIG and FLAT_TO_NESTED/NESTED_TO_FLAT consent keys to match Phase 43 consent matrix
- `src/mcp_server.py` — Updated _CONSENT_TOOL_MAP to use new consent key names, removed read-only tool entries
- `src/settings_dialog.py` — Updated constructor params and UI widgets for new consent matrix
- `src/pet_window.py` — Updated _saved_consent defaults and consent_keys tuple
- `tests/test_mcp_server.py` — Updated test handlers and assertions for new consent keys



---

### Phase 17 — opencode Session Persistence + Parser Robustness ✅ COMPLETE

| Task | File | Status | Notes |
|------|------|--------|-------|
| 17.3 Skill-once optimization | `src/opencode_worker.py`, `src/pet_window.py` | ✅ | `include_skill` param on `_build_prompt`; only sent on first query; CONCISE_PROMPT used for subsequent → moved to PS1-side skill loading |
| 17.4 Session state wiring | `src/pet_window.py` | ✅ | `_session_active` set True in all 3 success handlers; passed to all 4 worker creation sites |
| 17.5 Verification | — | ✅ | 179/179 tests pass, 1 skipped |
| 17.6 Fix `-Continue:$true` PowerShell crash | `src/opencode_worker.py` | ✅ | Changed `cmd.append("-Continue:$true")` → `cmd.append("-Continue")` — PowerShell `-File` mode passes `$true` as literal string, breaking `[switch]` param |
| 17.8 Batch array fallback for unquoted keys | `src/opencode_worker.py`, `tests/test_opencode_worker.py` | ✅ | Brace-depth splitting in `_parse_json_batch` extracts individual objects and parses each via `_parse_json_response` regex fallback; covers model outputting JS-style `{key:"value"}` |
| 17.9 Remove unquoted-key negative example | `assets/daemon-skill.md` | ✅ | Deleted `{ thought: "...", dialogue: "..." }` from INVALID section — LLMs learn from all examples including negative ones, causing model to output unquoted keys |

---

### Task 2 — Tuning: Dialog Cache 3→6, Active Chat 45→15s

| Task | File | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 2.1 Test + constants | `src/constants.py`, `tests/test_opencode_worker.py` | ✅ | d30fdbf | Updated ACTIVE_CHAT_INTERVAL_SEC 45→15, DIALOG_CACHE_SIZE 3→6; both tests pass |
| 2.2 Skill docs + prompts | `assets/daemon-skill.md`, `src/opencode_worker.py` | ✅ | d30fdbf | Updated 4 references in skill, 2 prompts in worker fallback & context line |
| 2.3 Verification | — | ✅ | d30fdbf | All 168 tests pass, 1 skipped; commit d30fdbf successful |

---

### Phase 18 — Dialog Cache Fix + Full Skill Loading + Debug Mode ✅ COMPLETE

| Task | File | Status | Notes |
|------|------|--------|-------|
| 18.1 Fix dialog cache cycling | `src/pet_window.py` | ✅ | `_dispatch_structured` calls from cache use `force=True` so bubble always shows; prevents skipped bubbles causing cache desync |
| 18.2 Load full daemon-skill.md in Python | `src/opencode_worker.py` | ✅ | `_build_prompt()` reads full `assets/daemon-skill.md` via `Path.read_text()` and prepends to every prompt |
| 18.4 Remove include_skill/NoSkill | `src/opencode_worker.py`, `src/pet_window.py` | ✅ | Removed `include_skill` param from `OpencodeWorker.__init__`, `_build_prompt`, and all call sites; removed `-NoSkill` from CLI invocation |
| 18.5 Add --verbose / DEBUG mode | `daemon.py`, `src/constants.py`, `src/pet_window.py`, `src/opencode_worker.py`, `src/memory_manager.py` | ✅ | Added `--verbose` CLI flag; `DEBUG` constant in `constants.py`; `debug_log()` helper that only prints when `DEBUG=True`; added debug logs to all key methods |
| 18.6 Full DB context in prompts | `src/memory.py`, `src/history.py` | ✅ | `get_context_block()` now accepts `None` to return ALL entries instead of just last 5/3 |
| 18.7 Tests | `tests/test_pet_window.py`, `tests/test_opencode_worker.py` | ✅ | Fixed test expecting `include_skill`; added `test_build_prompt_includes_full_skill_file` and `test_debug_log_only_prints_when_debug_true`; 182 pass, 1 skip |

### Phase 19 — OpenCode ADK API Call + DeepSeek V4 Flash + CLI Failover ✅ COMPLETE

| Task | File | Status | Notes |
|------|------|--------|-------|
| 19.1 Constants + config | `src/constants.py`, `src/config.py` | ✅ | `OPENCODE_SERVER_URL` (default `http://127.0.0.1:4096`), `OPENCODE_API_MODEL_PROVIDER`=`opencode-go`, `OPENCODE_API_MODEL_ID`=`deepseek-v4-flash`, `OPENCODE_API_TIMEOUT_SEC=90`; both URL and model id overridable via `~/.daemon_config.json` |
| 19.2 `_run_api()` method | `src/opencode_worker.py` | ✅ | `requests` POST to `/session` (if no session_id) then `/session/{id}/message`; extracts concatenated text from `parts[]` where `type=="text"`; returns `None` on connection error, timeout, 4xx/5xx, or empty text → caller falls back to CLI |
| 19.3 Session reuse | `src/opencode_worker.py`, `src/pet_window.py` | ✅ | New `session_id` kwarg on `OpencodeWorker`; `session_created` signal carries new id; `PetWindow._opencode_session_id` is stored at first API response and passed to every subsequent worker; `_close_opencode_session()` DELETEs `/session/{id}` on quit |
| 19.4 API-first with CLI failover | `src/opencode_worker.py` | ✅ | `run()` calls `_run_api(prompt)` first; on `None`, calls `_run_cli(prompt)` (existing PS1 path). CLI behaviour unchanged. |
| 19.5 Tests | `tests/test_opencode_worker.py` | ✅ | 8 new tests: API success (skip CLI), session reuse (single POST), ConnectionError→CLI, 4xx→CLI, Timeout→CLI, no-text-parts→CLI, both-fail→error, constants present. 190 pass, 1 skip. |

---

### Memory & LLM Optimization — Task 1 (WriteCoalescer) ✅ COMPLETE

| Task | File | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 1.1 WriteCoalescer module | `src/write_coalescer.py` | ✅ | `1927d6c` | QTimer-based batched flush (default 8s); `mark_dirty` / `flush` / `start` / `stop` API; per-flag independent retry; diary `synced` count read from file on each flush |
| 1.2 Memory coalescer param | `src/memory.py` | ✅ | `1927d6c` | `remember(key, value, coalescer=None)` and `forget(key, coalescer=None)`; `TYPE_CHECKING` import to avoid circular dep |
| 1.3 History coalescer param | `src/history.py` | ✅ | `1927d6c` | `add_entry(..., coalescer=None)`; same `TYPE_CHECKING` pattern |
| 1.4 Tests | `tests/test_write_coalescer.py`, `tests/test_memory.py`, `tests/test_history.py` | ✅ | `1927d6c` | 10 WriteCoalescer tests + 2 memory coalescer tests + 1 history coalescer test = 13 new tests; 226 pass, 1 skip |


---

### Memory & LLM Optimization — Task 2 (ContextBuilder + OpencodeWorker prompt=) ✅ COMPLETE

| Task | File | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 2.1 ContextBuilder module | `src/context_builder.py` | ✅ | `aeb31f1` | Snapshots baseline (memory/history/diary/window/APM) on first call; subsequent calls emit deltas. `on_path_change('cli')` resets baseline for full-prompt fallback. `build_prompt(user_input, context_hint, apm, is_autonomous, modes, idle_seconds, last_action)` — single entry point. |
| 2.2 Tests | `tests/test_context_builder.py` | ✅ | `aeb31f1` | 12 tests (full/delta, new facts/history/diary/window/APM bucket, reset, modes, persona hint, re-snapshot) |
| 2.3 OpencodeWorker prompt= | `src/opencode_worker.py` | ✅ | `aeb31f1` | `OpencodeWorker.__init__` accepts `prompt=str|None`; `run()` uses prebuilt prompt if set, else falls back to legacy `_build_prompt` for non-PetWindow callers |
| 2.4 Modes= wiring | `src/opencode_worker.py` | ✅ | `aeb31f1` | `modes: list[str]` kwarg on `OpencodeWorker`; when set, response items are tagged by REQUEST INDEX (ignoring model's `mode` field) to prevent silent reordering |


---

### Memory & LLM Optimization — Task 3 (TriggerCoalescer + PetWindow Wiring) ✅ COMPLETE

| Task | File | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 3.1 TriggerCoalescer module | `src/trigger_coalescer.py` | ✅ | `bb15057` | QTimer single-shot (default 2.5s) batches autonomous triggers. `request(mode, user_input, context_hint, apm, idle_seconds)` appends to pending. `cancel()` clears. `drain_pending()` returns copy. `_fire()` calls `on_fire(pending)` unless `query_pending_check()` returns True (drops with log). `mode="user_input"` fires synchronously. |
| 3.2 PetWindow wiring | `src/pet_window.py` | ✅ | `bb15057` | Construct WriteCoalescer + ContextBuilder + TriggerCoalescer in `__init__`. Memory/History coalescer attribute set after construction. Active_chat/joke/boredom ticks now call `_trigger_coalescer.request(mode)` instead of building a worker. Curiosity keeps its existing user-ask behavior (no LLM call). New `_should_fire_autonomous()` DRY helper. New `_dispatch_multiplexed(pending)` aggregates requests and starts ONE `OpencodeWorker` with `modes=[...]` and prebuilt prompt from ContextBuilder. New `_on_structured_multiplexed(items)` slot handles the multiplexed response; first item dispatched, rest cached. `_on_input_submitted` calls `coalescer.cancel()` after dialog cache clear. `_force_quit_app` follows spec section 7: timers → coalescer.cancel() → write_coalescer.stop()+flush() → worker.stop() → close session → APM.stop() → tray.hide() → quit. |
| 3.3 Constants | `src/constants.py` | ✅ | `bb15057` | `TRIGGER_COALESCE_WINDOW_SEC = 2.5` |
| 3.4 Memory/History constructor injection | `src/memory.py`, `src/history.py` | ✅ | `bb15057` | `Memory(path, coalescer=None)` and `History(path, coalescer=None)` accept coalescer; per-call coalescer param takes precedence over stored |
| 3.5 Tests | `tests/test_trigger_coalescer.py`, `tests/test_pet_window.py` | ✅ | `bb15057` | 8 TriggerCoalescer tests (constructor, request, drain, cancel, fire-callback, fire-drops-when-pending, user_input-immediate, user_input-cancels) + 8 new PetWindow integration tests (constructs coalescers, stored coalescer used by memory/history, active_chat/joke go through coalescer, curiosity preserved, input cancels pending, force_quit calls cancel+stop+flush, _should_fire_autonomous). 226 → 242 pass, 1 skip |


---

### Memory & LLM Optimization — Task 4 (daemon-skill.md 50/50 Kenny+Kenny Hybrid + Multiplexed Contract) ✅ COMPLETE

| Task | File | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 4.1 Persona rewrite | `assets/daemon-skill.md` | ✅ | `ef18547` | Full rewrite. 50/50 hybrid of Kenny (Gatlian, *High on Life*) and Kenny Smith (*Rick and Kenny*). 9 sections: identity anchor, two voices, verbal tics, memory/history awareness, environmental context, action matrix, multiplexed output contract, examples, JSON output spec. 6 existing examples updated with Kenny stammering; 2 new multiplexed examples added (active_chat+joke, curiosity+boredom). All 10 dialogues ≤ 20 words. Worker code (`structured_multiplexed` signal) was already in place from prior work; skill file now documents the contract. No code changes, no test changes — 226 tests still pass. |

---

### Memory & LLM Optimization — Task 5 (TypingBuffer Wiring) ✅ COMPLETE

| Task | File | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 5.1 Import + instantiate TypingBuffer | `src/pet_window.py` | ✅ | `70681af` | Imported after APMWorker; instantiated and started in `__init__` after APMWorker block |
| 5.2 Debounced reaction wiring | `src/pet_window.py` | ✅ | `70681af` | 2s single-shot QTimer; `text_updated` signal restarts timer; `_typing_last_len` tracks position |
| 5.3 `_on_typing_debounce` method | `src/pet_window.py` | ✅ | `70681af` | Checks ≥30 new chars and `_autonomous_query_pending` before triggering |
| 5.4 `_trigger_autonomous_query` method | `src/pet_window.py` | ✅ | `70681af` | Created since not found in codebase — uses OpencodeWorker with `is_autonomous=True` and `typing_content` context |
| 5.5 Pass `typing_content` to all prompt builders | `src/pet_window.py` | ✅ | `70681af` | Added to both `_on_input_submitted` OpencodeWorker call and `_on_refill_needed` build_prompt/OpencodeWorker calls |
| 5.6 Stop TypingBuffer on shutdown | `src/pet_window.py` | ✅ | `70681af` | Added `self._typing_buffer.stop()` before `_apm_worker.stop()` in `_force_quit_app` |
| 5.7 Fix test assertion for new kwarg | `tests/test_pet_window.py` | ✅ | `70681af` | Added `typing_content=""` to expected call in `test_input_submission_starts_opencode_worker` |


---

### Phase 47 — SKILL.md Complete Rewrite + Doc Sync (2026-06-13)

**Commits:** `2d85587` (initial rewrite) → `a97b55b` (15-point Phase 46 alignment)

**What was done:**

`.opencode/skills/kenny/SKILL.md` — fully rewritten from 113 lines to 280+ lines. All 15 deficiencies from the Phase 46 architecture audit addressed:

| # | Gap | Fix |
|---|-----|-----|
| 1 | Only 7 of 12 MCP tools documented | All 12 tools listed with params, consent keys, and hard constraints |
| 2 | Hardcoded "UNCENSORED" profanity | Runtime `full`/`moderate`/`sfw` param with per-level rules and SFW swap table |
| 3 | No Mixed-Bag item types in schema | Schema B added: `type` field required (`typing_reaction`/`observation`/`intel_roast`/`idle_thought`) |
| 4 | Thin stutter guidance | Full phonetics section: syllable split, word repeat, consonant catch, vowel stretch, sibilant emphasis |
| 5 | Outdated brain_update schema | Explicit writable/locked field tables; values = arrays of strings only |
| 6 | Locked fields not named | All 9 locked fields explicitly listed with validator-rejection warning |
| 7 | Tool constraints missing | `simulate_keystroke` max 50 chars; `browser_navigation` http/https only |
| 8 | No FSM vs Emotion boundary | Critical Boundary blockquote: LLM owns `change_visual_state`, system owns EmotionAnimator |
| 9 | Two-Stage contradiction | Stage 1 (INVESTIGATION) = natural language; Stage 2 (Generate N items) = strict JSON; explicit section |
| 10 | Spatial TTL not explained | Spatial TTL Warning block in Schema B; per-type TTL column; specificity requirement |
| 11 | Consent error not handled | -32001 → in-character roast in `dialogue`, log in `thought`, never surface to UI |
| 12 | No emotion-to-dialogue map | Full 9-emotion vocal style table; trigger conditions for each |
| 13 | `assets/daemon-skill.md` refs | All stale references removed |
| 14 | Missing codebase module map | Full module table with file/class/purpose for all 13 core files |
| 15 | No brain_update guidance on `get_memory` first | Explicit rule: call `get_memory` before personalizing dialogue |

**Docs also updated:**
- `docs/architecture.md` — Phase 46 coverage, SKILL.md contract section (2.2) fully rewritten, response pools → unified ThoughtPool, key decisions table expanded, TTS note corrected, recommended improvements updated
- `AGENTS.md` — Phase 46 Juice/EmotionProfile registry table added to Emotion Engine section; SKILL.md file map description expanded; 5 new pitfall rows (Stage 1/2 confusion, locked fields, spatial TTL, -32001 handling, EmotionProfile registry)

**Files changed:** `.opencode/skills/kenny/SKILL.md`, `docs/architecture.md`, `AGENTS.md`

---

## Git Workflow (ALWAYS follow this)

```
git checkout -b task-<N>-<slug>
# ... implement + commit on branch ...
git checkout master
git merge --squash task-<N>-<slug>
git commit -m "feat: ..."
git branch -D task-<N>-<slug>
```

Never commit to master directly. Never put AI assistant names in commit messages.

---

## Known Issues / Pitfalls Encountered

| Issue | Resolution |
|-------|-----------|
| HWND not available in `__init__` | Get `int(self.winId())` in `showEvent` after `show()` |
| `HYPER_FLASH` was a mutable list | Changed to tuple in 1.1 review |
| `_draw_state_overlay` leaked painter font state | Added `painter.save()/restore()` in 1.3 |
| `jump_y` in celebrate was oscillating downward | Changed to `abs(math.sin(...))` and negated in y calc |
| PyQt6 `event.position()` returns logical pixels | Do NOT divide mouse event coords by scale — already logical |
| Debug simulation `is_dragged=True` for one tick only | Use `70 <= tick < 80` ranges, not `tick == 70` |
| `FSMContext(**{**ctx.__dict__, ...})` fragile | Use `dataclasses.replace(ctx, field=value)` |
| `availableGeometry()` returns physical pixels on this Win11/PyQt6 setup | Always divide by `devicePixelRatio()` for screen geometry |
| `_click_through` AttributeError on startup | `show()` in `_setup_window()` fires `showEvent` immediately — init `self._click_through = None` BEFORE calling `_setup_window()` |
| Windows shell/encoding issues | Run `powershell.exe` with bypass execution policy and force UTF-8 encoding |
| Emoji encoding/rendering glitch | Set `$OutputEncoding` and `[Console]::OutputEncoding` to UTF8 in PowerShell, and use `font.setFamilies` with `"Segoe UI Emoji"` fallback in QPainter |
| AUTONOMOUS_THINKING never exits | All three callbacks (_on_structured_result, _on_opencode_result, _on_boredom_error) must clear autonomous_query_pending |
| JSON corrupted by markdown stripper | Always parse JSON from raw stdout BEFORE calling _process_output |
| Eye pupil drift in rotated states | screen-space atan2 in rotated painter coord — max 15° mismatch, intentional tradeoff |
| `os.environ.get` mock too broad in tests | Narrow with `side_effect` lambda: `lambda k, *a: "val" if k == "OPENCODE_API_KEY" else os.environ.get(k, *a)` |
| `firebase_admin` duplicate init | `initialize_app()` raises `ValueError` if called twice. Guard: `try: firebase_admin.get_app()` → `except ValueError: firebase_admin.initialize_app(cred)` |
| `OPENROUTER_API_URL` is base URL only | OpenAI SDK appends `/chat/completions` automatically — do NOT append it manually when calling the SDK |
| `requests.exceptions.ConnectionError` only catches `requests` exceptions | When mocking the API in tests, use `_real_requests.exceptions.ConnectionError` (not the built-in `ConnectionError`) as the `side_effect`. Patching the entire `requests` module breaks `requests.exceptions` references. |
| Windows clipboard global lock | `CloseClipboard()` must be in `finally` block — if left open, clipboard breaks until Daemon killed |
| Non-text clipboard data | `GetClipboardData(CF_UNICODETEXT)` returns null handle for images/files — return descriptive string |
| Screenshot directory must exist | `os.makedirs(dir_path, exist_ok=True)` before `screenshot.save()` |
| Windows Focus Assist suppresses toasts | `QSystemTrayIcon.showMessage()` silently drops notifications during full-screen games |
| COM UIA should be singleton | `_get_uia_automation()` lazy singleton avoids DLL binding 60x/min; `_cleanup_uia()` on shutdown |
| `worker.wait()` blocks GUI thread | On SLEEP transition, use signal `disconnect()` + `worker.quit()` instead of `wait()` |
| backoff can race with timer | Only increment backoff *after* a boredom FSM trigger fires, not on every tick |
| Path traversal in MCP | Use `os.path.normpath(os.path.abspath(path))` and verify prefix — Windows accepts both `/` and `\` |
| SLEEP timers tick unconditionally | Add `if state == SLEEP: return` at top of `_master_tick` to freeze all timers |
| SLEEP deferred trigger leak | Guard `_fire_deferred_trigger` with FSM state check — drop params in SLEEP |
| Joke timer ignores backoff | Add `elapsed_since_boredom >= _idle_backoff_seconds` gate in P3 joke route |
| `_consecutive_silent`/`_consecutive_engaged` not initialized | Initialize in `__init__` before `_on_output_displayed` can be called during startup |
| `Event` class not imported in `firebase_auth.py` | Import `Event` from `src.events` alongside `EventBus`, `EventType` | ✅ Fixed |
| `TOKEN_REFRESHED` missing from `EventType` enum | Add `TOKEN_REFRESHED = "token_refreshed"` to `EventType` enum |

---

## Recommendations For Future Sessions

- **Run tests first**: `py -m pytest tests/ -v` before starting any task — confirm baseline is clean
- **Phase 2 ordering**: Do 2.1 (FSM) before 2.2 (APMWorker) — `APMWorker` signals feed into FSM context
- **pynput on Windows**: Wrap listener start in `try/except` — some Windows configs block it
- **AgyWorker**: Reinstantiate per query, never reuse a QThread after `run()` completes
- **System tray icon**: Must be generated programmatically via `QPainter` on a 16×16 `QPixmap` — no image files
- **Test `--debug` mode** after every PetWindow/FSM change to catch regressions without needing a display

---

## Dependencies

```
PyQt6>=6.7.0
pynput>=1.7.7
pytest (dev)
requests
pyttsx3
comtypes>=1.4.8
Pillow>=10.0.0
```

Install: `pip install PyQt6 pynput pytest requests pyttsx3 comtypes Pillow`

---

## File Map (current)

```
src/
  __init__.py
  constants.py           ← All tunable values — import from here everywhere
  behavior_controller.py  ← BehaviorController (495 lines) — pure-logic autonomous behavior system: timers, engagement, emotion, backoff, EventBus dispatch. No Qt imports.
  brain_schema.py        ← 26-field brain schema, apply_brain_update, DEFAULT_BRAIN, validation
  pet_fsm.py             ← 15-state PetFSM, FSMContext dataclass, zero Qt imports
  pet_renderer.py        ← Stateless QPainter renderer, eye tracking, squash/stretch, 8-way perimeter
  click_through.py       ← Win32 WS_EX_TRANSPARENT toggle, 50ms QTimer poll
  apm_worker.py          ← pynput keyboard+mouse listeners, rolling 60s APM
  typing_buffer.py       ← pynput keystroke capture, deque ring buffer (500 chars)
  opencode_worker.py     ← HTTP API with structured JSON schema output, session reuse
  context_manager.py     ← Minimal trigger prompt builder (autonomous/user/pool_refill)
  context_menu.py        ← PetContextMenu with 6 actions, _Signals(QObject) for decoupling
  screen_reader.py       ← UIA text extraction via comtypes, WM_GETTEXT fallback
  pet_window.py          ← QWidget (1609 lines) — owns FSM, renderer, all wiring
   response_pool.py       ← ThoughtPool — single unified pool with type filtering, spatial TTL, priority decay
   response_manager.py    ← AutonomousResponseManager — single ThoughtPool, Mixed-Bag refill, persistence

  memory_manager.py      ← Firebase bridge: sync_to_local/sync_from_local, retry queue
  memory.py              ← Local JSON key-value fact store (.bak recovery, max 50 facts)
  history.py             ← Local JSON conversation log (.bak recovery, max 100 entries)
  firebase_crud.py       ← FirebaseCRUD class with 3-attempt retry, 6 CRUD verbs
  firebase_auth.py       ← Firebase Auth REST API, sign-in/sign-up/token-refresh
  diary_store.py         ← Atomic local diary I/O with .bak backup, 200-entry cap
  write_coalescer.py     ← QTimer batched flush (8s) for 5 dirty flags
  persistence.py         ← save_state/load_state to data/.daemon_state.json
  config.py              ← load_config/save_config, overridable keys
  opencode_serve_manager.py ← Auto-spawn opencode serve on boot, PID tracking
  tts_worker.py          ← TTSWorker(QThread) — pyttsx3 + pydub pitch shift + winsound
  settings_dialog.py     ← SettingsDialog(QDialog) — size/opacity/speed/voice sliders
  active_window.py       ← Win32 GetForegroundWindow, returns window title
  logging_setup.py       ← Unified stdlib logging with RotatingFileHandler
  fsm_bridge.py          ← FSMActionBridge — pyqtSignal relay for thread-safe MCP dispatch
  mcp_server.py          ← In-process JSON-RPC 2.0 MCP server, 7 tools
  login_dialog.py        ← Persona-infused email/password auth modal
  utils/
    __init__.py
    security.py          ← is_safe_write_path() sandbox, restricts writes to data/

scripts/
  generate_ast_map.py    ← AST codebase map generator (29 classes, 33 functions)

.opencode/skills/kenny/
  SKILL.md               ← Kenny persona + action matrix + output contract (loaded natively)

tests/ (~450 tests across 29 files)
  __init__.py
  test_fsm.py                    ← 35 FSM tests
  test_opencode_worker.py        ← structured schema, session reuse tests
   test_response_pool.py          ← ThoughtPool: type filtering, spatial TTL, priority tests (6 tests)
   test_response_manager.py       ← single ThoughtPool + atomic + Mixed-Bag tests (10 tests)
  test_memory_manager.py         ← Firebase mocked tests + retry queue
  test_memory.py                 ← memory key-value + .bak + coalescer tests
  test_history.py                ← history + .bak + coalescer tests
  test_context_manager.py        ← trigger/build tests
  test_write_coalescer.py        ← flush + brain flag + diary_store tests
  test_pet_window.py             ← PetWindow integration + session wiring tests
  test_pet_renderer.py           ← renderer tests
  test_screen_reader.py          ← UIA/WM_GETTEXT extraction tests
  test_active_window.py          ← active window module tests
  test_persistence.py            ← save/load + atomic write tests
  test_typing_buffer.py          ← typing capture tests (13 tests)
  test_config.py                 ← config loading tests
  test_logging_setup.py          ← logging setup tests
  test_council_additions.py      ← council feature tests
  test_opencode_serve_manager.py ← serve manager tests
  test_brain_schema.py           ← schema validation + apply_brain_update tests
  test_diary_store.py            ← atomic diary I/O, backup, cap tests
  test_firebase_crud.py          ← 22 tests (CRUD + retry)
  test_firebase_auth.py          ← Firebase Auth tests
  test_tts_worker.py             ← TTS tests (9 tests)
  test_settings_dialog.py        ← settings dialog tests (5 tests)
  test_fsm_bridge.py             ← FSM bridge signal tests
  test_mcp_server.py             ← MCP server tests
  test_security.py               ← write sandbox tests
  test_ast_mapper.py             ← AST codebase map tests
  test_codebase_awareness_e2e.py ← E2E codebase awareness tests

memory/
  project-dev-memory.md  ← THIS FILE

docs/
  architecture.md        ← Full architecture doc (generated 2026-06-10)
  OpenCode_Documentation.md
  Kenny-speach-report.md
  superpowers/plans/     ← Historical plan docs
  superpowers/specs/     ← Historical spec docs

AGENTS.md                ← Unified agent instructions
daemon.py                ← Entry point (argparse, PID lock, crash hook, auth gate)
requirements.txt         ← PyQt6, pynput, requests, pyttsx3, comtypes, Pillow
seed_brain.py            ← Standalone Firestore brain seeder
README.md                ← Comprehensive architecture documentation
```

---

---

### Phase 20 — Memory & LLM Optimization + Kenny/Kenny Persona ✅ COMPLETE

| Task | File | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 20.1 WriteCoalescer | `src/write_coalescer.py`, `tests/test_write_coalescer.py` | ✅ | `1927d6c` | QTimer-based batched flush (8s default); per-flag independent error handling; flag stays set on failure for retry; 10 tests |
| 20.2 Memory/History coalescer | `src/memory.py`, `src/history.py`, `tests/test_memory.py`, `tests/test_history.py` | ✅ | `1927d6c` (incl) | Constructor + per-call `coalescer=` param; per-call wins via `effective = coalescer if coalescer is not None else self._coalescer`; 3 tests |
| 20.3 TriggerCoalescer | `src/trigger_coalescer.py`, `tests/test_trigger_coalescer.py` | ✅ | `d26fbb9` | QTimer single-shot 2.5s; user-input mode fires synchronously; drops pending if worker already running; 8 tests |
| 20.4 ContextBuilder | `src/context_builder.py`, `tests/test_context_builder.py` | ✅ | `aeb31f1` | Full-then-delta prompt; baseline re-snapshots after each call; `on_path_change("cli")` resets baseline; 17 tests |
| 20.5 OpencodeWorker modes | `src/opencode_worker.py`, `tests/test_opencode_worker.py` | ✅ | `aeb31f1` (incl) | New `modes` kwarg, `structured_multiplexed` signal, `_SKILL_CONTENT` cached at module level; mode assignment by request INDEX (model's mode field ignored); 6 tests |
| 20.6 PetWindow wiring | `src/pet_window.py`, `tests/test_pet_window.py` | ✅ | `d26fbb9` (incl) | `_should_fire_autonomous()` DRY helper; `_dispatch_multiplexed()` aggregates modes; `_on_structured_multiplexed()` dispatches by mode; `_force_quit_app` follows spec §7 ordering; 8 integration tests |
| 20.7 Skill rewrite (Kenny+Kenny) | `assets/daemon-skill.md` | ✅ | `ef18547` | 50/50 hybrid with both voices; 6 existing examples updated with Kenny openers; 2 new multiplexed examples (active_chat+joke, curiosity+boredom); MULTIPLEXED OUTPUT CONTRACT section; 270 lines |
| 20.8 Doc sync | `CLAUDE.md`, `GEMINI.md`, `memory/project-dev-memory.md` | ✅ | `7f855cc` (incl) | Phase 20 section + 8 new pitfalls added; CLAUDE.md ↔ GEMINI.md mirror rule honored |

**Final state:** 242 tests pass, 1 skipped (52 new tests added on top of 190 baseline). Spec fully implemented. Branch `task-20-impl` ready for squash-merge to master.

**Curiosity not routed through TriggerCoalescer:** The spec listed curiosity in the 4 autonomous timers, but curiosity asks the user a question directly (no LLM call) — routing it through the coalescer would change behavior. The implementer preserved existing semantics and added a test that asserts curiosity still asks directly. This is a judgment call documented in the test `test_curiosity_tick_keeps_asking_user_directly`.

**Diary cap of 20 in full prompt:** ContextBuilder's `_build_full` truncates the diary to `self._diary[-20:]` to prevent prompt bloat. The spec said "full diary" but the cap is a sensible defensive bound. Noted as a minor deviation.

### Phase 21 — Auto-Start `opencode serve` ✅ COMPLETE

| Task | File | Status | Notes |
|------|------|--------|-------|
| 21.1 `ensure_opencode_serve_running()` | `src/opencode_serve_manager.py` | ✅ | Checks port; finds opencode on PATH; spawns as detached process (DETACHED_PROCESS + CREATE_NO_WINDOW); waits up to 5s for bind. Never raises. |
| 21.2 Wire into daemon.py | `daemon.py` | ✅ | Called at startup after `load_config()`, before PetWindow. Skipped on `--no-opencode`. |
| 21.3 Fix misleading doc | `CLAUDE.md`, `GEMINI.md` | ✅ | Removed "or keep the TUI open" — TUI does not serve HTTP. |
| 21.4 Tests | `tests/test_opencode_serve_manager.py` | ✅ | 8 tests: port-already-bound, spawn-success, not-in-PATH, Popen-failure, timeout, custom-port, log-dir-creation, no-wait-on-fast-path. |

**Note on auto-serve failure:** If a previous `opencode serve` or the daemon exited abruptly, port 4096 may enter `TIME_WAIT` for ~60 seconds. The manager's 5-second timeout won't be enough, and the daemon transparently falls back to CLI. This is transient.

**Test count:** 247 total pass, 1 skip.

### Phase 22 — Linguistic Butchery Brain Seeding ✅ COMPLETE

| Task | Files | Status | Notes |
|------|-------|--------|-------|
| 22.1 `user_mispronunciations` in brain | `src/memory_manager.py` | ✅ | 44 entries added to `_DEFAULT_BRAIN` |
| 22.2 Diary seeding | `src/pet_window.py` | ✅ | 3 imported-history entries on first run (Stopipy, Frood Coat, ODSD) |
| 22.3 Dossier section in skill | `assets/daemon-skill.md` | ✅ | DYNAMIC PSYCHOLOGICAL DOSSIER with linguistic butchery roast instructions |
| 22.4 Firestore seeder script | `seed_brain.py` | ✅ | Standalone utility: `py seed_brain.py --seed-defaults` to push to Firestore |

### Phase 23 — Engagement Tracker + Adaptive Backoff ✅ COMPLETE

| Task | Files | Status | Commit | Notes |
|------|-------|--------|--------|-------|
| 23.1 Add silence detection constants | `src/constants.py` | ✅ | `20f2f7f` | SILENCE_THRESHOLD=5, ENGAGED_THRESHOLD=2, BASE_INTERVAL_SEC=15, MAX_BACKOFF_SEC=120, BACKOFF_MULTIPLIER=1.5 |
| 23.2 Add `is_active()` to TriggerCoalescer | `src/trigger_coalescer.py` | ✅ | `57d5e75` | Returns `_running` flag; cleared on early returns in `_fire()` |
| 23.3 Engagement tracker in PetWindow | `src/pet_window.py` | ✅ | `818da78` | `_consecutive_silent`, `_consecutive_engaged`, `_current_interval`; `_on_output_displayed()`; `_should_fire_autonomous(mode)` with is_active check |
| 23.4 Add engagement + silence tests | `tests/test_pet_window.py` | ✅ | `bc1b085` | `test_silence_backoff_increases_interval`, `test_engagement_resets_to_base_interval` |
| 23.5 Early stop when bubble active | `src/pet_window.py` | ✅ | `7b595ba` | Bubble-active check before coalescer request in all 3 handlers; cache dispatch also guarded |

**Test count:** 249 pass, 1 skip.

**Key bugs found and fixed during review:**
- `_fire()` early returns leaked `_running = True` (57d5e75)
- Missing `_on_output_displayed(engaged=False)` in non-cached paths (818da78)
- Dialog cache dispatch bypassed bubble-active guard (7b595ba)

### Phase 24 — Multi-Pool Response Cache + Context Enrichment ✅ COMPLETE

| Task | Files | Status | Commit | Notes |
|------|-------|--------|--------|-------|
| 24.1 Remove hardcoded text constants | `src/constants.py` | ✅ | `a0d04f1` | Removed IDLE_QUIPS, IDLE_QUIP_INTERVAL, MEMORY_GAP_QUESTIONS, MEMORY_CURIOSITY_INTERVAL, DIALOG_CACHE_SIZE, TRIGGER_COALESCE_WINDOW |
| 24.2 Multi-pool constants | `src/constants.py` | ✅ | `a43ef29` | JOKES_BLACKMAIL_POOL_SIZE=30, SYSTEM_POOL_SIZE=10, POOL_DECAY_INTERVAL_SEC=120 |
| 24.3 ContextBuilder enrichment | `src/context_builder.py`, `tests/test_context_builder.py` | ✅ | `0fe0fd7` | 6 new context fields (day_of_week, session_duration, time_since_input, FSM state, FSM history, always last 10 history) |
| 24.4 WriteCoalescer response_cache flag | `src/write_coalescer.py` | ✅ | `736b1e3` | Added "response_cache" to dirty flags |
| 24.5 ResponseManager module | `src/response_manager.py`, `tests/test_response_manager.py` | ✅ | `112ab8f` | ResponsePool + AutonomousResponseManager with dual pools, priority-weighted draw, priority decay, persistence |
| 24.6 OpencodeWorker pool_items signal | `src/opencode_worker.py`, `tests/test_opencode_worker.py` | ✅ | `7b378a9` | `pool_items_ready` signal carrying `jokes_blackmail` + `system` items |
| 24.7 FORMAT_INSTRUCTIONS update | `src/opencode_worker.py` | ✅ | `e4244fd` | Multi-pool batch format with priority docs |
| 24.8 PetWindow TRM wiring | `src/pet_window.py`, `tests/test_pet_window.py` | ✅ | `d483e31` | Timer ticks draw from correct pools. User responses feed 2+2 items. Removed curiosity, dialog cache, quip timer |
| 24.9 Cleanup | `src/trigger_coalescer.py`, `tests/test_trigger_coalescer.py` | ✅ | `ecdc525` | Deleted TriggerCoalescer module and all references |
| 24.10 Web search | — | ✅ | Built-in | OpenCode Go's `websearch`/`webfetch` tools via Exa AI — no custom code needed |

**Architecture:**
- `AutonomousResponseManager` owns two `ResponsePool` instances
- Jokes_blackmail pool: size 30, refresh at 25, drawn by boredom/idle ticks
- System pool: size 10, refresh at 5, drawn by active_chat ticks
- Priority decays by 1 every 2 minutes (minimum 1)
- Selection uses weighted random (higher priority = more likely)
- User query responses include `jokes_blackmail_items` (2) + `system_items` (2) fed into pools
- Web search via OpenCode Go's built-in tools (TinyFish MCP, no API key needed)

**Test count:** 281 pass, 2 fail (pre-existing memory_manager.py), 1 skip.

**New pitfalls:**
| Pitfall | Fix |
|---------|------|
| WriteCoalescer ignores unknown flags | Add `"response_cache"` to `_dirty` dict before calling `mark_dirty("response_cache")` |
| Priority decay resets on pool refill | Fresh items from LLM arrive with priority 3-5, replacing decayed items naturally via weighted selection |
| Pool item format mismatch | All items must include `pool_type` tag for correct routing. `prime_from_user_response` wraps raw items with the tag |
| Empty pool returns `[]` not `None` | All timer handlers check `if not items: return` before using draw result |
| Web search falls back gracefully | If model has no web search tools, it simply answers without web data — no crash |
| PyQt6 signal + list.append doesn't work | `list.append` cannot be connected as a Qt slot (zero-arg signal + one-arg callable fails). Use `lambda: emitted.append(None)` |
| Autonomous worker signal routing | `is_autonomous=True` + no modes → `structured_batch_ready`. `is_autonomous=True` + modes → `structured_multiplexed`. Never `structured_ready` |
| Multiple pynput listeners | APMWorker + TypingBuffer both use `keyboard.Listener`. OS allows multiple low-level keyboard hooks — works correctly on Windows |

---
## Phase 25 — TypingBuffer Full Keystroke Capture (2026-06-07)

**Branch:** `master` (squash-merged, commit `84f293d`)

**What was built:**
- New `src/typing_buffer.py` — `TypingBuffer(QObject)` with pynput listener, deque ring buffer (500 chars), handles printable/backspace/enter/tab, ignores modifiers
- `typing_content` param added to `ContextBuilder.build_prompt()` and `OpencodeWorker._build_prompt()` — every LLM prompt sees "Recent Typing:\n  > <text>"
- PetWindow integration: instantiated on boot, stopped on shutdown, context passed to all query paths (user queries, refill, autonomous)
- Debounced autonomous reactions: ≥30 chars in 2s → triggers LLM query via `active_chat` mode
- 13 tests, dedicated test file
- Pool sizes reduced: jokes=10/threshold=7, system=3/threshold=1
- Priority propagation fixed: LLM `priority` field now flows through signal chain

**Files changed:** `src/typing_buffer.py` (new), `tests/test_typing_buffer.py` (new), `src/pet_window.py`, `src/context_builder.py`, `src/opencode_worker.py`, `tests/test_pet_window.py`

**Test count:** 281 pass, 2 pre-existing memory_manager failures, 1 skip.

---

## Phase 37 — Surveillance & Sabotage MCP Tools (2026-06-09)

**Branch:** `master` (squash-merged, commits `6024c2c..ffeeef2`)

**What was built:**
- 3 new MCP tools added to Daemon's in-process MCP server: `read_clipboard`, `capture_blackmail_evidence`, `send_system_toast`
- `FSMActionBridge.toast_request` signal for thread-safe Qt main thread notification delivery
- `_read_clipboard()` helper with Win32 ctypes clipboard API (try/finally guarded CloseClipboard)
- `_capture_screenshot()` helper with Pillow ImageGrab + `os.makedirs(exist_ok=True)` to `data/blackmail/`
- PetWindow slot `_on_toast_requested` wired to `QSystemTrayIcon.showMessage()`
- Kenny SKILL.md updated with SURVEILLANCE & SABOTAGE TOOLS section
- `Pillow>=10.0.0` added to `requirements.txt`
- 8 new tests (1 fsm_bridge, 7 mcp_server), all passing
- Zero new pip dependencies (Pillow was already installed)

**Architecture decisions:**
- Hybrid threading: `read_clipboard` + `capture_blackmail_evidence` run sync in MCP handler thread; `send_system_toast` routes through `pyqtSignal` to Qt main thread
- Clipboard uses ctypes (not PyQt6's QClipboard) to avoid cross-thread Qt widget access
- Screenshot helper is a pure function — no state, no side effects beyond file I/O
- Tool dispatches by `name` first (not `action`) to support multi-tool routing

**Files changed:** `requirements.txt`, `src/fsm_bridge.py`, `src/mcp_server.py`, `src/pet_window.py`, `.opencode/skills/kenny/SKILL.md`, `tests/test_fsm_bridge.py`, `tests/test_mcp_server.py`

**Test count:** 484 pass, 2 pre-existing logging failures.

**New pitfalls:**
| Pitfall | Fix |
|---------|------|
| Windows clipboard global lock | `CloseClipboard()` must be in `finally` block — if left open, clipboard breaks until Daemon killed |
| Non-text clipboard data | `GetClipboardData(CF_UNICODETEXT)` returns null handle for images/files — return descriptive string |
| Screenshot directory must exist | `os.makedirs(dir_path, exist_ok=True)` before `screenshot.save()` |
| Windows Focus Assist suppresses toasts | `QSystemTrayIcon.showMessage()` silently drops notifications during full-screen games |

### Phase 38 — LLM Mode Collapse Prevention, COM Caching, Codebase Awareness MCP Tools

| Task | File | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 38.1 COM UIA singleton caching | `src/screen_reader.py`, `src/pet_window.py` | ✅ | `3317478` | `_get_uia_automation()` lazy singleton, `_cleanup_uia()` on shutdown — eliminates DLL binding 60x/min overhead |
| 38.2 FSM SLEEP state integration | `src/pet_window.py` | ✅ | `3317478` | `PetState.SLEEP` added to blocked states in `_should_fire_autonomous` + `_trigger_boredom_query`; graceful disconnect pattern (no `worker.wait()` on main thread) for worker cleanup on SLEEP entry |
| 38.3 Exponential boredom backoff | `src/pet_window.py`, `tests/test_master_tick.py`, `tests/test_behavior_integration.py` | ✅ | `3317478` | Context stability tracking via `(window, APM, typing_len, screen_hash)`; backoff doubles after each boredom trigger in stable context (30s → 60s → 120s → 300s max); resets on user activity |
| 38.4 Read-only MCP tools | `src/mcp_server.py`, `src/utils/security.py` | ✅ | `3317478` | 3 read-only MCP tools: `list_directory`, `read_file`, `search_codebase` with path validation via `_validate_mcp_path()` and `_validate_read_extension()` |
| 38.5 Write sandbox | `src/utils/security.py` | ✅ | `3317478` | `is_safe_write_path()` guard restricting file writes to `data/` directory; screenshot tool wired through it |
| 38.6 AST codebase map | `scripts/generate_ast_map.py`, `data/codebase_map.json` | ✅ | `3317478` | Auto-generates `data/codebase_map.json` at daemon startup — 29 classes, 33 functions extracted |
| 38.7 Kenny SKILL.md update | `.opencode/skills/kenny/SKILL.md` | ✅ | `3317478` | Architectural awareness section added with 3 new MCP tools |
| 38.8 E2E codebase awareness tests | `tests/test_codebase_awareness_e2e.py` | ✅ | `3317478` | 4 e2e tests for full pipeline (read, write sandbox, AST map, read-write link) |

**New constants** (in `src/constants.py`): `MAX_IDLE_BACKOFF_SEC = 300`, `IDLE_BACKOFF_MULTIPLIER = 2.0`

**New files:** `src/utils/security.py`, `scripts/generate_ast_map.py`, `data/codebase_map.json`, `tests/test_security.py`, `tests/test_ast_mapper.py`, `tests/test_codebase_awareness_e2e.py`

**Key decisions:**
- Backoff only increases *after* a boredom FSM trigger fires, not on every tick — prevents the logic-bomb where backoff outruns the timer
- `time.time()` used for elapsed tracking instead of `_boredom_timer_ms` to avoid variable conflict with existing countdown mechanism in `_tick`
- `worker.wait()` replaced with signal `disconnect()` + `worker.quit()` pattern to avoid GUI freeze on SLEEP transition
- COM singleton is thread-safe for main thread only (verified: `get_text_via_uia()` only called from `_master_tick` running on main thread)
- Path validation uses `os.path.normpath()` to handle Windows mixed separator edge cases
- AST mapper runs at daemon startup before main window creation (daemon.py:94-102)

**Git history cleanup:** 194 commits squashed into 4 phase-boundary commits via `git rebase -i --root`. Phase 1-35 (154 commits), Phase 36 (12 commits), Phase 37 (18 commits), Phase 38 (1 commit). Duplicate origin commits and merge commit dropped.

---

### Phase 39 — Multi-Pet Refactor (2026-06-11)

**Branch:** `master` (squash-merged, commit `88e7473`)

**What was built:**

| Task | Files | Status | Notes |
|------|-------|--------|-------|
| 0. pet_id wiring | `src/config.py`, `daemon.py`, `src/pet_window.py`, `src/constants.py` | ✅ | `--pet-id` CLI arg, `pet_id` in config defaults, dynamic lockfile `data/.daemon_{pet_id}.lock` |
| 1. Multi-pet Firebase paths | `src/memory_manager.py` | ✅ | Paths use `users/{uid}/pets/{pet_id}`, user-level fields split from pet-level, `get_current_brain()`/`get_all_diary_entries()` added |
| 2. Diary encapsulation + hash dedup | `src/diary_store.py`, `src/write_coalescer.py`, `src/context_manager.py`, `src/pet_window.py` | ✅ | SHA-256 content-hash dedup, legacy `list[str]`→`list[dict]` migration on read, 200-entry cap, `.bak` fallback fixes, removed dead `diary_entries_ref` param |
| 3. MCP memory tools | `src/mcp_server.py`, `src/pet_window.py`, `tests/test_mcp_server.py` | ✅ | `get_memory`/`get_diary` tools, local read-only, null-limit guard, 8 new tests (38 total) |
| 4. ResponsePool extraction | `src/response_pool.py` (NEW), `src/response_manager.py`, `tests/test_response_manager.py` | ✅ | `ResponsePool` class extracted to dedicated module, clean imports, 25 tests pass |
| 5. firestore.rules | `firestore.rules` (NEW) | ✅ | Authenticated-only, per-user scoped, covers `users/{uid}` + pets subcollection + diary subcollection |
| 6. Config pruning | `src/config.py`, `src/settings_dialog.py` | ✅ | `_USER_FACING` reduced to 11 keys, `pet_speed`→`pet_speed_multiplier`, `tts_pitch` added |
| 7. Brain schema standardize | `src/brain_schema.py`, `tests/test_brain_schema.py` | ✅ | Unified 24-field schema, `USER_LEVEL_FIELDS` module constant |
| 8. Misc fixes | multiple | ✅ | Session reuse, SLEEP timer freeze, click-through debounce, brain load dedup, default config autocreate |

**Squashed 13 commits** — `dfd1e8c..16d0c27` (session reuse, SLEEP timers, click-through debounce, brain load dedup, config autocreate, pet_id wiring, lockfile, multi-pet paths, USER_LEVEL_FIELDS, diary dedup, brain schema, config pruning)

**Key decisions:**
- Option C (Minimal Churn) for MCP tools: static `MCP_TOOLS` list + `elif` dispatch + class-level attrs on `MCPHandler`
- Option A (Nested path support) for Firestore: pass `"users/{uid}/pets"` as collection, `pet_id` as doc_id
- Option B (New format + migration) for DiaryStore: dict format with read-time legacy string migration
- Option A (Local MCP reads): MCP tools read local Memory/DiaryStore, not Firebase
- Config + CLI hybrid for pet_id: config stores default, CLI overrides
- Hidden Power-User Pattern: `_USER_FACING` contains 11 user-facing keys; `_OVERRIDABLE` holds all internal dev keys

**Fixes applied during review:**
- `.bak` fallback now handles `FileNotFoundError` (silent data loss prevented)
- `_write_atomic` re-raises exceptions so WriteCoalescer keeps dirty flag on failure
- PetWindow MCPServer construction moved after `self._memory`/`self._diary_store` init (use-before-assignment crash)
- `get_diary` limit clamped `max(1, min(int(raw_limit or 10), 50))` (null-limit `TypeError` crash)
- Removed dead `diary_entries_ref` from WriteCoalescer + ContextManager
- Removed dead `_snapshot_current` method from ContextManager
- `pet_speed` → `pet_speed_multiplier` rename to match internal variable name

**Test count:** 416 pass, 1 pre-existing pet_window failure (test_active_chat_tick_dispatches_trigger)

### Documentation Overhaul (2026-06-12)

**What was done:**
- **AGENTS.md** — Complete rewrite with exhaustive end-to-end architecture documentation. Based on deep analysis of all 35 source files, 49 test files, and all existing docs via 6 parallel research agents.
- **README.md** — 12 targeted fixes: MCP tools 7→12, test count 522/28→450+/49, deps corrected (openai/edge-tts not requests/pyttsx3), config flat→nested, brain schema 26→22 fields, TTS engine updated, response pool 3→unified ThoughtPool, 4 missing files added to file map.
- **docs/architecture.md** — 7 targeted fixes: phase coverage 39→45, brain schema 26→22, pool 3→single, MCP tools 9→12 (+3 new), test count updated, PetWindow lines 1609→1756, 4 missing files added.

**Cross-doc inconsistencies resolved:**
| Topic | Before | After |
|-------|--------|-------|
| MCP tools | 7/8/9 (varied) | 12 (all docs) |
| Test files | 28 | 49 |
| Brain fields | 26 | 22 |
| Response pools | 3 separate | 1 unified ThoughtPool |
| TTS engine | pyttsx3 only | edge_tts primary + pyttsx3 fallback |
| Config format | flat JSON | nested (llm/pet/tts/consent) |

**Files undocumented before, now documented:**
- `src/animator.py`, `src/response_pool.py`, `src/thought_log_dialog.py`, `src/system_dialogs.json`

### Phase 46 — EmotionProfile & Eye Modifier Architecture (2026-06-13)

**What was done:**
- **`src/animator.py`** — Replaced all procedural `if/elif` chains with a declarative `EmotionProfile` dataclass and `EMOTION_PROFILES` registry. All 9 emotion profiles defined with "Juice" enhancements:
  - **MIRTH**: micro-tilt rotation (`2.0 * sin(t/200)`), sclera squish 0.8x
  - **ANGER**: jitter transform, red comet trail particles (`drift_x=-0.5`), angry brows (20°), squint (sclera 0.5x)
  - **FEAR**: stretched (1.3, 0.7), tiny pupils (0.3x), wide sclera (1.2x)
  - **DISGUST**: squished (0.8, 1.0), hue shift -30°, eye roll (pupil_offset_x=2.0)
  - **PATHOS**: flattened (1.0, 0.9), grayscale, opacity pulsing 0.6→0.9, sad brows (-15°)
  - **DEVOTION**: heart pupils, pink floating animation, pink hearts particles
  - **HEROISM**: golden aura pulsing 80→20→80→20, gold pupils (full sclera), easing transform
  - **WONDER**: elastic pop 1.5→1.0, 1-frame glitch (opacity=0 @ t=400ms), white screen flash
  - **TRANQUILITY**: slow breathe, zen squint (sclera 0.1x), 80% alpha
- **`src/pet_renderer.py`** — Added emotion opacity pipeline (`painter.setOpacity`) for pulsing/glitch effects. Eye modifier pipeline: sclera scale, pupil scale/shape/color/offset, and brow angle rendering with proper cursor-tracking integration.
- **`ParticleSystem.emit()`** — Added `drift_x` parameter for comet trail effects (ANGER).
- **Legacy dicts** (`_SINGLE_FIRE_DECAY`, `_EMOTION_OVERRIDE_COLOR`, `_PARTICLE_EMIT`) — Preserved as derived properties from the registry for full backward compatibility.

**Files changed:**
- `src/animator.py` — 156 lines added (EmotionProfile, EMOTION_PROFILES registry, helper functions, refactored EmotionAnimator)
- `src/pet_renderer.py` — 45 lines added (opacity + eye modifier pipelines)

**Test count:** All 68 animator tests + 5 renderer tests pass with zero modifications to test files.

---

## How To Update This File

After each completed task, update:
1. The task row in "What Is Built" (status → ✅, fill commit hash + notes)
2. "What To Do Next" section
All currently planned development phases through Phase 56 are complete. 
Potential future work considerations:
- EventStreamWorker 401/403 handling (currently declined)
- Constants.py domain split (currently skipped)  
- Sensitive data redaction filter (currently skipped)
See "Recommendations For Future Sessions" section for ongoing best practices.

3. Add any new issues/pitfalls discovered
4. Add recommendations if a non-obvious decision was made

---

## Agent Instructions

**CLAUDE.md and GEMINI.md have been replaced by `AGENTS.md`.** All agent instructions now live in that single file. Update it when adding new pitfalls, changing the file map, or modifying workflows.
### Phase 47 � Window Perching & The Super Jump ? COMPLETE

**Commit:** e1617ff

**What was built:**
- **DWM-Accurate Geometry:** ctive_window.py uses DwmGetWindowAttribute(DWMWA_EXTENDED_FRAME_BOUNDS) to get true visual pixels without drop-shadow bounds, skipping maximized/full-screen apps.
- **Sticky Drag & Perching:** pet_window.py tracks _last_window_rect. When the active window moves, the pet seamlessly rides the title bar (dx/dy applied to _pet_x and _pet_y).
- **Seeking & The Drop:** Pet wanders to the edge of the screen using PERIMETER if outside horizontal bounds. Drops to the active window title bar if aligned horizontally but above it.
- **The Super Jump:** Pet performs an arcing kinematic leap (y = -sqrt(2 * g * d)) from the taskbar up to the active window title bar.
- **Animation Polish:** Added 	akeoff_elapsed_ms (200ms stretch) and 	itle_land_elapsed_ms (200ms squash) to RenderContext directly evaluated in pet_renderer.py, bypassing the EmotionProfile to keep them purely physical.

**Key Decisions:**
- DWM allows frame precision, solving the floating issue on Windows 10/11.
- Gravity logic works by setting the precise _fall_velocity needed to reach exactly the window's top edge at the apex.
- Maximize check (WS_MAXIMIZE) ensures the pet doesn't get trapped offscreen on maximized game windows.

---

### Phase 48 - Opencode SSE and Config Stability (Hotfixes)

**Commit:** 5c09708

**What was fixed:**
- **Opencode 404 Fix:** Updated src/mcp_server.py to accept requests at / in addition to /sse and /message to resolve 404 errors during opencode server-sent event connections.
- **Config Migration Crashes:** Resolved missing imports and config mismatches during startup by porting OPENCODE_SERVER_URL over to the new unified config loader.
- **UnboundLocalError:** Fixed a scope issue where PetState was imported locally inside an if block, causing an UnboundLocalError when attempting to evaluate the condition.

**Key Decisions:**
- Ensuring robust BaseHTTPRequestHandler paths (/ and explicit paths) resolves tooling misconfigurations from client side without complex proxies.

---

### Phase 49 - Architectural Improvements & Bug Fixes

**Branch:** `task-49-architectural-improvements`

**What was done:**
Comprehensive architecture review and critical bug fixes across the codebase.

**Critical Bugs Fixed:**
| Bug | Status | Fix Applied |
|-----|--------|-------------|
| Hardcoded PROJECT_ROOT | ✅ Fixed | `Path(__file__).parent.parent.resolve()` in mcp_server.py:16 |
| ClickThrough hysteresis | ✅ Verified | Logic is correct: transparent expands, opaque shrinks |
| Refill worker race condition | ✅ Fixed | Lock added at pet_window.py:1976 |
| pool_refilled signal | ✅ Fixed | Connected at pet_window.py:224 |
| OpencodeWorker session leak | ✅ Fixed | DELETE in abort() method (lines 44-56) |
| Drift-free timers | ✅ Fixed | Monotonic time tracking in _master_tick() |

**Files Changed:**
- `src/pet_window.py` — Refill lock, monotonic time tracking
- `src/response_pool.py` — Added `type` field to tagged items
- `src/mcp_server.py` — PROJECT_ROOT fix (already applied)
- `src/click_through.py` — Verified correct logic

**New File Created:**
- `src/events.py` — EventBus with 27 event types (currently unused)

**Bugs Remaining (to be fixed):**
- TTS temp file leak
- Double window title call
- TypingBuffer signal spam (needs debounce)
- `_dispatch_multiplexed` session reuse
- Firestore write per brain field (needs batching)

**Test Results:** All 588 tests pass (including new typing_buffer tests)

---

### Phase 49.1 — Consent Matrix Refinement (2026-06-14)

**Branch:** `task-49-consent-refinement`

**What was done:**
- **Renamed consent keys:**
  - `allow_system_notifications` → `allow_audio_disruptions`
  - `allow_clipboard_reading` → `allow_clipboard_hijacking`
  - `allow_screenshot_capture` → `allow_window_management`
- **Removed consent gating for file operations:** `list_directory`, `read_file`, `search_codebase`, `get_memory`, `get_diary` are now always-allowed tools (no consent required)
- **Renamed tool:** `capture_screenshot` → `capture_blackmail_evidence`
- **Tool count:** 12 → 11 (after tool rename)
- **Consent matrix:** Simplified to 3 tiers (Tier 1: intrusive_animations, Tier 2: audio_disruptions/browser_redirection, Tier 3: clipboard_hijacking/mouse_interference/window_management/keyboard_injection)

**Files changed:**
- `src/config.py` — Updated consent keys and flat/nested mappings
- `src/mcp_server.py` — Updated tool names, consent map, removed gating for read-only tools
- `src/pet_window.py` — Updated saved_consent keys
- `src/settings_dialog.py` — Updated checkbox labels and wiring
- `tests/test_mcp_server.py` — Updated tool count assertions, consent tests
- `tests/test_settings_dialog.py` — Updated consent key assertions

**Test Results:** All 68 MCP/settings/config tests pass

---

### Phase 50 — Config Consolidation (2026-06-15)

**Summary:** Consolidated all model, API, and placeholder settings scattered across the source tree into `src/config.py`, relocated API keys to `.env`, cleaned hardcoded URLs, and added config sections for MCP, behavior, logging, and storage.

**Commits (on master):**
- `f9008e2` feat: wire python-dotenv into config, add _apply_env_overrides for env var overrides
- `d96a986` feat: add config sections for mcp, behavior, logging, storage; wire consumers
- `ddb064c` fix: replace hardcoded 127.0.0.1:4096 URLs with DEFAULT_SERVER_URL constant

**Task breakdown:**

| Task | Description | Commit |
|------|-------------|--------|
| Task 1 | `.env.example`, `.gitignore` (add `.env`), `requirements.txt` (+python-dotenv) | `f9008e2` plus earlier |
| Task 2 | Strip real API keys from `data/daemon_config.json` | earlier |
| Task 3 | Wire `python-dotenv` into `config.py`, add `_apply_env_overrides()` | `f9008e2` |
| Tasks 4-7 | Add config sections: firebase/credentials_path, mcp/host+port, behavior (40+ tunables), logging (level/dir/retention), storage (7 file paths) | `d96a986` |
| Task 9 | Replace all hardcoded `"http://127.0.0.1:4096"` fallbacks with `DEFAULT_SERVER_URL` from config | `ddb064c` |
| Task 10 | Update test files to use config constant (test input URLs left explicit) | `ddb064c` |
| Task 11 | Update dev memory (this entry) | — |

**Files changed:**
- `src/config.py` — New sections: firebase.credentials_path, mcp, behavior (41 keys), logging, storage (7 keys); new `DEFAULT_SERVER_URL` convenience constant; `_apply_env_overrides()` for env var overrides
- `src/firebase_crud.py` — Read `credentials_path` from config instead of hardcoded constant
- `src/mcp_server.py` — Read host/port from config mcp section; extract consent from nested config dict
- `src/event_worker.py` — Default URL uses `DEFAULT_SERVER_URL`
- `src/opencode_serve_manager.py` — `_DEFAULT_URL` uses `DEFAULT_SERVER_URL`
- `src/opencode_worker.py` (2 occurrences), `src/pet_window.py` (1), `daemon.py` (1), `scripts/test_connections.py` (1) — Fallback URLs use `DEFAULT_SERVER_URL`
- `daemon.py` — Pass `log_dir` from config logging section to `setup_logging`

**Key decisions:**
- `DEFAULT_SERVER_URL` exported from `config.py` as a single source of truth for `http://127.0.0.1:4096`
- Test files keep explicit URL strings for test input data (not fallback defaults)
- `_apply_env_overrides()` runs after JSON file merge so `.env`/env vars always win
- `load_config()` called once at startup, returns nested dict; consumers read their section
- MCP and logging consumers already supported config dicts — only needed wiring updates

**Test Results:** All 134 config/FSM/MCP/auth/CRUD/worker tests pass.

### Phase 50.5 — Codebase Cleanup ✅

**Date:** 2026-06-15
**Latest commit:** `6e37e2c`
**Commits:** `87bb405`, `6e37e2c`

**What was cleaned:**

| # | Item | Type | Details |
|---|------|------|---------|
| 1 | `.gitignore` | Edit | Deduplicated `crash_dump.log` (was listed twice); added `.hermes/` pattern |
| 2 | `crash_dump.log` | Delete | 0-byte empty file at repo root |
| 3 | `docs/superpowers/` | Delete (9 files) | Stale Phase 36-37 design docs superseded by `.hermes/plans/` system |
| 4 | `.git/.COMMIT_EDITMSG.swp` | Delete | Vim swap artifact |
| 5 | 5 x `__pycache__/` | Delete | Bytecode caches at root, src/, src/utils/, tests/, scripts/ |

**Verification:** `git status` clean, 603 tests pass (unchanged).

---

### Phase 51 — High-Priority Bug Fixes + Observability (2026-06-15)

**Summary:** Fixed 3 high-priority bugs (TTS temp file leak, TypingBuffer signal spam, stale opencode session reuse), investigated 2 false alarms (Firestore per-field writes, double window title call), added atexit emergency flush, JSON parse diagnostics, MCP health/metrcis endpoints, and boot timing instrumentation.

**Commits (on master, 4 total):**
- `3f32d9d` fix: TTS temp file cleanup and TypingBuffer signal debounce
- `bc029b2` fix: clear stale _opencode_session_id on worker error
- `1cb2845` fix: atexit emergency flush + JSON parse diagnostics
- `bcdfb33` feat: add MCP server health endpoint + metrics + boot timing instrumentation

**Task breakdown:**

| Task | Description | Status | Notes |
|------|-------------|--------|-------|
| A1 | Firestore write batching | ✅ False alarm | `firebase_crud.set()` is single-doc with merge=True; `update_brain()` writes all fields per response; `batch_update_brain()`/`flush_batch()` exist but are dead code |
| A2 | TTS temp file leak | ✅ Fixed | Track all temp files in `_process_utterance`, clean in `finally` block (was leaking edge-tts MP3 + pyttsx3 WAV fallback) |
| A3 | TypingBuffer signal spam | ✅ Fixed | Remove redundant `text_updated.emit()` from `_on_press`; rely on existing 50ms debounce timer. Burst keystrokes coalesce into one emission |
| A4 | Stale opencode session reuse | ✅ Fixed | Clear `_opencode_session_id = None` in `_on_opencode_error()` so next worker creates fresh session |
| A5 | Double window title call | ✅ False alarm | `_evaluate_emotion` already caches `get_active_window_title()` once at line 555 |
| B1 | Memory sync race (atexit) | ✅ Fixed | Added `_emergency_flush()` atexit handler for last-resort WriteCoalescer/Memory/History save on abnormal exit |
| B2 | JSON parse hardening | ✅ Fixed | Added line/col/context diagnostic logging on JSON decode error + "all strategies failed" fallback warning |
| B3 | MCP server health check | ✅ Fixed | Added `/health` GET endpoint to MCPHandler; `_check_mcp_health()` TCP-checks port 4097, wired into `_on_health_check` |
| B4 | Observability boot + /metrics | ✅ Fixed | Added `/metrics` endpoint returning pid, uptime, thread count (psutil optional); boot timing marks and summary log in daemon.py |
| B5 | Consent matrix tier audit | ⏭️ Skipped | Code/docs already correct from Phase 48 |
|| B6 | PetController extraction pilot | ✅ Completed (Phase 52) | Extracted to `src/behavior_controller.py` with 40 tests |

**Files changed:**
- `src/tts_worker.py` — Temp file tracking + finally cleanup
- `src/typing_buffer.py` — Removed redundant emit calls
- `tests/test_typing_buffer.py` — Updated for debounced signal behavior
- `src/pet_window.py` — `_check_mcp_health()` method + `_on_opencode_error` session invalidation + health check wiring
- `src/opencode_worker.py` — JSON parse diagnostic logging with line/col/context
- `src/mcp_server.py` — `/health` + `/metrics` GET endpoints; `_BOOT_TIME` module-level tracking
- `daemon.py` — `_emergency_flush()` atexit handler; boot timing marks + summary log

**Test Results:** 241 tests pass across 8 test files covering all changed modules.

---

### Phase 52 — PetController Extraction (2026-06-15)

**Commits (on master, 4 total):**
- `b81365f` feat: create BehaviorController with autonomous behavior logic
- `9515e69` refactor: wire BehaviorController into PetWindow
- `6fc8193` refactor: wire EventBus subscribers for autonomous trigger dispatch
- `50893ba` refactor: remove duplicated behavior logic from PetWindow
- `a05c513` fix: move EventBus init before BehaviorController, delete stale test files

**What was built:**

Extracted the autonomous behavior system from PetWindow's ~2175-line god object into a dedicated `BehaviorController` class.

| Task | Description | Status | Files |
|------|-------------|--------|-------|
| 1 | Create `src/behavior_controller.py` — Timer accumulation (chat/joke/emotion/idle/boredom), engagement tracking (consecutive silent/engaged, adaptive backoff), boredom backoff (exponential, context-sensitive), context stability (window/APM/typing/screen), emotion evaluation (OS context → Emotion), FSM trigger dispatch via EventBus | ✅ | Created: `behavior_controller.py`, `test_behavior_controller.py` (40 tests) |
| 2 | Wire `BehaviorController` into PetWindow — `_behavior.tick()` called from `_master_tick()`, delegates all timer/engagement/emotion logic | ✅ | +124/-258 lines across `pet_window.py`, `test_master_tick.py`, `test_behavior_integration.py` |
| 3 | EventBus subscribers — `_on_autonomous_trigger` dispatches chat/joke/boredom triggers via EventBus, replacing direct `_trigger_*()` method calls | ✅ | +77 lines in `pet_window.py`, event subscriber test in `test_behavior_integration.py` |
| 4 | Remove duplicated logic — 8 dead methods removed from PetWindow: `_trigger_chat`, `_trigger_joke`, `_trigger_boredom_fsm`, `_evaluate_emotion`, `_calculate_joke_modifier`, `_is_context_stable`, `_has_significant_delta`, `_get_context_signature`. Removed stale fields (`_emotion_timer_sec`, `_window_switch_count`, `_last_evaluated_window`). Deleted 4 stale test files. | ✅ | -130 lines in `pet_window.py`, -73 lines test code |
| 5 | Documentation update — dev memory, commit hashes, test counts | ✅ | `project-dev-memory.md` |

**Key design decisions:**
- Pure business logic class — NO Qt imports, zero Qt dependency. Communicates with PetWindow via EventBus pub/sub.
- EventBus initialized before BehaviorController (fixes AttributeError in tests that hit real `__init__`)
- `_evaluate_emotion()` is a pure function based on current state — no side effects, easy to test
- `tick()` at 1s interval handles: emotion evaluation (every 5s), timer accumulation, engagement tracking, backoff, boredom trigger selection
- BehaviorController owns all internal field tracking (`_chat_timer_sec`, `_joke_timer_sec`, etc.) — PetWindow no longer touches these

**Files changed:**
- **Created:** `src/behavior_controller.py` (495 lines), `tests/test_behavior_controller.py` (414 lines, 40 tests)
- **Modified:** `src/pet_window.py` (-130 lines, EventBus wiring, EventBus init ordering)
- **Deleted:** `tests/test_delta_detection.py`, `tests/test_joke_modifier.py`, `tests/test_trigger_chat.py`, `tests/test_trigger_joke.py`
- **Rewritten:** `tests/test_master_tick.py`, `tests/test_behavior_integration.py`, `tests/test_sleep_timers.py`

**Bugs fixed during Phase 52:**
| Bug | Cause | Fix |
|-----|-------|------|
| EventBus use-before-init in `__init__` | BehaviorController constructed before `self._events` | Moved `get_event_bus()` to line 229 (before BehaviorController ctor) |
| TRANQUILITY test failure | Patch target `src.active_window` doesn't affect module-level import in `behavior_controller` | Changed patch target to `src.behavior_controller.get_active_window_title` |

**Test results:** 246 pass across 13 targeted test files. 0 failures.

---

### Phase 53 — Performance Optimizations (2026-06-16)

**Commit:** `b8cf845`

**What was built:**

| Fix | File | Status | Notes |
|-----|------|--------|-------|
| Particle O(n) rebuild | `src/animator.py` | ✅ Fixed | In-place compaction using write index instead of list rebuild |
| ThoughtPool O(n) removal | `src/response_pool.py` | ✅ Fixed | Single-pass O(n) draw with reverse-order stale item removal |
| APMWorker unbounded deque | `src/apm_worker.py` | ✅ Fixed | Added `maxlen=600` safety cap |
| EventBus emission | `src/pet_window.py` | ✅ Fixed | Added events for APM threshold, shutdown, sleep, hotkey, boot, health |
| Duplicate TOKEN_REFRESHED | `src/events.py` | ✅ Fixed | Removed duplicate from Auth Events section |

**Key decisions:**
- Particle compaction uses slice deletion after write index
- ThoughtPool draws best priority item, then removes all stale in reverse order
- APM deque capped at 600 (10 events/sec * 60 seconds * 10 safety margin)

**Test results:** 87/87 tests pass in affected modules (animator: 54, response_pool: 6, events: 27).

---

### Phase 54 — API Call Reduction (2026-06-16)

**Goal:** Reduce opencode/LLM API calls by ~75% without affecting functionality.

**Files changed:**
| File | Action | Description |
|------|--------|-------------|
| `src/constants.py` | Modify | `THOUGHT_POOL_SIZE` 20→40, `THOUGHT_POOL_THRESHOLD` 5→15 |
| `src/response_manager.py` | Modify | Removed periodic refill timer (10-min auto-refill), kept demand-based refill |
| `src/opencode_worker.py` | Modify | Deprecated `_send_two_stage` (no longer called) |
| `src/pet_window.py` | Modify | Single-stage refill prompt; typing debounce tries pool first; conditional shutdown summary (skip if <10 items) |
| `src/behavior_controller.py` | Modify | 15s debounce between ANY autonomous triggers; `_last_autonomous_fire_time` tracking |
| `src/memory_manager.py` | Modify | Content-hash guard on `sync_from_local`; `push_pending_diaries` uses Firestore batch writes |
| `tests/test_memory_manager.py` | Modify | Updated tests for batch and content-hash changes |

**Key optimizations (predicted impact):**

| Change | Impact |
|--------|--------|
| Remove periodic refill timer (demand-based only) | Eliminates ~12 LLM calls/hr |
| Single-stage refill (was 2-stage) | Cuts refill LLM calls by 50% |
| Pool 20→40 items, threshold 5→15 | ~60% fewer refill events |
| Pool-first on typing debounce | Route through pool before API |
| 15s debounce between autonomous triggers | Prevents rapid-fire P2+P3+P4 |
| Conditional shutdown summary | Skips API call for short sessions |
| Content-hash guard on Firestore sync | Skips writes when nothing changed |
| Batch diary pushes | 1 Firestore API call instead of N |

**Estimated reduction:** ~200-350 LLM calls/hr → ~40-80/hr (~75%)

**Test results:** 630 passed, 1 skipped (full regression).

---

### Phase 55 — Remaining Plans Implementation (2026-06-16)

**Goal:** Implement 3 remaining plans: Codebase Cleanup, Mouth Shapes, High-Priority Bug Fixes.

**Plans status:**

| Plan | Status | Notes |
|------|--------|-------|
| Codebase Cleanup | ✅ Done | Removed crash_dump.log (0B), cleaned all `__pycache__`/`.pyc` |
| Mouth Shapes | ✅ Done | `mouth_shape` field on EmotionProfile, 9 Navarasa mappings, `get_mouth_modifier()`, `_draw_mouth()` with 10 shapes, 4 integration tests |
| High-Priority Bug Fixes | ✅ Partial | See below |

**Phase A — Critical Bug Fixes (all already fixed in prior phases):**

| Bug | Status | Notes |
|-----|--------|-------|
| A1: Firestore per-field writes | ✅ False alarm | `FirebaseCRUD.set()` uses `merge=True` (1 doc write), `sync_from_local` calls once |
| A2: TTS temp file leak | ✅ Already fixed | `_process_utterance` has `temp_files` tracking + `finally` cleanup (Phase 51) |
| A3: TypingBuffer signal spam | ✅ Already fixed | 50ms `_debounce_timer` coalesces keystrokes (Phase 51) |
| A4: Stale opencode session reuse | ✅ Already fixed | `_on_opencode_error()` clears `_opencode_session_id` (Phase 51) |
| A5: Double window title call | ✅ Already fixed | `_evaluate_emotion` cached variable (extracted to behavior_controller.py Phase 52) |

**Phase B — Architectural Debt:**

| Task | Status | Notes |
|------|--------|-------|
| B1: Memory RLock + atexit | ✅ Already fixed | `atexit.register(_emergency_flush)` exists at daemon.py:243 |
| B2: JSON parse diagnostics | ✅ Already fixed | `lineno` in parse error logging (Phase 51) |
| B3: MCP health check | ✅ Already fixed | `/health` endpoint at mcp_server.py port 4097 (Phase 51) |
| B4: Observability wiring | ✅ Fixed | Added `setup_observability()` call in `daemon.py` after config load |
| B5: Consent matrix cleanup | ✅ Already fixed | Exists as docstring in constants.py |
| B6: PetController extraction | ⏭️ Skipped | High-risk refactor (~2000 lines), behavior already extracted in Phase 52. Deferred. |

**Phase C — Medium-Priority Fixes:**

| Fix | Status | Notes |
|-----|--------|-------|
| C1: screen_reader UIA COM per-thread | ✅ Fixed | Replaced global `_UIA_AUTOMATION`/`_UIA_INITIALIZED` with `threading.local()` |
| C2: Particle O(n) rebuild | ✅ Already fixed | Phase 53 |
| C3: ThoughtPool per-type indices | ✅ Already fixed | Phase 53 |
| C4: ContextManager prompt cache | ✅ Fixed | Added snapshot-based cache key to `build_user_trigger`/`build_autonomous_trigger`, ~2μs hit vs 5μs rebuild |
| C5: APMWorker unbounded deque | ✅ Already fixed | Phase 53 |
| C6: EventStreamWorker 401/403 | ⏭️ Declined | Planned module, not worth implementing yet |
| C7: DiaryStore case-insensitive dup | ✅ Fixed | `calculate_content_hash` uses `NFKC + casefold + strip` |
| C8: GroundContactResolver extraction | ✅ Fixed | Created `src/physics.py` with `GroundContactResolver` class, `ContactResult` namedtuple |
| C9: constants.py domain split | ⏭️ Skipped | Large refactor, YAGNI for current scope |

**Files changed (Phase 55):**

| File | Action | Description |
|------|--------|-------------|
| `.gitignore` | Verify | Already had `.hermes/` + `crash_dump.log` |
| (cleanup) | Delete | Removed `crash_dump.log` (0B), all `__pycache__`/`.pyc` |
| `src/animator.py` | Modify | `mouth_shape` field on `EmotionProfile`, set on all 9 profiles, `get_mouth_modifier()` method |
| `src/pet_renderer.py` | Modify | `_draw_mouth()` with 10 shapes (smile, frown, open, pursed, ooo, wry, neutral, smile_teeth, kiss, tremble) |
| `tests/test_animator.py` | Add | `TestMouthShapes` class with 3 tests |
| `tests/test_pet_renderer.py` | Rewrite | Added `test_mouth_shape_smoke` + 4 shape-specific tests |
| `daemon.py` | Modify | Added `setup_observability()` after config load |
| `src/screen_reader.py` | Rewrite | `threading.local()` for UIA COM instance, per-thread initialization |
| `src/context_manager.py` | Modify | Prompt cache on `build_user_trigger`/`build_autonomous_trigger` |
| `tests/test_context_manager.py` | Modify | Added `_cache_key`/`_cached_prompt` init for bypass tests |
| `src/diary_store.py` | Modify | `calculate_content_hash` uses `NFKC + casefold + strip` |
| `src/physics.py` | Create | `GroundContactResolver` class + `ContactResult` NamedTuple |

**Test results:** 637 passed, 1 skipped (full regression).

---

### Phase 56 — Production Logging & Observability (2026-06-16)

**Goal:** Replace ad-hoc logging with production-grade infrastructure — structlog, correlation IDs, lazy formatting, Prometheus metrics, MCP observability tools.

**Files created:**
| File | Description |
|------|-------------|
| `src/log_context.py` | CorrelationIdDefault formatter, get/set/reset_correlation_id() |

**Files modified:**
| File | Description |
|------|-------------|
| `requirements.txt` | Added `structlog>=24.1.0`, `prometheus-client>=0.19.0` |
| `src/logging_setup.py` | RotatingFileHandler (10MiB, 5 backups), structlog JSON processor chain, configurable log dir/level, CorrelationIdDefault formatter |
| `daemon.py` | Wired structlog JSON output into boot sequence with json_output config toggle |
| `src/event_worker.py` | 3 f-string log calls → lazy `%s` formatting |
| `src/mcp_server.py` | 2 f-string → lazy `%s`; MCP tool call metrics; `set_log_level` MCP tool; upgraded `/metrics` to Prometheus `generate_latest()` |
| `src/opencode_serve_manager.py` | 6 f-string → lazy `%s` |
| `src/memory_manager.py` | 14 f-string → lazy `%s`; wired `update_memory_facts` metric |
| `src/pet_window.py` | 6 f-string → lazy `%s`; wired `record_fsm_transition`, `update_apm` metrics; set_correlation_id on user input |
| `src/behavior_controller.py` | 4 f-string → lazy `%s`; wired `record_autonomous_trigger` metrics; set_correlation_id on triggers |
| `src/logging_setup.py` | CorrelationIdDefault formatter, structlog JSON processor + `add_correlation_id` |
| `src/observability.py` | (existing) Init already calls `init_metrics()` — helpers wired into 5 real code paths |
| `tests/test_log_context.py` | Created — 5 tests: set_and_get, reset, unique_ids, formatter_default, formatter_injected |

**Tasks completed (from plan `.hermes/plans/2026-06-16_121500-production-logging.md`):**

| # | Task | Commit | Status |
|---|------|--------|--------|
| 1 | Add structlog + prometheus-client deps | `58819d7` | ✅ |
| 2 | RotatingFileHandler + configurable rotation | `1c3f9a2` | ✅ |
| 3 | Wire structlog JSON into boot sequence | `1679e8f` | ✅ |
| 4 | Convert 29 f-string log calls to lazy `%s` | `3cc1eec` | ✅ |
| 5 | Add correlation IDs via `log_context.py` | `e2811b4` | ✅ |
| 6 | Wire Prometheus metrics into 5 code paths | `3dc79e7` | ✅ |
| 7 | `set_log_level` MCP tool (DEBUG/INFO/WARNING/ERROR/CRITICAL) | `9878c9b` | ✅ |
| 8 | Upgrade `/metrics` to Prometheus `generate_latest()` + JSON fallback | `9878c9b` | ✅ |
| 9 | Sensitive data redaction filter | ❌ Skipped — YAGNI for current scope, low-value until real prod deployment |
| 10 | Update dev memory + docs | (this entry) | ✅ |

**Architecture wins:**
- **Correlation IDs:** Every log line carries `[cid=<uuid>]` — set on user input or autonomous trigger for end-to-end tracing
- **Lazy formatting:** All 29 `logger.info(f"...")` → `logger.info("...%s", val)` — prevents unnecessary string building when log level suppresses the line
- **MCP tools:** `set_log_level` allows remote debug log toggling without restart; `tools/list` returns 13 tools
- **Prometheus metrics:** FSM transitions, APM, MCP tool calls (latency + success), memory facts, autonomous triggers — exposed at `GET /metrics` in Prometheus text format
- **Structlog JSON:** Opt-in via `json_output: true` in config; produces NDJSON for ELK/Loki ingestion

**Test results:** 645 passed (full regression).


### Phase 57 — Plugin Architecture (2026-06-20)

**Goal:** Dynamic emotion/behavior loading via filesystem plugins — foundational infrastructure for extensibility without modifying core code.

**Design:**
- **Plugin protocol:** Each `.py` file in `plugins/` exports a `register(registry)` function called at boot
- **PluginRegistry** — central registry for plugin-contributed components (emotion profiles, emotion rules, behavior triggers)
- **PluginManager** — filesystem discovery and loading with per-module validation
- **Priority system:** Plugin rules run at configurable priority (lower = higher precedence), built-in rules run at priority 100
- **Cooldown:** Behavior triggers have per-trigger cooldown to prevent spam

**Files created:**

| File | Description |
|------|-------------|
| `src/plugin_registry.py` | PluginRegistry — registration + query API for emotion profiles, emotion rules, behavior triggers |
| `src/plugin_manager.py` | PluginManager — filesystem discovery (plugins/*.py), import/validation, per-plugin lifecycle |
| `plugins/__init__.py` | Plugin directory marker |
| `plugins/emotion_nostalgia.py` | **Sample plugin** — overrides PATHOS profile with sepia tone, adds emotion rule for legacy windows, adds behavior trigger for archive browsing |
| `tests/test_plugin_system.py` | 17 tests covering registry, plugin loading, cooldown, error handling, integration |

**Files modified:**

| File | Description |
|------|-------------|
| `src/animator.py` | Added `apply_plugin_profiles()` — merges plugin-registered profiles into `EMOTION_PROFILES` dict |
| `src/behavior_controller.py` | Added `plugin_registry` parameter; `_evaluate_plugin_emotion()` runs plugin rules before built-in chain |
| `src/pet_window.py` | Passes `plugin_registry` through to `BehaviorController` |
| `daemon.py` | Creates `PluginRegistry`, `PluginManager`, discovers and loads plugins, applies profiles at boot |

**Boot sequence addition:**
```
generate_codebase_map() - after
  → PluginRegistry()
  → PluginManager.discover()
  → PluginManager.load_all()
  → apply_plugin_profiles()
  → (continues to opencode serve check)
```

**Plugin rules API:**
```python
# Emotion profile override
registry.register_emotion_profile(Emotion.PATHOS, profile, plugin_name="my_plugin")

# Emotion evaluation rule (context dict → Emotion or None)
registry.register_emotion_rule("my_rule", fn, priority=50)

# Behavior trigger (context dict → dict or None)
registry.register_behavior_trigger("my_trigger", fn, cooldown_sec=120)
```

**Known limitations:**
- Emotion enum is fixed — plugins cannot add new enum values, only override profiles for existing ones
- No plugin hot-reload (plugins loaded once at boot)
- No plugin CLI management yet (`hermes plugin install/enable/disable`)
- Sample plugin `emotion_nostalgia.py` is purely demonstrational — override/remove in production

**Test results:** 17 new tests pass (all plugin system tests). Full existing test suite unaffected (animator, behavior controller all green).


### Phase 58 — Persistent LLM Sessions (2026-06-20)

**Goal:** Resume opencode conversation sessions across daemon restarts — preserve session ID, conversation history (last 30 turns), and inject history context into the first message of a new session when the old one can't be resumed.

**New files:**
| File | Purpose |
|------|---------|
| `src/llm_session_persistence.py` | `ChatTurn`, `LLMSessionState` dataclasses + `save_session()`, `load_session()`, `clear_session()` |
| `tests/test_llm_session_persistence.py` | 25 tests covering dataclass, save/load/clear, corrupt data, history trimming, worker integration |

**Modified files:**
| File | Change |
|------|--------|
| `src/opencode_worker.py` | Added `session_state` param, `session_turn_completed` signal, `_emit_turn_completed()` — prepends `history_context` to prompt on resume |
| `src/pet_window.py` | Loads `LLMSessionState` on init, passes to workers, connects `session_turn_completed` → `_on_session_turn_completed` (saves after every turn), saves on shutdown in `_finalize_quit` |
| `src/llm_session_persistence.py` | Added `DEFAULT_SERVER_URL` import, fixed `server_url` fallback for empty-string config |
| `src/opencode_worker.py` | (2nd fix) Changed `.get("server_url", DEFAULT)` → `.get("server_url") or DEFAULT` for both abort cleanup and `_post_message` paths |
| `src/pet_window.py` | (2nd fix) Same pattern fix in `_force_quit_app` opencode session cleanup |

**Data flow:**
```
Boot: load_session() → reads data/llm_session.json
  ├─ session_id set → reuse as _opencode_session_id (try to resume)
  └─ history present → history_context injected into first message

Every turn: worker emits session_turn_completed(session_state, prompt, response)
  → main thread calls save_session() → atomic write to data/llm_session.json

Shutdown: _finalize_quit() → save_session() → disk
```

**Session reuse logic:**
- Saved `session_id` is passed to `OpendcodeWorker` on construction
- If the server-side session is still alive (serve process hasn't restarted), it reconnects seamlessly
- If the session is gone (404/500 on message send), error handler clears `_opencode_session_id`, and the next worker creates a fresh session — but the `history_context` from the previous session is still injected into the first message of the new session
- `history_context` format:
  ```
  [Previous conversation resumed after restart]
  Conversation summary: <summary>
  
  User: <last few messages>
  Assistant: <last few messages>
  
  [Current message]
  ```

**Key design decisions:**
- History capped at 30 turns (configurable via `MAX_HISTORY_TURNS`) to keep prompt sizes manageable
- Individual turn content truncated to 2000 chars (user) / 3000 chars (assistant) on save, 500 chars in `history_context` for display
- Atomic write pattern (`.tmp` + rename) prevents corrupt files
- No session state saved for refill workers or summary workers — only user-facing conversations persist

**Known limitations:**
- Server-side sessions are lost when `opencode serve` restarts (server has no persistence)
- Session state is only saved on explicit turns (user → assistant), not on autonomous refills
- No session pruning / archival yet — old sessions accumulate in `data/llm_session.json`

**Fixes applied:**
- `server_url` empty-string bug (2026-06-20): `daemon_config.json` had `"server_url": ""`; all 4 code paths using `.get("server_url", DEFAULT)` returned `""` because the key existed. Changed to `.get("server_url") or DEFAULT_SERVER_URL` in `llm_session_persistence.py`, `opencode_worker.py` (2 locations), and `pet_window.py`.

**Test results:** 56 new tests pass (25 persistence + 31 opencode_worker). All existing tests unaffected.

---

### Phase 59 — Boot Config Validation & Strict Config Validation (2026-06-20)
**Branch:** `master`

**What was built:**
- `MissingConfigurationError` class and `validate_config(cfg)` function in `src/config.py` as a single source of truth for config constraints.
- `validate_config` checks for the existence of mandatory LLM and Firebase fields, explicitly verifies that `firebase.credentials_path` points to a valid file, and verifies write access to the `data/` directory.
- Boot sequence interception in `daemon.py` `main()`: catches `MissingConfigurationError`, pops the `SettingsDialog` immediately, allowing the user to provide API keys before continuing. Exits on cancel or subsequent failure.
- Redundant warning logs around `firebase_key` and `opencode_api_key` were removed.
- A test environment leakage in `tests/test_config.py` was fixed by patching `os.environ` and `_CONFIG_PATH` to `tmp_path`.
- Implemented **Strict Configuration Validation**: Removed DEFAULT_CONFIG entirely from src/config.py so that the file system (data/daemon_config.json) is the single source of truth.
- Created ssets/daemon_config_template.json to act as a fallback. load_config will automatically copy this template to the data directory if the user config does not exist.
- Expanded alidate_config to explicitly enforce the existence of all 10 top-level configuration sections.
- Updated AGENTS.md with a critical rule warning future agents that the app will crash if new config keys are added without explicitly placing them in daemon_config.json.

**Files changed:**
- `src/config.py`
- `tests/test_config.py`
- `daemon.py`

**Test results:** Config validation tests pass. Added new unit tests for strict validation logic. Removed reliance on hardcoded DEFAULT_CONFIG across the test suite. All tests passing.

---

**Done — End of Project Dev Memory**

---

### Test Suite Optimization (2026-06-20)

**What was built:**

1. **Shared conftest.py** (`tests/conftest.py`) — centralized fixture definitions:
   - `qapp` (session-scoped QApplication instance) — created once, shared by all Qt tests
   - `app` (alias for `qapp`) — function-scoped for readability
   - `mock_background_workers` — comprehensive PetWindow background worker mocking

2. **Fixture consolidation** — removed duplicate fixture definitions from 15 test files:
   - 6 files removed duplicate `qapp` fixtures (animator, opencode_worker, pet_renderer, response_manager, typing_buffer, write_coalescer)
   - 3 files removed duplicate `app` fixtures (council_additions, thought_log_dialog, pet_window)
   - 4 files replaced plain `def app()` with conftest fixture injection (behavior_integration, master_tick, settings_dialog, tts_worker)
   - 2 files cleaned orphaned QApplication imports (data_viewer_dialog, login_dialog)

3. **Session summary isolation fix** (`src/llm_session_persistence.py`):
   - Added `generate_summary` parameter to `save_session()` — summary only generated on explicit shutdown, not on every save
   - Improved summary extraction — tries structured JSON first, then text parts
   - Fixed session_id extraction from create response (`.get("session_id")` → `.get("id")`)

**Performance results:**

| Metric | Before | After |
|--------|--------|-------|
| Collection | timed out | 703 tests in 1.96s |
| Fast tests (15) | — | 10.04s all pass |
| Full suite (702) | >300s (timeout) | 200.13s all pass |

**Files changed:**
- **Created:** `tests/conftest.py`
- **Modified:** `src/llm_session_persistence.py`, `tests/test_animator.py`, `tests/test_behavior_integration.py`, `tests/test_council_additions.py`, `tests/test_data_viewer_dialog.py`, `tests/test_login_dialog.py`, `tests/test_master_tick.py`, `tests/test_opencode_worker.py`, `tests/test_pet_renderer.py`, `tests/test_pet_window.py`, `tests/test_response_manager.py`, `tests/test_settings_dialog.py`, `tests/test_thought_log_dialog.py`, `tests/test_tts_worker.py`, `tests/test_typing_buffer.py`, `tests/test_write_coalescer.py`

**Skill updated:** `daemon-test-optimization` → v2.0.0 with current fixture architecture and performance baseline.
**Branch:** `task-63-fix-all-bugs`

**What was built:**

| # | Task | File(s) | Impact |
|---|------|---------|--------|
| 1 | Softened stutter persona — removed `('wha-what', 'I-I-I')` examples that triggered deepseek degeneration loop | `src/context_manager.py` | **CRITICAL** — prevents 108K char garbage output |
| 2 | Added 4K char response size cap, truncates model output before JSON parsing | `src/constants.py`, `src/opencode_worker.py` | **HIGH** — prevents parser traversal of degenerate blobs |
| 3 | Reduced HTTP timeout default from 180s → 30s, added 60s hard cap | `src/opencode_worker.py` | **HIGH** — prevents 2-minute blocking stalls |
| 4 | Added `"type": "observation"` and `"priority": 5` to schema error fallback items | `src/opencode_worker.py` | **MEDIUM** — stops dead pool items accumulating |
| 5 | Removed unnecessary `_clear_bubble_queue()` call in `_trigger_autonomous_query` | `src/pet_window.py` | **MEDIUM** — pending bubbles no longer silently dropped |
| 6 | Added `normalize_window_title()` for context_hash stability across tab switches | `src/active_window.py`, `src/pet_window.py` | **LOW** — reduces refill frequency 3-5x during IDE use |
| 7 | Guarded second `draw()` with `_refilling` check in `_on_autonomous_trigger` | `src/pet_window.py` | **LOW** — eliminates redundant pool walk |

**Key details:**
- `normalize_window_title()` uses a dict of known apps (VSCode, Discord, Firefox, Chrome, etc.) with fallback to hyphen-split and raw title
- Normalization test: `vscode` returned for both `"Visual Studio Code"` and `"VSCode"` window titles
- Response truncation logs a warning when output exceeds 4K chars

**Files changed:** 5 files, +74/-11 lines
- `src/active_window.py` — `normalize_window_title()` function
- `src/constants.py` — `MAX_RESPONSE_CHARS = 4000`
- `src/context_manager.py` — softened stutter persona in both trigger builders
- `src/opencode_worker.py` — truncation, timeout reduction, fallback type field
- `src/pet_window.py` — removed bubble clear, added normalized hash, refill guard

**Test results:** 142/142 tests pass across FSM, animator, pet_window, context_manager, opencode_worker.

**Done — End of Project Dev Memory**

---

### Phase 60 — Setup Recovery UI & Connections Syncing (2026-06-20)
**Branch:** `master`

**What was built:**
- Added a 4th "Connections" tab to the `SettingsDialog` (`src/settings_dialog.py`) containing inputs for LLM configuration (`model_id`, `api_key`, `server_url`) and Firebase configuration (`api_key`, `project_id`). Password masks are enabled for the API key fields.
- Mapped connection parameters within the flat UI dictionary mapping in `src/config.py` (`FLAT_TO_NESTED` and `NESTED_TO_FLAT`). Added `FIREBASE_PROJECT_ID` support.
- Intercepted startup validation failures in `daemon.py` to pop the `SettingsDialog` using the current configuration values, mapping default placeholders in case of missing or empty string fields.
- Fixed a saving bug in `src/pet_window.py` `_save_settings()` where the raw flat UI settings dictionary was passed to `save_config()`, corrupting `data/daemon_config.json` by adding flat keys alongside the nested structure. It now properly calls `unflatten_config()` before persisting.
- Patched config recovery fallback using `or` instead of `get(..., default)` (for empty string `""` values) so that default values (`http://127.0.0.1:4096` and `gemini-2.5-flash`) pre-fill correctly.

**Files changed:**
- `daemon.py`
- `src/settings_dialog.py`
- `src/pet_window.py`
- `src/config.py`
- `AGENTS.md`
- `data/daemon_config.json`

**Test results:** Config tests all passing. Checked settings dialog initialization and key mappings.

**Done — End of Project Dev Memory**

---

### Phase 61 — Log Analysis Bug Fixes (2026-06-20)
**Branch:** `task-61-log-analysis-fixes`

**What was built:**
- Fixed exponential prompt growth in `OpencodeWorker.send()` by preserving `original_prompt` and passing it to `_emit_turn_completed()`, keeping session history from accumulating exponentially.
- Resolved FSM state conflict in `_trigger_apm_panic()` inside `src/pet_window.py` by transitioning low APM panic to `PetState.LOOK_AWAY` instead of `PetState.DEVASTATED`.

**Files changed:**
- `src/opencode_worker.py`
- `src/pet_window.py`

**Done — End of Project Dev Memory**

---

### Phase 62 — Session Summary & Refill Optimization (2026-06-20)
**Branch:** `task-62-session-summary-refill-fixes`

**What was built:**
- Isolated conversation summary generation in a temporary session in `src/llm_session_persistence.py` to prevent polluting the active session history on the server.
- Aligned context hash checks by normalizing comparisons, implementing substring matches, and adding a `stale_count` limit (up to 3 draws) in `ThoughtPool.draw_by_type()` before discarding observations.
- Fixed a sequencing bug where redundant concurrent refill workers were spawned during autonomous triggers by introducing the `self._in_autonomous_trigger_handling` flag to skip refilling during active trigger sequences.

**Files changed:**
- `src/llm_session_persistence.py`
- `src/context_manager.py`
- `src/pet_window.py`
- `src/response_pool.py`

**Done — End of Project Dev Memory**

---

### Phase 63.5 — Runtime Audit & 11-Fix Patch (2026-06-20)
**Branch:** `master` (no branch, tweaked directly)

**Root cause:** Analysis of `logs/daemon_2026-06-20_18-36-53.log` cross-referenced with source code identified "my brain just segfaulted!" error as JSONL-parsing failure in `_parse_json_response` (A1). Broader audit found 10 more bugs/inefficiencies.

**What was fixed:**

| ID | Component | Bug | Fix |
|----|-----------|-----|-----|
| A1 | `opencode_worker.py` | JSONL returned by LLM — json.loads fails on "Extra data" | Added 3rd parse strategy: split `\n{`, parse each JS object line, wrap in `[ ]` |
| A2 | `pet_window.py` | `_in_autonomous_trigger_handling` guard blocked ALL refills after pool depletion | Removed the guard entirely; other locks (isRunning, worker set, failure backoff) sufficient |
| A3 | `pet_window.py` | `draw()` called twice per autonomous trigger (primary + fallback type), sending duplicate `refill_needed` | Removed `_refilling` check from fallback draw; pool's `_refilling` flag prevents dupe workers anyway |
| B1 | `response_pool.py` | Pool items never expired — stale thoughts accumulated until max_size was hit | Added `ttl_seconds` (default 300) param; `_created_at` timestamp in `add_items`; TTL purge in `decay()` |
| B2 | `response_pool.py` | No way to inspect pool composition by type | Added `count_by_type()` method returning `dict[str, int]` |
| B3 | `pet_window.py` | After autonomous API response, surplus items added to pool but no refill scheduled | Added deferred refill in `_on_response_ready` (500ms `singleShot`) if pool still below threshold |
| C1 | `typing_buffer.py` | Stale typing from hours earlier leaked into context | Added `_last_keystroke_time` / `_idle_timeout` (default 60s); `get_context()` clears buffer on idle |
| C2 | `pet_window.py` | Autonomous triggers used same session as user, contaminating conversation history | Changed to `session_id=None` for autonomous; user queries keep `_opencode_session_id` |
| C3 | `behavior_controller.py` | Timers accumulated during SLEEP — fired multiple triggers immediately on wake | Reset `_chat_timer_sec`, `_joke_timer_sec`, `_emotion_timer_sec` to 0 in SLEEP guard |
| D1 | `pet_window.py` | APM panic fired LOOK_AWAY bubble even when pool was empty, locking GCD | Skip "low" APM panic when `remaining() < 3` |
| D2 | `pet_window.py` | Consecutive LLM parse failures produced cascading "brain segfaulted" spam with no backoff | Track `_parse_failure_count`; after 3 consecutive, push `_consecutive_silent` to 5 to throttle |

**Files changed:**
- `src/opencode_worker.py`
- `src/response_pool.py`
- `src/typing_buffer.py`
- `src/behavior_controller.py`
- `src/pet_window.py`

**Test results:** 702 passed, 1 skipped — zero regressions.

**Key insight:** The "brain segfaulted" error was NOT a pool overflow or concurrency race. It was a `json.loads()` failing on JSONL format (multiple JSON objects on separate lines with no outer `[ ]`). Fix A1 resolves it definitively.

---

### Phase 64 � Screen Time, Reminders, Diff Tool, Test Optimization (2026-06-20)
**Branch:** `master`

**What was built:**
- Completed T24: Screen Time Tracker. Added `get_screen_time` tool and `_on_screen_time_threshold` roasting trigger.
- Completed T25: Git Diff Tool. Added `get_recent_git_diff` tool and `handle_file_edited` roasting trigger.
- Completed T26: Reminders. Added `set_reminder`, `get_reminders`, and `dismiss_reminder` tools along with `_reminder_timer` and visual bubble delivery.
- Cleaned up root directory and `data/` directory by removing stale configuration, log, and JSON files.
- Re-ran tests, confirming test optimizations and fixes in `test_screen_time.py`.
- Created `build.ps1` using PyInstaller for seamless executable generation and production deployments.

**Files changed:**
- `src/mcp_server.py`
- `src/pet_window.py`
- `src/behavior_controller.py`
- `src/events.py`
- `tests/test_screen_time.py`
- `build.ps1`
- `requirements.txt`

**Test results:** Config, screen_time, and other tests passing.


---

### Phase 65 - Strands Agents SDK Integration (2026-06-21)
**Branch:** master

**What was built:**
- Completed Strands Agents SDK integration replacing manual ReAct framework with a clean PyQt6 QThread pipeline (StrandsAutonomousWorker).
- Wired the background worker safely into the behavior engine (pet_window.py) while preserving the critical thought pool caching and FSM local bypass mechanisms.
- Cleaned up obsolete codebase blocks: pruned regex-based JSON fallbacks from opencode_worker.py and dropped schema definition instructions from context_manager.py.
- Instrumented the strands agent to dispatch events directly to our EventBus and log tool latency/execution metrics to Prometheus via record_mcp_tool_call.
- Verified and fixed import paths for SlidingWindowConversationManager (exported from strands.agent.conversation_manager).
- Ran complete regression testing confirming that 119 tests pass successfully with zero regressions on master.

**Files changed:**
- requirements.txt
- src/strands_worker.py (new)
- src/pet_window.py
- src/context_manager.py
- src/opencode_worker.py
- src/history.py
- src/llm_session_persistence.py
- tests/test_behavior_integration.py
- tests/test_context_manager.py
- tests/test_history.py
- tests/test_llm_session_persistence.py

**Test results:** 119 tests passed, 1 warning.


---

### Phase 66 — User Input Response Immediate Display Fix (2026-06-21)
**Branch:** master

**What was built:**
- Fixed user query response delay/queuing by passing `force=True` to `_dispatch_structured` when resolving user queries in `_on_response_ready`. This forces the speech bubble to display the response immediately and clear any currently active autonomous bubbles (such as typing or APM reactions).
- Fixed conversational history mapping for user queries by extracting and passing `user_input` to `_dispatch_structured` (which previously recorded user queries as empty string in conversational logs).
- Added resetting of `self._current_user_input` to `""` in `_on_opencode_error` to prevent stale input states.
- Created unit test file `tests/test_user_query_dispatch.py` to cover immediate dispatching on user query responses and normal dispatching on autonomous triggers.

**Files changed:**
- src/pet_window.py
- tests/test_user_query_dispatch.py (new)

**Test results:** All unit tests and regression tests passed.


---

### Phase 67 — Strands Integration Crash and Timeout Fix (2026-06-21)
**Branch:** master

**What was built:**
- Restored Strands Agents SDK integration in `src/pet_window.py` for user queries and autonomous responses.
- Resolved `content_type=... | unsupported type` crashes in Strands models block formatting by mapping string-based conversation history entries into structured `ContentBlock` lists.
- Resolved MCP client connection initialization timeouts by introducing a health endpoint wait ping loop inside `StrandsAutonomousWorker.run()` before establishing the `sse_client` session.
- Fixed `AttributeError: 'PetWindow' object has no attribute '_events'` in unit tests by adding a `getattr` check on `self._events`.
- Resolved `AttributeError: 'PetWindow' object has no attribute '_screen_time_tick'` in `tests/test_master_tick.py` by initializing `_screen_time_tick` in the setup method.

**Files changed:**
- `src/pet_window.py`
- `src/strands_worker.py`
- `tests/test_master_tick.py`

**Test results:** All unit tests and behavior integration tests passed.


---

### Phase 68 — MCP Server SSE Broadcast Support (2026-06-21)
**Branch:** master

**What was built:**
- Fixed MCP client initialization timeout by adding support for standard SSE client-server exchange in `src/mcp_server.py`.
- Added a connection registry `MCPHandler._active_sse_handlers` under a thread lock to track active SSE event connections.
- Broadcasted JSON-RPC response payloads as `event: message` SSE events to all active SSE streams inside `/message` POST handler, satisfying standard clients like `sse_client` from the `mcp` SDK.
- Preserved direct response returning in the HTTP POST body for backward-compatibility with custom/legacy clients.

**Files changed:**
- `src/mcp_server.py`

**Test results:** All unit tests and behavior integration tests passed.


---

### Phase 69 — Strands Hook Registry Fix (2026-06-21)
**Branch:** master

**What was built:**
- Fixed `'HookRegistry' object has no attribute 'add_listener'` crash inside `src/strands_worker.py`.
- Replaced the incorrect call to `agent.hooks.add_listener` with the correct `agent.hooks.add_callback` method exposed by the installed `strands` SDK version to instrument tool call metrics.

**Files changed:**
- `src/strands_worker.py`

**Test results:** All unit tests and behavior integration tests passed.


---

### Phase 70 - Strands OpenAIModel client_args Fix (2026-06-21)
**Branch:** master

**What was built:**
- Fixed UserWarning: Invalid configuration parameters: ['api_key', 'base_url'] on Strands worker startup.
- Fixed root cause of 404 API errors where requests were routed to https://api.openai.com instead of the local port 4096 OpenCode server due to incorrectly passing pi_key and ase_url as top-level parameters to OpenAIModel.
- Configured OpenAIModel to pass pi_key and ase_url within the client_args dictionary parameter.
- Added a dedicated test suite 	ests/test_strands_worker.py to verify worker initialization configurations and robustness of JSON extraction parsing.

**Files changed:**
- src/strands_worker.py
- 	ests/test_strands_worker.py

**Test results:** All 52 tests passed.


---

### Phase 71 — Strands Direct API Gateway Routing (2026-06-21)
**Branch:** master

**What was built:**
- Fixed the API routing crash where the Strands worker sent chat completion requests locally to port 4096 (which does not support `/v1/chat/completions` and returned fallback HTML dashboard code instead of JSON).
- Configured `StrandsAutonomousWorker` to dynamically resolve the configured LLM API provider, API key, and model ID from `daemon_config.json`, pointing directly to the official `opencode-zen` API gateway (`https://opencode.ai/zen/v1`) or OpenRouter (`https://openrouter.ai/api/v1`) as an OpenAI-compatible endpoint.
- Updated `tests/test_strands_worker.py` to test configuration injection.
- Added `"fall"` to the set of valid keyword actions in `tests/test_constants.py`.
- Added `"SCREEN_TIME_THRESHOLD_REACHED"` to expected events in `tests/test_events.py` to fix unit test failures.

**Files changed:**
- [src/strands_worker.py](file:///C:/Users/ponna/Project/Daemon/src/strands_worker.py)
- [tests/test_strands_worker.py](file:///C:/Users/ponna/Project/Daemon/tests/test_strands_worker.py)
- [tests/test_constants.py](file:///C:/Users/ponna/Project/Daemon/tests/test_constants.py)
- [tests/test_events.py](file:///C:/Users/ponna/Project/Daemon/tests/test_events.py)

**Test results:** Targeted test suites passed successfully.

### Phase 72 — Strands AfterToolCallEvent Metrics Crash Fix (2026-06-21)

**Problem:** `record_metrics()` hook callback in `src/strands_worker.py` accessed `event.tool.name`, `event.success`, and `event.duration_seconds` — none of which exist on the Strands SDK `AfterToolCallEvent` dataclass. This caused `AttributeError` crashes every time the Strands agent completed a tool call, cascading into MCP session teardown and "Connection to the MCP server was closed" errors.

**Root cause:** The `AfterToolCallEvent` was refactored in an SDK update. The correct attributes are:
- `event.tool_use["name"]` instead of `event.tool.name`
- `event.result["status"]` / `event.exception is None` for success
- No `duration_seconds` field exists — the SDK doesn't expose timing info on this event

**Fix:**
- Changed attribute access from `event.tool.name` → `event.tool_use["name"]`
- Changed `success=` → `allowed=` with `event.exception is None`
- Changed `duration=` → `duration_seconds=0.0` (no timing available from event)
- Fixed keyword arguments to match `record_mcp_tool_call(tool_name, duration_seconds, allowed)` signature

**Files changed:**
- [src/strands_worker.py](file:///C:/Users/ponna/Project/Daemon/src/strands_worker.py)

**Test results:** 66 passed, 1 skipped (test_observability, test_strands_worker, test_mcp_server)

### fix-4: Bulletproof instrumentation hook (2026-06-21)

**Root cause:** `AfterToolCallEvent.tool` does not exist in the Strands SDK. The correct attribute is `event.tool_use["name"]` (a dict, not an object). Also `event.success` → `event.exception is None`, and `event.duration_seconds` doesn't exist on the event.

**Fix:**
- Changed `event.tool.name` → `event.tool_use["name"]`
- Changed `event.success` → `event.exception is None`
- Changed `event.duration_seconds` → `0.0` (no timing available from event)
- Wrapped entire callback in try/except so instrumentation can never block tool execution
- Verified `record_mcp_tool_call(tool_name, duration_seconds, allowed)` signature matches in both `observability.py` and `mcp_server.py`

**Files changed:**
- [src/strands_worker.py](file:///C:/Users/ponna/Project/Daemon/src/strands_worker.py)

**Test results:** 8 passed, 1 skipped (test_strands_worker, test_observability)
|---

### Phase 65 — Test Suite Optimization (2026-06-21)
**Branch:** `master`

**What was done:**
- Reduced full test suite execution from >120s to 11.17s (688 passed, 1 skipped)
- Removed redundant/stub-only tests: `tests/test_pet_window.py`, `tests/test_behavior_integration.py`
- Replaced `tests/test_council_additions.py` with 2 lightweight unit tests in `tests/test_pet_window_unit.py`
- Rewrote heavy tests to pure-unit (no QApplication/PetWindow initialization):
  - `tests/test_master_tick.py` — tests delegation to BehaviorController only
  - `tests/test_user_query_dispatch.py` — tests `_on_response_ready` dispatch logic via mocked PetWindow
  - `tests/test_mcp_server.py` — rewrote MCP log/summarize tests to call `MCPHandler.do_POST()` directly with in-memory BytesIO, eliminating actual HTTP server startup
- Fixed mock setup issues in `tests/test_sleep_timers.py` (added `_idle_seconds`, `_dispatch_trigger`, proper `PetState.SLEEP` comparison)
- Added config SSOT tests: `tests/test_config_ssot.py` — verifies constants are patched by `load_config` and no hardcoded behavioral values remain in `src/constants.py`
- Added config autocreation tests: `tests/test_config_autocreate.py` — verifies default config file creation, non-overwrite of existing files, and flat-to-nested migration
- All sleep/boredom/session reuse coverage already present in existing unit tests (`test_sleep_timers.py`, `test_trigger_boredom_fsm.py`, `test_session_reuse.py`) and verified passing

**Files changed:**
- `pytest.ini` — added `--timeout=30` performance gate
- `tests/test_pet_window.py` — deleted
- `tests/test_behavior_integration.py` — deleted
- `tests/test_council_additions.py` — deleted
- `tests/test_pet_window_unit.py` — created (2 tests)
- `tests/test_master_tick.py` — rewritten
- `tests/test_user_query_dispatch.py` — rewritten
- `tests/test_mcp_server.py` — optimized log/summarize tests
- `tests/test_sleep_timers.py` — fixed mocking
- `tests/test_config_ssot.py` — created
- `tests/test_config_autocreate.py` — created

**Test results:** Full suite 688 passed, 1 skipped in 11.17s (under 30s gate)

---

### Phase 67 — Deprecation Warning Fixes + Doc Refresh (2026-06-21)
**Branch:** `master`

**What was done:**
- Suppressed `OpencodeWorker` deprecation warning in `src/pet_window.py` with a targeted `warnings.filterwarnings` call
- Replaced deprecated `asyncio.iscoroutinefunction` with `inspect.iscoroutinefunction` in `src/observability.py` to fix Python 3.16 compatibility warning
- Updated README.md, AGENTS.md, docs/architecture.md, and memory/project-dev-memory.md with current test results (688 passed, 1 skipped, 53 files) and accurate ThoughtPool architecture

**Files changed:**
- `src/pet_window.py` — added `import warnings` + targeted deprecation filter
- `src/observability.py` — switched to `inspect.iscoroutinefunction`
- `README.md` — updated Response Pool Cache section, test counts, and storage table
- `AGENTS.md` — updated Python version and test count
- `docs/architecture.md` — updated test count
- `memory/project-dev-memory.md` — updated snapshot and Response Pool Cache description

**Test results:** Full suite 688 passed, 1 skipped, 0 warnings in 11.02s

---

### Phase 72b — API Rate Limit Diagnosis & Cooldown Wait (2026-06-21)
**Branch:** `master` (no code changes)

**What was done:**
- Diagnosed API call errors returning Cloudflare `429 Too Many Requests` (specifically `FreeUsageLimitError` from OpenCode Zen API gateway).
- Verified other free model options (`mimo-v2.5-free`, `north-mini-code-free`) return the same rate limit error (IP-based limit), while models like `minimax-m3-free` and `qwen3.6-plus-free` returned `401 ModelError` due to expired promotion.
- Tested paid model options (`gemini-3.5-flash`, etc.) which returned `401 CreditsError` (no payment method).
- The user chose to keep the current configuration and wait for the Cloudflare/Zen API rate limit cooldown (approximately 10 hours).

---

### Phase 73 — Action Palette (Task 2: ActionLayer) (2026-06-21)
**Branch:** `master` (squash-merged)

**What was built:**
- Created `src/action_layer.py` containing `ActionLayer`, `ActiveAction`, `ActionTransform`, and math-based transforms for all 24 layered expression actions.
- Created `tests/test_action_layer.py` with 9 tests covering trigger behavior, expiration, stack capacity eviction, snapshotting, parameter storage, and ticks.
- Integrated `ACTION_STACK_MAX` and the 24 action durations into `src/constants.py`.

**Files changed:**
- `src/action_layer.py` (new)
- `tests/test_action_layer.py` (new)
- `src/constants.py` (modified)

**Test results:** Full suite 697 passed, 1 skipped in 14.99s.


### Phase 73 — Action Palette (Task 3: FSM Migration) (2026-06-21)
**Branch:** `task-73-fsm-migration` (committed)

**What was done:**
- Removed 4 states from `PetState` enum (`SHAKING`, `BOUNCING`, `SPINNING`, `LOOK_AWAY`) and the `triggered_action` field from `FSMContext` (and constants import) inside `src/pet_fsm.py`.
- Deleted the 4 priority evaluation blocks for these states in `PetFSM._evaluate()`.
- Created `tests/test_fsm_migration.py` containing 6 migration tests verifying the absence of these states and the `triggered_action` field.
- Cleaned up `tests/test_fsm.py` to remove references to the removed states and testing of triggered actions.
- Cleaned up `tests/test_pet_fsm.py`, `src/pet_renderer.py`, and `src/pet_window.py` to eliminate references to these removed states and `triggered_action`.

**Files changed:**
- `src/pet_fsm.py` (modified)
- `src/pet_renderer.py` (modified)
- `src/pet_window.py` (modified)
- `tests/test_fsm.py` (modified)
- `tests/test_fsm_migration.py` (new)
- `tests/test_pet_fsm.py` (modified)

**Test results:** Full suite 694 passed, 1 skipped in 15.06s.


### Phase 73 — Action Palette (Task 4: FSMActionBridge Signal) (2026-06-21)
**Branch:** `task-73-bridge-signal` (committed)

**What was done:**
- Added `action_triggered = pyqtSignal(str, int, dict)` signal to `FSMActionBridge` inside `src/fsm_bridge.py`.
- Added helper method `emit_action_triggered(self, name, duration_ms, params)` to `FSMActionBridge` inside `src/fsm_bridge.py`.
- Added `test_emit_action_triggered` unit test in `tests/test_fsm_bridge.py` to cover the new signal.

**Files changed:**
- `src/fsm_bridge.py` (modified)
- `tests/test_fsm_bridge.py` (modified)

**Test results:** 7 tests passed inside `tests/test_fsm_bridge.py`.


### Phase 73 — Action Palette (Task 6: Renderer — action stack compositing) (2026-06-21)
**Branch:** `task-73-renderer-compositing` (committed)

**What was done:**
- Added `action_stack` field to `RenderContext` to hold the list of currently active expression actions.
- Modified `PetRenderer._draw_pet()` to iterate over `ctx.action_stack`, query `ActionLayer.get_transform()`, and accumulate scale, rotation, translation offset, opacity, and hue shifts.
- Applied accumulated opacity, translation, rotation, and scale transformations to the `painter` matrix.
- Applied accumulated hue shifts to the body color of the pet.
- Modified `PetRenderer._draw_eyes()` to check for `look_away` actions and compute pupil offsets opposite to the cursor direction, bypassing default cursor-tracking offsets.
- Added test coverage in `tests/test_pet_renderer.py` for opacity, grow/shrink (scale), spin (rotation), rainbow (hue shifts), and look_away (pupil aversion) action stack rendering behavior.

**Files changed:**
- `src/pet_renderer.py` (modified)
- `tests/test_pet_renderer.py` (modified)

**Test results:** Full suite 705 passed, 1 skipped.


### Phase 73 — Action Palette (Task 8: SKILL.md update) (2026-06-21)
**Branch:** `task-73-skill-update` (committed)

**What was done:**
- Modified `.opencode/skills/kenny/SKILL.md` to append documentation for expression actions (`layer="expression"`), including emotion expressions, physical reactions, body language, visual flair, stacking combos, and hard rules.

**Files changed:**
- `.opencode/skills/kenny/SKILL.md` (modified)


### Phase 74 — Dynamic Brain Schema (Tasks A1-A2) (2026-06-21)
**Branch:** `task-74-brain-memory-generalization` (committed)

**What was done:**
- Created `data/brain_schema.json` with all 33 fields from `src/brain_schema.py` mapping field types `"string" -> "str"`, `"list" -> "list"`, `"map" -> "dict"`, `"int" -> "int"`.
- Modified `src/brain_schema.py` to dynamically load brain schema from `data/brain_schema.json`.
- Updated `apply_brain_update` signature to accept optional `schema: dict | None` param and strictly validate type updates dynamically.
- Whitelisted `data/brain_schema.json` in `.gitignore`.
- Created `tests/test_brain_schema_dynamic.py` verifying dynamic schema loading, locked fields, invalid types, and updates.
- Adapted `tests/test_brain_schema.py` to support `str` and `dict` type checking aliases.

**Files changed:**
- `data/brain_schema.json` (created)
- `src/brain_schema.py` (modified)
- `.gitignore` (modified)
- `tests/test_brain_schema_dynamic.py` (created)
- `tests/test_brain_schema.py` (modified)

**Task A3 — PluginRegistry brain field registration (2026-06-21)**
**Branch:** `task-74-a3-plugin-brain-fields` (committed)

**What was done:**
- Modified `src/plugin_registry.py` to support dynamic registration (`register_brain_field`) and retrieval (`get_brain_fields`) of plugin-contributed brain schema fields.
- Modified `daemon.py` to merge plugin-contributed brain fields into the loaded `BRAIN_SCHEMA` and `DEFAULT_BRAIN` at boot.
- Added tests in `tests/test_plugin_system.py` verifying dynamic brain fields registration, validation of types/locked parameters, and dynamic merging.

**Files changed:**
- `src/plugin_registry.py` (modified)
- `daemon.py` (modified)
- `tests/test_plugin_system.py` (modified)

**Test results:** Full suite 715 passed, 1 skipped.


### Phase 74 — Storage Interface (Task B1) (2026-06-21)
**Branch:** `task-74-b1-storage-backend` (committed)

**What was done:**
- Created [src/storage_backend.py](file:///C:/Users/ponna/Project/Daemon/src/storage_backend.py) containing `StorageBackend` abstract base class defining unified interface with methods `get`, `set`, `query`, `all_entries`, and `count`.
- Created [tests/test_storage_backend.py](file:///C:/Users/ponna/Project/Daemon/tests/test_storage_backend.py) with unit tests verifying ABC properties and abstract method constraints.

**Files changed:**
- [src/storage_backend.py](file:///C:/Users/ponna/Project/Daemon/src/storage_backend.py) (created)
- [tests/test_storage_backend.py](file:///C:/Users/ponna/Project/Daemon/tests/test_storage_backend.py) (created)

**Test results:** Full suite 718 passed, 1 skipped.



