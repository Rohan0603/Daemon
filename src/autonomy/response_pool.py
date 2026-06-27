from __future__ import annotations
import json
import logging
import random
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


def _fuzzy_ratio(a: str, b: str) -> float:
    """Simple character-level similarity ratio between 0.0 and 1.0."""
    if not a or not b:
        return 0.0
    set_a = set(a.lower())
    set_b = set(b.lower())
    if not set_a and not set_b:
        return 1.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


class ThoughtPool(QObject):
    refill_needed = pyqtSignal()
    pool_refilled = pyqtSignal()
    refill_failed = pyqtSignal(str)

    def __init__(self, max_size: int, threshold: int,
                 refill_count: int, parent=None,
                 ttl_seconds: int = 300):
        super().__init__(parent)
        self._max_size = max_size
        self._threshold = threshold
        self._refill_count = refill_count
        self._ttl_seconds = ttl_seconds
        self._items: list[dict] = []
        self._refilling = False
        # ── Dialogue dedup cache (per-instance) ──────────
        self._dedup_cache: list[str] = []
        self._dedup_max = 20
        self._dedup_threshold = 0.75

    @property
    def refill_threshold(self) -> int:
        return self._threshold

    @refill_threshold.setter
    def refill_threshold(self, value: int) -> None:
        self._threshold = value

    def _is_repetitive(self, text: str) -> bool:
        """Check if *text* is too similar to recently-seen dialogue."""
        if not text:
            return False
        if text in self._dedup_cache:
            return True
        for existing in self._dedup_cache:
            if _fuzzy_ratio(text, existing) >= self._dedup_threshold:
                return True
        return False

    def _record_dialogue(self, text: str) -> None:
        """Record a dialogue in the dedup cache (bounded)."""
        self._dedup_cache.append(text)
        if len(self._dedup_cache) > self._dedup_max:
            self._dedup_cache.pop(0)

    def draw_by_type(self, target_type: str, current_context_hash: str = None) -> list[dict]:
        if not self._items:
            if not self._refilling:
                self._request_refill()
            return []
        if len(self._items) < self._threshold:
            if not self._refilling:
                self._request_refill()

        best_idx = -1
        best_priority = -1
        stale_indices: list[int] = []

        for idx, item in enumerate(self._items):
            if item.get("type") != target_type:
                continue
            item_hash = item.get("context_hash")
            if item_hash is not None and current_context_hash is not None:
                ih = str(item_hash).lower().strip()
                ch = str(current_context_hash).lower().strip()
                if ih not in ch and ch not in ih:
                    stale_count = item.get("stale_count", 0) + 1
                    item["stale_count"] = stale_count
                    if stale_count >= 3:
                        stale_indices.append(idx)
                    continue
                else:
                    item["stale_count"] = 0
            priority = item.get("priority", 3)
            if priority > best_priority:
                best_priority = priority
                best_idx = idx

        # Remove stale items (reverse order to preserve index validity)
        for idx in reversed(stale_indices):
            self._items.pop(idx)

        if best_idx >= 0:
            # Adjust index after stale removal
            for si in stale_indices:
                if si < best_idx:
                    best_idx -= 1
            item = self._items.pop(best_idx)
            item["last_used"] = datetime.now().isoformat()
            return [item]

        if not self._refilling:
            self._request_refill()
        return []

    def draw(self, count: int = 1) -> list[dict]:
        if not self._items:
            if not self._refilling:
                self._request_refill()
            return []
        if len(self._items) < count + (self._max_size - self._threshold):
            if not self._refilling:
                self._request_refill()
        weights = [max(1, item.get("priority", 3)) for item in self._items]
        total = sum(weights)
        if total == 0:
            pool_copy = list(self._items)
            result = pool_copy[:count]
            self._items = self._items[count:]
            return result
        selected = []
        pool_copy = list(zip(self._items, weights))
        for _ in range(min(count, len(pool_copy))):
            if not pool_copy:
                break
            pick = random.randint(0, total - 1)
            cumulative = 0
            for i, (item, w) in enumerate(pool_copy):
                cumulative += w
                if pick < cumulative:
                    selected.append(item)
                    total -= w
                    pool_copy.pop(i)
                    break
        self._items = [item for item, _ in pool_copy]
        for item in selected:
            item["last_used"] = datetime.now().isoformat()
        return selected

    def add_items(self, items: list[dict]):
        if not items:
            return
        now_dt = datetime.now().isoformat()
        now_ts = datetime.now().timestamp()
        tagged = []
        dedup_skipped = 0
        for item in items:
            dialogue = item.get("dialogue", "")
            # Skip repetitive dialogue (same or very similar to recent entries)
            if dialogue and self._is_repetitive(dialogue):
                dedup_skipped += 1
                logger.debug("Dialogue dedup skipped: '%.60s'", dialogue)
                continue
            if dialogue:
                self._record_dialogue(dialogue)
            tagged.append({
                "dialogue": dialogue,
                "type": item.get("type", "idle_thought"),
                "action": item.get("action", "idle"),
                "target_x": item.get("target_x"),
                "priority": item.get("priority", 3),
                "_created_at": now_ts,
            })
        self._items.extend(tagged)
        if len(self._items) > self._max_size:
            self._items = self._items[-self._max_size:]

    def remaining(self) -> int:
        return len(self._items)

    def decay(self):
        """Priority decay + TTL purge for stale items."""
        if not self._items:
            return
        now = datetime.now()
        cutoff = now.timestamp() - self._ttl_seconds
        # TTL purge: remove items older than ttl_seconds
        fresh = []
        for item in self._items:
            created = item.get("_created_at")
            if created:
                try:
                    if isinstance(created, (int, float)):
                        age_sec = now.timestamp() - created
                    else:
                        created_dt = datetime.fromisoformat(created) if isinstance(created, str) else now
                        age_sec = now.timestamp() - created_dt.timestamp()
                    if age_sec > self._ttl_seconds:
                        continue
                except (ValueError, TypeError):
                    pass
            fresh.append(item)
        purged = len(self._items) - len(fresh)
        if purged:
            logger.debug("TTL purge: removed %d stale items (pool %d -> %d)", purged, len(self._items), len(fresh))
        self._items = fresh
        # Priority decay for remaining items
        for item in self._items:
            item["priority"] = max(1, item.get("priority", 3) - 1)

    def count_by_type(self) -> dict[str, int]:
        """Return dict mapping type -> count for current pool items."""
        counts: dict[str, int] = {}
        for item in self._items:
            t = item.get("type", "unknown")
            counts[t] = counts.get(t, 0) + 1
        return counts

    def _request_refill(self):
        if self._refilling:
            return
        self._refilling = True
        self.refill_needed.emit()

    def on_refill_result(self, items: list[dict] | None, intentional_abort: bool = False):
        self._refilling = False
        if intentional_abort:
            return
        if not items:
            logger.warning("Refill returned no items")
            self.refill_failed.emit("empty response")
            return
        self.add_items(items)
        logger.info("Refill: added %d items (pool now %d)", len(items), len(self._items))
        self.pool_refilled.emit()

    def load_items(self, items: list[dict]):
        self._items = list(items)[:self._max_size]

    def save_items(self) -> list[dict]:
        return list(self._items)


# ── Export public class ───────────────────────────────────────────

__all__ = ["ThoughtPool"]