# Daemon Desktop Pet — Agent Instructions

**This file replaces CLAUDE.md and GEMINI.md.** Both AI agents use this single file.

---

## START HERE — Project Dev Memory

**Before doing anything**, read `memory/project-dev-memory.md`. It has:
- What's already built (with commit hashes)
- What to do next
- Known pitfalls already encountered
- Recommendations from prior sessions

After completing any task, update `memory/project-dev-memory.md` with the task result.

---

## Project

Transparent always-on-top Windows desktop companion built with PyQt6. Named **Daemon**. Reacts to system activity (APM, active window, typing), provides floating interface to the `opencode` multi-agent CLI, and maintains persistent memory via Firebase.

**Working directory:** `C:\Users\ponna\Project\Daemon`
**Git root:** `C:\Users\ponna\Project\Daemon`
**Python:** use `py` (not `python` or `python3`) — Windows py launcher
**Tests:** `py -m pytest tests/ -v`
**Stack:** Python 3.11+, PyQt6, pynput, ctypes (Win32), requests, comtypes, Pillow, pyttsx3
**Test count:** ~450+ across 49 test files

---

## Git Workflow (REQUIRED)

```
git checkout -b task-<N>-<slug>   # feature branch
# implement + commit on branch
git checkout master
git merge --squash task-<N>-<slug>
git commit -m "feat: ..."
git branch -D task-<N>-<slug>
```

Never commit directly to master. Never include AI assistant names in commit messages.

---

## End-to-End Architecture

### Boot Sequence (`daemon.py → PetWindow.__init__`)

```
daemon.py main()
  ├─ _ensure_ffmpeg_on_path()          # Finds WinGet ffmpeg, adds to PATH
  ├─ load_config()                     # data/daemon_config.json → nested dict
  │   └─ setattr(constants, key, val)  # Patches constants module at runtime
  ├─ argparse (--debug, --verbose, --no-opencode, --no-auth, --pet-id)
  ├─ _acquire_lock(pet_id)             # PID-based single-instance guard
  ├─ setup_logging()                   # RotatingFileHandler → logs/daemon_*.log
  ├─ generate_codebase_map()           # AST → data/codebase_map.json
  ├─ SetConsoleCtrlHandler()           # Win32 signal swallowing
  ├─ ensure_opencode_serve_running()   # Kill-respawn opencode serve on :4096
  ├─ load_state()                      # data/.daemon_state.json → {mood, interactions, ...}
  ├─ QApplication()
  ├─ FirebaseAuth()                    # Load saved tokens from data/.daemon_auth.json
  └─ PetWindow(opencode_enabled, initial_state, auth, pet_id)
      ├─ _setup_window()               # Frameless | TopMost | Tool, full-screen
      ├─ Config → _pet_scale, _pet_opacity, _pet_speed_multiplier, _chattiness
      ├─ PetFSM + PetRenderer + EmotionAnimator
      ├─ PetContextMenu (6 signals)
      ├─ APMWorker.start()             # pynput keyboard+mouse → rolling 60s APM
      ├─ TypingBuffer.start()          # pynput keystroke capture → 500-char ring buffer
      ├─ TTSWorker.start()             # edge_tts → pydub pitch shift → winsound
      ├─ FSMActionBridge + MCPServer    # JSON-RPC 2.0 on :4097
      ├─ Memory + History + DiaryStore  # Local JSON stores with .bak recovery
      ├─ WriteCoalescer.start()         # 8s QTimer for batched flushes
      ├─ ContextManager + AutonomousResponseManager
      ├─ _fsm_timer (33ms)  → _tick()          # Physics, animation, FSM
      ├─ _behavior_timer (1s) → _master_tick()  # Autonomous behavior tree
      ├─ _health_timer (10s) → health check     # opencode serve TCP check
      ├─ QTimer.singleShot(500) → _on_boot_check_auth()  # Firebase gate
      └─ MCPServer.start()
```

### Shutdown Sequence (`_force_quit_app`)

