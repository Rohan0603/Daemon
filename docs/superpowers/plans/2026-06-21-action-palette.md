# Action Palette Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 24 LLM-triggered expression actions (float, jump, grow, shrink, glitch, rainbow, etc.) that run parallel to the FSM via a new `ActionLayer`, and migrate the 4 existing FSM-driven actions (shake, bounce, spin, look_away) into the same layer.

**Architecture:** New `src/action_layer.py` owns a max-5 stack of `ActiveAction` items. Each action has a name, start time, and duration. `PetRenderer` reads the stack each frame and composites transform/color/opacity contributions on top of the FSM base transform. `MCP change_visual_state` gains a `layer` param to route FSM vs expression actions. The 4 existing FSM states (SHAKING, BOUNCING, SPINNING, LOOK_AWAY) are deleted and their renderer logic migrated to action handlers.

**Tech Stack:** Python 3.14, PyQt6, `src/pet_fsm.py`, `src/pet_renderer.py`, `src/mcp_server.py`, `src/fsm_bridge.py`, `src/pet_window.py`, `src/constants.py`

**Spec:** `docs/superpowers/specs/2026-06-21-action-palette-design.md`

---

## File Map

| File | Action |
|------|--------|
| `src/action_layer.py` | CREATE — ActionLayer, ActiveAction, ActionTransform, get_action_transform() |
| `src/constants.py` | MODIFY — add ACTION_* duration constants, ACTION_STACK_MAX |
| `src/pet_fsm.py` | MODIFY — remove 4 states + triggered_action field |
| `src/pet_renderer.py` | MODIFY — add action_stack compositing, remove 4 migrated state branches |
| `src/mcp_server.py` | MODIFY — add layer param, expression routing |
| `src/fsm_bridge.py` | MODIFY — add action_triggered signal |
| `src/pet_window.py` | MODIFY — wire ActionLayer, _apply_action_positions, _on_mcp_expression_action |
| `.opencode/skills/kenny/SKILL.md` | MODIFY — add Expression Action Palette + Good Combos sections |
| `tests/test_action_layer.py` | CREATE |
| `tests/test_action_transforms.py` | CREATE |
| `tests/test_mcp_action_routing.py` | CREATE |
| `tests/test_fsm_migration.py` | CREATE |

---

## Task 1: Constants

**Files:**
- Modify: `src/constants.py`

- [ ] **Step 1: Add constants**

Open `src/constants.py`. Append at the end:

```python
# ── Action Layer ─────────────────────────────────────────────────────────────
ACTION_STACK_MAX              = 5
ACTION_FLOAT_DURATION_MS      = 2000
ACTION_JUMP_DURATION_MS       = 800
ACTION_GROW_DURATION_MS       = 1200
ACTION_SHRINK_DURATION_MS     = 1200
ACTION_PULSE_DURATION_MS      = 600
ACTION_GLITCH_DURATION_MS     = 1500
ACTION_RAINBOW_DURATION_MS    = 2000
ACTION_FLIP_DURATION_MS       = 400
ACTION_TELEPORT_DURATION_MS   = 1100
ACTION_WAVE_DURATION_MS       = 1500
ACTION_WOBBLE_DURATION_MS     = 1000
ACTION_DASH_DURATION_MS       = 500
ACTION_MELT_DURATION_MS       = 1500
ACTION_INFLATE_DURATION_MS    = 1500
ACTION_NOD_DURATION_MS        = 800
ACTION_HEADSHAKE_DURATION_MS  = 800
ACTION_TREMBLE_DURATION_MS    = 1000
ACTION_STRUT_DURATION_MS      = 2000
ACTION_FLAIL_DURATION_MS      = 1200
ACTION_VANISH_DURATION_MS     = 1300
# Migrated from FSM
ACTION_SHAKE_DURATION_MS      = 500
ACTION_BOUNCE_DURATION_MS     = 600
ACTION_SPIN_DURATION_MS       = 1500
ACTION_LOOK_AWAY_DURATION_MS  = 4000
```

- [ ] **Step 2: Verify import works**

```bash
py -c "from src.constants import ACTION_STACK_MAX, ACTION_FLOAT_DURATION_MS; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add src/constants.py
git commit -m "feat(action-palette): add action duration constants"
```

---

## Task 2: ActionLayer module

**Files:**
- Create: `src/action_layer.py`
- Create: `tests/test_action_layer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_action_layer.py`:

