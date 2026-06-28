import pytest
from src.llm.strands_worker import StrandsAutonomousWorker
from src.ui.pet_window import PetWindow
from src.config import load_config
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication
from src.events import Event, EventType

def test_strands_worker_dual_profile_init_autonomous(qapp):
    """Autonomous profile: deep context (4000 tokens), full MCP tools."""
    context = {"active_window": "code", "apm": 45}
    chat_history = [{"role": "user", "content": "hi"}]
    worker = StrandsAutonomousWorker(
        context=context,
        chat_history=chat_history,
        zen_api_key="test-zen-key",
        uid="user-123",
        pet_id="kenny",
        is_autonomous=True
    )
    assert worker.uid == "user-123"
    assert worker.pet_id == "kenny"
    assert worker.is_autonomous is True
    assert worker.zen_api_key == "test-zen-key"
    assert "active_window" in worker.context

def test_strands_worker_dual_profile_init_user_chat(qapp):
    """User chat profile: ultra-compressed (1200 tokens), no tools unless requested."""
    context = {"user_query": "hello kenny"}
    chat_history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hey"}]
    worker = StrandsAutonomousWorker(
        context=context,
        chat_history=chat_history,
        zen_api_key="test-zen-key",
        uid="user-123",
        pet_id="kenny",
        is_autonomous=False
    )
    assert worker.uid == "user-123"
    assert worker.pet_id == "kenny"
    assert worker.is_autonomous is False
    assert worker.zen_api_key == "test-zen-key"
    assert "user_query" in worker.context
    assert worker.context["user_query"] == "hello kenny"

def test_strands_worker_correlation_id_propagation(qapp):
    """Correlation ID from context propagates to worker thread."""
    context = {"correlation_id": "test-cid-123", "active_window": "code"}
    worker = StrandsAutonomousWorker(
        context=context,
        chat_history=[],
        zen_api_key="test-key",
        uid="u1",
        pet_id="p1",
        is_autonomous=True
    )
    assert worker._correlation_id == "test-cid-123"

def test_strands_worker_tool_filters_autonomous():
    """Autonomous worker should have full tool access."""
    context = {"active_window": "code"}
    worker = StrandsAutonomousWorker(
        context=context,
        chat_history=[],
        zen_api_key="test-key",
        uid="u1",
        pet_id="p1",
        is_autonomous=True
    )
    assert worker._tool_filters is None

def test_strands_worker_tool_filters_user_chat():
    """User chat worker should have no tools by default."""
    context = {"user_query": "hello"}
    worker = StrandsAutonomousWorker(
        context=context,
        chat_history=[],
        zen_api_key="test-key",
        uid="u1",
        pet_id="p1",
        is_autonomous=False
    )
    assert worker._tool_filters == {"allowed": []}