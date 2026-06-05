"""Tests for AutonomousResponseManager (multi-pool)."""
from __future__ import annotations
import json
import os
import sys
import tempfile
from pathlib import Path
import pytest
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QApplication

from src.constants import (
    JOKES_BLACKMAIL_POOL_SIZE, JOKES_BLACKMAIL_POOL_THRESHOLD,
    JOKES_BLACKMAIL_POOL_REFILL_COUNT,
    SYSTEM_POOL_SIZE, SYSTEM_POOL_THRESHOLD, SYSTEM_POOL_REFILL_COUNT,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    return app


def _make_manager(qapp):
    from src.response_manager import AutonomousResponseManager
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w")
    tmp.write("{}")
    tmp.close()
    return AutonomousResponseManager(cache_path=tmp.name, write_coalescer=MagicMock())


def test_constructor_creates_two_pools(qapp):
    m = _make_manager(qapp)
    assert "jokes_blackmail" in m._pools
    assert "system" in m._pools
    assert len(m._pools) == 2


def test_jokes_pool_has_correct_config(qapp):
    m = _make_manager(qapp)
    p = m._pools["jokes_blackmail"]
    assert p._max_size == JOKES_BLACKMAIL_POOL_SIZE
    assert p._threshold == JOKES_BLACKMAIL_POOL_THRESHOLD
    assert p._refill_count == JOKES_BLACKMAIL_POOL_REFILL_COUNT


def test_system_pool_has_correct_config(qapp):
    m = _make_manager(qapp)
    p = m._pools["system"]
    assert p._max_size == SYSTEM_POOL_SIZE
    assert p._threshold == SYSTEM_POOL_THRESHOLD
    assert p._refill_count == SYSTEM_POOL_REFILL_COUNT


def test_draw_from_jokes_pool(qapp):
    m = _make_manager(qapp)
    m._pools["jokes_blackmail"]._items = [
        {"dialogue": "joke1", "action": "idle", "priority": 3, "pool_type": "jokes_blackmail"}
    ]
    items = m.draw("jokes_blackmail", 1)
    assert len(items) == 1
    assert items[0]["dialogue"] == "joke1"
    assert m.remaining("jokes_blackmail") == 0


def test_draw_from_system_pool(qapp):
    m = _make_manager(qapp)
    m._pools["system"]._items = [
        {"dialogue": "sys1", "action": "idle", "priority": 4, "pool_type": "system"}
    ]
    items = m.draw("system", 1)
    assert len(items) == 1
    assert items[0]["dialogue"] == "sys1"


def test_draw_returns_empty_when_empty(qapp):
    m = _make_manager(qapp)
    assert m.draw("jokes_blackmail", 1) == []
    assert m.draw("system", 1) == []


def test_remaining_counts(qapp):
    m = _make_manager(qapp)
    m._pools["jokes_blackmail"]._items = [{"dialogue": "a", "action": "idle", "priority": 3}]
    m._pools["system"]._items = [{"dialogue": "b", "action": "idle", "priority": 4}]
    assert m.remaining("jokes_blackmail") == 1
    assert m.remaining("system") == 1


def test_priority_decay_reduces_priority(qapp):
    m = _make_manager(qapp)
    m._pools["jokes_blackmail"]._items = [
        {"dialogue": "a", "action": "idle", "priority": 5},
        {"dialogue": "b", "action": "idle", "priority": 3},
    ]
    m.decay_all()
    assert m._pools["jokes_blackmail"]._items[0]["priority"] == 4
    assert m._pools["jokes_blackmail"]._items[1]["priority"] == 2


def test_priority_decay_minimum_one(qapp):
    m = _make_manager(qapp)
    m._pools["jokes_blackmail"]._items = [
        {"dialogue": "a", "action": "idle", "priority": 1},
    ]
    m.decay_all()
    assert m._pools["jokes_blackmail"]._items[0]["priority"] == 1


def test_draw_uses_weighted_priority(qapp):
    m = _make_manager(qapp)
    high_count = 0
    total = 200
    for _ in range(total):
        m._pools["jokes_blackmail"]._items = [
            {"dialogue": "high", "action": "idle", "priority": 5},
            {"dialogue": "low", "action": "idle", "priority": 1},
        ]
        items = m.draw("jokes_blackmail", 1)
        if items[0]["dialogue"] == "high":
            high_count += 1
    assert high_count > total * 0.6


def test_add_items_caps_at_max_size(qapp):
    m = _make_manager(qapp)
    items = [{"dialogue": f"j{i}", "action": "idle", "priority": 3} for i in range(JOKES_BLACKMAIL_POOL_SIZE + 25)]
    m.add_items("jokes_blackmail", items)
    assert m.remaining("jokes_blackmail") == JOKES_BLACKMAIL_POOL_SIZE


def test_prime_from_user_response_feeds_both_pools(qapp):
    m = _make_manager(qapp)
    m.prime_from_user_response(
        joke_items=[{"dialogue": "joke1", "action": "idle", "priority": 4}],
        system_items=[{"dialogue": "sys1", "action": "idle", "priority": 5}],
    )
    assert m.remaining("jokes_blackmail") == 1
    assert m.remaining("system") == 1
    assert m._pools["jokes_blackmail"]._items[0]["dialogue"] == "joke1"
    assert m._pools["system"]._items[0]["dialogue"] == "sys1"


def test_stop_saves_both_pools(qapp):
    from src.response_manager import AutonomousResponseManager
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w")
    tmp.write("{}")
    tmp.close()
    m = AutonomousResponseManager(cache_path=tmp.name, write_coalescer=MagicMock())
    m.add_items("jokes_blackmail", [{"dialogue": "j1", "action": "idle", "priority": 3}])
    m.add_items("system", [{"dialogue": "s1", "action": "idle", "priority": 4}])
    m.stop()
    with open(tmp.name, encoding="utf-8") as f:
        data = json.load(f)
    assert len(data["pools"]["jokes_blackmail"]["items"]) == 1
    assert len(data["pools"]["system"]["items"]) == 1
    assert data["version"] == 2


def test_load_restores_both_pools(qapp):
    from src.response_manager import AutonomousResponseManager
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w")
    json.dump({
        "version": 2,
        "pools": {
            "jokes_blackmail": {
                "items": [{"dialogue": "j1", "action": "idle", "priority": 3}],
                "last_refill": "2026-06-07T12:00:00"
            },
            "system": {
                "items": [{"dialogue": "s1", "action": "idle", "priority": 4}],
                "last_refill": "2026-06-07T12:00:00"
            }
        }
    }, tmp)
    tmp.close()
    m = AutonomousResponseManager(cache_path=tmp.name, write_coalescer=MagicMock())
    assert m.remaining("jokes_blackmail") == 1
    assert m.remaining("system") == 1


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


def test_items_persist_and_restore(tmp_path):
    from unittest.mock import MagicMock
    from src.response_manager import AutonomousResponseManager
    cache_path = str(tmp_path / "cache.json")
    wc = MagicMock()
    arm1 = AutonomousResponseManager(cache_path, wc)
    arm1.add_items("jokes_blackmail", [
        {"dialogue": "test joke", "action": "idle", "priority": 5}
    ])
    arm1.stop()
    arm2 = AutonomousResponseManager(cache_path, wc)
    assert arm2.remaining("jokes_blackmail") >= 1


def test_load_drops_old_items(tmp_path):
    import json
    from pathlib import Path
    from unittest.mock import MagicMock
    from src.response_manager import AutonomousResponseManager
    cache_path = str(tmp_path / "cache.json")
    old_data = {
        "version": 2,
        "pools": {
            "jokes_blackmail": {
                "items": [
                    {"dialogue": "old", "action": "idle", "priority": 3,
                     "pool_type": "jokes_blackmail", "last_used": "2020-01-01T00:00:00"},
                    {"dialogue": "recent", "action": "shake", "priority": 5,
                     "pool_type": "jokes_blackmail", "last_used": "2099-12-31T00:00:00"},
                ]
            },
            "system": {"items": []}
        }
    }
    Path(cache_path).write_text(json.dumps(old_data), encoding="utf-8")
    wc = MagicMock()
    arm = AutonomousResponseManager(cache_path, wc)
    # Old item (2020) should be dropped, recent item kept
    remaining = arm.remaining("jokes_blackmail")
    assert remaining <= 1
    if remaining == 1:
        items = arm.draw("jokes_blackmail", 1)
        assert items[0]["dialogue"] == "recent"


class TestResponseManagerEdgeCases:
    def test_add_items_empty_list(self, qapp):
        from src.response_manager import ResponsePool
        pool = ResponsePool("test", max_size=10, threshold=7, refill_count=5)
        pool.add_items([])
        assert pool.remaining() == 0

    def test_prime_from_user_response_empty_both(self, qapp):
        m = _make_manager(qapp)
        m.prime_from_user_response([], [])
        assert m.remaining("jokes_blackmail") == 0
        assert m.remaining("system") == 0

    def test_draw_with_n_gt_available(self, qapp):
        from src.response_manager import ResponsePool
        pool = ResponsePool("test", max_size=10, threshold=7, refill_count=5)
        pool._items = [
            {"dialogue": "a", "action": "idle", "priority": 3},
            {"dialogue": "b", "action": "idle", "priority": 3},
        ]
        result = pool.draw(count=5)
        assert len(result) == 2

    def test_save_with_empty_pools(self, qapp, tmp_path):
        from pathlib import Path
        import json
        from unittest.mock import MagicMock
        from src.response_manager import AutonomousResponseManager
        cache_path = str(tmp_path / "cache.json")
        Path(cache_path).write_text("{}", encoding="utf-8")
        arm = AutonomousResponseManager(cache_path, MagicMock())
        arm.stop()
        data = json.loads(Path(cache_path).read_text(encoding="utf-8"))
        assert data["version"] == 2
        assert data["pools"]["jokes_blackmail"]["items"] == []
        assert data["pools"]["system"]["items"] == []

    def test_load_v1_format_migration(self, qapp, tmp_path):
        from pathlib import Path
        import json
        from unittest.mock import MagicMock
        from src.response_manager import AutonomousResponseManager
        cache_path = str(tmp_path / "cache.json")
        v1_data = {
            "jokes_blackmail": [{"dialogue": "old", "action": "idle", "priority": 3}],
            "system": [{"dialogue": "old sys", "action": "idle", "priority": 4}],
        }
        Path(cache_path).write_text(json.dumps(v1_data), encoding="utf-8")
        arm = AutonomousResponseManager(cache_path, MagicMock())
        assert arm.remaining("jokes_blackmail") == 0
        assert arm.remaining("system") == 0

    def test_stop_called_twice(self, qapp):
        m = _make_manager(qapp)
        m.stop()
        m.stop()

    def test_pool_type_tag_auto_assigned(self, qapp):
        from src.response_manager import ResponsePool
        pool = ResponsePool("jokes_blackmail", max_size=10, threshold=7, refill_count=5)
        pool.add_items([{"dialogue": "test", "action": "idle"}])
        assert pool._items[0]["pool_type"] == "jokes_blackmail"
