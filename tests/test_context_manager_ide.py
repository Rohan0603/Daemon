"""Tests for IDE-aware prompt enrichment in ContextManager."""

from src.llm.context_manager import ContextManager
from src.memory import Memory
from src.history import History


def _make_cm() -> ContextManager:
    mem = Memory()
    hist = History()
    cm = ContextManager(memory=mem, history=hist)
    # Invalidate cache so each test gets fresh prompts
    cm._invalidate_cache()
    return cm


def test_user_trigger_ide_slug_injected():
    cm = _make_cm()
    prompt = cm.build_user_trigger(
        mode="active_chat", user_input="hello", apm=40,
        idle_seconds=10.0, ide_slug="vscode",
    )
    assert "you are in vscode" in prompt
    assert "The user is coding." in prompt


def test_user_trigger_no_ide_slug_when_empty():
    cm = _make_cm()
    prompt = cm.build_user_trigger(
        mode="active_chat", user_input="hello", apm=40,
        idle_seconds=10.0, ide_slug="",
    )
    assert "you are in" not in prompt
    assert "coding" not in prompt


def test_autonomous_trigger_ide_slug_injected():
    cm = _make_cm()
    prompt = cm.build_autonomous_trigger(
        mode="boredom", apm=5, idle_seconds=120.0, ide_slug="pycharm",
    )
    assert "the user is in pycharm" in prompt
    assert "They are coding." in prompt


def test_autonomous_trigger_no_ide_slug_when_empty():
    cm = _make_cm()
    prompt = cm.build_autonomous_trigger(
        mode="boredom", apm=5, idle_seconds=120.0, ide_slug="",
    )
    assert "the user is in" not in prompt
    assert "coding" not in prompt


def test_cache_invalidates_with_different_ide_slug():
    cm = _make_cm()
    p1 = cm.build_user_trigger(
        mode="active_chat", user_input="test", apm=40,
        idle_seconds=10.0, ide_slug="vscode",
    )
    p2 = cm.build_user_trigger(
        mode="active_chat", user_input="test", apm=40,
        idle_seconds=10.0, ide_slug="pycharm",
    )
    assert "vscode" in p1
    assert "pycharm" in p2
    # Cache should have busted due to different ide_slug in params
    # (cache key doesn't include ide_slug, but ide_slug text differs)
    # Actually cache key only uses static fields, but the prompt text
    # will differ because we add the ide line. We just verify p2 has pycharm.
    assert p1 != p2
