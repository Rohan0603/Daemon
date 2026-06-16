# Daemon Desktop Pet — Complete Architecture

> Generated 2026-06-13. Covers all phases through Phase 46.

---

## 1. Memory System Architecture (3-Tier)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MEMORY ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  TIER 3: CLOUD (Firestore) — Source of Truth                       │
│  ─────────────────────────────────────────────────────────────      │
│  • users/{uid}/pets/{pet_id}             → 22-field brain schema      │
│  • users/{uid}/pets/{pet_id}/diary       → 200-entry capped diary     │
│  • FirebaseCRUD (REST API)             → 3-attempt retry + fallback │
│  • FirebaseAuth (REST API)             → Email/password + refresh   │
│                                                                     │
│  TIER 2: BRIDGE (MemoryManager) — Sync & Retry                     │
│  ─────────────────────────────────────────────────────────────      │
│  • load_current_brain()          → Firestore → local Memory         │
│  • sync_to_local()               → Brain fields → Memory (50 max)   │
│  • sync_from_local()             → Memory → Firestore (merge)       │
│  • fetch_all_diary_entries()     → All 200 entries at boot          │
│  • push_pending_diaries()        → Local → Firebase on quit         │
│  • retry_pending_writes()        → Queued writes on WriteCoalescer  │
│  • _pending_writes (deque)       → Two-tier fallback after CRUD     │
│                                                                     │
│  TIER 1: LOCAL (Fast Cache) — Runtime Access                       │
│  ─────────────────────────────────────────────────────────────      │
│  • Memory (data/.daemon_memory.json)     → 50 key-value facts       │
│  • History (data/.daemon_history.json)   → 100 conversation entries │
│  • DiaryStore (data/.daemon_diary.json)  → 200 entries + synced idx │
│  • ResponseManager (data/.daemon_response_cache.json) → single ThoughtPool (max 20) │
│  • WriteCoalescer (8s batched flush)     → Atomic tmp+replace + .bak│
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.1 Data Flow — Boot → Runtime → Quit

```
BOOT (daemon.py → PetWindow.__init__):
  1. FirebaseAuth.load() → token from data/.daemon_auth.json
  2. FirebaseCRUD → Firestore client (lazy init)
  3. MemoryManager.load_current_brain() → core_brain doc
  4. MemoryManager.sync_to_local(Memory) → populates local Memory
  5. MemoryManager.fetch_all_diary_entries(200) → DiaryStore.add_diary_entry()
  6. DiaryStore.read() → local diary (fallback, .bak recovery)
  7. WriteCoalescer.start() → 8s flush timer
  8. ResponseManager._load() → cache with 7-day TTL pruning

RUNTIME (PetWindow):
  • Memory.remember() → WriteCoalescer.mark_dirty("memory")
  • History.add_entry() → WriteCoalescer.mark_dirty("history")
  • _add_diary_entry() → WriteCoalescer.mark_dirty("diary")
  • ResponseManager → mark_dirty("response_cache") on pool changes
  • brain_update → FirebaseCRUD.set() → _pending_writes if fail
  • WriteCoalescer.flush() every 8s → atomic writes + retry queue

QUIT (daemon.py finally block):
  1. MemoryManager.sync_from_local(Memory) → Firestore merge
  2. MemoryManager.push_pending_diaries() → flush unsynced
  3. WriteCoalescer.stop() + flush() → ensure all local state saved
  4. save_state() → data/.daemon_state.json
```

### 1.2 Local Storage Files (data/)

| File | Class | Content | Durability |
|------|-------|---------|------------|
| `.daemon_memory.json` | `Memory` | 50 key-value facts (seeded from core_brain) | Atomic tmp+replace, .bak |
| `.daemon_history.json` | `History` | 100 conversation entries | Atomic tmp+replace, .bak |
| `.daemon_diary.json` | `DiaryStore` | 200 entries + `synced` count | Atomic + creates .bak on first write |
| `.daemon_response_cache.json` | `AutonomousResponseManager` | Single unified ThoughtPool (max 20 items, 4 types) + priorities | Atomic + 7-day TTL |
| `.daemon_state.json` | `persistence` | mood, interactions, runtime, first_run_done | JSON |
| `daemon_config.json` | `config` | Nested config: llm/pet/tts/consent sections | JSON |
| `.daemon_auth.json` | `FirebaseAuth` | uid, email, idToken, refreshToken, expires_at | JSON |
| `.daemon_{pet_id}.lock` | PID lock | Per-pet single-instance guard | Plain text PID |
| `codebase_map.json` | `generate_ast_map.py` | AST index of all classes/functions for self-awareness | JSON |
| `.daemon_thoughts.log` | `PetWindow._log_thought()` | Rotating 1000 lines, keeps 500 | Text (always written) |

