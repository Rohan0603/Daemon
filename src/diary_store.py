"""Atomic local diary file I/O with backup and entry capping.

Encapsulates diary entries as dicts with content, timestamp, and content-hash
for deduplication. Legacy string-only entries are auto-migrated on read().
"""
from __future__ import annotations
import hashlib
import json
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_DIARY_ENTRIES = 200


def calculate_content_hash(text: str) -> str:
    """SHA-256 hash of stripped+lowercased text for dedup."""
    return hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()


def _migrate_entry(entry: str | dict) -> dict:
    """Convert a legacy string entry to dict format, or pass through dicts."""
    if isinstance(entry, str):
        return {
            "content": entry,
            "timestamp": time.time(),
            "hash": calculate_content_hash(entry),
        }
    return dict(entry)


def _migrate_entries(entries: list) -> list[dict]:
    """Migrate an entire entry list, handling legacy strings."""
    return [_migrate_entry(e) for e in entries]


class DiaryStore:
    def __init__(self, path: str, max_entries: int = MAX_DIARY_ENTRIES) -> None:
        self._path = path
        self._max_entries = max_entries
        self._diary_entries: list[dict] = []

    def read(self) -> dict | None:
        try:
            data = json.loads(Path(self._path).read_text(encoding="utf-8"))
            if isinstance(data, dict) and "entries" in data:
                data["entries"] = _migrate_entries(data["entries"])
                return data
            return None
        except FileNotFoundError:
            return self._read_bak()
        except (json.JSONDecodeError, ValueError):
            logger.warning("DiaryStore: main file corrupt, trying .bak")
            return self._read_bak()

    def _read_bak(self) -> dict | None:
        bak_path = self._path + ".bak"
        try:
            data = json.loads(Path(bak_path).read_text(encoding="utf-8"))
            if isinstance(data, dict) and "entries" in data:
                data["entries"] = _migrate_entries(data["entries"])
                return data
        except Exception:
            pass
        return None

    def write(self, entries: list, synced: int) -> None:
        """Write entries to disk. Accepts list[str] (legacy) or list[dict]."""
        converted = _migrate_entries(entries)
        self._diary_entries = list(converted)
        capped = self.prune(converted)
        data = {"entries": capped, "synced": synced}
        self._write_atomic(data)

    def add_diary_entry(self, content: str, timestamp: int = 0, **kwargs) -> bool:
        """Add an entry with content-hash dedup. Returns True if added."""
        entry_hash = calculate_content_hash(content)
        for entry in self._diary_entries:
            if entry.get("hash") == entry_hash:
                logger.debug("DiaryStore: duplicate entry skipped (hash=%s)", entry_hash[:12])
                return False
        entry: dict = {
            "content": content,
            "timestamp": timestamp if timestamp else time.time(),
            "hash": entry_hash,
        }
        entry.update(kwargs)
        self._diary_entries.append(entry)
        # Enforce cap
        if len(self._diary_entries) > self._max_entries:
            self._diary_entries = self._diary_entries[-self._max_entries:]
        return True

    def get_entries(self) -> list[dict]:
        """Return a copy of the in-memory entry list."""
        return list(self._diary_entries)

    def prune(self, entries: list) -> list:
        """Truncate to max_entries, keeping the most recent."""
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
            raise