```
1.  _force_quit = True
2.  MCPServer.stop()
3.  Stop _fsm_timer + _behavior_timer
4.  ResponseManager.stop()
5.  WriteCoalescer.stop() + flush()
6.  Abort + quit all refill workers
7.  Abort + quit active opencode worker
8.  Close opencode session (HTTP DELETE)
9.  TypingBuffer.stop()
10. TTSWorker.stop()
11. APMWorker.stop()
12. Tray.hide()
13. ThoughtLogDialog.close()
14. _cleanup_uia() (COM cleanup)
15. QApplication.quit()

daemon.py finally block:
16. Release PID lock
17. MemoryManager.sync_from_local() → Firestore
18. Push pending diary entries → Firestore
19. Save history + memory locally
20. stop_opencode_serve()
21. save_state({mood, interactions, runtime_seconds, ...})
```

---

## Core Loop — Two Timers

### _tick() — 33ms (FSM_TICK_MS)
Physics, animation, FSM state machine, bubble countdown.

```
1. Bubble countdown → clear if expired, pop queue
2. Boredom countdown timer check
3. Build FSMContext from current state
4. PetFSM.update(dt_ms, ctx) → next PetState
5. Handle state transitions
6. _apply_physics() — gravity, throw, ground detection
7. _tick_perimeter() — counter-clockwise screen patrol
8. EmotionAnimator.update() — particle/overlay updates
9. self.update() → triggers paintEvent → PetRenderer.render()
```

### _master_tick() — 1000ms (BEHAVIOR_TICK_MS)
Autonomous behavior priority tree. The brain of the pet.

```
1. SLEEP guard → return if sleeping
2. Track window switches for WONDER emotion
3. Every EMOTION_TICK_SEC: _evaluate_emotion() → animator
4. Accumulate chat/joke timers
5. GCD gate → return if speech bubble active
6. Compute dynamic thresholds from chattiness

Priority tree:
  P1: APM > 80 → TOTAL SILENCE
  P2: Chat timer ≥ threshold AND context changed → _trigger_chat()
  P3: Joke timer ≥ threshold AND APM < 20 → _trigger_joke()
  P4: Idle ≥ 60s AND APM == 0 → boredom with exp backoff → _trigger_boredom_fsm()
```

---

## Data Flow Pipelines

### User Query Pipeline
```
Double-click pet → QLineEdit → Enter
  → _on_input_submitted()
    ├─ !commands: !remember, !forget, !memories, !history (local)
    └─ Normal text:
       → FSM → THINKING
       → ContextManager.build_user_trigger(mode, input, apm, idle, typing, screen)
       → OpencodeWorker(prompt, session_id, schema=STRUCTURED_SCHEMA)
         → POST /session/{id}/message (opencode serve :4096)
         → JSON parse chain: direct → fence strip → regex → fallback
       → _on_response_ready(items)
         → _dispatch_structured(item[0]) → show bubble + TTS + history
         → surplus items → ThoughtPool cache
```

### Autonomous Query Pipeline
```
_master_tick() P2/P3/P4 fires
  → _should_fire_autonomous() guard checks:
     - _autonomous_query_pending? bubble active? SLEEP? brain disconnected?
  → Try ThoughtPool draw (typing_reaction / idle_thought / observation)
  → Cache hit → _dispatch_structured() directly (no API call)
  → Cache miss → ContextManager.build_autonomous_trigger()
     → OpencodeWorker (is_autonomous=True)
     → _on_response_ready() → dispatch + cache surplus
```

### Pool Refill Pipeline (Two-Stage Agentic)
```
ThoughtPool.remaining() < threshold
  → refill_needed signal
  → _on_refill_needed()
    → Stage 1: Investigation prompt (NO schema, MCP tools available)
       → LLM calls MCP tools (read_file, search_codebase, read_clipboard)
    → Stage 2: Mixed-bag prompt + Stage 1 results (WITH schema)
       → LLM generates 5 typed items (typing_reaction, observation, intel_roast, idle_thought)
  → _on_refill_result() → ThoughtPool.on_refill_result()
```

### Memory Sync Pipeline
```
Boot:
  FirebaseAuth.load() → token check → LoginDialog if needed
  → FirebaseCRUD(token_provider, project_id)
  → MemoryManager.sync_to_local(memory)
    → Firestore users/{uid}/pets/{pet_id} → Memory.remember() per field
  → DiaryStore: fetch from Firebase, dedup via content hash

Runtime:
  WriteCoalescer (8s QTimer) flushes dirty flags:
    memory → Memory._save()
    history → History._save()
    diary → DiaryStore._write_atomic()
    brain → MemoryManager.retry_pending_writes()

Quit:
  MemoryManager.sync_from_local(memory) → split user/pet fields → Firestore
  push_pending_diaries() → Firestore
```