```python
import time
import pytest
from src.action_layer import ActionLayer, ActiveAction


def test_trigger_adds_to_stack():
    layer = ActionLayer()
    layer.trigger("float", 2000)
    assert len(layer.get_active()) == 1
    assert layer.get_active()[0].name == "float"


def test_tick_removes_expired_action():
    layer = ActionLayer()
    layer.trigger("shake", 500)
    layer.tick(600)
    assert len(layer.get_active()) == 0


def test_tick_keeps_unexpired_action():
    layer = ActionLayer()
    layer.trigger("grow", 1200)
    layer.tick(400)
    assert len(layer.get_active()) == 1


def test_multiple_actions_stack():
    layer = ActionLayer()
    layer.trigger("float", 2000)
    layer.trigger("rainbow", 2000)
    assert len(layer.get_active()) == 2


def test_stack_cap_evicts_oldest():
    from src.constants import ACTION_STACK_MAX
    layer = ActionLayer()
    names = [f"action_{i}" for i in range(ACTION_STACK_MAX + 1)]
    for i, n in enumerate(names):
        layer.trigger(n, 9999)
    active_names = [a.name for a in layer.get_active()]
    assert len(active_names) == ACTION_STACK_MAX
    assert names[0] not in active_names   # oldest evicted


def test_clear_empties_stack():
    layer = ActionLayer()
    layer.trigger("float", 2000)
    layer.trigger("rainbow", 2000)
    layer.clear()
    assert len(layer.get_active()) == 0


def test_get_active_returns_snapshot():
    layer = ActionLayer()
    layer.trigger("nod", 800)
    snapshot = layer.get_active()
    layer.clear()
    assert len(snapshot) == 1  # snapshot is independent


def test_params_stored_on_action():
    layer = ActionLayer()
    layer.trigger("teleport", 1100, params={"target_x": 100, "target_y": 200})
    assert layer.get_active()[0].params["target_x"] == 100


def test_elapsed_ms_advances_with_tick():
    layer = ActionLayer()
    layer.trigger("grow", 1200)
    layer.tick(300)
    assert layer.get_active()[0].elapsed_ms == pytest.approx(300, abs=1)
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
py -m pytest tests/test_action_layer.py -v
```

Expected: `ImportError` or `ModuleNotFoundError`

- [ ] **Step 3: Implement ActionLayer**

Create `src/action_layer.py`:

