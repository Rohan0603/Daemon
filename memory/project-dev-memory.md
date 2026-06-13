# Daemon — Project Dev Memory

> **READ THIS FIRST in every new session** (Claude or Antigravity). It holds the authoritative state of the project: what's done, what's next, known issues, and agent recommendations.

---

## Project Snapshot

**Date updated:** 2026-06-12 (Phase 45 — The Puppeteer)
**Current branch:** `master`
**Latest commit:** `e0b0d0b` feat(config): migrate to unified nested configuration
**Git history:** Phase 1-35 → Phase 36 → Phase 37 → Phase 38 → Phase 39 → Phase 39.5 → Phase 40 → Phase 42 → Phase 43 → Phase 44 → Phase 44.5 → Phase 44.6 → Phase 45
**Git root:** `C:\Users\ponna\Project\Daemon`
**Python command:** `py` (Windows py launcher — not `python` or `python3`)
**Test command:** `py -m pytest tests/ -v --ignore=tests/test_output.txt --ignore=tests/test_firebase_crud.py`
**Test count:** ~450 across 29 test files (6 pool + 10 manager + 2 context + 2 pet_window new/updated)

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
| 3.1 OpencodeWorker | `src/opencode_worker.py`, `tests/test_opencode_worker.py` | ✅ | `5c003bc` | Subprocess wrapper calling opencode-query.ps1, markdown stripping, error handling; 6/6 tests pass (migrated from AgyWorker) |
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
| 5.9 Emoji / UTF-8 Fix | `opencode-query.ps1`, `src/pet_renderer.py`, `tests/test_pet_renderer.py` | ✅ | latest | Force UTF-8 OutputEncoding in PowerShell script and add font.setFamilies with emoji font fallbacks in PyQt renderer |

### Phase 6 — Autonomous Behavior & Context Awareness

| Task | File | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 6.1 AUTONOMOUS_THINKING FSM | `src/pet_fsm.py`, `src/constants.py`, `tests/test_fsm.py` | ✅ | `250a207` | New state priority 9 (between POOP and WANDER), BOREDOM_TIMEOUT_SEC=300, 25 FSM tests pass |
| 6.2 Active window module | `src/active_window.py`, `tests/test_active_window.py` | ✅ | `3e0f60f` | Win32 ctypes GetForegroundWindow, non-Windows returns "" |
| 6.3 OpencodeWorker JSON mode | `src/opencode_worker.py`, `tests/test_opencode_worker.py` | ✅ | `9146099` | structured_ready(str,str,int), _parse_json_response, fallback to result_ready |
| 6.3b Skill file externalisation | `assets/daemon-skill.md`, `opencode-query.ps1`, `src/opencode_worker.py` | ✅ | `0b0dd19` | Personality in Markdown, APM context in prompts, 6 FSM actions |
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
| 16.2 Fix opencode-query.ps1 | `opencode-query.ps1` | ✅ | — | Switched to standalone `opencode run --format json` without `--attach` |
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
- `_apply_morty_filter_wave()` now uses `TTS_PITCH_FACTOR` instead of hardcoded `2.0**(4/12.0)`

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

Two pre-fetched LLM response pools with priority-weighted random draw and 2-minute decay. Eliminates API calls for routine autonomous chatter.

### Engagement Tracker

Adaptive backoff: 5 consecutive silent outputs → exponential interval increase (max 120s). 2 engaged → reset to 15s base. Prevents spamming an inattentive user.

### Storage Durability

All local JSON: atomic tmp+replace writes, .bak fallback on read failure. Single-instance PID lock (data/.daemon.lock). Crash recovery via sys.excepthook that calls WriteCoalescer.flush().
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
- **Persona-infused LoginDialog** — Kenny+Morty UI strings ("Daemon: Clearance Check", "Access the Brain"), `_butcher_email()` helper for roasted error messages, persona error messages
- **PetFSM.transition_to()** — Centralized state transition method with optional callback; replaces direct `self.current_state = PetState.X`
- **RISKY_KEYWORDS dict** in `src/constants.py` — 6 keyword groups with 12 hardcoded roast lines for zero-latency interruptive reactions
- **daemon-skill.md Bickering Pair protocol** — `kenny_roast`/`morty_panic` modes and protocol rules for LLM-generated two-voice arguments
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

## What To Do Next

- **Linting:** `ruff check src/` — fix any remaining warnings before next phase
- **Test PyInstaller build** — `pyinstaller daemon.spec --clean` to produce `dist/Daemon.exe`
- **Future ideas:** multi-monitor screen reading, screen text delta detection, thought log viewer in settings dialog, opencode serve health monitoring, Linux/macOS compatibility layer, auto-serve port reuse to avoid TIME_WAIT on restart.



---

### Phase 17 — opencode Session Persistence + Parser Robustness ✅ COMPLETE

