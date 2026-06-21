import pytest
from unittest.mock import MagicMock, patch
from src.strands_worker import StrandsAutonomousWorker

def test_strands_worker_initialization(qapp):
    context = {"active_window": "python", "apm": 10}
    chat_history = [{"role": "user", "content": "hi"}]
    mock_config = {
        "llm": {
            "model_id": "test-model",
            "provider": "openrouter",
            "api_key": "test-key"
        }
    }
    
    worker = StrandsAutonomousWorker(context, chat_history, profanity_level="moderate", config=mock_config)
    
    # Check that model configuration is correct
    assert worker.model.config.get("model_id") == "test-model"
    assert worker.model.client_args.get("api_key") == "test-key"
    assert worker.model.client_args.get("base_url") == "https://openrouter.ai/api/v1"

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
    assert res[0]["thought"] == "observation"
    assert res[0]["dialogue"] == "invalid json data"

    # 5. Over-150 char dialogue in JSON parsed form → truncated
    long_dialogue = "x" * 200
    text_long = f'[{{"thought": "test", "dialogue": "{long_dialogue}", "type": "observation"}}]'
    res = worker._clean_and_parse_json(text_long)
    assert len(res) == 1
    assert len(res[0]["dialogue"]) == 150
    assert res[0]["dialogue"].endswith("..."), "Should end with ellipsis when truncated"
    assert res[0]["dialogue"] == "x" * 147 + "..."

    # 6. Over-150 char fallback text → truncated
    text_very_long = "z" * 500
    res = worker._clean_and_parse_json(text_very_long)
    assert len(res) == 1
    assert res[0]["thought"] == "observation"
    assert len(res[0]["dialogue"]) == 150
    assert res[0]["dialogue"] == "z" * 147 + "..."
