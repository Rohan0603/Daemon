from __future__ import annotations
import json
import logging
import time
from pathlib import Path
from typing import Optional

import requests

from src.constants import FIREBASE_PROJECT_ID, AUTH_TOKEN_PATH
from src.config import load_config
from src.events import Event, EventBus, EventType

logger = logging.getLogger(__name__)

IDENTITY_TOOLKIT_URL = "https://identitytoolkit.googleapis.com/v1/accounts"
SECURE_TOKEN_URL = "https://securetoken.googleapis.com/v1/token"
TOKEN_REFRESH_MARGIN_SEC = 60


class FirebaseAuth:
    def __init__(
        self,
        api_key: str = "",
        project_id: str = "",
        token_path: Path | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        if not api_key:
            cfg = load_config()
            self._api_key = cfg.get("firebase", {}).get("api_key", "")
        else:
            self._api_key = api_key
        if not project_id:
            cfg = load_config()
            self._project_id = cfg.get("firebase", {}).get("project_id", FIREBASE_PROJECT_ID)
        else:
            self._project_id = project_id
        self._token_path = Path(token_path) if token_path else Path(AUTH_TOKEN_PATH)
        self._event_bus = event_bus

        self._uid: Optional[str] = None
        self._email: Optional[str] = None
        self._id_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._expires_at: float = 0.0

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

    def _auth_request(self, endpoint: str, email: str, password: str) -> Optional[str]:
        try:
            resp = requests.post(
                f"{IDENTITY_TOOLKIT_URL}:{endpoint}?key={self._api_key}",
                json={"email": email, "password": password, "returnSecureToken": True},
                timeout=15,
            )
        except requests.RequestException as e:
            logger.warning("[FirebaseAuth] %s network error: %s", endpoint, e)
            self._publish_auth_failure(f"network_error: {e}")
            return None

        if resp.status_code != 200:
            logger.warning("[FirebaseAuth] %s failed: %s", endpoint, resp.text)
            self._publish_auth_failure(f"http_{resp.status_code}")
            return None

        data = resp.json()
        if "localId" not in data:
            logger.warning("[FirebaseAuth] %s returned 200 but missing localId", endpoint)
            self._publish_auth_failure("missing_local_id")
            return None

        self._set_tokens(data)
        self.save()
        return self._uid

    def sign_in(self, email: str, password: str) -> Optional[str]:
        return self._auth_request("signInWithPassword", email, password)

    def sign_up(self, email: str, password: str) -> Optional[str]:
        return self._auth_request("signUp", email, password)

    def refresh(self) -> bool:
        if not self._refresh_token:
            return False
        try:
            resp = requests.post(
                f"{SECURE_TOKEN_URL}?key={self._api_key}",
                json={"grant_type": "refresh_token", "refresh_token": self._refresh_token},
                timeout=15,
            )
        except requests.RequestException as e:
            logger.warning("[FirebaseAuth] refresh network error: %s", e)
            return False

        if resp.status_code != 200:
            logger.warning("[FirebaseAuth] refresh failed: %s", resp.text)
            self.clear()
            return False

        data = resp.json()
        self._id_token = data["id_token"]
        self._refresh_token = data.get("refresh_token", self._refresh_token)
        self._expires_at = time.time() + int(data.get("expires_in", 3600))
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
            self._token_path.write_text(json.dumps(data), encoding="utf-8")
        except OSError as e:
            logger.warning("[FirebaseAuth] failed to save token: %s", e)

    def load(self) -> bool:
        try:
            data = json.loads(self._token_path.read_text(encoding="utf-8"))
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
