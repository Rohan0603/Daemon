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

Transparent always-on-top Windows desktop companion built with PyQt6. Named Daemon. Reacts to system activity, provides floating interface to the `opencode` multi-agent CLI.

**Working directory:** `C:\Users\ponna\Project\Daemon`
**Git root:** `C:\Users\ponna\Project\Daemon`
**Python:** use `py` (not `python` or `python3`) — Windows py launcher
**Tests:** `py -m pytest tests/ -v`
**Stack:** Python 3.11+, PyQt6, pynput, ctypes (Win32), subprocess

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

## File Map

| File | Responsibility |
|------|---------------|
| `src/constants.py` | All tunable values — import from here everywhere |
| `src/pet_fsm.py` | `PetState` enum (15), `FSMContext` dataclass, `PetFSM` — zero Qt imports |
| `src/pet_renderer.py` | Stateless `PetRenderer` — QPainter drawing only |
| `src/click_through.py` | `ClickThroughManager` — Win32 ctypes, 50ms QTimer poll |
| `src/apm_worker.py` | `APMWorker(QThread)` — pynput listeners, rolling APM |
| `src/opencode_worker.py` | `OpencodeWorker(QThread)` — inject_context (noReply) + send_trigger, JSON parsing |
| `src/response_manager.py` | `AutonomousResponseManager` + `ResponsePool` — multi-pool response cache |
| `src/active_window.py` | `get_active_window_title()` — Win32 foreground window title |
| `src/typing_buffer.py` | `TypingBuffer` — pynput keystroke capture, deque ring buffer, text_updated signal |
| `src/context_menu.py` | `PetContextMenu(QMenu)` — 6 actions, build event signals |
| `src/pet_window.py` | `PetWindow(QWidget)` — FSM timer, paintEvent, drag, double-click, TRM owner |
| `src/persistence.py` | `save_state()` / `load_state()` — JSON to `~/.daemon_state.json` |
| `src/memory_manager.py` | `MemoryManager` — Firebase bridge, dual-brain (core_brain + diary), retry queue |
| `src/firebase_crud.py` | `FirebaseCRUD` — generic Firestore wrapper, 3-attempt retry, 6 CRUD verbs |
| `src/brain_schema.py` | Brain schema (26 fields), `apply_brain_update()`, `DEFAULT_BRAIN` |
| `src/diary_store.py` | `DiaryStore` — atomic local diary I/O with .bak backup, 200-entry cap |
| `src/memory.py` | `Memory` — local JSON key-value fact store (constructor accepts `coalescer=`) |
| `src/history.py` | `History` — local JSON conversation log (constructor accepts `coalescer=`) |
| `src/write_coalescer.py` | `WriteCoalescer` — QTimer-based batched flush (default 8s) for memory/history/diary/cache/brain |
| `src/context_manager.py` | `ContextManager` — inject_full/delta/trigger with 15-min heartbeat, re-snapshotting |
| `src/logging_setup.py` | Unified stdlib logging with RotatingFileHandler |
| `src/config.py` | `~/.daemon_config.json` loading |
| `src/opencode_serve_manager.py` | Auto-start `opencode serve` on boot |
| `src/tts_worker.py` | `TTSWorker(QThread)` — edge-tts + pyttsx3 + pitch shift + winsound playback |
| `src/settings_dialog.py` | `SettingsDialog(QDialog)` — size/opacity/speed/voice live-preview sliders |
| `daemon.py` | Entry point — argparse, QApplication, PID lock, clean shutdown |
| `seed_brain.py` | Standalone Firestore seeder — view/merge/seed core_brain document |
| `opencode-query.ps1` | PowerShell script (legacy CLI path, preserved but not called by PetWindow) |
| `assets/daemon-skill.md` | Daemon personality + strict JSON schema — loaded by OpencodeWorker at runtime |
| `tests/` | **432 tests** across 23 test files |

---

## Local Storage Paths

| File | Class | Content |
|------|-------|---------|
| `~/.daemon_memory.json` | `Memory` | User-taught key-value facts; seeded from Firestore core_brain on boot |
| `~/.daemon_history.json` | `History` | Conversation log (last 100 entries) |
| `~/.daemon_response_cache.json` | `ResponseManager` | Pre-fetched LLM response pools (jokes_blackmail + system) |
| `~/.daemon_diary.json` | `DiaryStore` | Diary entries cached locally; synced to Firebase `daemon_diary` on quit |
| `~/.daemon_state.json` | `persistence` | Runtime state (mood, interactions, first_run_done) |
| `~/.daemon_config.json` | `config` | User overrides (model, scale, opacity, speed, voice) |
| `~/.daemon.lock` | PID lock | Single-instance guard |

Firestore is the source of truth. Local files are a fast-access cache during sessions. Boot: Firestore → local. Quit: local pending entries → Firestore.

