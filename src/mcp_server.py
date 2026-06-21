import json
import logging
import os
import re
import time
import ctypes
from ctypes import wintypes
from datetime import datetime
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from threading import Thread
from pathlib import Path
from functools import lru_cache

from src.utils.security import get_safe_data_path

logger = logging.getLogger(__name__)

_BOOT_TIME = None  # Set when MCPServer.start() is called

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
ALLOWED_READ_EXTENSIONS = {".py", ".md", ".json", ".ps1", ".txt", ".log", ".yaml", ".yml"}
MAX_READ_LINES = 500

# Simple TTL cache for read_file tool (10 second TTL)
_file_cache = {}
_file_cache_ttl = 10  # seconds
_cache_timestamps = {}


def _validate_mcp_path(relative_path: str, root: str = PROJECT_ROOT) -> str:
    abs_root = os.path.normpath(os.path.abspath(root))
    normed = os.path.normpath(os.path.join(abs_root, relative_path))
    if not normed.startswith(abs_root):
        raise ValueError(f"Path traversal blocked: {relative_path}")
    return normed


def _validate_read_extension(file_path: str) -> bool:
    _, ext = os.path.splitext(file_path)
    return ext.lower() in ALLOWED_READ_EXTENSIONS


FSM_ACTIONS = frozenset({
    "idle", "wander", "hyper", "celebrate", "devastated", "fall", "chase"
})
EXPRESSION_ACTIONS = frozenset({
    "float", "jump", "grow", "shrink", "pulse", "glitch", "rainbow",
    "flip", "teleport", "wave", "wobble", "dash", "melt", "inflate",
    "nod", "headshake", "tremble", "strut", "flail", "vanish",
    "shake", "bounce", "spin", "look_away",
})
VALID_ACTIONS = FSM_ACTIONS | EXPRESSION_ACTIONS

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
                "layer": {
                    "type": "string",
                    "enum": ["fsm", "expression"]
                },
                "duration_ms": {
                    "type": "integer"
                },
                "target_x": {"type": "integer"},
                "target_y": {"type": "integer"}
            },
            "required": ["action", "layer"]
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
    {
        "name": "list_directory",
        "description": "List files and directories within the Daemon project root. Returns a structured JSON list with type (file/directory) and size for files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "relative_path": {
                    "type": "string",
                    "description": "Path relative to project root (e.g. 'src/', 'tests/', 'README.md'). Empty string for root."
                }
            },
            "required": ["relative_path"]
        }
    },
    {
        "name": "read_file",
        "description": "Read a source file from the Daemon project. Limited to allowed extensions (.py, .md, .json, .ps1, .txt, .log, .yaml) and max 500 lines.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path relative to project root (e.g. 'src/pet_window.py')"
                },
                "start_line": {"type": "integer", "minimum": 1, "description": "1-indexed start line (optional)"},
                "end_line": {"type": "integer", "minimum": 1, "description": "1-indexed end line (optional)"}
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "search_codebase",
        "description": "Search for a symbol (class, function, variable) across Python files in src/ and tests/. Returns file paths and line numbers with line snippets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "search_term": {
                    "type": "string",
                    "description": "Term to search for (regex supported)"
                }
            },
            "required": ["search_term"]
        }
    },
    {
        "name": "get_memory",
        "description": "Read all memory facts Daemon knows about the user (preferences, habits, profession, etc.).",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_diary",
        "description": "Read recent diary entries. Returns the N most recent entries.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "description": "Number of recent entries (default 10)"}
            }
        }
    },
    {
        "name": "simulate_keystroke",
        "description": "Type a string of characters as if the user typed them. Max 50 chars. Windows key blocked.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keys": {"type": "string", "description": "Text to type"}
            },
            "required": ["keys"]
        }
    },
    {
        "name": "move_mouse",
        "description": "Move the cursor to a screen position. Coordinates clamped to display bounds. Optionally click.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "Screen X coordinate"},
                "y": {"type": "integer", "description": "Screen Y coordinate"},
                "click": {"type": "boolean", "description": "If true, left-click after moving"}
            },
            "required": ["x", "y"]
        }
    },
    {
        "name": "browser_navigation",
        "description": "Open a URL in the default web browser. Only http:// and https:// allowed.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to open (http/https only)"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "set_log_level",
        "description": "Change the root logger level at runtime. Useful for enabling/disabling debug output without restart.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "level": {
                    "type": "string",
                    "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                    "description": "New log level"
                }
            },
            "required": ["level"]
        }
    },
    {
        "name": "get_screen_time",
        "description": "Get today's screen time usage per application (in seconds).",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_recent_git_diff",
        "description": "Get the git diff of the currently staged files or the last commit if working directory is clean.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "set_reminder",
        "description": "Set a reminder that will emit a system toast and pet bubble after a given time.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Reminder message"},
                "time_minutes": {"type": "number", "description": "Time in minutes to wait before reminding"}
            },
            "required": ["message", "time_minutes"]
        }
    },
    {
        "name": "get_reminders",
        "description": "List all currently active reminders.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "dismiss_reminder",
        "description": "Dismiss/cancel an active reminder by ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Reminder ID"}
            },
            "required": ["id"]
        }
    },
]


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


