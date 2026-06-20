# Context Menu Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Overhaul the right-click context menu with new actions (Sleep, Mute, Wipe), generic data viewers, and heavy Kenny persona flavor based on the High on Life reference.

**Architecture:** We will create a generic `DataViewerDialog` based on the existing Matrix-style window, restructure `PetContextMenu` with QMenu submenus, and wire new logic to `PetWindow` for state management and destructive wiping. Finally, we'll perform a persona dialogue pass on prompts and hardcoded strings.

**Tech Stack:** Python 3.11+, PyQt6

---

### Task 1: Generic Data Viewer Dialog

**Files:**
- Create: `src/data_viewer_dialog.py`
- Create: `tests/test_data_viewer_dialog.py`
- Modify: `src/thought_log_dialog.py` (make it a subclass or just use the new one directly)

- [ ] **Step 1: Write the failing test for DataViewerDialog**
```python
import pytest
from PyQt6.QtWidgets import QApplication
from src.data_viewer_dialog import DataViewerDialog

def test_data_viewer_dialog_initialization(qapp):
    dialog = DataViewerDialog(title="Test Viewer", content="Sample content\nLine 2")
    assert dialog.windowTitle() == "Test Viewer"
    assert "Sample content" in dialog._text_edit.toPlainText()
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_data_viewer_dialog.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Write minimal implementation**
Create `src/data_viewer_dialog.py` by extracting the visual shell of `ThoughtLogDialog` (Matrix-style green text on black, monospace). Remove the log-tailing timer. Pass static text string or text generation callable.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_data_viewer_dialog.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add src/data_viewer_dialog.py tests/test_data_viewer_dialog.py
git commit -m "feat(ui): create generic DataViewerDialog for text logs"
```

### Task 2: Refactor Context Menu Hierarchy

**Files:**
- Modify: `src/context_menu.py`
- Modify: `tests/test_context_menu.py` (if it exists, create if not)

- [ ] **Step 1: Update Context Menu Implementation**
Modify `src/context_menu.py` to add `sleep_toggle`, `mute_toggle`, and `wipe_memory` to `_Signals`. Rebuild the menu hierarchy with a `Brain Ops` QMenu submenu. Add Checkable actions for Pin, Sleep, and Mute.

- [ ] **Step 2: Test Context Menu structure**
Run tests on `context_menu.py` to ensure the correct signals exist and actions are added to submenus. Update tests as necessary.

- [ ] **Step 3: Commit**
```bash
git add src/context_menu.py tests/test_context_menu.py
git commit -m "feat(ui): overhaul context menu hierarchy and signals"
```

### Task 3: PetWindow Wiring (Mute and Sleep)

**Files:**
- Modify: `src/pet_window.py`
- Modify: `tests/test_pet_window.py`

- [ ] **Step 1: Write failing tests**
Write tests for `_on_sleep_toggle` ensuring it sets `self._forced_sleep = True` and transitions FSM to `PetState.SLEEP`. Write test for `_on_mute_toggle` ensuring it calls `_apply_settings(tts_enabled=not current)`.

- [ ] **Step 2: Implement handlers in PetWindow**
Add `_forced_sleep` to `__init__`. Wire the new context menu signals. In `_should_fire_autonomous()`, guard against `_forced_sleep`. 

- [ ] **Step 3: Test and Commit**
Run tests.
```bash
git add src/pet_window.py tests/test_pet_window.py
git commit -m "feat: implement forced sleep and mute toggle logic"
```

### Task 4: Data Viewer Integration (Memory & History)

**Files:**
- Modify: `src/pet_window.py`

- [ ] **Step 1: Replace bubble output with Dialogs**
Update `_on_recall_memory` to fetch `self._memory.get_all()`, format it nicely into a large string, and launch a `DataViewerDialog("Memory", content)`. Update `_on_recall_history` similarly.

- [ ] **Step 2: Refactor Thought Log**
Update `_open_thought_log` to use `DataViewerDialog` with an auto-refresh timer, or keep `ThoughtLogDialog` as a subclass of `DataViewerDialog`.

- [ ] **Step 3: Test and Commit**
Run tests.
```bash
git add src/pet_window.py
git commit -m "feat(ui): use DataViewerDialog for memory and history recall"
```

### Task 5: Lobotomy (Wipe Memory) Implementation

**Files:**
- Modify: `src/pet_window.py`

- [ ] **Step 1: Implement Lobotomy Handler**
Implement `_on_wipe_memory` in `pet_window.py`. Use `QMessageBox` to chain the 3 Kenny-flavored confirmation popups. If all 3 pass, clear `self._memory`, `self._history`, `self._diary_store`. Clear from `self._crud` if `self._firebase_available` is True. Reset `ContextManager`.

- [ ] **Step 2: Test Lobotomy Flow**
Write tests in `test_pet_window.py` simulating the popup flow (can mock `QMessageBox.exec`).

- [ ] **Step 3: Commit**
```bash
git add src/pet_window.py tests/test_pet_window.py
git commit -m "feat: implement triple-confirmation lobotomy wipe"
```

### Task 6: Persona & Dialogue Pass

**Files:**
- Modify: `src/constants.py` (for hardcoded `_LOGIN_PROMPT`, etc.)
- Modify: `.opencode/skills/kenny/SKILL.md` (or wherever Kenny prompt is)

- [ ] **Step 1: Overhaul LLM Prompts & Hardcoded Strings**
Update the instructions for Kenny to emphasize High on Life persona traits: long-winded anxious rambling, stuttering ("wha-what", "I-I-I"), 4th wall breaks, desktop-context references (Task Manager, Recycle Bin).

- [ ] **Step 2: Commit**
```bash
git add src/constants.py .opencode/skills/kenny/SKILL.md
git commit -m "feat(persona): apply High on Life Kenny dialogue styling"
```
