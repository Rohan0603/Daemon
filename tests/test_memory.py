import json
import pytest
from pathlib import Path


def _make_memory(tmp_path):
    from src.memory import Memory
    path = str(tmp_path / "memory.json")
    return Memory(path=path), path


def test_remember_and_recall(tmp_path):
    mem, _ = _make_memory(tmp_path)
    mem.remember("name", "Ponna")
    mem.remember("language", "Python")
    assert mem.recall("name") == "Ponna"
    assert mem.recall("language") == "Python"


def test_recall_missing_returns_none(tmp_path):
    mem, _ = _make_memory(tmp_path)
    assert mem.recall("nonexistent") is None


def test_forget_existing(tmp_path):
    mem, _ = _make_memory(tmp_path)
    mem.remember("key", "value")
    assert mem.forget("key") is True
    assert mem.recall("key") is None


def test_forget_missing(tmp_path):
    mem, _ = _make_memory(tmp_path)
    assert mem.forget("nope") is False


def test_get_all(tmp_path):
    mem, _ = _make_memory(tmp_path)
    mem.remember("a", "1")
    mem.remember("b", "2")
    assert mem.get_all() == {"a": "1", "b": "2"}


def test_get_all_returns_copy(tmp_path):
    mem, _ = _make_memory(tmp_path)
    mem.remember("x", "y")
    d = mem.get_all()
    d["new"] = "value"
    assert "new" not in mem.get_all()


def test_persistence_across_instances(tmp_path):
    mem1, path = _make_memory(tmp_path)
    mem1.remember("persist", "works")
    del mem1

    from src.memory import Memory
    mem2 = Memory(path=path)
    assert mem2.recall("persist") == "works"


def test_corrupt_file_returns_empty(tmp_path):
    from src.memory import Memory
    path = str(tmp_path / "corrupt.json")
    with open(path, "w") as f:
        f.write("{{{ not json")
    mem = Memory(path=path)
    assert mem.get_all() == {}


def test_missing_file_returns_empty(tmp_path):
    from src.memory import Memory
    path = str(tmp_path / "noexist.json")
    mem = Memory(path=path)
    assert mem.get_all() == {}


def test_context_block_with_facts(tmp_path):
    mem, _ = _make_memory(tmp_path)
    mem.remember("name", "Test")
    block = mem.get_context_block()
    assert "name" in block
    assert "Test" in block
    assert "Daemon remembers" in block


def test_context_block_empty_when_no_facts(tmp_path):
    mem, _ = _make_memory(tmp_path)
    assert mem.get_context_block() == ""


def test_context_block_respects_max_facts(tmp_path):
    mem, _ = _make_memory(tmp_path)
    for i in range(10):
        mem.remember(f"k{i}", f"v{i}")
    block = mem.get_context_block(max_facts=3)
    assert block.count("k") == 3


def test_update_existing_key(tmp_path):
    mem, _ = _make_memory(tmp_path)
    mem.remember("color", "blue")
    mem.remember("color", "red")
    assert mem.recall("color") == "red"


def test_atomic_save(tmp_path):
    mem, path = _make_memory(tmp_path)
    mem.remember("safe", "yes")
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    assert raw["facts"]["safe"] == "yes"


def test_save_is_callable(tmp_path):
    from src.memory import Memory
    m = Memory(path=str(tmp_path / "mem.json"))
    m.remember("k", "v")
    m.save()  # must not raise
    data = json.loads((tmp_path / "mem.json").read_text())
    assert data["facts"]["k"] == "v"


def test_remember_marks_dirty_when_coalescer_provided(tmp_path):
    from unittest.mock import MagicMock
    from src.memory import Memory
    m = Memory(path=str(tmp_path / "mem.json"))
    coalescer = MagicMock()
    m.remember("k", "v", coalescer=coalescer)
    coalescer.mark_dirty.assert_called_once_with("memory")
    assert m.recall("k") == "v"


def test_forget_marks_dirty_when_coalescer_provided(tmp_path):
    from unittest.mock import MagicMock
    from src.memory import Memory
    m = Memory(path=str(tmp_path / "mem.json"))
    m.remember("k", "v")
    coalescer = MagicMock()
    assert m.forget("k", coalescer=coalescer) is True
    coalescer.mark_dirty.assert_called_once_with("memory")
    assert m.recall("k") is None


