# tests/test_ollama_manager.py
import pytest
from unittest.mock import patch, MagicMock
from src.llm.ollama_manager import OllamaManager


class TestOllamaManager:
    def test_status_changed_signal(self):
        mgr = OllamaManager()
        assert hasattr(mgr, "status_changed")

    @patch("src.llm.ollama_manager.shutil.which", return_value=None)
    @patch.object(OllamaManager, "_is_ollama_running", return_value=False)
    def test_ollama_not_found(self, mock_health, mock_which):
        errors = []
        mgr = OllamaManager()
        mgr.error_occurred.connect(lambda e: errors.append(e))
        mgr.start()
        assert "ollama_not_found" in errors

    @patch("src.llm.ollama_manager.requests.get")
    def test_detects_already_running(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": []}
        mock_get.return_value = mock_resp
        statuses = []
        mgr = OllamaManager()
        mgr.status_changed.connect(lambda s: statuses.append(s))
        mgr.start()
        assert "ready" in statuses

    def test_stop_cleans_up(self):
        mgr = OllamaManager()
        mgr.stop()