---

## FSM Priority (highest = 1)

DRAGGED(1) > FALLING(2) > CHASE(3) > HYPER(4) > THINKING(5) > CELEBRATE(6) > DEVASTATED(7) > SHAKING(8) > BOUNCING(9) > SPINNING(10) > AUTONOMOUS_THINKING(11) > LOOK_AWAY(12) > PERIMETER(13) > SLEEP(14) > IDLE(15)

THINKING overrides CHASE and HYPER (user-initiated).
CELEBRATE/DEVASTATED interrupted only by DRAGGED/FALLING/THINKING.
SHAKE/BOUNCE/SPIN/LOOK_AWAY are duration-based — auto-exit after N ms.

---

## Key Pitfalls

| Pitfall | Fix |
|---------|------|
| HWND unavailable at `__init__` | Get `int(self.winId())` in `showEvent` after `show()` |
| Ground includes taskbar | `primaryScreen().availableGeometry().bottom()` |
| HiDPI coords | `availableGeometry()` and `geometry()` return LOGICAL pixels on this Win11/PyQt6 1.25x setup — do NOT divide by `devicePixelRatio()`. Mouse events and `QCursor::pos()` are also logical. |
| Tool window type missing | `FramelessWindowHint \| WindowStaysOnTopHint \| Tool` |
| pynput errors | `try/except` around import and listener start |
| HYPER flash | QTimer at 125ms (8Hz), index cycles 0→3 |
| QThread reuse | Reinstantiate `OpencodeWorker` per query |
| Black console | `creationflags=subprocess.CREATE_NO_WINDOW` |
| opencode hangs | Always pass `opencode -p "..."` (never interactive) |
| opencode markdown | `re.sub(r'[*#\`~_]', '', text)` before bubble display |
| Windows shell/encoding | Run `powershell.exe` with bypass execution policy and force UTF-8 encoding |
| Emoji rendering | Set `$OutputEncoding` and `[Console]::OutputEncoding` to UTF8 in PS, use `font.setFamilies` with `"Segoe UI Emoji"` fallback |
| AUTONOMOUS_THINKING never exits | All three callbacks must clear `_autonomous_query_pending` |
| JSON corrupted by markdown stripper | Parse JSON from raw stdout BEFORE calling `_process_output` |
| Eye pupil drift in rotated states | screen-space atan2 — max 15° mismatch, intentional tradeoff |
| `os.environ.get` mock too broad in tests | Narrow with `side_effect` lambda: `lambda k, *a: "val" if k == "OPENCODE_API_KEY" else os.environ.get(k, *a)` |
| `firebase_admin` duplicate init | Guard with `try: firebase_admin.get_app()` → `except ValueError: firebase_admin.initialize_app(cred)` |
| WriteCoalescer ignores unknown flags | Add new flag to `_dirty` dict before calling `mark_dirty()` |
| Priority decay resets on refill | Fresh LLM items arrive at priority 3-5, replace decayed items via weighted selection |
| Empty pool returns `[]` not `None` | All timer handlers check `if not items: return` |
| Pool item format mismatch | Items need `pool_type` tag for correct routing |
| ContextManager re-snapshot timing | Re-snapshot happens inside `build_prompt()` after building, not after API success |
| Auto-serve port TIME_WAIT | Previous serve exit puts port in TIME_WAIT ~60s. Daemon falls back to CLI during that window |
| Pool sizes (jokes=5, system=2) | Small pools trigger refill more often but keep prompts token-efficient. Thresholds: jokes=3, system=1 |
| PyQt6 signal + list.append | `list.append` can't be a Qt slot; use `lambda: emitted.append(None)` in tests |
| Autonomous signal routing | `is_autonomous=True` + `modes=[...]` → `structured_multiplexed`. No modes → `structured_batch_ready`. Never `structured_ready` for autonomous workers |
| OpencodeWorker as local var GC'd | Store in `self._refill_workers[pool_type]` before `start()`; add `_on_refill_error` cleanup |
| `pet_window.py` imports `apply_brain_update` from wrong module | Import from canonical `src.brain_schema` not `src.memory_manager` |
| Diaries not deduplicated on re-seed | Diary seeded only on `first_run_done=False` AND empty Firebase (no duplicates) |
| Cursor position in scaled/rotated context | Use screen-space `atan2` from eye centre, not body centre |

---

## Running

```powershell
pip install PyQt6 pynput pytest firebase-admin requests
py -m pytest tests/ -v
py daemon.py
py daemon.py --debug       # headless FSM simulation, no display needed
py daemon.py --verbose     # enable [DEBUG] diagnostic logging
py daemon.py --no-opencode # disable opencode integration
```

Progress is tracked in `memory/project-dev-memory.md`. Update it after every task with commit hash, files changed, and any fixes applied.
