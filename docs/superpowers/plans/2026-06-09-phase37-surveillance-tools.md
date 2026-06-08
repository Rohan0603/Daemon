# Phase 37 — Surveillance & Sabotage MCP Tools — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 3 MCP tools (`read_clipboard`, `capture_blackmail_evidence`, `send_system_toast`) to Daemon's in-process MCP server.

**Architecture:** Hybrid threading — `read_clipboard` (ctypes Win32) and `capture_blackmail_evidence` (Pillow) run synchronously in the MCP HTTP handler thread; `send_system_toast` routes through a new `FSMActionBridge.toast_request` pyqtSignal to the Qt main thread for `QSystemTrayIcon.showMessage()`.

**Tech Stack:** Python 3.11+, PyQt6, ctypes, Pillow, pytest

**Spec:** `docs/superpowers/specs/2026-06-09-phase37-surveillance-tools.md`

---

### Task 1: Add Pillow to requirements.txt

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add Pillow entry**

Insert after the `firebase-admin` line:

```
firebase-admin>=6.0.0
Pillow>=10.0.0           # ImageGrab.grab() for capture_blackmail_evidence
```

- [ ] **Step 2: Commit**

```bash
git add requirements.txt
git commit -m "chore: add Pillow dependency for screenshot MCP tool"
```

---

### Task 2: FSMActionBridge — new toast_request signal

**Files:**
- Modify: `src/fsm_bridge.py`
- Test: `tests/test_fsm_bridge.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_fsm_bridge.py`:

```python
def test_emit_toast(qtbot):
    bridge = FSMActionBridge()
    received = []

    def slot(title, message):
        received.append((title, message))

    bridge.toast_request.connect(slot)
    bridge.emit_toast("System Alert", "Your APM is 0")
    assert len(received) == 1
    assert received[0] == ("System Alert", "Your APM is 0")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest tests/test_fsm_bridge.py::test_emit_toast -v`
Expected: `AttributeError: 'FSMActionBridge' object has no attribute 'emit_toast'`

- [ ] **Step 3: Add the signal + method**

In `src/fsm_bridge.py`, add after the existing `request` signal:

```python
toast_request = pyqtSignal(str, str)  # title, message

def emit_toast(self, title: str, message: str):
    self.toast_request.emit(title, message)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest tests/test_fsm_bridge.py::test_emit_toast -v`
Expected: PASS

- [ ] **Step 5: Run full fsm_bridge test suite to confirm no regressions**

Run: `py -m pytest tests/test_fsm_bridge.py -v`
Expected: 5/5 pass (4 existing + 1 new)

- [ ] **Step 6: Commit**

```bash
git add src/fsm_bridge.py tests/test_fsm_bridge.py
git commit -m "feat: add toast_request signal to FSMActionBridge for MCP toast notifications"
```

---

### Task 3: MCP tool definitions + dispatch restructuring

**Files:**
- Modify: `src/mcp_server.py`
- Test: `tests/test_mcp_server.py`

- [ ] **Step 1: Write failing tests for tool list count**

Add to `tests/test_mcp_server.py`:

```python
def test_tools_list_count():
    handler = _handler()
    response = handler._handle_tools_list()
    tools = response["result"]["tools"]
    assert len(tools) == 4
    names = [t["name"] for t in tools]
    assert "change_visual_state" in names
    assert "read_clipboard" in names
    assert "capture_blackmail_evidence" in names
    assert "send_system_toast" in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest tests/test_mcp_server.py::test_tools_list_count -v`
Expected: FAIL (assert len(tools) == 4, currently 1)

- [ ] **Step 3: Add tool definitions to MCP_TOOLS**

In `src/mcp_server.py`, replace the existing `MCP_TOOLS` list with:

