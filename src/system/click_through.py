# src/system/click_through.py
import ctypes
import ctypes.wintypes
import logging
from typing import Callable
from PyQt6.QtCore import QTimer, QRect
from PyQt6.QtGui import QCursor
from src.constants import CLICK_THROUGH_POLL_MS

logger = logging.getLogger(__name__)

GWL_EXSTYLE          = -20
WS_EX_TRANSPARENT    = 0x00000020
WS_EX_LAYERED        = 0x00080000

_TOGGLE_DEBOUNCE_SEC = 0.5
_HYSTERESIS_MARGIN_PX = 15


class ClickThroughManager:
    def __init__(self, hwnd: int, get_geometry_fn: Callable[[], QRect]) -> None:
        self._hwnd = hwnd
        self._get_geometry = get_geometry_fn
        self._transparent = False
        self._prev_cursor_over: bool | None = None

        self._timer = QTimer()
        self._timer.setInterval(CLICK_THROUGH_POLL_MS)
        self._timer.timeout.connect(self._poll)
        self._timer.start()
        self._stopped = False

        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(100)
        self._debounce_timer.timeout.connect(self._apply_toggle)
        self._pending_transparent: bool | None = None

        self.enable_click_through()
        self._prev_cursor_over = False

    def _apply_toggle(self) -> None:
        if self._pending_transparent is None:
            return
        want_transparent = self._pending_transparent
        self._pending_transparent = None
        if want_transparent and not self._transparent:
            self.enable_click_through()
        elif not want_transparent and self._transparent:
            self.disable_click_through()

    def enable_click_through(self) -> None:
        style = ctypes.windll.user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(
            self._hwnd, GWL_EXSTYLE,
            style | WS_EX_LAYERED | WS_EX_TRANSPARENT
        )
        self._transparent = True
        logger.debug("Click-through enabled for HWND %d", self._hwnd)

    def disable_click_through(self) -> None:
        style = ctypes.windll.user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(
            self._hwnd, GWL_EXSTYLE,
            style & ~WS_EX_TRANSPARENT
        )
        self._transparent = False
        logger.debug("Click-through disabled for HWND %d", self._hwnd)

    def stop(self) -> None:
        self._stopped = True
        self._timer.stop()
        self._debounce_timer.stop()

    def _poll(self) -> None:
        if self._stopped:
            return
        cursor = QCursor.pos()
        geom: QRect = self._get_geometry()

        if self._transparent:
            hit_geom = geom.adjusted(
                -_HYSTERESIS_MARGIN_PX, -_HYSTERESIS_MARGIN_PX,
                _HYSTERESIS_MARGIN_PX, _HYSTERESIS_MARGIN_PX,
            )
            cursor_over = hit_geom.contains(cursor)
        else:
            hit_geom = geom.adjusted(
                _HYSTERESIS_MARGIN_PX, _HYSTERESIS_MARGIN_PX,
                -_HYSTERESIS_MARGIN_PX, -_HYSTERESIS_MARGIN_PX,
            )
            cursor_over = hit_geom.contains(cursor)

        if cursor_over == self._prev_cursor_over:
            return

        # Debounce: wait 100ms before toggling — cancels if cursor reverts
        self._prev_cursor_over = cursor_over
        self._pending_transparent = not cursor_over
        if self._debounce_timer.isActive():
            self._debounce_timer.stop()
        self._debounce_timer.start()