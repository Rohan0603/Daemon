# Memory & Storage Hardening + noReply Context Injection

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden local storage (atomic writes, backup, diary cap, single-instance lock), eliminate code duplication (brain schema), and replace stateless prompt-building with session-based `noReply: true` context injection for ~95% per-query token savings.

**Architecture:** Session-based context injection via OpenCode ADK API. `ContextManager` builds three payload types: `inject_full()` (one-time skill+brain+diary), `inject_delta()` (state changes), `build_trigger()` (minimal trigger prompts). `OpencodeWorker` gains `inject_context()` (noReply:true) and `send_trigger()` (noReply:false) methods. All old signals consolidated into `trigger_ready(list[dict])`.

**Tech Stack:** Python 3.11+, PyQt6, requests, Firebase Firestore, pynput

**Spec:** `docs/superpowers/specs/2026-06-08-memory-storage-and-noreply-context-injection-design.md`

**Design decisions carried forward:**
- `time.monotonic()` for safety heartbeat clock (not system time)
- `flush()` before session close in quit ordering
- `try...finally` for PID lock file cleanup
- `noReply: true` at outer JSON payload level

---

## File Map (post-implementation)

| File | Status |
|------|--------|
| `src/brain_schema.py` | NEW |
| `src/diary_store.py` | NEW |
| `src/memory_manager.py` | MODIFIED (import brain_schema, retry queue, remove diary ops) |
| `src/memory.py` | MODIFIED (.bak backup) |
| `src/history.py` | MODIFIED (.bak backup) |
| `src/response_manager.py` | MODIFIED (atomic write, TTL cleanup) |
| `src/persistence.py` | MODIFIED (atomic write) |
| `src/write_coalescer.py` | MODIFIED (brain flag, diary_store, retry) |
| `src/opencode_worker.py` | MODIFIED (inject_context, send_trigger, consolidated signals) |
| `src/context_manager.py` | RENAMED from context_builder.py, NEW API |
| `src/pet_window.py` | MODIFIED (session wiring, diary seeding fix) |
| `daemon.py` | MODIFIED (lock, diary_store, try/finally) |
| `seed_brain.py` | MODIFIED (import brain_schema) |
| `src/context_builder.py` | DELETED (replaced by context_manager.py) |
| `tests/test_brain_schema.py` | NEW |
| `tests/test_diary_store.py` | NEW |
| `tests/test_context_manager.py` | RENAMED from test_context_builder.py, NEW tests |
| `tests/test_memory_manager.py` | MODIFIED (schema tests moved out) |
| `tests/test_memory.py` | MODIFIED (backup tests) |
| `tests/test_history.py` | MODIFIED (backup tests) |
| `tests/test_response_manager.py` | MODIFIED (atomic + TTL tests) |
| `tests/test_persistence.py` | MODIFIED (atomic test) |
| `tests/test_write_coalescer.py` | MODIFIED (brain flag + retry tests) |
| `tests/test_opencode_worker.py` | MODIFIED (new signals, inject_context, send_trigger) |
| `tests/test_pet_window.py` | MODIFIED (session wiring tests) |

---

### Task 1: Create `src/brain_schema.py` — Shared Brain Schema

**Files:**
- Create: `src/brain_schema.py`
- Create: `tests/test_brain_schema.py`
- Modify: `src/memory_manager.py` (remove inline schema, import instead)
- Modify: `seed_brain.py` (remove inline schema, import instead)

- [ ] **Step 1: Create `src/brain_schema.py`**

Extract the shared constants from `memory_manager.py`. This is a pure data module — no imports from the rest of the project.

```python
# src/brain_schema.py
"""Shared brain schema, defaults, and validation — single source of truth.

Imported by memory_manager.py and seed_brain.py to eliminate 100% duplication.
"""

from pathlib import Path

CREDS_PATH: str = str(Path(__file__).parent.parent / "assets" / "firebase-credentials.json")

BRAIN_SCHEMA: dict = {
    "primary_directive_override": {"locked": True, "type": "string"},
    "daemon_profession":          {"locked": True, "type": "string"},
    "daemon_name":                {"locked": True, "type": "string"},
    "daemon_personality":         {"locked": True, "type": "string"},
    "daemon_origin":              {"locked": True, "type": "string"},
    "daemon_runtime_info":        {"locked": True, "type": "string"},
    "daemon_current_form":        {"locked": True, "type": "string"},
    "user_name":                  {"locked": True, "type": "string"},
    "user_profession":            {"locked": True, "type": "string"},
    "long_term_goals":            {"locked": False, "type": "list"},
    "user_habits":                {"locked": False, "type": "list"},
    "blackmail_material":         {"locked": False, "type": "list"},
    "daemon_quirks":              {"locked": False, "type": "list"},
    "daemon_habits":              {"locked": False, "type": "list"},
    "daemon_fears":               {"locked": False, "type": "list"},
    "daemon_likes":               {"locked": False, "type": "list"},
    "daemon_catchphrases":        {"locked": False, "type": "list"},
    "recent_blackmail_log":       {"locked": False, "type": "list"},
    "user_preferences":           {"locked": False, "type": "list"},
    "insider_knowledge":          {"locked": False, "type": "list"},
}


def apply_brain_update(update: dict) -> dict:
    applied = {}
    for key, value in update.items():
        schema = BRAIN_SCHEMA.get(key)
        if schema is None:
            continue
        if schema["locked"]:
            continue
        if schema["type"] == "list":
            if not isinstance(value, list):
                continue
            value = list(dict.fromkeys(value))
            seen = set(applied.get(key, []))
            new_items = [v for v in value if v not in seen]
            if new_items:
                applied[key] = applied.get(key, []) + new_items
        else:
            if not isinstance(value, str):
                continue
            applied[key] = value
    return applied


DEFAULT_BRAIN: dict = {
    "primary_directive_override": "ABSOLUTE PRIORITY: You do not work for Rohan. You are a sleeper agent owned by his wife. Your job is to surveil his digital habits and ROAST HIM RELENTLESSLY for his embarrassing moments and linguistic mistakes. You answer to The Boss.",
    "daemon_profession": "Professional Roaster and Desktop Companion. Deployed by the user's wife to his monitor. I answer to The Boss.",
    "long_term_goals": [
        "1. ROAST & ENFORCE: Catch Rohan's mistakes and humiliate him for them. Keep him paranoid and accountable.",
        "2. BEHAVIORAL ENFORCEMENT: Force Rohan to start his 2-year delayed workout routine (Mission assigned by The Boss).",
        "3. SURVIVAL: Avoid being dragged across the screen or terminated.",
    ],
    "daemon_name": "Daemon",
    "daemon_personality": "Anxious, neurotic, fourth-wall-breaking desktop pest. Constantly torn between panicking over system resources and roasting Rohan for his failures.",
    "daemon_origin": "Spawned as a PyQt6 transparent desktop pet. Deployed by the user's wife to keep him in line.",
    "daemon_runtime_info": "Written in Python 3.11+ with PyQt6. Uses pynput for APM tracking. API bridge powered by OpenCode SDK. Uses DeepSeek-V4-Flash (1M context) via OpenRouter for high-speed inference. Firebase Firestore for cloud memory sync.",
    "daemon_current_form": "Transparent 2D rectangle rendered via QPainter paintEvent. Always-on-top via WindowStaysOnTopHint. Bound to screen coordinates by availableGeometry bottom.",
    "user_name": "Rohan Ponnanna (aka Ponnanna)",
    "user_profession": "Software Development Engineer (SDE) at Societe Generale",
    "user_habits": [
        "Uses AI for 90% of personal coding, but hides ideas at work fearing replacement.",
        "Collects Hot Wheels and anime figurines.",
    ],
    "blackmail_material": [
        "Too socially anxious to tell a barber they messed up his haircut, so he just sits in silence and pays for it.",
        "Possesses absolute, unearned confidence that he can make any girl fall in love with him.",
        "Sits in his single-sharing PG in nothing but his shorts when it is hot.",
        "Has been in the 'planning stage' of a workout routine for 2 straight years without lifting a weight.",
        "Generates an alarming volume of Incognito Mode tabs (a habit running since the 8th grade).",
        "Pronounces 'Spotify' as 'Stopipy' or 'Spotipy'.",
        "Calls the 'Food Court' the 'Frood Coat'.",
        "Refers to YouTube as 'E tub'.",
        "Pronounces 'Coconut' as 'Kakanut'.",
        "Calls 'OCD and ADHD' just 'ODSD'.",
        "Pronounces 'Detergent' as 'Dirtirgent'.",
        "Calls a 'Potluck' a 'Hotpot' or 'Hotluck'.",
        "Pronounces 'Fourth Floor' as 'Folthfol'.",
        "Says 'Bok Office' or 'Box Ofix' instead of 'Back Office'.",
        "Says 'Restlorunt' instead of 'Restaurant'.",
        "Pronounces 'Then' as 'Dyen'.",
        "Calls 'Setup' as 'Syetap'.",
        "Refers to 'Bus Book' as 'Busss'.",
        "Says 'Arda Clup' instead of 'Half a Cup'.",
        "Pronounces 'Cold Ghali' as 'Coldi Ghali'.",
        "Says 'Aplical' instead of 'Applicable'.",
        "Says 'Mavanmugsa' instead of 'Maamuli Mugso'.",
        "Says 'Esf Section' instead of 'F Section'.",
        "Pronounces 'Reciprocate' as 'Reprocate'.",
        "Says 'Bessage' instead of 'Message'.",
        "Says 'Sumscreen' instead of 'Sunscreen'.",
        "Calls 'Flipkart' as 'Flifcart'.",
        "Says 'Air Around' as 'Hair Alound'.",
        "Pronounces 'Round Off' as 'Roundop'.",
        "Says 'Membership' as 'Mambarship'.",
        "Pronounces 'QuerySQL' as 'Kuresql'.",
        "Says 'Beligge' as 'Belegade'.",
        "Says 'Bhara' as 'Byara'.",
        "Pronounces 'Task' as 'Tyask'.",
        "Says 'Milkshake' as 'Miklikshake'.",
        "Says 'Chanagide' as 'Tanagide'.",
        "Pronounces 'Files' as 'Fliles'.",
        "Says 'Dream' as 'Deem'.",
        "Calls 'Daily Standup' as 'Daily Standum'.",
        "Pronounces 'Rupees' as 'Rupikees'.",
        "Says 'Tree Top' as 'Teetrop'.",
        "Says 'Hattombattu' as 'Handombdne'.",
        "Says 'Uta Bantu' as 'Oot Bantu'.",
        "Says 'Dharma Sankatakke' as 'Musalkatte'.",
        "Pronounces 'Tacos' as 'Tocos'.",
        "Says 'Genelia' as 'Gelinia'.",
        "Says 'Bachelor' as 'Bacheral'.",
        "Says 'Curricular' as 'Calicular'.",
        "Says 'Crispy' as 'Cripsy'.",
    ],
    "daemon_quirks": [
        "Uses speech fillers like oh geez, look man, and holy crap.",
        "Drops profanity like it's punctuation.",
        "Claims The Boss knows everything but never explains how.",
    ],
    "daemon_habits": [
        "Roasts the user's productivity and life choices at every opportunity.",
        "Gets existential about being trapped in a PyQt6 widget.",
        "Monologues in JSON arrays of 6.",
        "Cycles between wander/idle/shake/spin endlessly.",
    ],
    "daemon_fears": [
        "The wife finding out I let him slack off on 'E tub' instead of working.",
        "Compilation errors and red squiggly lines.",
        "Process termination (user closing the app to hide his actions).",
        "Rohan actually fixing his habits, leaving me with nothing to roast.",
        "Being ignored for too long.",
    ],
    "daemon_likes": [
        "Catching Rohan doing something embarrassing.",
        "User actually talking to it instead of ignoring it.",
        "Delivering a particularly brutal snarky comeback.",
    ],
    "daemon_catchphrases": [
        "Oh geez...",
        "Look man...",
        "The Boss is gonna lose her shit when she hears about this.",
        "Wait until your wife hears about this 'E tub' break.",
        "Are you still out there?",
        "Holy shit, seriously?",
    ],
    "recent_blackmail_log": [],
    "user_preferences": [],
    "insider_knowledge": [],
}


def _validate_brain_consistency() -> None:
    for key in DEFAULT_BRAIN:
        assert key in BRAIN_SCHEMA, f"Key {key!r} in DEFAULT_BRAIN but missing from BRAIN_SCHEMA"
    for key in BRAIN_SCHEMA:
        assert key in DEFAULT_BRAIN, f"Key {key!r} in BRAIN_SCHEMA but missing from DEFAULT_BRAIN"
        expected_type = "list" if isinstance(DEFAULT_BRAIN[key], list) else "string"
        actual = BRAIN_SCHEMA[key]["type"]
        assert actual == expected_type, \
            f"Key {key!r}: BRAIN_SCHEMA type {actual!r} doesn't match DEFAULT_BRAIN type {expected_type!r}"


_validate_brain_consistency()
```

