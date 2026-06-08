import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

logger = logging.getLogger(__name__)

VALID_ACTIONS = {"idle", "wander", "shake", "spin", "hyper", "bounce",
                 "look_away", "celebrate", "devastated", "fall", "chase"}

MCP_TOOLS = [{
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
}]


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
        if not params or "arguments" not in params:
            return {"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "Invalid params"}}
        args = params.get("arguments", {})
        action = args.get("action")
        if action not in VALID_ACTIONS:
            return {"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": f"Invalid action: {action}"}}
        if self.fsm_bridge:
            self.fsm_bridge.emit_request(action, args.get("target_x"), args.get("target_y"))
        return {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "ok"}]}}

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
                args = params.get("arguments", {})
                if args is None:
                    args = {}
                action = args.get("action")
                if action not in VALID_ACTIONS:
                    response["error"] = {"code": -32602, "message": f"Invalid action: {action}"}
                else:
                    response["result"] = {"content": [{"type": "text", "text": "ok"}]}
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
