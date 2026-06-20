import json
import time
import pytest
from pathlib import Path


def _make_history(tmp_path):
    from src.history import History
    path = str(tmp_path / "history.json")
    return History(path=path), path


def test_add_and_count(tmp_path):
    hist, _ = _make_history(tmp_path)
    hist.add_entry("hello", "hi there", "idle")
    hist.add_entry("how are you", "good", "idle")
    assert hist.count() == 2


def test_get_recent(tmp_path):
    hist, _ = _make_history(tmp_path)
    for i in range(10):
        hist.add_entry(f"input{i}", f"resp{i}", "idle")
    recent = hist.get_recent(3)
    assert len(recent) == 3
    assert recent[-1]["user_input"] == "input9"


def test_get_recent_returns_correct_order(tmp_path):
    hist, _ = _make_history(tmp_path)
    hist.add_entry("first", "resp1", "idle")
    hist.add_entry("second", "resp2", "idle")
    recent = hist.get_recent(2)
    assert recent[0]["user_input"] == "first"
    assert recent[1]["user_input"] == "second"


def test_get_all(tmp_path):
    hist, _ = _make_history(tmp_path)
    hist.add_entry("a", "A", "idle")
    hist.add_entry("b", "B", "wander")
    assert len(hist.get_all()) == 2


def test_clear(tmp_path):
    hist, _ = _make_history(tmp_path)
    hist.add_entry("x", "y", "idle")
    hist.clear()
    assert hist.count() == 0


def test_persistence_across_instances(tmp_path):
    hist1, path = _make_history(tmp_path)
    hist1.add_entry("persist", "test", "idle")
    del hist1

    from src.history import History
    hist2 = History(path=path)
    assert hist2.count() == 1
    assert hist2.get_recent(1)[0]["user_input"] == "persist"


def test_corrupt_file_returns_empty(tmp_path):
    from src.history import History
    path = str(tmp_path / "corrupt.json")
    with open(path, "w") as f:
        f.write("{{{ not json")
    hist = History(path=path)
    assert hist.count() == 0


def test_missing_file_returns_empty(tmp_path):
    from src.history import History
    path = str(tmp_path / "noexist.json")
    hist = History(path=path)
    assert hist.count() == 0


def test_context_block_with_entries(tmp_path):
    hist, _ = _make_history(tmp_path)
    hist.add_entry("hello", "hi back", "idle")
    block = hist.get_context_block()
    assert "hello" in block
    assert "hi back" in block
    assert "Recent conversations" in block


def test_context_block_empty_when_no_entries(tmp_path):
    hist, _ = _make_history(tmp_path)
    assert hist.get_context_block() == ""


def test_context_block_truncates_long_response(tmp_path):
    hist, _ = _make_history(tmp_path)
    long_resp = "x" * 100
    hist.add_entry("short", long_resp, "idle")
    block = hist.get_context_block()
    assert "..." in block


def test_autonomous_entry_stored_as_empty_user_input(tmp_path):
    hist, _ = _make_history(tmp_path)
    hist.add_entry("", "autonomous check-in", "wander")
    recent = hist.get_recent(1)
    assert recent[0]["user_input"] == ""
    assert recent[0]["daemon_response"] == "autonomous check-in"


def test_max_entries_enforced(tmp_path):
    from src.history import History, _MAX_ENTRIES
    hist, _ = _make_history(tmp_path)
    for i in range(_MAX_ENTRIES + 50):
        hist.add_entry(f"in{i}", f"out{i}", "idle")
    assert hist.count() == _MAX_ENTRIES
    assert hist.get_recent(1)[0]["user_input"] == f"in{_MAX_ENTRIES + 49}"


def test_context_block_shows_recent_first(tmp_path):
    hist, _ = _make_history(tmp_path)
    hist.add_entry("first", "one", "idle")
    hist.add_entry("second", "two", "idle")
    block = hist.get_context_block(n=2)
    second_idx = block.index("second")
    first_idx = block.index("first")
    assert second_idx < first_idx


