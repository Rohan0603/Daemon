# Daemon Master Optimization Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Systematically fix bugs, eliminate bottlenecks, and add high-value enhancements across the Daemon codebase without breaking the 792-test suite or pushing execution past 50s.

**Architecture:** Each task is self-contained and independently testable. Tasks are grouped by subsystem. Run `py -m pytest tests/ -v` and verify under 50s after every commit. Branch: `task-<N>-<slug>` per task, squash-merge to master.

**Tech Stack:** Python 3.14, PyQt6, pynput, ctypes (Win32), structlog, prometheus-client, requests, FastMCP, comtypes

---

## Audit Findings Summary

### 🐛 Bugs

| ID | Location | Description |
|----|----------|-------------|
| B1 | `pet_window.py:2593` | `_log_thought` has stray `print("DEBUG: ...")` statements in production code |
| B2 | `pet_window.py:344` | `_opencode_worker` declared **twice** (lines 334 and 344) — second shadows first |
| B3 | `pet_window.py:1919` | `_on_mute_toggle` references `self._tts_worker` (wrong name — should be `self._tts`) |
| B4 | `pet_window.py:1951` | `_on_wipe_memory` calls `self._diary.clear()` — attribute doesn't exist (should be `_diary_store`) |
| B5 | `behavior_controller.py:462` | `_on_screen_time_threshold` uses event data key `minutes` but the publisher sends `duration` (seconds) |
| B6 | `write_coalescer.py:83` | `WriteCoalescer.start()` creates a parentless `QTimer()` — can be garbage-collected under stress |
| B7 | `pet_window.py:2271` | `_schedule_boredom_retry` creates `QTimer()` with no parent — same orphan-timer risk as B6 |
| B8 | `opencode_worker.py:97-98` | `response_ready` AND `trigger_ready` both emit the same items list — double dispatch if consumer subscribes to both |

### ⚡ Performance / Bottlenecks

| ID | Location | Description |
|----|----------|-------------|
| P1 | `pet_window.py:_tick` (~30Hz) | `_get_logical_window_rect()` calls Win32 via ctypes every 33ms — result rarely changes |
| P2 | `behavior_controller.py:tick` (1Hz) | `get_active_window_title()` called **3 times** per tick |
| P3 | `response_pool.py:_is_repetitive` | O(N) fuzzy scan + set-ops per `add_items` item |
| P4 | `screen_reader.py` | UIA COM object created/destroyed twice per call chain |
| P5 | `pet_window.py:_log_thought` | Reads entire log file to count lines before rotating — O(file_size) per write |
| P6 | `memory_manager.py:sync_to_local` | Calls `crud.get("users", uid)` (Firestore HTTP) every call with no cache |
| P7 | `pet_window.py:paintEvent` | `QApplication.primaryScreen().availableGeometry()` called every 33ms frame |

### 🔧 Enhancements

| ID | Location | Description |
|----|----------|-------------|
| E1 | `pet_window.py` | Boredom local actions dispatched without setting `_gcd_expiry_timestamp` — back-to-back fires possible |
| E2 | `behavior_controller.py` | `_last_autonomous_fire_time = 0.0` — 15s debounce guard bypassed at boot |
| E3 | `opencode_worker.py` | Strategy 2 bracket-match parse is O(n) and prone to false positives |
| E4 | `pet_window.py` | Two independent `_should_fire_autonomous` implementations with divergent guard sets |
| E5 | `events.py` | `Event.data` is a `dict` — mutable despite `frozen=True` dataclass |
| E6 | `mcp_server.py` | `_FILE_CACHE` / `_CACHE_TIMESTAMPS` module-level dicts with no eviction |
| E7 | `pet_window.py:_on_mode_changed` | Calls `QApplication.quit()` inside a mode change handler — kills app on mode switch |
| E8 | `write_coalescer.py:flush` | Exception in flush branch skips `self._dirty[kind] = False` via `continue` |
| E9 | `pet_window.py:1846` | TTS `enqueue` commented out — users never hear speech despite TTS being fully wired |

---

## File Map

