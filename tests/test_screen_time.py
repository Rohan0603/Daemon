from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch
from src.pet_window import PetWindow
from src.behavior_controller import BehaviorController
from src.events import EventType

def test_screen_time_bucketing(safe_pet_window):
    window = safe_pet_window
    window.screen_time = {}
    window.screen_time_date = "2024-01-01"
    
    with patch("src.ui.pet_window.datetime") as mock_datetime:
        mock_datetime.now.return_value.strftime.return_value = "2024-01-01"
        window._events = MagicMock()
        window._memory = MagicMock()
        window._memory.get_all.return_value = {"screen_time_warn_sec": 3600}
        
        with patch("src.active_window.get_active_window_title", return_value="Google Chrome"):
            window._update_screen_time()
        assert window.screen_time["Google Chrome"] == 10
        
        with patch("src.active_window.get_active_window_title", return_value="Some Document - VSCode"):
            window._update_screen_time()
        assert window.screen_time["VSCode"] == 10

def test_screen_time_daily_reset(safe_pet_window):
    window = safe_pet_window
    window.screen_time = {"Chrome": 500}
    window.screen_time_date = "2024-01-01"
    
    with patch("src.ui.pet_window.datetime") as mock_datetime:
        mock_datetime.now.return_value.strftime.return_value = "2024-01-02"
        # Manually trigger the reset logic that normally happens in __init__ or update
        with patch("src.active_window.get_active_window_title", return_value="Google Chrome"):
            window._update_screen_time()
        assert window.screen_time == {"Google Chrome": 10}
        assert window.screen_time_date == "2024-01-02"

def test_screen_time_threshold_event(safe_pet_window):
    window = safe_pet_window
    window.screen_time = {"Game": 3590}
    window.screen_time_date = "2024-01-01"
    
    with patch("src.ui.pet_window.datetime") as mock_datetime:
        mock_datetime.now.return_value.strftime.return_value = "2024-01-01"
        window._events = MagicMock()
        window._memory = MagicMock()
        window._memory.get_all.return_value = {"screen_time_warn_sec": 3600}
        
        with patch("src.active_window.get_active_window_title", return_value="Game"):
            window._update_screen_time()
            
        assert window.screen_time["Game"] == 3600
        
        window._events.publish.assert_called_once()
        event = window._events.publish.call_args[0][0]
        assert event.type == EventType.SCREEN_TIME_THRESHOLD_REACHED
        assert event.data["app_name"] == "Game"
        assert event.data["duration"] == 3600