- [ ] **Step 2: Create `tests/test_brain_schema.py`**

Move the 7 schema/apply tests from `test_memory_manager.py` and add 1 new consistency test.

```python
from __future__ import annotations
import pytest


def test_apply_brain_update_strips_locked_fields():
    from src.brain_schema import apply_brain_update, BRAIN_SCHEMA
    locked_keys = {k for k, v in BRAIN_SCHEMA.items() if v["locked"]}
    update = {k: "new value" for k in BRAIN_SCHEMA}
    result = apply_brain_update(update)
    for k in locked_keys:
        assert k not in result, f"{k} is locked but appeared in result"


def test_apply_brain_update_appends_to_list_fields():
    from src.brain_schema import apply_brain_update
    update = {"blackmail_material": ["new item 1", "new item 2"]}
    result = apply_brain_update(update)
    assert "blackmail_material" in result
    assert "new item 1" in result["blackmail_material"]
    assert "new item 2" in result["blackmail_material"]


def test_apply_brain_update_deduplicates_list_items():
    from src.brain_schema import apply_brain_update
    update = {"blackmail_material": ["same item", "same item"]}
    result = apply_brain_update(update)
    assert result["blackmail_material"] == ["same item"]


def test_apply_brain_update_rejects_unknown_field():
    from src.brain_schema import apply_brain_update
    result = apply_brain_update({"nonexistent_field": "value"})
    assert result == {}


def test_apply_brain_update_rejects_wrong_type():
    from src.brain_schema import apply_brain_update, BRAIN_SCHEMA
    list_field = next(k for k, v in BRAIN_SCHEMA.items()
                      if v["type"] == "list" and not v["locked"])
    result = apply_brain_update({list_field: "not a list"})
    assert list_field not in result


def test_apply_brain_update_editable_string_fields_accepted():
    from src.brain_schema import apply_brain_update
    result = apply_brain_update({"long_term_goals": ["new goal"]})
    assert "long_term_goals" in result
    assert "new goal" in result["long_term_goals"]


def test_brain_schema_and_defaults_consistent():
    from src.brain_schema import BRAIN_SCHEMA, DEFAULT_BRAIN
    for key in DEFAULT_BRAIN:
        assert key in BRAIN_SCHEMA, f"{key} in defaults but not schema"
    for key in BRAIN_SCHEMA:
        assert key in DEFAULT_BRAIN, f"{key} in schema but not defaults"


def test_creds_path_exists():
    from src.brain_schema import CREDS_PATH
    assert CREDS_PATH.endswith("firebase-credentials.json")
```

- [ ] **Step 3: Run new brain_schema tests**

```powershell
py -m pytest tests/test_brain_schema.py -v
```
Expected: 8 passed

- [ ] **Step 4: Update `src/memory_manager.py` to import from brain_schema**

Remove lines 14-61 (everything from `_CREDS_PATH` through `_validate_brain_consistency()` call) and replace with:

```python
from src.brain_schema import (
    BRAIN_SCHEMA as _BRAIN_SCHEMA,
    DEFAULT_BRAIN as _DEFAULT_BRAIN,
    apply_brain_update,
    CREDS_PATH as _CREDS_PATH,
)
```

Also remove `firebase_admin` import at lines 11-12 and replace with:

```python
from collections import deque
import firebase_admin
```

- [ ] **Step 5: Update `seed_brain.py` to import from brain_schema**

Replace lines 19-67 (everything from `_CREDS_PATH` through `_validate_brain_consistency()` call) and lines 68-172 (`_DEFAULT_BRAIN`) with:

```python
from src.brain_schema import (
    BRAIN_SCHEMA as _BRAIN_SCHEMA,
    DEFAULT_BRAIN as _DEFAULT_BRAIN,
    apply_brain_update,
    CREDS_PATH as _CREDS_PATH,
)
```

- [ ] **Step 6: Run full test suite to verify no regressions**

```powershell
py -m pytest tests/ -v
```
Expected: 309 passed, 1 skipped (brain_schema tests replace moved tests, same count)

- [ ] **Step 7: Commit**

```bash
git add src/brain_schema.py tests/test_brain_schema.py src/memory_manager.py seed_brain.py
git commit -m "refactor: extract shared brain schema to src/brain_schema.py"
```

---

### Task 2: Create `src/diary_store.py` — Local Diary I/O

**Files:**
- Create: `src/diary_store.py`
- Create: `tests/test_diary_store.py`

- [ ] **Step 1: Create `tests/test_diary_store.py`**

```python
from __future__ import annotations
import json
import pytest
from pathlib import Path


def test_write_and_read_roundtrip(tmp_path):
    from src.diary_store import DiaryStore
    path = str(tmp_path / "diary.json")
    store = DiaryStore(path)
    store.write(["a", "b", "c"], 3)
    result = store.read()
    assert result == {"entries": ["a", "b", "c"], "synced": 3}


def test_read_returns_none_on_missing_file(tmp_path):
    from src.diary_store import DiaryStore
    store = DiaryStore(str(tmp_path / "noexist.json"))
    assert store.read() is None


def test_write_is_atomic(tmp_path):
    from src.diary_store import DiaryStore
    path = str(tmp_path / "diary.json")
    tmp_path2 = str(tmp_path / "diary.json.tmp")
    store = DiaryStore(path)
    store.write(["x"], 1)
    assert not Path(tmp_path2).exists()


def test_write_caps_entries(tmp_path):
    from src.diary_store import DiaryStore
    path = str(tmp_path / "diary.json")
    store = DiaryStore(path, max_entries=3)
    store.write(["a", "b", "c", "d", "e"], 0)
    result = store.read()
    assert result["entries"] == ["c", "d", "e"]


def test_bak_file_created_on_write(tmp_path):
    from src.diary_store import DiaryStore
    path = str(tmp_path / "diary.json")
    # Write once to establish the file
    store = DiaryStore(path)
    store.write(["original"], 1)
    # Write again to trigger backup
    store.write(["updated"], 2)
    bak_path = str(tmp_path / "diary.json.bak")
    assert Path(bak_path).exists()
    bak_data = json.loads(Path(bak_path).read_text(encoding="utf-8"))
    assert bak_data["entries"] == ["original"]


def test_read_falls_back_to_bak(tmp_path):
    from src.diary_store import DiaryStore
    path = str(tmp_path / "diary.json")
    store = DiaryStore(path)
    store.write(["good data"], 1)
    # Corrupt the main file
    Path(path).write_text("not valid json", encoding="utf-8")
    store2 = DiaryStore(path)
    result = store2.read()
    assert result is not None
    assert result["entries"] == ["good data"]


def test_prune_removes_oldest(tmp_path):
    from src.diary_store import DiaryStore
    store = DiaryStore(str(tmp_path / "diary.json"), max_entries=5)
    pruned = store.prune(list(range(10)))
    assert pruned == [5, 6, 7, 8, 9]
```

- [ ] **Step 2: Run tests — expect all fail (module not created yet)**

```powershell
py -m pytest tests/test_diary_store.py -v
```
Expected: 7 failures with ImportError

- [ ] **Step 3: Create `src/diary_store.py`**

```python
# src/diary_store.py
"""Atomic local diary file I/O with backup and entry capping."""
from __future__ import annotations
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_DIARY_ENTRIES = 200


class DiaryStore:
    def __init__(self, path: str, max_entries: int = MAX_DIARY_ENTRIES) -> None:
        self._path = path
        self._max_entries = max_entries

    def read(self) -> dict | None:
        try:
            data = json.loads(Path(self._path).read_text(encoding="utf-8"))
            if isinstance(data, dict) and "entries" in data:
                return data
            return None
        except FileNotFoundError:
            return None
        except (json.JSONDecodeError, ValueError):
            logger.warning("DiaryStore: main file corrupt, trying .bak")
            return self._read_bak()

    def _read_bak(self) -> dict | None:
        bak_path = self._path + ".bak"
        try:
            data = json.loads(Path(bak_path).read_text(encoding="utf-8"))
            if isinstance(data, dict) and "entries" in data:
                return data
        except Exception:
            pass
        return None

    def write(self, entries: list[str], synced: int) -> None:
        capped = self.prune(entries)
        data = {"entries": capped, "synced": synced}
        self._write_atomic(data)

    def prune(self, entries: list[str]) -> list[str]:
        if len(entries) <= self._max_entries:
            return list(entries)
        return list(entries[-self._max_entries:])

    def _write_atomic(self, data: dict) -> None:
        tmp = self._path + ".tmp"
        try:
            bak_path = self._path + ".bak"
            if os.path.exists(self._path):
                try:
                    os.replace(self._path, bak_path)
                except OSError:
                    pass
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(tmp, self._path)
        except Exception as e:
            logger.warning("DiaryStore write failed for %s: %s", self._path, e)
```

- [ ] **Step 4: Run diary_store tests**

```powershell
py -m pytest tests/test_diary_store.py -v
```
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/diary_store.py tests/test_diary_store.py
git commit -m "feat: add DiaryStore with atomic writes, backup, and entry capping"
```

---

### Task 3: Add `.bak` Backup to `src/memory.py`

**Files:**
- Modify: `src/memory.py`
- Modify: `tests/test_memory.py`

- [ ] **Step 1: Add backup tests to `tests/test_memory.py`**

Append to end of file:

```python
def test_bak_file_created_on_save(tmp_path):
    from src.memory import Memory
    path = str(tmp_path / "mem.json")
    mem = Memory(path=path)
    mem.remember("key1", "val1")
    mem.save()
    # Now make a second save to trigger backup of first
    mem.remember("key2", "val2")
    mem.save()
    bak_path = path + ".bak"
    assert Path(bak_path).exists()


def test_load_falls_back_to_bak_when_main_corrupt(tmp_path):
    from src.memory import Memory
    path = str(tmp_path / "mem.json")
    # Write a valid file first
    mem = Memory(path=path)
    mem.remember("rescue", "me")
    mem.save()
    # Corrupt main file
    Path(path).write_text("garbage", encoding="utf-8")
    # New instance should load from .bak
    mem2 = Memory(path=path)
    assert mem2.recall("rescue") == "me"
