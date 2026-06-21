# Action Palette — Design Spec

**Date:** 2026-06-21  
**Status:** Approved  
**Scope:** Parallel LLM-triggered expression action layer for Daemon desktop pet

---

## 1. Problem Statement

The current action system funnels all LLM-triggered pet animations through FSM states
(SHAKING, BOUNCING, SPINNING, LOOK_AWAY). This has two problems:

1. Actions are **exclusive** — they preempt THINKING, HYPER, etc., breaking user-facing
   interactions.
2. The FSM grows unbounded as new animations are added — every new action = a new state,
   a new priority block, a new duration constant, new renderer branches.

The goal is a **parallel expression layer**: actions run alongside the FSM state without
interrupting it, stack up to 5 simultaneously, and auto-expire after their duration.

---

## 2. Architecture

### 2.1 New module: `src/action_layer.py`

```
ActionLayer
  ├─ ActiveAction (dataclass)
  │    name: str
  │    start_ms: int          # monotonic ms at trigger time
  │    duration_ms: int       # total lifetime
  │    params: dict           # optional: target_x/y for teleport, etc.
  │    _position_applied: bool  # one-shot flag for teleport mid-point
  │
  ├─ _stack: list[ActiveAction]   # max 5 simultaneous, evict oldest at cap
  ├─ trigger(name, duration_ms, params={}) → None
  ├─ tick(dt_ms) → None          # advance elapsed, remove expired
  ├─ get_active() → list[ActiveAction]   # snapshot for renderer
  └─ clear() → None              # shutdown / SLEEP entry
```

### 2.2 Integration points

```
MCP change_visual_state {action, layer, duration_ms?}
  ├─ layer="fsm"         → FSMActionBridge (existing, unchanged)
  └─ layer="expression"  → FSMActionBridge.action_triggered signal (new)
                               → PetWindow._on_mcp_expression_action()
                                    → ActionLayer.trigger(name, duration_ms, params)

_tick() (33ms)
  → ActionLayer.tick(33)
  → PetWindow._apply_action_positions()   # position-affecting actions only

paintEvent
  → RenderContext.action_stack = action_layer.get_active()
  → PetRenderer composes action transforms onto FSM base transform
```

### 2.3 FSM migration

Remove 4 states from `PetState`:
- `SHAKING` → migrated to expression action `shake`
- `BOUNCING` → migrated to expression action `bounce`
- `SPINNING` → migrated to expression action `spin`
- `LOOK_AWAY` → migrated to expression action `look_away`

Remove from `FSMContext`:
- `triggered_action: Optional[str]` field (no longer needed)

Remove from `PetFSM._evaluate()`:
- Priority 8 (SHAKING), Priority 9 (BOUNCING), Priority 10 (SPINNING), Priority 12 (LOOK_AWAY) blocks

FSM states after migration: 11 → 7  
(IDLE, SLEEP, PERIMETER, CHASE, HYPER, THINKING, CELEBRATE, DEVASTATED, DRAGGED, FALLING, AUTONOMOUS_THINKING)

Remove from `PetRenderer`:
- `_state_offset()` SHAKING/BOUNCING branches
- `_state_transform()` SPINNING branch
- LOOK_AWAY eye-avert logic in `_draw_eyes()` (migrated to action transform)

---

## 3. Action Catalog (24 total)

### 3.1 Transform Actions — renderer-only

| Action | Default Duration | Renderer Behavior |
|--------|-----------------|-------------------|
| `shake` | 500ms | horizontal sine: `sin(t*π*15/500) * 5px` X offset |
| `bounce` | 600ms | vertical: `-abs(sin(t*π*2/600)) * 12px` Y offset |
| `spin` | 1500ms | full 360° rotation over duration |
| `grow` | 1200ms | scale: `1.0 + 0.3*sin(p*π)` where p=t/duration |
| `shrink` | 1200ms | scale: `1.0 - 0.3*sin(p*π)` |
| `inflate` | 1500ms | scale 1.0→1.4 ease-in (1100ms) → 1.0 snap-back (400ms) |
| `melt` | 1500ms | sx: 1.0→1.15, sy: 1.0→0.6 (hold 200ms, snap back) |
| `pulse` | 600ms | 2 rapid throbs: `1.0+0.15*abs(sin(t*π*2/300))` |
| `wobble` | 1000ms | damped: `20° * exp(-t/300) * sin(t*π*5/1000)` |
| `wave` | 1500ms | rotation: `sin(t*π*3/1500) * 15°` |
| `flip` | 400ms | sx: `cos(t*π/400)` (1 → -1 → 1 mirror) |
| `nod` | 800ms | rotation keyframes: 0→12°→0→-5°→0 |
| `headshake` | 800ms | rotation keyframes: 0→-18°→18°→-8°→0 |
| `tremble` | 1000ms | ±2° rotation + ±1px xy jitter at 12Hz |
| `flail` | 1200ms | random ±30° rotation burst every 100ms |
| `look_away` | 4000ms | pupils hard-avert opposite cursor direction |

