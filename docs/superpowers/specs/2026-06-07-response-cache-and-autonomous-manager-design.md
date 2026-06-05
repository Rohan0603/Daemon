# AutonomousResponseManager + Multi-Pool Design

**Date:** 2026-06-07
**Branch:** task-response-cache-autonomous-manager

---

## Goal

Replace the existing autonomous response system (TriggerCoalescer + DialogCache + hardcoded quips) with an **AutonomousResponseManager** that maintains separate priority-ranked pools of pre-fetched LLM responses for different trigger types. Eliminate all hardcoded text. Inject richer context into every prompt for more relatable responses.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            PetWindow                                     │
│                                                                         │
│  ┌──────────────┐ draw("system",1)  ┌─────────────────────────────┐     │
│  │ active_chat  │──────────────────▶│   AutonomousResponseManager  │     │
│  │ timer        │                   │                              │     │
│  ├──────────────┤ draw("joke",1)    │  ┌────────────────────────┐  │     │
│  │ boredom      │──────────────────▶│  │ JokePool (size 30)     │  │     │
│  │ timer        │                   │  │ threshold: 25          │  │     │
│  ├──────────────┤                   │  │ refill: 8 items        │  │     │
│  │ idle tick    │                   │  └────────────────────────┘  │     │
│  └──────────────┘                   │  ┌────────────────────────┐  │     │
│                                     │  │ SystemPool (size 10)   │  │     │
│  ┌──────────────┐                   │  │ threshold: 5           │  │     │
│  │ User Input   │───────────────────│  │ refill: 6 items        │  │     │
│  │ (double-click│ prime_from_user   │  └────────────────────────┘  │     │
│  │  → API)      │ _response(2+2)    │                              │     │
│  └──────────────┘                   │  Priority decay: -1/2min    │     │
│                                     └─────────────────────────────┘     │
│                                                   │                    │
│                                                   ▼                    │
│                                     ┌──────────────────────┐           │
│                                     │   ContextBuilder      │           │
│                                     │   (6 new context      │           │
│                                     │    fields + last 10   │           │
│                                     │    history)           │           │
│                                     └──────────────────────┘           │
│                                                   │                    │
│                                                   ▼                    │
│                                     ┌──────────────────────┐           │
│                                     │   OpencodeWorker     │           │
│                                     │   (API or CLI)      │           │
│                                     └──────────────────────┘           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Files Changed

| File | Action |
|------|--------|
| `src/response_manager.py` | **CREATE** — `AutonomousResponseManager` with two `ResponsePool` instances |
| `src/trigger_coalescer.py` | **DELETE** |
| `src/pet_window.py` | Modify — remove old wiring, add TRM with pool-specific draws |
| `src/context_builder.py` | Modify — add 6 context fields, always include last 10 history (DONE) |
| `src/constants.py` | Modify — remove hardcoded text, add per-pool constants |
| `src/opencode_worker.py` | Modify — add `pool_items_ready` signal, tagged pool_items |
| `assets/daemon-skill.md` | Modify — dual-batch format (8 for jokes, 6 for system) |
| `tests/test_response_manager.py` | **CREATE** |
| `tests/test_pet_window.py` | Modify |
| `tests/test_context_builder.py` | Modify — 6 new context tests (DONE) |
| `tests/test_opencode_worker.py` | Modify — pool_items extraction tests |
| `tests/test_trigger_coalescer.py` | **DELETE** |

---

## Component: AutonomousResponseManager

### Location

New file `src/response_manager.py`.

### Internal Architecture

```
AutonomousResponseManager
├── ResponsePool "jokes_blackmail" (size 30, threshold 25, refill 8)
│   ├── items: list[dict]
│   ├── draw() → weighted selection
│   └── refill() → emit signal
├── ResponsePool "system" (size 10, threshold 5, refill 6)
│   ├── items: list[dict]
│   ├── draw() → weighted selection
│   └── refill() → emit signal
├── Priority decay timer (every 2 min → decrement all items)
└── Persistence: ~/.daemon_response_cache.json
```

### Interface

