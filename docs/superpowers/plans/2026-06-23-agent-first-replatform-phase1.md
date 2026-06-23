# Agent-First Replatform Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replatform the codebase into domain-owned `system`, `llm`, `autonomy`, and `ui` packages so agents can edit smaller, isolated modules instead of reasoning through `src/pet_window.py` as the center of gravity.

**Architecture:** Preserve runtime behavior while moving ownership into domain-first packages. Extract leaf integrations first (`system`), then model/session orchestration (`llm`), then behavior coordination (`autonomy`), and finally the Qt shell (`ui`). Keep temporary root-level wrapper modules during the migration so imports remain stable while tests and callers move.

**Tech Stack:** Python 3.14, PyQt6, pytest, requests, Strands, opencode, Firebase Admin SDK, Windows platform integrations

## Global Constraints

- Use `py`, not `python` or `python3`.
- Full-suite verification command is `py -m pytest tests/ -v`.
- Never commit directly to `master`; use `task-<N>-<slug>` branch workflow.
- Update `memory/project-dev-memory.md` in the same task that changes repo architecture.
- Extraction order is fixed for this phase: `system -> llm -> autonomy -> ui`.
- Each stage must be independently test-backed and shippable.
- Temporary compatibility wrappers are allowed only as migration scaffolding.
- Docs and agent instructions must be updated in the same stage as the code move.
- Phase 1 is codebase decomposition only: no feature expansion, no UI redesign, no automation-rails work, no multi-agent-workflow work.

## File Structure

### New domain packages

- `src/system/__init__.py` — canonical export surface for platform-facing services.
- `src/system/active_window.py` — active-window lookup and title normalization.
- `src/system/apm_worker.py` — APM collection worker.
- `src/system/click_through.py` — transparent/opaque hit-testing integration.
- `src/system/event_worker.py` — event stream client and Qt signals.
- `src/system/screen_reader.py` — screen/UIA read utilities.
- `src/system/tts_worker.py` — speech playback worker.
- `src/system/typing_buffer.py` — typing capture buffer.

- `src/llm/__init__.py` — canonical export surface for LLM/session services.
- `src/llm/context_manager.py` — prompt/context assembly.
- `src/llm/llm_session_persistence.py` — session persistence helpers.
- `src/llm/opencode_worker.py` — opencode request/response worker.
- `src/llm/strands_worker.py` — Strands session and worker logic.

- `src/autonomy/__init__.py` — canonical export surface for autonomy services.
- `src/autonomy/behavior_controller.py` — behavior timing and trigger policy.
- `src/autonomy/response_manager.py` — response-pool persistence and decay.
- `src/autonomy/response_pool.py` — ThoughtPool behavior and refill signaling.
- `src/autonomy/reactions.py` — reminder and risky-typing reaction helpers extracted from `PetWindow`.

- `src/ui/__init__.py` — canonical export surface for UI services.
- `src/ui/context_menu.py` — tray/context menu UI.
- `src/ui/data_viewer_dialog.py` — memory/history viewer dialog.
- `src/ui/login_dialog.py` — auth dialog.
- `src/ui/pet_renderer.py` — paint/render layer.
- `src/ui/pet_window.py` — thin UI shell after extractions.
- `src/ui/settings_dialog.py` — settings UI.
- `src/ui/thought_log_dialog.py` — thought log UI.

### Root-level compatibility wrappers to keep temporarily

- `src/active_window.py`
- `src/apm_worker.py`
- `src/click_through.py`
- `src/context_manager.py`
- `src/event_worker.py`
- `src/llm_session_persistence.py`
- `src/opencode_worker.py`
- `src/response_manager.py`
- `src/response_pool.py`
- `src/screen_reader.py`
- `src/strands_worker.py`
- `src/tts_worker.py`
- `src/typing_buffer.py`
- `src/behavior_controller.py`
- `src/context_menu.py`
- `src/data_viewer_dialog.py`
- `src/login_dialog.py`
- `src/pet_renderer.py`
- `src/pet_window.py`
- `src/settings_dialog.py`
- `src/thought_log_dialog.py`

