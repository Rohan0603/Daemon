# tests/test_screen_reader_cache.py
from __future__ import annotations
from unittest.mock import patch, MagicMock
import sys


def test_prefetch_stores_text():
    """Test that prefetch_uia stores text in cache."""
    from src.system.screen_reader import (
        prefetch_uia,
        get_cached_uia,
        clear_uia_cache,
        get_text_via_uia,
        get_text_via_wm_gettext,
    )

    clear_uia_cache()
    with patch.object(sys, "platform", "win32"):
        with patch("src.system.screen_reader.get_text_via_uia", return_value="Hello UIA"):
            prefetch_uia()
            cached = get_cached_uia()
            assert cached == "Hello UIA"


def test_cached_returns_within_ttl():
    """Test that get_cached_uia returns cached text within TTL."""
    from src.system.screen_reader import (
        prefetch_uia,
        get_cached_uia,
        clear_uia_cache,
        _CACHE_TTL_SECONDS,
    )

    clear_uia_cache()
    
    with patch.object(sys, "platform", "win32"):
        with patch("src.system.screen_reader.time.time", return_value=1000.0):
            with patch("src.system.screen_reader.get_text_via_uia", return_value="Test Text"):
                prefetch_uia()
            cached = get_cached_uia()
            assert cached == "Test Text"


def test_cache_expires_after_ttl():
    """Test that get_cached_uia returns None when cache expires."""
    from src.system.screen_reader import (
        prefetch_uia,
        get_cached_uia,
        clear_uia_cache,
        _CACHE_TTL_SECONDS,
    )

    clear_uia_cache()
    with patch.object(sys, "platform", "win32"):
        with patch("src.system.screen_reader.time.time", return_value=1000.0):
            with patch("src.system.screen_reader.get_text_via_uia", return_value="Expiring Text"):
                prefetch_uia()
    
    with patch("src.system.screen_reader.time.time", return_value=1000.0 + _CACHE_TTL_SECONDS + 1.0):
        cached = get_cached_uia()
        assert cached is None


def test_cache_returned_via_get_foreground_text_delta():
    """Test that get_foreground_text_delta returns cached text when fresh."""
    from src.system.screen_reader import (
        prefetch_uia,
        get_foreground_text_delta,
        clear_uia_cache,
        clear_screen_cache,
    )

    clear_uia_cache()
    clear_screen_cache()
    with patch.object(sys, "platform", "win32"):
        with patch("src.system.screen_reader.time.time", return_value=1000.0):
            with patch("src.system.screen_reader.get_text_via_uia", return_value="Cached Delta"):
                prefetch_uia()
            result = get_foreground_text_delta()
            assert result == "Cached Delta"


def test_cache_expires_then_refetches():
    """Test that after cache expires, fresh text is retrieved."""
    from src.system.screen_reader import (
        prefetch_uia,
        get_foreground_text_delta,
        clear_uia_cache,
        clear_screen_cache,
        _CACHE_TTL_SECONDS,
    )

    clear_uia_cache()
    clear_screen_cache()

    # First fetch
    with patch.object(sys, "platform", "win32"):
        with patch("src.system.screen_reader.time.time", return_value=1000.0):
            with patch("src.system.screen_reader.get_text_via_uia", return_value="First"):
                prefetch_uia()
            result1 = get_foreground_text_delta()
            assert result1 == "First"

    # Clear cache and verify fresh fetch
    clear_uia_cache()
    with patch.object(sys, "platform", "win32"):
        with patch("src.system.screen_reader.time.time", return_value=1000.0):
            with patch("src.system.screen_reader.get_text_via_uia", return_value="New"):
                result2 = get_foreground_text_delta()
                assert result2 == "New"