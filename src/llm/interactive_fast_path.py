"""Safe local-first routing for interactive user queries."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any


_QUESTION_WORDS = {
    "a", "about", "am", "are", "do", "does", "for", "i", "is", "me",
    "my", "of", "tell", "the", "what", "who", "you", "your", "know",
    "remember",
}


def _normalize(value: str) -> str:
    return " ".join(re.findall(r"\w+", value.casefold()))


@dataclass(frozen=True)
class FastPathResult:
    item: dict[str, Any]
    source: str
    confidence: float
    expires_at: float


class InteractiveFastPath:
    """Bounded, invalidatable local answer cache.

    Only exact cached answers, exact memory-key questions, and high-confidence
    local RAG matches qualify.  Everything else returns ``None`` so the normal
    provider path remains authoritative.
    """

    def __init__(
        self,
        memory: Any,
        rag_retriever: Any = None,
        *,
        ttl_seconds: float = 300.0,
        rag_min_confidence: float = 0.86,
        max_entries: int = 64,
        clock=time.monotonic,
    ) -> None:
        if ttl_seconds <= 0 or not 0.0 <= rag_min_confidence <= 1.0 or max_entries <= 0:
            raise ValueError("invalid fast-path limits")
        self._memory = memory
        self._rag = rag_retriever
        self._ttl = ttl_seconds
        self._rag_min_confidence = rag_min_confidence
        self._max_entries = max_entries
        self._clock = clock
        self._cache: dict[str, FastPathResult] = {}
        self._generation = 0

    def invalidate(self) -> None:
        self._generation += 1
        self._cache.clear()

    def resolve(self, query: str) -> FastPathResult | None:
        normalized = _normalize(query)
        if not normalized:
            return None
        now = self._clock()
        cached = self._cache.get(normalized)
        if cached is not None:
            if cached.expires_at > now:
                return cached
            self._cache.pop(normalized, None)

        result = self._memory_result(normalized, now)
        if result is None:
            result = self._rag_result(query, now)
        if result is not None:
            self._cache[normalized] = result
            while len(self._cache) > self._max_entries:
                self._cache.pop(next(iter(self._cache)))
        return result

    def _memory_result(self, normalized: str, now: float) -> FastPathResult | None:
        facts = self._memory.get_all() if self._memory is not None else {}
        query_words = set(normalized.split()) - _QUESTION_WORDS
        if not query_words:
            return None
        for key, value in facts.items():
            key_normalized = _normalize(str(key))
            key_words = set(key_normalized.split())
            aliases = [key_words]
            if len(key_words) == 1 and "_" in key_normalized:
                parts = set(key_normalized.replace("_", " ").split())
                aliases.append(parts)
                aliases.append(parts - {"user", "pet", "mission"})
            if not key_words or query_words not in aliases:
                continue
            content = str(value)
            return FastPathResult(
                item={"dialogue": f"I remember: {content}", "thought": "local memory", "type": "idle_thought", "priority": 5},
                source="memory",
                confidence=1.0,
                expires_at=now + self._ttl,
            )
        return None

    def _rag_result(self, query: str, now: float) -> FastPathResult | None:
        if self._rag is None or not hasattr(self._rag, "retrieve_local"):
            return None
        try:
            results = self._rag.retrieve_local(query, limit=1)
        except Exception:
            return None
        if not results:
            return None
        result = results[0]
        confidence = float(result.get("score", 0.0))
        content = str(result.get("content", result.get("text", ""))).strip()
        if confidence < self._rag_min_confidence or not content:
            return None
        return FastPathResult(
            item={"dialogue": f"I found this locally: {content}", "thought": "local semantic memory", "type": "idle_thought", "priority": 4},
            source="rag",
            confidence=confidence,
            expires_at=now + self._ttl,
        )


__all__ = ["FastPathResult", "InteractiveFastPath"]
