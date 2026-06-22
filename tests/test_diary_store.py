from __future__ import annotations
import json
import pytest
from pathlib import Path

def _entry_text(entry: dict) -> str:
    return entry["content"]

def test_write_and_read_roundtrip(tmp_path):
    from src.diary_store import DiaryStore
    path = str(tmp_path / "diary.json")
    store = DiaryStore(path)
    store.write([{"content": "a"}, {"content": "b"}, {"content": "c"}], 3)
    result = store.read()
    assert len(result["entries"]) == 3
    assert result["synced"] == 3
    assert [_entry_text(e) for e in result["entries"]] == ["a", "b", "c"]

def test_read_returns_none_on_missing_file(tmp_path):
    from src.diary_store import DiaryStore
    store = DiaryStore(str(tmp_path / "noexist.json"))
    assert store.read() is None

def test_write_is_atomic(tmp_path):
    from src.diary_store import DiaryStore
    path = str(tmp_path / "diary.json")
    tmp_path2 = str(tmp_path / "diary.json.tmp")
    store = DiaryStore(path)
    store.write([{"content": "x"}], 1)
    assert not Path(tmp_path2).exists()

def test_write_caps_entries(tmp_path):
    from src.diary_store import DiaryStore
    path = str(tmp_path / "diary.json")
    store = DiaryStore(path, max_entries=3)
    entries = [{"content": c} for c in ["a", "b", "c", "d", "e"]]
    store.write(entries, 0)
    result = store.read()
    assert [_entry_text(e) for e in result["entries"]] == ["c", "d", "e"]

def test_bak_file_created_on_write(tmp_path):
    from src.diary_store import DiaryStore
    path = str(tmp_path / "diary.json")
    store = DiaryStore(path)
    store.write([{"content": "original"}], 1)
    store.write([{"content": "updated"}], 2)
    bak_path = str(tmp_path / "diary.json.bak")
    assert Path(bak_path).exists()
    bak_data = json.loads(Path(bak_path).read_text(encoding="utf-8"))
    assert bak_data["diary"][0]["content"] == "original"

def test_read_falls_back_to_bak(tmp_path):
    from src.diary_store import DiaryStore
    path = str(tmp_path / "diary.json")
    store = DiaryStore(path)
    store.write([{"content": "initial"}], 0)
    store.write([{"content": "good data"}], 1)
    Path(path).write_text("not valid json", encoding="utf-8")
    # reset instances because otherwise we just read from memory
    from src.brain_store import BrainStore
    BrainStore._instances.clear()
    store2 = DiaryStore(path)
    result = store2.read()
    assert result is not None
    assert result["entries"][0]["content"] == "initial"

def test_prune_removes_oldest(tmp_path):
    from src.diary_store import DiaryStore
    store = DiaryStore(str(tmp_path / "diary.json"), max_entries=5)
    pruned = store.prune(list(range(10)))
    assert pruned == [5, 6, 7, 8, 9]

class TestDiaryStoreEdgeCases:
    def test_write_with_empty_list(self, tmp_path):
        from src.diary_store import DiaryStore
        path = str(tmp_path / "diary.json")
        store = DiaryStore(path)
        store.write([], 0)
        result = store.read()
        assert result == {"entries": [], "synced": 0}

    def test_read_with_both_bak_and_main_corrupt(self, tmp_path):
        from src.diary_store import DiaryStore
        path = str(tmp_path / "diary.json")
        Path(path).write_text("not valid json", encoding="utf-8")
        Path(path + ".bak").write_text("also bad json", encoding="utf-8")
        store = DiaryStore(path)
        assert store.read() == {"entries": [], "synced": 0}

    def test_write_synced_greater_than_len(self, tmp_path):
        from src.diary_store import DiaryStore
        path = str(tmp_path / "diary.json")
        store = DiaryStore(path)
        store.write([{"content": "a"}, {"content": "b"}], 99)
        result = store.read()
        assert result["synced"] == 99

    def test_prune_with_empty_list(self, tmp_path):
        from src.diary_store import DiaryStore
        store = DiaryStore(str(tmp_path / "diary.json"), max_entries=5)
        assert store.prune([]) == []

    def test_read_after_multiple_writes(self, tmp_path):
        from src.diary_store import DiaryStore
        path = str(tmp_path / "diary.json")
        store = DiaryStore(path)
        for i in range(10):
            store.write([{"content": str(i)}], i)
        result = store.read()
        assert result["entries"][0]["content"] == "9"
        assert result["synced"] == 9

    def test_write_large_entry(self, tmp_path):
        from src.diary_store import DiaryStore
        path = str(tmp_path / "diary.json")
        store = DiaryStore(path)
        large_content = "A" * 100000
        store.write([{"content": large_content}], 1)
        result = store.read()
        assert result["entries"][0]["content"] == large_content