---

## 2. SKILL.md Loading — Native OpenCode Integration

### 2.1 How SKILL.md Reaches the LLM (Phase 36+)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SKILL.MD LOADING FLOW                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  FILE: .opencode/skills/kenny/SKILL.md                              │
│                                                                     │
│  OPENCODE ARCHITECTURE (Native):                                    │
│  ─────────────────────────────────────────────────────────────      │
│  1. opencode serve starts on port 4096 (daemon.py)                  │
│  2. OpenCode loads ALL skills from .opencode/skills/ on startup    │
│  3. SKILL.md YAML frontmatter:                                     │
│     - name: kenny                                                  │
│     - description: 100% Kenny persona                              │
│     - compatibility: opencode                                      │
│  4. Skill is AVAILABLE to all sessions via MCP tools               │
│  5. LLM reads skill content FROM THE SERVER, not from Python       │
│                                                                     │
│  PYTHON SIDE (PetWindow/OpencodeWorker):                           │
│  ─────────────────────────────────────────────────────────────      │
│  • NO MORE skill file reading in Python                            │
│  • NO MORE inlining skill into prompts                             │
│  • ContextManager.build_trigger() → MINIMAL prompt (~150 tokens)   │
│  • OpencodeWorker.send() → POST /session/{id}/message              │
│  • Server has FULL skill context from native loading               │
│                                                                     │
│  STRUCTURED OUTPUT (JSON Schema):                                   │
│  ─────────────────────────────────────────────────────────────      │
│  • STRUCTURED_SCHEMA passed in API payload (opencode_worker.py:102)│
│  • LLM MUST return raw JSON array (no markdown, no preamble)       │
│  • Schema: thought(200) + dialogue(150) + brain_update(opt)        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Key SKILL.md Contract (Phase 46)

```yaml
Profanity Level (runtime parameter, injected per trigger):
  full     → uncensored (default)
  moderate → mild expletives only
  sfw      → zero profanity, preserve catchphrases

Output Contract — Two Modes:
  Stage 1 (Investigation): natural language, MCP tools only, NO JSON
  Stage 2 (Generation): STRICT raw JSON array, no markdown, no preamble

Schema A (direct response / autonomous monologue):
  [{thought(200), dialogue(150), brain_update?(dict of string arrays)}]
  - Forbidden output keys: `action`, `mode`
  - Locked brain fields (validator rejects): user_name, user_profession,
    pet_name, pet_personality, pet_role, pet_origin, pet_appearance,
    pet_system_awareness, mission_directive

Schema B (Mixed-Bag pool refill):
  [{type, thought(150), dialogue(100), priority(1-5), context_hash?}]
  - type: typing_reaction | observation | intel_roast | idle_thought
  - observation/typing_reaction: MUST be screen-specific (spatial TTL)

MCP Tools (12 total, called BEFORE JSON output):
  Surveillance:  change_visual_state, read_clipboard,
                 capture_blackmail_evidence, send_system_toast
  Codebase:      list_directory, read_file (max 500 lines),
                 search_codebase, get_memory, get_diary
  Chaos (gated): simulate_keystroke (max 50 chars),
                 move_mouse, browser_navigation (http/https only)
  Consent gate: -32001 error = permission denied; roast user in dialogue

FSM vs Emotion boundary:
  LLM controls: change_visual_state (physical animations)
  System controls: EmotionAnimator (colors, particles, eye modifiers)
                   — evaluated autonomously every 5s, not LLM-driven

Self-Awareness:
  - codebase_map.json AST index available at startup
  - Write cage: data/ only via is_safe_write_path()
```