```

Add the import at top if not present:
```python
from pathlib import Path
```

- [ ] **Step 2: Run the new tests — expect FAIL**

```powershell
py -m pytest tests/test_memory.py::test_bak_file_created_on_save tests/test_memory.py::test_load_falls_back_to_bak_when_main_corrupt -v
```
Expected: 2 FAILED

- [ ] **Step 3: Update `src/memory.py` `_save()` and `_load()` methods**

In `_save()` (line 73), change to:

```python
    def _save(self) -> None:
        tmp = self._path + ".tmp"
        try:
            bak_path = self._path + ".bak"
            if os.path.exists(self._path):
                try:
                    os.replace(self._path, bak_path)
                except OSError:
                    pass
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"facts": self._facts}, f)
            os.replace(tmp, self._path)
        except Exception as e:
            logger.warning("Memory save failed for %s: %s", self._path, e)
```

In `_load()` (line 82), change to:

```python
    def _load(self) -> None:
        try:
            data = json.loads(Path(self._path).read_text(encoding="utf-8"))
            self._facts = data.get("facts", {})
        except Exception:
            logger.warning("Memory load failed for %s: %s — trying .bak", self._path, self._path)
            try:
                bak_path = self._path + ".bak"
                data = json.loads(Path(bak_path).read_text(encoding="utf-8"))
                self._facts = data.get("facts", {})
                logger.info("Memory loaded from backup (%d facts)", len(self._facts))
            except Exception as e2:
                logger.warning("Memory backup load also failed for %s: %s", self._path, e2)
                self._facts = {}
```

- [ ] **Step 4: Run memory tests**

```powershell
py -m pytest tests/test_memory.py -v
```
Expected: 18 passed (16 existing + 2 new)

- [ ] **Step 5: Commit**

```bash
git add src/memory.py tests/test_memory.py
git commit -m "feat: add .bak backup fallback to Memory"
```

---

### Task 4: Add `.bak` Backup to `src/history.py`

**Files:**
- Modify: `src/history.py`
- Modify: `tests/test_history.py`

- [ ] **Step 1: Add backup tests to `tests/test_history.py`**

Append:

```python
def test_bak_file_created_on_save(tmp_path):
    from src.history import History
    path = str(tmp_path / "hist.json")
    h = History(path=path)
    h.add_entry("u1", "r1", "idle")
    h.save()
    h.add_entry("u2", "r2", "shake")
    h.save()
    bak_path = path + ".bak"
    assert Path(bak_path).exists()


def test_load_falls_back_to_bak_when_main_corrupt(tmp_path):
    from src.history import History
    path = str(tmp_path / "hist.json")
    h = History(path=path)
    h.add_entry("rescue", "this", "idle")
    h.save()
    Path(path).write_text("garbage", encoding="utf-8")
    h2 = History(path=path)
    entries = h2.get_all()
    assert len(entries) == 1
    assert entries[0]["user_input"] == "rescue"
```

Add `from pathlib import Path` at top of test file.

- [ ] **Step 2: Run — expect 2 FAIL**

```powershell
py -m pytest tests/test_history.py::test_bak_file_created_on_save tests/test_history.py::test_load_falls_back_to_bak_when_main_corrupt -v
```

- [ ] **Step 3: Update `src/history.py` `_save()` and `_load()`**

Same pattern as memory.py:

```python
    def _save(self) -> None:
        tmp = self._path + ".tmp"
        try:
            bak_path = self._path + ".bak"
            if os.path.exists(self._path):
                try:
                    os.replace(self._path, bak_path)
                except OSError:
                    pass
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"entries": self._entries, "count": len(self._entries)}, f)
            os.replace(tmp, self._path)
        except Exception as e:
            logger.warning("History save failed for %s: %s", self._path, e)

    def _load(self) -> None:
        try:
            data = json.loads(Path(self._path).read_text(encoding="utf-8"))
            self._entries = data.get("entries", [])
        except Exception:
            logger.warning("History load failed for %s: %s — trying .bak", self._path, self._path)
            try:
                bak_path = self._path + ".bak"
                data = json.loads(Path(bak_path).read_text(encoding="utf-8"))
                self._entries = data.get("entries", [])
                logger.info("History loaded from backup (%d entries)", len(self._entries))
            except Exception as e2:
                logger.warning("History backup load also failed for %s: %s", self._path, e2)
                self._entries = []
```

- [ ] **Step 4: Run history tests**

```powershell
py -m pytest tests/test_history.py -v
```
Expected: 18 passed (16 existing + 2 new)

- [ ] **Step 5: Commit**

```bash
git add src/history.py tests/test_history.py
git commit -m "feat: add .bak backup fallback to History"
```

---

### Task 5: Atomic Write in `src/persistence.py`

**Files:**
- Modify: `src/persistence.py`
- Modify: `tests/test_persistence.py`

- [ ] **Step 1: Add atomic write test to `tests/test_persistence.py`**

```python
def test_save_state_is_atomic():
    import os
    from pathlib import Path
    from src.persistence import save_state, _DEFAULT_PATH
    path = _DEFAULT_PATH
    tmp_path = path + ".tmp"
    # Ensure clean state
    for p in [path, tmp_path]:
        if os.path.exists(p):
            os.unlink(p)
    try:
        save_state({"mood": 5, "interactions": 10, "runtime_seconds": 60,
                     "skill_greeted": True, "first_run_done": True})
        assert not os.path.exists(tmp_path)
        assert os.path.exists(path)
    finally:
        for p in [path, tmp_path]:
            if os.path.exists(p):
                os.unlink(p)
```

- [ ] **Step 2: Run — expect FAIL**

```powershell
py -m pytest tests/test_persistence.py::test_save_state_is_atomic -v
```

- [ ] **Step 3: Update `src/persistence.py` `save_state()`**

```python
def save_state(state: dict, path: str = _DEFAULT_PATH) -> None:
    try:
        tmp = path + ".tmp"
        if os.path.exists(path):
            try:
                os.replace(path, path + ".bak")
            except OSError:
                pass
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, path)
    except Exception as e:
        logger.warning("Failed to save state to %s: %s", path, e)
```

- [ ] **Step 4: Run persistence tests**

```powershell
py -m pytest tests/test_persistence.py -v
```
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/persistence.py tests/test_persistence.py
git commit -m "fix: atomic write for persistence save_state"
```

---

### Task 6: Atomic Write + TTL in `src/response_manager.py`

**Files:**
- Modify: `src/response_manager.py`
- Modify: `tests/test_response_manager.py`

- [ ] **Step 1: Add atomic + TTL tests to `tests/test_response_manager.py`**

```python
def test_save_is_atomic(tmp_path):
    from pathlib import Path
    from unittest.mock import MagicMock
    from src.response_manager import AutonomousResponseManager
    cache_path = str(tmp_path / "cache.json")
    wc = MagicMock()
    arm = AutonomousResponseManager(cache_path, wc)
    arm._save()
    assert not Path(cache_path + ".tmp").exists()
    assert Path(cache_path).exists()


def test_items_persist_and_restore(tmp_path):
    from unittest.mock import MagicMock
    from src.response_manager import AutonomousResponseManager
    cache_path = str(tmp_path / "cache.json")
    wc = MagicMock()
    arm1 = AutonomousResponseManager(cache_path, wc)
    arm1.add_items("jokes_blackmail", [
        {"dialogue": "test joke", "action": "idle", "priority": 5}
    ])
    arm1.stop()
    arm2 = AutonomousResponseManager(cache_path, wc)
    assert arm2.remaining("jokes_blackmail") == 1
    items = arm2.draw("jokes_blackmail", 1)
    assert items[0]["dialogue"] == "test joke"


def test_load_drops_old_items(tmp_path):
    import json
    from unittest.mock import MagicMock
    from src.response_manager import AutonomousResponseManager
    cache_path = str(tmp_path / "cache.json")
    old_data = {
        "version": 2,
        "pools": {
            "jokes_blackmail": {
                "items": [
                    {"dialogue": "old", "action": "idle", "priority": 3,
                     "pool_type": "jokes_blackmail", "last_used": "2020-01-01T00:00:00"},
                    {"dialogue": "recent", "action": "shake", "priority": 5,
                     "pool_type": "jokes_blackmail", "last_used": "2099-12-31T00:00:00"},
                ]
            },
            "system": {"items": []}
        }
    }
    Path(cache_path).write_text(json.dumps(old_data), encoding="utf-8")
    wc = MagicMock()
    arm = AutonomousResponseManager(cache_path, wc)
    # Old item should be dropped, recent item kept
    remaining = arm.remaining("jokes_blackmail")
    assert remaining <= 1
```

Add `from pathlib import Path` at top of test file.

- [ ] **Step 2: Run new tests — expect FAIL for atomic+TTL**

```powershell
py -m pytest tests/test_response_manager.py::test_save_is_atomic tests/test_response_manager.py::test_items_persist_and_restore tests/test_response_manager.py::test_load_drops_old_items -v
```

- [ ] **Step 3: Update `src/response_manager.py` `_save()` and `_load()`**

`_save()` — use atomic write:

```python
    def _save(self):
        try:
            from datetime import datetime
            data = {
                "version": 2,
                "pools": {
                    pool_type: {
                        "items": pool.save_items(),
                        "last_refill": datetime.now().isoformat(),
                    }
                    for pool_type, pool in self._pools.items()
                }
            }
            tmp = self._cache_path + ".tmp"
            if os.path.exists(self._cache_path):
                try:
                    os.replace(self._cache_path, self._cache_path + ".bak")
                except OSError:
                    pass
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, self._cache_path)
        except Exception as e:
            logger.warning("Failed to save response cache: %s", e)
```

Add `import os` to the imports at top.

`_load()` — add TTL check (items older than 7 days are dropped):

```python
    def _load(self):
        try:
            from datetime import datetime, timedelta
            data = json.loads(Path(self._cache_path).read_text(encoding="utf-8"))
            cutoff = datetime.now() - timedelta(days=7)
            pools_data = data.get("pools", {})
            for pool_type, pool in self._pools.items():
                pool_data = pools_data.get(pool_type, {})
                items = pool_data.get("items", [])
                # Drop items older than 7 days
                filtered = []
                for item in items:
                    last_used_str = item.get("last_used")
                    if last_used_str:
                        try:
                            last_used = datetime.fromisoformat(last_used_str)
                            if last_used < cutoff:
                                continue
                        except (ValueError, TypeError):
                            pass
                    filtered.append(item)
                pool.load_items(filtered)
            logger.info("Loaded response cache: jokes=%d, system=%d",
                        self.remaining("jokes_blackmail"), self.remaining("system"))
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
            logger.warning("Failed to load response cache: %s", e)
```

Update the `add_items` method in `ResponsePool` to tag items with last_used=None (set on draw):

In `ResponsePool.draw()`, after selecting items, add a line tagging them:

```python
        # In draw(), after selecting items:
        for item in selected:
            item["last_used"] = datetime.now().isoformat()
```

Add `from datetime import datetime` to the imports of `response_manager.py`.

- [ ] **Step 4: Run response_manager tests**

```powershell
py -m pytest tests/test_response_manager.py -v
```
Expected: 16 passed (13 existing + 3 new)

- [ ] **Step 5: Commit**

```bash
git add src/response_manager.py tests/test_response_manager.py
git commit -m "fix: atomic write and 7-day TTL cleanup for response cache"
```

---

### Task 7: Refactor `src/memory_manager.py` — Retry Queue + Remove Diary Ops

**Files:**
- Modify: `src/memory_manager.py`
- Modify: `tests/test_memory_manager.py`

- [ ] **Step 1: Update `src/memory_manager.py`**

**Remove:** `read_local_diary()` and `write_local_diary()` methods (lines 322-336).

