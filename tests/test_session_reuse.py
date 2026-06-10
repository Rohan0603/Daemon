import pytest
from unittest.mock import MagicMock, patch
from src.pet_window import PetWindow
from src.pet_fsm import PetState


class TestSessionReuse:
    """Verify pool refill workers receive the cached session_id."""

    @patch("src.pet_window.OpencodeWorker")
    def test_refill_worker_receives_session_id(self, MockWorker):
        """When _on_refill_needed fires, the OpencodeWorker must receive the
        cached _opencode_session_id so it reuses the existing session."""
        pw = MagicMock(spec=PetWindow)
        pw._opencode_session_id = "ses_abc123"
        pw._current_apm = 10
        pw._context_manager = MagicMock()
        pw._context_manager.build_pool_refill_prompt.return_value = "test prompt"
        pw._refill_workers = {}

        mock_worker = MagicMock()
        MockWorker.return_value = mock_worker

        PetWindow._on_refill_needed(pw, "jokes_blackmail")

        MockWorker.assert_called_once()
        call_kwargs = MockWorker.call_args
        assert call_kwargs[1].get("session_id") == "ses_abc123", \
            f"Expected session_id='ses_abc123', got {call_kwargs[1].get('session_id')}"