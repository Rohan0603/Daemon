"""WriteCoalescer — batches local-storage writes to disk on a timer.

Avoids disk thrashing during high-frequency autonomous chatter by deferring
saves of Memory, History, and the local diary file until the flush timer
fires (default 8s). `flush()` is also called synchronously on shutdown
so no in-memory mutations are lost.

Constructor does NOT start the timer — call `start()` to begin.
"""
from __future__ import annotations
import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QTimer


if TYPE_CHECKING:
    from src.memory import Memory
    from src.history import History
    from src.memory_manager import MemoryManager
    from src.diary_store import DiaryStore


class WriteCoalescer:
    def __init__(
        self,
        memory: "Memory",
        history: "History",
        memory_manager: "MemoryManager",
        diary_store: "DiaryStore | None" = None,
        diary_entries_ref: list | None = None,
        flush_sec: float = 8.0,
    ) -> None:
        self._memory = memory
        self._history = history
        self._memory_manager = memory_manager
        self._diary_store = diary_store
        self._diary_entries_ref = diary_entries_ref or []
        self._flush_sec = flush_sec
        self._timer: QTimer | None = None
        self._dirty: dict[str, bool] = {
            "memory": False,
            "history": False,
            "diary": False,
            "response_cache": False,
            "brain": False,
        }

    def mark_dirty(self, kind: str) -> None:
        if kind not in self._dirty:
            return
        self._dirty[kind] = True

    def flush(self) -> None:
        for kind in ("memory", "history", "diary", "response_cache", "brain"):
            if not self._dirty.get(kind):
                continue
            try:
                if kind == "memory":
                    self._memory.save()
                elif kind == "history":
                    self._history.save()
                elif kind == "diary":
                    self._flush_diary()
                elif kind == "response_cache":
                    pass
                elif kind == "brain":
                    self._memory_manager.retry_pending_writes()
            except Exception as e:
                logging.warning(f"[WriteCoalescer] {kind} flush failed: {e}")
                continue
            self._dirty[kind] = False

    def _flush_diary(self) -> None:
        if self._diary_store is None:
            return
        existing = self._diary_store.read()
        synced = existing.get("synced", 0) if existing else 0
        self._diary_store.write(self._diary_entries_ref, synced)

    def start(self) -> None:
        if self._timer is not None:
            self._timer.stop()
        self._timer = QTimer()
        self._timer.setInterval(int(self._flush_sec * 1000))
        self._timer.timeout.connect(self.flush)
        self._timer.start()

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.stop()