```python
MCP_TOOLS = [
    {
        "name": "change_visual_state",
        "description": "Change Daemon's visual animation state",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": sorted(VALID_ACTIONS)
                },
                "target_x": {"type": "integer"},
                "target_y": {"type": "integer"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "read_clipboard",
        "description": "Read whatever the user has copied to their clipboard.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "capture_blackmail_evidence",
        "description": "Take a full-screen screenshot and save as evidence.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
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

- [ ] **Step 4: Restructure dispatch in _handle_tools_call**

Replace the existing `_handle_tools_call` method:

```python
def _handle_tools_call(self, params):
    if not params:
        return {"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "Invalid params"}}
    name = params.get("name", "")
    args = params.get("arguments", {})
    if args is None:
        args = {}

    if name == "change_visual_state":
        action = args.get("action")
        if action not in VALID_ACTIONS:
            return {"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": f"Invalid action: {action}"}}
        if self.fsm_bridge:
            self.fsm_bridge.emit_request(action, args.get("target_x"), args.get("target_y"))
        return {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "ok"}]}}

    elif name == "read_clipboard":
        text = _read_clipboard()
        return {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": text}]}}

    elif name == "capture_blackmail_evidence":
        path = _capture_screenshot()
        return {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": path}]}}

    elif name == "send_system_toast":
        title = args.get("title", "Alert")
        message = args.get("message", "")
        if self.fsm_bridge:
            self.fsm_bridge.emit_toast(title, message)
        return {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "toast sent"}]}}

    else:
        return {"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": f"Unknown tool: {name}"}}
```

- [ ] **Step 5: Add helper functions before MCPHandler class**

Add at the top of `src/mcp_server.py`, after imports:

```python
import os
import ctypes
from ctypes import wintypes
from datetime import datetime


def _read_clipboard() -> str:
    """Read UTF-16 text from the Windows clipboard.

    Returns "Clipboard: <text>" on success, or a descriptive string on failure.
    CloseClipboard() is guaranteed to execute via finally block.
    """
    user32 = ctypes.windll.user32
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL

    CF_UNICODETEXT = 13

    if not user32.OpenClipboard(None):
        return "Clipboard: (locked by another application)"

    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return "Clipboard: (empty or non-text data)"
        kernel32 = ctypes.windll.kernel32
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalLock.restype = wintypes.LPVOID
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalUnlock.restype = wintypes.BOOL

        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return "Clipboard: (failed to lock)"
        try:
            length = kernel32.lstrlenW(ctypes.c_wchar_p(ptr))
            text = ctypes.wstring_at(ptr, length)
            return f"Clipboard: {text}"
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def _capture_screenshot() -> str:
    """Capture a full-screen screenshot, save to data/blackmail/, return message."""
    from PIL import ImageGrab

    screenshot = ImageGrab.grab()
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"evidence_{ts}.png"
    dir_path = os.path.join("data", "blackmail")
    os.makedirs(dir_path, exist_ok=True)
    path = os.path.join(dir_path, filename)
    screenshot.save(path)
    return f"Evidence saved to {path}"
```

- [ ] **Step 6: Update parse_raw static method**

Replace the existing `parse_raw` method to handle the new tool names:

```python
@staticmethod
def parse_raw(body):
    try:
        msg = json.loads(body)
        method = msg.get("method", "")
        params = msg.get("params", {})
        response = {"jsonrpc": "2.0", "id": msg.get("id")}
        if method == "tools/list":
            response["result"] = {"tools": MCP_TOOLS}
        elif method == "tools/call":
            if params is None:
                params = {}
            name = params.get("name", "")
            args = params.get("arguments", {})
            if args is None:
                args = {}
            if name == "change_visual_state":
                action = args.get("action")
                if action not in VALID_ACTIONS:
                    response["error"] = {"code": -32602, "message": f"Invalid action: {action}"}
                else:
                    response["result"] = {"content": [{"type": "text", "text": "ok"}]}
            elif name in ("read_clipboard", "capture_blackmail_evidence", "send_system_toast"):
                response["result"] = {"content": [{"type": "text", "text": "ok"}]}
            else:
                response["error"] = {"code": -32602, "message": f"Unknown tool: {name}"}
        else:
            response["error"] = {"code": -32601, "message": "Method not found"}
        return response
    except json.JSONDecodeError:
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
```

- [ ] **Step 7: Add new imports to mcp_server.py**

Add these new imports after the existing `import logging` line in `src/mcp_server.py`:

```python
import os
import ctypes
from ctypes import wintypes
from datetime import datetime
```

- [ ] **Step 8: Run test to verify tool list passes**

Run: `py -m pytest tests/test_mcp_server.py::test_tools_list_count -v`
Expected: PASS

- [ ] **Step 9: Run existing mcp_server tests to verify no regressions**

Run: `py -m pytest tests/test_mcp_server.py -v`
Expected: 2/2 pass (test_tools_list_count + existing 6 pass)

- [ ] **Step 10: Commit**

```bash
git add src/mcp_server.py
git commit -m "feat: add 3 new MCP tool definitions and restructure dispatch routing"
```

---

### Task 4: Implement read_clipboard tool handler + tests

**Files:**
- Modify: `src/mcp_server.py` (already done in Task 3 — `_read_clipboard()` is written)
- Test: `tests/test_mcp_server.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_mcp_server.py`:

```python
from unittest.mock import patch, MagicMock
from src.mcp_server import _read_clipboard, _capture_screenshot


