from __future__ import annotations
import json
import pytest
from pathlib import Path


def test_write_and_read_roundtrip(tmp_path):
    from src.diary_store import DiaryStore
    path = str(tmp_path / "diary.json")
    store = DiaryStore(path)
    store.write(["a", "b", "c"], 3)
    result = store.read()
    assert result == {"entries": ["a", "b", "c"], "synced": 3}


def test_read_returns_none_on_missing_file(tmp_path):
    from src.diary_store import DiaryStore
    store = DiaryStore(str(tmp_path / "noexist.json"))
    assert store.read() is None


def test_write_is_atomic(tmp_path):
    from src.diary_store import DiaryStore
    path = str(tmp_path / "diary.json")
    tmp_path2 = str(tmp_path / "diary.json.tmp")
    store = DiaryStore(path)
    store.write(["x"], 1)
    assert not Path(tmp_path2).exists()


def test_write_caps_entries(tmp_path):
    from src.diary_store import DiaryStore
    path = str(tmp_path / "diary.json")
    store = DiaryStore(path, max_entries=3)
    store.write(["a", "b", "c", "d", "e"], 0)
    result = store.read()
    assert result["entries"] == ["c", "d", "e"]


def test_bak_file_created_on_write(tmp_path):
    from src.diary_store import DiaryStore
    path = str(tmp_path / "diary.json")
    store = DiaryStore(path)
    store.write(["original"], 1)
    store.write(["updated"], 2)
    bak_path = str(tmp_path / "diary.json.bak")
    assert Path(bak_path).exists()
    bak_data = json.loads(Path(bak_path).read_text(encoding="utf-8"))
    assert bak_data["entries"] == ["original"]


def test_read_falls_back_to_bak(tmp_path):
    from src.diary_store import DiaryStore
    path = str(tmp_path / "diary.json")
    store = DiaryStore(path)
    store.write(["good data"], 1)
    Path(path).write_text("not valid json", encoding="utf-8")
    store2 = DiaryStore(path)
    result = store2.read()
    assert result is not None
    assert result["entries"] == ["good data"]


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
        assert store.read() is None

    def test_write_synced_greater_than_len(self, tmp_path):
        from src.diary_store import DiaryStore
        path = str(tmp_path / "diary.json")
        store = DiaryStore(path)
        store.write(["a", "b"], 99)
        result = store.read()
        assert result == {"entries": ["a", "b"], "synced": 99}

    def test_prune_with_empty_list(self, tmp_path):
        from src.diary_store import DiaryStore
        store = DiaryStore(str(tmp_path / "diary.json"))
        assert store.prune([]) == []

    def test_read_after_multiple_writes(self, tmp_path):
        from src.diary_store import DiaryStore
        path = str(tmp_path / "diary.json")
        store = DiaryStore(path)
        for i in range(5):
            store.write([f"entry_{i}"], i)
            result = store.read()
            assert result == {"entries": [f"entry_{i}"], "synced": i}

    def test_write_large_entry(self, tmp_path):
        from src.diary_store import DiaryStore
        path = str(tmp_path / "diary.json")
        store = DiaryStore(path)
        large = "x" * 100000
        store.write([large], 1)
        result = store.read()
        assert result["entries"][0] == large
