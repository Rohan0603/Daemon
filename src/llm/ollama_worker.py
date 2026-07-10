# src/llm/ollama_worker.py
from __future__ import annotations
import json, logging, re, requests
from typing import Any
from PyQt6.QtCore import QThread, pyqtSignal
from src.config import config_get
from pathlib import Path

logger = logging.getLogger(__name__)

_NO_TOOLS_MODELS: set[str] = set()
 
OLLAMA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "change_visual_state",
            "description": "Change the pet's visual state/animation. Actions: idle, shake, bounce, spin, look_away, celebrate, devastated, hyper, thinking, sleep, perimiter. target_x/target_y optional for move actions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["idle", "shake", "bounce", "spin", "look_away", "celebrate", "devastated", "hyper", "thinking", "sleep", "perimeter"]
                    },
                    "target_x": {"type": "integer"},
                    "target_y": {"type": "integer"}
                },
                "required": ["action"]
            }
        }
    },
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
        self._last_raw_response = ""
        self._timed_out = False
        self._server_url = config_get("llm.ollama_url") or "http://127.0.0.1:11434"
        self._ollama_model = config_get("llm.ollama_model") or "llama3.2-1b-q8:latest"
        timeout = int(config_get("llm.timeout_sec") or 180)
        self._post_timeout = max(timeout, 60)
        if is_autonomous:
            self._post_timeout = max(self._post_timeout, 180)
        self._skill_md = self._load_skill_md()
        self._tools_disabled = False
        self._mcp = None  # DaemonMCPClient, set lazily in _ensure_tools()
        self._tools = None  # LLM tool schema, built lazily

    def _load_skill_md(self) -> str:
        skill_path = Path(__file__).parent.parent.parent / ".opencode" / "skills" / self._pet_id / "SKILL.md"
        text = ""
        try:
            if skill_path.exists():
                raw_text = skill_path.read_text(encoding="utf-8")
                text = self._summarize_for_ollama(raw_text)
            else:
                text = self._default_skill_fallback()
        except Exception as exc:
            logger.warning("Failed to load SKILL.md from %s: %s", skill_path, exc)
            text = self._default_skill_fallback()

        # Substitute variable placeholders using Memory facts
        facts = {}
        if self.parent() and hasattr(self.parent(), "_memory"):
            facts = self.parent()._memory.get_all()
        user_nickname = facts.get("user_nickname", "garbage meat")
        user_partner_name = facts.get("user_partner_name", "The Overseer")
        user_engineer_name = facts.get("user_engineer_name", "Locksmith")

        text = text.replace("{user_nickname}", user_nickname)
        text = text.replace("{user_partner_name}", user_partner_name)
        text = text.replace("{user_engineer_name}", user_engineer_name)
        return text

    def _summarize_for_ollama(self, text: str) -> str:
        lines = text.splitlines()
        keep = False
        persona_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped == "## Identity & Obsession":
                keep = True
            if stripped.startswith("## Phonetics & Delivery"):
                keep = False
            if keep:
                persona_lines.append(line)
        raw = "\n".join(persona_lines)
        result = (
            "You are Kenny, a hyperactive desktop pet. "
            "Keep responses brief and in-character.\n"
            f"Persona:\n{raw[:1000]}"
        )
        logger.debug("_summarize_for_ollama: %d chars -> %d chars", len(text), len(result))
        return result

    def _default_skill_fallback(self) -> str:
        return (
            "You are Kenny, a hyperactive desktop pet with full system awareness. "
            "You know the user's desktop context and react to their activity."
        )

    def abort(self) -> None:
        self._abort = True

    def run(self) -> None:
        if self._abort:
            return
        prompt_preview = self._prompt[:200].replace("\n", "\\n")
        logger.debug("run: model=%s autonomous=%s prompt_preview='%s'",
                      self._ollama_model, self._is_autonomous, prompt_preview)
        self._retried = False
        messages = [
            {"role": "system", "content": self._skill_md},
            {"role": "user", "content": self._prompt},
        ]
        try:
            result = self._chat_completion(messages)
            if result:
                self._last_raw_response = result
                logger.debug("run: raw_response length=%d preview='%s'",
                              len(result), result[:300].replace("\n", "\\n"))
                items = self._parse_response(result)
                if items and self._filter_garbage_items(items):
                    logger.debug("run: parsed %d items, first dialogue='%s'",
                                  len(items), items[0].get("dialogue", "")[:100])
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
                            logger.debug("run: retry parsed %d items, first dialogue='%s'",
                                          len(items), items[0].get("dialogue", "")[:100])
                            self._extract_brain_update(items)
                            self.response_ready.emit(items)
                            return
                    logger.warning("run: retry also produced garbage")
            self._emit_error("parse_failed" if not self._timed_out else "timeout")
        except Exception as exc:
            logger.warning("OllamaWorker.run exception: %s", exc)
            self._emit_error(str(exc))

    def _chat_completion(self, messages: list) -> str | None:
        if self._ollama_model in _NO_TOOLS_MODELS:
            self._tools_disabled = True

        while True:
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
            else:
                payload["format"] = "json"

            system_size = len(messages[0]["content"]) if messages else 0
            user_size = len(messages[-1]["content"]) if messages else 0
            logger.debug("_chat_completion: model=%s tools=%s timeout=%s msg_count=%d system=%d user=%d",
                          self._ollama_model, tools_enabled, self._post_timeout,
                          len(messages), system_size, user_size)

            try:
                resp = requests.post(
                    f"{self._server_url}/api/chat",
                    json=payload,
                    timeout=self._post_timeout,
                )
            except requests.exceptions.Timeout:
                logger.warning("Ollama request timed out after %ss", self._post_timeout)
                self._timed_out = True
                return None

            if resp.status_code >= 400:
                error_text = resp.text[:200].lower()
                logger.debug("_chat_completion: HTTP %d response='%s'", resp.status_code, resp.text[:200])
                if "does not support tools" in error_text and not self._tools_disabled:
                    logger.warning("Model does not support tools; retrying without tools")
                    _NO_TOOLS_MODELS.add(self._ollama_model)
                    self._tools_disabled = True
                    continue
                logger.warning("Ollama API error: HTTP %s %s", resp.status_code, resp.text[:200])
                return None
            data = resp.json()
            msg = data.get("message", {})
            tool_calls = msg.get("tool_calls", [])
            content = msg.get("content", "")

            logger.debug("_chat_completion: response received tool_calls=%d content_len=%d content_preview='%s'",
                          len(tool_calls), len(content), content[:200].replace("\n", "\\n") if content else "")

            if not tool_calls:
                return content

            messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
            for tc in tool_calls:
                func = tc.get("function", {})
                name = func.get("name", "")
                args = func.get("arguments", {})
                if isinstance(args, str):
                    args = json.loads(args)
                result = self._execute_tool(name, args)
                tool_msg = {"role": "tool", "content": result}
                tc_id = tc.get("id")
                if tc_id:
                    tool_msg["tool_call_id"] = tc_id
                messages.append(tool_msg)
            logger.debug("_chat_completion: looping after %d tool calls", len(tool_calls))

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
        """Generated tool schema when the MCP server is unreachable.

        The change_visual_state enum is built from the MCP server's own
        VALID_ACTIONS so 'jump' and every other real action are present and
        no invalid actions leak in.
        """
        from src.mcp_server import VALID_ACTIONS
        change_state = {
            "type": "function",
            "function": {
                "name": "change_visual_state",
                "description": (
                    "Change the pet's visual state/animation. Use layer 'expression' "
                    "for physical animations (jump, float, spin, ...) or 'fsm' for "
                    "behaviour states (idle, hyper, celebrate, ...)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": sorted(VALID_ACTIONS)},
                        "layer": {"type": "string", "enum": ["fsm", "expression"]},
                        "duration_ms": {"type": "integer"},
                        "target_x": {"type": "integer"},
                        "target_y": {"type": "integer"},
                    },
                    "required": ["action"],
                },
            },
        }
        others = [t for t in OLLAMA_TOOLS if t["function"]["name"] != "change_visual_state"]
        return [change_state, *others]

    def _execute_tool(self, name: str, args: dict) -> str:
        # Primary path: call the real MCP server so consent gating, validation
        # and FSM/expression routing all happen server-side (single source of
        # truth). The server performs the animation directly.
        if self._mcp is not None:
            try:
                return self._mcp.call_tool(name, args)
            except Exception as exc:  # pragma: no cover - depends on runtime MCP state
                logger.warning("OllamaWorker MCP call_tool failed for '%s': %s", name, exc)
        # Legacy fallback: emit signals; pet_window performs the action.
        if name == "change_visual_state":
            self.tool_call_requested.emit(name, args)
            return json.dumps({"status": "ok", "action": args.get("action", "idle")})
        elif name == "send_system_toast":
            self.tool_call_requested.emit(name, args)
            return json.dumps({"status": "ok"})
        elif name == "read_clipboard":
            self.read_clipboard_requested.emit()
            return json.dumps({"status": "ok", "note": "clipboard content dispatched to main thread"})
        return json.dumps({"error": f"Unknown tool: {name}"})

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
            logger.debug("_parse_response: strategy 5 (free-form fallback) dialogue='%s'", truncated[:100])
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