### New verification tests

- `tests/system/test_import_surface.py` — verifies new `src.system` import surface and legacy wrappers.
- `tests/llm/test_import_surface.py` — verifies new `src.llm` import surface and legacy wrappers.
- `tests/autonomy/test_reactions.py` — covers reminder and risky-typing extraction behavior.
- `tests/ui/test_import_surface.py` — verifies new `src.ui` import surface and legacy wrappers.
- `tests/test_package_layout.py` — AST/import boundary guard for forbidden cross-domain imports.

---

### Task 1: Extract `system` Package

**Files:**
- Create: `src/system/__init__.py`
- Create: `src/system/active_window.py`
- Create: `src/system/apm_worker.py`
- Create: `src/system/click_through.py`
- Create: `src/system/event_worker.py`
- Create: `src/system/screen_reader.py`
- Create: `src/system/tts_worker.py`
- Create: `src/system/typing_buffer.py`
- Create: `tests/system/test_import_surface.py`
- Modify: `src/active_window.py`
- Modify: `src/apm_worker.py`
- Modify: `src/click_through.py`
- Modify: `src/event_worker.py`
- Modify: `src/screen_reader.py`
- Modify: `src/tts_worker.py`
- Modify: `src/typing_buffer.py`
- Modify: `src/pet_window.py`
- Test: `tests/test_event_worker.py`
- Test: `tests/test_tts_worker.py`
- Test: `tests/test_typing_buffer.py`

**Interfaces:**
- Consumes: existing implementations in root modules listed above.
- Produces: `src.system.APMWorker`, `src.system.TypingBuffer`, `src.system.ClickThroughManager`, `src.system.EventStreamWorker`, `src.system.ScreenReader`, `src.system.TTSWorker`, `src.system.get_active_window_title`, `src.system.normalize_window_title`.
- Produces: legacy wrappers that continue exporting the same symbols from the original root module paths.

- [ ] **Step 1: Write the failing import-surface test**

```python
# tests/system/test_import_surface.py
from src.system import (
    APMWorker,
    ClickThroughManager,
    EventStreamWorker,
    ScreenReader,
    TTSWorker,
    TypingBuffer,
    get_active_window_title,
    normalize_window_title,
)
from src.apm_worker import APMWorker as LegacyAPMWorker
from src.click_through import ClickThroughManager as LegacyClickThroughManager
from src.event_worker import EventStreamWorker as LegacyEventStreamWorker
from src.screen_reader import ScreenReader as LegacyScreenReader
from src.tts_worker import TTSWorker as LegacyTTSWorker
from src.typing_buffer import TypingBuffer as LegacyTypingBuffer
from src.active_window import (
    get_active_window_title as legacy_get_active_window_title,
    normalize_window_title as legacy_normalize_window_title,
)


def test_system_package_exports_current_services():
    assert APMWorker is LegacyAPMWorker
    assert ClickThroughManager is LegacyClickThroughManager
    assert EventStreamWorker is LegacyEventStreamWorker
    assert ScreenReader is LegacyScreenReader
    assert TTSWorker is LegacyTTSWorker
    assert TypingBuffer is LegacyTypingBuffer
    assert get_active_window_title is legacy_get_active_window_title
    assert normalize_window_title is legacy_normalize_window_title
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `py -m pytest tests/system/test_import_surface.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.system'`

- [ ] **Step 3: Create `src.system`, move implementations, and reduce root modules to wrappers**

```python
# src/system/__init__.py
from .active_window import get_active_window_title, normalize_window_title
from .apm_worker import APMWorker
from .click_through import ClickThroughManager
from .event_worker import EventStreamWorker
from .screen_reader import ScreenReader
from .tts_worker import TTSWorker
from .typing_buffer import TypingBuffer

__all__ = [
    "APMWorker",
    "ClickThroughManager",
    "EventStreamWorker",
    "ScreenReader",
    "TTSWorker",
    "TypingBuffer",
    "get_active_window_title",
    "normalize_window_title",
]
```

