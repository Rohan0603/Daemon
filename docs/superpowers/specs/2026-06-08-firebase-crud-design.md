# Firebase CRUD Layer — Design Spec

> **For agentic workers:** REQUIRED SUB-SKILL: Use writing-plans skill to create the implementation plan after this spec is approved.

**Goal:** Eliminate duplicated Firebase init and raw Firestore calls by extracting a reusable `FirebaseCRUD` class with built-in retry.

**Architecture:** Single generic `FirebaseCRUD` class wraps `firestore.Client` with lazy init, one method per CRUD verb, and transparent retry (3 attempts / 0.5s backoff). `MemoryManager` and `seed_brain.py` consume it, dropping ~40 lines of duplicated init code and all raw `collection().document().get/set/add()` chains.

**Tech Stack:** Python 3.11+, `firebase-admin` SDK, `firestore.Client`

---

## 1. `FirebaseCRUD` class (`src/firebase_crud.py`)

### Interface

```python
class FirebaseCRUD:
    def __init__(self, creds_path: str | None = None)
    # Lazy init — no firebase_admin call until first CRUD operation.
    # creds_path defaults to src.brain_schema.CREDS_PATH.
    # If creds file missing or init fails, sets _available = False.

    @property
    def available(self) -> bool
    # True if Firestore client initialized successfully.

    @property
    def client(self) -> firestore.Client | None
    # Returns the raw client for advanced usage (e.g., firestore.SERVER_TIMESTAMP).

    # ── CRUD ────────────────────────────────────────────────────────────

    def get(self, collection: str, doc_id: str) -> dict | None
    # Read a single document. Returns dict or None if missing/error.

    def set(self, collection: str, doc_id: str, data: dict, merge: bool = True) -> bool
    # Write/overwrite a document. Returns True on success, False if unavailable.

    def add(self, collection: str, data: dict) -> str | None
    # Add a document with auto-generated ID. Returns the doc ID or None.

    def delete(self, collection: str, doc_id: str) -> bool
    # Delete a document. Returns True on success, False if unavailable.

    def query(
        self,
        collection: str,
        order_by: str | None = None,
        limit: int | None = None,
        ascending: bool = True,
    ) -> list[dict]
    # Query a collection. Returns list of to_dict() results (empty list on error).

    def read_all_text(
        self,
        collection: str,
        text_field: str = "text",
        order_by: str | None = None,
        limit: int | None = None,
        ascending: bool = True,
    ) -> list[str]
    # Convenience: query + extract a text field from each doc, skipping empties.
    # Used for diary fetches.
```

### Retry behavior

Every public CRUD method wraps in a `_retry` decorator/helper:

```
attempt 1 → success → return
attempt 1 → fail → sleep 0.5s → attempt 2
attempt 2 → fail → sleep 1.0s → attempt 3
attempt 3 → fail → log warning at method level → return fallback (None/False)
```

`_ensure_client()` is NOT retried — if init fails, `available=False` and all methods return fallback values immediately.

### Lazy initialization

```python
def _ensure_client(self) -> None:
    if self._client is not None:
        return
    try:
        cred = credentials.Certificate(self._creds_path)
        try:
            firebase_admin.get_app()
        except ValueError:
            firebase_admin.initialize_app(cred)
        self._client = firestore.client()
    except FileNotFoundError:
        logger.warning("...")
        self._available = False
    except Exception as e:
        logger.warning("...")
        self._available = False
```

Only `get`, `set`, `add`, `delete`, `query` call `_ensure_client()` as their first step.

### Edge cases

- **Missing creds file:** `_ensure_client` catches `FileNotFoundError`, sets `available=False`. Every method returns fallback quietly.
- **Transient network error:** Every method has 3 attempts with sleep. If all 3 fail, returns `None`/`False` — no exception propagates to the caller.
- **Firestore quota:** Same as transient — retry 3x then return fallback. Caller never needs a try/except.
- **Doc doesn't exist:** `get` returns `None` (not empty dict).
- **Partial document:** `get` returns whatever fields exist — caller handles missing fields.

### Testing strategy

All tests mock `firestore.Client` at the method level:

| Test | What it verifies |
|------|------------------|
| `test_get_returns_dict_when_doc_exists` | `document().get().to_dict()` returned |
| `test_get_returns_none_when_doc_missing` | `doc.exists = False` → None |
| `test_set_calls_document_set_with_merge` | `document().set(data, merge=True)` called |
| `test_add_returns_doc_id` | `add(data)` returns the result.id |
| `test_delete_calls_document_delete` | `document().delete()` called |
| `test_query_returns_list_of_dicts` | `stream()` yields docs, each `.to_dict()` |
| `test_query_returns_empty_on_error` | Exception during `stream()` → `[]` |
| `test_read_all_text_filters_empty` | Docs with `text=""` excluded |
| `test_retry_succeeds_on_second_attempt` | Flaky client raises on 1st, succeeds on 2nd |
| `test_retry_exhausted_returns_fallback` | 3 failures → returns None |
| `test_available_false_when_creds_missing` | `available` property is False |
| `test_available_true_when_creds_valid` | `available` property is True |
| `test_all_methods_return_fallback_when_unavailable` | `available=False` → every CRUD returns fallback |

