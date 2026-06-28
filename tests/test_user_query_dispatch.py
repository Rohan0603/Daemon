import pytest
from unittest.mock import MagicMock, patch
from src.pet_window import PetWindow
from PyQt6.QtWidgets import QWidget

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
        self.pw._response_manager = MagicMock()
        self.pw._response_manager.remaining.return_value = 10
        self.pw._response_manager.thought_pool = MagicMock()
        self.pw._response_manager.thought_pool._threshold = 5
        self.pw._opencode_worker = None
        self.pw.strands_worker = None
        self.pw._fire_deferred_trigger = MagicMock()
        self.pw._fsm = MagicMock()
        self.pw._fsm.current_state = "IDLE"
        self.pw._events = None
        self.pw._boredom_timer_ms = 0
        self.pw._on_brain_update = MagicMock()

    def test_on_response_ready_with_user_input(self):
        self.pw._on_response_ready([{"thought": "t", "dialogue": "d", "type": "idle_thought"}])
        self.pw._dispatch_structured.assert_called_once_with(
            {"thought": "t", "dialogue": "d", "type": "idle_thought"},
            force=True,
            user_input="hi",
        )
        assert self.pw._current_user_input == ""

    def test_on_response_ready_with_autonomous_input(self):
        self.pw._last_mode = "boredom"
        self.pw._current_user_input = ""
        self.pw._on_response_ready([{"thought": "t", "dialogue": "d", "type": "idle_thought"}])
        self.pw._dispatch_structured.assert_called_once_with(
            {"thought": "t", "dialogue": "d", "type": "idle_thought"},
            force=False,
            user_input="",
        )

    def test_on_response_ready_extracts_brain_update(self):
        items = [
            {"thought": "t", "dialogue": "d", "type": "idle_thought",
             "brain_update": {"user_habits": ["codes at night"]}},
        ]
        self.pw._on_response_ready(items)
        self.pw._on_brain_update.assert_called_once_with({"user_habits": ["codes at night"]})
        assert "brain_update" not in items[0]
        self.pw._dispatch_structured.assert_called_once()

    def test_on_response_ready_extracts_only_first_brain_update(self):
        items = [
            {"thought": "t1", "dialogue": "d1", "type": "idle_thought",
             "brain_update": {"user_habits": ["a"]}},
            {"thought": "t2", "dialogue": "d2", "type": "observation",
             "brain_update": {"pet_quirks": ["b"]}},
        ]
        self.pw._on_response_ready(items)
        self.pw._on_brain_update.assert_called_once_with({"user_habits": ["a"]})
        assert "brain_update" not in items[0]
        assert "brain_update" not in items[1]

    def test_on_response_ready_no_brain_update(self):
        items = [{"thought": "t", "dialogue": "d", "type": "idle_thought"}]
        self.pw._on_response_ready(items)
        self.pw._on_brain_update.assert_not_called()
