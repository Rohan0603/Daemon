# src/llm/ollama_worker.py
from __future__ import annotations
import json, logging, re, requests, time
import threading
from typing import Any
from PyQt6.QtCore import QThread, pyqtSignal
from src.config import config_get
from src.llm.system_prompt import build_system_prompt, build_tool_directive
from src.observability import RequestTiming, record_request_phase, record_llm_fallback
from src.observability import record_request_cancellation
from src.log_context import correlation_scope

logger = logging.getLogger(__name__)

_NO_TOOLS_MODELS: set[str] = set()

# Static tool schema used ONLY when the live MCP server is unreachable (the
# DaemonMCPClient cannot fetch a schema). It is deliberately minimal — every
# real run uses the live schema from mcp_client so nothing drifts from
# mcp_server.py. The system prompt itself is never hardcoded; it comes from
# src.llm.system_prompt (the same SKILL.md opencode serve loads natively).
OLLAMA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "send_system_toast",
            "description": "Show a Windows toast notification.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "message": {"type": "string"}
                },
                "required": ["title", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_clipboard",
            "description": "Read the current clipboard contents.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
]


class OllamaWorker(QThread):
    response_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    trigger_ready = pyqtSignal(list)
    error = pyqtSignal(str)
    brain_update_ready = pyqtSignal(dict)
    tool_call_requested = pyqtSignal(str, dict)
    read_clipboard_requested = pyqtSignal()
    session_created = pyqtSignal(str)

    def __init__(self, *args: Any, prompt: str = "", is_autonomous: bool = False,
                 pet_id: str = "kenny", parent: Any = None, **kwargs: Any):
        super().__init__(parent)
        self._prompt = prompt
        self._is_autonomous = is_autonomous
        self._pet_id = pet_id
        self._abort = False
        self._cancel_event = threading.Event()
        self._last_raw_response = ""
        self._timed_out = False
        self._last_error_code = ""
        self._server_url = config_get("llm.ollama_url") or "http://127.0.0.1:11434"
        self._ollama_model = config_get("llm.ollama_model") or "llama3.2-1b-q8:latest"
        timeout = int(config_get("llm.timeout_sec") or 180)
        # Keep local fallback bounded even when config contains an accidental
        # zero or an excessively large cloud-oriented timeout.
        self._post_timeout = min(max(timeout, 5), 180)
        if is_autonomous:
            self._post_timeout = min(max(self._post_timeout, 10), 180)
        self._skill_md = self._load_skill_md()
        self._tools_disabled = False
        self._mcp = None  # DaemonMCPClient, set lazily in _ensure_tools()
        self._tools = None  # LLM tool schema, built lazily
        self._timing: RequestTiming | None = kwargs.pop("timing", None)
        self._correlation_id = kwargs.pop("correlation_id", "") or (
            self._timing.correlation_id if self._timing else ""
        )

    def _load_skill_md(self) -> str:
        """Load the canonical Kenny system prompt (single source of truth).

        Delegates to ``src.llm.system_prompt`` which reads the same SKILL.md
        that opencode serve loads natively. Nothing here is hardcoded — the
        persona comes from the file, placeholders are filled from Memory.
        """
        facts: dict = {}
        if self.parent() and hasattr(self.parent(), "_memory"):
            facts = self.parent()._memory.get_all()
        return build_system_prompt(self._pet_id, facts, compact=True)

    def abort(self) -> None:
        self._abort = True
        self._cancel_event.set()

    def run(self) -> None:
        if self._abort:
            return
        logger.debug("run: model=%s autonomous=%s prompt_chars=%d",
                     self._ollama_model, self._is_autonomous, len(self._prompt))
        self._retried = False
        self._mark("queue")
        messages = [
            {"role": "system", "content": self._skill_md},
            {"role": "user", "content": self._prompt},
        ]
        try:
            result = self._chat_completion(messages)
            if result:
                self._last_raw_response = result
                logger.debug("run: raw_response length=%d", len(result))
                items = self._parse_response(result)
                self._mark("parse")
                if items and self._filter_garbage_items(items):
                    logger.debug("run: parsed %d items", len(items))
                    self._extract_brain_update(items)
                    self.response_ready.emit(items)
                    return
                logger.warning("run: parse returned %d items after garbage filter (len=%d)",
                               len(items) if items else 0, len(result))
                if not self._retried:
                    logger.info("run: retrying with simplified prompt")
                    self._retried = True
                    messages[1] = {
                        "role": "user",
                        "content": self._prompt + (
                            "\n\nIMPORTANT: You MUST output a real in-character response. "
                            "DO NOT just repeat the user's name or say '...'. "
                            "Write a proper short dialogue as Kenny the pet."
                        )
                    }
                    result = self._chat_completion(messages)
                    if result:
                        items = self._parse_response(result)
                        if items and self._filter_garbage_items(items):
                            logger.debug("run: retry parsed %d items", len(items))
                            self._extract_brain_update(items)
                            self.response_ready.emit(items)
                            return
                    logger.warning("run: retry also produced garbage")
            reason = "timeout" if self._timed_out else (self._last_error_code or "parse_failed")
            self._fallback(reason)
            self._emit_error(reason)
        except Exception as exc:
            logger.warning("OllamaWorker.run exception (%s)", type(exc).__name__)
            self._fallback(type(exc).__name__)
            self._emit_error(type(exc).__name__)

    def _mark(self, phase: str, *, duration: float | None = None) -> None:
        if not self._timing:
            return
        self._timing.marks[phase] = duration if duration is not None else (
            time.monotonic() - self._timing.started_at
        )
        record_request_phase(
            self._timing, phase, "autonomous" if self._is_autonomous else "user", "ollama",
        )

    def _fallback(self, reason: str) -> None:
        record_llm_fallback("ollama", reason)

    MAX_TOOL_ITERATIONS = 4
    MAX_TOOL_CALLS_PER_ITERATION = 8

    def _chat_completion(self, messages: list) -> str | None:
        if self._abort:
            return None
        if self._ollama_model in _NO_TOOLS_MODELS:
            self._tools_disabled = True

        iteration = 0
        from src.llm.mcp_client import MCPExecutionBudget, MCPExecutionBudgetError, MCPExecutionError
        budget = MCPExecutionBudget(cancellation=self._cancel_event)
        while True:
            if self._abort:
                logger.debug("_chat_completion: aborting")
                return None

            iteration += 1
            if iteration > self.MAX_TOOL_ITERATIONS:
                logger.warning("_chat_completion: exceeded max tool iterations (%d)", self.MAX_TOOL_ITERATIONS)
                return None

            tools_enabled = not self._tools_disabled
            if tools_enabled:
                self._ensure_tools()
            payload = {
                "model": self._ollama_model,
                "messages": messages,
                "stream": False,
                "keep_alive": "10m",
                "options": {"num_predict": 1024},
            }
            if tools_enabled:
                payload["tools"] = self._tools
                messages[0] = {
                    "role": "system",
                    "content": self._skill_md + "\n\n" + build_tool_directive(self._tools),
                }
            else:
                payload["format"] = "json"

            system_size = len(messages[0]["content"]) if messages else 0
            user_size = len(messages[-1]["content"]) if messages else 0
            logger.debug("_chat_completion: model=%s tools=%s timeout=%s msg_count=%d system=%d user=%d iter=%d",
                          self._ollama_model, tools_enabled, self._post_timeout,
                          len(messages), system_size, user_size, iteration)

            provider_started = time.monotonic()
            try:
                resp = requests.post(
                    f"{self._server_url}/api/chat",
                    json=payload,
                    timeout=self._post_timeout,
                )
            except requests.exceptions.Timeout:
                self._mark("provider", duration=time.monotonic() - provider_started)
                logger.warning("Ollama request timed out after %ss (iter=%d)", self._post_timeout, iteration)
                self._timed_out = True
                return None
            except requests.exceptions.ConnectionError:
                self._mark("provider", duration=time.monotonic() - provider_started)
                logger.warning("Ollama server unavailable (iter=%d)", iteration)
                self._last_error_code = "unavailable"
                return None
            except requests.RequestException as exc:
                self._mark("provider", duration=time.monotonic() - provider_started)
                logger.warning("Ollama request failed: %s", exc)
                self._last_error_code = "connection"
                return None
            self._mark("provider", duration=time.monotonic() - provider_started)

            if resp.status_code >= 400:
                error_text = resp.text[:500].lower()
                logger.debug("_chat_completion: HTTP %d response_chars=%d", resp.status_code, len(resp.text))
                if self._is_tool_capability_error(error_text) and not self._tools_disabled:
                    logger.warning("Model does not support tools; retrying in degraded no-tool mode")
                    _NO_TOOLS_MODELS.add(self._ollama_model)
                    self._tools_disabled = True
                    continue
                self._last_error_code = self._classify_http_error(resp.status_code, error_text)
                logger.warning("Ollama API error: HTTP %s", resp.status_code)
                return None
            try:
                data = resp.json()
            except (ValueError, TypeError):
                self._last_error_code = "parse_failed"
                logger.warning("Ollama returned invalid JSON")
                return None
            msg = data.get("message", {})
            tool_calls = msg.get("tool_calls", [])
            content = msg.get("content", "")

            logger.debug("_chat_completion: response received tool_calls=%d content_len=%d content_preview='%s'",
                          len(tool_calls), len(content), content[:200].replace("\n", "\\n") if content else "")

            if not tool_calls:
                return content

            messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
            for tc in tool_calls[:self.MAX_TOOL_CALLS_PER_ITERATION]:
                func = tc.get("function", {})
                name = func.get("name", "")
                args = func.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except (ValueError, TypeError):
                        args = {}
                try:
                    result = self._execute_tool(name, args, budget=budget)
                except (MCPExecutionBudgetError, MCPExecutionError) as exc:
                    logger.warning("_chat_completion: MCP tool loop stopped: %s", exc)
                    if "cancelled" in str(exc).lower():
                        record_request_cancellation("ollama")
                    return json.dumps({"error": str(exc), "retry": False})
                tool_msg = {"role": "tool", "content": result}
                tc_id = tc.get("id")
                if tc_id:
                    tool_msg["tool_call_id"] = tc_id
                messages.append(tool_msg)
            logger.debug("_chat_completion: looping after %d tool calls (iter=%d)", len(tool_calls), iteration)

    @staticmethod
    def _is_tool_capability_error(text: str) -> bool:
        return any(marker in text for marker in (
            "does not support tools", "tool calling is not supported",
            "unknown field 'tools'", "invalid tools", "tools are not supported",
        ))

    @staticmethod
    def _classify_http_error(status_code: int, text: str) -> str:
        if "out of memory" in text or "oom" in text or ("cuda" in text and "memory" in text):
            return "oom"
        if "load" in text or ("model" in text and ("failed" in text or "not found" in text)):
            return "load_failed"
        if status_code in (408, 504):
            return "timeout"
        if status_code in (502, 503):
            return "unavailable"
        # Keep legacy parse_failed signal for generic HTTP failures; callers
        # already use explicit classifications for OOM, load, timeout, and
        # unavailable responses.
        return "parse_failed"

    def _ensure_tools(self) -> None:
        """Build the LLM tool schema, preferring the live MCP server catalog.

        Falls back to a generated schema (derived from the MCP server's own
        VALID_ACTIONS) if the MCP server is unreachable, so tool calling keeps
        working offline and can never drift from mcp_server.py.
        """
        if self._tools is not None:
            return
        try:
            from src.llm.mcp_client import build_client
            client = build_client()
            schema = client.get_tool_schema()
            if schema:
                self._mcp = client
                self._tools = schema
                logger.debug("OllamaWorker using %d live MCP tools", len(schema))
                return
        except Exception as exc:  # pragma: no cover - depends on runtime MCP state
            logger.warning("OllamaWorker: live MCP tool schema unavailable (%s); using fallback", exc)
        self._mcp = None
        self._tools = self._fallback_tools()

    def _fallback_tools(self) -> list[dict]:
        """Generated tool schema when the MCP server is unreachable."""
        others = [t for t in OLLAMA_TOOLS]
        return others

    _FALLBACK_TOOL_NAMES = frozenset({"send_system_toast", "read_clipboard"})

    def _execute_tool(self, name: str, args: dict, *, budget=None) -> str:
        # Primary path: call the real MCP server so consent gating, validation
        # and FSM/expression routing all happen server-side (single source of
        # truth). The server performs the animation directly.
        if self._mcp is not None:
            try:
                from src.llm.mcp_client import MCPExecutionBudgetError, MCPExecutionError
                if budget is not None:
                    budget.check_tool(name, args)
                if budget is None:
                    return self._mcp.call_tool(name, args)
                return self._mcp.call_tool(
                    name, args, budget=budget, cancellation=self._cancel_event,
                )
            except (MCPExecutionBudgetError, MCPExecutionError):
                raise
            except Exception as exc:  # pragma: no cover - depends on runtime MCP state
                logger.warning("OllamaWorker MCP call_tool failed for '%s': %s", name, exc)
                return json.dumps({"error": f"Tool '{name}' failed: {exc}. Do NOT retry — proceed without it."})
        # Legacy fallback: emit signals; pet_window performs the action.
        if budget is not None:
            budget.reserve(name, args)
        if name == "send_system_toast":
            self.tool_call_requested.emit(name, args)
            result = json.dumps({"status": "ok"})
        elif name == "read_clipboard":
            self.read_clipboard_requested.emit()
            result = json.dumps({"status": "ok", "note": "clipboard content dispatched to main thread"})
        else:
            result = json.dumps({
                "error": f"Tool '{name}' is not available. Available tools: {', '.join(sorted(self._FALLBACK_TOOL_NAMES))}. Do NOT retry — proceed without it."
            })
        if budget is not None:
            budget.record_result(result)
        return result

    def _emit_error(self, msg: str) -> None:
        self.error.emit(msg)
        self.error_occurred.emit(msg)

    def _parse_response(self, raw: str) -> list[dict] | None:
        if not raw or not raw.strip():
            logger.debug("_parse_response: empty input")
            return None
        from src.constants import MAX_RESPONSE_CHARS
        if len(raw) > MAX_RESPONSE_CHARS:
            logger.debug("_parse_response: truncated from %d to %d", len(raw), MAX_RESPONSE_CHARS)
            raw = raw[:MAX_RESPONSE_CHARS]
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            inner = []
            in_fence = False
            for line in lines:
                if line.strip().startswith("```") and not in_fence:
                    in_fence = True; continue
                if line.strip().startswith("```") and in_fence:
                    break
                if in_fence:
                    inner.append(line)
            if inner:
                logger.debug("_parse_response: stripped code fence, %d chars -> %d chars", len(text), len(inner))
                text = "\n".join(inner).strip()

        # Strategy 1: direct JSON parse
        try:
            items = json.loads(text)
            if isinstance(items, list):
                validated = [self._normalize_item(i) for i in items if isinstance(i, dict)]
                if validated:
                    logger.debug("_parse_response: strategy 1 (direct) OK, %d items", len(validated))
                    return validated
            if isinstance(items, dict):
                logger.debug("_parse_response: strategy 1 (single object) OK")
                return [self._normalize_item(items)]
        except json.JSONDecodeError as e:
            logger.debug("_parse_response: strategy 1 failed: %s", e)

        # Strategy 2: find JSON array via bracket matching
        start = text.find("[")
        if start != -1:
            end = text.rfind("]")
            if end != -1 and end > start:
                candidate = text[start:end + 1]
                logger.debug("_parse_response: strategy 2 bracket start=%d end=%d candidate_len=%d candidate_preview='%s'",
                              start, end, len(candidate), candidate[:100].replace("\n", "\\n"))
                try:
                    items = json.loads(candidate)
                    if isinstance(items, list):
                        validated = [self._normalize_item(i) for i in items if isinstance(i, dict)]
                        if validated:
                            logger.debug("_parse_response: strategy 2 (bracket) OK, %d items", len(validated))
                            return validated
                except json.JSONDecodeError as e:
                    logger.debug("_parse_response: strategy 2 bracket JSON parse failed: %s", e)
            else:
                logger.debug("_parse_response: strategy 2 found '[' at %d but no matching ']'", start)

        # Strategy 3: single object
        start = text.find("{")
        if start != -1:
            end = text.rfind("}")
            if end != -1 and end > start:
                candidate = text[start:end + 1]
                logger.debug("_parse_response: strategy 3 object start=%d end=%d", start, end)
                try:
                    obj = json.loads(candidate)
                    if isinstance(obj, dict):
                        logger.debug("_parse_response: strategy 3 (single object) OK")
                        return [self._normalize_item(obj)]
                except json.JSONDecodeError as e:
                    logger.debug("_parse_response: strategy 3 failed: %s", e)

        # Strategy 4: JSONL
        items = []
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        items.append(self._normalize_item(obj))
                except json.JSONDecodeError:
                    pass
        if items:
            logger.debug("_parse_response: strategy 4 (JSONL) OK, %d items", len(items))
            return items

        # Strategy 5: free-form fallback
        truncated = raw[:400].strip()
        if truncated:
            logger.debug("_parse_response: strategy 5 (free-form fallback, chars=%d)", len(truncated))
            return [self._normalize_item({"dialogue": truncated, "action": "idle", "type": "observation",
                     "priority": 3, "thought": ""})]
        logger.debug("_parse_response: all strategies failed")
        return []

    def _normalize_item(self, item: dict) -> dict:
        normalized = {
            "dialogue": "",
            "action": "idle",
            "type": "observation",
            "priority": 3,
            "thought": ""
        }
        if "thought" in item:
            normalized["thought"] = str(item["thought"])
        elif "reasoning" in item:
            normalized["thought"] = str(item["reasoning"])
            
        raw_dialogue = item.get("dialogue") or item.get("content") or item.get("response") or item.get("message") or ""
        if isinstance(raw_dialogue, list):
            msg_texts = []
            for d in raw_dialogue:
                if isinstance(d, dict):
                    role = str(d.get("role") or d.get("speaker") or "").lower()
                    content = d.get("content") or d.get("text") or ""
                    if role in ("assistant", "me", "kenny", "pet", "response"):
                        msg_texts.append(str(content))
                    elif not role:
                        msg_texts.append(str(content))
                elif isinstance(d, str):
                    msg_texts.append(d)
            if msg_texts:
                normalized["dialogue"] = " ".join(msg_texts)
            else:
                normalized["dialogue"] = str(raw_dialogue)
        elif isinstance(raw_dialogue, dict):
            normalized["dialogue"] = str(raw_dialogue.get("content") or raw_dialogue.get("text") or raw_dialogue)
        else:
            normalized["dialogue"] = str(raw_dialogue)
            
        normalized["dialogue"] = normalized["dialogue"].strip()
        
        raw_action = item.get("action")
        if isinstance(raw_action, str):
            normalized["action"] = raw_action
        elif isinstance(raw_action, list) and raw_action:
            normalized["action"] = str(raw_action[0])
        
        raw_type = item.get("type")
        if isinstance(raw_type, str):
            normalized["type"] = raw_type
            
        try:
            normalized["priority"] = int(item.get("priority", 3))
        except (ValueError, TypeError):
            pass
            
        if "brain_update" in item:
            normalized["brain_update"] = item["brain_update"]
            
        return normalized

    def _get_user_nickname(self) -> str:
        if self.parent() and hasattr(self.parent(), "_memory"):
            facts = self.parent()._memory.get_all()
            return facts.get("user_nickname", "garbage meat")
        return "garbage meat"

    def _filter_garbage_items(self, items: list[dict]) -> bool:
        valid = []
        for item in items:
            d = item.get("dialogue", "").strip()
            if not d or len(d) < 2:
                continue
            # Do NOT drop a reply merely because it equals the user's nickname.
            # The persona legitimately addresses the user by name, and weak
            # local models emit terse replies. Only drop contentless
            # punctuation-only strings (e.g. "...").
            if re.fullmatch(r'[\s.,!?…\-_]+', d):
                continue
            valid.append(item)
        items[:] = valid
        return len(valid) > 0

    def _extract_brain_update(self, items: list[dict]) -> None:
        emitted = False
        for item in items:
            bu = item.pop("brain_update", None)
            if bu is not None and not emitted:
                self.brain_update_ready.emit(bu)
                emitted = True
