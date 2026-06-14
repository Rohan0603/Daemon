# Daemon

A mischievous, always-on-top Windows desktop pet built with PyQt6. Lives on your screen, reacts to system activity, and talks to the `opencode` multi-agent platform via HTTP API. Kenny+Morty hybrid personality — an anxious, profane, surveillance-obsessed companion that roasts you relentlessly.

---

## Architecture Overview

Daemon is a stateful Qt6 desktop companion driven by three interconnected systems: a Finite State Machine for visual behaviors, a noReply context-injection pipeline for LLM communication, and a layered storage stack (local JSON + Firebase) for persistent memory.

```
                           ┌──────────────────────────────┐
                           │         daemon.py             │
                           │  argparse, QApplication,      │
                           │  opencode serve auto-start,    │
                           │  single-instance PID lock      │
                           └──────────────┬───────────────┘
                                          │
                           ┌──────────────▼───────────────┐
                           │        PetWindow              │
                           │  ┌─────────────────────────┐ │
                           │  │      PetFSM (pet_fsm.py) │ │
                           │  │  15 priority-ordered     │ │
                           │  │  states, zero Qt imports  │ │
                           │  └─────────────────────────┘ │
                           │  ┌─────────────────────────┐ │
                           │  │  PetRenderer (stateless) │ │
                           │  │  QPainter vector drawing, │ │
                           │  │  eye tracking, squash/    │ │
                           │  │  stretch, perimeter       │ │
                           │  └─────────────────────────┘ │
                           │  ┌─────────────────────────┐ │
                           │  │  Input / Sensing         │ │
                           │  │  APMWorker (pynput),     │ │
                           │  │  TypingBuffer (pynput),  │ │
                           │  │  ClickThroughManager      │ │
                           │  └─────────────────────────┘ │
                           │  ┌─────────────────────────┐ │
                           │  │  opencode Bridge         │ │
                           │  │  OpencodeWorker(QThread),│ │
                           │  │  ContextManager,         │ │
                           │  │  ResponseManager          │ │
                           │  └─────────────────────────┘ │
                           │  ┌─────────────────────────┐ │
                           │  │  Storage Stack           │ │
                           │  │  Memory / History /       │ │
                           │  │  DiaryStore /             │ │
                           │  │  WriteCoalescer /         │ │
                           │  │  MemoryManager /          │ │
                           │  │  FirebaseCRUD              │ │
                           │  └─────────────────────────┘ │
                           └──────────────────────────────┘
```

---

## FSM: 15-State Priority Machine

The pet's visual state is governed by a single-threaded priority evaluator in `src/pet_fsm.py`. Every 33ms tick, `PetFSM._evaluate()` walks through states in priority order — the first matching condition wins. The FSM has **zero Qt imports** and is fully testable standalone.

| Pri | State | Trigger | Exit |
|-----|-------|---------|------|
| 1 | **DRAGGED** | Left-click on pet | Mouse release |
| 2 | **FALLING** | Released in mid-air | Ground contact → squash/stretch → IDLE |
| 3 | **CHASE** | Cursor within 120px radius | Cursor beyond 250px |
| 4 | **HYPER** | APM > 150 sustained 3s, or LLM trigger | APM drops for 10s cooldown |
| 5 | **THINKING** | User submits query (double-click) | LLM response received |
| 6 | **CELEBRATE** | Build success event | 3s elapsed |
| 7 | **DEVASTATED** | Build failure event | 5s elapsed |
| 8 | **SHAKING** | LLM action `shake` | 2s elapsed |
| 9 | **BOUNCING** | LLM action `bounce` | 3s elapsed |
| 10 | **SPINNING** | LLM action `spin` | 1.5s elapsed |
| 11 | **AUTONOMOUS_THINKING** | Autonomous query in flight | Response received |
| 12 | **LOOK_AWAY** | LLM action `look_away` | 4s elapsed |
| 13 | **PERIMETER** | Wander timer from IDLE | Random fall-off-edge (20%) |
| 14 | **SLEEP** | 300s idle | Any mouse/key input |
| 15 | **IDLE** | Default | — |