```python
# src/apm_worker.py
from src.system.apm_worker import APMWorker

__all__ = ["APMWorker"]
```

```python
# src/active_window.py
from src.system.active_window import get_active_window_title, normalize_window_title

__all__ = ["get_active_window_title", "normalize_window_title"]
```

```python
# src/pet_window.py (import section only)
from src.system import (
    APMWorker,
    ClickThroughManager,
    EventStreamWorker,
    ScreenReader,
    TTSWorker,
    TypingBuffer,
    get_active_window_title,
    normalize_window_title,
)
```

Implementation note: copy the current implementation bodies from each root module into the matching `src/system/` file unchanged first, then convert the original root file into a wrapper like the examples above.

- [ ] **Step 4: Run focused verification for `system`**

Run: `py -m pytest tests/system/test_import_surface.py tests/test_event_worker.py tests/test_tts_worker.py tests/test_typing_buffer.py tests/test_active_window.py tests/test_click_through.py -v`

Expected: PASS for all selected tests

- [ ] **Step 5: Commit**

```bash
git checkout -b task-<N>-system-package-extraction
git add src/system tests/system src/active_window.py src/apm_worker.py src/click_through.py src/event_worker.py src/screen_reader.py src/tts_worker.py src/typing_buffer.py src/pet_window.py
git commit -m "refactor: extract system package"
```

### Task 2: Extract `llm` Package

**Files:**
- Create: `src/llm/__init__.py`
- Create: `src/llm/context_manager.py`
- Create: `src/llm/llm_session_persistence.py`
- Create: `src/llm/opencode_worker.py`
- Create: `src/llm/strands_worker.py`
- Create: `tests/llm/test_import_surface.py`
- Modify: `src/context_manager.py`
- Modify: `src/llm_session_persistence.py`
- Modify: `src/opencode_worker.py`
- Modify: `src/strands_worker.py`
- Modify: `src/pet_window.py`
- Test: `tests/test_context_manager.py`
- Test: `tests/test_llm_session_persistence.py`
- Test: `tests/test_opencode_worker.py`
- Test: `tests/test_strands_worker.py`

**Interfaces:**
- Consumes: current `ContextManager`, `LLMSessionState`, `load_session`, `save_session`, `OpencodeWorker`, `StrandsAutonomousWorker`, `StrandsSession`, `extract_dialogue_stream`.
- Produces: `src.llm.ContextManager`, `src.llm.LLMSessionState`, `src.llm.load_session`, `src.llm.save_session`, `src.llm.OpencodeWorker`, `src.llm.StrandsAutonomousWorker`, `src.llm.StrandsSession`, `src.llm.extract_dialogue_stream`.
- Produces: legacy wrapper modules that continue exporting the same symbols from original root paths.

- [ ] **Step 1: Write the failing import-surface test for `llm`**

```python
# tests/llm/test_import_surface.py
from src.llm import (
    ContextManager,
    LLMSessionState,
    OpencodeWorker,
    StrandsAutonomousWorker,
    StrandsSession,
    extract_dialogue_stream,
    load_session,
    save_session,
)
from src.context_manager import ContextManager as LegacyContextManager
from src.llm_session_persistence import (
    LLMSessionState as LegacyLLMSessionState,
    load_session as legacy_load_session,
    save_session as legacy_save_session,
)
from src.opencode_worker import OpencodeWorker as LegacyOpencodeWorker
from src.strands_worker import (
    StrandsAutonomousWorker as LegacyStrandsAutonomousWorker,
    StrandsSession as LegacyStrandsSession,
    extract_dialogue_stream as legacy_extract_dialogue_stream,
)


def test_llm_package_exports_current_services():
    assert ContextManager is LegacyContextManager
    assert LLMSessionState is LegacyLLMSessionState
    assert load_session is legacy_load_session
    assert save_session is legacy_save_session
    assert OpencodeWorker is LegacyOpencodeWorker
    assert StrandsAutonomousWorker is LegacyStrandsAutonomousWorker
    assert StrandsSession is LegacyStrandsSession
    assert extract_dialogue_stream is legacy_extract_dialogue_stream
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `py -m pytest tests/llm/test_import_surface.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.llm'`

