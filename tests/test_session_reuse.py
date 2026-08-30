import pytest
from unittest.mock import MagicMock, patch
from src.pet_window import PetWindow
from src.pet_fsm import PetState
import threading
from src.llm.opencode_session_manager import OpenCodeSessionManager

class TestSessionReuse:
    """Verify refill workers do NOT share the main dialog session to prevent
    concurrent request mixing."""

    def test_refill_worker_has_own_session(self):
        """When _on_refill_needed fires, the refill worker must NOT receive the
        cached _opencode_session_id — refill workers get their own session."""
        pw = MagicMock(spec=PetWindow)
        pw._opencode_session_id = "ses_abc123"
        pw._current_apm = 10
        pw._context_manager = MagicMock()
        pw._context_manager.build_mixed_bag_prompt.return_value = ("test prompt", "test prompt")
        pw._opencode_worker = None
        pw._refill_workers = {}
        pw._refill_workers_lock = threading.Lock()
        pw._llm_provider = "opencode"

        pw._make_llm_worker = MagicMock(return_value=MagicMock())

        PetWindow._on_refill_needed(pw)

        pw._make_llm_worker.assert_called_once()
        call_kwargs = pw._make_llm_worker.call_args[1]
        assert call_kwargs.get("session_id") is None, \
            f"Expected session_id=None (own session), got {call_kwargs.get('session_id')}"

    @patch("src.llm.opencode_session_manager.requests")
    def test_manager_reuses_session_until_turn_bound(self, requests_mock):
        requests_mock.post.return_value.status_code = 200
        requests_mock.post.return_value.json.return_value = {"id": "ses_1"}
        requests_mock.get.return_value.status_code = 200
        manager = OpenCodeSessionManager(enabled=True, max_turns=2)

        assert manager.acquire() == "ses_1"
        assert manager.acquire() == "ses_1"
        assert manager.turns == 2
        assert manager.acquire() == "ses_1"
        assert requests_mock.post.call_count == 2
        assert requests_mock.delete.call_count == 1

    @patch("src.llm.opencode_session_manager.requests")
    def test_manager_resets_on_unhealthy_session_and_closes(self, requests_mock):
        requests_mock.post.return_value.status_code = 200
        requests_mock.post.return_value.json.return_value = {"id": "ses_1"}
        requests_mock.get.return_value.status_code = 500
        manager = OpenCodeSessionManager(enabled=True)

        assert manager.acquire() == "ses_1"
        assert manager.acquire() == "ses_1"
        assert requests_mock.delete.call_count == 1
        manager.close()
        assert requests_mock.delete.call_count == 2

    @patch("src.llm.opencode_session_manager.requests")
    def test_manager_expires_idle_session(self, requests_mock):
        requests_mock.post.return_value.status_code = 200
        requests_mock.post.return_value.json.return_value = {"id": "ses_1"}
        manager = OpenCodeSessionManager(enabled=True, idle_expiry_seconds=1)

        assert manager.acquire() == "ses_1"
        manager._last_used -= 2
        assert manager.acquire() == "ses_1"
        assert requests_mock.delete.call_count == 1