Each state has distinct rendering: breathing idle, color-flash HYPER, eye averting for LOOK_AWAY, orange panic SHAKING, spin transform SPINNING, Zzz overlay SLEEP, etc. PERIMETER patrols all 4 screen edges counter-clockwise with full 8-way rotate+scale rendering per edge × facing direction.

---

## opencode Communication: noReply Context Injection

Daemon talks to `opencode` via its HTTP API (default `http://127.0.0.1:4096`). The communication pattern is a **two-phase noReply design** that minimizes per-query token usage while maintaining persistent context:

### Phase 1: Session + Injection (one-time)

```
Daemon ──POST /session─────────────────────► opencode server
       ◄──session_id──────────────────────
       ──POST /session/{id}/message────────►
          { noReply: true, text: <~2500 tokens> }
       ◄──200 OK (no response text)──────── (context stored server-side)
```

The injection payload contains:
- **Native Agent Skill** (`.opencode/skills/kenny/SKILL.md` — Kenny persona, action matrix, output contract)
- **Memory context** (all 50+ facts from `Memory` → factual grounding)
- **Diary entries** (last 5 entries → emotional history)
- **Role instruction** (sleeper agent owned by wife)
- **Format instructions** (strict JSON output contract)

### Phase 2: Triggers (per-query, ~50-100 tokens)

```
Daemon ──POST /session/{id}/message────────►
          { text: "Mode: active_chat\nAPM: 45\nIdle seconds: 12\n..." }
       ◄──JSON response─────────────────── (50-100 token trigger + LLM response)
```

Autonomous triggers are minimal prompts (`Mode`, `APM`, `Idle seconds`, optional `typing content`). The LLM responds with contextualized JSON because it already has the full personality and context from phase 1.

### Session persistence

- All triggers share one `session_id` — the LLM model maintains message history server-side
- `ContextManager.needs_reinjection()` checks for 15-minute idle via `time.monotonic()` heartbeat
- On stale session: automatically creates new session, re-injects full context, then processes deferred triggers

### API-first with auto-serve

- `opencode_serve_manager.py` auto-spawns `opencode serve --port 4096` on daemon startup
- `OpencodeWorker._post_message()` uses `requests` HTTP to the local API
- If API is unavailable (port TIME_WAIT, serve not started), the daemon falls back gracefully
- `--no-opencode` CLI flag disables all LLM integration

---

## Memory Architecture

### Three Layers

```
┌─────────────────────────────────────────────┐
│ Layer 3: Firebase Firestore (source of truth)│
│  daemon_data/core_brain  ← document          │
│  daemon_diary            ← collection        │
├─────────────────────────────────────────────┤
│ Layer 2: MemoryManager (bridge)              │
│  sync_to_local() / sync_from_local()         │
│  pending-write retry queue                   │
│  FirebaseCRUD wrapper (3-attempt retry)      │
├─────────────────────────────────────────────┤
│ Layer 1: Local JSON (fast cache)             │
│  Memory     → ~/.daemon_memory.json           │
│  History    → ~/.daemon_history.json          │
│  DiaryStore → ~/.daemon_diary.json           │
│  Response   → ~/.daemon_response_cache.json  │
│  State      → ~/.daemon_state.json           │
└─────────────────────────────────────────────┘
```

### Boot Sequence

1. Startup → `load_config()` → `ensure_opencode_serve_running()` → `load_state()`
2. `PetWindow.__init__()` creates `Memory`, `History`, `MemoryManager`, `DiaryStore`
3. `_init_diary()`:
   - `MemoryManager.sync_to_local(memory)` — fetches `core_brain` from Firestore, writes all fields into local `Memory`
   - Loads diary from local file; if missing, fetches from Firebase (limit 200)
   - On first-ever run (`first_run_done=False`): seeds 3 diary entries with the user's linguistic mistakes
4. `ContextManager.inject_full()` on first API session — includes all brain fields + last 5 diary entries

### During Session

