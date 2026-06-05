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


# ── _process_output tests ────────────────────────────────────────────────────


def test_markdown_stripped():
    from src.opencode_worker import _process_output
    assert _process_output("**bold** `code` ~strike~") == "bold code strike"


def test_truncation_at_280_chars():
    from src.opencode_worker import _process_output
    long_text = "a" * 300
    result = _process_output(long_text)
    assert len(result) <= 280 + len("\u2026 (see terminal for full output)")
    assert result.endswith("\u2026 (see terminal for full output)")


def test_no_truncation_under_280():
    from src.opencode_worker import _process_output
    short_text = "a" * 100
    result = _process_output(short_text)
    assert result == short_text


# ── _parse_json_response tests ───────────────────────────────────────────────


def test_parse_json_response_valid():
    from src.opencode_worker import _parse_json_response
    text = '{"thought": "hmm", "dialogue": "hello", "action": "idle", "target_x": 0}'
    result = _parse_json_response(text)
    assert result is not None
    assert result["dialogue"] == "hello"
    assert result["action"] == "idle"


def test_parse_json_response_strips_code_fences():
    from src.opencode_worker import _parse_json_response
    text = '```json\n{"thought": "t", "dialogue": "hi", "action": "wander", "target_x": 500}\n```'
    result = _parse_json_response(text)
    assert result is not None
    assert result["target_x"] == 500


def test_parse_json_response_returns_none_on_invalid():
    from src.opencode_worker import _parse_json_response
    assert _parse_json_response("just some text with no json") is None
    assert _parse_json_response('{"no_dialogue_key": 1}') is None


def test_parse_json_response_ignores_preamble():
    from src.opencode_worker import _parse_json_response
    text = 'Here is my response:\n{"thought": "t", "dialogue": "hi", "action": "idle", "target_x": 0}'
    result = _parse_json_response(text)
    assert result is not None
    assert result["dialogue"] == "hi"


def test_parse_json_response_ignores_trailing_text():
    from src.opencode_worker import _parse_json_response
    text = '{"thought": "t", "dialogue": "hi", "action": "idle", "target_x": 0}\nSome trailing note.'
    result = _parse_json_response(text)
    assert result is not None
    assert result["dialogue"] == "hi"


def test_parse_json_response_unquoted_keys_fallback():
    from src.opencode_worker import _parse_json_response
    text = '{thought:"internal",dialogue:"Just vibing.",action:"idle",target:null}'
    result = _parse_json_response(text)
    assert result is not None
    assert result["dialogue"] == "Just vibing."
    assert result["action"] == "idle"


def test_parse_json_response_unquoted_keys_with_apostrophe():
    from src.opencode_worker import _parse_json_response
    text = '{thought:"hmm",dialogue:"You\'re working late.",action:"wander",target_x:500}'
    result = _parse_json_response(text)
    assert result is not None
    assert "working late" in result["dialogue"]
    assert result["action"] == "wander"


# ── _parse_json_batch tests ──────────────────────────────────────────────────


def test_parse_json_batch_handles_array():
    from src.opencode_worker import _parse_json_batch
    raw = '[{"thought":"t1","dialogue":"d1","action":"idle","target_x":null},{"thought":"t2","dialogue":"d2","action":"wander","target_x":300}]'
    items = _parse_json_batch(raw)
    assert len(items) == 2
    assert items[0]["dialogue"] == "d1"
    assert items[0]["action"] == "idle"
    assert items[1]["action"] == "wander"
    assert items[1]["target_x"] == 300


def test_parse_json_batch_falls_back_to_single():
    from src.opencode_worker import _parse_json_batch
    raw = '{"thought":"t","dialogue":"hi there","action":"shake","target_x":null}'
    items = _parse_json_batch(raw)
    assert len(items) == 1
    assert items[0]["dialogue"] == "hi there"
    assert items[0]["action"] == "shake"