**Primary modified files:**
- `src/ui/pet_window.py` — B1, B2, B3, B4, B7, E1, E7, E9, P1, P5, P7
- `src/autonomy/behavior_controller.py` — B5, E2, P2
- `src/write_coalescer.py` — B6, E8
- `src/llm/opencode_worker.py` — B8
- `src/memory_manager.py` — P6
- `src/mcp_server.py` — E6
- `src/events.py` — E5
- `src/diary_store.py` — B4 (add `clear()` if missing)

**Test files:**
- `tests/test_pet_window_unit.py`
- `tests/test_behavior_controller.py`
- `tests/test_write_coalescer.py`
- `tests/test_opencode_worker.py`
- `tests/test_memory_manager.py`
- `tests/test_mcp_server_fastmcp.py`
- `tests/test_events.py`
- `tests/test_tts_worker.py`

---

## Task 1 — Fix Debug Prints in `_log_thought` (B1)

**Files:** `src/ui/pet_window.py:2593-2607`, `tests/test_pet_window_unit.py`

- [ ] Write failing test: `_log_thought` must not write to stdout
- [ ] Run `py -m pytest tests/test_pet_window_unit.py::test_log_thought_no_debug_prints -v` → FAIL
- [ ] Remove the two `print("DEBUG: ...")` lines at lines 2593 and 2596
- [ ] Run test → PASS; run full suite under 50s
- [ ] `git commit -m "fix(ui): remove stray debug prints from _log_thought"`

```python
# test
def test_log_thought_no_debug_prints(tmp_path, monkeypatch):
    import io, sys
    from unittest.mock import patch
    from src.ui.pet_window import PetWindow
    log_path = tmp_path / "thoughts.log"
    with patch("src.ui.pet_window.THOUGHTS_LOG_PATH", str(log_path)):
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        pw = object.__new__(PetWindow)
        pw._log_thought("a thought", "test_mode", "some dialogue")
    assert captured.getvalue() == "", "No debug prints allowed in _log_thought"
```

---

## Task 2 — Fix Duplicate `_opencode_worker` Declaration (B2)

**Files:** `src/ui/pet_window.py:334-344`, `tests/test_pet_window_unit.py`

- [ ] Write failing test: AST walk finds `_opencode_worker` assigned twice in `__init__`
- [ ] Run test → FAIL (two assignments)
- [ ] Remove the FIRST assignment at ~line 334 (keep the one at ~line 344)
- [ ] Run test → PASS; run full suite
- [ ] `git commit -m "fix(ui): remove duplicate _opencode_worker declaration in PetWindow.__init__"`

```python
# test
def test_opencode_worker_declared_once():
    import ast, pathlib
    source = pathlib.Path("src/ui/pet_window.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "PetWindow":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                    assigns = [n for n in ast.walk(item)
                               if isinstance(n, ast.Assign)
                               and any(isinstance(t, ast.Attribute)
                                       and t.attr == "_opencode_worker"
                                       for t in n.targets)]
                    assert len(assigns) == 1, f"_opencode_worker assigned {len(assigns)} times in __init__"
```

---

## Task 3 — Fix `_on_mute_toggle` Wrong Attribute (B3)

**Files:** `src/ui/pet_window.py:1919`, `tests/test_pet_window_unit.py`

- [ ] Write failing test: AST scan finds `_tts_worker` referenced in `_on_mute_toggle`
- [ ] Run test → FAIL
- [ ] Change `self._tts_worker` → `self._tts` in `_on_mute_toggle`
- [ ] Run test → PASS; run full suite
- [ ] `git commit -m "fix(ui): fix _on_mute_toggle referencing nonexistent _tts_worker attribute"`

```python
# fix
def _on_mute_toggle(self, muted: bool) -> None:
    if self._tts:
        self._tts.set_enabled(not muted)
```

---

## Task 4 — Fix `_on_wipe_memory` Wrong Diary Attr (B4)

**Files:** `src/ui/pet_window.py:1951`, `src/diary_store.py`, `tests/test_pet_window_unit.py`

