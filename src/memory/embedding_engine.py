"""Client-side text embeddings with optional Ollama and deterministic fallback."""
from __future__ import annotations

import hashlib
import logging
import math
from collections import OrderedDict
from typing import Callable, Sequence

import requests

logger = logging.getLogger(__name__)


class EmbeddingEngine:
    """Generate normalized dense vectors and cache repeated requests."""

    def __init__(
        self,
        *,
        dimension: int = 384,
        cache_size: int = 256,
        provider: Callable[[str], Sequence[float]] | None = None,
        ollama_url: str | None = None,
        ollama_model: str = "nomic-embed-text",
        timeout: float = 15.0,
    ) -> None:
        if dimension <= 0 or cache_size <= 0 or timeout <= 0:
            raise ValueError("dimension, cache_size, and timeout must be positive")
        self.dimension = dimension
        self.cache_size = cache_size
        self._provider = provider
        self.ollama_url = ollama_url.rstrip("/") if ollama_url else None
        self.ollama_model = ollama_model
        self.timeout = timeout
        self._cache: OrderedDict[str, tuple[float, ...]] = OrderedDict()

    def embed(self, text: str) -> list[float]:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        key = text.strip()
        if not key:
            raise ValueError("text must not be empty")
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return list(cached)
        vector = self._generate(key)
        if len(vector) != self.dimension:
            raise ValueError(f"embedding provider returned {len(vector)} dimensions; expected {self.dimension}")
        normalized = self.normalize(vector)
        self._cache[key] = normalized
        self._cache.move_to_end(key)
        while len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)
        return list(normalized)

    def embed_many(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]

    def _generate(self, text: str) -> Sequence[float]:
        if self._provider is not None:
            return self._provider(text)
        if self.ollama_url:
            response = requests.post(
                f"{self.ollama_url}/api/embeddings",
                json={"model": self.ollama_model, "prompt": text},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            embedding = data.get("embedding")
            if not isinstance(embedding, list):
                raise ValueError("Ollama response did not include an embedding list")
            return embedding
        return self._hash_embedding(text)

    def _hash_embedding(self, text: str) -> list[float]:
        """Dependency-free fallback for offline operation and tests."""
        values = [0.0] * self.dimension
        words = text.casefold().split()
        for index, word in enumerate(words):
            digest = hashlib.sha256(f"{index}:{word}".encode("utf-8")).digest()
            for offset in range(0, len(digest), 4):
                bucket = int.from_bytes(digest[offset:offset + 4], "big") % self.dimension
                values[bucket] += 1.0 if digest[offset] & 1 else -1.0
        return values

    @staticmethod
    def normalize(vector: Sequence[float]) -> tuple[float, ...]:
        values = tuple(float(value) for value in vector)
        norm = math.sqrt(sum(value * value for value in values))
        if norm == 0:
            raise ValueError("embedding vector must not be zero")
        return tuple(value / norm for value in values)

    @staticmethod
    def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
        if len(left) != len(right) or not left:
            raise ValueError("vectors must have equal non-zero dimensions")
        return sum(float(a) * float(b) for a, b in zip(left, right))
