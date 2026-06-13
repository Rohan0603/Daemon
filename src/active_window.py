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


def get_window_rect() -> tuple[int, int, int, int] | None:
    """Return (left, top, right, bottom) of foreground window, or None."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        import ctypes.wintypes
        
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return None

        # Check if maximized (GWL_STYLE = -16, WS_MAXIMIZE = 0x01000000)
        style = ctypes.windll.user32.GetWindowLongW(hwnd, -16)
        if style & 0x01000000:
            return None

        rect = ctypes.wintypes.RECT()
        DWMWA_EXTENDED_FRAME_BOUNDS = 9
        
        try:
            result = ctypes.windll.dwmapi.DwmGetWindowAttribute(
                hwnd,
                ctypes.c_uint(DWMWA_EXTENDED_FRAME_BOUNDS),
                ctypes.byref(rect),
                ctypes.sizeof(rect)
            )
            if result != 0:
                ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        except Exception:
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
            
        return (rect.left, rect.top, rect.right, rect.bottom)
    except Exception as e:
        logger.debug("Failed to get window rect: %s", e)
        return None