def test_save_is_callable(tmp_path):
    from src.history import History
    h = History(path=str(tmp_path / "hist.json"))
    h.add_entry("q", "a", "idle")
    h.save()  # must not raise
    data = json.loads((tmp_path / "hist.json").read_text())
    assert len(data["history"]) == 1


def test_add_entry_marks_dirty_when_coalescer_provided(tmp_path):
    from unittest.mock import MagicMock
    from src.history import History
    h = History(path=str(tmp_path / "hist.json"))
    coalescer = MagicMock()
    h.add_entry("q", "a", "idle", coalescer=coalescer)
    coalescer.mark_dirty.assert_called_once_with("history")
    assert h.count() == 1


def test_bak_file_created_on_save(tmp_path):
    from src.history import History
    from pathlib import Path
    path = str(tmp_path / "hist.json")
    h = History(path=path)
    h.add_entry("u1", "r1", "idle")
    h.save()
    h.add_entry("u2", "r2", "shake")
    h.save()
    bak_path = path + ".bak"
    assert Path(bak_path).exists()


def test_load_falls_back_to_bak_when_main_corrupt(tmp_path):
    from src.history import History
    from pathlib import Path
    path = str(tmp_path / "hist.json")
    h = History(path=path)
    h.add_entry("rescue", "this", "idle")
    h.save()
    Path(path).write_text("garbage", encoding="utf-8")
    h2 = History(path=path)
    entries = h2.get_all()
    assert len(entries) == 1
    assert entries[0]["user_input"] == "rescue"


class TestHistoryEdgeCases:
    def test_get_recent_with_more_requested_than_available(self, tmp_path):
        from src.history import History
        hist = History(path=str(tmp_path / "hist.json"))
        for i in range(5):
            hist.add_entry(f"in{i}", f"out{i}", "idle")
        recent = hist.get_recent(100)
        assert len(recent) == 5

    def test_get_recent_with_zero(self, tmp_path):
        from src.history import History
        hist = History(path=str(tmp_path / "hist.json"))
        hist.add_entry("hello", "world", "idle")
        assert hist.get_recent(0) == []

    def test_get_recent_with_negative(self, tmp_path):
        from src.history import History
        hist = History(path=str(tmp_path / "hist.json"))
        hist.add_entry("hello", "world", "idle")
        assert hist.get_recent(-1) == []

    def test_add_entry_with_empty_response(self, tmp_path):
        from src.history import History
        hist = History(path=str(tmp_path / "hist.json"))
        hist.add_entry("hello", "", "idle")
        recent = hist.get_recent(1)
        assert recent[0]["daemon_response"] == ""

    def test_get_context_block_max_entries_zero(self, tmp_path):
        from src.history import History
        hist = History(path=str(tmp_path / "hist.json"))
        hist.add_entry("test", "response", "idle")
        assert hist.get_context_block(n=0) == ""

    def test_get_context_block_with_one_entry(self, tmp_path):
        from src.history import History
        hist = History(path=str(tmp_path / "hist.json"))
        hist.add_entry("hello", "hi", "idle")
        block = hist.get_context_block()
        assert "## Recent conversations:" in block
        assert 'You: "hello"' in block
        assert 'Daemon: "hi"' in block

    def test_unicode_in_input_and_response(self, tmp_path):
        from src.history import History
        hist = History(path=str(tmp_path / "hist.json"))
        hist.add_entry("héllo 🌍", "wörld 👋", "idle")
        recent = hist.get_recent(1)
        assert recent[0]["user_input"] == "héllo 🌍"
        assert recent[0]["daemon_response"] == "wörld 👋"

    def test_save_no_entries(self, tmp_path):
        from src.history import History
        hist = History(path=str(tmp_path / "hist.json"))
        hist.save()

    def test_bak_fallback_when_main_is_directory(self, tmp_path):
        from src.history import History
        from pathlib import Path
        path = str(tmp_path / "hist.json")
        hist = History(path=path)
        hist.add_entry("rescue", "me", "idle")
        hist.save()
        Path(path).unlink()
        Path(path).mkdir()
        hist2 = History(path=path)
        assert hist2.count() == 1
        assert hist2.get_recent(1)[0]["user_input"] == "rescue"
