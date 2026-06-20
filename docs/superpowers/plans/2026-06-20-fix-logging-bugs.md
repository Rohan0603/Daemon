# Bug Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix schema-to-prompt mismatch, APM bubble spamming, THINKING starvation, and remove hardcoded model strings from tests.

**Architecture:** We will update the JSON schema to match the backend expectation, add debouncing to `behavior_controller` to stop redundant messages, improve state recovery for THINKING state timeouts, and dynamically fetch the model ID in tests.

**Tech Stack:** Python 3, PyQt6, pytest

---

### Task 1: Fix JSON Schema Mismatch

**Files:**
- Modify: `src/constants.py`

- [ ] **Step 1: Write the minimal implementation**

Update `STRUCTURED_SCHEMA` to allow the missing fields that the prompt is actively requesting. The LLM refuses to generate `type`, `priority`, and `context_hash` because the JSON schema rejects them.

```python
# src/constants.py (around line 164)
STRUCTURED_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "type":         {"type": "string", "enum": ["typing_reaction", "observation", "intel_roast", "idle_thought"]},
            "thought":      {"type": "string", "maxLength": 200},
            "dialogue":     {"type": "string", "maxLength": 150},
            "priority":     {"type": "integer", "minimum": 1, "maximum": 5},
            "context_hash": {"type": "string"},
            "brain_update": {
                "type": "object",
                "description": "Optional dict to update user memory facts.",
                "additionalProperties": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            }
        },
        "required": ["thought", "dialogue", "type"],
        "additionalProperties": False,
    },
    "minItems": 1,
    "maxItems": 5,
}
```

- [ ] **Step 2: Commit**

```bash
git add src/constants.py
git commit -m "fix(schema): allow required properties in STRUCTURED_SCHEMA"
```

---

### Task 2: Fix Hardcoded Model ID in Tests

**Files:**
- Modify: `tests/test_opencode_worker.py`

- [ ] **Step 1: Write minimal implementation**

The user noticed the `north-mini-code-free` string is hardcoded in the test files. Instead of hardcoding, we should read it dynamically.
(Note: You'll need to find the exact line in `tests/test_opencode_worker.py` where `"north-mini-code-free"` is used and replace it with `DEFAULT_CONFIG["llm"]["model_id"]`)

```python
# Instead of asserting equal to "north-mini-code-free", assert it exists or equals DEFAULT_CONFIG
from src.config import DEFAULT_CONFIG

def test_something():
    # Replace hardcoded assertions:
    assert config["llm"]["model_id"] == DEFAULT_CONFIG["llm"]["model_id"]
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_opencode_worker.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_opencode_worker.py
git commit -m "test: remove hardcoded model ID from opencode worker tests"
```

---

### Task 3: Fix APM Bubble Spamming (Debouncing)

**Files:**
- Modify: `src/behavior_controller.py`

- [ ] **Step 1: Write minimal implementation**

We need to add a tracker for the last emitted APM message so that the same threshold doesn't get repeatedly triggered before the cooldown expires.

Look for the method that triggers the APM messages (e.g. `_check_apm_thresholds` or where APM bubble logic lives). Make sure it correctly respects `APM_STATE_CHANGE_COOLDOWN` or implements a flag so that if `last_apm_state == current_apm_state`, it doesn't queue duplicate dialogue.

If it relies on `_trigger_boredom_fsm()` or similar, ensure we only emit if we've been quiet for at least a few seconds.

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_behavior.py -v` (or whatever tests are relevant)
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/behavior_controller.py
git commit -m "fix(behavior): add debouncing to APM state changes to prevent bubble spam"
```

---

### Task 4: Fix THINKING State Starvation

**Files:**
- Modify: `src/pet_window.py`

- [ ] **Step 1: Write minimal implementation**

Ensure that if an opencode worker fails or times out, the `PetState` properly resets to `IDLE`.
In `src/pet_window.py`, ensure `_on_opencode_error` correctly clears the `THINKING` state.
Also check that pool refills (which run silently) do **not** force the pet into `THINKING` mode if they're purely background refills. Background refills should happen transparently.

```python
# In _on_refill_needed or wherever the background worker is launched:
# Make sure it DOES NOT call self._fsm.current_state = PetState.THINKING
# Background tasks shouldn't change the pet's physical state.
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/ -v` (You can skip old tests per user request, run only relevant test files or run all if fast)
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/pet_window.py
git commit -m "fix(fsm): prevent background pool refills from blocking pet in THINKING state"
```
