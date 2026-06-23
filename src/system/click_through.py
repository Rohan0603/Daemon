# src/system/click_through.py
import ctypes
import ctypes.wintypes
import logging
import time
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
        self._get_geometry = get_geometry_fn   # callable -> QRect
        self._transparent = False
        self._last_toggle_time: float = 0.0
        self._prev_cursor_over: bool | None = None

        self._timer = QTimer()
        self._timer.setInterval(CLICK_THROUGH_POLL_MS)
        self._timer.timeout.connect(self._poll)
        self._timer.start()
        self._stopped = False

        self.enable_click_through()
        self._prev_cursor_over = False

    def enable_click_through(self) -> None:
        style = ctypes.windll.user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(
            self._hwnd, GWL_EXSTYLE,
            style | WS_EX_LAYERED | WS_EX_TRANSPARENT
        )
        self._transparent = True
        self._last_toggle_time = time.time()
        logger.debug("Click-through enabled for HWND %d", self._hwnd)

    def disable_click_through(self) -> None:
        style = ctypes.windll.user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(
            self._hwnd, GWL_EXSTYLE,
            style & ~WS_EX_TRANSPARENT
        )
        self._transparent = False
        self._last_toggle_time = time.time()
        logger.debug("Click-through disabled for HWND %d", self._hwnd)

    def stop(self) -> None:
        self._stopped = True
        self._timer.stop()

    def _poll(self) -> None:
        if self._stopped:
            return
        cursor = QCursor.pos()
        geom: QRect = self._get_geometry()

        if self._transparent:
            # When transparent, EXPAND hit area so cursor easily enters to disable click-through
            hit_geom = geom.adjusted(
                -_HYSTERESIS_MARGIN_PX, -_HYSTERESIS_MARGIN_PX,
                _HYSTERESIS_MARGIN_PX, _HYSTERESIS_MARGIN_PX,
            )
            cursor_over = hit_geom.contains(cursor)
        else:
            # When opaque, SHRINK hit area so cursor must be well inside to keep click-through disabled
            hit_geom = geom.adjusted(
                _HYSTERESIS_MARGIN_PX, _HYSTERESIS_MARGIN_PX,
                -_HYSTERESIS_MARGIN_PX, -_HYSTERESIS_MARGIN_PX,
            )
            cursor_over = hit_geom.contains(cursor)

        if cursor_over == self._prev_cursor_over:
            return

        if time.time() - self._last_toggle_time < _TOGGLE_DEBOUNCE_SEC:
            return

        self._prev_cursor_over = cursor_over

        if cursor_over and self._transparent:
            self.disable_click_through()
        elif not cursor_over and not self._transparent:
            self.enable_click_through()