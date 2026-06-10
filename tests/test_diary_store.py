from __future__ import annotations
import json
import pytest
from pathlib import Path


def _entry_text(entry: dict) -> str:
    """Helper: extract content from a dict entry."""
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
    assert bak_data["entries"][0]["content"] == "original"


def test_read_falls_back_to_bak(tmp_path):
    from src.diary_store import DiaryStore
    path = str(tmp_path / "diary.json")
    store = DiaryStore(path)
    store.write([{"content": "good data"}], 1)
    Path(path).write_text("not valid json", encoding="utf-8")
    store2 = DiaryStore(path)
    result = store2.read()
    assert result is not None
    assert result["entries"][0]["content"] == "good data"


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
        store.write([{"content": "a"}, {"content": "b"}], 99)
        result = store.read()
        assert len(result["entries"]) == 2
        assert result["synced"] == 99

    def test_prune_with_empty_list(self, tmp_path):
        from src.diary_store import DiaryStore
        store = DiaryStore(str(tmp_path / "diary.json"))
        assert store.prune([]) == []

    def test_read_after_multiple_writes(self, tmp_path):
        from src.diary_store import DiaryStore
        path = str(tmp_path / "diary.json")
        store = DiaryStore(path)
        for i in range(5):
            store.write([{"content": f"entry_{i}"}], i)
            result = store.read()
            assert len(result["entries"]) == 1
            assert result["entries"][0]["content"] == f"entry_{i}"
            assert result["synced"] == i

    def test_write_large_entry(self, tmp_path):
        from src.diary_store import DiaryStore
        path = str(tmp_path / "diary.json")
        store = DiaryStore(path)
        large = "x" * 100000
        store.write([{"content": large}], 1)
        result = store.read()
        assert result["entries"][0]["content"] == large


class TestDiaryStoreMigration:
    """Tests for legacy string-to-dict migration and new encapsulation."""

    def test_read_migrates_legacy_string_entries(self, tmp_path):
        """String entries on disk should be auto-migrated to dicts on read."""
        path = str(tmp_path / "diary.json")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        json.dump({"entries": ["old style", "also old"], "synced": 2},
                  Path(path).open("w", encoding="utf-8"))
        from src.diary_store import DiaryStore
        store = DiaryStore(path)
        result = store.read()
        assert result is not None
        assert len(result["entries"]) == 2
        for entry in result["entries"]:
            assert isinstance(entry, dict)
            assert "content" in entry
            assert "timestamp" in entry
            assert "hash" in entry
        assert result["entries"][0]["content"] == "old style"

    def test_add_diary_entry_returns_true_on_add(self, tmp_path):
        from src.diary_store import DiaryStore
        store = DiaryStore(str(tmp_path / "diary.json"))
        assert store.add_diary_entry("hello world", 1000) is True

    def test_add_diary_entry_returns_false_on_duplicate(self, tmp_path):
        from src.diary_store import DiaryStore
        store = DiaryStore(str(tmp_path / "diary.json"))
        store.add_diary_entry("hello world", 1000)
        assert store.add_diary_entry("Hello World  ", 2000) is False  # same after strip+lower

    def test_add_diary_entry_different_text_is_not_duplicate(self, tmp_path):
        from src.diary_store import DiaryStore
        store = DiaryStore(str(tmp_path / "diary.json"))
        store.add_diary_entry("hello world", 1000)
        assert store.add_diary_entry("goodbye world", 2000) is True

    def test_add_diary_entry_200_cap(self, tmp_path):
        from src.diary_store import DiaryStore
        store = DiaryStore(str(tmp_path / "diary.json"), max_entries=3)
        for i in range(5):
            store.add_diary_entry(f"entry_{i}", i)
        entries = store.get_entries()
        assert len(entries) == 3
        assert entries[-1]["content"] == "entry_4"
        assert entries[0]["content"] == "entry_2"

    def test_get_entries_returns_copy(self, tmp_path):
        from src.diary_store import DiaryStore
        store = DiaryStore(str(tmp_path / "diary.json"))
        store.add_diary_entry("test", 1000)
        entries = store.get_entries()
        entries.pop()
        assert len(store.get_entries()) == 1  # original unchanged

    def test_write_accepts_legacy_strings(self, tmp_path):
        """write() should accept list[str] and auto-convert."""
        from src.diary_store import DiaryStore
        path = str(tmp_path / "diary.json")
        store = DiaryStore(path)
        store.write(["a", "b"], 2)
        result = store.read()
        assert result is not None
        assert result["entries"][0]["content"] == "a"
        assert result["entries"][1]["content"] == "b"
        assert result["synced"] == 2

    def test_content_hash_stable(self, tmp_path):
        from src.diary_store import calculate_content_hash
        h1 = calculate_content_hash("  Hello World  ")
        h2 = calculate_content_hash("hello world")
        assert h1 == h2  # strip + lower

    def test_bak_read_migrates_legacy_strings(self, tmp_path):
        """Backup file with legacy strings should also be migrated."""
        path = str(tmp_path / "diary.json")
        bak_path = path + ".bak"
        Path(path).write_text("corrupt", encoding="utf-8")
        json.dump({"entries": ["legacy bak"], "synced": 1},
                  Path(bak_path).open("w", encoding="utf-8"))
        from src.diary_store import DiaryStore
        store = DiaryStore(path)
        result = store.read()
        assert result is not None
        assert result["entries"][0]["content"] == "legacy bak"
