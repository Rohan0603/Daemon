"""Hybrid semantic retrieval for memory and diary records."""
from __future__ import annotations

import logging
import time
from typing import Any, Iterable

from .embedding_engine import EmbeddingEngine

logger = logging.getLogger(__name__)


class RAGRetriever:
    """Prefer Firestore kNN and fall back to an in-memory local vector index."""

    def __init__(
        self,
        embedding_engine: EmbeddingEngine,
        *,
        crud: Any = None,
        collection: str = "memories",
        records: Iterable[dict[str, Any]] = (),
        min_score: float = 0.0,
    ) -> None:
        if not 0.0 <= min_score <= 1.0:
            raise ValueError("min_score must be between 0 and 1")
        self.engine = embedding_engine
        self.crud = crud
        self.collection = collection
        self.min_score = min_score
        self._records: list[dict[str, Any]] = []
        self.replace_records(records)

    def replace_records(self, records: Iterable[dict[str, Any]]) -> None:
        self._records = []
        for record in records:
            if record.get("content") or record.get("text"):
                item = dict(record)
                item["content"] = str(item.get("content", item.get("text", "")))
                item["embedding"] = item.get("embedding") or self.engine.embed(item["content"])
                self._records.append(item)
        logger.debug("RAG local index refreshed: records=%d", len(self._records))

    def add_record(self, record: dict[str, Any]) -> None:
        self.replace_records([*self._records, record])

    def retrieve(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        started = time.monotonic()
        logger.debug(
            "RAG retrieval started: query_chars=%d limit=%d local_records=%d remote=%s collection=%s",
            len(query), limit, len(self._records),
            bool(self.crud is not None and getattr(self.crud, "available", False)),
            self.collection,
        )
        vector = self.engine.embed(query)
        if self.crud is not None and getattr(self.crud, "available", False):
            try:
                remote = self.crud.find_nearest_vector(
                    self.collection, vector, limit=limit, vector_field="embedding"
                )
            except Exception:
                logger.warning("Remote semantic retrieval failed; using local index", exc_info=True)
            else:
                if remote is not None:
                    logger.info(
                        "RAG retrieval complete: backend=firestore results=%d duration_ms=%.1f",
                        len(remote), (time.monotonic() - started) * 1000,
                    )
                    return remote
        scored = []
        for record in self._records:
            score = self.engine.cosine_similarity(vector, record["embedding"])
            if score >= self.min_score:
                item = {key: value for key, value in record.items() if key != "embedding"}
                item["score"] = score
                scored.append(item)
        scored.sort(key=lambda item: item["score"], reverse=True)
        results = scored[:limit]
        logger.info(
            "RAG retrieval complete: backend=local results=%d duration_ms=%.1f",
            len(results), (time.monotonic() - started) * 1000,
        )
        return results

    def retrieve_local(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Retrieve only from the local index.

        Interactive fast paths must never turn a cache miss into a network
        request.  Keep this separate from ``retrieve`` because the latter
        intentionally prefers Firestore when it is available.
        """
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        vector = self.engine.embed(query)
        scored = []
        for record in self._records:
            score = self.engine.cosine_similarity(vector, record["embedding"])
            if score >= self.min_score:
                item = {key: value for key, value in record.items() if key != "embedding"}
                item["score"] = score
                scored.append(item)
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:limit]
