from __future__ import annotations
import json
import logging
import random
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class ThoughtPool(QObject):
    refill_needed = pyqtSignal()
    pool_refilled = pyqtSignal()
    refill_failed = pyqtSignal(str)

    def __init__(self, max_size: int, threshold: int,
                 refill_count: int, parent=None):
        super().__init__(parent)
        self._max_size = max_size
        self._threshold = threshold
        self._refill_count = refill_count
        self._items: list[dict] = []
        self._refilling = False

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
            if item_hash is not None and current_context_hash is not None and item_hash != current_context_hash:
                stale_indices.append(idx)
                continue
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
        tagged = []
        for item in items:
            tagged.append({
                "dialogue": item.get("dialogue", ""),
                "type": item.get("type", "idle_thought"),
                "action": item.get("action", "idle"),
                "target_x": item.get("target_x"),
                "priority": item.get("priority", 3),
            })
        self._items.extend(tagged)
        if len(self._items) > self._max_size:
            self._items = self._items[-self._max_size:]

    def remaining(self) -> int:
        return len(self._items)

    def decay(self):
        for item in self._items:
            item["priority"] = max(1, item.get("priority", 3) - 1)

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
