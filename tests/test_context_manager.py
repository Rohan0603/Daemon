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


def test_has_injected_full_false_initially(tmp_path):
    mgr, _, _, _ = _make_manager(tmp_path)
    assert mgr.has_injected_full() is False


def test_inject_full_sets_flag(tmp_path):
    mgr, mem, _, _ = _make_manager(tmp_path, memory_facts={"user_name": "Appi"})
    payload = mgr.inject_full()
    assert len(payload) > 100
    assert mgr.has_injected_full() is True
    assert "Appi" in payload


def test_inject_delta_returns_none_when_no_changes(tmp_path):
    mgr, _, _, _ = _make_manager(tmp_path)
    mgr.inject_full()
    mgr.snapshot_context("Desktop", 100)
    result = mgr.inject_delta("Desktop", 100)
    assert result is None


def test_inject_delta_detects_window_change(tmp_path):
    mgr, _, _, _ = _make_manager(tmp_path)
    mgr.inject_full()
    mgr._snapshot["active_window"] = "Notepad"
    result = mgr.inject_delta("YouTube", 100)
    assert result is not None
    assert "YouTube" in result


def test_inject_delta_detects_new_memory_fact(tmp_path):
    mgr, mem, _, _ = _make_manager(tmp_path, memory_facts={"user_name": "Appi"})
    mgr.inject_full()
    mem.remember("user_profession", "engineer")
    result = mgr.inject_delta("Desktop", 100)
    assert result is not None
    assert "user_profession" in result
    assert "engineer" in result
    assert "user_name" not in result


def test_inject_delta_detects_new_diary_entries(tmp_path):
    mgr, _, _, diary = _make_manager(tmp_path, diary=["old entry"])
    mgr.inject_full()
    diary.append("brand new diary entry")
    result = mgr.inject_delta("Desktop", 100)
    assert result is not None
    assert "brand new diary entry" in result
    assert "old entry" not in result


def test_inject_delta_detects_apm_bucket_change(tmp_path):
    mgr, _, _, _ = _make_manager(tmp_path)
    mgr.inject_full()
    mgr._snapshot["apm_bucket"] = "low"
    result = mgr.inject_delta("Desktop", 200)
    assert result is not None
    assert "high" in result


def test_needs_reinjection_initially_true(tmp_path):
    mgr, _, _, _ = _make_manager(tmp_path)
    assert mgr.needs_reinjection() is True


def test_needs_reinjection_false_after_full():
    from unittest.mock import MagicMock
    from src.context_manager import ContextManager
    mem = MagicMock()
    mem.get_all.return_value = {}
    mem.get_context_block.return_value = ""
    cm = ContextManager(mem, MagicMock(), [])
    cm.inject_full()
    assert cm.needs_reinjection() is False


def test_build_trigger_is_minimal(tmp_path):
    mgr, _, _, _ = _make_manager(tmp_path)
    trigger = mgr.build_trigger("active_chat", "", 180, 5.0)
    assert len(trigger) < 500
    assert "active_chat" in trigger
    assert "180" in trigger


def test_reset_forces_reinjection():
    from unittest.mock import MagicMock
    from src.context_manager import ContextManager
    mem = MagicMock()
    mem.get_all.return_value = {}
    mem.get_context_block.return_value = ""
    cm = ContextManager(mem, MagicMock(), [])
    cm.inject_full()
    cm.reset()
    assert cm.needs_reinjection() is True
    assert cm.has_injected_full() is False


def test_inject_full_includes_skill():
    from unittest.mock import MagicMock
    from src.context_manager import ContextManager
    mem = MagicMock()
    mem.get_context_block.return_value = ""
    cm = ContextManager(mem, MagicMock(), [])
    payload = cm.inject_full()
    assert len(payload) > 100
    assert cm.has_injected_full()


def test_snapshot_context_updates_fields(tmp_path):
    mgr, _, _, _ = _make_manager(tmp_path)
    mgr.inject_full()
    mgr.snapshot_context("Firefox", 200)
    assert mgr._snapshot["active_window"] == "Firefox"
    assert mgr._snapshot["apm_bucket"] == "high"


# ═══════════════════════════════════════════════════════════════════════════════
# Edge-case tests: inject_full
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCaseInjectFull:

    def test_empty_memory_and_diary(self, tmp_path):
        mgr, _, _, _ = _make_manager(tmp_path, memory_facts={}, diary=[])
        payload = mgr.inject_full()
        assert "SYSTEM ROLE: DAEMON DESKTOP PET" in payload
        assert "INSTRUCTION: Respond ONLY" in payload
        assert len(payload) > 100

    def test_empty_memory_with_diary(self, tmp_path):
        mgr, _, _, _ = _make_manager(tmp_path, memory_facts={}, diary=["entry1"])
        payload = mgr.inject_full()
        assert "entry1" in payload
        assert "DIARY" in payload.upper() or "diary" in payload

    def test_includes_all_expected_sections(self, tmp_path):
        mgr, mem, _, _ = _make_manager(
            tmp_path,
            memory_facts={"color": "blue"},
            diary=["diary note"],
        )
        payload = mgr.inject_full()
        assert "IDENTITY ANCHOR" in payload
        assert "Daemon" in payload
        assert "dialogue" in payload
        assert "action" in payload
        assert "diary" in payload.lower()
        assert "color: blue" in payload

    def test_includes_skill_content(self, tmp_path):
        mgr, _, _, _ = _make_manager(tmp_path)
        payload = mgr.inject_full()
        assert "SYSTEM ROLE: DAEMON DESKTOP PET" in payload