### 2.3 Historical: Phase 17-35 (Legacy Skill Loading)

Before Phase 36, skill was loaded as `assets/daemon-skill.md` and inlined into every prompt via Python `Path.read_text()`. This was ~2500 tokens/query. Phase 36 eliminated this entirely by migrating to native opencode skill loading. The noReply injection pattern was also deleted (~280 lines removed).

---

## 3. Context Injection to OpenCode

### 3.1 Two-Phase noReply Pattern

```
  PHASE 1: SESSION CREATION + FULL INJECTION (One-time, ~2500 tokens)
  ─────────────────────────────────────────────────────────────
  PetWindow._dispatch_trigger() → OpencodeWorker
       ↓
  OpencodeWorker._post_message() → POST /session
       ↓  (if no session_id)
  POST /session/{id}/message with noReply: true
       ↓
  PAYLOAD:
  {
    "model": {providerID: "opencode-go", modelID: "deepseek-v4-flash"},
    "parts": [{"type": "text", "text": FULL_PROMPT}],
    "structured": STRUCTURED_SCHEMA
  }
       ↓
  SERVER RESPONSE: UserMessage (echoes input, NO AI response)
  → session_created signal → PetWindow._opencode_session_id set

  PHASE 2: TRIGGERS (Per-query, ~50-100 tokens)
  ─────────────────────────────────────────────
  ContextManager.build_autonomous_trigger() / build_user_trigger()
       ↓
  MINIMAL PROMPT:
  "Mode: active_chat\nAPM: 45\nIdle seconds: 120\nUser said: ..."
       ↓
  POST /session/{id}/message (no noReply flag)
       ↓
  SERVER RESPONSE: AssistantMessage with JSON array
  → response_ready signal → _on_response_ready()

  HEARTBEAT RE-INJECTION:
  ──────────────────────
  • 15-minute time.monotonic() heartbeat
  • If session stale → full injection again
  • Prevents context loss on server restart/timeout
```

### 3.2 ContextManager Prompt Builders

```
build_user_trigger (direct user interaction):
  "You are responding directly to the user.
   Mode: user_input
   APM (actions per minute — primary signal): 45
   Idle seconds: 0
   User said: hello daemon
   Respond with a JSON array containing EXACTLY ONE object."

build_autonomous_trigger (internal monologue):
  "Daemon is watching the user. He is a hyperactive...
   APM: 12
   Mode: joke
   Idle seconds: 180
   He is thinking to himself — NOT responding to the user.
   Generate exactly 5 items as a JSON array."

build_mixed_bag_prompt (unified pool refill):
  "Generate EXACTLY 5 items as a JSON array.
   Each item MUST have: type, dialogue, thought, priority, context_hash?
   Types: typing_reaction | observation | intel_roast | idle_thought
   Respond ONLY with the JSON array, no preamble."

Two-Stage agentic refill (OpencodeWorker._send_two_stage):
  Stage 1: Investigation prompt (no schema) → LLM calls MCP tools
  Stage 2: Mixed-bag prompt + Stage 1 results (with schema) → JSON array
```

---

## 4. Autonomous Behavior System

### 4.1 Timers

| Timer | Interval | Purpose |
|-------|----------|---------|
| `_chat_timer_sec` | 25s × chattiness multiplier | Active chat delta detection |
| `_joke_timer_sec` | 60s × APM modifier | Joke trigger |
| `_boredom_timer_ms` | 30s + exponential backoff | Boredom FSMActions |
| `_behavior_timer` | 1000ms | Master behavioral tick |
| `_hyper_flash_timer` | 125ms (8Hz) | HYPER color cycle |
| `_typing_debounce_timer` | 2000ms | Typing burst detection |

### 4.2 Behavioral Priority Tree (_master_tick)

```
P1: Flow State (APM > 80) → TOTAL SILENCE
P2: Active Chat Delta (window change/typing burst) → instant local + background API
P3: Joke (APM < 20, no backoff) → API call
P4: Boredom (APM == 0, idle ≥ 60s) → FSM action + API every 3rd tick
     - Adaptive backoff: 5 silent → exponential (max 120s)
     - 2 engaged → reset to 15s base
```