- **Memory**: Key-value facts (`!remember key: value`), auto-populated from Firestore brain, cap at 50 facts. LLM can emit `brain_update` in JSON responses to add facts (only unlocked fields in `BrainSchema`).
- **History**: Last 100 conversation entries (`user_input` ↔ `daemon_response`), wrapped by `ContextManager` into `build_trigger()` prompts.
- **Diary**: Append-only local list during session. Marked dirty on write → flushed by `WriteCoalescer` every 8 seconds.
- **Brain updates**: LLM can emit `brain_update` dict in trigger responses → validated by `apply_brain_update()` (respects `locked=True` fields) → written to Firestore + local Memory.

### Quit Sequence

1. Timers stopped → `WriteCoalescer.stop()` + `flush()` (synchronous)
2. `brain` pending writes retried via `MemoryManager.retry_pending_writes()`
3. `MemoryManager.sync_from_local(memory)` — pushes changed local facts back to Firestore `core_brain`
4. `MemoryManager.push_pending_diaries()` — pushes unsynced diary entries to Firestore `daemon_diary`
5. `History.save()`, `Memory.save()`, `save_state()` — atomic tmp+replace writes with `.bak` backup

### Brain Schema

Defined in `src/brain_schema.py`. 26 fields with `locked` flags:
- **Locked fields** (7): `primary_directive_override`, `daemon_profession`, `daemon_name`, `daemon_personality`, `daemon_origin`, `daemon_runtime_info`, `daemon_current_form`, `user_name`, `user_profession` — only settable via `seed_brain.py`
- **Unlockable fields** (17): `long_term_goals`, `user_habits`, `blackmail_material`, `daemon_quirks`, `daemon_habits`, `daemon_fears`, `daemon_likes`, `daemon_catchphrases`, `recent_blackmail_log`, `user_preferences`, `insider_knowledge` — LLM can append to these

`seed_brain.py` is a standalone CLI utility to view/merge/seed the Firestore `core_brain` document.

---

## Response Pool Cache

The `AutonomousResponseManager` manages two pre-fetched LLM response pools:

| Pool | Size | Refill Threshold | Source |
|------|------|------------------|--------|
| `jokes_blackmail` | 5 | 3 | Boredom/joke timers + user responses |
| `system` | 2 | 1 | Active chat timers + user responses |

### How it works

- **Draw**: Weighted random selection by priority (higher priority = more likely). Selected items are removed from the pool.
- **Decay**: Priority drops by 1 every 2 minutes (min 1). Old items fade, fresh items surface.
- **Refill**: When pool drops below threshold, a dedicated `OpencodeWorker` is spawned with a specialized refill prompt (no context injection needed — standalone JSON array request).
- **User-response priming**: When the user sends a query, the LLM response can include `jokes_blackmail_items` (2) + `system_items` (2) → automatically fed into pools.
- **Persistence**: Pools saved to `~/.daemon_response_cache.json` on quit. 7-day TTL cleanup on load — stale items discarded.

This cache eliminates API calls for simple autonomous chatter. Boredom quips and idle observations come from the pool without hitting the LLM.

---

## Engagement Tracker (Adaptive Backoff)

Daemon tracks whether the user is engaged or ignoring it:

| Metric | Threshold | Effect |
|--------|-----------|--------|
| `consecutive_silent` | 5 | Exponential backoff: interval × 1.5ⁿ, max 120s |
| `consecutive_engaged` | 2 | Reset to base 15s interval |

Engagement is recorded whenever output is displayed (bubble visible). User input (double-click query) immediately resets to base interval. This prevents Daemon from spamming a user who isn't paying attention.

---

## Storage Durability

All local JSON files use **atomic writes**: write to `.tmp` → `os.replace(tmp, final)`. Existing files become `.bak` before overwrite. On load failure, the system tries `.bak` recovery.

### WriteCoalescer

Batch-flushes dirty local stores every 8 seconds. Prevents disk thrashing during high-frequency autonomous chatter. Tracks 5 dirty flags:
- `memory` → `Memory.save()`
- `history` → `History.save()`
- `diary` → `DiaryStore.write()`
- `response_cache` → Response pools persist
- `brain` → `MemoryManager.retry_pending_writes()`

### Crash Recovery