```python
from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from typing import Optional
import structlog

from src.constants import ACTION_STACK_MAX

logger = structlog.get_logger()

# Default duration map — used when MCP omits duration_ms
_DEFAULT_DURATIONS: dict[str, int] = {}  # populated after constants import

def _load_defaults() -> dict[str, int]:
    from src.constants import (
        ACTION_FLOAT_DURATION_MS, ACTION_JUMP_DURATION_MS,
        ACTION_GROW_DURATION_MS, ACTION_SHRINK_DURATION_MS,
        ACTION_PULSE_DURATION_MS, ACTION_GLITCH_DURATION_MS,
        ACTION_RAINBOW_DURATION_MS, ACTION_FLIP_DURATION_MS,
        ACTION_TELEPORT_DURATION_MS, ACTION_WAVE_DURATION_MS,
        ACTION_WOBBLE_DURATION_MS, ACTION_DASH_DURATION_MS,
        ACTION_MELT_DURATION_MS, ACTION_INFLATE_DURATION_MS,
        ACTION_NOD_DURATION_MS, ACTION_HEADSHAKE_DURATION_MS,
        ACTION_TREMBLE_DURATION_MS, ACTION_STRUT_DURATION_MS,
        ACTION_FLAIL_DURATION_MS, ACTION_VANISH_DURATION_MS,
        ACTION_SHAKE_DURATION_MS, ACTION_BOUNCE_DURATION_MS,
        ACTION_SPIN_DURATION_MS, ACTION_LOOK_AWAY_DURATION_MS,
    )
    return {
        "float": ACTION_FLOAT_DURATION_MS, "jump": ACTION_JUMP_DURATION_MS,
        "grow": ACTION_GROW_DURATION_MS, "shrink": ACTION_SHRINK_DURATION_MS,
        "pulse": ACTION_PULSE_DURATION_MS, "glitch": ACTION_GLITCH_DURATION_MS,
        "rainbow": ACTION_RAINBOW_DURATION_MS, "flip": ACTION_FLIP_DURATION_MS,
        "teleport": ACTION_TELEPORT_DURATION_MS, "wave": ACTION_WAVE_DURATION_MS,
        "wobble": ACTION_WOBBLE_DURATION_MS, "dash": ACTION_DASH_DURATION_MS,
        "melt": ACTION_MELT_DURATION_MS, "inflate": ACTION_INFLATE_DURATION_MS,
        "nod": ACTION_NOD_DURATION_MS, "headshake": ACTION_HEADSHAKE_DURATION_MS,
        "tremble": ACTION_TREMBLE_DURATION_MS, "strut": ACTION_STRUT_DURATION_MS,
        "flail": ACTION_FLAIL_DURATION_MS, "vanish": ACTION_VANISH_DURATION_MS,
        "shake": ACTION_SHAKE_DURATION_MS, "bounce": ACTION_BOUNCE_DURATION_MS,
        "spin": ACTION_SPIN_DURATION_MS, "look_away": ACTION_LOOK_AWAY_DURATION_MS,
    }


EXPRESSION_ACTIONS: frozenset[str] = frozenset([
    "float", "jump", "grow", "shrink", "pulse", "glitch", "rainbow",
    "flip", "teleport", "wave", "wobble", "dash", "melt", "inflate",
    "nod", "headshake", "tremble", "strut", "flail", "vanish",
    "shake", "bounce", "spin", "look_away",
])


@dataclass
class ActionTransform:
    sx: float = 1.0
    sy: float = 1.0
    rot: float = 0.0
    ox: float = 0.0
    oy: float = 0.0
    opacity: float = 1.0
    hue_shift: Optional[float] = None


@dataclass
class ActiveAction:
    name: str
    duration_ms: int
    params: dict = field(default_factory=dict)
    elapsed_ms: float = 0.0
    _position_applied: bool = False   # one-shot for teleport reposition


class ActionLayer:
    """Parallel expression action stack. Thread-safe for main-thread use only."""

    def __init__(self) -> None:
        self._stack: list[ActiveAction] = []
        self._defaults = _load_defaults()

    def trigger(self, name: str, duration_ms: Optional[int] = None,
                params: Optional[dict] = None) -> None:
        dur = duration_ms or self._defaults.get(name, 1000)
        action = ActiveAction(name=name, duration_ms=dur, params=params or {})
        if len(self._stack) >= ACTION_STACK_MAX:
            self._stack.pop(0)   # evict oldest
        self._stack.append(action)
        logger.debug("ActionLayer triggered %s for %dms", name, dur)

    def tick(self, dt_ms: int) -> None:
        for action in self._stack:
            action.elapsed_ms += dt_ms
        self._stack = [a for a in self._stack if a.elapsed_ms < a.duration_ms]

    def get_active(self) -> list[ActiveAction]:
        return list(self._stack)  # snapshot

    def clear(self) -> None:
        self._stack.clear()

    @staticmethod
    def get_transform(action: ActiveAction) -> ActionTransform:
        return _get_action_transform(action.name, action.elapsed_ms, action.duration_ms)


def _p(elapsed: float, duration: int) -> float:
    """Normalized progress 0.0→1.0, clamped."""
    return min(1.0, elapsed / max(duration, 1))


def _get_action_transform(name: str, t: float, dur: int) -> ActionTransform:
    """Return the ActionTransform for action `name` at elapsed time `t` ms."""
    p = _p(t, dur)
    sin = math.sin
    exp = math.exp
    pi = math.pi
    abs_ = abs

    if name == "shake":
        return ActionTransform(ox=sin(t * pi * 15 / dur) * 5)

    if name == "bounce":
        return ActionTransform(oy=-abs_(sin(t * pi * 2 / dur)) * 12)

    if name == "spin":
        return ActionTransform(rot=p * 360.0)

    if name == "look_away":
        # Signal to renderer via hue_shift=None sentinel; renderer checks name
        return ActionTransform()  # renderer handles look_away by name

    if name == "grow":
        s = 1.0 + 0.3 * sin(p * pi)
        return ActionTransform(sx=s, sy=s)

    if name == "shrink":
        s = 1.0 - 0.3 * sin(p * pi)
        return ActionTransform(sx=s, sy=s)

    if name == "inflate":
        if t < dur * 0.73:  # puff phase
            s = 1.0 + 0.4 * sin((t / (dur * 0.73)) * pi / 2)
        else:  # snap back
            s = 1.4 - 0.4 * ((t - dur * 0.73) / (dur * 0.27))
        return ActionTransform(sx=s, sy=s)

    if name == "melt":
        if t < dur * 0.6:
            sx = 1.0 + 0.15 * sin((t / (dur * 0.6)) * pi / 2)
            sy = 1.0 - 0.4 * sin((t / (dur * 0.6)) * pi / 2)
        else:
            frac = (t - dur * 0.6) / (dur * 0.4)
            sx = 1.15 - 0.15 * frac
            sy = 0.6 + 0.4 * frac
        return ActionTransform(sx=sx, sy=sy)

    if name == "pulse":
        s = 1.0 + 0.15 * abs_(sin(t * pi * 2 / 300))
        return ActionTransform(sx=s, sy=s)

    if name == "wobble":
        rot = 20.0 * exp(-t / 300) * sin(t * pi * 5 / dur)
        return ActionTransform(rot=rot)

    if name == "wave":
        rot = sin(t * pi * 3 / dur) * 15.0
        return ActionTransform(rot=rot)

    if name == "flip":
        rot_sx = math.cos(t * pi / dur)
        return ActionTransform(sx=rot_sx)

    if name == "nod":
        # keyframes: 0→12°→0→-5°→0
        if t < dur * 0.35:
            rot = 12.0 * (t / (dur * 0.35))
        elif t < dur * 0.65:
            rot = 12.0 * (1.0 - (t - dur * 0.35) / (dur * 0.30))
        elif t < dur * 0.85:
            rot = -5.0 * ((t - dur * 0.65) / (dur * 0.20))
        else:
            rot = -5.0 * (1.0 - (t - dur * 0.85) / (dur * 0.15))
        return ActionTransform(rot=rot)

    if name == "headshake":
        if t < dur * 0.25:
            rot = -18.0 * (t / (dur * 0.25))
        elif t < dur * 0.55:
            rot = -18.0 + 36.0 * ((t - dur * 0.25) / (dur * 0.30))
        elif t < dur * 0.80:
            rot = 18.0 - 26.0 * ((t - dur * 0.55) / (dur * 0.25))
        else:
            rot = -8.0 * (1.0 - (t - dur * 0.80) / (dur * 0.20))
        return ActionTransform(rot=rot)

    if name == "tremble":
        # High-freq jitter at ~12Hz (every ~83ms)
        bucket = int(t // 83)
        rng = random.Random(bucket)
        rot = rng.uniform(-2.0, 2.0)
        ox = rng.uniform(-1.0, 1.0)
        oy = rng.uniform(-1.0, 1.0)
        return ActionTransform(rot=rot, ox=ox, oy=oy)

    if name == "flail":
        bucket = int(t // 100)
        rng = random.Random(bucket)
        rot = rng.uniform(-30.0, 30.0)
        return ActionTransform(rot=rot)

    if name == "rainbow":
        hue = p * 360.0
        return ActionTransform(hue_shift=hue)

    if name == "glitch":
        bucket = int(t // 30)
        rng = random.Random(bucket)
        ox = rng.uniform(-5.0, 5.0)
        oy = rng.uniform(-5.0, 5.0)
        hue = rng.uniform(-40.0, 40.0)
        op = rng.uniform(0.7, 1.0)
        return ActionTransform(ox=ox, oy=oy, hue_shift=hue, opacity=op)

    if name == "vanish":
        fade = 400.0
        hold = 500.0
        if t < fade:
            op = 1.0 - (t / fade)
        elif t < fade + hold:
            op = 0.0
        else:
            op = min(1.0, (t - fade - hold) / fade)
        return ActionTransform(opacity=op)

    # jump, float, dash, strut, teleport — position handled by PetWindow
    # Return identity; PetWindow._apply_action_positions reads these by name
    return ActionTransform()
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
py -m pytest tests/test_action_layer.py -v
```