### 4.3 Response Pool (Phase 42+)

Single unified `ThoughtPool` with 4 typed item categories:

| Type | Drawn by | Spatial TTL |
|------|---------|-------------|
| `typing_reaction` | active chat timer | Yes — screen-specific |
| `observation` | boredom timer | Yes — context_hash pinned |
| `intel_roast` | randomly | No — always valid |
| `idle_thought` | boredom timer | No — always valid |

- **Size:** 20 items max, threshold 5, refill batch 5
- **Seeded:** 15 hardcoded Kenny typing reactions on boot
- **Priority-weighted** random draw (fresh items start at 3-5)
- **Decay:** priority -1 every 120s (min 1)
- **Spatial TTL:** items with mismatched `context_hash` discarded after 3 stale draws
- **Persistence:** `data/.daemon_response_cache.json`, 7-day TTL cleanup on load
- **Two-stage refill:** Stage 1 MCP investigation → Stage 2 Mixed-Bag JSON generation

---

## 5. FSM State Machine (15 States)

```
Priority (highest = 1):
  1. DRAGGED       → User dragging
  2. FALLING       → Physics falling
  3. CHASE         → Cursor chase
  4. HYPER         → APM > 150 sustained
  5. THINKING      → User query in progress
  6. CELEBRATE     → Build success
  7. DEVASTATED    → Build fail / fresh login
  8. SHAKING       → 2s duration, auto-exit
  9. BOUNCING      → 3s duration, auto-exit
 10. SPINNING      → 1.5s duration, auto-exit
 11. LOOK_AWAY     → 4s duration, auto-exit
 12. AUTONOMOUS_THINKING → Internal processing
 13. PERIMETER     → Screen edge patrol (counter-clockwise)
 14. SLEEP         → 300s idle
 15. IDLE          → Default
```

- THINKING overrides CHASE and HYPER (user-initiated queries)
- CELEBRATE/DEVASTATED interrupted only by DRAGGED/FALLING/THINKING
- SHAKE/BOUNCE/SPIN/LOOK_AWAY are duration-based — auto-exit after N ms

---

## 6. MCP Server (In-Process, Port 4097)

### 6.1 Architecture

```
HTTP Server (daemon thread) + JSON-RPC 2.0 + SSE
  → FSMActionBridge (pyqtSignal, no mutex — QueuedConnection handles threading)
  → PetWindow._on_mcp_fsm_action() dispatches to PetFSM.transition_to()
```

### 6.2 Tools

| Tool | Input | Output |
|------|-------|--------|
| `change_visual_state` | action (11 states), target_x?, target_y? | ok |
| `read_clipboard` | — | Clipboard text |
| `capture_blackmail_evidence` | — | saves to data/blackmail/ |
| `send_system_toast` | title, message | Windows toast |
| `list_directory` | relative_path | JSON file listing |
| `read_file` | file_path, start_line?, end_line? | File content (max 500 lines) |
| `search_codebase` | search_term (regex) | file:line:snippet results |
| `get_memory` | key? | All facts or specific fact value |
| `get_diary` | limit? | Recent diary entry texts |
| `simulate_keystroke` | keys (max 50 chars) | HID injection — type text on user keyboard (consent: keyboard_injection) |
| `move_mouse` | x, y, click? | HID injection — move cursor + optional click (consent: mouse_interference) |
|| `browser_navigation` | url (http/https only) | Open URL in default browser (consent: browser_redirection) | |
|| `set_log_level` | level (DEBUG/INFO/WARNING/ERROR/CRITICAL) | Change root logger level at runtime |

### 6.3 Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/sse` | GET | SSE stream for real-time MCP events |
| `/health` | GET | Returns `{"status": "ok"}` (used by 10s health timer) |
| `/metrics` | GET | Prometheus `generate_latest()` text format (JSON fallback) |
| `/log` | POST | Accepts `{service, level, message, extra?}` — external logging ingestion |

### 6.4 Security

- `_validate_mcp_path()` blocks path traversal
- `_validate_read_extension()` → only .py/.md/.json/.ps1/.txt/.log/.yaml
- `is_safe_write_path()` → ONLY `data/` allowed for writes
- Server runs in SAME process as PetWindow (no separate auth)

