"""Atomic local diary file I/O with backup and entry capping."""
from __future__ import annotations
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_DIARY_ENTRIES = 200


class DiaryStore:
    def __init__(self, path: str, max_entries: int = MAX_DIARY_ENTRIES) -> None:
        self._path = path
        self._max_entries = max_entries

    def read(self) -> dict | None:
        try:
            data = json.loads(Path(self._path).read_text(encoding="utf-8"))
            if isinstance(data, dict) and "entries" in data:
                return data
            return None
        except FileNotFoundError:
            return None
        except (json.JSONDecodeError, ValueError):
            logger.warning("DiaryStore: main file corrupt, trying .bak")
            return self._read_bak()

    def _read_bak(self) -> dict | None:
        bak_path = self._path + ".bak"
        try:
            data = json.loads(Path(bak_path).read_text(encoding="utf-8"))
            if isinstance(data, dict) and "entries" in data:
                return data
        except Exception:
            pass
        return None

    def write(self, entries: list[str], synced: int) -> None:
        capped = self.prune(entries)
        data = {"entries": capped, "synced": synced}
        self._write_atomic(data)

    def prune(self, entries: list[str]) -> list[str]:
        if len(entries) <= self._max_entries:
            return list(entries)
        return list(entries[-self._max_entries:])

    def _write_atomic(self, data: dict) -> None:
        tmp = self._path + ".tmp"
        try:
            bak_path = self._path + ".bak"
            if os.path.exists(self._path):
                try:
                    os.replace(self._path, bak_path)
                except OSError:
                    pass
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(tmp, self._path)
            if not os.path.exists(bak_path):
                try:
                    with open(bak_path, "w", encoding="utf-8") as f:
                        json.dump(data, f)
                except OSError:
                    pass
        except Exception as e:
            logger.warning("DiaryStore write failed for %s: %s", self._path, e)
