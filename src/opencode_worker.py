from __future__ import annotations
import json
import logging
import re
import requests
from PyQt6.QtCore import QThread, pyqtSignal
from src.config import load_config, DEFAULT_SERVER_URL

logger = logging.getLogger(__name__)


class OpencodeWorker(QThread):
    response_ready = pyqtSignal(list)

    error_occurred = pyqtSignal(str)
    session_created = pyqtSignal(str)
    path_used = pyqtSignal(str)
    brain_update_ready = pyqtSignal(dict)
    pool_items_ready = pyqtSignal(dict)
    session_turn_completed = pyqtSignal(object, object, object)  # session_state, user_input, response_text

    def __init__(self, user_input: str, context_hint: str = "", apm: int = 0,
                 is_autonomous: bool = False, parent=None,
                 session_id: str | None = None,
                 prompt: str | None = None,
                 typing_content: str = "",
                 two_stage_prompts: tuple[str, str] | None = None,
                 config: dict | None = None,
                 session_state: object = None) -> None:
        super().__init__(parent)
        self._user_input = user_input
        self._context_hint = context_hint
        self._apm = apm
        self._is_autonomous = is_autonomous
        self._session_id = session_id or (session_state.session_id if session_state else None)
        self._prebuilt_prompt = prompt
        self._typing_content = typing_content
        self._used_api = False
        self._two_stage = two_stage_prompts
        self._abort = False
        self._config = config if config is not None else load_config()
        self._session_state = session_state

    def abort(self) -> None:
        self._abort = True
        # Clean up opencode session if we created one
        if self._session_id:
            try:
                import requests
                from src.config import load_config
                config = load_config()
                server_url = config.get("llm", {}).get("server_url") or DEFAULT_SERVER_URL
                requests.delete(
                    f"{server_url}/session/{self._session_id}",
                    timeout=5,
                )
                logger.debug("Cleaned up session %s on abort", self._session_id)
            except Exception as e:
                logger.debug("Failed to clean up session on abort: %s", e)

    def _post_message(self, payload: dict, is_refill: bool = False) -> str | None:
        session_id = self._session_id
        if self._abort:
            return None
        llm_cfg = self._config.get("llm", {})
        server_url = llm_cfg.get("server_url") or DEFAULT_SERVER_URL
        model_id = llm_cfg.get("model_id", "")
        # Use longer timeout for refill operations (two-stage takes 2x API calls)
        timeout_sec = llm_cfg.get("timeout_sec", 180)
        if is_refill:
            timeout_sec = max(timeout_sec, 300)  # 5 minutes for refill
        try:
            if not session_id:
                if self._abort:
                    return None
                logger.info("API: creating session at %s/session", server_url)
                session_payload = {"skill": "kenny"}
                if model_id:
                    session_payload["agent"] = model_id
                r = requests.post(
                    f"{server_url}/session",
                    json=session_payload,
                    timeout=timeout_sec,
                )
                if r.status_code >= 400:
                    logger.warning("API session create failed: %s %s", r.status_code, r.text[:200])
                    return None
                session_id = r.json().get("id")
                if not session_id:
                    logger.warning("API session create returned no id: %s", r.text[:200])
                    return None
                self._session_id = session_id
                self.session_created.emit(session_id)
                logger.info("API: created session %s", session_id)

            if self._abort:
                return None
            logger.info("API: posting message to session %s", session_id)
            r = requests.post(
                f"{server_url}/session/{session_id}/message",
                json=payload,
                timeout=timeout_sec,
            )
            if r.status_code >= 400:
                logger.warning("API message failed: %s %s", r.status_code, r.text[:200])
                # If 500 error or 404 (session not found), invalidate session and retry once
                if r.status_code in (500, 404) and session_id:
                    logger.info("Server error or session lost, invalidating session and retrying once")
                    self._session_id = None
                    # Retry once with new session
                    return self._post_message(payload)
                if not self._is_autonomous:
                    self.error_occurred.emit(f"API failed with HTTP {r.status_code}")
                return None

            data = r.json()
            parts = data.get("parts") or []
            text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
            if not text:
                logger.debug("API response had no text parts")
                return None
            logger.info("API: received %s chars", len(text))
            return text
        except requests.exceptions.ConnectionError as e:
            logger.warning("API connection error: %s", e)
            if not self._is_autonomous:
                self.error_occurred.emit("Lost connection to opencode server.")
            return None
        except requests.exceptions.Timeout as e:
            logger.warning("API timeout: %s", e)
            if not self._is_autonomous:
                self.error_occurred.emit("OpenCode API timed out. Rate limit exceeded?")
            return None
        except requests.exceptions.RequestException as e:
            logger.warning("API request error: %s", e)
            return None
        except (ValueError, KeyError) as e:
            logger.warning("API response parse error: %s", e)
            return None

    def send(self, prompt: str) -> None:
        if self._abort:
            return
        from src.constants import STRUCTURED_SCHEMA
        llm_cfg = self._config.get("llm", {})
        provider = llm_cfg.get("provider", "")
        model_id = llm_cfg.get("model_id", "")

        # Prepend previous conversation history as context if resuming
        history_ctx = ""
        if self._session_state and hasattr(self._session_state, "history_context"):
            history_ctx = self._session_state.history_context
        if history_ctx:
            prompt = f"{history_ctx}\n\n[Current message]\n{prompt}"

        payload = {
            "parts": [{"type": "text", "text": prompt}],
            "structured": STRUCTURED_SCHEMA,
        }
        # Note: We omit passing payload["model"] because OpenCode server 
        # crashes with HTTP 500 when overriding with OpenRouter models.
        # It automatically uses the primary agent defined in opencode.json.
        logger.debug("SEND payload prompt (first 500): %s", prompt[:500])
        logger.debug("SEND payload full: %s", json.dumps(payload, indent=2)[:2000])
        raw = self._post_message(payload, is_refill=self._is_autonomous)
        if self._abort:
            return
        if raw:
            logger.debug("RECV raw (first 1000): %s", raw[:1000])
            self._used_api = True
            self.path_used.emit("api")
            items = self._parse_json_response(raw)
            if items is not None:
                logger.debug("RECV parsed: %d items, first: %s", len(items), json.dumps(items[0] if items else {}))
                # Emit turn data for persistence
                self._emit_turn_completed(prompt, raw)
                self.response_ready.emit(items)
                return
            items = self._handle_schema_error(raw)
            self._emit_turn_completed(prompt, raw)
            self.response_ready.emit(items)
        else:
            logger.warning("send: API returned empty or None")

    def _emit_turn_completed(self, user_prompt: str, response_text: str) -> None:
        """Emit session_turn_completed signal if session_state is available."""
        if self._session_state and hasattr(self._session_state, "add_turn"):
            try:
                from src.llm_session_persistence import LLMSessionState
                if isinstance(self._session_state, LLMSessionState):
                    self._session_state.session_id = self._session_id
                    self.session_turn_completed.emit(self._session_state, user_prompt, response_text)
            except ImportError:
                pass

    def _send_two_stage(self) -> None:
        """DEPRECATED — no longer called (refill uses single prompt now).

        Kept for backward compatibility. Removed when no external callers remain.
        """
        if self._abort:
            return
        logger.debug("[VERIFY] two-stage agentic refill: starting stage1 (investigation, no JSON constraint)")
        from src.constants import STRUCTURED_SCHEMA
        stage1, stage2 = self._two_stage
        llm_cfg = self._config.get("llm", {})
        provider = llm_cfg.get("provider", "")
        model_id = llm_cfg.get("model_id", "")
        payload1 = {
            "parts": [{"type": "text", "text": stage1}],
        }
        # Omit model override (see above)
        raw1 = self._post_message(payload1, is_refill=True)
        if self._abort:
            return
        if raw1 is None:
            self.response_ready.emit([])
            return
        self._used_api = True
        self.path_used.emit("api")

        logger.debug("[VERIFY] two-stage agentic refill: stage1 complete (%d chars), now sending stage2 with structured schema", len(raw1))
        enriched = f"[Investigation results]\n{raw1}\n\n[Generation task]\n{stage2}"
        payload2 = {
            "parts": [{"type": "text", "text": enriched}],
            "structured": STRUCTURED_SCHEMA,
        }
        # Omit model override
        raw2 = self._post_message(payload2, is_refill=True)
        if self._abort:
            return
        if raw2 is None:
            self.response_ready.emit([])
            return

        items = self._parse_json_response(raw2)
        if items is not None:
            self.response_ready.emit(items)
            return
        items = self._handle_schema_error(raw2)
        self.response_ready.emit(items)

    def _parse_json_response(self, raw: str) -> list[dict] | None:
        """Parse JSON response from LLM with multiple fallback strategies.

        Returns parsed list of dicts or None if all parsing fails.
        On failure, logs detailed diagnostic info (line, column, context).
        """
        cleaned = raw.strip()

        # 1. Strip markdown code fences
        for fence in ("```json", "```"):
            if cleaned.startswith(fence):
                cleaned = cleaned[len(fence):]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        # 2. Direct JSON parse
        try:
            items = json.loads(cleaned)
            if isinstance(items, list):
                if self._validate_items(items):
                    return items
                logger.debug("Parsed JSON but validation failed: %s", cleaned[:200])
        except json.JSONDecodeError as e:
            logger.warning(
                "JSON decode error at line %d col %d: %s",
                e.lineno, e.colno, e.msg,
            )
            # Log context around the error position
            lines = cleaned.split('\n')
            start = max(0, (e.lineno or 1) - 3)
            end = min(len(lines), (e.lineno or 1) + 2)
            ctx = '\n'.join(
                f"{i+1}| {lines[i]}" for i in range(start, end)
            )
            logger.debug("JSON parse context around error:\n%s", ctx)

        # 3. Regex extraction for array of objects (more precise)
        # Match: [ { ... }, { ... }, ... ] with proper bracket nesting
        try:
            # Find the outermost array brackets
            start = cleaned.find('[')
            if start != -1:
                bracket_count = 0
                end = -1
                for i, ch in enumerate(cleaned[start:], start):
                    if ch == '[':
                        bracket_count += 1
                    elif ch == ']':
                        bracket_count -= 1
                        if bracket_count == 0:
                            end = i + 1
                            break
                if end != -1:
                    candidate = cleaned[start:end]
                    items = json.loads(candidate)
                    if isinstance(items, list) and self._validate_items(items):
                        return items
        except (json.JSONDecodeError, ValueError):
            pass

        logger.warning(
            "All JSON parsing strategies failed for response (first 500 chars): %s",
            raw[:500],
        )
        return None

    def _validate_items(self, items: list[Any]) -> bool:
        """Validate parsed items against STRUCTURED_SCHEMA requirements."""
        if not isinstance(items, list):
            return False
        for item in items:
            if not isinstance(item, dict):
                return False
            if "thought" not in item or "dialogue" not in item:
                return False
            if not isinstance(item["thought"], str) or not isinstance(item["dialogue"], str):
                return False
        return True

    def _handle_schema_error(self, raw_response: str) -> list[dict]:
        logger.warning("All JSON parsing failed, returning fallback. Raw: %s", raw_response[:500])
        return [{
            "thought": "Kenny's brain just bluescreened.",
            "dialogue": "Holy crap, my brain just segfaulted!",
        }]

    def run(self) -> None:
        if self._two_stage is not None:
            self._send_two_stage()
            return
        if self._prebuilt_prompt is not None:
            self.send(self._prebuilt_prompt)
