# Screen Reading, APM Priority, & Autonomous Framing

**Date:** 2026-06-08
**Status:** Design (pre-implementation)

## Problem

The Daemon desktop pet has three connected gaps:

1. **No screen content visibility** — The pet knows the active window title but cannot see what's *in* the window (terminal output, code, browser page). Responses are blind to what the user is actually working on.
2. **APM underutilized as context** — APM is sent as a raw number but not framed as the pet's primary signal. The LLM doesn't understand to weight it heavily.
3. **Autonomous responses framed as user queries** — When the pet thinks autonomously, the LLM still formats its output as if responding to a user question. The prompt doesn't adequately distinguish internal monologue from direct response.
4. **Storage scattered in home directory** — All state files use `Path.home()` making the project non-portable for dev.
5. **No insight into LLM reasoning** — The `thought` field in the JSON schema is parsed but discarded.

## Solution Overview

Five independent changes, each in a single file:

| # | Change | Primary file(s) | Complexity |
|---|--------|-----------------|------------|
| 1 | Screen Reader module | `src/screen_reader.py` (NEW) | ~50 lines |
| 2 | APM as primary signal | `src/context_manager.py` | ~5 lines |
| 3 | Autonomous vs user framing | `src/context_manager.py` | ~30 lines |
| 4 | Storage to `data/` | `src/constants.py` + 5 files | ~15 lines |
| 5 | CoT thought capture | `src/opencode_worker.py`, `src/pet_window.py` | ~30 lines |

## 1. Screen Reader

**File:** `src/screen_reader.py` (new)

### Interface

```python
class ScreenReader:
    @staticmethod
    def get_foreground_text() -> str
```

### Implementation

Uses `comtypes` to call Windows UI Automation API:

1. Get foreground window HWND via `ctypes.windll.user32.GetForegroundWindow()`
2. Get `IUIAutomation` COM interface via `comtypes.client`
3. Navigate to focused element, request `TextPattern`
4. Get `DocumentRange.GetText()` → returns up to 2000 characters
5. Trim whitespace, return

### Fallback chain

```
UIA success → return text
UIA fails → try WM_GETTEXT via ctypes on the HWND
WM_GETTEXT fails → return ""
```

### Integration

Called in `PetWindow._dispatch_trigger()` alongside `get_active_window_title()`:

```python
screen_text = ScreenReader.get_foreground_text()  # NEW
context_hint = get_active_window_title()
```

Passed to `build_trigger()` as new optional parameter `screen_text: str = ""`.

### Dependencies

- `comtypes` (pip install) — lightweight COM wrapper, pure Python
- Windows-only (returns `""` on non-Windows)

### Error handling

- Every COM/call wrapped in `try/except Exception` — never raises
- `comtypes` import gated: `try: import comtypes.client; except ImportError: return ""`
- Returns `""` on any failure

## 2. APM as Primary Signal

**No separate change.** The APM label is incorporated into the new trigger templates in Section 3. The raw number `APM: 50` becomes `APM (actions per minute — primary signal): 50` inside both `build_user_trigger()` and `build_autonomous_trigger()`. No new data structures, no trend history.

## 3. Autonomous vs User Framing

**File:** `src/context_manager.py`

### Change

Split `build_trigger()` into two methods:

```python
def build_user_trigger(self, mode, user_input, apm, idle_seconds, typing_content="", screen_text="") -> str
def build_autonomous_trigger(self, mode, apm, idle_seconds, typing_content="", screen_text="") -> str
```

### User trigger template

```
You are responding directly to the user.
Mode: {mode}
APM (actions per minute — primary signal): {apm}
Idle seconds: {int(idle_seconds)}
User said: {user_input}
{typing_content}
Screen: {screen_text}
Respond with a single JSON object.
```

### Autonomous trigger template

```
Daemon is watching the user. She notices something worth thinking about.
APM (actions per minute) is her main signal.
APM: {apm}
Screen: {screen_text}
Mode: {mode}
Idle seconds: {int(idle_seconds)}
{typing_content}

She is thinking to herself. This is an internal monologue — she is NOT responding to the user.
She should NOT say "you asked" or "you said" because the user did not say anything.
Generate exactly 5 dialogs as a JSON array.
```

**Key differences from current:**
- Autonomous: "Daemon is watching" framings instead of "You are thinking..."
- Explicit: "NOT responding to the user" — addresses the hallucination directly
- Explicit: "NOT say 'you asked' or 'you said'" — negative example prevents the pattern
- Screen text is first-class context, not appended

### Routing

```python
# In _dispatch_trigger():
if is_autonomous:
    prompt = self._context_manager.build_autonomous_trigger(...)
else:
    prompt = self._context_manager.build_user_trigger(...)
```

### daemon-skill.md addition

Add to the JSON format section:

```
Autonomous (internal monologue):
{"thought":"...","dialogue":"...","action":"<action>","priority":<1-5>}
  - dialogue must SOUND like internal monologue (muttering, observing, NOT addressing user)
  - The user did NOT ask anything. Daemon is thinking to herself.
```

## 4. Storage Relocation to `data/`

**File:** `src/constants.py`

### Change

Add:

```python
from pathlib import Path
STORAGE_DIR = Path(__file__).parent.parent / "data"
STORAGE_DIR.mkdir(exist_ok=True)
```

