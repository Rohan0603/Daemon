from __future__ import annotations
import hashlib
import json
import logging
logger = logging.getLogger(__name__)
from collections import deque

import time

from src.brain_schema import (
    BRAIN_SCHEMA as _BRAIN_SCHEMA,
    DEFAULT_BRAIN as _DEFAULT_BRAIN,
    USER_LEVEL_KEYS as _USER_LEVEL_KEYS,
    apply_brain_update,
    _classify_tier,
)
from src.firebase_crud import FirebaseCRUD
from src.memory.embedding_engine import EmbeddingEngine


class MemoryManager:
    def __init__(self, crud: FirebaseCRUD, uid: str, pet_id: str = "kenny") -> None:
        self._pending_writes: deque = deque()
        self.crud = crud
        self._uid = uid
        self._pet_id = pet_id
        self._last_sync_hash: str = ""
        self._batch_cache: dict[str, object] = {}
        self._batch_dirty: bool = False
        self._cached_user_data: dict = {}
        self._user_data_cache_time: float = 0.0
        self._USER_DATA_CACHE_TTL: float = 30.0
        self._embedding_engine = EmbeddingEngine()

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
            logger.warning("[MemoryManager] load_current_brain failed: %s", e)
            return dict(_DEFAULT_BRAIN)
        if data:
            logger.debug("core_brain loaded (%d fields)", len(data))
            logger.info("[MemoryManager] core_brain loaded (%d fields)", len(data))
            return data
        logger.debug("core_brain missing or unavailable, returning defaults")
        logger.info("[MemoryManager] core_brain missing — using defaults")
        return dict(_DEFAULT_BRAIN)

    def update_brain(self, new_data: dict) -> None:
        if not self.crud.set(self._brain_collection, self._brain_doc_id, new_data, merge=True):
            logger.warning("[MemoryManager] update_brain failed after retries — queued for retry")
            self._pending_writes.append(("brain", new_data))
        else:
            logger.info("[MemoryManager] core_brain updated (%d fields merged)", len(new_data))

    def batch_update_brain(self, new_data: dict) -> None:
        """Accumulate brain updates in a batch, write on flush."""
        self._batch_cache.update(new_data)
        self._batch_dirty = True

    def flush_batch(self) -> None:
        """Write accumulated batch to Firestore."""
        if not self._batch_dirty or not self._batch_cache:
            return
        if self.crud.set(self._brain_collection, self._brain_doc_id, self._batch_cache, merge=True):
            logger.info("[MemoryManager] batch update flushed (%d fields)", len(self._batch_cache))
        else:
            logger.warning("[MemoryManager] batch update failed — queued for retry")
            self._pending_writes.append(("brain", dict(self._batch_cache)))
        self._batch_cache.clear()
        self._batch_dirty = False

    def sync_to_local(self, memory: "Memory", brain: dict | None = None) -> None:
        """Sync brain fields from Firebase to local Memory.

        Supports both hierarchical (v2) tier dict and flat (v1) format.
        Hierarchical: {"identity": {...}, "profile": {...}, ...}
        Flat: {"user_name": "...", "user_habits": [...], ...}
        """
        logger.debug("MemoryManager.sync_to_local called")
        if not self.crud.available:
            logger.debug("  crud unavailable, skipping")
            return
        if brain is None:
            brain = self.load_current_brain()
        # Normalize to hierarchical format if flat
        if self._is_flat_brain(brain):
            brain = self._flat_to_tier(brain)
        now = time.time()
        if now - self._user_data_cache_time > self._USER_DATA_CACHE_TTL:
            self._cached_user_data = self.crud.get("users", self._uid) or {}
            self._user_data_cache_time = now
        user_data = self._cached_user_data
        # Merge all 5 tiers: identity, profile, personality, relationship, intel
        merged = {}
        for tier in ("identity", "profile", "personality", "relationship", "intel"):
            merged.update(brain.get(tier, {}))
        # Also overlay user data from Firebase (e.g. user_name, user_profession)
        for key, value in user_data.items():
            if self._get_field_spec(key) is not None:
                merged[key] = value
        count = 0
        for key, value in merged.items():
            field_spec = self._get_field_spec(key)
            if field_spec is None:
                continue
            # Handle type conversion
            if isinstance(value, list):
                val_str = "; ".join(str(v) for v in value if v)
            elif isinstance(value, dict):
                val_str = "; ".join(f"{k}={v}" for k, v in value.items())
            else:
                val_str = str(value).strip()
            if val_str:
                memory.remember(key, val_str)
                count += 1
        logger.debug("synced %d brain fields to local memory", count)
        logger.info("[MemoryManager] synced %d brain fields to local memory", count)
        try:
            from src.observability import update_memory_facts
            update_memory_facts(count)
        except Exception:
            pass

    @staticmethod
    def _is_flat_brain(brain: dict) -> bool:
        """Check if brain dict uses flat (v1) keys."""
        return bool(brain) and "." not in str(list(brain.keys())[0])

    @staticmethod
    def _flat_to_tier(flat_brain: dict) -> dict:
        """Convert flat (v1) brain dict to hierarchical (v2) tier format."""
        from src.brain_schema import _classify_tier
        tier_fields: dict[str, dict] = {
            "identity": {},
            "profile": {},
            "personality": {},
            "relationship": {},
            "intel": {},
        }
        for key, value in flat_brain.items():
            tier = _classify_tier(key)
            if tier is not None:
                tier_fields[tier][key] = value
            else:
                tier_fields.setdefault("identity", {})[key] = value
        return tier_fields

    def _get_field_spec(self, key: str) -> dict | None:
        """Find the field spec for a key across all tiers in BRAIN_SCHEMA."""
        for tier, field_specs in _BRAIN_SCHEMA.items():
            if key in field_specs:
                return field_specs[key]
        return None

    def sync_from_local(self, memory: "Memory") -> None:
        if not self.crud.available:
            return
        facts = memory.get_all()
        if not facts:
            logger.info("[MemoryManager] sync_from_local: nothing to push (memory empty)")
            return

        # Content-hash guard: skip if nothing changed since last sync
        current_hash = hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()[:16]
        if getattr(self, '_last_sync_hash', '') == current_hash:
            logger.debug("[MemoryManager] sync_from_local: hash unchanged, skipping Firestore write")
            return
        self._last_sync_hash = current_hash

        # Separate facts by tier using BRAIN_SCHEMA and USER_LEVEL_KEYS
        user_facts: dict[str, object] = {}
        pet_facts: dict[str, object] = {}

        for key, value in facts.items():
            # Determine tier from BRAIN_SCHEMA by searching through tiers
            tier = None
            field_spec = None
            for t, field_specs in _BRAIN_SCHEMA.items():
                if key in field_specs:
                    tier = t
                    field_spec = field_specs[key]
                    break
            if tier is None:
                continue
            # Check if it's a profile key that belongs to user_level_keys
            if tier == "profile" and key in _USER_LEVEL_KEYS:
                user_facts[key] = value
            elif tier in ("personality", "relationship"):
                pet_facts[key] = value
            # identity and non-indexed relationship fields are skipped for Firebase sync
            # (they are stored as vector sidecars or local-only)

        # Merge user_facts into users/{uid}

        # Merge user_facts into users/{uid}
        if user_facts:
            existing = self.crud.get("users", self._uid) or {}
            merged = dict(existing)
            for key, value in user_facts.items():
                if key not in merged:
                    merged[key] = value
                else:
                    existing_val = merged.get(key)
                    if isinstance(existing_val, list):
                        items = [v.strip() for v in str(value).split("; ") if v.strip()]
                        for item in items:
                            if item not in existing_val and item not in [str(x) for x in existing_val]:
                                merged.setdefault(key, []).append(item)
                    elif isinstance(existing_val, dict):
                        merged.setdefault(key, {}).update(value)
                    else:
                        merged[key] = value
            self.crud.set("users", self._uid, merged, merge=True)
            logger.info("[MemoryManager] sync_from_local: merged %d user fields into users/%s",
                         len(user_facts), self._uid)

        # Merge pet_facts into brain doc
        if pet_facts:
            existing = self.crud.get(self._brain_collection, self._brain_doc_id) or {}
            merged = dict(existing)
            for key, value in pet_facts.items():
                if isinstance(value, list):
                    items = [v.strip() for v in str(value).split("; ") if v.strip()]
                    for item in items:
                        # Check if item already exists
                        existing_val = merged.get(key, [])
                        if isinstance(existing_val, list):
                            if item not in existing_val and item not in [str(x) for x in existing_val]:
                                merged.setdefault(key, []).append(item)
                        else:
                            merged[key] = value
                elif isinstance(value, dict):
                    merged.setdefault(key, {}).update(value)
                else:
                    merged[key] = value
            self.crud.set(self._brain_collection, self._brain_doc_id, merged, merge=True)
            logger.info("[MemoryManager] sync_from_local: merged %d pet fields into %s/%s",
                         len(pet_facts), self._brain_collection, self._brain_doc_id)

        # Write vector sidecar records for indexed fields only
        self._write_vector_records(facts)

        if not user_facts and not pet_facts:
            logger.info("[MemoryManager] sync_from_local: no relevant facts to push (all non-schema keys)")

    def _write_vector_records(self, facts: dict) -> None:
        """Write searchable sidecar documents for indexed fields only.

        Only fields with ``indexed: true`` in the schema are written as
        vector sidecar docs. Identity and high-frequency fields are excluded.
        """
        engine = getattr(self, "_embedding_engine", None)
        if engine is None:
            engine = self._embedding_engine = EmbeddingEngine()
        collection = f"{self._brain_collection}/{self._pet_id}/memories"
        for key, value in facts.items():
            # Determine tier and check indexing flag
            field_spec = self._get_field_spec(key)
            if field_spec is None:
                continue
            if not field_spec.get("indexed", False):
                continue  # Skip non-indexed fields (identity, high-frequency)
            content = str(value)
            self.crud.set(collection, f"memory_{key}", {
                "source": "core_brain",
                "key": key,
                "content": content,
                "embedding": engine.embed(content),
            }, merge=True)

    # ── Diary (local file during session, Firebase only at startup/quit) ──────

    def add_diary_entry(self, text: str) -> None:
        data = {"text": text, "timestamp": int(time.time())}
        result = self.crud.add(self._diary_collection, data)
        if result:
            logger.info("[MemoryManager] diary entry written (id=%s)", result)
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
            logger.warning("[MemoryManager] fetch_all_diary_entries failed: %s", e)
            return []
        logger.debug("fetched %d diary entries from Firebase", len(entries))
        if entries:
            logger.info("[MemoryManager] fetched %d diary entries from Firebase", len(entries))
        return entries

    def push_pending_diaries(self, diary_store, entries: list[str], synced: int) -> int:
        if not self.crud.available:
            return synced
        pending = entries[synced:]
        if not pending:
            return synced
        data = [{"text": text, "timestamp": int(time.time())} for text in pending]
        if not self.crud.batch_add(self._diary_collection, data):
            logger.warning("[MemoryManager] failed to push diary batch")
            return synced
        new_synced = len(entries)
        diary_store.write(entries, new_synced)
        logger.info("[MemoryManager] pushed %d diary entries in 1 batch", len(pending))
        return new_synced

    def get_current_brain(self) -> dict:
        return self.load_current_brain()

    def update_affinity_score(self, score: int) -> bool:
        """Write affinity score to the brain doc."""
        success = self.crud.set(self._brain_collection, self._brain_doc_id,
                                {"pet_affinity_score": score}, merge=True)
        if success:
            logger.info("[MemoryManager] affinity score updated to %d", score)
        else:
            logger.warning("[MemoryManager] affinity score update failed — queued for retry")
            self._pending_writes.append(("affinity", score))
        return bool(success)

    def get_all_diary_entries(self) -> list:
        try:
            entries = self.crud.get_all(self._diary_collection)
            return list(entries) if entries else []
        except Exception as e:
            logger.warning("[MemoryManager] get_all_diary_entries failed: %s", e)
            return []
