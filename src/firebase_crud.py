from __future__ import annotations
import logging
import time

import firebase_admin
from firebase_admin import credentials, firestore
from src.constants import FIREBASE_CREDENTIALS_PATH
from src.config import load_config

logger = logging.getLogger(__name__)


class FirebaseCRUD:
    _RETRY_ATTEMPTS = 3
    _RETRY_BASE_DELAY = 0.5

    def __init__(self, creds_path: str | None = None):
        if creds_path is None:
            cfg = load_config()
            creds_path = cfg.get("firebase", {}).get("credentials_path", str(FIREBASE_CREDENTIALS_PATH))
        self._creds_path = creds_path
        self._client: firestore.Client | None = None
        self._available: bool = True

    @property
    def available(self) -> bool:
        return self._available

    @property
    def client(self) -> firestore.Client | None:
        return self._client

    def _ensure_client(self) -> None:
        if self._client is not None:
            return
        try:
            cred = credentials.Certificate(self._creds_path)
            try:
                firebase_admin.get_app()
            except ValueError:
                firebase_admin.initialize_app(cred)
            self._client = firestore.client()
        except FileNotFoundError:
            logger.warning("Firebase credentials not found at %s", self._creds_path)
            self._available = False
        except Exception as e:
            logger.warning("Firebase init failed: %s", e)
            self._available = False

    def _with_retry(self, fn, *args, **kwargs):
        last_error = None
        for attempt in range(1, self._RETRY_ATTEMPTS + 1):
            try:
                self._ensure_client()
                if not self._available:
                    return None
                return fn(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < self._RETRY_ATTEMPTS:
                    delay = self._RETRY_BASE_DELAY * attempt
                    logger.debug("Retry %d/%d for %s in %ss after: %s",
                                 attempt, self._RETRY_ATTEMPTS, fn.__name__, delay, e)
                    time.sleep(delay)
        logger.warning("%s failed after %d attempts: %s",
                       fn.__name__, self._RETRY_ATTEMPTS, last_error)
        return None

    def get(self, collection: str, doc_id: str) -> dict | None:
        def _do():
            doc = self._client.collection(collection).document(doc_id).get()
            return doc.to_dict() if doc.exists else None
        return self._with_retry(_do)

    def set(self, collection: str, doc_id: str, data: dict, merge: bool = True) -> bool:
        def _do():
            self._client.collection(collection).document(doc_id).set(data, merge=merge)
            return True
        result = self._with_retry(_do)
        return bool(result)

    def add(self, collection: str, data: dict) -> str | None:
        def _do():
            _ref, result = self._client.collection(collection).add(data)
            return result.id
        return self._with_retry(_do)

    def delete(self, collection: str, doc_id: str) -> bool:
        def _do():
            self._client.collection(collection).document(doc_id).delete()
            return True
        result = self._with_retry(_do)
        return bool(result)

    def query(
        self,
        collection: str,
        order_by: str | None = None,
        limit: int | None = None,
        ascending: bool = True,
    ) -> list[dict]:
        def _do():
            ref = self._client.collection(collection)
            if order_by:
                direction = firestore.Query.ASCENDING if ascending else firestore.Query.DESCENDING
                ref = ref.order_by(order_by, direction=direction)
            if limit:
                ref = ref.limit(limit)
            return [doc.to_dict() for doc in ref.stream()]
        result = self._with_retry(_do)
        return result or []

    def read_all_text(
        self,
        collection: str,
        text_field: str = "text",
        order_by: str | None = None,
        limit: int | None = None,
        ascending: bool = True,
    ) -> list[str]:
        docs = self.query(collection, order_by=order_by, limit=limit, ascending=ascending)
        return [d[text_field] for d in docs if d.get(text_field)]
