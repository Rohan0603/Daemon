# Brain/Memory/Diary Generalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** (A) Make the brain schema dynamic — fields defined in `data/brain_schema.json` not hardcoded in `brain_schema.py`. (B) Add a unified `StorageBackend` abstraction over Memory/DiaryStore/History and a single `query_memory` MCP tool replacing three separate read tools.

**Architecture:** Two independent tracks. Track A: `brain_schema.py` loads its 22-field schema from a JSON file at boot, validates it, and the `PluginRegistry` can register additional fields before validation runs. Track B: `StorageBackend` ABC with `get/set/query` methods implemented by all three stores; `query_memory(type, filter)` MCP tool dispatches to the right backend; the 3 existing read tools stay as thin wrappers.

**Tech Stack:** Python 3.14, `src/brain_schema.py`, `src/memory.py`, `src/diary_store.py`, `src/history.py`, `src/mcp_server.py`, `src/plugin_registry.py`, `data/brain_schema.json`

---

## File Map

### Track A — Dynamic Brain Schema

| File | Action |
|------|--------|
| `data/brain_schema.json` | CREATE — serialized version of current BRAIN_SCHEMA |
| `src/brain_schema.py` | MODIFY — load schema from JSON, validate, PluginRegistry hook |
| `src/plugin_registry.py` | MODIFY — add `register_brain_field()` method |
| `tests/test_brain_schema_dynamic.py` | CREATE |

### Track B — Unified Storage Interface

| File | Action |
|------|--------|
| `src/storage_backend.py` | CREATE — StorageBackend ABC |
| `src/memory.py` | MODIFY — implement StorageBackend |
| `src/diary_store.py` | MODIFY — implement StorageBackend |
| `src/history.py` | MODIFY — implement StorageBackend |
| `src/mcp_server.py` | MODIFY — add `query_memory` MCP tool |
| `tests/test_storage_backend.py` | CREATE |
| `tests/test_query_memory_mcp.py` | CREATE |

---

## Track A: Dynamic Brain Schema

### Task A1: Create brain_schema.json

**Files:**
- Create: `data/brain_schema.json`

- [ ] **Step 1: Extract current BRAIN_SCHEMA from brain_schema.py to JSON**

Read current `BRAIN_SCHEMA` dict in `src/brain_schema.py`. Create `data/brain_schema.json` with the equivalent structure:

```json
{
  "version": 1,
  "fields": {
    "user_name":              {"type": "str",  "locked": true,  "default": ""},
    "user_profession":        {"type": "str",  "locked": true,  "default": ""},
    "user_habits":            {"type": "str",  "locked": false, "default": ""},
    "user_preferences":       {"type": "str",  "locked": false, "default": ""},
    "user_long_term_goals":   {"type": "str",  "locked": false, "default": ""},
    "user_imposed_rules":     {"type": "str",  "locked": false, "default": ""},
    "pet_name":               {"type": "str",  "locked": true,  "default": "Kenny"},
    "pet_personality":        {"type": "str",  "locked": true,  "default": ""},
    "pet_role":               {"type": "str",  "locked": true,  "default": ""},
    "pet_origin":             {"type": "str",  "locked": true,  "default": ""},
    "pet_appearance":         {"type": "str",  "locked": true,  "default": ""},
    "pet_system_awareness":   {"type": "str",  "locked": true,  "default": ""},
    "pet_likes":              {"type": "str",  "locked": false, "default": ""},
    "pet_quirks":             {"type": "str",  "locked": false, "default": ""},
    "pet_habits":             {"type": "str",  "locked": false, "default": ""},
    "pet_fears":              {"type": "str",  "locked": false, "default": ""},
    "pet_catchphrases":       {"type": "list", "locked": false, "default": []},
    "mission_directive":      {"type": "str",  "locked": true,  "default": ""},
    "mission_goals":          {"type": "list", "locked": false, "default": []},
    "intel_archive":          {"type": "str",  "locked": false, "default": ""},
    "intel_insider_knowledge":{"type": "str",  "locked": false, "default": ""},
    "pet_affinity_score":     {"type": "int",  "locked": false, "default": 0},
    "pet_current_mood":       {"type": "str",  "locked": false, "default": "neutral"},
    "progression_flags":      {"type": "dict", "locked": false, "default": {}}
  }
}
```

