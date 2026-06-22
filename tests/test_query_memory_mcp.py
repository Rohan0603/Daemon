import json
import pytest
from unittest.mock import MagicMock


def _make_handler(memory=None, diary=None, history=None):
    from src.mcp_server import MCPHandler
    handler = MCPHandler.__new__(MCPHandler)
    handler._memory = memory or MagicMock()
    handler._diary = diary or MagicMock()
    handler._history = history or MagicMock()
    handler._config = {"consent": {}}
    return handler


def test_query_memory_type_memory():
    mem = MagicMock()
    mem.query.return_value = [{"id": "k1", "content": "v1", "timestamp": ""}]
    handler = _make_handler(memory=mem)
    result = handler._handle_query_memory({"type": "memory", "limit": 10})
    assert result["result"]["type"] == "memory"
    assert len(result["result"]["entries"]) == 1
    mem.query.assert_called_once()


def test_query_memory_type_diary():
    diary = MagicMock()
    diary.query.return_value = [{"id": "h1", "content": "entry", "timestamp": "2026-06-21"}]
    handler = _make_handler(diary=diary)
    result = handler._handle_query_memory({"type": "diary", "limit": 5})
    assert result["result"]["type"] == "diary"
    assert len(result["result"]["entries"]) == 1


def test_query_memory_type_history():
    hist = MagicMock()
    hist.query.return_value = [{"id": "0", "content": "user: hi", "timestamp": ""}]
    handler = _make_handler(history=hist)
    result = handler._handle_query_memory({"type": "history", "limit": 20})
    assert result["result"]["type"] == "history"


def test_query_memory_invalid_type_returns_error():
    handler = _make_handler()
    result = handler._handle_query_memory({"type": "unknown"})
    assert "error" in result


def test_query_memory_with_keyword_filter():
    from src.memory import Memory
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        mem = Memory(path=os.path.join(d, "mem.json"))
        mem.remember("fav_lang", "Python")
        mem.remember("fav_food", "Pizza")
        handler = _make_handler(memory=mem)
        result = handler._handle_query_memory({"type": "memory", "keyword": "Python"})
        entries = result["result"]["entries"]
        assert any("Python" in e["content"] for e in entries)