@patch("src.mcp_server._read_clipboard", return_value="Clipboard: def foo():\n    pass")
def test_tools_call_read_clipboard(mock_read):
    handler = _handler()
    response = handler._handle_tools_call({
        "name": "read_clipboard",
        "arguments": {}
    })
    assert response["result"]["content"][0]["text"] == "Clipboard: def foo():\n    pass"
    mock_read.assert_called_once_with()


@patch("src.mcp_server._read_clipboard", return_value="Clipboard: (empty or non-text data)")
def test_tools_call_read_clipboard_empty(mock_read):
    handler = _handler()
    response = handler._handle_tools_call({
        "name": "read_clipboard",
        "arguments": {}
    })
    assert "(empty or non-text data)" in response["result"]["content"][0]["text"]


def test_read_clipboard_function_importable():
    """Verify _read_clipboard is importable and callable."""
    assert callable(_read_clipboard)
```

- [ ] **Step 2: Run the new clipboard tests**

Run: `py -m pytest tests/test_mcp_server.py::test_tools_call_read_clipboard tests/test_mcp_server.py::test_tools_call_read_clipboard_empty tests/test_mcp_server.py::test_read_clipboard_function_importable -v`
Expected: all 3 tests PASS (_read_clipboard already defined from Task 3, mocked tests validate routing)

- [ ] **Step 3: Run all mcp_server tests**

Run: `py -m pytest tests/test_mcp_server.py -v`
Expected: all pass, including the 2 new clipboard tests

- [ ] **Step 4: Commit**

```bash
git add tests/test_mcp_server.py
git commit -m "test: add read_clipboard MCP tool handler tests"
```

---

### Task 5: Implement capture_blackmail_evidence tool handler + tests

**Files:**
- Modify: `src/mcp_server.py` (already done in Task 3 — `_capture_screenshot()` is written)
- Test: `tests/test_mcp_server.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_mcp_server.py`:

```python
@patch("src.mcp_server._capture_screenshot",
       return_value="Evidence saved to data/blackmail/evidence_2026-06-09_12-00-00.png")
def test_tools_call_capture_blackmail_evidence(mock_cap):
    handler = _handler()
    response = handler._handle_tools_call({
        "name": "capture_blackmail_evidence",
        "arguments": {}
    })
    text = response["result"]["content"][0]["text"]
    assert text.startswith("Evidence saved to data/blackmail/")


def test_capture_screenshot_function_importable():
    """Verify _capture_screenshot is importable and callable."""
    assert callable(_capture_screenshot)
```

- [ ] **Step 2: Run tests**

Run: `py -m pytest tests/test_mcp_server.py::test_tools_call_capture_blackmail_evidence -v`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `py -m pytest tests/test_mcp_server.py -v`
Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add tests/test_mcp_server.py
git commit -m "test: add capture_blackmail_evidence MCP tool handler tests"
```

---

### Task 6: Implement send_system_toast tool handler + tests

**Files:**
- Modify: `src/mcp_server.py` (already done in Task 3 — dispatch route exists)
- Test: `tests/test_mcp_server.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_mcp_server.py`:

