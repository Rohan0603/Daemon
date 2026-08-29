from src.memory.embedding_engine import EmbeddingEngine
from src.memory.rag_retriever import RAGRetriever


def test_offline_retrieval_ranks_local_records():
    engine = EmbeddingEngine(dimension=16)
    retriever = RAGRetriever(engine, records=[
        {"id": "python", "content": "Python programming language"},
        {"id": "music", "content": "Classical music composition"},
    ])

    results = retriever.retrieve("Python programming")

    assert results[0]["id"] == "python"
    assert results[0]["score"] > 0


def test_online_retrieval_uses_firestore():
    class CRUD:
        available = True

        def find_nearest_vector(self, collection, vector, **kwargs):
            assert collection == "memories"
            return [{"id": "remote", "content": "cloud result"}]

    retriever = RAGRetriever(EmbeddingEngine(dimension=8), crud=CRUD())
    assert retriever.retrieve("hello") == [{"id": "remote", "content": "cloud result"}]


def test_context_manager_can_include_rag_results():
    from src.llm.context_manager import ContextManager

    class Memory:
        def get_all(self):
            return {"name": "Kenny"}

    class Retriever:
        def retrieve(self, query, limit):
            return [{"content": "related fact"}]

    manager = ContextManager(Memory(), object(), rag_retriever=Retriever())
    assert "related fact" in manager._get_memory_block()