- [ ] **Step 3: Create `src.llm`, move implementations, and convert root modules to wrappers**

```python
# src/llm/__init__.py
from .context_manager import ContextManager
from .llm_session_persistence import LLMSessionState, load_session, save_session
from .opencode_worker import OpencodeWorker
from .strands_worker import (
    StrandsAutonomousWorker,
    StrandsSession,
    extract_dialogue_stream,
)

__all__ = [
    "ContextManager",
    "LLMSessionState",
    "OpencodeWorker",
    "StrandsAutonomousWorker",
    "StrandsSession",
    "extract_dialogue_stream",
    "load_session",
    "save_session",
]
```

```python
# src/opencode_worker.py
from src.llm.opencode_worker import OpencodeWorker

__all__ = ["OpencodeWorker"]
```

```python
# src/strands_worker.py
from src.llm.strands_worker import (
    StrandsAutonomousWorker,
    StrandsSession,
    extract_dialogue_stream,
)

__all__ = ["StrandsAutonomousWorker", "StrandsSession", "extract_dialogue_stream"]
```

```python
# src/pet_window.py (import section only)
from src.llm import (
    ContextManager,
    LLMSessionState,
    OpencodeWorker,
    StrandsAutonomousWorker,
    StrandsSession,
    load_session,
    save_session,
)
```

Implementation note: copy current implementations into `src/llm/` first, then reduce the original root files to wrappers as above.

- [ ] **Step 4: Run focused verification for `llm`**

Run: `py -m pytest tests/llm/test_import_surface.py tests/test_context_manager.py tests/test_llm_session_persistence.py tests/test_opencode_worker.py tests/test_strands_worker.py -v`

Expected: PASS for all selected tests

- [ ] **Step 5: Commit**

```bash
git add src/llm tests/llm src/context_manager.py src/llm_session_persistence.py src/opencode_worker.py src/strands_worker.py src/pet_window.py
git commit -m "refactor: extract llm package"
```

### Task 3: Extract `autonomy` Package and Reaction Helpers

**Files:**
- Create: `src/autonomy/__init__.py`
- Create: `src/autonomy/behavior_controller.py`
- Create: `src/autonomy/response_manager.py`
- Create: `src/autonomy/response_pool.py`
- Create: `src/autonomy/reactions.py`
- Create: `tests/autonomy/test_reactions.py`
- Modify: `src/behavior_controller.py`
- Modify: `src/response_manager.py`
- Modify: `src/response_pool.py`
- Modify: `src/pet_window.py`
- Test: `tests/test_behavior_controller.py`
- Test: `tests/test_response_manager.py`
- Test: `tests/test_response_pool.py`
- Test: `tests/test_fsm_migration.py`

**Interfaces:**
- Consumes: existing `BehaviorController`, `AutonomousResponseManager`, `ThoughtPool`, reminder handling in `PetWindow._fire_reminder`, and risky-typing handling in `PetWindow._on_typing_debounce`.
- Produces: `src.autonomy.BehaviorController`, `src.autonomy.AutonomousResponseManager`, `src.autonomy.ThoughtPool`.
- Produces: `src.autonomy.reactions.build_reminder_effect(reminders: dict, rem_id: str, msg: str) -> dict`.
- Produces: `src.autonomy.reactions.evaluate_risky_typing_reaction(typing_content: str, current_len: int, last_len: int, risky_keywords: dict[str, list[dict]]) -> dict | None`.

- [ ] **Step 1: Write failing regression tests for extracted reactions**