def test_parse_json_batch_unquoted_keys_6_items():
    """Model sometimes outputs unquoted keys in arrays; brace-depth fallback must handle it."""
    from src.opencode_worker import _parse_json_batch
    raw = ('[{thought:"t1",dialogue:"d1",action:"idle",target_x:null},'
           '{thought:"t2",dialogue:"d2",action:"wander",target_x:300},'
           '{thought:"t3",dialogue:"d3",action:"shake",target_x:null},'
           '{thought:"t4",dialogue:"d4",action:"bounce",target_x:null},'
           '{thought:"t5",dialogue:"d5",action:"look_away",target_x:null},'
           '{thought:"t6",dialogue:"d6",action:"spin",target_x:null}]')
    items = _parse_json_batch(raw)
    assert len(items) == 6
    assert items[0]["dialogue"] == "d1"
    assert items[2]["action"] == "shake"
    assert items[4]["action"] == "look_away"
    assert items[5]["target_x"] == 0





def test_module_logger_has_debug_method():
    from src.opencode_worker import logger
    assert hasattr(logger, "debug")
    assert callable(logger.debug)


# ── constants / skill tests ──────────────────────────────────────────────────


def test_active_chat_interval_constant():
    from src.constants import ACTIVE_CHAT_INTERVAL_SEC
    assert ACTIVE_CHAT_INTERVAL_SEC == 25


def test_boredom_timeout_constant():
    from src.constants import BOREDOM_TIMEOUT_SEC
    assert BOREDOM_TIMEOUT_SEC == 30


def test_api_constants_present():
    from src import constants
    assert constants.OPENCODE_SERVER_URL.startswith("http")
    assert constants.OPENCODE_API_MODEL_ID == "deepseek-v4-flash"
    assert constants.OPENCODE_API_MODEL_PROVIDER == "opencode-go"
    assert isinstance(constants.OPENCODE_API_TIMEOUT_SEC, int)


def test_persona_hint_constant_exists():
    from src.constants import _PERSONA_HINT
    assert isinstance(_PERSONA_HINT, str)
    assert "Daemon" in _PERSONA_HINT


def test_skill_content_cached_at_module_level():
    """Skill is read once at import time and exposed as a module constant."""
    from src import opencode_worker
    assert hasattr(opencode_worker, "_SKILL_CONTENT")
    assert isinstance(opencode_worker._SKILL_CONTENT, str)
    assert "SYSTEM ROLE: DAEMON DESKTOP PET" in opencode_worker._SKILL_CONTENT


def test_pool_items_dual_pools_extracted():
    """Single-item user response with jokes_blackmail_items and system_items should parse correctly."""
    from src.opencode_worker import _parse_json_response
    text = '''{
        "thought":"ok","dialogue":"hi","action":"idle","target_x":null,"priority":3,
        "jokes_blackmail_items":[
            {"dialogue":"joke1","action":"idle","priority":4},
            {"dialogue":"joke2","action":"shake","priority":3}
        ],
        "system_items":[
            {"dialogue":"sys1","action":"idle","priority":5},
            {"dialogue":"sys2","action":"wander","priority":2}
        ]
    }'''
    result = _parse_json_response(text)
    assert result is not None
    assert result["dialogue"] == "hi"
    assert "jokes_blackmail_items" in result
    assert len(result["jokes_blackmail_items"]) == 2
    assert "system_items" in result
    assert len(result["system_items"]) == 2


def test_pool_items_missing_does_not_crash():
    """Response without pool items should work normally."""
    from src.opencode_worker import _parse_json_response
    text = '{"thought":"ok","dialogue":"hi","action":"idle","target_x":null,"priority":3}'
    result = _parse_json_response(text)
    assert result is not None


def test_worker_emits_pool_items_ready_signal(qapp):
    """OpencodeWorker should have pool_items_ready signal."""
    from src.opencode_worker import OpencodeWorker
    w = OpencodeWorker("hello")
    assert hasattr(w, "pool_items_ready")