Verify field count matches `len(BRAIN_SCHEMA)` in current code.

- [ ] **Step 2: Commit**

```bash
git add data/brain_schema.json
git commit -m "feat(brain): extract brain schema to JSON file"
```

---

### Task A2: Dynamic schema loading in brain_schema.py

**Files:**
- Modify: `src/brain_schema.py`
- Create: `tests/test_brain_schema_dynamic.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_brain_schema_dynamic.py`:

```python
import json
import tempfile
from pathlib import Path
import pytest


def test_load_schema_from_json_file(tmp_path):
    schema_file = tmp_path / "brain_schema.json"
    schema_data = {
        "version": 1,
        "fields": {
            "test_field": {"type": "str", "locked": False, "default": "hello"}
        }
    }
    schema_file.write_text(json.dumps(schema_data))
    from src.brain_schema import load_brain_schema
    schema = load_brain_schema(schema_path=str(schema_file))
    assert "test_field" in schema
    assert schema["test_field"]["default"] == "hello"


def test_locked_field_preserved(tmp_path):
    schema_file = tmp_path / "brain_schema.json"
    schema_data = {
        "version": 1,
        "fields": {
            "locked_field": {"type": "str", "locked": True, "default": "x"}
        }
    }
    schema_file.write_text(json.dumps(schema_data))
    from src.brain_schema import load_brain_schema
    schema = load_brain_schema(schema_path=str(schema_file))
    assert schema["locked_field"]["locked"] is True


def test_missing_schema_file_raises():
    from src.brain_schema import load_brain_schema
    with pytest.raises(FileNotFoundError):
        load_brain_schema(schema_path="/nonexistent/brain_schema.json")


def test_invalid_field_type_raises(tmp_path):
    schema_file = tmp_path / "brain_schema.json"
    schema_data = {
        "version": 1,
        "fields": {
            "bad_field": {"type": "badtype", "locked": False, "default": ""}
        }
    }
    schema_file.write_text(json.dumps(schema_data))
    from src.brain_schema import load_brain_schema
    with pytest.raises(ValueError, match="Invalid type"):
        load_brain_schema(schema_path=str(schema_file))


def test_apply_brain_update_respects_loaded_schema(tmp_path):
    schema_file = tmp_path / "brain_schema.json"
    schema_data = {
        "version": 1,
        "fields": {
            "custom_field": {"type": "str", "locked": False, "default": ""}
        }
    }
    schema_file.write_text(json.dumps(schema_data))
    from src.brain_schema import load_brain_schema, apply_brain_update
    schema = load_brain_schema(schema_path=str(schema_file))
    brain = {"custom_field": ""}
    updated, rejected = apply_brain_update(brain, {"custom_field": "hello"}, schema=schema)
    assert updated["custom_field"] == "hello"
    assert len(rejected) == 0


def test_apply_brain_update_rejects_locked_field(tmp_path):
    schema_file = tmp_path / "brain_schema.json"
    schema_data = {
        "version": 1,
        "fields": {
            "locked_field": {"type": "str", "locked": True, "default": "orig"}
        }
    }
    schema_file.write_text(json.dumps(schema_data))
    from src.brain_schema import load_brain_schema, apply_brain_update
    schema = load_brain_schema(schema_path=str(schema_file))
    brain = {"locked_field": "orig"}
    updated, rejected = apply_brain_update(brain, {"locked_field": "new"}, schema=schema)
    assert updated["locked_field"] == "orig"
    assert "locked_field" in rejected
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
py -m pytest tests/test_brain_schema_dynamic.py -v
```

