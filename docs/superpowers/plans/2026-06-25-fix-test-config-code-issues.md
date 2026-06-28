# Fix Test, Config, and Code Issues Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 8 failing tests, 3 code bugs, and 1 template config gap in the Daemon codebase.

**Architecture:** Issues span three independent areas: (1) test assertions that mismatch runtime config values, (2) unreferenced variable and missing HTTP auth handling in system modules, and (3) a missing config key in the template. Each task is self-contained and can be executed in any order.

**Tech Stack:** Python 3.14, PyQt6, pytest, requests, comtypes (UIA)

---

## File Structure

### Files to modify:
| File | Change |
|------|--------|
| `tests/test_events.py:11` | Add `AFFINITY_MILESTONE_REACHED` to expected set |
| `tests/test_fsm.py:107` | Change cursor offset from 300 to 301 to exceed actual CHASE_EXIT_RADIUS_PX=300 |
| `tests/test_bubble_behavior.py:49-50` | Increase text length from 500 to 1000 chars to force ≥3 pages |
| `tests/test_bubble_behavior.py:113` | Increase "word " repetitions from 80 to 100 to exceed BUBBLE_MAX_CHARS=400 |
| `tests/test_bubble_behavior.py:153-154,160` | Fix comments from "80ms" to "50ms" |
| `tests/test_bubble_behavior.py:228` | Change `_TYPEWRITER_CHARS_PER_TICK` from 4 to 8 |
| `tests/test_bubble_behavior.py:255` | Change expected `BUBBLE_MS_PER_CHAR` from 80 to 50 |
| `tests/test_bubble_behavior.py:285` | Increase "hello world " repetitions from 30 to 40 to exceed BUBBLE_MAX_CHARS=400 |
| `tests/test_bubble_behavior.py:389-413` | Update typewriter test assertions from 4→8 chars/tick and rename test |
| `src/system/screen_reader.py:23` | Remove unreferenced `global _UIA_INITIALIZED` |
| `src/system/event_worker.py:13,42-50` | Add `auth_failed` signal and 401/403 handling |
| `assets/daemon_config_template.json:103-104` | Add missing `dialogue_max_length: 150` |

---

### Task 1: Fix event test — add missing AFFINITY_MILESTONE_REACHED

**Files:**
- Modify: `tests/test_events.py:11`
- Test: same file (run after fix)

- [ ] **Step 1: Add AFFINITY_MILESTONE_REACHED to expected set**

In `tests/test_events.py`, add `"AFFINITY_MILESTONE_REACHED"` to the `expected` set at line 11. The set should now include this event type between `"EMOTION_SHIFTED"` and `"USER_INPUT_RECEIVED"`:

```python
expected = {
    "FSM_STATE_CHANGED", "FSM_TRANSITION_DENIED",
    "EMOTION_SHIFTED",
    "AFFINITY_MILESTONE_REACHED",
    "USER_INPUT_RECEIVED", "USER_HOTKEY_PRESSED",
    ...
}
```

- [ ] **Step 2: Run tests to verify**

Run: `py -m pytest tests/test_events.py::TestEventType::test_has_all_expected_event_types -v`

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_events.py
git commit -m "fix: add AFFINITY_MILESTONE_REACHED to event type test"
```

---

### Task 2: Fix CHASE exit test — use cursor distance > actual CHASE_EXIT_RADIUS_PX

**Files:**
- Modify: `tests/test_fsm.py:107`
- Test: `tests/test_fsm.py::test_chase_exits_when_cursor_far_and_min_duration_elapsed`

- [ ] **Step 1: Change cursor offset from 300 to 301**

The config has `CHASE_EXIT_RADIUS_PX = 300`. The test sets cursor at `(120 + 300, 925)` = distance 300, but `300 > 300` is false. Change to `120 + 301` so distance is 301, which IS `> 300`.

```python
# cursor 301px away (> CHASE_EXIT_RADIUS_PX=300)
ctx = make_context(
    cursor_pos=(120 + 301, 925),
    pet_rect=(100, 900, 40, 50),
    state_elapsed_ms=MIN_CHASE_DURATION_MS,
)
```

Also update the comment on line 105 from `> CHASE_EXIT_RADIUS_PX=250` to `> CHASE_EXIT_RADIUS_PX=300`.

- [ ] **Step 2: Run tests to verify**

Run: `py -m pytest tests/test_fsm.py::test_chase_exits_when_cursor_far_and_min_duration_elapsed -v`

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_fsm.py
git commit -m "fix: update CHASE exit test cursor offset to exceed actual config value"
```

