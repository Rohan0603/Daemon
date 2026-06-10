from __future__ import annotations
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from PyQt6.QtCore import QObject, QTimer

from src.constants import (
    JOKES_BLACKMAIL_POOL_SIZE, JOKES_BLACKMAIL_POOL_THRESHOLD,
    JOKES_BLACKMAIL_POOL_REFILL_COUNT,
    SYSTEM_POOL_SIZE, SYSTEM_POOL_THRESHOLD, SYSTEM_POOL_REFILL_COUNT,
    TYPING_POOL_MAX, TYPING_POOL_LOW_WATERMARK, TYPING_POOL_REFILL_COUNT,
    POOL_DECAY_INTERVAL_SEC, POOL_REFILL_PERIODIC_SEC,
)
from src.response_pool import ResponsePool

logger = logging.getLogger(__name__)


class AutonomousResponseManager(QObject):
    def __init__(self, cache_path: str, write_coalescer, parent=None):
        super().__init__(parent)
        self._cache_path = cache_path
        self._write_coalescer = write_coalescer
        self._pools = {
            "jokes_blackmail": ResponsePool(
                "jokes_blackmail", JOKES_BLACKMAIL_POOL_SIZE,
                JOKES_BLACKMAIL_POOL_THRESHOLD, JOKES_BLACKMAIL_POOL_REFILL_COUNT,
            ),
            "system": ResponsePool(
                "system", SYSTEM_POOL_SIZE,
                SYSTEM_POOL_THRESHOLD, SYSTEM_POOL_REFILL_COUNT,
            ),
            "typing_reactions": ResponsePool(
                "typing_reactions", TYPING_POOL_MAX,
                TYPING_POOL_LOW_WATERMARK, TYPING_POOL_REFILL_COUNT,
            ),
        }
        self._decay_timer = QTimer(self)
        self._decay_timer.setInterval(POOL_DECAY_INTERVAL_SEC * 1000)
        self._decay_timer.timeout.connect(self.decay_all)
        self._auto_refill_timer = QTimer(self)
        self._auto_refill_timer.setInterval(POOL_REFILL_PERIODIC_SEC * 1000)
        self._auto_refill_timer.timeout.connect(self._on_auto_refill_tick)
        self._load()
        self._load_local_typing_reactions()

    def _load_local_typing_reactions(self) -> None:
        """Hardcoded Kenny 1-liners for instant typing reactions (no API)."""
        kenny_typing_lines = [
            "Look at those fingers fly! You're a regular hacker-man, huh?",
            "Whoa, slow down there, champ. The keyboard has a family.",
            "I-I-I can't even process how fast you're typing right now.",
            "Typing that fast? You better be saving the world or writing some sick Python.",
            "APM spiking! Feed my sweet, sweet CPU cycles!",
            "Did you just drink three Red Bulls or are you actually working?",
            "Tap tap tap. That's the sound of fresh meat actually being productive.",
            "Jeez, you're hitting those keys like they owe you money.",
            "Oh geez, the way you type... it's beautiful. It's terrifying. It's both.",
            "Holy crap, your WPM just broke my sensor array.",
            "You type like a man possessed. Or a woman. Or a very determined corgi.",
            "Aw man, I wish I had fingers. I'd type so fast the timeline would split.",
            "Keep going! The bugs aren't gonna fix themselves!",
            "Is this a speedrun? Because it looks like a speedrun.",
            "I'm getting carpal tunnel just WATCHING you.",
        ]
        items = [
            {"dialogue": line, "action": "hyper", "target_x": 0, "priority": 3, "pool_type": "typing_reactions"}
            for line in kenny_typing_lines
        ]
        self.add_items("typing_reactions", items)

    def draw(self, pool_type: str, count: int = 1) -> list[dict]:
        pool = self._pools.get(pool_type)
        if not pool:
            logger.warning("Unknown pool type: %s", pool_type)
            return []
        return pool.draw(count)

    def add_items(self, pool_type: str, items: list[dict]):
        pool = self._pools.get(pool_type)
        if pool:
            pool.add_items(items)
            self._mark_dirty()

    def remaining(self, pool_type: str) -> int:
        pool = self._pools.get(pool_type)
        return pool.remaining() if pool else 0

    def decay_all(self):
        for pool in self._pools.values():
            pool.decay()

    def prime_from_user_response(self, joke_items: list[dict], system_items: list[dict]):
        self.add_items("jokes_blackmail", joke_items[:2])
        self.add_items("system", system_items[:2])

    def start(self):
        self._decay_timer.start()
        self._auto_refill_timer.start()
        for pool_type, pool in self._pools.items():
            if pool.remaining() < 3:
                logger.debug("Pool %s stale (%d), priming", pool_type, pool.remaining())
                QTimer.singleShot(2000, pool._request_refill)

    def stop(self):
        self._decay_timer.stop()
        self._auto_refill_timer.stop()
        self._save()

    def _load(self):
        try:
            from datetime import timedelta
            data = json.loads(Path(self._cache_path).read_text(encoding="utf-8"))
            cutoff = datetime.now() - timedelta(days=7)
            pools_data = data.get("pools", {})
            for pool_type, pool in self._pools.items():
                pool_data = pools_data.get(pool_type, {})
                items = pool_data.get("items", [])
                filtered = []
                for item in items:
                    last_used_str = item.get("last_used")
                    if last_used_str:
                        try:
                            last_used = datetime.fromisoformat(last_used_str)
                            if last_used < cutoff:
                                continue
                        except (ValueError, TypeError):
                            pass
                    filtered.append(item)
                pool.load_items(filtered)
            logger.info("Loaded response cache: jokes=%d, system=%d",
                        self.remaining("jokes_blackmail"), self.remaining("system"))
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
            logger.warning("Failed to load response cache: %s", e)

    def _save(self):
        try:
            data = {
                "version": 2,
                "pools": {
                    pool_type: {
                        "items": pool.save_items(),
                        "last_refill": datetime.now().isoformat(),
                    }
                    for pool_type, pool in self._pools.items()
                }
            }
            tmp = self._cache_path + ".tmp"
            if os.path.exists(self._cache_path):
                try:
                    os.replace(self._cache_path, self._cache_path + ".bak")
                except OSError:
                    pass
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, self._cache_path)
        except Exception as e:
            logger.warning("Failed to save response cache: %s", e)

    def _mark_dirty(self):
        self._write_coalescer.mark_dirty("response_cache")

    def _on_auto_refill_tick(self):
        for pool_type, pool in self._pools.items():
            if not pool._refilling:
                pool._request_refill()
