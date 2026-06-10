from __future__ import annotations
import json
import logging
import random
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class ResponsePool(QObject):
    refill_needed = pyqtSignal(str)
    pool_refilled = pyqtSignal()
    refill_failed = pyqtSignal(str)

    def __init__(self, pool_type: str, max_size: int, threshold: int,
                 refill_count: int, parent=None):
        super().__init__(parent)
        self._pool_type = pool_type
        self._max_size = max_size
        self._threshold = threshold
        self._refill_count = refill_count
        self._items: list[dict] = []
        self._refilling = False

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
            return [item for item, _ in pool_copy][:count]
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
                "action": item.get("action", "idle"),
                "target_x": item.get("target_x"),
                "priority": item.get("priority", 3),
                "pool_type": self._pool_type,
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
        self.refill_needed.emit(self._pool_type)

    def on_refill_result(self, items: list[dict] | None):
        self._refilling = False
        if not items:
            logger.warning("Refill for %s returned no items", self._pool_type)
            self.refill_failed.emit(f"{self._pool_type}: empty response")
            return
        self.add_items(items)
        logger.info("Refill %s: added %d items (pool now %d)",
                     self._pool_type, len(items), len(self._items))
        self.pool_refilled.emit()

    def load_items(self, items: list[dict]):
        self._items = list(items)[:self._max_size]

    def save_items(self) -> list[dict]:
        return list(self._items)
