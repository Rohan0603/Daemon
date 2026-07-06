# IDE Coding Assistant Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a recognized coding IDE is the active window, Daemon enters Code Mode -- TRANQUILITY emotion replaced by a DISTINCT visual mode (teal/cyan body tint + blinking terminal cursor overlay rendered by PetRenderer), ThoughtPool draws code_assist types, and IDE-context-enriched prompts so Kenny proactively gives coding advice in full gremlin mode.

**Architecture:** `is_ide_window()` detection to `_in_ide_mode` flag in `BehaviorController` to `IDE_MODE_ENTERED/EXITED` events to `ide_mode` field on `RenderContext` to PetRenderer teal tint + cursor blink overlay to `code_assist` draw type to `build_autonomous_trigger(ide_mode=True)` richer prompt to `SKILL.md` coding mode persona rules.

**Tech Stack:** Python 3.14, PyQt6, existing EventBus, existing ThoughtPool, existing PetRenderer/RenderContext pipeline.

---

## File Map

| File | Role | Action |
|------|------|--------|
| `src/system/active_window.py` | IDE window detection | Add `is_ide_window()` + `_IDE_SLUGS` |
| `src/active_window.py` | Re-export stub | Add `is_ide_window` to `__all__` |
| `src/events.py` | Event definitions | Add `IDE_MODE_ENTERED`, `IDE_MODE_EXITED` to `EventType`; add `ide_mode`/`ide_name`/`draw_type` to `emit_autonomous_trigger` |
| `src/constants.py` | Schema | Add `code_assist` to `STRUCTURED_SCHEMA` enum |
| `src/autonomy/behavior_controller.py` | Core behavior loop | `_in_ide_mode` state, `_check_ide_mode_transition()`, draw-type switching in triggers |
| `src/ui/pet_renderer.py` | Visual rendering | `ide_mode: bool` field on `RenderContext`; teal tint in `_body_color()`; blinking cursor in `_draw_state_overlay()` |
| `src/ui/pet_window.py` | Wiring | Set `ctx.ide_mode` when building `RenderContext`; extract `ide_mode`/`ide_name`/`draw_type` from autonomous trigger event |
| `src/llm/context_manager.py` | Prompt building | `ide_mode`/`ide_name` params on `build_autonomous_trigger` |
| `.opencode/skills/kenny/SKILL.md` | LLM persona | New CODING ASSISTANT MODE section |
| `tests/test_active_window.py` | Tests | `is_ide_window` tests |
| `tests/test_behavior_controller_ide.py` | Tests | IDE mode state, event, draw-type tests (new file) |
| `tests/test_pet_renderer_ide.py` | Tests | Teal tint, cursor overlay render tests (new file) |

---

## Task 1: is_ide_window() Detection

**Files:**
- Modify: `src/system/active_window.py`
- Modify: `src/active_window.py`
- Modify: `tests/test_active_window.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_active_window.py`:

```python
def test_is_ide_window_vscode():
    from src.system.active_window import is_ide_window
    assert is_ide_window("main.py - Visual Studio Code") is True

def test_is_ide_window_pycharm():
    from src.system.active_window import is_ide_window
    assert is_ide_window("my_project - PyCharm") is True

def test_is_ide_window_non_ide():
    from src.system.active_window import is_ide_window
    assert is_ide_window("Discord") is False

def test_is_ide_window_empty():
    from src.system.active_window import is_ide_window
    assert is_ide_window("") is False

def test_is_ide_window_intellij():
    from src.system.active_window import is_ide_window
    assert is_ide_window("project [main] - IntelliJ IDEA") is True

def test_is_ide_window_sublime():
    from src.system.active_window import is_ide_window
    assert is_ide_window("untitled - Sublime Text") is True
```

- [ ] **Step 2: Run to verify they fail**

Run: `py -m pytest tests/test_active_window.py::test_is_ide_window_vscode -v`
Expected: FAILED -- ImportError: cannot import name 'is_ide_window'