# ── New signals tests ────────────────────────────────────────────────────────


def test_trigger_ready_signal_exists(qapp):
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker("hi")
    assert hasattr(worker, "trigger_ready")
    captured = []
    worker.trigger_ready.connect(lambda items: captured.append(items))
    assert True


def test_context_injected_signal_exists(qapp):
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker("hi")
    assert hasattr(worker, "context_injected")
    emitted = []
    worker.context_injected.connect(lambda: emitted.append(None))


def test_injection_failed_signal_exists(qapp):
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker("hi")
    assert hasattr(worker, "injection_failed")
    emitted = []
    worker.injection_failed.connect(emitted.append)


def test_old_signals_removed(qapp):
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker("hi")
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
    assert worker._injection_in_flight is False


def test_constructor_no_removed_params(qapp):
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker("hi")
    assert not hasattr(worker, "_modes")
    assert not hasattr(worker, "_memory_context")
    assert not hasattr(worker, "_history_context")
    assert not hasattr(worker, "_idle_seconds")
    assert not hasattr(worker, "_last_action")
    assert not hasattr(worker, "_continue_session")


# ── _normalize_parsed tests ─────────────────────────────────────────────────


def test_normalize_parsed_strips_markdown(qapp):
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker("hi")
    items = [{"dialogue": "**bold** `code`", "action": "idle", "target_x": 0, "priority": 3}]
    result = worker._normalize_parsed(items)
    assert result[0]["dialogue"] == "bold code"


def test_normalize_parsed_validates_action(qapp):
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker("hi")
    items = [{"dialogue": "hi", "action": "INVALID", "target_x": 0, "priority": 3}]
    result = worker._normalize_parsed(items)
    assert result[0]["action"] == "idle"


def test_normalize_parsed_coerces_target_x(qapp):
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker("hi")
    items = [{"dialogue": "hi", "action": "wander", "target_x": "500", "priority": 3}]
    result = worker._normalize_parsed(items)
    assert result[0]["target_x"] == 500


def test_normalize_parsed_target_x_none_coerces_to_zero(qapp):
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker("hi")
    items = [{"dialogue": "hi", "action": "idle", "target_x": None, "priority": 3}]
    result = worker._normalize_parsed(items)
    assert result[0]["target_x"] == 0


def test_normalize_parsed_ensures_priority_int(qapp):
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker("hi")
    items = [{"dialogue": "hi", "action": "idle", "target_x": 0, "priority": "4"}]
    result = worker._normalize_parsed(items)
    assert result[0]["priority"] == 4
    assert isinstance(result[0]["priority"], int)


def test_normalize_parsed_default_priority(qapp):
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker("hi")
    items = [{"dialogue": "hi", "action": "idle", "target_x": 0}]
    result = worker._normalize_parsed(items)
    assert result[0]["priority"] == 3


def test_normalize_parsed_action_lowercase(qapp):
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker("hi")
    items = [{"dialogue": "hi", "action": "SHAKE", "target_x": 0, "priority": 3}]
    result = worker._normalize_parsed(items)
    assert result[0]["action"] == "shake"


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


# ── send_trigger tests ──────────────────────────────────────────────────────


def test_send_trigger_emits_trigger_ready(qapp):
    from src.opencode_worker import OpencodeWorker
    payload = (
        '[{"thought":"t","dialogue":"hello world","action":"idle","target_x":null,"priority":3}]'
    )
    msg_resp = _mock_response(200, {"parts": [{"type": "text", "text": payload}]})

    with patch("src.opencode_worker.requests.post") as mock_req:
        mock_req.return_value = msg_resp
        captured = []
        worker = OpencodeWorker("hi", session_id="ses_xyz")
        worker.trigger_ready.connect(captured.append)
        worker.send_trigger("test prompt")
    assert len(captured) == 1
    assert captured[0][0]["dialogue"] == "hello world"
    assert captured[0][0]["action"] == "idle"


