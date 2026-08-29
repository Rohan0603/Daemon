"""Screen capture and bounded coordinate interaction for non-UIA applications."""
from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes
import io
import logging
import math
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

_SM_XVIRTUALSCREEN = 76
_SM_YVIRTUALSCREEN = 77
_SM_CXVIRTUALSCREEN = 78
_SM_CYVIRTUALSCREEN = 79
_MOUSEEVENTF_LEFTDOWN = 0x0002
_MOUSEEVENTF_LEFTUP = 0x0004
_MOUSEEVENTF_RIGHTDOWN = 0x0008
_MOUSEEVENTF_RIGHTUP = 0x0010
_MOUSEEVENTF_MIDDLEDOWN = 0x0020
_MOUSEEVENTF_MIDDLEUP = 0x0040


def _virtual_screen() -> tuple[int, int, int, int]:
    user32 = ctypes.windll.user32
    left = int(user32.GetSystemMetrics(_SM_XVIRTUALSCREEN))
    top = int(user32.GetSystemMetrics(_SM_YVIRTUALSCREEN))
    width = int(user32.GetSystemMetrics(_SM_CXVIRTUALSCREEN))
    height = int(user32.GetSystemMetrics(_SM_CYVIRTUALSCREEN))
    if width <= 0 or height <= 0:
        raise RuntimeError("Unable to determine virtual screen bounds")
    return left, top, left + width, top + height


def _set_cursor(x: int, y: int) -> None:
    if not ctypes.windll.user32.SetCursorPos(x, y):
        raise OSError(f"SetCursorPos failed for ({x}, {y})")


def _cursor_position() -> tuple[int, int]:
    point = ctypes.wintypes.POINT()
    if not ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
        raise OSError("GetCursorPos failed")
    return int(point.x), int(point.y)


def _mouse_click(click_type: str) -> None:
    flags = {
        "left": (_MOUSEEVENTF_LEFTDOWN, _MOUSEEVENTF_LEFTUP),
        "right": (_MOUSEEVENTF_RIGHTDOWN, _MOUSEEVENTF_RIGHTUP),
        "middle": (_MOUSEEVENTF_MIDDLEDOWN, _MOUSEEVENTF_MIDDLEUP),
    }.get(click_type)
    if flags is None:
        raise ValueError(f"Unsupported click type: {click_type}")
    user32 = ctypes.windll.user32
    user32.mouse_event(flags[0], 0, 0, 0, 0)
    user32.mouse_event(flags[1], 0, 0, 0, 0)


