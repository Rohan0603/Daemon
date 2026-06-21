import pytest
from unittest.mock import MagicMock, patch
from src.strands_worker import StrandsAutonomousWorker

def test_strands_worker_initialization(qapp):
    context = {"active_window": "python", "apm": 10}
    chat_history = [{"role": "user", "content": "hi"}]
    
    worker = StrandsAutonomousWorker(context, chat_history, profanity_level="moderate")
    
    # Check that model configuration is correct
    assert worker.model.config.get("model_id") == "opencode-default"
    assert worker.model.client_args.get("api_key") == "opencode-local"
    assert worker.model.client_args.get("base_url") == "http://127.0.0.1:4096/v1"

def test_clean_and_parse_json():
    context = {"active_window": "python", "apm": 10}
    chat_history = []
    worker = StrandsAutonomousWorker(context, chat_history)
    
    # 1. Normal JSON array
    text_normal = '[{"thought": "test", "dialogue": "hello", "type": "observation"}]'
    res = worker._clean_and_parse_json(text_normal)
    assert len(res) == 1
    assert res[0]["dialogue"] == "hello"
    
    # 2. Markdown block JSON array
    text_md = '```json\n[{"thought": "test", "dialogue": "hello", "type": "observation"}]\n```'
    res = worker._clean_and_parse_json(text_md)
    assert len(res) == 1
    assert res[0]["dialogue"] == "hello"
    
    # 3. Single JSON dict (should be wrapped in list)
    text_dict = '{"thought": "test", "dialogue": "hello", "type": "observation"}'
    res = worker._clean_and_parse_json(text_dict)
    assert len(res) == 1
    assert res[0]["dialogue"] == "hello"
    
    # 4. Invalid JSON (should return fallback)
    text_invalid = 'invalid json data'
    res = worker._clean_and_parse_json(text_invalid)
    assert len(res) == 1
    assert "Strands payload parsing failure" in res[0]["thought"]
    assert res[0]["dialogue"] == "invalid json data"
