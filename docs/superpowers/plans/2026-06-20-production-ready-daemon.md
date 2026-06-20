# Daemon Production-Ready Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Daemon fully production-ready — bug-free, behaviorally polished, LLM-efficient, and transferable as a self-contained `.exe` that any user can install and run on Windows without a Python environment.

**Architecture:** Daemon is a PyQt6 transparent always-on-top Windows desktop pet with a 15-state FSM, emotion engine, MCP server (port 4097), opencode serve bridge (port 4096), Firebase cloud memory, and a plugin system. The pet communicates via opencode's HTTP API using a structured JSON schema for LLM responses. Production packaging uses PyInstaller `--onefile` with a bundled NSIS installer for distribution.

**Tech Stack:** Python 3.11+, PyQt6 6.7+, pynput, edge_tts, pydub, winsound, pyttsx3, structlog, prometheus-client, openai SDK, firebase-admin, comtypes, Pillow, python-dotenv, PyInstaller 6+, NSIS (for installer)

---

## Git Workflow (MANDATORY — enforce on every task)

```bash
# ALWAYS start a task with:
git checkout master
git pull
git checkout -b task-<N>-<slug>

# Commit often on branch, then finish with:
git checkout master
git merge --squash task-<N>-<slug>
git commit -m "feat/fix/refactor: <description>"
git branch -D task-<N>-<slug>
```

- **Never commit directly to master**
- **Never include AI assistant names in commit messages**
- **Run `py -m pytest tests/ -v` before every squash merge — must be green**

---

## Brainstorm Insights (Key Decisions)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Packaging | PyInstaller --onefile + NSIS installer | opencode CLI is Node.js — can't bundle; installer handles pre-flight |
| LLM sessions | Keep autonomous=None, add shared refill session | User session stays clean; refill pool reuses one session |
| Pet window refactor | No full split — targeted extractions only | 2306 lines but extraction already in progress; full split = high risk |
| FSM spam | Add transition dedup guard in logging only | Don't throttle real transitions, just suppress repeated log lines |
| Bubble length | Truncate at render-time; enforce in prompt | LLM sometimes returns >150 chars despite maxLength:150 in schema |
| TTL purge | Increase default from 300s to 600s | 300s too aggressive — items are still relevant for 10min sessions |
| Shutdown timeout | Cap session summary generation at 10s | 3min shutdown is unacceptable; summary is best-effort |

---

## File Map (Files Created or Modified Per Task)

| Task | Files Touched |
|------|--------------|
| T1 (FSM spam + log dedup) | `src/pet_window.py`, `tests/test_pet_window.py` |
| T2 (Bubble length enforcement) | `src/pet_window.py`, `src/constants.py` |
| T3 (TTL + shutdown timeout) | `src/response_pool.py`, `src/constants.py`, `src/llm_session_persistence.py`, `tests/test_llm_session_persistence.py`, `tests/test_response_pool.py` |
| T4 (Refill session reuse) | `src/opencode_worker.py`, `src/pet_window.py`, `tests/test_opencode_worker.py` |
| T5 (Behavioral: queue overflow gate) | `src/behavior_controller.py`, `src/constants.py`, `src/pet_window.py`, `tests/test_behavior_controller.py` |
| T6 (Behavioral: pool starvation UX) | `src/system_dialogs.json`, `src/pet_window.py`, `tests/test_pet_window.py` |
| T7 (Missing requirements) | `requirements.txt`, `tests/test_tts_worker.py` |
| T8 (PERIMETER/CHASE thrash) | `src/pet_window.py`, `src/pet_fsm.py`, `tests/test_fsm.py` |
| T9 (Crash dump AppData) | `daemon.py`, `src/config.py`, `tests/test_config.py` |
| T10 (Data dir AppData migration) | `src/constants.py`, `src/config.py`, `tests/test_config.py` |
| T11 (Config onboarding wizard) | `src/settings_dialog.py`, `daemon.py`, `tests/test_settings_dialog.py` |
| T12 (PyInstaller spec rebuild) | `daemon.spec`, `scripts/build_exe.ps1` |
| T13 (NSIS installer) | `installer/daemon_installer.nsi`, `installer/README.md`, `scripts/build_installer.ps1` |
| T14 (opencode pre-flight check) | `src/opencode_serve_manager.py`, `daemon.py`, `scripts/check_opencode.ps1`, `tests/test_opencode_serve_manager.py` |
| T15 (Prompt compression) | `src/context_manager.py`, `tests/test_context_manager.py` |
| T16 (Plugin hot-reload) | `src/plugin_manager.py`, `src/context_menu.py`, `src/pet_window.py`, `tests/test_plugin_system.py` |
| T17 (Update dev memory + docs) | `memory/project-dev-memory.md`, `AGENTS.md`, `README.md` |
| T18 (Full regression + packaging test) | All test files, `daemon.spec`, build artifacts |

---

## Task 1: Fix FSM State Transition Log Spam

**Problem:** Logs show PERIMETER->CHASE firing 20+ times per second during cursor movement near the screen edge. Each fires a DEBUG log, flooding logs. FSM transitions are real and correct — the logging is the issue.

**Branch:** `task-1-fsm-log-dedup`

- [ ] **Step 1: Create feature branch**
  ```bash
  git checkout master && git checkout -b task-1-fsm-log-dedup
  ```

- [ ] **Step 2: Write the failing test** in `tests/test_pet_window.py`:
  ```python
  def test_fsm_transition_log_dedup():
      """Same prev->new state pair should only be logged once consecutively."""
      from src.pet_fsm import PetState
      # Simulate dedup logic
      last_logged = None
      transitions_logged = 0
      pairs = [(PetState.PERIMETER, PetState.CHASE)] * 20
      for prev, new in pairs:
          key = (prev, new)
          if key != last_logged:
              transitions_logged += 1
              last_logged = key
      assert transitions_logged == 1
  ```

- [ ] **Step 3: Run test** — verify it passes (confirms the dedup logic is correct):
  ```bash
  py -m pytest tests/test_pet_window.py::test_fsm_transition_log_dedup -v
  ```

- [ ] **Step 4: Add `_last_logged_transition` field to `PetWindow.__init__`** in `src/pet_window.py`:
  ```python
  self._last_logged_transition: tuple | None = None  # dedup FSM log spam
  ```

- [ ] **Step 5: Find the FSM transition log line** in `src/pet_window.py`. Search for `"FSM state transition"` or `"state transition"`. Wrap with dedup:
  ```python
  # Replace direct logger.debug("FSM state transition: %s -> %s", ...) with:
  transition_key = (prev_state, new_state)
  if transition_key != self._last_logged_transition:
      logger.debug("FSM state transition: %s -> %s", prev_state.name, new_state.name)
      self._last_logged_transition = transition_key
  # Reset when state changes to something new (clear stale key when different)
  elif prev_state != new_state:
      self._last_logged_transition = None
  ```

- [ ] **Step 6: Run full suite:**
  ```bash
  py -m pytest tests/ -v --tb=short 2>&1 | tail -20
  ```

- [ ] **Step 7: Squash merge to master:**
  ```bash
  git add src/pet_window.py tests/test_pet_window.py
  git commit -m "fix: dedup FSM state transition log spam"
  git checkout master
  git merge --squash task-1-fsm-log-dedup
  git commit -m "fix: dedup FSM state transition log spam"
  git branch -D task-1-fsm-log-dedup
  ```

---

## Task 2: Enforce Bubble Dialogue Length at Runtime

**Problem:** Logs show dialogues exceeding 150 chars. The schema `maxLength:150` is advisory — LLMs ignore it. Bubbles overflow visually and TTS reads too long.

**Branch:** `task-2-bubble-truncation`

- [ ] **Step 1:** `git checkout master && git checkout -b task-2-bubble-truncation`

- [ ] **Step 2: Add constant to `src/constants.py`** (find the SPEECH_BUBBLE section):
  ```python
  MAX_DIALOGUE_CHARS = 150  # truncate LLM dialogue at dispatch time
  ```

- [ ] **Step 3: Write failing test** in `tests/test_pet_window.py`:
  ```python
  def test_max_dialogue_chars_constant_exists():
      from src.constants import MAX_DIALOGUE_CHARS
      assert MAX_DIALOGUE_CHARS == 150

  def test_dialogue_truncation_logic():
      from src.constants import MAX_DIALOGUE_CHARS
      long = "A" * (MAX_DIALOGUE_CHARS + 50)
      if len(long) > MAX_DIALOGUE_CHARS:
          long = long[:MAX_DIALOGUE_CHARS - 3] + "..."
      assert len(long) == MAX_DIALOGUE_CHARS
      assert long.endswith("...")
  ```