### 3.2 Position Actions — PetWindow applies x/y

| Action | Default Duration | Behavior |
|--------|-----------------|----------|
| `jump` | 800ms | Y offset: `-sin(t/800*π)*40px` (parabolic arc, no physics) |
| `float` | 2000ms | Y offset: `-sin(t*π/1000)*8px` (1 gentle oscillation cycle) |
| `dash` | 500ms | X burst: +60px toward current facing direction, snap back |
| `strut` | 2000ms | deliberate PERIMETER-style walk at 60% speed |
| `teleport` | 1100ms | opacity 1→0 (350ms), reposition to random screen point, 0→1 (350ms) |

### 3.3 Color / Opacity Actions — renderer-only

| Action | Default Duration | Behavior |
|--------|-----------------|----------|
| `rainbow` | 2000ms | body hue cycles 0°→360° via HSL |
| `glitch` | 1500ms | ±5px random offset every 30ms + ±40° hue shift + opacity flicker 0.7–1.0 |
| `vanish` | 1300ms | opacity: 1.0→0.0 (400ms) → hold 500ms → 0.0→1.0 (400ms) |

---

## 4. MCP Contract

### 4.1 Updated `change_visual_state` schema

```json
{
  "name": "change_visual_state",
  "description": "Trigger Daemon's FSM state or a layered expression action.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "action": {
        "type": "string",
        "enum": [
          "idle", "wander", "hyper", "celebrate", "devastated", "fall", "chase",
          "float", "jump", "grow", "shrink", "pulse", "glitch", "rainbow",
          "flip", "teleport", "wave", "wobble", "dash", "melt", "inflate",
          "nod", "headshake", "tremble", "strut", "flail", "vanish",
          "shake", "bounce", "spin", "look_away"
        ]
      },
      "layer": {
        "type": "string",
        "enum": ["fsm", "expression"],
        "description": "fsm = exclusive behavioral state. expression = stackable physical action, auto-expires."
      },
      "duration_ms": {
        "type": "integer",
        "description": "Optional duration override for expression actions. Ignored for fsm layer."
      }
    },
    "required": ["action", "layer"]
  }
}
```

### 4.2 Routing rules in MCPHandler

| Condition | Outcome |
|-----------|---------|
| `layer="fsm"` + FSM action | Routes to FSMActionBridge (existing path) |
| `layer="expression"` + expression action | Routes to ActionLayer.trigger() |
| `layer="fsm"` + expression action | -32602 invalid params |
| `layer="expression"` + FSM action | -32602 invalid params |

FSM-only actions: `idle`, `wander`, `hyper`, `celebrate`, `devastated`, `fall`, `chase`  
Expression-only actions: all 24 listed in Section 3

---

## 5. Renderer Pipeline

### 5.1 `RenderContext` addition

```python
@dataclass
class RenderContext:
    # ... all existing fields unchanged ...
    action_stack: list = field(default_factory=list)  # list[ActiveAction]
```

### 5.2 `PetRenderer._draw_pet()` updated pipeline

```
1. FSM base transform:    sx, sy, rot    ← _state_transform(ctx)
2. FSM offset:            ox, oy         ← _state_offset(ctx)
3. Accumulate expression layer from action_stack:
     expr_sx = expr_sy = 1.0;  expr_rot = expr_ox = expr_oy = 0.0
     expr_opacity = 1.0;  expr_hue = None

     for action in ctx.action_stack:
         elapsed_ms = action's elapsed time
         tr = get_action_transform(action.name, elapsed_ms, action.duration_ms)
         expr_sx      *= tr.sx
         expr_sy      *= tr.sy
         expr_rot     += tr.rot
         expr_ox      += tr.ox
         expr_oy      += tr.oy
         expr_opacity *= tr.opacity
         if tr.hue_shift is not None:
             expr_hue = tr.hue_shift   # last color action wins

4. painter.setOpacity(base_opacity * expr_opacity)
5. painter.translate(cx + ox + expr_ox, cy + oy + expr_oy)
6. painter.rotate(rot + expr_rot)
7. painter.scale(sx * expr_sx, sy * expr_sy)
8. if expr_hue: hue-shift body_color by expr_hue degrees
9. _draw_body → _draw_eyes → _draw_mouth   (unchanged)
10. painter.restore()
```

