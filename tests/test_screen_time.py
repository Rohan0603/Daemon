from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch
from src.pet_window import PetWindow
from src.behavior_controller import BehaviorController
from src.events import EventType

def test_screen_time_bucketing(qapp, tmp_path):
    # Setup initial state
    initial_state = {"screen_time": {}, "screen_time_date": "2024-01-01"}
    
    with patch("src.config.load_config", return_value={}), \
         patch("src.ui.pet_window.get_event_bus") as mock_bus, \
         patch("src.ui.pet_window.datetime") as mock_datetime:
         
        mock_datetime.now.return_value.strftime.return_value = "2024-01-01"
        
        # We'll mock the internal components so PetWindow doesn't crash
        with patch("src.ui.pet_window.Memory"), \
             patch("src.ui.pet_window.History"), \
             patch("src.ui.pet_window.DiaryStore"), \
             patch("src.ui.pet_window.MCPServer"), \
             patch("src.ui.pet_window.AutonomousResponseManager"), \
             patch("src.ui.pet_window.WriteCoalescer"), \
             patch("src.ui.pet_window.BehaviorController"):
             
            window = PetWindow(initial_state=initial_state)
            
            # Manually mock events and active window
            window._events = MagicMock()
            window._memory = MagicMock()
            window._memory.get_all.return_value = {"screen_time_warn_sec": 3600}
            
            # Simulate active window change
            with patch("src.active_window.get_active_window_title", return_value="Google Chrome"):
                window._update_screen_time()
                
            assert window.screen_time["Google Chrome"] == 10
            
            with patch("src.active_window.get_active_window_title", return_value="Some Document - VSCode"):
                window._update_screen_time()
                
            assert window.screen_time["VSCode"] == 10

def test_screen_time_daily_reset(qapp, tmp_path):
    initial_state = {"screen_time": {"Chrome": 500}, "screen_time_date": "2024-01-01"}
    
    with patch("src.config.load_config", return_value={}), \
         patch("src.ui.pet_window.get_event_bus") as mock_bus, \
         patch("src.ui.pet_window.datetime") as mock_datetime:
         
        # Simulate a new day
        mock_datetime.now.return_value.strftime.return_value = "2024-01-02"
        
        with patch("src.ui.pet_window.Memory"), \
             patch("src.ui.pet_window.History"), \
             patch("src.ui.pet_window.DiaryStore"), \
             patch("src.ui.pet_window.MCPServer"), \
             patch("src.ui.pet_window.AutonomousResponseManager"), \
             patch("src.ui.pet_window.WriteCoalescer"), \
             patch("src.ui.pet_window.BehaviorController"):
             
            window = PetWindow(initial_state=initial_state)
            
            # The reset should have happened in __init__
            assert window.screen_time == {}
            assert window.screen_time_date == "2024-01-02"

def test_screen_time_threshold_event(qapp, tmp_path):
    initial_state = {"screen_time": {"Game": 3590}, "screen_time_date": "2024-01-01"}
    
    with patch("src.config.load_config", return_value={}), \
         patch("src.ui.pet_window.get_event_bus") as mock_bus, \
         patch("src.ui.pet_window.datetime") as mock_datetime:
         
        mock_datetime.now.return_value.strftime.return_value = "2024-01-01"
        
        with patch("src.ui.pet_window.Memory"), \
             patch("src.ui.pet_window.History"), \
             patch("src.ui.pet_window.DiaryStore"), \
             patch("src.ui.pet_window.MCPServer"), \
             patch("src.ui.pet_window.AutonomousResponseManager"), \
             patch("src.ui.pet_window.WriteCoalescer"), \
             patch("src.ui.pet_window.BehaviorController"):
             
            window = PetWindow(initial_state=initial_state)
            
            window._events = MagicMock()
            window._memory = MagicMock()
            window._memory.get_all.return_value = {"screen_time_warn_sec": 3600}
            
            # This should bump "Game" to 3600
            with patch("src.active_window.get_active_window_title", return_value="Game"):
                window._update_screen_time()
                
            assert window.screen_time["Game"] == 3600
            
            # Verify event was published
            window._events.publish.assert_called_once()
            event = window._events.publish.call_args[0][0]
            assert event.type == EventType.SCREEN_TIME_THRESHOLD_REACHED
            assert event.data["app_name"] == "Game"
            assert event.data["duration"] == 3600