Expected: all 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/action_layer.py tests/test_action_layer.py
git commit -m "feat(action-palette): add ActionLayer module with 24 action transforms"
```

---

## Task 3: FSM Migration (remove 4 states)

**Files:**
- Modify: `src/pet_fsm.py`
- Create: `tests/test_fsm_migration.py`

- [ ] **Step 1: Write migration tests**

Create `tests/test_fsm_migration.py`:

```python
from src.pet_fsm import PetState, FSMContext


def test_shaking_not_in_pet_state():
    assert not hasattr(PetState, "SHAKING")


def test_bouncing_not_in_pet_state():
    assert not hasattr(PetState, "BOUNCING")


def test_spinning_not_in_pet_state():
    assert not hasattr(PetState, "SPINNING")


def test_look_away_not_in_pet_state():
    assert not hasattr(PetState, "LOOK_AWAY")


def test_triggered_action_not_in_fsm_context():
    import dataclasses
    field_names = {f.name for f in dataclasses.fields(FSMContext)}
    assert "triggered_action" not in field_names


def test_fsm_context_can_be_constructed_without_triggered_action():
    # Ensure FSMContext no longer requires triggered_action
    ctx = FSMContext(
        cursor_pos=(0, 0), pet_rect=(0, 0, 60, 80),
        apm=0, is_dragged=False, is_falling=False,
        query_pending=False, build_event=None,
        idle_seconds=0.0, wander_due=False,
        hyper_sustained_seconds=0.0, hyper_cooldown_seconds=0.0,
        state_elapsed_ms=0, autonomous_query_pending=False,
    )
    assert ctx is not None
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
py -m pytest tests/test_fsm_migration.py -v
```

Expected: FAIL (states still exist)

- [ ] **Step 3: Remove 4 states from pet_fsm.py**

In `src/pet_fsm.py`:

**Remove from `PetState` enum:**
```python
# DELETE these 4 lines:
SHAKING            = auto()
BOUNCING           = auto()
SPINNING           = auto()
LOOK_AWAY          = auto()
```

**Remove from `FSMContext`:**
```python
# DELETE this line:
triggered_action: Optional[str] = None
```

**Remove from `PetFSM._evaluate()`** — delete all 4 priority blocks:
```python
# DELETE Priority 8 block:
# Priority 8: SHAKING
if ctx.triggered_action == "shake":
    return PetState.SHAKING