```python
# tests/autonomy/test_reactions.py
from src.autonomy.reactions import build_reminder_effect, evaluate_risky_typing_reaction


def test_build_reminder_effect_returns_expression_action_not_deleted_fsm_state():
    reminders = {"abc": object()}
    effect = build_reminder_effect(reminders, "abc", "ship it")
    assert effect["removed"] is True
    assert effect["bubble"] == "ship it"
    assert effect["toast"] == ("Reminder", "ship it")
    assert effect["expression_action"]["name"] == "bounce"


def test_evaluate_risky_typing_reaction_returns_dialogue_and_action():
    risky_keywords = {
        "rm -rf": [{"dialogue": "Nope.", "action": "shake"}],
    }
    effect = evaluate_risky_typing_reaction(
        typing_content="please do rm -rf / now",
        current_len=23,
        last_len=0,
        risky_keywords=risky_keywords,
    )
    assert effect is not None
    assert effect["dialogue"] == "Nope."
    assert effect["action"] == "shake"
    assert effect["matched_keyword"] == "rm -rf"
    assert effect["new_last_len"] == 23
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `py -m pytest tests/autonomy/test_reactions.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.autonomy'`

- [ ] **Step 3: Create `src.autonomy`, move existing modules, and extract reminder/risky-typing helpers**

```python
# src/autonomy/__init__.py
from .behavior_controller import BehaviorController
from .response_manager import AutonomousResponseManager
from .response_pool import ThoughtPool
from .reactions import build_reminder_effect, evaluate_risky_typing_reaction

__all__ = [
    "AutonomousResponseManager",
    "BehaviorController",
    "ThoughtPool",
    "build_reminder_effect",
    "evaluate_risky_typing_reaction",
]
```

```python
# src/autonomy/reactions.py
from __future__ import annotations

import random
import re


def build_reminder_effect(reminders: dict, rem_id: str, msg: str) -> dict:
    removed = rem_id in reminders
    if removed:
        del reminders[rem_id]
    return {
        "removed": removed,
        "toast": ("Reminder", msg),
        "bubble": msg,
        "expression_action": {"name": "bounce", "duration_ms": 3000, "params": {}},
    }


def evaluate_risky_typing_reaction(
    typing_content: str,
    current_len: int,
    last_len: int,
    risky_keywords: dict[str, list[dict]],
) -> dict | None:
    lower = typing_content.lower()
    for keyword, responses in risky_keywords.items():
        kw = keyword.lower()
        matched = re.search(r"\b" + re.escape(kw) + r"\b", lower) if kw[-1].isalpha() else (kw in lower)
        if not matched:
            continue
        item = random.choice(responses)
        return {
            "dialogue": item["dialogue"],
            "action": item["action"],
            "matched_keyword": keyword,
            "new_last_len": current_len,
        }
    if current_len <= last_len:
        return None
    return None
```

```python
# src/pet_window.py (reaction call sites only)
from src.autonomy import (
    AutonomousResponseManager,
    BehaviorController,
    build_reminder_effect,
    evaluate_risky_typing_reaction,
)
```

```python
# src/pet_window.py (_fire_reminder sketch)
effect = build_reminder_effect(self._reminders, rem_id, msg)
self._on_toast_requested(*effect["toast"])
self._bubble_queue.append((effect["bubble"], time.time()))
self._show_next_bubble()
self._action_layer.trigger(
    effect["expression_action"]["name"],
    effect["expression_action"]["duration_ms"],
    effect["expression_action"]["params"],
)
```

```python
# src/pet_window.py (_on_typing_debounce sketch)
effect = evaluate_risky_typing_reaction(
    typing_content=typing_content,
    current_len=current_len,
    last_len=self._typing_last_len,
    risky_keywords=RISKY_KEYWORDS,
)
if effect is not None:
    self._clear_bubble_queue()
    self._show_bubble(effect["dialogue"])
    self._action_layer.trigger(effect["action"])
    self._typing_last_len = effect["new_last_len"]
    self._behavior.set_risky_match(effect["matched_keyword"])
    return
```

Implementation note: move the current `behavior_controller.py`, `response_manager.py`, and `response_pool.py` bodies under `src/autonomy/` unchanged first, then convert the original root files into wrappers exactly like Tasks 1 and 2.

- [ ] **Step 4: Run focused verification for `autonomy`**

Run: `py -m pytest tests/autonomy/test_reactions.py tests/test_behavior_controller.py tests/test_response_manager.py tests/test_response_pool.py tests/test_fsm_migration.py -v`

Expected: PASS for all selected tests