```python
class ResponsePool(QObject):
    """A single pool with its own config, items, and refill logic."""
    refill_needed = pyqtSignal(str)  # pool_type
    pool_refilled = pyqtSignal()
    refill_failed = pyqtSignal(str)

    def __init__(self, pool_type: str, max_size: int, threshold: int,
                 refill_count: int, parent=None):
        ...

    def draw(self, count: int = 1) -> list[dict]:
        """Weighted random selection using current priority (after decay)."""

    def add_items(self, items: list[dict]):
        """Add items, cap at max_size."""

    def remaining(self) -> int:
        return len(self._items)

    def decay(self):
        """Decrement all priorities by 1 (min 1)."""

    def load(self, items: list[dict])
    def save_items(self) -> list[dict]


class AutonomousResponseManager(QObject):
    def __init__(self, cache_path: str, write_coalescer, parent=None):
        self._pools = {
            "jokes_blackmail": ResponsePool("jokes_blackmail", 30, 25, 8),
            "system": ResponsePool("system", 10, 5, 6),
        }
        self._decay_timer = QTimer(interval=120_000)  # 2 min

    def draw(self, pool_type: str, count: int = 1) -> list[dict]:
        """Draw from a specific pool."""

    def add_items(self, pool_type: str, items: list[dict]):
        """Add items to a specific pool."""

    def prime_from_user_response(self, joke_items: list[dict], system_items: list[dict]):
        """Add 2 items to jokes pool + 2 items to system pool."""

    def remaining(self, pool_type: str) -> int:
        """Return remaining count for a pool."""

    def start(self): ...
    def stop(self): ...
```

### Priority decay

- Every 2 minutes, all items across all pools get `priority -= 1` (minimum 1)
- Priority starts at LLM-assigned value (1-5)
- Decay ensures fresh items are preferred over stale ones
- On refill, old items (decayed to 1-2) are naturally replaced because fresh items arrive with priority 3-5
- Selection weight = current priority value only (no category multiplier needed with separate pools)

### Item format

```python
{
    "dialogue": "Holy shit, another compile error?",
    "action": "idle",
    "target_x": null,
    "priority": 4,       # LLM-provided 1-5, decays over time
    "pool_type": "jokes_blackmail"  # which pool this belongs to
}
```

### Pools

| Pool | Max Size | Refresh Threshold | Refill Count | Drawn By |
|------|----------|-----------------|-------------|----------|
| `jokes_blackmail` | 30 | 25 | 8 | boredom timer, idle ticks |
| `system` | 10 | 5 | 6 | active_chat timer, system-aware ticks |

### Persistence

File: `~/.daemon_response_cache.json`

```json
{
    "version": 2,
    "pools": {
        "jokes_blackmail": {
            "items": [
                {"dialogue": "...", "action": "idle", "priority": 3, "pool_type": "jokes_blackmail"}
            ],
            "last_refill": "2026-06-07T15:30:00"
        },
        "system": {
            "items": [...],
            "last_refill": "2026-06-07T15:32:00"
        }
    }
}
```

---

## Component: Constants Changes

### Removed

Same as before: `IDLE_QUIPS`, `IDLE_QUIP_INTERVAL_SEC`, `MEMORY_GAP_QUESTIONS`, `MEMORY_CURIOSITY_INTERVAL_SEC`, `DIALOG_CACHE_SIZE`, `TRIGGER_COALESCE_WINDOW_SEC`.

### Added — Per-pool configuration

```python
JOKES_BLACKMAIL_POOL_SIZE = 30
JOKES_BLACKMAIL_POOL_THRESHOLD = 25  # refresh when >25 items consumed
JOKES_BLACKMAIL_POOL_REFILL_COUNT = 8

SYSTEM_POOL_SIZE = 10
SYSTEM_POOL_THRESHOLD = 5
SYSTEM_POOL_REFILL_COUNT = 6

POOL_DECAY_INTERVAL_SEC = 120  # priority -1 every 2 min
POOL_REFILL_PERIODIC_SEC = 600  # periodic refill every 10 min
```

---

## Component: OpencodeWorker Changes

### User-input response → feeds both pools

When the user submits input, the LLM response includes:

```json
{
    "thought": "He asked about my day...",
    "dialogue": "Honestly? Same debug loop.",     ← shown in bubble immediately
    "action": "idle",
    "target_x": null,
    "priority": 4,
    "jokes_blackmail_items": [
        {"dialogue": "Stopipy strikes again.", "action": "idle", "priority": 4},
        {"dialogue": "Your code is on fire, bro.", "action": "shake", "priority": 3}
    ],
    "system_items": [
        {"dialogue": "He's been coding for 3 hours straight.", "action": "idle", "priority": 5},
        {"dialogue": "Visual Studio Code. Again. Shocking.", "action": "look_away", "priority": 3}
    ]
}
```

- `jokes_blackmail_items`: 2 items added to the jokes pool
- `system_items`: 2 items added to the system pool
- All 4 generated with the same context as the user query

### Refill prompts

For jokes pool refill: `return exactly 8 items with priority`
For system pool refill: `return exactly 6 items with priority`

The `daemon-skill.md` output contract specifies both formats.

### Signals

```python
pool_items_ready = pyqtSignal(dict)  # {"jokes_blackmail": [...], "system": [...]}
```

