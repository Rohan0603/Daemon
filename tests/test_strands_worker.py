import pytest
from unittest.mock import MagicMock, patch
from src.strands_worker import StrandsAutonomousWorker, StrandsSession, extract_dialogue_stream

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

@patch("src.strands_worker.sse_client")
@patch("src.strands_worker.MCPClient")
@patch("src.strands_worker.Agent")
def test_strands_session_persistency(mock_agent_class, mock_mcp_client_class, mock_sse_client):
    # Reset singleton instance
    StrandsSession._instance = None
    session = StrandsSession.get_instance()
    
    mock_mcp = mock_mcp_client_class.return_value
    mock_mcp.list_tools_sync.return_value = ["dummy_tool"]
    
    # 1. Create first user agent
    agent1, tools1 = session.get_agent(
        mode="user",
        system_prompt="prompt1",
        model="dummy_model",
        messages=[]
    )
    assert mock_agent_class.call_count == 1
    
    # 2. Get user agent again (should reuse)
    agent2, tools2 = session.get_agent(
        mode="user",
        system_prompt="prompt2",
        model="dummy_model",
        messages=[]
    )
    assert agent2 is agent1
    assert mock_mcp_client_class.call_count == 1  # No new client created
    assert mock_agent_class.call_count == 1
    
    # 3. Get autonomous agent (should recreate due to mode change)
    agent3, tools3 = session.get_agent(
        mode="autonomous",
        system_prompt="prompt3",
        model="dummy_model",
        messages=[]
    )
    assert mock_agent_class.call_count == 2
    assert mock_mcp_client_class.call_count == 2
    
    # Verify tool filters were passed
    last_args, last_kwargs = mock_mcp_client_class.call_args
    assert "tool_filters" in last_kwargs
    allowed = last_kwargs["tool_filters"]["allowed"]
    assert "read_file" in allowed
    assert "move_mouse" not in allowed
    
    # Cleanup
    session.close()

@patch("src.strands_worker.StrandsSession")
def test_strands_worker_streaming(mock_session_class, qapp):
    mock_session = mock_session_class.get_instance.return_value
    mock_agent = MagicMock()
    mock_session.get_agent.return_value = (mock_agent, [])
    
    worker = StrandsAutonomousWorker(
        context={},
        chat_history=[],
        profanity_level="moderate",
        mode="user"
    )
    
    # Mock agent execution to simulate streaming chunk callback
    def fake_agent_call(prompt, callback_handler=None):
        if callback_handler:
            callback_handler(data="chunk1")
            callback_handler(data="chunk2")
        # Return mock result object
        mock_result = MagicMock()
        mock_result.__str__.return_value = '[{"thought": "ok", "dialogue": "done"}]'
        return mock_result
        
    mock_agent.side_effect = fake_agent_call
    
    emitted_chunks = []
    worker.partial_text.connect(emitted_chunks.append)
    
    # Run the worker synchronously for testing
    worker.run()
    
    assert emitted_chunks == ["chunk1", "chunk2"]

def test_extract_dialogue_stream():
    assert extract_dialogue_stream('[{"dialogue": "hello') == "hello"
    assert extract_dialogue_stream('[{"dialogue": "hello"}') == "hello"
    assert extract_dialogue_stream('raw text') == "raw text"
    assert extract_dialogue_stream('[{"dialogue": "hello \\"world\\"\\nline') == 'hello "world"\nline'
    assert extract_dialogue_stream('[{"dialogue": "hello \\') == "hello "
