# tests/test_screen_reader.py
from __future__ import annotations
import sys
from unittest.mock import patch, MagicMock


def test_returns_empty_on_non_windows():
    with patch.object(sys, "platform", "linux"):
        from src.screen_reader import ScreenReader
        result = ScreenReader.get_foreground_text()
        assert result == ""


def test_returns_empty_when_both_methods_fail():
    with patch("src.screen_reader.get_text_via_uia", return_value=""):
        with patch("src.screen_reader.get_text_via_wm_gettext", return_value=""):
            from src.screen_reader import ScreenReader
            result = ScreenReader.get_foreground_text()
            assert result == ""


def test_returns_empty_when_no_foreground_window():
    with patch.object(sys, "platform", "win32"):
        with patch("src.screen_reader.get_text_via_uia", return_value=""):
            with patch("src.screen_reader.get_text_via_wm_gettext", return_value=""):
                from src.screen_reader import ScreenReader
                result = ScreenReader.get_foreground_text()
                assert result == ""


def test_uia_returns_text():
    with patch.object(sys, "platform", "win32"):
        with patch("src.screen_reader.get_text_via_uia", return_value="Hello world"):
            from src.screen_reader import ScreenReader
            result = ScreenReader.get_foreground_text()
            assert result == "Hello world"


def test_wm_gettext_fallback():
    with patch.object(sys, "platform", "win32"):
        with patch("src.screen_reader.get_text_via_uia", return_value=""):
            with patch("src.screen_reader.get_text_via_wm_gettext", return_value="Fallback text"):
                from src.screen_reader import ScreenReader
                result = ScreenReader.get_foreground_text()
                assert result == "Fallback text"


def test_caps_at_2000_chars():
    long_text = "a" * 3000
    with patch.object(sys, "platform", "win32"):
        with patch("src.screen_reader.get_text_via_uia", return_value=long_text):
            from src.screen_reader import ScreenReader
            result = ScreenReader.get_foreground_text()
            assert len(result) <= 2000
            assert result == "a" * 2000
