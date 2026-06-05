from __future__ import annotations
import json
import logging
import re
import requests
from PyQt6.QtCore import QThread, pyqtSignal
from pathlib import Path
from src.constants import (
    OPENCODE_SERVER_URL,
    OPENCODE_API_MODEL_PROVIDER,
    OPENCODE_API_MODEL_ID,
    OPENCODE_API_TIMEOUT_SEC,
)


logger = logging.getLogger(__name__)


# Cached once at import time to avoid re-reading the skill file on every prompt build.
try:
    _SKILL_CONTENT = (Path(__file__).parent.parent / "assets" / "daemon-skill.md").read_text(encoding="utf-8")
except Exception:
    _SKILL_CONTENT = ""


def _process_output(text: str) -> str:
    stripped = re.sub(r'[*#`~_]', '', text.strip())
    if len(stripped) > 280:
        return stripped[:280] + "\u2026 (see terminal for full output)"
    return stripped


def _parse_json_response(text: str) -> dict | None:
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end > start:
        try:
            data = json.loads(text[start:end + 1])
            if isinstance(data, dict) and "dialogue" in data:
                return data
        except (json.JSONDecodeError, ValueError):
            pass
    # Fallback: regex field extraction for JS-style objects with unquoted keys/values
    dialogue_m = re.search(r'"?dialogue"?\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    if not dialogue_m:
        # Unquoted value: capture up to next "key:" or closing brace
        dialogue_m = re.search(r'"?dialogue"?\s*:\s*([^{}]+?)(?=\s*,\s*\w+\s*:|\s*\})', text, re.DOTALL)
    if not dialogue_m:
        return None
    action_m = re.search(r'"?action"?\s*:\s*"?([A-Za-z_]+)"?', text)
    target_m = re.search(r'"?target(?:_x)?"?\s*:\s*(-?\d+)', text)
    return {
        "dialogue": dialogue_m.group(1).strip(),
        "action": action_m.group(1) if action_m else "idle",
        "target_x": int(target_m.group(1)) if target_m else 0,
    }


def _parse_json_batch(text: str) -> list[dict]:
    """Parse a JSON array of response objects. Falls back to single-object parse."""
    arr_start = text.find('[')
    arr_end = text.rfind(']')
    if arr_start != -1 and arr_end > arr_start:
        try:
            data = json.loads(text[arr_start:arr_end + 1])
            if isinstance(data, list) and all(
                isinstance(item, dict) and "dialogue" in item for item in data
            ):
                return data
        except (json.JSONDecodeError, ValueError):
            pass
        # Fallback: split array by brace depth and parse each object individually
        inner = text[arr_start + 1:arr_end]
        results = []
        depth = 0
        start = -1
        for i, ch in enumerate(inner):
            if ch == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and start != -1:
                    obj_text = inner[start:i + 1]
                    parsed = _parse_json_response(obj_text)
                    if parsed and parsed.get("dialogue"):
                        results.append(parsed)
                    start = -1
        if results:
            return results
    single = _parse_json_response(text)
    return [single] if single else []


FORMAT_INSTRUCTIONS = """Respond ONLY with valid JSON. No markdown, no preamble, no text outside the JSON.

Single-query format (user responding):
{"thought":"...","dialogue":"...","action":"<action>","target_x":<int or null>,"priority":<1-5>}

User query may ALSO include pool items (2 jokes/roasts + 2 system observations):
{"thought":"...","dialogue":"...","action":"idle","priority":4,
 "jokes_blackmail_items":[
   {"dialogue":"...","action":"idle","priority":3},
   {"dialogue":"...","action":"shake","priority":4}
 ],
 "system_items":[
   {"dialogue":"...","action":"idle","priority":5},
   {"dialogue":"...","action":"wander","priority":2}
 ]}

Autonomous batch format \u2014 return array with priority on each item:
[{"dialogue":"...","action":"<action>","target_x":<int or null>,"priority":<1-5>}, ...]

Rules:
- dialogue: \u226420 words
- action: one of idle/wander/celebrate/devastated/hyper/shake/bounce/spin/look_away
- target_x: integer (for wander) or null (for other actions)
- priority: integer 1-5 \u2014 higher = more likely to be shown. Priority decays over time.
- Keys and strings use double quotes. No trailing commas.
- For user queries: single object. For autonomous: array."""

VALID_ACTIONS = {
    "idle", "wander", "celebrate", "devastated",
    "hyper", "shake", "bounce", "spin", "look_away",
}


class OpencodeWorker(QThread):
    trigger_ready = pyqtSignal(list)
    context_injected = pyqtSignal()
    injection_failed = pyqtSignal(str)

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
        self._injection_in_flight = False

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
                logger.debug("API response had no text parts (expected for noReply)")
                return ""
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

    def inject_context(self, prompt: str) -> None:
        if self._injection_in_flight:
            logger.debug("inject_context: already in flight, skipping")
            return
        self._injection_in_flight = True
        try:
            payload = {"noReply": True, "parts": [{"type": "text", "text": prompt}]}
            raw = self._post_message(payload)
            if raw is not None:
                self.context_injected.emit()
            else:
                self.injection_failed.emit("No response from server")
        except Exception as e:
            self.injection_failed.emit(str(e))
        finally:
            self._injection_in_flight = False

    def send_trigger(self, prompt: str) -> None:
        payload = {
            "model": {
                "providerID": OPENCODE_API_MODEL_PROVIDER,
                "modelID": OPENCODE_API_MODEL_ID,
            },
            "parts": [{"type": "text", "text": prompt}],
        }
        raw = self._post_message(payload)
        if raw:
            self._used_api = True
            self.path_used.emit("api")
            self._process_raw_output(raw)
        else:
            logger.warning("send_trigger: API returned empty or None")

    def _process_raw_output(self, raw: str) -> None:
        raw_stripped = raw.strip()
        if raw_stripped.startswith('{') and not raw_stripped.startswith('['):
            single = _parse_json_response(raw)
            parsed_items = [single] if single else []
        else:
            parsed_items = _parse_json_batch(raw)
        logger.debug("PARSED_ITEMS: count=%d | raw_len=%s", len(parsed_items), len(raw))
        if parsed_items:
            brain_updates = []
            for item in parsed_items:
                bu = item.pop("brain_update", None)
                if bu is not None and isinstance(bu, dict):
                    brain_updates.append(bu)

            normalized = self._normalize_parsed(parsed_items)

            for bu in brain_updates:
                self.brain_update_ready.emit(bu)

            pool_items = {}
            if parsed_items:
                item = parsed_items[0]
                if "jokes_blackmail_items" in item or "system_items" in item:
                    pool_items["jokes_blackmail"] = item.get("jokes_blackmail_items", [])
                    pool_items["system"] = item.get("system_items", [])
                    if pool_items["jokes_blackmail"] or pool_items["system"]:
                        logger.info("Emitting pool_items_ready: jokes=%d, system=%d",
                                    len(pool_items["jokes_blackmail"]), len(pool_items["system"]))
                        self.pool_items_ready.emit(pool_items)

            logger.info("Emitting trigger_ready: %d items", len(normalized))
            self.trigger_ready.emit(normalized)
        else:
            processed = _process_output(raw)
            logger.info("Emitting trigger_ready (fallback): '%s'", processed)
            self.trigger_ready.emit([{
                "dialogue": processed,
                "action": "idle",
                "target_x": 0,
                "priority": 3,
            }])

    def _normalize_parsed(self, items: list[dict]) -> list[dict]:
        normalized = []
        for item in items:
            dialogue = re.sub(r'[*#`~_]', '', item.get("dialogue", "")).strip()
            action = str(item.get("action", "idle")).lower().strip()
            if action not in VALID_ACTIONS:
                logger.debug("invalid action '%s' -> idle", action)
                action = "idle"
            try:
                target_x = int(item.get("target_x") or 0)
            except (ValueError, TypeError):
                target_x = 0
            priority = int(item.get("priority", 3))
            normalized.append({
                "dialogue": dialogue,
                "action": action,
                "target_x": target_x,
                "priority": priority,
                "thought": item.get("thought", ""),
            })
        return normalized

    def run(self) -> None:
        if self._prebuilt_prompt is not None:
            self.send_trigger(self._prebuilt_prompt)
