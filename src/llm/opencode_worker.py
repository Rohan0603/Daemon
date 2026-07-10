"""src/llm/opencode_worker.py — Stateless burst LLM execution coordinator.

Every call creates a fresh ephemeral OpenCode session (POST /session → message
→ DELETE /session), carrying the full XML context payload every time.
Zero SQLite accumulation in opencode serve.
"""
from __future__ import annotations

import json
import logging
import warnings
from typing import Any

import requests
from PyQt6.QtCore import QThread, pyqtSignal

from src.config import config_get, DEFAULT_SERVER_URL

logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore", category=DeprecationWarning, module="src.llm.opencode_worker")


class OpencodeWorker(QThread):
    """Stateless burst LLM worker. Creates/destroys an OpenCode session per call.

    Every burst is fully self-contained: session create, message post, session
    delete.  No session state persists across calls.
    """

    # ── Signals (forward-compatible aliases) ────────────────────────────────

    response_ready = pyqtSignal(list)       # list[dict] — parsed structured items
    error_occurred = pyqtSignal(str)        # error description
    trigger_ready = pyqtSignal(list)        # alias for response_ready
    session_created = pyqtSignal(str)       # emitted for backward compat (never fires in stateless mode)
    brain_update_ready = pyqtSignal(dict)   # emitted if items contain brain_update
    error = pyqtSignal(str)                 # alias for error_occurred

    # ── Constructor ─────────────────────────────────────────────────────────

    def __init__(
        self,
        *args: Any,
        prompt: str = "",
        is_autonomous: bool = False,
        screen_context: str | None = None,
        parent: Any = None,
        **kwargs: Any,  # absorb legacy kwargs for backward compat
    ):
        super().__init__(parent)
        self._prompt = prompt
        self._is_autonomous = is_autonomous
        self._screen_context = screen_context
        self._abort = False
        self._last_raw_response = ""
        self._timed_out = False

        # Config — local opencode serve URL for session management
        self._server_url = DEFAULT_SERVER_URL
        timeout = int(config_get("llm.timeout_sec") or 30)
        self._post_timeout = min(timeout, 60)
        # Refill operations get a longer timeout
        if is_autonomous:
            self._post_timeout = max(timeout, 120)

        # MCP tool forwarding: let opencode emit tool calls that we execute
        # against the Daemon MCP server so the pet can actually perform actions
        # (e.g. "jump"). Automatically disabled if the MCP server is
        # unreachable. Set llm.opencode_forward_tools=false to disable it
        # (e.g. when opencode serve is itself configured with the Daemon MCP
        # server) so each tool is not executed twice.
        self._forward_tools = str(config_get("llm.opencode_forward_tools") or "true").lower() != "false"
        self._mcp = None
        self._tools = None

    # ── Public API ──────────────────────────────────────────────────────────

    def abort(self) -> None:
        self._abort = True

    def run(self) -> None:
        """Execute a single stateless burst: create → post → parse → cleanup."""
        if self._abort:
            return

        session_id = self._create_session()
        if not session_id:
            self.error.emit("session_create_failed")
            self.error_occurred.emit("session_create_failed")
            return

        try:
            if self._abort:
                return

            raw = self._post_message(session_id, self._prompt)
            if self._abort:
                return

            if raw:
                self._last_raw_response = raw
                items = self._parse_response(raw)
                if items:
                    # Extract brain_update before emitting
                    self._extract_brain_update(items)
                    self.response_ready.emit(items)
                    return

            if self._timed_out:
                logger.warning("run: post_message timed out for %s",
                               session_id[:8] if session_id else "?")
                self.error.emit("timeout")
                self.error_occurred.emit("timeout")
            else:
                logger.warning("run: all parse strategies failed for %s (first 200): %s",
                               session_id[:8] if session_id else "?", (raw or "")[:200])
                self.error.emit("parse_failed")
                self.error_occurred.emit("parse_failed")

        finally:
            self._delete_session(session_id)

    # ── HTTP helpers ────────────────────────────────────────────────────────

    def _create_session(self) -> str | None:
        """POST /session → returns session_id or None."""
        if self._abort:
            return None
        try:
            resp = requests.post(
                f"{self._server_url}/session",
                json={},
                timeout=10,
            )
            if resp.status_code >= 400:
                logger.warning("create_session failed: HTTP %s %s",
                               resp.status_code, resp.text[:200])
                return None
            data = resp.json()
            sid = data.get("id") or data.get("session_id")
            if not sid:
                logger.warning("create_session returned no id: %s", resp.text[:200])
                return None
            return sid
        except requests.exceptions.ConnectionError:
            logger.warning("create_session: connection refused to %s", self._server_url)
            return None
        except Exception as exc:
            logger.warning("create_session exception: %s", exc)
            return None

    def _post_message(self, session_id: str, payload_text: str) -> str:
        """POST /session/{id}/message → extract text; forward any tool calls.

        Best-effort: if the Daemon MCP server is reachable we advertise its
        tool catalog in the payload so opencode can emit tool calls, then
        execute those calls against the MCP server (the pet performs the
        action). If opencode returns no tool calls, behaviour is unchanged
        (plain dialogue).
        """
        if self._abort:
            return ""
        self._ensure_tools()
        payload = {"parts": [{"type": "text", "text": payload_text}]}
        if self._tools:
            payload["tools"] = self._tools
        try:
            resp = requests.post(
                f"{self._server_url}/session/{session_id}/message",
                json=payload,
                timeout=self._post_timeout,
            )
            if resp.status_code >= 400:
                logger.warning("post_message failed: HTTP %s %s",
                               resp.status_code, resp.text[:200])
                return ""

            data = resp.json()
            # Execute any tool calls opencode emitted (pet performs the action).
            self._forward_tool_calls(data)
            # Extract text from parts array (standard OpenCode response shape)
            for part in data.get("parts", []):
                if isinstance(part, dict) and part.get("type") == "text":
                    text = part.get("text", "")
                    if text:
                        return text
            # Alternate response shape: direct text field
            direct_text = data.get("text") or data.get("content", "")
            if direct_text:
                return direct_text
            return ""
        except requests.exceptions.Timeout:
            logger.warning("post_message timed out after %ss", self._post_timeout)
            self._timed_out = True
            return ""
        except Exception as exc:
            logger.warning("post_message exception: %s", exc)
            return ""

    def _ensure_tools(self) -> None:
        """Build the MCP tool catalog for opencode (no-op if disabled/unreachable)."""
        if not self._forward_tools or self._tools is not None:
            return
        try:
            from src.llm.mcp_client import build_client
            client = build_client()
            schema = client.get_tool_schema()
            if schema:
                self._mcp = client
                self._tools = schema
                logger.debug("OpencodeWorker advertising %d MCP tools to opencode", len(schema))
        except Exception as exc:  # pragma: no cover - depends on runtime MCP state
            logger.warning("OpencodeWorker: live MCP tool schema unavailable (%s); tools disabled", exc)
            self._mcp = None
            self._tools = None

    @staticmethod
    def _extract_tool_calls(data: dict) -> list[dict]:
        """Defensively pull tool calls from an opencode response (any known shape)."""
        calls: list[dict] = []

        def _normalize(block):
            fn = block.get("function") or {}
            name = fn.get("name")
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            if name:
                calls.append({"name": name, "arguments": args})

        for tc in (data.get("tool_calls") or []):
            if isinstance(tc, dict):
                _normalize(tc)
        msg = data.get("message") or {}
        for tc in (msg.get("tool_calls") or []):
            if isinstance(tc, dict):
                _normalize(tc)
        for part in (data.get("parts") or []):
            if isinstance(part, dict) and part.get("type") == "tool_call":
                name = part.get("name") or (part.get("function") or {}).get("name")
                args = part.get("arguments") or part.get("args") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                if name:
                    calls.append({"name": name, "arguments": args})
        return calls

    def _forward_tool_calls(self, data: dict) -> None:
        """Execute any tool calls opencode emitted, via the Daemon MCP server."""
        if self._mcp is None:
            return
        for call in self._extract_tool_calls(data):
            name = call["name"]
            args = call.get("arguments") or {}
            try:
                logger.info("OpencodeWorker forwarding tool call '%s' to MCP server", name)
                self._mcp.call_tool(name, args)
            except Exception as exc:  # pragma: no cover - depends on runtime MCP state
                logger.warning("OpencodeWorker MCP call_tool failed for '%s': %s", name, exc)

    def _delete_session(self, session_id: str) -> None:
        """DELETE /session/{id}. Non-critical — failures logged at debug level."""
        if not session_id:
            return
        try:
            requests.delete(
                f"{self._server_url}/session/{session_id}",
                timeout=5,
            )
        except Exception as exc:
            logger.debug("delete_session failed (non-critical): %s", exc)

    # ── Response parsing ────────────────────────────────────────────────────

    def _parse_response(self, raw: str) -> list[dict] | None:
        """Parse LLM response into list[dict].

        Strategies, in order:
          1. Direct JSON array
          2. Single JSON object → wrapped in list
          3. JSONL (multiple objects on separate lines)
        Returns None if all strategies fail.
        """
        if not raw or not raw.strip():
            return None

        # Trim degenerate responses
        from src.constants import MAX_RESPONSE_CHARS
        if len(raw) > MAX_RESPONSE_CHARS:
            logger.warning("Response truncated from %d to %d chars",
                           len(raw), MAX_RESPONSE_CHARS)
            raw = raw[:MAX_RESPONSE_CHARS]

        text = raw.strip()

        # Strip markdown code fences
        if text.startswith("```"):
            lines = text.splitlines()
            inner = []
            in_fence = False
            for line in lines:
                if line.strip().startswith("```") and not in_fence:
                    in_fence = True
                    continue
                if line.strip().startswith("```") and in_fence:
                    break
                if in_fence:
                    inner.append(line)
            if inner:
                text = "\n".join(inner).strip()

        # Strategy 1: direct JSON array
        try:
            items = json.loads(text)
            if isinstance(items, list):
                validated = [i for i in items if isinstance(i, dict)]
                if validated:
                    return validated
            if isinstance(items, dict):
                return [items]
        except json.JSONDecodeError:
            pass

        # Strategy 2: find JSON array in text (bracket matching)
        start = text.find("[")
        if start != -1:
            end = text.rfind("]")
            if end != -1 and end > start:
                try:
                    items = json.loads(text[start:end + 1])
                    if isinstance(items, list):
                        validated = [i for i in items if isinstance(i, dict)]
                        if validated:
                            return validated
                except json.JSONDecodeError:
                    pass

        # Strategy 3: single JSON object
        start = text.find("{")
        if start != -1:
            end = text.rfind("}")
            if end != -1 and end > start:
                try:
                    obj = json.loads(text[start:end + 1])
                    if isinstance(obj, dict):
                        return [obj]
                except json.JSONDecodeError:
                    pass

        # Strategy 4: JSONL — objects on separate lines
        items = []
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        items.append(obj)
                except json.JSONDecodeError:
                    pass
        if items:
            return items

        # Strategy N — free-form text: wrap as valid dialogue item
        logger.info("All JSON parse strategies failed; wrapping as free-form dialogue")
        truncated = raw[:400].strip()
        if truncated:
            return [{"dialogue": truncated, "action": "idle", "type": "observation",
                     "priority": 3, "thought": ""}]
        return []

    def _extract_brain_update(self, items: list[dict]) -> None:
        """Emit brain_update_ready if any item contains a brain_update field."""
        emitted = False
        for item in items:
            bu = item.pop("brain_update", None)
            if bu is not None and not emitted:
                self.brain_update_ready.emit(bu)
                emitted = True
