from src.llm.interactive_fast_path import InteractiveFastPath
from src.memory.rag_retriever import RAGRetriever
from src.memory.embedding_engine import EmbeddingEngine


class Memory:
    def __init__(self, facts):
        self.facts = facts

    def get_all(self):
        return dict(self.facts)


def test_exact_memory_question_is_local_and_cached():
    now = [10.0]
    path = InteractiveFastPath(
        Memory({"user_name": "Ada"}), ttl_seconds=5, clock=lambda: now[0],
    )
    first = path.resolve("What is my name?")
    second = path.resolve("what is my name")
    assert first is not None
    assert first.source == "memory"
    assert first.confidence == 1.0
    assert second is first


def test_expired_and_invalidated_entries_miss():
    now = [0.0]
    memory = Memory({"name": "Ada"})
    path = InteractiveFastPath(memory, ttl_seconds=1, clock=lambda: now[0])
    assert path.resolve("what is my name") is not None
    memory.facts.clear()
    now[0] = 2.0
    assert path.resolve("what is my name") is None
    path.invalidate()
    assert path.resolve("what is my name") is None


def test_rag_fast_path_uses_local_only_and_confidence_threshold():
    rag = RAGRetriever(
        EmbeddingEngine(dimension=16),
        records=[{"id": "x", "content": "Python programming"}],
        min_score=0.0,
    )
    path = InteractiveFastPath(Memory({}), rag, rag_min_confidence=0.1)
    result = path.resolve("Python programming")
    assert result is not None
    assert result.source == "rag"


def test_miss_preserves_provider_fallback():
    path = InteractiveFastPath(Memory({"name": "Ada"}))
    assert path.resolve("explain quantum tunneling") is None
