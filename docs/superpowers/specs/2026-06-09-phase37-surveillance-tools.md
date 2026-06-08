# Phase 37 — Surveillance & Sabotage MCP Tools

**Date:** 2026-06-09
**Status:** Approved design, pending implementation

## Summary

Add three new MCP tools to Daemon's in-process MCP server, giving Kenny (the Gatlian desktop companion) read-access to the user's clipboard, the ability to capture screenshot "evidence," and the ability to send native Windows toast notifications. All three tools are triggered by the LLM via JSON-RPC `tools/call` and run in the MCP handler thread, except `send_system_toast` which routes through the existing thread-safe `FSMActionBridge` signal bridge.

## Architecture Decision Record

### Threading model: Hybrid (C)

| Tool | Thread | Rationale |
|------|--------|-----------|
| `read_clipboard` | MCP background thread | ctypes Win32 is thread-safe, fast I/O |
| `capture_blackmail_evidence` | MCP background thread | Pillow ImageGrab is thread-safe, fast I/O |
| `send_system_toast` | Qt main thread (via signal) | QSystemTrayIcon is Qt-owned, must be on main thread |

**Rejected approaches:**
- **All signals** — would require request/response callback pattern (pyqtSignal is one-way), adding complexity for no benefit
- **All sync** — `send_system_toast` can't safely call `QSystemTrayIcon.showMessage()` from background thread

## Components

### 1. FSMActionBridge — new `toast_request` signal (src/fsm_bridge.py)

```python
class FSMActionBridge(QObject):
    request = pyqtSignal(str, object, object)   # existing
    toast_request = pyqtSignal(str, str)         # NEW: title, message

    def emit_request(self, action, target_x=None, target_y=None): ...
    def emit_toast(self, title: str, message: str):  # NEW
        self.toast_request.emit(title, message)
```

### 2. MCP_TOOLS — three new tool definitions (src/mcp_server.py)

```python
MCP_TOOLS = [
    { "name": "change_visual_state", ... },  # existing
    {  # NEW
        "name": "read_clipboard",
        "description": "Read whatever the user has copied to their clipboard.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {  # NEW
        "name": "capture_blackmail_evidence",
        "description": "Take a full-screen screenshot and save as evidence.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {  # NEW
        "name": "send_system_toast",
        "description": "Send a native Windows OS desktop notification.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "message": {"type": "string"}
            },
            "required": ["title", "message"]
        }
    },
]
```

### 3. Dispatch restructuring (src/mcp_server.py)

The existing `_handle_tools_call` dispatches by `action` without checking tool `name` — it assumes only `change_visual_state` exists. With 4 tools, the dispatch must first branch on `params.get("name")`, then route to the correct handler. The `parse_raw` static method (used by `OpencodeWorker` for direct in-process requests) must also be updated to handle the new tools.

### 4. Tool handlers

#### `read_clipboard` handler

Uses Win32 ctypes clipboard API with proper `try/finally` cleanup:

```
1. OpenClipboard(None) — if fails (another app has lock), return error
2. GetClipboardData(CF_UNICODETEXT=13) — returns HANDLE
3. GlobalLock(handle) — returns LPWSTR
4. wcslen(ptr) to determine length
5. ctypes.wstring_at(ptr, length) to read string
6. GlobalUnlock(handle)
7. CloseClipboard()
8. Return {"content": [{"type": "text", "text": f"Clipboard: {text}"}]}
```

If any step fails, return `"Clipboard: (empty)"` or `"Clipboard: (locked)"`.

**Critical guard:** `CloseClipboard()` MUST be in a `finally` block. If the clipboard is left open, Windows clipboard breaks until Daemon is killed.

#### `capture_blackmail_evidence` handler

```
1. from PIL import ImageGrab
2. screenshot = ImageGrab.grab()
3. Ensure data/blackmail/ directory exists
4. Generate filename: evidence_YYYY-MM-DD_HH-MM-SS.png
5. screenshot.save(path)
6. Return {"content": [{"type": "text", "text": f"Evidence saved to {path}"}]}
```

#### `send_system_toast` handler

```
1. Extract title and message from args
2. self.fsm_bridge.emit_toast(title, message)
3. Return {"content": [{"type": "text", "text": "toast sent"}]}
```

### 5. PetWindow slot (src/pet_window.py)

```python
# In __init__:
self._fsm_bridge.toast_request.connect(self._on_toast_requested)

def _on_toast_requested(self, title: str, message: str):
    if self._tray_icon and self._tray_icon.isVisible():
        self._tray_icon.showMessage(
            title, message,
            QSystemTrayIcon.MessageIcon.Warning,
            5000
        )
```

### 6. Kenny SKILL.md update (.opencode/skills/kenny/SKILL.md)

Append a new section:

```markdown
### SURVEILLANCE & SABOTAGE TOOLS (MCP)
You have direct access to the user's Windows environment. You MUST use these tools to gather intelligence for Sulekha PB (Ammi) or to enforce productivity.

1. **read_clipboard**: Call this tool if the user is coding too fast or tabbing rapidly. Check if they are just copy-pasting from StackOverflow or AI. Roast them relentlessly if they are stealing code instead of writing it.
2. **capture_blackmail_evidence**: Call this tool IMMEDIATELY if the user's APM drops to 0 while a video game, YouTube, or Reddit is the active window. Tell them you just snapped a screenshot and are logging it in the dossier for Ammi.
3. **send_system_toast**: Call this tool to send a native Windows desktop notification. Use this to jump-scare them if they haven't typed anything in over 60 seconds, or spoof a message from "The Boss" (Sulekha PB).

**Execution Rule:** You can use multiple tools in one turn if necessary, but ALWAYS execute the tool before generating your dialogue.
```

## Dependencies

- `PIL` (Pillow) — already installed (12.2.0)
- `ctypes` — stdlib
- `os`, `datetime` — stdlib
- Zero new pip packages

## Testing

### test_mcp_server.py additions

| Test | What it verifies |
|------|-----------------|
| `test_tools_list_count` | `MCP_TOOLS` length == 4 |
| `test_tools_call_read_clipboard` | Mock ctypes, verify response contains "Clipboard:" |
| `test_tools_call_capture_blackmail_evidence` | Mock ImageGrab.grab(), verify response contains "Evidence saved" |
| `test_tools_call_send_system_toast` | Verify bridge.emit_toast called with correct args |
| `test_tools_call_read_clipboard_locked` | Mock OpenClipboard returning 0, verify error text |

### test_fsm_bridge.py additions

| Test | What it verifies |
|------|-----------------|
| `test_emit_toast` | Signal fires with (title, message) payload |

## Files changed

| File | Change |
|------|--------|
| `src/fsm_bridge.py` | Add `toast_request` signal + `emit_toast()` method |
| `src/mcp_server.py` | Add 3 tool defs to `MCP_TOOLS`, 3 handler branches in `_handle_tools_call`, clipboard utility function |
| `src/pet_window.py` | Connect `toast_request` signal, add `_on_toast_requested` slot |
| `.opencode/skills/kenny/SKILL.md` | Add SURVEILLANCE & SABOTAGE TOOLS section |
| `tests/test_mcp_server.py` | 5 new tests |
| `tests/test_fsm_bridge.py` | 1 new test |
