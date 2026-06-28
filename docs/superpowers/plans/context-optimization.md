# Plan: Context Injection Optimization

## Council Verdict
- **Do NOT implement delta-only context injection.** Negligible savings (free-tier DeepSeek, ~175 tokens/call), real complexity (thread-safe state, stale bugs, all-5-changed edge case).
- **DO configure `SlidingWindowConversationManager`** to manage context accumulation.
- **DO strip context** to only what the LLM actually acts on (active_window + typing_content).

## Deeper Analysis (Post-Council)

The council had a blind spot: `self.agent.messages = messages` in `StrandsSession.get_agent()` **replaces** the entire conversation history on every invocation. There is no accumulation of "Current system state" messages across invocations — they're wiped and replaced each time.

The *actual* problem is different:

1. **Each invocation sends 10 turns of full chat history** (from `self._history.get_recent(10)`) plus a full ~700-char context snapshot — all as a single prompt. The `SlidingWindowConversationManager(max_messages=10)` then processes these ~11+ turns plus tool-call/tool-result pairs, potentially dropping earlier historical turns to make room for tool interactions.

2. **`screen_text[:500]` dominates the context snapshot.** For an idle desk pet that mostly observes the user coding, ~500 chars of screen text is changing constantly (every keystroke in the editor) but the LLM rarely acts on it. Most autonomous triggers just produce a short quip.

3. **APM + idle_seconds change every tick** but are rarely actionable independently. They're context modifiers, not behavior triggers.

## Changes

| # | File | Change | Type |
|---|------|--------|------|
| 1 | `src/llm/strands_worker.py` | Pass `max_messages=20` to `SlidingWindowConversationManager()` — gives room for 10 historical turns + tool-call chain without dropping context | Config |
| 2 | `src/ui/pet_window.py` | `_build_context_snapshot()`: drop `apm`, `idle_seconds`, `screen_text` by default. Add them only when they cross significant thresholds (APM bucket change, >30s idle delta, window switch) | Logic |
| 3 | `src/ui/pet_window.py` | `_build_context_snapshot()`: keep `active_window` + `typing_content` always — these are the primary behavioral signals | Logic |
| 4 | `src/llm/strands_worker.py` | Strip `screen_text` from context dict entirely in autonomous mode — the thought pool doesn't need screen-level detail for background quips | Logic |
| 5 | `src/ui/pet_window.py` | Trim `formatted_history` fed to `StrandsAutonomousWorker` from 10 to 3 turns for autonomous mode — background thoughts don't need the full conversation log | Logic |
| 6 | `src/llm/strands_worker.py` | Not needed: `self.agent.messages = messages` already resets history on every invocation. No accumulation to fix. | N/A |

## Implementation Steps

### Step 1: Bump SlidingWindowConversationManager max_messages

**File:** `src/llm/strands_worker.py`, line 218

```python
# Before:
conversation_manager=SlidingWindowConversationManager()

# After:
conversation_manager=SlidingWindowConversationManager(max_messages=20)
```

**Why 20?** 10 historical turns + ~6-8 tool-call/result pairs + 1 system state + 1 response = ~18-20 messages. Prevents sliding window from dropping historical context during tool-heavy invocations.

### Step 2: Strip context snapshot to essentials

**File:** `src/ui/pet_window.py`, method `_build_context_snapshot()`

```python
def _build_context_snapshot(self) -> dict:
    context = get_active_window_title() or "unknown"
    typing = self._typing_buffer.get_context() if self._typing_buffer else ""
    apm = self._apm_worker.apm if self._apm_worker else 0
    idle_seconds = getattr(self, "_idle_seconds", 0.0)
    
    # Council recommendation: strip to active fields only.
    # APM and idle_seconds change every frame — sending them
    # wastes context window on noise.
    snapshot = {
        "active_window": context,
        "typing_content": typing,
    }
    
    # Only include APM when it crosses a behavioral threshold
    if apm > 80 or apm == 0:
        snapshot["apm"] = apm
    
    # Only include idle when it's notable
    if idle_seconds > 30:
        snapshot["idle_seconds"] = idle_seconds
    
    return snapshot
```

**Savings:** ~700 chars full → ~50-200 chars typical (70-90% reduction). No delta complexity — simple conditionals on the output.

### Step 3: Trim history for autonomous mode

**File:** `src/ui/pet_window.py`, in `_on_autonomous_trigger_fired()`

```python
# Before:
recent_chat_raw = self._history.get_recent(10)

# After:
recent_chat_raw = self._history.get_recent(10)
# Autonomous triggers only need minimal context for background thoughts
recent_chat_raw = recent_chat_raw[-3:]
```

### Step 4: Verify with tests

```bash
py -m pytest tests/test_bubble_behavior.py tests/test_pet_window_unit.py tests/test_opencode_worker.py -v
```

## Expected Outcome

| Metric | Before | After |
|--------|--------|-------|
| Context snapshot size (avg) | ~700 chars | ~100-200 chars |
| History turns sent (auto) | 10 | 3 |
| Sliding window capacity | 10 messages | 20 messages |
| Tool-call chain safety | History drops during tools | Safe up to ~10 tool rounds |
| LLM input per call (auto) | ~3000 chars | ~1000 chars |
| Behavioral awareness | Full noise (APM every tick) | Signal only (threshold crossing) |

## What This Doesn't Do

- **Doesn't change user-initiated query path** — user queries still get full context
- **Doesn't add delta encoding** — council said no; APM/idle change every tick, net savings vs complexity not worthwhile
- **Doesn't touch the opencode serve path** — Strands only; opencode via ContextManager has its own caching

## Rollback

| Change | Rollback |
|--------|----------|
| `max_messages=20` | Revert to `SlidingWindowConversationManager()` |
| Context stripping | Revert `_build_context_snapshot()` to full 5 fields |
| History trimming | Remove `recent_chat_raw[-3:]` line |
