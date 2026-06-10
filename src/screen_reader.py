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

_UIA_AUTOMATION = None
_UIA_INITIALIZED = False


def _get_uia_automation():
    """Lazy initialization of IUIAutomation singleton."""
    global _UIA_AUTOMATION, _UIA_INITIALIZED
    if not _UIA_AVAILABLE:
        return None
    if _UIA_AUTOMATION is not None:
        return _UIA_AUTOMATION

    try:
        import ctypes
        from comtypes.client import CreateObject, GetModule
        import comtypes

        # Initialize COM only once per thread
        if not _UIA_INITIALIZED:
            comtypes.CoInitialize()
            _UIA_INITIALIZED = True

        # Load typelib once
        GetModule("UIAutomationCore.dll")
        from comtypes.gen.UIAutomationClient import IUIAutomation

        clsid = "{ff48dba4-60ef-4201-aa87-54103eef594e}"
        _UIA_AUTOMATION = CreateObject(clsid, interface=IUIAutomation)
        logger.info("UIA automation initialized successfully")
        return _UIA_AUTOMATION
    except Exception as e:
        logger.warning("UIA initialization failed: %s", e)
        return None


def get_text_via_uia() -> str:
    automation = _get_uia_automation()
    if not automation:
        return ""
    try:
        import ctypes

        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return ""

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
        return text.strip()[:2000]
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


def _cleanup_uia():
    """Clean up COM on shutdown."""
    global _UIA_AUTOMATION, _UIA_INITIALIZED
    _UIA_AUTOMATION = None
    _UIA_INITIALIZED = False
    try:
        import comtypes
        comtypes.CoUninitialize()
    except Exception:
        pass


class ScreenReader:
    @staticmethod
    def get_foreground_text() -> str:
        if sys.platform != "win32":
            return ""
        text = get_text_via_uia()
        if text:
            return text[:2000]
        return get_text_via_wm_gettext()[:2000]