- [ ] **Step 5: Commit**

```bash
git add src/autonomy tests/autonomy src/behavior_controller.py src/response_manager.py src/response_pool.py src/pet_window.py
git commit -m "refactor: extract autonomy package"
```

### Task 4: Extract `ui` Package and Shrink `PetWindow` Ownership

**Files:**
- Create: `src/ui/__init__.py`
- Create: `src/ui/context_menu.py`
- Create: `src/ui/data_viewer_dialog.py`
- Create: `src/ui/login_dialog.py`
- Create: `src/ui/pet_renderer.py`
- Create: `src/ui/pet_window.py`
- Create: `src/ui/settings_dialog.py`
- Create: `src/ui/thought_log_dialog.py`
- Create: `tests/ui/test_import_surface.py`
- Modify: `src/context_menu.py`
- Modify: `src/data_viewer_dialog.py`
- Modify: `src/login_dialog.py`
- Modify: `src/pet_renderer.py`
- Modify: `src/pet_window.py`
- Modify: `src/settings_dialog.py`
- Modify: `src/thought_log_dialog.py`
- Modify: `daemon.py`
- Test: `tests/test_pet_window_unit.py`
- Test: `tests/test_pet_renderer.py`
- Test: `tests/test_settings_dialog.py`
- Test: `tests/test_login_dialog.py`
- Test: `tests/test_data_viewer_dialog.py`
- Test: `tests/test_thought_log_dialog.py`

**Interfaces:**
- Consumes: existing UI classes `PetWindow`, `PetRenderer`, `PetContextMenu`, `SettingsDialog`, `LoginDialog`, `ThoughtLogDialog`, `DataViewerDialog`.
- Produces: `src.ui.PetWindow`, `src.ui.PetRenderer`, `src.ui.PetContextMenu`, `src.ui.SettingsDialog`, `src.ui.LoginDialog`, `src.ui.ThoughtLogDialog`, `src.ui.DataViewerDialog`.
- Produces: root-level wrapper modules that preserve existing imports during the migration.

- [ ] **Step 1: Write the failing `ui` import-surface test**

```python
# tests/ui/test_import_surface.py
from src.ui import (
    DataViewerDialog,
    LoginDialog,
    PetContextMenu,
    PetRenderer,
    PetWindow,
    SettingsDialog,
    ThoughtLogDialog,
)
from src.context_menu import PetContextMenu as LegacyPetContextMenu
from src.data_viewer_dialog import DataViewerDialog as LegacyDataViewerDialog
from src.login_dialog import LoginDialog as LegacyLoginDialog
from src.pet_renderer import PetRenderer as LegacyPetRenderer
from src.pet_window import PetWindow as LegacyPetWindow
from src.settings_dialog import SettingsDialog as LegacySettingsDialog
from src.thought_log_dialog import ThoughtLogDialog as LegacyThoughtLogDialog


def test_ui_package_exports_current_widgets():
    assert PetContextMenu is LegacyPetContextMenu
    assert DataViewerDialog is LegacyDataViewerDialog
    assert LoginDialog is LegacyLoginDialog
    assert PetRenderer is LegacyPetRenderer
    assert PetWindow is LegacyPetWindow
    assert SettingsDialog is LegacySettingsDialog
    assert ThoughtLogDialog is LegacyThoughtLogDialog
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `py -m pytest tests/ui/test_import_surface.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.ui'`

- [ ] **Step 3: Create `src.ui`, move UI modules, and switch the app entry point to the new package**

```python
# src/ui/__init__.py
from .context_menu import PetContextMenu
from .data_viewer_dialog import DataViewerDialog
from .login_dialog import LoginDialog
from .pet_renderer import PetRenderer
from .pet_window import PetWindow
from .settings_dialog import SettingsDialog
from .thought_log_dialog import ThoughtLogDialog

__all__ = [
    "DataViewerDialog",
    "LoginDialog",
    "PetContextMenu",
    "PetRenderer",
    "PetWindow",
    "SettingsDialog",
    "ThoughtLogDialog",
]
```

