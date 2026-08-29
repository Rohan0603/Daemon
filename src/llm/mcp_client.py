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
import logging
import threading
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

    def call_tool(self, name: str, args: Optional[dict]) -> str:
        return asyncio.run(self._with_timeout(self._acall_tool(name, args or {}), self.CALL_TOOL_TIMEOUT))

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
                    self._schema_cache = []
            return self._schema_cache


def build_client() -> DaemonMCPClient:
    """Build a client pointed at the running Daemon MCP server (from config)."""
    try:
        from src.config import config_get
        host = config_get("mcp.host") or "127.0.0.1"
        port = config_get("mcp.port") or 4097
    except Exception:
        host, port = "127.0.0.1", 4097
    return DaemonMCPClient(f"http://{host}:{port}/sse")