### MCP Tool Pipeline
```
opencode serve → JSON-RPC 2.0 POST /message → MCPHandler
  → tools/call → _is_tool_allowed(name, consent_config)
    → Blocked → -32001 error
    → Allowed → dispatch to handler:
       FSM tools → fsm_bridge.emit_request(action) → Qt signal → PetWindow._on_mcp_fsm_action()
       Toast → fsm_bridge.emit_toast(title, msg) → Qt signal → tray.showMessage()
       Read tools → direct execution in handler thread
```

### TTS Pipeline
```
_show_bubble(text) → TTSWorker.enqueue(text)
  → queue.Queue → worker thread:
    → edge_tts (async, .mp3) OR pyttsx3 (sync, .wav) fallback
    → pydub pitch shift (1.15x) OR wave stdlib fallback
    → winsound.PlaySound (SND_FILENAME | SND_SYNC)
```

---

## FSM States (15) — Priority Order (1=highest)

| # | State | Priority | Trigger | Duration | Visual |
|---|-------|----------|---------|----------|--------|
| 1 | DRAGGED | — | mousePressEvent | Until release | sx=1.0, sy=0.9, ±5° tilt |
| 2 | FALLING | — | Drop/throw/FEAR macro | Until ground | sy=1.15, rotation=f(velocity) |
| 3 | CHASE | P3 | Cursor < 120px | Until cursor > 250px + 500ms | 10° lean, speed lines |
| 4 | HYPER | P4 | APM > 150 for 3s | Until 10s cooldown | 4-color flash cycle (8Hz) |
| 5 | THINKING | P5 | query_pending=True | Until response | #7B9EC7, cascading dots |
| 6 | CELEBRATE | P6 | build_success | 3000ms | Golden star sparkles |
| 7 | DEVASTATED | P7 | build_fail / brain disconnect | 5000ms | Grayscale + red overlay |
| 8 | SHAKING | P8 | triggered_action | 2000ms | Orange, horizontal sine |
| 9 | BOUNCING | P9 | triggered_action | 3000ms | Vertical bounce |
| 10 | SPINNING | P10 | triggered_action | 1500ms | Yellow, full rotation |
| 11 | AUTONOMOUS_THINKING | P11 | autonomous pending | Until response | Muted purple #9B7EC8 |
| 12 | LOOK_AWAY | P12 | triggered_action | 4000ms | Pupils face away from cursor |
| 13 | PERIMETER | P13 | idle 10-30s (sticky) | Until interrupted | 8-way edge patrol, CCW |
| 14 | SLEEP | P14 | idle ≥ 300s | Until activity | 80% alpha, animated Zzz |
| 15 | IDLE | P15 | Default | — | Gentle breathing animation |

**Rules:**
- THINKING overrides CHASE/HYPER (user-initiated query takes precedence)
- CELEBRATE/DEVASTATED interrupted only by DRAGGED/FALLING/THINKING
- PERIMETER is sticky — once entered, stays until higher priority triggers
- Duration-based states (SHAKE/BOUNCE/SPIN/LOOK_AWAY) auto-exit via state_elapsed_ms
- CHASE has hysteresis: enter at 120px, exit at 250px + 500ms min dwell

---

## Emotion Engine (9 Emotions)

Evaluated every 5s by `_evaluate_emotion()`. Pure visual overlay — never writes pet_x/pet_y.