def test_send_trigger_emits_path_used_api(qapp):
    from src.opencode_worker import OpencodeWorker
    payload = '[{"thought":"t","dialogue":"hi","action":"idle","target_x":null,"priority":3}]'
    msg_resp = _mock_response(200, {"parts": [{"type": "text", "text": payload}]})

    with patch("src.opencode_worker.requests.post") as mock_req:
        mock_req.return_value = msg_resp
        paths = []
        worker = OpencodeWorker("hi", session_id="ses_xyz")
        worker.path_used.connect(paths.append)
        worker.send_trigger("test prompt")
    assert paths == ["api"]


def test_send_trigger_sends_model_in_payload(qapp):
    from src.opencode_worker import OpencodeWorker, OPENCODE_API_MODEL_PROVIDER, OPENCODE_API_MODEL_ID
    payload = '[{"thought":"t","dialogue":"hi","action":"idle","target_x":null,"priority":3}]'
    msg_resp = _mock_response(200, {"parts": [{"type": "text", "text": payload}]})

    with patch("src.opencode_worker.requests.post") as mock_req:
        mock_req.return_value = msg_resp
        worker = OpencodeWorker("hi", session_id="ses_xyz")
        worker.send_trigger("test prompt")
    sent_json = mock_req.call_args.kwargs.get("json") or mock_req.call_args.args[1]
    assert sent_json["model"]["providerID"] == OPENCODE_API_MODEL_PROVIDER
    assert sent_json["model"]["modelID"] == OPENCODE_API_MODEL_ID
    assert sent_json["parts"][0]["text"] == "test prompt"


def test_send_trigger_handles_post_message_none(qapp):
    from src.opencode_worker import OpencodeWorker
    with patch("src.opencode_worker.requests.post") as mock_req:
        mock_req.side_effect = _real_requests.exceptions.ConnectionError("no")
        worker = OpencodeWorker("hi")
        worker.send_trigger("test")  # should not raise


def test_send_trigger_emits_brain_update(qapp):
    from src.opencode_worker import OpencodeWorker
    payload = '[{"thought":"t","dialogue":"test","action":"idle","target_x":null,"priority":3,"brain_update":{"blackmail_material":["new"]}}]'
    msg_resp = _mock_response(200, {"parts": [{"type": "text", "text": payload}]})

    with patch("src.opencode_worker.requests.post") as mock_req:
        mock_req.return_value = msg_resp
        updates = []
        worker = OpencodeWorker("hi", session_id="ses_xyz")
        worker.brain_update_ready.connect(updates.append)
        worker.send_trigger("test prompt")
    assert len(updates) == 1
    assert updates[0] == {"blackmail_material": ["new"]}


def test_send_trigger_emits_pool_items(qapp):
    from src.opencode_worker import OpencodeWorker
    payload = (
        '{"thought":"t","dialogue":"hi","action":"idle","target_x":null,"priority":3,'
        '"jokes_blackmail_items":[{"dialogue":"j1","action":"idle","priority":4}],'
        '"system_items":[{"dialogue":"s1","action":"idle","priority":5}]}'
    )
    msg_resp = _mock_response(200, {"parts": [{"type": "text", "text": payload}]})

    with patch("src.opencode_worker.requests.post") as mock_req:
        mock_req.return_value = msg_resp
        pool_items = []
        worker = OpencodeWorker("hi", session_id="ses_xyz")
        worker.pool_items_ready.connect(pool_items.append)
        worker.send_trigger("test prompt")
    assert len(pool_items) == 1
    assert pool_items[0]["jokes_blackmail"] == [{"dialogue": "j1", "action": "idle", "priority": 4}]
    assert pool_items[0]["system"] == [{"dialogue": "s1", "action": "idle", "priority": 5}]


# ── inject_context tests ────────────────────────────────────────────────────