---

### Task 3: Fix bubble pagination tests — text too short for BUBBLE_MAX_CHARS=400

**Files:**
- Modify: `tests/test_bubble_behavior.py:49-50,113,285`
- Tests: `test_long_text_splits_into_pages`, `test_show_bubble_with_multi_page_text`, `test_show_bubble_paginates_at_bubble_max_chars`

- [ ] **Step 1: Fix `test_long_text_splits_into_pages` — need ≥3 pages**

Current: `"word " * 100` = 500 chars → `_paginate_text` with max_chars=400 splits into 2 pages (400 + 100), but test asserts `>= 3`.

Change to `"word " * 200` = 1000 chars → 3 pages. Update the assertion to `>= 3` (it already is) and the comment:

```python
# 1000 chars of words should split into 3+ pages
words = "word " * 200  # 1000 chars
pages = window._paginate_text(words, BUBBLE_MAX_CHARS)
assert len(pages) >= 3
```

- [ ] **Step 2: Fix `test_show_bubble_with_multi_page_text` — text at boundary**

Current: `"word " * 80` = 400 chars, exactly equal to `BUBBLE_MAX_CHARS=400`. `_paginate_text` returns `[text]` (len 1), so `_bubble_pages = []`.

Change to `"word " * 100` = 500 chars > 400:

```python
text = "word " * 100  # ~500 chars — should paginate
```

- [ ] **Step 3: Fix `test_show_bubble_paginates_at_bubble_max_chars` — text below limit**

Current: `"hello world " * 30` = 360 chars < 400 → no pagination.

Change to `"hello world " * 40` = 480 chars > 400:

```python
text = "hello world " * 40  # ~480 chars
```

- [ ] **Step 4: Run all bubble tests to verify**

Run: `py -m pytest tests/test_bubble_behavior.py::TestPagination -v`