| Priority | Emotion | Trigger | Body Color | Transform |
|----------|---------|---------|------------|-----------|
| 1 | FEAR | Task Manager in window title | #6B5B95 | Stretched tall (1.3, 0.7) → FALLING macro |
| 2 | DISGUST | reddit/4chan in window title | Hue-shift -30° | Squished (0.8, 1.0) |
| 3 | WONDER | ≥3 window switches in 5s | White (#FFF) | Shrink 1.5→1.0 (800ms) |
| 4 | ANGER | Risky keyword matched | #E74C3C | Jitter ±0.02, ±2° |
| 5 | DEVOTION | APM > 60 | #FF69B4 | (1, 1, 0) |
| 6 | PATHOS | idle ≥ 120s AND APM == 0 | Grayscale | Slightly flat (1.0, 0.9) |
| 7 | TRANQUILITY | 0 < APM ≤ 60 AND "code" in title | 80% alpha | Slow breathe |
| 8 | MIRTH | Default | Base color | Gentle bounce |

Single-fire emotions auto-decay to MIRTH: HEROISM (1s), WONDER (0.8s), DISGUST (3s).

**Phase 46 — EmotionProfile Registry (Juice):**
All 9 emotions are now declared as `EmotionProfile` dataclasses in `EMOTION_PROFILES` registry (replaces procedural if/elif chains). Each profile carries full visual spec:

| Emotion | Eye modifier | Particle | Extra |
|---------|-------------|---------|-------|
| MIRTH | micro-tilt rotation (2° sin wave), sclera 0.8x | — | — |
| ANGER | angry brows 20°, squint 0.5x | red comet trail (`drift_x=-0.5`) | — |
| FEAR | tiny pupils 0.3x, wide sclera 1.2x | — | → FALLING macro |
| DISGUST | eye roll (pupil_offset_x=2.0) | — | hue shift -30° |
| PATHOS | sad brows -15° | — | opacity pulse 0.6→0.9 |
| DEVOTION | heart-shaped pupils | pink floating hearts | — |
| HEROISM | gold pupils (full sclera) | — | golden aura pulse 80→20 |
| WONDER | — | white screen flash | elastic pop 1.5→1.0, 1-frame glitch |
| TRANQUILITY | zen squint 0.1x | — | 80% alpha, slow breathe |

**Boundary:** EmotionAnimator is purely system-driven. The LLM controls **physical animations** (`change_visual_state`) only — it cannot set emotions, colors, or eye states via JSON or MCP.

---

## Engagement Tracker & Backoff

**Engagement tracking:**
- `_consecutive_silent` / `_consecutive_engaged` counters
- ≥ SILENCE_THRESHOLD (5) silent outputs → `_current_interval *= BACKOFF_MULTIPLIER (1.5x)` (max 120s)
- ≥ ENGAGED_THRESHOLD (2) engaged outputs → reset to BASE_INTERVAL_SEC (15s)

**Boredom backoff (context stability):**
- Context signature: `(active_window, apm, typing_len, screen_hash)`
- If context unchanged: `_idle_backoff_seconds` doubles after each boredom fire (max 300s)
- If context changes: reset backoff to 0, take new snapshot

**Reset triggers:** APM > 0, mouse activity, user input submission, SLEEP exit

---

## MCP Server (12 Tools on port 4097)

In-process JSON-RPC 2.0 HTTP server. SSE init at GET /sse, messages at POST /message.

| # | Tool | Consent Key | Params |
|---|------|-------------|--------|
| 1 | `change_visual_state` | allow_intrusive_animations | action (enum), target_x, target_y |
| 2 | `read_clipboard` | allow_clipboard_hijacking | — |
| 3 | `capture_blackmail_evidence` | allow_window_management | — |
| 4 | `send_system_toast` | allow_audio_disruptions | title, message |
| 5 | `list_directory` | — (always allowed) | relative_path |
| 6 | `read_file` | — | file_path, start_line, end_line |
| 7 | `search_codebase` | — | search_term (regex) |
| 8 | `get_memory` | — | — |
| 9 | `get_diary` | — | limit (1-50) |
| 10 | `simulate_keystroke` | allow_keyboard_injection | keys (max 50 chars) |
| 11 | `move_mouse` | allow_mouse_interference | x, y, click |
| 12 | `browser_navigation` | allow_browser_redirection | url (http/https only) |

**Consent Matrix (7 tiers in Settings → Boundaries):**
- Tier 1 (Low Risk): allow_intrusive_animations (default: True)
- Tier 2 (Medium Risk): allow_audio_disruptions, allow_browser_redirection (default: False)
- Tier 3 (High Risk): allow_clipboard_hijacking, allow_mouse_interference, allow_window_management, allow_keyboard_injection (default: False)

---

## Memory Architecture (3-Tier)

```
┌──────────────────────────────────────────┐
│ Tier 3 — Cloud (Source of Truth)         │
│ Firestore: users/{uid}/pets/{pet_id}     │
│   ├─ core_brain doc (22 fields)          │
│   └─ diary subcollection                 │
│ Security: per-user auth (firestore.rules)│
└──────────────────┬───────────────────────┘
                   │ FirebaseCRUD (3-attempt retry, 0.5s backoff)
┌──────────────────┴───────────────────────┐
│ Tier 2 — Bridge                          │
│ MemoryManager: sync_to_local / from_local│
│   ├─ _pending_writes deque (retry queue) │
│   └─ USER_LEVEL_KEYS split at sync       │
└──────────────────┬───────────────────────┘
                   │ WriteCoalescer (8s QTimer)
┌──────────────────┴───────────────────────┐
│ Tier 1 — Local (Fast Cache)              │
│ Memory: data/.daemon_memory.json (50 max)│
│ History: data/.daemon_history.json (100)  │
│ DiaryStore: data/.daemon_diary.json (200) │
│ All: atomic .tmp+.bak writes             │
└──────────────────────────────────────────┘
```

**Brain Schema (22 fields in 4 tiers):**
- Tier 1 (User Context, 6): user_name🔒, user_profession🔒, user_habits, user_preferences, user_long_term_goals, user_imposed_rules
- Tier 2 (Pet Identity, 6): pet_name🔒, pet_personality🔒, pet_role🔒, pet_origin🔒, pet_appearance🔒, pet_system_awareness🔒
- Tier 3 (Pet Behavior, 5): pet_likes, pet_quirks, pet_habits, pet_fears, pet_catchphrases
- Tier 4 (Mission/State, 5+): mission_directive🔒, mission_goals, intel_archive, intel_insider_knowledge, pet_affinity_score, pet_current_mood, progression_flags

🔒 = locked (LLM cannot modify via brain_update)

---

## ThoughtPool & Response Cache

Single unified `ThoughtPool` with 4 item types:
- `typing_reaction` — drawn by active chat timer
- `observation` — drawn by boredom timer
- `intel_roast` — drawn randomly
- `idle_thought` — drawn by boredom timer

**Pool config:** size=20, threshold=5, refill_count=5
**Priority decay:** every 120s, all priorities decrement by 1 (min 1)
**Spatial TTL:** items with mismatched `context_hash` discarded after 3 stale draws
**Persistence:** `data/.daemon_response_cache.json` with 7-day TTL cleanup on load
**Seeds:** 15 hardcoded Kenny typing reactions from `src/system_dialogs.json`

---

## File Map

### Source (`src/` — 35 files)

| File | Class/Module | Responsibility |
|------|-------------|----------------|
| `constants.py` | — | All tunable values; patched by config at runtime |
| `config.py` | `load_config`, `save_config` | Nested JSON config with flat↔nested conversion |
| `pet_fsm.py` | `PetState`, `FSMContext`, `PetFSM` | 15-state FSM, zero Qt imports |
| `pet_renderer.py` | `RenderContext`, `PetRenderer` | Stateless QPainter: body, eyes, overlays, bubble |
| `animator.py` | `Emotion`, `EmotionAnimator`, `ParticleSystem` | 9 emotions, transforms, particles (200 cap) |
| `click_through.py` | `ClickThroughManager` | Win32 WS_EX_TRANSPARENT, 50ms poll, 15px hysteresis |
| `apm_worker.py` | `APMWorker(QThread)` | pynput keyboard+mouse, rolling 60s APM, Ctrl+Alt+D hotkey |
| `typing_buffer.py` | `TypingBuffer(QObject)` | pynput keystroke capture, 500-char deque ring buffer |
| `opencode_worker.py` | `OpencodeWorker(QThread)` | HTTP POST to opencode serve, structured JSON schema, abort flag |
| `opencode_serve_manager.py` | `ensure_opencode_serve_running` | Kill-respawn opencode serve, PID tracking, health check |
| `context_manager.py` | `ContextManager` | Prompt builder: user/autonomous/mixed-bag triggers |
| `context_menu.py` | `PetContextMenu(QMenu)` | 6 actions: memory, history, restart, brain scan, pin, quit |
| `screen_reader.py` | `ScreenReader` | UIA text extraction via comtypes, WM_GETTEXT fallback, SHA-256 delta |
| `active_window.py` | `get_active_window_title` | Win32 GetForegroundWindow + GetWindowTextW |
| `pet_window.py` | `PetWindow(QWidget)` | ~1756 lines — owns everything: FSM, renderer, all wiring |
| `response_pool.py` | `ThoughtPool(QObject)` | Priority-weighted draw, type filtering, spatial TTL, decay |
| `response_manager.py` | `AutonomousResponseManager` | Single ThoughtPool, Mixed-Bag refill, persistence, seed data |
| `memory.py` | `Memory` | Local JSON key-value facts, 50 max, .bak recovery |
| `history.py` | `History` | Local JSON conversation log, 100 max, .bak recovery |
| `diary_store.py` | `DiaryStore` | Atomic diary I/O, SHA-256 dedup, 200 cap, .bak backup |
| `brain_schema.py` | `BRAIN_SCHEMA`, `apply_brain_update` | 22-field schema, locked fields, type validation |
| `memory_manager.py` | `MemoryManager` | Firebase bridge: sync_to/from_local, user/pet field split |
| `firebase_crud.py` | `FirebaseCRUD` | Firestore REST via firebase-admin SDK, 3-attempt retry |
| `firebase_auth.py` | `FirebaseAuth` | Firebase Auth REST API, token refresh, persistence |
| `write_coalescer.py` | `WriteCoalescer(QObject)` | 8s QTimer batched flush for 5 dirty flags |
| `persistence.py` | `save_state`, `load_state` | Atomic JSON state to data/.daemon_state.json |
| `tts_worker.py` | `TTSWorker(QThread)` | edge_tts/pyttsx3 → pydub pitch shift → winsound playback |
| `settings_dialog.py` | `SettingsDialog(QDialog)` | 3 tabs: Appearance, Voice, Boundaries (consent) |
| `thought_log_dialog.py` | `ThoughtLogDialog(QDialog)` | Matrix-style green-on-black log viewer, 1s refresh |
| `login_dialog.py` | `LoginDialog(QDialog)` | Kenny-persona email/password auth modal |
| `fsm_bridge.py` | `FSMActionBridge(QObject)` | pyqtSignal relay: MCP thread → Qt main thread |
| `mcp_server.py` | `MCPServer`, `MCPHandler` | JSON-RPC 2.0 HTTP on :4097, 12 tools, consent gating |
| `logging_setup.py` | `setup_logging` | RotatingFileHandler, 7-day cleanup, per-module levels |
| `system_dialogs.json` | — | 21 pre-baked Kenny system event responses |
| `utils/security.py` | `is_safe_write_path` | Write sandbox: all writes restricted to data/ |

### Scripts & Config

| File | Responsibility |
|------|----------------|
| `daemon.py` | Entry point: argparse, PID lock, crash hook, auth gate, shutdown |
| `seed_brain.py` | Standalone Firestore brain seeder: --view, --merge, --seed-defaults |

| `scripts/generate_ast_map.py` | AST parser → data/codebase_map.json (29 classes, 33 functions) |
| `firestore.rules` | Per-user auth, pet-level scoping |
| `.opencode/skills/kenny/SKILL.md` | Kenny persona, 12 MCP tools, profanity param (`full`/`moderate`/`sfw`), two-stage output contract (investigation = natural language, generation = strict JSON), locked brain fields, Mixed-Bag item types, spatial TTL guidance (loaded natively by opencode serve) |
| `daemon.spec` | PyInstaller --onefile spec (⚠️ references deleted assets/) |

### Tests (`tests/` — 49 files)

| File | Coverage |
|------|----------|
| `test_fsm.py` | 35 FSM state transition tests |
| `test_pet_window.py` | ~45KB, integration + session + dispatch tests |
| `test_mcp_server.py` | ~23KB, 49+ MCP tool + consent tests |
| `test_opencode_worker.py` | Structured schema, session reuse, fallback tests |
| `test_memory_manager.py` | Firebase mocked tests + retry queue |
| `test_animator.py` | 54 emotion/particle/transform tests |
| `test_response_pool.py` | ThoughtPool type filtering, spatial TTL, priority |
| `test_response_manager.py` | Single pool + Mixed-Bag + persistence |
| `test_write_coalescer.py` | Flush + dirty flags + diary integration |
| `test_diary_store.py` | Atomic I/O, backup, cap, dedup |
| `test_firebase_crud.py` | 22 CRUD + retry tests |
| `test_firebase_auth.py` | Auth REST API tests |
| `test_typing_buffer.py` | 13 keystroke capture tests |
| `test_tts_worker.py` | 9 TTS pipeline tests |
| `test_settings_dialog.py` | 5 settings UI tests |
| `test_brain_schema.py` | Schema validation + apply_brain_update |
| `test_config.py` | Config loading + flat↔nested |
| `test_screen_reader.py` | UIA/WM_GETTEXT extraction |
| `test_master_tick.py` | Behavioral priority tree tests |
| `test_behavior_integration.py` | Cross-module behavioral tests |
| `test_security.py` | Write sandbox tests |
| `test_codebase_awareness_e2e.py` | E2E MCP codebase tools |
| + 27 more test files | Various module tests |

---

## Local Storage Paths

All files stored in project `data/` directory (gitignored):

| File | Class | Content |
|------|-------|---------|
| `data/.daemon_memory.json` | `Memory` | User-taught key-value facts (max 50); seeded from Firestore on boot |
| `data/.daemon_history.json` | `History` | Conversation log (max 100 entries) |
| `data/.daemon_response_cache.json` | `AutonomousResponseManager` | ThoughtPool items (max 20), 7-day TTL |
| `data/.daemon_diary.json` | `DiaryStore` | Diary entries, SHA-256 dedup, synced flag (max 200) |
| `data/.daemon_state.json` | `persistence` | Runtime state: mood, interactions, runtime_seconds, first_run_done |
| `data/daemon_config.json` | `config` | Nested config: llm, pet, tts, consent, firebase sections |
| `data/.daemon_auth.json` | `FirebaseAuth` | Firebase auth tokens: uid, email, idToken, refreshToken, expires_at |
| `data/codebase_map.json` | AST mapper | Auto-generated architecture map (29 classes, 33 functions) |
| `data/.daemon_{pet_id}.lock` | PID lock | Single-instance guard (pet_id-scoped) |
| `data/.daemon_thoughts.log` | PetWindow | Internal monologue log (1000 line cap, rotate to 500) |
| `data/blackmail/` | MCP screenshot tool | Screenshots from capture_blackmail_evidence |

---

## Configuration (`data/daemon_config.json`)

Nested JSON with 5 sections:

```json
{
  "llm": {
    "model_id": "north-mini-code-free",
    "provider": "opencode",
    "server_url": "http://127.0.0.1:4096",
    "timeout_sec": 180
  },
  "pet": {
    "id": "kenny",
    "scale": 1.0,
    "opacity": 0.85,
    "speed_multiplier": 1.0,
    "chattiness": 1.0
  },
  "tts": {
    "enabled": true,
    "rate": 220,
    "volume": 1.0,
    "voice_id": "en-US-GuyNeural",
    "pitch": 1.15
  },
  "consent": {
    "allow_intrusive_animations": true,
    "allow_audio_disruptions": false,
    "allow_browser_redirection": false,
    "allow_clipboard_hijacking": false,
    "allow_mouse_interference": false,
    "allow_window_management": false,
    "allow_keyboard_injection": false
  },
  "firebase": { "api_key": "..." }
}
```

Config values override constants.py at startup via `setattr(constants, key, val)`.

---

## Key Pitfalls

| Pitfall | Fix |
|---------|------|
| HWND unavailable at `__init__` | Get `int(self.winId())` in `showEvent` after `show()` |
| Ground includes taskbar | `primaryScreen().availableGeometry().bottom()` |
| HiDPI coords | `availableGeometry()` and `geometry()` return LOGICAL pixels on Win11/PyQt6 1.25x — do NOT divide by `devicePixelRatio()`. Mouse events and `QCursor::pos()` are also logical |
| Tool window type missing | `FramelessWindowHint | WindowStaysOnTopHint | Tool` |
| pynput errors | `try/except` around import and listener start |
| QThread reuse | Reinstantiate `OpencodeWorker` per query — never reuse after `run()` completes |
| Black console on subprocess | `creationflags=subprocess.CREATE_NO_WINDOW` |
| Emoji rendering | `font.setFamilies` with `"Segoe UI Emoji"` fallback in QPainter |
| AUTONOMOUS_THINKING never exits | All callbacks must clear `_autonomous_query_pending` |
| Eye pupil drift in rotated states | Screen-space atan2 — max 15° mismatch, intentional tradeoff |
| `firebase_admin` duplicate init | Guard with `try: firebase_admin.get_app()` → `except ValueError: initialize_app()` |
| WriteCoalescer ignores unknown flags | Add new flag to `_dirty` dict before calling `mark_dirty()` |
| OpencodeWorker as local var GC'd | Store in `self._refill_workers[pool_type]` before `start()` |
| Auto-serve port TIME_WAIT | Previous serve exit puts port in TIME_WAIT ~60s; daemon falls back |
| PyQt6 signal + list.append | Can't be a Qt slot; use `lambda: emitted.append(None)` in tests |
| Zombie worker on shutdown | `_abort` flag checked before each `requests.post()` in worker |
| Click-through thrashing | Hysteresis deadzone: 15px margin for entry/exit detection |
| COM UIA should be singleton | `_get_uia_automation()` lazy singleton, `_cleanup_uia()` on shutdown |
| `worker.wait()` blocks GUI | Use signal `disconnect()` + `worker.quit()` instead of `wait()` |
| Path traversal in MCP | `os.path.normpath(os.path.abspath(path))` and verify prefix |
| SLEEP timers tick unconditionally | Add `if state == SLEEP: return` at top of `_master_tick` |
| Clipboard global lock | `CloseClipboard()` must be in `finally` block |
| opencode serve kill-respawn | Always kills existing and respawns fresh so SKILL.md updates take effect |
| SKILL.md Stage 1 / Stage 2 confusion | Stage 1 (INVESTIGATION) = natural language + MCP tools, NO JSON. Stage 2 (Generate N items) = strict JSON array only. Never mix them. |
| LLM writes locked brain field | `apply_brain_update()` silently drops locked fields (`user_name`, `pet_personality`, etc.). Confirm brain schema before adding new fields. |
| Spatial TTL kills observation items | `context_hash` mismatch discards after 3 stale draws. Observation items must be intensely screen-specific; generic ones waste API calls. |
| consent gate -32001 not handled | SKILL.md instructs LLM to roast user for being a control freak in `dialogue`; log in `thought`. Never surface JSON error to UI. |
| EmotionProfile Juice breaks old tests | `EMOTION_PROFILES` registry is source of truth. Legacy dicts (`_SINGLE_FIRE_DECAY`, `_EMOTION_OVERRIDE_COLOR`, `_PARTICLE_EMIT`) are derived properties — do NOT edit them directly. |

---

## Threading Model

```
Main Thread (Qt Event Loop)
  ├── PetWindow (all UI, FSM, timers, painting)
  ├── ClickThroughManager (50ms QTimer poll)
  ├── WriteCoalescer (8s QTimer)
  └── All signal slots

Worker Threads:
  ├── APMWorker (QThread) — pynput keyboard+mouse listeners
  ├── TypingBuffer (pynput thread via listener) — keystroke capture
  ├── TTSWorker (QThread) — TTS generation + playback
  ├── OpencodeWorker (QThread) — one-shot per query, HTTP to :4096
  └── Refill Workers (QThread) — stored in _refill_workers dict

Daemon Threads:
  ├── MCPServer HTTPServer (daemon thread on :4097)
  └── opencode serve (detached process on :4096)
```

**Thread safety:** All cross-thread communication via Qt signals with QueuedConnection. FSMActionBridge relays MCP handler thread → main Qt thread. No mutexes needed.

---

## Running

```powershell
pip install PyQt6 pynput pytest requests pyttsx3 comtypes Pillow firebase-admin
py -m pytest tests/ -v
py daemon.py
py daemon.py --debug       # headless FSM simulation, no display needed
py daemon.py --verbose     # enable DEBUG diagnostic logging
py daemon.py --no-opencode # disable opencode integration
py daemon.py --no-auth     # skip Firebase auth login gate
py daemon.py --pet-id foo  # use pet_id "foo" instead of "kenny"
```

Progress is tracked in `memory/project-dev-memory.md`. Update it after every task with commit hash, files changed, and any fixes applied.