if cur == PetState.SHAKING:
    if ctx.state_elapsed_ms >= SHAKE_DURATION_MS:
        pass
    else:
        return PetState.SHAKING

# DELETE Priority 9 block:
# Priority 9: BOUNCING
if ctx.triggered_action == "bounce":
    return PetState.BOUNCING
if cur == PetState.BOUNCING:
    if ctx.state_elapsed_ms >= BOUNCE_DURATION_MS:
        pass
    else:
        return PetState.BOUNCING

# DELETE Priority 10 block:
# Priority 10: SPINNING
if ctx.triggered_action == "spin":
    return PetState.SPINNING
if cur == PetState.SPINNING:
    if ctx.state_elapsed_ms >= SPIN_DURATION_MS:
        pass
    else:
        return PetState.SPINNING

# DELETE Priority 12 block:
# Priority 12: LOOK_AWAY
if ctx.triggered_action == "look_away":
    return PetState.LOOK_AWAY
if cur == PetState.LOOK_AWAY:
    if ctx.state_elapsed_ms >= LOOK_AWAY_DURATION_MS:
        pass
    else:
        return PetState.LOOK_AWAY
```

**Remove from `src/pet_fsm.py` imports** the now-unused constants:
```python
# REMOVE from the constants import:
SHAKE_DURATION_MS, BOUNCE_DURATION_MS,
SPIN_DURATION_MS, LOOK_AWAY_DURATION_MS,
```

- [ ] **Step 4: Run migration + FSM tests**

```bash
py -m pytest tests/test_fsm_migration.py tests/test_fsm.py -v
```

Expected: migration tests PASS. FSM tests — any test asserting SHAKING/BOUNCING/SPINNING/LOOK_AWAY will fail. Delete those specific test cases from `tests/test_fsm.py` (search for `SHAKING`, `BOUNCING`, `SPINNING`, `LOOK_AWAY`, `triggered_action`).

After cleanup, run again:

```bash
py -m pytest tests/test_fsm_migration.py tests/test_fsm.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/pet_fsm.py tests/test_fsm_migration.py tests/test_fsm.py
git commit -m "refactor(action-palette): remove 4 triggered FSM states, migrate to ActionLayer"
```

---

## Task 4: FSMActionBridge — add action_triggered signal

**Files:**
- Modify: `src/fsm_bridge.py`

- [ ] **Step 1: Add signal to FSMActionBridge**

Open `src/fsm_bridge.py`. Add a new signal to the `FSMActionBridge` class:

```python
from PyQt6.QtCore import QObject, pyqtSignal


class FSMActionBridge(QObject):
    fsm_action_requested = pyqtSignal(str)          # existing
    toast_request = pyqtSignal(str, str)            # existing
    action_triggered = pyqtSignal(str, int, dict)   # NEW: name, duration_ms, params
```

- [ ] **Step 2: Verify existing tests still pass**

```bash
py -m pytest tests/test_fsm_bridge.py -v
```

Expected: all PASS

- [ ] **Step 3: Commit**

```bash
git add src/fsm_bridge.py
git commit -m "feat(action-palette): add action_triggered signal to FSMActionBridge"
```

---

## Task 5: MCP Server — add layer routing

**Files:**
- Modify: `src/mcp_server.py`
- Create: `tests/test_mcp_action_routing.py`

- [ ] **Step 1: Write routing tests**

Create `tests/test_mcp_action_routing.py`:

```python
import json
import pytest
from unittest.mock import MagicMock, patch


def _make_handler(fsm_bridge=None, action_layer=None):
    from src.mcp_server import MCPHandler
    handler = MCPHandler.__new__(MCPHandler)
    handler._fsm_bridge = fsm_bridge or MagicMock()
    handler._action_layer = action_layer or MagicMock()
    handler._config = {"consent": {}}
    return handler


def test_expression_layer_routes_to_action_layer():
    handler = _make_handler()
    params = {"action": "float", "layer": "expression"}
    handler._handle_change_visual_state(params)
    handler._action_layer.trigger.assert_called_once()
    handler._fsm_bridge.fsm_action_requested.emit.assert_not_called()