---

## Component: Web Search via TinyFish MCP

Web search is handled entirely by the opencode server via TinyFish MCP. No custom code needed in Daemon.

### Configuration

The user's opencode configuration (`~/.config/opencode/opencode.json`) must include the TinyFish MCP server:

```json
{
  "mcpServers": {
    "tinyfish": {
      "command": "npx",
      "args": ["@tinyfish-ai/mcp-server"],
      "env": {
        "TINYFISH_API_KEY": "user-api-key-here"
      }
    }
  }
}
```

### How it works

1. User asks a question that needs web data
2. Prompt is sent to opencode server as before
3. opencode server's model detects it needs web info
4. Model calls `web_search` / `web_fetch` MCP tools from TinyFish
5. Response includes the fetched data inline
6. Daemon receives the final response — no extra code needed

### No changes to OpencodeWorker

The existing single-pass API call handles everything. The opencode server manages the tool-calling loop internally. This means the `web_search` field in the JSON response is not used by Daemon — it's handled by the opencode server's MCP infrastructure.

---

## Component: PetWindow Changes

### Removed from `__init__`

- `self._trigger_coalescer`
- `self._dialog_cache`
- `self._curiosity_timer`
- `self._pending_question_field`

### Added to `__init__`

```python
self._response_manager = AutonomousResponseManager(
    cache_path=str(Path.home() / ".daemon_response_cache.json"),
    write_coalescer=self._write_coalescer,
    parent=self,
)
self._response_manager._pools["jokes_blackmail"].refill_needed.connect(self._on_refill_needed)
self._response_manager._pools["system"].refill_needed.connect(self._on_refill_needed)
```

### Timer tick handlers

**`_on_active_chat_tick`** → `self._response_manager.draw("system", 1)`

**`_on_joke_tick`** → `self._response_manager.draw("jokes_blackmail", 1)`

**`_trigger_boredom_query`** → `self._response_manager.draw("jokes_blackmail", 1)`

### `_on_structured_result` change

When user-input response returns with pool items:

```python
def _on_structured_result(self, dialogue, action, target_x):
    # ... existing bubble + dispatch ...
    if hasattr(self.sender(), "pool_items"):
        items = self.sender().pool_items
        joke_items = items.get("jokes_blackmail_items", [])
        system_items = items.get("system_items", [])
        self._response_manager.prime_from_user_response(joke_items, system_items)
```

### `_should_fire_autonomous` change

```python
def _should_fire_autonomous(self, mode: str) -> bool:
    if self._autonomous_query_pending:
        return False
    pool_type = "system" if mode == "active_chat" else "jokes_blackmail"
    if self._response_manager.remaining(pool_type) == 0:
        return False
    return True
```

### `_force_quit_app` change

Add `self._response_manager.stop()`, remove `self._trigger_coalescer.cancel()`.

---

## Component: `assets/daemon-skill.md` Changes

### Priority field

```yaml
priority:
  type: integer
  range: 1-5
  description: >
    Quality/urgency rank. Higher priority items are more likely to be shown.
    Priority decays by 1 every 2 minutes, so fresh items float to the top.
```

### Dual format spec

- For autonomous refills: array of 8 for jokes, array of 6 for system
- For user queries: single object + `jokes_blackmail_items` (2 items) + `system_items` (2 items)

---

## Test Plan

### `tests/test_response_manager.py`

| Test | What it verifies |
|------|-----------------|
| Pool construction | Two pools created with correct configs |
| `draw("jokes_blackmail")` returns from correct pool | |
| `draw("system")` returns from correct pool | |
| Priority decay over time | After 2 min, priority decreases by 1 |
| Priority decay minimum 1 | Never drops below 1 |
| Refill trigger at threshold | Pool below threshold triggers refill |
| Separate pool thresholds | Jokes pool (25) and system pool (5) trigger independently |
| User response feeds both pools | `prime_from_user_response` adds to both |
| Pool cap enforced | Jokes pool capped at 30, system at 10 |
| Persistence saves both pools | Both pools saved to same cache file |
| Corrupt file handling | Bad JSON → empty pools |
| Stop saves + stops timer | |

### Modified tests for context, opencode_worker, pet_window — same structure as original plan

---

## Self-Review Checklist

1. **Spec coverage:** All requirements mapped. Two pools with separate configs. Priority decay. User query feeds both pools. Context fields done.

2. **No placeholders:** All signatures, formats, and constants specified.

3. **Type consistency:** `draw(pool_type, count)` returns `list[dict]`. Pool items use `pool_type` tag. `prime_from_user_response` takes two lists.

4. **Backward compat:** User input without pool items works unchanged. Missing pool cache file → empty pools.
