import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QWidget
from src.pet_window import PetWindow
from src.pet_fsm import PetState

pytestmark = pytest.mark.usefixtures("app")

class TestUserQueryDispatch:
    def setup_method(self):
        def mock_init(self, *a, **kw):
            QWidget.__init__(self)
        with patch.object(PetWindow, '__init__', mock_init):
            self.pw = PetWindow()
            self.pw._last_mode = "user_input"
            self.pw._current_user_input = "hi"
            self.pw._dispatch_structured = MagicMock()
            
            # Setup response manager mock with threshold and remaining values
            self.pw._response_manager = MagicMock()
            self.pw._response_manager.remaining.return_value = 10
            self.pw._response_manager.thought_pool = MagicMock()
            self.pw._response_manager.thought_pool._threshold = 5
            
            self.pw._opencode_worker = MagicMock()
            self.pw._fire_deferred_trigger = MagicMock()

    def test_on_response_ready_with_user_input(self):
        items = [{"thought": "t", "dialogue": "d", "type": "idle_thought"}]
        self.pw._on_response_ready(items)
        
        # Verify that _dispatch_structured is called with force=True and user_input="hi"
        self.pw._dispatch_structured.assert_called_once_with(items[0], force=True, user_input="hi")
        # Verify that current user input is cleared
        assert self.pw._current_user_input == ""

    def test_on_response_ready_with_autonomous_input(self):
        self.pw._last_mode = "boredom"
        self.pw._current_user_input = ""
        items = [{"thought": "t", "dialogue": "d", "type": "idle_thought"}]
        self.pw._on_response_ready(items)
        
        # Verify that _dispatch_structured is called with force=False and user_input=""
        self.pw._dispatch_structured.assert_called_once_with(items[0], force=False, user_input="")
