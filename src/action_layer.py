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
