"""Focused tests for OpenCode SSE streaming and graceful fallback."""
from unittest.mock import MagicMock, patch

from src.llm.opencode_worker import OpencodeWorker


def _response(status=200, payload=None, lines=()):
    response = MagicMock()
    response.status_code = status
    response.json.return_value = payload or {}
    response.iter_lines.return_value = iter(lines)
    return response


def test_sse_partial_response_and_first_visible_signal():
    event = (
        'data: {"type":"message.part.updated","properties":{"part":'
        '{"sessionID":"s1","type":"text","text":"[{\\\"dialogue\\\":\\\"hello"}}}'
    )
    event2 = (
        'data: {"type":"message.part.updated","properties":{"part":'
        '{"sessionID":"s1","type":"text","text":"[{\\\"dialogue\\\":\\\"hello world\\\"}]"}}}'
    )

    partial, first = [], []
    worker = OpencodeWorker(prompt="test")
    worker.partial_response.connect(partial.append)
    worker.first_visible.connect(first.append)
    worker._handle_stream_event(event[5:], "s1")
    worker._handle_stream_event(event2[5:], "s1")

    assert "".join(partial) == "hello world"
    assert len(first) == 1
    assert first[0] >= 0


def test_streaming_404_preserves_non_streaming_response():
    calls = []

    def post(url, **kwargs):
        calls.append(url)
        if url.endswith("/session"):
            return _response(payload={"id": "s2"})
        return _response(payload={"parts": [{"type": "text", "text": '[{"dialogue":"fallback"}]'}]})

    with patch("src.llm.opencode_worker.requests.get", return_value=_response(status=404)), \
         patch("src.llm.opencode_worker.requests.post", side_effect=post), \
         patch("src.llm.opencode_worker.requests.delete"), \
         patch.object(OpencodeWorker, "_parse_response", return_value=[{"dialogue": "fallback"}]):
        items = []
        worker = OpencodeWorker(prompt="test")
        worker.response_ready.connect(items.append)
        worker.run()

    assert items[0][0]["dialogue"] == "fallback"
    assert any(url.endswith("/message") for url in calls)


def test_abort_closes_stream_and_requests_session_abort():
    response = MagicMock()
    response.status_code = 200
    response.iter_lines.side_effect = lambda **kwargs: iter(())
    with patch("src.llm.opencode_worker.requests.post") as post:
        worker = OpencodeWorker(prompt="test")
        worker._active_session_id = "s3"
        worker._stream_response = response
        worker.abort()

    response.close.assert_called_once()
    assert any("/session/s3/abort" in call.args[0] for call in post.call_args_list)