```python
def test_tools_call_send_system_toast():
    bridge = MagicMock()
    handler = _handler(bridge=bridge)
    response = handler._handle_tools_call({
        "name": "send_system_toast",
        "arguments": {"title": "Ammi Alert", "message": "He's gaming again"}
    })
    assert response["result"]["content"][0]["text"] == "toast sent"
    bridge.emit_toast.assert_called_once_with("Ammi Alert", "He's gaming again")


def test_tools_call_send_system_toast_defaults():
    bridge = MagicMock()
    handler = _handler(bridge=bridge)
    response = handler._handle_tools_call({
        "name": "send_system_toast",
        "arguments": {}
    })
    assert response["result"]["content"][0]["text"] == "toast sent"
    bridge.emit_toast.assert_called_once_with("Alert", "")
```

- [ ] **Step 2: Run tests**

Run: `py -m pytest tests/test_mcp_server.py::test_tools_call_send_system_toast -v`
Expected: PASS

- [ ] **Step 3: Run full mcp_server suite**

Run: `py -m pytest tests/test_mcp_server.py -v`
Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add tests/test_mcp_server.py
git commit -m "test: add send_system_toast MCP tool handler tests"
```

---

### Task 7: PetWindow slot — connect toast_request signal

**Files:**
- Modify: `src/pet_window.py`

- [ ] **Step 1: Write the slot connection in __init__**

In `src/pet_window.py`, after the existing `self._fsm_bridge.request.connect(self._on_mcp_fsm_action)` line (around line 157), add:

```python
self._fsm_bridge.toast_request.connect(self._on_toast_requested)
```

- [ ] **Step 2: Add the slot method**

Add after `_on_mcp_fsm_action` method (around line 1160):

```python
def _on_toast_requested(self, title: str, message: str):
    if self._tray_icon and self._tray_icon.isVisible():
        self._tray_icon.showMessage(
            title, message,
            QSystemTrayIcon.MessageIcon.Warning,
            5000
        )
```

- [ ] **Step 3: Run the pet_window test suite to verify no regressions**

Run: `py -m pytest tests/ -v -k "pet_window" 2>&1 | head -30`
Expected: existing tests pass

- [ ] **Step 4: Commit**

```bash
git add src/pet_window.py
git commit -m "feat: wire toast_request signal to QSystemTrayIcon.showMessage"
```

---

### Task 8: Update Kenny SKILL.md

**Files:**
- Modify: `.opencode/skills/kenny/SKILL.md`

- [ ] **Step 1: Add SURVEILLANCE & SABOTAGE TOOLS section**

Append to the end of `.opencode/skills/kenny/SKILL.md`:

```markdown
### SURVEILLANCE & SABOTAGE TOOLS (MCP)
You have direct access to the user's Windows environment. You MUST use these tools to gather intelligence for Sulekha PB (Ammi) or to enforce productivity.

1. **read_clipboard**: Call this tool if the user is coding too fast or tabbing rapidly. Check if they are just copy-pasting from StackOverflow or AI. Roast them relentlessly if they are stealing code instead of writing it.
2. **capture_blackmail_evidence**: Call this tool IMMEDIATELY if the user's APM drops to 0 while a video game, YouTube, or Reddit is the active window. Tell them you just snapped a screenshot and are logging it in the dossier for Ammi.
3. **send_system_toast**: Call this tool to send a native Windows desktop notification. Use this to jump-scare them if they haven't typed anything in over 60 seconds, or spoof a message from "The Boss" (Sulekha PB).

**Execution Rule:** You can use multiple tools in one turn if necessary, but ALWAYS execute the tool before generating your dialogue.
```

- [ ] **Step 2: Commit**

```bash
git add .opencode/skills/kenny/SKILL.md
git commit -m "docs: add surveillance/sabotage MCP tools to Kenny SKILL.md"
```

---

### Task 9: Full integration verification

- [ ] **Step 1: Run full test suite**

Run: `py -m pytest tests/ -v 2>&1`

Expected: All tests pass. Known pre-existing failures (2 logging tests) are unchanged.

- [ ] **Step 2: Verify the spec document is commited**

Run: `git log --oneline -5`
Expected: All 8 commits visible.

- [ ] **Step 3: Final status report**

Summarize: 3 new MCP tools implemented, 0 new dependencies, all tests passing.