def test_bak_file_created_on_save(tmp_path):
    from src.memory import Memory
    path = str(tmp_path / "mem.json")
    mem = Memory(path=path)
    mem.remember("key1", "val1")
    mem.save()
    mem.remember("key2", "val2")
    mem.save()
    bak_path = path + ".bak"
    assert Path(bak_path).exists()


def test_load_falls_back_to_bak_when_main_corrupt(tmp_path):
    from src.memory import Memory
    path = str(tmp_path / "mem.json")
    mem = Memory(path=path)
    mem.remember("rescue", "me")
    mem.save()
    Path(path).write_text("garbage", encoding="utf-8")
    mem2 = Memory(path=path)
    assert mem2.recall("rescue") == "me"


class TestMemoryEdgeCases:
    def test_remember_empty_string_key(self, tmp_path):
        from src.memory import Memory
        mem = Memory(path=str(tmp_path / "mem.json"))
        mem.remember("", "empty_key_value")
        assert mem.recall("") == "empty_key_value"

    def test_remember_unicode_value(self, tmp_path):
        from src.memory import Memory
        mem = Memory(path=str(tmp_path / "mem.json"))
        mem.remember("greeting", "héllo 🌍 wörld 👋")
        assert mem.recall("greeting") == "héllo 🌍 wörld 👋"

    def test_remember_none_value(self, tmp_path):
        from src.memory import Memory
        mem = Memory(path=str(tmp_path / "mem.json"))
        mem.remember("key", "None")
        assert mem.recall("key") == "None"

    def test_remember_very_long_value(self, tmp_path):
        from src.memory import Memory
        mem = Memory(path=str(tmp_path / "mem.json"))
        long_val = "x" * 10001
        mem.remember("long", long_val)
        assert mem.recall("long") == long_val

    def test_forget_marks_empty_state(self, tmp_path):
        from src.memory import Memory
        mem = Memory(path=str(tmp_path / "mem.json"))
        mem.remember("a", "1")
        mem.remember("b", "2")
        mem.forget("a")
        mem.forget("b")
        assert mem.get_all() == {}

    def test_get_context_block_max_facts_zero(self, tmp_path):
        from src.memory import Memory
        mem = Memory(path=str(tmp_path / "mem.json"))
        mem.remember("k", "v")
        assert mem.get_context_block(max_facts=0) == ""

    def test_save_no_data_does_not_crash(self, tmp_path):
        from src.memory import Memory
        mem = Memory(path=str(tmp_path / "mem.json"))
        mem.save()

    def test_bak_file_restores_on_save_failure(self, tmp_path):
        from src.memory import Memory
        from pathlib import Path
        path = str(tmp_path / "mem.json")
        mem = Memory(path=path)
        mem.remember("rescue", "me")
        mem.save()
        Path(path).unlink()
        Path(path).mkdir()
        mem2 = Memory(path=path)
        assert mem2.recall("rescue") == "me"

    def test_get_context_block_formatted_correctly(self, tmp_path):
        from src.memory import Memory
        mem = Memory(path=str(tmp_path / "mem.json"))
        mem.remember("name", "Daemon")
        mem.remember("color", "blue")
        block = mem.get_context_block()
        lines = block.split("\n")
        assert lines[0] == "## What Daemon remembers about you:"
        assert lines[1] == "- name: Daemon"
        assert lines[2] == "- color: blue"


def test_memory_storage_backend_interface(tmp_path):
    from src.memory import Memory
    from src.storage_backend import StorageBackend
    
    path = str(tmp_path / "mem.json")
    mem = Memory(path=path)
    
    assert isinstance(mem, StorageBackend)
    
    # test count
    assert mem.count() == 0
    
    # test set/get
    assert mem.set("user_profession", "coder") is True
    assert mem.get("user_profession") == "coder"
    assert mem.count() == 1
    
    # test query
    results = mem.query()
    assert len(results) == 1
    assert results[0] == {"id": "user_profession", "content": "coder", "timestamp": ""}
    
    # test query with filter
    results_filter = mem.query(filter_fn=lambda x: x["id"] == "user_profession")
    assert len(results_filter) == 1
    results_filter_empty = mem.query(filter_fn=lambda x: x["id"] == "nonexistent")
    assert len(results_filter_empty) == 0
    
    # test all_entries
    assert mem.all_entries() == [{"id": "user_profession", "content": "coder", "timestamp": ""}]
