"""src/llm/mcp_client.py

In-process MCP client that lets the pet's LLM brain call the Daemon MCP
server's tools (e.g. ``change_visual_state``) instead of a hardcoded, stale
tool list.

Why this exists
---------------
``OllamaWorker`` previously carried a hand-written ``OLLAMA_TOOLS`` list whose
``change_visual_state`` enum was missing valid actions (e.g. ``jump``) and
included invalid ones. ``OpencodeWorker`` had no tool wiring at all, so the
brain could only ever return dialogue. Both problems are solved by letting the
LLM call the *actual* MCP server:

* the tool schema is generated live from ``list_tools()`` and can never drift
  from ``mcp_server.py``;
* consent gating, action validation and FSM/expression routing all happen
  server-side (one canonical action path);
* all 23 tools become available, not just the 3 that were hardcoded.

The Daemon MCP server exposes an SSE endpoint (FastMCP) on
``mcp.host:mcp.port`` (default ``127.0.0.1:4097``). We connect over SSE using
the ``mcp`` SDK.

The workers are synchronous ``QThread``s, so the async MCP calls are wrapped
with ``asyncio.run``. A ``session_cm_factory`` can be injected for testing
without a live server.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

try:
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    _HAVE_MCP = True
except Exception:  # pragma: no cover - the mcp SDK ships with the project
    ClientSession = None  # type: ignore
    sse_client = None  # type: ignore
    _HAVE_MCP = False

logger = logging.getLogger(__name__)

_CLIENT_CACHE: dict[str, "DaemonMCPClient"] = {}
_CLIENT_CACHE_LOCK = threading.Lock()


class MCPExecutionError(RuntimeError):
    """Base error for bounded MCP request execution."""


class MCPExecutionBudgetError(MCPExecutionError):
    """Raised when a request exceeds its tool, time, or payload budget."""


@dataclass
class MCPExecutionBudget:
    """Per-request limits shared by a worker's MCP tool loop."""

    max_tool_calls: int = 8
    max_wall_clock_seconds: float = 30.0
    max_payload_bytes: int = 64 * 1024
    cancellation: threading.Event | None = None
    started_at: float = field(default_factory=time.monotonic)
    tool_calls: int = 0
    payload_bytes: int = 0

    def _check(self) -> None:
        if self.cancellation is not None and self.cancellation.is_set():
            raise MCPExecutionError("MCP request cancelled")
        if time.monotonic() - self.started_at >= self.max_wall_clock_seconds:
            raise MCPExecutionBudgetError(
                f"MCP request exceeded wall-clock budget ({self.max_wall_clock_seconds:.1f}s)"
            )

    def reserve(self, name: str, args: dict[str, Any]) -> None:
        self._check()
        if self.tool_calls >= self.max_tool_calls:
            raise MCPExecutionBudgetError(
                f"MCP request exceeded tool-call budget ({self.max_tool_calls})"
            )
        payload_size = self._payload_size(name, args)
        if self.payload_bytes + payload_size > self.max_payload_bytes:
            raise MCPExecutionBudgetError(
                f"MCP request exceeded payload budget ({self.max_payload_bytes} bytes)"
            )
        self.tool_calls += 1
        self.payload_bytes += payload_size

    @staticmethod
    def _payload_size(name: str, args: dict[str, Any]) -> int:
        try:
            return len(json.dumps(
                {"name": name, "arguments": args or {}},
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise MCPExecutionError(f"MCP tool payload is not serializable: {exc}") from exc

    def check_tool(self, name: str, args: dict[str, Any]) -> None:
        """Preflight a tool call (useful when the client is mocked)."""
        self._check()
        if self.tool_calls >= self.max_tool_calls:
            raise MCPExecutionBudgetError(
                f"MCP request exceeded tool-call budget ({self.max_tool_calls})"
            )
        if self.payload_bytes + self._payload_size(name, args) > self.max_payload_bytes:
            raise MCPExecutionBudgetError(
                f"MCP request exceeded payload budget ({self.max_payload_bytes} bytes)"
            )

    def record_result(self, result: str) -> None:
        self._check()
        result_size = len((result or "").encode("utf-8"))
        if self.payload_bytes + result_size > self.max_payload_bytes:
            raise MCPExecutionBudgetError(
                f"MCP request exceeded payload budget ({self.max_payload_bytes} bytes)"
            )
        self.payload_bytes += result_size

    def remaining_seconds(self) -> float:
        self._check()
        return max(0.001, self.max_wall_clock_seconds - (time.monotonic() - self.started_at))


def _tool_to_llm_schema(tool: Any) -> dict:
    """Convert an MCP ``Tool`` object into an OpenAI-style function schema."""
    return {
        "type": "function",
        "function": {
            "name": getattr(tool, "name", ""),
            "description": getattr(tool, "description", "") or "",
            "parameters": getattr(tool, "inputSchema", {}) or {},
        },
    }


def _extract_text(result: Any) -> str:
    """Flatten an MCP ``CallToolResult`` into a plain string."""
    parts = getattr(result, "content", None) or []
    chunks = []
    for part in parts:
        text = getattr(part, "text", None)
        if text:
            chunks.append(text)
    return "\n".join(chunks)


class DaemonMCPClient:
    """Thin synchronous wrapper around the Daemon MCP server (SSE)."""

    def __init__(
        self,
        base_url: str,
        session_cm_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        self._base_url = base_url
        # Injected only for tests; otherwise we dial the real SSE endpoint.
        self._session_cm_factory = session_cm_factory
        self._schema_cache: Optional[list[dict]] = None
        self._lock = threading.Lock()

    # ── async core ────────────────────────────────────────────────────────

    def _session_cm(self):
        if self._session_cm_factory is not None:
            return self._session_cm_factory()
        if not _HAVE_MCP:
            raise RuntimeError("mcp SDK is not installed")
        return sse_client(self._base_url)

    async def _alist_tools(self) -> list[dict]:
        async with self._session_cm() as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                resp = await session.list_tools()
                return [_tool_to_llm_schema(t) for t in getattr(resp, "tools", [])]

    async def _acall_tool(self, name: str, args: dict) -> str:
        async with self._session_cm() as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, args or {})
                if getattr(result, "isError", False):
                    logger.warning("MCP tool '%s' returned an error", name)
                return _extract_text(result)

    # ── synchronous wrappers (workers are sync QThreads) ───────────────────

    # Hard ceiling so a broken/slow MCP server can never hang a worker thread
    # forever (e.g. a zombie process holding port 4097 that accepts the TCP
    # connection but never completes the SSE/initialize handshake). Without
    # this the LLM worker would block indefinitely and the pet would sit on
    # "..." forever with no error.
    LIST_TOOLS_TIMEOUT = 8.0
    CALL_TOOL_TIMEOUT = 10.0

    def list_tools(self) -> list[dict]:
        return asyncio.run(self._with_timeout(self._alist_tools(), self.LIST_TOOLS_TIMEOUT))

    def call_tool(
        self,
        name: str,
        args: Optional[dict],
        *,
        budget: MCPExecutionBudget | None = None,
        cancellation: threading.Event | None = None,
    ) -> str:
        if budget is not None:
            budget.reserve(name, args or {})
            timeout = min(self.CALL_TOOL_TIMEOUT, budget.remaining_seconds())
        else:
            if cancellation is not None and cancellation.is_set():
                raise MCPExecutionError("MCP request cancelled")
            timeout = self.CALL_TOOL_TIMEOUT
        result = asyncio.run(self._with_timeout(self._acall_tool(name, args or {}), timeout))
        if cancellation is not None and cancellation.is_set():
            raise MCPExecutionError("MCP request cancelled")
        if budget is not None:
            budget.record_result(result)
        return result

    @staticmethod
    async def _with_timeout(coro, seconds: float):
        return await asyncio.wait_for(coro, timeout=seconds)

    def get_tool_schema(self, force_refresh: bool = False) -> list[dict]:
        with self._lock:
            if self._schema_cache is None or force_refresh:
                try:
                    self._schema_cache = self.list_tools()
                except Exception as exc:  # timeout / connection / handshake errors
                    logger.warning("MCP schema fetch failed (%s); tools disabled this run", exc)
                    # Keep a previously known-good catalog. A transient server
                    # failure must not erase schemas for in-flight workers.
                    if self._schema_cache is None:
                        self._schema_cache = []
            return self._schema_cache


def build_client() -> DaemonMCPClient:
    """Return a process-shared client pointed at the configured MCP server.

    Workers are short-lived, but MCP schema discovery is not request-specific.
    Sharing the client preserves its schema cache and avoids a fresh SSE
    initialize handshake for every LLM request.
    """
    try:
        from src.config import config_get
        host = config_get("mcp.host") or "127.0.0.1"
        port = config_get("mcp.port") or 4097
    except Exception:
        host, port = "127.0.0.1", 4097
    base_url = f"http://{host}:{port}/sse"
    with _CLIENT_CACHE_LOCK:
        client = _CLIENT_CACHE.get(base_url)
        if client is None:
            client = DaemonMCPClient(base_url)
            _CLIENT_CACHE[base_url] = client
        return client


def clear_client_cache() -> None:
    """Clear shared MCP clients after server/config lifecycle changes."""
    with _CLIENT_CACHE_LOCK:
        _CLIENT_CACHE.clear()
