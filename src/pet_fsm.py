from __future__ import annotations
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Tuple

from src.constants import (
    CHASE_ENTER_RADIUS_PX, CHASE_EXIT_RADIUS_PX,
    APM_HYPER_THRESHOLD, SLEEP_IDLE_SECONDS,
    MIN_CHASE_DURATION_MS,
)


class PetState(Enum):
    IDLE               = auto()
    SLEEP              = auto()
    PERIMETER          = auto()
    CHASE              = auto()
    HYPER              = auto()
    THINKING           = auto()
    CELEBRATE          = auto()
    DEVASTATED         = auto()
    DRAGGED            = auto()
    FALLING            = auto()
    AUTONOMOUS_THINKING = auto()


@dataclass
class FSMContext:
    cursor_pos: Tuple[int, int]
    pet_rect: Tuple[int, int, int, int]   # x, y, w, h
    apm: int
    is_dragged: bool
    is_falling: bool
    query_pending: bool
    build_event: Optional[str]            # "success" | "failure" | None
    idle_seconds: float
    wander_due: bool
    hyper_sustained_seconds: float
    hyper_cooldown_seconds: float
    state_elapsed_ms: int
    autonomous_query_pending: bool
    edge: str = "bottom"      # "bottom" | "left" | "top" | "right"
    facing: str = "right"     # direction along edge


class PetFSM:
    def __init__(self) -> None:
        self.current_state = PetState.IDLE
        self._last_chase_exit_time: float = 0.0

    def transition_to(self, new_state: PetState, on_transition=None) -> None:
        if new_state == self.current_state:
            return
        old = self.current_state
        self.current_state = new_state
        if on_transition:
            on_transition(old, new_state)

    def update(self, dt_ms: int, ctx: FSMContext) -> PetState:
        next_state = self._evaluate(ctx)
        if next_state == self.current_state:
            return next_state
        self.current_state = next_state
        return next_state

    def _cursor_distance(self, ctx: FSMContext) -> float:
        px, py = ctx.cursor_pos
        rx, ry, rw, rh = ctx.pet_rect
        cx = rx + rw / 2
        cy = ry + rh / 2
        return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5

    def _evaluate(self, ctx: FSMContext) -> PetState:
        cur = self.current_state

        # Priority 1: DRAGGED
        if ctx.is_dragged:
            return PetState.DRAGGED

        # Priority 2: FALLING
        if ctx.is_falling:
            return PetState.FALLING

        # Priority 3: CHASE (minimum dwell 500ms to prevent cursor jitter thrashing)
        if not ctx.query_pending:
            dist = self._cursor_distance(ctx)
            if cur == PetState.CHASE:
                if dist > CHASE_EXIT_RADIUS_PX and ctx.state_elapsed_ms >= MIN_CHASE_DURATION_MS:
                    self._last_chase_exit_time = time.monotonic()
                    pass
                else:
                    return PetState.CHASE
            elif dist <= CHASE_ENTER_RADIUS_PX and cur not in (
                PetState.THINKING, PetState.CELEBRATE, PetState.DEVASTATED
            ):
                if time.monotonic() - self._last_chase_exit_time < 0.5:
                    pass
                else:
                    return PetState.CHASE

        # Priority 4: HYPER
        if cur == PetState.HYPER:
            if ctx.hyper_cooldown_seconds >= 10.0:
                pass
            else:
                return PetState.HYPER
        elif (
            ctx.apm > APM_HYPER_THRESHOLD and ctx.hyper_sustained_seconds >= 3.0
        ):
            return PetState.HYPER

        # Priority 5: THINKING
        if ctx.query_pending:
            return PetState.THINKING

        # Priority 6: CELEBRATE
        if ctx.build_event == "success":
            return PetState.CELEBRATE
        if cur == PetState.CELEBRATE:
            if ctx.state_elapsed_ms >= 3000:
                pass
            else:
                return PetState.CELEBRATE

        # Priority 7: DEVASTATED
        if ctx.build_event == "failure":
            return PetState.DEVASTATED
        if cur == PetState.DEVASTATED:
            if ctx.state_elapsed_ms >= 5000:
                pass
            else:
                return PetState.DEVASTATED

        # Priority 11: AUTONOMOUS_THINKING
        if ctx.autonomous_query_pending:
            return PetState.AUTONOMOUS_THINKING

        # Priority 13: PERIMETER
        if ctx.wander_due and cur == PetState.IDLE:
            return PetState.PERIMETER
        if cur == PetState.PERIMETER:
            return PetState.PERIMETER

        # Priority 14: SLEEP
        if ctx.idle_seconds >= SLEEP_IDLE_SECONDS:
            return PetState.SLEEP
        if cur == PetState.SLEEP and ctx.idle_seconds < SLEEP_IDLE_SECONDS:
            return PetState.IDLE

        # Priority 15: IDLE (default)
        return PetState.IDLE