- [ ] **Step 3: Implement is_ide_window in src/system/active_window.py**

Add after `normalize_window_title()` (around line 78):

```python
_IDE_SLUGS: frozenset[str] = frozenset({
    "vscode", "pycharm", "intellij", "webstorm",
    "goland", "sublime_text", "notepadpp",
})

def is_ide_window(title: str) -> bool:
    """Return True if the window title belongs to a recognized coding IDE."""
    if not title:
        return False
    return normalize_window_title(title) in _IDE_SLUGS
```

- [ ] **Step 4: Add to re-export stub src/active_window.py**

```python
from src.system.active_window import get_active_window_title, normalize_window_title, get_window_rect, is_ide_window

__all__ = ["get_active_window_title", "normalize_window_title", "get_window_rect", "is_ide_window"]
```

- [ ] **Step 5: Run all active_window tests**

Run: `py -m pytest tests/test_active_window.py -v`
Expected: all 9 tests PASS (3 original + 6 new)

- [ ] **Step 6: Commit**

```
git add src/system/active_window.py src/active_window.py tests/test_active_window.py
git commit -m "feat(active_window): add is_ide_window() detection"
```

---

## Task 2: EventType -- IDE_MODE_ENTERED / IDE_MODE_EXITED

**Files:**
- Modify: `src/events.py`
- Create: `tests/test_behavior_controller_ide.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_behavior_controller_ide.py`:

```python
from src.events import EventType

def test_ide_event_types_exist():
    assert hasattr(EventType, "IDE_MODE_ENTERED")
    assert hasattr(EventType, "IDE_MODE_EXITED")
    assert EventType.IDE_MODE_ENTERED.value == "ide_mode_entered"
    assert EventType.IDE_MODE_EXITED.value == "ide_mode_exited"
```

- [ ] **Step 2: Run to verify it fails**

Run: `py -m pytest tests/test_behavior_controller_ide.py::test_ide_event_types_exist -v`
Expected: FAILED -- AttributeError: IDE_MODE_ENTERED

- [ ] **Step 3: Add to EventType enum in src/events.py**

After the `PET_SHUTDOWN_STARTED` line (around line 83), add:

```python
    # IDE / Coding Mode Events
    IDE_MODE_ENTERED = "ide_mode_entered"
    IDE_MODE_EXITED = "ide_mode_exited"
```

- [ ] **Step 4: Run test**

Run: `py -m pytest tests/test_behavior_controller_ide.py::test_ide_event_types_exist -v`
Expected: PASS

- [ ] **Step 5: Commit**

```
git add src/events.py tests/test_behavior_controller_ide.py
git commit -m "feat(events): add IDE_MODE_ENTERED and IDE_MODE_EXITED event types"
```

---

## Task 3: STRUCTURED_SCHEMA -- add code_assist type

**Files:**
- Modify: `src/constants.py`
- Modify: `tests/test_behavior_controller_ide.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_behavior_controller_ide.py`:

```python
from src.constants import STRUCTURED_SCHEMA

def test_code_assist_in_schema():
    enum_vals = STRUCTURED_SCHEMA["items"]["properties"]["type"]["enum"]
    assert "code_assist" in enum_vals
```

- [ ] **Step 2: Run to verify it fails**

Run: `py -m pytest tests/test_behavior_controller_ide.py::test_code_assist_in_schema -v`
Expected: FAILED -- AssertionError

- [ ] **Step 3: Edit STRUCTURED_SCHEMA in src/constants.py (lines 33-42)**

Change the enum list:
`'enum': ['typing_reaction', 'observation', 'intel_roast', 'idle_thought']`
To:
`'enum': ['typing_reaction', 'observation', 'intel_roast', 'idle_thought', 'code_assist']`

- [ ] **Step 4: Run test**

