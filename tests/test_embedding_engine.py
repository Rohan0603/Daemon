import pytest

from src.memory.embedding_engine import EmbeddingEngine


def test_fallback_embedding_is_normalized_and_cached():
    engine = EmbeddingEngine(dimension=8, cache_size=2)
    first = engine.embed("Daemon remembers Python")
    second = engine.embed("Daemon remembers Python")

    assert len(first) == 8
    assert EmbeddingEngine.cosine_similarity(first, first) == pytest.approx(1.0)
    assert first == second
    assert len(engine._cache) == 1


def test_provider_and_lru_eviction():
    calls = []

    def provider(text):
        calls.append(text)
        return [1, 0, 0, 0]

    engine = EmbeddingEngine(dimension=4, cache_size=1, provider=provider)
    engine.embed("one")
    engine.embed("one")
    engine.embed("two")
    engine.embed("one")

    assert calls == ["one", "two", "one"]


def test_ollama_provider(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"embedding": [3, 4]}

    monkeypatch.setattr("src.memory.embedding_engine.requests.post", lambda *args, **kwargs: Response())
    result = EmbeddingEngine(dimension=2, ollama_url="http://localhost:11434").embed("hello")
    assert result == pytest.approx([0.6, 0.8])


def test_validation():
    with pytest.raises(ValueError):
        EmbeddingEngine(dimension=0)
    with pytest.raises(ValueError):
        EmbeddingEngine(dimension=2).embed(" ")
    with pytest.raises(ValueError):
        EmbeddingEngine.normalize([0, 0])