def test_inject_context_sends_no_reply_payload(qapp):
    from src.opencode_worker import OpencodeWorker
    msg_resp = _mock_response(200, {"parts": [{"type": "text", "text": "ok"}]})

    with patch("src.opencode_worker.requests.post") as mock_req:
        mock_req.return_value = msg_resp
        worker = OpencodeWorker("hi", session_id="ses_xyz")
        worker.inject_context("system context here")
    sent_json = mock_req.call_args.kwargs.get("json") or mock_req.call_args.args[1]
    assert sent_json["noReply"] is True
    assert sent_json["parts"][0]["text"] == "system context here"
    assert "model" not in sent_json


def test_inject_context_emits_context_injected_on_success(qapp):
    from src.opencode_worker import OpencodeWorker
    msg_resp = _mock_response(200, {"parts": [{"type": "text", "text": "ok"}]})

    with patch("src.opencode_worker.requests.post") as mock_req:
        mock_req.return_value = msg_resp
        emitted = []
        worker = OpencodeWorker("hi", session_id="ses_xyz")
        worker.context_injected.connect(lambda: emitted.append(None))
        worker.inject_context("test prompt")
    assert len(emitted) == 1


def test_inject_context_emits_injection_failed_on_none(qapp):
    from src.opencode_worker import OpencodeWorker
    with patch("src.opencode_worker.requests.post") as mock_req:
        mock_req.side_effect = _real_requests.exceptions.ConnectionError("refused")
        errors = []
        ci_emitted = []
        worker = OpencodeWorker("hi")
        worker.injection_failed.connect(errors.append)
        worker.context_injected.connect(lambda: ci_emitted.append(None))
        worker.inject_context("test prompt")
    assert len(errors) >= 1
    assert len(ci_emitted) == 0


def test_inject_context_clears_injection_in_flight(qapp):
    from src.opencode_worker import OpencodeWorker
    msg_resp = _mock_response(200, {"parts": [{"type": "text", "text": "ok"}]})

    with patch("src.opencode_worker.requests.post") as mock_req:
        mock_req.return_value = msg_resp
        worker = OpencodeWorker("hi")
        worker.inject_context("test")
    assert worker._injection_in_flight is False


def test_inject_context_clears_injection_in_flight_on_failure(qapp):
    from src.opencode_worker import OpencodeWorker
    with patch("src.opencode_worker.requests.post") as mock_req:
        mock_req.side_effect = _real_requests.exceptions.ConnectionError("refused")
        worker = OpencodeWorker("hi")
        worker.inject_context("test")
    assert worker._injection_in_flight is False


def test_inject_context_emits_injection_failed_on_exception(qapp):
    from src.opencode_worker import OpencodeWorker
    with patch("src.opencode_worker.requests.post") as mock_req:
        mock_req.side_effect = RuntimeError("unexpected crash")
        errors = []
        worker = OpencodeWorker("hi")
        worker.injection_failed.connect(errors.append)
        worker.inject_context("test prompt")
    assert len(errors) == 1
    assert "unexpected crash" in errors[0]


# ── run() tests ─────────────────────────────────────────────────────────────


def test_run_delegates_to_send_trigger(qapp):
    from src.opencode_worker import OpencodeWorker
    payload = '[{"thought":"t","dialogue":"from prompt","action":"idle","target_x":null,"priority":3}]'
    msg_resp = _mock_response(200, {"parts": [{"type": "text", "text": payload}]})

    with patch("src.opencode_worker.requests.post") as mock_req:
        mock_req.return_value = msg_resp
        captured = []
        paths = []
        worker = OpencodeWorker("hi", session_id="ses_xyz", prompt="prebuilt prompt text")
        worker.trigger_ready.connect(captured.append)
        worker.path_used.connect(paths.append)
        worker.run()
    assert len(captured) == 1
    assert captured[0][0]["dialogue"] == "from prompt"
    assert paths == ["api"]


def test_run_does_nothing_without_prebuilt_prompt(qapp):
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker("hi")
    captured = []
    worker.trigger_ready.connect(captured.append)
    worker.run()
    assert len(captured) == 0


