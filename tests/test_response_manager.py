"""Tests for AutonomousResponseManager (single ThoughtPool)."""
from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
import pytest
from unittest.mock import MagicMock

from src.constants import THOUGHT_POOL_SIZE, THOUGHT_POOL_THRESHOLD, THOUGHT_POOL_REFILL_COUNT


def _make_manager(qapp):
    from src.response_manager import AutonomousResponseManager
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w")
    tmp.write("{}")
    tmp.close()
    return AutonomousResponseManager(cache_path=tmp.name, write_coalescer=MagicMock())


def test_constructor_creates_single_thought_pool(qapp):
    m = _make_manager(qapp)
    assert hasattr(m, "thought_pool")
    from src.response_pool import ThoughtPool
    assert isinstance(m.thought_pool, ThoughtPool)


def test_thought_pool_has_correct_config(qapp):
    m = _make_manager(qapp)
    p = m.thought_pool
    assert p._max_size == THOUGHT_POOL_SIZE
    assert p._threshold == THOUGHT_POOL_THRESHOLD
    assert p._refill_count == THOUGHT_POOL_REFILL_COUNT


def test_draw_returns_item(qapp):
    m = _make_manager(qapp)
    m.thought_pool._items = [
        {"type": "idle_thought", "dialogue": "hello", "priority": 3}
    ]
    items = m.thought_pool.draw_by_type("idle_thought")
    assert len(items) == 1
    assert items[0]["dialogue"] == "hello"
    assert m.thought_pool.remaining() == 0


def test_draw_returns_empty_when_no_type_match(qapp):
    m = _make_manager(qapp)
    m.thought_pool._items = [
        {"type": "observation", "dialogue": "obs", "priority": 3}
    ]
    items = m.thought_pool.draw_by_type("typing_reaction")
    assert items == []


def test_add_items(qapp):
    m = _make_manager(qapp)
    before = m.thought_pool.remaining()
    m.add_items([
        {"dialogue": "test", "type": "idle_thought", "priority": 3}
    ])
    expected = min(before + 1, m.thought_pool._max_size)
    assert m.thought_pool.remaining() == expected


def test_decay_reduces_priority(qapp):
    m = _make_manager(qapp)
    m.thought_pool._items = [
        {"type": "idle_thought", "dialogue": "a", "priority": 5},
        {"type": "observation", "dialogue": "b", "priority": 3},
    ]
    m.decay_all()
    assert m.thought_pool._items[0]["priority"] == 4
    assert m.thought_pool._items[1]["priority"] == 2


def test_stop_saves_pool(qapp):
    from src.response_manager import AutonomousResponseManager
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w")
    tmp.write("{}")
    tmp.close()
    m = AutonomousResponseManager(cache_path=tmp.name, write_coalescer=MagicMock())
    before = len(m.thought_pool.save_items())
    m.add_items([{"type": "idle_thought", "dialogue": "j1", "priority": 3}])
    m.stop()
    with open(tmp.name, encoding="utf-8") as f:
        data = json.load(f)
    expected = min(before + 1, m.thought_pool._max_size)
    assert len(data["pools"]["thought_pool"]["items"]) == expected
    assert data["version"] == 2


def test_load_restores_pool(qapp):
    from src.response_manager import AutonomousResponseManager
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w")
    json.dump({
        "version": 2,
        "pools": {
            "thought_pool": {
                "items": [{"type": "idle_thought", "dialogue": "j1", "priority": 3}],
                "last_refill": "2026-06-07T12:00:00"
            }
        }
    }, tmp)
    tmp.close()
    m = AutonomousResponseManager(cache_path=tmp.name, write_coalescer=MagicMock())
    # Pool should contain the loaded item among seeded entries
    items = m.thought_pool.save_items()
    loaded = [i for i in items if i.get("dialogue") == "j1"]
    assert len(loaded) == 1
    assert len(items) > 1  # seeds loaded alongside


def test_stop_called_twice(qapp):
    m = _make_manager(qapp)
    m.stop()
    m.stop()


def test_save_is_atomic(tmp_path):
    from pathlib import Path
    from unittest.mock import MagicMock
    from src.response_manager import AutonomousResponseManager
    cache_path = str(tmp_path / "cache.json")
    wc = MagicMock()
    arm = AutonomousResponseManager(cache_path, wc)
    arm._save()
    assert not Path(cache_path + ".tmp").exists()
    assert Path(cache_path).exists()