```python
# src/pet_window.py
from src.ui.pet_window import PetWindow

__all__ = ["PetWindow"]
```

```python
# daemon.py (import section only)
from src.ui.pet_window import PetWindow
```

Implementation note: move the current UI module bodies into `src/ui/` first, then convert the original root files into wrappers. Do not add new behavior in this task; the goal is to leave a thinner UI shell on top of the already-extracted `system`, `llm`, and `autonomy` domains.

- [ ] **Step 4: Run focused verification for `ui`**

Run: `py -m pytest tests/ui/test_import_surface.py tests/test_pet_window_unit.py tests/test_pet_renderer.py tests/test_settings_dialog.py tests/test_login_dialog.py tests/test_data_viewer_dialog.py tests/test_thought_log_dialog.py -v`

Expected: PASS for all selected tests

- [ ] **Step 5: Commit**

```bash
git add src/ui tests/ui src/context_menu.py src/data_viewer_dialog.py src/login_dialog.py src/pet_renderer.py src/pet_window.py src/settings_dialog.py src/thought_log_dialog.py daemon.py
git commit -m "refactor: extract ui package"
```

### Task 5: Add Boundary Guards and Update Docs

**Files:**
- Create: `tests/test_package_layout.py`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/architecture.md`
- Modify: `memory/project-dev-memory.md`
- Test: `tests/test_package_layout.py`

**Interfaces:**
- Consumes: the new package layout from Tasks 1-4.
- Produces: AST-based checks that forbid `system -> ui`, `system -> llm`, and `llm -> ui` imports.
- Produces: updated docs that describe the canonical package boundaries and phase-1 completion state.

- [ ] **Step 1: Write the failing layout-guard test**

```python
# tests/test_package_layout.py
from pathlib import Path
import ast


ROOT = Path("src")


def _imports_in(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                found.append(alias.name)
    return found


def test_system_does_not_import_ui_or_llm():
    for path in ROOT.joinpath("system").glob("*.py"):
        imports = _imports_in(path)
        assert not any(name.startswith("src.ui") for name in imports), path
        assert not any(name.startswith("src.llm") for name in imports), path


def test_llm_does_not_import_ui():
    for path in ROOT.joinpath("llm").glob("*.py"):
        imports = _imports_in(path)
        assert not any(name.startswith("src.ui") for name in imports), path
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `py -m pytest tests/test_package_layout.py -v`

Expected: FAIL before Tasks 1-4 are complete because the package directories and import boundaries do not yet exist or are not yet clean.

- [ ] **Step 3: Update docs to match the new package structure and current workflow**

```markdown
# README.md changes to make
- Replace root-module architecture descriptions with the four domain packages.
- Update storage-path documentation to match `data/`-based paths.
- Replace stale test counts with the current full-suite result captured during this task.
- Document the canonical import direction: `ui -> autonomy -> {llm, system}`.
```

```markdown
# AGENTS.md changes to make
- Remove or repair the broken `@RTK.md` instruction reference.
- Add the new package ownership map under the architecture/file-map sections.
- Explicitly tell future agents to prefer the domain package over legacy wrappers when editing.
```

```markdown
# memory/project-dev-memory.md changes to make
- Add a phase entry summarizing the package extraction and the new canonical layout.
- Record exact test results from final verification.
```

- [ ] **Step 4: Run final full verification**

Run: `py -m pytest tests/ -v`

Expected: PASS with zero new failures and the current total test count reported by pytest

- [ ] **Step 5: Commit**

```bash
git add tests/test_package_layout.py README.md AGENTS.md docs/architecture.md memory/project-dev-memory.md
git commit -m "docs: codify domain boundaries"
```

## Self-Review

- Spec coverage: the plan covers all four approved domains, the required extraction order, compatibility shims, regression coverage for reminder/risky-typing paths, and docs alignment.
- Placeholder scan: no `TBD`, `TODO`, or “implement later” placeholders remain in task steps.
- Type consistency: all exported symbols and package names match the approved design: `system`, `llm`, `autonomy`, `ui`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-23-agent-first-replatform-phase1.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