- [ ] **Step 3: Add `load_brain_schema()` to brain_schema.py**

In `src/brain_schema.py`, add:

```python
import json
from pathlib import Path

VALID_FIELD_TYPES = frozenset({"str", "int", "float", "list", "dict", "bool"})
_DEFAULT_SCHEMA_PATH = str(Path(__file__).parent.parent / "data" / "brain_schema.json")


def load_brain_schema(schema_path: str = _DEFAULT_SCHEMA_PATH) -> dict:
    """Load brain schema from JSON file. Returns dict of field_name → spec."""
    path = Path(schema_path)
    if not path.exists():
        raise FileNotFoundError(f"Brain schema file not found: {schema_path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    fields = data.get("fields", {})
    for fname, spec in fields.items():
        if spec.get("type") not in VALID_FIELD_TYPES:
            raise ValueError(f"Invalid type {spec.get('type')!r} for field {fname!r}")
    return fields
```

**Update `apply_brain_update` signature** to accept optional `schema` param:

```python
def apply_brain_update(
    brain: dict,
    updates: dict,
    schema: dict | None = None,
) -> tuple[dict, list[str]]:
    """Apply LLM brain updates. Returns (updated_brain, rejected_field_names)."""
    if schema is None:
        schema = BRAIN_SCHEMA  # backward compat: fall back to hardcoded schema
    rejected = []
    result = dict(brain)
    for key, value in updates.items():
        if key not in schema:
            rejected.append(key)
            continue
        spec = schema[key]
        if spec.get("locked"):
            rejected.append(key)
            continue
        expected_type = spec.get("type", "str")
        # Type coercion / validation
        try:
            if expected_type == "str":
                result[key] = str(value)
            elif expected_type == "int":
                result[key] = int(value)
            elif expected_type == "float":
                result[key] = float(value)
            elif expected_type in ("list", "dict"):
                if not isinstance(value, (list, dict)):
                    raise ValueError
                result[key] = value
            elif expected_type == "bool":
                result[key] = bool(value)
        except (ValueError, TypeError):
            rejected.append(key)
    return result, rejected
```

**Update `DEFAULT_BRAIN`** to be derived from `BRAIN_SCHEMA`:

```python
DEFAULT_BRAIN: dict = {k: v["default"] for k, v in BRAIN_SCHEMA.items()}
```

- [ ] **Step 4: Run tests**

```bash
py -m pytest tests/test_brain_schema_dynamic.py tests/test_brain_schema.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/brain_schema.py tests/test_brain_schema_dynamic.py
git commit -m "feat(brain): dynamic schema loading from data/brain_schema.json"
```

---

### Task A3: PluginRegistry brain field registration

**Files:**
- Modify: `src/plugin_registry.py`
- Modify: `daemon.py`

- [ ] **Step 1: Add `register_brain_field()` to PluginRegistry**

In `src/plugin_registry.py`, add to the `PluginRegistry` class:

```python
def register_brain_field(
    self,
    field_name: str,
    field_type: str,
    default,
    locked: bool = False,
    plugin_name: str = "unknown",
) -> None:
    """Register a plugin-contributed brain schema field.

    Call before brain schema validation runs at boot.
    field_type must be one of: str, int, float, list, dict, bool
    """
    from src.brain_schema import VALID_FIELD_TYPES
    if field_type not in VALID_FIELD_TYPES:
        raise ValueError(f"Invalid field_type {field_type!r} for field {field_name!r}")
    if field_name in self._brain_fields:
        logger.warning("Plugin %s overrides existing brain field %s", plugin_name, field_name)
    self._brain_fields[field_name] = {
        "type": field_type,
        "locked": locked,
        "default": default,
        "plugin": plugin_name,
    }
    logger.debug("Plugin %s registered brain field: %s (%s)", plugin_name, field_name, field_type)

def get_brain_fields(self) -> dict:
    """Return all plugin-contributed brain schema fields."""
    return dict(self._brain_fields)
```

