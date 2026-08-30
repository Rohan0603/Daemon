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

    @patch("src.llm.ollama_manager.requests.get")
    def test_readiness_uses_configured_server_and_validates_tags(self, mock_get):
        response = MagicMock(status_code=200)
        response.json.return_value = {"models": []}
        mock_get.return_value = response
        mgr = OllamaManager(ollama_url="http://localhost:9999/")
        assert mgr._is_ollama_running() is True
        mock_get.assert_called_once_with("http://localhost:9999/api/tags", timeout=3)

    @patch("src.llm.ollama_manager.requests.post")
    def test_warm_model_classifies_oom(self, mock_post):
        response = MagicMock(status_code=500, text="CUDA out of memory")
        mock_post.return_value = response
        errors = []
        mgr = OllamaManager()
        mgr.error_occurred.connect(errors.append)
        mgr._warm_model()
        assert errors == ["ollama_oom"]