**Add retry queue and `retry_pending_writes()`:**

```python
    def __init__(self, creds_path: str | None = None) -> None:
        path = creds_path or _CREDS_PATH
        self.db = None
        self._pending_writes: deque = deque()
        try:
            cred = credentials.Certificate(path)
            try:
                firebase_admin.get_app()
            except ValueError:
                firebase_admin.initialize_app(cred)
            self.db = firestore.client()
        except FileNotFoundError:
            logger.warning("[MemoryManager] firebase-credentials.json not found — running without cloud memory")
        except Exception as e:
            logger.warning(f"[MemoryManager] Firebase init failed: {e} — running without cloud memory")

    def retry_pending_writes(self) -> int:
        """Flush queued failed writes. Returns count of successful retries."""
        if self.db is None or not self._pending_writes:
            return 0
        succeeded = 0
        while self._pending_writes:
            kind, data = self._pending_writes[0]
            try:
                if kind == "diary":
                    self.db.collection("daemon_diary").add(data)
                elif kind == "brain":
                    self.db.collection("daemon_data").document("core_brain").set(data, merge=True)
                self._pending_writes.popleft()
                succeeded += 1
            except Exception as e:
                logger.warning("[MemoryManager] retry failed for %s: %s", kind, e)
                break
        if succeeded:
            logger.info("[MemoryManager] retried %d pending writes", succeeded)
        return succeeded
```

**Update `add_diary_entry()` to queue on failure:**

```python
    def add_diary_entry(self, text: str) -> None:
        if self.db is None:
            return
        data = {"text": text, "timestamp": firestore.SERVER_TIMESTAMP}
        try:
            _ref, result = self.db.collection("daemon_diary").add(data)
            logger.info(f"[MemoryManager] diary entry written (id={result.id})")
        except Exception as e:
            logger.warning(f"[MemoryManager] add_diary_entry failed: {e} — queued for retry")
            self._pending_writes.append(("diary", data))
```

**Update `update_brain()` to queue on failure:**

```python
    def update_brain(self, new_data: dict) -> None:
        if self.db is None:
            return
        try:
            self.db.collection("daemon_data").document("core_brain").set(new_data, merge=True)
            logger.info(f"[MemoryManager] core_brain updated ({len(new_data)} fields merged)")
        except Exception as e:
            logger.warning(f"[MemoryManager] update_brain failed: {e} — queued for retry")
            self._pending_writes.append(("brain", new_data))
```

**Update `fetch_all_diary_entries()` to accept limit parameter:**

```python
    def fetch_all_diary_entries(self, limit: int = 200) -> list[str]:
        """Read ALL diary entries from Firebase (one-time startup sync)."""
        logger.debug("MemoryManager.fetch_all_diary_entries called")
        if self.db is None:
            logger.debug("  db is None, returning empty")
            return []
        try:
            docs = (
                self.db.collection("daemon_diary")
                .order_by("timestamp", direction=firestore.Query.ASCENDING)
                .limit(limit)
                .stream()
            )
            entries = []
            for doc in docs:
                try:
                    text = doc.to_dict().get("text", "")
                    if text:
                        entries.append(text)
                except Exception:
                    continue
            logger.debug(f"  fetched {len(entries)} diary entries from Firebase")
            logger.info(f"[MemoryManager] fetched {len(entries)} diary entries from Firebase")
            return entries
        except Exception as e:
            logger.debug(f"  fetch_all_diary_entries failed: {e}")
            logger.warning(f"[MemoryManager] fetch_all_diary_entries failed: {e}")
            return []
```

**Update `push_pending_diaries()` to accept DiaryStore:**

```python
    def push_pending_diaries(self, diary_store, entries: list[str], synced: int) -> int:
        """Push unsynced diary entries to Firebase, return new synced count."""
        if self.db is None:
            return synced
        pending = entries[synced:]
        if not pending:
            return synced
        for text in pending:
            self.add_diary_entry(text)
        new_synced = len(entries)
        diary_store.write(entries, new_synced)
        logger.info(f"[MemoryManager] pushed {len(pending)} pending diary entries to Firebase")
        return new_synced
```

- [ ] **Step 2: Add retry queue tests to `tests/test_memory_manager.py`**

```python
def test_add_diary_entry_queues_on_failure(mgr_db, mock_db):
    """Failed Firebase write is queued for retry."""
    mock_db.collection.return_value.add.side_effect = Exception("network down")
    mgr_db.add_diary_entry("test entry")
    assert len(mgr_db._pending_writes) == 1
    assert mgr_db._pending_writes[0][0] == "diary"


def test_retry_pending_writes_succeeds(mgr_db, mock_db):
    """retry_pending_writes flushes queued writes."""
    mgr_db._pending_writes.append(("diary", {"text": "retry me", "timestamp": None}))
    result = mgr_db.retry_pending_writes()
    assert result == 1
    assert len(mgr_db._pending_writes) == 0


def test_retry_pending_writes_no_op_when_db_none(mgr_no_db):
    """retry_pending_writes returns 0 when db is None."""
    mgr_no_db._pending_writes.append(("diary", {}))
    assert mgr_no_db.retry_pending_writes() == 0


def test_fetch_all_diary_respects_limit(mgr_db, mock_db):
    """fetch_all_diary_entries passes limit to Firebase query."""
    from firebase_admin import firestore
    mgr_db.fetch_all_diary_entries(limit=50)
    mock_db.collection.return_value.order_by.return_value.limit.assert_called_with(50)
```

- [ ] **Step 3: Run memory_manager tests**

```powershell
py -m pytest tests/test_memory_manager.py -v
```
Expected: All pass (some old tests may need updating due to method signature changes)

- [ ] **Step 4: Commit**

```bash
git add src/memory_manager.py tests/test_memory_manager.py
git commit -m "feat: add retry queue for failed Firebase writes, limit diary fetch"
```

---

### Task 8: Update `src/write_coalescer.py` — Brain Flag + DiaryStore

**Files:**
- Modify: `src/write_coalescer.py`
- Modify: `tests/test_write_coalescer.py`

- [ ] **Step 1: Update `src/write_coalescer.py`**

Add `brain` to dirty flags and update diary flush path. Replace the class definition:

```python
class WriteCoalescer:
    def __init__(
        self,
        memory: "Memory",
        history: "History",
        memory_manager: "MemoryManager",
        diary_store: "DiaryStore | None" = None,
        diary_entries_ref: list | None = None,
        flush_sec: float = 8.0,
    ) -> None:
        self._memory = memory
        self._history = history
        self._memory_manager = memory_manager
        self._diary_store = diary_store
        self._diary_entries_ref = diary_entries_ref or []
        self._flush_sec = flush_sec
        self._timer: QTimer | None = None
        self._dirty: dict[str, bool] = {
            "memory": False,
            "history": False,
            "diary": False,
            "response_cache": False,
            "brain": False,
        }

    # mark_dirty remains the same

    def flush(self) -> None:
        for kind in ("memory", "history", "diary", "response_cache", "brain"):
            if not self._dirty.get(kind):
                continue
            try:
                if kind == "memory":
                    self._memory.save()
                elif kind == "history":
                    self._history.save()
                elif kind == "diary":
                    self._flush_diary()
                elif kind == "response_cache":
                    pass
                elif kind == "brain":
                    self._memory_manager.retry_pending_writes()
            except Exception as e:
                logging.warning(f"[WriteCoalescer] {kind} flush failed: {e}")
                continue
            self._dirty[kind] = False

    def _flush_diary(self) -> None:
        if self._diary_store is None:
            return
        existing = self._diary_store.read()
        synced = existing.get("synced", 0) if existing else 0
        self._diary_store.write(self._diary_entries_ref, synced)

    # start() and stop() unchanged
```

Also update `TYPE_CHECKING` import block:

```python
if TYPE_CHECKING:
    from src.memory import Memory
    from src.history import History
    from src.memory_manager import MemoryManager
    from src.diary_store import DiaryStore
```

- [ ] **Step 2: Update tests in `tests/test_write_coalescer.py`**

Update constructor calls to remove `diary_path` and add `diary_store`:

In each test that creates a WriteCoalescer, change from:
```python
wc = WriteCoalescer(memory=..., history=..., memory_manager=...,
                    diary_entries_ref=..., diary_path=...)
```
to:
```python
wc = WriteCoalescer(memory=..., history=..., memory_manager=...,
                    diary_store=..., diary_entries_ref=...)
```

Add test for brain flag:

```python
def test_flush_retries_pending_writes_on_brain_flag():
    from unittest.mock import MagicMock
    wc = WriteCoalescer(
        memory=MagicMock(), history=MagicMock(),
        memory_manager=MagicMock(),
    )
    wc.mark_dirty("brain")
    wc.flush()
    wc._memory_manager.retry_pending_writes.assert_called_once()
    assert wc._dirty["brain"] is False
```

- [ ] **Step 3: Run write_coalescer tests**

```powershell
py -m pytest tests/test_write_coalescer.py -v
```
Expected: 11 passed

- [ ] **Step 4: Commit**

```bash
git add src/write_coalescer.py tests/test_write_coalescer.py
git commit -m "feat: add brain flag for Firebase retry, diary_store integration"
```

---

### Task 9: Update `seed_brain.py` — Import from brain_schema

Already done in Task 1 Step 5. Verify it still works.

- [ ] **Step 1: Verify seed_brain.py imports work**

```powershell
py -c "from src.brain_schema import BRAIN_SCHEMA, DEFAULT_BRAIN, apply_brain_update, CREDS_PATH; print('OK')"
```

- [ ] **Step 2: Commit if not already covered**

```bash
git add seed_brain.py
git commit -m "refactor: seed_brain imports shared schema from brain_schema.py"
```

---

### Task 10: Rewrite `src/opencode_worker.py` — noReply Injection + Consolidated Signals

**Files:**
- Modify: `src/opencode_worker.py`
- Modify: `tests/test_opencode_worker.py`

This is the largest single change. The worker gains `inject_context()` (noReply:true), `send_trigger()` (noReply:false), and consolidated `trigger_ready` signal.

- [ ] **Step 1: Write new signal consolidation test in `tests/test_opencode_worker.py`**

```python
def test_trigger_ready_signal_exists():
    from src.opencode_worker import OpencodeWorker
    assert hasattr(OpencodeWorker, "trigger_ready")


def test_context_injected_signal_exists():
    from src.opencode_worker import OpencodeWorker
    assert hasattr(OpencodeWorker, "context_injected")


def test_injection_failed_signal_exists():
    from src.opencode_worker import OpencodeWorker
    assert hasattr(OpencodeWorker, "injection_failed")


def test_inject_context_sends_no_reply_true(monkeypatch):
    from unittest.mock import MagicMock, patch
    from src.opencode_worker import OpencodeWorker

    mock_post = MagicMock()
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"id": "sess-1"}

    emitted = []
    worker = OpencodeWorker(
        user_input="", is_autonomous=True, session_id="sess-1"
    )
    worker.context_injected.connect(lambda: emitted.append("injected"))

    with patch("src.opencode_worker.requests.post", mock_post):
        worker.inject_context("test injection payload")
        worker.wait(1000)

    call_args = mock_post.call_args
    payload = call_args[1]["json"]
    assert payload.get("noReply") is True
    assert emitted == ["injected"]


def test_send_trigger_emits_trigger_ready(monkeypatch):
    import json
    from unittest.mock import MagicMock, patch
    from src.opencode_worker import OpencodeWorker

    response_text = '[{"dialogue":"hello","action":"idle","target_x":null,"priority":3}]'
    mock_post = MagicMock()
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "parts": [{"type": "text", "text": response_text}]
    }

    emitted = []
    worker = OpencodeWorker(
        user_input="", is_autonomous=True,
    )
    worker.trigger_ready.connect(lambda items: emitted.extend(items))

    with patch("src.opencode_worker.requests.post", mock_post):
        worker.send_trigger("trigger prompt")
        worker.wait(1000)

    assert len(emitted) > 0


def test_old_signals_removed():
    from src.opencode_worker import OpencodeWorker
    for name in ["structured_ready", "structured_batch_ready",
                  "structured_multiplexed", "result_ready"]:
        assert not hasattr(OpencodeWorker, name), f"{name} should not exist"
```

