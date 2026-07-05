"""Test query_memory tool in FastMCP server.

Calls _handle_query_memory directly.
"""
import json
import os
import tempfile
from unittest.mock import MagicMock
from src.mcp_server import _handle_query_memory


def _make_thread(memory=None, diary=None, history=None):
    thread = MagicMock()
    thread._memory = memory or MagicMock()
    thread._diary_store = diary or MagicMock()
    thread._history = history or MagicMock()
    thread._config = {"consent": {}}
    return thread


def _parse_result(result):
    """Parse the text content from the handler result dict."""
    return json.loads(result["content"][0]["text"])


def test_query_memory_type_memory():
    mem = MagicMock()
    mem.get_all.return_value = {"k1": "v1"}
    thread = _make_thread(memory=mem)
    result = _handle_query_memory(thread, "memory", None, 10)
    entries = _parse_result(result)
    assert len(entries) == 1
    assert "k1: v1" in entries[0]["content"]


def test_query_memory_type_diary():
    diary = MagicMock()
    diary.get_entries.return_value = [{"id": "h1", "content": "entry", "timestamp": "2026-06-21"}]
    thread = _make_thread(diary=diary)
    result = _handle_query_memory(thread, "diary", None, 5)
    entries = _parse_result(result)
    assert len(entries) == 1


def test_query_memory_type_history():
    hist = MagicMock()
    hist.get_entries.return_value = [{"id": "0", "content": "user: hi", "timestamp": ""}]
    thread = _make_thread(history=hist)
    result = _handle_query_memory(thread, "history", None, 20)
    entries = _parse_result(result)
    assert len(entries) == 1


def test_query_memory_invalid_type_returns_error():
    thread = _make_thread()
    result = _handle_query_memory(thread, "unknown", None, 20)
    text = result["content"][0]["text"]
    assert "Unknown type" in text


def test_query_memory_with_keyword_filter():
    from src.memory import Memory
    with tempfile.TemporaryDirectory() as d:
        mem = Memory(path=os.path.join(d, "mem.json"))
        mem.remember("fav_lang", "Python")
        mem.remember("fav_food", "Pizza")
        thread = _make_thread(memory=mem)
        result = _handle_query_memory(thread, "memory", "Python", 20)
        entries = _parse_result(result)
        assert any("Python" in e["content"] for e in entries)
