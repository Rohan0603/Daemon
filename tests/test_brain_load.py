from unittest.mock import MagicMock, patch
from src.memory_manager import MemoryManager


class TestBrainLoadDedup:
    """Verify sync_to_local uses cached brain data instead of re-fetching."""

    def test_sync_to_local_uses_cached_brain(self):
        """sync_to_local fetches user context but not brain when brain is passed in."""
        crud = MagicMock()
        crud.get.return_value = {"name": "Kenny", "personality": "chaotic"}
        crud.available = True
        mm = MemoryManager(crud, "test_uid")

        mock_memory = MagicMock()
        mock_memory.remember = MagicMock()

        brain_data = {"user_habits": ["codes at night", "drinks coffee"], "pet_likes": ["python", "testing"]}
        mm.sync_to_local(mock_memory, brain=brain_data)

        # Should fetch shared user context but NOT re-fetch brain
        crud.get.assert_called_once_with("users", "test_uid")
        assert mock_memory.remember.call_count == 2