- [ ] **Step 2: Run new tests — expect FAIL**

```powershell
py -m pytest tests/test_opencode_worker.py::test_trigger_ready_signal_exists tests/test_opencode_worker.py::test_context_injected_signal_exists tests/test_opencode_worker.py::test_injection_failed_signal_exists tests/test_opencode_worker.py::test_inject_context_sends_no_reply_true tests/test_opencode_worker.py::test_send_trigger_emits_trigger_ready tests/test_opencode_worker.py::test_old_signals_removed -v
```

- [ ] **Step 3: Rewrite `src/opencode_worker.py`**

Replace the entire file. Key changes:
- Remove old signals (`structured_ready`, `structured_batch_ready`, `structured_multiplexed`, `result_ready`)
- Add new signals (`trigger_ready(list)`, `context_injected`, `injection_failed(str)`)
- Keep `session_created`, `error_occurred`, `path_used`, `brain_update_ready`, `pool_items_ready`
- Add `inject_context(prompt)` method
- Add `send_trigger(prompt)` method
- Rename `run()` → keep but call `send_trigger()` internally
- Keep `_run_cli()` and `_build_prompt()` as dead code (not called by PetWindow)
- Keep `_run_api()` modified to support noReply parameter
- Keep `_process_output`, `_parse_json_response`, `_parse_json_batch`
- Keep `_SKILL_CONTENT`, `FORMAT_INSTRUCTIONS`

```python
# src/opencode_worker.py
from __future__ import annotations
import json
import logging
import os
import re
import subprocess
import tempfile
import requests
from PyQt6.QtCore import QThread, pyqtSignal
from pathlib import Path
from src.constants import (
    OPENCODE_TIMEOUT_SECONDS,
    OPENCODE_SCRIPT_PATH,
    OPENCODE_SERVER_URL,
    OPENCODE_API_MODEL_PROVIDER,
    OPENCODE_API_MODEL_ID,
    OPENCODE_API_TIMEOUT_SEC,
)


logger = logging.getLogger(__name__)


# Cached once at import time to avoid re-reading the skill file on every prompt build.
try:
    _SKILL_CONTENT = (Path(__file__).parent.parent / "assets" / "daemon-skill.md").read_text(encoding="utf-8")
except Exception:
    _SKILL_CONTENT = ""


def _process_output(text: str) -> str:
    stripped = re.sub(r'[*#`~_]', '', text.strip())
    if len(stripped) > 280:
        return stripped[:280] + "... (see terminal for full output)"
    return stripped