def test_fsm_layer_routes_to_fsm_bridge():
    handler = _make_handler()
    params = {"action": "celebrate", "layer": "fsm"}
    handler._handle_change_visual_state(params)
    handler._fsm_bridge.fsm_action_requested.emit.assert_called_once_with("celebrate")
    handler._action_layer.trigger.assert_not_called()


def test_expression_action_on_fsm_layer_returns_error():
    handler = _make_handler()
    params = {"action": "float", "layer": "fsm"}
    result = handler._handle_change_visual_state(params)
    assert result.get("error") is not None


def test_fsm_action_on_expression_layer_returns_error():
    handler = _make_handler()
    params = {"action": "celebrate", "layer": "expression"}
    result = handler._handle_change_visual_state(params)
    assert result.get("error") is not None


def test_duration_ms_passed_to_action_layer():
    handler = _make_handler()
    params = {"action": "rainbow", "layer": "expression", "duration_ms": 3000}
    handler._handle_change_visual_state(params)
    handler._action_layer.trigger.assert_called_once_with("rainbow", 3000, {})
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
py -m pytest tests/test_mcp_action_routing.py -v
```

- [ ] **Step 3: Update MCP server**

In `src/mcp_server.py`:

**Update `VALID_ACTIONS` and add sets:**
```python
FSM_ACTIONS = frozenset({
    "idle", "wander", "hyper", "celebrate", "devastated", "fall", "chase"
})
EXPRESSION_ACTIONS = frozenset({
    "float", "jump", "grow", "shrink", "pulse", "glitch", "rainbow",
    "flip", "teleport", "wave", "wobble", "dash", "melt", "inflate",
    "nod", "headshake", "tremble", "strut", "flail", "vanish",
    "shake", "bounce", "spin", "look_away",
})
VALID_ACTIONS = FSM_ACTIONS | EXPRESSION_ACTIONS
```

**Update `MCP_TOOLS` `change_visual_state` inputSchema** — add `layer` and `duration_ms` properties:
```python
{
    "name": "change_visual_state",
    "description": "Trigger Daemon's FSM state or a layered expression action.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": sorted(VALID_ACTIONS)},
            "layer": {
                "type": "string",
                "enum": ["fsm", "expression"],
                "description": "fsm = exclusive state. expression = stackable, auto-expires."
            },
            "duration_ms": {
                "type": "integer",
                "description": "Optional duration override for expression actions."
            }
        },
        "required": ["action", "layer"]
    }
}
```

**Add `_handle_change_visual_state` method** (extract from existing dispatch or create new):
```python
def _handle_change_visual_state(self, params: dict) -> dict:
    action = params.get("action", "")
    layer = params.get("layer", "fsm")
    duration_ms = params.get("duration_ms")

    if action not in VALID_ACTIONS:
        return {"error": {"code": -32602, "message": f"Unknown action: {action}"}}

    if layer == "expression":
        if action not in EXPRESSION_ACTIONS:
            return {"error": {"code": -32602,
                              "message": f"{action!r} is an FSM action; use layer='fsm'"}}
        self._action_layer.trigger(action, duration_ms, {})
        return {"result": "ok"}

    elif layer == "fsm":
        if action not in FSM_ACTIONS:
            return {"error": {"code": -32602,
                              "message": f"{action!r} is an expression action; use layer='expression'"}}
        self._fsm_bridge.fsm_action_requested.emit(action)
        return {"result": "ok"}

    return {"error": {"code": -32602, "message": f"Unknown layer: {layer}"}}
```

Wire `self._action_layer` attribute: `MCPHandler` receives `action_layer` param (pass from `MCPServer.start()` → `MCPHandler`).

- [ ] **Step 4: Run tests**

```bash
py -m pytest tests/test_mcp_action_routing.py tests/test_mcp_server.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp_server.py tests/test_mcp_action_routing.py
git commit -m "feat(action-palette): add layer routing to change_visual_state MCP tool"
```

---

## Task 6: Renderer — action stack compositing

**Files:**
- Modify: `src/pet_renderer.py`

- [ ] **Step 1: Add `action_stack` to RenderContext**

In `src/pet_renderer.py`, in the `RenderContext` dataclass, add:

```python
from dataclasses import dataclass, field
# ... existing imports ...

@dataclass
class RenderContext:
    # ... all existing fields unchanged ...
    action_stack: list = field(default_factory=list)  # list[ActiveAction]
```

- [ ] **Step 2: Update `_draw_pet` to composite action stack**

In `PetRenderer._draw_pet()`, after computing `ox, oy = self._state_offset(ctx)` and `scale_x, scale_y, rotation = self._state_transform(ctx)`, add the accumulation loop before `painter.translate`:

```python
from src.action_layer import ActionLayer

# Accumulate expression layer
expr_sx = 1.0; expr_sy = 1.0; expr_rot = 0.0
expr_ox = 0.0; expr_oy = 0.0; expr_opacity = 1.0
expr_hue = None