# ═══════════════════════════════════════════════════════════════════════════════
# Edge-case tests: inject_delta
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCaseInjectDelta:

    def test_returns_none_when_no_full_injection(self, tmp_path):
        mgr, _, _, _ = _make_manager(tmp_path)
        result = mgr.inject_delta("Desktop", 100)
        assert result is None

    def test_detects_multiple_changes(self, tmp_path):
        mgr, _, _, _ = _make_manager(tmp_path)
        mgr.inject_full()
        mgr._snapshot["active_window"] = "Notepad"
        mgr._snapshot["apm_bucket"] = "low"
        result = mgr.inject_delta("YouTube", 200)
        assert result is not None
        assert "YouTube" in result
        assert "high" in result

    def test_diary_shrink_does_not_crash(self, tmp_path):
        mgr, _, _, diary = _make_manager(
            tmp_path, diary=["a", "b", "c", "d", "e"]
        )
        mgr.inject_full()
        assert mgr._diary_injected_up_to == 5
        diary.clear()
        diary.append("new")
        result = mgr.inject_delta("Desktop", 100)
        assert result is not None
        assert "Desktop" in result

    def test_no_duplicate_on_repeated_call(self, tmp_path):
        mgr, _, _, _ = _make_manager(tmp_path)
        mgr.inject_full()
        mgr.snapshot_context("Desktop", 100)
        assert mgr.inject_delta("Desktop", 100) is None
        assert mgr.inject_delta("Desktop", 100) is None


# ═══════════════════════════════════════════════════════════════════════════════
# Edge-case tests: needs_reinjection
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCaseNeedsReinjection:

    def test_after_15_min_idle(self):
        import time as _real_time
        from unittest.mock import patch, MagicMock
        from src.context_manager import ContextManager
        mem = MagicMock()
        mem.get_all.return_value = {}
        mem.get_context_block.return_value = ""
        cm = ContextManager(mem, MagicMock(), [])
        with patch("src.context_manager.time.monotonic") as mock_time:
            mock_time.side_effect = [100.0, 100.0 + 16 * 60]
            cm.inject_full()
            assert cm.needs_reinjection() is True

    def test_false_under_threshold(self):
        import time as _real_time
        from unittest.mock import patch, MagicMock
        from src.context_manager import ContextManager
        mem = MagicMock()
        mem.get_all.return_value = {}
        mem.get_context_block.return_value = ""
        cm = ContextManager(mem, MagicMock(), [])
        with patch("src.context_manager.time.monotonic") as mock_time:
            mock_time.side_effect = [100.0, 100.0 + 5 * 60]
            cm.inject_full()
            assert cm.needs_reinjection() is False


# ═══════════════════════════════════════════════════════════════════════════════
# Edge-case tests: reset / build_trigger
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCaseReset:

    def test_reset_clears_all_snapshot_state(self, tmp_path):
        mgr, _, _, _ = _make_manager(tmp_path)
        mgr.inject_full()
        mgr.snapshot_context("Chrome", 100)
        mgr.reset()
        assert mgr.has_injected_full() is False
        assert mgr._snapshot == {}
        assert mgr._diary_injected_up_to == 0
        assert mgr.inject_delta("Desktop", 100) is None


class TestEdgeCaseBuildTrigger:

    def test_minimal_params(self, tmp_path):
        mgr, _, _, _ = _make_manager(tmp_path)
        trigger = mgr.build_trigger("boredom", "", 0, 0.0)
        assert "boredom" in trigger
        assert "0" in trigger
        assert "APM:" in trigger or "APM" in trigger

    def test_includes_idle_seconds(self, tmp_path):
        mgr, _, _, _ = _make_manager(tmp_path)
        trigger = mgr.build_trigger("active_chat", "", 50, 300.0)
        assert "300" in trigger

    def test_generates_array_for_autonomous(self, tmp_path):
        mgr, _, _, _ = _make_manager(tmp_path)
        trigger = mgr.build_trigger("boredom", "", 0, 0.0, is_autonomous=True)
        assert "JSON array" in trigger or "5 dialogs" in trigger or "array" in trigger.lower()

    def test_single_object_for_user_response(self, tmp_path):
        mgr, _, _, _ = _make_manager(tmp_path)
        trigger = mgr.build_trigger("active_chat", "hello", 10, 0.0, is_autonomous=False)
        assert "single JSON object" in trigger
        assert "hello" in trigger


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


def test_inject_delta_returns_none_when_no_context_changes():
    from unittest.mock import MagicMock
    from src.context_manager import ContextManager
    cm = ContextManager.__new__(ContextManager)
    cm._memory = MagicMock()
    cm._memory.get_all.return_value = {}
    cm._diary = []
    cm._snapshot = {"active_window": "", "apm_bucket": "low", "memory": {}, "diary_len": 0}
    cm._diary_injected_up_to = 0
    cm._full_injected = True
    result = cm.inject_delta("", 30)
    assert result is None


def test_inject_delta_returns_changes_when_window_changed():
    from unittest.mock import MagicMock
    from src.context_manager import ContextManager
    cm = ContextManager.__new__(ContextManager)
    cm._memory = MagicMock()
    cm._memory.get_all.return_value = {}
    cm._diary = []
    cm._snapshot = {"active_window": "Old", "apm_bucket": "low", "memory": {}, "diary_len": 0}
    cm._diary_injected_up_to = 0
    cm._full_injected = True
    result = cm.inject_delta("New Window", 30)
    assert result is not None
    assert "New Window" in result