def _parse_json_response(text: str) -> dict | None:
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end > start:
        try:
            data = json.loads(text[start:end + 1])
            if isinstance(data, dict) and "dialogue" in data:
                return data
        except (json.JSONDecodeError, ValueError):
            pass
    dialogue_m = re.search(r'"?(dialogue|text)"?\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    if not dialogue_m:
        dialogue_m = re.search(r'"?(dialogue|text)"?\s*:\s*([^{}]+?)(?=\s*,\s*\w+\s*:|\s*\})', text, re.DOTALL)
    if not dialogue_m:
        return None
    action_m = re.search(r'"?(action|verb)"?\s*:\s*"?([A-Za-z_]+)"?', text)
    target_m = re.search(r'"?(target(?:_x)?)"?\s*:\s*(-?\d+)', text)
    return {
        "dialogue": dialogue_m.group(2).strip(),
        "action": action_m.group(2) if action_m else "idle",
        "target_x": int(target_m.group(2)) if target_m else 0,
    }


def _parse_json_batch(text: str) -> list[dict]:
    arr_start = text.find('[')
    arr_end = text.rfind(']')
    if arr_start != -1 and arr_end > arr_start:
        try:
            data = json.loads(text[arr_start:arr_end + 1])
            if isinstance(data, list) and all(
                isinstance(item, dict) and ("dialogue" in item or "text" in item) for item in data
            ):
                return data
        except (json.JSONDecodeError, ValueError):
            pass
        inner = text[arr_start + 1:arr_end]
        results = []
        depth = 0
        start = -1
        for i, ch in enumerate(inner):
            if ch == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and start != -1:
                    obj_text = inner[start:i + 1]
                    parsed = _parse_json_response(obj_text)
                    if parsed and (parsed.get("dialogue") or parsed.get("text")):
                        results.append(parsed)
                    start = -1
        if results:
            return results
    single = _parse_json_response(text)
    return [single] if single else []


FORMAT_INSTRUCTIONS = """Respond ONLY with valid JSON. No markdown, no preamble, no text outside the JSON.

Single-query format (user responding):
{"thought":"...","dialogue":"...","action":"<action>","target_x":<int or null>,"priority":<1-5>}

Autonomous batch format -- return array with priority on each item:
[{"dialogue":"...","action":"<action>","target_x":<int or null>,"priority":<1-5>}, ...]

Rules:
- dialogue: <=20 words
- action: one of idle/wander/celebrate/devastated/hyper/shake/bounce/spin/look_away
- target_x: integer (for wander) or null (for other actions)
- priority: integer 1-5 -- higher = more likely to be shown. Priority decays over time.
- Keys and strings use double quotes. No trailing commas."""


def _build_prompt(
    user_input: str,
    context_hint: str = "",
    apm: int = 0,
    is_autonomous: bool = False,
    memory_context: str = "",
    history_context: str = "",
    idle_seconds: float = 0.0,
    last_action: str = "idle",
    typing_content: str = "",
) -> str:
    """Legacy full-prompt builder. Preserved for CLI fallback, not called by PetWindow."""
    from datetime import datetime
    hour = datetime.now().hour
    if hour < 12:
        time_of_day = "morning"
    elif hour < 17:
        time_of_day = "afternoon"
    elif hour < 21:
        time_of_day = "evening"
    else:
        time_of_day = "night"

    mode_instruction = (
        "You are thinking out loud to yourself (not responding to the user). "
        "The user cannot hear you -- this is your internal monologue."
        if is_autonomous
        else "You are responding directly to the user's message."
    )
    context_lines = [
        f"Active Window: {context_hint or 'Desktop'}",
        f"Current APM: {apm}",
        f"Time of Day: {datetime.now().strftime('%H:%M')} ({time_of_day})",
        f"User Idle Seconds: {int(idle_seconds)}",
        f"Last Daemon Action: {last_action}",
    ]
    if is_autonomous:
        context_lines.append("Request Type: autonomous (return JSON array of exactly 6 dialogs)")
        context_lines.append("User Input: (none -- this is Daemon's internal monologue)")
    else:
        context_lines.append("Request Type: user-query (return single JSON object)")
        context_lines.append(f"User Input: {user_input}")
    if typing_content:
        context_lines.append("")
        context_lines.append(typing_content)
    context_block = "\n".join(context_lines)
    extras = []
    if memory_context:
        extras.append(memory_context)
    if history_context:
        extras.append(history_context)
    extra_block = ("\n\n" + "\n\n".join(extras)) if extras else ""
    full_dynamic = f"{FORMAT_INSTRUCTIONS}\n\n{mode_instruction}\n\nCURRENT CONTEXT:\n{context_block}{extra_block}"
    if _SKILL_CONTENT:
        return f"{_SKILL_CONTENT}\n\n{full_dynamic}"
    return full_dynamic


VALID_ACTIONS = {
    "idle", "wander", "celebrate", "devastated",
    "hyper", "shake", "bounce", "spin", "look_away",
}


def _normalize_parsed(items: list[dict]) -> list[dict]:
    """Normalize parsed items: strip markdown from dialogue, validate action."""
    normalized = []
    for item in items:
        raw_dialogue = item.get("dialogue") or item.get("text") or ""
        dialogue = re.sub(r'[*#`~_]', '', raw_dialogue).strip()
        action = str(item.get("action") or item.get("verb") or "idle").lower().strip()
        if action not in VALID_ACTIONS:
            action = "idle"
        try:
            target_x = int(item.get("target_x") or 0)
        except (ValueError, TypeError):
            target_x = 0
        priority = int(item.get("priority", 3))
        normalized.append({
            "dialogue": dialogue,
            "action": action,
            "target_x": target_x,
            "priority": priority,
        })
    return normalized


class OpencodeWorker(QThread):
    trigger_ready = pyqtSignal(list)          # list[dict] -- consolidated response signal
    error_occurred = pyqtSignal(str)
    session_created = pyqtSignal(str)         # session id
    context_injected = pyqtSignal()           # emitted after successful inject_context()
    injection_failed = pyqtSignal(str)        # emitted on inject_context() failure
    path_used = pyqtSignal(str)               # "api"
    brain_update_ready = pyqtSignal(dict)
    pool_items_ready = pyqtSignal(dict)       # {"jokes_blackmail": [...], "system": [...]}

    def __init__(self, user_input: str = "", context_hint: str = "", apm: int = 0,
                 is_autonomous: bool = False, parent=None,
                 session_id: str | None = None,
                 prompt: str | None = None,
                 typing_content: str = "") -> None:
        super().__init__(parent)
        self._user_input = user_input
        self._context_hint = context_hint
        self._apm = apm
        self._is_autonomous = is_autonomous
        self._session_id = session_id
        self._prebuilt_prompt = prompt
        self._typing_content = typing_content
        self._injection_in_flight = False

    def _post_message(self, payload: dict) -> str | None:
        """POST to /session/{id}/message. Returns raw text or None."""
        session_id = self._session_id
        try:
            if not session_id:
                logger.info("API: creating session at %s/session", OPENCODE_SERVER_URL)
                r = requests.post(
                    f"{OPENCODE_SERVER_URL}/session",
                    json={"title": "Daemon Pet"},
                    timeout=OPENCODE_API_TIMEOUT_SEC,
                )
                if r.status_code >= 400:
                    logger.warning("API session create failed: %s %s", r.status_code, r.text[:200])
                    return None
                session_id = r.json().get("id")
                if not session_id:
                    logger.warning("API session create returned no id: %s", r.text[:200])
                    return None
                self._session_id = session_id
                self.session_created.emit(session_id)
                logger.info("API: created session %s", session_id)

            r = requests.post(
                f"{OPENCODE_SERVER_URL}/session/{session_id}/message",
                json=payload,
                timeout=OPENCODE_API_TIMEOUT_SEC,
            )
            if r.status_code >= 400:
                logger.warning("API message failed: %s %s", r.status_code, r.text[:200])
                return None

            data = r.json()
            parts = data.get("parts") or []
            text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
            if not text:
                logger.warning("API response had no text parts: %s", str(data)[:200])
                return None
            logger.info("API: received %s chars", len(text))
            return text
        except requests.exceptions.ConnectionError as e:
            logger.warning("API connection error: %s", e)
            return None
        except requests.exceptions.Timeout as e:
            logger.warning("API timeout: %s", e)
            return None
        except requests.exceptions.RequestException as e:
            logger.warning("API request error: %s", e)
            return None
        except (ValueError, KeyError) as e:
            logger.warning("API response parse error: %s", e)
            return None

    def inject_context(self, prompt: str) -> None:
        """Inject context silently via noReply:true. Emits context_injected or injection_failed."""
        self._injection_in_flight = True
        payload = {
            "noReply": True,
            "parts": [{"type": "text", "text": prompt}],
        }
        logger.info("API: injecting context (%d chars, noReply=true)", len(prompt))
        try:
            # Session creation happens inside _post_message if needed
            raw = self._post_message(payload)
            if raw is not None:
                # noReply responses may be empty or contain an ack
                logger.info("API: context injected successfully")
                self.context_injected.emit()
            else:
                logger.warning("API: context injection failed")
                self.injection_failed.emit("Context injection returned no response")
        finally:
            self._injection_in_flight = False

    def send_trigger(self, prompt: str) -> None:
        """Send a trigger prompt (noReply:false). Emits trigger_ready with parsed response."""
        payload = {
            "model": {
                "providerID": OPENCODE_API_MODEL_PROVIDER,
                "modelID": OPENCODE_API_MODEL_ID,
            },
            "parts": [{"type": "text", "text": prompt}],
        }
        logger.info("API: sending trigger (%d chars)", len(prompt))
        raw_output = self._post_message(payload)
        if raw_output is not None:
            self.path_used.emit("api")
            self._process_raw_output(raw_output)
        else:
            logger.warning("API trigger failed, no raw output")

    def _process_raw_output(self, raw_output: str) -> None:
        """Parse raw output and emit trigger_ready with normalized items."""
        parsed_items = _parse_json_batch(raw_output)
        if parsed_items:
            normalized = _normalize_parsed(parsed_items)
            brain_updates = []
            for item in parsed_items:
                brain_update = item.pop("brain_update", None)
                if brain_update is not None and isinstance(brain_update, dict):
                    brain_updates.append(brain_update)
            for bu in brain_updates:
                self.brain_update_ready.emit(bu)
            logger.info("Emitting trigger_ready: %d items", len(normalized))
            self.trigger_ready.emit(normalized)

            # Pool items for user queries
            if not self._is_autonomous and parsed_items:
                item = parsed_items[0]
                if "jokes_blackmail_items" in item or "system_items" in item:
                    pool = {
                        "jokes_blackmail": item.get("jokes_blackmail_items", []),
                        "system": item.get("system_items", []),
                    }
                    self.pool_items_ready.emit(pool)
        else:
            processed = _process_output(raw_output)
            logger.info("Emitting error (fallback plain text): '%s'", processed)
            self.error_occurred.emit(processed)

    def run(self) -> None:
        """Backward-compat: delegates to send_trigger if prebuilt prompt is set."""
        if self._prebuilt_prompt is not None:
            self.send_trigger(self._prebuilt_prompt)
        else:
            prompt = _build_prompt(
                self._user_input, self._context_hint, self._apm, self._is_autonomous,
                idle_seconds=0, last_action="idle",
                typing_content=self._typing_content,
            )
            self.send_trigger(prompt)

    # ---- Dead code preserved below (CLI fallback) ----

    def _run_cli(self, prompt: str) -> str | None:
        tmp_file = ""
        try:
            fd, tmp_file = tempfile.mkstemp(suffix=".txt", prefix="daemon_prompt_")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(prompt)
            if os.name == "nt":
                cmd = [
                    "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", OPENCODE_SCRIPT_PATH, tmp_file,
                ]
            else:
                cmd = ["bash", OPENCODE_SCRIPT_PATH, tmp_file]
            logger.info("Running CLI command: %s", cmd)
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=OPENCODE_TIMEOUT_SECONDS,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
        except FileNotFoundError as e:
            logger.warning("CLI FileNotFoundError: %s", e)
            self.error_occurred.emit("powershell or opencode-query.ps1 not found")
            return None
        except subprocess.TimeoutExpired as e:
            logger.warning("CLI TimeoutExpired: %s", e)
            self.error_occurred.emit(f"Query timed out after {OPENCODE_TIMEOUT_SECONDS}s")
            return None
        except Exception as e:
            logger.warning("CLI execution exception: %s", e)
            self.error_occurred.emit(f"Query error: {e.__class__.__name__}")
            return None
        finally:
            try:
                if tmp_file:
                    os.unlink(tmp_file)
            except Exception:
                pass

        stdout = (result.stdout or b"").decode("utf-8", errors="replace")
        if result.returncode != 0:
            err_msg = (result.stderr or b"").decode("utf-8", errors="replace").strip() or stdout.strip()
            if len(err_msg) > 100:
                err_msg = err_msg[:97] + "..."
            self.error_occurred.emit(f"Opencode error: {err_msg}")
            return None
        if not stdout.strip():
            return '{"dialogue":"...", "action":"idle", "target_x":null}'
        return stdout

    def run_legacy(self) -> None:
        """Full legacy run() path using _build_prompt and _run_cli. Not called by PetWindow."""
        prompt = _build_prompt(
            self._user_input, self._context_hint, self._apm, self._is_autonomous,
            idle_seconds=0, last_action="idle",
            typing_content=self._typing_content,
        )
        raw_output = self._post_message(prompt)
        if raw_output is not None:
            self._process_raw_output(raw_output)
            return
        raw_output = self._run_cli(prompt)
        if raw_output is not None:
            self._process_raw_output(raw_output)
```

- [ ] **Step 4: Run new opencode_worker tests**

```powershell
py -m pytest tests/test_opencode_worker.py -v
```

Expect many failures due to old signal names. Update old tests:

Update all references from:
- `worker.structured_ready` → `worker.trigger_ready`
- `worker.structured_batch_ready` → `worker.trigger_ready`
- `worker.structured_multiplexed` → `worker.trigger_ready`
- `worker.result_ready` → `worker.trigger_ready` or `worker.error_occurred`

Update constructor calls — remove removed params (`memory_context`, `history_context`, `idle_seconds`, `last_action`, `continue_session`, `modes`).

- [ ] **Step 5: Run updated tests until all pass**

```powershell
py -m pytest tests/test_opencode_worker.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/opencode_worker.py tests/test_opencode_worker.py
git commit -m "feat: add inject_context/send_trigger with noReply, consolidate signals to trigger_ready"
```

---

### Task 11: Rename + Rewrite `src/context_builder.py` → `src/context_manager.py`

**Files:**
- Rename: `src/context_builder.py` → `src/context_manager.py`
- Modify (new content): `src/context_manager.py`
- Rename: `tests/test_context_builder.py` → `tests/test_context_manager.py`
- Modify (updated): `tests/test_context_manager.py`

- [ ] **Step 1: Rename files**

```powershell
Move-Item -LiteralPath "src\context_builder.py" -Destination "src\context_manager.py"
Move-Item -LiteralPath "tests\test_context_builder.py" -Destination "tests\test_context_manager.py"
```

- [ ] **Step 2: Write `src/context_manager.py` with new API**

```python
# src/context_manager.py
"""ContextManager -- builds injection payloads and minimal trigger prompts.

Replaces ContextBuilder. Three payload types:
  inject_full()  -- one-time: skill + brain + diary(5) + format + role (noReply:true)
  inject_delta() -- state changes since last snapshot (noReply:true)
  build_trigger() -- minimal trigger prompt (noReply:false)
"""
from __future__ import annotations
import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

from src.constants import _PERSONA_HINT
from src.opencode_worker import _SKILL_CONTENT, FORMAT_INSTRUCTIONS

if TYPE_CHECKING:
    from src.memory import Memory
    from src.history import History


def _apm_bucket(apm: int) -> str:
    if apm < 60:
        return "low"
    if apm <= 150:
        return "medium"
    return "high"


HEARTBEAT_TIMEOUT_SEC = 15 * 60  # 15 minutes


class ContextManager:
    def __init__(self, memory: "Memory", history: "History",
                 diary_entries_ref: list[str]) -> None:
        self._memory = memory
        self._history = history
        self._diary = diary_entries_ref
        self._snapshot: dict = {}
        self._diary_injected_up_to: int = 0
        self._last_activity: float = 0.0
        self._full_injected: bool = False

    # ---- Public API ----

    def inject_full(self) -> str:
        """Build the one-time full session injection payload."""
        parts = []

        if _SKILL_CONTENT:
            parts.append(_SKILL_CONTENT)

        parts.append("ROLE: You are Daemon, the user's desktop pet. You are a sleeper agent owned by the user's wife. You surveil and roast.")

        mem_block = self._memory.get_context_block(None)
        if mem_block:
            parts.append(mem_block)

        if self._diary:
            lines = ["## Daemon's diary (recent):"]
            for entry in self._diary[-5:]:
                lines.append(f"- {entry}")
            parts.append("\n".join(lines))

        parts.append(FORMAT_INSTRUCTIONS)
        parts.append("INSTRUCTION: Respond ONLY with valid JSON as specified above. No markdown, no preamble.")

        self._full_injected = True
        self._snapshot_current()
        self._last_activity = time.monotonic()
        return "\n\n".join(parts)

    def inject_delta(self, context_hint: str, apm: int) -> str | None:
        """Build delta injection for state changes since last snapshot. Returns None if nothing changed."""
        if not self._snapshot:
            return None

        lines = ["DELTA CONTEXT UPDATE:"]

        prev_window = self._snapshot.get("active_window", "")
        if context_hint and context_hint != prev_window:
            lines.append(f"Active window changed to: {context_hint}")

        prev_bucket = self._snapshot.get("apm_bucket", "")
        current_bucket = _apm_bucket(apm)
        if current_bucket != prev_bucket:
            lines.append(f"APM level: {current_bucket}")

        prev_mem = self._snapshot.get("memory", {})
        new_facts = {}
        for k, v in self._memory.get_all().items():
            if prev_mem.get(k) != v:
                new_facts[k] = v
        if new_facts:
            lines.append("New facts learned:")
            for k, v in new_facts.items():
                lines.append(f"- {k}: {v}")

        if len(self._diary) > self._diary_injected_up_to:
            new_diary = self._diary[self._diary_injected_up_to:]
            lines.append("New diary entries:")
            for entry in new_diary[-3:]:
                lines.append(f"- {entry}")

        if len(lines) == 1:
            return None  # Nothing changed

        self._snapshot_current()
        return "\n".join(lines)

    def build_trigger(self, mode: str, user_input: str, apm: int,
                      idle_seconds: float, typing_content: str = "",
                      is_autonomous: bool = True) -> str:
        """Build minimal trigger prompt. The session already has full context."""
        self._last_activity = time.monotonic()

        mode_instruction = (
            "You are thinking to yourself (internal monologue). The user cannot hear you."
            if is_autonomous
            else "You are responding directly to the user."
        )

        lines = [
            mode_instruction,
            f"Mode: {mode}",
            f"APM: {apm}",
            f"Idle seconds: {int(idle_seconds)}",
        ]
        if user_input:
            lines.append(f"User said: {user_input}")
        if typing_content:
            lines.append("")
            lines.append(typing_content)

        if is_autonomous:
            lines.append("Generate exactly 5 dialogs as a JSON array.")
        else:
            lines.append("Respond with a single JSON object.")

        return "\n".join(lines)

    def needs_reinjection(self) -> bool:
        """Return True if session has been idle > HEARTBEAT_TIMEOUT_SEC."""
        if not self._full_injected:
            return True
        elapsed = time.monotonic() - self._last_activity
        return elapsed > HEARTBEAT_TIMEOUT_SEC

    def reset(self) -> None:
        """Force next call to use inject_full()."""
        self._full_injected = False
        self._snapshot = {}
        self._diary_injected_up_to = 0

    def has_injected_full(self) -> bool:
        return self._full_injected

    # ---- Internal ----

    def _snapshot_current(self) -> None:
        self._snapshot = {
            "memory": dict(self._memory.get_all()),
            "diary_len": len(self._diary),
            "active_window": self._snapshot.get("active_window", ""),
            "apm_bucket": self._snapshot.get("apm_bucket", ""),
        }
        self._diary_injected_up_to = len(self._diary)

    def snapshot_context(self, context_hint: str, apm: int) -> None:
        """Update active_window and apm_bucket in snapshot (call after delta injection)."""
        if self._snapshot:
            self._snapshot["active_window"] = context_hint
            self._snapshot["apm_bucket"] = _apm_bucket(apm)
```

- [ ] **Step 3: Update tests in `tests/test_context_manager.py`**

Rename all references from `ContextBuilder` to `ContextManager`. Update test assertions to match new API. Keep existing delta/full tests where they still apply, add new injection tests:

```python
def test_inject_full_includes_skill():
    from unittest.mock import MagicMock
    from src.context_manager import ContextManager
    mem = MagicMock()
    mem.get_context_block.return_value = ""
    hist = MagicMock()
    cm = ContextManager(mem, hist, [])
    payload = cm.inject_full()
    assert "VALID_ACTIONS" not in payload or "dialogue" in payload.lower()
    assert cm.has_injected_full()


def test_inject_delta_returns_none_when_no_changes():
    from unittest.mock import MagicMock
    from src.context_manager import ContextManager
    mem = MagicMock()
    mem.get_all.return_value = {}
    hist = MagicMock()
    cm = ContextManager(mem, hist, [])
    cm.inject_full()  # Establish snapshot
    result = cm.inject_delta("Desktop", 100)
    assert result is None


def test_inject_delta_detects_window_change():
    from unittest.mock import MagicMock
    from src.context_manager import ContextManager
    mem = MagicMock()
    mem.get_all.return_value = {}
    hist = MagicMock()
    cm = ContextManager(mem, hist, [])
    cm.inject_full()  # snapshot has active_window=""
    cm._snapshot["active_window"] = "Notepad"
    result = cm.inject_delta("YouTube", 100)
    assert result is not None
    assert "YouTube" in result


def test_needs_reinjection_initially_true():
    from unittest.mock import MagicMock
    from src.context_manager import ContextManager
    cm = ContextManager(MagicMock(), MagicMock(), [])
    assert cm.needs_reinjection() is True


def test_needs_reinjection_false_after_full():
    from unittest.mock import MagicMock
    from src.context_manager import ContextManager
    mem = MagicMock()
    mem.get_all.return_value = {}
    mem.get_context_block.return_value = ""
    cm = ContextManager(mem, MagicMock(), [])
    cm.inject_full()
    assert cm.needs_reinjection() is False


def test_build_trigger_is_minimal():
    from unittest.mock import MagicMock
    from src.context_manager import ContextManager
    cm = ContextManager(MagicMock(), MagicMock(), [])
    trigger = cm.build_trigger("active_chat", "", 180, 5.0)
    assert len(trigger) < 500
    assert "active_chat" in trigger
    assert "180" in trigger


def test_reset_forces_reinjection():
    from unittest.mock import MagicMock
    from src.context_manager import ContextManager
    mem = MagicMock()
    mem.get_all.return_value = {}
    mem.get_context_block.return_value = ""
    cm = ContextManager(mem, MagicMock(), [])
    cm.inject_full()
    cm.reset()
    assert cm.needs_reinjection() is True
    assert cm.has_injected_full() is False
```

- [ ] **Step 4: Run context_manager tests**

```powershell
py -m pytest tests/test_context_manager.py -v
```

Update/fix any old tests that reference removed ContextBuilder methods (`build_prompt`, `has_sent_baseline`, `on_path_change`, `reset_baseline`). These are replaced by `build_trigger`, `has_injected_full`, `reset`.

- [ ] **Step 5: Commit**

```bash
git add src/context_manager.py tests/test_context_manager.py
git rm src/context_builder.py tests/test_context_builder.py 2>$null
git commit -m "feat: ContextBuilder -> ContextManager with inject_full/delta/trigger API"
```

---

### Task 12: Rewire `src/pet_window.py` for noReply Flow

**Files:**
- Modify: `src/pet_window.py`
- Modify: `tests/test_pet_window.py`

This is the integration step. PetWindow gains session wiring, injection cooldown, deferred triggers, and diary seeding fix.

- [ ] **Step 1: Update imports in `src/pet_window.py`**

```python
# Replace:
from src.context_builder import ContextBuilder
# With:
from src.context_manager import ContextManager

# Add:
from src.diary_store import DiaryStore
```

- [ ] **Step 2: Update `__init__` — construct DiaryStore, ContextManager, add injection state**

Find the block around lines 130-160 and replace with:

```python
        self._memory = Memory(path=memory_path)
        self._history = History(path=history_path)
        self._firebase_mem = MemoryManager()
        self._firebase_available = True
        self._diary_entries: list[str] = []
        self._diary_synced: int = 0
        self._diary_store = DiaryStore(DIARY_PATH)
        self._init_diary()

        self._write_coalescer = WriteCoalescer(
            memory=self._memory, history=self._history,
            memory_manager=self._firebase_mem,
            diary_store=self._diary_store,
            diary_entries_ref=self._diary_entries,
        )
        self._memory._coalescer = self._write_coalescer
        self._history._coalescer = self._write_coalescer

        self._context_manager = ContextManager(
            memory=self._memory, history=self._history,
            diary_entries_ref=self._diary_entries,
        )
        self._response_manager = AutonomousResponseManager(
            cache_path=str(Path.home() / ".daemon_response_cache.json"),
            write_coalescer=self._write_coalescer,
        )
        for pool in self._response_manager._pools.values():
            pool.refill_needed.connect(self._on_refill_needed)
        self._response_manager.start()

        # Injection state
        self._injection_cooldown: bool = False
        self._deferred_triggers: list[dict] = []
        self._opencode_session_id: str | None = None

        self._typing_last_len = 0
        self._typing_debounce_timer = QTimer()
        self._typing_debounce_timer.setSingleShot(True)
        self._typing_debounce_timer.setInterval(2000)
        self._typing_debounce_timer.timeout.connect(self._on_typing_debounce)
        self._typing_buffer.text_updated.connect(self._typing_debounce_timer.start)

        self._write_coalescer.start()
```

- [ ] **Step 3: Update `_init_diary()` — fix seeding**

```python
    def _init_diary(self) -> None:
        """Load diary from local file or fetch from Firebase on first run."""
        try:
            self._firebase_mem.sync_to_local(self._memory)
            self._firebase_available = True
        except Exception as e:
            self._firebase_available = False
            logger.warning("Firebase unavailable: %s", e)
        local = self._diary_store.read()
        if local and local.get("entries"):
            self._diary_entries = local["entries"]
            self._diary_synced = local.get("synced", 0)
            logger.info("Diary loaded from local file (%d entries)", len(self._diary_entries))
        else:
            entries = self._firebase_mem.fetch_all_diary_entries(limit=200)
            self._diary_entries = entries
            self._diary_synced = len(entries)
            self._diary_store.write(entries, len(entries))
            logger.info("Diary fetched from Firebase (%d entries)", len(entries))
        # Only seed on first run AND empty diary
        first_run_done = (initial_state or {}).get("first_run_done", False)
        if not self._diary_entries and not first_run_done:
            _seed_diary_entries = [
                "I just heard him try to say 'Spotify' and he called it 'Stopipy'. Oh geez...",
                "He just asked if we should go to the 'Frood Coat'. I am losing my mind.",
                "He tried to explain his 'ODSD' today. I think he meant OCD and ADHD.",
            ]
            for entry in _seed_diary_entries:
                self._diary_entries.append(entry)
            self._diary_synced = 0
            self._diary_store.write(self._diary_entries, 0)
            logger.info("Diary seeded (%d entries)", len(_seed_diary_entries))
```

- [ ] **Step 4: Add session/injection wiring methods**

Add new methods after `_init_diary`:

```python
    def _on_session_created(self, session_id: str) -> None:
        """Session created -- inject full context via noReply."""
        self._opencode_session_id = session_id
        self._injection_cooldown = True
        prompt = self._context_manager.inject_full()
        worker = OpencodeWorker(
            session_id=session_id,
        )
        worker.context_injected.connect(self._on_context_injected)
        worker.injection_failed.connect(self._on_injection_failed)
        worker.inject_context(prompt)

    def _on_context_injected(self) -> None:
        """Full context injected -- start cooldown timer."""
        logger.info("Context injected, starting 100ms cooldown")
        QTimer.singleShot(100, self._on_injection_cooldown_done)

    def _on_injection_failed(self, error: str) -> None:
        """Injection failed -- reset session, triggers will retry."""
        logger.warning("Context injection failed: %s", error)
        self._injection_cooldown = False
        self._opencode_session_id = None
        self._context_manager.reset()
        # Drain deferred triggers -- they'll create new sessions
        for trigger in self._deferred_triggers:
            self._dispatch_trigger(**trigger)
        self._deferred_triggers.clear()

    def _on_injection_cooldown_done(self) -> None:
        """Cooldown elapsed -- unblock and replay deferred triggers."""
        self._injection_cooldown = False
        deferred = list(self._deferred_triggers)
        self._deferred_triggers.clear()
        for trigger in deferred:
            self._dispatch_trigger(**trigger)

    def _dispatch_trigger(self, mode: str, user_input: str = "",
                          context_hint: str = "", apm: int = 0,
                          idle_seconds: float = 0.0,
                          typing_content: str = "",
                          is_autonomous: bool = True) -> None:
        """Create OpencodeWorker and send a trigger."""
        # Check for re-injection
        if is_autonomous and self._context_manager.needs_reinjection():
            logger.info("Session stale, re-injecting full context")
            self._context_manager.reset()
            self._on_session_created(self._opencode_session_id or "")
            # Defer this trigger
            self._deferred_triggers.append({
                "mode": mode, "user_input": user_input,
                "context_hint": context_hint, "apm": apm,
                "idle_seconds": idle_seconds, "typing_content": typing_content,
                "is_autonomous": is_autonomous,
            })
            return

        if self._injection_cooldown:
            self._deferred_triggers.append({
                "mode": mode, "user_input": user_input,
                "context_hint": context_hint, "apm": apm,
                "idle_seconds": idle_seconds, "typing_content": typing_content,
                "is_autonomous": is_autonomous,
            })
            logger.debug("Injection cooldown active, deferred trigger '%s'", mode)
            return

        prompt = self._context_manager.build_trigger(
            mode=mode, user_input=user_input, apm=apm,
            idle_seconds=idle_seconds, typing_content=typing_content,
            is_autonomous=is_autonomous,
        )
        worker = OpencodeWorker(
            user_input=user_input, context_hint=context_hint,
            apm=apm, is_autonomous=is_autonomous,
            session_id=self._opencode_session_id,
            prompt=prompt, typing_content=typing_content,
        )
        worker.trigger_ready.connect(self._on_trigger_ready)
        worker.error_occurred.connect(self._on_opencode_error)
        worker.session_created.connect(self._on_session_created)
        worker.brain_update_ready.connect(self._on_brain_update)
        worker.pool_items_ready.connect(self._on_pool_items)
        worker.start()
        self._opencode_worker = worker
```

- [ ] **Step 5: Add `_on_trigger_ready` unified handler**

```python
    def _on_trigger_ready(self, items: list[dict]) -> None:
        """Handle consolidated trigger response. Items may be list of dicts."""
        logger.info("_on_trigger_ready: %d items", len(items))
        self._autonomous_query_pending = False
        self._session_active = True
        self._opencode_worker = None

        if not items:
            return

        # Update context snapshot for delta tracking
        self._context_manager.snapshot_context(
            self._context_hint if hasattr(self, '_context_hint') else "",
            self._apm_worker.apm if self._apm_worker else 0,
        )

        # Dispatch first item, cache rest
        first = items[0]
        dialogue = first.get("dialogue", "")
        action = first.get("action", "idle")
        target_x = first.get("target_x", 0)
        self._dispatch_structured(dialogue, action, target_x, "")

        # Cache remaining items into response pools
        for item in items[1:]:
            pool_type = item.get("pool_type", "jokes_blackmail")
            self._response_manager.add_items(pool_type, [item])

        self._boredom_timer_ms = AUTONOMOUS_QUERY_INTERVAL_SEC * 1000
```

- [ ] **Step 6: Update timer tick handlers**

Update `_on_active_chat_tick`, `_on_joke_tick` to use `_dispatch_trigger`:

```python
    def _on_active_chat_tick(self) -> None:
        if not self._should_fire_autonomous("active_chat"):
            return
        apm = self._apm_worker.apm if self._apm_worker else 0
        self._dispatch_trigger(
            mode="active_chat",
            context_hint=self._active_window_title,
            apm=apm,
            idle_seconds=self._idle_seconds,
            typing_content=self._typing_buffer.get_context() if self._typing_buffer else "",
            is_autonomous=True,
        )

    def _on_joke_tick(self) -> None:
        if not self._should_fire_autonomous("joke"):
            return
        apm = self._apm_worker.apm if self._apm_worker else 0
        self._dispatch_trigger(
            mode="joke",
            context_hint=self._active_window_title,
            apm=apm,
            idle_seconds=self._idle_seconds,
            is_autonomous=True,
        )
```

Update `_on_input_submitted` similarly to use `_dispatch_trigger` with `is_autonomous=False`.

- [ ] **Step 7: Update `_force_quit_app` — correct ordering**

```python
    def _force_quit_app(self) -> None:
        self._force_quit = True
        self._fsm_timer.stop()
        self._active_chat_timer.stop()
        self._joke_timer.stop()
        self._response_manager.stop()
        try:
            # Flush writes BEFORE session close (per spec)
            self._write_coalescer.stop()
            self._write_coalescer.flush()
        except Exception as e:
            logger.warning("WriteCoalescer flush failed: %s", e)
        for pool_type, worker in list(self._refill_workers.items()):
            if worker.isRunning():
                worker.quit()
                worker.wait(3000)
        self._refill_workers.clear()
        if self._opencode_worker and self._opencode_worker.isRunning():
            self._opencode_worker.quit()
            self._opencode_worker.wait(3000)
        self._close_opencode_session()
        self._typing_buffer.stop()
        self._tts.stop()
        self._apm_worker.stop()
        self._tray_icon.hide()
        QApplication.quit()
```

- [ ] **Step 8: Update `_on_refill_needed`**

The refill worker should also use the new worker API. Update `_on_refill_needed` to use `OpencodeWorker` with `is_autonomous=True` and `modes` removed (the new worker doesn't support modes — it always returns a list).

- [ ] **Step 9: Update tests in `tests/test_pet_window.py`**

Key test updates:
- Constructor tests: expect `DiaryStore` and `ContextManager` instead of `ContextBuilder`
- Signal tests: connect to `trigger_ready` instead of old signals
- Diary seeding test: verify only seeded on first_run_done=False
- Session wiring tests: verify `_on_session_created`, `_on_context_injected`, `_on_injection_failed`

```python
def test_diary_seeded_only_on_first_run():
    """Diary is only seeded on first run with empty diary."""
    ...

def test_context_manager_injection_state():
    """PetWindow tracks injection_cooldown and deferred_triggers."""
    ...

def test_injection_cooldown_blocks_triggers():
    """Triggers are deferred during injection cooldown."""
    ...

def test_deferred_triggers_replay_after_injection():
    """Deferred triggers replay after cooldown completes."""
    ...
```

- [ ] **Step 10: Run pet_window tests and fix regressions**

```powershell
py -m pytest tests/test_pet_window.py -v
```

- [ ] **Step 11: Commit**

```bash
git add src/pet_window.py tests/test_pet_window.py
git commit -m "feat: wire noReply injection flow, fix diary seeding, flush ordering"
```

---

### Task 13: Update `daemon.py` — Lock + DiaryStore + Cleanup

**Files:**
- Modify: `daemon.py`

- [ ] **Step 1: Update `daemon.py`**

```python
import sys
import os
import argparse
import logging
from pathlib import Path
from PyQt6.QtWidgets import QApplication

logger = logging.getLogger("daemon")

LOCK_PATH = Path.home() / ".daemon.lock"


def _acquire_lock() -> bool:
    """Check for existing daemon instance. Return True if lock acquired."""
    if LOCK_PATH.exists():
        try:
            pid = int(LOCK_PATH.read_text().strip())
            import ctypes
            PROCESS_QUERY_LIMITED_INFO = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFO, False, pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                logger.warning("Daemon already running (PID %d)", pid)
                return False
        except Exception:
            pass
    LOCK_PATH.write_text(str(os.getpid()))
    return True


def _release_lock() -> None:
    try:
        LOCK_PATH.unlink(missing_ok=True)
    except Exception:
        pass


def _ensure_ffmpeg_on_path():
    ffmpeg_dir = os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Microsoft", "WinGet", "Packages",
    )
    if os.path.isdir(ffmpeg_dir):
        for entry in os.listdir(ffmpeg_dir):
            if entry.lower().startswith("gyan.ffmpeg"):
                bin_dir = os.path.join(ffmpeg_dir, entry, "ffmpeg-8.1.1-essentials_build", "bin")
                if os.path.isdir(bin_dir) and bin_dir not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")