for action in ctx.action_stack:
    tr = ActionLayer.get_transform(action)
    expr_sx      *= tr.sx
    expr_sy      *= tr.sy
    expr_rot     += tr.rot
    expr_ox      += tr.ox
    expr_oy      += tr.oy
    expr_opacity *= tr.opacity
    if tr.hue_shift is not None:
        expr_hue = tr.hue_shift

# Apply opacity
if expr_opacity < 1.0:
    painter.setOpacity(expr_opacity)

painter.translate(cx + ox + expr_ox, cy + oy + expr_oy)
if (rotation + expr_rot) != 0:
    painter.rotate(rotation + expr_rot)
painter.scale(scale_x * expr_sx, scale_y * expr_sy)
```

- [ ] **Step 3: Apply hue_shift to body_color**

After `body_color = self._body_color(ctx)`, add:

```python
if expr_hue is not None:
    from PyQt6.QtGui import QColor
    h, s, v, a = body_color.getHsvF()
    new_h = ((h * 360.0 + expr_hue) % 360.0) / 360.0
    body_color = QColor.fromHsvF(new_h, s, v, a)
```

- [ ] **Step 4: Remove migrated state branches**

In `_state_offset()`, remove:
```python
# DELETE:
if ctx.state == PetState.SHAKING:
    return math.sin(t * math.pi * 15) * 5, 0.0
if ctx.state == PetState.BOUNCING:
    return 0.0, -abs(math.sin(t * math.pi * 2)) * 12
```

In `_state_transform()`, remove the SPINNING branch.

In `_draw_eyes()`, remove LOOK_AWAY pupil-avert logic. The `look_away` action now returns `ActionTransform()` identity — the renderer handles it by name check:

```python
# In _draw_eyes(), check ctx.action_stack for look_away:
look_away_active = any(a.name == "look_away" for a in ctx.action_stack)
if look_away_active:
    # avert pupils opposite cursor direction
    dx = ctx.cursor_x - (ctx.pet_x + PET_WIDTH / 2)
    dy = ctx.cursor_y - (ctx.pet_y + PET_HEIGHT / 2)
    dist = max(1.0, (dx**2 + dy**2)**0.5)
    # Push pupils in opposite direction capped at ±8px
    pupil_offset_x = -dx / dist * 8
    pupil_offset_y = -dy / dist * 8
```

- [ ] **Step 5: Run renderer tests**

```bash
py -m pytest tests/test_pet_renderer.py -v
```

Expected: all PASS (empty `action_stack` default = no change to existing behavior)

- [ ] **Step 6: Commit**

```bash
git add src/pet_renderer.py
git commit -m "feat(action-palette): composite action stack transforms in PetRenderer"
```

---

## Task 7: PetWindow wiring

**Files:**
- Modify: `src/pet_window.py`

- [ ] **Step 1: Instantiate ActionLayer in `__init__`**

In `PetWindow.__init__`, after existing worker instantiation:

```python
from src.action_layer import ActionLayer
self._action_layer = ActionLayer()
```

Pass `action_layer` to `MCPServer` (or `MCPHandler`) at construction so it can route expression actions.

- [ ] **Step 2: Connect `action_triggered` signal**

```python
self._fsm_bridge.action_triggered.connect(self._on_mcp_expression_action)
```

- [ ] **Step 3: Implement `_on_mcp_expression_action`**

```python
def _on_mcp_expression_action(self, name: str, duration_ms: int, params: dict) -> None:
    """Slot: MCP layer='expression' → ActionLayer."""
    self._action_layer.trigger(name, duration_ms or None, params)
```

- [ ] **Step 4: Call `ActionLayer.tick()` in `_tick()`**

In `_tick()` (the 33ms timer), add near the top:

```python
self._action_layer.tick(FSM_TICK_MS)
self._apply_action_positions()
```

- [ ] **Step 5: Implement `_apply_action_positions`**

```python
def _apply_action_positions(self) -> None:
    """Apply position-affecting actions (jump, float, dash, strut, teleport)."""
    import math, random
    from src.action_layer import ActionLayer
    for action in self._action_layer.get_active():
        t = action.elapsed_ms
        d = action.duration_ms
        p = min(1.0, t / max(d, 1))

        if action.name == "jump":
            dy = -math.sin(p * math.pi) * 40
            self._pet_y += dy  # renderer offset; no FALLING physics

        elif action.name == "float":
            dy = -math.sin(t * math.pi / 1000) * 8
            self._pet_y += dy

        elif action.name == "bounce":
            # Handled in renderer; no position change needed
            pass

        elif action.name == "dash":
            facing = getattr(self, "_perimeter_facing", "right")
            dx = math.sin(p * math.pi) * 60 * (1 if facing == "right" else -1)
            self._pet_x += dx

        elif action.name == "strut":
            # Walk at 60% PERIMETER speed
            self._tick_perimeter(speed_multiplier=0.6)

        elif action.name == "teleport":
            # At midpoint (opacity ≈ 0), reposition once
            if t >= 350 and not action._position_applied:
                action._position_applied = True
                screen = self.screen().availableGeometry()
                import random as _r
                rx = _r.randint(0, max(0, screen.width() - self._pet_width))
                ry = _r.randint(0, max(0, screen.height() - self._pet_height))
                self._pet_x = rx
                self._pet_y = ry
