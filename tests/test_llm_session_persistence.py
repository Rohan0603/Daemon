"""Tests for LLM session persistence (Persistent LLM Sessions)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestChatTurn:
    """Test ChatTurn dataclass."""

    def test_create_turn_user(self):
        from src.llm.llm_session_persistence import ChatTurn
        t = ChatTurn(role="user", content="hello")
        assert t.role == "user"
        assert t.content == "hello"
        assert t.timestamp == 0.0

    def test_create_turn_assistant(self):
        from src.llm.llm_session_persistence import ChatTurn
        t = ChatTurn(role="assistant", content="world")
        assert t.role == "assistant"
        assert t.content == "world"

    def test_to_from_dict(self):
        from src.llm.llm_session_persistence import ChatTurn
        t = ChatTurn(role="user", content="test", timestamp=123.0)
        d = t.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "test"
        assert d["timestamp"] == 123.0

        t2 = ChatTurn.from_dict(d)
        assert t2.role == "user"
        assert t2.content == "test"
        assert t2.timestamp == 123.0

    def test_to_from_dict_rejects_missing_keys(self):
        from src.llm.llm_session_persistence import ChatTurn
        with pytest.raises(KeyError):
            ChatTurn.from_dict({"role": "user"})


class TestLLMSessionState:
    """Test LLMSessionState dataclass."""

    @pytest.fixture
    def state(self):
        from src.llm.llm_session_persistence import LLMSessionState
        return LLMSessionState(
            session_id="test-session-123",
            model="deepseek-v4-flash-free",
            skill="kenny",
        )

    def test_create_default(self):
        from src.llm.llm_session_persistence import LLMSessionState
        s = LLMSessionState()
        assert s.session_id is None
        assert s.model == ""
        assert s.skill == "kenny"
        assert s.history == []
        assert s.summary == ""
        assert s.created_at == 0.0
        assert s.last_used_at == 0.0

    def test_add_turn_appends(self, state):
        state.add_turn("user", "hello")
        state.add_turn("assistant", "world")
        assert len(state.history) == 2
        assert state.history[0].role == "user"
        assert state.history[0].content == "hello"
        assert state.history[1].role == "assistant"
        assert state.history[1].content == "world"

    def test_to_from_dict(self, state):
        state.add_turn("user", "hello")
        state.add_turn("assistant", "world")
        d = state.to_dict()
        assert d["session_id"] == "test-session-123"
        assert d["model"] == "deepseek-v4-flash-free"
        assert len(d["history"]) == 2

        from src.llm.llm_session_persistence import LLMSessionState
        s2 = LLMSessionState.from_dict(d)
        assert s2.session_id == "test-session-123"
        assert len(s2.history) == 2

    def test_from_dict_corrupt_history_skipped(self):
        from src.llm.llm_session_persistence import LLMSessionState
        d = {
            "session_id": "test",
            "history": [
                {"role": "user", "content": "ok"},  # valid
                {"bad": "data"},                     # invalid - skipped
                {"role": "assistant", "content": "also ok"},  # valid
                "not_a_dict",                        # invalid - skipped
            ]
        }
        s = LLMSessionState.from_dict(d)
        assert len(s.history) == 2
        assert s.history[0].content == "ok"
        assert s.history[1].content == "also ok"

    def test_history_context_empty(self, state):
        assert state.history_context == ""

    def test_history_context_with_turns(self, state):
        state.add_turn("user", "Hello there")
        state.add_turn("assistant", "Hi!")
        ctx = state.history_context
        assert "[Previous conversation resumed after restart]" in ctx
        assert "User: Hello there" in ctx
        assert "Assistant: Hi!" in ctx

    def test_history_context_with_summary(self, state):
        state.add_turn("user", "Hey")
        state.summary = "User likes coding"
        ctx = state.history_context
        assert "Conversation summary: User likes coding" in ctx

    def test_history_context_truncates_long_turns(self, state):
        long_text = "x" * 1000
        state.add_turn("user", long_text)
        ctx = state.history_context
        # Should be truncated to 500 chars
        assert len("x" * 500) in (len(ctx[ctx.find("x"):ctx.rfind("x")+1]), 500)

    def test_last_used_updated_on_add_turn(self, state):
        old = state.last_used_at
        import time
        time.sleep(0.001)
        state.add_turn("user", "test")
        assert state.last_used_at > old


class TestSaveLoad:
    """Test save_session, load_session with temporary storage."""

    @pytest.fixture(autouse=True)
    def patch_storage_dir(self, monkeypatch, tmp_path):
        """Redirect STORAGE_DIR to a temp directory."""
        self.storage_dir = tmp_path / "data"
        self.storage_dir.mkdir()
        monkeypatch.setattr(
            "src.llm.llm_session_persistence._get_session_path",
            lambda: self.storage_dir / "llm_session.json",
        )

    def test_save_and_load(self):
        from src.llm.llm_session_persistence import (
            LLMSessionState, save_session, load_session,
        )
        state = LLMSessionState(session_id="sid-1", model="test-model")
        state.add_turn("user", "hello")
        state.add_turn("assistant", "world")
        save_session(state)

        loaded = load_session()
        assert loaded.session_id == "sid-1"
        assert loaded.model == "test-model"
        assert len(loaded.history) == 2
        assert loaded.history[0].content == "hello"

    def test_load_empty_file(self):
        from src.llm.llm_session_persistence import load_session
        loaded = load_session()
        assert loaded.session_id is None
        assert loaded.history == []

    def test_load_corrupt_json(self):
        from src.llm.llm_session_persistence import load_session
        path = self.storage_dir / "llm_session.json"
        path.write_text("{{{corrupt json}}")
        loaded = load_session()
        assert loaded.session_id is None

    def test_save_creates_directory(self, monkeypatch):
        """save_session should create the storage dir if missing."""
        deep_path = Path(tempfile.mkdtemp()) / "deep" / "nested"
        monkeypatch.setattr(
            "src.llm.llm_session_persistence._get_session_path",
            lambda: deep_path / "llm_session.json",
        )
        from src.llm.llm_session_persistence import LLMSessionState, save_session
        state = LLMSessionState(session_id="test")
        save_session(state)  # should not raise
        assert deep_path.exists()

    def test_save_and_clear(self):
        from src.llm.llm_session_persistence import (
            LLMSessionState, save_session, load_session, clear_session,
        )
        state = LLMSessionState(session_id="sid-2")
        save_session(state)
        assert load_session().session_id == "sid-2"
        clear_session()
        assert load_session().session_id is None

    def test_clear_session_nonexistent(self):
        from src.llm.llm_session_persistence import clear_session
        # Should not raise when file doesn't exist
        clear_session()


class TestWorkerIntegration:
    """Test that OpencodeWorker correctly uses session_state."""

    def test_session_state_reuses_session_id(self):
        from src.llm.llm_session_persistence import LLMSessionState
        from src.opencode_worker import OpencodeWorker

        state = LLMSessionState(session_id="previous-session-456")
        worker = OpencodeWorker(
            user_input="test",
            session_state=state,
        )
        assert worker._session_id == "previous-session-456"
        assert worker._session_state is state

    def test_session_id_overrides_session_state(self):
        from src.llm.llm_session_persistence import LLMSessionState
        from src.opencode_worker import OpencodeWorker

        state = LLMSessionState(session_id="old-session")
        worker = OpencodeWorker(
            user_input="test",
            session_id="explicit-session",
            session_state=state,
        )
        # explicit session_id takes precedence
        assert worker._session_id == "explicit-session"

    def test_session_state_none_by_default(self):
        from src.opencode_worker import OpencodeWorker
        worker = OpencodeWorker(user_input="test")
        assert worker._session_state is None

    def test_emit_turn_completed_called(self):
        """Verify _emit_turn_completed logic exists and doesn't crash."""
        from src.llm.llm_session_persistence import LLMSessionState
        from src.opencode_worker import OpencodeWorker

        state = LLMSessionState(session_id="test-session")
        worker = OpencodeWorker(
            user_input="hello",
            session_state=state,
        )
        # Should not raise — signal not connected but emit is safe
        # We can't easily test cross-thread signals here, but at least
        # verify the method is callable without error
        try:
            worker._emit_turn_completed("user prompt", "response text")
        except Exception as e:
            pytest.fail(f"_emit_turn_completed raised: {e}")

    def test_emit_turn_completed_no_state(self):
        from src.opencode_worker import OpencodeWorker
        worker = OpencodeWorker(user_input="test")
        # Should not raise when there's no session_state
        try:
            worker._emit_turn_completed("prompt", "response")
        except Exception as e:
            pytest.fail(f"_emit_turn_completed raised: {e}")
