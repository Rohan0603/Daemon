from __future__ import annotations
from unittest.mock import MagicMock


def _make_manager(tmp_path, memory_facts=None):
    from src.context_manager import ContextManager
    from src.memory import Memory
    from src.history import History

    mem = Memory(path=str(tmp_path / "mem.json"))
    for k, v in (memory_facts or {}).items():
        mem.remember(k, v)
    hist = History(path=str(tmp_path / "hist.json"))
    return ContextManager(mem, hist), mem, hist


def test_build_context_is_minimal(tmp_path):
    mgr, _, _ = _make_manager(tmp_path)
    trigger = mgr.build_context("active_chat", "", 180, 5.0)
    assert len(trigger) < 500
    assert "active_chat" in trigger
    assert "180" in trigger


# ═══════════════════════════════════════════════════════════════════════════════
# Edge-case tests: build_context
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCaseBuildContext:

    def test_minimal_params(self, tmp_path):
        mgr, _, _ = _make_manager(tmp_path)
        trigger = mgr.build_context("boredom", "", 0, 0.0)
        assert "boredom" in trigger
        assert "0" in trigger
        assert "APM:" in trigger or "APM" in trigger

    def test_includes_idle_seconds(self, tmp_path):
        mgr, _, _ = _make_manager(tmp_path)
        trigger = mgr.build_context("active_chat", "", 50, 300.0)
        assert "300" in trigger

    def test_build_context_generates_mode_and_apm(self, tmp_path):
        mgr, _, _ = _make_manager(tmp_path)
        trigger = mgr.build_context("boredom", "", 0, 0.0)
        assert "Mode: boredom" in trigger
        assert "APM: 0" in trigger

    def test_build_context_includes_user_input(self, tmp_path):
        mgr, _, _ = _make_manager(tmp_path)
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
    assert "'thought' and 'dialogue'" in prompt


def test_user_trigger_has_single_json_object():
    from src.context_manager import ContextManager
    cm = ContextManager.__new__(ContextManager)
    cm._snapshot = {}
    cm._full_injected = False
    prompt = cm.build_user_trigger("user_input", "hello", 50, 0.0)
    assert "JSON array containing EXACTLY ONE object" in prompt
    assert "'thought' and 'dialogue'" in prompt


def test_user_trigger_mentions_required_keys():
    """User trigger must explicitly name 'thought' and 'dialogue' keys to prevent schema drift."""
    from src.context_manager import ContextManager
    cm = ContextManager.__new__(ContextManager)
    cm._snapshot = {}
    cm._full_injected = False
    prompt = cm.build_user_trigger("user_input", "test", 50, 0.0)
    assert "MUST contain" in prompt
    assert "thought" in prompt
    assert "dialogue" in prompt


def test_trigger_prompt_excludes_skill_content():
    """Verify SKILL.md content is NOT injected into trigger prompts (loaded natively by opencode serve)."""
    from src.context_manager import ContextManager
    from pathlib import Path
    cm = ContextManager.__new__(ContextManager)
    cm._snapshot = {}
    cm._full_injected = False
    user_prompt = cm.build_user_trigger("user_input", "hello", 50, 0.0)
    auto_prompt = cm.build_autonomous_trigger("active_chat", 50, 30.0)

    skill_path = Path(__file__).parent.parent / ".opencode" / "skills" / "kenny" / "SKILL.md"
    if skill_path.exists():
        skill_text = skill_path.read_text(encoding="utf-8")
        for line in skill_text.splitlines():
            if line.strip() and len(line.strip()) > 20:
                assert line.strip() not in user_prompt, f"SKILL.md leaked into user trigger: {line.strip()[:40]}"
                assert line.strip() not in auto_prompt, f"SKILL.md leaked into autonomous trigger: {line.strip()[:40]}"


def test_build_pool_refill_prompt_typing_high_apm():
    """Typing pool refill prompt adapts to high APM with panicked vibe."""
    from src.context_manager import ContextManager
    cm = ContextManager.__new__(ContextManager)
    cm._snapshot = {}
    cm._full_injected = False
    prompt = cm.build_pool_refill_prompt("typing_reactions", 80, 5)
    assert "frantically" in prompt
    assert "panicked" in prompt
    assert "APM: 80" in prompt
    assert "EXACTLY 5" in prompt
    assert "'thought' and 'dialogue'" in prompt


def test_build_pool_refill_prompt_typing_low_apm():
    """Typing pool refill prompt adapts to low APM with bored vibe."""
    from src.context_manager import ContextManager
    cm = ContextManager.__new__(ContextManager)
    cm._snapshot = {}
    cm._full_injected = False
    prompt = cm.build_pool_refill_prompt("typing_reactions", 5, 5)
    assert "painfully slow" in prompt
    assert "bored" in prompt
    assert "APM: 5" in prompt


def test_build_pool_refill_prompt_typing_normal_apm():
    """Typing pool refill prompt adapts to normal APM with distracted vibe."""
    from src.context_manager import ContextManager
    cm = ContextManager.__new__(ContextManager)
    cm._snapshot = {}
    cm._full_injected = False
    prompt = cm.build_pool_refill_prompt("typing_reactions", 30, 5)
    assert "normal pace" in prompt
    assert "distracted" in prompt
    assert "APM: 30" in prompt


def test_build_pool_refill_prompt_custom_count():
    """Typing pool refill prompt respects custom count parameter."""
    from src.context_manager import ContextManager
    cm = ContextManager.__new__(ContextManager)
    cm._snapshot = {}
    cm._full_injected = False
    prompt = cm.build_pool_refill_prompt("typing_reactions", 50, 3)
    assert "EXACTLY 3" in prompt


def test_build_pool_refill_prompt_unknown_type_fallback():
    """Unknown pool type gets generic fallback prompt."""
    from src.context_manager import ContextManager
    cm = ContextManager.__new__(ContextManager)
    cm._snapshot = {}
    cm._full_injected = False
    prompt = cm.build_pool_refill_prompt("unknown_pool", 50, 2)
    assert "autonomous thoughts/jokes" in prompt
    assert "2 autonomous" in prompt
