import sys
from unittest.mock import patch, MagicMock


def test_returns_string_on_current_platform():
    from src.active_window import get_active_window_title
    result = get_active_window_title()
    assert isinstance(result, str)


def test_returns_empty_string_on_non_windows():
    with patch.object(sys, "platform", "linux"):
        from src.system.active_window import get_active_window_title
        result = get_active_window_title()
    assert result == ""


def test_is_ide_window_vscode():
    from src.system.active_window import is_ide_window
    assert is_ide_window("main.py - Visual Studio Code") is True


def test_is_ide_window_pycharm():
    from src.system.active_window import is_ide_window
    assert is_ide_window("my_project - PyCharm") is True


def test_is_ide_window_non_ide():
    from src.system.active_window import is_ide_window
    assert is_ide_window("Discord") is False


def test_is_ide_window_empty():
    from src.system.active_window import is_ide_window
    assert is_ide_window("") is False


def test_is_ide_window_intellij():
    from src.system.active_window import is_ide_window
    assert is_ide_window("project [main] - IntelliJ IDEA") is True


def test_is_ide_window_sublime():
    from src.system.active_window import is_ide_window
    assert is_ide_window("untitled - Sublime Text") is True


def test_returns_empty_string_on_ctypes_exception():
    import ctypes
    with patch("ctypes.windll") as mock_windll:
        mock_windll.user32.GetForegroundWindow.side_effect = Exception("no access")
        from src.active_window import get_active_window_title
        result = get_active_window_title()
    assert result == ""