class VisionController:
    """Capture screens and perform explicitly bounded coordinate interactions."""

    def __init__(
        self,
        enable_grid: bool = True,
        grid_spacing: int = 100,
        *,
        screen_bounds_provider: Callable[[], tuple[int, int, int, int]] = _virtual_screen,
        cursor_position_provider: Callable[[], tuple[int, int]] = _cursor_position,
        cursor_provider: Callable[[int, int], None] = _set_cursor,
        click_provider: Callable[[str], None] = _mouse_click,
        sleep_provider: Callable[[float], None] = time.sleep,
        keyboard_provider: Callable[[], Any] | None = None,
    ) -> None:
        if grid_spacing <= 0:
            raise ValueError("grid_spacing must be positive")
        self.enable_grid = enable_grid
        self.grid_spacing = grid_spacing
        self._screen_bounds_provider = screen_bounds_provider
        self._cursor_position_provider = cursor_position_provider
        self._cursor_provider = cursor_provider
        self._click_provider = click_provider
        self._sleep_provider = sleep_provider
        self._keyboard_provider = keyboard_provider

    def capture_screen(
        self,
        region: tuple[int, int, int, int] | None = None,
        add_grid: bool | None = None,
        add_som: bool = False,
    ) -> dict[str, Any]:
        """Capture a PNG with optional absolute-coordinate grid metadata."""
        from PIL import ImageGrab, ImageDraw

        bounds = self._screen_bounds_provider()
        capture_region = self._normalize_region(region, bounds)
        image = ImageGrab.grab(bbox=capture_region, all_screens=True)
        grid_enabled = self.enable_grid if add_grid is None else bool(add_grid)
        if grid_enabled:
            self._draw_grid(image, capture_region)

        som_elements: list[dict[str, Any]] = []
        if add_som:
            logger.info("Set-of-Marks requested without element provider; returning empty marks")

        encoded = io.BytesIO()
        image.save(encoded, format="PNG")
        return {
            "image_base64": base64.b64encode(encoded.getvalue()).decode("ascii"),
            "image_path": None,
            "region": capture_region,
            "grid_overlay": grid_enabled,
            "som_overlay": bool(add_som),
            "som_elements": som_elements,
            "dpi_scale": 1.0,
            "monitor_info": [
                {
                    "left": bounds[0],
                    "top": bounds[1],
                    "right": bounds[2],
                    "bottom": bounds[3],
                    "dpi_scale": 1.0,
                }
            ],
        }

    def click_coordinate(
        self,
        x: int,
        y: int,
        click_type: str = "left",
        smooth: bool = True,
        duration: float = 0.3,
    ) -> dict[str, Any]:
        """Move to a clamped virtual-screen coordinate and click."""
        if click_type not in {"left", "right", "middle", "double"}:
            return {"success": False, "error": f"Unsupported click type: {click_type}"}
        if duration < 0:
            return {"success": False, "error": "duration must be non-negative"}
        bounds = self._screen_bounds_provider()
        cx = max(bounds[0], min(int(x), bounds[2] - 1))
        cy = max(bounds[1], min(int(y), bounds[3] - 1))
        try:
            self._move_cursor(cx, cy, smooth, duration)
            actual_click = "left" if click_type == "double" else click_type
            self._click_provider(actual_click)
            if click_type == "double":
                self._sleep_provider(0.05)
                self._click_provider("left")
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Vision coordinate action failed: %s", exc)
            return {"success": False, "error": str(exc), "x": cx, "y": cy}
        return {"success": True, "error": None, "x": cx, "y": cy, "click_type": click_type}

    def type_text(self, text: str, interval: float = 0.01) -> dict[str, Any]:
        """Type text at the current cursor position through pynput."""
        if not isinstance(text, str) or not text:
            return {"success": False, "error": "text must be a non-empty string"}
        if interval < 0:
            return {"success": False, "error": "interval must be non-negative"}
        try:
            keyboard = self._keyboard_provider() if self._keyboard_provider else self._default_keyboard()
            keyboard.type(text, interval=interval)
        except (ImportError, OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Vision text action failed: %s", exc)
            return {"success": False, "error": str(exc)}
        return {"success": True, "error": None, "characters": len(text)}

    def get_monitor_layout(self) -> list[dict[str, Any]]:
        """Return the virtual monitor layout available to the process."""
        left, top, right, bottom = self._screen_bounds_provider()
        return [{"left": left, "top": top, "right": right, "bottom": bottom, "dpi_scale": 1.0}]

    def _move_cursor(self, x: int, y: int, smooth: bool, duration: float) -> None:
        if not smooth or duration == 0:
            self._cursor_provider(x, y)
            return
        steps = max(2, min(60, math.ceil(duration * 60)))
        start_x, start_y = self._cursor_position_provider()
        # Use a short bounded interpolation; absolute coordinates remain clamped.
        for step in range(1, steps + 1):
            progress = step / steps
            eased = progress * progress * (3 - 2 * progress)
            self._cursor_provider(
                round(start_x + (x - start_x) * eased),
                round(start_y + (y - start_y) * eased),
            )
            self._sleep_provider(duration / steps)

    @staticmethod
    def _default_keyboard() -> Any:
        from pynput.keyboard import Controller

        return Controller()

    @staticmethod
    def _normalize_region(
        region: tuple[int, int, int, int] | None,
        bounds: tuple[int, int, int, int],
    ) -> tuple[int, int, int, int]:
        if region is None:
            return bounds
        if len(region) != 4:
            raise ValueError("region must contain four coordinates")
        left, top, right, bottom = (int(value) for value in region)
        left = max(bounds[0], min(left, bounds[2] - 1))
        top = max(bounds[1], min(top, bounds[3] - 1))
        right = max(left + 1, min(right, bounds[2]))
        bottom = max(top + 1, min(bottom, bounds[3]))
        return left, top, right, bottom

    def _draw_grid(self, image: Any, region: tuple[int, int, int, int]) -> None:
        from PIL import ImageDraw

        left, top, right, bottom = region
        draw = ImageDraw.Draw(image, "RGBA")
        for x in range(left - (left % self.grid_spacing), right, self.grid_spacing):
            px = x - left
            draw.line((px, 0, px, image.height), fill=(255, 255, 0, 150), width=1)
            draw.text((px + 2, 2), str(x), fill=(255, 255, 0, 255))
        for y in range(top - (top % self.grid_spacing), bottom, self.grid_spacing):
            py = y - top
            draw.line((0, py, image.width, py), fill=(255, 255, 0, 150), width=1)
            draw.text((2, py + 2), str(y), fill=(255, 255, 0, 255))
