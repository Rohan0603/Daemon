from __future__ import annotations
import logging
import sys

logger = logging.getLogger(__name__)


def normalize_window_title(title: str) -> str:
    """Extract a stable application identifier from a window title.

    Examples:
        'main.py - Visual Studio Code' -> 'vscode'
        'readme.md - VSCode'           -> 'vscode'
        'Discord'                      -> 'discord'
        'Firefox'                      -> 'firefox'
        ''                             -> ''
    """
    if not title:
        return ""
    title_lower = title.lower()

    # Known application patterns (order: more specific first)
    KNOWN_APPS = {
        "visual studio code": "vscode",
        "vscode": "vscode",
        "discord": "discord",
        "mozilla firefox": "firefox",
        "firefox": "firefox",
        "google chrome": "chrome",
        "chrome": "chrome",
        "sublime text": "sublime_text",
        "notepad++": "notepadpp",
        "intellij idea": "intellij",
        "pycharm": "pycharm",
        "webstorm": "webstorm",
        "goland": "goland",
        "windows terminal": "terminal",
        "terminal": "terminal",
        "outlook": "outlook",
        "slack": "slack",
        "spotify": "spotify",
    }

    for app, normalized in KNOWN_APPS.items():
        if app in title_lower:
            return normalized

    # Fallback: take last word after dash/hyphen (e.g., "main.py - Editor" -> "editor")
    for sep in (" - ", " — ", " – "):
        if sep in title:
            parts = title.split(sep)
            return parts[-1].strip().lower().replace(" ", "_")

    # Last resort: use the title itself (lowercased, trimmed)
    return title_lower.strip()[:30]


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


_last_hwnd = None

def get_window_rect(ignore_hwnd: int = 0) -> tuple[int, int, int, int] | None:
    """Return (left, top, right, bottom) of foreground window, or None."""
    global _last_hwnd
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        import ctypes.wintypes
        
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return None
            
        if hwnd == ignore_hwnd:
            if _last_hwnd:
                hwnd = _last_hwnd
            else:
                return None
        else:
            _last_hwnd = hwnd

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