A `sys.excepthook` patch in `PetWindow` calls `WriteCoalescer.flush()` on any unhandled exception. Single-instance PID lock (`~/.daemon.lock`) prevents duplicate daemon processes.

---

## TTS (Text-to-Speech)

`TTSWorker(QThread)` generates voice output with:
- **Primary**: `edge-tts` (Azure Neural TTS — `en-US-GuyNeural` voice), async generation via `asyncio`
- **Fallback**: `pyttsx3` (local SAPI voices)
- **DSP**: Pitch shift via framerate manipulation (`TTS_PITCH_FACTOR=1.15`), high-pass filter (120Hz)
- **Playback**: `winsound.SND_SYNC` (primary) with `simpleaudio` fallback
- TTS is currently **paused** — `enqueue()` calls are commented out in bubble display

---

## Perimeter Patrol System

When wander timer fires from IDLE, the pet enters PERIMETER state (not random wander). It patrols all 4 screen edges counter-clockwise:
- **bottom** → right edge → top edge → left edge → bottom
- At corner transitions: 20% chance of falling off edge → FALLING state
- 8-way renderer transform: each edge × each facing direction has correct rotate/scale

---

## File Map

| File | Role |
|------|------|
| `daemon.py` | Entry point — argparse, PID lock, opencode serve, QApplication lifecycle |
| `src/constants.py` | All tunable values (100 lines) |
| `src/pet_fsm.py` | `PetState` enum (15), `FSMContext` dataclass, `PetFSM` — zero Qt imports |
| `src/pet_renderer.py` | `PetRenderer` — stateless QPainter vector drawing (422 lines) |
| `src/pet_window.py` | `PetWindow(QWidget)` — FSM timer, physics, drag, input, all wiring (1190 lines) |
| `src/click_through.py` | `ClickThroughManager` — Win32 `WS_EX_TRANSPARENT` toggle, 50ms poll |
| `src/apm_worker.py` | `APMWorker(QThread)` — pynput keyboard+mouse listeners, rolling 60s APM |
| `src/typing_buffer.py` | `TypingBuffer` — pynput keystroke capture, deque ring buffer |
| `src/opencode_worker.py` | `OpencodeWorker(QThread)` — HTTP API, `inject_context` (noReply), `send_trigger`, JSON parsing |
| `src/context_manager.py` | `ContextManager` — `inject_full()` / `inject_delta()` / `build_trigger()` / heartbeat |
| `src/response_manager.py` | `AutonomousResponseManager` + `ResponsePool` — dual-pool with weighted draw + priority decay |
| `src/context_menu.py` | `PetContextMenu(QMenu)` — 6 actions: build events, memory recall, history, pin, quit |
| `src/memory.py` | `Memory` — local JSON key-value fact store (`.bak` recovery) |
| `src/history.py` | `History` — local JSON conversation log (100 entries, `.bak` recovery) |
| `src/memory_manager.py` | `MemoryManager` — Firestore bridge: sync brain + diary, retry queue |
| `src/firebase_crud.py` | `FirebaseCRUD` — generic Firestore wrapper with 3-attempt retry, 6 verbs |
| `src/brain_schema.py` | Brain schema definition (26 fields), `apply_brain_update()`, `DEFAULT_BRAIN`, validation |
| `src/diary_store.py` | `DiaryStore` — atomic local diary I/O, 200-entry cap, backup recovery |
| `src/write_coalescer.py` | `WriteCoalescer` — QTimer batched flush (8s) for 5 dirty flags |
| `src/persistence.py` | `save_state()` / `load_state()` — `~/.daemon_state.json`, atomic write |
| `src/config.py` | `load_config()` / `save_config()` — `~/.daemon_config.json`, 19 overridable keys |
| `src/opencode_serve_manager.py` | Auto-spawn `opencode serve` on boot, port-bound detection |
| `src/tts_worker.py` | `TTSWorker(QThread)` — edge-tts + pyttsx3 + pydub pitch shift + winsound playback |
| `src/settings_dialog.py` | `SettingsDialog(QDialog)` — size/opacity/speed sliders + voice toggle |
| `src/active_window.py` | `get_active_window_title()` — Win32 `GetForegroundWindow` |
| `src/logging_setup.py` | Unified stdlib logging with `RotatingFileHandler` |
| `seed_brain.py` | Standalone Firestore brain seeder — view/merge/seed core_brain document |