Expected: All 6 tests in TestPagination PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_bubble_behavior.py
git commit -m "fix: increase bubble pagination test text lengths for BUBBLE_MAX_CHARS=400"
```

---

### Task 4: Fix bubble duration tests — config values changed

**Files:**
- Modify: `tests/test_bubble_behavior.py:153-154,160,228,255`
- Tests: `test_duration_proportional_to_length`, `test_each_page_gets_own_proportional_duration`, `test_bubble_duration_config_values_present`

- [ ] **Step 1: Fix comments in `test_duration_proportional_to_length`**

Lines 153 and 157 say "80ms/char" but config has `BUBBLE_MS_PER_CHAR=50`. The assertions use the constant so they're correct — just fix the comments:

```python
# 100 chars at 50ms/char = 5000ms
d100 = window._bubble_duration("x" * 100)
assert d100 == 100 * BUBBLE_MS_PER_CHAR, f"Expected {100 * BUBBLE_MS_PER_CHAR}, got {d100}"
# 50 chars at 50ms/char = 2500ms
d50 = window._bubble_duration("x" * 50)
assert d50 == 50 * BUBBLE_MS_PER_CHAR, f"Expected {50 * BUBBLE_MS_PER_CHAR}, got {d50}"
```

- [ ] **Step 2: Fix `test_each_page_gets_own_proportional_duration`**

Hardcoded `_TYPEWRITER_CHARS_PER_TICK = 4` at line 228. Actual config has `typewriter_chars_per_tick = 8` and the test calls `window._tick_typewriter()` which uses the instance's `_typewriter_chars_per_tick = 8`.

Change to 8 and update the expected calculation comment:

```python
_TYPEWRITER_CHARS_PER_TICK = 8
_TYPEWRITER_TICK_MS = 30
typewriter_ms = (100 // _TYPEWRITER_CHARS_PER_TICK) * _TYPEWRITER_TICK_MS
expected = 100 * BUBBLE_MS_PER_CHAR - typewriter_ms
```

With `BUBBLE_MS_PER_CHAR=50`: `expected = 100 * 50 - (100 // 8) * 30 = 5000 - 360 = 4640`

- [ ] **Step 3: Fix `test_bubble_duration_config_values_present`**

Line 255 asserts `flat.get("BUBBLE_MS_PER_CHAR") == 80` but config has 50. Change to:

```python
assert flat.get("BUBBLE_MS_PER_CHAR") == 50
```

- [ ] **Step 4: Run duration tests to verify**

Run: `py -m pytest tests/test_bubble_behavior.py::TestProportionalDuration tests/test_bubble_behavior.py::TestConfigurableCharLimit -v`

Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_bubble_behavior.py
git commit -m "fix: update bubble duration test expectations to match config (50ms/char, 8 chars/tick)"
```

---

### Task 5: Fix typewriter speed test — update from 4 to 8 chars/tick

**Files:**
- Modify: `tests/test_bubble_behavior.py:386-413`
- Test: `TestTypewriterSpeed::test_typewriter_reveals_four_chars_per_tick`

- [ ] **Step 1: Rename test and update assertions**

The config has `typewriter_chars_per_tick = 8`. Rename the test and update all assertions. With 20 chars and 8 chars/tick:
- Tick 1: min(0+8, 20) = 8 → "ABCDEFGH"
- Tick 2: min(8+8, 20) = 16 → "ABCDEFGHIJKLMNOP"
- Tick 3: min(16+8, 20) = 20 → all revealed

```python
class TestTypewriterSpeed:
    """Typewriter reveals text at 8 chars per 30ms tick for low-latency display."""

    def test_typewriter_reveals_eight_chars_per_tick(self, app):
        with patch("src.ui.pet_window.ClickThroughManager"), \
             patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
             patch("src.ui.pet_window.APMWorker"), \
             patch("src.ui.pet_window.MCPServer"), \
             patch("src.ui.pet_window.BehaviorController"):
            from src.ui.pet_window import PetWindow
            window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
            text = "ABCDEFGHIJKLMNOPQRST"  # 20 chars
            window._start_typewriter(text)
            # After one tick, min(0+8, 20) = 8 chars
            window._tick_typewriter()
            assert window._bubble_text == "ABCDEFGH"
            # After second tick, min(8+8, 20) = 16 chars
            window._tick_typewriter()
            assert window._bubble_text == "ABCDEFGHIJKLMNOP"
            # After third tick, min(16+8, 20) = 20 chars — all revealed
            window._tick_typewriter()
            assert window._bubble_text == "ABCDEFGHIJKLMNOPQRST"
```

- [ ] **Step 2: Run typewriter test to verify**

Run: `py -m pytest tests/test_bubble_behavior.py::TestTypewriterSpeed -v`

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_bubble_behavior.py
git commit -m "fix: update typewriter test for 8 chars/tick config"
```

---

### Task 6: Fix screen_reader.py — remove unreferenced `_UIA_INITIALIZED`

**Files:**
- Modify: `src/system/screen_reader.py:23`
- Test: Run existing screen_reader tests if any, otherwise `py -m pytest tests/ -k "screen" -v`

- [ ] **Step 1: Remove dead `global _UIA_INITIALIZED` line**

In `src/system/screen_reader.py`, remove line 23 (`global _UIA_INITIALIZED`). The variable is never assigned anywhere in the file — it's dead code that would cause an `UnboundLocalError` if `_get_uia_automation()` ran to completion without assigning it.

The function after fix:

```python
def _get_uia_automation():
    """Lazy initialization of IUIAutomation, thread-local."""
    if not _UIA_AVAILABLE:
        return None
    if hasattr(_uia_local, 'automation') and _uia_local.automation is not None:
        return _uia_local.automation

    try:
        import ctypes
        from comtypes.client import CreateObject, GetModule
        import comtypes

        comtypes.CoInitialize()
        GetModule("UIAutomationCore.dll")
        from comtypes.gen.UIAutomationClient import IUIAutomation
        clsid = "{ff48dba4-60ef-4201-aa87-54103eef594e}"
        _uia_local.automation = CreateObject(clsid, interface=IUIAutomation)
        logger.info("UIA automation initialized on thread %s", threading.current_thread().name)
        return _uia_local.automation
    except Exception as e:
        logger.warning("UIA initialization failed on thread %s: %s",
                       threading.current_thread().name, e)
        return None
```

- [ ] **Step 2: Verify the fix**

```bash
# Check the line is removed
rg "_UIA_INITIALIZED" src/system/screen_reader.py
```

Expected: No output (variable no longer referenced)

- [ ] **Step 3: Run screen_reader tests**

Run: `py -m pytest tests/ -k "screen" -v`

Expected: Any existing screen_reader tests PASS (or skip if no tests)

- [ ] **Step 4: Commit**

```bash
git add src/system/screen_reader.py
git commit -m "fix: remove dead _UIA_INITIALIZED global reference in screen_reader"
```

---

### Task 7: Fix EventStreamWorker — add 401/403 auth handling

**Files:**
- Modify: `src/system/event_worker.py:12-13,42-50`
- No tests exist for this file — manual verification via code review.

- [ ] **Step 1: Add `auth_failed` signal and 401/403 handling**

The `EventStreamWorker` has no HTTP status code handling. When `raise_for_status()` fires on 401/403, the generic catch block just logs and retries with backoff — the worker will retry forever without triggering token refresh.

Add an `auth_failed` signal and check the response status code before `raise_for_status()`:

```python
class EventStreamWorker(QThread):
    lsp_error_detected = pyqtSignal(dict)
    lsp_error_cleared = pyqtSignal()
    command_completed = pyqtSignal(str, int)
    file_edited = pyqtSignal(str)
    auth_failed = pyqtSignal()
```

In the `run()` method, add status code check between the response and `raise_for_status()`:

```python
def run(self):
    backoff = 3
    while self._running:
        try:
            self._response = requests.get(f"{self.server_url}/event", stream=True, timeout=60)
            # Check for auth failure before raise_for_status
            if self._response.status_code in (401, 403):
                logger.error("EventStreamWorker auth failure (HTTP %d)", self._response.status_code)
                self.auth_failed.emit()
                self._running = False
                break
            self._response.raise_for_status()
            backoff = 3
            for line in self._response.iter_lines():
                ...
        except Exception as e:
            if self._running:
                logger.error("EventStreamWorker network error: %s", e)
                time.sleep(backoff)
                backoff = min(backoff * 2, 15)
        finally:
            if self._response is not None:
                try:
                    self._response.close()
                except Exception:
                    pass
                self._response = None
```

- [ ] **Step 2: Verify the fix via code review**

Read the modified file to confirm:
```bash
rg "auth_failed" src/system/event_worker.py
```

Expected: 2 matches — signal declaration (line ~13) and emit call (line ~43)

- [ ] **Step 3: Commit**

```bash
git add src/system/event_worker.py
git commit -m "fix: add 401/403 auth handling to EventStreamWorker"
```

---

### Task 8: Fix template config — add missing dialogue_max_length

**Files:**
- Modify: `assets/daemon_config_template.json:103-104`

- [ ] **Step 1: Add `dialogue_max_length` to behavior section**

The template is missing `"dialogue_max_length": 150` which exists in the live config and is read by `get_structured_schema()`. Add it after `look_away_duration_ms`:

```json
    "look_away_duration_ms": 4000,
    "dialogue_max_length": 150
```

- [ ] **Step 2: Verify the fix**

```bash
rg "dialogue_max_length" assets/daemon_config_template.json
```

Expected: Shows `"dialogue_max_length": 150`

- [ ] **Step 3: Commit**

```bash
git add assets/daemon_config_template.json
git commit -m "fix: add missing dialogue_max_length to config template"
```

---

### Task 9: Run full regression test suite

- [ ] **Step 1: Run all tests**

```bash
py -m pytest tests/ -v --tb=short 2>&1
```

Expected: All previously failing tests now PASS. Total: 760+ passed, 1 skipped as before.

- [ ] **Step 2: If any failures remain, investigate and fix**

Check for any NEW failures introduced by the changes. The fixes in Tasks 1-8 should only affect the specific failing tests.

- [ ] **Step 3: Commit any additional fixes**

If any test fixes were needed beyond the planned changes, commit them with appropriate messages.

---

## Self-Review Checklist

- **Spec coverage:** All 8 test failures addressed (Tasks 1-5), all 3 code bugs fixed (Tasks 6-7), template gap filled (Task 8), regression verified (Task 9).
- **Placeholder scan:** No "TBD", "TODO", or incomplete code blocks. Every step has exact file paths, code changes, and expected test output.
- **Type consistency:** All method signatures and property names match existing code. No new types introduced beyond what's necessary.
