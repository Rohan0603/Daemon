"""Tests for ThoughtPool (unified single pool with type filtering + spatial TTL)."""
from __future__ import annotations
import pytest
from src.constants import THOUGHT_POOL_SIZE, THOUGHT_POOL_THRESHOLD, THOUGHT_POOL_REFILL_COUNT


@pytest.fixture
def pool():
    from src.response_pool import ThoughtPool
    p = ThoughtPool(max_size=THOUGHT_POOL_SIZE, threshold=THOUGHT_POOL_THRESHOLD, refill_count=THOUGHT_POOL_REFILL_COUNT)
    return p


def test_draw_by_type_returns_matching_type(pool):
    pool._items = [
        {"type": "observation", "dialogue": "A", "priority": 3},
        {"type": "idle_thought", "dialogue": "B", "priority": 4},
    ]
    result = pool.draw_by_type("idle_thought")
    assert len(result) == 1
    assert result[0]["dialogue"] == "B"


def test_draw_by_type_returns_empty_when_no_match(pool):
    pool._items = [
        {"type": "observation", "dialogue": "A", "priority": 3},
    ]
    result = pool.draw_by_type("typing_reaction")
    assert result == []


def test_context_invalidation_discards_stale(pool):
    pool._items = [
        {"type": "observation", "dialogue": "Stale", "priority": 3, "context_hash": "hash_1"},
        {"type": "observation", "dialogue": "Fresh", "priority": 4, "context_hash": "hash_2"},
    ]
    result = pool.draw_by_type("observation", current_context_hash="hash_2")
    assert len(result) == 1
    assert result[0]["dialogue"] == "Fresh"


def test_context_invalidation_all_stale_returns_empty(pool):
    pool._items = [
        {"type": "observation", "dialogue": "Stale", "priority": 3, "context_hash": "hash_1"},
    ]
    result = pool.draw_by_type("observation", current_context_hash="hash_2")
    assert result == []


def test_item_without_context_hash_always_valid(pool):
    pool._items = [
        {"type": "typing_reaction", "dialogue": "Always valid", "priority": 5},
    ]
    result = pool.draw_by_type("typing_reaction", current_context_hash="any_hash")
    assert len(result) == 1
    assert result[0]["dialogue"] == "Always valid"


def test_draw_by_type_returns_highest_priority_first(pool):
    pool._items = [
        {"type": "idle_thought", "dialogue": "Low", "priority": 1},
        {"type": "idle_thought", "dialogue": "High", "priority": 5},
    ]
    result = pool.draw_by_type("idle_thought")
    assert result[0]["dialogue"] == "High"