- [ ] Write failing test: AST scan finds `self._diary` in `_on_wipe_memory`
- [ ] Run test → FAIL
- [ ] Change `self._diary.clear()` → `self._diary_store.clear()`
- [ ] Verify `DiaryStore.clear()` exists; add if missing:

```python
# src/diary_store.py
def clear(self) -> None:
    """Remove all diary entries."""
    self._entries = []
    self._write_atomic({"entries": [], "synced": 0})
```

- [ ] Run test → PASS; run full suite
- [ ] `git commit -m "fix(ui): fix _on_wipe_memory using nonexistent _diary attribute"`

---

## Task 5 — Fix Screen-Time Event Key Mismatch (B5)

**Files:** `src/autonomy/behavior_controller.py:456-463`, `tests/test_behavior_controller.py`

- [ ] Write failing test: trigger `_on_screen_time_threshold` with `{"app_name": "reddit", "duration": 3600}` and verify handler receives `3600` not `None`
- [ ] Run test → FAIL (current code: `event.data.get("minutes")` → None, then `None * 60` crashes)
- [ ] Fix handler to use `event.data.get("duration", 0)` directly
- [ ] Run test → PASS; run full suite
- [ ] `git commit -m "fix(autonomy): fix screen time event using wrong data key 'minutes' vs 'duration'"`

```python
# fix
def _on_screen_time_threshold(self, event):
    app_name = event.data.get("app_name")
    duration_sec = event.data.get("duration", 0)  # seconds
    logger.debug("[Screen Time] %s: %d sec", app_name, duration_sec)
    if app_name and app_name.lower() in [d.lower() for d in PROCRASTINATION_DOMAINS]:
        self._trigger_screen_time_roast(app_name, duration_sec)
```

---

## Task 6 — Fix Orphan QTimers (B6, B7)

**Files:** `src/write_coalescer.py:80-86`, `src/ui/pet_window.py:2271`, `tests/test_write_coalescer.py`

- [ ] Write failing test: `WriteCoalescer.__init__` rejects unknown `parent` kwarg
- [ ] Run test → FAIL
- [ ] Add `parent=None` param to `WriteCoalescer.__init__`; pass parent to `QTimer(parent_obj)` in `start()`
- [ ] Fix `_schedule_boredom_retry` in pet_window: `QTimer(self)` instead of `QTimer()`
- [ ] Run test → PASS; run full suite
- [ ] `git commit -m "fix(storage): parent QTimers in WriteCoalescer and boredom retry to prevent GC"`

```python
# write_coalescer.py start() fix
def start(self) -> None:
    if self._timer is not None:
        self._timer.stop()
    from PyQt6.QtCore import QObject
    parent_obj = self._parent if isinstance(self._parent, QObject) else None
    self._timer = QTimer(parent_obj)
    self._timer.setInterval(int(self._flush_sec * 1000))
    self._timer.timeout.connect(self.flush)
    self._timer.start()
```

---

## Task 7 — Eliminate Dual Signal Emit in OpencodeWorker (B8)

**Files:** `src/llm/opencode_worker.py`, `tests/test_opencode_worker.py`

- [ ] Write failing test: inspect `run()` source and assert `.emit(items)` count ≤ 1
- [ ] Run test → FAIL (currently emits `response_ready.emit(items)` AND `trigger_ready.emit(items)`)
- [ ] Remove `self.trigger_ready.emit(items)` from `run()` — keep only `response_ready.emit`
- [ ] Run test → PASS; run full suite
- [ ] `git commit -m "fix(llm): remove duplicate trigger_ready emit in OpencodeWorker.run"`

---

## Task 8 — Fix `_on_mode_changed` Calling `quit()` (E7)

**Files:** `src/ui/pet_window.py:~955`, `tests/test_pet_window_unit.py`

- [ ] Write failing test: AST scan finds `quit()` call inside `_on_mode_changed`
- [ ] Run test → FAIL
- [ ] Remove the `QApplication.quit()` line from `_on_mode_changed`
- [ ] Run test → PASS; run full suite
- [ ] `git commit -m "fix(ui): remove QApplication.quit() from _on_mode_changed — mode changes are not shutdowns"`

