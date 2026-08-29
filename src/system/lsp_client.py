"""Minimal JSON-RPC over stdio client for language servers."""
from __future__ import annotations

import json
import logging
import subprocess
import threading
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


class LSPError(RuntimeError):
    """Raised when a language server cannot complete an operation."""


class LSPClient:
    """Synchronous LSP client with publishDiagnostics notification support."""

    def __init__(
        self,
        command: list[str],
        workspace: str | Path,
        *,
        process_factory: Callable[..., Any] = subprocess.Popen,
        request_timeout: float = 10.0,
    ) -> None:
        if not command:
            raise ValueError("command must not be empty")
        if request_timeout <= 0:
            raise ValueError("request_timeout must be positive")
        root = Path(workspace).expanduser().resolve()
        if not root.is_dir():
            raise ValueError(f"Workspace does not exist: {root}")
        self.command = list(command)
        self.workspace = root
        self._process_factory = process_factory
        self.request_timeout = request_timeout
        self._process: Any | None = None
        self._next_id = 1
        self._diagnostics: dict[str, list[dict[str, Any]]] = {}
        self._lock = threading.RLock()

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def start(self) -> dict[str, Any]:
        """Start the server and perform the LSP initialize/initialized handshake."""
        with self._lock:
            if self.running:
                return {}
            try:
                self._process = self._process_factory(
                    self.command,
                    cwd=str(self.workspace),
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                result = self._request(
                    "initialize",
                    {
                        "processId": None,
                        "rootUri": self._uri(self.workspace),
                        "capabilities": {
                            "textDocument": {
                                "publishDiagnostics": {"relatedInformation": True}
                            }
                        },
                        "workspaceFolders": [
                            {"uri": self._uri(self.workspace), "name": self.workspace.name}
                        ],
                    },
                )
                self._notify("initialized", {})
                return result
            except (OSError, LSPError) as exc:
                self.stop()
                raise LSPError(f"Unable to start LSP server: {exc}") from exc

    def stop(self) -> None:
        """Close the stdio process without waiting indefinitely."""
        process = self._process
        if process is None:
            return
        try:
            self._notify("shutdown", {})
            if process.poll() is None:
                self._notify("exit", {})
        except (BrokenPipeError, OSError, LSPError):
            logger.debug("LSP shutdown handshake failed", exc_info=True)
        finally:
            self._process = None
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=2)
            except (subprocess.TimeoutExpired, OSError):
                process.kill()

    def did_open(self, path: str | Path, text: str, language_id: str) -> None:
        """Notify the server that a document is open."""
        document_uri = self._document_uri(path)
        self._notify(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": document_uri,
                    "languageId": language_id,
                    "version": 1,
                    "text": text,
                }
            },
        )

    def did_change(self, path: str | Path, text: str, version: int) -> None:
        """Notify the server of a complete document replacement."""
        if version < 1:
            raise ValueError("version must be positive")
        self._notify(
            "textDocument/didChange",
            {
                "textDocument": {"uri": self._document_uri(path), "version": version},
                "contentChanges": [{"text": text}],
            },
        )

    def get_diagnostics(self, path: str | Path | None = None) -> Any:
        """Return diagnostics received through publishDiagnostics."""
        if path is None:
            return {uri: list(items) for uri, items in self._diagnostics.items()}
        return list(self._diagnostics.get(self._document_uri(path), []))

    def goto_definition(self, path: str | Path, line: int, column: int) -> list[dict[str, Any]]:
        """Request definitions at a 1-based source position."""
        return self._location_request("textDocument/definition", path, line, column)

    def find_references(self, path: str | Path, line: int, column: int) -> list[dict[str, Any]]:
        """Request references at a 1-based source position."""
        result = self._location_request(
            "textDocument/references", path, line, column, {"includeDeclaration": True}
        )
        return result

    def symbol_info(self, path: str | Path, line: int, column: int) -> dict[str, Any]:
        """Return definitions and references as one MCP-friendly result."""
        return {
            "definitions": self.goto_definition(path, line, column),
            "references": self.find_references(path, line, column),
        }

    def _location_request(
        self,
        method: str,
        path: str | Path,
        line: int,
        column: int,
        extra: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if line < 1 or column < 1:
            raise ValueError("line and column must be positive 1-based positions")
        context = {"textDocument": {"uri": self._document_uri(path)}, "position": {
            "line": line - 1, "character": column - 1
        }}
        if extra:
            context["context"] = extra
        result = self._request(method, context)
        if result is None:
            return []
        if isinstance(result, dict):
            return [result]
        if not isinstance(result, list):
            raise LSPError(f"Unexpected {method} response")
        return result

    def _request(self, method: str, params: Any) -> Any:
        request_id = self._next_id
        self._next_id += 1
        self._write({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        while True:
            message = self._read()
            if "method" in message and "id" not in message:
                self._handle_notification(message)
                continue
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise LSPError(str(message["error"]))
            return message.get("result")

    def _notify(self, method: str, params: Any) -> None:
        self._write({"jsonrpc": "2.0", "method": method, "params": params})

    def _write(self, message: dict[str, Any]) -> None:
        process = self._process
        if process is None or process.stdin is None:
            raise LSPError("LSP server is not running")
        payload = json.dumps(message, separators=(",", ":")).encode("utf-8")
        process.stdin.write(f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii") + payload)
        process.stdin.flush()

    def _read(self) -> dict[str, Any]:
        process = self._process
        if process is None or process.stdout is None:
            raise LSPError("LSP server is not running")
        headers: dict[str, str] = {}
        while True:
            line = process.stdout.readline()
            if not line:
                raise LSPError("Language server closed stdout")
            if line in (b"\r\n", b"\n"):
                break
            key, separator, value = line.decode("ascii").partition(":")
            if separator:
                headers[key.casefold()] = value.strip()
        try:
            length = int(headers["content-length"])
            return json.loads(process.stdout.read(length).decode("utf-8"))
        except (KeyError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LSPError("Invalid language-server JSON-RPC frame") from exc

    def _handle_notification(self, message: dict[str, Any]) -> None:
        if message.get("method") != "textDocument/publishDiagnostics":
            return
        params = message.get("params") or {}
        uri = params.get("uri")
        if isinstance(uri, str):
            self._diagnostics[uri] = list(params.get("diagnostics") or [])

    def _document_uri(self, path: str | Path) -> str:
        document = Path(path).expanduser().resolve()
        try:
            document.relative_to(self.workspace)
        except ValueError as exc:
            raise ValueError(f"Document is outside workspace: {document}") from exc
        return self._uri(document)

    @staticmethod
    def _uri(path: Path) -> str:
        return path.as_uri()
