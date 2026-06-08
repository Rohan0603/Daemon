from __future__ import annotations
from unittest.mock import MagicMock


def _make_manager(tmp_path, memory_facts=None, diary=None):
    from src.context_manager import ContextManager
    from src.memory import Memory
    from src.history import History

    mem = Memory(path=str(tmp_path / "mem.json"))
    for k, v in (memory_facts or {}).items():
        mem.remember(k, v)
    hist = History(path=str(tmp_path / "hist.json"))
    diary_list = list(diary or [])
    return ContextManager(mem, hist, diary_list), mem, hist, diary_list


def test_build_context_is_minimal(tmp_path):
    mgr, _, _, _ = _make_manager(tmp_path)
    trigger = mgr.build_context("active_chat", "", 180, 5.0)
    assert len(trigger) < 500
    assert "active_chat" in trigger
    assert "180" in trigger


# ═══════════════════════════════════════════════════════════════════════════════
# Edge-case tests: build_context
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCaseBuildContext:

    def test_minimal_params(self, tmp_path):
        mgr, _, _, _ = _make_manager(tmp_path)
        trigger = mgr.build_context("boredom", "", 0, 0.0)
        assert "boredom" in trigger
        assert "0" in trigger
        assert "APM:" in trigger or "APM" in trigger

    def test_includes_idle_seconds(self, tmp_path):
        mgr, _, _, _ = _make_manager(tmp_path)
        trigger = mgr.build_context("active_chat", "", 50, 300.0)
        assert "300" in trigger

    def test_build_context_generates_mode_and_apm(self, tmp_path):
        mgr, _, _, _ = _make_manager(tmp_path)
        trigger = mgr.build_context("boredom", "", 0, 0.0)
        assert "Mode: boredom" in trigger
        assert "APM: 0" in trigger

    def test_build_context_includes_user_input(self, tmp_path):
        mgr, _, _, _ = _make_manager(tmp_path)
        trigger = mgr.build_context("active_chat", "hello", 10, 0.0)
        assert "active_chat" in trigger
        assert "User: hello" in trigger


def test_build_user_trigger_has_response_framing():
    from src.context_manager import ContextManager
    cm = ContextManager.__new__(ContextManager)
    cm._snapshot = {}
    cm._full_injected = False
    prompt = cm.build_user_trigger("user_input", "hello", 50, 0.0)
    assert "responding directly" in prompt
    assert "User said: hello" in prompt


def test_build_autonomous_trigger_has_internal_monologue():
    from src.context_manager import ContextManager
    cm = ContextManager.__new__(ContextManager)
    cm._snapshot = {}
    cm._full_injected = False
    prompt = cm.build_autonomous_trigger("active_chat", 50, 30.0)
    assert "internal monologue" in prompt or "thinking to herself" in prompt
    assert "NOT responding" in prompt


def test_autonomous_trigger_has_apm_as_primary_signal():
    from src.context_manager import ContextManager
    cm = ContextManager.__new__(ContextManager)
    cm._snapshot = {}
    cm._full_injected = False
    prompt = cm.build_autonomous_trigger("active_chat", 50, 30.0)
    assert "main signal" in prompt
    assert "APM: 50" in prompt


def test_user_trigger_has_apm_as_primary_signal():
    from src.context_manager import ContextManager
    cm = ContextManager.__new__(ContextManager)
    cm._snapshot = {}
    cm._full_injected = False
    prompt = cm.build_user_trigger("user_input", "hello", 50, 0.0)
    assert "primary signal" in prompt


def test_autonomous_trigger_includes_screen_text():
    from src.context_manager import ContextManager
    cm = ContextManager.__new__(ContextManager)
    cm._snapshot = {}
    cm._full_injected = False
    prompt = cm.build_autonomous_trigger("active_chat", 50, 30.0, screen_text="VS Code")
    assert "VS Code" in prompt


def test_user_trigger_includes_screen_text():
    from src.context_manager import ContextManager
    cm = ContextManager.__new__(ContextManager)
    cm._snapshot = {}
    cm._full_injected = False
    prompt = cm.build_user_trigger("user_input", "hello", 50, 0.0, screen_text="Notepad")
    assert "Notepad" in prompt


def test_autonomous_trigger_has_5_dialogs_instruction():
    from src.context_manager import ContextManager
    cm = ContextManager.__new__(ContextManager)
    cm._snapshot = {}
    cm._full_injected = False
    prompt = cm.build_autonomous_trigger("active_chat", 50, 30.0)
    assert "5 dialogs" in prompt


def test_user_trigger_has_single_json_object():
    from src.context_manager import ContextManager
    cm = ContextManager.__new__(ContextManager)
    cm._snapshot = {}
    cm._full_injected = False
    prompt = cm.build_user_trigger("user_input", "hello", 50, 0.0)
    assert "single JSON object" in prompt
