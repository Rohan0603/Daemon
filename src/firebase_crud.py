from __future__ import annotations

import logging
import time
from typing import Sequence

import requests

logger = logging.getLogger(__name__)


class FirebaseCRUD:
    _RETRY_ATTEMPTS = 3
    _RETRY_BASE_DELAY = 0.5

    def __init__(self, auth=None, project_id: str | None = None, database_id: str = "(default)"):
        self._auth = auth
        self._project_id = project_id or ""
        self._database_id = database_id
        backend_url = getattr(auth, "auth_backend_url", "")
        self._backend_url = backend_url.rstrip("/") if isinstance(backend_url, str) else ""
        self._session = requests.Session()
        self._available = bool(self._auth and self._backend_url)
        self._last_status: int | None = None

    @property
    def available(self) -> bool:
        return self._available

    @property
    def client(self):
        return None

    def _token(self) -> str | None:
        return self._auth.get_valid_token() if self._auth else None

    def _request(self, method: str, endpoint: str, **kwargs):
        token = self._token()
        if not token or not self._backend_url:
            self._last_status = 401
            return None
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {token}"
        headers.setdefault("Content-Type", "application/json")
        url = f"{self._backend_url}/{endpoint.strip('/')}"
        response = self._session.request(method, url, headers=headers, timeout=15, **kwargs)
        self._last_status = response.status_code
        auth = self._auth
        if response.status_code == 401 and auth is not None and hasattr(auth, "refresh") and auth.refresh():
            refreshed = self._token()
            if refreshed:
                headers["Authorization"] = f"Bearer {refreshed}"
                response = self._session.request(method, url, headers=headers, timeout=15, **kwargs)
                self._last_status = response.status_code
        return response

    @staticmethod
    def _decode_value(value: dict):
        if "nullValue" in value:
            return None
        if "booleanValue" in value:
            return value["booleanValue"]
        if "integerValue" in value:
            return int(value["integerValue"])
        if "doubleValue" in value:
            return value["doubleValue"]
        if "stringValue" in value:
            return value["stringValue"]
        if "arrayValue" in value:
            return [FirebaseCRUD._decode_value(item) for item in value["arrayValue"].get("values", [])]
        if "mapValue" in value:
            return FirebaseCRUD._decode_fields(value["mapValue"].get("fields", {}))
        return None

    @staticmethod
    def _decode_fields(fields: dict) -> dict:
        return {key: FirebaseCRUD._decode_value(value) for key, value in fields.items()}

    @staticmethod
    def _payload_data(payload):
        if not isinstance(payload, dict):
            return None
        if isinstance(payload.get("data"), dict):
            return payload["data"]
        if isinstance(payload.get("fields"), dict):
            return FirebaseCRUD._decode_fields(payload["fields"])
        return payload

    @staticmethod
    def _payload_documents(payload) -> list[dict]:
        rows = payload.get("documents", []) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return []
        documents: list[dict] = []
        for row in rows:
            if isinstance(row, dict) and "document" in row:
                documents.append(FirebaseCRUD._decode_fields(row.get("document", {}).get("fields", {})))
            elif isinstance(row, dict):
                documents.append(row)
        return documents

    def _with_retry(self, fn, *args, **kwargs):
        last_error = None
        for attempt in range(1, self._RETRY_ATTEMPTS + 1):
            try:
                if not self._available:
                    return None
                return fn(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < self._RETRY_ATTEMPTS:
                    delay = self._RETRY_BASE_DELAY * attempt
                    logger.debug(
                        "Retry %d/%d for %s in %ss after: %s",
                        attempt, self._RETRY_ATTEMPTS, fn.__name__, delay, e,
                    )
                    time.sleep(delay)
        logger.warning("%s failed after %d attempts: %s", fn.__name__, self._RETRY_ATTEMPTS, last_error)
        return None

    def get(self, collection: str, doc_id: str) -> dict | None:
        def _do():
            response = self._request(
                "GET",
                "data/document",
                params={"collection": collection, "doc_id": doc_id},
            )
            if response is None or response.status_code == 404:
                return None
            response.raise_for_status()
            return self._payload_data(response.json())
        return self._with_retry(_do)

    def set(self, collection: str, doc_id: str, data: dict, merge: bool = True) -> bool:
        def _do():
            response = self._request(
                "PATCH",
                "data/document",
                json={"collection": collection, "doc_id": doc_id, "data": data, "merge": merge},
            )
            if response is None:
                return False
            response.raise_for_status()
            return True
        return bool(self._with_retry(_do))

    def add(self, collection: str, data: dict) -> str | None:
        def _do():
            response = self._request("POST", "data/collection", json={"collection": collection, "data": data})
            if response is None:
                return None
            response.raise_for_status()
            payload = response.json()
            return payload.get("id") or payload.get("doc_id") or payload.get("name", "").rsplit("/", 1)[-1] or None
        return self._with_retry(_do)

    def batch_add(self, collection: str, items: list[dict]) -> bool:
        def _do():
            response = self._request("POST", "data/batch", json={"collection": collection, "items": items})
            if response is None:
                return False
            response.raise_for_status()
            return True
        return bool(self._with_retry(_do))

    def delete(self, collection: str, doc_id: str) -> bool:
        def _do():
            response = self._request(
                "DELETE",
                "data/document",
                params={"collection": collection, "doc_id": doc_id},
            )
            if response is None:
                return False
            response.raise_for_status()
            return True
        return bool(self._with_retry(_do))

    def query(
        self,
        collection: str,
        order_by: str | None = None,
        limit: int | None = None,
        ascending: bool = True,
    ) -> list[dict]:
        def _do():
            params: dict[str, object] = {"collection": collection, "ascending": str(ascending).lower()}
            if order_by:
                params["order_by"] = order_by
            if limit:
                params["limit"] = limit
            response = self._request("GET", "data/query", params=params)
            if response is None:
                return []
            response.raise_for_status()
            return self._payload_documents(response.json())
        return self._with_retry(_do) or []

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

    def find_nearest_vector(
        self,
        collection: str,
        vector: Sequence[float],
        *,
        limit: int = 5,
        vector_field: str = "embedding",
        distance_measure: str = "COSINE",
        category_field: str | None = None,
        category_value: str | None = None,
    ) -> list[dict]:
        """Run a backend-mediated vector query with an optional category filter."""
        if not vector:
            raise ValueError("vector must not be empty")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if distance_measure not in {"COSINE", "EUCLIDEAN", "DOT_PRODUCT"}:
            raise ValueError("unsupported distance measure")
        if (category_field is None) != (category_value is None):
            raise ValueError("category_field and category_value must be provided together")

        def _do():
            response = self._request(
                "POST",
                "data/vector-search",
                json={
                    "collection": collection,
                    "vector": [float(value) for value in vector],
                    "limit": limit,
                    "vector_field": vector_field,
                    "distance_measure": distance_measure,
                    "category_field": category_field,
                    "category_value": category_value,
                },
            )
            if response is None:
                return []
            response.raise_for_status()
            return self._payload_documents(response.json())

        return self._with_retry(_do) or []