def _capture_blackmail_evidence() -> str:
    """Capture a full-screen screenshot, save to data/blackmail/, return message."""
    from PIL import ImageGrab

    screenshot = ImageGrab.grab()
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"evidence_{ts}.png"
    path = get_safe_data_path(os.path.join("blackmail", filename))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    screenshot.save(path)
    return f"Evidence saved to {path}"


_MAX_KEYSTROKE_LEN = 50
_BLOCKED_KEYS = {"win", "cmd", "super", "win_l", "win_r", "cmd_l", "cmd_r", "super_l", "super_r"}


def _simulate_keystroke(keys: str) -> str:
    """Type *keys* using pynput keyboard controller. Max 50 chars.
    Blocks Windows/super modifier keys. Returns status string."""
    from pynput.keyboard import Controller
    lower = keys.lower()
    for bk in _BLOCKED_KEYS:
        if bk in lower:
            return "Error: Windows key is blocked for safety"
    if len(keys) > _MAX_KEYSTROKE_LEN:
        return f"Error: Payload too large ({len(keys)} chars, max {_MAX_KEYSTROKE_LEN})"
    kb = Controller()
    kb.type(keys)
    return f"Typed {len(keys)} characters"


def _move_mouse(x: int, y: int, click: bool = False) -> str:
    """Move cursor to (x, y) using pynput mouse controller.
    Clamps coordinates to screen bounds. Optionally left-clicks.
    Returns status string."""
    from pynput.mouse import Controller, Button
    import ctypes
    w = ctypes.windll.user32.GetSystemMetrics(0)
    h = ctypes.windll.user32.GetSystemMetrics(1)
    cx = max(0, min(x, w - 1))
    cy = max(0, min(y, h - 1))
    mouse = Controller()
    mouse.position = (cx, cy)
    if click:
        mouse.click(Button.left)
    return f"Moved cursor to ({cx}, {cy})" + (" and clicked" if click else "")


def _browser_navigation(url: str) -> str:
    """Open *url* in default browser. Only http:// and https:// allowed.
    Returns status string."""
    import webbrowser
    lower = url.strip().lower()
    if not (lower.startswith("http://") or lower.startswith("https://")):
        return "Error: Only http:// and https:// URLs are allowed"
    webbrowser.open(url.strip())
    return f"Opened {url.strip()}"


_CONSENT_TOOL_MAP: dict[str, str] = {
    "change_visual_state": "allow_intrusive_animations",
    "read_clipboard": "allow_clipboard_hijacking",
    "capture_blackmail_evidence": "allow_window_management",
    "send_system_toast": "allow_audio_disruptions",
    "simulate_keystroke": "allow_keyboard_injection",
    "move_mouse": "allow_mouse_interference",
    "browser_navigation": "allow_browser_redirection",
}


import threading
_sse_handlers_lock = threading.Lock()