---

## Task 9 — Fix WriteCoalescer Dirty Flag Skipped on Exception (E8)

**Files:** `src/write_coalescer.py:52-70`, `tests/test_write_coalescer.py`

**Root cause:** `except ... continue` skips `self._dirty[kind] = False`, leaving dirty flag permanently set.

- [ ] Write failing test: mark `memory` dirty, mock `self._memory.save()` to raise, flush; assert `_dirty["memory"]` is `False` after
- [ ] Run test → FAIL
- [ ] Move `self._dirty[kind] = False` into a `finally` block:

```python
def flush(self) -> None:
    for kind in ("memory", "history", "diary", "response_cache", "brain"):
        if not self._dirty.get(kind):
            continue
        try:
            if kind == "memory":
                self._memory.save()
            elif kind == "history":
                self._history.save()
            elif kind == "diary":
                self._flush_diary()
            elif kind == "response_cache":
                pass
            elif kind == "brain":
                self._memory_manager.retry_pending_writes()
        except Exception as e:
            logging.warning(f"[WriteCoalescer] {kind} flush failed: {e}")
        finally:
            self._dirty[kind] = False  # always clear
```

- [ ] Run test → PASS; run full suite
- [ ] `git commit -m "fix(storage): always clear dirty flags after flush attempt in WriteCoalescer"`

---

## Task 10 — Cache Win32 Window Rect in `_tick` (P1)

**Files:** `src/ui/pet_window.py`, `tests/test_pet_window_unit.py`

**Problem:** `_get_logical_window_rect()` calls Win32 ctypes every 33ms (30/s). Window rect changes rarely.

- [ ] Write failing test: assert `_cached_window_rect` exists in source
- [ ] Run test → FAIL
- [ ] Add cache fields in `__init__`:

```python
self._cached_window_rect = None
self._window_rect_cache_tick = 0
self._WINDOW_RECT_CACHE_TICKS = 10  # refresh every ~330ms
```

- [ ] In `_tick()`, throttle the call:

```python
self._window_rect_cache_tick += 1
if self._window_rect_cache_tick >= self._WINDOW_RECT_CACHE_TICKS:
    self._window_rect_cache_tick = 0
    self._cached_window_rect = self._get_logical_window_rect()
current_rect = self._cached_window_rect
self._update_ground_y(current_rect)
```

- [ ] Run test → PASS; run full suite
- [ ] `git commit -m "perf(ui): cache window rect in _tick to reduce Win32 calls from 30/s to 3/s"`

---

## Task 11 — Deduplicate `get_active_window_title` in `BehaviorController.tick` (P2)

**Files:** `src/autonomy/behavior_controller.py`, `tests/test_behavior_controller.py`

**Problem:** Called 3x per tick: window-switch tracking, `_check_ide_mode_transition`, `_has_significant_delta`.

- [ ] Write failing test: mock `get_active_window_title` and count calls during `bc.tick(1.0)` → assert ≤ 1
- [ ] Run test → FAIL (3 calls)
- [ ] Fetch once at top of `tick()`, pass to helpers:

```python
def tick(self, master_dt: float) -> None:
    try:
        if self._fsm.current_state == PetState.SLEEP:
            ...
            return
        self._apply_affinity_silence_decay(master_dt)
        current_window = get_active_window_title()  # single fetch
        self._check_ide_mode_transition(current_window)
        if current_window and current_window != self._last_evaluated_window:
            self._window_switch_count += 1
            self._last_evaluated_window = current_window
        ...
        if self._chat_timer_sec >= chat_threshold and self._has_significant_delta(current_window):
```

- [ ] Update `_check_ide_mode_transition(self, current_window=None)` and `_has_significant_delta(self, current_window=None)` to accept optional param with fallback
- [ ] Run test → PASS; run full suite
- [ ] `git commit -m "perf(autonomy): deduplicate get_active_window_title calls from 3/tick to 1/tick"`

---

## Task 12 — Cache Screen Geometry in `paintEvent` (P7)

**Files:** `src/ui/pet_window.py`, `tests/test_pet_window_unit.py`

