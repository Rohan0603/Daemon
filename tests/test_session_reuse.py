import pytest
from unittest.mock import MagicMock, patch
from src.pet_window import PetWindow
from src.pet_fsm import PetState
import threading

class TestSessionReuse:
    """Verify refill workers do NOT share the main dialog session to prevent
    concurrent request mixing."""

    @patch("src.pet_window.OpencodeWorker")
    def test_refill_worker_has_own_session(self, MockWorker):
        """When _on_refill_needed fires, the OpencodeWorker must NOT receive the
        cached _opencode_session_id — refill workers get their own session."""
        pw = MagicMock(spec=PetWindow)
        pw._opencode_session_id = "ses_abc123"
        pw._current_apm = 10
        pw._context_manager = MagicMock()
        pw._context_manager.build_mixed_bag_prompt.return_value = ("test prompt", "test prompt")
        pw._opencode_worker = None
        pw._refill_workers = {}
        pw._refill_workers_lock = threading.Lock()

        mock_worker = MagicMock()
        MockWorker.return_value = mock_worker

        PetWindow._on_refill_needed(pw)

        MockWorker.assert_called_once()
        call_kwargs = MockWorker.call_args[1]
        assert call_kwargs.get("session_id") is None, \
            f"Expected session_id=None (own session), got {call_kwargs.get('session_id')}"