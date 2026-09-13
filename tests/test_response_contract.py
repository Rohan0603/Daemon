from src.llm.response_contract import normalize_response_items


def test_accepts_only_lean_fields():
    result = normalize_response_items([{
        "dialogue": "  hello  ",
        "action": "idle",
        "visual_state": "mirth",
        "brain_update": {"user_habits": ["reads at night"]},
    }])

    assert result == [{
        "dialogue": "hello",
        "action": "idle",
        "visual_state": "mirth",
        "brain_update": {"user_habits": ["reads at night"]},
    }]


def test_rejects_legacy_and_invalid_fields():
    assert normalize_response_items([{"dialogue": "hello", "thought": "secret"}]) == []
    assert normalize_response_items([{"dialogue": "hello", "action": "not-an-action"}]) == []
    assert normalize_response_items([{"dialogue": "hello", "visual_state": "not-an-emotion"}]) == []


def test_bounds_unicode_dialogue_without_corrupting_text():
    dialogue = "你好 👋 שלום " * 40
    result = normalize_response_items([{"dialogue": dialogue}])

    assert len(result[0]["dialogue"]) == 150
    assert result[0]["dialogue"].startswith("你好 👋 שלום")