# ── _process_raw_output tests ───────────────────────────────────────────────


def test_process_raw_output_fallback_on_plain_text(qapp):
    from src.opencode_worker import OpencodeWorker
    worker = OpencodeWorker("hi")
    captured = []
    worker.trigger_ready.connect(captured.append)
    worker._process_raw_output("plain text without json")
    assert len(captured) == 1
    assert captured[0][0]["dialogue"] == "plain text without json"
    assert captured[0][0]["action"] == "idle"


def test_process_raw_output_emits_brain_update(qapp):
    from src.opencode_worker import OpencodeWorker
    raw = '[{"thought":"t","dialogue":"test","action":"idle","target_x":null,"priority":3,"brain_update":{"key":"val"}}]'
    worker = OpencodeWorker("hi")
    updates = []
    captured = []
    worker.brain_update_ready.connect(updates.append)
    worker.trigger_ready.connect(captured.append)
    worker._process_raw_output(raw)
    assert len(updates) == 1
    assert updates[0] == {"key": "val"}
    assert len(captured) == 1
    assert captured[0][0]["dialogue"] == "test"


def test_process_raw_output_no_brain_update_when_absent(qapp):
    from src.opencode_worker import OpencodeWorker
    raw = '[{"thought":"t","dialogue":"test","action":"idle","target_x":null,"priority":3}]'
    worker = OpencodeWorker("hi")
    updates = []
    worker.brain_update_ready.connect(updates.append)
    worker._process_raw_output(raw)
    assert len(updates) == 0


def test_process_raw_output_emits_pool_items(qapp):
    from src.opencode_worker import OpencodeWorker
    raw = ('{"thought":"t","dialogue":"hi","action":"idle","target_x":null,"priority":3,'
           '"jokes_blackmail_items":[{"dialogue":"j1","action":"idle","priority":4}],'
           '"system_items":[{"dialogue":"s1","action":"idle","priority":5}]}')
    worker = OpencodeWorker("hi")
    pool_items = []
    worker.pool_items_ready.connect(pool_items.append)
    worker._process_raw_output(raw)
    assert len(pool_items) == 1


