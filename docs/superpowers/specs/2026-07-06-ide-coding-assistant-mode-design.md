# IDE Coding Assistant Mode — Design Spec

**Date:** 2026-07-06
**Status:** Approved

---

## Goal

When a recognized coding IDE is the foreground window, Daemon enters **Code Mode**:
- Emotional state shifts to TRANQUILITY (focused, zen squint, 80% alpha)
- ThoughtPool draws exclusively `code_assist` and `typing_reaction` types
- Kenny proactively reads screen text & typing buffer to give actual coding hints, suggestions, and code reviews as dialogue
- Full Kenny gremlin voice — same panic/humor, but content is technical

---

## IDE Detection

**Qualified IDEs** (already normalized in `src/system/active_window.py::KNOWN_APPS`):
- `vscode`, `pycharm`, `intellij`, `webstorm`, `goland`, `sublime_text`, `notepadpp`

Detection is a pure function: `is_ide_window(title: str) -> bool`
Lives in `src/system/active_window.py` alongside `normalize_window_title`.

**Entry:** `normalize_window_title(get_active_window_title())` is one of the IDE slugs.
**Exit:** Title no longer normalizes to an IDE slug.

---

## Architecture

### 1. BehaviorController — IDE mode state

`_in_ide_mode: bool = False`  
Per-tick: detect transition, publish EventBus event, switch draw type.

### 2. New EventType variants

```python
IDE_MODE_ENTERED = "ide_mode_entered"
IDE_MODE_EXITED = "ide_mode_exited"
```

### 3. ThoughtPool draw in IDE mode

- Chat trigger: draw `code_assist` (fallback: `typing_reaction`)
- Boredom trigger: draw `code_assist`
- Normal mode: unchanged (`typing_reaction` / `idle_thought`)

Spatial TTL auto-expires wrong-context items.

### 4. STRUCTURED_SCHEMA — new type

Add `code_assist` to the `type` enum in `constants.py`.

### 5. ContextManager — IDE-aware prompt

`build_autonomous_trigger()` gains `ide_mode: bool = False, ide_name: str = ""` params.
In IDE mode, appends CODING MODE block with screen text + typing snippet.

### 6. Emotion Engine — TRANQUILITY in IDE

In `_evaluate_emotion()`, above DEVOTION:
```python
if self._in_ide_mode:
    return Emotion.TRANQUILITY
```

### 7. SKILL.md — CODING ASSISTANT MODE section

Documents `code_assist` type rules, Kenny's coding persona, examples.

---

## Files Changed

| File | Change |
|------|--------|
| `src/system/active_window.py` | Add `is_ide_window(title) -> bool` |
| `src/events.py` | Add `IDE_MODE_ENTERED`, `IDE_MODE_EXITED` |
| `src/constants.py` | Add `code_assist` to schema enum |
| `src/autonomy/behavior_controller.py` | `_in_ide_mode` state, mode draw, emotion pin |
| `src/llm/context_manager.py` | `ide_mode` param on `build_autonomous_trigger` |
| `.opencode/skills/kenny/SKILL.md` | CODING ASSISTANT MODE section |
| `tests/test_active_window.py` | Tests for `is_ide_window` |
| `tests/test_behavior_controller_ide.py` | IDE mode state, event, draw type |

---

## Constraints

- No new FSM state
- No new Pool
- No new LLM model
- APM > 80 gate still silences even in IDE mode
- Kenny reads code and talks — no MCP writes to files