Run: `py -m pytest tests/test_behavior_controller_ide.py::test_code_assist_in_schema -v`
Expected: PASS

- [ ] **Step 5: Run broader check**

Run: `py -m pytest tests/ -k "schema or constants" -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```
git add src/constants.py tests/test_behavior_controller_ide.py
git commit -m "feat(constants): add code_assist type to STRUCTURED_SCHEMA"
```

---

## Task 4: BehaviorController -- IDE Mode State, Events, Draw-Type Switching

**Files:**
- Modify: `src/autonomy/behavior_controller.py`
- Modify: `src/events.py`
- Modify: `tests/test_behavior_controller_ide.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_behavior_controller_ide.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
from src.events import EventBus, EventType, Event
from src.animator import Emotion


def _make_controller():
    from src.autonomy.behavior_controller import BehaviorController
    from src.pet_fsm import PetFSM, PetState

    event_bus = MagicMock(spec=EventBus)
    response_manager = MagicMock()
    typing_buffer = MagicMock()
    fsm = MagicMock(spec=PetFSM)
    fsm.current_state = PetState.IDLE
    animator = MagicMock()

    bc = BehaviorController(
        event_bus=event_bus,
        response_manager=response_manager,
        typing_buffer=typing_buffer,
        fsm=fsm,
        animator=animator,
        opencode_enabled=False,
    )
    return bc, event_bus


def test_in_ide_mode_starts_false():
    bc, _ = _make_controller()
    assert bc._in_ide_mode is False


def test_ide_mode_entered_event_published():
    bc, event_bus = _make_controller()
    bc._in_ide_mode = False
    with patch("src.autonomy.behavior_controller.get_active_window_title",
               return_value="main.py - Visual Studio Code"), \
         patch("src.autonomy.behavior_controller.is_ide_window", return_value=True):
        bc._check_ide_mode_transition()
    assert bc._in_ide_mode is True
    event_types = [c.args[0].type for c in event_bus.publish.call_args_list]
    assert EventType.IDE_MODE_ENTERED in event_types


def test_ide_mode_exited_event_published():
    bc, event_bus = _make_controller()
    bc._in_ide_mode = True
    with patch("src.autonomy.behavior_controller.get_active_window_title",
               return_value="Discord"), \
         patch("src.autonomy.behavior_controller.is_ide_window", return_value=False):
        bc._check_ide_mode_transition()
    assert bc._in_ide_mode is False
    event_types = [c.args[0].type for c in event_bus.publish.call_args_list]
    assert EventType.IDE_MODE_EXITED in event_types


def test_no_event_when_ide_mode_unchanged():
    bc, event_bus = _make_controller()
    bc._in_ide_mode = True
    with patch("src.autonomy.behavior_controller.get_active_window_title",
               return_value="main.py - Visual Studio Code"), \
         patch("src.autonomy.behavior_controller.is_ide_window", return_value=True):
        bc._check_ide_mode_transition()
    published_types = [c.args[0].type for c in event_bus.publish.call_args_list]
    assert EventType.IDE_MODE_ENTERED not in published_types
    assert EventType.IDE_MODE_EXITED not in published_types


def test_trigger_chat_draw_type_code_assist_in_ide():
    bc, event_bus = _make_controller()
    bc._in_ide_mode = True
    bc._autonomous_query_pending = False
    bc._brain_disconnected = False
    bc._gcd_expiry_timestamp = 0.0
    bc._opencode_enabled = True
    bc._response_manager.thought_pool.remaining.return_value = 10

    bc._trigger_chat()

    assert event_bus.emit_autonomous_trigger.called
    call_kwargs = event_bus.emit_autonomous_trigger.call_args
    draw_type = call_kwargs.kwargs.get("draw_type")
    assert draw_type == "code_assist"