```

- [ ] **Step 6: Pass action_stack to RenderContext in `paintEvent`**

In `paintEvent`, where `RenderContext(...)` is constructed, add:

```python
action_stack=self._action_layer.get_active(),
```

- [ ] **Step 7: Call `action_layer.clear()` on SLEEP entry and shutdown**

In `_force_quit_app()` before existing cleanup:
```python
self._action_layer.clear()
```

In the SLEEP FSM transition handler:
```python
self._action_layer.clear()
```

- [ ] **Step 8: Run regression**

```bash
py -m pytest tests/ -v --timeout=30
```

Expected: 688+ pass, 1 skipped, no new failures.

- [ ] **Step 9: Commit**

```bash
git add src/pet_window.py
git commit -m "feat(action-palette): wire ActionLayer into PetWindow tick, paint, and shutdown"
```

---

## Task 8: SKILL.md update

**Files:**
- Modify: `.opencode/skills/kenny/SKILL.md`

- [ ] **Step 1: Add Expression Action Palette section**

In `.opencode/skills/kenny/SKILL.md`, find the existing `## MCP Tools` or `## Actions` section. After it, insert:

```markdown
## Expression Actions (`layer="expression"`)

Stack up to 2 per `change_visual_state` call. Auto-expire after duration. **Do NOT interrupt FSM state.**

### Emotion Expressions
| Action | Use when |
|--------|----------|
| `nod` | Agreement, affirmation |
| `headshake` | Disagreement, exasperation |
| `tremble` | Fear, nervous energy |
| `flail` | Panic, chaos, overwhelm |
| `wobble` | Uncertainty, confusion |

### Physical Reactions
| Action | Use when |
|--------|----------|
| `shake` | Startled, bad code seen |
| `bounce` | Excitement, can't contain it |
| `jump` | Surprise, sudden realization |
| `float` | Smug, above it all |
| `strut` | Confident, nailed it |
| `dash` | Urgency, quick movement |

### Body Language
| Action | Use when |
|--------|----------|
| `grow` | Puffing up, proud or threatening |
| `shrink` | Embarrassed, backing down |
| `inflate` | Building up to something |
| `melt` | Defeated, exasperated |

### Visual Flair (use sparingly — Kenny's chaos, not disco)
| Action | Use when |
|--------|----------|
| `spin` | Dizzy, spiral reaction |
| `flip` | Disbelief, "no way" |
| `pulse` | Heartbeat spike, alarmed |
| `rainbow` | Celebration or mockery |
| `glitch` | Malfunctioning, confused |
| `vanish` | Dramatic exit or ignoring user |
| `teleport` | Restless, can't stay still |
| `wave` | Wavering, unsure |
| `look_away` | Pointedly ignoring |

## Action Stacking — Good Combos
Max 2 actions per trigger call:
- `grow` + `rainbow` → triumph
- `tremble` + `float` → anxious hovering
- `nod` + `pulse` → emphatic agreement
- `shrink` + `vanish` → embarrassed exit
- `flail` + `glitch` → full system panic
- `headshake` + `melt` → pure exasperation

## Hard Rules
- NEVER use `layer="fsm"` for expression actions
- NEVER use `layer="expression"` for FSM states (idle/celebrate/etc.)
- Stack maximum **2 actions** per call — don't spam
- `teleport` and `strut` move the pet physically — use contextually
- `duration_ms` override only when timing matters (synced to dialogue)
```

- [ ] **Step 2: Commit**

```bash
git add .opencode/skills/kenny/SKILL.md
git commit -m "docs(action-palette): add expression action palette to SKILL.md"
```

---

## Task 9: Full regression + squash merge

- [ ] **Step 1: Run full suite**

```bash
py -m pytest tests/ -v --timeout=30
```

Expected: all pass, 0 failures.

- [ ] **Step 2: Squash-merge to master**

```bash
git checkout master
git merge --squash task-73-action-palette
git commit -m "feat: add 24-action expression palette with parallel ActionLayer (Phase 73)"
git branch -D task-73-action-palette
```
