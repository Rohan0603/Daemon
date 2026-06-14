from __future__ import annotations
import json
import logging
import re
import requests
from PyQt6.QtCore import QThread, pyqtSignal
from src.config import load_config

logger = logging.getLogger(__name__)


class OpencodeWorker(QThread):
    response_ready = pyqtSignal(list)

    error_occurred = pyqtSignal(str)
    session_created = pyqtSignal(str)
    path_used = pyqtSignal(str)
    brain_update_ready = pyqtSignal(dict)
    pool_items_ready = pyqtSignal(dict)

    def __init__(self, user_input: str, context_hint: str = "", apm: int = 0,
                 is_autonomous: bool = False, parent=None,
                 session_id: str | None = None,
                 prompt: str | None = None,
                 typing_content: str = "",
                 two_stage_prompts: tuple[str, str] | None = None,
                 config: dict | None = None) -> None:
        super().__init__(parent)
        self._user_input = user_input
        self._context_hint = context_hint
        self._apm = apm
        self._is_autonomous = is_autonomous
        self._session_id = session_id
        self._prebuilt_prompt = prompt
        self._typing_content = typing_content
        self._used_api = False
        self._two_stage = two_stage_prompts
        self._abort = False
        self._config = config if config is not None else load_config()

    def abort(self) -> None:
        self._abort = True

    def _post_message(self, payload: dict) -> str | None:
        session_id = self._session_id
        if self._abort:
            return None
        llm_cfg = self._config.get("llm", {})
        server_url = llm_cfg.get("server_url", "http://127.0.0.1:4096")
        model_id = llm_cfg.get("model_id", "")
        timeout_sec = llm_cfg.get("timeout_sec", 180)
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
        payload = {
            "parts": [{"type": "text", "text": prompt}],
            "structured": STRUCTURED_SCHEMA,
        }
        # Note: We omit passing payload["model"] because OpenCode server 
        # crashes with HTTP 500 when overriding with OpenRouter models.
        # It automatically uses the primary agent defined in opencode.json.
        logger.debug("SEND payload prompt (first 500): %s", prompt[:500])
        logger.debug("SEND payload full: %s", json.dumps(payload, indent=2)[:2000])
        raw = self._post_message(payload)
        if self._abort:
            return
        if raw:
            logger.debug("RECV raw (first 1000): %s", raw[:1000])
            self._used_api = True
            self.path_used.emit("api")
            try:
                cleaned = raw.strip()
                for fence in ("```json", "```"):
                    if cleaned.startswith(fence):
                        cleaned = cleaned[len(fence):]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()
                items = json.loads(cleaned)
                if isinstance(items, list):
                    logger.debug("RECV parsed: %d items, first: %s", len(items), json.dumps(items[0] if items else {}))
                    self.response_ready.emit(items)
                    return
            except json.JSONDecodeError:
                logger.debug("RECV json parse failed (attempted stripped), raw: %s", raw[:500])
                pass
            try:
                match = re.search(r'\[\s*\{.*?\}\s*\]', raw, re.DOTALL)
                if match:
                    items = json.loads(match.group(0))
                    if isinstance(items, list):
                        logger.debug("RECV parsed via regex: %d items", len(items))
                        self.response_ready.emit(items)
                        return
            except (json.JSONDecodeError, AttributeError):
                logger.debug("RECV regex extraction also failed")
                pass
            items = self._handle_schema_error(raw)
            self.response_ready.emit(items)
        else:
            logger.warning("send: API returned empty or None")

    def _send_two_stage(self) -> None:
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
        raw1 = self._post_message(payload1)
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
        raw2 = self._post_message(payload2)
        if self._abort:
            return
        if raw2 is None:
            self.response_ready.emit([])
            return

        try:
            cleaned = raw2.strip()
            for fence in ("```json", "```"):
                if cleaned.startswith(fence):
                    cleaned = cleaned[len(fence):]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            items = json.loads(cleaned)
            if isinstance(items, list):
                self.response_ready.emit(items)
                return
        except json.JSONDecodeError:
            pass
        try:
            match = re.search(r'\[\s*\{.*?\}\s*\]', raw2, re.DOTALL)
            if match:
                items = json.loads(match.group(0))
                if isinstance(items, list):
                    self.response_ready.emit(items)
                    return
        except (json.JSONDecodeError, AttributeError):
            pass
        items = self._handle_schema_error(raw2)
        self.response_ready.emit(items)

    def _handle_schema_error(self, raw_response: str) -> list[dict]:
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
