from unittest.mock import Mock

from src.mcp_server import _create_fastmcp_app


def test_query_semantic_memory_requires_configuration():
    server = Mock()
    server._rag_retriever = None
    app = _create_fastmcp_app(server)
    result = app._tool_manager._tools["query_semantic_memory"].fn("hello", 5)
    assert result["error"] == "Semantic memory is not configured"


def test_query_semantic_memory_delegates():
    server = Mock()
    server._rag_retriever = Mock()
    server._rag_retriever.retrieve.return_value = [{"id": "1"}]
    app = _create_fastmcp_app(server)
    result = app._tool_manager._tools["query_semantic_memory"].fn("hello", 2)
    server._rag_retriever.retrieve.assert_called_once_with("hello", 2)
    assert result == [{"id": "1"}]