---

## 7. End-to-End Data Flow

```
USER INPUT (double-click + type)
       ↓
  PetWindow._on_input_submitted()
       ↓
  _dispatch_trigger(mode="user_input", ...)
       ↓
  ContextManager.build_user_trigger() → minimal prompt
       ↓
  OpencodeWorker(prompt=..., session_id=...)
       ↓
  POST /session/{id}/message + STRUCTURED_SCHEMA
       ↓
  OpenCode Server (has SKILL.md natively loaded)
       ↓
  LLM calls MCP tools (change_visual_state, etc.)
       ↓
  LLM returns JSON array: [{thought, dialogue, brain_update?}]
       ↓
  OpencodeWorker.response_ready → PetWindow._on_response_ready()
       ↓
  _dispatch_structured() → shows bubble, logs thought, updates history
       ↓
  brain_update → MemoryManager.update_brain() → Firestore
       ↓
  Memory.remember() → WriteCoalescer.mark_dirty("memory")


AUTONOMOUS TICK (master_tick)
       ↓
  _trigger_chat() / _trigger_joke() / _trigger_boredom_fsm()
       ↓
  ResponseManager.draw(pool) → local cache hit?
       ↓ YES: _dispatch_structured() → instant bubble, NO API CALL
       ↓ NO:  TriggerCoalescer.request(mode) → 2.5s batch window
       ↓
  _dispatch_multiplexed(modes) → single OpencodeWorker
       ↓
  _on_structured_multiplexed() → first shown, rest cached
```

---

## 8. Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| **3-tier memory (Firestore → Bridge → Local)** | Offline-first, fast reads, durable writes, graceful degradation |
| **WriteCoalescer (8s batch + atomic)** | Prevents disk thrashing during high-frequency autonomous chatter |
| **Native OpenCode skill loading** | No prompt inlining; skill always available; versioned with code |
| **Structured JSON output (schema)** | Eliminates parsing errors; strict contract; no markdown cleanup |
| **Two-stage agentic refill** | Stage 1 MCP investigation (no schema) → Stage 2 generation (strict JSON); fixes fake-agency hallucination |
| **MCP tools for FSM + surveillance** | LLM controls physical animations; EmotionAnimator controls colors/particles autonomously |
| **Unified ThoughtPool + spatial TTL** | Single pool with type filtering; screen-pinned items discard on context change |
| **Profanity parameter** | Runtime `full`/`moderate`/`sfw` injected per trigger; SKILL.md enforces SFW swap rules |
| **Locked brain fields** | 9 fields (identity/persona) rejected by `apply_brain_update()` — LLM cannot overwrite identity |
| **Consent matrix (7 tiers)** | Chaos tools (keyboard/mouse/browser/clipboard) gated; -32001 on violation |
| **Engagement tracker + backoff** | Adaptive silence prevents annoyance; 5 silent → exponential (max 120s) |
| **PID lock + crash recovery hook** | Single instance per pet_id; flush on crash; .bak fallback on corrupt reads |
| **Firebase Auth REST (no Admin SDK)** | Works in PyInstaller --onefile; per-user isolation via Security Rules |
| **EmotionProfile registry (Phase 46)** | Declarative dataclass replaces procedural if/elif; 9 profiles with Juice enhancements (heart pupils, comet trails, elastic pop) |
| **CorrelationIdDefault formatter (Phase 56)** | Subclass of `logging.Formatter` injects correlation_id from `contextvars` into every log record — no filter needed, no KeyError on unset cids |
| **Correlation IDs on triggers** | `set_correlation_id()` called at entry point of every user input and autonomous trigger — end-to-end traceability through logs |
| **Structlog JSON (opt-in)** | `json_output: true` in config produces NDJSON with correlation_id, timestamp, module, level — ready for ELK/Loki |

---

## 9. Optimization Notes

### Already Implemented

- **Token savings**: ~2500 tokens per injection (one-time) → ~50 tokens per trigger (~95%)
- **Cache-first**: Response pools eliminate API calls for 60%+ of autonomous chatter
- **Trigger coalescing**: Multiple autonomous triggers → single API call
- **Write coalescing**: All local storage writes batched to 8s intervals
- **Adaptive backoff**: Exponential silence detection prevents spamming

