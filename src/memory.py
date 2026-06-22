from __future__ import annotations
import logging
import threading
from typing import TYPE_CHECKING
from src.brain_store import BrainStore
from src.storage_backend import StorageBackend

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.write_coalescer import WriteCoalescer

_MAX_FACTS = 50

class Memory(StorageBackend):
    def __init__(self, path: str | None = None,
                 coalescer: "WriteCoalescer | None" = None) -> None:
        self._brain = BrainStore.get_instance(path)
        self._coalescer = coalescer
        self._lock = threading.RLock()

    @property
    def _facts(self):
        return self._brain.facts

    def remember(self, key: str, value: str, coalescer: "WriteCoalescer | None" = None) -> None:
        with self._lock:
            self._facts[key.strip()] = value.strip()
            if len(self._facts) > _MAX_FACTS:
                oldest = sorted(self._facts.keys())[: len(self._facts) - _MAX_FACTS]
                for k in oldest:
                    del self._facts[k]
        effective = coalescer if coalescer is not None else self._coalescer
        if effective is not None:
            effective.mark_dirty("memory")
        else:
            self._save()

    def recall(self, key: str) -> str | None:
        with self._lock:
            return self._facts.get(key)

    def forget(self, key: str, coalescer: "WriteCoalescer | None" = None) -> bool:
        with self._lock:
            result = self._facts.pop(key, None) is not None
        if result:
            effective = coalescer if coalescer is not None else self._coalescer
            if effective is not None:
                effective.mark_dirty("memory")
            else:
                self._save()
        return result

    def get_all(self) -> dict[str, str]:
        return dict(self._facts)

    def get_context_block(self, max_facts: int | None = None) -> str:
        if not self._facts:
            return ""
        items = list(self._facts.items())
        if max_facts is not None:
            if max_facts <= 0:
                return ""
            items = items[-max_facts:]
        lines = ["## What Daemon remembers about you:"]
        for k, v in items:
            lines.append(f"- {k}: {v}")
        return "\n".join(lines)

    def save(self) -> None:
        self._save()

    def _save(self) -> None:
        self._brain.save()

    def _load(self) -> None:
        self._brain._load()

    def get(self, key: str):
        with self._lock:
            return self._facts.get(key)

    def set(self, key: str, value) -> bool:
        self.remember(key, value)
        return True

    def query(self, filter_fn=None, limit: int = 50) -> list[dict]:
        with self._lock:
            entries = []
            for k, v in self._facts.items():
                entry = {"id": k, "content": str(v), "timestamp": ""}
                if filter_fn is None or filter_fn(entry):
                    entries.append(entry)
            return entries[:limit]

    def all_entries(self) -> list[dict]:
        return self.query()

    def count(self) -> int:
        with self._lock:
            return len(self._facts)
