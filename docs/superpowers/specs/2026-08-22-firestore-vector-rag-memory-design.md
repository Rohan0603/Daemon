# Cloud Firestore Vector DB & RAG Memory Architecture Design Specification

**Date:** 2026-08-22  
**Status:** Approved / Next Priority  
**Author:** Daemon Core Architecture  

---

## 1. Executive Summary

Daemon currently uses a structured 3-tier memory system (local JSON cache ↔ `MemoryManager` ↔ Cloud Firestore `core_brain` document & sequential `diary` collection). As conversation history, diary logs, and user knowledge expand, loading entire brain documents into prompt context wastes tokens and lacks deep semantic retrieval.

This specification outlines the migration of Daemon's persistent memory and diary storage to a **Cloud Firestore Native Vector Database with Retrieval-Augmented Generation (RAG)**, structured specifically for the **Firebase Spark (100% Free) Plan**.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DAEMON RAG MEMORY SYSTEM                           │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                ┌──────────────────────┴──────────────────────┐
                │                                             │
   ┌────────────▼────────────┐                   ┌────────────▼────────────┐
   │  CLIENT-SIDE EMBEDDING  │                   │  FIRESTORE VECTOR DB    │
   │  (100% Free / Spark)    │                   │  (kNN Index & Search)   │
   ├─────────────────────────┤                   ├─────────────────────────┤
   │ - Local ONNX / FastEmbed│                   │ - Native `Vector` types │
   │ - Ollama /api/embeddings│                   │ - `find_nearest` query  │
   │ - Zero Cloud Functions  │                   │ - Cost: 1 read/100 scan │
   └────────────┬────────────┘                   └────────────▲────────────┘
                │                                             │
                └──────────────────────┬──────────────────────┘
                                       │
                        ┌──────────────▼──────────────┐
                        │   RAG RETRIEVAL PIPELINE    │
                        ├─────────────────────────────┤
                        │ - Context-aware query embed │
                        │ - Top-K nearest memories    │
                        │ - Prompt injection          │
                        │ - Local cosine sim fallback │
                        └─────────────────────────────┘
```

---

## 2. Free Tier (Spark Plan) Architecture & Economics

### 2.1 The Spark Plan Quota Model
* **Daily Quota:** 50,000 document reads per day.
* **Vector Index Scan Cost:** 1 read operation for every batch of up to 100 kNN vector index entries scanned.
* **Result Document Cost:** 1 standard read operation per returned match.

$$\text{Total Reads} = \left\lceil \frac{\text{Indexed Entries Scanned}}{100} \right\rceil + K_{\text{results}}$$

*Example:* Querying top-5 memories across a collection of 1,200 indexed memories costs $\lceil 1200 / 100 \rceil + 5 = 12 + 5 = 17$ reads. At 100 RAG queries/day, this uses only 1,700 reads (~3.4% of daily 50,000 free quota).

### 2.2 Avoiding the "Firebase Extension" Paywall
* **The Paid Trap:** The official Firebase "Vector Search with Firestore" Extension requires Cloud Functions and Secret Manager, forcing a mandatory upgrade to the Blaze (pay-as-you-go) plan with billing account details.
* **The 100% Free Solution:** Daemon computes vector embeddings **client-side on the host machine** (via a lightweight local embedding model such as `all-MiniLM-L6-v2` via ONNX Runtime / `fastembed`, or local Ollama embeddings). The resulting float arrays are wrapped in `firestore.Vector(array)` and saved directly via the Firestore Python SDK.

---

## 3. Storage Schema & Vector Indexing

### 3.1 Collections & Document Layout

#### `users/{uid}/pets/{pet_id}/memories/{memory_id}`
```json
{
  "id": "mem_9f82a1c0",
  "category": "user_preference",
  "content": "User prefers concise Git commit messages and strict pre-commit test runs.",
  "embedding": "Vector([0.024, -0.091, 0.183, ...])", // 384-dim
  "importance": 0.9,
  "access_count": 14,
  "created_at": "2026-08-22T18:00:00Z",
  "last_accessed_at": "2026-08-22T23:20:00Z",
  "tags": ["git", "workflow", "preferences"]
}
```

#### `users/{uid}/pets/{pet_id}/diary/{diary_id}`
```json
{
  "id": "diary_20260822_01",
  "title": "Debugging LSP client and UIA trees",
  "content": "Spent the evening implementing UI Automation patterns for the desktop companion.",
  "embedding": "Vector([-0.015, 0.082, 0.114, ...])",
  "mood": "FOCUSED",
  "created_at": "2026-08-22T23:00:00Z"
}
```

### 3.2 Firestore Vector Index Definition
Vector search requires creating a vector index in Firestore:
- **Collection Group:** `memories` / `diary`
- **Vector Field:** `embedding`
- **Dimension:** 384 (for `all-MiniLM-L6-v2` / `bge-small-en-v1.5`)
- **Distance Measure:** `COSINE` (or `EUCLIDEAN` / `DOT_PRODUCT`)

---

## 4. Client-Side Embedding Engine (`src/memory/embedding_engine.py`)

To ensure zero cost and offline capability:
1. **Primary Provider:** Local ONNX / `fastembed` runner (CPU-optimized, ~20ms inference for 384 dimensions, <100MB RAM).
2. **Secondary Provider:** Local Ollama `/api/embeddings` endpoint (if Ollama is enabled).
3. **Tertiary Fallback:** Pre-computed token frequency hash / offline dense cache.

---

## 5. RAG Retrieval Pipeline (`src/memory/rag_retriever.py`)

### 5.1 Retrieval Flow
1. **Trigger:** User query submitted or autonomous thought cycle activated.
2. **Query Vectorization:** `query_vec = embedding_engine.embed_text(query_text)`
3. **Firestore kNN Query:**
   ```python
   from google.cloud.firestore_v1.vector import Vector
   from google.cloud.firestore_v1.base_vector_query import DistanceMeasure

   collection = db.collection(f"users/{uid}/pets/{pet_id}/memories")
   vector_query = collection.find_nearest(
       vector_field="embedding",
       query_vector=Vector(query_vec),
       distance_measure=DistanceMeasure.COSINE,
       limit=5,
       distance_result_field="vector_distance"
   )
   results = vector_query.get()
   ```
4. **Offline / Cache Fallback:** If network is unavailable, compute cosine similarity over the local `.daemon_memory.json` / `.daemon_diary.json` vector arrays with NumPy.
5. **Context Injection:** Inject the top-$K$ most relevant memory and diary facts into `ContextManager` dynamic prompt templates.

---

## 6. Migration Strategy

1. **Schema Migration Script (`scripts/migrate_to_vector_db.py`):**
   - Reads existing flat `core_brain` and historical diary entries.
   - Splits atomic memories into semantic chunks.
   - Generates embeddings client-side.
   - Writes batch updates with `Vector` objects to Firestore.
2. **Dual-Read / Graceful Fallback:**
   - Fall back to standard key-value brain if vector queries return empty or index is building.
