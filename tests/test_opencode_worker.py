import os
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from PyQt6.QtWidgets import QApplication
import sys
import requests as _real_requests


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    return app


def _mock_response(status_code=200, json_payload=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_payload or {}
    resp.text = text
    return resp


# ── Module-level tests ──────────────────────────────────────────────────────


def test_module_logger_has_debug_method():
    from src.opencode_worker import logger
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
    from src.config import DEFAULT_CONFIG
    assert DEFAULT_CONFIG["llm"]["server_url"].startswith("http")
    # model_id and provider now have sensible defaults
    assert DEFAULT_CONFIG["llm"]["model_id"] == "north-mini-code-free"
    assert DEFAULT_CONFIG["llm"]["provider"] == "opencode-zen"
    assert isinstance(DEFAULT_CONFIG["llm"]["timeout_sec"], int)


def test_persona_hint_constant_exists():
    from src.constants import _PERSONA_HINT
    assert isinstance(_PERSONA_HINT, str)
    assert "Daemon" in _PERSONA_HINT


def test_worker_emits_pool_items_ready_signal(qapp):
    """OpencodeWorker should have pool_items_ready signal."""
    from src.opencode_worker import OpencodeWorker
    w = OpencodeWorker("hello")
    assert hasattr(w, "pool_items_ready")


# ── New signals tests ────────────────────────────────────────────────────────


def test_response_ready_signal_exists(qapp):
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker("hi")
    assert hasattr(worker, "response_ready")


def test_old_signals_removed(qapp):
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker("hi")
    assert not hasattr(worker, "trigger_ready")
    assert not hasattr(worker, "context_injected")
    assert not hasattr(worker, "injection_failed")
    assert not hasattr(worker, "structured_ready")
    assert not hasattr(worker, "structured_batch_ready")
    assert not hasattr(worker, "structured_multiplexed")
    assert not hasattr(worker, "result_ready")


# ── Constructor tests ────────────────────────────────────────────────────────


def test_constructor_simplified_kwargs(qapp):
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker("hi", context_hint="Chrome", apm=42,
                            is_autonomous=True, session_id="ses_1",
                            prompt="prebuilt prompt", typing_content="hello world")
    assert worker._user_input == "hi"
    assert worker._context_hint == "Chrome"
    assert worker._apm == 42
    assert worker._is_autonomous is True
    assert worker._session_id == "ses_1"
    assert worker._prebuilt_prompt == "prebuilt prompt"
    assert worker._typing_content == "hello world"


def test_constructor_no_removed_params(qapp):
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker("hi")
    assert not hasattr(worker, "_modes")
    assert not hasattr(worker, "_memory_context")
    assert not hasattr(worker, "_history_context")
    assert not hasattr(worker, "_idle_seconds")
    assert not hasattr(worker, "_last_action")
    assert not hasattr(worker, "_continue_session")
    assert not hasattr(worker, "_injection_in_flight")


# ── _post_message tests ─────────────────────────────────────────────────────


def test_post_message_creates_session_when_none(qapp):
    from src.opencode_worker import OpencodeWorker
    session_resp = _mock_response(200, {"id": "new_ses"})
    msg_resp = _mock_response(200, {"parts": [{"type": "text", "text": "hello"}]})

    with patch("src.opencode_worker.requests.post") as mock_req:
        mock_req.side_effect = [session_resp, msg_resp]
        session_ids = []
        worker = OpencodeWorker("hi")
        worker.session_created.connect(session_ids.append)
        result = worker._post_message({"parts": [{"type": "text", "text": "test"}]})
    assert result == "hello"
    assert session_ids == ["new_ses"]
    assert worker._session_id == "new_ses"
    assert mock_req.call_count == 2


def test_post_message_reuses_existing_session(qapp):
    from src.opencode_worker import OpencodeWorker
    msg_resp = _mock_response(200, {"parts": [{"type": "text", "text": "response"}]})

    with patch("src.opencode_worker.requests.post") as mock_req:
        mock_req.return_value = msg_resp
        worker = OpencodeWorker("hi", session_id="ses_existing")
        result = worker._post_message({"parts": [{"type": "text", "text": "test"}]})
    assert result == "response"
    assert mock_req.call_count == 1
    called_url = mock_req.call_args.args[0]
    assert called_url.endswith("/session/ses_existing/message")


def test_post_message_returns_none_on_connection_error(qapp):
    from src.opencode_worker import OpencodeWorker
    with patch("src.opencode_worker.requests.post") as mock_req:
        mock_req.side_effect = _real_requests.exceptions.ConnectionError("refused")
        worker = OpencodeWorker("hi")
        result = worker._post_message({"parts": [{"type": "text", "text": "test"}]})
    assert result is None


def test_post_message_returns_none_on_timeout(qapp):
    from src.opencode_worker import OpencodeWorker
    with patch("src.opencode_worker.requests.post") as mock_req:
        mock_req.side_effect = _real_requests.exceptions.Timeout("slow")
        worker = OpencodeWorker("hi")
        result = worker._post_message({"parts": [{"type": "text", "text": "test"}]})
    assert result is None


def test_post_message_returns_none_on_4xx(qapp):
    from src.opencode_worker import OpencodeWorker
    with patch("src.opencode_worker.requests.post") as mock_req:
        mock_req.return_value = _mock_response(status_code=500, text="boom")
        worker = OpencodeWorker("hi")
        result = worker._post_message({"parts": [{"type": "text", "text": "test"}]})
    assert result is None


def test_post_message_returns_none_on_no_text_parts(qapp):
    from src.opencode_worker import OpencodeWorker
    resp = _mock_response(200, {"parts": [{"type": "reasoning", "text": "hmm"}]})
    with patch("src.opencode_worker.requests.post") as mock_req:
        mock_req.return_value = resp
        worker = OpencodeWorker("hi")
        result = worker._post_message({"parts": [{"type": "text", "text": "test"}]})
    assert result is None


def test_post_message_returns_none_on_session_create_fail(qapp):
    from src.opencode_worker import OpencodeWorker
    with patch("src.opencode_worker.requests.post") as mock_req:
        mock_req.return_value = _mock_response(status_code=500, text="error")
        worker = OpencodeWorker("hi")
        result = worker._post_message({"parts": [{"type": "text", "text": "test"}]})
    assert result is None


def test_post_message_returns_none_on_session_no_id(qapp):
    from src.opencode_worker import OpencodeWorker
    with patch("src.opencode_worker.requests.post") as mock_req:
        mock_req.return_value = _mock_response(200, {"no": "id"})
        worker = OpencodeWorker("hi")
        result = worker._post_message({"parts": [{"type": "text", "text": "test"}]})
    assert result is None


# ── send tests ────────────────────────────────────────────────────────────────


def test_send_emits_response_ready(qapp):
    from src.opencode_worker import OpencodeWorker
    payload = '[{"thought":"t","dialogue":"hello","action":"idle"}]'
    msg_resp = _mock_response(200, {"parts": [{"type": "text", "text": payload}]})
    with patch("src.opencode_worker.requests.post") as mock_req:
        mock_req.return_value = msg_resp
        captured = []
        worker = OpencodeWorker("hi", session_id="ses_xyz")
        worker.response_ready.connect(captured.append)
        worker.send("test prompt")
    assert len(captured) == 1
    assert captured[0][0]["dialogue"] == "hello"


def test_send_includes_structured_schema(qapp):
    from src.opencode_worker import OpencodeWorker
    from src.constants import STRUCTURED_SCHEMA
    payload = '[{"thought":"t","dialogue":"hi","action":"idle"}]'
    msg_resp = _mock_response(200, {"parts": [{"type": "text", "text": payload}]})
    with patch("src.opencode_worker.requests.post") as mock_req:
        mock_req.return_value = msg_resp
        worker = OpencodeWorker("hi", session_id="ses_xyz")
        worker.send("test prompt")
    sent_json = mock_req.call_args.kwargs.get("json") or mock_req.call_args.args[1]
    assert "structured" in sent_json
    assert sent_json["structured"] == STRUCTURED_SCHEMA
    assert sent_json["parts"][0]["text"] == "test prompt"


def test_send_emits_schema_error_on_garbage(qapp):
    from src.opencode_worker import OpencodeWorker
    msg_resp = _mock_response(200, {"parts": [{"type": "text", "text": "not json at all"}]})
    with patch("src.opencode_worker.requests.post") as mock_req:
        mock_req.return_value = msg_resp
        captured = []
        worker = OpencodeWorker("hi", session_id="ses_xyz")
        worker.response_ready.connect(captured.append)
        worker.send("test prompt")
    assert len(captured) == 1
    assert "dialogue" in captured[0][0]
    assert "thought" in captured[0][0]


def test_handle_schema_error_returns_safe_default(qapp):
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker("hi")
    items = worker._handle_schema_error("garbage")
    assert len(items) == 1
    assert "dialogue" in items[0]
    assert "thought" in items[0]


# ── run() tests ─────────────────────────────────────────────────────────────


def test_run_delegates_to_send(qapp):
    from src.opencode_worker import OpencodeWorker
    payload = '[{"thought":"t","dialogue":"from prompt","action":"idle"}]'
    msg_resp = _mock_response(200, {"parts": [{"type": "text", "text": payload}]})
    with patch("src.opencode_worker.requests.post") as mock_req:
        mock_req.return_value = msg_resp
        captured = []
        paths = []
        worker = OpencodeWorker("hi", session_id="ses_xyz", prompt="prebuilt prompt")
        worker.response_ready.connect(captured.append)
        worker.path_used.connect(paths.append)
        worker.run()
    assert len(captured) == 1
    assert captured[0][0]["dialogue"] == "from prompt"
    assert paths == ["api"]


def test_run_does_nothing_without_prebuilt_prompt(qapp):
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker("hi")
    captured = []
    worker.response_ready.connect(captured.append)
    worker.run()
    assert len(captured) == 0


# ── Error signal tests ──────────────────────────────────────────────────────


def test_error_occurred_signal_exists(qapp):
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker("hi")
    assert hasattr(worker, "error_occurred")
    emitted = []
    worker.error_occurred.connect(emitted.append)


def test_session_created_signal_exists(qapp):
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker("hi")
    assert hasattr(worker, "session_created")


def test_path_used_signal_exists(qapp):
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker("hi")
    assert hasattr(worker, "path_used")


def test_brain_update_ready_signal_exists(qapp):
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker("hi")
    assert hasattr(worker, "brain_update_ready")


# ═══════════════════════════════════════════════════════════════════════════════
# Edge-case tests: session lifecycle
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCaseSessionLifecycle:

    def test_session_id_persists_after_send(self, qapp):
        from src.opencode_worker import OpencodeWorker
        session_resp = _mock_response(200, {"id": "persist_ses"})
        resp1 = _mock_response(200, {"parts": [{"type": "text", "text": '[{"thought":"t","dialogue":"hi","action":"idle"}]'}]})
        resp2 = _mock_response(200, {"parts": [{"type": "text", "text": '[{"thought":"t","dialogue":"hi","action":"idle"}]'}]})
        with patch("src.opencode_worker.requests.post") as mock_req:
            mock_req.side_effect = [session_resp, resp1, resp2]
            worker = OpencodeWorker("hi")
            worker.send("first message")
            assert worker._session_id == "persist_ses"
            worker.send("second message")
        assert mock_req.call_count == 3
        last_url = mock_req.call_args_list[2].args[0]
        assert "persist_ses" in last_url

    def test_two_stage_worker_sends_two_messages(self, qapp):
        """Two-stage worker posts two messages — first without schema, second with."""
        from src.opencode_worker import OpencodeWorker
        from unittest.mock import MagicMock
        handler = MagicMock()
        with patch.object(OpencodeWorker, "_post_message") as mock_post:
            mock_post.side_effect = [
                "Tool result: user is coding at terminal",
                '[{"thought": "t", "dialogue": "hi"}]',
            ]
            worker = OpencodeWorker(
                user_input="",
                two_stage_prompts=("investigate", "generate 5"),
            )
            worker.response_ready.connect(handler)
            worker._send_two_stage()

        assert mock_post.call_count == 2
        payload1 = mock_post.call_args_list[0][0][0]
        payload2 = mock_post.call_args_list[1][0][0]
        assert "structured" not in payload1
        from src.constants import STRUCTURED_SCHEMA
        assert payload2.get("structured") == STRUCTURED_SCHEMA
        assert "user is coding" in payload2["parts"][0]["text"]
        handler.assert_called_once_with([{"thought": "t", "dialogue": "hi"}])

    def test_session_created_emitted_on_send_when_no_session(self, qapp):
        from src.opencode_worker import OpencodeWorker
        session_resp = _mock_response(200, {"id": "send_new_ses"})
        msg_resp = _mock_response(200, {"parts": [{"type": "text", "text": '[{"thought":"t","dialogue":"hi","action":"idle"}]'}]})
        with patch("src.opencode_worker.requests.post") as mock_req:
            mock_req.side_effect = [session_resp, msg_resp]
            session_ids = []
            worker = OpencodeWorker("hi")
            worker.session_created.connect(session_ids.append)
            worker.send("system context")
        assert len(session_ids) == 1
        assert session_ids[0] == "send_new_ses"
