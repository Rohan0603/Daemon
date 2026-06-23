from __future__ import annotations
import hashlib
import logging
import time
import unicodedata
from src.brain_store import BrainStore
from src.storage_backend import StorageBackend

logger = logging.getLogger(__name__)

MAX_DIARY_ENTRIES = 200
DIARY_DEDUP_SIMILARITY = 0.85  # Reject if >85% character overlap with existing


def _fuzzy_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    set_a = set(a.casefold())
    set_b = set(b.casefold())
    if not set_a and not set_b:
        return 1.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def _has_fuzzy_duplicate(content: str, entries: list[dict], threshold: float = DIARY_DEDUP_SIMILARITY) -> bool:
    norm = content.strip().casefold()
    for entry in entries:
        existing = (entry.get("content") or "").strip().casefold()
        if _fuzzy_ratio(norm, existing) >= threshold:
            return True
    return False

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

class DiaryStore(StorageBackend):
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
        # Fuzzy dedup: reject if >85% character overlap with any existing entry
        if _has_fuzzy_duplicate(content, self._diary_entries):
            logger.debug("Diary fuzzy dedup skipped entry: '%.60s'", content)
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

    @property
    def _entries(self):
        return self._diary_entries

    def add(self, text: str) -> bool:
        return self.add_diary_entry(text)

    def get(self, key: str) -> dict | None:
        for entry in self._entries:
            if entry.get("hash") == key:
                return entry
        return None

    def set(self, key: str, value) -> bool:
        return self.add(str(value))

    def query(self, filter_fn=None, limit: int = 50) -> list[dict]:
        entries = []
        for e in self._entries:
            entry = {
                "id": e.get("hash", ""),
                "content": e.get("text", e.get("content", "")),
                "timestamp": e.get("timestamp", ""),
            }
            if filter_fn is None or filter_fn(entry):
                entries.append(entry)
        return entries[-limit:] if limit > 0 else []

    def all_entries(self) -> list[dict]:
        return self.query(limit=len(self._entries))

    def count(self) -> int:
        return len(self._entries)