---

## 2. `MemoryManager` refactored (`src/memory_manager.py`)

### What changes

- `__init__` creates `self.crud = FirebaseCRUD(creds_path)` instead of calling `firebase_admin` directly
- `self.db` is removed — consumers use `self.crud` instead
- `self._pending_writes` is kept as a last-resort fallback (when CRUD's 3 retries fail, queue it here)
- All raw `self.db.collection("X").document("Y").get()` chains replaced by `self.crud.get("X", "Y")`

### Method mapping

| Current | Replaced by |
|---------|-------------|
| `self.db.collection("daemon_data").document("core_brain").get()` | `self.crud.get("daemon_data", "core_brain")` |
| `self.db.collection("daemon_data").document("core_brain").set(d, merge=True)` | `self.crud.set("daemon_data", "core_brain", d, merge=True)` |
| `self.db.collection("daemon_diary").add(data)` | `self.crud.add("daemon_diary", data)` |
| `.order_by().limit().stream()` chain | `self.crud.read_all_text("daemon_diary", order_by="timestamp", limit=200)` |
| `.order_by().limit().stream()` in `retry_pending_writes` | `self.crud.add(...)` / `self.crud.set(...)` |
| Firestore init boilerplate | Deleted — delegated to `FirebaseCRUD.__init__` |

### Methods that STAY with the same signature

- `load_current_brain()` — body changes to use `self.crud`
- `update_brain(data)` — body changes, retry falls to `_pending_writes`
- `add_diary_entry(text)` — body changes, retry falls to `_pending_writes`
- `retry_pending_writes()` — body changes to use `self.crud`
- `fetch_all_diary_entries(limit=200)` — body changes to use `self.crud`
- `sync_to_local(memory)`, `sync_from_local(memory)` — use `self.crud` internally

### `_pending_writes` two-tier retry

```
CRUD operation → 3 retries → all failed → append to memory_manager._pending_writes
                                                      ↓
WriteCoalescer flush → MemoryManager.retry_pending_writes() → self.crud.add/set
                                                      ↓
                                              still fails → stays in deque
```

This is the same pattern as today, except today's `retry_pending_writes` calls raw Firestore. After refactor it calls `self.crud`.

### Test changes

The `mgr_db` and `mgr_no_db` fixtures currently inject `self.db` directly. They need to inject `self.crud` instead:

```python
@pytest.fixture
def mock_crud():
    return MagicMock(spec=FirebaseCRUD)

@pytest.fixture
def mgr_db(mock_crud):
    mgr = MemoryManager.__new__(MemoryManager)
    mgr.crud = mock_crud
    mgr._pending_writes = deque()
    return mgr
```

Existing 35 tests need mechanical rewiring: `mock_db.collection.return_value...` → `mock_crud.get.return_value = ...` etc. No new behavior tests needed — they already exist.

---

## 3. `seed_brain.py` refactored

### What changes

- Remove `import firebase_admin`, `from firebase_admin import credentials, firestore`
- Remove `_get_firestore_client()` function (~10 lines)
- `get_brain(db)` becomes inline `crud.get("daemon_data", "core_brain")`
- `set_brain(db, data)` becomes inline `crud.set("daemon_data", "core_brain", data, merge=True)`

### Before/After

```python
# BEFORE
def _get_firestore_client():
    cred = credentials.Certificate(_CREDS_PATH)
    try: firebase_admin.get_app()
    except ValueError: firebase_admin.initialize_app(cred)
    return firestore.client()

def get_brain(db):
    doc = db.collection("daemon_data").document("core_brain").get()
    ...

def set_brain(db, data):
    db.collection("daemon_data").document("core_brain").set(data, merge=True)
```

```python
# AFTER
from src.firebase_crud import FirebaseCRUD

def main():
    crud = FirebaseCRUD()
    if not crud.available:
        print("[seed_brain] Cannot connect to Firestore.", file=sys.stderr)
        sys.exit(1)
    current = crud.get("daemon_data", "core_brain") or {}
    ...
    crud.set("daemon_data", "core_brain", current, merge=True)
```

---

## 4. File inventory

| Action | File | Lines added/removed |
|--------|------|---------------------|
| **Create** | `src/firebase_crud.py` | ~120 new |
| **Modify** | `src/memory_manager.py` | ~-40 (remove init boilerplate, replace chains) |
| **Modify** | `seed_brain.py` | ~-40 (remove init + wrappers) |
| **Create** | `tests/test_firebase_crud.py` | ~200 new |
| **Modify** | `tests/test_memory_manager.py` | ~35 test bodies rewired (no count change) |

---

## 5. Exclusions (YAGNI)

- **Batched writes / transactions:** Not needed — `daemon_diary` uses single `add()`, `core_brain` uses single `set()`. Add if a future feature requires atomic multi-doc writes.
- **Collection group queries:** Not needed — only two top-level collections.
- **Real-time listeners / `on_snapshot`:** Not needed — Daemon only syncs at boot and quit.
- **Caching layer:** Not needed — every CRUD call goes to the network. Add if latency becomes an issue.