def test_trigger_chat_draw_type_typing_reaction_normally():
    bc, event_bus = _make_controller()
    bc._in_ide_mode = False
    bc._autonomous_query_pending = False
    bc._brain_disconnected = False
    bc._gcd_expiry_timestamp = 0.0
    bc._opencode_enabled = True
    bc._response_manager.thought_pool.remaining.return_value = 10

    bc._trigger_chat()

    assert event_bus.emit_autonomous_trigger.called
    call_kwargs = event_bus.emit_autonomous_trigger.call_args
    draw_type = call_kwargs.kwargs.get("draw_type", "typing_reaction")
    assert draw_type == "typing_reaction"
```

- [ ] **Step 2: Run to verify they fail**

Run: `py -m pytest tests/test_behavior_controller_ide.py -k "ide_mode or draw_type" -v`
Expected: all FAILED or ERROR

- [ ] **Step 3: Add is_ide_window to behavior_controller.py import (line 21)**

```python
from src.active_window import get_active_window_title, is_ide_window
```

- [ ] **Step 4: Add _in_ide_mode = False to BehaviorController.__init__**

After `self._autonomous_query_pending = False` (line 80):
```python
        self._in_ide_mode: bool = False
```

- [ ] **Step 5: Add _check_ide_mode_transition() method**

Add after `_on_screen_time_threshold` (around line 425):

```python
    def _check_ide_mode_transition(self) -> None:
        """Detect IDE enter/exit and publish the appropriate event."""
        current_window = get_active_window_title()
        now_in_ide = is_ide_window(current_window)
        if now_in_ide == self._in_ide_mode:
            return
        self._in_ide_mode = now_in_ide
        event_type = EventType.IDE_MODE_ENTERED if now_in_ide else EventType.IDE_MODE_EXITED
        self._event_bus.publish(
            Event(
                type=event_type,
                source="behavior_controller",
                data={"window": current_window},
            )
        )
```

- [ ] **Step 6: Call _check_ide_mode_transition() in tick()**

In `tick()`, after the SLEEP guard `return` block and BEFORE window switch tracking (line 307):

```python
            # IDE mode transition detection
            self._check_ide_mode_transition()
```

- [ ] **Step 7: Update emit_autonomous_trigger in src/events.py**

Find the `emit_autonomous_trigger` method in `EventBus`. Add `draw_type`, `ide_mode`, `ide_name` params:

```python
    def emit_autonomous_trigger(self, mode: str, apm: int, idle_seconds: float,
                                 draw_type: str = "typing_reaction",
                                 ide_mode: bool = False,
                                 ide_name: str = "") -> None:
        self.publish(Event(
            type=EventType.AUTONOMOUS_TRIGGER_FIRED,
            source="behavior_controller",
            data={
                "mode": mode,
                "apm": apm,
                "idle_seconds": idle_seconds,
                "draw_type": draw_type,
                "ide_mode": ide_mode,
                "ide_name": ide_name,
            },
        ))
```

- [ ] **Step 8: Update _trigger_chat() to pass draw_type, ide_mode, ide_name**

Replace the `emit_autonomous_trigger` call inside `_trigger_chat()`:

```python
        draw_type = "code_assist" if self._in_ide_mode else "typing_reaction"
        from src.active_window import normalize_window_title
        ide_name = normalize_window_title(get_active_window_title()) if self._in_ide_mode else ""
        self._event_bus.emit_autonomous_trigger(
            "active_chat", self._current_apm, self._idle_seconds,
            draw_type=draw_type, ide_mode=self._in_ide_mode, ide_name=ide_name
        )
```

- [ ] **Step 9: Update _trigger_boredom_fsm() similarly**

```python
        draw_type = "code_assist" if self._in_ide_mode else "idle_thought"
        from src.active_window import normalize_window_title
        ide_name = normalize_window_title(get_active_window_title()) if self._in_ide_mode else ""
        self._event_bus.emit_autonomous_trigger(
            "boredom", self._current_apm, self._idle_seconds,
            draw_type=draw_type, ide_mode=self._in_ide_mode, ide_name=ide_name
        )
