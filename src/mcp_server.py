import json
import logging
import os
import ctypes
from ctypes import wintypes
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

logger = logging.getLogger(__name__)

VALID_ACTIONS = {"idle", "wander", "shake", "spin", "hyper", "bounce",
                 "look_away", "celebrate", "devastated", "fall", "chase"}

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


class MCPHandler(BaseHTTPRequestHandler):

    fsm_bridge = None

    def do_GET(self):
        if self.path == "/sse":
            self._handle_sse()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/message":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            msg = json.loads(body)
            method = msg.get("method", "")
            params = msg.get("params", {})
            response = self._handle_request(method, params)
            response["id"] = msg.get("id")
            self._send_json(response)
        else:
            self.send_error(404)

    def _handle_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        self.wfile.write(f"event: endpoint\ndata: /message\n\n".encode())
        self.wfile.flush()

    def _send_json(self, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_request(self, method, params):
        if method == "tools/list":
            return self._handle_tools_list()
        elif method == "tools/call":
            return self._handle_tools_call(params)
        else:
            return {"jsonrpc": "2.0", "id": None, "error": {"code": -32601, "message": "Method not found"}}

    def _handle_tools_list(self):
        return {"jsonrpc": "2.0", "id": 1, "result": {"tools": MCP_TOOLS}}

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


class MCPServer:

    def __init__(self, fsm_bridge, host="127.0.0.1", port=4097):
        self._host = host
        self._port = port
        self._fsm_bridge = fsm_bridge
        self._server = None
        self._thread = None

    def start(self):
        def handler_factory(*args, **kwargs):
            handler = MCPHandler(*args, **kwargs)
            handler.fsm_bridge = self._fsm_bridge
            return handler

        self._server = HTTPServer((self._host, self._port), handler_factory)
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