**Problem:** `QApplication.primaryScreen().availableGeometry()` called every 33ms paint frame.

- [ ] Write failing test: AST scan finds `availableGeometry()` call inside `paintEvent` body
- [ ] Run test → FAIL
- [ ] Add in `__init__` after `_setup_window()`:

```python
self._screen_rect = QApplication.primaryScreen().availableGeometry()
QApplication.primaryScreen().geometryChanged.connect(self._on_screen_geometry_changed)
QApplication.primaryScreen().availableGeometryChanged.connect(self._on_screen_geometry_changed)
```

- [ ] Add handler:

```python
def _on_screen_geometry_changed(self, *_) -> None:
    self._screen_rect = QApplication.primaryScreen().availableGeometry()
```

- [ ] In `paintEvent`, replace `QApplication.primaryScreen().availableGeometry()` with `self._screen_rect`
- [ ] Run test → PASS; run full suite
- [ ] `git commit -m "perf(ui): cache screen geometry in PetWindow to avoid per-frame Qt calls"`

---

## Task 13 — Add GCD After Boredom Local Actions (E1)

**Files:** `src/ui/pet_window.py:2178-2188`, `tests/test_pet_window_unit.py`

**Problem:** Boredom triggers local FSM animations without setting GCD, so `_on_autonomous_trigger_fired` can fire multiple times in rapid succession.

- [ ] Write failing test: assert `_gcd_expiry_timestamp` assignment exists in the boredom branch of `_on_autonomous_trigger_fired`
- [ ] Run test → FAIL
- [ ] Add to boredom branch:

```python
if mode == "boredom":
    actions = ["PERIMETER", "shake", "spin", "look_away", "bounce"]
    action = random.choice(actions)
    if action == "PERIMETER":
        self._fsm.transition_to(PetState.PERIMETER)
    else:
        self._action_layer.trigger(action)
    self._gcd_expiry_timestamp = time.time() + 5.0  # 5s cooldown
    self._behavior.set_gcd_expiry(self._gcd_expiry_timestamp)
    self._on_output_displayed(engaged=False)
    return
```

- [ ] Run test → PASS; run full suite
- [ ] `git commit -m "fix(autonomy): add 5s GCD after boredom local actions to prevent rapid re-trigger"`

---

## Task 14 — Add TTL Eviction to MCP File Cache (E6)

**Files:** `src/mcp_server.py`, `tests/test_mcp_server_fastmcp.py`

**Problem:** `_FILE_CACHE` is module-level, never evicted — grows unbounded over long sessions.