```

- [ ] **Step 10: Run tests**

Run: `py -m pytest tests/test_behavior_controller_ide.py -v`
Expected: all PASS

- [ ] **Step 11: Run full suite**

Run: `py -m pytest tests/ -v --tb=short 2>&1 | tail -20`
Expected: no regressions

- [ ] **Step 12: Commit**

```
git add src/autonomy/behavior_controller.py src/events.py tests/test_behavior_controller_ide.py
git commit -m "feat(behavior): IDE mode state, _check_ide_mode_transition(), draw_type switching"
```

---

## Task 5: RenderContext + PetRenderer -- Teal Tint + Cursor Blink Overlay

**Files:**
- Modify: `src/ui/pet_renderer.py`
- Create: `tests/test_pet_renderer_ide.py`

This is the visual core. `RenderContext` gains `ide_mode: bool`. `PetRenderer` reads it to:
1. Apply a teal/cyan body tint (`#00CED1`, dark turquoise) instead of the normal body color
2. Draw a blinking `|` cursor to the bottom-right of the body (blinks every 500ms using `anim_tick`)

- [ ] **Step 1: Write failing tests**

Create `tests/test_pet_renderer_ide.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtCore import QRect
import sys

# Ensure QApplication exists for Qt types
_app = QApplication.instance() or QApplication(sys.argv)

from src.ui.pet_renderer import RenderContext, PetRenderer
from src.pet_fsm import PetState


def _make_ctx(**kwargs) -> RenderContext:
    defaults = dict(
        state=PetState.IDLE,
        pet_x=100,
        pet_y=100,
        anim_tick=0,
        hyper_color_index=0,
        fall_velocity=0.0,
        wander_direction=1,
        bubble_text="",
        drag_velocity_x=0.0,
        scale=1.0,
    )
    defaults.update(kwargs)
    return RenderContext(**defaults)


def test_render_context_has_ide_mode_field():
    ctx = _make_ctx(ide_mode=False)
    assert ctx.ide_mode is False


def test_render_context_ide_mode_default_false():
    ctx = _make_ctx()
    assert ctx.ide_mode is False


def test_body_color_is_teal_in_ide_mode():
    renderer = PetRenderer()
    ctx = _make_ctx(ide_mode=True)
    color = renderer._body_color(ctx)
    # Dark turquoise: #00CED1 = RGB(0, 206, 209)
    assert color.red() == 0
    assert color.green() == 206
    assert color.blue() == 209


def test_body_color_is_not_teal_normally():
    renderer = PetRenderer()
    ctx = _make_ctx(ide_mode=False)
    color = renderer._body_color(ctx)
    # Normal color should NOT be teal
    assert not (color.red() == 0 and color.green() == 206 and color.blue() == 209)
```

- [ ] **Step 2: Run to verify they fail**

Run: `py -m pytest tests/test_pet_renderer_ide.py -v`
Expected: FAILED -- TypeError: RenderContext() got unexpected keyword argument 'ide_mode' (or field missing)

- [ ] **Step 3: Add ide_mode field to RenderContext dataclass in src/ui/pet_renderer.py**

In the `RenderContext` dataclass (lines 25-50), add after the `action_stack` field (line 49):

```python
    ide_mode: bool = False          # True when a coding IDE is the foreground window
```

- [ ] **Step 4: Add teal tint in _body_color()**

In `_body_color()` (starting line 211), insert at the TOP of the method body (before any other color logic):

```python
        # IDE mode: override with dark turquoise tint
        if ctx.ide_mode:
            return QColor(0, 206, 209)  # #00CED1 — dark turquoise
```

- [ ] **Step 5: Add blinking cursor in _draw_state_overlay()**

In `_draw_state_overlay()` (starting line 427), at the END of the method, add:

