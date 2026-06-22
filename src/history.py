from __future__ import annotations
import logging
import time
from typing import TYPE_CHECKING
from src.brain_store import BrainStore
from src.storage_backend import StorageBackend

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.write_coalescer import WriteCoalescer


class History(StorageBackend):
    def __init__(self, path: str | None = None,
                 coalescer: "WriteCoalescer | None" = None) -> None:
        self._brain = BrainStore.get_instance(path)
        self._coalescer = coalescer
        self._dirty = False

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

    def save(self) -> None:
        self._save()

    def _save(self) -> None:
        self._brain.save()

    def _load(self) -> None:
        self._brain._load()

    @property
    def _turns(self):
        return self._entries

    def add(self, role: str, content: str) -> None:
        entry = {
            "timestamp": time.time(),
            "role": role,
            "content": content,
            "user_input": content if role == "user" else "",
            "daemon_response": content if role != "user" else "",
            "action": "idle",
        }
        self._turns.append(entry)
        self._dirty = True
        effective = self._coalescer
        if effective is not None:
            effective.mark_dirty("history")
        else:
            self._save()

    def get(self, key: str) -> dict | None:
        try:
            idx = int(key)
            return self._turns[idx]
        except (IndexError, ValueError):
            return None

    def set(self, key: str, value) -> bool:
        if isinstance(value, dict):
            self._turns.append(value)
            self._dirty = True
            effective = self._coalescer
            if effective is not None:
                effective.mark_dirty("history")
            else:
                self._save()
        else:
            self.add(role="user", content=str(value))
        return True

    def query(self, filter_fn=None, limit: int = 50) -> list[dict]:
        entries = []
        for i, t in enumerate(self._turns):
            role = t.get('role', '')
            content = t.get('content', '')
            if not role and not content:
                user_val = t.get('user_input')
                daemon_val = t.get('daemon_response')
                if user_val is not None or daemon_val is not None:
                    role = "user" if user_val else "daemon"
                    content = user_val if user_val else daemon_val
            entry = {
                "id": str(i),
                "content": f"{role}: {content}",
                "timestamp": t.get("timestamp", ""),
            }
            if filter_fn is None or filter_fn(entry):
                entries.append(entry)
        return entries[-limit:] if limit > 0 else []

    def all_entries(self) -> list[dict]:
        return self.query(limit=len(self._turns))

    def count(self) -> int:
        return len(self._turns)
