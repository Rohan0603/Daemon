import json

from scripts.benchmark_model_routing import _extract_tools, _extract_text, _json_valid, summarize, Sample


def test_benchmark_extracts_provider_shapes():
    assert _extract_text("ollama", {"message": {"content": "{\"ok\":true}"}}) == "{\"ok\":true}"
    assert _extract_text("opencode", {"parts": [{"type": "text", "text": "{\"ok\":true}"}]}) == "{\"ok\":true}"
    assert _extract_tools({"message": {"tool_calls": [{"function": {"name": "change_visual_state"}}]}}) == ["change_visual_state"]


def test_benchmark_json_and_summary_metrics():
    assert _json_valid(json.dumps({"dialogue": "ok"}))
    assert not _json_valid("not json")
    sample = Sample("ollama", "q8", "case", 1, True, 10, 8, True, True,
                    ["change_visual_state"], 2, 3, 5, 1, 0.5)
    summary = summarize([sample])["ollama"]
    assert summary["json_valid_rate"] == 1
    assert summary["tool_adherence_rate"] == 1
    assert summary["tokens"]["total"] == 5
