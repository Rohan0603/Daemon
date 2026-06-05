# Brain Schema & Field Mutability Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Add a typed, locked/editable schema to Daemon's brain so the LLM can propose updates to selected fields without accidentally overwriting core identity.

**Architecture:** A `_BRAIN_SCHEMA` dict in `memory_manager.py` defines every field with `locked`/`type`. The LLM includes an optional `brain_update` key in JSON responses. Python strips locked fields, validates types, and merges editable ones.

**Tech Stack:** Python 3.11+, PyQt6, Firebase Firestore, JSON

---

## Schema

```python
_BRAIN_SCHEMA: dict = {
    # ── Locked (never touched by LLM) ──
    "primary_directive_override": {"locked": True, "type": "string"},
    "daemon_profession":          {"locked": True, "type": "string"},
    "daemon_name":                {"locked": True, "type": "string"},
    "daemon_personality":         {"locked": True, "type": "string"},
    "daemon_origin":              {"locked": True, "type": "string"},
    "daemon_runtime_info":        {"locked": True, "type": "string"},
    "daemon_current_form":        {"locked": True, "type": "string"},
    "user_name":                  {"locked": True, "type": "string"},
    "user_profession":            {"locked": True, "type": "string"},
    # ── Editable (LLM can update) ──
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
```

## LLM `brain_update` Flow

During any autonomous mode, the LLM may include an optional `brain_update` key:

```json
{
  "thought": "He said 'Stopipy' again.",
  "dialogue": "Logging that one.",
  "action": "idle",
  "target_x": null,
  "brain_update": {
    "blackmail_material": ["Pronounces 'Restaurant' as 'Restlorunt'."],
    "recent_blackmail_log": ["2026-06-07 14:32: Caught Stopipy incident."]
  }
}
```

## Processing Pipeline

1. `OpencodeWorker._parse_json_response()` extracts `brain_update` if present
2. New signal: `brain_update_ready = pyqtSignal(dict)`
3. `PetWindow._on_brain_update(update)` → `MemoryManager.apply_brain_update(update)`
4. `apply_brain_update()` strips locked fields, validates types, deduplicates list items, caps `recent_blackmail_log` at 10
5. Results written to Firestore + local memory

## Files Changed

| File | Change |
|------|--------|
| `src/memory_manager.py` | Add `_BRAIN_SCHEMA`, `apply_brain_update()`, generate `_DEFAULT_BRAIN` from schema |
| `src/opencode_worker.py` | Extract `brain_update`, add signal |
| `src/pet_window.py` | Add `_on_brain_update()` slot, wire signal |
| `assets/daemon-skill.md` | Add `brain_update` to output contract |
| `seed_brain.py` | Mirror schema |
| `tests/` | Schema validation, locking, parsing, PetWindow integration |
