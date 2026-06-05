# TypingBuffer — Full Keystroke Content Capture

## Summary

Capture everything the user types (across all applications) into a ring buffer and include it in the LLM prompt context so the daemon can react to what they're writing.

## Design Overview

New `TypingBuffer` module vs. extending `APMWorker`. Keystroke content (rate + content) are separate concerns — `APMWorker` measures, `TypingBuffer` captures.

- Full capture, no exclusions
- Used both as passive context (in every prompt) and for active reactions (daemon comments on typing)
- Ring buffer: last 500 chars
- No persistence (disk, cache)
- Opt-in by presence of the module, no toggle needed

## Component: TypingBuffer

**File:** `src/typing_buffer.py`

QObject (not QThread — pynput runs its own daemon thread). API:

```python
class TypingBuffer(QObject):
    text_updated = pyqtSignal()        # emitted when buffer changes

    def __init__(self, parent=None):
        # creates pynput.keyboard.Listener(on_press=_on_press)

    def get_context(self, max_chars: int = 300) -> str:
        # returns formatted "Recent Typing:\n  > <text>"
        # or "" if buffer is empty
```

### Character Handling

| Input | Action |
|-------|--------|
| Printable char (`a`, `1`, `!`) | Append to buffer |
| Backspace | Pop last char from buffer |
| Enter | Append `\n` |
| Tab | Append `  ` (2 spaces) |
| Ctrl+letter | Ignored entirely |
| Alt, Shift, Ctrl alone | Ignored |
| Arrow keys, Esc, Home/End, etc. | Ignored |
| Caps Lock, Num Lock | Ignored |
| Function keys (F1-F12) | Ignored |

### Buffer Management

- `collections.deque(maxlen=500)` — thread-safe for appends, oldest dropped at cap
- No locking needed for the reader (QObject + pynput thread safety via deque)
- Cleared on shutdown implicitly (deque goes out of scope)

### Signal Debounce

- `text_updated` emitted, but connected to a `QTimer.singleShot(2000, ...)` debounce in PetWindow
- Only triggers active reaction if ≥30 new chars accumulated since last emission

## Integration

### ContextBuilder

`build_prompt()` gains optional param `typing_content: str = ""`. When non-empty, last 300 chars (preserving newlines) are appended to the context block:

```
Recent Typing:
  > def hello():
  >     print("world")
  >
```

Wrapped in indented blockquote format, inserted after active window title line.

### PetWindow

```python
# in __init__
self._typing_buffer = TypingBuffer(self)
self._typing_buffer.text_updated.connect(self._on_typing_updated)

# in _on_typing_updated
# count new chars, if >= 30 → self._trigger_autonomous_query()

# in every build_prompt() call
typing_text = self._typing_buffer.get_context()
```

Every prompt call — autonomous, refill, user query — includes typing context.

### Active Reactions

- PetWindow debounces `text_updated` at 2s intervals
- If ≥30 new chars typed since last check: set `AUTONOMOUS_THINKING` state, trigger query with modes `["active_chat"]`
- The daemon can then say something about what you're typing ("Nice try/catch", "'fuxk' again?", etc.)
- Uses the existing worker/autonomous flow, no new query machinery needed

## Edge Cases

- **Empty buffer** → `get_context()` returns empty string, ContextBuilder omits typing section
- **Rapid typing** → debounce prevents every keystroke from triggering a reaction; 2s window + 30 char threshold
- **Special keys only** → buffer stays empty, no trigger
- **Backspace spam** → buffer shrinks, no harm
- **Unicode** → pynput captures char directly, no encoding issues
- **Window switch** → capture continues; daemon sees whatever is in focus

## Testing

**File:** `tests/test_typing_buffer.py`

1. `test_prints_appended()` — type "abc", assert buffer contains "abc"
2. `test_backspace_removes_last()` — type "abc", backspace, assert "ab"
3. `test_backspace_on_empty()` — backspace on empty buffer, no error
4. `test_enter_appends_newline()` — type "a\nb", assert "a\nb"
5. `test_tab_appends_spaces()` — type "\t", assert "  "
6. `test_modifier_ignored()` — Ctrl, Alt, Shift alone, assert empty
7. `test_caps_lock_ignored()` — Caps Lock, assert empty
8. `test_buffer_caps_at_500()` — type 510 chars, assert buffer size 500
9. `test_get_context_formatted()` — type "hello", assert "Recent Typing:\n  > hello"
10. `test_get_context_empty()` — empty buffer, returns ""
11. `test_get_context_truncates()` — type 500 chars, get_context(10) returns last 10 typed

## Files Changed

| File | Change |
|------|--------|
| `src/typing_buffer.py` | **New** — TypingBuffer class |
| `tests/test_typing_buffer.py` | **New** — 11 tests |
| `src/context_builder.py` | Add `typing_content` param to `build_prompt()` |
| `src/pet_window.py` | Instantiate TypingBuffer, pass context, wire debounced reaction |
