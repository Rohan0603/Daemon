# IDE Coding Assistant Mode

> **Feature Status:** Implemented (Phase 1)
> **Commits:** Tasks 1-7 on `task-48-ide-coding-mode`

## Overview

When the Daemon detects the user is working in a coding IDE (VS Code, PyCharm, IntelliJ, WebStorm, GoLand, Sublime Text, Notepad++), it switches into **Coding Assistant Mode** — altering its visual appearance, autonomous behavior, and LLM prompt context to match a coding-focused interaction style.

## Detection

The system checks the active window title every `_master_tick()` (1s) via `src/system/active_window.py`:

- **`is_ide_window(title)`** — returns `True` if the window title contains any slug in `_IDE_SLUGS`: `vscode`, `pycharm`, `intellij`, `webstorm`, `goland`, `sublime_text`, `notepadpp`
- **`normalize_window_title(title)`** — extracts the canonical slug (e.g. `"main.py — Visual Studio Code"` → `"vscode"`)

## Behavior Changes (BehaviorController)

| Trigger | Normal Mode | IDE Mode |
|---------|------------|----------|
| `_trigger_chat()` | `draw_type: "typing_reaction"` | `draw_type: "code_assist"` |
| `_trigger_boredom_fsm()` | `draw_type: "idle_thought"` | `draw_type: "code_assist"` |
| Event emitted | `AUTONOMOUS_TRIGGER_FIRED` | Same event with `draw_type`, `ide_mode`, `ide_name` in data |

### IDE Mode Events

- **`IDE_MODE_ENTERED`** (weight 500) — published when `is_ide_window()` becomes `True`
- **`IDE_MODE_EXITED`** (weight 500) — published when `is_ide_window()` becomes `False`

PetWindow subscribes to these events and toggles `self._ide_mode`.

## Visual Changes (PetRenderer)

| Aspect | Normal | IDE Mode |
|--------|--------|----------|
| Body color | `BODY_BLUE` (#4A6FA5) | Dark Turquoise (#00CED1) |
| Overlay | None | Blinking `▋` cursor in bottom-right (500ms on/off cycle) |

The teal tint is applied at the top of `_body_color()` — it overrides all state-based colors (HYPER flash colors etc.).

The cursor blink uses `anim_tick` (33ms per tick): visible for 15 ticks (~500ms), hidden for 15 ticks.

## Prompt Enrichment (ContextManager)

When `ide_slug` is passed to either `build_user_trigger()` or `build_autonomous_trigger()`, an additional context line is appended:

**User trigger:**
> Context: you are in {ide_slug}. The user is coding.

**Autonomous trigger:**
> Context: the user is in {ide_slug}. They are coding.

## ThoughtPool Integration

The `draw_type: "code_assist"` maps to the existing `code_assist` type in the structured output schema (`STRUCTURED_SCHEMA` in `src/constants.py`). When `_trigger_chat()` fires in IDE mode, the ThoughtPool draw is filtered to `code_assist` type, which can be generated during mixed-bag refills alongside `typing_reaction`, `idle_thought`, `observation`, and `intel_roast`.

## Test Coverage

| Test File | Tests | What it covers |
|-----------|-------|----------------|
| `tests/test_active_window.py` | 5 new tests | `is_ide_window()` TRUE/FALSE for each slug, non-IDE windows |
| `tests/test_behavior_controller_ide.py` | 8 tests | `_in_ide_mode`, `_check_ide_mode_transition()`, draw_type switching, event publishing |
| `tests/test_pet_renderer_ide.py` | 7 tests | `ide_mode` in RenderContext, teal body color, cursor blink phases |
| `tests/test_context_manager_ide.py` | 5 tests | IDE slug injection in build methods, cache invalidation |

## Implementation Details

### Files Changed

| File | Change |
|------|--------|
| `src/system/active_window.py` | Added `_IDE_SLUGS` frozenset, `is_ide_window()`, `normalize_window_title()` |
| `src/active_window.py` | Exported new functions |
| `src/events.py` | Added `IDE_MODE_ENTERED`, `IDE_MODE_EXITED` events; extended `emit_autonomous_trigger()` signature |
| `src/constants.py` | Added `"code_assist"` to `STRUCTURED_SCHEMA` enum |
| `src/autonomy/behavior_controller.py` | Added `_in_ide_mode`, `_check_ide_mode_transition()`, draw-type switching in triggers |
| `src/ui/pet_renderer.py` | Added `ide_mode` to `RenderContext`, teal body color, `_draw_ide_cursor()` |
| `src/ui/pet_window.py` | Wired `ide_mode` from events → `RenderContext`, passed `ide_slug` to ContextManager |
| `src/llm/context_manager.py` | Added `ide_slug` param to build methods + cache key |

### Adding IDE Slugs

To add a new IDE, add its slug to `_IDE_SLUGS` in `src/system/active_window.py`:

```python
_IDE_SLUGS = frozenset({
    "vscode", "pycharm", "intellij", "webstorm",
    "goland", "sublime_text", "notepadpp",
    "vim", "emacs",  # new
})
```

The slug must match a substring found in the IDE's window title (lowercased).
