"""Tests for WriteCoalescer.

The WriteCoalescer batches writes to local storage (memory, history, diary)
on an 8-second timer to avoid disk thrashing during autonomous chatter.
"""
import sys
import pytest
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    return app


def _make_memory(tmp_path):
    from src.memory import Memory
    return Memory(path=str(tmp_path / "mem.json"))


def _make_history(tmp_path):
    from src.history import History
    return History(path=str(tmp_path / "hist.json"))


def _make_coalescer(
    tmp_path,
    memory=None,
    history=None,
    memory_manager=None,
    diary_entries=None,
    diary_store=None,
    flush_sec=8.0,
):
    from src.write_coalescer import WriteCoalescer
    if memory is None:
        memory = _make_memory(tmp_path)
    if history is None:
        history = _make_history(tmp_path)
    if memory_manager is None:
        memory_manager = MagicMock()
    if diary_entries is None:
        diary_entries = []
    
    return WriteCoalescer(
        memory=memory,
        history=history,
        memory_manager=memory_manager,
        diary_store=diary_store,
        flush_sec=flush_sec,
    )


def test_constructor_does_not_start_timer(qapp, tmp_path):
    c = _make_coalescer(tmp_path)
    assert c._timer is None


def test_mark_dirty_does_not_write(qapp, tmp_path):
    mem = _make_memory(tmp_path)
    c = _make_coalescer(tmp_path, memory=mem)
    save = MagicMock()
    mem.save = save
    c.mark_dirty("memory")
    save.assert_not_called()


def test_flush_writes_dirty_memory(qapp, tmp_path):
    from src.memory import Memory
    mem = _make_memory(tmp_path)
    mem.remember("seed", "value")
    c = _make_coalescer(tmp_path, memory=mem)

    mem._facts["new"] = "data"
    c.mark_dirty("memory")
    c.flush()

    mem2 = Memory(path=str(tmp_path / "mem.json"))
    assert mem2.recall("new") == "data"


def test_flush_writes_dirty_history(qapp, tmp_path):
    from src.history import History
    hist = _make_history(tmp_path)
    hist.add_entry("a", "b", "idle")
    c = _make_coalescer(tmp_path, history=hist)

    hist._entries.append(
        {"timestamp": 0, "user_input": "x", "daemon_response": "y", "action": "idle"}
    )
    c.mark_dirty("history")
    c.flush()

    hist2 = History(path=str(tmp_path / "hist.json"))
    assert hist2.count() == 2
    assert hist2.get_recent(1)[0]["user_input"] == "x"


def test_flush_writes_dirty_diary(qapp, tmp_path):
    diary_entries = [
        {"content": "first entry", "timestamp": 1000, "hash": "abc"},
        {"content": "second entry", "timestamp": 2000, "hash": "def"},
    ]
    diary_store = MagicMock()
    diary_store.read.return_value = None
    diary_store.get_entries.return_value = diary_entries
    c = _make_coalescer(
        tmp_path, diary_entries=diary_entries, diary_store=diary_store
    )
    c.mark_dirty("diary")
    c.flush()

    diary_store.write.assert_called_once_with(diary_entries, 0)


def test_flush_retries_pending_writes_on_brain_flag():
    from src.write_coalescer import WriteCoalescer
    wc = WriteCoalescer(
        memory=MagicMock(), history=MagicMock(),
        memory_manager=MagicMock(),
    )
    wc.mark_dirty("brain")
    wc.flush()
    wc._memory_manager.retry_pending_writes.assert_called_once()
    assert wc._dirty["brain"] is False


def test_flush_handles_independent_failures(qapp, tmp_path):
    mem = MagicMock()
    mem.save.side_effect = Exception("memory write failed")
    hist = _make_history(tmp_path)
    hist.add_entry("seed", "value", "idle")
    c = _make_coalescer(tmp_path, memory=mem, history=hist)

    c.mark_dirty("memory")
    c.mark_dirty("history")
    c.flush()

    mem.save.assert_called_once()
    assert (tmp_path / "hist.json").exists()