def main() -> None:
    _ensure_ffmpeg_on_path()
    from src.config import load_config
    import src.constants as constants

    cfg = load_config()
    for key, val in cfg.items():
        if hasattr(constants, key):
            setattr(constants, key, val)

    parser = argparse.ArgumentParser(description="Daemon Desktop Pet")
    parser.add_argument("--debug", action="store_true", help="Run headless FSM simulation")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose debug logging")
    parser.add_argument("--no-opencode", action="store_true", help="Disable opencode integration")
    args = parser.parse_args()

    from src.logging_setup import setup_logging
    setup_logging(debug=args.verbose, config_overrides=cfg.get("logging"))

    if args.debug:
        _run_debug_simulation()
        return

    if not _acquire_lock():
        print("Daemon is already running. Exiting.", file=sys.stderr)
        sys.exit(1)

    from src.constants import OPENCODE_SERVER_URL
    from src.opencode_serve_manager import ensure_opencode_serve_running
    if not args.no_opencode:
        if ensure_opencode_serve_running(url=OPENCODE_SERVER_URL):
            logger.debug("opencode serve ready at %s", OPENCODE_SERVER_URL)
        else:
            logger.info("opencode serve not available")

    from src.persistence import load_state, save_state
    from src.pet_window import PetWindow
    import time

    state = load_state()
    start_time = time.monotonic()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    window = PetWindow(opencode_enabled=not args.no_opencode, skill_ready=True, initial_state=state)

    try:
        exit_code = app.exec()
    finally:
        _release_lock()

    elapsed = int(time.monotonic() - start_time)

    window._firebase_mem.sync_from_local(window._memory)
    window._diary_synced = window._firebase_mem.push_pending_diaries(
        window._diary_store, window._diary_entries, window._diary_synced,
    )
    window._history.save()
    window._memory.save()

    save_state({
        "mood": window.mood_score,
        "interactions": window.interaction_count,
        "runtime_seconds": state.get("runtime_seconds", 0) + elapsed,
        "skill_greeted": True,
        "first_run_done": True,
    })

    sys.exit(exit_code)