Then re-point all path constants:

```python
MEMORY_PATH = STORAGE_DIR / ".daemon_memory.json"
HISTORY_PATH = STORAGE_DIR / ".daemon_history.json"
DIARY_PATH = STORAGE_DIR / ".daemon_diary.json"
STATE_PATH = STORAGE_DIR / ".daemon_state.json"
CONFIG_PATH = STORAGE_DIR / ".daemon_config.json"
LOCK_PATH = STORAGE_DIR / ".daemon.lock"
RESPONSE_CACHE_PATH = STORAGE_DIR / ".daemon_response_cache.json"
THOUGHTS_LOG_PATH = STORAGE_DIR / "thoughts.log"
```

### Files to update

| File | What changes |
|------|-------------|
| `src/constants.py` | Add `STORAGE_DIR`, re-point all path constants |
| `src/config.py` | Use `CONFIG_PATH` instead of hardcoded home path |
| `src/persistence.py` | Already uses `STATE_PATH` constant (check) |
| `src/memory.py` | Already uses `MEMORY_PATH` constant (check) |
| `src/history.py` | Already uses `HISTORY_PATH` constant (check) |
| `src/diary_store.py` | Already uses `DIARY_PATH` constant (check) |
| `src/response_manager.py` | Uses home path directly — update to constant |
| `daemon.py` | PID lock uses `LOCK_PATH` constant |
| `.gitignore` | Add `data/` |

### Migration

No migration script. Old files in home directory are abandoned. State will rebuild naturally. On first boot with `data/` paths, the pet starts fresh (clean slate is fine for dev).

## 5. CoT Thought Capture

**File:** `src/opencode_worker.py`, `src/pet_window.py`

### Change in OpencodeWorker

In `_normalize_parsed()`, preserve the `thought` field:

```python
normalized.append({
    "dialogue": dialogue,
    "action": action,
    "target_x": target_x,
    "priority": priority,
    "thought": item.get("thought", ""),  # NEW — preserve, default to ""
})
```

### Change in PetWindow

New method `_log_thought()`:

```python
def _log_thought(self, thought: str, mode: str, dialogue: str) -> None:
    if not DEBUG:
        return
    log_path = THOUGHTS_LOG_PATH
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] [{mode}] Thought({len(thought)}c): {thought}\n"
    entry += f"[{timestamp}] [{mode}] Dialogue: {dialogue}\n"
    
    # Rotate: if >= 1000 lines, keep last 500
    if log_path.exists():
        lines = log_path.read_text().splitlines()
        if len(lines) >= 1000:
            log_path.write_text("\n".join(lines[-500:]) + "\n")
    
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry)
```

Called from `_on_trigger_ready()`:

```python
for item in items:
    thought = item.pop("thought", "")  # Extract before rest of pipeline
    if thought:
        self._log_thought(thought, mode, item.get("dialogue", ""))
```

### Guard

- Only writes when `--verbose` (`DEBUG=True`) is active
- Rotates at 1000 lines to prevent infinite growth
- Logs character count of thought field for debugging model output length

## Token Impact

| Phase | Current | After | Delta |
|-------|---------|-------|-------|
| Session injection (one-time) | ~2500 | ~2500 | 0 |
| Autonomous trigger | ~40 | ~90-165 | +50-125 (screen text) |
| User trigger | ~40-200 | ~90-325 | +50-125 (screen text) |

Screen text capped at 2000 chars (~500 tokens) in the reader, but typical window text is 200-500 chars (~50-125 tokens). This is negligible for the API.

## Testing

### New test file: `tests/test_screen_reader.py`

| Test | Description |
|------|-------------|
| `test_returns_empty_on_non_windows` | sys.platform mock → returns "" |
| `test_returns_empty_on_uia_failure` | comtypes import fails → returns "" |
| `test_returns_text_on_success` | UIA mocked → returns text |
| `test_caps_at_2000_chars` | Long text truncated |

### Existing file additions

| File | Tests |
|------|-------|
| `tests/test_context_manager.py` | 2 tests: autonomous trigger template has internal monologue wording, user trigger template has "responding directly" wording |
| `tests/test_opencode_worker.py` | 2 tests: thought preserved through pipeline, thought defaults to "" when absent |
| `tests/test_pet_window.py` | 2 tests: thought logged when DEBUG=True, not logged when DEBUG=False |

## Edge Cases

| Case | Behavior |
|------|----------|
| UIA not installed (no comtypes) | Returns "" — existing behavior preserved |
| Window has no text | Returns "" — hit the fallback chain |
| Screen text >2000 chars | Truncated to first 2000 chars |
| Model outputs no `thought` field | Defaults to "" — no crash |
| `data/` directory deleted | `STORAGE_DIR.mkdir(exist_ok=True)` recreates on next boot |
| All storage files missing | Fresh start (first_run_done=False → onboarding + seed diary) |

## Non-Goals

- No OCR. Pixel-based text extraction is out of scope for this design.
- No APM trend history or bucket enrichment. The raw number + "primary signal" label is sufficient.
- No per-app text extractors. UIA covers most windows; if it doesn't work for a particular app, that app simply returns "".
- No UI for the thought log. It's a debug file, tail it with `cat` / `Get-Content`.
