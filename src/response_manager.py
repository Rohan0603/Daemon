from __future__ import annotations
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from PyQt6.QtCore import QObject, QTimer

from src.constants import (
    THOUGHT_POOL_SIZE, THOUGHT_POOL_THRESHOLD, THOUGHT_POOL_REFILL_COUNT,
    POOL_DECAY_INTERVAL_SEC, POOL_REFILL_PERIODIC_SEC,
)
from src.response_pool import ThoughtPool

logger = logging.getLogger(__name__)


class AutonomousResponseManager(QObject):
    def __init__(self, cache_path: str, write_coalescer, parent=None):
        super().__init__(parent)
        self._cache_path = cache_path
        self._write_coalescer = write_coalescer
        self.thought_pool = ThoughtPool(
            max_size=THOUGHT_POOL_SIZE,
            threshold=THOUGHT_POOL_THRESHOLD,
            refill_count=THOUGHT_POOL_REFILL_COUNT,
        )
        logger.debug("[VERIFY] unified ThoughtPool: single pool created (max=%d, threshold=%d, refill=%d)",
                     THOUGHT_POOL_SIZE, THOUGHT_POOL_THRESHOLD, THOUGHT_POOL_REFILL_COUNT)
        self._decay_timer = QTimer(self)
        self._decay_timer.setInterval(POOL_DECAY_INTERVAL_SEC * 1000)
        self._decay_timer.timeout.connect(self.decay_all)
        self._auto_refill_timer = QTimer(self)
        self._auto_refill_timer.setInterval(POOL_REFILL_PERIODIC_SEC * 1000)
        self._auto_refill_timer.timeout.connect(self._on_auto_refill_tick)
        self._load()
        self._load_local_seeds()

    def _load_local_seeds(self) -> None:
        logger.debug("[VERIFY] ThoughtPool: seeding with %d local typing reactions", 15)
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
            {"dialogue": line, "type": "typing_reaction", "action": "hyper",
             "target_x": 0, "priority": 3}
            for line in kenny_typing_lines
        ]
        self.thought_pool.add_items(items)

    def draw(self, target_type: str, current_context_hash: str = None) -> list[dict]:
        return self.thought_pool.draw_by_type(target_type, current_context_hash)

    def add_items(self, items: list[dict]):
        if items:
            self.thought_pool.add_items(items)
            self._mark_dirty()

    def remaining(self) -> int:
        return self.thought_pool.remaining()

    def decay_all(self):
        self.thought_pool.decay()

    def start(self):
        self._decay_timer.start()
        self._auto_refill_timer.start()
        if self.thought_pool.remaining() < 3:
            logger.debug("ThoughtPool stale (%d), priming", self.thought_pool.remaining())
            QTimer.singleShot(2000, self.thought_pool._request_refill)

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
            pool_data = pools_data.get("thought_pool", {})
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
            self.thought_pool.load_items(filtered)
            logger.info("Loaded thought pool: %d items", self.thought_pool.remaining())
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
            logger.warning("Failed to load response cache: %s", e)

    def _save(self):
        try:
            data = {
                "version": 2,
                "pools": {
                    "thought_pool": {
                        "items": self.thought_pool.save_items(),
                        "last_refill": datetime.now().isoformat(),
                    }
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
        if not self.thought_pool._refilling:
            self.thought_pool._request_refill()