| `.opencode/skills/kenny/SKILL.md` | Full Kenny persona + action matrix + output contract (loaded natively by OpenCode) |

---

## Local Storage Paths

| File | Class | Content |
|------|-------|---------|
| `~/.daemon_memory.json` | `Memory` | Key-value facts (seeded from Firestore, updated by LLM) |
| `~/.daemon_history.json` | `History` | Last 100 conversations |
| `~/.daemon_response_cache.json` | `ResponseManager` | Dual-pool pre-fetched LLM responses |
| `~/.daemon_diary.json` | `DiaryStore` | Diary entries (synced to Firebase daemon_diary on quit) |
| `~/.daemon_state.json` | `persistence` | Runtime state (mood, interactions, first_run_done) |
| `~/.daemon_config.json` | `config` | User overrides (model, scale, opacity, speed, TTS) |
| `~/.daemon.lock` | PID lock | Single-instance guard |

---

## Configuration

Override any constant via `~/.daemon_config.json`:

```json
{
    "OPENCODE_SERVER_URL": "http://127.0.0.1:4096",
    "OPENCODE_API_MODEL_ID": "deepseek-v4-flash",
    "pet_scale": 1.0,
    "pet_opacity": 0.85,
    "pet_speed": 1.0,
    "tts_enabled": true,
    "tts_rate": 220,
    "tts_volume": 1.0,
    "tts_voice_id": "en-US-GuyNeural"
}
```

Settings panel (right-click tray → Settings) provides live-preview sliders for size, opacity, speed, and voice toggle.

---

## Commands

| Action | Result |
|--------|--------|
| `py daemon.py` | Run normally |
| `py daemon.py --debug` | Headless FSM simulation (100 ticks) |
| `py daemon.py --verbose` | DEBUG-level logging to console + file |
| `py daemon.py --no-opencode` | Disable all LLM integration |
| `py seed_brain.py` | View current Firestore brain + diff from defaults |
| `py seed_brain.py --seed-defaults` | Push DEFAULT_BRAIN to Firestore |
| `py -m pytest tests/ -v` | Run all tests |

### In-Pet Commands

| Input | Effect |
|-------|--------|
| Double-click pet | Open query input → send to opencode |
| `!remember key: value` | Store a fact in local + cloud memory |
| `!forget key` | Remove a fact |
| `!memories` | Show all stored facts |
| `!history` | Show recent conversations |
| Left-click + drag | Pick up Daemon |
| Right-click | Context menu (build events, memory, history, pin, quit) |
| Ctrl+Alt+D | Global hotkey — focus Daemon |

---

## Dependencies

```
PyQt6>=6.7.0        # GUI framework
pynput>=1.7.7       # Global keyboard/mouse monitoring
openai>=1.0.0       # SDK (legacy, not currently used)
firebase-admin>=6.5.0  # Firestore cloud sync
requests             # HTTP to opencode API
edge-tts             # Azure Neural TTS (voice generation)
pyttsx3              # Local SAPI TTS fallback
pydub                # Audio DSP (pitch shift)
simpleaudio          # Audio playback fallback
pytest               # Test runner
```

## Tests

```bash
py -m pytest tests/ -v
```

~450+ tests across 49 test files. All pass, 0 skipped.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| GUI | PyQt6 (QWidget, QPainter, QSystemTrayIcon) |
| Rendering | QPainter vector drawing (no image assets) |
| Input monitoring | pynput (keyboard + mouse listeners) |
| Window transparency | Win32 ctypes (`WS_EX_TRANSPARENT`, `SetWindowLongW`) |
| AI bridge | opencode HTTP API (127.0.0.1:4096) |
| AI model | DeepSeek V4 Flash via OpenCode Go |
| Persistence | Firebase Firestore + local JSON (`.bak` recovery) |
| Voice | edge-tts (Azure Neural) + pyttsx3 (SAPI) + pydub DSP |
| Web search | Built into OpenCode Go (via Exa AI) |
