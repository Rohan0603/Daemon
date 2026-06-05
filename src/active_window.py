from __future__ import annotations
import logging
import sys

logger = logging.getLogger(__name__)


def get_active_window_title() -> str:
    if sys.platform != "win32":
        return ""
    try:
        import ctypes
        import ctypes.wintypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value
    except Exception as e:
        logger.debug("Failed to get active window title: %s", e)
        return ""