Add `self._brain_fields: dict = {}` to `PluginRegistry.__init__`.

- [ ] **Step 2: Merge plugin fields into schema at boot**

In `daemon.py`, after `PluginManager.load_all()` and before `PetWindow(...)` construction, add:

```python
# Merge plugin-contributed brain fields into loaded schema
from src.brain_schema import load_brain_schema, BRAIN_SCHEMA
_loaded_schema = load_brain_schema()
_loaded_schema.update(plugin_registry.get_brain_fields())
# Patch module-level BRAIN_SCHEMA so apply_brain_update sees new fields
import src.brain_schema as _bs
_bs.BRAIN_SCHEMA = _loaded_schema
_bs.DEFAULT_BRAIN = {k: v["default"] for k, v in _loaded_schema.items()}
```

- [ ] **Step 3: Run existing plugin + brain tests**

```bash
py -m pytest tests/test_plugin_system.py tests/test_brain_schema.py tests/test_brain_schema_dynamic.py -v
```

Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add src/plugin_registry.py daemon.py
git commit -m "feat(brain): PluginRegistry.register_brain_field for dynamic schema extension"
```

---

## Track B: Unified Storage Interface

### Task B1: StorageBackend ABC

**Files:**
- Create: `src/storage_backend.py`
- Create: `tests/test_storage_backend.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_storage_backend.py`:

```python
from abc import ABC
from src.storage_backend import StorageBackend


def test_storage_backend_is_abstract():
    assert issubclass(StorageBackend, ABC)


def test_storage_backend_has_required_methods():
    for method in ("get", "set", "query", "all_entries", "count"):
        assert hasattr(StorageBackend, method), f"Missing method: {method}"