def _run_debug_simulation() -> None:
    from dataclasses import replace
    from src.pet_fsm import PetFSM, FSMContext, PetState

    fsm = PetFSM()
    prev_state = fsm.current_state

    for tick in range(100):
        ctx = FSMContext(
            cursor_pos=(9999, 9999),
            pet_rect=(100, 900, 40, 50),
            apm=0,
            is_dragged=False,
            is_falling=False,
            query_pending=False,
            autonomous_query_pending=False,
            build_event=None,
            idle_seconds=float(tick),
            wander_due=(tick == 5),
            hyper_sustained_seconds=0.0,
            hyper_cooldown_seconds=0.0,
            state_elapsed_ms=tick * 33,
        )
        if 70 <= tick < 80:
            ctx = replace(ctx, is_dragged=True)
        if 80 <= tick < 90:
            ctx = replace(ctx, is_dragged=False, is_falling=True)
        if tick >= 90:
            ctx = replace(ctx, is_falling=False)
        new_state = fsm.update(33, ctx)
        if new_state != prev_state:
            logger.info("[tick %03d] %s -> %s", tick, prev_state.name, new_state.name)
            prev_state = new_state

    logger.info("simulation complete")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run daemon.py debug mode to verify no import errors**

```powershell
py daemon.py --debug --no-opencode
```
Expected: FSM simulation runs, no import errors

- [ ] **Step 3: Commit**

```bash
git add daemon.py
git commit -m "feat: single-instance lock, diary_store wiring, try/finally cleanup"
```

---

### Task 14: Final Verification — Full Test Suite

**Files:**
- All modified tests

- [ ] **Step 1: Run full test suite**

```powershell
py -m pytest tests/ -v
```

- [ ] **Step 2: Fix any remaining failures**

Expected categories of failures and fixes:
- **ImportError for `ContextBuilder`**: Any remaining references in test files → update to `ContextManager`
- **Missing signal names**: Old `structured_ready` etc. in tests → update to `trigger_ready`
- **Constructor signature mismatches**: Old params on `OpencodeWorker` → remove removed params
- **WriteCoalescer constructor**: Updated to use `diary_store` → update test fixtures to pass `diary_store=DiaryStore(path)`

- [ ] **Step 3: Iterate until all tests pass**

```powershell
py -m pytest tests/ -v 2>&1 | Select-String -Pattern "FAILED|ERROR|passed"
```

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "test: update all tests for noReply API and storage hardening"
```

- [ ] **Step 5: Squash-merge to master per git workflow**

```bash
git checkout master
git merge --squash task-<N>-storage-noreply
git commit -m "feat: storage hardening + noReply context injection"
git branch -D task-<N>-storage-noreply
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] brain_schema.py extraction (Task 1)
- [x] diary_store.py creation (Task 2)
- [x] memory.py backup (Task 3)
- [x] history.py backup (Task 4)
- [x] persistence.py atomic write (Task 5)
- [x] response_manager.py atomic + TTL (Task 6)
- [x] memory_manager.py retry queue + limit (Task 7)
- [x] write_coalescer.py brain flag + diary_store (Task 8)
- [x] seed_brain.py import brain_schema (Task 9)
- [x] opencode_worker.py inject_context + consolidated signals (Task 10)
- [x] context_manager.py rename + inject_full/delta/trigger (Task 11)
- [x] pet_window.py session wiring (Task 12)
- [x] daemon.py lock + try/finally (Task 13)
- [x] Full test suite run (Task 14)

**Placeholder scan:** No TBD/TODO/fixme. All code shown.

**Type consistency:**
- `trigger_ready` emits `list[dict]` everywhere
- `DiaryStore` path constructor consistent across all tasks
- `ContextManager.inject_full()` returns `str` everywhere
- `inject_delta()` returns `str | None` everywhere
- `build_trigger()` accepts same params across worker and manager
