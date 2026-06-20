from __future__ import annotations
import hashlib
import logging
import time
import unicodedata
from src.brain_store import BrainStore

logger = logging.getLogger(__name__)

MAX_DIARY_ENTRIES = 200

def calculate_content_hash(text: str) -> str:
    normalized = unicodedata.normalize('NFKC', text.strip()).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

def _migrate_entry(entry: str | dict) -> dict:
    if isinstance(entry, str):
        return {
            "content": entry,
            "timestamp": time.time(),
            "hash": calculate_content_hash(entry),
        }
    return dict(entry)

def _migrate_entries(entries: list) -> list[dict]:
    return [_migrate_entry(e) for e in entries]

class DiaryStore:
    def __init__(self, path: str, max_entries: int = MAX_DIARY_ENTRIES) -> None:
        self._brain = BrainStore.get_instance(path)
        self._max_entries = max_entries
        self._has_written = False

    @property
    def _diary_entries(self):
        return self._brain.diary

    @_diary_entries.setter
    def _diary_entries(self, value):
        self._brain.diary = value

    @property
    def _diary_synced(self):
        return self._brain.diary_synced

    @_diary_synced.setter
    def _diary_synced(self, value):
        self._brain.diary_synced = value

    def read(self) -> dict | None:
        import os
        if not os.path.exists(self._brain._path) and not self._has_written:
            return None
        self._diary_entries = _migrate_entries(self._diary_entries)
        return {"entries": self._diary_entries, "synced": self._diary_synced}

    def write(self, entries: list, synced: int) -> None:
        converted = _migrate_entries(entries)
        self._diary_entries = list(converted)
        capped = self.prune(converted)
        self._diary_entries = capped
        self._diary_synced = synced
        self._has_written = True
        self._brain.save()

    def add_diary_entry(self, content: str, timestamp: int = 0, **kwargs) -> bool:
        entry_hash = calculate_content_hash(content)
        for entry in self._diary_entries:
            if entry.get("hash") == entry_hash:
                return False
        entry: dict = {
            "content": content,
            "timestamp": timestamp if timestamp else time.time(),
            "hash": entry_hash,
        }
        entry.update(kwargs)
        self._diary_entries.append(entry)
        if len(self._diary_entries) > self._max_entries:
            self._diary_entries = self._diary_entries[-self._max_entries:]
        self._has_written = True
        return True

    def get_entries(self) -> list[dict]:
        return list(self._diary_entries)

    def prune(self, entries: list[dict]) -> list[dict]:
        return entries[-self._max_entries:]
