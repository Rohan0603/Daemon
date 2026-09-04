from __future__ import annotations
import json
import logging
import time
import base64
import ctypes
import os
from pathlib import Path
from typing import Optional

import requests

from src.constants import FIREBASE_PROJECT_ID, AUTH_TOKEN_PATH
from src.config import load_config
from src.events import Event, EventBus, EventType

logger = logging.getLogger(__name__)

TOKEN_REFRESH_MARGIN_SEC = 60


def _protect(data: str) -> dict:
    if os.name != "nt":
        return {"format": "plain-v1", "payload": data}
    try:
        class Blob(ctypes.Structure):
            _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

        raw = data.encode("utf-8")
        source = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
        input_blob = Blob(len(raw), source)
        output_blob = Blob()
        if not ctypes.windll.crypt32.CryptProtectData(ctypes.byref(input_blob), None, None, None, None, 0, ctypes.byref(output_blob)):
            raise OSError("CryptProtectData failed")
        try:
            protected = ctypes.string_at(output_blob.pbData, output_blob.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(output_blob.pbData)
        return {"format": "dpapi-v1", "payload": base64.b64encode(protected).decode("ascii")}
    except (AttributeError, OSError):
        logger.warning("Windows token protection unavailable; using development fallback")
        return {"format": "plain-v1", "payload": data}


def _unprotect(data: dict) -> str:
    if data.get("format") != "dpapi-v1":
        return data.get("payload", json.dumps(data)) if data.get("format") == "plain-v1" else json.dumps(data)
    if os.name != "nt":
        raise OSError("DPAPI token cannot be decrypted on this platform")
    class Blob(ctypes.Structure):
        _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]
    protected = base64.b64decode(data["payload"])
    source = (ctypes.c_ubyte * len(protected)).from_buffer_copy(protected)
    input_blob = Blob(len(protected), source)
    output_blob = Blob()
    if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(input_blob), None, None, None, None, 0, ctypes.byref(output_blob)):
        raise OSError("CryptUnprotectData failed")
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(output_blob.pbData)


