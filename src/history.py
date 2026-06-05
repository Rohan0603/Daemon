from __future__ import annotations
import json
import logging
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING
from src.constants import HISTORY_PATH

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from src.write_coalescer import WriteCoalescer


_MAX_ENTRIES = 100


class History:
    def __init__(self, path: str | None = None,
                 coalescer: "WriteCoalescer | None" = None) -> None:
        self._path = path or HISTORY_PATH
        self._entries: list[dict] = []
        self._coalescer = coalescer
        self._load()

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
        if len(self._entries) > _MAX_ENTRIES:
            self._entries = self._entries[-_MAX_ENTRIES:]
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
            lines.append(f'- You: "{user}" → Daemon: "{daemon}"')
        return "\n".join(lines)

    def count(self) -> int:
        return len(self._entries)

    def save(self) -> None:
        self._save()

    def _save(self) -> None:
        tmp = self._path + ".tmp"
        try:
            bak_path = self._path + ".bak"
            if os.path.exists(self._path):
                try:
                    os.replace(self._path, bak_path)
                except OSError:
                    pass
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"entries": self._entries, "count": len(self._entries)}, f)
            os.replace(tmp, self._path)
        except Exception as e:
            logger.warning("History save failed for %s: %s", self._path, e)

    def _load(self) -> None:
        try:
            data = json.loads(Path(self._path).read_text(encoding="utf-8"))
            self._entries = data.get("entries", [])
        except Exception:
            logger.warning("History load failed for %s — trying .bak", self._path)
            try:
                bak_path = self._path + ".bak"
                data = json.loads(Path(bak_path).read_text(encoding="utf-8"))
                self._entries = data.get("entries", [])
                logger.info("History loaded from backup (%d entries)", len(self._entries))
            except Exception as e2:
                logger.warning("History backup load also failed for %s: %s", self._path, e2)
                self._entries = []
