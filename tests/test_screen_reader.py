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


def test_browser_url_found_via_edit_condition():
    from src.system.screen_reader import get_browser_url_via_uia
    mock_automation = MagicMock()
    mock_element = MagicMock()
    mock_edit = MagicMock()
    mock_value = MagicMock()
    mock_value.CurrentValue = "https://github.com/user/repo"
    mock_edit.GetCurrentPattern.return_value = mock_value
    mock_element.FindFirst.return_value = mock_edit
    mock_automation.ElementFromHandle.return_value = mock_element
    with patch("src.system.screen_reader._get_uia_automation", return_value=mock_automation):
        result = get_browser_url_via_uia()
    assert result == "https://github.com/user/repo"


def test_browser_url_empty_when_uia_unavailable():
    from src.system.screen_reader import get_browser_url_via_uia
    with patch("src.system.screen_reader._get_uia_automation", return_value=None):
        result = get_browser_url_via_uia()
    assert result == ""


def test_browser_url_fallback_to_walker():
    from src.system.screen_reader import get_browser_url_via_uia
    mock_automation = MagicMock()
    mock_element = MagicMock()
    mock_walker = MagicMock()
    mock_child = MagicMock()
    mock_value = MagicMock()
    mock_value.CurrentValue = "https://example.com/page"
    mock_child.GetCurrentPattern.return_value = mock_value
    mock_element.FindFirst.return_value = None
    mock_automation.ElementFromHandle.return_value = mock_element
    mock_automation.CreateTreeWalker.return_value = mock_walker
    mock_walker.GetFirstChildElement.return_value = mock_child
    mock_walker.GetNextSiblingElement.return_value = None
    with patch("src.system.screen_reader._get_uia_automation", return_value=mock_automation):
        result = get_browser_url_via_uia()
    assert result == "https://example.com/page"


def test_browser_url_skips_non_url_values():
    from src.system.screen_reader import get_browser_url_via_uia
    mock_automation = MagicMock()
    mock_element = MagicMock()
    mock_edit = MagicMock()
    mock_value = MagicMock()
    mock_walker = MagicMock()
    mock_value.CurrentValue = "Search or enter address"
    mock_edit.GetCurrentPattern.return_value = mock_value
    mock_element.FindFirst.return_value = mock_edit
    mock_automation.ElementFromHandle.return_value = mock_element
    mock_automation.CreateTreeWalker.return_value = mock_walker
    mock_walker.GetFirstChildElement.return_value = None
    with patch("src.system.screen_reader._get_uia_automation", return_value=mock_automation):
        result = get_browser_url_via_uia()
    assert result == ""


def test_browser_url_empty_when_no_value_pattern():
    from src.system.screen_reader import get_browser_url_via_uia
    mock_automation = MagicMock()
    mock_element = MagicMock()
    mock_edit = MagicMock()
    mock_walker = MagicMock()
    mock_edit.GetCurrentPattern.side_effect = Exception("No pattern")
    mock_element.FindFirst.return_value = mock_edit
    mock_automation.ElementFromHandle.return_value = mock_element
    mock_automation.CreateTreeWalker.return_value = mock_walker
    mock_walker.GetFirstChildElement.return_value = None
    with patch("src.system.screen_reader._get_uia_automation", return_value=mock_automation):
        result = get_browser_url_via_uia()
    assert result == ""


def test_url_prepended_to_screen_text():
    from src.screen_reader import get_foreground_text_delta, clear_screen_cache
    clear_screen_cache()
    with patch("src.system.screen_reader.get_text_via_uia", return_value="Page content here") as _:
        with patch("src.system.screen_reader.get_browser_url_via_uia", return_value="https://example.com"):
            result = get_foreground_text_delta()
    assert result == "[URL: https://example.com] Page content here"


def test_url_alone_when_no_screen_text():
    from src.screen_reader import get_foreground_text_delta, clear_screen_cache
    clear_screen_cache()
    with patch("src.system.screen_reader.get_text_via_uia", return_value=""):
        with patch("src.system.screen_reader.get_text_via_wm_gettext", return_value=""):
            with patch("src.system.screen_reader.get_browser_url_via_uia", return_value="https://example.com"):
                result = get_foreground_text_delta()
    assert result == "[URL: https://example.com]"


def test_url_changes_hash_and_invalidates_cache():
    from src.screen_reader import get_foreground_text_delta, clear_screen_cache
    clear_screen_cache()
    with patch("src.system.screen_reader.get_text_via_uia", return_value="Same page"):
        with patch("src.system.screen_reader.get_browser_url_via_uia", return_value="https://page1.com"):
            first = get_foreground_text_delta()
        with patch("src.system.screen_reader.get_browser_url_via_uia", return_value="https://page2.com"):
            second = get_foreground_text_delta()
    assert first == "[URL: https://page1.com] Same page"
    assert second == "[URL: https://page2.com] Same page"
