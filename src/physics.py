# src/physics.py - Ground contact physics for Daemon

from __future__ import annotations
import logging
import time
from typing import NamedTuple

logger = logging.getLogger(__name__)

GRAVITY_ACCELERATION = 0.8


class ContactResult(NamedTuple):
    """Result of ground contact resolution."""
    pet_y: int
    fall_velocity: float
    ground_y: int | None
    landed: bool
    bounced: bool
    land_time: float | None


class GroundContactResolver:
    """Resolves pet collision with ground and windows (title bars).

    Encapsulates the bounce/land logic previously inline in PetWindow._apply_physics.
    Pure logic — no Qt dependencies, fully testable.
    """

    def __init__(self, ground_y: int | None = None):
        self._ground_y = ground_y

    @property
    def ground_y(self) -> int | None:
        return self._ground_y

    @ground_y.setter
    def ground_y(self, value: int | None) -> None:
        self._ground_y = value

    def resolve(
        self,
        pet_x: int,
        pet_y: int,
        fall_velocity: float,
        pet_width: int,
        pet_height: int,
        bounce_delay_ms: int,
        pending_bounce_velocity: float,
        dt: int,
        window_rect: tuple[int, int, int, int] | None = None,
    ) -> ContactResult:
        """Apply gravity and check ground/window collision.

        Args:
            pet_x, pet_y: Current pet position (top-left).
            fall_velocity: Current vertical velocity (px/frame, positive = down).
            pet_width, pet_height: Pet dimensions.
            bounce_delay_ms: Remaining ms in bounce cooldown.
            pending_bounce_velocity: Velocity to apply after bounce cooldown.
            dt: Frame delta in ms.
            window_rect: (left, top, right, bottom) of the window title bar area.

        Returns:
            ContactResult with updated state.
        """
        if bounce_delay_ms > 0:
            new_delay = bounce_delay_ms - dt
            if new_delay <= 0:
                fall_velocity = pending_bounce_velocity
                pet_y -= 1
            return ContactResult(
                pet_y=pet_y,
                fall_velocity=fall_velocity,
                ground_y=self._ground_y,
                landed=False,
                bounced=new_delay > 0,
                land_time=None,
            )

        fall_velocity += GRAVITY_ACCELERATION
        pet_y += int(fall_velocity)

        landed = False
        bounced = False

        if window_rect is not None and fall_velocity >= 0:
            w_left, w_top, w_right, w_bottom = window_rect
            pet_center_x = pet_x + pet_width // 2
            proximity = (pet_y + pet_height) - w_top
            if w_left <= pet_center_x <= w_right and -5.0 <= proximity <= max(5.0, fall_velocity + 5.0):
                if fall_velocity > 10.0:
                    pet_y = w_top - pet_height
                    pending_bounce_velocity = -fall_velocity * 0.3
                    fall_velocity = 0.0
                    bounced = True
                else:
                    pet_y = w_top - pet_height
                    fall_velocity = 0.0
                    landed = True

        if not landed and self._ground_y is not None and pet_y >= self._ground_y and fall_velocity >= 0:
            if fall_velocity > 10.0:
                pet_y = self._ground_y
                pending_bounce_velocity = -fall_velocity * 0.3
                fall_velocity = 0.0
                bounced = True
            else:
                pet_y = self._ground_y
                fall_velocity = 0.0
                landed = True

        land_time = time.time() if landed or bounced else None
        return ContactResult(
            pet_y=pet_y,
            fall_velocity=fall_velocity,
            ground_y=self._ground_y,
            landed=landed,
            bounced=bounced,
            land_time=land_time,
        )