def test_concrete_without_methods_raises():
    class IncompleteBackend(StorageBackend):
        pass
    import pytest
    with pytest.raises(TypeError):
        IncompleteBackend()
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
py -m pytest tests/test_storage_backend.py -v
```

- [ ] **Step 3: Implement StorageBackend**

Create `src/storage_backend.py`:

```python
"""Abstract storage backend interface for Memory, DiaryStore, and History."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Optional


class StorageBackend(ABC):
    """Unified interface for all persistent stores."""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Get a single entry by key/id. Returns None if not found."""

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Set/update a single entry by key/id."""

    @abstractmethod
    def query(self, filter_fn=None, limit: int = 50) -> list[dict]:
        """Return entries matching filter_fn (callable → bool). filter_fn=None returns all.

        Each returned item must be a dict with at least:
          - "id": str — unique identifier for this entry
          - "content": str — human-readable content
          - "timestamp": str — ISO 8601 timestamp (or empty string)
        """

    @abstractmethod
    def all_entries(self) -> list[dict]:
        """Return all entries as list of dicts (same format as query)."""

    @abstractmethod
    def count(self) -> int:
        """Return number of stored entries."""
```

- [ ] **Step 4: Run tests**

```bash
py -m pytest tests/test_storage_backend.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/storage_backend.py tests/test_storage_backend.py
git commit -m "feat(storage): add StorageBackend abstract interface"
```

---

### Task B2: Implement StorageBackend on Memory, DiaryStore, History

**Files:**
- Modify: `src/memory.py`
- Modify: `src/diary_store.py`
- Modify: `src/history.py`

- [ ] **Step 1: Implement on Memory**

In `src/memory.py`, update `Memory` class to inherit from `StorageBackend`:

```python
from src.storage_backend import StorageBackend

class Memory(StorageBackend):
    # ... existing code unchanged ...

    def get(self, key: str):
        return self._data.get(key)

    def set(self, key: str, value) -> None:
        self.remember(key, value)   # delegates to existing remember()

    def query(self, filter_fn=None, limit: int = 50) -> list[dict]:
        entries = [
            {"id": k, "content": str(v), "timestamp": ""}
            for k, v in self._data.items()
        ]
        if filter_fn:
            entries = [e for e in entries if filter_fn(e)]
        return entries[:limit]

    def all_entries(self) -> list[dict]:
        return self.query()

    def count(self) -> int:
        return len(self._data)
```

- [ ] **Step 2: Implement on DiaryStore**

In `src/diary_store.py`, update `DiaryStore` class:

```python
from src.storage_backend import StorageBackend

class DiaryStore(StorageBackend):
    # ... existing code unchanged ...

    def get(self, key: str):
        """Return diary entry by content hash (key)."""
        for entry in self._entries:
            if entry.get("hash") == key:
                return entry
        return None

    def set(self, key: str, value) -> None:
        """Add a new diary entry (key ignored, value is the entry text)."""
        self.add(str(value))  # delegates to existing add()

    def query(self, filter_fn=None, limit: int = 50) -> list[dict]:
        entries = [
            {
                "id": e.get("hash", ""),
                "content": e.get("text", e.get("content", "")),
                "timestamp": e.get("timestamp", ""),
            }
            for e in self._entries
        ]
        if filter_fn:
            entries = [e for e in entries if filter_fn(e)]
        return entries[-limit:]  # most recent first

    def all_entries(self) -> list[dict]:
        return self.query(limit=len(self._entries))

    def count(self) -> int:
        return len(self._entries)
```

- [ ] **Step 3: Implement on History**

In `src/history.py`, update `History` class:

```python
from src.storage_backend import StorageBackend

class History(StorageBackend):
    # ... existing code unchanged ...

    def get(self, key: str):
        """Return history entry at index (key as str int)."""
        try:
            return self._turns[int(key)]
        except (ValueError, IndexError):
            return None

    def set(self, key: str, value) -> None:
        """Append a new turn (key ignored, value is turn dict or str)."""
        if isinstance(value, dict):
            self._turns.append(value)
            self._dirty = True
        else:
            self.add(role="user", content=str(value))

    def query(self, filter_fn=None, limit: int = 50) -> list[dict]:
        entries = [
            {
                "id": str(i),
                "content": f"{t.get('role', '')}: {t.get('content', '')}",
                "timestamp": t.get("timestamp", ""),
            }
            for i, t in enumerate(self._turns)
        ]
        if filter_fn:
            entries = [e for e in entries if filter_fn(e)]
        return entries[-limit:]

    def all_entries(self) -> list[dict]:
        return self.query(limit=len(self._turns))

    def count(self) -> int:
        return len(self._turns)
```

- [ ] **Step 4: Run existing tests for all three stores**

```bash
py -m pytest tests/test_memory.py tests/test_diary_store.py tests/test_history.py -v
```

Expected: all PASS (interface methods are additive — no existing behavior changed)

- [ ] **Step 5: Commit**

```bash
git add src/memory.py src/diary_store.py src/history.py
git commit -m "feat(storage): implement StorageBackend on Memory, DiaryStore, History"
```

---

### Task B3: `query_memory` MCP tool

**Files:**
- Modify: `src/mcp_server.py`
- Create: `tests/test_query_memory_mcp.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_query_memory_mcp.py`:

```python
import json
import pytest
from unittest.mock import MagicMock


def _make_handler(memory=None, diary=None, history=None):
    from src.mcp_server import MCPHandler
    handler = MCPHandler.__new__(MCPHandler)
    handler._memory = memory or MagicMock()
    handler._diary = diary or MagicMock()
    handler._history = history or MagicMock()
    handler._config = {"consent": {}}
    return handler


def test_query_memory_type_memory():
    mem = MagicMock()
    mem.query.return_value = [{"id": "k1", "content": "v1", "timestamp": ""}]
    handler = _make_handler(memory=mem)
    result = handler._handle_query_memory({"type": "memory", "limit": 10})
    assert result["result"]["type"] == "memory"
    assert len(result["result"]["entries"]) == 1
    mem.query.assert_called_once()


def test_query_memory_type_diary():
    diary = MagicMock()
    diary.query.return_value = [{"id": "h1", "content": "entry", "timestamp": "2026-06-21"}]
    handler = _make_handler(diary=diary)
    result = handler._handle_query_memory({"type": "diary", "limit": 5})
    assert result["result"]["type"] == "diary"
    assert len(result["result"]["entries"]) == 1


def test_query_memory_type_history():
    hist = MagicMock()
    hist.query.return_value = [{"id": "0", "content": "user: hi", "timestamp": ""}]
    handler = _make_handler(history=hist)
    result = handler._handle_query_memory({"type": "history", "limit": 20})
    assert result["result"]["type"] == "history"


def test_query_memory_invalid_type_returns_error():
    handler = _make_handler()
    result = handler._handle_query_memory({"type": "unknown"})
    assert "error" in result


def test_query_memory_with_keyword_filter():
    from src.memory import Memory
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        mem = Memory(path=os.path.join(d, "mem.json"))
        mem.remember("fav_lang", "Python")
        mem.remember("fav_food", "Pizza")
        handler = _make_handler(memory=mem)
        result = handler._handle_query_memory({"type": "memory", "keyword": "Python"})
        entries = result["result"]["entries"]
        assert any("Python" in e["content"] for e in entries)
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
py -m pytest tests/test_query_memory_mcp.py -v
```

- [ ] **Step 3: Add `query_memory` to MCP_TOOLS list**

In `src/mcp_server.py`, add to `MCP_TOOLS`:

```python
{
    "name": "query_memory",
    "description": "Query any of Daemon's persistent stores: memory (key-value facts), diary (timestamped entries), or history (conversation turns).",
    "inputSchema": {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": ["memory", "diary", "history"],
                "description": "Which store to query."
            },
            "keyword": {
                "type": "string",
                "description": "Optional keyword filter — returns only entries whose content contains this string (case-insensitive)."
            },
            "limit": {
                "type": "integer",
                "description": "Max entries to return (default 20, max 50).",
                "default": 20
            }
        },
        "required": ["type"]
    }
}
```

- [ ] **Step 4: Implement `_handle_query_memory`**

In `MCPHandler`:

```python
def _handle_query_memory(self, params: dict) -> dict:
    store_type = params.get("type", "")
    keyword = params.get("keyword", "").lower()
    limit = min(int(params.get("limit", 20)), 50)

    backend_map = {
        "memory": self._memory,
        "diary":  self._diary,
        "history": self._history,
    }
    if store_type not in backend_map:
        return {"error": {"code": -32602, "message": f"Unknown type: {store_type!r}"}}

    backend = backend_map[store_type]
    filter_fn = (lambda e: keyword in e.get("content", "").lower()) if keyword else None
    entries = backend.query(filter_fn=filter_fn, limit=limit)

    return {"result": {"type": store_type, "count": len(entries), "entries": entries}}
```

Wire dispatch in `_dispatch_tool()`:
```python
elif name == "query_memory":
    return self._handle_query_memory(arguments)
```

- [ ] **Step 5: Run tests**

```bash
py -m pytest tests/test_query_memory_mcp.py tests/test_mcp_server.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/mcp_server.py tests/test_query_memory_mcp.py
git commit -m "feat(storage): add query_memory MCP tool with unified StorageBackend dispatch"
```

---

### Task B4: Full regression

- [ ] **Step 1: Run full suite**

```bash
py -m pytest tests/ -v --timeout=30
```

Expected: all pass, 0 failures.

- [ ] **Step 2: Squash merge**

```bash
git checkout master
git merge --squash task-74-brain-memory-generalization
git commit -m "feat: dynamic brain schema + unified StorageBackend + query_memory MCP (Phase 74)"
git branch -D task-74-brain-memory-generalization
```
