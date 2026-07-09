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
                return skill_path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to load SKILL.md from %s: %s", skill_path, exc)
        return self._default_skill_fallback()

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
        messages = [
            {"role": "system", "content": self._skill_md},
            {"role": "user", "content": self._prompt},
        ]
        try:
            result = self._chat_completion(messages)
            if result:
                self._last_raw_response = result
                items = self._parse_response(result)
                if items:
                    self._extract_brain_update(items)
                    self.response_ready.emit(items)
                    return
            self._emit_error("parse_failed" if not self._timed_out else "timeout")
        except Exception as exc:
            logger.warning("OllamaWorker.run exception: %s", exc)
            self._emit_error(str(exc))

    def _chat_completion(self, messages: list) -> str | None:
        payload = {
            "model": self._ollama_model,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": 1024},
        }
        if not self._tools_disabled:
            payload["tools"] = OLLAMA_TOOLS

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
            return None
        from src.constants import MAX_RESPONSE_CHARS
        if len(raw) > MAX_RESPONSE_CHARS:
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
                text = "\n".join(inner).strip()
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
        truncated = raw[:400].strip()
        if truncated:
            return [{"dialogue": truncated, "action": "idle", "type": "observation",
                     "priority": 3, "thought": ""}]
        return []

    def _extract_brain_update(self, items: list[dict]) -> None:
        emitted = False
        for item in items:
            bu = item.pop("brain_update", None)
            if bu is not None and not emitted:
                self.brain_update_ready.emit(bu)
                emitted = True
