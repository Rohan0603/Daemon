from __future__ import annotations
import logging
import time
from typing import Any, Callable, Optional

import requests

logger = logging.getLogger(__name__)

TYPE_MAP = {
    str: "stringValue",
    bool: "booleanValue",
    int: "integerValue",
    float: "doubleValue",
}


class FirebaseCRUD:
    _RETRY_ATTEMPTS = 3
    _RETRY_BASE_DELAY = 0.5

    def __init__(
        self,
        token_provider: Callable[[], Optional[str]],
        project_id: str,
    ) -> None:
        self._token_provider = token_provider
        self._project_id = project_id
        self._base_url = (
            f"https://firestore.googleapis.com/v1/projects/{project_id}"
            f"/databases/(default)/documents"
        )
        self._available: bool = True

    @property
    def available(self) -> bool:
        return self._available

    # ── Auth header ──────────────────────────────────────────────────────────

    def _headers(self) -> dict:
        token = self._token_provider()
        if not token:
            self._available = False
            return {}
        return {"Authorization": f"Bearer {token}"}

    # ── Field conversion helpers ─────────────────────────────────────────────

    @staticmethod
    def _flatten_fields(fields: dict) -> dict:
        result = {}
        for key, value in fields.items():
            result[key] = FirebaseCRUD._flatten_value(value)
        return result

    @staticmethod
    def _flatten_value(value: dict) -> Any:
        if "stringValue" in value:
            return value["stringValue"]
        if "integerValue" in value:
            return int(value["integerValue"])
        if "doubleValue" in value:
            return value["doubleValue"]
        if "booleanValue" in value:
            return value["booleanValue"]
        if "nullValue" in value:
            return None
        if "arrayValue" in value:
            return [FirebaseCRUD._flatten_value(v) for v in value["arrayValue"].get("values", [])]
        if "mapValue" in value:
            return FirebaseCRUD._flatten_fields(value["mapValue"].get("fields", {}))
        return None

    @staticmethod
    def _unflatten_fields(data: dict) -> dict:
        fields = {}
        for key, value in data.items():
            fields[key] = FirebaseCRUD._unflatten_value(value)
        return fields

    @staticmethod
    def _unflatten_value(value: Any) -> dict:
        if isinstance(value, str):
            return {"stringValue": value}
        if isinstance(value, bool):
            return {"booleanValue": value}
        if isinstance(value, int):
            return {"integerValue": str(value)}
        if isinstance(value, float):
            return {"doubleValue": value}
        if isinstance(value, list):
            return {"arrayValue": {"values": [FirebaseCRUD._unflatten_value(v) for v in value]}}
        if value is None:
            return {"nullValue": None}
        if isinstance(value, dict):
            return {"mapValue": {"fields": FirebaseCRUD._unflatten_fields(value)}}
        return {"stringValue": str(value)}

    @staticmethod
    def _flatten_document(doc: dict) -> dict:
        result: dict = {}
        fields = doc.get("fields", {})
        for key, value in fields.items():
            result[key] = FirebaseCRUD._flatten_value(value)
        return result

    # ── Retry ────────────────────────────────────────────────────────────────

    def _with_retry(self, fn, *args, **kwargs):
        last_error = None
        for attempt in range(1, self._RETRY_ATTEMPTS + 1):
            try:
                return fn(*args, **kwargs)
            except requests.RequestException as e:
                last_error = e
                if attempt < self._RETRY_ATTEMPTS:
                    time.sleep(self._RETRY_BASE_DELAY * attempt)
            except Exception as e:
                last_error = e
                if attempt < self._RETRY_ATTEMPTS:
                    time.sleep(self._RETRY_BASE_DELAY)
        logger.warning("%s failed after %d attempts: %s", fn.__name__, self._RETRY_ATTEMPTS, last_error)
        self._available = False
        return None

    # ── Path helpers ─────────────────────────────────────────────────────────

    def _doc_path(self, collection: str, doc_id: str) -> str:
        return f"{self._base_url}/{collection}/{doc_id}"

    def _col_path(self, collection: str) -> str:
        return f"{self._base_url}/{collection}"

    # ── CRUD Methods ─────────────────────────────────────────────────────────

    def get(self, collection: str, doc_id: str) -> dict | None:
        def _do() -> dict | None:
            headers = self._headers()
            if not headers:
                return None
            resp = requests.get(self._doc_path(collection, doc_id), headers=headers, timeout=15)
            if resp.status_code == 404:
                return None
            if resp.status_code != 200:
                logger.warning("Firestore GET %s/%s: %d %s", collection, doc_id, resp.status_code, resp.text)
                if resp.status_code in (401, 403):
                    self._available = False
                    return None
                if 500 <= resp.status_code < 600:
                    raise requests.HTTPError(f"Server error {resp.status_code}", response=resp)
                return None
            return self._flatten_document(resp.json())
        return self._with_retry(_do)

    def set(self, collection: str, doc_id: str, data: dict, merge: bool = True) -> bool:
        def _do() -> bool:
            headers = self._headers()
            if not headers:
                return False
            if merge:
                existing = self.get(collection, doc_id)
                merged = dict(existing) if existing else {}
                merged.update(data)
                body = {"fields": self._unflatten_fields(merged)}
            else:
                body = {"fields": self._unflatten_fields(data)}
            resp = requests.patch(
                self._doc_path(collection, doc_id),
                json=body, headers=headers, timeout=15,
            )
            if resp.status_code not in (200, 201):
                logger.warning("Firestore PATCH %s/%s: %d %s", collection, doc_id, resp.status_code, resp.text)
                if resp.status_code in (401, 403):
                    self._available = False
                    return False
                if 500 <= resp.status_code < 600:
                    raise requests.HTTPError(f"Server error {resp.status_code}", response=resp)
                return False
            return True
        return bool(self._with_retry(_do))

    def add(self, collection: str, data: dict) -> str | None:
        def _do() -> str | None:
            headers = self._headers()
            if not headers:
                return None
            body = {"fields": self._unflatten_fields(data)}
            resp = requests.post(self._col_path(collection), json=body, headers=headers, timeout=15)
            if resp.status_code not in (200, 201):
                logger.warning("Firestore POST %s: %d %s", collection, resp.status_code, resp.text)
                if resp.status_code in (401, 403):
                    self._available = False
                    return None
                if 500 <= resp.status_code < 600:
                    raise requests.HTTPError(f"Server error {resp.status_code}", response=resp)
                return None
            doc_name = resp.json().get("name", "")
            return doc_name.split("/")[-1] if doc_name else None
        return self._with_retry(_do)

    def delete(self, collection: str, doc_id: str) -> bool:
        def _do() -> bool:
            headers = self._headers()
            if not headers:
                return False
            resp = requests.delete(self._doc_path(collection, doc_id), headers=headers, timeout=15)
            if resp.status_code == 404:
                return False
            if resp.status_code != 200:
                logger.warning("Firestore DELETE %s/%s: %d %s", collection, doc_id, resp.status_code, resp.text)
                if resp.status_code in (401, 403):
                    self._available = False
                    return False
                if 500 <= resp.status_code < 600:
                    raise requests.HTTPError(f"Server error {resp.status_code}", response=resp)
                return False
            return True
        return bool(self._with_retry(_do))

    def query(
        self,
        collection: str,
        order_by: str | None = None,
        limit: int | None = None,
        ascending: bool = True,
    ) -> list[dict]:
        def _do() -> list[dict]:
            headers = self._headers()
            if not headers:
                return []
            url = self._col_path(collection)
            params = {}
            if order_by:
                direction = "ASCENDING" if ascending else "DESCENDING"
                params["orderBy"] = f"{order_by} {direction}"
            if limit:
                params["pageSize"] = limit
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            if resp.status_code != 200:
                logger.warning("Firestore GET %s: %d %s", collection, resp.status_code, resp.text)
                if resp.status_code in (401, 403):
                    self._available = False
                    return []
                if 500 <= resp.status_code < 600:
                    raise requests.HTTPError(f"Server error {resp.status_code}", response=resp)
                return []
            return [self._flatten_document(d) for d in resp.json().get("documents", [])]
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