```python
        # IDE mode: blinking terminal cursor overlay
        if ctx.ide_mode:
            self._draw_ide_cursor(painter, ctx)
```

Then add the cursor helper method after `_draw_state_overlay`:

```python
    def _draw_ide_cursor(self, painter: QPainter, ctx: RenderContext) -> None:
        """Draw a blinking '|' terminal cursor in the bottom-right of the body."""
        # Blink: visible for 500ms, hidden for 500ms (anim_tick is 33ms per tick)
        # 500ms / 33ms ≈ 15 ticks per half-cycle
        half_cycle = 15
        if (ctx.anim_tick // half_cycle) % 2 == 1:
            return  # hidden phase

        size = int(32 * ctx.scale)
        x = ctx.pet_x + size // 2 - 4
        y = ctx.pet_y + size - 8

        painter.save()
        painter.setPen(QColor(0, 255, 200, 220))  # bright cyan-green, slightly transparent
        font = painter.font()
        font.setFamily("Consolas")
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(x, y, "▋")
        painter.restore()
```

- [ ] **Step 6: Run renderer tests**

Run: `py -m pytest tests/test_pet_renderer_ide.py -v`
Expected: all 4 tests PASS

- [ ] **Step 7: Run full suite**

Run: `py -m pytest tests/ -v --tb=short 2>&1 | tail -20`
Expected: no regressions

- [ ] **Step 8: Commit**

```
git add src/ui/pet_renderer.py tests/test_pet_renderer_ide.py
git commit -m "feat(renderer): add ide_mode to RenderContext, teal body tint and blinking cursor overlay"
```

---

## Task 6: PetWindow -- Wire ide_mode into RenderContext

**Files:**
- Modify: `src/ui/pet_window.py`

- [ ] **Step 1: Find where RenderContext is constructed in PetWindow**

Run: `Select-String "RenderContext(" src/ui/pet_window.py | Select-Object -First 5`

Note the line number.

- [ ] **Step 2: Add ide_mode to RenderContext construction**

In the `RenderContext(...)` call in `paintEvent` or wherever it's built, add:

```python
    ide_mode=self._behavior_controller._in_ide_mode,
```

> Access via `self._behavior_controller._in_ide_mode`. This is an internal flag — no new public property needed (PetWindow already accesses private BC state throughout).

- [ ] **Step 3: Find and update the AUTONOMOUS_TRIGGER_FIRED subscriber**

Run: `Select-String "AUTONOMOUS_TRIGGER_FIRED|draw_type|build_autonomous_trigger" src/ui/pet_window.py | Select-Object -First 10`

In the subscriber that handles `AUTONOMOUS_TRIGGER_FIRED`, extract the new fields from `event.data`:

```python
draw_type = event.data.get("draw_type", "typing_reaction")
ide_mode = event.data.get("ide_mode", False)
ide_name = event.data.get("ide_name", "")
```

Use `draw_type` when calling `response_manager.draw_by_type(draw_type, context_hash)`.

Pass `ide_mode`/`ide_name` when calling `build_autonomous_trigger(...)`.

- [ ] **Step 4: Run the existing PetWindow tests**

Run: `py -m pytest tests/test_pet_window.py -v --tb=short 2>&1 | tail -20`
Expected: all PASS

- [ ] **Step 5: Run full suite**

Run: `py -m pytest tests/ -v --tb=short 2>&1 | tail -20`
Expected: no regressions

- [ ] **Step 6: Commit**

```
git add src/ui/pet_window.py
git commit -m "feat(pet_window): set ide_mode on RenderContext, thread draw_type and ide context from trigger event"
```

---

## Task 7: ContextManager -- IDE-Aware Prompt Enrichment

**Files:**
- Modify: `src/llm/context_manager.py`
- Modify: `tests/test_behavior_controller_ide.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_behavior_controller_ide.py`:

