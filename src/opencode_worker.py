from __future__ import annotations
import json
import logging
import re
import requests
from PyQt6.QtCore import QThread, pyqtSignal
from src.constants import (
    OPENCODE_SERVER_URL,
    OPENCODE_API_MODEL_PROVIDER,
    OPENCODE_API_MODEL_ID,
    OPENCODE_API_TIMEOUT_SEC,
)


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
                 typing_content: str = "") -> None:
        super().__init__(parent)
        self._user_input = user_input
        self._context_hint = context_hint
        self._apm = apm
        self._is_autonomous = is_autonomous
        self._session_id = session_id
        self._prebuilt_prompt = prompt
        self._typing_content = typing_content
        self._used_api = False

    def _post_message(self, payload: dict) -> str | None:
        session_id = self._session_id
        try:
            if not session_id:
                logger.info("API: creating session at %s/session", OPENCODE_SERVER_URL)
                r = requests.post(
                    f"{OPENCODE_SERVER_URL}/session",
                    json={"title": "Daemon Pet"},
                    timeout=OPENCODE_API_TIMEOUT_SEC,
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

            logger.info("API: posting message to session %s", session_id)
            r = requests.post(
                f"{OPENCODE_SERVER_URL}/session/{session_id}/message",
                json=payload,
                timeout=OPENCODE_API_TIMEOUT_SEC,
            )
            if r.status_code >= 400:
                logger.warning("API message failed: %s %s", r.status_code, r.text[:200])
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
            return None
        except requests.exceptions.Timeout as e:
            logger.warning("API timeout: %s", e)
            return None
        except requests.exceptions.RequestException as e:
            logger.warning("API request error: %s", e)
            return None
        except (ValueError, KeyError) as e:
            logger.warning("API response parse error: %s", e)
            return None

    def send(self, prompt: str) -> None:
        from src.constants import STRUCTURED_SCHEMA
        payload = {
            "model": {
                "providerID": OPENCODE_API_MODEL_PROVIDER,
                "modelID": OPENCODE_API_MODEL_ID,
            },
            "parts": [{"type": "text", "text": prompt}],
            "structured": STRUCTURED_SCHEMA,
        }
        logger.debug("SEND payload prompt (first 500): %s", prompt[:500])
        logger.debug("SEND payload full: %s", json.dumps(payload, indent=2)[:2000])
        raw = self._post_message(payload)
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

    def _handle_schema_error(self, raw_response: str) -> list[dict]:
        return [{
            "thought": "Kenny's brain just bluescreened.",
            "dialogue": "Holy crap, my brain just segfaulted!",
        }]

    def run(self) -> None:
        if self._prebuilt_prompt is not None:
            self.send(self._prebuilt_prompt)
