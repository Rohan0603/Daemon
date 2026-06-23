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
    with patch("src.system.screen_reader.get_text_via_uia", return_value=""):
        with patch("src.system.screen_reader.get_text_via_wm_gettext", return_value=""):
            from src.screen_reader import ScreenReader
            result = ScreenReader.get_foreground_text()
            assert result == ""


def test_returns_empty_when_no_foreground_window():
    with patch.object(sys, "platform", "win32"):
        with patch("src.system.screen_reader.get_text_via_uia", return_value=""):
            with patch("src.system.screen_reader.get_text_via_wm_gettext", return_value=""):
                from src.screen_reader import ScreenReader
                result = ScreenReader.get_foreground_text()
                assert result == ""


def test_uia_returns_text():
    with patch.object(sys, "platform", "win32"):
        with patch("src.system.screen_reader.get_text_via_uia", return_value="Hello world"):
            from src.screen_reader import ScreenReader
            result = ScreenReader.get_foreground_text()
            assert result == "Hello world"


def test_wm_gettext_fallback():
    with patch.object(sys, "platform", "win32"):
        with patch("src.system.screen_reader.get_text_via_uia", return_value=""):
            with patch("src.system.screen_reader.get_text_via_wm_gettext", return_value="Fallback text"):
                from src.screen_reader import ScreenReader
                result = ScreenReader.get_foreground_text()
                assert result == "Fallback text"


def test_caps_at_2000_chars():
    long_text = "a" * 3000
    with patch.object(sys, "platform", "win32"):
        with patch("src.system.screen_reader.get_text_via_uia", return_value=long_text):
            from src.screen_reader import ScreenReader
            result = ScreenReader.get_foreground_text()
            assert len(result) <= 2000
            assert result == "a" * 2000


def test_delta_returns_text_on_first_call():
    from src.screen_reader import get_foreground_text_delta
    with patch("src.system.screen_reader.get_text_via_uia", return_value="Window Content"):
        result = get_foreground_text_delta()
    assert result == "Window Content"


def test_delta_returns_unchanged_on_repeat():
    from src.screen_reader import get_foreground_text_delta, clear_screen_cache
    clear_screen_cache()
    with patch("src.system.screen_reader.get_text_via_uia", return_value="Same Content"):
        first = get_foreground_text_delta()
        second = get_foreground_text_delta()
    assert first == "Same Content"
    assert second == "[Screen unchanged]"


def test_delta_returns_new_text_after_change():
    from src.screen_reader import get_foreground_text_delta, clear_screen_cache
    clear_screen_cache()
    with patch("src.system.screen_reader.get_text_via_uia", return_value="Old Content"):
        get_foreground_text_delta()
    with patch("src.system.screen_reader.get_text_via_uia", return_value="New Content"):
        result = get_foreground_text_delta()
    assert result == "New Content"


def test_delta_returns_new_text_after_clear():
    from src.screen_reader import get_foreground_text_delta, clear_screen_cache
    clear_screen_cache()
    with patch("src.system.screen_reader.get_text_via_uia", return_value="Cached"):
        get_foreground_text_delta()
    clear_screen_cache()
    with patch("src.system.screen_reader.get_text_via_uia", return_value="Fresh"):
        result = get_foreground_text_delta()
    assert result == "Fresh"


def test_delta_uses_uia_fallback_and_hashes():
    from src.screen_reader import get_foreground_text_delta, clear_screen_cache
    clear_screen_cache()
    with patch("src.system.screen_reader.get_text_via_uia", return_value=""), \
         patch("src.system.screen_reader.get_text_via_wm_gettext", return_value="Fallback"):
        first = get_foreground_text_delta()
        second = get_foreground_text_delta()
    assert first == "Fallback"
    assert second == "[Screen unchanged]"
