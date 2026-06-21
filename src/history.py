from __future__ import annotations
import logging
import time
from typing import TYPE_CHECKING
from src.brain_store import BrainStore

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.write_coalescer import WriteCoalescer


class History:
    def __init__(self, path: str | None = None,
                 coalescer: "WriteCoalescer | None" = None) -> None:
        self._brain = BrainStore.get_instance(path)
        self._coalescer = coalescer

    @property
    def _entries(self):
        return self._brain.history

    @_entries.setter
    def _entries(self, value):
        self._brain.history = value

    def add_entry(
        self,
        user_input: str,
        daemon_response: str,
        action: str,
        coalescer: "WriteCoalescer | None" = None,
    ) -> None:
        entry = {
            "timestamp": time.time(),
            "user_input": user_input or "",
            "daemon_response": daemon_response or "",
            "action": action or "idle",
        }
        self._entries.append(entry)
        effective = coalescer if coalescer is not None else self._coalescer
        if effective is not None:
            effective.mark_dirty("history")
        else:
            self._save()

    def get_recent(self, n: int = 5) -> list[dict]:
        if n <= 0:
            return []
        return list(self._entries[-n:])

    def get_all(self) -> list[dict]:
        return list(self._entries)

    def clear(self) -> None:
        self._entries = []
        self._save()

    def get_context_block(self, n: int | None = None) -> str:
        recent = self.get_recent(n) if n is not None else self._entries
        if not recent:
            return ""
        lines = ["## Recent conversations:"]
        for entry in reversed(recent):
            user = entry["user_input"] or "(autonomous check-in)"
            daemon = entry["daemon_response"]
            if len(daemon) > 60:
                daemon = daemon[:57] + "..."
            lines.append(f'- You: "{user}" ? Daemon: "{daemon}"')
        return "\n".join(lines)

    def count(self) -> int:
        return len(self._entries)

    def save(self) -> None:
        self._save()

    def _save(self) -> None:
        self._brain.save()

    def _load(self) -> None:
        self._brain._load()
