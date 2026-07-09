# Optimize Unit Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce test suite execution time to <50 seconds, remove redundant tests, and verify overall code coverage.

**Architecture:** The current slow tests (taking 500+ seconds globally and up to 15 seconds in teardown per test) are primarily caused by unmocked `QTimer` instances and `PetWindow` lifecycle leaks. By centralizing the instantiation and safe teardown of `PetWindow` in `conftest.py` and mocking background Qt event loops, we will speed up test execution exponentially.

**Tech Stack:** Python 3.14, pytest, PyQt6

---

### Task 1: Create Centralized PetWindow Fixture in conftest.py

**Files:**
- Modify: `C:/Users/ponna/Project/Daemon/tests/conftest.py`

- [ ] **Step 1: Write a failing placeholder test (optional/skip)**
- [ ] **Step 2: Add `safe_pet_window` fixture to conftest.py**
Implement a fixture that properly patches necessary background threads, creates `PetWindow`, and gracefully destroys it (stopping timers instead of running the 15-second `_trigger_ghost_summarization`).

```python
import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture
def safe_pet_window(app):
    with patch("src.ui.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.ui.pet_window.APMWorker"), \
         patch("src.ui.pet_window.MCPServer"), \
         patch("src.ui.pet_window.BehaviorController"), \
         patch("src.ui.pet_window.TTSWorker"):
        
        from src.ui.pet_window import PetWindow
        window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
        
        yield window
        
        # Fast teardown without 15s ghost summarization
        window._force_quit = True
        if hasattr(window, '_fsm_timer'): window._fsm_timer.stop()
        if hasattr(window, '_behavior_timer'): window._behavior_timer.stop()
        if hasattr(window, '_boot_timer'): window._boot_timer.stop()
        if hasattr(window, '_health_timer'): window._health_timer.stop()
        if hasattr(window, '_firestore_sync_timer'): window._firestore_sync_timer.stop()
        
        window.close()
        window.deleteLater()
```

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add safe_pet_window fixture to prevent teardown hangs"
```

### Task 2: Refactor `test_bubble_behavior.py`

**Files:**
- Modify: `C:/Users/ponna/Project/Daemon/tests/test_bubble_behavior.py`

- [ ] **Step 1: Replace all manual PetWindow instantiations with the fixture**
For all test methods in `test_bubble_behavior.py`, inject `safe_pet_window` and remove the massive `with patch(...)` blocks and manual `PetWindow(...)` instantiations.

```python
    def test_short_text_stays_single_page(self, safe_pet_window):
        from src.constants import BUBBLE_MAX_CHARS
        text = "Hello, world!"
        pages = safe_pet_window._paginate_text(text, BUBBLE_MAX_CHARS)
        assert len(pages) == 1
        assert pages[0] == text
```

- [ ] **Step 2: Consolidate Redundant Tests**
Merge `test_text_at_limit_stays_single_page` and `test_short_text_stays_single_page` into a single parameterized test or just combine them to reduce boilerplate and run time.

- [ ] **Step 3: Run the test file**

Run: `py -m pytest tests/test_bubble_behavior.py -v --durations=5`
Expected: PASS in < 5 seconds instead of 53+ seconds.

- [ ] **Step 4: Commit**

```bash
git add tests/test_bubble_behavior.py
git commit -m "test: use safe_pet_window fixture and consolidate bubble tests"
```

### Task 3: Refactor `test_pet_window_unit.py`

**Files:**
- Modify: `C:/Users/ponna/Project/Daemon/tests/test_pet_window_unit.py`

- [ ] **Step 1: Replace all manual PetWindow instantiations with the fixture**
For all test methods, inject `safe_pet_window` and remove manual setups. Remove duplicated tests.

- [ ] **Step 2: Run the test file**

Run: `py -m pytest tests/test_pet_window_unit.py -v --durations=5`
Expected: PASS rapidly without timer leakage.

- [ ] **Step 3: Commit**

```bash
git add tests/test_pet_window_unit.py
git commit -m "test: refactor pet_window_unit to use safe fixture"
```

### Task 4: Run Overall Tests and Measure Coverage

**Files:**
- None (CLI task)

- [ ] **Step 1: Verify suite completes in < 50s**

Run: `py -m pytest tests/ --durations=10`
Expected: PASS with total time under 50 seconds.

- [ ] **Step 2: Generate Coverage Report**

Run: `py -m pytest tests/ --cov=src --cov-report=term-missing`
Expected: Generate coverage report showing which lines in `src` are covered.

- [ ] **Step 3: Commit and summarize**
Log the coverage metrics and time savings in `memory/project-dev-memory.md` (or equivalent) to finish up the refactor.