### Areas to Monitor

- **Session staleness**: 15min heartbeat re-injects if context lost
- **Pool decay**: 2-min priority decay ensures fresh content gets displayed
- **Diary deduplication**: Content-hash on sync prevents duplicates
- **Crash recovery**: sys.excepthook → flush() + .bak fallback on corrupt files

### Recommended Improvements

| Area | Current | Suggested |
|------|---------|-----------|
| **PetWindow** | ~1756 lines, single class | Split into PetWindowCore, PetWindowBehavior, PetWindowOpencode, PetWindowStorage |
| **MCP tools** | 12 tools | Add `get_fsm_state` for LLM state awareness |
| **TTS** | edge_tts primary + pyttsx3 fallback | Improve pitch-shift quality; reduce temp file I/O |
| **Screen reading** | UIA + WM_GETTEXT | Add OCR fallback for non-text apps (games, terminals) |
| **Codebase map** | Blocks startup (AST parse) | Background generation with file mtime cache |
| **SKILL.md profanity** | Level injected per trigger | Persist user preference in `daemon_config.json` consent section |

---

## 10. File Map

```
daemon.py                              # Entry point, PID lock, crash hook, auth gate
src/
  constants.py                         # All tunable values
  brain_schema.py                      # 22-field brain schema + DEFAULT_BRAIN
  pet_fsm.py                           # 15-state PetFSM, FSMContext dataclass
  pet_renderer.py                      # Stateless QPainter renderer
  pet_window.py                        # Main window, all wiring (1756 lines, ~77KB)
  click_through.py                     # Win32 WS_EX_TRANSPARENT toggle
  apm_worker.py                        # pynput APM tracking QThread
  typing_buffer.py                     # pynput keystroke capture, deque ring buffer
  opencode_worker.py                   # opencode serve HTTP client QThread
  context_manager.py                   # Minimal trigger prompt builder
  response_manager.py                  # Multi-pool response cache
  memory.py                            # Local JSON key-value fact store
  history.py                           # Local JSON conversation log
  diary_store.py                       # Atomic local diary I/O with .bak
  memory_manager.py                    # Firebase bridge (brain + diary sync)
  firebase_crud.py                     # Generic Firestore wrapper, 3-attempt retry
  firebase_auth.py                     # Firebase Auth REST API
  write_coalescer.py                   # QTimer-based batched flush (8s)
  fsm_bridge.py                        # pyqtSignal relay for MCP → Qt thread
  mcp_server.py                        # In-process JSON-RPC 2.0 MCP server
  screen_reader.py                     # UIA text extraction via comtypes
  tts_worker.py                        # pyttsx3 + pitch shift + winsound playback
  animator.py                          # EmotionAnimator, ParticleSystem — 9 emotions, body color, transform, particles
  response_pool.py                     # ThoughtPool(QObject) — priority-weighted draw, spatial TTL, decay, type filtering
  thought_log_dialog.py                # ThoughtLogDialog(QDialog) — Matrix-style monologue viewer, 1s auto-refresh
  system_dialogs.json                  # 21 pre-baked Kenny system event responses
  settings_dialog.py                   # Settings sliders (scale/opacity/speed/voice)
  login_dialog.py                      # Persona-infused auth modal
  context_menu.py                      # Right-click menu (6 actions)
  active_window.py                     # Win32 foreground window title
  persistence.py                       # save_state/load_state
  config.py                            # data/.daemon_config.json loader
  logging_setup.py                     # RotatingFileHandler + CorrelationIdDefault + structlog JSON (opt-in)
  log_context.py                       # CorrelationIdDefault formatter, contextvars-based correlations
  opencode_serve_manager.py            # Auto-start opencode serve on boot
  utils/
    security.py                        # is_safe_write_path() sandbox
scripts/
  generate_ast_map.py                  # AST codebase map generator
.opencode/
  skills/kenny/SKILL.md                # Kenny persona + action matrix + output contract
data/                                  # All local storage (gitignored)
tests/                                 # ~450+ tests across 49 test files
```