class TestDiaryStoreMigration:
    def test_read_migrates_legacy_string_entries(self, tmp_path):
        path = str(tmp_path / "diary.json")
        data = {"version": 2, "diary": ["legacy string 1", "legacy string 2"], "diary_synced": 2}
        Path(path).write_text(json.dumps(data), encoding="utf-8")
        from src.diary_store import DiaryStore
        from src.brain_store import BrainStore
        BrainStore._instances.clear()
        store = DiaryStore(path)
        result = store.read()
        assert len(result["entries"]) == 2
        assert "hash" in result["entries"][0]
        assert result["entries"][0]["content"] == "legacy string 1"

    def test_add_diary_entry_returns_true_on_add(self, tmp_path):
        from src.diary_store import DiaryStore
        path = str(tmp_path / "diary.json")
        store = DiaryStore(path)
        assert store.add_diary_entry("new entry") is True

    def test_add_diary_entry_returns_false_on_duplicate(self, tmp_path):
        from src.diary_store import DiaryStore
        path = str(tmp_path / "diary.json")
        store = DiaryStore(path)
        store.add_diary_entry("duplicate me")
        assert store.add_diary_entry("duplicate me") is False
        assert store.add_diary_entry(" DUPLICATE ME ") is False

    def test_get_entries_returns_copy(self, tmp_path):
        from src.diary_store import DiaryStore
        path = str(tmp_path / "diary.json")
        store = DiaryStore(path)
        store.write([{"content": "test"}], 1)
        entries = store.get_entries()
        entries.append({"content": "hacked"})
        assert len(store.get_entries()) == 1

    def test_bak_read_migrates_legacy_strings(self, tmp_path):
        path = str(tmp_path / "diary.json")
        bak_path = path + ".bak"
        data = {"version": 2, "diary": ["legacy bak"], "diary_synced": 1}
        Path(bak_path).write_text(json.dumps(data), encoding="utf-8")
        Path(path).write_text("invalid", encoding="utf-8")
        from src.diary_store import DiaryStore
        from src.brain_store import BrainStore
        BrainStore._instances.clear()
        store = DiaryStore(path)
        result = store.read()
        assert result is not None
        assert len(result["entries"]) == 1
        assert result["entries"][0]["content"] == "legacy bak"


def test_diary_store_storage_backend_interface(tmp_path):
    from src.diary_store import DiaryStore
    from src.storage_backend import StorageBackend
    
    path = str(tmp_path / "diary.json")
    store = DiaryStore(path)
    
    assert isinstance(store, StorageBackend)
    
    # test count
    assert store.count() == 0
    
    # test set
    assert store.set("ignored_key", "diary content text") is True
    assert store.count() == 1
    
    # get the hash of the entry
    entries = store.get_entries()
    assert len(entries) == 1
    entry_hash = entries[0]["hash"]
    
    # test get
    entry = store.get(entry_hash)
    assert entry is not None
    assert entry["content"] == "diary content text"
    
    # test query
    q_res = store.query()
    assert len(q_res) == 1
    assert q_res[0]["id"] == entry_hash
    assert q_res[0]["content"] == "diary content text"
    
    # test query filter
    q_res_filter = store.query(filter_fn=lambda x: "text" in x["content"])
    assert len(q_res_filter) == 1
    q_res_filter_empty = store.query(filter_fn=lambda x: "nonexistent" in x["content"])
    assert len(q_res_filter_empty) == 0
    
    # test all_entries
    assert len(store.all_entries()) == 1