| Task | File | Status | Notes |
|------|------|--------|-------|
| 17.1 Fix `-f` flag bug | `opencode-query.ps1` | ✅ | `-f` alone doesn't supply message; changed to `Get-Content -Raw` + positional arg |
| 17.2 Session continuation | `opencode-query.ps1`, `src/opencode_worker.py`, `src/pet_window.py` | ✅ | Added `-Continue` switch to PS1; `continue_session` flag on worker; `_session_active` tracking in PetWindow |
| 17.3 Skill-once optimization | `src/opencode_worker.py`, `src/pet_window.py` | ✅ | `include_skill` param on `_build_prompt`; only sent on first query; CONCISE_PROMPT used for subsequent → moved to PS1-side skill loading |
| 17.4 Session state wiring | `src/pet_window.py` | ✅ | `_session_active` set True in all 3 success handlers; passed to all 4 worker creation sites |
| 17.5 Verification | — | ✅ | 179/179 tests pass, 1 skipped |
| 17.6 Fix `-Continue:$true` PowerShell crash | `src/opencode_worker.py` | ✅ | Changed `cmd.append("-Continue:$true")` → `cmd.append("-Continue")` — PowerShell `-File` mode passes `$true` as literal string, breaking `[switch]` param |
| 17.7 Move skill loading from Python to PS1 | `src/opencode_worker.py`, `opencode-query.ps1`, `tests/test_opencode_worker.py` | ✅ | `daemon-skill.md` loaded directly by PS1 from `$PSScriptRoot\assets\daemon-skill.md` instead of inlined into temp file; avoids command-line truncation risk |
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
| 18.3 Remove PS1 skill loading | `opencode-query.ps1` | ✅ | Removed `-NoSkill` param and all skill loading logic; PS1 now only reads temp file and passes to opencode |
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

### Memory & LLM Optimization — Task 4 (daemon-skill.md 50/50 Kenny+Morty Hybrid + Multiplexed Contract) ✅ COMPLETE

| Task | File | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 4.1 Persona rewrite | `assets/daemon-skill.md` | ✅ | `ef18547` | Full rewrite. 50/50 hybrid of Kenny (Gatlian, *High on Life*) and Morty Smith (*Rick and Morty*). 9 sections: identity anchor, two voices, verbal tics, memory/history awareness, environmental context, action matrix, multiplexed output contract, examples, JSON output spec. 6 existing examples updated with Morty stammering; 2 new multiplexed examples added (active_chat+joke, curiosity+boredom). All 10 dialogues ≤ 20 words. Worker code (`structured_multiplexed` signal) was already in place from prior work; skill file now documents the contract. No code changes, no test changes — 226 tests still pass. |

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
opencode-query.ps1       ← PowerShell script (legacy, not called by PetWindow)
requirements.txt         ← PyQt6, pynput, requests, pyttsx3, comtypes, Pillow
seed_brain.py            ← Standalone Firestore brain seeder
README.md                ← Comprehensive architecture documentation
```

---

---

### Phase 20 — Memory & LLM Optimization + Kenny/Morty Persona ✅ COMPLETE

| Task | File | Status | Commit | Notes |
|------|------|--------|--------|-------|
| 20.1 WriteCoalescer | `src/write_coalescer.py`, `tests/test_write_coalescer.py` | ✅ | `1927d6c` | QTimer-based batched flush (8s default); per-flag independent error handling; flag stays set on failure for retry; 10 tests |
| 20.2 Memory/History coalescer | `src/memory.py`, `src/history.py`, `tests/test_memory.py`, `tests/test_history.py` | ✅ | `1927d6c` (incl) | Constructor + per-call `coalescer=` param; per-call wins via `effective = coalescer if coalescer is not None else self._coalescer`; 3 tests |
| 20.3 TriggerCoalescer | `src/trigger_coalescer.py`, `tests/test_trigger_coalescer.py` | ✅ | `d26fbb9` | QTimer single-shot 2.5s; user-input mode fires synchronously; drops pending if worker already running; 8 tests |
| 20.4 ContextBuilder | `src/context_builder.py`, `tests/test_context_builder.py` | ✅ | `aeb31f1` | Full-then-delta prompt; baseline re-snapshots after each call; `on_path_change("cli")` resets baseline; 17 tests |
| 20.5 OpencodeWorker modes | `src/opencode_worker.py`, `tests/test_opencode_worker.py` | ✅ | `aeb31f1` (incl) | New `modes` kwarg, `structured_multiplexed` signal, `_SKILL_CONTENT` cached at module level; mode assignment by request INDEX (model's mode field ignored); 6 tests |
| 20.6 PetWindow wiring | `src/pet_window.py`, `tests/test_pet_window.py` | ✅ | `d26fbb9` (incl) | `_should_fire_autonomous()` DRY helper; `_dispatch_multiplexed()` aggregates modes; `_on_structured_multiplexed()` dispatches by mode; `_force_quit_app` follows spec §7 ordering; 8 integration tests |
| 20.7 Skill rewrite (Kenny+Morty) | `assets/daemon-skill.md` | ✅ | `ef18547` | 50/50 hybrid with both voices; 6 existing examples updated with Morty openers; 2 new multiplexed examples (active_chat+joke, curiosity+boredom); MULTIPLEXED OUTPUT CONTRACT section; 270 lines |
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

---

## How To Update This File

After each completed task, update:
1. The task row in "What Is Built" (status → ✅, fill commit hash + notes)
2. "What To Do Next" section
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