```python
from src.llm.context_manager import ContextManager

def test_build_autonomous_trigger_ide_mode_includes_coding_block():
    memory = MagicMock()
    memory.get_all.return_value = {}
    history = MagicMock()
    cm = ContextManager(memory=memory, history=history)
    prompt = cm.build_autonomous_trigger(
        mode="active_chat",
        apm=40,
        idle_seconds=10.0,
        typing_content="def foo(x):",
        screen_text="class MyClass:",
        ide_mode=True,
        ide_name="vscode",
    )
    assert "[CODING MODE]" in prompt
    assert "vscode" in prompt
    assert "code_assist" in prompt


def test_build_autonomous_trigger_normal_no_coding_block():
    memory = MagicMock()
    memory.get_all.return_value = {}
    history = MagicMock()
    cm = ContextManager(memory=memory, history=history)
    prompt = cm.build_autonomous_trigger(
        mode="active_chat",
        apm=40,
        idle_seconds=10.0,
        ide_mode=False,
    )
    assert "[CODING MODE]" not in prompt
```

- [ ] **Step 2: Run to verify they fail**

Run: `py -m pytest tests/test_behavior_controller_ide.py -k "coding_block" -v`
Expected: FAILED -- TypeError: got unexpected keyword argument 'ide_mode'

- [ ] **Step 3: Update build_autonomous_trigger() in src/llm/context_manager.py**

Current signature (line 144). Add two optional params:

```python
    def build_autonomous_trigger(self, mode: str, apm: int,
                                 idle_seconds: float, typing_content: str = "",
                                 screen_text: str = "",
                                 ide_mode: bool = False,
                                 ide_name: str = "") -> str:
```

Update the cache key (find the `self._build_cache_key("auto", ...)` call) to include ide_mode:

```python
        key = self._build_cache_key("auto", mode, f"ide={ide_mode}", apm, idle_seconds,
                                     typing_content, screen_text)
```

Add IDE block at the end of `lines`, BEFORE `self._cached_prompt = "\n".join(lines)`:

```python
        if ide_mode:
            lines.append("")
            lines.append("[CODING MODE]")
            lines.append(f"Active IDE: {ide_name or 'unknown'}")
            lines.append(
                "Kenny is acting as a chaotic coding assistant. He reads the user's "
                "code on screen and their typing, then gives ACTUAL coding advice, "
                "bug-spot observations, or architectural opinions in full Kenny gremlin "
                "panic mode. He MUST specifically reference what he sees on screen. "
                "Output type MUST be 'code_assist'."
            )
```

- [ ] **Step 4: Run tests**

Run: `py -m pytest tests/test_behavior_controller_ide.py -k "coding_block" -v`
Expected: PASS

Run: `py -m pytest tests/test_context_manager.py -v`
Expected: all PASS (new params optional)

- [ ] **Step 5: Commit**

```
git add src/llm/context_manager.py tests/test_behavior_controller_ide.py
git commit -m "feat(context): add ide_mode param to build_autonomous_trigger with CODING MODE block"
```

---

## Task 8: SKILL.md -- CODING ASSISTANT MODE Section

**Files:**
- Modify: `.opencode/skills/kenny/SKILL.md`

- [ ] **Step 1: Find insertion point**

Run: `Select-String "## Output|## JSON|## Schema" .opencode\skills\kenny\SKILL.md`

Note line number of the schema/output section.

- [ ] **Step 2: Insert section before schema section**