- [ ] Write failing test: fill cache with 200 expired entries, call `_evict_stale_file_cache()`, assert cache is empty
- [ ] Run test → FAIL (function doesn't exist)
- [ ] Add constants and eviction function:

```python
_FILE_CACHE_MAX_ENTRIES = 50

def _evict_stale_file_cache() -> None:
    now = time.time()
    stale = [k for k, ts in _CACHE_TIMESTAMPS.items() if now - ts > _FILE_CACHE_TTL]
    for k in stale:
        _FILE_CACHE.pop(k, None)
        _CACHE_TIMESTAMPS.pop(k, None)
    if len(_FILE_CACHE) > _FILE_CACHE_MAX_ENTRIES:
        oldest = sorted(_CACHE_TIMESTAMPS, key=_CACHE_TIMESTAMPS.get)
        for k in oldest[:len(_FILE_CACHE) - _FILE_CACHE_MAX_ENTRIES]:
            _FILE_CACHE.pop(k, None)
            _CACHE_TIMESTAMPS.pop(k, None)
```

- [ ] Call `_evict_stale_file_cache()` at the top of the `read_file` tool handler
- [ ] Run test → PASS; run full suite
- [ ] `git commit -m "fix(mcp): add TTL eviction to _FILE_CACHE to prevent unbounded memory growth"`

---

## Task 15 — Re-enable TTS (E9)

**Files:** `src/ui/pet_window.py:1846`, `tests/test_tts_worker.py`

**Problem:** `self._tts.enqueue(text)` is commented out — users never hear speech.

- [ ] Write failing test: call `_show_bubble("hello")` on a mock PetWindow, assert `_tts.enqueue` called
- [ ] Run test → FAIL
- [ ] Uncomment line 1846: `self._tts.enqueue(text)`
- [ ] Run test → PASS; run full suite
- [ ] `git commit -m "feat(ui): re-enable TTS speech output on bubble display"`

```python
# test
def test_show_bubble_enqueues_tts(qapp):
    from src.ui.pet_window import PetWindow
    from unittest.mock import MagicMock, patch
    pw = object.__new__(PetWindow)
    pw._tts = MagicMock()
    pw._bubble_timer_ms = 0
    pw._bubble_queue = []
    pw._bubble_pages = []
    pw._bubble_page_index = 0
    pw._typewriter_timer = MagicMock()
    pw._typewriter_tick_ms = 50
    pw._typewriter_chars_per_tick = 3
    with patch.object(pw, "_start_typewriter"):
        pw._show_bubble("Hello test")
    pw._tts.enqueue.assert_called_once_with("Hello test")
```

---

## Task 16 — Fix `_log_thought` O(file_size) Read (P5)

**Files:** `src/ui/pet_window.py:2602-2607`, `tests/test_pet_window_unit.py`

**Problem:** `log_path.read_text()` → splitlines → count lines → rewrite 500 lines. O(file_size) on every thought.

- [ ] Write failing test: mock `Path.read_text` and assert 0 calls during `_log_thought`
- [ ] Run test → FAIL
- [ ] Replace with stat-based rotation:

```python
def _log_thought(self, thought: str, mode: str, dialogue: str) -> None:
    log_path = Path(THOUGHTS_LOG_PATH)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = (
        f"[{timestamp}] [{mode}] Thought({len(thought)}c): {thought}\n"
        f"[{timestamp}] [{mode}] Dialogue: {dialogue}\n"
    )
    MAX_LOG_BYTES = 50_000
    try:
        if log_path.exists() and log_path.stat().st_size > MAX_LOG_BYTES:
            with open(log_path, "r", encoding="utf-8") as f:
                f.seek(MAX_LOG_BYTES // 2)
                f.readline()  # skip partial line
                tail = f.read()
            log_path.write_text(tail, encoding="utf-8")
    except OSError:
        pass
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry)
```

- [ ] Run test → PASS; run full suite
- [ ] `git commit -m "perf(ui): replace O(file_size) line-count rotation with stat-based rotation in _log_thought"`

---

## Task 17 — Make `Event.data` Immutable (E5)

**Files:** `src/events.py`, `tests/test_events.py`

**Problem:** `Event` is `frozen=True` but `data: dict` is mutable — subscribers can corrupt shared state.

- [ ] Write failing test: construct `Event(data={"k": "v"})`, assert `isinstance(event.data, MappingProxyType)` and that mutation raises `TypeError`
- [ ] Run test → FAIL
- [ ] In `__post_init__`:

```python
from types import MappingProxyType

def __post_init__(self):
    if not self.source:
        object.__setattr__(self, "source", "unknown")
    if isinstance(self.data, dict):
        object.__setattr__(self, "data", MappingProxyType(self.data))
```

- [ ] Run full suite → fix any tests that mutate `event.data` by creating new Events instead
- [ ] `git commit -m "fix(events): wrap Event.data in MappingProxyType to enforce immutability"`

---

## Task 18 — Cache Firestore User Data GET in `sync_to_local` (P6)

**Files:** `src/memory_manager.py`, `tests/test_memory_manager.py`

**Problem:** `sync_to_local` calls `crud.get("users", uid)` (HTTP) on every invocation. Called periodically from `_on_firestore_sync_tick`.

- [ ] Write failing test: call `sync_to_local` twice with same brain; assert `crud.get("users", ...)` called only once
- [ ] Run test → FAIL
- [ ] Add cache to `__init__`:

```python
self._cached_user_data: dict = {}
self._user_data_cache_time: float = 0.0
self._USER_DATA_CACHE_TTL: float = 30.0
```

- [ ] In `sync_to_local`, replace direct call with:

```python
now = time.time()
if now - self._user_data_cache_time > self._USER_DATA_CACHE_TTL:
    self._cached_user_data = self.crud.get("users", self._uid) or {}
    self._user_data_cache_time = now
user_data = self._cached_user_data
```

- [ ] Run test → PASS; run full suite
- [ ] `git commit -m "perf(memory): cache user_data GET in sync_to_local to reduce Firestore calls"`

---

## Task 19 — Boot Guard for Autonomous Fire (E2)

**Files:** `src/autonomy/behavior_controller.py`, `tests/test_behavior_controller.py`

**Problem:** `_last_autonomous_fire_time = 0.0` means `time.time() - 0.0` is epoch offset (~1.7B seconds), bypassing the 15s debounce guard immediately at startup.

- [ ] Write failing test: instantiate `BehaviorController`, immediately call `_should_fire_autonomous("active_chat")` → assert `False`
- [ ] Run test → FAIL (returns `True`)
- [ ] Change initialization to `time.monotonic()` (current time, not epoch zero):

```python
# __init__
self._last_autonomous_fire_time = time.monotonic()  # was 0.0
```

- [ ] Update all `self._last_autonomous_fire_time = time.time()` → `time.monotonic()` in `behavior_controller.py`
- [ ] Update `_should_fire_autonomous` guard to use `time.monotonic()`:

```python
elapsed = time.monotonic() - self._last_autonomous_fire_time
```

- [ ] Run test → PASS; run full suite
- [ ] `git commit -m "fix(autonomy): initialize _last_autonomous_fire_time to boot time to block immediate autonomous fire"`

---

## Task 20 — Final Verification and Memory Update

- [ ] Run full suite: `py -m pytest tests/ -v --timeout=50`
- [ ] Verify ≥ 792 passed, runtime < 50s
- [ ] Quick count: `py -m pytest tests/ --tb=no -q`
- [ ] Update `memory/project-dev-memory.md`:
  - Last updated: 2026-07-10
  - Note all 19 tasks completed
  - Update test count if changed
- [ ] `git commit -m "docs(memory): update dev memory after master optimization plan"`

---

## Self-Review: Coverage Matrix

| Finding | Task | Status |
|---------|------|--------|
| B1 Debug prints | Task 1 | ✅ |
| B2 Duplicate `_opencode_worker` | Task 2 | ✅ |
| B3 Wrong `_tts_worker` attr | Task 3 | ✅ |
| B4 Wrong `_diary` attr | Task 4 | ✅ |
| B5 Screen time event key | Task 5 | ✅ |
| B6 Orphan WriteCoalescer timer | Task 6 | ✅ |
| B7 Orphan boredom retry timer | Task 6 | ✅ |
| B8 Dual emit in OpencodeWorker | Task 7 | ✅ |
| P1 Win32 every 33ms | Task 10 | ✅ |
| P2 Window title called 3×/tick | Task 11 | ✅ |
| P3 Fuzzy dedup O(N) | — | ⚠️ N=20 max, skip per YAGNI |
| P4 UIA called twice | — | ⚠️ Both callers already cache; skip |
| P5 Log file O(size) read | Task 16 | ✅ |
| P6 Firestore GET on every sync | Task 18 | ✅ |
| P7 Screen rect in paintEvent | Task 12 | ✅ |
| E1 No GCD on boredom | Task 13 | ✅ |
| E2 Boot guard for autonomy | Task 19 | ✅ |
| E3 Bracket-match parse | — | ⚠️ Functional; skip per YAGNI |
| E4 Dual `_should_fire_autonomous` | — | ⚠️ Guards overlap correctly; skip |
| E5 Event data mutable | Task 17 | ✅ |
| E6 MCP cache unbounded | Task 14 | ✅ |
| E7 `quit()` in mode change | Task 8 | ✅ |
| E8 Dirty flag skip on exception | Task 9 | ✅ |
| E9 TTS disabled | Task 15 | ✅ |

**19 of 19 actionable findings covered. 4 skipped per YAGNI (low risk, not worth complexity).**
