"""Authenticated localhost WebSocket bridge for IDE integrations."""
from __future__ import annotations

import asyncio
import json
import logging
import secrets
import threading
from typing import Any, Callable

logger = logging.getLogger(__name__)


class IDEBridge:
    """Serve a small JSON protocol for a trusted local editor extension."""

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 4098,
        token: str | None = None,
        handlers: dict[str, Callable[[dict[str, Any]], Any]] | None = None,
    ) -> None:
        if host != "127.0.0.1":
            raise ValueError("IDE bridge must bind to localhost")
        if not 1 <= port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        self.host = host
        self.port = port
        self.token = token or secrets.token_urlsafe(32)
        self.handlers = handlers or {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server: Any = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._context: dict[str, Any] = {}

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="ide-bridge", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2)
        self._thread = None
        self._loop = None

    def dispatch(self, message: dict[str, Any]) -> dict[str, Any]:
        """Dispatch one authenticated protocol message without network concerns."""
        if message.get("token") != self.token:
            return {"ok": False, "error": "unauthorized"}
        message_type = message.get("type")
        if not isinstance(message_type, str):
            return {"ok": False, "error": "missing message type"}
        if message_type == "GET_ACTIVE_CONTEXT":
            return {"ok": True, "context": dict(self._context)}
        if message_type == "EDITOR_CONTEXT":
            self._context = dict(message.get("context") or {})
            return {"ok": True}
        handler = self.handlers.get(message_type)
        if handler is None:
            return {"ok": False, "error": f"unsupported message type: {message_type}"}
        result = handler(message)
        return {"ok": True, "result": result} if result is not None else {"ok": True}

    def _run(self) -> None:
        try:
            import websockets
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._server = self._loop.run_until_complete(
                websockets.serve(self._handle_client, self.host, self.port)
            )
            self._loop.run_forever()
        except Exception:
            logger.exception("IDE bridge stopped unexpectedly")
        finally:
            if self._loop is not None:
                pending = asyncio.all_tasks(self._loop)
                for task in pending:
                    task.cancel()
                self._loop.close()
            self._server = None

    async def _handle_client(self, websocket: Any) -> None:
        async for raw_message in websocket:
            try:
                message = json.loads(raw_message)
                if not isinstance(message, dict):
                    raise ValueError("message must be an object")
                response = self.dispatch(message)
            except (json.JSONDecodeError, ValueError) as exc:
                response = {"ok": False, "error": str(exc)}
            await websocket.send(json.dumps(response, separators=(",", ":")))


def default_ide_handlers(
    *,
    insert_code: Callable[[str], Any] | None = None,
    replace_selection: Callable[[str], Any] | None = None,
    format_document: Callable[[], Any] | None = None,
) -> dict[str, Callable[[dict[str, Any]], Any]]:
    """Build handlers while keeping editor operations owned by the host app."""
    handlers: dict[str, Callable[[dict[str, Any]], Any]] = {}
    if insert_code is not None:
        handlers["INSERT_CODE"] = lambda msg: insert_code(str(msg.get("text", "")))
    if replace_selection is not None:
        handlers["REPLACE_SELECTION"] = lambda msg: replace_selection(str(msg.get("text", "")))
    if format_document is not None:
        handlers["FORMAT_DOCUMENT"] = lambda _msg: format_document()
    return handlers
