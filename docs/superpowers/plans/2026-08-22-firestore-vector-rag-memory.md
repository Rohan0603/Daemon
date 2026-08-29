# Cloud Firestore Vector DB & RAG Memory Implementation Plan

> **Goal:** Migrate Daemon's persistent memory and diary subsystems to Cloud Firestore Native Vector Search with a client-side RAG retrieval pipeline operating 100% within the free Firebase Spark plan.

---

## Architecture Overview

```
                                  ┌───────────────────────────┐
                                  │      User Input / Tick    │
                                  └─────────────┬─────────────┘
                                                │
                                  ┌─────────────▼─────────────┐
                                  │ EmbeddingEngine (Client)  │
                                  │ (ONNX / Ollama Embeddings)│
                                  └─────────────┬─────────────┘
                                                │ Query Vector
                 ┌──────────────────────────────┴──────────────────────────────┐
                 │ (Online Path)                                               │ (Offline Path)
        ┌────────▼────────┐                                           ┌────────▼────────┐
        │ Firestore kNN   │                                           │ Local NumPy     │
        │ `find_nearest`  │                                           │ Cosine Sim Cache│
        └────────┬────────┘                                           └────────┬────────┘
                 │                                                             │
                 └──────────────────────────────┬──────────────────────────────┘
                                                │ Relevant Chunks
                                  ┌─────────────▼─────────────┐
                                  │   ContextManager (RAG)    │
                                  │  (Prompt Template Hook)   │
                                  └─────────────┬─────────────┘
                                                │
                                  ┌─────────────▼─────────────┐
                                  │       LLM Response        │
                                  └───────────────────────────┘
```

---

## Detailed Task Breakdown

### Phase 1: Client-Side Embedding Engine
- [x] **Task 1.1:** Implement `src/memory/embedding_engine.py` with 384-dimensional normalized vectors and offline fallback.
- [x] **Task 1.2:** Add secondary provider for local Ollama `/api/embeddings` endpoint.
- [x] **Task 1.3:** Implement LRU caching for repeated string embeddings to eliminate redundant CPU cycles.
- [x] **Task 1.4:** Unit tests in `tests/test_embedding_engine.py`.

### Phase 2: Firestore Vector Query & Storage Layer
- [x] **Task 2.1:** Update `src/firebase_crud.py` to support `google.cloud.firestore_v1.vector.Vector` serialization.
- [x] **Task 2.2:** Implement `find_nearest_vector(collection_path, vector, limit=5, distance_measure="COSINE")` in `FirebaseCRUD`.
- [x] **Task 2.3:** Add index scan optimization guards (category pre-filtering) to minimize Spark free quota read usage.
- [x] **Task 2.4:** Unit tests with mocked Firestore Vector query API in `tests/test_firebase_vector_crud.py`.

### Phase 3: RAG Memory Manager & Retriever
- [x] **Task 3.1:** Create `src/memory/rag_retriever.py` to coordinate embedding generation, kNN retrieval, and relevance score thresholding.
- [x] **Task 3.2:** Implement offline fallback retriever in `src/memory/rag_retriever.py` utilizing vectorized `.daemon_memory.json` / `.daemon_diary.json`.
- [x] **Task 3.3:** Integrate RAG results into `src/llm/context_manager.py` dynamic prompt builder.
- [x] **Task 3.4:** Add MCP tool `query_semantic_memory(query, limit=5)` to expose vector memory search to LLM tool calls.
- [x] **Task 3.5:** Unit tests in `tests/test_rag_retriever.py`.

### Phase 4: Migration & Backwards Compatibility
- [x] **Task 4.1:** Write migration script `scripts/migrate_to_vector_db.py` to chunk and vectorize existing `core_brain` fields and historical diary entries.
- [x] **Task 4.2:** Preserve legacy stores and support dry-run migration.
- [x] **Task 4.2:** Update `MemoryManager` to write dual-format records (structured + vector embedding) during runtime writes.
- [x] **Task 4.3:** End-to-end verification of memory recall with RAG vs legacy keyword search.
