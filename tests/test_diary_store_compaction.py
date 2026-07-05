"""Tests for DiaryStore compaction (Phase 5 Part A).

Note: test entries use diverse content strings to avoid SequenceMatcher
dedup (DIARY_DEDUP_SIMILARITY=0.85) that blocks very similar entries.
"""
import time
import pytest
from src.diary_store import DiaryStore, calculate_content_hash


def _make_entry(content: str, timestamp: float | None = None) -> dict:
    ts = timestamp if timestamp is not None else time.time()
    return {
        "content": content,
        "timestamp": ts,
        "hash": calculate_content_hash(content),
    }


def _make_store(entries: list[dict]) -> DiaryStore:
    """Create a DiaryStore with pre-populated entries (no file I/O)."""
    store = DiaryStore.__new__(DiaryStore)
    store._brain = type("FakeBrain", (), {"diary": list(entries), "diary_synced": 0,
                                          "_path": "/dev/null", "save": lambda self: None})()
    store._max_entries = 200
    store._has_written = False
    return store


def test_compact_does_nothing_below_threshold():
    """Compact should be a no-op when entries <= max_entries."""
    now = time.time()
    entries = [_make_entry(f"testing the quick brown fox {i}", now - i * 3600) for i in range(5)]
    store = _make_store(entries)
    store.compact(max_entries=150)
    assert len(store.get_entries()) == 5


def test_compact_merges_day_clusters():
    """Day with >3 entries should be replaced by a summary entry."""
    now = time.time()
    entries = [
        _make_entry(f"the quick brown fox jumps over the lazy dog {i}", now - i * 3600)
        for i in range(5)
    ]
    store = _make_store(entries)
    # 5 entries > 4 max_entries, all same day (>3) → compressed to 1 summary
    store.compact(max_entries=4)
    result = store.get_entries()
    assert len(result) == 1
    assert "Diary:" in result[0]["content"]
    assert "entries from" in result[0]["content"]


def test_compact_preserves_recent_entries():
    """Entries on a day with ≤3 should survive compaction."""
    now = time.time()
    # 4 entries from 3 days ago (>3 per day → compressed), 2 from today (≤3 → kept)
    old_entries = [
        _make_entry(f"old entry number {i} about something", now - 3 * 86400 - i * 3600)
        for i in range(4)
    ]
    new_entries = [
        _make_entry(f"fresh thought just now about topic {i}", now - 3600 * i)
        for i in range(2)
    ]
    store = _make_store(old_entries + new_entries)
    # 6 total > 4 max_entries, triggers compaction
    store.compact(max_entries=4)
    result = store.get_entries()
    # Old day (4 entries, >3) → 1 summary; today (2 entries, ≤3) → 2 individual
    assert len(result) == 3
    summaries = [e for e in result if "Diary:" in e["content"]]
    assert len(summaries) == 1
    preserved = [e for e in result if "fresh" in e["content"]]
    assert len(preserved) == 2


def test_compact_idempotent():
    """Calling compact() twice should produce the same result."""
    now = time.time()
    entries = [
        _make_entry(f"distinct sentence pattern variant {i}", now - i * 3600)
        for i in range(6)
    ]
    store = _make_store(entries)
    store.compact(max_entries=4)
    result_first = store.get_entries()
    store.compact(max_entries=4)
    result_second = store.get_entries()
    assert len(result_first) == len(result_second)
    assert result_first == result_second


def test_compact_called_automatically_on_add_high_water():
    """add() should trigger compact() when entries exceed 75% of max."""
    now = time.time()
    entries = [
        _make_entry(f"unique log entry about project alpha phase {i}", now - i * 86400 * 2)
        for i in range(8)
    ]
    store = _make_store(entries)
    store._max_entries = 10
    assert len(store.get_entries()) == 8

    # Add one more — 9 entries, each on its own date (16-day span, 2-day spacing)
    # So none should have >3 per day, compact is no-op
    store.add("brand new thought about something different today")
    assert len(store.get_entries()) == 9


def test_compact_uses_earliest_timestamp():
    """Summary entry should use earliest timestamp from the group."""
    now = time.time()
    entries = [
        _make_entry("first series about coding in python", now),
        _make_entry("second data structures entry about python", now + 100),
        _make_entry("third algorithms sorting entry about trees", now + 200),
        _make_entry("fourth design patterns about cpp factory", now + 300),
    ]
    store = _make_store(entries)
    store.compact(max_entries=3)
    result = store.get_entries()
    assert len(result) == 1
    assert abs(result[0]["timestamp"] - now) < 1.0


def test_compact_multiple_days():
    """Multiple days each with >3 entries should each be summarised."""
    now = time.time()
    entries = []
    for i in range(4):
        entries.append(_make_entry(f"hiking in the mountains adventure {i}", now - 2 * 86400 - i * 3600))
    for i in range(5):
        entries.append(_make_entry(f"cooking italian pasta recipes {i}", now - 86400 - i * 3600))
    store = _make_store(entries)
    # 9 entries > 8 max_entries, triggers compaction
    store.compact(max_entries=8)
    result = store.get_entries()
    summaries = [e for e in result if "Diary:" in e["content"]]
    assert len(summaries) == 2