def test_process_raw_output_brain_update_does_not_affect_dialogue(qapp):
    from src.opencode_worker import OpencodeWorker
    raw = '[{"thought":"t","dialogue":"hello","action":"wander","target_x":100,"priority":3,"brain_update":{"log":["event"]}}]'
    worker = OpencodeWorker("hi")
    updates = []
    captured = []
    worker.brain_update_ready.connect(updates.append)
    worker.trigger_ready.connect(captured.append)
    worker._process_raw_output(raw)
    assert updates == [{"log": ["event"]}]
    assert captured[0][0]["dialogue"] == "hello"
    assert captured[0][0]["action"] == "wander"
    assert captured[0][0]["target_x"] == 100


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
# Edge-case tests: inject_context
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCaseInjectContext:

    def test_creates_session_when_none(self, qapp):
        from src.opencode_worker import OpencodeWorker
        session_resp = _mock_response(200, {"id": "new_ses"})
        msg_resp = _mock_response(200, {"parts": [{"type": "text", "text": "ok"}]})
        with patch("src.opencode_worker.requests.post") as mock_req:
            mock_req.side_effect = [session_resp, msg_resp]
            session_ids = []
            worker = OpencodeWorker("hi")
            worker.session_created.connect(session_ids.append)
            worker.inject_context("system context")
        assert session_ids == ["new_ses"]
        assert worker._session_id == "new_ses"
        assert mock_req.call_count == 2

    def test_does_nothing_when_in_flight(self, qapp):
        from src.opencode_worker import OpencodeWorker
        worker = OpencodeWorker("hi")
        worker._injection_in_flight = True
        with patch("src.opencode_worker.requests.post") as mock_req:
            worker.inject_context("test")
        mock_req.assert_not_called()

    def test_clears_in_flight_on_success(self, qapp):
        from src.opencode_worker import OpencodeWorker
        msg_resp = _mock_response(200, {"parts": [{"type": "text", "text": "ok"}]})
        with patch("src.opencode_worker.requests.post") as mock_req:
            mock_req.return_value = msg_resp
            worker = OpencodeWorker("hi")
            worker.inject_context("test")
        assert worker._injection_in_flight is False

    def test_clears_in_flight_on_failure(self, qapp):
        from src.opencode_worker import OpencodeWorker
        with patch("src.opencode_worker.requests.post") as mock_req:
            mock_req.side_effect = ConnectionError("fail")
            worker = OpencodeWorker("hi")
            worker.inject_context("test")
        assert worker._injection_in_flight is False

    def test_does_not_set_noReply_on_session_create(self, qapp):
        from src.opencode_worker import OpencodeWorker
        session_resp = _mock_response(200, {"id": "new_ses"})
        msg_resp = _mock_response(200, {"parts": [{"type": "text", "text": "ok"}]})
        with patch("src.opencode_worker.requests.post") as mock_req:
            mock_req.side_effect = [session_resp, msg_resp]
            worker = OpencodeWorker("hi")
            worker.inject_context("system context here")
        assert mock_req.call_count == 2
        call1_json = mock_req.call_args_list[0].kwargs.get("json") or mock_req.call_args_list[0].args[1]
        call2_json = mock_req.call_args_list[1].kwargs.get("json") or mock_req.call_args_list[1].args[1]
        assert "noReply" not in call1_json
        assert call2_json.get("noReply") is True

    def test_passes_exact_prompt_text(self, qapp):
        from src.opencode_worker import OpencodeWorker
        msg_resp = _mock_response(200, {"parts": [{"type": "text", "text": "ok"}]})
        with patch("src.opencode_worker.requests.post") as mock_req:
            mock_req.return_value = msg_resp
            worker = OpencodeWorker("hi", session_id="ses_xyz")
            worker.inject_context("EXACT_PROMPT_123!@#")
        sent_json = mock_req.call_args.kwargs.get("json") or mock_req.call_args.args[1]
        assert sent_json["parts"][0]["text"] == "EXACT_PROMPT_123!@#"


# ═══════════════════════════════════════════════════════════════════════════════
# Edge-case tests: send_trigger
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCaseSendTrigger:

    def test_does_not_set_noReply(self, qapp):
        from src.opencode_worker import OpencodeWorker
        payload = '[{"thought":"t","dialogue":"hi","action":"idle","target_x":null,"priority":3}]'
        msg_resp = _mock_response(200, {"parts": [{"type": "text", "text": payload}]})
        with patch("src.opencode_worker.requests.post") as mock_req:
            mock_req.return_value = msg_resp
            worker = OpencodeWorker("hi", session_id="ses_xyz")
            worker.send_trigger("test prompt")
        sent_json = mock_req.call_args.kwargs.get("json") or mock_req.call_args.args[1]
        assert "noReply" not in sent_json


# ═══════════════════════════════════════════════════════════════════════════════
# Edge-case tests: session lifecycle
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCaseSessionLifecycle:

    def test_session_id_persists_after_injection(self, qapp):
        from src.opencode_worker import OpencodeWorker
        session_resp = _mock_response(200, {"id": "persist_ses"})
        msg_resp1 = _mock_response(200, {"parts": [{"type": "text", "text": "ok"}]})
        msg_resp2 = _mock_response(200, {"parts": [{"type": "text", "text": '[{"dialogue":"hi","action":"idle","target_x":null,"priority":3}]'}]})
        with patch("src.opencode_worker.requests.post") as mock_req:
            mock_req.side_effect = [session_resp, msg_resp1, msg_resp2]
            worker = OpencodeWorker("hi")
            worker.inject_context("system context")
            assert worker._session_id == "persist_ses"
            worker.send_trigger("trigger prompt")
        assert mock_req.call_count == 3
        last_url = mock_req.call_args_list[2].args[0]
        assert "persist_ses" in last_url

    def test_session_created_emitted_on_inject_when_no_session(self, qapp):
        from src.opencode_worker import OpencodeWorker
        session_resp = _mock_response(200, {"id": "inject_new_ses"})
        msg_resp = _mock_response(200, {"parts": [{"type": "text", "text": "ok"}]})
        with patch("src.opencode_worker.requests.post") as mock_req:
            mock_req.side_effect = [session_resp, msg_resp]
            session_ids = []
            worker = OpencodeWorker("hi")
            worker.session_created.connect(session_ids.append)
            worker.inject_context("system context")
        assert len(session_ids) == 1
        assert session_ids[0] == "inject_new_ses"


