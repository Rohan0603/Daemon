# src/screen_reader.py
from __future__ import annotations
import logging
import sys

logger = logging.getLogger(__name__)

_UIA_AVAILABLE = False
try:
    import comtypes.client
    _UIA_AVAILABLE = True
except ImportError:
    pass


def get_text_via_uia() -> str:
    if not _UIA_AVAILABLE:
        return ""
    try:
        import ctypes
        from comtypes.client import CreateObject
        import comtypes

        comtypes.CoInitialize()
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return ""

        clsid = "{ff48dba4-60ef-4201-aa87-54103eef594e}"
        automation = CreateObject(clsid)
        element = automation.ElementFromHandle(hwnd)
        if not element:
            return ""

        pattern = element.GetCurrentPattern(10014)
        if not pattern:
            return ""

        text_range = pattern.DocumentRange
        if not text_range:
            return ""

        text = text_range.GetText(-1) or ""
        text = text.strip()
        return text[:2000]
    except Exception as e:
        logger.debug("get_text_via_uia failed: %s", e)
        return ""


def get_text_via_wm_gettext() -> str:
    try:
        import ctypes
        import ctypes.wintypes

        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return ""
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        text = buf.value.strip()
        return text[:2000]
    except Exception as e:
        logger.debug("get_text_via_wm_gettext failed: %s", e)
        return ""


class ScreenReader:
    @staticmethod
    def get_foreground_text() -> str:
        if sys.platform != "win32":
            return ""
        text = get_text_via_uia()
        if text:
            return text[:2000]
        return get_text_via_wm_gettext()[:2000]