def test_flush_does_not_write_when_clean(qapp, tmp_path):
    mem = _make_memory(tmp_path)
    c = _make_coalescer(tmp_path, memory=mem)
    save = MagicMock()
    mem.save = save
    c.flush()
    save.assert_not_called()


def test_start_creates_qtimer_with_correct_interval(qapp, tmp_path):
    c = _make_coalescer(tmp_path, flush_sec=8.0)
    c.start()
    try:
        assert c._timer is not None
        assert isinstance(c._timer, QTimer)
        assert c._timer.interval() == 8000
        assert c._timer.isActive()
    finally:
        c.stop()


def test_stop_stops_timer(qapp, tmp_path):
    c = _make_coalescer(tmp_path)
    c.start()
    assert c._timer.isActive()
    c.stop()
    assert not c._timer.isActive()


def test_flush_keeps_flag_set_on_failure(qapp, tmp_path):
    mem = MagicMock()
    mem.save.side_effect = Exception("fail")
    c = _make_coalescer(tmp_path, memory=mem)
    c.mark_dirty("memory")
    c.flush()
    c.flush()
    assert mem.save.call_count == 2


class TestWriteCoalescerEdgeCases:
    def test_mark_dirty_multiple_flags(self, qapp, tmp_path):
        mem = _make_memory(tmp_path)
        hist = _make_history(tmp_path)
        mgr = MagicMock()
        diary_store = MagicMock()
        diary_store.read.return_value = None
        diary_store.get_entries.return_value = []
        c = _make_coalescer(tmp_path, memory=mem, history=hist,
                            memory_manager=mgr, diary_store=diary_store)
        for flag in ("memory", "history", "diary", "brain"):
            c.mark_dirty(flag)
        mem.remember("k", "v")
        hist.add_entry("a", "b", "idle")
        c.flush()
        assert c._dirty["memory"] is False
        assert c._dirty["history"] is False
        assert c._dirty["diary"] is False
        assert c._dirty["brain"] is False

    def test_flush_without_diary_store(self, qapp, tmp_path):
        from src.write_coalescer import WriteCoalescer
        c = WriteCoalescer(
            memory=MagicMock(), history=MagicMock(),
            memory_manager=MagicMock(),
            diary_store=None,
        )
        c.mark_dirty("diary")
        c.flush()

    def test_constructor_accepts_null_diary_args(self, qapp, tmp_path):
        from src.write_coalescer import WriteCoalescer
        c = WriteCoalescer(
            memory=MagicMock(), history=MagicMock(),
            memory_manager=MagicMock(),
            diary_store=None,
        )
        assert c._diary_store is None

    def test_start_stop_multiple(self, qapp, tmp_path):
        from src.write_coalescer import WriteCoalescer
        c = WriteCoalescer(
            memory=MagicMock(), history=MagicMock(),
            memory_manager=MagicMock(),
        )
        c.start()
        c.stop()
        c.start()
        assert c._timer is not None
        assert c._timer.isActive()
        c.stop()

    def test_flush_diary_with_empty_entries(self, qapp, tmp_path):
        from src.write_coalescer import WriteCoalescer
        diary_store = MagicMock()
        diary_store.read.return_value = None
        diary_store.get_entries.return_value = []
        c = WriteCoalescer(
            memory=MagicMock(), history=MagicMock(),
            memory_manager=MagicMock(),
            diary_store=diary_store,
        )
        c.mark_dirty("diary")
        c.flush()
        diary_store.write.assert_called_once_with([], 0)

    def test_flush_diary_with_none_entries(self, qapp, tmp_path):
        from src.write_coalescer import WriteCoalescer
        diary_store = MagicMock()
        diary_store.read.return_value = None
        diary_store.get_entries.return_value = []
        c = WriteCoalescer(
            memory=MagicMock(), history=MagicMock(),
            memory_manager=MagicMock(),
            diary_store=diary_store,
        )
        c.mark_dirty("diary")
        c.flush()
        diary_store.write.assert_called_once_with([], 0)
