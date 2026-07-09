# tests/test_ollama_worker.py
import pytest
from unittest.mock import patch, MagicMock
from src.llm.ollama_worker import OllamaWorker

class TestOllamaWorker:
    @patch("src.llm.ollama_worker.requests.post")
    def test_response_ready_emitted_on_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"role": "assistant", "content": '[{"dialogue": "hello", "thought": "hi", "type": "observation", "priority": 3}]'}
        }
        mock_post.return_value = mock_resp

        results = []
        worker = OllamaWorker(prompt="test prompt", pet_id="kenny")
        worker.response_ready.connect(lambda items: results.append(items))
        worker.run()
        assert len(results) == 1
        assert results[0][0]["dialogue"] == "hello"

    def test_tool_call_requested_signal(self):
        worker = OllamaWorker(prompt="test", pet_id="kenny")
        assert hasattr(worker, "tool_call_requested")