class FirebaseAuth:
    def __init__(
        self,
        api_key: str = "",
        project_id: str = "",
        token_path: Path | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        if not project_id:
            cfg = load_config(validate=False)
            self._project_id = cfg.get("firebase", {}).get("project_id", FIREBASE_PROJECT_ID)
        else:
            self._project_id = project_id
        cfg = load_config(validate=False)
        self._auth_backend_url = cfg.get("firebase", {}).get("auth_backend_url", "").rstrip("/")
        self._token_path = Path(token_path) if token_path else Path(AUTH_TOKEN_PATH)
        self._event_bus = event_bus

        self._uid: Optional[str] = None
        self._email: Optional[str] = None
        self._id_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._expires_at: float = 0.0
        self._last_error_code: Optional[str] = None

    @property
    def uid(self) -> Optional[str]:
        return self._uid

    @property
    def email(self) -> Optional[str]:
        return self._email

    @property
    def id_token(self) -> Optional[str]:
        return self._id_token

    @property
    def refresh_token(self) -> Optional[str]:
        return self._refresh_token

    @property
    def auth_backend_url(self) -> str:
        return self._auth_backend_url

    @property
    def last_error_code(self) -> Optional[str]:
        return self._last_error_code

    def _auth_request(
        self, endpoint: str, email: str, password: str, remember_me: bool = True
    ) -> Optional[str]:
        self._last_error_code = None
        if not self._auth_backend_url:
            logger.warning("[FirebaseAuth] auth backend URL is not configured")
            self._last_error_code = "backend_not_configured"
            self._publish_auth_failure("backend_not_configured")
            return None
        return self._backend_auth_request(endpoint, email, password, remember_me)

    def _backend_auth_request(
        self, endpoint: str, email: str, password: str, remember_me: bool
    ) -> Optional[str]:
        try:
            resp = requests.post(
                f"{self._auth_backend_url}/auth/{'sign-in' if endpoint == 'signInWithPassword' else 'sign-up'}",
                json={"email": email, "password": password},
                timeout=15,
            )
        except requests.RequestException as exc:
            logger.warning("[FirebaseAuth] auth backend network error: %s", exc)
            self._last_error_code = "backend_network_error"
            self._publish_auth_failure("backend_network_error")
            return None
        if resp.status_code != 200:
            logger.warning("[FirebaseAuth] auth backend failed: HTTP %s", resp.status_code)
            try:
                payload = resp.json()
                error = payload.get("error", payload) if isinstance(payload, dict) else {}
                code = error.get("message") if isinstance(error, dict) else None
            except (ValueError, TypeError):
                code = None
            self._last_error_code = code or f"backend_http_{resp.status_code}"
            self._publish_auth_failure(f"backend_http_{resp.status_code}")
            return None
        try:
            data = resp.json()
            data["localId"] = data.get("localId") or data["uid"]
            data["idToken"] = data.get("idToken") or data["id_token"]
            data["refreshToken"] = data.get("refreshToken") or data["refresh_token"]
            data["expiresIn"] = data.get("expiresIn") or data.get("expires_in", 3600)
        except (ValueError, KeyError, TypeError):
            logger.warning("[FirebaseAuth] auth backend returned invalid token payload")
            self._last_error_code = "backend_invalid_response"
            self._publish_auth_failure("backend_invalid_response")
            return None
        self._set_tokens(data)
        if remember_me:
            self.save()
        else:
            try:
                self._token_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("[FirebaseAuth] failed to remove non-persistent token file")
        return self._uid

    def sign_in(self, email: str, password: str, remember_me: bool = True) -> Optional[str]:
        return self._auth_request("signInWithPassword", email, password, remember_me)

    def sign_up(self, email: str, password: str, remember_me: bool = True) -> Optional[str]:
        return self._auth_request("signUp", email, password, remember_me)

    def refresh(self) -> bool:
        if not self._refresh_token:
            return False
        if not self._auth_backend_url:
            logger.warning("[FirebaseAuth] auth backend URL is not configured")
            return False
        try:
            resp = requests.post(
                f"{self._auth_backend_url}/auth/refresh",
                json={"refresh_token": self._refresh_token},
                timeout=15,
            )
        except requests.RequestException as exc:
            logger.warning("[FirebaseAuth] auth backend refresh network error: %s", exc)
            return False

        if resp.status_code != 200:
            logger.warning("[FirebaseAuth] auth backend refresh failed: HTTP %s", resp.status_code)
            return False
        try:
            data = resp.json()
            self._id_token = data["id_token"]
            self._refresh_token = data.get("refresh_token", self._refresh_token)
            self._expires_at = time.time() + int(data.get("expires_in", 3600))
        except (ValueError, KeyError, TypeError):
            logger.warning("[FirebaseAuth] auth backend refresh returned invalid token payload")
            return False
        self.save()
        self._publish_token_refreshed()
        return True

    def get_valid_token(self) -> Optional[str]:
        if self._id_token and time.time() < self._expires_at - TOKEN_REFRESH_MARGIN_SEC:
            return self._id_token
        if self._refresh_token:
            if self.refresh():
                return self._id_token
        return None

    def save(self) -> None:
        data = {
            "uid": self._uid,
            "email": self._email,
            "idToken": self._id_token,
            "refreshToken": self._refresh_token,
            "expires_at": self._expires_at,
        }
        try:
            self._token_path.parent.mkdir(parents=True, exist_ok=True)
            payload = _protect(json.dumps(data))
            self._token_path.write_text(json.dumps(payload), encoding="utf-8")
        except OSError as e:
            logger.warning("[FirebaseAuth] failed to save token: %s", e)

    def load(self) -> bool:
        try:
            stored = json.loads(self._token_path.read_text(encoding="utf-8"))
            data = json.loads(_unprotect(stored))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return False

        self._uid = data.get("uid")
        self._email = data.get("email")
        self._id_token = data.get("idToken")
        self._refresh_token = data.get("refreshToken")
        self._expires_at = data.get("expires_at", 0.0)
        return self._uid is not None

    def is_authenticated(self) -> bool:
        return bool(self._uid and self._id_token)

    def clear(self) -> None:
        self._uid = None
        self._email = None
        self._id_token = None
        self._refresh_token = None
        self._expires_at = 0.0
        try:
            self._token_path.unlink(missing_ok=True)
        except OSError:
            pass
        if self._event_bus:
            self._event_bus.publish(Event(
                type=EventType.AUTH_CLEARED,
                source="firebase_auth",
                data={}
            ))

    def sign_out(self) -> None:
        self.clear()

    def _set_tokens(self, data: dict) -> None:
        self._uid = data.get("localId")
        self._email = data.get("email")
        self._id_token = data.get("idToken")
        self._refresh_token = data.get("refreshToken")
        expires_in = int(data.get("expiresIn", 3600))
        self._expires_at = time.time() + expires_in
        if self._event_bus:
            self._event_bus.publish(Event(
                type=EventType.AUTH_SUCCESS,
                source="firebase_auth",
                data={"uid": self._uid, "email": self._email}
            ))

    def _publish_auth_failure(self, reason: str) -> None:
        if self._event_bus:
            self._event_bus.publish(Event(
                type=EventType.AUTH_FAILURE,
                source="firebase_auth",
                data={"reason": reason}
            ))

    def _publish_token_refreshed(self) -> None:
        if self._event_bus:
            self._event_bus.publish(Event(
                type=EventType.TOKEN_REFRESHED,
                source="firebase_auth",
                data={"uid": self._uid}
            ))
