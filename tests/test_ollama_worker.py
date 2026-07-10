# tests/test_ollama_worker.py
import unittest

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

    @patch("src.llm.ollama_worker.requests.post")
    def test_handles_tool_calls_and_returns_content(self, mock_post):
        mock_resp1 = MagicMock()
        mock_resp1.status_code = 200
        mock_resp1.json.return_value = {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "function": {"name": "change_visual_state", "arguments": {"action": "shake"}}
                }]
            }
        }
        mock_resp2 = MagicMock()
        mock_resp2.status_code = 200
        mock_resp2.json.return_value = {
            "message": {
                "role": "assistant",
                "content": '[{"dialogue": "done", "thought": "ok", "type": "observation", "priority": 3}]'
            }
        }
        mock_post.side_effect = [mock_resp1, mock_resp2]

        results = []
        worker = OllamaWorker(prompt="test", pet_id="kenny")
        worker.response_ready.connect(lambda items: results.append(items))
        worker.run()
        assert len(results) == 1
        assert results[0][0]["dialogue"] == "done"

    @patch("src.llm.ollama_worker.requests.post")
    def test_http_error_emits_error(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_post.return_value = mock_resp

        errors = []
        worker = OllamaWorker(prompt="test", pet_id="kenny")
        worker.error_occurred.connect(lambda e: errors.append(e))
        worker.run()
        assert any("parse_failed" in e for e in errors)

    @patch("src.llm.ollama_worker.requests.post")
    def test_abort_stops_execution(self, mock_post):
        worker = OllamaWorker(prompt="test", pet_id="kenny")
        worker.abort()
        worker.run()
        mock_post.assert_not_called()

    def test_parse_garbage_falls_back_to_freeform(self):
        worker = OllamaWorker(prompt="test", pet_id="kenny")
        result = worker._parse_response("   some free form text   ")
        assert result is not None
        assert result[0]["dialogue"] == "some free form text"
        assert result[0]["type"] == "observation"

    @patch("src.llm.ollama_worker.requests.post")
    def test_read_clipboard_signal(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "function": {"name": "read_clipboard", "arguments": {}}
                }]
            }
        }
        mock_resp2 = MagicMock()
        mock_resp2.status_code = 200
        mock_resp2.json.return_value = {
            "message": {
                "role": "assistant",
                "content": '[{"dialogue": "ok", "thought": "", "type": "observation", "priority": 3}]'
            }
        }
        mock_post.side_effect = [mock_resp, mock_resp2]

        signals = []
        worker = OllamaWorker(prompt="test", pet_id="kenny")
        worker.read_clipboard_requested.connect(lambda: signals.append("read"))
        worker.run()
        assert "read" in signals

    def test_normalize_item_variants(self):
        worker = OllamaWorker(prompt="test", pet_id="kenny")
        
        # Test 1: Chat message format (list of dicts)
        item1 = {
            "dialogue": [
                {"speaker": "You", "content": "hello"},
                {"speaker": "Me", "content": "how can I help?"}
            ],
            "action": ["spin"],
            "type": "observation"
        }
        res1 = worker._normalize_item(item1)
        assert res1["dialogue"] == "how can I help?"
        assert res1["action"] == "spin"
        assert res1["type"] == "observation"

        # Test 2: Standard dictionary format
        item2 = {
            "dialogue": "simple response",
            "action": "celebrate",
            "brain_update": {"user_nickname": "new name"}
        }
        res2 = worker._normalize_item(item2)
        assert res2["dialogue"] == "simple response"
        assert res2["action"] == "celebrate"
        assert res2["brain_update"] == {"user_nickname": "new name"}

    def test_variable_substitutions(self):
        from pathlib import Path
        # Mock parent and memory
        mock_parent = MagicMock()
        mock_memory = MagicMock()
        mock_memory.get_all.return_value = {
            "user_nickname": "test_nick",
            "user_partner_name": "test_partner",
            "user_engineer_name": "test_engineer"
        }
        mock_parent._memory = mock_memory
        
        worker = OllamaWorker(prompt="test", pet_id="kenny")
        worker.parent = MagicMock(return_value=mock_parent)
        
        # Verify custom system prompt loader substitutes variables correctly
        with patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "read_text", return_value="## Identity & Obsession\nIdentity: {user_nickname} deployed by {user_partner_name} for {user_engineer_name}\n## Phonetics & Delivery (CRITICAL - TTS reads verbatim)"):
            skill_md = worker._load_skill_md()
            assert "test_nick" in skill_md
            assert "test_partner" in skill_md
            assert "test_engineer" in skill_md
            assert "{user_nickname}" not in skill_md
            assert "Phonetics & Delivery" not in skill_md


class TestGarbageFilterNickname(unittest.TestCase):
    def test_blacklisted_literal_now_kept(self):
        worker = OllamaWorker(prompt="hi", pet_id="kenny")
        items = [{"dialogue": "garbage meat", "thought": "finally talked to me"}]
        self.assertTrue(worker._filter_garbage_items(items))
        self.assertEqual(len(items), 1)

    def test_pure_punctuation_still_dropped(self):
        worker = OllamaWorker(prompt="hi", pet_id="kenny")
        items = [{"dialogue": "...", "thought": "x"}]
        self.assertFalse(worker._filter_garbage_items(items))