### 5.3 `ActionTransform` dataclass (internal to `action_layer.py`)

```python
@dataclass
class ActionTransform:
    sx: float = 1.0
    sy: float = 1.0
    rot: float = 0.0
    ox: float = 0.0
    oy: float = 0.0
    opacity: float = 1.0
    hue_shift: float | None = None
```

### 5.4 Position-affecting actions (`PetWindow._apply_action_positions`)

Called from `_tick()` after `ActionLayer.tick(33)`. Reads `action_layer.get_active()`:

- `jump`, `float`, `bounce`: add computed Y offset to `_pet_y` each tick (does not trigger FALLING physics)
- `dash`: add computed X offset to `_pet_x` toward current facing
- `strut`: move pet as PERIMETER at 60% speed
- `teleport`: at midpoint (opacity≈0), call `_reposition_pet(rx, ry)` where rx/ry
  are pre-computed random screen coords stored in `action.params` at trigger time.
  Gated by `action._position_applied` flag (one-shot).

---

## 6. SKILL.md Additions (`.opencode/skills/kenny/SKILL.md`)

### Expression Action Palette section

```markdown
## Expression Actions (layer="expression")
Stack up to 2 per trigger call. Auto-expire. Do NOT interrupt FSM state.

### Emotion Expressions
nod          → agreement, affirmation
headshake    → disagreement, exasperation
tremble      → fear, nervous energy
flail        → panic, chaos
wobble       → uncertainty, confusion

### Physical Reactions
shake        → startled, bad code
bounce       → excitement
jump         → surprise, realization
float        → smugness, above it all
strut        → confidence
dash         → urgency

### Body Language
grow         → puffing up, proud or threatening
shrink       → embarrassed, backing down
inflate      → building to something
melt         → defeated, exasperated

### Visual Flair (use sparingly)
spin         → dizziness
flip         → disbelief
pulse        → alarmed
rainbow      → celebration or mockery
glitch       → malfunctioning
vanish       → ignoring or dramatic exit
teleport     → restless, can't stay still
wave         → wavering, unsure
look_away    → pointedly ignoring
```

### Good Combos section

```markdown
## Action Stacking — max 2 actions per trigger call
grow + rainbow      → triumph
tremble + float     → anxious hovering
nod + pulse         → emphatic agreement
shrink + vanish     → embarrassed exit
flail + glitch      → full system panic
headshake + melt    → pure exasperation
```

### Hard rules for LLM

- NEVER use `layer="fsm"` for expression actions
- NEVER use `layer="expression"` for FSM actions (idle/celebrate/etc.)
- Stack maximum 2 actions per call
- `teleport` and `strut` move the pet on screen — use contextually, not spamming
- `duration_ms` override only when timing matters (synced to dialogue)

---

## 7. Test Plan

| File | Coverage |
|------|----------|
| `tests/test_action_layer.py` | trigger(), tick() expiry, stack cap (5), clear(), get_active() snapshot |
| `tests/test_action_transforms.py` | each of 24 actions: transform at t=0, t=mid, t=duration |
| `tests/test_mcp_action_routing.py` | expression routing, FSM routing, mismatch → -32602 |
| `tests/test_fsm_migration.py` | SHAKING/BOUNCING/SPINNING/LOOK_AWAY absent from PetState; triggered_action absent from FSMContext |
| Existing `tests/test_fsm.py` | Regression: 35 tests minus 4 removed-state tests still pass |
| Existing `tests/test_pet_renderer.py` | Regression: renderer works with empty action_stack |

---

## 8. Constants (additions to `src/constants.py`)

```python
# Action Layer
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
# Migrated (updated from old FSM constants)
ACTION_SHAKE_DURATION_MS      = 500
ACTION_BOUNCE_DURATION_MS     = 600
ACTION_SPIN_DURATION_MS       = 1500
ACTION_LOOK_AWAY_DURATION_MS  = 4000
```

---

## 9. Out of Scope

- Action chaining / sequencing
- Sound effects per action
- User-facing action picker UI
- Plugin-contributed actions (possible future extension via PluginRegistry)