# ═══════════════════════════════════════════════════════════════════════════════
# Edge-case tests: _normalize_parsed
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCaseNormalizeParsed:

    def test_missing_action_defaults_to_idle(self, qapp):
        from src.opencode_worker import OpencodeWorker
        worker = OpencodeWorker("hi")
        items = [{"dialogue": "hello", "target_x": 0, "priority": 3}]
        result = worker._normalize_parsed(items)
        assert result[0]["action"] == "idle"

    def test_missing_target_x_defaults_to_zero(self, qapp):
        from src.opencode_worker import OpencodeWorker
        worker = OpencodeWorker("hi")
        items = [{"dialogue": "hello", "action": "wander", "priority": 3}]
        result = worker._normalize_parsed(items)
        assert result[0]["target_x"] == 0

    def test_missing_dialogue_defaults_to_empty(self, qapp):
        from src.opencode_worker import OpencodeWorker
        worker = OpencodeWorker("hi")
        items = [{"action": "idle", "target_x": 0, "priority": 3}]
        result = worker._normalize_parsed(items)
        assert result[0]["dialogue"] == ""

    def test_missing_priority_defaults_to_three(self, qapp):
        from src.opencode_worker import OpencodeWorker
        worker = OpencodeWorker("hi")
        items = [{"dialogue": "hello", "action": "idle", "target_x": 0}]
        result = worker._normalize_parsed(items)
        assert result[0]["priority"] == 3


# ═══════════════════════════════════════════════════════════════════════════════
# Edge-case tests: _process_raw_output
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCaseProcessRawOutput:

    def test_empty_string_produces_fallback(self, qapp):
        from src.opencode_worker import OpencodeWorker
        worker = OpencodeWorker("hi")
        captured = []
        worker.trigger_ready.connect(captured.append)
        worker._process_raw_output("")
        assert len(captured) == 1
        assert captured[0][0]["action"] == "idle"
        assert captured[0][0]["target_x"] == 0
        assert captured[0][0]["priority"] == 3

    def test_whitespace_only_produces_fallback(self, qapp):
        from src.opencode_worker import OpencodeWorker
        worker = OpencodeWorker("hi")
        captured = []
        worker.trigger_ready.connect(captured.append)
        worker._process_raw_output("   \n  \t  ")
        assert len(captured) == 1
        assert captured[0][0]["action"] == "idle"
        assert captured[0][0]["target_x"] == 0
        assert captured[0][0]["priority"] == 3


class TestNormalizeParsedThought:

    def test_thought_field_preserved_in_normalized(self):
        from src.opencode_worker import OpencodeWorker
        worker = OpencodeWorker.__new__(OpencodeWorker)
        items = [{"dialogue": "hello", "action": "idle", "thought": "deep thought"}]
        result = worker._normalize_parsed(items)
        assert result[0]["thought"] == "deep thought"

    def test_thought_field_defaults_to_empty(self):
        from src.opencode_worker import OpencodeWorker
        worker = OpencodeWorker.__new__(OpencodeWorker)
        items = [{"dialogue": "hello", "action": "idle"}]
        result = worker._normalize_parsed(items)
        assert result[0]["thought"] == ""
