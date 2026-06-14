from __future__ import annotations
import logging
logger = logging.getLogger(__name__)
from collections import deque

import time

from src.brain_schema import (
    BRAIN_SCHEMA as _BRAIN_SCHEMA,
    DEFAULT_BRAIN as _DEFAULT_BRAIN,
    USER_LEVEL_KEYS as _USER_LEVEL_KEYS,
    apply_brain_update,
)
from src.firebase_crud import FirebaseCRUD


class MemoryManager:
    def __init__(self, crud: FirebaseCRUD, uid: str, pet_id: str = "kenny") -> None:
        self._pending_writes: deque = deque()
        self.crud = crud
        self._uid = uid
        self._pet_id = pet_id

    @property
    def _brain_collection(self) -> str:
        return f"users/{self._uid}/pets"

    @property
    def _brain_doc_id(self) -> str:
        return self._pet_id

    @property
    def _diary_collection(self) -> str:
        return f"users/{self._uid}/pets/{self._pet_id}/diary"

    # ── Brain (Firebase → local on startup, local → Firebase on quit) ──────────

    def load_current_brain(self) -> dict:
        logger.debug("MemoryManager.load_current_brain called")
        try:
            data = self.crud.get(self._brain_collection, self._brain_doc_id)
        except Exception as e:
            logger.warning(f"[MemoryManager] load_current_brain failed: {e}")
            return dict(_DEFAULT_BRAIN)
        if data:
            logger.debug(f"  core_brain loaded ({len(data)} fields)")
            logger.info(f"[MemoryManager] core_brain loaded ({len(data)} fields)")
            return data
        logger.debug("  core_brain missing or unavailable, returning defaults")
        logger.info("[MemoryManager] core_brain missing — using defaults")
        return dict(_DEFAULT_BRAIN)

    def update_brain(self, new_data: dict) -> None:
        if not self.crud.set(self._brain_collection, self._brain_doc_id, new_data, merge=True):
            logger.warning("[MemoryManager] update_brain failed after retries — queued for retry")
            self._pending_writes.append(("brain", new_data))
        else:
            logger.info(f"[MemoryManager] core_brain updated ({len(new_data)} fields merged)")

    def batch_update_brain(self, new_data: dict) -> None:
        """Accumulate brain updates in a batch, write on flush."""
        self._batch_cache.update(new_data)
        self._batch_dirty = True

    def flush_batch(self) -> None:
        """Write accumulated batch to Firestore."""
        if not self._batch_dirty or not self._batch_cache:
            return
        if self.crud.set(self._brain_collection, self._brain_doc_id, self._batch_cache, merge=True):
            logger.info(f"[MemoryManager] batch update flushed ({len(self._batch_cache)} fields)")
        else:
            logger.warning("[MemoryManager] batch update failed — queued for retry")
            self._pending_writes.append(("brain", dict(self._batch_cache)))
        self._batch_cache.clear()
        self._batch_dirty = False

    def sync_to_local(self, memory: "Memory", brain: dict | None = None) -> None:
        logger.debug("MemoryManager.sync_to_local called")
        if not self.crud.available:
            logger.debug("  crud unavailable, skipping")
            return
        if brain is None:
            brain = self.load_current_brain()
        user_data = self.crud.get("users", self._uid) or {}
        merged = dict(brain)
        for key, value in user_data.items():
            if key in _BRAIN_SCHEMA:
                merged[key] = value
        count = 0
        for key, value in merged.items():
            if key not in _BRAIN_SCHEMA:
                continue
            if not value:
                continue
            if isinstance(value, list):
                val_str = "; ".join(str(v) for v in value if v)
            elif isinstance(value, dict):
                val_str = "; ".join(f"{k}={v}" for k, v in value.items())
            else:
                val_str = str(value).strip()
            if val_str:
                memory.remember(key, val_str)
                count += 1
        logger.debug(f"  synced {count} brain fields to local memory")
        logger.info(f"[MemoryManager] synced {count} brain fields to local memory")

    def sync_from_local(self, memory: "Memory") -> None:
        if not self.crud.available:
            return
        facts = memory.get_all()
        if not facts:
            logger.info("[MemoryManager] sync_from_local: nothing to push (memory empty)")
            return

        user_facts = {}
        pet_facts = {}
        for key, value in facts.items():
            if key not in _BRAIN_SCHEMA:
                continue
            if key in _USER_LEVEL_KEYS:
                user_facts[key] = value
            else:
                pet_facts[key] = value

        if user_facts:
            existing = self.crud.get("users", self._uid) or {}
            merged = dict(existing)
            for key, value in user_facts.items():
                existing_val = existing.get(key)
                if isinstance(existing_val, list):
                    items = [v.strip() for v in value.split("; ") if v.strip()]
                    for item in items:
                        if item not in existing_val and item not in [str(x) for x in existing_val]:
                            merged.setdefault(key, []).append(item)
                elif isinstance(existing_val, dict):
                    pass
                else:
                    merged[key] = value
            self.crud.set("users", self._uid, merged, merge=True)
            logger.info(f"[MemoryManager] sync_from_local: merged {len(user_facts)} user fields into users/{self._uid}")

        if pet_facts:
            existing = self.crud.get(self._brain_collection, self._brain_doc_id) or {}
            merged = dict(existing)
            for key, value in pet_facts.items():
                existing_val = existing.get(key)
                if isinstance(existing_val, list):
                    items = [v.strip() for v in value.split("; ") if v.strip()]
                    for item in items:
                        if item not in existing_val and item not in [str(x) for x in existing_val]:
                            merged.setdefault(key, []).append(item)
                elif isinstance(existing_val, dict):
                    pass
                else:
                    merged[key] = value
            self.crud.set(self._brain_collection, self._brain_doc_id, merged, merge=True)
            logger.info(f"[MemoryManager] sync_from_local: merged {len(pet_facts)} pet fields into {self._brain_collection}/{self._brain_doc_id}")

        if not user_facts and not pet_facts:
            logger.info("[MemoryManager] sync_from_local: no relevant facts to push (all non-schema keys)")

    # ── Diary (local file during session, Firebase only at startup/quit) ──────

    def add_diary_entry(self, text: str) -> None:
        data = {"text": text, "timestamp": int(time.time())}
        result = self.crud.add(self._diary_collection, data)
        if result:
            logger.info(f"[MemoryManager] diary entry written (id={result})")
        else:
            logger.warning("[MemoryManager] add_diary_entry failed — queued for retry")
            self._pending_writes.append(("diary", data))

    def retry_pending_writes(self) -> int:
        if not self._pending_writes:
            return 0
        succeeded = 0
        while self._pending_writes:
            kind, data = self._pending_writes[0]
            try:
                if kind == "diary":
                    ok = bool(self.crud.add(self._diary_collection, data))
                elif kind == "brain":
                    ok = self.crud.set(self._brain_collection, self._brain_doc_id, data, merge=True)
                else:
                    ok = False
                if not ok:
                    break
                self._pending_writes.popleft()
                succeeded += 1
            except Exception as e:
                logger.warning("[MemoryManager] retry failed for %s: %s", kind, e)
                break
        if succeeded:
            logger.info("[MemoryManager] retried %d pending writes", succeeded)
        return succeeded

    def fetch_all_diary_entries(self, limit: int = 200) -> list[str]:
        logger.debug("MemoryManager.fetch_all_diary_entries called")
        try:
            entries = self.crud.read_all_text(
                self._diary_collection,
                text_field="text",
                order_by="timestamp",
                limit=limit,
                ascending=True,
            )
        except Exception as e:
            logger.warning(f"[MemoryManager] fetch_all_diary_entries failed: {e}")
            return []
        logger.debug(f"  fetched {len(entries)} diary entries from Firebase")
        if entries:
            logger.info(f"[MemoryManager] fetched {len(entries)} diary entries from Firebase")
        return entries

    def push_pending_diaries(self, diary_store, entries: list[str], synced: int) -> int:
        if not self.crud.available:
            return synced
        pending = entries[synced:]
        if not pending:
            return synced
        for text in pending:
            self.crud.add(self._diary_collection, {"text": text, "timestamp": int(time.time())})
        new_synced = len(entries)
        diary_store.write(entries, new_synced)
        logger.info(f"[MemoryManager] pushed {len(pending)} pending diary entries to Firebase")
        return new_synced

    def get_current_brain(self) -> dict:
        return self.load_current_brain()

    def get_all_diary_entries(self) -> list:
        return []