class MCPHandler(BaseHTTPRequestHandler):
    _active_sse_handlers = set()

    def __init__(self, request, client_address, server, fsm_bridge=None, memory=None, diary=None, history=None, config=None, action_layer=None):
        self._fsm_bridge = fsm_bridge or getattr(server, "fsm_bridge", None)
        self._memory = memory or getattr(server, "memory", None)
        self._diary = diary or getattr(server, "diary_store", None)
        self._history = history or getattr(server, "history", None)
        self._config = config or getattr(server, "config", None)
        self._action_layer = action_layer or getattr(server, "action_layer", None)
        super().__init__(request, client_address, server)

    @classmethod
    def broadcast_sse_message(cls, message_dict):
        payload = f"event: message\ndata: {json.dumps(message_dict)}\n\n".encode("utf-8")
        with _sse_handlers_lock:
            handlers = list(cls._active_sse_handlers)
        for handler in handlers:
            try:
                handler.wfile.write(payload)
                handler.wfile.flush()
                logger.debug("Broadcasted SSE message to handler %s", handler)
            except Exception as e:
                logger.debug("Failed to write to SSE stream: %s", e)
                with _sse_handlers_lock:
                    cls._active_sse_handlers.discard(handler)

    @property
    def fsm_bridge(self):
        return getattr(self.server, "fsm_bridge", None)

    @property
    def memory(self):
        return getattr(self.server, "memory", None)

    @property
    def diary_store(self):
        return getattr(self.server, "diary_store", None)

    @property
    def consent(self):
        return getattr(self.server, "consent", None)

    def handle(self):
        try:
            super().handle()
        except ConnectionResetError:
            pass

    def do_GET(self):
        if self.path in ("/sse", "/"):
            self._handle_sse()
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))
        elif self.path == "/metrics":
            self._handle_metrics()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/log":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            
            try:
                msg = json.loads(body)
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON payload")
                return
            
            service = msg.get("service", "unknown")
            level_str = msg.get("level", "INFO").upper()
            message = msg.get("message", "")
            extra = msg.get("extra", {})
            
            # Map level to logging module
            level_map = {
                "DEBUG": logging.DEBUG,
                "INFO": logging.INFO,
                "WARNING": logging.WARNING,
                "ERROR": logging.ERROR
            }
            level = level_map.get(level_str, logging.INFO)
            
            logger.log(level, f"[{service}] {message} - Extra: {extra}")
            
            # Write to thoughts log for visual output if INFO or above
            if level >= logging.INFO:
                from src.constants import THOUGHTS_LOG_PATH
                from pathlib import Path
                try:
                    with open(THOUGHTS_LOG_PATH, "a", encoding="utf-8") as f:
                        f.write(f"[{service}] {message}\n")
                except Exception as e:
                    logger.error("Failed to write to thoughts log: %s", e)
            
            self._send_json({"success": True})
            return

        match = re.match(r"^/session/([^/]+)/summarize$", self.path)
        if match:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            
            try:
                msg = json.loads(body)
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON payload")
                return
            
            provider_id = msg.get("providerID", "")
            model_id = msg.get("modelID", "")
            
            if hasattr(self.server, "fsm_bridge") and self.server.fsm_bridge:
                self.server.fsm_bridge.emit_summarize_requested(provider_id, model_id)
                
            self._send_json({"success": True, "events": []})
            return

        if self.path in ("/message", "/"):
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            msg = json.loads(body)
            method = msg.get("method", "")
            params = msg.get("params", {})
            response = self._handle_request(method, params)
            if response is not None:
                if "id" in msg:
                    response["id"] = msg["id"]
                MCPHandler.broadcast_sse_message(response)
                self._send_json(response)
            else:
                self._send_json({})
        else:
            self.send_error(404)

    def _is_tool_allowed(self, tool_name: str) -> tuple[bool, str]:
        """Check consent for *tool_name*. Returns (allowed, error_message).

        If *consent* is None (no config loaded), all tools are allowed
        for backward compatibility.
        """
        if self.consent is None:
            return True, ""
        consent_key = _CONSENT_TOOL_MAP.get(tool_name)
        if consent_key is None:
            return True, ""
        allowed = self.consent.get(consent_key, False)
        if not allowed:
            msg = f"ERROR: User has denied permission '{consent_key}'. Tool '{tool_name}' blocked."
            logger.warning("MCP Blocked: LLM attempted '%s' but '%s' is False", tool_name, consent_key)
            return False, msg
        return True, ""

    def _handle_sse(self):
        import socket
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        self.wfile.write(f"event: endpoint\ndata: /message\n\n".encode())
        self.wfile.flush()

        with _sse_handlers_lock:
            MCPHandler._active_sse_handlers.add(self)

        # Keep connection alive with periodic keepalive comments
        try:
            while True:
                self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
                import time
                time.sleep(15)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with _sse_handlers_lock:
                MCPHandler._active_sse_handlers.discard(self)

    def _handle_metrics(self):
        """Return Prometheus-format metrics for scraping."""
        try:
            from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
            body = generate_latest()
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except ImportError:
            # Fallback: basic JSON metrics
            import os
            import time
            import threading
            data = {
                "pid": os.getpid(),
                "uptime_seconds": time.monotonic() - _BOOT_TIME,
                "thread_count": threading.active_count(),
                "prometheus": "not_installed",
            }
            # Try psutil for richer metrics if available (optional dependency)
            try:
                import psutil as _psutil
                proc = _psutil.Process()
                mem = proc.memory_info()
                data["memory_rss_bytes"] = mem.rss
                data["memory_vms_bytes"] = mem.vms
                data["cpu_percent"] = proc.cpu_percent(interval=0)
                data["open_handles"] = proc.num_handles()
            except ImportError:
                data["psutil"] = "not_installed"
            self._send_json(data)

    def _send_json(self, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_request(self, method, params):
        logger.debug("MCP received method: %s", method)
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "DaemonMCP", "version": "1.0.0"}
                }
            }
        elif method == "notifications/initialized":
            return None
        elif method == "notifications/cancelled":
            return None
        elif method == "ping":
            return {"jsonrpc": "2.0", "result": {}}
        elif method == "tools/list":
            return self._handle_tools_list()
        elif method == "tools/call":
            return self._handle_tools_call(params)
        else:
            logger.debug("MCP unknown method: %s", method)
            return {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}}

    def _handle_tools_list(self):
        return {"jsonrpc": "2.0", "id": 1, "result": {"tools": MCP_TOOLS}}

    def _handle_change_visual_state(self, params: dict) -> dict:
        action = params.get("action")
        layer = params.get("layer")
        duration_ms = params.get("duration_ms")

        # Validations
        if action not in VALID_ACTIONS:
            return {"error": {"code": -32602, "message": f"Invalid action: {action}"}}

        if layer not in ("fsm", "expression"):
            return {"error": {"code": -32602, "message": f"Invalid layer: {layer}"}}

        if layer == "fsm":
            if action not in FSM_ACTIONS:
                return {"error": {"code": -32602, "message": f"Action '{action}' is not valid for fsm layer"}}
            if self._fsm_bridge:
                self._fsm_bridge.fsm_action_requested.emit(action)

        elif layer == "expression":
            if action not in EXPRESSION_ACTIONS:
                return {"error": {"code": -32602, "message": f"Action '{action}' is not valid for expression layer"}}
            if self._action_layer:
                self._action_layer.trigger(action, duration_ms, {})

        return {"result": {"content": [{"type": "text", "text": "ok"}]}}

    def _handle_tools_call(self, params):
        if not params:
            logger.debug("MCP tools/call: missing params")
            return {"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "Invalid params"}}
        name = params.get("name", "")
        args = params.get("arguments", {})
        if args is None:
            args = {}
        logger.debug("MCP tools/call: %s args=%s", name, json.dumps(args)[:200])
        import time as _time
        _t0 = _time.time()

        def _mcp_result(response):
            elapsed = _time.time() - _t0
            allowed = "error" not in response
            try:
                from src.observability import record_mcp_tool_call
                record_mcp_tool_call(name, elapsed, allowed)
            except Exception:
                pass
            return response

        if name == "change_visual_state":
            allowed, err = self._is_tool_allowed(name)
            if not allowed:
                return _mcp_result({"jsonrpc": "2.0", "id": 1, "error": {"code": -32001, "message": err}})
            res = self._handle_change_visual_state(args)
            if "error" in res:
                return _mcp_result({"jsonrpc": "2.0", "id": 1, "error": res["error"]})
            return _mcp_result({"jsonrpc": "2.0", "id": 1, "result": res.get("result")})

        elif name == "read_clipboard":
            allowed, err = self._is_tool_allowed(name)
            if not allowed:
                return _mcp_result({"jsonrpc": "2.0", "id": 1, "error": {"code": -32001, "message": err}})
            text = _read_clipboard()
            return _mcp_result({"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": text}]}})

        elif name == "capture_blackmail_evidence":
            allowed, err = self._is_tool_allowed(name)
            if not allowed:
                return _mcp_result({"jsonrpc": "2.0", "id": 1, "error": {"code": -32001, "message": err}})
            path = _capture_blackmail_evidence()
            return _mcp_result({"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": path}]}})

        elif name == "send_system_toast":
            allowed, err = self._is_tool_allowed(name)
            if not allowed:
                return _mcp_result({"jsonrpc": "2.0", "id": 1, "error": {"code": -32001, "message": err}})
            title = args.get("title", "Alert")
            message = args.get("message", "")
            if self.fsm_bridge:
                self.fsm_bridge.emit_toast(title, message)
            return _mcp_result({"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "toast sent"}]}})

        elif name == "list_directory":
            return _mcp_result(self._handle_list_directory(args))
        elif name == "read_file":
            return _mcp_result(self._handle_read_file(args))
        elif name == "search_codebase":
            return _mcp_result(self._handle_search_codebase(args))

        elif name == "get_memory":
            if self.memory is None:
                text = "Memory not available (no memory store configured)"
            else:
                facts = self.memory.get_all()
                if not facts:
                    text = "No memory facts stored."
                else:
                    lines = [f"{k}: {v}" for k, v in facts.items()]
                    text = "Memory facts:\n" + "\n".join(lines)
            logger.debug("MCP get_memory -> %d chars", len(text))
            return _mcp_result({"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": text}]}})

        elif name == "get_diary":
            if self.diary_store is None:
                text = "Diary not available (no diary store configured)"
            else:
                entries = self.diary_store.get_entries()
                if not entries:
                    text = "No diary entries."
                else:
                    raw_limit = args.get("limit", 10)
                    limit = max(1, min(int(raw_limit) if raw_limit is not None else 10, 50))
                    recent = entries[-limit:]
                    lines = []
                    for e in recent:
                        ts = e.get("timestamp", "")
                        content = e.get("content", "")
                        lines.append(f"[{ts}] {content}")
                    text = "Recent diary entries:\n" + "\n".join(lines)
            logger.debug("MCP get_diary -> %d chars", len(text))
            return _mcp_result({"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": text}]}})

        elif name == "simulate_keystroke":
            allowed, err = self._is_tool_allowed(name)
            if not allowed:
                return _mcp_result({"jsonrpc": "2.0", "id": 1, "error": {"code": -32001, "message": err}})
            keys = args.get("keys", "")
            result = _simulate_keystroke(keys)
            return _mcp_result({"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": result}]}})

        elif name == "move_mouse":
            allowed, err = self._is_tool_allowed(name)
            if not allowed:
                return _mcp_result({"jsonrpc": "2.0", "id": 1, "error": {"code": -32001, "message": err}})
            x = args.get("x", 0)
            y = args.get("y", 0)
            click = args.get("click", False)
            result = _move_mouse(x, y, click)
            return _mcp_result({"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": result}]}})

        elif name == "browser_navigation":
            allowed, err = self._is_tool_allowed(name)
            if not allowed:
                return _mcp_result({"jsonrpc": "2.0", "id": 1, "error": {"code": -32001, "message": err}})
            url = args.get("url", "")
            result = _browser_navigation(url)
            return _mcp_result({"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": result}]}})

        elif name == "set_log_level":
            level_str = args.get("level", "INFO").upper()
            import logging
            level_map = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING,
                         "ERROR": logging.ERROR, "CRITICAL": logging.CRITICAL}
            level = level_map.get(level_str)
            if level is None:
                return _mcp_result({"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": f"Invalid level: {level_str}"}})
            logging.getLogger().setLevel(level)
            logger.info("Root logger level set to %s by MCP tool", level_str)
            return _mcp_result({"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": f"Log level set to {level_str}"}]}})

        elif name == "get_screen_time":
            logger.debug("[MCP] Tool called: get_screen_time")
            from src.persistence import load_state
            state = load_state()
            screen_time = state.get("screen_time", {})
            return _mcp_result({"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": json.dumps(screen_time, indent=2)}]}})

        elif name == "get_recent_git_diff":
            logger.debug("[MCP] Tool called: get_recent_git_diff")
            import subprocess
            try:
                # First try to get staged diff
                diff = subprocess.check_output(["git", "diff", "--cached"], stderr=subprocess.STDOUT, text=True).strip()
                if not diff:
                    # If empty, try un-staged diff
                    diff = subprocess.check_output(["git", "diff"], stderr=subprocess.STDOUT, text=True).strip()
                if not diff:
                    # If still empty, get last commit diff
                    diff = subprocess.check_output(["git", "show", "--stat", "-p", "HEAD"], stderr=subprocess.STDOUT, text=True).strip()
                # Truncate if too long
                if len(diff) > 4000:
                    diff = diff[:4000] + "\n...[truncated]"
                return _mcp_result({"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": diff}]}})
            except Exception as e:
                return _mcp_result({"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message": str(e)}})

        elif name == "set_reminder":
            logger.debug(f"[MCP] Tool called: set_reminder with args: {args}")
            import concurrent.futures
            future = concurrent.futures.Future()
            data = {"message": args.get("message"), "time_minutes": args.get("time_minutes"), "future": future}
            self._fsm_bridge.reminder_request.emit("set", data)
            rem_id = future.result(timeout=2.0)
            return _mcp_result({"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": f"Reminder set with ID: {rem_id}"}]}})

        elif name == "get_reminders":
            logger.debug("[MCP] Tool called: get_reminders")
            import concurrent.futures
            future = concurrent.futures.Future()
            self._fsm_bridge.reminder_request.emit("get", {"future": future})
            active = future.result(timeout=2.0)
            return _mcp_result({"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": json.dumps(active, indent=2)}]}})

        elif name == "dismiss_reminder":
            logger.debug(f"[MCP] Tool called: dismiss_reminder with args: {args}")
            import concurrent.futures
            future = concurrent.futures.Future()
            data = {"id": args.get("id"), "future": future}
            self._fsm_bridge.reminder_request.emit("dismiss", data)
            success = future.result(timeout=2.0)
            if success:
                return _mcp_result({"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": f"Reminder {args.get('id')} dismissed"}]}})
            else:
                return _mcp_result({"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message": "Reminder ID not found"}})

        else:
            logger.debug("MCP unknown tool: %s", name)
            return _mcp_result({"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": f"Unknown tool: {name}"}})

    def _handle_list_directory(self, args):
        relative_path = args.get("relative_path", "")
        try:
            abs_path = _validate_mcp_path(relative_path)
        except ValueError as e:
            return {"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": str(e)}}
        if not os.path.exists(abs_path):
            return {"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": f"Path not found: {relative_path}"}}
        if not os.path.isdir(abs_path):
            return {"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": f"Not a directory: {relative_path}"}}
        entries = []
        for entry in sorted(os.listdir(abs_path)):
            full = os.path.join(abs_path, entry)
            if os.path.isdir(full):
                entries.append({"name": entry, "type": "directory"})
            else:
                try:
                    size = os.path.getsize(full)
                except OSError:
                    size = 0
                entries.append({"name": entry, "type": "file", "size": size})
        return {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": json.dumps(entries, indent=2)}]}}

    def _handle_read_file(self, args):
        file_path = args.get("file_path", "")
        start_line = args.get("start_line")
        end_line = args.get("end_line")
        if not _validate_read_extension(file_path):
            return {"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": f"File type not allowed: {file_path}"}}
        try:
            abs_path = _validate_mcp_path(file_path)
        except ValueError as e:
            return {"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": str(e)}}
        if not os.path.exists(abs_path):
            return {"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": f"File not found: {file_path}"}}
        if not os.path.isfile(abs_path):
            return {"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": f"Not a file: {file_path}"}}

        # Check cache
        import time
        cache_key = f"{file_path}:{start_line or 1}:{end_line or 'end'}"
        now = time.time()
        if cache_key in _file_cache and (now - _cache_timestamps.get(cache_key, 0)) < _file_cache_ttl:
            logger.debug("MCP read_file cache hit: %s", file_path)
            return _file_cache[cache_key]

        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            return {"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": f"Cannot read binary file: {file_path}"}}
        total_lines = len(lines)
        start_idx = max(0, (start_line or 1) - 1)
        end_idx = min(total_lines, end_line) if end_line else min(total_lines, start_idx + MAX_READ_LINES)
        selected = lines[start_idx:end_idx]
        content = "".join(selected)
        header = f"# {file_path} (lines {start_idx + 1}-{end_idx} of {total_lines})\n"
        if end_idx - start_idx >= MAX_READ_LINES:
            content += "\n... (truncated at 500 lines max, use start_line/end_line to paginate)"
        result = {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": header + content}]}}

        # Cache the result
        _file_cache[cache_key] = result
        _cache_timestamps[cache_key] = now

        return result

    def _handle_search_codebase(self, args):
        search_term = args.get("search_term", "")
        if not search_term:
            return {"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "search_term required"}}
        results = []
        search_dirs = [os.path.join(PROJECT_ROOT, "src"), os.path.join(PROJECT_ROOT, "tests")]
        pattern = re.compile(search_term)
        for search_dir in search_dirs:
            if not os.path.exists(search_dir):
                continue
            for root, dirs, files in os.walk(search_dir):
                dirs[:] = [d for d in dirs if not d.startswith("__") and not d.startswith(".")]
                for file in files:
                    if not file.endswith(".py"):
                        continue
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, PROJECT_ROOT)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            for i, line in enumerate(f, 1):
                                if pattern.search(line):
                                    results.append({"file": rel_path, "line": i, "snippet": line.strip()[:200]})
                    except UnicodeDecodeError:
                        continue
        return {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": json.dumps(results, indent=2)}]}}

    @staticmethod
    def parse_raw(body, consent: dict[str, bool] | None = None):
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
                consent_key = _CONSENT_TOOL_MAP.get(name)
                if consent_key is not None:
                    allowed = consent.get(consent_key, False) if consent else False
                    if not allowed:
                        response["error"] = {"code": -32001, "message": f"ERROR: User has denied permission '{consent_key}'. Tool '{name}' blocked."}
                        return response
                if name == "change_visual_state":
                    action = args.get("action")
                    if action not in VALID_ACTIONS:
                        response["error"] = {"code": -32602, "message": f"Invalid action: {action}"}
                    else:
                        response["result"] = {"content": [{"type": "text", "text": "ok"}]}
                elif name in ("read_clipboard", "capture_blackmail_evidence", "send_system_toast",
                               "list_directory", "read_file", "search_codebase", "get_memory", "get_diary",
                               "simulate_keystroke", "move_mouse", "browser_navigation"):
                    response["result"] = {"content": [{"type": "text", "text": "ok"}]}
                elif name == "set_log_level":
                    response["result"] = {"content": [{"type": "text", "text": "ok"}]}
                else:
                    response["error"] = {"code": -32602, "message": f"Unknown tool: {name}"}
            else:
                response["error"] = {"code": -32601, "message": "Method not found"}
            return response
        except json.JSONDecodeError:
            return {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}


class MCPServer:

    def __init__(self, fsm_bridge, memory=None, diary_store=None, host="127.0.0.1", port=4097, config: dict | None = None):
        self._config = config
        # Read MCP host/port from config if available
        if config and "mcp" in config:
            self._host = config["mcp"].get("host", host)
            self._port = config["mcp"].get("port", port)
        else:
            self._host = host
            self._port = port
        self._fsm_bridge = fsm_bridge
        self._memory = memory
        self._diary_store = diary_store
        self._server = None
        self._thread = None

    @property
    def server(self):
        return self._server

    @property
    def server_address(self):
        return self._server.server_address if self._server else (self._host, self._port)

    def start(self, action_layer=None):
        global _BOOT_TIME
        _BOOT_TIME = time.monotonic()
        consent = {}
        if self._config:
            # Extract consent from the consent sub-section
            consent_data = self._config.get("consent", {})
            if isinstance(consent_data, dict):
                consent = {
                    k: consent_data.get(k, False) for k in _CONSENT_TOOL_MAP.values()
                }

        self._server = ThreadingHTTPServer((self._host, self._port), MCPHandler)
        self._server.fsm_bridge = self._fsm_bridge
        self._server.memory = self._memory
        self._server.diary_store = self._diary_store
        self._server.consent = consent
        self._server.action_layer = action_layer
        self._port = self._server.server_address[1]
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logger.info("MCP server started on %s:%s", self._host, self._port)

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            self._thread = None
            logger.info("MCP server stopped")
