"""Tests for stateless burst OpencodeWorker.

Updated for Phase 4 Task 4.1 stateless burst executor.
"""
import os
import subprocess
import pytest
from unittest.mock import patch, MagicMock
import sys
import requests as _real_requests


def _mock_response(status_code=200, json_payload=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_payload or {}
    resp.text = text
    return resp


# ── Module-level tests ──────────────────────────────────────────────────────


def test_to_opencode_tools_converts_openai_format():
    from src.llm.opencode_worker import OpencodeWorker

    openai_tools = [
        {
            "type": "function",
            "function": {
                "name": "change_visual_state",
                "description": "Change the pet's visual state.",
                "parameters": {"type": "object", "properties": {"action": {"type": "string"}}},
            },
        }
    ]
    converted = OpencodeWorker._to_opencode_tools(openai_tools)
    assert len(converted) == 1
    assert converted[0] == {
        "name": "change_visual_state",
        "description": "Change the pet's visual state.",
        "input_schema": {"type": "object", "properties": {"action": {"type": "string"}}},
    }


def test_to_opencode_tools_skips_malformed_entries():
    from src.llm.opencode_worker import OpencodeWorker

    converted = OpencodeWorker._to_opencode_tools([{"type": "function"}, None, "junk"])
    assert converted == []


def test_to_opencode_tools_handles_none():
    from src.llm.opencode_worker import OpencodeWorker

    assert OpencodeWorker._to_opencode_tools(None) == []


def test_module_logger_has_debug_method():
    from src.llm.opencode_worker import logger
    assert hasattr(logger, "debug")
    assert callable(logger.debug)


# ── constants / skill tests ─────────────────────────────────────────────────


def test_active_chat_interval_constant():
    from src.constants import ACTIVE_CHAT_INTERVAL_SEC
    assert ACTIVE_CHAT_INTERVAL_SEC == 25


def test_boredom_timeout_constant():
    from src.constants import BOREDOM_TIMEOUT_SEC
    assert BOREDOM_TIMEOUT_SEC == 30


def test_api_constants_present():
    from src.config import DEFAULT_SERVER_URL
    assert DEFAULT_SERVER_URL.startswith("http")


def test_persona_hint_constant_exists():
    from src.constants import _PERSONA_HINT
    assert isinstance(_PERSONA_HINT, str)
    assert "Kenny" in _PERSONA_HINT


# ── Signal existence tests ────────────────────────────────────────────────


def test_response_ready_signal_exists(qapp):
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker(prompt="hi")
    assert hasattr(worker, "response_ready")


def test_trigger_ready_signal_added(qapp):
    """trigger_ready is the new preferred signal name (Phase 4.1)."""
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker(prompt="hi")
    assert hasattr(worker, "trigger_ready")


def test_error_occurred_signal_exists(qapp):
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker(prompt="hi")
    assert hasattr(worker, "error_occurred")
    assert hasattr(worker, "error")
    emitted = []
    worker.error_occurred.connect(emitted.append)


def test_session_created_signal_bw_compat(qapp):
    """session_created still exists for backward compat but is never emitted."""
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker(prompt="hi")
    assert hasattr(worker, "session_created")


def test_brain_update_ready_signal_exists(qapp):
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker(prompt="hi")
    assert hasattr(worker, "brain_update_ready")


def test_legacy_signals_not_present(qapp):
    """Removed signals from old stateful interface."""
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker(prompt="hi")
    assert not hasattr(worker, "pool_items_ready")
    assert not hasattr(worker, "path_used")
    assert not hasattr(worker, "session_turn_completed")
    assert not hasattr(worker, "context_injected")
    assert not hasattr(worker, "structured_ready")
    assert not hasattr(worker, "injection_failed")


# ── Constructor tests ────────────────────────────────────────────────────


def test_constructor_keyword_prompt(qapp):
    """New constructor uses prompt= keyword (first positional is accepted for backward compat)."""
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker(prompt="hello")
    assert worker._prompt == "hello"


def test_constructor_backward_compat_kwargs(qapp):
    """Extra kwargs (context_hint, apm, session_id, etc.) must not crash."""
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker(
        "hi", context_hint="Chrome", apm=42,
        is_autonomous=True, session_id="ses_1",
        prompt="prebuilt prompt", typing_content="hello world"
    )
    assert worker._prompt == "prebuilt prompt"
    assert worker._is_autonomous is True


# ── Session lifecycle (stateless burst) tests ────────────────────────────


def test_run_creates_and_deletes_session(qapp):
    """Every burst must create a session, use it, and delete it."""
    from src.llm.opencode_worker import OpencodeWorker

    call_log = []

    def fake_post(url, **kw):
        call_log.append(("post", url))
        if "/session" == url.rstrip("/").split("/")[-1] or url.endswith("/session"):
            return _mock_response(200, {"id": "sess_burst"})
        return _mock_response(200, {"parts": [{"type": "text", "text": '[{"dialogue":"hi","thought":"ok","type":"observation"}]'}]})

    def fake_delete(url, **kw):
        call_log.append(("delete", url))

    with patch("src.llm.opencode_worker.requests.post", fake_post), \
         patch("src.llm.opencode_worker.requests.delete", fake_delete):
        items = []
        worker = OpencodeWorker(prompt="test")
        worker.response_ready.connect(items.append)
        worker.run()

    assert len(items) == 1
    post_urls = [u for a, u in call_log if a == "post"]
    delete_urls = [u for a, u in call_log if a == "delete"]
    assert len(delete_urls) == 1, "Session must be deleted after burst"
    assert any("sess_burst" in u for u in delete_urls)


def test_session_deleted_on_parse_error(qapp):
    """Session must be deleted even if JSON parse fails."""
    from src.llm.opencode_worker import OpencodeWorker

    deleted_sessions = []

    def fake_post(url, **kw):
        if "/session" == url.rstrip("/").split("/")[-1] or url.endswith("/session"):
            return _mock_response(200, {"id": "sess_err"})
        return _mock_response(200, {"parts": [{"type": "text", "text": "not json at all }{{"}]})

    def fake_delete(url, **kw):
        deleted_sessions.append(url)

    with patch("src.llm.opencode_worker.requests.post", fake_post), \
         patch("src.llm.opencode_worker.requests.delete", fake_delete):
        worker = OpencodeWorker(prompt="test")
        worker.run()
    assert len(deleted_sessions) > 0
    assert any("sess_err" in u for u in deleted_sessions)


def test_abort_prevents_run(qapp):
    """Calling abort() before run() should skip all work."""
    from src.llm.opencode_worker import OpencodeWorker

    call_log = []

    def fake_post(url, **kw):
        call_log.append(url)
        return _mock_response(200, {"id": "sess"})

    worker = OpencodeWorker(prompt="test")
    worker.abort()
    with patch("src.llm.opencode_worker.requests.post", fake_post):
        worker.run()
    assert len(call_log) == 0


# ── brain_update signal emission tests ────────────────────────────────────


def test_brain_update_extracted_when_present(qapp):
    """run() must emit brain_update_ready with the brain_update dict
    and strip brain_update from items emitted via response_ready."""
    from src.llm.opencode_worker import OpencodeWorker

    def fake_post(url, **kw):
        if "/session" == url.rstrip("/").split("/")[-1] or url.endswith("/session"):
            return _mock_response(200, {"id": "bu_sess"})
        payload = '[{"thought":"t","dialogue":"hello","type":"observation","brain_update":{"user_habits":["codes at night"]}}]'
        return _mock_response(200, {"parts": [{"type": "text", "text": payload}]})

    with patch("src.llm.opencode_worker.requests.post", fake_post), \
         patch("src.llm.opencode_worker.requests.delete"):
        brain_updates = []
        response_items = []
        worker = OpencodeWorker(prompt="test")
        worker.brain_update_ready.connect(brain_updates.append)
        worker.response_ready.connect(response_items.append)
        worker.run()

    assert len(brain_updates) == 1
    assert brain_updates[0] == {"user_habits": ["codes at night"]}
    assert len(response_items) == 1
    assert "brain_update" not in response_items[0][0]


def test_brain_update_extracts_only_first_item(qapp):
    """When multiple items have brain_update, only emit the first one."""
    from src.llm.opencode_worker import OpencodeWorker

    def fake_post(url, **kw):
        if "/session" == url.rstrip("/").split("/")[-1] or url.endswith("/session"):
            return _mock_response(200, {"id": "bu2_sess"})
        payload = ('[{"thought":"t1","dialogue":"d1","type":"observation","brain_update":{"user_habits":["a"]}},'
                   '{"thought":"t2","dialogue":"d2","type":"observation","brain_update":{"pet_quirks":["b"]}}]')
        return _mock_response(200, {"parts": [{"type": "text", "text": payload}]})

    with patch("src.llm.opencode_worker.requests.post", fake_post), \
         patch("src.llm.opencode_worker.requests.delete"):
        brain_updates = []
        response_items = []
        worker = OpencodeWorker(prompt="test")
        worker.brain_update_ready.connect(brain_updates.append)
        worker.response_ready.connect(response_items.append)
        worker.run()

    assert len(brain_updates) == 1
    assert brain_updates[0] == {"user_habits": ["a"]}
    for item in response_items[0]:
        assert "brain_update" not in item


def test_brain_update_not_emitted_when_not_present(qapp):
    """When items have no brain_update, nothing should be emitted on that signal."""
    from src.llm.opencode_worker import OpencodeWorker

    def fake_post(url, **kw):
        if "/session" == url.rstrip("/").split("/")[-1] or url.endswith("/session"):
            return _mock_response(200, {"id": "bu3_sess"})
        payload = '[{"thought":"t","dialogue":"hello","type":"observation"}]'
        return _mock_response(200, {"parts": [{"type": "text", "text": payload}]})

    with patch("src.llm.opencode_worker.requests.post", fake_post), \
         patch("src.llm.opencode_worker.requests.delete"):
        brain_updates = []
        worker = OpencodeWorker(prompt="test")
        worker.brain_update_ready.connect(brain_updates.append)
        worker.run()
    assert len(brain_updates) == 0


# ── Parse strategy tests ─────────────────────────────────────────────────


def test_parse_direct_array(qapp):
    """_parse_response should handle direct JSON array."""
    from src.llm.opencode_worker import OpencodeWorker
    worker = OpencodeWorker(prompt="test")
    result = worker._parse_response('[{"dialogue":"hello","thought":"hi","type":"observation"}]')
    assert result is not None
    assert len(result) == 1
    assert result[0]["dialogue"] == "hello"


def test_parse_markdown_fence(qapp):
    """_parse_response should handle markdown-wrapped JSON."""
    from src.llm.opencode_worker import OpencodeWorker
    worker = OpencodeWorker(prompt="test")
    result = worker._parse_response('```json\n[{"dialogue":"hi","thought":"ok"}]\n```')
    assert result is not None
    assert len(result) == 1


def test_parse_single_object(qapp):
    """_parse_response should handle a single JSON object."""
    from src.llm.opencode_worker import OpencodeWorker
    worker = OpencodeWorker(prompt="test")
    result = worker._parse_response('{"dialogue":"hello","thought":"hi"}')
    assert result is not None
    assert len(result) == 1


def test_parse_jsonl(qapp):
    """_parse_response should handle JSONL (multiple objects on separate lines)."""
    from src.llm.opencode_worker import OpencodeWorker
    worker = OpencodeWorker(prompt="test")
    raw = '{"dialogue":"first","thought":"a"}\n{"dialogue":"second","thought":"b"}'
    result = worker._parse_response(raw)
    assert result is not None
    assert len(result) == 2


def test_parse_returns_fallback_for_garbage(qapp):
    from src.llm.opencode_worker import OpencodeWorker
    worker = OpencodeWorker(prompt="test")
    result = worker._parse_response("This is not JSON at all.")
    assert result == [{"dialogue": "This is not JSON at all.", "action": "idle", "type": "observation", "priority": 3, "thought": ""}]



# ── Backward compat: call site pattern tests ──────────────────────────────


def test_call_pattern_user_query(qapp):
    """Verify pattern used by pet_window for user queries."""
    from src.llm.opencode_worker import OpencodeWorker
    worker = OpencodeWorker(
        prompt="some prompt",
        is_autonomous=False,
    )
    assert worker._prompt == "some prompt"
    assert hasattr(worker, "response_ready")
    assert hasattr(worker, "error_occurred")


def test_call_pattern_autonomous_trigger(qapp):
    """Verify pattern used by pet_window for autonomous triggers."""
    from src.llm.opencode_worker import OpencodeWorker
    worker = OpencodeWorker(
        prompt="autonomous thought",
        is_autonomous=True,
    )
    assert worker._is_autonomous is True
    assert hasattr(worker, "brain_update_ready")
    assert hasattr(worker, "response_ready")


def test_call_pattern_refill(qapp):
    """Verify pattern used by pet_window for thought pool refill."""
    from src.llm.opencode_worker import OpencodeWorker
    worker = OpencodeWorker(
        "",
        is_autonomous=True,
        session_id=None,
        prompt="pool refill prompt",
    )
    assert worker._prompt == "pool refill prompt"
    assert worker._is_autonomous is True


def test_call_pattern_summary(qapp):
    """Verify pattern used by pet_window for summary generation."""
    from src.llm.opencode_worker import OpencodeWorker
    worker = OpencodeWorker(
        prompt="summarize this",
        session_id="existing_sess",
        is_autonomous=True,
    )
    assert worker._prompt == "summarize this"
    assert hasattr(worker, "response_ready")
