# src/llm/ollama_worker.py
from __future__ import annotations
import json, logging, requests
from typing import Any
from PyQt6.QtCore import QThread, pyqtSignal
from src.config import config_get
from pathlib import Path

logger = logging.getLogger(__name__)
 
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
        self._ollama_model = config_get("llm.ollama_model") or "daemon-local"
        timeout = int(config_get("llm.timeout_sec") or 180)
        self._post_timeout = max(timeout, 60)
        if is_autonomous:
            self._post_timeout = max(self._post_timeout, 180)
        self._skill_md = self._load_skill_md()
        self._tools_disabled = False

    def _load_skill_md(self) -> str:
        skill_path = Path(__file__).parent.parent.parent / ".opencode" / "skills" / self._pet_id / "SKILL.md"
        try:
            if skill_path.exists():
                text = skill_path.read_text(encoding="utf-8")
                return self._strip_opencode_sections(text)
        except Exception as exc:
            logger.warning("Failed to load SKILL.md from %s: %s", skill_path, exc)
        return self._default_skill_fallback()

    def _strip_opencode_sections(self, text: str) -> str:
        lines = text.splitlines()
        keep = True
        stripped = []
        for line in lines:
            if line.strip().startswith("## Two-Stage Output Mode"):
                keep = False
            if line.strip().startswith("## Dialogue Examples"):
                keep = True
            if keep:
                stripped.append(line)
        result = "\n".join(stripped)
        logger.debug("_strip_opencode_sections: %d chars -> %d chars", len(text), len(result))
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
                if items:
                    logger.debug("run: parsed %d items, first dialogue='%s'",
                                  len(items), items[0].get("dialogue", "")[:100])
                    self._extract_brain_update(items)
                    self.response_ready.emit(items)
                    return
                logger.warning("run: parse returned None for response of len=%d", len(result))
            self._emit_error("parse_failed" if not self._timed_out else "timeout")
        except Exception as exc:
            logger.warning("OllamaWorker.run exception: %s", exc)
            self._emit_error(str(exc))

    def _chat_completion(self, messages: list) -> str | None:
        tools_enabled = not self._tools_disabled
        payload = {
            "model": self._ollama_model,
            "messages": messages,
            "stream": False,
            "keep_alive": "10m",
            "options": {"num_predict": 1024},
        }
        if tools_enabled:
            payload["tools"] = OLLAMA_TOOLS

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
                self._tools_disabled = True
                return self._chat_completion(messages)
            logger.warning("Ollama API error: HTTP %s %s", resp.status_code, resp.text[:200])
            return None
        data = resp.json()
        msg = data.get("message", {})
        tool_calls = msg.get("tool_calls", [])
        content = msg.get("content", "")

        logger.debug("_chat_completion: response received tool_calls=%d content_len=%d content_preview='%s'",
                      len(tool_calls), len(content), content[:200].replace("\n", "\\n") if content else "")

        if tool_calls:
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
            logger.debug("_chat_completion: recursing after %d tool calls", len(tool_calls))
            return self._chat_completion(messages)

        return content

    def _execute_tool(self, name: str, args: dict) -> str:
        if name == "change_visual_state":
            action = args.get("action", "idle")
            self.tool_call_requested.emit(name, args)
            return json.dumps({"status": "ok", "action": action})
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
                validated = [i for i in items if isinstance(i, dict)]
                if validated:
                    logger.debug("_parse_response: strategy 1 (direct) OK, %d items", len(validated))
                    return validated
            if isinstance(items, dict):
                logger.debug("_parse_response: strategy 1 (single object) OK")
                return [items]
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
                        validated = [i for i in items if isinstance(i, dict)]
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
                        return [obj]
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
                        items.append(obj)
                except json.JSONDecodeError:
                    pass
        if items:
            logger.debug("_parse_response: strategy 4 (JSONL) OK, %d items", len(items))
            return items

        # Strategy 5: free-form fallback
        truncated = raw[:400].strip()
        if truncated:
            logger.debug("_parse_response: strategy 5 (free-form fallback) dialogue='%s'", truncated[:100])
            return [{"dialogue": truncated, "action": "idle", "type": "observation",
                     "priority": 3, "thought": ""}]
        logger.debug("_parse_response: all strategies failed")
        return []

    def _extract_brain_update(self, items: list[dict]) -> None:
        emitted = False
        for item in items:
            bu = item.pop("brain_update", None)
            if bu is not None and not emitted:
                self.brain_update_ready.emit(bu)
                emitted = True
