"""Tests for _has_significant_delta context switch detection."""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from src.pet_window import PetWindow


class TestDeltaDetection:
    def setup_method(self):
        with patch.object(PetWindow, '__init__', lambda self, *a, **kw: None):
            self.pw = PetWindow.__new__(PetWindow)
            self.pw._last_active_window = ""
            self.pw._last_typing_snapshot = ""
            self.pw._typing_buffer = MagicMock()
            self.pw._typing_buffer.get_context.return_value = ""

    @patch('src.pet_window.get_active_window_title')
    def test_no_change_returns_false(self, mock_window):
        mock_window.return_value = " same "
        self.pw._last_active_window = " same "
        assert self.pw._has_significant_delta() is False

    @patch('src.pet_window.get_active_window_title')
    def test_window_change_returns_true(self, mock_window):
        mock_window.return_value = "NewWindow"
        self.pw._last_active_window = "OldWindow"
        assert self.pw._has_significant_delta() is True

    @patch('src.pet_window.get_active_window_title')
    def test_typing_burst_returns_true(self, mock_window):
        mock_window.return_value = ""
        self.pw._typing_buffer.get_context.return_value = "x" * 30
        self.pw._last_typing_snapshot = ""
        assert self.pw._has_significant_delta() is True

    @patch('src.pet_window.get_active_window_title')
    def test_small_typing_no_burst(self, mock_window):
        mock_window.return_value = ""
        self.pw._typing_buffer.get_context.return_value = "x" * 5
        self.pw._last_typing_snapshot = "x" * 3
        assert self.pw._has_significant_delta() is False
