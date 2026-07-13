"""Phase 4 Task 4.1 — Stateless burst OpencodeWorker tests.

Pure mock tests — no real HTTP calls.
"""
from unittest.mock import MagicMock, patch
import pytest


def test_worker_creates_and_deletes_session():
    """Every burst must create a session, use it, and delete it."""
    from src.llm.opencode_worker import OpencodeWorker

    created = []
    deleted = []

    def fake_create(self):
        created.append("sess_abc")
        return "sess_abc"

    def fake_delete(self, session_id):
        deleted.append(session_id)

    def fake_post(self, session_id, payload):
        return '[{"dialogue": "hi", "thought": "ok", "type": "observation"}]'

    with patch.object(OpencodeWorker, "_create_session", fake_create), \
         patch.object(OpencodeWorker, "_delete_session", fake_delete), \
         patch.object(OpencodeWorker, "_post_message", fake_post):
        worker = OpencodeWorker(prompt="test", is_autonomous=False)
        worker.run()

    assert created == ["sess_abc"]
    assert deleted == ["sess_abc"], "Session must always be deleted, even on success"


def test_session_deleted_on_parse_error():
    """Session must be deleted even if JSON parse fails."""
    from src.llm.opencode_worker import OpencodeWorker

    deleted = []

    def fake_create(self):
        return "sess_err"

    def fake_delete(self, session_id):
        deleted.append(session_id)

    def fake_post(self, session_id, payload):
        return "not json at all }{{"

    with patch.object(OpencodeWorker, "_create_session", fake_create), \
         patch.object(OpencodeWorker, "_delete_session", fake_delete), \
         patch.object(OpencodeWorker, "_post_message", fake_post):
        worker = OpencodeWorker(prompt="test", is_autonomous=False)
        worker.run()

    assert "sess_err" in deleted


def test_session_created_on_session_create_failure():
    """No error if session creation fails — worker should not explode."""
    from src.llm.opencode_worker import OpencodeWorker

    def fake_create(self):
        return None  # session creation failed

    errors = []

    with patch.object(OpencodeWorker, "_create_session", fake_create):
        worker = OpencodeWorker(prompt="test")
        worker.error.connect(lambda msg: errors.append(msg))
        worker.error_occurred.connect(lambda msg: errors.append(msg))
        worker.run()

    assert any("session_create_failed" in str(e) for e in errors)


def test_abort_prevents_run():
    """Calling abort() before run() should skip all work."""
    from src.llm.opencode_worker import OpencodeWorker

    worker = OpencodeWorker(prompt="test")
    worker.abort()

    session_called = []
    original_create = worker._create_session
    worker._create_session = lambda: (session_called.append(1), "sess")[1]

    worker.run()
    assert len(session_called) == 0


def test_backward_compatible_signals():
    """Must still expose response_ready, error_occurred, brain_update_ready signals."""
    from src.llm.opencode_worker import OpencodeWorker
    worker = OpencodeWorker(prompt="test")
    assert hasattr(worker, "response_ready")
    assert hasattr(worker, "error_occurred")
    assert hasattr(worker, "brain_update_ready")
    assert hasattr(worker, "trigger_ready")
    assert hasattr(worker, "error")


def test_parse_strategy_direct_array():
    """_parse_response should handle direct JSON array."""
    from src.llm.opencode_worker import OpencodeWorker
    worker = OpencodeWorker(prompt="test")
    raw = '[{"dialogue": "hello", "thought": "hi", "type": "observation"}]'
    result = worker._parse_response(raw)
    assert result is not None
    assert len(result) == 1
    assert result[0]["dialogue"] == "hello"


def test_parse_strategy_markdown_fence():
    """_parse_response should handle markdown-wrapped JSON."""
    from src.llm.opencode_worker import OpencodeWorker
    worker = OpencodeWorker(prompt="test")
    raw = '```json\n[{"dialogue": "hi", "thought": "ok"}]\n```'
    result = worker._parse_response(raw)
    assert result is not None
    assert len(result) == 1


def test_parse_strategy_single_object():
    """_parse_response should handle a single JSON object."""
    from src.llm.opencode_worker import OpencodeWorker
    worker = OpencodeWorker(prompt="test")
    raw = '{"dialogue": "hello", "thought": "hi"}'
    result = worker._parse_response(raw)
    assert result is not None
    assert len(result) == 1


def test_parse_strategy_jsonl():
    """_parse_response should handle JSONL (multiple objects on separate lines)."""
    from src.llm.opencode_worker import OpencodeWorker
    worker = OpencodeWorker(prompt="test")
    raw = '{"dialogue": "first", "thought": "a"}\n{"dialogue": "second", "thought": "b"}'
    result = worker._parse_response(raw)
    assert result is not None
    assert len(result) == 2


def test_parse_returns_fallback_for_garbage():
    """When all parse strategies fail, _parse_response returns None and
    emits both error signals rather than silently wrapping as dialogue."""
    from src.llm.opencode_worker import OpencodeWorker
    worker = OpencodeWorker(prompt="test")

    error_signals: list[str] = []
    error_occurred_signals: list[str] = []
    worker.error.connect(lambda e: error_signals.append(e))
    worker.error_occurred.connect(lambda e: error_occurred_signals.append(e))

    result = worker._parse_response("This is not JSON at all. And definitely not a list.")
    assert result is None
    assert error_signals == ["parse_failed"]
    assert error_occurred_signals == ["parse_failed"]