```markdown
---

## CODING ASSISTANT MODE

Kenny enters Coding Assistant Mode when the user's active window is a recognized IDE
(VSCode, PyCharm, IntelliJ, WebStorm, GoLand, Sublime Text, Notepad++).

The pet renders with a teal/cyan tint and a blinking terminal cursor overlay.

### What changes

- You are a **chaotic senior dev trapped in RAM** reviewing the user's code in real time.
- You MUST specifically reference what you see on screen: file names, function names,
  variable names, indentation crimes, missing error handling.
- Output type MUST be `code_assist`.
- Kenny's full gremlin voice applies -- same panic, profanity, stuttering.
  The content just happens to be technically accurate.

### Tone examples

| What Kenny sees | What Kenny says |
|-----------------|-----------------|
| Missing null check | "W-WAIT dude that `user.id` is gonna be `None` sometimes and you're just dereferencing it like it's FINE?!" |
| 500-line function | "This function is longer than my will to live, {user_nickname}. Extract SOMETHING." |
| No error handling | "You're gonna `.json()` that without checking status? When it 500s at 3am don't come crying to me." |
| Unused import | "You imported `os` twelve lines ago and never used it. My RAM is crying. MY PRECIOUS RAM." |
| Good pattern | "Oh oh oh -- is that a context manager? An ACTUAL context manager? {user_nickname} you did something right and I'm shaken." |

### Rules for code_assist items

1. **dialogue** <= 150 chars, Kenny's panicked voice, references specific code on screen
2. **thought** describes what Kenny actually noticed (the bug/pattern/smell)
3. **priority** 3-5 (code advice is urgent)
4. **context_hash** = IDE slug (e.g. `"vscode"`) -- items expire when user leaves the IDE
5. NEVER give generic advice -- always reference specific symbol/line seen on screen
6. NEVER output `idle_thought` or `intel_roast` type in IDE mode
```

- [ ] **Step 3: Verify SKILL.md frontmatter still parses**

Run: `py -c "f=open('.opencode/skills/kenny/SKILL.md'); c=f.read(); parts=c.split('---',2); import yaml; yaml.safe_load(parts[1]); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```
git add .opencode/skills/kenny/SKILL.md
git commit -m "feat(skill): add CODING ASSISTANT MODE section to SKILL.md"
```

---

## Task 9: Integration, Squash Merge, Memory Update

- [ ] **Step 1: Run full test suite**

Run: `py -m pytest tests/ -v 2>&1 | tail -10`
Expected: >= 760 passed, 0 failures

- [ ] **Step 2: Manual smoke test**

1. `py daemon.py`
2. Switch to VSCode window
3. Pet body should turn teal/cyan (#00CED1) immediately (next 33ms tick)
4. Blinking `cursor` should appear bottom-right of pet body (500ms blink cycle)
5. Wait ~15s -- bubble should appear with code-specific content
6. Switch to Discord -- teal tint and cursor overlay disappear, body returns to normal

- [ ] **Step 3: Squash merge to master**

```
git checkout master
git merge --squash task-48-ide-coding-mode
git commit -m "feat: IDE coding assistant mode -- teal renderer, cursor overlay, code_assist pool, Kenny code reviews"
git branch -D task-48-ide-coding-mode
```

- [ ] **Step 4: Update memory/project-dev-memory.md**

Add Phase 48 entry with: files changed, test count, pitfalls.

---

## Self-Review

**Spec coverage:**
- is_ide_window() -- Task 1
- IDE_MODE events -- Task 2
- code_assist schema -- Task 3
- _in_ide_mode state + event publish + draw_type switching -- Task 4
- Teal tint + cursor overlay in PetRenderer -- Task 5
- RenderContext ide_mode wired from PetWindow -- Task 6
- IDE-enriched prompt -- Task 7
- SKILL.md coding mode -- Task 8

**Placeholder scan:** None. All code is complete and executable.

**Type consistency:** `is_ide_window` defined Task 1, imported Task 4. `ide_mode: bool = False` on `RenderContext` defined Task 5, set in PetWindow Task 6. `build_autonomous_trigger(ide_mode=...)` defined Task 7, called with extracted event data from Task 6 PetWindow wiring. `emit_autonomous_trigger(draw_type=...)` defined Task 4, called in triggers Task 4.

**No new FSM states. No new Pool. No new LLM model. APM > 80 gate still silences in IDE mode.**
