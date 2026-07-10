---
name: add-emotion
description: Use when adding a new emotion to Daemon's visual layer. Covers adding the Emotion enum member in src/animator.py, registering it in the EMOTION_PROFILES registry, the EmotionProfile field set, and the system-driven (never LLM-driven) trigger boundary.
version: 1.0.0
author: Daemon Project
license: MIT
metadata:
  hermes:
    tags: [emotions, animator, visuals, daemon]
    related_skills: [run-tests]
---

# Add an Emotion

## Overview

Emotions are **purely system-driven visual overlays** evaluated every 5s by
`PetWindow._evaluate_emotion()`. Each emotion is declared as an `EmotionProfile`
dataclass in the `EMOTION_PROFILES` registry — this replaced the old
procedural `if/elif` chains. The LLM controls only *physical* animations
(`change_visual_state` MCP tool); it can never set an emotion, a color, or an
eye state.

## When to Use

- You want the pet to react visually to a new system condition (window title,
  APM threshold, idle, context change)
- Extending the 9-emotion set with a new mood
- Adjusting an existing emotion's color/eye/particle spec

Do NOT use for: LLM-driven reactions (those are FSM states / `change_visual_state`,
not emotions); changing the FSM (see `add-mcp-tool` / FSM docs in `AGENTS.md`).

## Edit Sites (all in `src/animator.py`)

1. **Add the enum member** — `class Emotion(Enum)` (around line 86):

   ```python
   class Emotion(Enum):
       MIRTH = "mirth"
       # ...
       MY_NEW = "my_new"     # add here
   ```

2. **Register the profile** — `EMOTION_PROFILES` (around line 137). Add a
   `EmotionProfile(...)` entry keyed by the new enum member:

   ```python
   EMOTION_PROFILES: dict[Emotion, EmotionProfile] = {
       # ...
       Emotion.MY_NEW: EmotionProfile(
           name="my_new",
           color_override="#ABCDEF",
           pupil_scale=0.9,
           mouth_shape="smile",
       ),
   }
   ```

3. **`EmotionProfile` fields** (dataclass at line 98) — pick what your emotion
   needs:
   - `name: str` (required)
   - `color_override: str` — hex body color
   - `color_hue_shift: int` — hue rotation in degrees (e.g. `-30` for disgust)
   - `pupil_scale: float`, `pupil_offset_x: float`, `pupil_shape: str`
     (`heart`, etc.)
   - `brow_angle: float`, `mouth_shape: str` (`smile`, `frown`, `sneer`, ...)
   - `particle_count: int`, `particle_color: str`, `particle_gravity: float`
   - `opacity_func: Callable` — e.g. `lambda t: 0.75 + 0.15*math.sin(...)`
   - `single_fire_decay_ms: int` — auto-decay to MIRTH (e.g. 3000)

4. **Wire the trigger** (if it needs a new system condition) — in
   `src/ui/pet_window.py`, `_evaluate_emotion()`. Add the condition that
   returns your `Emotion.MY_NEW`. Keep it system-driven (window title, APM,
   idle, context signature) — never LLM-controlled.

5. **Tests + verify** (see `run-tests` skill) — add tests for the new
   `EmotionProfile` and, if added, the evaluator branch. Use `safe_pet_window`
   / `mock_background_workers`; never build `PetWindow` by hand.

## The Boundary (important)

- **EmotionAnimator is system-driven only.** The LLM cannot set emotions,
  colors, or eye states via JSON or MCP.
- The LLM may only drive *physical* animations through `change_visual_state`
  (`action`, `layer`, `duration_ms`, `target_x/y`).
- Profiles must never write `pet_x` / `pet_y` (position) — they are visual
  overlays only.

## Common Pitfalls

1. Adding the enum member but forgetting the `EMOTION_PROFILES` entry →
   `KeyError` when the evaluator looks it up.
2. Wiring the trigger in `_evaluate_emotion()` but the condition never fires
   (wrong window-title substring, wrong APM threshold).
3. Letting an `EmotionProfile` set position/shape that writes `pet_x/pet_y` →
   violates the overlay-only boundary.
4. Trying to let the LLM pick the emotion → architecturally forbidden; route
   LLM reactions through FSM/`change_visual_state` instead.
5. Forgetting `single_fire_decay_ms` on a one-shot emotion → it sticks instead
   of decaying to MIRTH.

## Verification Checklist

- [ ] New `Emotion` enum member added
- [ ] Matching `EmotionProfile` registered in `EMOTION_PROFILES`
- [ ] Trigger condition added in `_evaluate_emotion()` (if applicable) and is
      system-driven
- [ ] No `pet_x`/`pet_y` writes in the profile (overlay-only)
- [ ] `py -m pytest tests/ -v` green and under 50s