- [ ] **Step 4: Run test:**
  ```bash
  py -m pytest tests/test_pet_window.py::test_max_dialogue_chars_constant_exists tests/test_pet_window.py::test_dialogue_truncation_logic -v
  ```
  Expected: `test_max_dialogue_chars_constant_exists` FAILS (constant doesn't exist yet). Add the constant, then run again.

- [ ] **Step 5: Add truncation in `_dispatch_structured`** in `src/pet_window.py`. Find `def _dispatch_structured`. At the top where `dialogue` is extracted:
  ```python
  from src.constants import MAX_DIALOGUE_CHARS
  dialogue = item.get("dialogue", "").strip()
  if len(dialogue) > MAX_DIALOGUE_CHARS:
      logger.warning("Dialogue truncated: %d -> %d chars", len(dialogue), MAX_DIALOGUE_CHARS)
      dialogue = dialogue[:MAX_DIALOGUE_CHARS - 3] + "..."
  ```

- [ ] **Step 6: Full suite + squash merge:**
  ```bash
  py -m pytest tests/ -v --tb=short 2>&1 | tail -20
  git add src/constants.py src/pet_window.py tests/test_pet_window.py
  git commit -m "fix: truncate dialogue at MAX_DIALOGUE_CHARS at dispatch time"
  git checkout master && git merge --squash task-2-bubble-truncation
  git commit -m "fix: truncate LLM dialogue at 150 chars at dispatch time"
  git branch -D task-2-bubble-truncation
  ```

---

## Task 3: Fix Pool TTL and Shutdown Timeout

**Problem A:** Pool TTL of 300s causes 14 items to be purged every 5 minutes — constant unnecessary refills.
**Problem B:** Shutdown blocked for 3+ minutes on session summary LLM call — unacceptable.

**Branch:** `task-3-ttl-and-shutdown`

- [ ] **Step 1:** `git checkout master && git checkout -b task-3-ttl-and-shutdown`

- [ ] **Step 2: Add constants to `src/constants.py`:**
  ```python
  THOUGHT_POOL_TTL_SECONDS = 600    # 10 minutes (was 300 — too aggressive)
  SUMMARY_TIMEOUT_SEC = 10          # max wait for session summary LLM call on quit
  ```

- [ ] **Step 3: Write tests** in `tests/test_response_pool.py`:
  ```python
  def test_default_ttl_is_600():
      from src.constants import THOUGHT_POOL_TTL_SECONDS
      assert THOUGHT_POOL_TTL_SECONDS == 600

  def test_pool_uses_constant_ttl():
      from src.response_pool import ThoughtPool
      from src.constants import THOUGHT_POOL_TTL_SECONDS
      pool = ThoughtPool(max_size=10, threshold=3, refill_count=3)
      assert pool._ttl_seconds == THOUGHT_POOL_TTL_SECONDS
  ```
  In `tests/test_llm_session_persistence.py`:
  ```python
  def test_summary_timeout_constant_exists():
      from src.constants import SUMMARY_TIMEOUT_SEC
      assert SUMMARY_TIMEOUT_SEC == 10
  ```

- [ ] **Step 4: Run tests to see failures:**
  ```bash
  py -m pytest tests/test_response_pool.py::test_default_ttl_is_600 tests/test_llm_session_persistence.py::test_summary_timeout_constant_exists -v
  ```

- [ ] **Step 5: Update `src/response_pool.py` ThoughtPool TTL default.** Find `def __init__` and the `ttl_seconds` default:
  ```python
  from src.constants import THOUGHT_POOL_TTL_SECONDS

  def __init__(self, max_size: int, threshold: int, refill_count: int,
               ttl_seconds: int = THOUGHT_POOL_TTL_SECONDS):
  ```

- [ ] **Step 6: Add `timeout_sec` to session summary generation in `src/llm_session_persistence.py`.** Find the function that makes an HTTP call to generate summary. Add `timeout_sec` param and pass it to `requests.post(timeout=timeout_sec)`.

- [ ] **Step 7: Wire `SUMMARY_TIMEOUT_SEC` in daemon.py/pet_window.py** where `save_session` or summary generation is called on shutdown. Find the call and pass `timeout_sec=SUMMARY_TIMEOUT_SEC`.

- [ ] **Step 8: Run full suite:**
  ```bash
  py -m pytest tests/ -v --tb=short 2>&1 | tail -20
  ```

- [ ] **Step 9: Squash merge:**
  ```bash
  git add src/constants.py src/response_pool.py src/llm_session_persistence.py daemon.py
  git add tests/test_response_pool.py tests/test_llm_session_persistence.py
  git commit -m "fix: pool TTL 600s, session summary timeout 10s"
  git checkout master && git merge --squash task-3-ttl-and-shutdown
  git commit -m "fix: pool TTL to 600s; cap session summary timeout at 10s"
  git branch -D task-3-ttl-and-shutdown
  ```

---

## Task 4: Refill Pool Session Reuse

**Problem:** Each pool refill creates a NEW opencode session, losing persona context and wasting 2–3s on session creation. A dedicated `_refill_session_id` reuses one session for all refills.

**Branch:** `task-4-refill-session-reuse`

- [ ] **Step 1:** `git checkout master && git checkout -b task-4-refill-session-reuse`

- [ ] **Step 2: Write failing test** in `tests/test_opencode_worker.py`:
  ```python
  def test_worker_skips_session_creation_when_session_id_provided(mock_requests):
      """If session_id is provided to OpencodeWorker, it should NOT create a new session."""
      import json
      from unittest.mock import patch, MagicMock, call
      from src.opencode_worker import OpencodeWorker

      created_sessions = []
      def fake_post(url, *args, **kwargs):
          if url.endswith("/session") and "message" not in url:
              created_sessions.append(url)
              r = MagicMock(status_code=200)
              r.json.return_value = {"id": "ses_new_unwanted"}
              return r
          r = MagicMock(status_code=200)
          r.text = json.dumps([{"type":"idle_thought","dialogue":"hi",
                                 "thought":"ok","priority":3}])
          r.json.return_value = {}
          return r

      with patch('requests.post', side_effect=fake_post):
          worker = OpencodeWorker(prompt="test", session_id="ses_existing_123")
          worker.run()

      assert len(created_sessions) == 0, "Should not create a new session when one is provided"
  ```

- [ ] **Step 3: Run test — expected FAIL:**
  ```bash
  py -m pytest tests/test_opencode_worker.py::test_worker_skips_session_creation_when_session_id_provided -v
  ```

- [ ] **Step 4: Read `src/opencode_worker.py`** — find `def run()` or `def send()`. Locate where session is created unconditionally. Modify to skip creation if `self._session_id` is already set:
  ```python
  def run(self) -> None:
      if not self._session_id:
          self._session_id = self._create_session()
          if not self._session_id:
              self.error_occurred.emit("Failed to create session")
              return
          # Emit signal so caller can cache this session_id
          self.session_created.emit(self._session_id)
      else:
          logger.info("Reusing existing session: %s", self._session_id)
      # ... rest of run ...
  ```

- [ ] **Step 5: Add `session_created = pyqtSignal(str)` to `OpencodeWorker` signals** (if not already present).

- [ ] **Step 6: Add `_refill_session_id: str | None = None` to `PetWindow.__init__`** in `src/pet_window.py`.

- [ ] **Step 7: In `_on_refill_needed`**, pass `session_id=self._refill_session_id` to the refill `OpencodeWorker`. Connect `worker.session_created` to `self._on_refill_session_created`.

- [ ] **Step 8: Add `_on_refill_session_created(self, session_id: str)` slot** to `PetWindow`:
  ```python
  def _on_refill_session_created(self, session_id: str) -> None:
      if not self._refill_session_id:
          self._refill_session_id = session_id
          logger.info("Refill session established: %s", session_id)
  ```

- [ ] **Step 9: Clear `_refill_session_id = None`** in the opencode serve respawn path (health check / restart).

- [ ] **Step 10: Run full suite + squash merge:**
  ```bash
  py -m pytest tests/ -v --tb=short 2>&1 | tail -20
  git add src/opencode_worker.py src/pet_window.py tests/test_opencode_worker.py
  git commit -m "feat: refill pool reuses dedicated session_id"
  git checkout master && git merge --squash task-4-refill-session-reuse
  git commit -m "feat: reuse dedicated refill session to skip per-refill session creation"
  git branch -D task-4-refill-session-reuse
  ```

---

## Task 5: Behavioral — Skip Autonomous Trigger When Bubble Queue Is Full

**Problem:** Autonomous triggers fire even when the bubble queue has 4–5 items queued. Pet talks over itself. Should hold off when queue is at or near capacity.

**Branch:** `task-5-queue-overflow-gate`

- [ ] **Step 1:** `git checkout master && git checkout -b task-5-queue-overflow-gate`

- [ ] **Step 2: Add constant to `src/constants.py`:**
  ```python
  BUBBLE_QUEUE_OVERFLOW_THRESHOLD = 3  # skip autonomous trigger if queue size >= this
  ```

- [ ] **Step 3: Write failing test** in `tests/test_behavior_controller.py`:
  ```python
  def test_autonomous_trigger_skipped_when_queue_overflowing():
      from src.behavior_controller import BehaviorController
      from unittest.mock import MagicMock

      bus = MagicMock()
      bc = BehaviorController(event_bus=bus)

      fired = []
      bus.publish.side_effect = lambda *a, **k: fired.append(a)

      # Context: queue size at overflow threshold
      context = {
          "apm": 10, "idle_seconds": 30,
          "fsm_state": "IDLE",
          "bubble_queue_size": 3,  # at BUBBLE_QUEUE_OVERFLOW_THRESHOLD
          "bubble_active": False,
          "autonomous_query_pending": False,
          "refill_in_progress": False,
          "chat_timer": 999,  # normally would fire
          "joke_timer": 999,
          "boredom_timer": 999,
      }
      bc.tick(context)
      autonomous_fired = any('autonomous' in str(a) for a in fired)
      assert not autonomous_fired
  ```

- [ ] **Step 4: Run test — expected FAIL:**
  ```bash
  py -m pytest tests/test_behavior_controller.py::test_autonomous_trigger_skipped_when_queue_overflowing -v
  ```

- [ ] **Step 5: In `src/behavior_controller.py`** find `_should_fire_autonomous` or the main firing guard. Add:
  ```python
  from src.constants import BUBBLE_QUEUE_OVERFLOW_THRESHOLD

  bubble_queue_size = context.get("bubble_queue_size", 0)
  if bubble_queue_size >= BUBBLE_QUEUE_OVERFLOW_THRESHOLD:
      logger.debug("[%s] Skipping: bubble queue overflowing (%d)", mode, bubble_queue_size)
      return False
  ```

- [ ] **Step 6: In `src/pet_window.py`** find `_master_tick` where the BehaviorController context dict is built. Add:
  ```python
  "bubble_queue_size": len(self._bubble_queue),
  ```

- [ ] **Step 7: Run full suite + squash merge:**
  ```bash
  py -m pytest tests/ -v --tb=short 2>&1 | tail -20
  git add src/behavior_controller.py src/constants.py src/pet_window.py
  git add tests/test_behavior_controller.py
  git commit -m "fix: skip autonomous trigger when bubble queue overflowing"
  git checkout master && git merge --squash task-5-queue-overflow-gate
  git commit -m "feat: skip autonomous trigger when bubble queue >= overflow threshold"
  git branch -D task-5-queue-overflow-gate
  ```

---

## Task 6: Pool Starvation UX — Better Fallback Messages

**Problem:** When pool is empty and refill pending, pet shows the generic error message. Need Kenny-style "brain buffering" messages instead.

**Branch:** `task-6-pool-starvation-ux`

- [ ] **Step 1:** `git checkout master && git checkout -b task-6-pool-starvation-ux`

- [ ] **Step 2: Read current `src/system_dialogs.json` structure:**
  ```bash
  type src\system_dialogs.json
  ```

- [ ] **Step 3: Add `pool_starved_messages` to `src/system_dialogs.json`:**
  ```json
  "pool_starved_messages": [
      "H-hold on, my brain is buffering...",
      "G-gimme a sec, I'm loading up my anxiety reserves!",
      "I've got thoughts, I just... need a moment. Don't look at me.",
      "My internal monologue is compiling. Please wait.",
      "Okay okay okay, I'm thinking! Just— one sec."
  ]
  ```

- [ ] **Step 4: Write test** in `tests/test_pet_window.py`:
  ```python
  def test_pool_starved_messages_in_system_dialogs():
      import json
      from pathlib import Path
      data = json.loads((Path("src/system_dialogs.json")).read_text(encoding="utf-8"))
      msgs = data.get("pool_starved_messages", [])
      assert len(msgs) >= 3
      for m in msgs:
          assert 0 < len(m) <= 150
  ```

- [ ] **Step 5: Find the pool-empty fallback path in `src/pet_window.py`** — search for the code that shows a fallback message when `item` is None and `_refill_in_progress` is True. Replace the generic error message with:
  ```python
  import random
  _pool_starved = _dialogs.get("pool_starved_messages", ["H-hold on, buffering..."])
  # ...
  if not item and self._refill_in_progress:
      self._show_bubble(random.choice(_pool_starved), duration_ms=4000)
      return
  ```

- [ ] **Step 6: Load `pool_starved_messages`** near the top of `pet_window.py` where `system_dialogs.json` is loaded (or add to the existing load block).

- [ ] **Step 7: Run full suite + squash merge:**
  ```bash
  py -m pytest tests/ -v --tb=short 2>&1 | tail -20
  git add src/system_dialogs.json src/pet_window.py tests/test_pet_window.py
  git commit -m "fix: pool-starved UX shows buffering message"
  git checkout master && git merge --squash task-6-pool-starvation-ux
  git commit -m "feat: pool-starved UX shows Kenny-style buffering message"
  git branch -D task-6-pool-starvation-ux
  ```

---

## Task 7: Fix Missing Dependencies in requirements.txt

**Problem:** `requirements.txt` missing `edge-tts`, `pydub`, `pyttsx3`, `requests`. These are all actively used in production but not pinned, so fresh installs fail silently.

**Branch:** `task-7-fix-requirements`

- [ ] **Step 1:** `git checkout master && git checkout -b task-7-fix-requirements`

- [ ] **Step 2: Audit imports vs requirements:**
  ```bash
  py -c "import edge_tts; print('edge_tts ok')"
  py -c "import pydub; print('pydub ok')"
  py -c "import pyttsx3; print('pyttsx3 ok')"
  py -c "import requests; print('requests ok')"
  ```

- [ ] **Step 3: Write test** in `tests/test_tts_worker.py`:
  ```python
  def test_all_tts_dependencies_importable():
      import importlib
      deps = ['edge_tts', 'pydub', 'pyttsx3']
      for dep in deps:
          try:
              importlib.import_module(dep)
          except ImportError as e:
              pytest.fail(f"Missing TTS dep: {dep} — {e}")
  ```

- [ ] **Step 4: Update `requirements.txt`** — add missing deps, pin versions, clarify comments:
  ```
  # Daemon requirements — Python 3.11+, Windows only

  # Core GUI
  PyQt6>=6.7.0

  # Input monitoring
  pynput>=1.7.7

  # Environment
  python-dotenv>=1.0.0

  # HTTP client (opencode API + Firebase REST)
  requests>=2.31.0

  # LLM session (opencode-compatible)
  openai>=1.0.0

  # Windows UI Automation
  comtypes>=1.4.8

  # Firebase
  firebase-admin>=6.0.0

  # Screenshot capture
  Pillow>=10.0.0

  # TTS pipeline
  edge-tts>=6.1.9
  pydub>=0.25.1
  pyttsx3>=2.90

  # Observability
  structlog>=24.1.0
  prometheus-client>=0.19.0

  # External: opencode CLI — npm install -g opencode@latest
  ```

- [ ] **Step 5: Run test + squash merge:**
  ```bash
  py -m pytest tests/test_tts_worker.py::test_all_tts_dependencies_importable -v
  git add requirements.txt tests/test_tts_worker.py
  git commit -m "fix: add edge-tts, pydub, pyttsx3, requests to requirements"
  git checkout master && git merge --squash task-7-fix-requirements
  git commit -m "fix: add missing TTS and HTTP deps to requirements.txt"
  git branch -D task-7-fix-requirements
  ```

---

## Task 8: Fix PERIMETER/CHASE Hysteresis Thrash

**Problem:** PERIMETER→CHASE fires rapidly in a tight loop during cursor movement near screen edge. The FSM's `CHASE_HYSTERESIS_MS=500` minimum dwell should prevent this. Root cause: either `_tick_perimeter` bypasses the FSM exit guard, or the FSM doesn't check `state_elapsed_ms` before exiting CHASE.

**Branch:** `task-8-chase-hysteresis`

- [ ] **Step 1:** `git checkout master && git checkout -b task-8-chase-hysteresis`

- [ ] **Step 2: Read `src/pet_fsm.py`** — find the CHASE state handler and the exit condition. Verify `state_elapsed_ms > CHASE_HYSTERESIS_MS` is checked before returning `PetState.IDLE` or `PetState.PERIMETER`.

- [ ] **Step 3: Write test** in `tests/test_fsm.py`:
  ```python
  def test_chase_exit_requires_min_dwell():
      """CHASE should not exit before CHASE_HYSTERESIS_MS even if cursor moves far."""
      from src.pet_fsm import PetFSM, PetState, FSMContext
      from src.constants import CHASE_HYSTERESIS_MS

      fsm = PetFSM()
      fsm.current_state = PetState.CHASE

      # Cursor far away but state_elapsed too short
      ctx = FSMContext(
          query_pending=False, autonomous_query_pending=False,
          is_dragged=False, apm=5, idle_seconds=5,
          cursor_dist=400,  # beyond exit threshold
          state_elapsed_ms=50,  # way less than CHASE_HYSTERESIS_MS
          triggered_action=None, fsm_state=PetState.CHASE,
      )
      result = fsm.update(dt_ms=33, ctx=ctx)
      assert result == PetState.CHASE, "Should stay CHASE before hysteresis dwell expires"

  def test_chase_exits_after_min_dwell():
      """CHASE exits to IDLE only after CHASE_HYSTERESIS_MS has elapsed."""
      from src.pet_fsm import PetFSM, PetState, FSMContext
      from src.constants import CHASE_HYSTERESIS_MS

      fsm = PetFSM()
      fsm.current_state = PetState.CHASE

      ctx = FSMContext(
          query_pending=False, autonomous_query_pending=False,
          is_dragged=False, apm=5, idle_seconds=5,
          cursor_dist=400,
          state_elapsed_ms=CHASE_HYSTERESIS_MS + 100,  # past the threshold
          triggered_action=None, fsm_state=PetState.CHASE,
      )
      result = fsm.update(dt_ms=33, ctx=ctx)
      assert result != PetState.CHASE, "Should exit CHASE after hysteresis dwell"
  ```

- [ ] **Step 4: Run tests — identify if they pass or fail:**
  ```bash
  py -m pytest tests/test_fsm.py::test_chase_exit_requires_min_dwell tests/test_fsm.py::test_chase_exits_after_min_dwell -v
  ```

- [ ] **Step 5: If test fails**, fix `src/pet_fsm.py` CHASE handler:
  ```python
  # In the CHASE state case:
  if ctx.cursor_dist > CHASE_EXIT_DIST and ctx.state_elapsed_ms > CHASE_HYSTERESIS_MS:
      return PetState.IDLE
  return PetState.CHASE
  ```

- [ ] **Step 6: Also check `_tick_perimeter` in `src/pet_window.py`** — if it calls `_fsm.transition_to(PetState.CHASE)` unconditionally without checking if already in CHASE or hysteresis, add a guard:
  ```python
  def _tick_perimeter(self) -> None:
      if self._fsm.current_state != PetState.PERIMETER:
          return  # only check CHASE entry when actually in PERIMETER
      # ... rest of perimeter patrol ...
  ```

- [ ] **Step 7: Run full suite + squash merge:**
  ```bash
  py -m pytest tests/ -v --tb=short 2>&1 | tail -20
  git add src/pet_fsm.py src/pet_window.py tests/test_fsm.py
  git commit -m "fix: CHASE hysteresis prevents PERIMETER→CHASE rapid thrash"
  git checkout master && git merge --squash task-8-chase-hysteresis
  git commit -m "fix: PERIMETER/CHASE hysteresis prevents rapid state oscillation"
  git branch -D task-8-chase-hysteresis
  ```

---

## Task 9: Crash Dump Location for Production

**Problem:** Crash dump is hardcoded to project root. In a packaged `.exe`, the install dir may be read-only. Must write to `%APPDATA%\Daemon\logs\crash_dump.log` when running frozen.

**Branch:** `task-9-crash-dump-appdata`

- [ ] **Step 1:** `git checkout master && git checkout -b task-9-crash-dump-appdata`

- [ ] **Step 2: Write test** in `tests/test_config.py`:
  ```python
  def test_get_crash_dump_path_frozen_uses_appdata(tmp_path, monkeypatch):
      import sys, os
      from unittest.mock import patch

      fake_appdata = str(tmp_path / "AppData" / "Roaming")
      os.makedirs(fake_appdata, exist_ok=True)

      with patch.dict(os.environ, {"APPDATA": fake_appdata}):
          with patch.object(sys, 'frozen', True, create=True):
              from importlib import import_module, reload
              import src.config as cfg_mod
              reload(cfg_mod)  # reload to pick up frozen=True
              path = cfg_mod.get_crash_dump_path()
              assert "Daemon" in str(path)
              assert "crash_dump" in str(path)

  def test_get_crash_dump_path_dev_uses_project_root():
      import sys
      from src.config import get_crash_dump_path
      with __import__('unittest.mock', fromlist=['patch']).patch.object(sys, 'frozen', False, create=True):
          path = get_crash_dump_path()
          assert "crash_dump" in str(path)
  ```

- [ ] **Step 3: Add `get_crash_dump_path()` to `src/config.py`:**
  ```python
  def get_crash_dump_path() -> Path:
      """Return crash dump path. Uses AppData in .exe, project root in dev."""
      import sys
      if getattr(sys, 'frozen', False):
          appdata = Path(os.environ.get("APPDATA", Path.home()))
          log_dir = appdata / "Daemon" / "logs"
          log_dir.mkdir(parents=True, exist_ok=True)
          return log_dir / "crash_dump.log"
      return Path(__file__).parent.parent / "crash_dump.log"
  ```

- [ ] **Step 4: Wire in `daemon.py`** — replace hardcoded crash dump path:
  ```python
  from src.config import get_crash_dump_path
  CRASH_DUMP_PATH = get_crash_dump_path()
  ```

- [ ] **Step 5: Run tests + squash merge:**
  ```bash
  py -m pytest tests/test_config.py -v
  git add src/config.py daemon.py tests/test_config.py
  git commit -m "fix: crash dump writes to AppData in packaged mode"
  git checkout master && git merge --squash task-9-crash-dump-appdata
  git commit -m "fix: crash dump path uses AppData/Daemon/logs when frozen"
  git branch -D task-9-crash-dump-appdata
  ```

---

## Task 10: Data Directory — AppData Migration for Production

**Problem:** All `data/` files are relative to project root. In a packaged `.exe`, the install directory is read-only. Need `%APPDATA%\Daemon\data\` in production.

**Branch:** `task-10-data-appdata`

> **⚠️ High test-impact task** — many tests use `tmp_path` already, but some may hardcode `data/` paths. Check all test failures after the change and patch them.

- [ ] **Step 1:** `git checkout master && git checkout -b task-10-data-appdata`

- [ ] **Step 2: Write test** in `tests/test_config.py`:
  ```python
  def test_get_data_dir_frozen_uses_appdata(tmp_path, monkeypatch):
      import sys, os
      from unittest.mock import patch

      fake_appdata = str(tmp_path / "AppData" / "Roaming")
      with patch.dict(os.environ, {"APPDATA": fake_appdata}):
          with patch.object(sys, 'frozen', True, create=True):
              from importlib import reload
              import src.config as cfg
              reload(cfg)
              d = cfg.get_data_dir()
              assert "Daemon" in str(d)
              assert "data" in str(d)

  def test_get_data_dir_dev_uses_local_data():
      import sys
      from unittest.mock import patch
      with patch.object(sys, 'frozen', False, create=True):
          from src.config import get_data_dir
          d = get_data_dir()
          assert d.name == "data"
  ```

- [ ] **Step 3: Add `get_data_dir()` to `src/config.py`:**
  ```python
  def get_data_dir() -> Path:
      """Return data directory. Uses AppData in .exe, project data/ in dev."""
      import sys
      if getattr(sys, 'frozen', False):
          appdata = Path(os.environ.get("APPDATA", Path.home()))
          data_dir = appdata / "Daemon" / "data"
      else:
          data_dir = Path(__file__).parent.parent / "data"
      data_dir.mkdir(parents=True, exist_ok=True)
      return data_dir
  ```

- [ ] **Step 4: Update `src/constants.py`** — replace hardcoded `Path` constructions for all data paths with a `_get_data_dir()` helper:
  ```python
  def _get_data_dir() -> Path:
      import sys
      if getattr(sys, 'frozen', False):
          import os
          d = Path(os.environ.get("APPDATA", Path.home())) / "Daemon" / "data"
      else:
          d = Path(__file__).parent.parent / "data"
      d.mkdir(parents=True, exist_ok=True)
      return d

  DATA_DIR = _get_data_dir()
  MEMORY_PATH         = DATA_DIR / ".daemon_memory.json"
  HISTORY_PATH        = DATA_DIR / ".daemon_history.json"
  DIARY_PATH          = DATA_DIR / ".daemon_diary.json"
  STATE_PATH          = DATA_DIR / ".daemon_state.json"
  RESPONSE_CACHE_PATH = DATA_DIR / ".daemon_response_cache.json"
  AUTH_PATH           = DATA_DIR / ".daemon_auth.json"
  THOUGHTS_LOG_PATH   = DATA_DIR / ".daemon_thoughts.log"
  LLM_SESSION_PATH    = DATA_DIR / "llm_session.json"
  CODEBASE_MAP_PATH   = DATA_DIR / "codebase_map.json"
  ```

- [ ] **Step 5: Run full suite — catch and fix test failures from path changes:**
  ```bash
  py -m pytest tests/ -v --tb=short 2>&1 | grep -E "FAIL|ERROR"
  ```
  For each failing test, check if it hardcodes a `data/` path. Patch with `tmp_path` or mock `get_data_dir`.

- [ ] **Step 6: Squash merge:**
  ```bash
  py -m pytest tests/ -v --tb=short 2>&1 | tail -10
  git add src/constants.py src/config.py tests/test_config.py
  git commit -m "feat: data dir resolves to AppData in packaged mode"
  git checkout master && git merge --squash task-10-data-appdata
  git commit -m "feat: data directory uses AppData/Daemon/data when frozen"
  git branch -D task-10-data-appdata
  ```

---

## Task 11: First-Run Config Onboarding — Open Connections Tab

**Problem:** First-run config validation opens `SettingsDialog` on tab 1 (Appearance). Users don't see the Connections tab (tab 4) where they must enter their API key. Need `setup_mode=True` to jump to Connections tab with a prominent banner.

**Branch:** `task-11-onboarding-wizard`

- [ ] **Step 1:** `git checkout master && git checkout -b task-11-onboarding-wizard`

- [ ] **Step 2: Write test** in `tests/test_settings_dialog.py`:
  ```python
  def test_settings_opens_connections_tab_in_setup_mode(app):
      from src.settings_dialog import SettingsDialog
      from PyQt6.QtWidgets import QTabWidget

      dlg = SettingsDialog(config={}, setup_mode=True)
      tabs = dlg.findChild(QTabWidget)
      if tabs:
          # Connections is the last tab (index 3 for 4 tabs)
          assert tabs.currentIndex() == tabs.count() - 1
      dlg.close()
  ```

- [ ] **Step 3: Read `src/settings_dialog.py`** — find `__init__`, locate tab construction, find Connections tab index.

- [ ] **Step 4: Add `setup_mode: bool = False` param to `SettingsDialog.__init__`:**
  ```python
  def __init__(self, config: dict, setup_mode: bool = False, parent=None):
      super().__init__(parent)
      # ... existing init ...
      if setup_mode:
          self._tabs.setCurrentIndex(self._tabs.count() - 1)  # jump to Connections
          if hasattr(self, '_setup_banner'):
              self._setup_banner.setVisible(True)
  ```

- [ ] **Step 5: Add setup banner widget to Connections tab** (at the top of the connections tab layout):
  ```python
  from PyQt6.QtWidgets import QLabel
  self._setup_banner = QLabel(
      "⚙️  First-time setup — enter your LLM API key and server URL below."
  )
  self._setup_banner.setWordWrap(True)
  self._setup_banner.setStyleSheet(
      "color: #F0C040; font-weight: bold; padding: 8px; "
      "background: rgba(240,192,64,0.1); border-radius: 4px;"
  )
  self._setup_banner.setVisible(False)
  connections_layout.insertWidget(0, self._setup_banner)
  ```

- [ ] **Step 6: Wire in `daemon.py`** where `SettingsDialog` is shown for missing config:
  ```python
  from src.settings_dialog import SettingsDialog
  # Pass setup_mode=True on first-run / missing config:
  dlg = SettingsDialog(config=cfg, setup_mode=True, parent=None)
  ```

- [ ] **Step 7: Run tests + squash merge:**
  ```bash
  py -m pytest tests/test_settings_dialog.py -v
  git add src/settings_dialog.py daemon.py tests/test_settings_dialog.py
  git commit -m "feat: settings dialog opens Connections tab in setup mode"
  git checkout master && git merge --squash task-11-onboarding-wizard
  git commit -m "feat: first-run onboarding opens Connections tab with setup banner"
  git branch -D task-11-onboarding-wizard
  ```

---

## Task 12: Rebuild PyInstaller Spec

**Problem:** `daemon.spec` is severely outdated — references deleted files, missing all new modules added in Phases 40–63, missing runtime data files (plugins/, system_dialogs.json), and incorrectly excludes `http`/`urllib` which the MCP server needs.

**Branch:** `task-12-pyinstaller-spec`

- [ ] **Step 1:** `git checkout master && git checkout -b task-12-pyinstaller-spec`

- [ ] **Step 2: Audit current `src/` modules:**
  ```bash
  dir src\*.py | Select-Object Name
  ```

- [ ] **Step 3: Audit runtime data files that must be bundled:**
  ```bash
  dir assets\
  dir src\system_dialogs.json
  dir plugins\*.py
  dir .opencode\skills\kenny\SKILL.md
  ```

- [ ] **Step 4: Rewrite `daemon.spec`:**
  ```python
  # -*- mode: python ; coding: utf-8 -*-
  from pathlib import Path

  block_cipher = None

  datas = [
      ('assets/daemon_config_template.json', 'assets'),
      ('src/system_dialogs.json', 'src'),
      ('plugins', 'plugins'),
      ('.opencode/skills/kenny/SKILL.md', '.opencode/skills/kenny'),
  ]

  hidden_imports = [
      # PyQt6
      'PyQt6', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets', 'PyQt6.sip',
      # Input
      'pynput', 'pynput.keyboard', 'pynput.mouse',
      'pynput.keyboard._win32', 'pynput.mouse._win32',
      # COM / UIA
      'comtypes', 'comtypes.client', 'comtypes.server', 'comtypes.gen',
      # Networking (MCP server needs http + urllib)
      'http', 'http.server', 'urllib', 'urllib.parse', 'urllib.request',
      'requests', 'requests.adapters',
      # LLM
      'openai', 'openai._client',
      # Firebase
      'firebase_admin', 'firebase_admin.credentials', 'firebase_admin.firestore',
      'google.auth', 'google.auth.transport', 'google.oauth2',
      # TTS
      'edge_tts', 'pydub', 'pydub.audio_segment', 'pyttsx3',
      'pyttsx3.drivers', 'pyttsx3.drivers.sapi5',
      'winsound',
      # Observability
      'structlog', 'prometheus_client',
      # Env
      'dotenv',
      # Imaging
      'PIL', 'PIL.Image', 'PIL.ImageGrab',
      # All daemon src modules
      'src.constants', 'src.config', 'src.pet_fsm', 'src.pet_renderer',
      'src.pet_window', 'src.animator', 'src.apm_worker', 'src.typing_buffer',
      'src.click_through', 'src.context_menu', 'src.context_manager',
      'src.opencode_worker', 'src.opencode_serve_manager', 'src.mcp_server',
      'src.fsm_bridge', 'src.screen_reader', 'src.active_window',
      'src.memory', 'src.history', 'src.diary_store', 'src.brain_schema',
      'src.memory_manager', 'src.firebase_crud', 'src.firebase_auth',
      'src.write_coalescer', 'src.persistence', 'src.response_pool',
      'src.response_manager', 'src.tts_worker', 'src.settings_dialog',
      'src.thought_log_dialog', 'src.login_dialog', 'src.data_viewer_dialog',
      'src.behavior_controller', 'src.events', 'src.event_worker',
      'src.plugin_manager', 'src.plugin_registry', 'src.llm_session_persistence',
      'src.log_context', 'src.logging_setup', 'src.observability', 'src.physics',
  ]

  excludes = [
      'tkinter', 'pip', 'setuptools',
      'pytest', '_pytest', 'pytest_mock',
      'IPython', 'numpy', 'scipy', 'matplotlib',
      'tests',
  ]

  a = Analysis(
      ['daemon.py'],
      pathex=['.'],
      binaries=[],
      datas=datas,
      hiddenimports=hidden_imports,
      hookspath=[],
      runtime_hooks=[],
      excludes=excludes,
      win_no_prefer_redirects=False,
      win_private_assemblies=False,
      cipher=block_cipher,
      noarchive=False,
  )

  pyz = PYZ(a.pure, cipher=block_cipher)

  exe = EXE(
      pyz, a.scripts, a.binaries, a.datas, [],
      name='Daemon',
      debug=False,
      bootloader_ignore_signals=False,
      strip=False,
      upx=True,
      upx_exclude=['PyQt6*.dll', 'Qt6*.dll'],
      runtime_tmpdir=None,
      console=False,
      disable_windowed_traceback=False,
      argv_emulation=False,
      target_arch=None,
      codesign_identity=None,
      entitlements_file=None,
      icon=None,
      onefile=True,
  )
  ```

- [ ] **Step 5: Create `scripts/build_exe.ps1`:**
  ```powershell
  # scripts/build_exe.ps1 — Build Daemon.exe via PyInstaller
  Set-StrictMode -Version Latest
  $ErrorActionPreference = "Stop"

  Write-Host "=== Daemon EXE Builder ===" -ForegroundColor Cyan

  # Clean previous build
  if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
  if (Test-Path "build") { Remove-Item -Recurse -Force "build" }

  # Run tests first
  Write-Host "Running tests..." -ForegroundColor Yellow
  py -m pytest tests/ -q --tb=short
  if ($LASTEXITCODE -ne 0) { Write-Host "Tests failed — aborting" -ForegroundColor Red; exit 1 }

  # Build
  Write-Host "Building..." -ForegroundColor Yellow
  py -m PyInstaller daemon.spec --clean

  if (Test-Path "dist\Daemon.exe") {
      $mb = [math]::Round((Get-Item "dist\Daemon.exe").Length / 1MB, 1)
      Write-Host "Build OK: dist\Daemon.exe ($mb MB)" -ForegroundColor Green
  } else {
      Write-Host "Build FAILED" -ForegroundColor Red; exit 1
  }
  ```

- [ ] **Step 6: Test build:**
  ```powershell
  .\scripts\build_exe.ps1
  ```

- [ ] **Step 7: Smoke test:**
  ```powershell
  .\dist\Daemon.exe --help
  Start-Process ".\dist\Daemon.exe" "--no-opencode --no-auth"
  Start-Sleep 5
  Get-Process Daemon -ErrorAction SilentlyContinue | Stop-Process
  ```

- [ ] **Step 8: Squash merge:**
  ```bash
  git add daemon.spec scripts/build_exe.ps1
  git commit -m "feat: rebuild PyInstaller spec for all current modules"
  git checkout master && git merge --squash task-12-pyinstaller-spec
  git commit -m "feat: rebuild daemon.spec with all Phase 40-63 modules and runtime data"
  git branch -D task-12-pyinstaller-spec
  ```

---

## Task 13: NSIS Installer for Windows Distribution

**Goal:** Create a distributable Windows installer that: installs Daemon.exe to `%LOCALAPPDATA%\Daemon`, creates config from template, offers optional opencode install, creates shortcuts.

**Branch:** `task-13-nsis-installer`

- [ ] **Step 1:** `git checkout master && git checkout -b task-13-nsis-installer`

- [ ] **Step 2: Create `installer/` directory:**
  ```bash
  mkdir installer
  ```

- [ ] **Step 3: Create `installer/daemon_installer.nsi`:**
  ```nsis
  ; daemon_installer.nsi
  !define APP_NAME "Daemon"
  !define APP_VERSION "1.0.0"
  !define APP_EXE "Daemon.exe"
  !define INSTALL_DIR "$LOCALAPPDATA\${APP_NAME}"
  !define DATA_DIR "$APPDATA\${APP_NAME}\data"
  !define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"

  Name "${APP_NAME} ${APP_VERSION}"
  OutFile "..\dist\DaemonSetup-${APP_VERSION}.exe"
  InstallDir "${INSTALL_DIR}"
  RequestExecutionLevel user
  ShowInstDetails show

  Page welcome
  Page directory
  Page instfiles
  Page finish
  UninstPage uninstConfirm
  UninstPage instfiles

  Section "Install Daemon" SEC_MAIN
      SetOutPath "$INSTDIR"
      File "..\dist\${APP_EXE}"
      CreateDirectory "${DATA_DIR}"

      ; Copy config template if first install
      IfFileExists "${DATA_DIR}\daemon_config.json" +2 0
          File /oname=${DATA_DIR}\daemon_config.json "..\assets\daemon_config_template.json"

      CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
      CreateDirectory "$SMPROGRAMS\${APP_NAME}"
      CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
      CreateShortcut "$SMPROGRAMS\${APP_NAME}\Uninstall.lnk" "$INSTDIR\Uninstall.exe"

      WriteUninstaller "$INSTDIR\Uninstall.exe"
      WriteRegStr HKCU "${UNINST_KEY}" "DisplayName" "${APP_NAME}"
      WriteRegStr HKCU "${UNINST_KEY}" "UninstallString" "$INSTDIR\Uninstall.exe"
      WriteRegStr HKCU "${UNINST_KEY}" "DisplayVersion" "${APP_VERSION}"
      WriteRegDWORD HKCU "${UNINST_KEY}" "NoModify" 1
  SectionEnd

  Section /o "Install opencode CLI (needs Node.js)" SEC_OPENCODE
      ExecWait 'cmd /c npm install -g opencode@latest'
  SectionEnd

  Section /o "Start Daemon with Windows" SEC_STARTUP
      CreateShortcut "$SMSTARTUP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
  SectionEnd

  Section "Uninstall"
      Delete "$INSTDIR\${APP_EXE}"
      Delete "$INSTDIR\Uninstall.exe"
      RMDir "$INSTDIR"
      Delete "$DESKTOP\${APP_NAME}.lnk"
      Delete "$SMPROGRAMS\${APP_NAME}\*.*"
      RMDir "$SMPROGRAMS\${APP_NAME}"
      Delete "$SMSTARTUP\${APP_NAME}.lnk"
      DeleteRegKey HKCU "${UNINST_KEY}"
  SectionEnd
  ```

- [ ] **Step 4: Create `installer/README.md`:**
  ```markdown
  # Daemon Installer

  ## Requirements
  - Windows 10/11 64-bit
  - Node.js 18+ (for opencode serve)
  - NSIS 3.x to compile the .nsi file

  ## Build
  ```powershell
  .\scripts\build_installer.ps1
  ```

  ## What Gets Installed
  1. `%LOCALAPPDATA%\Daemon\Daemon.exe`
  2. `%APPDATA%\Daemon\data\daemon_config.json` (from template)
  3. Desktop + Start Menu shortcuts
  4. Optional: opencode CLI via npm
  5. Optional: Windows startup shortcut
  ```

- [ ] **Step 5: Create `scripts/build_installer.ps1`:**
  ```powershell
  # scripts/build_installer.ps1
  Set-StrictMode -Version Latest
  $ErrorActionPreference = "Stop"

  Write-Host "=== Daemon Installer Builder ===" -ForegroundColor Cyan

  # Build EXE first
  .\scripts\build_exe.ps1

  # Check NSIS
  $nsis = Get-Command "makensis" -ErrorAction SilentlyContinue
  if (-not $nsis) {
      Write-Host "NSIS not found. Download: https://nsis.sourceforge.io" -ForegroundColor Yellow
      Write-Host "EXE is at dist\Daemon.exe — installer skipped." -ForegroundColor Yellow
      exit 0
  }

  Write-Host "Compiling NSIS installer..." -ForegroundColor Yellow
  makensis installer\daemon_installer.nsi

  if (Test-Path "dist\DaemonSetup-1.0.0.exe") {
      Write-Host "Installer ready: dist\DaemonSetup-1.0.0.exe" -ForegroundColor Green
  } else {
      Write-Host "NSIS compilation failed" -ForegroundColor Red; exit 1
  }
  ```

- [ ] **Step 6: Validate NSIS syntax (if available):**
  ```powershell
  makensis /NOCD installer\daemon_installer.nsi
  ```

- [ ] **Step 7: Squash merge:**
  ```bash
  git add installer/daemon_installer.nsi installer/README.md scripts/build_installer.ps1
  git commit -m "feat: NSIS installer for Daemon distribution"
  git checkout master && git merge --squash task-13-nsis-installer
  git commit -m "feat: NSIS Windows installer — DaemonSetup-1.0.0.exe"
  git branch -D task-13-nsis-installer
  ```

---

## Task 14: opencode Pre-flight Check with Install Guide

**Problem:** Daemon silently fails if opencode CLI is missing from PATH. In packaged mode, users have no idea why. Need a clear error dialog with install instructions.

**Branch:** `task-14-opencode-preflight`

- [ ] **Step 1:** `git checkout master && git checkout -b task-14-opencode-preflight`

- [ ] **Step 2: Write test** in `tests/test_opencode_serve_manager.py`:
  ```python
  def test_check_opencode_available_returns_false_when_missing():
      from src.opencode_serve_manager import check_opencode_available
      from unittest.mock import patch

      with patch('shutil.which', return_value=None):
          available, msg = check_opencode_available()
      assert available is False
      assert "opencode" in msg.lower()
      assert "install" in msg.lower() or "npm" in msg.lower()

  def test_check_opencode_available_returns_true_when_found():
      from src.opencode_serve_manager import check_opencode_available
      from unittest.mock import patch

      with patch('shutil.which', return_value="C:\\npm\\opencode.cmd"):
          available, path = check_opencode_available()
      assert available is True
      assert "opencode" in path
  ```

- [ ] **Step 3: Add `check_opencode_available()` to `src/opencode_serve_manager.py`:**
  ```python
  def check_opencode_available() -> tuple[bool, str]:
      """Check if opencode CLI is on PATH.
      Returns (True, path_str) or (False, install_instructions).
      """
      import shutil
      path = shutil.which("opencode") or shutil.which("opencode.cmd")
      if path:
          return True, path
      return False, (
          "opencode CLI not found on PATH.\n\n"
          "Install it with:\n"
          "    npm install -g opencode@latest\n\n"
          "Requires Node.js 18+: https://nodejs.org\n"
          "More info: https://opencode.ai/docs"
      )
  ```

- [ ] **Step 4: Wire into `daemon.py`** early in `main()` before `ensure_opencode_serve_running`:
  ```python
  from src.opencode_serve_manager import check_opencode_available

  if not args.no_opencode:
      available, msg = check_opencode_available()
      if not available:
          from PyQt6.QtWidgets import QMessageBox
          box = QMessageBox()
          box.setWindowTitle("Daemon — Setup Required")
          box.setText("opencode CLI is required but not installed.")
          box.setDetailedText(msg)
          box.setIcon(QMessageBox.Icon.Critical)
          box.exec()
          sys.exit(1)
  ```

- [ ] **Step 5: Create `scripts/check_opencode.ps1`:**
  ```powershell
  # scripts/check_opencode.ps1 — Verify opencode CLI
  $cmd = Get-Command "opencode" -ErrorAction SilentlyContinue
  if ($cmd) {
      Write-Host "opencode found: $($cmd.Source)" -ForegroundColor Green
      & opencode --version
  } else {
      Write-Host "opencode not found. Install: npm install -g opencode@latest" -ForegroundColor Red
      exit 1
  }
  ```

- [ ] **Step 6: Run tests + squash merge:**
  ```bash
  py -m pytest tests/test_opencode_serve_manager.py -v
  git add src/opencode_serve_manager.py daemon.py scripts/check_opencode.ps1
  git add tests/test_opencode_serve_manager.py
  git commit -m "feat: opencode pre-flight check with install instructions"
  git checkout master && git merge --squash task-14-opencode-preflight
  git commit -m "feat: opencode pre-flight check shows install guide when CLI missing"
  git branch -D task-14-opencode-preflight
  ```

---

## Task 15: LLM API Optimization — Compact Refill Prompt

**Problem:** Pool refill prompt is ~800 chars (~200 tokens) and includes the full PERSONA block on every call. With a dedicated refill session (Task 4), the persona is already in session context. Compressing the prompt to ~150 tokens saves ~25% tokens per refill call.

**Branch:** `task-15-prompt-compression`

- [ ] **Step 1:** `git checkout master && git checkout -b task-15-prompt-compression`

- [ ] **Step 2: Read `src/context_manager.py`** — find the refill prompt builder (search for `build_pool_refill_prompt`, `build_mixed_bag_prompt`, or `build_autonomous_trigger` with `mode=="refill"`).

- [ ] **Step 3: Write test** in `tests/test_context_manager.py`:
  ```python
  def test_refill_prompt_is_compact():
      """Pool refill prompt should be under 700 chars (approx 175 tokens)."""
      from src.context_manager import ContextManager
      cm = ContextManager()

      # Try calling the refill prompt builder — adapt name to actual method
      # Try: build_pool_refill_prompt, build_mixed_bag_prompt, etc.
      prompt = cm.build_pool_refill_prompt(
          screen_context="VSCode — daemon.py",
          apm=25,
          count=5,
      )
      assert len(prompt) < 700, f"Refill prompt too long: {len(prompt)} chars"
  ```

- [ ] **Step 4: Run test — expected FAIL:**
  ```bash
  py -m pytest tests/test_context_manager.py::test_refill_prompt_is_compact -v
  ```

- [ ] **Step 5: Rewrite the refill prompt** (note: the PERSONA section can be omitted since Task 4 injects it via refill session):
  ```python
  def build_pool_refill_prompt(
      self,
      screen_context: str,
      apm: int,
      count: int = 5,
  ) -> str:
      """Compact pool refill prompt. Persona already in refill session context."""
      types = '"typing_reaction","observation","intel_roast","idle_thought"'
      return (
          f"Screen: {screen_context} | APM: {apm}\n"
          f"Generate {count} JSON items, types=[{types}].\n"
          f'Each: {{"type":..., "dialogue":<100chars, "thought":<150chars, "priority":1-5}}.\n'
          f'Only "observation" items get "context_hash": "<screen value>".\n'
          f"Reply ONLY with a JSON array. No preamble."
      )
  ```

  If pool refill uses a Stage-2 `build_mixed_bag_prompt`, the same compression applies — remove the persona block and shorten the type guide.

- [ ] **Step 6: Run test + verify quality**
  ```bash
  py -m pytest tests/test_context_manager.py -v
  ```
  Then run Daemon for 5 minutes and check logs — pool items should be well-formed with correct types, meaningful dialogues, correct priorities. If quality degrades, add back the type guide lines.

- [ ] **Step 7: Full suite + squash merge:**
  ```bash
  py -m pytest tests/ -v --tb=short 2>&1 | tail -20
  git add src/context_manager.py tests/test_context_manager.py
  git commit -m "perf: compact pool refill prompt to ~150 tokens"
  git checkout master && git merge --squash task-15-prompt-compression
  git commit -m "perf: compress pool refill prompt — remove redundant persona in session"
  git branch -D task-15-prompt-compression
  ```

---

## Task 16: Plugin Hot-Reload via Context Menu

**Problem:** Plugins loaded once at boot. No way to reload or see loaded plugins from UI without restarting Daemon. Need "Reload Plugins" in the right-click context menu.

**Branch:** `task-16-plugin-hot-reload`

- [ ] **Step 1:** `git checkout master && git checkout -b task-16-plugin-hot-reload`

- [ ] **Step 2: Write test** in `tests/test_plugin_system.py`:
  ```python
  def test_plugin_manager_supports_reload(tmp_path):
      """PluginManager should reload plugins from disk when reload() is called."""
      from src.plugin_manager import PluginManager
      from src.plugin_registry import PluginRegistry

      plugin_dir = tmp_path / "plugins"
      plugin_dir.mkdir()
      registry = PluginRegistry()

      mgr = PluginManager(plugin_dir=str(plugin_dir))
      mgr.discover()
      mgr.load_all(registry)
      assert mgr.loaded_count == 0

      # Add a plugin after initial load
      (plugin_dir / "test_hot.py").write_text(
          'PLUGIN_NAME="HotTest"\nPLUGIN_VERSION="1.0"\n'
          'def register(registry): pass\n'
      )

      # Reload
      mgr.discover()
      mgr.load_all(registry)
      assert mgr.loaded_count >= 1
  ```

- [ ] **Step 3: Run test:**
  ```bash
  py -m pytest tests/test_plugin_system.py::test_plugin_manager_supports_reload -v
  ```

- [ ] **Step 4: Add `reload()` method to `PluginManager`** in `src/plugin_manager.py`:
  ```python
  def reload(self, registry) -> int:
      """Clear loaded plugins and re-discover/load from disk."""
      self._loaded_plugins.clear()
      self._discovered.clear()
      self.discover()
      self.load_all(registry)
      logger.info("Plugin reload: %d plugins loaded", self.loaded_count)
      return self.loaded_count
  ```

- [ ] **Step 5: Add `reload_plugins = pyqtSignal()` signal to context menu `_Signals` class** in `src/context_menu.py`. Add "Reload Plugins" action connected to this signal.

- [ ] **Step 6: Connect in `PetWindow`** in `src/pet_window.py`:
  ```python
  self._context_menu.signals.reload_plugins.connect(self._on_reload_plugins)

  def _on_reload_plugins(self) -> None:
      count = self._plugin_manager.reload(self._plugin_registry)
      self._show_bubble(f"Reloaded {count} plugin(s)!", duration_ms=4000)
  ```

- [ ] **Step 7: Run full suite + squash merge:**
  ```bash
  py -m pytest tests/ -v --tb=short 2>&1 | tail -20
  git add src/plugin_manager.py src/context_menu.py src/pet_window.py
  git add tests/test_plugin_system.py
  git commit -m "feat: plugin hot-reload via context menu"
  git checkout master && git merge --squash task-16-plugin-hot-reload
  git commit -m "feat: right-click context menu offers plugin hot-reload"
  git branch -D task-16-plugin-hot-reload
  ```

---

## Task 17: Update Dev Memory and Documentation

**Branch:** `task-17-docs`

- [ ] **Step 1:** `git checkout master && git checkout -b task-17-docs`

- [ ] **Step 2: Update `memory/project-dev-memory.md`** — add Phase 64 at the end:
  ```markdown
  ### Phase 64 — Production-Ready & Packaging (2026-06-20)
  **Plan file:** `docs/superpowers/plans/2026-06-20-production-ready-daemon.md`

  Key changes:
  - T1: FSM log dedup (no more spam)
  - T2: Dialogue truncated at MAX_DIALOGUE_CHARS=150 at dispatch
  - T3: Pool TTL raised to 600s; session summary timeout capped at 10s
  - T4: Dedicated refill session reused across pool refills
  - T5: Autonomous trigger skipped when bubble queue overflowing
  - T6: Pool-starved UX shows Kenny "buffering" messages
  - T7: requirements.txt now includes edge-tts, pydub, pyttsx3, requests
  - T8: PERIMETER/CHASE hysteresis fixed
  - T9: Crash dump writes to %APPDATA%\Daemon\logs\ when frozen
  - T10: Data dir resolves to %APPDATA%\Daemon\data\ when frozen
  - T11: Settings dialog opens Connections tab in first-run setup mode
  - T12: daemon.spec rebuilt for all Phase 40-63 modules + runtime data
  - T13: NSIS installer: dist\DaemonSetup-1.0.0.exe
  - T14: opencode pre-flight check with install instructions
  - T15: Refill prompt compressed to ~150 tokens
  - T16: Plugin hot-reload via context menu

  Known pitfalls:
  - comtypes generates COM bindings at runtime — needs write access to %TEMP% in .exe
  - pynput requires hookspath for Windows platform hooks in PyInstaller
  - DATA_DIR resolves differently in .exe vs dev — always use get_data_dir() from config.py
  - NSIS 3.x required — not in PATH by default on Windows
  ```

- [ ] **Step 3: Update `README.md`** — add Installation section before Development:
  ```markdown
  ## Installation (End Users)

  ### Requirements
  - Windows 10/11 (64-bit)
  - opencode CLI: `npm install -g opencode@latest` (Node.js 18+ required)
  - LLM API key (Claude/OpenRouter/Anthropic)

  ### Download
  Download `DaemonSetup-<version>.exe` from Releases.

  ### First-Run Setup
  1. Run the installer
  2. Launch Daemon from Desktop shortcut
  3. Settings will open on the Connections tab — enter your API key and server URL
  4. Firebase credentials optional (cloud memory sync)

  ## Development
  ```

- [ ] **Step 4: Commit + squash merge:**
  ```bash
  git add memory/project-dev-memory.md README.md AGENTS.md
  git commit -m "docs: Phase 64 production-ready summary in dev memory and README"
  git checkout master && git merge --squash task-17-docs
  git commit -m "docs: update dev memory, README for Phase 64 production-ready"
  git branch -D task-17-docs
  ```

---

## Task 18: Full Regression + Packaging Smoke Test

**This is the gate before any release. Every prior task must be merged to master first.**

**Branch:** `task-18-regression`

- [ ] **Step 1:** `git checkout master && git checkout -b task-18-regression`

- [ ] **Step 2: Run full test suite:**
  ```bash
  py -m pytest tests/ -v 2>&1 | tee test_results.txt
  tail -20 test_results.txt
  ```
  Expected: All tests pass, 0 failures.

- [ ] **Step 3: Check test count is >= 700:**
  ```bash
  py -m pytest tests/ --collect-only -q 2>&1 | tail -5
  ```

- [ ] **Step 4: Build the EXE:**
  ```powershell
  .\scripts\build_exe.ps1
  ```
  Expected: `dist\Daemon.exe` exists, > 50MB.

- [ ] **Step 5: Smoke test the EXE:**
  ```powershell
  # Test help
  .\dist\Daemon.exe --help

  # Test startup in no-opencode+no-auth mode
  $proc = Start-Process ".\dist\Daemon.exe" "--no-opencode --no-auth" -PassThru
  Start-Sleep 8
  if ($proc.HasExited) {
      Write-Host "FAIL: Daemon.exe exited unexpectedly" -ForegroundColor Red
      exit 1
  }
  $proc | Stop-Process
  Write-Host "Smoke test PASS" -ForegroundColor Green
  ```

- [ ] **Step 6: Build installer (if NSIS available):**
  ```powershell
  .\scripts\build_installer.ps1
  ```

- [ ] **Step 7: Check crash dump path in packaged mode:**
  The smoke test above running as .exe should create `%APPDATA%\Daemon\logs\` directory. Verify:
  ```powershell
  dir "$env:APPDATA\Daemon\logs\"
  ```

- [ ] **Step 8: Squash merge to master:**
  ```bash
  git add test_results.txt 2>/dev/null || true
  git commit -m "test: full regression results for Phase 64"
  git checkout master && git merge --squash task-18-regression
  git commit -m "test: Phase 64 full regression — all tests pass, EXE smoke tested"
  git branch -D task-18-regression
  ```

- [ ] **Step 9: Tag the release:**
  ```bash
  git tag v1.0.0 -m "Production-ready Daemon v1.0.0"
  ```

---

## Summary

| # | Task | Type | Impact |
|---|------|------|--------|
| 1 | FSM log dedup | Bug | Cleans up log spam (20+ lines/sec) |
| 2 | Bubble truncation | Bug | Prevents visual/TTS overflow |
| 3 | Pool TTL 600s + shutdown 10s | Bug | Reduces refills 50%; fixes 3min shutdown |
| 4 | Refill session reuse | Perf | -2-3s per refill, consistent persona |
| 5 | Queue overflow gate | Behavior | Prevents dialogue pileup |
| 6 | Pool-starved UX | Behavior | Kenny-appropriate feedback instead of error |
| 7 | Fix requirements.txt | Infra | Fresh installs now work correctly |
| 8 | CHASE hysteresis fix | Bug | No more PERIMETER↔CHASE oscillation |
| 9 | Crash dump AppData | Infra | Crashes captured in packaged mode |
| 10 | Data dir AppData | Infra | Core enabler for transferability |
| 11 | Onboarding UX | UX | First-run setup is guided |
| 12 | PyInstaller spec | Packaging | Correct .exe build with all modules |
| 13 | NSIS installer | Packaging | One-click install for end users |
| 14 | opencode pre-flight | UX | Clear error + install guide on missing CLI |
| 15 | Prompt compression | Perf | ~25% fewer tokens per refill |
| 16 | Plugin hot-reload | Feature | No restart needed for new plugins |
| 17 | Dev memory + docs | Docs | Session continuity for future agents |
| 18 | Regression + smoke test | QA | Gate before v1.0.0 tag |

