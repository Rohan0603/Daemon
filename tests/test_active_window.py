import sys
from unittest.mock import patch, MagicMock


def test_returns_string_on_current_platform():
    from src.active_window import get_active_window_title
    result = get_active_window_title()
    assert isinstance(result, str)


def test_returns_empty_string_on_non_windows():
    import importlib
    import src.active_window
    with patch.object(src.active_window.sys, "platform", "linux"):
        result = src.active_window.get_active_window_title()
    assert result == ""


def test_returns_empty_string_on_ctypes_exception():
    import src.active_window
    if sys.platform != "win32":
        return
    import ctypes
    with patch("ctypes.windll") as mock_windll:
        mock_windll.user32.GetForegroundWindow.side_effect = Exception("no access")
        result = src.active_window.get_active_window_title()
    assert result == ""


def test_get_window_rect_returns_tuple_or_none():
    from src.active_window import get_window_rect
    result = get_window_rect()
    assert result is None or (isinstance(result, tuple) and len(result) == 4)
